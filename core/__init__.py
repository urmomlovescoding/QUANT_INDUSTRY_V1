"""
QUANT_INDUSTRY_V1 Core Module

Provides base interfaces, protocols, and common types used throughout the system.
All major subsystems should depend on this module for shared abstractions.
"""

from .interfaces import (
    DataProvider,
    SignalGenerator,
    Executor,
    RiskManager,
    FeatureComputer,
    ModelTrainer,
    ModelPredictor,
)
from .types import (
    Symbol,
    Timeframe,
    Signal,
    Direction,
    Regime,
    MarketData,
    FeatureVector,
    Prediction,
    ExecutionResult,
    RiskAssessment,
)
from .exceptions import (
    QuantError,
    DataError,
    ModelError,
    ExecutionError,
    RiskError,
    ConfigError,
    ValidationError,
)
from .context import (
    RunContext,
    get_current_context,
    set_current_context,
)
from .engine import (
    EngineState,
    TradingMode,
    EngineConfig,
    TradingEngine,
)
from .signal_aggregator import (
    SignalSource,
    SignalDirection,
    TradingSignal,
    AggregatedSignal,
    SignalCombiner,
    WeightedAverageCombiner,
    VotingCombiner,
    BayesianCombiner,
    SignalAggregator,
    SignalConflictResolver,
    SignalStreamer,
    EnsembleSignalGenerator,
)

__all__ = [
    # Interfaces
    'DataProvider',
    'SignalGenerator',
    'Executor',
    'RiskManager',
    'FeatureComputer',
    'ModelTrainer',
    'ModelPredictor',
    # Types
    'Symbol',
    'Timeframe',
    'Signal',
    'Direction',
    'Regime',
    'MarketData',
    'FeatureVector',
    'Prediction',
    'ExecutionResult',
    'RiskAssessment',
    # Exceptions
    'QuantError',
    'DataError',
    'ModelError',
    'ExecutionError',
    'RiskError',
    'ConfigError',
    'ValidationError',
    # Context
    'RunContext',
    'get_current_context',
    'set_current_context',
    # Engine
    'EngineState',
    'TradingMode',
    'EngineConfig',
    'TradingEngine',
    # Signal Aggregation
    'SignalSource',
    'SignalDirection',
    'TradingSignal',
    'AggregatedSignal',
    'SignalCombiner',
    'WeightedAverageCombiner',
    'VotingCombiner',
    'BayesianCombiner',
    'SignalAggregator',
    'SignalConflictResolver',
    'SignalStreamer',
    'EnsembleSignalGenerator',
]
