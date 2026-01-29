"""
Market Microstructure & ML Order Flow Module
=============================================
Machine learning-based order flow analysis and backtesting.

Components:
- order_flow_features: Feature engineering from order book data
- flow_models: ML models for order flow prediction
- flow_backtester: Backtesting framework for order flow strategies
- imbalance_signals: Order book imbalance trading signals
- tape_reader: Time & sales analysis
"""

from .order_flow_features import (
    OrderFlowFeatureEngine,
    OrderBookSnapshot,
    TradeEvent,
    FeatureSet,
)
from .flow_models import (
    OrderFlowPredictor,
    FlowModel,
    ModelType,
)
from .flow_backtester import (
    OrderFlowBacktester,
    BacktestConfig,
    BacktestResult,
    Trade,
)
from .imbalance_signals import (
    ImbalanceDetector,
    OrderImbalance,
    ImbalanceSignal,
)
from .tape_reader import (
    TapeReader,
    TapeEvent,
    TapePattern,
)

__all__ = [
    "OrderFlowFeatureEngine",
    "OrderBookSnapshot",
    "TradeEvent",
    "FeatureSet",
    "OrderFlowPredictor",
    "FlowModel",
    "ModelType",
    "OrderFlowBacktester",
    "BacktestConfig",
    "BacktestResult",
    "Trade",
    "ImbalanceDetector",
    "OrderImbalance",
    "ImbalanceSignal",
    "TapeReader",
    "TapeEvent",
    "TapePattern",
]

__version__ = "1.0.0"
