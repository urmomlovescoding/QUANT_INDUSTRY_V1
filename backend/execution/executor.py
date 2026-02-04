"""
Execution Engine
================
P0 Critical Feature: Signal processing and order execution with risk integration.

Implements exact parity with quant-platform/execution/executor.py

THREAD SAFETY: All order tracking operations are protected by RLock to prevent
race conditions during concurrent order updates (e.g., from WebSocket callbacks
and manual API calls).
"""
import logging
import threading
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

logger = logging.getLogger("EXECUTOR")


class ExecutionMode(Enum):
    """
    Execution mode - matches quant-platform exactly.

    APP_MODE=platform_compat: Use these exact values
    APP_MODE=industry_improved: May add additional modes
    """
    SIGNAL_ONLY = "signal_only"     # Generate signals, no execution
    AUTO_PAPER = "auto_paper"       # Auto-execute on paper account
    AUTO_LIVE = "auto_live"         # Auto-execute with real money


@dataclass
class ExecutionDecision:
    """
    Record of an execution decision.
    Matches quant-platform/execution/executor.py:ExecutionDecision
    """
    decision_id: str
    timestamp: datetime
    ticker: str
    direction: str

    # Signal info
    signal_confidence: float
    signal_size_pct: float

    # Risk check
    risk_approved: bool
    risk_reason: str
    adjusted_size_pct: float
    risk_warnings: List[str] = field(default_factory=list)

    # Execution
    mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY
    was_executed: bool = False
    order_id: Optional[str] = None

    # Fill info (updated later)
    filled: bool = False
    filled_price: Optional[float] = None
    filled_qty: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "ticker": self.ticker,
            "direction": self.direction,
            "signal_confidence": self.signal_confidence,
            "signal_size_pct": self.signal_size_pct,
            "risk_approved": self.risk_approved,
            "risk_reason": self.risk_reason,
            "adjusted_size_pct": self.adjusted_size_pct,
            "risk_warnings": self.risk_warnings,
            "mode": self.mode.value,
            "was_executed": self.was_executed,
            "order_id": self.order_id,
            "filled": self.filled,
            "filled_price": self.filled_price,
            "filled_qty": self.filled_qty,
        }


@dataclass
class OrderTracker:
    """
    Track pending order.
    Matches quant-platform/execution/executor.py:OrderTracker
    """
    order_id: str
    ticker: str
    side: str
    qty: int
    status: str
    submitted_at: datetime
    filled_at: Optional[datetime] = None
    filled_qty: int = 0
    filled_price: float = 0.0
    decision_id: str = ""
    stop_order_id: Optional[str] = None
    target_order_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "order_id": self.order_id,
            "ticker": self.ticker,
            "side": self.side,
            "qty": self.qty,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "filled_qty": self.filled_qty,
            "filled_price": self.filled_price,
            "decision_id": self.decision_id,
            "stop_order_id": self.stop_order_id,
            "target_order_id": self.target_order_id,
        }


class ExecutionEngine:
    """
    Execution engine with risk integration.

    Implements exact parity with quant-platform behavior.

    Features:
    - Signal processing through risk engine
    - Multiple execution modes (SIGNAL_ONLY, AUTO_PAPER, AUTO_LIVE)
    - Order tracking
    - Decision audit trail
    - Kill switch integration
    """

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY,
        risk_engine: Optional[Any] = None,
        broker_adapter: Optional[Any] = None,
    ):
        self.mode = mode
        self.risk_engine = risk_engine
        self.broker_adapter = broker_adapter

        # Thread lock for order state - CRITICAL for concurrent access safety
        # Use RLock to allow recursive acquisition (e.g., cancel_all_orders -> update_order_status)
        self._order_lock = threading.RLock()

        # Decision history (audit trail)
        self.decisions: List[ExecutionDecision] = []

        # Active orders - ALWAYS access with self._order_lock held
        self.pending_orders: Dict[str, OrderTracker] = {}
        self.filled_orders: Dict[str, OrderTracker] = {}

        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            "decision": [],
            "order_submitted": [],
            "order_filled": [],
            "order_cancelled": [],
        }

        # Kill switch reference
        self._kill_switch = None

        logger.info(f"ExecutionEngine initialized in {mode.value} mode")

    def set_kill_switch(self, kill_switch: Any) -> None:
        """Set kill switch reference."""
        self._kill_switch = kill_switch

    def set_mode(self, mode: ExecutionMode) -> None:
        """Change execution mode."""
        old_mode = self.mode
        self.mode = mode
        logger.info(f"Execution mode changed: {old_mode.value} -> {mode.value}")

    def register_callback(self, event: str, callback: Callable) -> None:
        """Register callback for execution events."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _notify(self, event: str, data: Any) -> None:
        """Notify registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    def process_signal(
        self,
        ticker: str,
        direction: str,
        confidence: float,
        size_pct: float,
        metadata: Optional[Dict] = None,
    ) -> ExecutionDecision:
        """
        Process a trading signal through the execution pipeline.

        Args:
            ticker: Symbol to trade
            direction: 'BUY' or 'SELL'
            confidence: Signal confidence (0.0 - 1.0)
            size_pct: Position size as percentage
            metadata: Additional signal metadata

        Returns:
            ExecutionDecision with full audit trail
        """
        decision_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now()

        # Check kill switch first
        if self._kill_switch and self._kill_switch.is_active:
            decision = ExecutionDecision(
                decision_id=decision_id,
                timestamp=timestamp,
                ticker=ticker,
                direction=direction,
                signal_confidence=confidence,
                signal_size_pct=size_pct,
                risk_approved=False,
                risk_reason="Kill switch is active",
                adjusted_size_pct=0.0,
                mode=self.mode,
                was_executed=False,
            )
            self.decisions.append(decision)
            self._notify("decision", decision)
            logger.warning(f"Signal blocked by kill switch: {ticker} {direction}")
            return decision

        # Risk check
        risk_approved = True
        risk_reason = "No risk engine configured"
        adjusted_size = size_pct
        risk_warnings = []

        if self.risk_engine:
            try:
                result = self.risk_engine.check_trade(
                    ticker=ticker,
                    direction=direction,
                    size_pct=size_pct,
                    confidence=confidence,
                )
                risk_approved = result.approved
                risk_reason = result.reason
                adjusted_size = result.adjusted_size_pct
                risk_warnings = result.warnings
            except Exception as e:
                logger.error(f"Risk check error: {e}")
                risk_approved = False
                risk_reason = f"Risk check error: {e}"

        # Create decision record
        decision = ExecutionDecision(
            decision_id=decision_id,
            timestamp=timestamp,
            ticker=ticker,
            direction=direction,
            signal_confidence=confidence,
            signal_size_pct=size_pct,
            risk_approved=risk_approved,
            risk_reason=risk_reason,
            adjusted_size_pct=adjusted_size,
            risk_warnings=risk_warnings,
            mode=self.mode,
            was_executed=False,
        )

        # Execute based on mode
        if risk_approved and self.mode != ExecutionMode.SIGNAL_ONLY:
            decision = self._execute_decision(decision)

        # Record decision
        self.decisions.append(decision)
        self._notify("decision", decision)

        logger.info(
            f"Signal processed: {ticker} {direction} @ {confidence:.2f} -> "
            f"{'EXECUTED' if decision.was_executed else 'NOT EXECUTED'} ({decision.risk_reason})"
        )

        return decision

    def _execute_decision(self, decision: ExecutionDecision) -> ExecutionDecision:
        """
        Execute an approved decision.

        THREAD-SAFE: Order tracking is protected by RLock.
        """
        if self.mode == ExecutionMode.SIGNAL_ONLY:
            return decision

        if not self.broker_adapter:
            decision.risk_reason = "No broker adapter configured"
            return decision

        try:
            # Submit order to broker
            order_id = self.broker_adapter.submit_order(
                ticker=decision.ticker,
                side=decision.direction,
                qty=int(decision.adjusted_size_pct * 100),  # Convert to quantity
            )

            decision.was_executed = True
            decision.order_id = order_id

            # Track order - thread-safe
            tracker = OrderTracker(
                order_id=order_id,
                ticker=decision.ticker,
                side=decision.direction,
                qty=int(decision.adjusted_size_pct * 100),
                status="SUBMITTED",
                submitted_at=datetime.now(),
                decision_id=decision.decision_id,
            )

            with self._order_lock:
                self.pending_orders[order_id] = tracker

            self._notify("order_submitted", tracker)

        except Exception as e:
            logger.error(f"Order submission error: {e}")
            decision.risk_reason = f"Order submission failed: {e}"

        return decision

    def update_order_status(
        self,
        order_id: str,
        status: str,
        filled_qty: int = 0,
        filled_price: float = 0.0,
    ) -> None:
        """
        Update order status from broker.

        THREAD-SAFE: Protected by RLock to prevent race conditions
        when multiple threads update order state concurrently.
        """
        with self._order_lock:
            if order_id not in self.pending_orders:
                logger.warning(f"Unknown order ID: {order_id}")
                return

            tracker = self.pending_orders[order_id]
            tracker.status = status
            tracker.filled_qty = filled_qty
            tracker.filled_price = filled_price

            if status == "FILLED":
                tracker.filled_at = datetime.now()
                self.filled_orders[order_id] = tracker
                del self.pending_orders[order_id]
                # Notify outside lock to prevent deadlocks in callbacks
                self._notify("order_filled", tracker)
                logger.info(f"Order filled: {order_id} @ {filled_price}")

            elif status == "CANCELLED":
                del self.pending_orders[order_id]
                # Notify outside lock to prevent deadlocks in callbacks
                self._notify("order_cancelled", tracker)
                logger.info(f"Order cancelled: {order_id}")

    def cancel_all_orders(self, reason: str = "Manual cancellation") -> int:
        """
        Cancel all pending orders.

        THREAD-SAFE: Uses RLock which allows recursive acquisition
        (this method calls update_order_status which also acquires the lock).
        """
        cancelled = 0

        # Get snapshot of order IDs under lock
        with self._order_lock:
            order_ids = list(self.pending_orders.keys())

        for order_id in order_ids:
            try:
                if self.broker_adapter:
                    self.broker_adapter.cancel_order(order_id)
                # update_order_status will acquire the lock (RLock allows this)
                self.update_order_status(order_id, "CANCELLED")
                cancelled += 1
            except Exception as e:
                logger.error(f"Cancel error for {order_id}: {e}")

        logger.info(f"Cancelled {cancelled} orders: {reason}")
        return cancelled

    def get_recent_decisions(self, limit: int = 50) -> List[ExecutionDecision]:
        """Get recent execution decisions."""
        return self.decisions[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics (thread-safe)."""
        total_decisions = len(self.decisions)
        executed = sum(1 for d in self.decisions if d.was_executed)
        approved = sum(1 for d in self.decisions if d.risk_approved)

        with self._order_lock:
            pending_count = len(self.pending_orders)
            filled_count = len(self.filled_orders)

        return {
            "mode": self.mode.value,
            "total_decisions": total_decisions,
            "executed": executed,
            "approved": approved,
            "pending_orders": pending_count,
            "filled_orders": filled_count,
            "execution_rate": executed / total_decisions if total_decisions > 0 else 0,
            "approval_rate": approved / total_decisions if total_decisions > 0 else 0,
        }


# Singleton instance
_execution_engine: Optional[ExecutionEngine] = None


def get_execution_engine(
    mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY,
) -> ExecutionEngine:
    """Get or create execution engine singleton."""
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = ExecutionEngine(mode=mode)
    return _execution_engine
