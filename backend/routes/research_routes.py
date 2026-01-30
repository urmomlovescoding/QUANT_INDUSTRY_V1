"""
Research Routes
===============
Endpoints for research, screener, 13F holdings, SEC filings, and earnings.
"""

import numpy as np
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ._shared import (
    logger, SERVICES_AVAILABLE, ScreenerResult,
    get_data_service, get_research_service
)

router = APIRouter(prefix="/api", tags=["research"])


# ============== SCREENER ==============

@router.get("/screener/scan")
async def scan_stocks(tickers: str = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD"):
    """Scan multiple stocks with real technical analysis"""
    symbol_list = [s.strip().upper() for s in tickers.split(",")]
    results = []

    if SERVICES_AVAILABLE:
        ds = get_data_service()
        from indicators.technical import calculate_rsi, calculate_sma

        for symbol in symbol_list:
            try:
                quote = ds.get_quote(symbol)
                historical = ds.get_historical(symbol, period="3mo", interval="1d")

                if not historical or len(historical) < 20:
                    continue

                closes = [bar.close for bar in historical]
                rsi_values = calculate_rsi(closes, 14)
                sma_20 = calculate_sma(closes, 20)
                sma_50 = calculate_sma(closes, 50)

                rsi = float(rsi_values[-1]) if not np.isnan(rsi_values[-1]) else 50.0
                current_price = closes[-1]

                if not np.isnan(sma_20[-1]) and not np.isnan(sma_50[-1]):
                    trend = "UP" if current_price > sma_20[-1] > sma_50[-1] else (
                        "DOWN" if current_price < sma_20[-1] < sma_50[-1] else "FLAT")
                else:
                    trend = "FLAT"

                signal = "OVERBOUGHT" if rsi > 70 else "OVERSOLD" if rsi < 30 else (
                    "BUY" if trend == "UP" and rsi > 50 else "SELL" if trend == "DOWN" and rsi < 50 else "HOLD")

                results.append(ScreenerResult(
                    symbol=symbol,
                    price=quote.price,
                    change_pct=quote.change_pct,
                    volume=quote.volume,
                    rsi=round(rsi, 2),
                    trend=trend,
                    signal=signal
                ))
            except Exception as e:
                logger.warning(f"Screener failed for {symbol}: {e}")

    return results


class ScreenerFilters(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_volume: Optional[int] = None
    min_change_pct: Optional[float] = None
    max_change_pct: Optional[float] = None


@router.post("/screener/scan")
async def screener_scan_post(filters: ScreenerFilters):
    """Scan stocks with filters (POST version)"""
    tickers = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,NFLX,CRM"
    symbol_list = [s.strip().upper() for s in tickers.split(",")]
    results = []

    if SERVICES_AVAILABLE:
        ds = get_data_service()
        for symbol in symbol_list:
            try:
                quote = ds.get_quote(symbol)
                if not quote:
                    continue
                if filters.min_price and quote.price < filters.min_price:
                    continue
                if filters.max_price and quote.price > filters.max_price:
                    continue
                if filters.min_volume and quote.volume < filters.min_volume:
                    continue
                if filters.min_change_pct and quote.change_pct < filters.min_change_pct:
                    continue
                if filters.max_change_pct and quote.change_pct > filters.max_change_pct:
                    continue

                results.append({
                    "symbol": symbol,
                    "price": quote.price,
                    "change_pct": quote.change_pct,
                    "volume": quote.volume,
                    "trend": "bullish" if quote.change_pct > 0 else "bearish"
                })
            except Exception as e:
                logger.warning(f"Screener error for {symbol}: {e}")

    return results


@router.get("/screener/presets")
async def get_screener_presets():
    """Get screener presets"""
    return [
        {"id": "momentum", "name": "Momentum Breakouts", "filters": {"min_change_pct": 2}},
        {"id": "oversold", "name": "Oversold Bounces", "filters": {"max_change_pct": -3}},
        {"id": "high-volume", "name": "High Volume", "filters": {"min_volume": 5000000}}
    ]


# ============== RESEARCH ==============

@router.get("/research/13f/{symbol}")
async def get_13f_holdings(symbol: str):
    """Get 13F institutional holdings"""
    research = get_research_service()
    response = research.get_13f_holdings(symbol)
    return response.to_dict()


@router.get("/research/sec/{symbol}")
async def get_sec_filings(symbol: str, limit: int = 20):
    """Get SEC filings"""
    research = get_research_service()
    response = research.get_sec_filings(symbol, limit)
    return response.to_dict()


@router.get("/research/darkpool/{symbol}")
async def get_dark_pool_data(symbol: str):
    """Get dark pool activity"""
    research = get_research_service()
    response = research.get_dark_pool_data(symbol)
    return response.to_dict()


@router.get("/research/earnings")
async def get_earnings_calendar(symbols: str = ""):
    """Get earnings calendar"""
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    research = get_research_service()
    response = research.get_earnings(symbols=symbol_list)
    return response.to_dict()


@router.get("/research/earnings/{symbol}")
async def get_earnings_by_symbol(symbol: str):
    """Get earnings data for a specific symbol"""
    research = get_research_service()
    response = research.get_earnings(symbol=symbol)
    return response.to_dict()


# ============== NEWS ==============

@router.get("/news")
async def get_news(symbols: str = None, limit: int = 20):
    """Get market news"""
    return {
        "status": "unavailable",
        "articles": [],
        "message": "News API not configured",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/news/sentiment")
async def get_market_sentiment():
    """Get overall market sentiment"""
    return {
        "status": "unavailable",
        "overall": None,
        "_note": "Real sentiment analysis requires NLP processing",
        "timestamp": datetime.now().isoformat()
    }
