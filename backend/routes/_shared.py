"""
Shared utilities and service access for all backend routes.
This module centralizes imports to prevent duplication and circular imports.
"""

import logging
import os
import random
import math
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ============== SERVICE AVAILABILITY FLAGS ==============
# These will be populated when services are imported

SERVICES_AVAILABLE = False
BEAST_AVAILABLE = False
RL_AVAILABLE = False
DL_AVAILABLE = False
EVOLUTION_AVAILABLE = False
PROPFIRM_AVAILABLE = False
PROPFIRM_BRAIN_V6_AVAILABLE = False
DATA_INTEGRITY_AVAILABLE = False
MARKET_HOURS_AVAILABLE = False
ICT_AVAILABLE = False
MARKET_MEMORY_AVAILABLE = False
REGIME_DISCOVERY_AVAILABLE = False
TPT_AGGRESSIVE_AVAILABLE = False
TRADE_JOURNAL_AVAILABLE = False
BROKER_ADAPTER_AVAILABLE = False
LEARNING_CENTER_AVAILABLE = False
FEEDBACK_LOOP_AVAILABLE = False
ERROR_UTILS_AVAILABLE = False

# Service references (lazy loaded)
_data_service = None
_trading_service = None
_risk_service = None
_options_service = None
_gex_analyzer = None
_neural_engine = None
_regime_detector = None
_trading_brain = None
_algo_bot = None
_portfolio_service = None
_research_service = None
_health_service = None


def _init_services():
    """Initialize service availability flags and imports."""
    global SERVICES_AVAILABLE, BEAST_AVAILABLE, RL_AVAILABLE, DL_AVAILABLE
    global EVOLUTION_AVAILABLE, PROPFIRM_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE
    global DATA_INTEGRITY_AVAILABLE, MARKET_HOURS_AVAILABLE
    global ICT_AVAILABLE, MARKET_MEMORY_AVAILABLE, REGIME_DISCOVERY_AVAILABLE
    global TPT_AGGRESSIVE_AVAILABLE, TRADE_JOURNAL_AVAILABLE, BROKER_ADAPTER_AVAILABLE
    global LEARNING_CENTER_AVAILABLE, FEEDBACK_LOOP_AVAILABLE, ERROR_UTILS_AVAILABLE
    
    try:
        from services.data_service import get_data_service
        from services.trading_service import get_trading_service
        from services.risk_service import get_risk_service
        from services.health_service import get_health_service
        from brain.trading_brain import get_trading_brain
        from brain.neural_engine import get_neural_engine
        from brain.regime_detector import get_regime_detector
        from brain.algo_bot import get_algo_bot
        from options.options_service import get_options_service
        from options.gex_analyzer import get_gex_analyzer
        from portfolio.portfolio_service import get_portfolio_service
        from research.research_service import get_research_service
        from brain import BEAST_AVAILABLE as _BEAST, DL_AVAILABLE as _DL
        from brain import RL_AVAILABLE as _RL, EVOLUTION_AVAILABLE as _EVOL
        
        SERVICES_AVAILABLE = True
        BEAST_AVAILABLE = _BEAST
        RL_AVAILABLE = _RL
        DL_AVAILABLE = _DL
        EVOLUTION_AVAILABLE = _EVOL
        logger.info("Core services loaded successfully")
    except ImportError as e:
        logger.warning(f"Core services not available: {e}")
        SERVICES_AVAILABLE = False

    # Data Integrity
    try:
        from core.data_integrity import DataMode, get_data_mode, set_data_mode
        DATA_INTEGRITY_AVAILABLE = True
    except ImportError:
        DATA_INTEGRITY_AVAILABLE = False

    # Market Hours
    try:
        from services.market_hours import get_market_status, is_market_open
        MARKET_HOURS_AVAILABLE = True
    except ImportError:
        MARKET_HOURS_AVAILABLE = False

    # PropFirm Brain V6
    try:
        from brain.propfirm_brain_v6 import get_propfirm_brain_v6
        PROPFIRM_BRAIN_V6_AVAILABLE = True
    except ImportError:
        PROPFIRM_BRAIN_V6_AVAILABLE = False

    # PropFirm Risk
    try:
        from brain.propfirm_risk import get_propfirm_risk_engine
        PROPFIRM_AVAILABLE = True
    except ImportError:
        PROPFIRM_AVAILABLE = False

    # ICT Strategies
    try:
        from strategies.ict_strategies import ICTAnalyzer
        ICT_AVAILABLE = True
    except ImportError:
        ICT_AVAILABLE = False

    # Market Memory
    try:
        from core.market_memory import MarketMemory
        MARKET_MEMORY_AVAILABLE = True
    except ImportError:
        MARKET_MEMORY_AVAILABLE = False

    # Regime Discovery
    try:
        from core.regime_discovery import RegimeDiscovery
        REGIME_DISCOVERY_AVAILABLE = True
    except ImportError:
        REGIME_DISCOVERY_AVAILABLE = False

    # TPT Strategy
    try:
        from strategies.tpt_aggressive import TPTAggressiveStrategy
        TPT_AGGRESSIVE_AVAILABLE = True
    except ImportError:
        TPT_AGGRESSIVE_AVAILABLE = False

    # Trade Journal
    try:
        from execution.trade_journal import TradeJournal
        TRADE_JOURNAL_AVAILABLE = True
    except ImportError:
        TRADE_JOURNAL_AVAILABLE = False

    # Broker Adapter
    try:
        from execution.broker_adapter import PaperBroker, Order, OrderType, OrderSide
        BROKER_ADAPTER_AVAILABLE = True
    except ImportError:
        BROKER_ADAPTER_AVAILABLE = False

    # Learning Center
    try:
        from services.learning_center import get_learning_center, TopicCategory
        LEARNING_CENTER_AVAILABLE = True
    except ImportError:
        LEARNING_CENTER_AVAILABLE = False

    # Feedback Loop
    try:
        from brain.feedback_loop import get_feedback_loop
        FEEDBACK_LOOP_AVAILABLE = True
    except ImportError:
        FEEDBACK_LOOP_AVAILABLE = False

    # Error Utils
    try:
        from utils.errors import APIError, error_response, success_response
        ERROR_UTILS_AVAILABLE = True
    except ImportError:
        ERROR_UTILS_AVAILABLE = False


# Initialize on module load
_init_services()


# ============== SERVICE GETTERS ==============

def get_data_service():
    """Get the data service singleton."""
    global _data_service
    if _data_service is None and SERVICES_AVAILABLE:
        from services.data_service import get_data_service as _get_ds
        _data_service = _get_ds()
    return _data_service


def get_trading_service():
    """Get the trading service singleton."""
    global _trading_service
    if _trading_service is None and SERVICES_AVAILABLE:
        from services.trading_service import get_trading_service as _get_ts
        _trading_service = _get_ts()
    return _trading_service


def get_risk_service():
    """Get the risk service singleton."""
    global _risk_service
    if _risk_service is None and SERVICES_AVAILABLE:
        from services.risk_service import get_risk_service as _get_rs
        _risk_service = _get_rs()
    return _risk_service


def get_options_service():
    """Get the options service singleton."""
    global _options_service
    if _options_service is None and SERVICES_AVAILABLE:
        from options.options_service import get_options_service as _get_os
        _options_service = _get_os()
    return _options_service


def get_gex_analyzer():
    """Get the GEX analyzer singleton."""
    global _gex_analyzer
    if _gex_analyzer is None and SERVICES_AVAILABLE:
        from options.gex_analyzer import get_gex_analyzer as _get_gex
        _gex_analyzer = _get_gex()
    return _gex_analyzer


def get_neural_engine():
    """Get the neural engine singleton."""
    global _neural_engine
    if _neural_engine is None and SERVICES_AVAILABLE:
        from brain.neural_engine import get_neural_engine as _get_ne
        _neural_engine = _get_ne()
    return _neural_engine


def get_regime_detector():
    """Get the regime detector singleton."""
    global _regime_detector
    if _regime_detector is None and SERVICES_AVAILABLE:
        from brain.regime_detector import get_regime_detector as _get_rd
        _regime_detector = _get_rd()
    return _regime_detector


def get_trading_brain():
    """Get the trading brain singleton."""
    global _trading_brain
    if _trading_brain is None and SERVICES_AVAILABLE:
        from brain.trading_brain import get_trading_brain as _get_tb
        _trading_brain = _get_tb()
    return _trading_brain


def get_algo_bot():
    """Get the algo bot singleton."""
    global _algo_bot
    if _algo_bot is None and SERVICES_AVAILABLE:
        from brain.algo_bot import get_algo_bot as _get_ab
        _algo_bot = _get_ab()
    return _algo_bot


def get_portfolio_service():
    """Get the portfolio service singleton."""
    global _portfolio_service
    if _portfolio_service is None and SERVICES_AVAILABLE:
        from portfolio.portfolio_service import get_portfolio_service as _get_ps
        _portfolio_service = _get_ps()
    return _portfolio_service


def get_research_service():
    """Get the research service singleton."""
    global _research_service
    if _research_service is None and SERVICES_AVAILABLE:
        from research.research_service import get_research_service as _get_res
        _research_service = _get_res()
    return _research_service


def get_health_service():
    """Get the health service singleton."""
    global _health_service
    if _health_service is None and SERVICES_AVAILABLE:
        from services.health_service import get_health_service as _get_hs
        _health_service = _get_hs()
    return _health_service


# ============== SHARED MODELS ==============

class TickerPrice(BaseModel):
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int


class Signal(BaseModel):
    id: str
    symbol: str
    direction: str
    confidence: float
    strategy: str
    entry_price: float
    target: float
    stop_loss: float
    timestamp: str
    status: str


class Position(BaseModel):
    id: str
    symbol: str
    side: str
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float


class ScreenerResult(BaseModel):
    symbol: str
    price: float
    change_pct: float
    volume: int
    rsi: float
    trend: str
    signal: str


class TradeConfirmation(BaseModel):
    ticker: str
    direction: str
    entry_price: float
    target: float
    stop_loss: float


class AIDecision(BaseModel):
    approved: bool
    score: int
    confidence: float
    components: Dict[str, Any]
    recommendation: str
    analysis: str


class RiskMetrics(BaseModel):
    var_95: float
    current_drawdown: float
    max_position_exposure: float
    sector_concentration: float
    daily_pnl: float
    risk_score: float


class BacktestResult(BaseModel):
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    profit_factor: float
    equity_curve: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]


# ============== SHARED DATA CACHES ==============

# Live market data cache
MARKET_DATA: Dict[str, Dict] = {}
MARKET_SYMBOLS = ["SPY", "QQQ", "DIA", "IWM", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "^VIX"]

# Active signals
ACTIVE_SIGNALS: Dict[str, Dict] = {}


def init_market_data():
    """Initialize market data from live sources."""
    global MARKET_DATA
    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            quotes = ds.get_quotes(MARKET_SYMBOLS)
            for symbol, quote in quotes.items():
                display_symbol = "VIX" if symbol == "^VIX" else symbol
                MARKET_DATA[display_symbol] = {
                    "price": quote.price,
                    "change": quote.change,
                    "change_pct": quote.change_pct,
                    "volume": quote.volume,
                    "high": quote.high,
                    "low": quote.low,
                    "open": quote.open,
                    "prev_close": quote.prev_close,
                    "bid": quote.bid if quote.bid else quote.price - 0.01,
                    "ask": quote.ask if quote.ask else quote.price + 0.01,
                    "source": quote.source
                }
            logger.info(f"Market data initialized: {len(MARKET_DATA)} symbols")
        except Exception as e:
            logger.warning(f"Failed to init market data: {e}")
            _init_fallback_data()
    else:
        _init_fallback_data()


def _init_fallback_data():
    """Initialize fallback static data."""
    global MARKET_DATA
    MARKET_DATA = {
        "SPY": {"price": 688.98, "change": 3.52, "change_pct": 0.52, "source": "fallback"},
        "QQQ": {"price": 620.76, "change": 4.51, "change_pct": 0.73, "source": "fallback"},
        "DIA": {"price": 493.69, "change": 2.91, "change_pct": 0.59, "source": "fallback"},
        "IWM": {"price": 269.79, "change": 2.02, "change_pct": 0.75, "source": "fallback"},
        "AAPL": {"price": 235.48, "change": 1.85, "change_pct": 0.79, "source": "fallback"},
        "MSFT": {"price": 442.35, "change": 3.21, "change_pct": 0.73, "source": "fallback"},
        "GOOGL": {"price": 198.72, "change": 1.45, "change_pct": 0.73, "source": "fallback"},
        "AMZN": {"price": 228.65, "change": 2.15, "change_pct": 0.95, "source": "fallback"},
        "NVDA": {"price": 142.85, "change": 2.35, "change_pct": 1.67, "source": "fallback"},
        "META": {"price": 612.45, "change": 4.85, "change_pct": 0.80, "source": "fallback"},
        "TSLA": {"price": 412.50, "change": -3.25, "change_pct": -0.78, "source": "fallback"},
        "AMD": {"price": 125.30, "change": 1.95, "change_pct": 1.58, "source": "fallback"},
        "VIX": {"price": 16.5, "change": -0.35, "change_pct": -2.08, "source": "fallback"},
    }


def refresh_market_data():
    """Refresh market data from live sources."""
    global MARKET_DATA
    if not SERVICES_AVAILABLE:
        return
    try:
        ds = get_data_service()
        quotes = ds.get_quotes(MARKET_SYMBOLS)
        for symbol, quote in quotes.items():
            display_symbol = "VIX" if symbol == "^VIX" else symbol
            MARKET_DATA[display_symbol] = {
                "price": quote.price,
                "change": quote.change,
                "change_pct": quote.change_pct,
                "volume": quote.volume,
                "high": quote.high,
                "low": quote.low,
                "open": quote.open,
                "prev_close": quote.prev_close,
                "bid": quote.bid if quote.bid else quote.price - 0.01,
                "ask": quote.ask if quote.ask else quote.price + 0.01,
                "source": quote.source
            }
    except Exception as e:
        logger.debug(f"Market data refresh failed: {e}")


# Initialize on load
init_market_data()
