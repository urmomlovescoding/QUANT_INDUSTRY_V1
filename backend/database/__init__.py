"""
QUANT INDUSTRY V1 - Database Layer
===================================
Industry-grade database architecture for quantitative trading.

Architecture:
- SQLite for local development / single-instance deployment
- PostgreSQL + TimescaleDB for production (horizontal scaling)
- Redis for caching hot data (quotes, signals)
- Async support throughout

Components:
- market_data: Time-series OHLCV data (high volume)
- trade_journal: Trade records with full audit trail
- portfolio: Positions, equity curves, performance
- signals: Trading signals and their outcomes
- features: ML feature store
- risk: Risk metrics history
- compliance: Rules and violations
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    'get_db',
    'get_async_db', 
    'init_database',
    'DatabaseSession',
    'Base',
    'Trade',
    'Position',
    'Signal',
    'RiskMetric',
    'BacktestRun',
    'PortfolioSnapshot',
    'MarketBar',
    'Feature',
    'TradeRepository',
    'PositionRepository',
    'SignalRepository',
    'MarketDataRepository',
]

def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name in ['get_db', 'get_async_db', 'init_database', 'DatabaseSession']:
        from .connection import get_db, get_async_db, init_database, DatabaseSession
        return locals()[name]
    
    if name in ['Base', 'Trade', 'Position', 'Signal', 'RiskMetric', 
                'BacktestRun', 'PortfolioSnapshot', 'MarketBar', 'Feature']:
        from . import models
        return getattr(models, name)
    
    if name in ['TradeRepository', 'PositionRepository', 'SignalRepository', 'MarketDataRepository']:
        from . import repositories
        return getattr(repositories, name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
