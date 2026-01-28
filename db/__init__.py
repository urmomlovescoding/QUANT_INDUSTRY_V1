"""
QUANT_INDUSTRY_V1 Database Access Layer (DAL)

SQLite-first storage with typed queries and proper error handling.
This is the ONLY module allowed to directly interact with SQLite.

All other code MUST access data through this DAL.
"""

from .dal import (
    DatabaseManager,
    get_db,
    init_db,
)
from .models import (
    Run,
    MarketBar,
    Signal,
    Trade,
    Order,
    Position,
    Model,
    Strategy,
    RiskLimit,
    AuditEntry,
    ErrorEntry,
    HealthMetric,
    SelfGradeScore,
)
from .repositories import (
    RunRepository,
    MarketDataRepository,
    SignalRepository,
    TradeRepository,
    PositionRepository,
    ModelRepository,
    StrategyRepository,
    RiskRepository,
    AuditRepository,
    HealthRepository,
)

__all__ = [
    # Core
    'DatabaseManager',
    'get_db',
    'init_db',
    # Models
    'Run',
    'MarketBar',
    'Signal',
    'Trade',
    'Order',
    'Position',
    'Model',
    'Strategy',
    'RiskLimit',
    'AuditEntry',
    'ErrorEntry',
    'HealthMetric',
    'SelfGradeScore',
    # Repositories
    'RunRepository',
    'MarketDataRepository',
    'SignalRepository',
    'TradeRepository',
    'PositionRepository',
    'ModelRepository',
    'StrategyRepository',
    'RiskRepository',
    'AuditRepository',
    'HealthRepository',
]
