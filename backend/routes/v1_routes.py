"""
V1 API Routes
=============
Endpoints for frontend V2 API client with /api/v1/ prefix.

WARNING: These endpoints return SIMULATED data for UI development.
Data provenance fields indicate the source and quality of data.

Data Source Types:
- LIVE: Real-time data from production sources
- DELAYED: Real data with time delay
- SIMULATED: Random/mock data for testing
- CACHED: Previously fetched data
"""

import random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter
from enum import Enum


class DataSource(Enum):
    """Data provenance source types."""
    LIVE = "live"
    DELAYED = "delayed"
    SIMULATED = "simulated"
    CACHED = "cached"


class DataQuality(Enum):
    """Data quality indicators."""
    FRESH = "fresh"          # < 1 second old
    RECENT = "recent"        # < 60 seconds old
    STALE = "stale"          # > 60 seconds old
    MOCK = "mock"            # Generated/fake data


def add_provenance(data: dict, source: DataSource = DataSource.SIMULATED) -> dict:
    """
    Add data provenance metadata to response.

    This is CRITICAL for preventing simulated data from being treated as real.
    """
    data["_provenance"] = {
        "source": source.value,
        "quality": DataQuality.MOCK.value if source == DataSource.SIMULATED else DataQuality.FRESH.value,
        "as_of": datetime.now().isoformat(),
        "is_simulated": source == DataSource.SIMULATED,
        "warning": "SIMULATED DATA - NOT FOR TRADING" if source == DataSource.SIMULATED else None
    }
    return data


router = APIRouter(prefix="/api/v1", tags=["v1"])


# ============== MICROSTRUCTURE ==============

@router.get("/microstructure/orderbook/{symbol}")
async def get_orderbook(symbol: str):
    """
    Get order book for a symbol.

    WARNING: Returns SIMULATED data. Check _provenance.is_simulated field.
    """
    symbol = symbol.upper()
    mid = random.uniform(150, 500)

    bids = [{"price": round(mid - i * 0.05, 2), "size": random.randint(100, 5000)} for i in range(1, 11)]
    asks = [{"price": round(mid + i * 0.05, 2), "size": random.randint(100, 5000)} for i in range(1, 11)]

    return add_provenance({
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "bids": bids,
        "asks": asks,
        "midPrice": round(mid, 2),
        "spread": round(asks[0]["price"] - bids[0]["price"], 4),
        "imbalance": round(random.uniform(-0.3, 0.3), 4)
    })


@router.get("/microstructure/imbalance/{symbol}")
async def get_imbalance(symbol: str):
    """Get order book imbalance metrics"""
    return {
        "symbol": symbol.upper(),
        "timestamp": datetime.now().isoformat(),
        "bid_volume": random.randint(500000, 2000000),
        "ask_volume": random.randint(500000, 2000000),
        "imbalance_ratio": round(random.uniform(-0.4, 0.4), 4),
        "cumulative_delta": random.randint(-100000, 100000),
        "vwap": round(random.uniform(150, 500), 2),
        "intensity": round(random.uniform(0.3, 0.9), 4)
    }


@router.get("/microstructure/tape/{symbol}")
async def get_tape(symbol: str, limit: int = 100):
    """Get time & sales data"""
    entries = []
    base_price = random.uniform(150, 500)

    for i in range(min(limit, 100)):
        entries.append({
            "timestamp": (datetime.now() - timedelta(seconds=i * 2)).isoformat(),
            "price": round(base_price + random.uniform(-0.5, 0.5), 2),
            "size": random.randint(100, 5000),
            "side": random.choice(["BUY", "SELL"]),
            "exchange": random.choice(["NYSE", "NASDAQ", "ARCA", "BATS"])
        })

    return entries


@router.get("/microstructure/tape/{symbol}/analysis")
async def get_tape_analysis(symbol: str):
    """Get tape analysis"""
    return {
        "symbol": symbol.upper(),
        "timestamp": datetime.now().isoformat(),
        "buy_volume": random.randint(500000, 1500000),
        "sell_volume": random.randint(500000, 1500000),
        "large_trades": random.randint(10, 50),
        "avg_trade_size": random.randint(200, 800),
        "block_trades": random.randint(5, 20),
        "sweep_count": random.randint(0, 10),
        "aggression_ratio": round(random.uniform(0.4, 0.6), 4)
    }


@router.get("/microstructure/models/metrics")
async def get_model_metrics():
    """Get flow model metrics"""
    return [
        {"model": "order_flow", "accuracy": round(random.uniform(0.6, 0.8), 3), "signals_today": random.randint(10, 50)},
        {"model": "imbalance", "accuracy": round(random.uniform(0.55, 0.75), 3), "signals_today": random.randint(5, 30)},
        {"model": "tape_reader", "accuracy": round(random.uniform(0.5, 0.7), 3), "signals_today": random.randint(8, 40)},
    ]


@router.get("/microstructure/backtest/results")
async def get_backtest_results():
    """Get backtest results"""
    return []


@router.post("/microstructure/backtest/run")
async def run_backtest(config: dict = {}):
    """Run a microstructure backtest"""
    return {"status": "completed", "pnl": round(random.uniform(-1000, 5000), 2)}


# ============== ARBITRAGE ==============

@router.get("/arbitrage/prices")
async def get_arb_prices(symbol: Optional[str] = None):
    """Get price matrix across exchanges"""
    symbols = [symbol.upper()] if symbol else ["BTC", "ETH", "SOL"]
    exchanges = ["Binance", "Coinbase", "Kraken", "FTX"]

    result = []
    for sym in symbols:
        base = random.uniform(100, 50000)
        for ex in exchanges:
            result.append({
                "symbol": sym,
                "exchange": ex,
                "bid": round(base * (1 - random.uniform(0.001, 0.003)), 2),
                "ask": round(base * (1 + random.uniform(0.001, 0.003)), 2),
                "volume_24h": random.randint(1000000, 50000000),
                "timestamp": datetime.now().isoformat()
            })

    return result


@router.get("/arbitrage/opportunities")
async def get_opportunities():
    """
    Get arbitrage opportunities.

    WARNING: Returns SIMULATED data. DO NOT TRADE on this data.
    """
    opps = []
    if random.random() > 0.3:
        opps.append({
            "id": "arb_001",
            "symbol": "BTC",
            "buy_exchange": "Kraken",
            "sell_exchange": "Binance",
            "spread_bps": round(random.uniform(5, 25), 2),
            "estimated_profit": round(random.uniform(50, 500), 2),
            "expires_at": (datetime.now() + timedelta(seconds=30)).isoformat()
        })
    return add_provenance({"opportunities": opps, "count": len(opps)})


@router.post("/arbitrage/opportunities/{opp_id}/execute")
async def execute_opportunity(opp_id: str):
    """
    Execute an arbitrage opportunity.

    WARNING: SIMULATED endpoint. No actual trades are executed.
    """
    return add_provenance({
        "status": "SIMULATED_EXECUTION",
        "warning": "This is a SIMULATED execution - no real trades occurred",
        "opp_id": opp_id,
        "pnl": round(random.uniform(20, 200), 2)
    })


@router.get("/arbitrage/triangular")
async def get_triangular_paths():
    """Get triangular arbitrage paths"""
    return [
        {"path": ["BTC", "ETH", "USDT", "BTC"], "profit_pct": round(random.uniform(0.1, 0.5), 3), "valid": True},
        {"path": ["ETH", "SOL", "USDT", "ETH"], "profit_pct": round(random.uniform(-0.1, 0.3), 3), "valid": False},
    ]


@router.get("/arbitrage/cex-dex/{symbol}")
async def get_cex_dex_spread(symbol: str):
    """Get CEX-DEX spread"""
    return {
        "symbol": symbol.upper(),
        "cex_price": round(random.uniform(100, 5000), 2),
        "dex_price": round(random.uniform(100, 5000), 2),
        "spread_bps": round(random.uniform(-20, 50), 2),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/arbitrage/cex-dex/{symbol}/history")
async def get_cex_dex_history(symbol: str):
    """Get CEX-DEX spread history"""
    history = []
    for i in range(24):
        history.append({
            "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
            "spread_bps": round(random.uniform(-20, 50), 2)
        })
    return {"symbol": symbol.upper(), "history": history}


@router.get("/arbitrage/latency")
async def get_latency():
    """Get exchange latency metrics"""
    return [
        {"exchange": "Binance", "latency_ms": random.randint(10, 50), "status": "healthy"},
        {"exchange": "Coinbase", "latency_ms": random.randint(20, 80), "status": "healthy"},
        {"exchange": "Kraken", "latency_ms": random.randint(30, 100), "status": "healthy"},
    ]


@router.get("/arbitrage/executions")
async def get_executions():
    """Get execution history"""
    return []


# ============== NEWS & EVENTS ==============

@router.get("/news-events/news")
async def get_news(symbol: Optional[str] = None):
    """Get news feed"""
    articles = []
    headlines = [
        "Fed signals continued rate path amid inflation concerns",
        "Tech earnings beat expectations, stocks rally",
        "Oil prices surge on supply concerns",
        "Crypto markets stabilize after weekend volatility",
        "Jobs report shows resilient labor market"
    ]

    for i, headline in enumerate(headlines):
        articles.append({
            "id": f"news_{i}",
            "headline": headline,
            "source": random.choice(["Reuters", "Bloomberg", "CNBC", "WSJ"]),
            "timestamp": (datetime.now() - timedelta(hours=i * 2)).isoformat(),
            "sentiment": round(random.uniform(-1, 1), 3),
            "relevance": round(random.uniform(0.5, 1), 3)
        })

    return {"articles": articles, "count": len(articles)}


@router.get("/news-events/sentiment/market")
async def get_market_sentiment():
    """Get overall market sentiment"""
    return {
        "overall": round(random.uniform(-0.3, 0.5), 3),
        "bullish_pct": round(random.uniform(40, 65), 1),
        "bearish_pct": round(random.uniform(25, 45), 1),
        "neutral_pct": round(random.uniform(10, 25), 1),
        "fear_greed_index": random.randint(30, 70),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/news-events/sentiment/{symbol}")
async def get_symbol_sentiment(symbol: str):
    """Get symbol sentiment"""
    return {
        "symbol": symbol.upper(),
        "sentiment": round(random.uniform(-0.5, 0.7), 3),
        "mentions_24h": random.randint(100, 5000),
        "social_volume": random.randint(1000, 50000),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/news-events/earnings")
async def get_earnings(symbol: Optional[str] = None):
    """Get earnings calendar"""
    earnings = [
        {"symbol": "AAPL", "date": "2026-02-05", "time": "after_close", "est_eps": 2.15, "est_revenue": "124B"},
        {"symbol": "MSFT", "date": "2026-02-06", "time": "after_close", "est_eps": 3.02, "est_revenue": "65B"},
        {"symbol": "GOOGL", "date": "2026-02-07", "time": "after_close", "est_eps": 1.85, "est_revenue": "85B"},
    ]
    if symbol:
        earnings = [e for e in earnings if e["symbol"] == symbol.upper()]
    return earnings


@router.get("/news-events/economic")
async def get_economic_calendar(start: Optional[str] = None, end: Optional[str] = None):
    """Get economic calendar"""
    return {
        "events": [
            {"event": "CPI Release", "date": "2026-02-10", "impact": "high", "previous": "3.1%", "forecast": "2.9%"},
            {"event": "FOMC Minutes", "date": "2026-02-12", "impact": "high", "previous": None, "forecast": None},
            {"event": "Retail Sales", "date": "2026-02-14", "impact": "medium", "previous": "0.4%", "forecast": "0.3%"},
        ]
    }


@router.get("/news-events/signals")
async def get_event_signals(symbol: Optional[str] = None):
    """Get event-based signals"""
    return [
        {"symbol": "SPY", "event": "CPI Release", "signal": "BULLISH", "confidence": 0.72},
        {"symbol": "QQQ", "event": "Fed Speech", "signal": "NEUTRAL", "confidence": 0.55},
    ]


@router.post("/news-events/analyze-headline")
async def analyze_headline(body: dict):
    """Analyze a headline for sentiment"""
    headline = body.get("headline", "")
    return {
        "headline": headline,
        "sentiment": round(random.uniform(-0.5, 0.5), 3),
        "entities": ["Fed", "inflation"] if "Fed" in headline else [],
        "keywords": headline.split()[:5]
    }


# ============== OPTIONS FLOW ==============

@router.get("/options-flow/unusual")
async def get_unusual_activity(symbol: Optional[str] = None):
    """Get unusual options activity"""
    symbols = [symbol.upper()] if symbol else ["AAPL", "TSLA", "NVDA", "AMD", "META"]
    activities = []

    for sym in symbols:
        for _ in range(random.randint(1, 3)):
            is_call = random.random() > 0.45
            activities.append({
                "symbol": sym,
                "type": "CALL" if is_call else "PUT",
                "strike": round(random.uniform(100, 500), 0),
                "expiry": (datetime.now() + timedelta(days=random.randint(7, 60))).strftime("%Y-%m-%d"),
                "premium": round(random.uniform(50000, 2000000), 0),
                "volume": random.randint(500, 10000),
                "open_interest": random.randint(1000, 50000),
                "sentiment": "BULLISH" if is_call else "BEARISH",
                "unusual_score": round(random.uniform(60, 99), 1),
                "timestamp": datetime.now().isoformat()
            })

    return sorted(activities, key=lambda x: x["unusual_score"], reverse=True)


@router.get("/options-flow/gamma-exposure/{symbol}")
async def get_gamma_exposure(symbol: str):
    """Get gamma exposure profile"""
    current_price = random.uniform(150, 300)
    strikes = []

    for i in range(-10, 11):
        strike = round(current_price + i * 5, 0)
        strikes.append({
            "strike": strike,
            "call_gex": round(random.uniform(-50, 150) * 1000000, 0),
            "put_gex": round(random.uniform(-100, 50) * 1000000, 0),
            "net_gex": round(random.uniform(-80, 120) * 1000000, 0)
        })

    return {
        "symbol": symbol.upper(),
        "current_price": round(current_price, 2),
        "strikes": strikes,
        "total_gex": sum(s["net_gex"] for s in strikes),
        "gex_flip": round(current_price * random.uniform(0.95, 1.05), 2),
        "max_pain": round(current_price * random.uniform(0.98, 1.02), 2),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/options-flow/dark-pool/prints")
async def get_dark_pool_prints(symbol: Optional[str] = None):
    """Get dark pool prints"""
    prints = []
    symbols = [symbol.upper()] if symbol else ["AAPL", "MSFT", "NVDA"]

    for sym in symbols:
        for i in range(5):
            prints.append({
                "symbol": sym,
                "price": round(random.uniform(150, 300), 2),
                "size": random.randint(10000, 500000),
                "timestamp": (datetime.now() - timedelta(minutes=i * 10)).isoformat(),
                "venue": random.choice(["SIGMA", "UBS", "CITI", "MS"])
            })

    return prints


@router.get("/options-flow/dark-pool/accumulation")
async def get_dark_pool_accumulation(symbol: Optional[str] = None):
    """Get dark pool accumulation data"""
    symbols = [symbol.upper()] if symbol else ["AAPL", "MSFT", "NVDA"]

    return [
        {
            "symbol": sym,
            "net_dark_volume": random.randint(-5000000, 10000000),
            "dark_pct_of_volume": round(random.uniform(30, 50), 1),
            "signal": "ACCUMULATION" if random.random() > 0.4 else "DISTRIBUTION"
        }
        for sym in symbols
    ]


@router.get("/options-flow/smart-money/flow")
async def get_smart_money_flow(symbol: Optional[str] = None):
    """Get smart money flow"""
    return [
        {"symbol": "AAPL", "flow": "BUYING", "confidence": 0.78, "volume": 5000000},
        {"symbol": "TSLA", "flow": "SELLING", "confidence": 0.65, "volume": 3000000},
    ]


@router.get("/options-flow/smart-money/metrics")
async def get_smart_money_metrics(symbol: Optional[str] = None):
    """Get smart money metrics"""
    return [
        {"metric": "institutional_ownership", "value": round(random.uniform(60, 85), 1)},
        {"metric": "smart_money_ratio", "value": round(random.uniform(0.8, 1.5), 2)},
        {"metric": "block_trade_pct", "value": round(random.uniform(15, 35), 1)},
    ]


@router.get("/options-flow/signals")
async def get_flow_signals(symbol: Optional[str] = None):
    """
    Get flow-based signals.

    WARNING: Returns SIMULATED signals. DO NOT USE for actual trading decisions.
    """
    signals = []
    symbols = [symbol.upper()] if symbol else ["AAPL", "NVDA", "TSLA"]

    for sym in symbols:
        if random.random() > 0.4:
            signals.append({
                "symbol": sym,
                "signal": random.choice(["STRONG_BUY", "BUY", "SELL", "STRONG_SELL"]),
                "confidence": round(random.uniform(0.6, 0.95), 2),
                "source": random.choice(["unusual_activity", "dark_pool", "smart_money"]),
                "timestamp": datetime.now().isoformat()
            })

    return add_provenance({
        "signals": signals,
        "warning": "SIMULATED SIGNALS - NOT FOR TRADING",
        "count": len(signals)
    })
