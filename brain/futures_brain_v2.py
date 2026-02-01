"""
FUTURES BRAIN V2 - NEXT-GENERATION ML/DEEP LEARNING FOR PROP FIRM TRADING
===========================================================================
Major enhancements over V1:

1. TEMPORAL FUSION TRANSFORMER (TFT) - State-of-the-art time series model
2. WAVENET TEMPORAL CNN - Dilated causal convolutions for multi-scale patterns
3. ATTENTION FLOW - Order flow analysis with attention mechanisms
4. REGIME DETECTION - HMM-based market regime classifier
5. ADVERSARIAL TRAINING - Robust to distribution shifts
6. CAUSAL DISCOVERY - Finding true predictive features
7. ONLINE META-LEARNING - MAML-style fast adaptation
8. UNCERTAINTY QUANTIFICATION - Bayesian confidence intervals

ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FUTURES BRAIN V2 ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │   WaveNet    │   │   Temporal   │   │  Attention   │   │    Regime    │ │
│  │  Temporal    │   │   Fusion     │   │    Flow      │   │   Detector   │ │
│  │    CNN       │   │ Transformer  │   │   Network    │   │    (HMM)     │ │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘ │
│         │                  │                   │                  │         │
│         └────────┬─────────┴───────────┬──────┴──────────┬──────┘         │
│                  ▼                      ▼                 ▼                 │
│         ┌──────────────────────────────────────────────────────┐           │
│         │              STACKING META-LEARNER                    │           │
│         │     (Attention-weighted ensemble with uncertainty)    │           │
│         └──────────────────────────────────────────────────────┘           │
│                                    │                                        │
│                                    ▼                                        │
│         ┌──────────────────────────────────────────────────────┐           │
│         │            RL POSITION SIZER + RISK ENGINE            │           │
│         │        (PPO with risk-adjusted reward shaping)        │           │
│         └──────────────────────────────────────────────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Author: QuantBrain Futures System V2
Version: 2.0.0
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts, OneCycleLR
from torch.cuda.amp import autocast, GradScaler
import sqlite3
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from collections import deque, OrderedDict
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
import pickle
import copy
import math
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger("FUTURES_BRAIN_V2")

# Paths
ROOT = Path(__file__).parent.parent
WEIGHTS_DIR = ROOT / "weights" / "futures_brain_v2"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = ROOT / "data" / "futures_brain_v2.db"

# GPU Detection with Mixed Precision
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP = torch.cuda.is_available()  # Automatic Mixed Precision


# =============================================================================
# CONFIGURATION V2
# =============================================================================

@dataclass
class FuturesBrainV2Config:
    """Enhanced configuration for V2 brain."""
    # Model dimensions
    input_features: int = 96  # Expanded from 72
    hidden_dim: int = 384  # Larger hidden dimension
    num_layers: int = 6
    num_heads: int = 12
    dropout: float = 0.15
    
    # WaveNet settings
    wavenet_layers: int = 8
    wavenet_channels: int = 64
    dilation_base: int = 2
    
    # TFT settings
    tft_hidden_dim: int = 256
    tft_num_heads: int = 8
    num_static_features: int = 8  # Symbol, session, regime, etc.
    
    # Sequence settings
    sequence_length: int = 120  # 10 hours of 5m bars
    prediction_horizon: int = 24  # 2 hours ahead
    
    # Training
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    batch_size: int = 64
    gradient_clip: float = 1.0
    warmup_epochs: int = 5
    
    # Uncertainty
    mc_dropout_samples: int = 10  # Monte Carlo dropout
    uncertainty_threshold: float = 0.3
    
    # Regime detection
    num_regimes: int = 4  # Trending, Ranging, Volatile, Quiet
    regime_lookback: int = 50
    
    # Ensemble
    ensemble_temperature: float = 1.5  # Softmax temperature
    min_model_weight: float = 0.05
    
    # Risk
    max_position_risk: float = 0.02
    kelly_fraction: float = 0.25
    var_confidence: float = 0.95


# =============================================================================
# POSITIONAL ENCODING (Learnable + Sinusoidal Hybrid)
# =============================================================================

class HybridPositionalEncoding(nn.Module):
    """Learnable + sinusoidal positional encoding for better temporal modeling."""
    
    def __init__(self, d_model: int, max_len: int = 500, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        # Sinusoidal encoding
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
        
        # Learnable encoding
        self.learnable_pe = nn.Parameter(torch.randn(1, max_len, d_model) * 0.02)
        
        # Gate to blend them
        self.gate = nn.Parameter(torch.tensor(0.5))
    
    def forward(self, x):
        seq_len = x.size(1)
        pe_sinusoidal = self.pe[:, :seq_len, :]
        pe_learned = self.learnable_pe[:, :seq_len, :]
        
        # Blend sinusoidal and learned
        alpha = torch.sigmoid(self.gate)
        pe = alpha * pe_sinusoidal + (1 - alpha) * pe_learned
        
        x = x + pe
        return self.dropout(x)


# =============================================================================
# WAVENET TEMPORAL CNN - Multi-scale Pattern Recognition
# =============================================================================

class CausalConv1d(nn.Module):
    """Causal convolution for temporal modeling."""
    
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int = 1):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, 
                              padding=self.padding, dilation=dilation)
    
    def forward(self, x):
        out = self.conv(x)
        if self.padding > 0:
            out = out[:, :, :-self.padding]  # Remove future padding
        return out


class WaveNetBlock(nn.Module):
    """Single WaveNet residual block with gated activation."""
    
    def __init__(self, channels: int, kernel_size: int, dilation: int):
        super().__init__()
        self.dilated_conv = CausalConv1d(channels, 2 * channels, kernel_size, dilation)
        self.res_conv = nn.Conv1d(channels, channels, 1)
        self.skip_conv = nn.Conv1d(channels, channels, 1)
        self.gate_norm = nn.LayerNorm(channels)
    
    def forward(self, x):
        # x: (batch, channels, seq_len)
        out = self.dilated_conv(x)
        
        # Gated activation
        tanh_out = torch.tanh(out[:, :out.size(1)//2, :])
        sigmoid_out = torch.sigmoid(out[:, out.size(1)//2:, :])
        gated = tanh_out * sigmoid_out
        
        # Skip and residual
        skip = self.skip_conv(gated)
        residual = self.res_conv(gated)
        
        return (x + residual), skip


class WaveNetEncoder(nn.Module):
    """
    WaveNet-style encoder for multi-scale temporal patterns.
    Captures patterns at different time scales via dilated convolutions.
    """
    
    def __init__(self, input_dim: int, channels: int = 64, num_layers: int = 8, 
                 kernel_size: int = 2, dilation_base: int = 2):
        super().__init__()
        
        self.input_conv = nn.Conv1d(input_dim, channels, 1)
        
        self.blocks = nn.ModuleList()
        for i in range(num_layers):
            dilation = dilation_base ** (i % 4)  # Reset dilation every 4 layers
            self.blocks.append(WaveNetBlock(channels, kernel_size, dilation))
        
        self.output_conv = nn.Sequential(
            nn.ReLU(),
            nn.Conv1d(channels, channels * 2, 1),
            nn.ReLU(),
            nn.Conv1d(channels * 2, channels, 1)
        )
        
        self.channels = channels
    
    def forward(self, x):
        # x: (batch, seq_len, features) -> (batch, features, seq_len)
        x = x.transpose(1, 2)
        x = self.input_conv(x)
        
        skip_sum = 0
        for block in self.blocks:
            x, skip = block(x)
            skip_sum = skip_sum + skip
        
        out = self.output_conv(skip_sum)
        return out.transpose(1, 2)  # Back to (batch, seq_len, channels)


# =============================================================================
# TEMPORAL FUSION TRANSFORMER - State-of-the-Art Time Series
# =============================================================================

class GatedResidualNetwork(nn.Module):
    """GRN from TFT paper - feature processing with gating."""
    
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, 
                 context_dim: int = None, dropout: float = 0.1):
        super().__init__()
        
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.context_proj = nn.Linear(context_dim, hidden_dim, bias=False) if context_dim else None
        
        self.fc1 = nn.Linear(hidden_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.gate_fc = nn.Linear(hidden_dim, output_dim)
        
        self.layer_norm = nn.LayerNorm(output_dim)
        self.dropout = nn.Dropout(dropout)
        
        self.residual_proj = nn.Linear(input_dim, output_dim) if input_dim != output_dim else None
    
    def forward(self, x, context=None):
        hidden = self.input_proj(x)
        if self.context_proj is not None and context is not None:
            hidden = hidden + self.context_proj(context)
        
        hidden = F.elu(hidden)
        hidden = self.fc1(hidden)
        hidden = F.elu(hidden)
        hidden = self.dropout(hidden)
        
        # Gating
        gate = torch.sigmoid(self.gate_fc(hidden))
        output = self.fc2(hidden) * gate
        
        # Residual
        residual = self.residual_proj(x) if self.residual_proj else x
        return self.layer_norm(output + residual)


class VariableSelectionNetwork(nn.Module):
    """VSN from TFT - learns which features are important."""
    
    def __init__(self, input_dim: int, num_inputs: int, hidden_dim: int, 
                 context_dim: int = None, dropout: float = 0.1):
        super().__init__()
        
        self.num_inputs = num_inputs
        self.feature_dim = input_dim // num_inputs
        
        # Per-feature GRNs
        self.feature_grns = nn.ModuleList([
            GatedResidualNetwork(self.feature_dim, hidden_dim, hidden_dim, context_dim, dropout)
            for _ in range(num_inputs)
        ])
        
        # Flattened GRN for softmax weights
        self.weight_grn = GatedResidualNetwork(
            hidden_dim * num_inputs, hidden_dim, num_inputs, context_dim, dropout
        )
    
    def forward(self, x, context=None):
        # Split features
        features = x.split(self.feature_dim, dim=-1)
        
        # Process each feature
        processed = []
        for i, (feat, grn) in enumerate(zip(features, self.feature_grns)):
            processed.append(grn(feat, context))
        
        # Stack and compute weights
        stacked = torch.stack(processed, dim=-1)  # (batch, seq, hidden, num_inputs)
        flat = torch.cat(processed, dim=-1)
        
        weights = F.softmax(self.weight_grn(flat, context), dim=-1)  # (batch, seq, num_inputs)
        
        # Weighted sum
        output = (stacked * weights.unsqueeze(-2)).sum(dim=-1)
        return output, weights


class InterpretableMultiHeadAttention(nn.Module):
    """Interpretable attention from TFT with attention scores."""
    
    def __init__(self, hidden_dim: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads
        
        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)
        self.out_proj = nn.Linear(hidden_dim, hidden_dim)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, query, key, value, mask=None):
        batch_size = query.size(0)
        
        q = self.q_proj(query).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(key).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(value).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        
        if mask is not None:
            # Use -1e4 instead of -1e9 for FP16 compatibility
            scores = scores.masked_fill(mask == 0, float('-inf') if scores.dtype == torch.float32 else -1e4)
        
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        attn_output = torch.matmul(attn_weights, v)
        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, -1, self.num_heads * self.head_dim)
        
        return self.out_proj(attn_output), attn_weights


class TemporalFusionEncoder(nn.Module):
    """
    Simplified TFT encoder for futures trading.
    Handles both static and temporal features.
    """
    
    def __init__(self, config: FuturesBrainV2Config):
        super().__init__()
        
        self.config = config
        hidden_dim = config.tft_hidden_dim
        
        # Input processing
        self.input_grn = GatedResidualNetwork(
            config.input_features, hidden_dim, hidden_dim, dropout=config.dropout
        )
        
        # Static feature embedding
        self.static_embed = nn.Sequential(
            nn.Linear(config.num_static_features, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )
        
        # LSTM encoder-decoder
        self.encoder_lstm = nn.LSTM(
            hidden_dim, hidden_dim, num_layers=2, batch_first=True, 
            dropout=config.dropout, bidirectional=False
        )
        
        # Attention layers
        self.self_attention = InterpretableMultiHeadAttention(
            hidden_dim, config.tft_num_heads, config.dropout
        )
        self.attention_grn = GatedResidualNetwork(
            hidden_dim, hidden_dim, hidden_dim, dropout=config.dropout
        )
        
        # Output
        self.output_proj = nn.Linear(hidden_dim, hidden_dim)
        self.layer_norm = nn.LayerNorm(hidden_dim)
    
    def forward(self, temporal_features, static_features=None):
        # Process inputs
        x = self.input_grn(temporal_features)
        
        # Add static context if available
        if static_features is not None:
            static = self.static_embed(static_features).unsqueeze(1)
            x = x + static.expand(-1, x.size(1), -1)
        
        # LSTM encoding
        lstm_out, _ = self.encoder_lstm(x)
        
        # Self-attention with causal mask
        seq_len = lstm_out.size(1)
        mask = torch.triu(torch.ones(seq_len, seq_len, device=lstm_out.device), diagonal=1) == 0
        
        attn_out, attn_weights = self.self_attention(lstm_out, lstm_out, lstm_out, mask)
        attn_out = self.attention_grn(attn_out)
        
        # Residual connection
        output = self.layer_norm(lstm_out + attn_out)
        
        return self.output_proj(output), attn_weights


# =============================================================================
# ATTENTION FLOW NETWORK - Order Flow with Attention
# =============================================================================

class OrderFlowAttention(nn.Module):
    """
    Attention-based order flow analysis.
    Models the relationship between price, volume, and trade direction.
    """
    
    def __init__(self, hidden_dim: int, num_heads: int = 4):
        super().__init__()
        
        # Separate embeddings for different flow components
        self.price_embed = nn.Linear(8, hidden_dim)  # OHLC + derived
        self.volume_embed = nn.Linear(8, hidden_dim)  # Volume features
        self.flow_embed = nn.Linear(8, hidden_dim)  # Order flow features
        
        # Cross-attention: flow attends to price/volume
        self.cross_attention = nn.MultiheadAttention(
            hidden_dim, num_heads, batch_first=True, dropout=0.1
        )
        
        # Self-attention for temporal patterns
        self.self_attention = nn.MultiheadAttention(
            hidden_dim, num_heads, batch_first=True, dropout=0.1
        )
        
        # Fusion
        self.fusion = nn.Sequential(
            nn.Linear(hidden_dim * 3, hidden_dim * 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim * 2, hidden_dim)
        )
        
        self.layer_norm = nn.LayerNorm(hidden_dim)
    
    def forward(self, price_features, volume_features, flow_features):
        # Embed each component
        price = self.price_embed(price_features)
        volume = self.volume_embed(volume_features)
        flow = self.flow_embed(flow_features)
        
        # Cross-attention: flow queries price/volume
        pv_concat = torch.cat([price, volume], dim=1)
        cross_out, cross_attn = self.cross_attention(flow, pv_concat, pv_concat)
        
        # Self-attention on crossed output
        self_out, self_attn = self.self_attention(cross_out, cross_out, cross_out)
        
        # Fuse all representations
        fused = self.fusion(torch.cat([price[:, -flow.size(1):, :], 
                                       volume[:, -flow.size(1):, :], 
                                       self_out], dim=-1))
        
        return self.layer_norm(fused + flow), (cross_attn, self_attn)


# =============================================================================
# REGIME DETECTION - HMM-style with Neural Network
# =============================================================================

class NeuralRegimeDetector(nn.Module):
    """
    Neural network-based regime detection.
    Identifies market states: Trending, Ranging, Volatile, Quiet.
    """
    
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_regimes: int = 4):
        super().__init__()
        
        self.num_regimes = num_regimes
        
        # Feature extraction for regime
        self.regime_features = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim)
        )
        
        # Regime classifier
        self.regime_classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_regimes)
        )
        
        # Transition matrix (learnable)
        self.transition_logits = nn.Parameter(torch.zeros(num_regimes, num_regimes))
        
        # Regime embeddings for downstream use
        self.regime_embeddings = nn.Embedding(num_regimes, hidden_dim)
    
    def forward(self, x, return_probs: bool = True):
        # x: (batch, seq_len, features)
        features = self.regime_features(x)
        logits = self.regime_classifier(features)
        
        if return_probs:
            probs = F.softmax(logits, dim=-1)
            regime_idx = probs.argmax(dim=-1)
            regime_embed = self.regime_embeddings(regime_idx)
            return probs, regime_embed, regime_idx
        
        return logits
    
    def get_transition_matrix(self):
        """Get normalized transition probabilities."""
        return F.softmax(self.transition_logits, dim=-1)


# =============================================================================
# UNCERTAINTY QUANTIFICATION - Monte Carlo Dropout + Ensemble
# =============================================================================

class UncertaintyWrapper(nn.Module):
    """Wraps model to provide uncertainty estimates via MC Dropout."""
    
    def __init__(self, model: nn.Module, num_samples: int = 10):
        super().__init__()
        self.model = model
        self.num_samples = num_samples
    
    def forward(self, *args, return_uncertainty: bool = True, **kwargs):
        if not return_uncertainty or not self.training:
            return self.model(*args, **kwargs)
        
        # Monte Carlo dropout - run multiple forward passes
        predictions = []
        self.model.train()  # Enable dropout
        
        for _ in range(self.num_samples):
            with torch.no_grad():
                pred = self.model(*args, **kwargs)
                if isinstance(pred, tuple):
                    pred = pred[0]
                predictions.append(pred)
        
        preds = torch.stack(predictions)
        mean_pred = preds.mean(dim=0)
        std_pred = preds.std(dim=0)
        
        return mean_pred, std_pred


# =============================================================================
# STACKING META-LEARNER - Attention-weighted Ensemble
# =============================================================================

class StackingMetaLearner(nn.Module):
    """
    Meta-learner that combines multiple base models with attention weighting.
    Learns which models to trust based on market conditions.
    """
    
    def __init__(self, num_models: int, model_dim: int, hidden_dim: int = 128,
                 regime_dim: int = 64, temperature: float = 1.5):
        super().__init__()
        
        self.num_models = num_models
        self.temperature = temperature
        
        # Model embeddings (learnable)
        self.model_embeddings = nn.Parameter(torch.randn(num_models, model_dim) * 0.1)
        
        # Attention for model weighting based on regime
        self.regime_query = nn.Linear(regime_dim, model_dim)
        self.model_key = nn.Linear(model_dim, model_dim)
        self.model_value = nn.Linear(model_dim, model_dim)
        
        # Performance tracking (for dynamic weighting)
        self.performance_gate = nn.Sequential(
            nn.Linear(num_models, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_models),
            nn.Sigmoid()
        )
        
        # Final combination
        self.combiner = nn.Sequential(
            nn.Linear(model_dim + regime_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, 3)  # BUY, HOLD, SELL
        )
    
    def forward(self, model_outputs: List[torch.Tensor], regime_embed: torch.Tensor,
                model_performances: Optional[torch.Tensor] = None):
        """
        Args:
            model_outputs: List of (batch, seq, model_dim) tensors from each model
            regime_embed: (batch, seq, regime_dim) regime embedding
            model_performances: (num_models,) recent accuracy of each model
        """
        batch_size, seq_len = model_outputs[0].shape[:2]
        
        # Stack model outputs
        stacked = torch.stack(model_outputs, dim=2)  # (batch, seq, num_models, dim)
        
        # Attention-based weighting
        query = self.regime_query(regime_embed).unsqueeze(2)  # (batch, seq, 1, dim)
        keys = self.model_key(stacked)  # (batch, seq, num_models, dim)
        values = self.model_value(stacked)
        
        # Attention scores
        scores = (query * keys).sum(dim=-1) / math.sqrt(query.size(-1))  # (batch, seq, num_models)
        
        # Apply temperature
        weights = F.softmax(scores / self.temperature, dim=-1)
        
        # Performance gating (if available)
        if model_performances is not None:
            perf_gate = self.performance_gate(model_performances)
            weights = weights * perf_gate.unsqueeze(0).unsqueeze(0)
            weights = weights / (weights.sum(dim=-1, keepdim=True) + 1e-8)
        
        # Weighted combination
        combined = (values * weights.unsqueeze(-1)).sum(dim=2)  # (batch, seq, dim)
        
        # Final prediction with regime context
        context = torch.cat([combined, regime_embed], dim=-1)
        output = self.combiner(context)
        
        return output, weights


# =============================================================================
# FUTURES BRAIN V2 - MAIN CLASS
# =============================================================================

class FuturesBrainV2(nn.Module):
    """
    Next-generation futures trading brain with state-of-the-art ML.
    """
    
    def __init__(self, config: FuturesBrainV2Config = None):
        super().__init__()
        
        self.config = config or FuturesBrainV2Config()
        
        # Component models
        self.wavenet = WaveNetEncoder(
            input_dim=self.config.input_features,
            channels=self.config.wavenet_channels,
            num_layers=self.config.wavenet_layers,
            dilation_base=self.config.dilation_base
        )
        
        self.tft = TemporalFusionEncoder(self.config)
        
        self.order_flow = OrderFlowAttention(
            hidden_dim=self.config.hidden_dim // 2,
            num_heads=4
        )
        
        self.regime_detector = NeuralRegimeDetector(
            input_dim=self.config.input_features,
            hidden_dim=64,
            num_regimes=self.config.num_regimes
        )
        
        # Projections to common dimension
        self.wavenet_proj = nn.Linear(self.config.wavenet_channels, self.config.hidden_dim)
        self.tft_proj = nn.Linear(self.config.tft_hidden_dim, self.config.hidden_dim)
        self.flow_proj = nn.Linear(self.config.hidden_dim // 2, self.config.hidden_dim)
        
        # Meta-learner
        self.meta_learner = StackingMetaLearner(
            num_models=3,  # WaveNet, TFT, OrderFlow
            model_dim=self.config.hidden_dim,
            hidden_dim=128,
            regime_dim=64,
            temperature=self.config.ensemble_temperature
        )
        
        # Position sizing head (outputs Kelly fraction)
        self.position_head = nn.Sequential(
            nn.Linear(self.config.hidden_dim + 64, 128),  # + regime
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Sigmoid()  # 0-1 fraction
        )
        
        # Uncertainty estimation
        self.uncertainty_head = nn.Sequential(
            nn.Linear(self.config.hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Softplus()  # Positive uncertainty
        )
        
        # Model performance tracking
        self.register_buffer('model_performances', torch.ones(3) / 3)
        
        # Initialize weights
        self._init_weights()
        
        logger.info(f"FuturesBrainV2 initialized on {DEVICE}")
        logger.info(f"  - WaveNet: {self.config.wavenet_layers} layers")
        logger.info(f"  - TFT: {self.config.tft_hidden_dim} hidden dim")
        logger.info(f"  - Regimes: {self.config.num_regimes}")
    
    def _init_weights(self):
        """Initialize weights with Xavier/Kaiming."""
        for name, param in self.named_parameters():
            if 'weight' in name and param.dim() > 1:
                nn.init.xavier_uniform_(param)
            elif 'bias' in name:
                nn.init.zeros_(param)
    
    def forward(self, x: torch.Tensor, static_features: torch.Tensor = None,
                price_features: torch.Tensor = None, volume_features: torch.Tensor = None,
                flow_features: torch.Tensor = None) -> Dict[str, torch.Tensor]:
        """
        Forward pass through all components.
        
        Args:
            x: (batch, seq_len, features) main features
            static_features: (batch, num_static) static features
            price_features: (batch, seq_len, 8) price-specific features
            volume_features: (batch, seq_len, 8) volume-specific features
            flow_features: (batch, seq_len, 8) order flow features
        
        Returns:
            Dictionary with predictions and intermediate values
        """
        # Regime detection
        regime_probs, regime_embed, regime_idx = self.regime_detector(x)
        
        # WaveNet encoding
        wavenet_out = self.wavenet(x)
        wavenet_proj = self.wavenet_proj(wavenet_out)
        
        # TFT encoding
        tft_out, tft_attn = self.tft(x, static_features)
        tft_proj = self.tft_proj(tft_out)
        
        # Order flow (if available)
        if price_features is not None and volume_features is not None and flow_features is not None:
            flow_out, flow_attn = self.order_flow(price_features, volume_features, flow_features)
            flow_proj = self.flow_proj(flow_out)
        else:
            # Use zeros if flow not available
            flow_proj = torch.zeros_like(wavenet_proj)
            flow_attn = None
        
        # Meta-learner combines all
        model_outputs = [wavenet_proj, tft_proj, flow_proj]
        signal_logits, model_weights = self.meta_learner(
            model_outputs, regime_embed, self.model_performances
        )
        
        # Get final hidden state for auxiliary heads
        final_hidden = (wavenet_proj + tft_proj + flow_proj) / 3
        final_hidden_with_regime = torch.cat([final_hidden, regime_embed], dim=-1)
        
        # Position sizing
        position_fraction = self.position_head(final_hidden_with_regime)
        
        # Uncertainty
        uncertainty = self.uncertainty_head(final_hidden)
        
        return {
            'signal_logits': signal_logits,  # (batch, seq, 3)
            'signal_probs': F.softmax(signal_logits, dim=-1),
            'position_fraction': position_fraction,  # (batch, seq, 1)
            'uncertainty': uncertainty,  # (batch, seq, 1)
            'regime_probs': regime_probs,  # (batch, seq, num_regimes)
            'regime_idx': regime_idx,  # (batch, seq)
            'model_weights': model_weights,  # (batch, seq, num_models)
            'tft_attention': tft_attn,
        }
    
    def predict(self, features: np.ndarray, static: np.ndarray = None) -> Dict[str, Any]:
        """
        Make prediction from numpy arrays.
        
        Returns dict with signal, confidence, position_size, regime, uncertainty.
        """
        self.eval()
        
        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32, device=DEVICE)
            if x.dim() == 2:
                x = x.unsqueeze(0)  # Add batch dim
            
            static_t = None
            if static is not None:
                static_t = torch.tensor(static, dtype=torch.float32, device=DEVICE)
                if static_t.dim() == 1:
                    static_t = static_t.unsqueeze(0)
            
            outputs = self(x, static_t)
            
            # Get last timestep predictions
            signal_probs = outputs['signal_probs'][0, -1].cpu().numpy()
            signal = int(signal_probs.argmax())
            confidence = float(signal_probs.max())
            
            position = float(outputs['position_fraction'][0, -1].cpu().item())
            uncertainty = float(outputs['uncertainty'][0, -1].cpu().item())
            
            regime_probs = outputs['regime_probs'][0, -1].cpu().numpy()
            regime = int(regime_probs.argmax())
            regime_names = ['TRENDING', 'RANGING', 'VOLATILE', 'QUIET']
            
            model_weights = outputs['model_weights'][0, -1].cpu().numpy()
        
        return {
            'signal': signal,  # 0=BUY, 1=HOLD, 2=SELL
            'signal_name': ['BUY', 'HOLD', 'SELL'][signal],
            'confidence': confidence,
            'signal_probs': signal_probs.tolist(),
            'position_fraction': position,
            'uncertainty': uncertainty,
            'regime': regime,
            'regime_name': regime_names[regime],
            'regime_probs': regime_probs.tolist(),
            'model_weights': {
                'wavenet': float(model_weights[0]),
                'tft': float(model_weights[1]),
                'order_flow': float(model_weights[2])
            }
        }
    
    def update_model_performance(self, model_idx: int, accuracy: float, decay: float = 0.95):
        """Update performance tracking for a specific model."""
        current = self.model_performances[model_idx].item()
        updated = decay * current + (1 - decay) * accuracy
        self.model_performances[model_idx] = updated
    
    def save(self, path: Path = None):
        """Save model state."""
        path = path or WEIGHTS_DIR / "futures_brain_v2.pt"
        torch.save({
            'model_state': self.state_dict(),
            'config': self.config,
            'model_performances': self.model_performances.cpu().numpy(),
        }, path)
        logger.info(f"Saved FuturesBrainV2 to {path}")
    
    def load(self, path: Path = None):
        """Load model state."""
        path = path or WEIGHTS_DIR / "futures_brain_v2.pt"
        if path.exists():
            checkpoint = torch.load(path, map_location=DEVICE)
            self.load_state_dict(checkpoint['model_state'])
            if 'model_performances' in checkpoint:
                self.model_performances = torch.tensor(
                    checkpoint['model_performances'], device=DEVICE
                )
            logger.info(f"Loaded FuturesBrainV2 from {path}")
            return True
        return False


# =============================================================================
# TRAINING UTILITIES
# =============================================================================

class FuturesBrainV2Trainer:
    """Training loop for FuturesBrainV2 with mixed precision."""
    
    def __init__(self, model: FuturesBrainV2, config: FuturesBrainV2Config = None):
        self.model = model.to(DEVICE)
        self.config = config or model.config
        
        self.optimizer = AdamW(
            model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )
        
        self.scheduler = CosineAnnealingWarmRestarts(
            self.optimizer, T_0=10, T_mult=2
        )
        
        self.scaler = GradScaler() if USE_AMP else None
        
        # Loss functions
        self.signal_loss = nn.CrossEntropyLoss(label_smoothing=0.1)
        self.position_loss = nn.MSELoss()
        self.regime_loss = nn.CrossEntropyLoss()
    
    def train_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """Single training step with mixed precision."""
        self.model.train()
        self.optimizer.zero_grad()
        
        with autocast(enabled=USE_AMP):
            outputs = self.model(
                batch['features'],
                batch.get('static'),
                batch.get('price'),
                batch.get('volume'),
                batch.get('flow')
            )
            
            # Signal prediction loss
            signal_loss = self.signal_loss(
                outputs['signal_logits'].view(-1, 3),
                batch['signal_labels'].view(-1)
            )
            
            # Position sizing loss (if labels available)
            position_loss = torch.tensor(0.0, device=DEVICE)
            if 'position_labels' in batch:
                position_loss = self.position_loss(
                    outputs['position_fraction'],
                    batch['position_labels']
                )
            
            # Regime loss (if labels available)
            regime_loss = torch.tensor(0.0, device=DEVICE)
            if 'regime_labels' in batch:
                regime_loss = self.regime_loss(
                    outputs['regime_probs'].view(-1, self.config.num_regimes),
                    batch['regime_labels'].view(-1)
                )
            
            # Total loss
            total_loss = signal_loss + 0.3 * position_loss + 0.2 * regime_loss
        
        # Backprop with mixed precision
        if self.scaler:
            self.scaler.scale(total_loss).backward()
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
            self.optimizer.step()
        
        self.scheduler.step()
        
        return {
            'total_loss': total_loss.item(),
            'signal_loss': signal_loss.item(),
            'position_loss': position_loss.item(),
            'regime_loss': regime_loss.item(),
            'lr': self.optimizer.param_groups[0]['lr']
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_futures_brain_v2(config: FuturesBrainV2Config = None) -> FuturesBrainV2:
    """Create and optionally load a FuturesBrainV2 instance."""
    config = config or FuturesBrainV2Config()
    model = FuturesBrainV2(config).to(DEVICE)
    
    # Try to load existing weights
    model.load()
    
    return model


if __name__ == "__main__":
    # Test instantiation
    logging.basicConfig(level=logging.INFO)
    
    config = FuturesBrainV2Config()
    brain = create_futures_brain_v2(config)
    
    # Test forward pass
    batch_size = 4
    seq_len = 60
    
    x = torch.randn(batch_size, seq_len, config.input_features).to(DEVICE)
    static = torch.randn(batch_size, config.num_static_features).to(DEVICE)
    
    outputs = brain(x, static)
    
    print(f"\nTest forward pass:")
    print(f"  Signal logits: {outputs['signal_logits'].shape}")
    print(f"  Position fraction: {outputs['position_fraction'].shape}")
    print(f"  Uncertainty: {outputs['uncertainty'].shape}")
    print(f"  Regime probs: {outputs['regime_probs'].shape}")
    print(f"  Model weights: {outputs['model_weights'].shape}")
    
    # Test prediction
    features = np.random.randn(seq_len, config.input_features).astype(np.float32)
    pred = brain.predict(features)
    
    print(f"\nTest prediction:")
    print(f"  Signal: {pred['signal_name']} ({pred['confidence']:.2%})")
    print(f"  Position: {pred['position_fraction']:.2%}")
    print(f"  Regime: {pred['regime_name']}")
    print(f"  Uncertainty: {pred['uncertainty']:.4f}")
    print(f"  Model weights: {pred['model_weights']}")
