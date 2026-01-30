"""
Broker Routes
=============
Endpoints for broker connections, account info, and order management.
"""

import os
import time
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from ._shared import logger, BROKER_ADAPTER_AVAILABLE, get_data_service

router = APIRouter(prefix="/api", tags=["broker"])


# Paper broker instance
_paper_broker = None

def get_paper_broker():
    global _paper_broker
    if _paper_broker is None and BROKER_ADAPTER_AVAILABLE:
        from execution.broker_adapter import PaperBroker
        _paper_broker = PaperBroker(initial_capital=100000.0)
    return _paper_broker


# ============== BROKER STATUS ==============

@router.get("/broker/status")
async def get_broker_status():
    """Get broker status"""
    if not BROKER_ADAPTER_AVAILABLE:
        return {"available": False}
    try:
        broker = get_paper_broker()
        return {"available": True, "name": broker.name, "connected": broker.is_connected(), "mode": "paper"}
    except Exception as e:
        return {"available": True, "error": str(e)}


@router.get("/broker/account")
async def get_broker_account():
    """Get broker account info"""
    if not BROKER_ADAPTER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Broker not available")
    try:
        broker = get_paper_broker()
        account = broker.get_account()
        return {
            "account_id": account.account_id,
            "buying_power": account.buying_power,
            "cash": account.cash,
            "equity": account.equity,
            "portfolio_value": account.portfolio_value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/broker/positions")
async def get_broker_positions():
    """Get all open positions"""
    if not BROKER_ADAPTER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Broker not available")
    try:
        broker = get_paper_broker()
        positions = broker.get_positions()
        return {
            "positions": [{
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "side": pos.side,
                "avg_entry_price": pos.avg_entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "market_value": pos.market_value
            } for pos in positions]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/broker/order")
async def submit_broker_order(order_data: dict):
    """Submit an order"""
    if not BROKER_ADAPTER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Broker not available")
    try:
        from execution.broker_adapter import OrderSide
        broker = get_paper_broker()

        if "price" in order_data:
            broker.set_price(order_data["symbol"], order_data["price"], order_data["price"] * 1.0001)

        side = OrderSide.BUY if order_data["side"].lower() == "buy" else OrderSide.SELL
        order = broker.create_market_order(
            symbol=order_data["symbol"],
            side=side,
            quantity=order_data["quantity"]
        )
        result = broker.submit_order(order)

        return {
            "order_id": result.order_id,
            "status": result.status.value,
            "filled_qty": result.filled_qty,
            "avg_fill_price": result.avg_fill_price
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== CONNECTIONS ==============

API_CONNECTIONS = {}


@router.get("/connections")
async def get_connections():
    """Get all API connections"""
    alpaca_connected = bool(os.getenv("ALPACA_API_KEY"))
    tradier_connected = bool(os.getenv("TRADIER_API_KEY"))

    alpaca_latency = None
    if alpaca_connected:
        try:
            start = time.perf_counter()
            ds = get_data_service()
            if ds:
                ds.get_quote("SPY")
                alpaca_latency = round((time.perf_counter() - start) * 1000, 0)
        except Exception:
            pass

    return [
        {
            "id": "conn_alpaca",
            "name": "Alpaca Paper",
            "type": "broker",
            "provider": "alpaca",
            "status": "connected" if alpaca_connected else "disconnected",
            "apiKey": "***" + (os.getenv("ALPACA_API_KEY", "")[-4:] if os.getenv("ALPACA_API_KEY") else ""),
            "latency": alpaca_latency,
            "rateLimit": 200,
            "features": ["trading", "streaming", "account"],
            "isPaper": True
        },
        {
            "id": "conn_tradier",
            "name": "Tradier",
            "type": "data",
            "provider": "tradier",
            "status": "connected" if tradier_connected else "disconnected",
            "apiKey": "***" + (os.getenv("TRADIER_API_KEY", "")[-4:] if os.getenv("TRADIER_API_KEY") else ""),
            "latency": None,
            "rateLimit": 120,
            "features": ["quotes", "options", "historical"],
            "isPaper": False
        }
    ]


@router.post("/connections/{connection_id}/test")
async def test_connection(connection_id: str):
    """Test an API connection"""
    start_time = time.time()
    success = False
    error = None
    latency = None

    try:
        if "alpaca" in connection_id:
            if os.getenv("ALPACA_API_KEY"):
                ds = get_data_service()
                quote = ds.get_quote("SPY")
                if quote:
                    success = True
                    latency = int((time.time() - start_time) * 1000)
            else:
                error = "API key not configured"
        elif "tradier" in connection_id:
            if os.getenv("TRADIER_API_KEY"):
                success = True
                latency = int((time.time() - start_time) * 1000)
            else:
                error = "API key not configured"
        else:
            error = f"Unknown connection: {connection_id}"
    except Exception as e:
        error = str(e)

    return {"success": success, "latency": latency, "error": error}


@router.post("/connections")
async def add_connection(connection: Dict[str, Any]):
    """Add a new API connection"""
    conn_id = f"conn_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    API_CONNECTIONS[conn_id] = {**connection, "id": conn_id, "status": "disconnected"}
    return {"id": conn_id, "status": "created"}


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str):
    """Delete an API connection"""
    API_CONNECTIONS.pop(connection_id, None)
    return {"status": "deleted"}
