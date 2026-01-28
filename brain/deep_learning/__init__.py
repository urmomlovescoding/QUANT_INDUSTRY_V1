"""
QUANT_INDUSTRY_V1 Deep Learning Module

State-of-the-art neural network architectures for financial time series.
"""

from brain.deep_learning.temporal_fusion import TemporalFusionTransformer, TFTConfig
from brain.deep_learning.wavenet import WaveNetModel, WaveNetConfig
from brain.deep_learning.attention_flow import AttentionFlowNetwork, AttentionFlowConfig
from brain.deep_learning.ensemble import DeepLearningEnsemble

__all__ = [
    'TemporalFusionTransformer',
    'TFTConfig',
    'WaveNetModel',
    'WaveNetConfig',
    'AttentionFlowNetwork',
    'AttentionFlowConfig',
    'DeepLearningEnsemble',
]
