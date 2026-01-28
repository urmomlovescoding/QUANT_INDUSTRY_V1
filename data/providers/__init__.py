"""
Data Providers - Production Market Data Feeds
QUANT_INDUSTRY_V1
"""

from .polygon import PolygonProvider, PolygonConfig, create_polygon_provider
from .alpaca import AlpacaProvider, AlpacaConfig, create_alpaca_provider

# IBKR requires ibapi package
try:
    from .ibkr import IBKRProvider, IBKRConfig, AsyncIBKRProvider
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False

__all__ = [
    'PolygonProvider',
    'PolygonConfig',
    'create_polygon_provider',
    'AlpacaProvider',
    'AlpacaConfig',
    'create_alpaca_provider',
    'IBKR_AVAILABLE',
]

if IBKR_AVAILABLE:
    __all__.extend(['IBKRProvider', 'IBKRConfig', 'AsyncIBKRProvider'])
