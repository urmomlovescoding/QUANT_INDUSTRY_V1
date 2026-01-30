"""
Backend Routes Package
======================
Extracted from the monolithic backend/main.py for better organization.
"""

from .market_routes import router as market_router
from .trading_routes import router as trading_router
from .brain_routes import router as brain_router
from .risk_routes import router as risk_router
from .options_routes import router as options_router
from .system_routes import router as system_router
from .websocket_routes import router as websocket_router, ws_manager, data_engine
from .research_routes import router as research_router
from .quant_routes import router as quant_router
from .portfolio_routes import router as portfolio_router
from .broker_routes import router as broker_router
from .parity_routes import router as parity_router
from .algobot_routes import router as algobot_router

__all__ = [
    'market_router',
    'trading_router', 
    'brain_router',
    'risk_router',
    'options_router',
    'system_router',
    'websocket_router',
    'research_router',
    'quant_router',
    'portfolio_router',
    'broker_router',
    'parity_router',
    'algobot_routes',
    'ws_manager',
    'data_engine',
]
