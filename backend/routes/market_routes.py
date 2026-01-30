"""
Market Data Routes
==================
Endpoints for market data, quotes, tickers, sectors, and movers.
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


# ============== MARKET STATUS ==============

@router.get("/market/status")
async def get_market_status():
    """Get current market hours status including pre-market, after-hours, and weekend/holiday detection"""
    if MARKET_HOURS_AVAILABLE:
        try:
            from services.market_hours import get_market_status as _get_status
            return _get_status()
        except Exception as e:
            logger.warning(f"Market status failed: {e}")

    # Fallback based on current time
    import pytz
    try:
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)
    except Exception:
        now = datetime.now()

    hour = now.hour
    weekday = now.weekday()
    is_weekend = weekday >= 5
    is_pre_market = not is_weekend and 4 <= hour < 9
    is_regular = not is_weekend and 9 <= hour < 16
    is_after_hours = not is_weekend and 16 <= hour < 20

    session = "closed"
    if is_regular:
        session = "regular"
    elif is_pre_market:
        session = "pre_market"
    elif is_after_hours:
        session = "after_hours"

    return {
        "session": session,
        "is_open": is_regular,
        "is_pre_market": is_pre_market,
        "is_after_hours": is_after_hours,
        "is_weekend": is_weekend,
        "is_holiday": False,
        "current_time_et": now.strftime("%Y-%m-%d %H:%M:%S ET"),
        "reason": "Weekend - Markets Closed" if is_weekend else (
            "Regular Market Hours" if is_regular else (
                "Pre-Market Trading" if is_pre_market else (
                    "After-Hours Trading" if is_after_hours else "Markets Closed"
                )
            )
        )
    }


# ============== TICKERS ==============

@router.get("/market/tickers")
async def get_tickers(symbols: str = "SPY,QQQ,DIA,IWM,VIX"):
    """Get live ticker prices from Alpaca/yfinance - includes VIX"""
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    results = []

    # Check MARKET_DATA cache first
    for symbol in symbol_list:
        if symbol in MARKET_DATA:
            data = MARKET_DATA[symbol]
            if data.get("price", 0) > 0:
                results.append(TickerPrice(
                    symbol=symbol,
                    price=data["price"],
                    change=data.get("change", 0),
                    change_pct=data.get("change_pct", 0),
                    volume=data.get("volume", 0)
                ))

    # If cache has all, return
    if len(results) == len(symbol_list):
        return results

    # Fetch missing from DataService
    missing = [s for s in symbol_list if s not in [r.symbol for r in results]]
    if missing and SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            fetch_symbols = ["^VIX" if s == "VIX" else s for s in missing]
            quotes = ds.get_quotes(fetch_symbols)
            for fetch_sym, display_sym in zip(fetch_symbols, missing):
                quote = quotes.get(fetch_sym)
                if quote and quote.price > 0:
                    MARKET_DATA[display_sym] = {
                        "price": quote.price,
                        "change": quote.change,
                        "change_pct": quote.change_pct,
                        "volume": quote.volume,
                        "source": quote.source
                    }
                    results.append(TickerPrice(
                        symbol=display_sym,
                        price=quote.price,
                        change=quote.change,
                        change_pct=quote.change_pct,
                        volume=quote.volume
                    ))
        except Exception as e:
            logger.warning(f"Live data fetch failed: {e}")

    return results


# ============== QUOTES ==============

@router.get("/market/quote/{symbol}")
async def get_quote(symbol: str):
    """Get detailed quote for a symbol from Alpaca/yfinance"""
    display_symbol = symbol.upper()
    fetch_symbol = "^VIX" if display_symbol == "VIX" else display_symbol

    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            quote = ds.get_quote(fetch_symbol)
            if quote:
                MARKET_DATA[display_symbol] = {
                    "price": quote.price,
                    "change": quote.change,
                    "change_pct": quote.change_pct,
                    "volume": quote.volume,
                    "high": quote.high,
                    "low": quote.low,
                    "open": quote.open,
                    "prev_close": quote.prev_close,
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "source": quote.source
                }
                market_session = getattr(quote, 'market_session', 'unknown')
                is_open = getattr(quote, 'is_market_open', True)

                return {
                    "symbol": display_symbol,
                    "price": quote.price,
                    "change": quote.change,
                    "change_pct": quote.change_pct,
                    "open": quote.open,
                    "high": quote.high,
                    "low": quote.low,
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "volume": quote.volume,
                    "prev_close": quote.prev_close,
                    "source": quote.source,
                    "market_session": market_session,
                    "is_market_open": is_open,
                    "avg_volume": 80000000,
                    "market_cap": 1500000000000,
                    "pe_ratio": 25.0,
                    "dividend_yield": 1.5,
                    "52w_high": quote.price * 1.3,
                    "52w_low": quote.price * 0.7,
                }
        except Exception as e:
            logger.warning(f"Live quote fetch failed for {display_symbol}: {e}")

    # Fallback
    if display_symbol not in MARKET_DATA:
        base_price = 50 + (hash(display_symbol) % 450)
        MARKET_DATA[display_symbol] = {
            "price": base_price,
            "change": 0,
            "change_pct": 0
        }

    data = MARKET_DATA[display_symbol]
    return {
        "symbol": display_symbol,
        "price": data["price"],
        "change": data["change"],
        "change_pct": data["change_pct"],
        "open": data.get("open", data["price"]),
        "high": data.get("high", data["price"]),
        "low": data.get("low", data["price"]),
        "volume": data.get("volume", 0),
        "source": data.get("source", "fallback"),
    }


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
