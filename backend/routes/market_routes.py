"""
Market Data Routes (supplemental)
==================================
Additional market endpoints: sectors, movers, live data.
NOTE: /market/status, /market/tickers, and /market/quote/{symbol}
are defined in api/routes/core_routes.py (authoritative).
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException

from ._shared import (
    logger, SERVICES_AVAILABLE, MARKET_HOURS_AVAILABLE,
    MARKET_DATA, MARKET_SYMBOLS, TickerPrice,
    get_data_service, refresh_market_data
)

router = APIRouter(prefix="/api", tags=["market"])


# NOTE: /market/status, /market/tickers, /market/quote/{symbol}
# are handled by api/routes/core_routes.py (loaded first, takes precedence).
# Removed from here to avoid duplicate route registrations.


# ============== SECTORS ==============

@router.get("/market/sectors")
async def get_sectors():
    """Get sector performance from live data"""
    sector_weights = {
        "Technology": 28.5, "Healthcare": 13.2, "Financials": 12.8,
        "Consumer Disc.": 10.5, "Communication": 8.9, "Industrials": 8.5,
        "Consumer Staples": 6.2, "Energy": 4.5, "Utilities": 2.8,
        "Real Estate": 2.5, "Materials": 1.6
    }

    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            live_sectors = ds.get_sectors()
            if live_sectors:
                for sector in live_sectors:
                    sector["weight"] = sector_weights.get(sector["name"], 5.0)
                return live_sectors
        except Exception as e:
            logger.warning(f"Live sector data failed: {e}")

    # Fallback
    sectors = []
    for name, weight in sector_weights.items():
        sectors.append({"name": name, "change_pct": 0.0, "weight": weight})
    return sectors


# ============== MOVERS ==============

@router.get("/market/movers")
async def get_movers():
    """Get top movers from live data"""
    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            movers = ds.get_movers()
            if movers and movers.get("gainers"):
                return movers
        except Exception as e:
            logger.warning(f"Live movers data failed: {e}")

    return {
        "status": "unavailable",
        "gainers": [],
        "losers": [],
        "message": "Market movers data unavailable - requires market hours or premium data feed",
        "timestamp": datetime.now().isoformat()
    }


# ============== LIVE DATA ==============

@router.get("/live/quote/{symbol}")
async def get_live_quote(symbol: str):
    """Get live quote using data service"""
    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            quote = ds.get_quote(symbol)
            return {
                "symbol": quote.symbol,
                "price": quote.price,
                "bid": quote.bid,
                "ask": quote.ask,
                "volume": quote.volume,
                "change": quote.change,
                "change_pct": quote.change_pct,
                "high": quote.high,
                "low": quote.low,
                "open": quote.open,
                "prev_close": quote.prev_close,
                "timestamp": quote.timestamp.isoformat(),
                "source": quote.source
            }
        except Exception as e:
            logger.error(f"Error getting live quote: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    symbol = symbol.upper()
    if symbol in MARKET_DATA:
        data = MARKET_DATA[symbol]
        return {
            "symbol": symbol,
            "price": data["price"],
            "change": data["change"],
            "change_pct": data["change_pct"],
            "source": "fallback"
        }
    raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")


@router.get("/live/historical/{symbol}")
async def get_live_historical(symbol: str, period: str = "1y", interval: str = "1d"):
    """Get live historical data using data service"""
    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            data = ds.get_historical(symbol, period, interval)
            return [
                {
                    "timestamp": d.timestamp.isoformat() if hasattr(d.timestamp, 'isoformat') else str(d.timestamp),
                    "open": d.open,
                    "high": d.high,
                    "low": d.low,
                    "close": d.close,
                    "volume": d.volume
                }
                for d in data
            ]
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=500, detail="Data service not available")
