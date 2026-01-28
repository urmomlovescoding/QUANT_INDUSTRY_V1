"""
QUANT_INDUSTRY_V1 Execution Engine

Smart order execution:
- Order management
- Execution algorithms (TWAP, VWAP, POV)
- Slippage modeling
- Fill tracking

Rollback Plan: Delete this file
Tests Required: Order lifecycle, algorithm correctness
Failure Modes: Reject orders, alert operators
"""

import numpy as np
import logging
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import deque

logger = logging.getLogger(__name__)


# =============================================================================
# ORDER TYPES
# =============================================================================

class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


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
    """Time in force."""
    DAY = "day"
    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


# =============================================================================
# ORDER AND FILL
# =============================================================================

@dataclass
class Order:
    """Trading order."""
    symbol: str
    quantity: float
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    client_order_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_avg_price: float = 0.0
    commission: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        return self.status in [
            OrderStatus.FILLED, OrderStatus.CANCELLED,
            OrderStatus.REJECTED, OrderStatus.EXPIRED
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'time_in_force': self.time_in_force.value,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_avg_price': self.filled_avg_price,
            'commission': self.commission,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class Fill:
    """Order fill."""
    fill_id: str
    order_id: str
    symbol: str
    quantity: float
    price: float
    side: OrderSide
    timestamp: datetime
    commission: float = 0.0
    exchange: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'fill_id': self.fill_id,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'side': self.side.value,
            'timestamp': self.timestamp.isoformat(),
            'commission': self.commission,
            'exchange': self.exchange,
        }


@dataclass
class OrderResult:
    """Result of order submission."""
    success: bool
    order: Order
    message: str = ""
    fills: List[Fill] = field(default_factory=list)
    slippage: float = 0.0
    execution_time_ms: float = 0.0


# =============================================================================
# EXECUTION ALGORITHMS
# =============================================================================

class ExecutionAlgorithm(ABC):
    """Base class for execution algorithms."""

    @abstractmethod
    def generate_child_orders(
        self,
        parent_order: Order,
        market_data: Dict[str, Any],
        position: float = 0.0
    ) -> List[Order]:
        """Generate child orders from parent."""
        pass

    @abstractmethod
    def update(
        self,
        fills: List[Fill],
        market_data: Dict[str, Any]
    ) -> List[Order]:
        """Update and generate new child orders based on fills."""
        pass


class TWAPAlgorithm(ExecutionAlgorithm):
    """
    Time-Weighted Average Price algorithm.

    Splits order into equal slices over time.
    """

    def __init__(
        self,
        duration_minutes: int = 30,
        n_slices: int = 10,
        randomize: bool = True
    ):
        self.duration_minutes = duration_minutes
        self.n_slices = n_slices
        self.randomize = randomize

        self.parent_order: Optional[Order] = None
        self.slice_size: float = 0.0
        self.slices_sent: int = 0
        self.start_time: Optional[datetime] = None

    def generate_child_orders(
        self,
        parent_order: Order,
        market_data: Dict[str, Any],
        position: float = 0.0
    ) -> List[Order]:
        """Generate first slice."""
        self.parent_order = parent_order
        self.slice_size = parent_order.quantity / self.n_slices
        self.start_time = datetime.now(timezone.utc)
        self.slices_sent = 0

        return self._create_slice()

    def update(
        self,
        fills: List[Fill],
        market_data: Dict[str, Any]
    ) -> List[Order]:
        """Generate next slice based on time."""
        if self.parent_order is None:
            return []

        # Check if time for next slice
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        expected_slices = int(elapsed / (self.duration_minutes * 60 / self.n_slices))

        if expected_slices > self.slices_sent and self.slices_sent < self.n_slices:
            return self._create_slice()

        return []

    def _create_slice(self) -> List[Order]:
        """Create a single slice order."""
        if self.slices_sent >= self.n_slices:
            return []

        size = self.slice_size

        # Add randomization
        if self.randomize:
            size *= np.random.uniform(0.8, 1.2)

        # Ensure we don't exceed remaining
        remaining = self.parent_order.quantity - (self.slices_sent * self.slice_size)
        size = min(size, remaining)

        if size <= 0:
            return []

        self.slices_sent += 1

        order = Order(
            symbol=self.parent_order.symbol,
            quantity=size,
            side=self.parent_order.side,
            order_type=OrderType.LIMIT if self.parent_order.limit_price else OrderType.MARKET,
            limit_price=self.parent_order.limit_price,
            client_order_id=f"{self.parent_order.order_id}_slice_{self.slices_sent}",
            metadata={'parent_id': self.parent_order.order_id, 'algorithm': 'TWAP'},
        )

        return [order]


class VWAPAlgorithm(ExecutionAlgorithm):
    """
    Volume-Weighted Average Price algorithm.

    Schedules orders based on historical volume profile.
    """

    def __init__(
        self,
        duration_minutes: int = 30,
        volume_profile: List[float] = None,
        participation_rate: float = 0.1
    ):
        self.duration_minutes = duration_minutes
        self.participation_rate = participation_rate

        # Default volume profile (30-minute bars)
        if volume_profile is None:
            # U-shaped profile typical for intraday
            self.volume_profile = [
                0.15, 0.12, 0.10, 0.08, 0.08, 0.07,
                0.07, 0.08, 0.10, 0.15
            ]
        else:
            self.volume_profile = volume_profile

        self.parent_order: Optional[Order] = None
        self.current_slice: int = 0
        self.start_time: Optional[datetime] = None

    def generate_child_orders(
        self,
        parent_order: Order,
        market_data: Dict[str, Any],
        position: float = 0.0
    ) -> List[Order]:
        """Generate first volume-weighted slice."""
        self.parent_order = parent_order
        self.current_slice = 0
        self.start_time = datetime.now(timezone.utc)

        return self._create_volume_slice(market_data)

    def update(
        self,
        fills: List[Fill],
        market_data: Dict[str, Any]
    ) -> List[Order]:
        """Generate next slice based on volume."""
        if self.parent_order is None:
            return []

        # Check if time for next slice
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        expected_slice = int(elapsed / (self.duration_minutes * 60 / len(self.volume_profile)))

        if expected_slice > self.current_slice and self.current_slice < len(self.volume_profile):
            return self._create_volume_slice(market_data)

        return []

    def _create_volume_slice(self, market_data: Dict[str, Any]) -> List[Order]:
        """Create volume-weighted slice."""
        if self.current_slice >= len(self.volume_profile):
            return []

        # Get volume weight
        weight = self.volume_profile[self.current_slice]

        # Calculate size based on volume profile
        size = self.parent_order.quantity * weight

        # Adjust based on current market volume
        current_volume = market_data.get('volume', 0)
        if current_volume > 0:
            max_size = current_volume * self.participation_rate
            size = min(size, max_size)

        self.current_slice += 1

        if size <= 0:
            return []

        order = Order(
            symbol=self.parent_order.symbol,
            quantity=size,
            side=self.parent_order.side,
            order_type=OrderType.LIMIT,
            limit_price=self._calculate_limit_price(market_data),
            client_order_id=f"{self.parent_order.order_id}_vwap_{self.current_slice}",
            metadata={'parent_id': self.parent_order.order_id, 'algorithm': 'VWAP'},
        )

        return [order]

    def _calculate_limit_price(self, market_data: Dict[str, Any]) -> float:
        """Calculate limit price based on VWAP target."""
        vwap = market_data.get('vwap', market_data.get('price', 0))
        spread = market_data.get('spread', 0.01)

        if self.parent_order.side == OrderSide.BUY:
            return vwap + spread * 0.5
        else:
            return vwap - spread * 0.5


class POVAlgorithm(ExecutionAlgorithm):
    """
    Percentage of Volume algorithm.

    Trades as a percentage of market volume.
    """

    def __init__(
        self,
        target_participation: float = 0.1,
        min_order_size: float = 100,
        max_order_size: float = 10000
    ):
        self.target_participation = target_participation
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size

        self.parent_order: Optional[Order] = None
        self.total_filled: float = 0.0
        self.volume_window: deque = deque(maxlen=10)

    def generate_child_orders(
        self,
        parent_order: Order,
        market_data: Dict[str, Any],
        position: float = 0.0
    ) -> List[Order]:
        """Generate initial POV order."""
        self.parent_order = parent_order
        self.total_filled = 0.0

        return self._create_pov_order(market_data)

    def update(
        self,
        fills: List[Fill],
        market_data: Dict[str, Any]
    ) -> List[Order]:
        """Update based on market volume."""
        if self.parent_order is None:
            return []

        # Update filled quantity
        for fill in fills:
            if fill.order_id.startswith(self.parent_order.order_id):
                self.total_filled += fill.quantity

        # Check if more to fill
        remaining = self.parent_order.quantity - self.total_filled
        if remaining <= 0:
            return []

        return self._create_pov_order(market_data)

    def _create_pov_order(self, market_data: Dict[str, Any]) -> List[Order]:
        """Create POV order."""
        current_volume = market_data.get('volume', 0)
        self.volume_window.append(current_volume)

        # Calculate target size
        avg_volume = np.mean(self.volume_window) if self.volume_window else current_volume
        target_size = avg_volume * self.target_participation

        # Clamp to limits
        size = max(self.min_order_size, min(self.max_order_size, target_size))

        # Don't exceed remaining
        remaining = self.parent_order.quantity - self.total_filled
        size = min(size, remaining)

        if size < self.min_order_size:
            return []

        order = Order(
            symbol=self.parent_order.symbol,
            quantity=size,
            side=self.parent_order.side,
            order_type=OrderType.MARKET,
            client_order_id=f"{self.parent_order.order_id}_pov_{len(self.volume_window)}",
            metadata={'parent_id': self.parent_order.order_id, 'algorithm': 'POV'},
        )

        return [order]


# =============================================================================
# SLIPPAGE MODEL
# =============================================================================

class SlippageModel:
    """Model execution slippage."""

    def __init__(
        self,
        base_slippage_bps: float = 5.0,
        volume_impact_factor: float = 0.1,
        volatility_impact_factor: float = 0.5
    ):
        self.base_slippage_bps = base_slippage_bps
        self.volume_impact_factor = volume_impact_factor
        self.volatility_impact_factor = volatility_impact_factor

    def estimate_slippage(
        self,
        order: Order,
        market_data: Dict[str, Any]
    ) -> float:
        """
        Estimate slippage for order.

        Returns slippage as decimal (e.g., 0.001 = 10 bps).
        """
        price = market_data.get('price', 100)
        volume = market_data.get('volume', 10000)
        volatility = market_data.get('volatility', 0.02)
        spread = market_data.get('spread', 0.01)

        # Base slippage
        slippage = self.base_slippage_bps / 10000

        # Volume impact (square root)
        participation = order.quantity / (volume + 1)
        volume_impact = self.volume_impact_factor * np.sqrt(participation)
        slippage += volume_impact

        # Volatility impact
        vol_impact = self.volatility_impact_factor * volatility
        slippage += vol_impact

        # Spread cost (half spread for market orders)
        if order.order_type == OrderType.MARKET:
            slippage += spread / price / 2

        return slippage

    def apply_slippage(
        self,
        order: Order,
        reference_price: float,
        slippage: float
    ) -> float:
        """Apply slippage to get execution price."""
        if order.side == OrderSide.BUY:
            return reference_price * (1 + slippage)
        else:
            return reference_price * (1 - slippage)


# =============================================================================
# EXECUTION ENGINE
# =============================================================================

class ExecutionEngine:
    """
    Main execution engine.

    Handles order submission, routing, and tracking.
    """

    def __init__(
        self,
        broker: 'BaseBroker' = None,
        slippage_model: SlippageModel = None,
        max_order_value: float = 100000,
        max_daily_orders: int = 1000
    ):
        self.broker = broker
        self.slippage_model = slippage_model or SlippageModel()
        self.max_order_value = max_order_value
        self.max_daily_orders = max_daily_orders

        # Order tracking
        self.pending_orders: Dict[str, Order] = {}
        self.completed_orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []

        # Daily counters
        self.orders_today = 0
        self.last_reset = datetime.now(timezone.utc).date()

        # Algorithms
        self.active_algorithms: Dict[str, ExecutionAlgorithm] = {}

        self._lock = threading.RLock()

        # Event handlers
        self.on_fill: List[Callable[[Fill], None]] = []
        self.on_order_complete: List[Callable[[Order], None]] = []

    def submit(
        self,
        order: Order,
        algorithm: ExecutionAlgorithm = None
    ) -> OrderResult:
        """
        Submit order for execution.

        Args:
            order: Order to submit
            algorithm: Optional execution algorithm

        Returns:
            OrderResult with execution details
        """
        start_time = time.time()

        # Reset daily counter if needed
        self._check_daily_reset()

        # Validate order
        validation = self._validate_order(order)
        if not validation[0]:
            order.status = OrderStatus.REJECTED
            return OrderResult(
                success=False,
                order=order,
                message=validation[1],
            )

        # Check limits
        if self.orders_today >= self.max_daily_orders:
            order.status = OrderStatus.REJECTED
            return OrderResult(
                success=False,
                order=order,
                message="Daily order limit exceeded",
            )

        with self._lock:
            self.pending_orders[order.order_id] = order
            self.orders_today += 1

        # Use algorithm if provided
        if algorithm:
            self.active_algorithms[order.order_id] = algorithm
            child_orders = algorithm.generate_child_orders(order, self._get_market_data(order.symbol))
            for child in child_orders:
                self._execute_order(child)
        else:
            self._execute_order(order)

        execution_time = (time.time() - start_time) * 1000

        # Get fills for this order
        order_fills = [f for f in self.fills if f.order_id == order.order_id]

        # Calculate slippage if we have fills
        slippage = 0.0
        if order_fills and order.limit_price:
            avg_fill_price = np.mean([f.price for f in order_fills])
            slippage = abs(avg_fill_price - order.limit_price) / order.limit_price

        return OrderResult(
            success=order.status in [OrderStatus.FILLED, OrderStatus.PARTIAL, OrderStatus.SUBMITTED],
            order=order,
            message="Order submitted",
            fills=order_fills,
            slippage=slippage,
            execution_time_ms=execution_time,
        )

    def _execute_order(self, order: Order) -> None:
        """Execute single order."""
        order.status = OrderStatus.SUBMITTED

        if self.broker:
            # Real execution
            try:
                result = self.broker.submit_order(order)
                order.status = result.status
                order.filled_quantity = result.filled_quantity
                order.filled_avg_price = result.avg_price

                for fill in result.fills:
                    self._record_fill(fill)

            except Exception as e:
                logger.error(f"Order execution error: {e}")
                order.status = OrderStatus.REJECTED
        else:
            # Simulated execution
            self._simulate_execution(order)

        if order.is_complete:
            self._complete_order(order)

    def _simulate_execution(self, order: Order) -> None:
        """Simulate order execution."""
        market_data = self._get_market_data(order.symbol)
        price = market_data.get('price', 100)

        # Apply slippage
        slippage = self.slippage_model.estimate_slippage(order, market_data)
        exec_price = self.slippage_model.apply_slippage(order, price, slippage)

        # Check limit price
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and exec_price > order.limit_price:
                return  # Would not fill
            if order.side == OrderSide.SELL and exec_price < order.limit_price:
                return

        # Create fill
        fill = Fill(
            fill_id=str(uuid.uuid4())[:8],
            order_id=order.order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=exec_price,
            side=order.side,
            timestamp=datetime.now(timezone.utc),
            commission=order.quantity * exec_price * 0.0001,  # 1 bp commission
        )

        self._record_fill(fill)

        order.filled_quantity = order.quantity
        order.filled_avg_price = exec_price
        order.commission = fill.commission
        order.status = OrderStatus.FILLED

    def _record_fill(self, fill: Fill) -> None:
        """Record a fill."""
        with self._lock:
            self.fills.append(fill)

        # Update parent order
        if fill.order_id in self.pending_orders:
            order = self.pending_orders[fill.order_id]
            order.filled_quantity += fill.quantity
            order.commission += fill.commission

            # Update average price
            total_value = order.filled_avg_price * (order.filled_quantity - fill.quantity)
            total_value += fill.price * fill.quantity
            order.filled_avg_price = total_value / order.filled_quantity

            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED
            else:
                order.status = OrderStatus.PARTIAL

        # Notify handlers
        for handler in self.on_fill:
            try:
                handler(fill)
            except Exception as e:
                logger.error(f"Fill handler error: {e}")

    def _complete_order(self, order: Order) -> None:
        """Handle order completion."""
        with self._lock:
            if order.order_id in self.pending_orders:
                del self.pending_orders[order.order_id]
            self.completed_orders[order.order_id] = order

            # Remove algorithm
            if order.order_id in self.active_algorithms:
                del self.active_algorithms[order.order_id]

        # Notify handlers
        for handler in self.on_order_complete:
            try:
                handler(order)
            except Exception as e:
                logger.error(f"Order complete handler error: {e}")

    def cancel(self, order_id: str) -> bool:
        """Cancel pending order."""
        with self._lock:
            if order_id not in self.pending_orders:
                return False

            order = self.pending_orders[order_id]

            if self.broker:
                try:
                    self.broker.cancel_order(order_id)
                except Exception as e:
                    logger.error(f"Cancel error: {e}")
                    return False

            order.status = OrderStatus.CANCELLED
            self._complete_order(order)

        return True

    def _validate_order(self, order: Order) -> Tuple[bool, str]:
        """Validate order before submission."""
        if order.quantity <= 0:
            return False, "Quantity must be positive"

        if order.order_type == OrderType.LIMIT and order.limit_price is None:
            return False, "Limit orders require limit price"

        if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and order.stop_price is None:
            return False, "Stop orders require stop price"

        # Check max value
        estimated_value = order.quantity * (order.limit_price or 100)
        if estimated_value > self.max_order_value:
            return False, f"Order value ${estimated_value:.2f} exceeds max ${self.max_order_value:.2f}"

        return True, ""

    def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get current market data for symbol."""
        if self.broker:
            try:
                return self.broker.get_quote(symbol)
            except Exception:
                pass

        # Default simulated data
        return {
            'price': 100.0,
            'bid': 99.95,
            'ask': 100.05,
            'spread': 0.10,
            'volume': 100000,
            'volatility': 0.02,
            'vwap': 100.0,
        }

    def _check_daily_reset(self) -> None:
        """Reset daily counters if new day."""
        today = datetime.now(timezone.utc).date()
        if today != self.last_reset:
            self.orders_today = 0
            self.last_reset = today

    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders."""
        with self._lock:
            return list(self.pending_orders.values())

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        with self._lock:
            if order_id in self.pending_orders:
                return self.pending_orders[order_id]
            return self.completed_orders.get(order_id)

    def get_fills(
        self,
        symbol: str = None,
        since: datetime = None
    ) -> List[Fill]:
        """Get fills, optionally filtered."""
        fills = self.fills

        if symbol:
            fills = [f for f in fills if f.symbol == symbol]

        if since:
            fills = [f for f in fills if f.timestamp >= since]

        return fills

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self.fills:
            return {}

        prices = [f.price for f in self.fills]
        quantities = [f.quantity for f in self.fills]
        commissions = [f.commission for f in self.fills]

        return {
            'total_fills': len(self.fills),
            'total_volume': sum(quantities),
            'total_value': sum(p * q for p, q in zip(prices, quantities)),
            'total_commission': sum(commissions),
            'avg_fill_price': np.mean(prices),
            'orders_today': self.orders_today,
            'pending_orders': len(self.pending_orders),
            'completed_orders': len(self.completed_orders),
        }
