"""
News & Events API Routes
========================
REST endpoints for news feed, sentiment, earnings calendar, economic events, etc.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news-events", tags=["News & Events"])

# Try to import backend modules
try:
    from news_events.news_feed import NewsFeed
    from news_events.sentiment_analyzer import SentimentAnalyzer
    from news_events.event_calendar import EventCalendar
    from news_events.headline_parser import HeadlineParser
    from news_events.event_signals import EventSignalGenerator

    news_feed = NewsFeed()
    sentiment = SentimentAnalyzer()
    calendar = EventCalendar()
    parser = HeadlineParser()
    signals = EventSignalGenerator()
    MODULES_LOADED = True
except ImportError as e:
    logger.warning(f"News events modules not fully loaded: {e}")
    MODULES_LOADED = False


@router.get("/news")
async def get_news(
    symbol: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(20, le=100)
):
    """Get news feed with sentiment."""
    return {
        "status": "unavailable",
        "message": "Connect news data provider for real-time news and sentiment",
        "news": [],
        "total": 0,
        "filters": {"symbol": symbol, "category": category}
    }


@router.get("/sentiment/market")
async def get_market_sentiment():
    """Get overall market sentiment."""
    return {
        "status": "unavailable",
        "message": "Connect news data provider for real-time news and sentiment",
        "overall_score": None,
        "overall_label": None,
        "confidence": None,
        "components": {},
        "sector_sentiment": {},
        "trending_topics": [],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/sentiment/{symbol}")
async def get_symbol_sentiment(symbol: str):
    """Get sentiment for a specific symbol."""
    return {
        "status": "unavailable",
        "message": "Connect news data provider for real-time news and sentiment",
        "symbol": symbol,
        "overall_score": None,
        "overall_label": None,
        "confidence": None,
        "news_count_24h": 0,
        "mention_count_24h": 0,
        "sentiment_trend": None,
        "sentiment_history": [],
        "key_drivers": [],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/earnings")
async def get_earnings_calendar(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbol: Optional[str] = None
):
    """Get upcoming earnings calendar."""
    return {
        "status": "unavailable",
        "message": "Connect news data provider for real-time news and sentiment",
        "earnings": [],
        "count": 0
    }


@router.get("/economic")
async def get_economic_calendar(
    importance: Optional[str] = Query(None, description="high, medium, low"),
    country: Optional[str] = None
):
    """Get economic events calendar."""
    return {
        "status": "unavailable",
        "message": "Connect news data provider for real-time news and sentiment",
        "events": [],
        "count": 0
    }


@router.get("/signals")
async def get_event_signals(
    symbol: Optional[str] = None,
    signal_type: Optional[str] = None
):
    """Get event-driven trading signals."""
    return {
        "status": "unavailable",
        "message": "Connect news data provider for real-time news and sentiment",
        "signals": [],
        "count": 0
    }


@router.post("/analyze-headline")
async def analyze_headline(body: dict = Body(...)):
    """Analyze a headline for trading signals."""
    headline = body.get("headline", "")

    if not headline:
        raise HTTPException(status_code=400, detail="Headline required")

    # Simple keyword-based analysis (real logic, no external data needed)
    bullish_words = ["beats", "raises", "upgrades", "record", "growth", "surge", "buy"]
    bearish_words = ["misses", "cuts", "downgrades", "decline", "falls", "sell", "weak"]

    headline_lower = headline.lower()
    bullish_count = sum(1 for w in bullish_words if w in headline_lower)
    bearish_count = sum(1 for w in bearish_words if w in headline_lower)

    sentiment = (bullish_count - bearish_count) / max(1, bullish_count + bearish_count)

    # Extract potential symbols
    import re
    symbols = re.findall(r'\b[A-Z]{2,5}\b', headline)
    symbols = [s for s in symbols if s not in ["CEO", "CFO", "IPO", "GDP", "CPI", "THE", "AND", "FOR"]]

    return {
        "headline": headline,
        "sentiment_score": round(sentiment, 2),
        "sentiment_label": "bullish" if sentiment > 0.2 else "bearish" if sentiment < -0.2 else "neutral",
        "confidence": round(0.5 + abs(sentiment) * 0.4, 2),
        "detected_symbols": symbols[:5],
        "detected_action": "beat" if "beat" in headline_lower else "miss" if "miss" in headline_lower else "upgrade" if "upgrade" in headline_lower else "downgrade" if "downgrade" in headline_lower else "unknown",
        "trading_relevance": round(0.5 + abs(sentiment) * 0.5, 2),
        "timestamp": datetime.now().isoformat()
    }
