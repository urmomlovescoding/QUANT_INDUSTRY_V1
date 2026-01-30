"""
QUANT INDUSTRY V1 - API v2 Router Assembly
==========================================
Consolidated API v2 with domain-driven organization.

This module assembles all v2 routers into a single router
that can be mounted on the main application.

Endpoint Summary:
- /health, /health/detailed
- /market/* (quotes, bars, indicators, sectors, movers)
- /trading/* (signals, orders, positions, broker)
- /portfolio/* (holdings, performance, allocation)
- /risk/* (metrics, exposure, alerts, kill-switch)
- /brain/* (status, signals, train, regime, feedback, models)
- /options/* (chain, gex, flow, dark-pool, signals)
- /backtest/* (run, strategies, monte-carlo)
- /research/* (news, 13f, earnings, ratings)
- /settings/* (config, api-keys)
- /ws/* (unified websocket stream)
"""

from fastapi import APIRouter

# Import all domain routers
from .health import router as health_router
from .market import router as market_router
from .trading import router as trading_router
from .portfolio import router as portfolio_router
from .risk import router as risk_router
from .brain import router as brain_router
from .options import router as options_router
from .backtest import router as backtest_router
from .research import router as research_router
from .settings import router as settings_router
from .websocket import router as websocket_router


# Create main v2 router
api_v2 = APIRouter()

# Include all domain routers with appropriate prefixes and tags
api_v2.include_router(
    health_router,
    tags=["Health"]
)

api_v2.include_router(
    market_router,
    prefix="/market",
    tags=["Market Data"]
)

api_v2.include_router(
    trading_router,
    prefix="/trading",
    tags=["Trading"]
)

api_v2.include_router(
    portfolio_router,
    prefix="/portfolio",
    tags=["Portfolio"]
)

api_v2.include_router(
    risk_router,
    prefix="/risk",
    tags=["Risk Management"]
)

api_v2.include_router(
    brain_router,
    prefix="/brain",
    tags=["ML Brain"]
)

api_v2.include_router(
    options_router,
    prefix="/options",
    tags=["Options"]
)

api_v2.include_router(
    backtest_router,
    prefix="/backtest",
    tags=["Backtesting"]
)

api_v2.include_router(
    research_router,
    prefix="/research",
    tags=["Research"]
)

api_v2.include_router(
    settings_router,
    prefix="/settings",
    tags=["Settings"]
)

api_v2.include_router(
    websocket_router,
    prefix="/ws",
    tags=["WebSocket"]
)


# Export the assembled router
__all__ = ["api_v2"]
