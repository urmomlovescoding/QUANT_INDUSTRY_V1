"""
Execution Contract
==================
Canonical interface for order execution.

ALL order submissions MUST go through implementations of this contract.
Direct broker API calls are FORBIDDEN outside adapters.

Safety Requirements:
1. Every order MUST pass SafetyGuard.can_trade()
2. Every order MUST pass KillSwitch.check_and_block()
3. Every fill MUST be recorded via feedback loop
4. Live orders REQUIRE ALLOW_LIVE=true environment variable
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


class ExecutionMode(Enum):
    """Execution environment."""
    PAPER = "paper"         # Paper trading, no real money
    LIVE = "live"           # Live trading, real money at risk
    BACKTEST = "backtest"   # Historical simulation
    SIGNAL_ONLY = "signal"  # Generate signals, no execution


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
    """Order lifecycle status."""
    PENDING = "pending"         # Created, not submitted
    SUBMITTED = "submitted"     # Sent to broker
    ACCEPTED = "accepted"       # Broker accepted
    PARTIAL = "partial"         # Partially filled
    FILLED = "filled"           # Fully filled
    CANCELLED = "cancelled"     # Cancelled
    REJECTED = "rejected"       # Broker rejected
    EXPIRED = "expired"         # Time expired
    BLOCKED = "blocked"         # Blocked by safety


@dataclass
class OrderRequest:
    """
    Order request structure.

    This is what comes IN to the execution service.
    """
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"

    # Metadata
    strategy_id: Optional[str] = None
    signal_id: Optional[str] = None
    client_order_id: Optional[str] = None

    # Risk context
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_slippage_pct: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force,
            "strategy_id": self.strategy_id,
            "signal_id": self.signal_id,
        }


@dataclass
class OrderResult:
    """
    Order result structure.

    This is what comes OUT of the execution service.
    """
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    status: OrderStatus

    # Fill info
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    filled_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.now)

    # Execution details
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    broker: str = "unknown"

    # Error info
    rejection_reason: Optional[str] = None
    error_message: Optional[str] = None

    # Calculated fields
    @property
    def is_terminal(self) -> bool:
        """Order is in terminal state (no more updates expected)."""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.BLOCKED,
        ]

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def notional_value(self) -> float:
        if self.avg_fill_price > 0:
            return self.filled_qty * self.avg_fill_price
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "filled_qty": self.filled_qty,
            "avg_fill_price": self.avg_fill_price,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "created_at": self.created_at.isoformat(),
            "execution_mode": self.execution_mode.value,
            "broker": self.broker,
            "rejection_reason": self.rejection_reason,
            "is_filled": self.is_filled,
            "notional_value": self.notional_value,
        }


class ExecutionContract(ABC):
    """
    Execution Service Contract.

    All implementations MUST:
    1. Check SafetyGuard before every order
    2. Check KillSwitch before every order
    3. Record every fill via feedback loop
    4. Enforce ALLOW_LIVE for live trading
    5. Never execute in wrong mode
    """

    @property
    @abstractmethod
    def mode(self) -> ExecutionMode:
        """Current execution mode."""
        pass

    @abstractmethod
    def submit_order(self, request: OrderRequest) -> OrderResult:
        """
        Submit an order.

        MUST:
        1. Call SafetyGuard.can_trade() first
        2. Call KillSwitch.check_and_block() first
        3. Validate request fields
        4. Return OrderResult with full status
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order. Returns True if cancellation submitted."""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[OrderResult]:
        """Get order by ID."""
        pass

    @abstractmethod
    def get_open_orders(self) -> List[OrderResult]:
        """Get all open orders."""
        pass

    @abstractmethod
    def flatten_all(self, reason: str = "Manual flatten") -> List[OrderResult]:
        """
        Close all positions.

        Used by KillSwitch and EOD flatten.
        """
        pass

    @abstractmethod
    def validate_order(self, request: OrderRequest) -> Tuple[bool, str]:
        """
        Pre-validate an order without submitting.

        Returns (is_valid, reason).
        """
        pass

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """
        Get execution service health.

        MUST return:
        - mode: Current execution mode
        - broker_connected: Connection status
        - orders_today: Order count
        - fills_today: Fill count
        - safety_status: SafetyGuard status
        - kill_switch_active: KillSwitch status
        """
        pass
