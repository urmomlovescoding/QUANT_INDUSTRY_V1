"""
Data Providers - Production Market Data Feeds
QUANT_INDUSTRY_V1

Providers are loaded conditionally based on available dependencies.
"""

# Alpaca - primary provider (free, good quality)
try:
    from .alpaca import AlpacaProvider, AlpacaConfig, create_alpaca_provider
    ALPACA_AVAILABLE = True
except (ImportError, Exception) as e:
    ALPACA_AVAILABLE = False
    print(f"[WARN] Alpaca provider not available: {e}")

# Polygon - premium provider
try:
    from .polygon import PolygonProvider, PolygonConfig, create_polygon_provider
    POLYGON_AVAILABLE = True
except (ImportError, Exception) as e:
    POLYGON_AVAILABLE = False
    print(f"[WARN] Polygon provider not available: {e}")

# IBKR - requires ibapi package
try:
    from .ibkr import IBKRProvider, IBKRConfig, AsyncIBKRProvider
    IBKR_AVAILABLE = True
except (ImportError, NameError, Exception) as e:
    IBKR_AVAILABLE = False
    # Only warn if not a simple import error
    if "ibapi" not in str(e).lower():
        print(f"[WARN] IBKR provider not available: {e}")

__all__ = [
    'ALPACA_AVAILABLE',
    'POLYGON_AVAILABLE',
    'IBKR_AVAILABLE',
]

if ALPACA_AVAILABLE:
    __all__.extend(['AlpacaProvider', 'AlpacaConfig', 'create_alpaca_provider'])

if POLYGON_AVAILABLE:
    __all__.extend(['PolygonProvider', 'PolygonConfig', 'create_polygon_provider'])

if IBKR_AVAILABLE:
    __all__.extend(['IBKRProvider', 'IBKRConfig', 'AsyncIBKRProvider'])
