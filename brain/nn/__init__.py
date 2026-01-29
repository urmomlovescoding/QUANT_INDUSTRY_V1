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

__all__ = [
    'BaseModel', 'ModelConfig',
    'LSTMPredictor', 'LSTMConfig',
    'TransformerPredictor', 'TransformerConfig',
    'TCNPredictor', 'TCNConfig',
    'AttentionPredictor',
]
