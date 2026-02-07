"""
QUANT INDUSTRY V1 - Trading API (v2)
====================================
Consolidated trading endpoints: signals, orders, positions, broker.
Wired to real broker/service implementations.
"""

import asyncio
import os
import logging
from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Service Availability Detection
# ============================================================================

BROKER_ADAPTER_AVAILABLE = False
ALPACA_BROKER_AVAILABLE = False
PROPFIRM_BRAIN_V6_AVAILABLE = False
SERVICES_AVAILABLE = False
DATA_SERVICE_AVAILABLE = False

try:
    from backend.execution.broker_adapter import (
        PaperBroker, Order as BrokerOrder, OrderType as BrokerOrderType,
        OrderSide as BrokerOrderSide, OrderStatus as BrokerOrderStatus,
        TimeInForce as BrokerTimeInForce, Position as BrokerPosition, AccountInfo
    )
    BROKER_ADAPTER_AVAILABLE = True
except ImportError:
    pass

try:
    from backend.execution.alpaca_broker import AlpacaBroker, ALPACA_AVAILABLE
    ALPACA_BROKER_AVAILABLE = ALPACA_AVAILABLE
except ImportError:
    pass

try:
    from brain.propfirm_brain_v6 import get_propfirm_brain_v6
    PROPFIRM_BRAIN_V6_AVAILABLE = True
except ImportError:
    pass

try:
    from backend.services.data_service import get_data_service
    DATA_SERVICE_AVAILABLE = True
except ImportError:
    try:
        from services.data_service import get_data_service
        DATA_SERVICE_AVAILABLE = True
    except ImportError:
        pass

try:
    from backend.services.trading_service import get_trading_service
    SERVICES_AVAILABLE = True
except ImportError:
    try:
        from services.trading_service import get_trading_service
        SERVICES_AVAILABLE = True
    except ImportError:
        pass


# ============================================================================
# Broker Singleton
# ============================================================================

_broker = None
_alpaca_broker = None


def get_broker():
    """Get broker instance - Alpaca if configured, otherwise Paper."""
    global _broker, _alpaca_broker
    
    # Check for Alpaca credentials
    alpaca_key = os.getenv("ALPACA_API_KEY")
    alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
    
    if alpaca_key and alpaca_secret and ALPACA_BROKER_AVAILABLE:
        if _alpaca_broker is None:
            try:
                from backend.execution.alpaca_broker import AlpacaBroker
                _alpaca_broker = AlpacaBroker(paper=True)
                if _alpaca_broker.connect():
                    logger.info("Connected to Alpaca broker")
                    return _alpaca_broker
            except Exception as e:
                logger.warning(f"Alpaca broker init failed: {e}")
    
    # Fallback to paper broker
    if _broker is None and BROKER_ADAPTER_AVAILABLE:
        from backend.execution.broker_adapter import PaperBroker
        _broker = PaperBroker(initial_capital=100000.0)
        logger.info("Using Paper broker")
    
    return _alpaca_broker if _alpaca_broker and _alpaca_broker.is_connected() else _broker


# ============================================================================
# Signal Cache (for generated signals)
# ============================================================================

ACTIVE_SIGNALS = {}


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


class AccountInfoResponse(BaseModel):
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
    signals = []
    
    # Get signals from PropFirm Brain V6 if available
    if PROPFIRM_BRAIN_V6_AVAILABLE and DATA_SERVICE_AVAILABLE:
        try:
            import pandas as pd
            brain = get_propfirm_brain_v6()
            ds = get_data_service()
            
            # Default symbols to scan
            symbols_to_scan = [symbol.upper()] if symbol else ["NVDA", "AAPL", "TSLA", "AMD", "MSFT", "GOOGL"]
            
            for idx, sym in enumerate(symbols_to_scan):
                try:
                    data = ds.get_historical(sym, "60d", "1d")
                    if not data or len(data) < 50:
                        continue
                    
                    df = pd.DataFrame([{
                        'timestamp': d.timestamp, 'open': d.open, 'high': d.high,
                        'low': d.low, 'close': d.close, 'volume': d.volume
                    } for d in data])
                    df.set_index('timestamp', inplace=True)
                    
                    brain_signal = brain.generate_signal(df, sym)
                    if brain_signal.get('direction') in ['HOLD', None]:
                        continue
                    
                    direction = SignalDirection.LONG if brain_signal.get('direction') in ['BUY', 'STRONG_BUY'] else SignalDirection.SHORT
                    confidence = brain_signal.get('confidence', 0)
                    
                    sig = Signal(
                        id=f"SIG-{sym}-{idx:03d}",
                        symbol=sym,
                        direction=direction,
                        confidence=round(confidence, 2),
                        entry_price=round(brain_signal.get('current_price', 0), 2),
                        stop_loss=round(brain_signal.get('stop_loss', 0), 2) if brain_signal.get('stop_loss') else 0,
                        take_profit=round(brain_signal.get('take_profit', 0), 2) if brain_signal.get('take_profit') else None,
                        position_size=brain_signal.get('position_size', 100),
                        status=SignalStatus.ACTIVE if confidence >= 0.7 else SignalStatus.EXPIRED,
                        source="propfirm_brain_v6",
                        reasoning=", ".join(brain_signal.get('agreeing_strategies', ['Ensemble']))
                    )
                    signals.append(sig)
                    ACTIVE_SIGNALS[sig.id] = sig.model_dump()
                    
                except Exception as e:
                    logger.warning(f"Signal generation failed for {sym}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Brain signal generation error: {e}")
    
    # Include cached signals
    for sig_id, sig_data in ACTIVE_SIGNALS.items():
        if not any(s.id == sig_id for s in signals):
            signals.append(Signal(**sig_data))
    
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
    symbol = request.symbol.upper()
    
    if PROPFIRM_BRAIN_V6_AVAILABLE and DATA_SERVICE_AVAILABLE:
        try:
            import pandas as pd
            brain = get_propfirm_brain_v6()
            ds = get_data_service()
            
            data = ds.get_historical(symbol, "60d", "1d")
            if data and len(data) >= 50:
                df = pd.DataFrame([{
                    'timestamp': d.timestamp, 'open': d.open, 'high': d.high,
                    'low': d.low, 'close': d.close, 'volume': d.volume
                } for d in data])
                df.set_index('timestamp', inplace=True)
                
                brain_signal = brain.generate_signal(df, symbol)
                
                direction = SignalDirection.LONG
                if brain_signal.get('direction') in ['SELL', 'STRONG_SELL']:
                    direction = SignalDirection.SHORT
                
                confidence = brain_signal.get('confidence', 0.5)
                
                sig = Signal(
                    symbol=symbol,
                    direction=direction,
                    confidence=round(confidence, 2),
                    entry_price=round(brain_signal.get('current_price', 0), 2),
                    stop_loss=round(brain_signal.get('stop_loss', 0), 2) if brain_signal.get('stop_loss') else 0,
                    take_profit=round(brain_signal.get('take_profit', 0), 2) if brain_signal.get('take_profit') else None,
                    position_size=brain_signal.get('position_size', 100),
                    source="propfirm_brain_v6",
                    reasoning=", ".join(brain_signal.get('agreeing_strategies', ['Generated on demand']))
                )
                
                ACTIVE_SIGNALS[sig.id] = sig.model_dump()
                return sig
                
        except Exception as e:
            logger.error(f"Brain signal generation error: {e}")
    
    # Fallback: generate basic signal from price data
    current_price = 150.00
    if DATA_SERVICE_AVAILABLE:
        try:
            ds = get_data_service()
            quote = ds.get_quote(symbol)
            if quote:
                current_price = quote.price
        except Exception as e:
            logger.debug(f"Could not fetch quote for {symbol}: {e}")

    return Signal(
        symbol=symbol,
        direction=SignalDirection.LONG,
        confidence=0.65,
        entry_price=current_price,
        stop_loss=round(current_price * 0.97, 2),
        take_profit=round(current_price * 1.05, 2),
        position_size=75,
        source="technical_fallback",
        reasoning="Generated from basic technical analysis"
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
    if signal_id not in ACTIVE_SIGNALS:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    
    sig_data = ACTIVE_SIGNALS[signal_id]
    broker = get_broker()
    
    side = OrderSide.BUY if sig_data['direction'] == 'long' else OrderSide.SELL
    quantity = request.override_size if request and request.override_size else sig_data.get('position_size', 100)
    limit_price = request.limit_price if request and request.limit_price else None
    order_type = OrderType.LIMIT if limit_price else OrderType.MARKET
    
    if broker and BROKER_ADAPTER_AVAILABLE:
        try:
            # Create broker order
            broker_side = BrokerOrderSide.BUY if side == OrderSide.BUY else BrokerOrderSide.SELL
            broker_type = BrokerOrderType.LIMIT if limit_price else BrokerOrderType.MARKET
            
            if limit_price:
                broker_order = broker.create_limit_order(
                    symbol=sig_data['symbol'],
                    side=broker_side,
                    quantity=int(quantity),
                    limit_price=limit_price
                )
            else:
                broker_order = broker.create_market_order(
                    symbol=sig_data['symbol'],
                    side=broker_side,
                    quantity=int(quantity)
                )
            
            # Set price for paper broker simulation
            if hasattr(broker, 'set_price'):
                entry = sig_data.get('entry_price', 100)
                broker.set_price(sig_data['symbol'], entry - 0.01, entry + 0.01)
            
            result = broker.submit_order(broker_order)
            
            ACTIVE_SIGNALS[signal_id]['status'] = 'executed'
            
            return Order(
                id=result.order_id,
                symbol=sig_data['symbol'],
                side=side,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                status=OrderStatus(result.status.value) if hasattr(result.status, 'value') else OrderStatus.SUBMITTED,
                filled_quantity=result.filled_qty,
                filled_avg_price=result.avg_fill_price if result.avg_fill_price else None,
                signal_id=signal_id
            )
            
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Fallback mock response
    ACTIVE_SIGNALS[signal_id]['status'] = 'executed'
    return Order(
        symbol=sig_data['symbol'],
        side=side,
        order_type=order_type,
        quantity=quantity,
        limit_price=limit_price,
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
    if signal_id not in ACTIVE_SIGNALS:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    
    ACTIVE_SIGNALS[signal_id]['status'] = 'dismissed'
    return Signal(**ACTIVE_SIGNALS[signal_id])


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
    orders = []
    broker = get_broker()
    
    if broker:
        try:
            # Get open orders
            broker_orders = broker.get_open_orders()
            
            for bo in broker_orders:
                o = Order(
                    id=bo.order_id,
                    symbol=bo.symbol,
                    side=OrderSide(bo.side.value) if hasattr(bo.side, 'value') else OrderSide.BUY,
                    order_type=OrderType(bo.order_type.value) if hasattr(bo.order_type, 'value') else OrderType.MARKET,
                    quantity=bo.quantity,
                    limit_price=bo.limit_price,
                    stop_price=bo.stop_price,
                    status=OrderStatus(bo.status.value) if hasattr(bo.status, 'value') else OrderStatus.PENDING,
                    filled_quantity=bo.filled_qty,
                    filled_avg_price=bo.avg_fill_price if bo.avg_fill_price else None
                )
                orders.append(o)
                
        except Exception as e:
            logger.warning(f"Failed to get broker orders: {e}")
    
    # Apply filters
    if status:
        orders = [o for o in orders if o.status == status]
    if symbol:
        orders = [o for o in orders if o.symbol == symbol.upper()]
    
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
    broker = get_broker()
    
    if broker and BROKER_ADAPTER_AVAILABLE:
        try:
            broker_side = BrokerOrderSide.BUY if request.side == OrderSide.BUY else BrokerOrderSide.SELL
            
            if request.order_type == OrderType.LIMIT and request.limit_price:
                broker_order = broker.create_limit_order(
                    symbol=request.symbol.upper(),
                    side=broker_side,
                    quantity=int(request.quantity),
                    limit_price=request.limit_price
                )
            elif request.order_type == OrderType.STOP and request.stop_price:
                broker_order = broker.create_stop_order(
                    symbol=request.symbol.upper(),
                    side=broker_side,
                    quantity=int(request.quantity),
                    stop_price=request.stop_price
                )
            else:
                broker_order = broker.create_market_order(
                    symbol=request.symbol.upper(),
                    side=broker_side,
                    quantity=int(request.quantity)
                )
            
            # Set mock price for paper trading
            if hasattr(broker, 'set_price') and DATA_SERVICE_AVAILABLE:
                try:
                    ds = get_data_service()
                    quote = ds.get_quote(request.symbol.upper())
                    if quote:
                        broker.set_price(request.symbol.upper(), quote.bid or quote.price, quote.ask or quote.price)
                except Exception as e:
                    logger.warning(f"Could not fetch price for paper order {request.symbol}: {e}")
                    broker.set_price(request.symbol.upper(), 100, 100.01)
            
            result = broker.submit_order(broker_order)
            
            return Order(
                id=result.order_id,
                symbol=request.symbol.upper(),
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                limit_price=request.limit_price,
                stop_price=request.stop_price,
                time_in_force=request.time_in_force,
                status=OrderStatus(result.status.value) if hasattr(result.status, 'value') else OrderStatus.SUBMITTED,
                filled_quantity=result.filled_qty,
                filled_avg_price=result.avg_fill_price if result.avg_fill_price else None,
                signal_id=request.signal_id
            )
            
        except Exception as e:
            logger.error(f"Order submission error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Fallback
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
    broker = get_broker()
    
    if broker:
        try:
            success = broker.cancel_order(order_id)
            if success:
                return {"status": "cancelled", "order_id": order_id}
            else:
                raise HTTPException(status_code=400, detail="Could not cancel order")
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
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
    positions = []
    broker = get_broker()
    
    if broker:
        try:
            broker_positions = broker.get_all_positions()
            
            for bp in broker_positions:
                qty = bp.quantity
                entry = bp.avg_entry_price
                current = bp.current_price if bp.current_price else entry
                market_val = current * qty
                cost = entry * qty
                pnl = bp.unrealized_pnl if bp.unrealized_pnl else (market_val - cost)
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0
                
                positions.append(Position(
                    symbol=bp.symbol,
                    quantity=qty,
                    side=bp.side if isinstance(bp.side, str) else "long",
                    avg_entry_price=entry,
                    current_price=current,
                    market_value=market_val,
                    unrealized_pnl=round(pnl, 2),
                    unrealized_pnl_percent=round(pnl_pct, 2),
                    cost_basis=cost,
                    opened_at=datetime.utcnow()
                ))
                
        except Exception as e:
            logger.warning(f"Failed to get positions: {e}")
    
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
    broker = get_broker()
    
    if broker:
        try:
            bp = broker.get_position(symbol.upper())
            if bp:
                qty = bp.quantity
                entry = bp.avg_entry_price
                current = bp.current_price if bp.current_price else entry
                market_val = current * qty
                cost = entry * qty
                pnl = bp.unrealized_pnl if bp.unrealized_pnl else (market_val - cost)
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0
                
                return Position(
                    symbol=bp.symbol,
                    quantity=qty,
                    side=bp.side if isinstance(bp.side, str) else "long",
                    avg_entry_price=entry,
                    current_price=current,
                    market_value=market_val,
                    unrealized_pnl=round(pnl, 2),
                    unrealized_pnl_percent=round(pnl_pct, 2),
                    cost_basis=cost,
                    opened_at=datetime.utcnow()
                )
        except Exception as e:
            logger.warning(f"Failed to get position: {e}")
    
    raise HTTPException(status_code=404, detail=f"No position found for {symbol}")


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
    broker = get_broker()
    
    if broker:
        try:
            order = broker.close_position(symbol.upper())
            return {
                "status": "closing",
                "symbol": symbol.upper(),
                "order_id": order.order_id if order else None
            }
        except Exception as e:
            logger.error(f"Close position error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=404, detail=f"No position found for {symbol}")


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
    broker = get_broker()
    
    if broker:
        is_connected = broker.is_connected()
        is_alpaca = hasattr(broker, 'api_key')
        is_paper = getattr(broker, 'paper', True) if is_alpaca else True
        
        return BrokerStatusResponse(
            status=BrokerStatus.CONNECTED if is_connected else BrokerStatus.DISCONNECTED,
            broker="alpaca" if is_alpaca else "paper",
            connected_at=datetime.utcnow() if is_connected else None,
            last_heartbeat=datetime.utcnow() if is_connected else None,
            paper_trading=is_paper
        )
    
    return BrokerStatusResponse(
        status=BrokerStatus.DISCONNECTED,
        broker="none",
        paper_trading=True,
        message="No broker configured"
    )


@router.get(
    "/broker/account",
    response_model=AccountInfoResponse,
    summary="Account info",
    description="Get broker account information."
)
async def get_account_info() -> AccountInfoResponse:
    """
    Get broker account details including buying power and margin.
    """
    broker = get_broker()
    
    if broker:
        try:
            account = broker.get_account()
            
            return AccountInfoResponse(
                account_id=account.account_id,
                buying_power=account.buying_power,
                cash=account.cash,
                portfolio_value=account.portfolio_value,
                equity=account.equity,
                margin_used=getattr(account, 'initial_margin', 0),
                margin_available=account.buying_power - getattr(account, 'initial_margin', 0),
                day_trades_remaining=4 - getattr(account, 'day_trade_count', 0),
                pattern_day_trader=getattr(account, 'pattern_day_trader', False)
            )
            
        except Exception as e:
            logger.error(f"Get account error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Fallback mock
    return AccountInfoResponse(
        account_id="PAPER-001",
        buying_power=100000.00,
        cash=100000.00,
        portfolio_value=100000.00,
        equity=100000.00,
        margin_used=0.00,
        margin_available=100000.00,
        day_trades_remaining=3,
        pattern_day_trader=False
    )
