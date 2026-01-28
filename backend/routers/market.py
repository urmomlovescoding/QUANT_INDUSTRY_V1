"""
QUANT INDUSTRY - Market Data Router
====================================
Handles market data endpoints:
- Market status and hours
- Ticker prices and quotes
- Sector performance
- Top movers
- Stock screener

Extracted from main.py to improve maintainability.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Market Data"])

# ============== MODELS ==============


class TickerPrice(BaseModel):
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int


class ScreenerResult(BaseModel):
    symbol: str
    price: float
    change_pct: float
    volume: int
    rsi: float
    trend: str
    signal: str


# ============== DEPENDENCIES ==============


def _get_services():
    """Get required services, raising HTTPException if unavailable."""
    try:
        from services.data_service import get_data_service
        return get_data_service()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Data service not available"
        )


def _get_market_hours():
    """Get market hours service if available."""
    try:
        from services.market_hours import get_market_status, is_market_open
        return get_market_status, is_market_open
    except ImportError:
        return None, None


def _get_market_status_fallback() -> dict:
    """Fallback market status based on current Eastern time."""
    try:
        import pytz
        et = pytz.timezone("US/Eastern")
        now = datetime.now(et)
    except Exception:
        now = datetime.now()

    hour = now.hour
    weekday = now.weekday()
    is_weekend = weekday >= 5
    is_pre_market = not is_weekend and 4 <= hour < 9
    is_regular = not is_weekend and 9 <= hour < 16
    is_after_hours = not is_weekend and 16 <= hour < 20

    if is_regular:
        session = "regular"
        reason = "Regular Market Hours"
    elif is_pre_market:
        session = "pre_market"
        reason = "Pre-Market Trading"
    elif is_after_hours:
        session = "after_hours"
        reason = "After-Hours Trading"
    else:
        session = "closed"
        reason = "Weekend - Markets Closed" if is_weekend else "Markets Closed"

    return {
        "session": session,
        "is_open": is_regular,
        "is_pre_market": is_pre_market,
        "is_after_hours": is_after_hours,
        "is_weekend": is_weekend,
        "is_holiday": False,
        "is_early_close": False,
        "current_time_et": now.strftime("%Y-%m-%d %H:%M:%S ET"),
        "reason": reason,
    }


# ============== ROUTES ==============


@router.get("/market/status/v2")
async def get_market_status_v2():
    """
    Get current market hours status.

    Returns pre-market, regular, after-hours, and weekend/holiday detection.
    Uses the market hours service when available, falls back to timezone-based
    calculation.
    """
    get_status, _ = _get_market_hours()

    if get_status is not None:
        try:
            status = get_status()
            if isinstance(status, dict):
                return status
        except Exception as e:
            logger.warning(f"Market status service failed: {e}")

    return _get_market_status_fallback()


@router.get("/market/sectors/v2")
async def get_sectors_v2():
    """
    Get sector performance data.

    Returns sector weights and performance from live data when available,
    falling back to sector ETF calculations.
    """
    sector_weights = {
        "Technology": 28.5,
        "Healthcare": 13.2,
        "Financials": 12.8,
        "Consumer Disc.": 10.5,
        "Communication": 8.9,
        "Industrials": 8.5,
        "Consumer Staples": 6.2,
        "Energy": 4.5,
        "Utilities": 2.8,
        "Real Estate": 2.5,
        "Materials": 1.6,
    }

    try:
        data_service = _get_services()
        live_sectors = data_service.get_sectors()
        if live_sectors:
            for sector in live_sectors:
                sector["weight"] = sector_weights.get(sector["name"], 5.0)
            return live_sectors
    except HTTPException:
        pass
    except Exception as e:
        logger.warning(f"Live sector data failed: {e}")

    # Fallback: Calculate from sector ETFs
    sector_etfs = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Disc.": "XLY",
        "Communication": "XLC",
        "Industrials": "XLI",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Materials": "XLB",
    }

    sectors = []
    for name, weight in sector_weights.items():
        change_pct = 0.0
        etf = sector_etfs.get(name)
        if etf:
            try:
                data_service = _get_services()
                hist = data_service.get_historical(etf, "5d", "1d")
                if hist and len(hist) >= 2:
                    prev_close = hist[-2].close
                    curr_close = hist[-1].close
                    if prev_close > 0:
                        change_pct = ((curr_close - prev_close) / prev_close) * 100
            except Exception as e:
                logger.debug(f"Failed to get ETF data for {name} ({etf}): {e}")
        sectors.append({
            "name": name,
            "change_pct": round(change_pct, 2),
            "weight": weight,
        })

    return sectors


@router.get("/market/movers/v2")
async def get_movers_v2():
    """
    Get top market movers (gainers and losers).

    Returns live data from the data service when available.
    Returns an empty response when market data is unavailable rather than
    generating synthetic data.
    """
    try:
        data_service = _get_services()
        movers = data_service.get_movers()
        if movers and movers.get("gainers"):
            return movers
    except HTTPException:
        pass
    except Exception as e:
        logger.warning(f"Live movers data failed: {e}")

    return {
        "status": "unavailable",
        "gainers": [],
        "losers": [],
        "message": "Market movers data unavailable - requires market hours or premium data feed",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/screener/scan/v2")
async def scan_stocks_v2(
    tickers: str = Query(
        default="AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD",
        description="Comma-separated list of ticker symbols to scan",
    ),
):
    """
    Scan multiple stocks with real technical analysis.

    Calculates RSI, SMA-based trends, and generates buy/sell signals
    based on technical indicators derived from live market data.
    """
    from indicators.technical import calculate_rsi, calculate_sma

    symbol_list = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols per scan")

    data_service = _get_services()
    results: List[ScreenerResult] = []

    for symbol in symbol_list:
        try:
            quote = data_service.get_quote(symbol)
            historical = data_service.get_historical(symbol, period="3mo", interval="1d")

            if not historical or len(historical) < 20:
                continue

            closes = [bar.close for bar in historical]
            volumes = [bar.volume for bar in historical]

            # Calculate RSI
            rsi_values = calculate_rsi(closes, 14)
            rsi = float(rsi_values[-1]) if not np.isnan(rsi_values[-1]) else 50.0

            # Calculate trend from SMAs
            sma_20 = calculate_sma(closes, 20)
            sma_50 = calculate_sma(closes, 50)
            current_price = closes[-1]

            if not np.isnan(sma_20[-1]) and not np.isnan(sma_50[-1]):
                if current_price > sma_20[-1] > sma_50[-1]:
                    trend = "UP"
                elif current_price < sma_20[-1] < sma_50[-1]:
                    trend = "DOWN"
                else:
                    trend = "FLAT"
            else:
                trend = "FLAT"

            # Generate signal
            if rsi > 70:
                signal = "OVERBOUGHT"
            elif rsi < 30:
                signal = "OVERSOLD"
            elif trend == "UP" and rsi > 50:
                signal = "BUY"
            elif trend == "DOWN" and rsi < 50:
                signal = "SELL"
            else:
                signal = "HOLD"

            results.append(
                ScreenerResult(
                    symbol=symbol,
                    price=quote.price,
                    change_pct=quote.change_pct,
                    volume=volumes[-1] if volumes else quote.volume,
                    rsi=round(rsi, 2),
                    trend=trend,
                    signal=signal,
                )
            )
        except Exception as e:
            logger.warning(f"Screener failed for {symbol}: {e}")
            continue

    return results
