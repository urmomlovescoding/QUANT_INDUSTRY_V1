"""
QUANT INDUSTRY - Order Book API Routes
=====================================
REST API endpoints for order book data and HFT metrics.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/orderbook", tags=["orderbook"])


class PriceLevelResponse(BaseModel):
    """Price level in order book"""
    price: float
    size: int
    total: int = 0


class OrderBookSnapshot(BaseModel):
    """Order book snapshot response"""
    symbol: str
    timestamp: str
    bids: List[PriceLevelResponse]
    asks: List[PriceLevelResponse]
    spread: float
    spread_bps: float
    imbalance: float
    microprice: float
    mid_price: float


class OrderBookMetricsResponse(BaseModel):
    """Detailed order book metrics"""
    symbol: str
    timestamp: str
    mid_price: float
    spread: float
    spread_bps: float
    microprice: float
    bid_depth_5: float
    ask_depth_5: float
    bid_depth_10: float
    ask_depth_10: float
    imbalance_1: float
    imbalance_5: float
    imbalance_10: float
    bid_pressure: float
    ask_pressure: float
    net_pressure: float
    vpin: float


# In-memory order book storage (would be Redis in production)
_order_books = {}


def get_or_create_book(symbol: str):
    """Get or create order book for symbol"""
    if symbol not in _order_books:
        try:
            from hft import OrderBook
            _order_books[symbol] = OrderBook(symbol)
            
            # Initialize with some mock data for demo
            from hft import OrderSide
            book = _order_books[symbol]
            
            # Generate realistic order book levels
            import random
            base_price = 150.0 if symbol == "SPY" else 100.0
            
            for i in range(10):
                bid_price = base_price - 0.01 * (i + 1)
                ask_price = base_price + 0.01 * (i + 1)
                bid_size = random.randint(100, 5000)
                ask_size = random.randint(100, 5000)
                
                book.update_level(OrderSide.BID, bid_price, bid_size)
                book.update_level(OrderSide.ASK, ask_price, ask_size)
        except ImportError:
            return None
    
    return _order_books.get(symbol)


@router.get("/{symbol}/snapshot", response_model=OrderBookSnapshot)
async def get_orderbook_snapshot(
    symbol: str,
    levels: int = Query(10, description="Number of levels", ge=1, le=20)
):
    """Get order book snapshot for a symbol"""
    book = get_or_create_book(symbol.upper())
    
    if book is None:
        raise HTTPException(status_code=404, detail=f"Order book not available for {symbol}")
    
    try:
        snapshot = book.get_snapshot()
        metrics = book.get_metrics()
        
        # Convert to response format
        bids = []
        total_bid = 0
        for level in snapshot.bids[:levels]:
            total_bid += level.size
            bids.append(PriceLevelResponse(
                price=level.price,
                size=level.size,
                total=total_bid
            ))
        
        asks = []
        total_ask = 0
        for level in snapshot.asks[:levels]:
            total_ask += level.size
            asks.append(PriceLevelResponse(
                price=level.price,
                size=level.size,
                total=total_ask
            ))
        
        return OrderBookSnapshot(
            symbol=symbol.upper(),
            timestamp=datetime.now().isoformat(),
            bids=bids,
            asks=asks,
            spread=metrics.spread,
            spread_bps=metrics.spread_bps,
            imbalance=metrics.imbalance_1,
            microprice=metrics.microprice,
            mid_price=metrics.mid_price
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/metrics", response_model=OrderBookMetricsResponse)
async def get_orderbook_metrics(symbol: str):
    """Get detailed order book metrics for a symbol"""
    book = get_or_create_book(symbol.upper())
    
    if book is None:
        raise HTTPException(status_code=404, detail=f"Order book not available for {symbol}")
    
    try:
        metrics = book.get_metrics()
        vpin = book.calculate_vpin() if len(book.trades) > 100 else 0.5
        
        return OrderBookMetricsResponse(
            symbol=symbol.upper(),
            timestamp=datetime.now().isoformat(),
            mid_price=metrics.mid_price,
            spread=metrics.spread,
            spread_bps=metrics.spread_bps,
            microprice=metrics.microprice,
            bid_depth_5=metrics.bid_depth_5,
            ask_depth_5=metrics.ask_depth_5,
            bid_depth_10=metrics.bid_depth_10,
            ask_depth_10=metrics.ask_depth_10,
            imbalance_1=metrics.imbalance_1,
            imbalance_5=metrics.imbalance_5,
            imbalance_10=metrics.imbalance_10,
            bid_pressure=metrics.bid_pressure,
            ask_pressure=metrics.ask_pressure,
            net_pressure=metrics.net_pressure,
            vpin=vpin
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/signal")
async def get_orderbook_signal(symbol: str):
    """Get trading signal derived from order book state"""
    book = get_or_create_book(symbol.upper())
    
    if book is None:
        raise HTTPException(status_code=404, detail=f"Order book not available for {symbol}")
    
    try:
        signal = book.get_signal()
        
        return {
            "symbol": symbol.upper(),
            "timestamp": datetime.now().isoformat(),
            "signal": signal["signal"],
            "confidence": signal["confidence"],
            "imbalance": signal["imbalance"],
            "spread_bps": signal["spread_bps"],
            "vpin": signal["vpin"],
            "direction": "LONG" if signal["signal"] > 0.3 else "SHORT" if signal["signal"] < -0.3 else "NEUTRAL"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{symbol}/update")
async def update_orderbook(
    symbol: str,
    side: str = Query(..., description="BID or ASK"),
    price: float = Query(..., description="Price level"),
    size: int = Query(..., description="Size (0 to remove)")
):
    """Update a price level in the order book"""
    book = get_or_create_book(symbol.upper())
    
    if book is None:
        raise HTTPException(status_code=404, detail=f"Order book not available for {symbol}")
    
    try:
        from hft import OrderSide
        
        order_side = OrderSide.BID if side.upper() == "BID" else OrderSide.ASK
        book.update_level(order_side, price, size)
        
        return {"status": "updated", "symbol": symbol.upper(), "side": side.upper(), "price": price, "size": size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/impact")
async def estimate_price_impact(
    symbol: str,
    side: str = Query(..., description="BUY or SELL"),
    size: int = Query(..., description="Order size")
):
    """Estimate price impact for a market order"""
    book = get_or_create_book(symbol.upper())
    
    if book is None:
        raise HTTPException(status_code=404, detail=f"Order book not available for {symbol}")
    
    try:
        from hft import OrderSide
        
        order_side = OrderSide.BID if side.upper() == "BUY" else OrderSide.ASK
        impact = book.estimate_impact(order_side, size)
        
        return {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "size": size,
            "estimated_impact_pct": impact * 100,
            "estimated_impact_bps": impact * 10000
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
