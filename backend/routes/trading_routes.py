"""
Trading Routes
==============
Endpoints for signals, positions, and trade execution.
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ._shared import (
    logger, SERVICES_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE, BROKER_ADAPTER_AVAILABLE,
    Signal, Position, ACTIVE_SIGNALS,
    get_data_service
)

router = APIRouter(prefix="/api", tags=["trading"])


# ============== SIGNALS ==============

@router.get("/signals/active")
async def get_active_signals(symbols: str = "NVDA,AAPL,TSLA,AMD,MSFT,GOOGL"):
    """Get active trading signals from PropFirm Brain V6"""
    import pandas as pd
    from indicators.technical import calculate_rsi, calculate_sma

    if PROPFIRM_BRAIN_V6_AVAILABLE and SERVICES_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            ds = get_data_service()
            signals = []
            symbol_list = [s.strip().upper() for s in symbols.split(",")]

            for idx, symbol in enumerate(symbol_list):
                try:
                    data = ds.get_historical(symbol, "60d", "1d")
                    if not data or len(data) < 50:
                        continue

                    df = pd.DataFrame([{
                        'timestamp': d.timestamp, 'open': d.open, 'high': d.high,
                        'low': d.low, 'close': d.close, 'volume': d.volume
                    } for d in data])
                    df.set_index('timestamp', inplace=True)

                    brain_signal = brain.generate_signal(df, symbol)
                    if brain_signal.get('direction') in ['HOLD', None]:
                        continue

                    direction = "LONG" if brain_signal.get('direction') in ['BUY', 'STRONG_BUY'] else "SHORT"
                    confidence = brain_signal.get('confidence', 0)

                    signals.append(Signal(
                        id=f"SIG{idx+1:03d}",
                        symbol=symbol,
                        direction=direction,
                        confidence=round(confidence, 2),
                        strategy=brain_signal.get('agreeing_strategies', ['Ensemble'])[0] if brain_signal.get('agreeing_strategies') else "Ensemble",
                        entry_price=round(brain_signal.get('current_price', 0), 2),
                        target=round(brain_signal.get('take_profit', 0), 2) if brain_signal.get('take_profit') else 0,
                        stop_loss=round(brain_signal.get('stop_loss', 0), 2) if brain_signal.get('stop_loss') else 0,
                        timestamp=brain_signal.get('timestamp', datetime.now().isoformat()),
                        status="ACTIVE" if confidence >= 0.7 else "PENDING"
                    ))
                except Exception as e:
                    logger.warning(f"Signal generation failed for {symbol}: {e}")
                    continue

            if signals:
                return signals
        except Exception as e:
            logger.error(f"Brain signal generation error: {e}")

    # Fallback to technical analysis
    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            signals = []
            symbol_list = [s.strip().upper() for s in symbols.split(",")]

            for idx, symbol in enumerate(symbol_list):
                try:
                    data = ds.get_historical(symbol, "60d", "1d")
                    if not data or len(data) < 20:
                        continue

                    closes = [d.close for d in data]
                    rsi_values = calculate_rsi(closes, 14)
                    sma_20 = calculate_sma(closes, 20)

                    current_price = closes[-1]
                    rsi = rsi_values[-1] if rsi_values else 50
                    sma = sma_20[-1] if sma_20 else current_price

                    if rsi < 30 and current_price > sma:
                        direction = "LONG"
                        confidence = min(0.9, (30 - rsi) / 30 + 0.5)
                    elif rsi > 70 and current_price < sma:
                        direction = "SHORT"
                        confidence = min(0.9, (rsi - 70) / 30 + 0.5)
                    else:
                        continue

                    signals.append(Signal(
                        id=f"SIG{idx+1:03d}",
                        symbol=symbol,
                        direction=direction,
                        confidence=round(confidence, 2),
                        strategy="Technical Analysis",
                        entry_price=round(current_price, 2),
                        target=round(current_price * (1.05 if direction == "LONG" else 0.95), 2),
                        stop_loss=round(current_price * (0.97 if direction == "LONG" else 1.03), 2),
                        timestamp=datetime.now().isoformat(),
                        status="ACTIVE" if confidence >= 0.7 else "PENDING"
                    ))
                except Exception as e:
                    logger.warning(f"Technical signal failed for {symbol}: {e}")
                    continue

            return signals
        except Exception as e:
            logger.error(f"Fallback signal generation error: {e}")

    return []


@router.get("/signals/all")
async def get_all_signals():
    """Get all signals (active and historical).
    NOTE: /api/signals is defined in api/routes/core_routes.py (authoritative).
    This endpoint is renamed to /signals/all to avoid conflict.
    """
    return list(ACTIVE_SIGNALS.values())


@router.post("/signals/{signal_id}/execute")
async def execute_signal(signal_id: str):
    """Execute a trading signal"""
    if signal_id not in ACTIVE_SIGNALS:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    signal = ACTIVE_SIGNALS[signal_id]
    try:
        if BROKER_ADAPTER_AVAILABLE and os.getenv("ALPACA_API_KEY"):
            from execution.broker_adapter import Order, OrderSide, OrderType
            from execution.alpaca_broker import AlpacaBroker
            broker = AlpacaBroker()
            order = Order(
                symbol=signal["symbol"],
                side=OrderSide.BUY if signal["direction"] == "LONG" else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=signal.get("quantity", 100)
            )
            result = await asyncio.to_thread(broker.submit_order, order)
            signal["status"] = "executed"
            return {"success": True, "order_id": result.id if result else None}

        signal["status"] = "executed"
        return {"success": True, "order_id": f"SIM-{signal_id}"}
    except Exception as e:
        logger.error(f"Error executing signal {signal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/signals/{signal_id}/dismiss")
async def dismiss_signal(signal_id: str):
    """Dismiss a trading signal"""
    if signal_id not in ACTIVE_SIGNALS:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    ACTIVE_SIGNALS[signal_id]["status"] = "dismissed"
    return {"success": True}


# ============== POSITIONS ==============

@router.get("/positions/broker")
async def get_positions():
    """Get open positions from broker or paper.
    NOTE: /api/positions is defined in api/routes/core_routes.py (authoritative).
    This endpoint is renamed to /positions/broker to avoid conflict.
    """
    if BROKER_ADAPTER_AVAILABLE:
        try:
            from execution.broker_adapter import PaperBroker
            broker = PaperBroker()
            broker_positions = broker.get_positions()
            if broker_positions:
                positions = []
                for idx, pos in enumerate(broker_positions):
                    pnl = pos.unrealized_pnl if hasattr(pos, 'unrealized_pnl') else (
                        (pos.current_price - pos.avg_entry_price) * pos.quantity
                    )
                    entry = pos.avg_entry_price if hasattr(pos, 'avg_entry_price') else pos.entry_price
                    pnl_pct = ((pos.current_price - entry) / entry * 100) if entry > 0 else 0

                    positions.append(Position(
                        id=f"POS{idx+1:03d}",
                        symbol=pos.symbol,
                        side=pos.side.upper(),
                        quantity=pos.quantity,
                        entry_price=round(entry, 2),
                        current_price=round(pos.current_price, 2),
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 2)
                    ))
                if positions:
                    return positions
        except Exception as e:
            logger.warning(f"Failed to get broker positions: {e}")

    return []


# ============== ORDERS ==============

_orders: Dict[str, Dict] = {}


class OrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: int
    order_type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"


@router.get("/orders")
async def get_orders():
    """Get all orders"""
    if BROKER_ADAPTER_AVAILABLE and os.getenv("ALPACA_API_KEY"):
        try:
            from execution.alpaca_broker import AlpacaBroker
            broker = AlpacaBroker()
            orders = broker.get_orders()
            return [{
                "id": o.id,
                "symbol": o.symbol,
                "side": o.side.value if hasattr(o.side, 'value') else o.side,
                "quantity": o.quantity,
                "filled_qty": o.filled_qty,
                "status": o.status,
            } for o in orders]
        except Exception as e:
            logger.warning(f"Broker orders error: {e}")
    return list(_orders.values())


@router.post("/orders")
async def submit_order(order: OrderRequest):
    """Submit a new order"""
    import random
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"

    if BROKER_ADAPTER_AVAILABLE and os.getenv("ALPACA_API_KEY"):
        try:
            from execution.broker_adapter import Order, OrderSide, OrderType
            from execution.alpaca_broker import AlpacaBroker
            broker = AlpacaBroker()
            broker_order = Order(
                symbol=order.symbol,
                side=OrderSide.BUY if order.side.lower() == "buy" else OrderSide.SELL,
                order_type=OrderType.MARKET if order.order_type.lower() == "market" else OrderType.LIMIT,
                quantity=order.quantity,
                limit_price=order.limit_price
            )
            result = broker.submit_order(broker_order)
            return {"id": result.id, "status": "submitted"}
        except Exception as e:
            logger.error(f"Broker order error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Paper trading
    _orders[order_id] = {
        "id": order_id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "filled_qty": order.quantity,
        "status": "filled",
        "created_at": datetime.now().isoformat(),
        "filled_at": datetime.now().isoformat()
    }
    return {"id": order_id, "status": "filled", "filled_qty": order.quantity}


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order"""
    if order_id in _orders:
        _orders[order_id]["status"] = "cancelled"
        return {"success": True}
    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


# ============== CLOSED TRADES ==============

@router.get("/trades/closed")
async def get_closed_trades(limit: int = 50, offset: int = 0):
    """Get closed trades history"""
    trades = []
    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            if brain and hasattr(brain, 'recent_trades'):
                for i, t in enumerate(brain.recent_trades[offset:offset+limit]):
                    trades.append({
                        "id": t.get("id", f"trade_{i}"),
                        "symbol": t.get("symbol", "UNKNOWN"),
                        "side": t.get("side", "long"),
                        "realizedPnl": t.get("pnl", 0),
                        "source": "brain_v6"
                    })
        except Exception as e:
            logger.debug(f"Closed trades fetch error: {e}")

    if not trades:
        return {"status": "unavailable", "trades": [], "_note": "No closed trades yet"}
    return trades


@router.get("/trades/stats")
async def get_trade_stats(range: str = "30d"):
    """Get trading statistics"""
    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            if brain and hasattr(brain, 'recent_trades') and brain.recent_trades:
                trades = brain.recent_trades
                winners = [t for t in trades if t.get('pnl', 0) > 0]
                total_pnl = sum(t.get('pnl', 0) for t in trades)
                win_rate = (len(winners) / len(trades) * 100) if trades else 0

                return {
                    "totalTrades": len(trades),
                    "winners": len(winners),
                    "losers": len(trades) - len(winners),
                    "winRate": round(win_rate, 1),
                    "totalPnl": round(total_pnl, 2),
                    "is_real": True
                }
        except Exception as e:
            logger.debug(f"Trade stats error: {e}")

    return {"status": "unavailable", "totalTrades": 0, "is_real": False}
