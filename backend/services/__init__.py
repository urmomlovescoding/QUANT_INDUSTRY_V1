# QUANT INDUSTRY Services Package
#
# v10.1: Added alternative data and walk-forward validation

from .data_service import DataService, get_data_service
from .health_service import HealthService, get_health_service
from .risk_service import RiskService, get_risk_service
from .trading_service import TradingService, get_trading_service

# NEW: Alternative data for alpha generation
from .alternative_data import (
    AlternativeDataService,
    get_alternative_data_service,
    get_sentiment,
    get_alternative_features,
    get_insider_signal,
    SentimentData,
    SentimentScore,
)

# NEW: Walk-forward validation
from .walk_forward import (
    WalkForwardValidator,
    ValidationMethod,
    WalkForwardSplit,
    WalkForwardResult,
    WalkForwardReport,
    walk_forward_validate,
    generate_walk_forward_splits,
)

__all__ = [
    # Core services
    "DataService",
    "HealthService",
    "RiskService",
    "TradingService",
    "get_data_service",
    "get_health_service",
    "get_risk_service",
    "get_trading_service",
    # Alternative data
    "AlternativeDataService",
    "get_alternative_data_service",
    "get_sentiment",
    "get_alternative_features",
    "get_insider_signal",
    "SentimentData",
    "SentimentScore",
    # Walk-forward validation
    "WalkForwardValidator",
    "ValidationMethod",
    "WalkForwardSplit",
    "WalkForwardResult",
    "WalkForwardReport",
    "walk_forward_validate",
    "generate_walk_forward_splits",
]
