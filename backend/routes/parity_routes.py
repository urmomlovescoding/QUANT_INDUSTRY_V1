"""
Parity Routes
=============
Endpoints for ICT strategies, market memory, regime discovery, TPT, journal, and learning.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException

from ._shared import (
    logger, SERVICES_AVAILABLE, ICT_AVAILABLE, MARKET_MEMORY_AVAILABLE,
    REGIME_DISCOVERY_AVAILABLE, TPT_AGGRESSIVE_AVAILABLE, TRADE_JOURNAL_AVAILABLE,
    LEARNING_CENTER_AVAILABLE, get_data_service
)

router = APIRouter(prefix="/api", tags=["parity"])


# Singleton instances
_ict_analyzer = None
_market_memory = None
_regime_discovery = None
_tpt_strategy = None
_trade_journal = None


# ============== ICT STRATEGIES ==============

@router.get("/ict/status")
async def get_ict_status():
    """Get ICT module status"""
    return {
        "available": ICT_AVAILABLE,
        "module": "ICT Smart Money Strategies",
        "features": ["FVG Detection", "Order Blocks", "Breaker Blocks", "Liquidity Sweeps"]
    }


@router.post("/ict/analyze/{symbol}")
async def analyze_ict(symbol: str):
    """Analyze symbol with ICT methodology"""
    global _ict_analyzer
    if not ICT_AVAILABLE:
        raise HTTPException(status_code=503, detail="ICT module not available")

    try:
        from strategies.ict_strategies import ICTAnalyzer
        if _ict_analyzer is None:
            _ict_analyzer = ICTAnalyzer()

        ds = get_data_service()
        bars = ds.get_historical(symbol, "1D", 100)
        if not bars:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        opens = [b.open for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        timestamps = [b.timestamp for b in bars]

        result = _ict_analyzer.analyze_candles(opens, highs, lows, closes, timestamps)
        return {"symbol": symbol, "bias": result.get("htf_bias", "neutral"), **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== MARKET MEMORY ==============

@router.get("/memory/status")
async def get_memory_status():
    """Get Market Memory status"""
    return {
        "available": MARKET_MEMORY_AVAILABLE,
        "module": "Episodic Market Memory",
        "features": ["Episode Storage", "Similarity Search", "Pattern Recognition"]
    }


@router.post("/memory/store")
async def store_episode(episode_data: dict):
    """Store a market episode"""
    global _market_memory
    if not MARKET_MEMORY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Market Memory not available")

    try:
        from core.market_memory import MarketMemory, MarketEpisode
        if _market_memory is None:
            _market_memory = MarketMemory()

        episode = MarketEpisode(
            episode_id=episode_data.get("episode_id", f"ep_{datetime.now().timestamp()}"),
            symbol=episode_data.get("symbol", "SPY"),
            regime=episode_data.get("regime", "unknown"),
            features=episode_data.get("features", {}),
            outcome=episode_data.get("outcome", 0.0),
            timestamp=datetime.now()
        )
        _market_memory.store_episode(episode)
        return {"status": "stored", "episode_id": episode.episode_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== REGIME DISCOVERY ==============

@router.get("/regime/status")
async def get_regime_status():
    """Get Regime Discovery status"""
    return {
        "available": REGIME_DISCOVERY_AVAILABLE,
        "module": "Advanced Regime Discovery",
        "features": ["Multi-factor Detection", "Transition Tracking"]
    }


@router.post("/regime/detect/{symbol}")
async def detect_regime(symbol: str):
    """Detect current market regime"""
    global _regime_discovery
    if not REGIME_DISCOVERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Regime Discovery not available")

    try:
        from core.regime_discovery import RegimeDiscovery
        if _regime_discovery is None:
            _regime_discovery = RegimeDiscovery()

        ds = get_data_service()
        bars = ds.get_historical(symbol, "1D", 50)
        if not bars:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        opens = [b.open for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]
        timestamps = [b.timestamp for b in bars]

        state = _regime_discovery.detect_regime(opens, highs, lows, closes, volumes, timestamps)
        return {
            "symbol": symbol,
            "regime": state.regime.value if hasattr(state.regime, 'value') else str(state.regime),
            "confidence": state.confidence
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== TPT STRATEGY ==============

@router.get("/tpt/status")
async def get_tpt_status():
    """Get TPT Strategy status"""
    global _tpt_strategy
    if not TPT_AGGRESSIVE_AVAILABLE:
        return {"available": False}

    try:
        from strategies.tpt_aggressive import TPTAggressiveStrategy
        if _tpt_strategy is None:
            _tpt_strategy = TPTAggressiveStrategy()

        state = _tpt_strategy.state
        return {
            "available": True,
            "status": state.status.value if hasattr(state.status, 'value') else str(state.status),
            "equity": state.current_balance,
            "total_pnl": state.total_pnl
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


# ============== TRADE JOURNAL ==============

@router.get("/journal/status")
async def get_journal_status():
    """Get Trade Journal status"""
    global _trade_journal
    if not TRADE_JOURNAL_AVAILABLE:
        return {"available": False}

    try:
        from execution.trade_journal import TradeJournal
        if _trade_journal is None:
            _trade_journal = TradeJournal()
        return {
            "available": True,
            "total_entries": len(_trade_journal.entries) if hasattr(_trade_journal, 'entries') else 0
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


@router.post("/journal/record")
async def record_trade(trade_data: dict):
    """Record a trade in the journal"""
    global _trade_journal
    if not TRADE_JOURNAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Trade Journal not available")

    try:
        from execution.trade_journal import TradeJournal, JournalEntry
        if _trade_journal is None:
            _trade_journal = TradeJournal()

        entry = JournalEntry(
            entry_id=trade_data.get("entry_id", f"trade_{datetime.now().timestamp()}"),
            symbol=trade_data["symbol"],
            direction=trade_data["direction"],
            entry_price=trade_data["entry_price"],
            exit_price=trade_data.get("exit_price"),
            contracts=trade_data.get("contracts", 1),
            pnl=trade_data.get("pnl", 0),
            strategy=trade_data.get("strategy", "manual"),
            notes=trade_data.get("notes", ""),
            entry_time=datetime.now()
        )
        _trade_journal.record_entry(entry)
        return {"status": "recorded", "entry_id": entry.entry_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== LEARNING CENTER ==============

@router.get("/learning/status")
async def get_learning_status():
    """Get Learning Center status"""
    return {
        "available": LEARNING_CENTER_AVAILABLE,
        "module": "Comprehensive Learning Center",
        "features": ["Topic Categories", "Search", "Detailed Explanations"]
    }


@router.get("/learning/topics")
async def get_learning_topics(category: Optional[str] = None):
    """Get all learning topics"""
    if not LEARNING_CENTER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Learning Center not available")

    try:
        from services.learning_center import get_learning_center, TopicCategory
        center = get_learning_center()

        if category:
            try:
                cat = TopicCategory(category)
                topics = center.get_topics_by_category(cat)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        else:
            topics = center.get_all_topics()

        return {"topics": [t.to_dict() for t in topics], "count": len(topics)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/topics/{topic_id}")
async def get_learning_topic(topic_id: str):
    """Get a specific learning topic"""
    if not LEARNING_CENTER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Learning Center not available")

    try:
        from services.learning_center import get_learning_center
        center = get_learning_center()
        topic = center.get_topic(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic not found: {topic_id}")
        return topic.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/search")
async def search_learning_topics(q: str):
    """Search learning topics"""
    if not LEARNING_CENTER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Learning Center not available")

    try:
        from services.learning_center import get_learning_center
        center = get_learning_center()
        topics = center.search_topics(q)
        return {"query": q, "results": [t.to_dict() for t in topics], "count": len(topics)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
