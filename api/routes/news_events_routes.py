"""
News & Events API Routes
========================
REST endpoints for news feed, sentiment, earnings calendar, economic events, etc.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import random

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


SAMPLE_HEADLINES = [
    ("Fed signals potential rate cuts in 2025", "Reuters", "macro", 0.3),
    ("Apple beats Q4 earnings estimates, raises guidance", "CNBC", "earnings", 0.8),
    ("NVIDIA announces new AI chip architecture", "Bloomberg", "tech", 0.6),
    ("Tesla misses delivery expectations", "WSJ", "earnings", -0.5),
    ("Oil prices surge on Middle East tensions", "Reuters", "commodities", -0.2),
    ("Amazon expands same-day delivery to 15 new cities", "TechCrunch", "retail", 0.4),
    ("Goldman Sachs upgrades Microsoft to Buy", "MarketWatch", "analyst", 0.7),
    ("China GDP growth slows to 4.5%", "FT", "macro", -0.3),
    ("Crypto ETF sees record inflows", "CoinDesk", "crypto", 0.5),
    ("JPMorgan reports record quarterly profit", "Bloomberg", "earnings", 0.6),
]


@router.get("/news")
async def get_news(
    symbol: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(20, le=100)
):
    """Get news feed with sentiment."""
    news = []
    
    for i in range(min(limit, len(SAMPLE_HEADLINES) * 3)):
        headline, source, cat, sent = random.choice(SAMPLE_HEADLINES)
        
        if category and cat != category:
            continue
            
        # Add some variation
        sent_variation = sent + random.uniform(-0.2, 0.2)
        
        news.append({
            "id": f"NEWS-{random.randint(10000, 99999)}",
            "headline": headline,
            "source": source,
            "category": cat,
            "symbols": [symbol] if symbol else random.sample(["SPY", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"], k=random.randint(1, 3)),
            "sentiment_score": round(max(-1, min(1, sent_variation)), 2),
            "sentiment_label": "bullish" if sent_variation > 0.2 else "bearish" if sent_variation < -0.2 else "neutral",
            "relevance_score": round(random.uniform(0.5, 1.0), 2),
            "timestamp": (datetime.now() - timedelta(minutes=i * random.randint(5, 60))).isoformat(),
            "url": f"https://example.com/news/{random.randint(1000, 9999)}"
        })
    
    return {
        "news": news[:limit],
        "total": len(news),
        "filters": {"symbol": symbol, "category": category}
    }


@router.get("/sentiment/market")
async def get_market_sentiment():
    """Get overall market sentiment."""
    return {
        "overall_score": round(random.uniform(-0.3, 0.5), 2),
        "overall_label": random.choice(["bullish", "neutral", "slightly_bullish"]),
        "confidence": round(random.uniform(0.6, 0.9), 2),
        "components": {
            "news_sentiment": round(random.uniform(-0.2, 0.4), 2),
            "social_sentiment": round(random.uniform(-0.3, 0.5), 2),
            "analyst_sentiment": round(random.uniform(0, 0.4), 2),
            "options_sentiment": round(random.uniform(-0.2, 0.3), 2)
        },
        "sector_sentiment": {
            "Technology": round(random.uniform(0.1, 0.6), 2),
            "Healthcare": round(random.uniform(-0.2, 0.3), 2),
            "Financials": round(random.uniform(0, 0.4), 2),
            "Energy": round(random.uniform(-0.3, 0.2), 2),
            "Consumer": round(random.uniform(-0.1, 0.3), 2)
        },
        "trending_topics": ["AI", "Fed rates", "Earnings", "China"],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/sentiment/{symbol}")
async def get_symbol_sentiment(symbol: str):
    """Get sentiment for a specific symbol."""
    base_sentiment = random.uniform(-0.3, 0.5)
    
    return {
        "symbol": symbol,
        "overall_score": round(base_sentiment, 2),
        "overall_label": "bullish" if base_sentiment > 0.2 else "bearish" if base_sentiment < -0.2 else "neutral",
        "confidence": round(random.uniform(0.5, 0.9), 2),
        "news_count_24h": random.randint(5, 50),
        "mention_count_24h": random.randint(100, 5000),
        "sentiment_trend": random.choice(["improving", "stable", "declining"]),
        "sentiment_history": [
            {
                "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                "score": round(base_sentiment + random.uniform(-0.2, 0.2), 2)
            }
            for i in range(24)
        ],
        "key_drivers": [
            {"topic": "Earnings report", "impact": round(random.uniform(0.1, 0.5), 2)},
            {"topic": "Analyst upgrade", "impact": round(random.uniform(0.1, 0.3), 2)},
            {"topic": "Product launch", "impact": round(random.uniform(0.05, 0.2), 2)}
        ],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/earnings")
async def get_earnings_calendar(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbol: Optional[str] = None
):
    """Get upcoming earnings calendar."""
    earnings = []
    
    companies = [
        ("AAPL", "Apple Inc", 2.15, 2.10),
        ("MSFT", "Microsoft Corp", 2.95, 2.88),
        ("GOOGL", "Alphabet Inc", 1.85, 1.78),
        ("AMZN", "Amazon.com", 1.25, 1.15),
        ("NVDA", "NVIDIA Corp", 5.50, 5.25),
        ("META", "Meta Platforms", 5.25, 5.10),
        ("TSLA", "Tesla Inc", 0.85, 0.90),
        ("JPM", "JPMorgan Chase", 4.50, 4.35),
    ]
    
    for i, (sym, name, est, prev) in enumerate(companies):
        if symbol and sym != symbol:
            continue
            
        report_date = datetime.now() + timedelta(days=random.randint(1, 30))
        
        earnings.append({
            "symbol": sym,
            "company_name": name,
            "report_date": report_date.strftime("%Y-%m-%d"),
            "report_time": random.choice(["BMO", "AMC"]),  # Before/After market
            "eps_estimate": est,
            "eps_prior": prev,
            "revenue_estimate": round(random.uniform(10, 100), 2),
            "revenue_prior": round(random.uniform(10, 100), 2),
            "surprise_history": round(random.uniform(-5, 10), 1),
            "implied_move": round(random.uniform(3, 12), 1),
            "options_activity": random.choice(["high", "normal", "low"])
        })
    
    return {
        "earnings": sorted(earnings, key=lambda x: x["report_date"]),
        "count": len(earnings)
    }


@router.get("/economic")
async def get_economic_calendar(
    importance: Optional[str] = Query(None, description="high, medium, low"),
    country: Optional[str] = None
):
    """Get economic events calendar."""
    events = [
        ("FOMC Meeting", "US", "high", "Interest rate decision"),
        ("Non-Farm Payrolls", "US", "high", "Employment report"),
        ("CPI Release", "US", "high", "Inflation data"),
        ("GDP Growth", "US", "medium", "Economic growth"),
        ("Retail Sales", "US", "medium", "Consumer spending"),
        ("PMI Manufacturing", "US", "medium", "Manufacturing activity"),
        ("ECB Rate Decision", "EU", "high", "Interest rate decision"),
        ("UK GDP", "UK", "medium", "Economic growth"),
        ("China Trade Balance", "CN", "medium", "Trade data"),
    ]
    
    calendar_events = []
    
    for name, ctry, imp, desc in events:
        if importance and imp != importance:
            continue
        if country and ctry != country:
            continue
            
        event_date = datetime.now() + timedelta(days=random.randint(1, 14))
        
        calendar_events.append({
            "id": f"ECON-{random.randint(1000, 9999)}",
            "name": name,
            "country": ctry,
            "importance": imp,
            "description": desc,
            "date": event_date.strftime("%Y-%m-%d"),
            "time": f"{random.randint(8, 16):02d}:30",
            "forecast": str(round(random.uniform(-1, 5), 1)) + "%",
            "previous": str(round(random.uniform(-1, 5), 1)) + "%",
            "impact_estimate": round(random.uniform(0.3, 1.0), 2) if imp == "high" else round(random.uniform(0.1, 0.5), 2)
        })
    
    return {
        "events": sorted(calendar_events, key=lambda x: x["date"]),
        "count": len(calendar_events)
    }


@router.get("/signals")
async def get_event_signals(
    symbol: Optional[str] = None,
    signal_type: Optional[str] = None
):
    """Get event-driven trading signals."""
    signal_types = ["earnings_surprise", "analyst_action", "news_momentum", "event_anticipation"]
    
    signals_list = []
    
    for i in range(random.randint(3, 10)):
        sig_type = signal_type or random.choice(signal_types)
        
        signals_list.append({
            "id": f"SIG-{random.randint(10000, 99999)}",
            "symbol": symbol or random.choice(["SPY", "AAPL", "MSFT", "NVDA", "TSLA"]),
            "signal_type": sig_type,
            "direction": random.choice(["bullish", "bearish"]),
            "strength": round(random.uniform(0.5, 1.0), 2),
            "confidence": round(random.uniform(0.5, 0.9), 2),
            "trigger": random.choice(["Earnings beat", "Analyst upgrade", "News catalyst", "Economic data"]),
            "description": "Signal generated based on event analysis",
            "entry_price": round(random.uniform(100, 500), 2),
            "target_price": round(random.uniform(100, 500), 2),
            "stop_price": round(random.uniform(100, 500), 2),
            "timeframe": random.choice(["1D", "1W", "2W"]),
            "timestamp": datetime.now().isoformat()
        })
    
    return {
        "signals": signals_list,
        "count": len(signals_list)
    }


@router.post("/analyze-headline")
async def analyze_headline(body: dict = Body(...)):
    """Analyze a headline for trading signals."""
    headline = body.get("headline", "")
    
    if not headline:
        raise HTTPException(status_code=400, detail="Headline required")
    
    # Simple keyword-based analysis
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
        "trading_relevance": round(random.uniform(0.5, 1.0), 2),
        "timestamp": datetime.now().isoformat()
    }
