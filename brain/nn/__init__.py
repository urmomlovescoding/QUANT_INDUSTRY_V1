"""
Neural Network Module
=====================
Industry-grade PyTorch implementations for quantitative trading.
"""

from .base import BaseModel, ModelConfig
from .lstm import LSTMPredictor, LSTMConfig
from .transformer import TransformerPredictor, TransformerConfig
from .tcn import TCNPredictor, TCNConfig
from .attention import AttentionPredictor
from .trading_brain import TradingBrain, TradingBrainConfig, create_trading_brain
from .multi_timeframe import (
    MultiTimeframeBrain, 
    MultiTimeframeConfig,
    TradingHorizon,
    TimeframeConfig,
    create_multi_timeframe_brain
)

__all__ = [
    # Base
    'BaseModel', 'ModelConfig',
    # Architecture components
    'LSTMPredictor', 'LSTMConfig',
    'TransformerPredictor', 'TransformerConfig',
    'TCNPredictor', 'TCNConfig',
    'AttentionPredictor',
    # Single timeframe unified model
    'TradingBrain', 'TradingBrainConfig', 'create_trading_brain',
    # Multi-timeframe model
    'MultiTimeframeBrain', 'MultiTimeframeConfig', 'TradingHorizon',
    'TimeframeConfig', 'create_multi_timeframe_brain',
]
