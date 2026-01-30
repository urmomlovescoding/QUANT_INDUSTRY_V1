"""
QUANT INDUSTRY V1 - Trading API (v2)
====================================
Consolidated trading endpoints: signals, orders, positions, broker.
"""

from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

router = APIRouter()


# ============================================================================
# Enums
# ============================================================================

class SignalStatus(str, Enum):
    """Signal status options."""
    ACTIVE = "active"
    EXECUTED = "executed"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class SignalDirection(str, Enum):
    """Signal direction."""
    LONG = "long"
    SHORT = "short"


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TimeInForce(str, Enum):
    """Time in force options."""
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


class BrokerStatus(str, Enum):
    """Broker connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


# ============================================================================
# Pydantic Models - Signals
# ============================================================================

class Signal(BaseModel):
    """Trading signal from ML brain."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    direction: SignalDirection
    confidence: float = Field(..., ge=0, le=1, description="Signal confidence 0-1")
    entry_price: float
    stop_loss: float
    take_profit: Optional[float] = None
    position_size: float = Field(..., description="Suggested position size")
    status: SignalStatus = SignalStatus.ACTIVE
    source: str = Field(default="brain_v6", description="Signal source model")
    reasoning: Optional[str] = Field(None, description="AI reasoning for signal")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class SignalsResponse(BaseModel):
    """List of signals response."""
    signals: list[Signal] = Field(default_factory=list)
    total: int
    active_count: int


class GenerateSignalRequest(BaseModel):
    """Request to generate a new signal."""
    symbol: str = Field(..., description="Ticker symbol")
    force: bool = Field(False, description="Force generation even if recent signal exists")


class ExecuteSignalRequest(BaseModel):
    """Request to execute a signal."""
    override_size: Optional[float] = Field(None, description="Override position size")
    limit_price: Optional[float] = Field(None, description="Use limit order at this price")


# ============================================================================
# Pydantic Models - Orders
# ============================================================================

class Order(BaseModel):
    """Order details."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0
    filled_avg_price: Optional[float] = None
    signal_id: Optional[str] = Field(None, description="Associated signal ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrdersResponse(BaseModel):
    """List of orders response."""
    orders: list[Order] = Field(default_factory=list)
    total: int


class CreateOrderRequest(BaseModel):
    """Request to create a new order."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(..., gt=0)
    limit_price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)
    time_in_force: TimeInForce = TimeInForce.DAY
    signal_id: Optional[str] = None


# ============================================================================
# Pydantic Models - Positions
# ============================================================================

class Position(BaseModel):
    """Current position details."""
    symbol: str
    quantity: float
    side: str = Field(..., description="long or short")
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    cost_basis: float
    opened_at: datetime


class PositionsResponse(BaseModel):
    """List of positions response."""
    positions: list[Position] = Field(default_factory=list)
    total_value: float
    total_unrealized_pnl: float


# ============================================================================
# Pydantic Models - Broker
# ============================================================================

class BrokerStatusResponse(BaseModel):
    """Broker connection status."""
    status: BrokerStatus
    broker: str = Field(..., description="Broker name (e.g., alpaca, ibkr)")
    connected_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    paper_trading: bool = Field(True, description="Whether in paper trading mode")
    message: Optional[str] = None


class AccountInfo(BaseModel):
    """Broker account information."""
    account_id: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    margin_used: float
    margin_available: float
    day_trades_remaining: int
    pattern_day_trader: bool


# ============================================================================
# Endpoints - Signals
# ============================================================================

@router.get(
    "/signals",
    response_model=SignalsResponse,
    summary="List signals",
    description="Get trading signals with optional status filter."
)
async def list_signals(
    status: Optional[SignalStatus] = Query(None, description="Filter by status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=200)
) -> SignalsResponse:
    """
    List trading signals from the ML brain.
    
    Filter by status (active, executed, dismissed) or symbol.
    """
    # Mock data
    signals = [
        Signal(
            id="sig-001",
            symbol="AAPL",
            direction=SignalDirection.LONG,
            confidence=0.85,
            entry_price=150.00,
            stop_loss=145.00,
            take_profit=160.00,
            position_size=100,
            status=SignalStatus.ACTIVE,
            reasoning="Strong technical setup with bullish momentum"
        ),
        Signal(
            id="sig-002",
            symbol="TSLA",
            direction=SignalDirection.SHORT,
            confidence=0.72,
            entry_price=245.00,
            stop_loss=255.00,
            take_profit=225.00,
            position_size=50,
            status=SignalStatus.ACTIVE,
            reasoning="Overbought conditions, resistance rejection"
        ),
    ]
    
    # Apply filters
    if status:
        signals = [s for s in signals if s.status == status]
    if symbol:
        signals = [s for s in signals if s.symbol == symbol.upper()]
    
    active_count = len([s for s in signals if s.status == SignalStatus.ACTIVE])
    
    return SignalsResponse(
        signals=signals[:limit],
        total=len(signals),
        active_count=active_count
    )


@router.post(
    "/signals/generate",
    response_model=Signal,
    summary="Generate signal",
    description="Generate a new trading signal for a symbol."
)
async def generate_signal(request: GenerateSignalRequest) -> Signal:
    """
    Generate a new trading signal using the ML brain.
    
    Analyzes the symbol and returns a signal with entry, stop, and target.
    """
    return Signal(
        symbol=request.symbol.upper(),
        direction=SignalDirection.LONG,
        confidence=0.78,
        entry_price=150.00,
        stop_loss=145.00,
        take_profit=162.00,
        position_size=75,
        reasoning="Generated signal based on current market conditions"
    )


@router.post(
    "/signals/{signal_id}/execute",
    response_model=Order,
    summary="Execute signal",
    description="Execute a trading signal by creating an order."
)
async def execute_signal(
    signal_id: str = Path(..., description="Signal ID"),
    request: Optional[ExecuteSignalRequest] = None
) -> Order:
    """
    Execute a trading signal.
    
    Creates an order based on the signal parameters.
    """
    return Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=150.00,
        status=OrderStatus.SUBMITTED,
        signal_id=signal_id
    )


@router.post(
    "/signals/{signal_id}/dismiss",
    response_model=Signal,
    summary="Dismiss signal",
    description="Dismiss a trading signal without executing."
)
async def dismiss_signal(
    signal_id: str = Path(..., description="Signal ID")
) -> Signal:
    """
    Dismiss a signal without executing.
    
    Marks the signal as dismissed for feedback loop tracking.
    """
    return Signal(
        id=signal_id,
        symbol="AAPL",
        direction=SignalDirection.LONG,
        confidence=0.85,
        entry_price=150.00,
        stop_loss=145.00,
        position_size=100,
        status=SignalStatus.DISMISSED
    )


# ============================================================================
# Endpoints - Orders
# ============================================================================

@router.get(
    "/orders",
    response_model=OrdersResponse,
    summary="List orders",
    description="Get orders with optional status filter."
)
async def list_orders(
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=200)
) -> OrdersResponse:
    """
    List orders from the broker.
    """
    orders = [
        Order(
            id="ord-001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            limit_price=150.00,
            status=OrderStatus.FILLED,
            filled_quantity=100,
            filled_avg_price=149.95
        ),
    ]
    
    return OrdersResponse(orders=orders[:limit], total=len(orders))


@router.post(
    "/orders",
    response_model=Order,
    summary="Create order",
    description="Submit a new order to the broker."
)
async def create_order(request: CreateOrderRequest) -> Order:
    """
    Submit a new order.
    
    Validates risk limits before submission.
    """
    return Order(
        symbol=request.symbol.upper(),
        side=request.side,
        order_type=request.order_type,
        quantity=request.quantity,
        limit_price=request.limit_price,
        stop_price=request.stop_price,
        time_in_force=request.time_in_force,
        status=OrderStatus.SUBMITTED,
        signal_id=request.signal_id
    )


@router.delete(
    "/orders/{order_id}",
    summary="Cancel order",
    description="Cancel a pending order."
)
async def cancel_order(
    order_id: str = Path(..., description="Order ID")
) -> dict:
    """
    Cancel a pending order.
    """
    return {"status": "cancelled", "order_id": order_id}


# ============================================================================
# Endpoints - Positions
# ============================================================================

@router.get(
    "/positions",
    response_model=PositionsResponse,
    summary="List positions",
    description="Get all current positions."
)
async def list_positions() -> PositionsResponse:
    """
    List all current positions.
    """
    positions = [
        Position(
            symbol="AAPL",
            quantity=100,
            side="long",
            avg_entry_price=149.50,
            current_price=152.00,
            market_value=15200.00,
            unrealized_pnl=250.00,
            unrealized_pnl_percent=1.67,
            cost_basis=14950.00,
            opened_at=datetime(2025, 1, 10, 10, 30)
        ),
        Position(
            symbol="NVDA",
            quantity=25,
            side="long",
            avg_entry_price=850.00,
            current_price=875.00,
            market_value=21875.00,
            unrealized_pnl=625.00,
            unrealized_pnl_percent=2.94,
            cost_basis=21250.00,
            opened_at=datetime(2025, 1, 8, 14, 15)
        ),
    ]
    
    total_value = sum(p.market_value for p in positions)
    total_pnl = sum(p.unrealized_pnl for p in positions)
    
    return PositionsResponse(
        positions=positions,
        total_value=total_value,
        total_unrealized_pnl=total_pnl
    )


@router.get(
    "/positions/{symbol}",
    response_model=Position,
    summary="Get position",
    description="Get position details for a specific symbol."
)
async def get_position(
    symbol: str = Path(..., description="Ticker symbol")
) -> Position:
    """
    Get position details for a symbol.
    """
    return Position(
        symbol=symbol.upper(),
        quantity=100,
        side="long",
        avg_entry_price=149.50,
        current_price=152.00,
        market_value=15200.00,
        unrealized_pnl=250.00,
        unrealized_pnl_percent=1.67,
        cost_basis=14950.00,
        opened_at=datetime(2025, 1, 10, 10, 30)
    )


@router.delete(
    "/positions/{symbol}",
    summary="Close position",
    description="Close a position by selling all shares."
)
async def close_position(
    symbol: str = Path(..., description="Ticker symbol")
) -> dict:
    """
    Close a position by creating a market order to sell all shares.
    """
    return {
        "status": "closing",
        "symbol": symbol.upper(),
        "order_id": "ord-close-001"
    }


# ============================================================================
# Endpoints - Broker
# ============================================================================

@router.get(
    "/broker/status",
    response_model=BrokerStatusResponse,
    summary="Broker status",
    description="Get broker connection status."
)
async def get_broker_status() -> BrokerStatusResponse:
    """
    Get current broker connection status.
    """
    return BrokerStatusResponse(
        status=BrokerStatus.CONNECTED,
        broker="alpaca",
        connected_at=datetime(2025, 1, 13, 8, 0),
        last_heartbeat=datetime.utcnow(),
        paper_trading=True
    )


@router.get(
    "/broker/account",
    response_model=AccountInfo,
    summary="Account info",
    description="Get broker account information."
)
async def get_account_info() -> AccountInfo:
    """
    Get broker account details including buying power and margin.
    """
    return AccountInfo(
        account_id="PA12345678",
        buying_power=250000.00,
        cash=125000.00,
        portfolio_value=375000.00,
        equity=375000.00,
        margin_used=0.00,
        margin_available=125000.00,
        day_trades_remaining=3,
        pattern_day_trader=False
    )
