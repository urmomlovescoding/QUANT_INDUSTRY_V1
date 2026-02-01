"""
Broker Adapter
==============
P1 Feature: Abstract broker interface for execution.

Implements parity with quant-platform/execution/broker_adapter.py

Provides a unified interface for:
- Order submission
- Order management
- Position tracking
- Account information
- SafetyGuard integration for non-negotiable risk limits
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple

# Import SafetyGuard for order validation
try:
    from backend.core.safety_guard import get_safety_guard, SafetyError
    SAFETY_GUARD_AVAILABLE = True
except ImportError:
    try:
        from core.safety_guard import get_safety_guard, SafetyError
        SAFETY_GUARD_AVAILABLE = True
    except ImportError:
        SAFETY_GUARD_AVAILABLE = False
        get_safety_guard = None

# Import KillSwitch singleton
try:
    from backend.execution.kill_switch import get_kill_switch
    KILL_SWITCH_AVAILABLE = True
except ImportError:
    try:
        from .kill_switch import get_kill_switch
        KILL_SWITCH_AVAILABLE = True
    except ImportError:
        KILL_SWITCH_AVAILABLE = False
        get_kill_switch = None

logger = logging.getLogger("BROKER_ADAPTER")


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(Enum):
    """Time in force options."""
    DAY = "day"
    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


class ExecutionMode(Enum):
    """Execution modes - matches quant-platform pattern."""
    SIGNAL_ONLY = "signal_only"    # Generate signals but don't execute
    AUTO_PAPER = "auto_paper"      # Auto-execute on paper account
    AUTO_LIVE = "auto_live"        # Auto-execute on live account


@dataclass
class KillSwitch:
    """
    Emergency kill switch for halting all trading.
    Matches quant-platform/execution/kill_switch.py pattern.
    """
    active: bool = False
    reason: str = ""
    activated_at: Optional[datetime] = None
    activated_by: str = ""
    auto_deactivate_at: Optional[datetime] = None

    def activate(self, reason: str, activated_by: str = "system", duration_minutes: Optional[int] = None):
        """Activate the kill switch."""
        self.active = True
        self.reason = reason
        self.activated_at = datetime.now()
        self.activated_by = activated_by
        if duration_minutes:
            from datetime import timedelta
            self.auto_deactivate_at = datetime.now() + timedelta(minutes=duration_minutes)
        logger.warning(f"[KILL SWITCH] ACTIVATED by {activated_by}: {reason}")

    def deactivate(self, deactivated_by: str = "system"):
        """Deactivate the kill switch."""
        was_active = self.active
        self.active = False
        self.reason = ""
        self.activated_at = None
        self.activated_by = ""
        self.auto_deactivate_at = None
        if was_active:
            logger.info(f"[KILL SWITCH] Deactivated by {deactivated_by}")

    def check_auto_deactivate(self):
        """Check if kill switch should auto-deactivate."""
        if self.active and self.auto_deactivate_at and datetime.now() >= self.auto_deactivate_at:
            self.deactivate("auto_timeout")

    def is_trading_allowed(self) -> tuple:
        """Check if trading is allowed. Returns (allowed, reason)."""
        self.check_auto_deactivate()
        if self.active:
            return False, f"Kill switch active: {self.reason}"
        return True, "OK"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "reason": self.reason,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "activated_by": self.activated_by,
            "auto_deactivate_at": self.auto_deactivate_at.isoformat() if self.auto_deactivate_at else None,
        }


@dataclass
class ExecutionDecision:
    """
    Complete audit trail for every execution decision.
    Matches quant-platform/execution/executor.py pattern.
    """
    decision_id: str
    timestamp: datetime
    ticker: str
    direction: str
    signal_confidence: float
    signal_size_pct: float

    # Risk checks
    risk_approved: bool = False
    risk_reason: str = ""
    risk_warnings: List[str] = field(default_factory=list)
    adjusted_size_pct: float = 0.0

    # Regime context
    regime: str = "unknown"
    volatility: float = 0.0
    vix: float = 0.0

    # Execution
    mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY
    was_executed: bool = False
    order_id: Optional[str] = None

    # Fill information
    filled: bool = False
    filled_price: Optional[float] = None
    filled_qty: Optional[int] = None
    filled_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "ticker": self.ticker,
            "direction": self.direction,
            "signal_confidence": self.signal_confidence,
            "signal_size_pct": self.signal_size_pct,
            "risk_approved": self.risk_approved,
            "risk_reason": self.risk_reason,
            "risk_warnings": self.risk_warnings,
            "adjusted_size_pct": self.adjusted_size_pct,
            "regime": self.regime,
            "volatility": self.volatility,
            "vix": self.vix,
            "mode": self.mode.value,
            "was_executed": self.was_executed,
            "order_id": self.order_id,
            "filled": self.filled,
            "filled_price": self.filled_price,
            "filled_qty": self.filled_qty,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }


# Global kill switch instance
_kill_switch = KillSwitch()


def get_kill_switch() -> KillSwitch:
    """Get the global kill switch instance."""
    return _kill_switch


# ============== EXECUTION CALLBACKS ==============

class ExecutionEvent(Enum):
    """Execution event types for callbacks."""
    PRE_ORDER = "pre_order"          # Before order submission
    ORDER_SUBMITTED = "order_submitted"  # After order submitted
    ORDER_FILLED = "order_filled"    # Order fully filled
    ORDER_PARTIAL = "order_partial"  # Order partially filled
    ORDER_CANCELLED = "order_cancelled"  # Order cancelled
    ORDER_REJECTED = "order_rejected"  # Order rejected
    ORDER_ERROR = "order_error"      # Order error
    POSITION_OPENED = "position_opened"  # New position opened
    POSITION_CLOSED = "position_closed"  # Position closed
    POSITION_MODIFIED = "position_modified"  # Position modified


@dataclass
class ExecutionCallbackResult:
    """Result from a callback execution."""
    event: ExecutionEvent
    success: bool
    callback_name: str
    execution_time_ms: float
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ExecutionCallbackManager:
    """
    Comprehensive callback manager for trade execution events.
    Matches quant-platform pattern for execution hooks.

    Supports:
    - Pre-execution validation (can block execution)
    - Post-execution notifications
    - Error handling callbacks
    - Async callback support
    """

    def __init__(self):
        self._callbacks: Dict[ExecutionEvent, List[Dict[str, Any]]] = {
            event: [] for event in ExecutionEvent
        }
        self._callback_history: List[ExecutionCallbackResult] = []
        self._max_history = 1000

    def register(
        self,
        event: ExecutionEvent,
        callback: Callable,
        name: str = "",
        priority: int = 0,
        can_block: bool = False
    ) -> str:
        """
        Register a callback for an execution event.

        Args:
            event: The event type to listen for
            callback: Function to call (receives event data dict)
            name: Optional name for the callback
            priority: Higher priority callbacks run first
            can_block: If True, callback can prevent execution (PRE_ORDER only)

        Returns:
            Callback ID for unregistering
        """
        import uuid
        callback_id = str(uuid.uuid4())[:8]
        callback_name = name or f"callback_{callback_id}"

        self._callbacks[event].append({
            "id": callback_id,
            "name": callback_name,
            "callback": callback,
            "priority": priority,
            "can_block": can_block and event == ExecutionEvent.PRE_ORDER
        })

        # Sort by priority (higher first)
        self._callbacks[event].sort(key=lambda x: -x["priority"])

        logger.debug(f"Registered callback '{callback_name}' for {event.value}")
        return callback_id

    def unregister(self, callback_id: str) -> bool:
        """Unregister a callback by ID."""
        for event in ExecutionEvent:
            for i, cb in enumerate(self._callbacks[event]):
                if cb["id"] == callback_id:
                    self._callbacks[event].pop(i)
                    logger.debug(f"Unregistered callback '{cb['name']}'")
                    return True
        return False

    def trigger(
        self,
        event: ExecutionEvent,
        data: Dict[str, Any]
    ) -> Tuple[bool, List[ExecutionCallbackResult]]:
        """
        Trigger callbacks for an event.

        Args:
            event: Event type
            data: Event data to pass to callbacks

        Returns:
            (should_continue, results) - should_continue is False if a blocking callback vetoed
        """
        import time
        results = []
        should_continue = True

        for cb_info in self._callbacks[event]:
            start_time = time.time()
            result = ExecutionCallbackResult(
                event=event,
                success=True,
                callback_name=cb_info["name"],
                execution_time_ms=0.0
            )

            try:
                callback_result = cb_info["callback"](data)

                # Check for blocking (PRE_ORDER events)
                if cb_info["can_block"] and callback_result is False:
                    should_continue = False
                    result.data = {"blocked": True}
                    logger.warning(f"Callback '{cb_info['name']}' blocked execution")

                result.data = result.data or {"result": callback_result}

            except Exception as e:
                result.success = False
                result.error = str(e)
                logger.error(f"Callback '{cb_info['name']}' error: {e}")

            result.execution_time_ms = (time.time() - start_time) * 1000
            results.append(result)
            self._record_result(result)

        return should_continue, results

    def _record_result(self, result: ExecutionCallbackResult):
        """Record callback result in history."""
        self._callback_history.append(result)
        if len(self._callback_history) > self._max_history:
            self._callback_history.pop(0)

    def get_registered_callbacks(self, event: Optional[ExecutionEvent] = None) -> Dict[str, List[str]]:
        """Get list of registered callbacks."""
        if event:
            return {event.value: [cb["name"] for cb in self._callbacks[event]]}

        return {
            evt.value: [cb["name"] for cb in self._callbacks[evt]]
            for evt in ExecutionEvent
        }

    def get_callback_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent callback execution history."""
        return [
            {
                "event": r.event.value,
                "success": r.success,
                "callback_name": r.callback_name,
                "execution_time_ms": r.execution_time_ms,
                "error": r.error
            }
            for r in self._callback_history[-limit:]
        ]

    def clear_callbacks(self, event: Optional[ExecutionEvent] = None):
        """Clear callbacks for an event or all events."""
        if event:
            self._callbacks[event] = []
        else:
            for evt in ExecutionEvent:
                self._callbacks[evt] = []


# Global execution callback manager
_execution_callback_manager: Optional[ExecutionCallbackManager] = None


def get_execution_callback_manager() -> ExecutionCallbackManager:
    """Get global execution callback manager instance."""
    global _execution_callback_manager
    if _execution_callback_manager is None:
        _execution_callback_manager = ExecutionCallbackManager()
    return _execution_callback_manager


@dataclass
class Order:
    """Order representation."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int

    # Prices
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None

    # Status
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    avg_fill_price: float = 0.0

    # Timing
    time_in_force: TimeInForce = TimeInForce.DAY
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    # Metadata
    client_order_id: Optional[str] = None
    broker_order_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_qty": self.filled_qty,
            "avg_fill_price": self.avg_fill_price,
            "time_in_force": self.time_in_force.value,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }


@dataclass
class Position:
    """Position representation."""
    symbol: str
    quantity: int
    side: str  # 'long' or 'short'
    avg_entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    market_value: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "side": self.side,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "market_value": self.market_value,
        }


@dataclass
class AccountInfo:
    """Account information."""
    account_id: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float

    # Margins
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0

    # Day trading
    day_trade_count: int = 0
    pattern_day_trader: bool = False

    # Status
    status: str = "active"
    trading_blocked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "buying_power": self.buying_power,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
            "equity": self.equity,
            "initial_margin": self.initial_margin,
            "maintenance_margin": self.maintenance_margin,
            "status": self.status,
            "trading_blocked": self.trading_blocked,
        }


class BrokerAdapter(ABC):
    """
    Abstract broker adapter interface.

    All broker implementations must inherit from this class
    and implement the abstract methods.

    Matches quant-platform broker adapter interface.

    Integrates with SafetyGuard for non-negotiable risk limits.
    """

    def __init__(self, name: str, is_live: bool = False):
        self.name = name
        self.is_live = is_live
        self.connected: bool = False
        self._order_callbacks: List[Callable] = []
        self._fill_callbacks: List[Callable] = []

        logger.info(f"BrokerAdapter '{name}' initialized (live={is_live})")

    def validate_order_safety(self, order: 'Order') -> Tuple[bool, str]:
        """
        Validate order through SafetyGuard and KillSwitch.

        This is the FINAL gate - if this returns False, do NOT submit.

        Args:
            order: Order to validate

        Returns:
            (allowed, reason) tuple
        """
        # Check KillSwitch first
        if KILL_SWITCH_AVAILABLE and get_kill_switch:
            ks = get_kill_switch()
            allowed, reason = ks.check_and_block("order_submission")
            if not allowed:
                logger.warning(f"Order blocked by KillSwitch: {reason}")
                return False, reason

        # Check SafetyGuard
        if SAFETY_GUARD_AVAILABLE and get_safety_guard:
            guard = get_safety_guard()

            # Calculate position size as percentage (rough estimate)
            # This would be more accurate with actual account equity
            size_pct = 0.05  # Default 5% position

            allowed, reason = guard.can_trade(
                symbol=order.symbol,
                size_pct=size_pct,
                contracts=order.quantity if hasattr(order, 'quantity') else 0,
                is_live=self.is_live
            )

            if not allowed:
                logger.warning(f"Order blocked by SafetyGuard: {reason}")
                return False, reason

        return True, "OK"

    def pre_submit_validation(self, order: 'Order') -> 'Order':
        """
        Validate order before submission. Override in subclasses for custom logic.

        Raises:
            SafetyError: If order is blocked by safety systems
        """
        allowed, reason = self.validate_order_safety(order)
        if not allowed:
            order.status = OrderStatus.REJECTED
            order.rejection_reason = reason
            if SAFETY_GUARD_AVAILABLE:
                raise SafetyError(f"Order blocked: {reason}")
            else:
                raise ValueError(f"Order blocked: {reason}")
        return order

    # Connection management

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the broker.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the broker."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        pass

    # Order management

    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        """
        Submit an order to the broker.

        Args:
            order: Order to submit

        Returns:
            Updated order with broker info
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order to cancel

        Returns:
            True if cancellation submitted
        """
        pass

    @abstractmethod
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """
        Modify an existing order.

        Args:
            order_id: Order to modify
            quantity: New quantity (optional)
            limit_price: New limit price (optional)
            stop_price: New stop price (optional)

        Returns:
            Updated order
        """
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order or None if not found
        """
        pass

    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get all open orders.

        Args:
            symbol: Filter by symbol (optional)

        Returns:
            List of open orders
        """
        pass

    # Position management

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a symbol.

        Args:
            symbol: Symbol to query

        Returns:
            Position or None if no position
        """
        pass

    @abstractmethod
    def get_all_positions(self) -> List[Position]:
        """
        Get all positions.

        Returns:
            List of positions
        """
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> Order:
        """
        Close a position.

        Args:
            symbol: Symbol to close

        Returns:
            Closing order
        """
        pass

    @abstractmethod
    def close_all_positions(self) -> List[Order]:
        """
        Close all positions (flatten).

        Returns:
            List of closing orders
        """
        pass

    # Account info

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """
        Get account information.

        Returns:
            Account info
        """
        pass

    # Market data (basic)

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, float]:
        """
        Get current quote for a symbol.

        Args:
            symbol: Symbol to query

        Returns:
            Dict with 'bid', 'ask', 'last', 'volume'
        """
        pass

    # Callbacks

    def register_order_callback(self, callback: Callable) -> None:
        """Register callback for order updates."""
        self._order_callbacks.append(callback)

    def register_fill_callback(self, callback: Callable) -> None:
        """Register callback for fills."""
        self._fill_callbacks.append(callback)

    def _notify_order_update(self, order: Order) -> None:
        """Notify callbacks of order update."""
        for callback in self._order_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Order callback error: {e}")

    def _notify_fill(self, order: Order, fill_qty: int, fill_price: float) -> None:
        """Notify callbacks of fill."""
        for callback in self._fill_callbacks:
            try:
                callback(order, fill_qty, fill_price)
            except Exception as e:
                logger.error(f"Fill callback error: {e}")

    def _update_safety_guard_equity(self, equity: float) -> None:
        """Update SafetyGuard with current account equity."""
        if SAFETY_GUARD_AVAILABLE and get_safety_guard:
            try:
                guard = get_safety_guard()
                guard.set_equity(equity, is_starting=False)
            except Exception as e:
                logger.warning(f"Failed to update SafetyGuard equity: {e}")

    def _record_trade_to_feedback_loop(
        self,
        symbol: str,
        pnl: float,
        strategy_id: str = None,
        signal_confidence: float = 0.0
    ) -> None:
        """Record trade result to feedback loop for ML learning."""
        try:
            from brain.feedback_loop import get_feedback_loop, TradeResult, TradeOutcome
            from datetime import datetime, timezone

            feedback = get_feedback_loop()

            # Determine outcome
            if pnl > 0:
                outcome = TradeOutcome.WIN
            elif pnl < 0:
                outcome = TradeOutcome.LOSS
            else:
                outcome = TradeOutcome.BREAKEVEN

            # Create trade result (simplified - full version would have more details)
            result = TradeResult(
                trade_id=f"trade_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                symbol=symbol,
                direction="UNKNOWN",  # Would be set from order
                entry_price=0,  # Would be tracked
                exit_price=0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc),
                quantity=0,
                pnl=pnl,
                pnl_pct=0,
                outcome=outcome,
                strategy=strategy_id or "unknown",
                signal_confidence=signal_confidence,
                regime_at_entry="unknown"
            )

            feedback.record_trade(result)
            logger.info(f"Recorded trade to feedback loop: {symbol} PnL=${pnl:.2f}")

        except ImportError:
            logger.debug("FeedbackLoop not available")
        except Exception as e:
            logger.warning(f"Failed to record trade to feedback loop: {e}")

    # Utility methods

    def create_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """Create a market order."""
        order_id = f"ord_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        return Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            client_order_id=client_order_id,
        )

    def create_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        limit_price: float,
        time_in_force: TimeInForce = TimeInForce.DAY,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """Create a limit order."""
        order_id = f"ord_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        return Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            limit_price=limit_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
        )

    def create_stop_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        stop_price: float,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """Create a stop order."""
        order_id = f"ord_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        return Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.STOP,
            quantity=quantity,
            stop_price=stop_price,
            client_order_id=client_order_id,
        )

    def create_bracket_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Dict[str, Order]:
        """
        Create a bracket order (entry + stop loss + take profit).

        Returns:
            Dict with 'entry', 'stop_loss', 'take_profit' orders
        """
        base_id = datetime.now().strftime('%Y%m%d%H%M%S%f')

        entry = Order(
            order_id=f"ord_{base_id}_entry",
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            limit_price=entry_price,
        )

        # Stop loss is opposite side
        sl_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        stop_loss_order = Order(
            order_id=f"ord_{base_id}_sl",
            symbol=symbol,
            side=sl_side,
            order_type=OrderType.STOP,
            quantity=quantity,
            stop_price=stop_loss,
        )

        take_profit_order = Order(
            order_id=f"ord_{base_id}_tp",
            symbol=symbol,
            side=sl_side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            limit_price=take_profit,
        )

        return {
            "entry": entry,
            "stop_loss": stop_loss_order,
            "take_profit": take_profit_order,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get adapter status."""
        return {
            "name": self.name,
            "connected": self.connected,
            "order_callbacks": len(self._order_callbacks),
            "fill_callbacks": len(self._fill_callbacks),
        }


class PaperBroker(BrokerAdapter):
    """
    Paper trading broker for simulation.

    Simulates order execution without real money.
    Used for backtesting and paper trading modes.
    """

    def __init__(self, initial_capital: float = 100000.0):
        super().__init__("paper")

        self.initial_capital = initial_capital
        self.cash = initial_capital

        # Order and position tracking
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}

        # Simulated prices
        self.prices: Dict[str, Dict[str, float]] = {}

        # Stats
        self.total_trades = 0
        self.realized_pnl = 0.0

        self.connected = True
        logger.info(f"PaperBroker initialized with ${initial_capital:,.2f}")

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def set_price(self, symbol: str, bid: float, ask: float) -> None:
        """Set simulated price for a symbol."""
        self.prices[symbol] = {
            "bid": bid,
            "ask": ask,
            "last": (bid + ask) / 2,
            "volume": 0,
        }

    def submit_order(self, order: Order) -> Order:
        """Submit and immediately fill market orders."""
        # Validate through SafetyGuard first
        try:
            self.pre_submit_validation(order)
        except (SafetyError if SAFETY_GUARD_AVAILABLE else ValueError) as e:
            logger.warning(f"Order rejected by safety check: {e}")
            order.status = OrderStatus.REJECTED
            order.rejection_reason = str(e)
            self.orders[order.order_id] = order
            return order
        except Exception as e:
            logger.warning(f"Order rejected: {e}")
            order.status = OrderStatus.REJECTED
            order.rejection_reason = str(e)
            self.orders[order.order_id] = order
            return order

        order.submitted_at = datetime.now()
        order.status = OrderStatus.SUBMITTED

        self.orders[order.order_id] = order
        self._notify_order_update(order)

        # Simulate immediate fill for market orders
        if order.order_type == OrderType.MARKET:
            self._simulate_fill(order)

        return order

    def _simulate_fill(self, order: Order) -> None:
        """Simulate order fill."""
        quote = self.prices.get(order.symbol, {"bid": 100, "ask": 100.01})

        # Fill at bid for sells, ask for buys
        if order.side == OrderSide.BUY:
            fill_price = quote["ask"]
        else:
            fill_price = quote["bid"]

        order.filled_qty = order.quantity
        order.avg_fill_price = fill_price
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now()

        # Update position
        self._update_position(order)

        self._notify_order_update(order)
        self._notify_fill(order, order.quantity, fill_price)

        self.total_trades += 1

    def _update_position(self, order: Order) -> None:
        """Update position after fill."""
        symbol = order.symbol
        qty = order.quantity if order.side == OrderSide.BUY else -order.quantity
        price = order.avg_fill_price

        if symbol not in self.positions:
            if qty > 0:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=qty,
                    side="long",
                    avg_entry_price=price,
                )
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=abs(qty),
                    side="short",
                    avg_entry_price=price,
                )
        else:
            pos = self.positions[symbol]
            old_qty = pos.quantity if pos.side == "long" else -pos.quantity
            new_qty = old_qty + qty

            if new_qty == 0:
                # Position closed - calculate P&L
                if pos.side == "long":
                    pnl = (price - pos.avg_entry_price) * pos.quantity
                else:
                    pnl = (pos.avg_entry_price - price) * pos.quantity

                self.realized_pnl += pnl
                self.cash += pnl
                del self.positions[symbol]

                # Record to feedback loop and update SafetyGuard
                self._record_trade_to_feedback_loop(symbol, pnl)
                self._update_safety_guard_equity(self.get_account().equity)

            elif (new_qty > 0) != (old_qty > 0):
                # Position flipped
                # First close old position
                if pos.side == "long":
                    pnl = (price - pos.avg_entry_price) * pos.quantity
                else:
                    pnl = (pos.avg_entry_price - price) * pos.quantity

                self.realized_pnl += pnl
                self.cash += pnl

                # Record to feedback loop and update SafetyGuard
                self._record_trade_to_feedback_loop(symbol, pnl)
                self._update_safety_guard_equity(self.get_account().equity)

                # Then open new position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=abs(new_qty),
                    side="long" if new_qty > 0 else "short",
                    avg_entry_price=price,
                )
            else:
                # Position increased
                total_cost = pos.avg_entry_price * abs(old_qty) + price * abs(qty)
                pos.quantity = abs(new_qty)
                pos.avg_entry_price = total_cost / pos.quantity

    def cancel_order(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if order and order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            order.status = OrderStatus.CANCELLED
            self._notify_order_update(order)
            return True
        return False

    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        if quantity:
            order.quantity = quantity
        if limit_price:
            order.limit_price = limit_price
        if stop_price:
            order.stop_price = stop_price

        self._notify_order_update(order)
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        open_orders = [
            o for o in self.orders.values()
            if o.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]
        ]
        if symbol:
            open_orders = [o for o in open_orders if o.symbol == symbol]
        return open_orders

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def get_all_positions(self) -> List[Position]:
        return list(self.positions.values())

    def get_positions(self) -> List[Position]:
        """Alias for get_all_positions for compatibility."""
        return self.get_all_positions()

    def close_position(self, symbol: str) -> Order:
        pos = self.positions.get(symbol)
        if not pos:
            raise ValueError(f"No position for {symbol}")

        side = OrderSide.SELL if pos.side == "long" else OrderSide.BUY
        order = self.create_market_order(symbol, side, pos.quantity)
        return self.submit_order(order)

    def close_all_positions(self) -> List[Order]:
        orders = []
        for symbol in list(self.positions.keys()):
            orders.append(self.close_position(symbol))
        return orders

    def get_account(self) -> AccountInfo:
        # Calculate portfolio value
        portfolio_value = self.cash
        for pos in self.positions.values():
            quote = self.prices.get(pos.symbol, {"last": pos.avg_entry_price})
            pos.current_price = quote["last"]

            if pos.side == "long":
                pos.unrealized_pnl = (pos.current_price - pos.avg_entry_price) * pos.quantity
            else:
                pos.unrealized_pnl = (pos.avg_entry_price - pos.current_price) * pos.quantity

            pos.market_value = pos.current_price * pos.quantity
            portfolio_value += pos.unrealized_pnl

        return AccountInfo(
            account_id="paper_account",
            buying_power=self.cash,
            cash=self.cash,
            portfolio_value=portfolio_value,
            equity=portfolio_value,
        )

    def get_quote(self, symbol: str) -> Dict[str, float]:
        return self.prices.get(symbol, {
            "bid": 0,
            "ask": 0,
            "last": 0,
            "volume": 0,
        })

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status.update({
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "total_trades": self.total_trades,
            "open_positions": len(self.positions),
            "open_orders": len(self.get_open_orders()),
        })
        return status
