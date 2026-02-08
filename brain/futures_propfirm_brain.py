"""
FUTURES PROP FIRM BRAIN - ML/DEEP LEARNING FOR PROP FIRM EVALUATIONS
======================================================================
Advanced neural learning system specifically designed for futures prop firm
evaluations (TPT, Topstep, Apex, etc.) with bidirectional feedback loop.

ARCHITECTURE (Same as ML Brain):
1. LSTM Sequence Predictor - Temporal futures pattern recognition
2. Transformer Attention - Multi-timeframe futures analysis  
3. CNN Feature Extractor - Price action & order flow patterns
4. Reinforcement Learning - Adaptive position sizing for eval rules
5. Online Learning - Real-time adaptation to market conditions
6. Meta-Learner - Ensemble coordination with TPT Bot feedback

FEEDBACK LOOP:
┌─────────────────────────────────────────────────────────────────────┐
│                    BIDIRECTIONAL FEEDBACK LOOP                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────────┐          ┌──────────────────┐                │
│   │  FuturesPropFirm │  share   │                  │                │
│   │       Brain      │ ───────► │    TPT Bot       │                │
│   │                  │  params  │                  │                │
│   │  - LSTM          │          │  - Executes      │                │
│   │  - Transformer   │◄──────── │  - Monitors      │                │
│   │  - CNN           │  adjust  │  - Validates     │                │
│   │  - RL Sizer      │  signals │                  │                │
│   └──────────────────┘          └──────────────────┘                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

PROP FIRM RULES SUPPORTED:
- Daily loss limits (trailing/fixed)
- Maximum drawdown tracking
- Minimum trading days
- Daily profit targets
- Position size limits
- Time-of-day restrictions

Author: QuantBrain Futures System
Version: 1.0.0
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR, CosineAnnealingWarmRestarts
import sqlite3
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
import pickle
import copy

logger = logging.getLogger("FUTURES_PROPFIRM_BRAIN")

# Paths
ROOT = Path(__file__).parent.parent
WEIGHTS_DIR = ROOT / "weights" / "futures_propfirm"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = ROOT / "data" / "futures_propfirm_brain.db"

# GPU Detection
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# =============================================================================
# PROP FIRM CONFIGURATIONS
# =============================================================================

class PropFirmType(Enum):
    """Supported prop firm types."""
    TPT_50K = "tpt_50k"
    TPT_100K = "tpt_100k"
    TPT_150K = "tpt_150k"
    TOPSTEP_50K = "topstep_50k"
    TOPSTEP_100K = "topstep_100k"
    APEX_50K = "apex_50k"
    APEX_100K = "apex_100k"
    CUSTOM = "custom"


@dataclass
class PropFirmRuleset:
    """
    Configuration for prop firm evaluation rules.
    These rules are CRITICAL for passing evaluations.
    """
    firm_type: PropFirmType
    account_size: float
    
    # Loss Limits
    daily_loss_limit: float  # Max loss per day
    trailing_drawdown: float  # Trailing max drawdown
    max_drawdown: float  # Absolute max drawdown
    
    # Targets
    profit_target: float  # Required profit to pass
    daily_target: float  # Optimal daily profit
    
    # Trading Rules
    min_trading_days: int  # Minimum days to trade
    max_contracts: int  # Maximum position size
    max_positions: int  # Maximum concurrent positions
    
    # Time Rules
    trading_hours_start: int = 6  # Hour (24h format)
    trading_hours_end: int = 16
    no_weekend_holds: bool = True
    no_news_trading: bool = True
    
    # Risk Management
    risk_per_trade: float = 0.01  # 1% risk per trade
    max_daily_trades: int = 10
    min_trade_interval_minutes: int = 5
    
    # Scaling Rules
    scale_in_allowed: bool = True
    scale_out_required: bool = False
    
    @classmethod
    def get_tpt_50k(cls) -> 'PropFirmRuleset':
        """TPT 50K Evaluation rules."""
        return cls(
            firm_type=PropFirmType.TPT_50K,
            account_size=50000,
            daily_loss_limit=1100,
            trailing_drawdown=2000,
            max_drawdown=2500,
            profit_target=3000,
            daily_target=600,
            min_trading_days=5,
            max_contracts=6,
            max_positions=2,
            risk_per_trade=0.015,
            max_daily_trades=8
        )
    
    @classmethod
    def get_tpt_100k(cls) -> 'PropFirmRuleset':
        """TPT 100K Evaluation rules."""
        return cls(
            firm_type=PropFirmType.TPT_100K,
            account_size=100000,
            daily_loss_limit=2200,
            trailing_drawdown=3000,
            max_drawdown=3500,
            profit_target=6000,
            daily_target=1200,
            min_trading_days=5,
            max_contracts=12,
            max_positions=3,
            risk_per_trade=0.015,
            max_daily_trades=10
        )
    
    @classmethod
    def get_tpt_150k(cls) -> 'PropFirmRuleset':
        """TPT 150K Evaluation rules."""
        return cls(
            firm_type=PropFirmType.TPT_150K,
            account_size=150000,
            daily_loss_limit=3300,
            trailing_drawdown=4500,
            max_drawdown=5000,
            profit_target=9000,
            daily_target=1800,
            min_trading_days=5,
            max_contracts=15,
            max_positions=4,
            risk_per_trade=0.015,
            max_daily_trades=12
        )


# =============================================================================
# FEEDBACK LOOP DATA STRUCTURES
# =============================================================================

@dataclass
class AdjustmentSignal:
    """
    Signal sent from TPT Bot back to ML Brain for adjustment.
    This is the core feedback mechanism.
    """
    signal_id: str
    timestamp: datetime
    signal_type: str  # 'weight_adjustment', 'confidence_calibration', 'risk_adjustment'
    
    # Adjustment data
    strategy_adjustments: Dict[str, float] = field(default_factory=dict)
    confidence_bias: float = 0.0  # Positive = increase confidence, Negative = decrease
    risk_multiplier: float = 1.0  # Scale position sizes
    
    # Context
    recent_win_rate: float = 0.5
    recent_pnl: float = 0.0
    drawdown_level: float = 0.0
    trading_days_remaining: int = 0
    profit_to_target: float = 0.0
    
    # Performance feedback
    model_accuracy: float = 0.5
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    
    # Rule violations
    rule_violations: List[str] = field(default_factory=list)
    
    # Urgency level (0-1, higher = more urgent adjustment needed)
    urgency: float = 0.0


@dataclass
class SharedParameters:
    """
    Parameters shared from FuturesPropFirmBrain to TPT Bot.
    Contains learned weights, thresholds, and configurations.
    """
    param_id: str
    timestamp: datetime
    version: int
    
    # Model weights (serialized)
    lstm_weights: Optional[bytes] = None
    transformer_weights: Optional[bytes] = None
    cnn_weights: Optional[bytes] = None
    rl_weights: Optional[bytes] = None
    
    # Ensemble configuration
    ensemble_weights: Dict[str, float] = field(default_factory=dict)
    confidence_thresholds: Dict[str, float] = field(default_factory=dict)
    
    # Risk parameters
    position_size_table: Dict[str, int] = field(default_factory=dict)  # confidence -> contracts
    stop_loss_atr_mult: float = 1.5
    take_profit_atr_mult: float = 2.5
    
    # Regime-specific parameters
    regime_configs: Dict[str, Dict] = field(default_factory=dict)
    
    # Performance stats
    training_epochs: int = 0
    validation_accuracy: float = 0.0
    sharpe_ratio: float = 0.0
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary for transmission."""
        return {
            'param_id': self.param_id,
            'timestamp': self.timestamp.isoformat(),
            'version': self.version,
            'ensemble_weights': self.ensemble_weights,
            'confidence_thresholds': self.confidence_thresholds,
            'position_size_table': self.position_size_table,
            'stop_loss_atr_mult': self.stop_loss_atr_mult,
            'take_profit_atr_mult': self.take_profit_atr_mult,
            'regime_configs': self.regime_configs,
            'training_epochs': self.training_epochs,
            'validation_accuracy': self.validation_accuracy,
            'sharpe_ratio': self.sharpe_ratio
        }


@dataclass
class TradeRecord:
    """Complete record of a futures trade for learning."""
    trade_id: str
    symbol: str  # MNQ, MES, etc.
    direction: str  # LONG or SHORT
    contracts: int
    
    # Prices
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    # Timestamps
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    
    # Strategy attribution
    primary_model: str = ""  # lstm, transformer, cnn, rl, ensemble
    model_scores: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    
    # Context at entry
    regime: str = ""
    atr_at_entry: float = 0.0
    volatility: float = 0.0
    trend_strength: float = 0.0
    
    # Results
    pnl: float = 0.0
    pnl_pct: float = 0.0
    ticks_captured: int = 0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    hold_time_minutes: float = 0.0
    
    # Exit info
    exit_reason: str = ""  # TP_HIT, SL_HIT, TRAIL_STOP, TIME_EXIT, RULE_VIOLATION
    is_closed: bool = False
    
    # Prop firm tracking
    daily_pnl_after: float = 0.0
    drawdown_after: float = 0.0
    trading_day: int = 0




# =============================================================================
# NEURAL NETWORK MODELS (Same Architecture as tpt_deep_learning.py)
# =============================================================================

@dataclass
class FuturesModelConfig:
    """Configuration for futures ML models."""
    # Model dimensions
    input_features: int = 72  # Extended for futures-specific features
    hidden_dim: int = 256
    num_layers: int = 4
    num_heads: int = 8
    dropout: float = 0.1
    
    # Sequence settings
    sequence_length: int = 60  # 5 hours of 5m bars
    prediction_horizon: int = 12  # 1 hour ahead
    
    # Training
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5
    batch_size: int = 32
    
    # Online learning
    online_learning_rate: float = 1e-5
    adaptation_window: int = 100
    
    # Ensemble weights (dynamically adjusted via feedback)
    lstm_weight: float = 0.25
    transformer_weight: float = 0.30
    cnn_weight: float = 0.20
    rl_weight: float = 0.25


class FuturesLSTMPredictor(nn.Module):
    """
    LSTM-based predictor for futures scalping.
    Optimized for capturing short-term price momentum.
    """
    
    def __init__(self, config: FuturesModelConfig):
        super().__init__()
        self.config = config
        
        # Input normalization
        self.input_norm = nn.LayerNorm(config.input_features)
        
        # Bidirectional LSTM stack
        self.lstm = nn.LSTM(
            input_size=config.input_features,
            hidden_size=config.hidden_dim,
            num_layers=config.num_layers,
            batch_first=True,
            dropout=config.dropout if config.num_layers > 1 else 0,
            bidirectional=True
        )
        
        # Attention for sequence weighting
        self.attention = nn.MultiheadAttention(
            embed_dim=config.hidden_dim * 2,
            num_heads=config.num_heads,
            dropout=config.dropout,
            batch_first=True
        )
        
        self.dropout = nn.Dropout(config.dropout)
        
        # Output layers: 3 classes (SHORT=-1, HOLD=0, LONG=1)
        self.fc1 = nn.Linear(config.hidden_dim * 2, config.hidden_dim)
        self.fc2 = nn.Linear(config.hidden_dim, 3)
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass with confidence estimation."""
        # Normalize input
        x = self.input_norm(x)
        
        # LSTM forward
        lstm_out, _ = self.lstm(x)
        
        # Self-attention
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        attn_out = self.dropout(attn_out)
        
        # Take last timestep
        final = attn_out[:, -1, :]
        
        # Output
        out = F.gelu(self.fc1(final))
        out = self.dropout(out)
        logits = self.fc2(out)
        
        # Confidence from softmax entropy
        probs = F.softmax(logits, dim=-1)
        entropy = -torch.sum(probs * torch.log(probs + 1e-8), dim=-1, keepdim=True)
        confidence = 1 - (entropy / np.log(3))
        
        return logits, confidence


class FuturesTransformerPredictor(nn.Module):
    """
    Transformer-based predictor for futures.
    Captures long-range dependencies and multi-timeframe patterns.
    """
    
    def __init__(self, config: FuturesModelConfig):
        super().__init__()
        self.config = config
        
        # Input projection
        self.input_proj = nn.Linear(config.input_features, config.hidden_dim)
        
        # Positional encoding
        self.pos_encoding = nn.Parameter(
            self._create_positional_encoding(config.sequence_length, config.hidden_dim)
        )
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_dim * 4,
            dropout=config.dropout,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)
        
        # Multi-scale pooling
        self.pool_1 = nn.AdaptiveAvgPool1d(1)
        self.pool_5 = nn.AdaptiveAvgPool1d(5)
        self.pool_10 = nn.AdaptiveAvgPool1d(10)
        
        # Output
        self.fc = nn.Sequential(
            nn.Linear(config.hidden_dim * 16, config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim, 3)
        )
    
    def _create_positional_encoding(self, seq_len: int, d_model: int) -> torch.Tensor:
        """Create sinusoidal positional encoding."""
        position = torch.arange(seq_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
        pe = torch.zeros(1, seq_len, d_model)
        pe[0, :, 0::2] = torch.sin(position * div_term)
        pe[0, :, 1::2] = torch.cos(position * div_term)
        return pe
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass."""
        batch_size = x.shape[0]
        
        # Project input
        x = self.input_proj(x)
        
        # Add positional encoding
        x = x + self.pos_encoding[:, :x.shape[1], :].to(x.device)
        
        # Transformer
        x = self.transformer(x)
        
        # Multi-scale pooling
        x_t = x.transpose(1, 2)
        pool1 = self.pool_1(x_t).flatten(1)
        pool5 = self.pool_5(x_t).flatten(1)
        pool10 = self.pool_10(x_t).flatten(1)
        
        # Concatenate
        pooled = torch.cat([pool1, pool5, pool10], dim=1)
        
        # Output
        logits = self.fc(pooled)
        
        # Confidence
        probs = F.softmax(logits, dim=-1)
        confidence = torch.max(probs, dim=-1, keepdim=True)[0]
        
        return logits, confidence


class FuturesCNNPredictor(nn.Module):
    """
    CNN-based pattern recognizer for futures price action.
    Detects candlestick patterns and chart formations.
    """
    
    def __init__(self, config: FuturesModelConfig):
        super().__init__()
        self.config = config
        
        # 1D Convolutions for different pattern scales
        self.conv1 = nn.Conv1d(config.input_features, 128, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(128, 256, kernel_size=5, padding=2)
        self.conv3 = nn.Conv1d(256, 256, kernel_size=7, padding=3)
        self.conv4 = nn.Conv1d(256, config.hidden_dim, kernel_size=11, padding=5)
        
        self.bn1 = nn.BatchNorm1d(128)
        self.bn2 = nn.BatchNorm1d(256)
        self.bn3 = nn.BatchNorm1d(256)
        self.bn4 = nn.BatchNorm1d(config.hidden_dim)
        
        # Global pooling
        self.global_pool = nn.AdaptiveMaxPool1d(1)
        
        # Output
        self.fc = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, 3)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass."""
        # Transpose for conv1d (batch, features, seq)
        x = x.transpose(1, 2)
        
        # Convolutions
        x = F.gelu(self.bn1(self.conv1(x)))
        x = F.gelu(self.bn2(self.conv2(x)))
        x = F.gelu(self.bn3(self.conv3(x)))
        x = F.gelu(self.bn4(self.conv4(x)))
        
        # Global pooling
        x = self.global_pool(x).squeeze(-1)
        
        # Output
        logits = self.fc(x)
        
        probs = F.softmax(logits, dim=-1)
        confidence = torch.max(probs, dim=-1, keepdim=True)[0]
        
        return logits, confidence


class FuturesRLPositionSizer(nn.Module):
    """
    Reinforcement learning position sizer for prop firm rules.
    Learns optimal contract allocation respecting evaluation constraints.
    """
    
    def __init__(self, config: FuturesModelConfig, ruleset: PropFirmRuleset):
        super().__init__()
        self.config = config
        self.ruleset = ruleset
        
        # Account state features: 8 dimensions
        # [daily_pnl_pct, drawdown_pct, days_remaining_pct, profit_to_target_pct,
        #  recent_win_rate, consecutive_losses, time_of_day_pct, volatility_regime]
        
        # State encoder
        self.state_encoder = nn.Sequential(
            nn.Linear(config.input_features + 8, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
        )
        
        # Actor (policy) - outputs contract allocation (0 to max_contracts)
        self.actor = nn.Sequential(
            nn.Linear(config.hidden_dim // 2, 64),
            nn.GELU(),
            nn.Linear(64, ruleset.max_contracts + 1)
        )
        
        # Critic (value)
        self.critic = nn.Sequential(
            nn.Linear(config.hidden_dim // 2, 64),
            nn.GELU(),
            nn.Linear(64, 1)
        )
        
        # Experience buffer for online RL
        self.experience_buffer = deque(maxlen=1000)
        
    def forward(self, features: torch.Tensor, account_state: torch.Tensor
               ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            features: Market features (batch, seq, input_features)
            account_state: Account state (batch, 8)
        
        Returns:
            action_probs: Contract allocation probabilities
            value: State value estimate
            confidence: Action confidence
        """
        # Take last timestep of features
        if len(features.shape) == 3:
            features = features[:, -1, :]
        
        # Concatenate with account state
        combined = torch.cat([features, account_state], dim=-1)
        
        # Encode state
        encoded = self.state_encoder(combined)
        
        # Actor output
        action_logits = self.actor(encoded)
        action_probs = F.softmax(action_logits, dim=-1)
        
        # Critic output
        value = self.critic(encoded)
        
        # Confidence from action distribution entropy
        entropy = -torch.sum(action_probs * torch.log(action_probs + 1e-8), dim=-1, keepdim=True)
        max_entropy = np.log(self.ruleset.max_contracts + 1)
        confidence = 1 - (entropy / max_entropy)
        
        return action_probs, value, confidence
    
    def select_contracts(self, features: torch.Tensor, account_state: torch.Tensor,
                        deterministic: bool = False) -> Tuple[int, float]:
        """
        Select number of contracts based on policy.
        
        Returns:
            contracts: Number of contracts to trade
            confidence: Confidence in the selection
        """
        with torch.no_grad():
            action_probs, _, confidence = self.forward(features, account_state)
            
            if deterministic:
                contracts = torch.argmax(action_probs, dim=-1).item()
            else:
                # Sample from distribution
                contracts = torch.multinomial(action_probs, 1).item()
        
        return contracts, confidence.item()




# =============================================================================
# MAIN BRAIN CLASS WITH FEEDBACK LOOP
# =============================================================================

class FuturesPropFirmBrain:
    """
    Main ML Brain for futures prop firm trading.
    
    Features:
    - Same ML/Deep Learning architecture as ML Brain
    - Prop firm rule-aware training
    - Bidirectional feedback loop with TPT Bot
    - Online learning and adaptation
    """
    
    def __init__(self, ruleset: Optional[PropFirmRuleset] = None):
        """
        Initialize the Futures Prop Firm Brain.
        
        Args:
            ruleset: Prop firm rules to optimize for (default: TPT 50K)
        """
        self.ruleset = ruleset or PropFirmRuleset.get_tpt_50k()
        self.config = FuturesModelConfig()
        
        # Initialize models
        print(f"[FUTURES BRAIN] Initializing for {self.ruleset.firm_type.value}...")
        print(f"[FUTURES BRAIN] Device: {DEVICE}")
        
        self.lstm_model = FuturesLSTMPredictor(self.config).to(DEVICE)
        self.transformer_model = FuturesTransformerPredictor(self.config).to(DEVICE)
        self.cnn_model = FuturesCNNPredictor(self.config).to(DEVICE)
        self.rl_model = FuturesRLPositionSizer(self.config, self.ruleset).to(DEVICE)
        
        # Optimizers
        self.lstm_optimizer = AdamW(self.lstm_model.parameters(), 
                                    lr=self.config.learning_rate,
                                    weight_decay=self.config.weight_decay)
        self.transformer_optimizer = AdamW(self.transformer_model.parameters(),
                                           lr=self.config.learning_rate,
                                           weight_decay=self.config.weight_decay)
        self.cnn_optimizer = AdamW(self.cnn_model.parameters(),
                                   lr=self.config.learning_rate,
                                   weight_decay=self.config.weight_decay)
        self.rl_optimizer = AdamW(self.rl_model.parameters(),
                                  lr=self.config.learning_rate,
                                  weight_decay=self.config.weight_decay)
        
        # === FEEDBACK LOOP STATE ===
        self.adjustment_queue: deque[AdjustmentSignal] = deque(maxlen=100)
        self.shared_params_history: List[SharedParameters] = []
        self.param_version = 0
        
        # Ensemble weights (adjusted via feedback)
        self.ensemble_weights = {
            'lstm': self.config.lstm_weight,
            'transformer': self.config.transformer_weight,
            'cnn': self.config.cnn_weight,
            'rl': self.config.rl_weight
        }
        
        # Confidence calibration (adjusted via feedback)
        self.confidence_bias = 0.0
        self.risk_multiplier = 1.0
        
        # === LEARNING STATE ===
        self.trade_history: deque[TradeRecord] = deque(maxlen=5000)
        self.training_data_buffer: List[Tuple] = []
        self.total_epochs = 0
        self.best_validation_loss = float('inf')
        
        # Online learning buffer
        self.online_buffer: deque = deque(maxlen=self.config.adaptation_window)
        
        # === PROP FIRM TRACKING ===
        self.current_daily_pnl = 0.0
        self.current_drawdown = 0.0
        self.peak_balance = self.ruleset.account_size
        self.trading_days = 0
        self.consecutive_losses = 0
        
        # === DATABASE ===
        self._init_database()
        self._load_state()
        
        # === CALLBACKS ===
        self._tpt_bot_callback: Optional[Callable[[SharedParameters], None]] = None
        
        print(f"[FUTURES BRAIN] Models initialized: {self._count_parameters():,} parameters")
    
    def _count_parameters(self) -> int:
        """Count total trainable parameters."""
        total = 0
        for model in [self.lstm_model, self.transformer_model, self.cnn_model, self.rl_model]:
            total += sum(p.numel() for p in model.parameters() if p.requires_grad)
        return total
    
    # =========================================================================
    # FEEDBACK LOOP: SEND PARAMETERS TO TPT BOT
    # =========================================================================
    
    def share_parameters_to_tpt_bot(self) -> SharedParameters:
        """
        Package and share current model parameters to TPT Bot.
        This is the SEND direction of the feedback loop.
        
        Returns:
            SharedParameters object containing all learned configurations
        """
        self.param_version += 1
        
        params = SharedParameters(
            param_id=f"fpb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.param_version}",
            timestamp=datetime.now(),
            version=self.param_version,
            
            # Serialize model weights
            lstm_weights=self._serialize_model(self.lstm_model),
            transformer_weights=self._serialize_model(self.transformer_model),
            cnn_weights=self._serialize_model(self.cnn_model),
            rl_weights=self._serialize_model(self.rl_model),
            
            # Current ensemble configuration
            ensemble_weights=self.ensemble_weights.copy(),
            
            # Confidence thresholds per regime
            confidence_thresholds={
                'trending': 0.65 + self.confidence_bias,
                'ranging': 0.70 + self.confidence_bias,
                'volatile': 0.75 + self.confidence_bias,
                'quiet': 0.60 + self.confidence_bias
            },
            
            # Position sizing table
            position_size_table=self._compute_position_size_table(),
            
            # Risk parameters
            stop_loss_atr_mult=1.5 * self.risk_multiplier,
            take_profit_atr_mult=2.5 * self.risk_multiplier,
            
            # Regime-specific configs
            regime_configs=self._get_regime_configs(),
            
            # Performance stats
            training_epochs=self.total_epochs,
            validation_accuracy=self._get_validation_accuracy(),
            sharpe_ratio=self._calculate_sharpe_ratio()
        )
        
        # Store in history
        self.shared_params_history.append(params)
        
        # Save to database
        self._save_shared_params(params)
        
        # Invoke callback if registered
        if self._tpt_bot_callback:
            self._tpt_bot_callback(params)
        
        print(f"[FUTURES BRAIN] Shared params v{self.param_version} to TPT Bot")
        print(f"  - Ensemble: LSTM={params.ensemble_weights['lstm']:.2f}, "
              f"Transformer={params.ensemble_weights['transformer']:.2f}, "
              f"CNN={params.ensemble_weights['cnn']:.2f}, "
              f"RL={params.ensemble_weights['rl']:.2f}")
        
        return params
    
    def register_tpt_bot_callback(self, callback: Callable[[SharedParameters], None]):
        """
        Register callback for TPT Bot to receive parameters.
        
        Args:
            callback: Function to call when parameters are shared
        """
        self._tpt_bot_callback = callback
        print("[FUTURES BRAIN] TPT Bot callback registered")
    
    # =========================================================================
    # FEEDBACK LOOP: RECEIVE ADJUSTMENTS FROM TPT BOT
    # =========================================================================
    
    def receive_adjustment_from_tpt_bot(self, signal: AdjustmentSignal):
        """
        Receive and process adjustment signal from TPT Bot.
        This is the RECEIVE direction of the feedback loop.
        
        Args:
            signal: Adjustment signal containing performance feedback
        """
        self.adjustment_queue.append(signal)
        
        print(f"\n[FUTURES BRAIN] 📥 Received adjustment signal: {signal.signal_type}")
        print(f"  - Urgency: {signal.urgency:.2f}")
        print(f"  - Recent Win Rate: {signal.recent_win_rate:.1%}")
        print(f"  - Drawdown Level: {signal.drawdown_level:.1%}")
        
        # Process based on signal type
        if signal.signal_type == 'weight_adjustment':
            self._apply_weight_adjustment(signal)
        elif signal.signal_type == 'confidence_calibration':
            self._apply_confidence_calibration(signal)
        elif signal.signal_type == 'risk_adjustment':
            self._apply_risk_adjustment(signal)
        elif signal.signal_type == 'emergency_stop':
            self._apply_emergency_stop(signal)
        
        # Check for rule violations and adjust accordingly
        if signal.rule_violations:
            self._handle_rule_violations(signal.rule_violations)
        
        # Trigger online learning if enough feedback accumulated
        if len(self.adjustment_queue) >= 5:
            self._online_learning_step()
        
        # Save state
        self._save_adjustment_signal(signal)
    
    def _apply_weight_adjustment(self, signal: AdjustmentSignal):
        """Apply ensemble weight adjustments based on feedback."""
        for model_name, adjustment in signal.strategy_adjustments.items():
            if model_name in self.ensemble_weights:
                old_weight = self.ensemble_weights[model_name]
                # Smooth adjustment (don't change too drastically)
                new_weight = old_weight + (adjustment * 0.1 * signal.urgency)
                self.ensemble_weights[model_name] = np.clip(new_weight, 0.05, 0.5)
                print(f"  - {model_name}: {old_weight:.3f} -> {self.ensemble_weights[model_name]:.3f}")
        
        # Normalize weights to sum to 1
        total = sum(self.ensemble_weights.values())
        self.ensemble_weights = {k: v/total for k, v in self.ensemble_weights.items()}
    
    def _apply_confidence_calibration(self, signal: AdjustmentSignal):
        """Apply confidence bias adjustment."""
        old_bias = self.confidence_bias
        
        # If false positive rate high, increase confidence threshold
        if signal.false_positive_rate > 0.3:
            self.confidence_bias += 0.05 * signal.urgency
        # If false negative rate high, decrease threshold
        elif signal.false_negative_rate > 0.3:
            self.confidence_bias -= 0.03 * signal.urgency
        else:
            # Gentle drift toward provided bias
            self.confidence_bias = (self.confidence_bias * 0.9) + (signal.confidence_bias * 0.1)
        
        self.confidence_bias = np.clip(self.confidence_bias, -0.15, 0.15)
        print(f"  - Confidence bias: {old_bias:.3f} -> {self.confidence_bias:.3f}")
    
    def _apply_risk_adjustment(self, signal: AdjustmentSignal):
        """Apply risk multiplier adjustment."""
        old_mult = self.risk_multiplier
        
        # Increase risk if ahead of target with low drawdown
        if signal.profit_to_target < 0.5 and signal.drawdown_level < 0.3:
            self.risk_multiplier = min(1.5, signal.risk_multiplier * (1 + signal.urgency * 0.1))
        # Decrease risk if near drawdown limit
        elif signal.drawdown_level > 0.7:
            self.risk_multiplier = max(0.5, signal.risk_multiplier * (1 - signal.urgency * 0.2))
        else:
            self.risk_multiplier = (self.risk_multiplier * 0.8) + (signal.risk_multiplier * 0.2)
        
        self.risk_multiplier = np.clip(self.risk_multiplier, 0.3, 2.0)
        print(f"  - Risk multiplier: {old_mult:.2f} -> {self.risk_multiplier:.2f}")
    
    def _apply_emergency_stop(self, signal: AdjustmentSignal):
        """Apply emergency stop - stop all trading."""
        print(f"  ⚠️ EMERGENCY STOP: {signal.rule_violations}")
        self.risk_multiplier = 0.0
        self.confidence_bias = 0.5  # Require very high confidence
    
    def _handle_rule_violations(self, violations: List[str]):
        """Handle prop firm rule violations."""
        for violation in violations:
            print(f"  ⚠️ Rule Violation: {violation}")
            
            if 'daily_loss' in violation.lower():
                # Temporarily stop trading for the day
                self.risk_multiplier *= 0.5
            elif 'drawdown' in violation.lower():
                # Reduce position sizes
                self.risk_multiplier *= 0.7
            elif 'position_size' in violation.lower():
                # Cap RL model output
                pass  # Handled in RL model



    
    # =========================================================================
    # INFERENCE
    # =========================================================================
    
    def predict(self, features: torch.Tensor, account_state: Optional[Dict] = None
               ) -> Dict[str, Any]:
        """
        Generate prediction using ensemble of all models.
        
        Args:
            features: Market features (batch, seq, input_features)
            account_state: Current account state for RL sizing
        
        Returns:
            Dictionary with prediction, confidence, and sizing
        """
        self.lstm_model.eval()
        self.transformer_model.eval()
        self.cnn_model.eval()
        self.rl_model.eval()
        
        with torch.no_grad():
            # Get predictions from each model
            lstm_logits, lstm_conf = self.lstm_model(features)
            trans_logits, trans_conf = self.transformer_model(features)
            cnn_logits, cnn_conf = self.cnn_model(features)
            
            # Weighted ensemble
            ensemble_logits = (
                self.ensemble_weights['lstm'] * lstm_logits +
                self.ensemble_weights['transformer'] * trans_logits +
                self.ensemble_weights['cnn'] * cnn_logits
            )
            
            # Get final prediction
            probs = F.softmax(ensemble_logits, dim=-1)
            prediction = torch.argmax(probs, dim=-1).item()  # 0=SHORT, 1=HOLD, 2=LONG
            
            # Weighted confidence
            confidence = (
                self.ensemble_weights['lstm'] * lstm_conf.mean().item() +
                self.ensemble_weights['transformer'] * trans_conf.mean().item() +
                self.ensemble_weights['cnn'] * cnn_conf.mean().item()
            )
            
            # Apply confidence bias
            confidence = confidence + self.confidence_bias
            
            # Get position sizing from RL
            contracts = 0
            rl_confidence = 0.0
            if account_state and prediction != 1:  # Not HOLD
                acct_tensor = self._prepare_account_state(account_state)
                contracts, rl_confidence = self.rl_model.select_contracts(
                    features, acct_tensor, deterministic=True
                )
                # Apply risk multiplier
                contracts = int(contracts * self.risk_multiplier)
                contracts = min(contracts, self.ruleset.max_contracts)
        
        # Map prediction to signal
        signal_map = {0: -1, 1: 0, 2: 1}  # SHORT, HOLD, LONG
        
        return {
            'signal': signal_map[prediction],
            'signal_name': ['SHORT', 'HOLD', 'LONG'][prediction],
            'confidence': float(np.clip(confidence, 0, 1)),
            'contracts': contracts,
            'model_scores': {
                'lstm': float(lstm_conf.mean().item()),
                'transformer': float(trans_conf.mean().item()),
                'cnn': float(cnn_conf.mean().item()),
                'rl': float(rl_confidence)
            },
            'ensemble_weights': self.ensemble_weights.copy(),
            'risk_multiplier': self.risk_multiplier,
            'probs': probs.cpu().numpy().tolist()[0]
        }
    
    def _prepare_account_state(self, account_state: Dict) -> torch.Tensor:
        """Prepare account state tensor for RL model."""
        state = torch.tensor([[
            account_state.get('daily_pnl_pct', 0.0),
            account_state.get('drawdown_pct', 0.0),
            account_state.get('days_remaining_pct', 1.0),
            account_state.get('profit_to_target_pct', 1.0),
            account_state.get('recent_win_rate', 0.5),
            account_state.get('consecutive_losses', 0) / 5,  # Normalize
            account_state.get('time_of_day_pct', 0.5),
            account_state.get('volatility_regime', 0.5)
        ]], dtype=torch.float32, device=DEVICE)
        return state
    
    # =========================================================================
    # TRAINING
    # =========================================================================
    
    def train_on_trades(self, trades: List[TradeRecord], epochs: int = 50):
        """
        Train all models on historical trades.
        
        Args:
            trades: List of trade records
            epochs: Number of training epochs
        """
        if len(trades) < 20:
            print(f"[FUTURES BRAIN] Not enough trades to train ({len(trades)} < 20)")
            return
        
        print(f"[FUTURES BRAIN] Training on {len(trades)} trades for {epochs} epochs...")
        
        # Prepare training data
        X, y, weights = self._prepare_training_data(trades)
        
        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Train each model
        for model, optimizer, name in [
            (self.lstm_model, self.lstm_optimizer, 'LSTM'),
            (self.transformer_model, self.transformer_optimizer, 'Transformer'),
            (self.cnn_model, self.cnn_optimizer, 'CNN')
        ]:
            print(f"  Training {name}...")
            model.train()
            
            best_loss = float('inf')
            patience = 10
            patience_counter = 0
            
            for epoch in range(epochs):
                # Training
                optimizer.zero_grad()
                logits, _ = model(X_train)
                loss = F.cross_entropy(logits, y_train)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                
                # Validation
                model.eval()
                with torch.no_grad():
                    val_logits, _ = model(X_val)
                    val_loss = F.cross_entropy(val_logits, y_val)
                model.train()
                
                if val_loss < best_loss:
                    best_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        print(f"    Early stop at epoch {epoch+1}")
                        break
            
            print(f"    Best val loss: {best_loss:.4f}")
        
        self.total_epochs += epochs
        
        # Train RL model separately with reward shaping
        self._train_rl_model(trades)
        
        # Share updated params to TPT Bot
        self.share_parameters_to_tpt_bot()
    
    def _prepare_training_data(self, trades: List[TradeRecord]
                              ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Prepare training data from trade records."""
        # This is simplified - in production, you'd fetch actual OHLCV data
        # and create proper sequences
        
        n_samples = len(trades)
        X = torch.randn(n_samples, self.config.sequence_length, self.config.input_features, 
                       device=DEVICE)
        
        # Labels: 0=SHORT (loss on LONG), 1=HOLD (small move), 2=LONG (profit on LONG)
        y = []
        weights = []
        for trade in trades:
            if trade.pnl_pct > 0.5:
                y.append(2 if trade.direction == 'LONG' else 0)
            elif trade.pnl_pct < -0.5:
                y.append(0 if trade.direction == 'LONG' else 2)
            else:
                y.append(1)
            
            # Weight by PnL magnitude
            weights.append(1 + abs(trade.pnl_pct) * 0.1)
        
        y = torch.tensor(y, dtype=torch.long, device=DEVICE)
        weights = torch.tensor(weights, dtype=torch.float32, device=DEVICE)
        
        return X, y, weights
    
    def _train_rl_model(self, trades: List[TradeRecord]):
        """Train RL position sizer using PPO-style updates."""
        print("  Training RL Position Sizer...")
        
        # Calculate rewards based on risk-adjusted returns
        for trade in trades[-100:]:
            reward = self._calculate_rl_reward(trade)
            self.rl_model.experience_buffer.append({
                'trade': trade,
                'reward': reward
            })
        
        # PPO update (simplified)
        if len(self.rl_model.experience_buffer) < 20:
            return
        
        self.rl_model.train()
        
        for _ in range(10):  # 10 PPO epochs
            self.rl_optimizer.zero_grad()
            
            # Sample batch
            batch = list(self.rl_model.experience_buffer)[-50:]
            
            # Calculate loss (simplified policy gradient)
            total_loss = 0
            for exp in batch:
                features = torch.randn(1, self.config.sequence_length, 
                                      self.config.input_features, device=DEVICE)
                acct_state = torch.randn(1, 8, device=DEVICE)
                
                action_probs, value, _ = self.rl_model(features, acct_state)
                
                # Policy loss
                contracts_taken = exp['trade'].contracts
                log_prob = torch.log(action_probs[0, contracts_taken] + 1e-8)
                policy_loss = -log_prob * exp['reward']
                
                # Value loss
                value_loss = F.mse_loss(value.squeeze(), torch.tensor([exp['reward']], device=DEVICE))
                
                total_loss += policy_loss + 0.5 * value_loss
            
            total_loss.backward()
            self.rl_optimizer.step()
    
    def _calculate_rl_reward(self, trade: TradeRecord) -> float:
        """
        Calculate reward for RL training with prop firm rules in mind.
        
        Reward shaping:
        - Positive for profitable trades
        - Bonus for staying within drawdown limits
        - Penalty for approaching daily loss limit
        - Bonus for contributing to minimum trading days
        """
        base_reward = trade.pnl_pct * 10  # Scale PnL
        
        # Drawdown bonus/penalty
        if trade.drawdown_after < self.ruleset.trailing_drawdown * 0.5:
            base_reward += 0.2  # Bonus for low drawdown
        elif trade.drawdown_after > self.ruleset.trailing_drawdown * 0.8:
            base_reward -= 0.5  # Penalty for high drawdown
        
        # Daily loss limit awareness
        if trade.daily_pnl_after < -self.ruleset.daily_loss_limit * 0.5:
            base_reward -= 0.3  # Approaching daily limit
        
        # Reward for trading on new days (min trading days rule)
        if trade.trading_day > self.trading_days:
            base_reward += 0.2
        
        return np.clip(base_reward, -3, 3)
    
    def _online_learning_step(self):
        """Perform online learning update based on recent adjustments."""
        if len(self.adjustment_queue) < 3:
            return
        
        recent_adjustments = list(self.adjustment_queue)[-5:]
        
        # Calculate average performance metrics
        avg_win_rate = np.mean([a.recent_win_rate for a in recent_adjustments])
        avg_accuracy = np.mean([a.model_accuracy for a in recent_adjustments])
        
        print(f"[FUTURES BRAIN] Online learning step (avg accuracy: {avg_accuracy:.1%})")
        
        # Adjust learning rates based on performance
        if avg_accuracy < 0.4:
            # Poor performance - increase learning rate for faster adaptation
            for optimizer in [self.lstm_optimizer, self.transformer_optimizer, 
                            self.cnn_optimizer, self.rl_optimizer]:
                for param_group in optimizer.param_groups:
                    param_group['lr'] = min(param_group['lr'] * 1.2, 
                                           self.config.learning_rate * 3)
        elif avg_accuracy > 0.6:
            # Good performance - decrease learning rate for stability
            for optimizer in [self.lstm_optimizer, self.transformer_optimizer,
                            self.cnn_optimizer, self.rl_optimizer]:
                for param_group in optimizer.param_groups:
                    param_group['lr'] = max(param_group['lr'] * 0.9,
                                           self.config.learning_rate * 0.1)



    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _serialize_model(self, model: nn.Module) -> bytes:
        """Serialize model state dict to bytes."""
        buffer = pickle.dumps(model.state_dict())
        return buffer
    
    def _deserialize_model(self, model: nn.Module, data: bytes):
        """Deserialize model state dict from bytes.

        SECURITY WARNING: pickle.loads can execute arbitrary code if data is tampered.
        Only use with trusted data sources (local database, secure storage).
        TODO: Migrate to torch.load(weights_only=True) or safetensors for production.
        """
        state_dict = pickle.loads(data)
        model.load_state_dict(state_dict)
    
    def _compute_position_size_table(self) -> Dict[str, int]:
        """Compute position size table based on confidence levels."""
        table = {}
        for conf_level in [0.5, 0.6, 0.7, 0.8, 0.9]:
            # Scale contracts based on confidence and risk multiplier
            base_contracts = int((conf_level - 0.4) * self.ruleset.max_contracts / 0.5)
            adjusted = int(base_contracts * self.risk_multiplier)
            table[f"{conf_level:.1f}"] = min(adjusted, self.ruleset.max_contracts)
        return table
    
    def _get_regime_configs(self) -> Dict[str, Dict]:
        """Get regime-specific configurations."""
        return {
            'trending': {
                'min_confidence': 0.60 + self.confidence_bias,
                'risk_mult': 1.2 * self.risk_multiplier,
                'preferred_models': ['transformer', 'lstm']
            },
            'ranging': {
                'min_confidence': 0.70 + self.confidence_bias,
                'risk_mult': 0.8 * self.risk_multiplier,
                'preferred_models': ['cnn']
            },
            'volatile': {
                'min_confidence': 0.75 + self.confidence_bias,
                'risk_mult': 0.6 * self.risk_multiplier,
                'preferred_models': ['lstm']
            },
            'quiet': {
                'min_confidence': 0.55 + self.confidence_bias,
                'risk_mult': 1.0 * self.risk_multiplier,
                'preferred_models': ['transformer', 'cnn']
            }
        }
    
    def _get_validation_accuracy(self) -> float:
        """Get current validation accuracy estimate."""
        if not self.adjustment_queue:
            return 0.5
        recent = list(self.adjustment_queue)[-10:]
        return np.mean([a.model_accuracy for a in recent])
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from recent trades."""
        if len(self.trade_history) < 10:
            return 0.0
        
        returns = [t.pnl_pct for t in list(self.trade_history)[-50:]]
        if np.std(returns) == 0:
            return 0.0
        return np.mean(returns) / np.std(returns) * np.sqrt(252)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    def _init_database(self):
        """Initialize SQLite database."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # Trades table
        c.execute('''CREATE TABLE IF NOT EXISTS futures_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE,
            symbol TEXT,
            direction TEXT,
            contracts INTEGER,
            entry_price REAL,
            exit_price REAL,
            entry_time TEXT,
            exit_time TEXT,
            primary_model TEXT,
            model_scores TEXT,
            confidence REAL,
            regime TEXT,
            pnl REAL,
            pnl_pct REAL,
            exit_reason TEXT,
            daily_pnl_after REAL,
            drawdown_after REAL,
            trading_day INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Shared parameters table
        c.execute('''CREATE TABLE IF NOT EXISTS shared_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            param_id TEXT UNIQUE,
            version INTEGER,
            ensemble_weights TEXT,
            confidence_thresholds TEXT,
            position_size_table TEXT,
            stop_loss_mult REAL,
            take_profit_mult REAL,
            regime_configs TEXT,
            training_epochs INTEGER,
            validation_accuracy REAL,
            sharpe_ratio REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Adjustment signals table
        c.execute('''CREATE TABLE IF NOT EXISTS adjustment_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT UNIQUE,
            signal_type TEXT,
            strategy_adjustments TEXT,
            confidence_bias REAL,
            risk_multiplier REAL,
            recent_win_rate REAL,
            recent_pnl REAL,
            drawdown_level REAL,
            model_accuracy REAL,
            rule_violations TEXT,
            urgency REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Brain state table
        c.execute('''CREATE TABLE IF NOT EXISTS brain_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ensemble_weights TEXT,
            confidence_bias REAL,
            risk_multiplier REAL,
            param_version INTEGER,
            total_epochs INTEGER,
            best_validation_loss REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
        print("[FUTURES BRAIN] Database initialized")
    
    def _save_shared_params(self, params: SharedParameters):
        """Save shared parameters to database."""
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO shared_params 
                    (param_id, version, ensemble_weights, confidence_thresholds,
                     position_size_table, stop_loss_mult, take_profit_mult,
                     regime_configs, training_epochs, validation_accuracy, sharpe_ratio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (params.param_id, params.version,
                  json.dumps(params.ensemble_weights),
                  json.dumps(params.confidence_thresholds),
                  json.dumps(params.position_size_table),
                  params.stop_loss_atr_mult, params.take_profit_atr_mult,
                  json.dumps(params.regime_configs),
                  params.training_epochs, params.validation_accuracy, params.sharpe_ratio))
        
        conn.commit()
        conn.close()
    
    def _save_adjustment_signal(self, signal: AdjustmentSignal):
        """Save adjustment signal to database."""
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO adjustment_signals
                    (signal_id, signal_type, strategy_adjustments, confidence_bias,
                     risk_multiplier, recent_win_rate, recent_pnl, drawdown_level,
                     model_accuracy, rule_violations, urgency)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (signal.signal_id, signal.signal_type,
                  json.dumps(signal.strategy_adjustments), signal.confidence_bias,
                  signal.risk_multiplier, signal.recent_win_rate, signal.recent_pnl,
                  signal.drawdown_level, signal.model_accuracy,
                  json.dumps(signal.rule_violations), signal.urgency))
        
        conn.commit()
        conn.close()
    
    def _save_state(self):
        """Save brain state to database."""
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        c.execute('''INSERT INTO brain_state
                    (ensemble_weights, confidence_bias, risk_multiplier,
                     param_version, total_epochs, best_validation_loss)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (json.dumps(self.ensemble_weights), self.confidence_bias,
                  self.risk_multiplier, self.param_version, self.total_epochs,
                  self.best_validation_loss))
        
        conn.commit()
        conn.close()
    
    def _load_state(self):
        """Load brain state from database."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            c = conn.cursor()
            
            c.execute('SELECT * FROM brain_state ORDER BY id DESC LIMIT 1')
            row = c.fetchone()
            
            if row:
                self.ensemble_weights = json.loads(row[1])
                self.confidence_bias = row[2]
                self.risk_multiplier = row[3]
                self.param_version = row[4]
                self.total_epochs = row[5]
                self.best_validation_loss = row[6]
                print(f"[FUTURES BRAIN] Loaded state: v{self.param_version}, {self.total_epochs} epochs")
            
            conn.close()
        except Exception as e:
            print(f"[FUTURES BRAIN] Could not load state: {e}")
    
    def record_trade(self, trade: TradeRecord):
        """Record a completed trade for learning."""
        self.trade_history.append(trade)
        
        # Update tracking
        self.current_daily_pnl += trade.pnl
        if trade.pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Update drawdown
        balance = self.ruleset.account_size + sum(t.pnl for t in self.trade_history)
        if balance > self.peak_balance:
            self.peak_balance = balance
        self.current_drawdown = self.peak_balance - balance
        
        trade.daily_pnl_after = self.current_daily_pnl
        trade.drawdown_after = self.current_drawdown
        
        # Save to database
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO futures_trades
                    (trade_id, symbol, direction, contracts, entry_price, exit_price,
                     entry_time, exit_time, primary_model, model_scores, confidence,
                     regime, pnl, pnl_pct, exit_reason, daily_pnl_after, drawdown_after,
                     trading_day)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (trade.trade_id, trade.symbol, trade.direction, trade.contracts,
                  trade.entry_price, trade.exit_price,
                  trade.entry_time.isoformat() if trade.entry_time else None,
                  trade.exit_time.isoformat() if trade.exit_time else None,
                  trade.primary_model, json.dumps(trade.model_scores), trade.confidence,
                  trade.regime, trade.pnl, trade.pnl_pct, trade.exit_reason,
                  trade.daily_pnl_after, trade.drawdown_after, trade.trading_day))
        
        conn.commit()
        conn.close()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current brain status."""
        return {
            'firm_type': self.ruleset.firm_type.value,
            'param_version': self.param_version,
            'total_epochs': self.total_epochs,
            'ensemble_weights': self.ensemble_weights,
            'confidence_bias': self.confidence_bias,
            'risk_multiplier': self.risk_multiplier,
            'trades_recorded': len(self.trade_history),
            'pending_adjustments': len(self.adjustment_queue),
            'current_daily_pnl': self.current_daily_pnl,
            'current_drawdown': self.current_drawdown,
            'consecutive_losses': self.consecutive_losses
        }




# =============================================================================
# TPT BOT INTERFACE (Feedback Loop Partner)
# =============================================================================

class TPTBotInterface:
    """
    Interface for TPT Bot to communicate with FuturesPropFirmBrain.
    
    This class handles:
    1. Receiving shared parameters from the brain
    2. Sending adjustment signals back
    3. Monitoring trade performance
    4. Validating against prop firm rules
    """
    
    def __init__(self, brain: FuturesPropFirmBrain):
        """
        Initialize TPT Bot Interface.
        
        Args:
            brain: FuturesPropFirmBrain instance to communicate with
        """
        self.brain = brain
        self.ruleset = brain.ruleset
        
        # Current parameters from brain
        self.current_params: Optional[SharedParameters] = None
        
        # Performance tracking
        self.session_trades: List[TradeRecord] = []
        self.session_pnl: float = 0.0
        self.session_start: datetime = datetime.now()
        
        # Register callback to receive params
        self.brain.register_tpt_bot_callback(self._on_params_received)
        
        print("[TPT BOT] Interface initialized")
    
    def _on_params_received(self, params: SharedParameters):
        """Callback when brain shares new parameters."""
        self.current_params = params
        print(f"[TPT BOT] Received params v{params.version}")
        print(f"  - Ensemble: {params.ensemble_weights}")
        print(f"  - Validation accuracy: {params.validation_accuracy:.1%}")
    
    def record_trade_result(self, trade: TradeRecord):
        """
        Record a trade result and potentially send feedback.
        
        Args:
            trade: Completed trade record
        """
        self.session_trades.append(trade)
        self.session_pnl += trade.pnl
        
        # Record in brain as well
        self.brain.record_trade(trade)
        
        # Check for rule violations
        violations = self._check_rule_violations(trade)
        
        # Determine if adjustment needed
        if self._should_send_adjustment():
            self._send_adjustment_signal(violations)
    
    def _check_rule_violations(self, trade: TradeRecord) -> List[str]:
        """Check for prop firm rule violations."""
        violations = []
        
        # Daily loss limit
        if self.brain.current_daily_pnl <= -self.ruleset.daily_loss_limit:
            violations.append(f"daily_loss_exceeded: ${self.brain.current_daily_pnl:.2f}")
        elif self.brain.current_daily_pnl <= -self.ruleset.daily_loss_limit * 0.8:
            violations.append(f"daily_loss_warning: ${self.brain.current_daily_pnl:.2f}")
        
        # Trailing drawdown
        if self.brain.current_drawdown >= self.ruleset.trailing_drawdown:
            violations.append(f"drawdown_exceeded: ${self.brain.current_drawdown:.2f}")
        elif self.brain.current_drawdown >= self.ruleset.trailing_drawdown * 0.8:
            violations.append(f"drawdown_warning: ${self.brain.current_drawdown:.2f}")
        
        # Position size
        if trade.contracts > self.ruleset.max_contracts:
            violations.append(f"position_size_exceeded: {trade.contracts} > {self.ruleset.max_contracts}")
        
        # Consecutive losses
        if self.brain.consecutive_losses >= 3:
            violations.append(f"consecutive_losses: {self.brain.consecutive_losses}")
        
        return violations
    
    def _should_send_adjustment(self) -> bool:
        """Determine if an adjustment signal should be sent."""
        # Send after every 5 trades
        if len(self.session_trades) % 5 == 0:
            return True
        
        # Send if recent performance is poor
        recent = self.session_trades[-10:]
        if len(recent) >= 5:
            recent_wins = sum(1 for t in recent if t.pnl > 0)
            if recent_wins / len(recent) < 0.3:
                return True
        
        # Send if approaching limits
        if self.brain.current_drawdown > self.ruleset.trailing_drawdown * 0.6:
            return True
        
        return False
    
    def _send_adjustment_signal(self, violations: List[str]):
        """Send adjustment signal to brain."""
        recent = self.session_trades[-20:] if len(self.session_trades) >= 5 else self.session_trades
        
        # Calculate metrics
        wins = [t for t in recent if t.pnl > 0]
        win_rate = len(wins) / len(recent) if recent else 0.5
        recent_pnl = sum(t.pnl for t in recent)
        
        # Calculate model accuracy
        correct_predictions = sum(1 for t in recent 
                                 if (t.pnl > 0 and t.confidence > 0.6) or 
                                    (t.pnl < 0 and t.confidence < 0.4))
        model_accuracy = correct_predictions / len(recent) if recent else 0.5
        
        # Calculate false positive/negative rates
        high_conf_trades = [t for t in recent if t.confidence > 0.7]
        false_positives = sum(1 for t in high_conf_trades if t.pnl < 0)
        fp_rate = false_positives / len(high_conf_trades) if high_conf_trades else 0
        
        low_conf_trades = [t for t in recent if t.confidence < 0.5]
        false_negatives = sum(1 for t in low_conf_trades if t.pnl > 100)
        fn_rate = false_negatives / len(low_conf_trades) if low_conf_trades else 0
        
        # Determine signal type
        if violations:
            signal_type = 'risk_adjustment'
        elif fp_rate > 0.3 or fn_rate > 0.3:
            signal_type = 'confidence_calibration'
        else:
            signal_type = 'weight_adjustment'
        
        # Calculate urgency
        urgency = 0.0
        if self.brain.current_drawdown > self.ruleset.trailing_drawdown * 0.5:
            urgency += 0.3
        if win_rate < 0.4:
            urgency += 0.2
        if len(violations) > 0:
            urgency += 0.3
        urgency = min(1.0, urgency)
        
        # Calculate strategy adjustments
        strategy_adjustments = {}
        for model in ['lstm', 'transformer', 'cnn', 'rl']:
            model_trades = [t for t in recent if t.primary_model == model]
            if model_trades:
                model_win_rate = sum(1 for t in model_trades if t.pnl > 0) / len(model_trades)
                # Positive adjustment if model performing well
                strategy_adjustments[model] = (model_win_rate - 0.5) * 2
        
        # Profit to target
        total_pnl = sum(t.pnl for t in self.brain.trade_history)
        profit_to_target = max(0, (self.ruleset.profit_target - total_pnl) / self.ruleset.profit_target)
        
        # Create signal
        signal = AdjustmentSignal(
            signal_id=f"adj_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            signal_type=signal_type,
            strategy_adjustments=strategy_adjustments,
            confidence_bias=0.05 if fp_rate > 0.3 else -0.03 if fn_rate > 0.3 else 0.0,
            risk_multiplier=0.7 if urgency > 0.5 else 1.0,
            recent_win_rate=win_rate,
            recent_pnl=recent_pnl,
            drawdown_level=self.brain.current_drawdown / self.ruleset.trailing_drawdown,
            trading_days_remaining=self.ruleset.min_trading_days - self.brain.trading_days,
            profit_to_target=profit_to_target,
            model_accuracy=model_accuracy,
            false_positive_rate=fp_rate,
            false_negative_rate=fn_rate,
            rule_violations=violations,
            urgency=urgency
        )
        
        # Send to brain
        self.brain.receive_adjustment_from_tpt_bot(signal)
    
    def request_params_update(self):
        """Request updated parameters from brain."""
        return self.brain.share_parameters_to_tpt_bot()
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current trading configuration."""
        if not self.current_params:
            return {}
        
        return {
            'ensemble_weights': self.current_params.ensemble_weights,
            'confidence_thresholds': self.current_params.confidence_thresholds,
            'position_size_table': self.current_params.position_size_table,
            'stop_loss_mult': self.current_params.stop_loss_atr_mult,
            'take_profit_mult': self.current_params.take_profit_atr_mult
        }
    
    def should_trade(self, confidence: float, regime: str) -> bool:
        """
        Check if trade should be taken based on current config.
        
        Args:
            confidence: Model confidence
            regime: Current market regime
        
        Returns:
            True if trade should be taken
        """
        if not self.current_params:
            return confidence > 0.6
        
        threshold = self.current_params.confidence_thresholds.get(regime, 0.65)
        return confidence >= threshold
    
    def get_position_size(self, confidence: float) -> int:
        """
        Get recommended position size based on confidence.
        
        Args:
            confidence: Model confidence
        
        Returns:
            Number of contracts
        """
        if not self.current_params:
            return 1
        
        # Find appropriate tier
        for conf_str, contracts in sorted(self.current_params.position_size_table.items(), 
                                         reverse=True):
            if confidence >= float(conf_str):
                return contracts
        return 1


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def example_usage():
    """Example of how to use the FuturesPropFirmBrain with TPT Bot feedback loop."""
    
    print("=" * 70)
    print("FUTURES PROP FIRM BRAIN - FEEDBACK LOOP EXAMPLE")
    print("=" * 70)
    
    # Initialize brain with TPT 50K ruleset
    brain = FuturesPropFirmBrain(PropFirmRuleset.get_tpt_50k())
    
    # Initialize TPT Bot interface (connects to brain)
    tpt_bot = TPTBotInterface(brain)
    
    # Initial parameter share
    params = brain.share_parameters_to_tpt_bot()
    print(f"\nInitial params shared: v{params.version}")
    
    # Simulate some trades
    print("\n--- Simulating Trades ---")
    
    for i in range(10):
        # TPT Bot gets prediction from brain
        features = torch.randn(1, 60, 72, device=DEVICE)
        account_state = {
            'daily_pnl_pct': brain.current_daily_pnl / brain.ruleset.daily_loss_limit,
            'drawdown_pct': brain.current_drawdown / brain.ruleset.trailing_drawdown,
            'days_remaining_pct': 0.8,
            'profit_to_target_pct': 0.7,
            'recent_win_rate': 0.5,
            'consecutive_losses': brain.consecutive_losses,
            'time_of_day_pct': 0.5,
            'volatility_regime': 0.5
        }
        
        prediction = brain.predict(features, account_state)
        print(f"\nTrade {i+1}: Signal={prediction['signal_name']}, "
              f"Conf={prediction['confidence']:.2f}, Contracts={prediction['contracts']}")
        
        # Check if we should trade
        if prediction['signal'] != 0 and tpt_bot.should_trade(prediction['confidence'], 'trending'):
            # Simulate trade result
            pnl = np.random.normal(50, 200)  # Random PnL
            
            trade = TradeRecord(
                trade_id=f"trade_{i}",
                symbol="MNQ",
                direction="LONG" if prediction['signal'] == 1 else "SHORT",
                contracts=prediction['contracts'],
                entry_price=20000 + np.random.uniform(-100, 100),
                exit_price=20000 + np.random.uniform(-100, 100) + pnl/2,
                entry_time=datetime.now(),
                exit_time=datetime.now(),
                primary_model=max(prediction['model_scores'], key=prediction['model_scores'].get),
                model_scores=prediction['model_scores'],
                confidence=prediction['confidence'],
                regime='trending',
                pnl=pnl,
                pnl_pct=pnl/1000,
                exit_reason='TP_HIT' if pnl > 0 else 'SL_HIT',
                is_closed=True
            )
            
            # Record in TPT Bot (will auto-send feedback to brain)
            tpt_bot.record_trade_result(trade)
            print(f"  Result: ${pnl:.2f} | Daily: ${brain.current_daily_pnl:.2f} | "
                  f"DD: ${brain.current_drawdown:.2f}")
    
    # Final status
    print("\n--- Final Status ---")
    status = brain.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n[DONE] Feedback loop demonstration complete")


if __name__ == "__main__":
    example_usage()


# =============================================================================
# INTEGRATION WITH EVOLUTION ENGINE
# =============================================================================

# Import at module level (with fallback)
try:
    from brain.futures_evolution_engine import (
        FuturesEvolutionSystem,
        CrossBrainKnowledgeTransfer,
        FuturesTradeAnalysis,
        create_futures_evolution_system,
        get_knowledge_from_stock_brain
    )
    HAS_EVOLUTION = True
except ImportError:
    HAS_EVOLUTION = False
    print("[!] futures_evolution_engine not found - evolution disabled")


class EnhancedFuturesPropFirmBrain(FuturesPropFirmBrain):
    """
    Enhanced Futures Brain with:
    1. Cross-Brain Knowledge Transfer (get strategies from stock ML brain)
    2. Intensive Testing (evolution engine + ML predictor)
    3. Bidirectional learning
    """
    
    def __init__(self, ruleset: Optional[PropFirmRuleset] = None):
        """Initialize enhanced brain with evolution system."""
        super().__init__(ruleset)
        
        # Evolution system (includes cross-brain transfer)
        if HAS_EVOLUTION:
            ruleset_type = 'tpt_50k'  # Default
            if self.ruleset:
                ruleset_type = self.ruleset.firm_type.value
            
            self.evolution_system = create_futures_evolution_system(ruleset_type)
            self.cross_brain = CrossBrainKnowledgeTransfer()
            print(f"[ENHANCED BRAIN] Evolution system initialized")
            print(f"[ENHANCED BRAIN] Stock brain knowledge loaded: {len(self.cross_brain.stock_indicator_weights)} indicators")
        else:
            self.evolution_system = None
            self.cross_brain = None
    
    def get_enhanced_signal(self, features: torch.Tensor, indicators: Dict,
                           market_internals: Dict = None, symbol: str = 'MNQ',
                           session: str = 'RTH') -> Dict:
        """
        Get trading signal using BOTH neural models AND evolution knowledge.
        
        This combines:
        - Neural network predictions (LSTM, Transformer, CNN)
        - Evolved strategy parameters
        - ML predictor confidence
        - Stock brain knowledge
        """
        # Base neural signal
        base_signal = self.generate_signal(features)
        
        # Evolution-enhanced signal
        if self.evolution_system and HAS_EVOLUTION:
            evo_signal = self.evolution_system.get_enhanced_signal(
                indicators, market_internals or {}, symbol, session
            )
            
            # Blend signals (60% neural, 40% evolution)
            blended_confidence = (
                0.6 * base_signal['confidence'] + 
                0.4 * evo_signal['confidence']
            )
            
            # Use evolved thresholds
            strategy = evo_signal.get('strategy_params', {})
            min_conf = strategy.get('min_confidence', 0.6)
            
            return {
                'should_trade': blended_confidence >= min_conf,
                'confidence': blended_confidence,
                'neural_confidence': base_signal['confidence'],
                'evolution_confidence': evo_signal['confidence'],
                'ml_prediction': evo_signal.get('ml_prediction', 0.5),
                'composite_score': evo_signal['composite_score'],
                'direction': base_signal['direction'],
                'contracts': base_signal['contracts'],
                'stop_loss_mult': strategy.get('sl_atr_mult', 1.5),
                'take_profit_mult': strategy.get('tp_atr_mult', 2.5),
                'indicator_weights': evo_signal.get('indicator_weights', {}),
            }
        else:
            return base_signal
    
    def record_trade_for_evolution(self, trade_data: Dict, indicators: Dict,
                                  market_internals: Dict = None):
        """Record trade for evolution learning."""
        if self.evolution_system and HAS_EVOLUTION:
            self.evolution_system.record_trade(trade_data, indicators, market_internals)
    
    def run_intensive_analysis(self) -> Dict:
        """
        Run full intensive analysis (like stock ML brain).
        Call this after each trading session.
        """
        if self.evolution_system and HAS_EVOLUTION:
            return self.evolution_system.run_full_analysis()
        else:
            return {'error': 'Evolution system not available'}
    
    def get_stock_brain_knowledge(self) -> Dict:
        """Get knowledge pulled from stock ML brain."""
        if self.cross_brain:
            return {
                'indicator_weights': self.cross_brain.get_adapted_indicator_weights(),
                'strategy_params': self.cross_brain.get_adapted_strategy_params(),
            }
        return {}
    
    def sync_with_stock_brain(self):
        """Sync bidirectional knowledge with stock brain."""
        if self.cross_brain:
            self.cross_brain.sync_knowledge()
            print("[ENHANCED BRAIN] Synced with stock brain")
    
    def load_from_reinforcement_loop(self, symbol: str = 'MNQ') -> bool:
        """
        Load trained parameters from Futures Reinforcement Loop.
        
        This integrates the intensive training results into the neural models.
        
        Args:
            symbol: The symbol used in RL training (e.g., 'MNQ')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to load export file
            export_path = ROOT / "weights" / "futures_rl" / f"{symbol}_export_to_brain.json"
            
            if not export_path.exists():
                print(f"[BRAIN] No RL export found at {export_path}")
                print("[BRAIN] Run: python -m brain.futures_reinforcement_loop")
                return False
            
            with open(export_path, 'r') as f:
                export_data = json.load(f)
            
            # Extract learned weights
            strategy_weights = export_data.get('strategy_weights', {})
            strategy_states = export_data.get('strategy_states', {})
            best_metrics = export_data.get('best_metrics', {})
            
            print(f"[BRAIN] Loading RL training results:")
            print(f"  Export time: {export_data.get('export_time', 'unknown')}")
            print(f"  Best WR: {best_metrics.get('win_rate', 0):.1%}")
            print(f"  Best PF: {best_metrics.get('profit_factor', 0):.2f}")
            print(f"  Best Sharpe: {best_metrics.get('sharpe', 0):.2f}")
            
            # Update ensemble weights based on RL training
            if strategy_weights and hasattr(self, 'models'):
                # Map RL strategy weights to neural model ensemble
                model_weight_map = {
                    'MOMENTUM_BREAKOUT': 'lstm',
                    'TREND_FOLLOWING': 'lstm',
                    'MEAN_REVERSION': 'cnn',
                    'VWAP_BOUNCE': 'transformer',
                    'ORB': 'transformer',
                    'TRAPPED_TRADERS': 'cnn',
                    'SMC_ORDER_BLOCKS': 'lstm',
                    'SMC_FVG': 'transformer',
                    'SUPERTREND': 'lstm',
                    'DELTA_DIVERGENCE': 'cnn',
                }
                
                # Calculate neural model weights from strategy weights
                model_contributions = {'lstm': 0, 'transformer': 0, 'cnn': 0}
                for strat, weight in strategy_weights.items():
                    model_type = model_weight_map.get(strat, 'lstm')
                    model_contributions[model_type] += weight
                
                # Normalize
                total = sum(model_contributions.values()) or 1
                for model in model_contributions:
                    model_contributions[model] /= total
                
                # Update ensemble weights
                if hasattr(self, 'ensemble_weights'):
                    self.ensemble_weights = model_contributions
                    print(f"[BRAIN] Updated ensemble weights: {model_contributions}")
            
            # Update confidence thresholds from successful strategies
            if strategy_states:
                high_performing = [
                    (name, state) for name, state in strategy_states.items()
                    if state.get('trades', 0) > 10 and 
                    state.get('wins', 0) / max(state.get('trades', 1), 1) > 0.6
                ]
                
                if high_performing:
                    print(f"[BRAIN] High-performing strategies:")
                    for name, state in high_performing:
                        wr = state.get('wins', 0) / max(state.get('trades', 1), 1)
                        print(f"    {name}: {wr:.1%} WR over {state.get('trades', 0)} trades")
            
            print("[BRAIN] RL training integrated successfully!")
            return True
            
        except Exception as e:
            print(f"[BRAIN] Error loading RL results: {e}")
            return False
    
    def get_rl_loop_interface(self):
        """
        Get interface to Futures Reinforcement Loop for live trading integration.
        
        Returns:
            TPTBotInterface instance connected to the RL loop
        """
        try:
            from .futures_reinforcement_loop import FuturesReinforcementLoop, TPTBotInterface
            
            # Create or get existing loop
            loop = FuturesReinforcementLoop(
                symbol='MNQ',
                prop_firm='tpt_50k',
                seed_from_stock=True
            )
            
            interface = TPTBotInterface(loop)
            print("[BRAIN] Connected to RL Loop")
            return interface
            
        except Exception as e:
            print(f"[BRAIN] Could not connect to RL Loop: {e}")
            return None
    
    # =========================================================================
    # INTEGRATED INTENSIVE TRAINING (from RL Loop)
    # =========================================================================
    
    def run_intensive_training(
        self,
        symbol: str = 'MNQ',
        epochs: int = 100,
        data: 'pd.DataFrame' = None,
        verbose: bool = True
    ) -> Dict:
        """
        Run intensive training directly in the brain.
        
        This integrates the Reinforcement Loop methodology:
        1. Seeds from stock ML Brain
        2. Runs backtests with prop firm rules
        3. Learns from each trade via Adam optimizer
        4. Validates against targets
        5. Updates neural model weights
        
        Args:
            symbol: Futures symbol (MNQ, MES, etc.)
            epochs: Number of training epochs
            data: Optional historical data (generates synthetic if None)
            verbose: Print progress
            
        Returns:
            Dict with training results and metrics
        """
        import numpy as np
        from collections import deque
        import time
        
        print("\n" + "=" * 60)
        print("  FUTURES BRAIN INTENSIVE TRAINING")
        print("=" * 60)
        
        # Initialize training state
        strategy_names = [
            'MOMENTUM_BREAKOUT', 'MEAN_REVERSION', 'VWAP_BOUNCE',
            'ORB', 'TRAPPED_TRADERS', 'TREND_FOLLOWING',
            'SMC_ORDER_BLOCKS', 'SMC_FVG', 'SUPERTREND', 'DELTA_DIVERGENCE'
        ]
        n_strategies = len(strategy_names)
        
        # Strategy weights (seed from stock brain if available)
        weights = np.ones(n_strategies) / n_strategies
        if self.cross_brain:
            adapted = self.cross_brain.get_adapted_indicator_weights()
            for i, name in enumerate(strategy_names):
                for ind, w in adapted.items():
                    if ind.lower() in name.lower() or name.lower() in ind.lower():
                        weights[i] = w * 1.2
            weights = weights / np.sum(weights)
            print(f"[TRAIN] Seeded weights from stock brain")
        
        # Adam optimizer state
        m = np.zeros(n_strategies)  # First moment
        v = np.zeros(n_strategies)  # Second moment
        t = 0
        lr = 0.015
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        
        # Generate synthetic data if not provided
        if data is None:
            print(f"[TRAIN] Generating synthetic {symbol} data...")
            data = self._generate_training_data(5000)
        
        # Add indicators to data
        data = self._add_training_indicators(data)
        
        # Training metrics
        best_sharpe = -np.inf
        best_weights = weights.copy()
        training_history = []
        no_improvement = 0
        
        # Per-strategy stats
        strategy_stats = {name: {'trades': 0, 'wins': 0, 'pnl': 0.0, 'returns': deque(maxlen=50)}
                        for name in strategy_names}
        
        print(f"[TRAIN] Starting {epochs} epochs...")
        
        for epoch in range(epochs):
            epoch_start = time.time()
            
            # Run backtest epoch
            trades, metrics = self._run_backtest_epoch(data, weights, strategy_names)
            
            # Learn from trades
            for trade in trades:
                # Compute gradient
                gradient = np.zeros(n_strategies)
                reward = 1.0 + (trade['pnl_pct'] * 10) if trade['win'] else -1.0 - (abs(trade['pnl_pct']) * 10)
                
                total_score = sum(trade.get('strategy_scores', {}).values()) + 1e-8
                for i, name in enumerate(strategy_names):
                    if name in trade.get('strategy_scores', {}):
                        contribution = trade['strategy_scores'][name] / total_score
                        gradient[i] = reward * contribution
                
                # Regularization
                gradient += -0.01 * (weights - 1/n_strategies)
                
                # Adam update
                t += 1
                m = beta1 * m + (1 - beta1) * gradient
                v = beta2 * v + (1 - beta2) * (gradient ** 2)
                m_hat = m / (1 - beta1 ** t)
                v_hat = v / (1 - beta2 ** t)
                weights += lr * m_hat / (np.sqrt(v_hat) + eps)
                weights = np.clip(weights, 0.01, 0.35)
                weights = weights / np.sum(weights)
                
                # Update strategy stats
                primary = trade.get('primary_strategy', strategy_names[0])
                if primary in strategy_stats:
                    strategy_stats[primary]['trades'] += 1
                    strategy_stats[primary]['pnl'] += trade['pnl_pct']
                    if trade['win']:
                        strategy_stats[primary]['wins'] += 1
                    strategy_stats[primary]['returns'].append(trade['pnl_pct'])
            
            # Decay learning rate
            lr = max(0.002, lr * 0.993)
            
            # Check if best
            if metrics['sharpe'] > best_sharpe:
                best_sharpe = metrics['sharpe']
                best_weights = weights.copy()
                no_improvement = 0
            else:
                no_improvement += 1
            
            # Record history
            training_history.append(metrics)
            
            # Verbose output
            if verbose and (epoch + 1) % 10 == 0:
                elapsed = time.time() - epoch_start
                print(f"  Epoch {epoch+1}/{epochs} | "
                      f"Trades: {metrics['total_trades']} | "
                      f"WR: {metrics['win_rate']:.1%} | "
                      f"PF: {metrics['profit_factor']:.2f} | "
                      f"Sharpe: {metrics['sharpe']:.2f} | "
                      f"Time: {elapsed:.1f}s")
            
            # Early stopping
            if no_improvement >= 15:
                print(f"[TRAIN] Early stop at epoch {epoch+1}")
                break
        
        # Restore best weights
        weights = best_weights
        
        # Update brain's ensemble weights
        self._update_ensemble_from_training(weights, strategy_names, strategy_stats)
        
        # Final metrics
        final_metrics = training_history[-1] if training_history else {}
        
        print("\n" + "=" * 60)
        print("  TRAINING COMPLETE")
        print("=" * 60)
        print(f"  Best Sharpe: {best_sharpe:.2f}")
        print(f"  Final Win Rate: {final_metrics.get('win_rate', 0):.1%}")
        print(f"  Final Profit Factor: {final_metrics.get('profit_factor', 0):.2f}")
        print("\n  Learned Strategy Weights:")
        for i, name in enumerate(strategy_names):
            bar = "#" * int(weights[i] * 40)
            print(f"    {name:20s} {weights[i]:.3f} {bar}")
        
        return {
            'best_sharpe': best_sharpe,
            'final_metrics': final_metrics,
            'strategy_weights': dict(zip(strategy_names, weights)),
            'strategy_stats': {k: dict(v) for k, v in strategy_stats.items()},
            'epochs_trained': len(training_history),
        }
    
    def _generate_training_data(self, n_bars: int) -> 'pd.DataFrame':
        """Generate synthetic futures price data."""
        import pandas as pd
        import numpy as np
        np.random.seed(42)
        
        price = 15000.0
        prices = []
        
        for _ in range(n_bars):
            change = np.random.normal(0.0001, 0.002) * price
            price += change
            
            bar_range = abs(np.random.normal(0, 0.001) * price)
            open_p = price + np.random.uniform(-bar_range, bar_range) * 0.3
            close_p = price
            high_p = max(open_p, close_p) + bar_range * np.random.uniform(0.2, 1.0)
            low_p = min(open_p, close_p) - bar_range * np.random.uniform(0.2, 1.0)
            volume = np.random.randint(100, 10000)
            
            prices.append({'open': open_p, 'high': high_p, 'low': low_p, 
                          'close': close_p, 'volume': volume})
        
        df = pd.DataFrame(prices)
        df.index = pd.date_range(start='2024-01-01', periods=n_bars, freq='1min')
        return df
    
    def _add_training_indicators(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """Add technical indicators for training."""
        import numpy as np
        
        # EMAs
        df['ema5'] = df['close'].ewm(span=5).mean()
        df['ema13'] = df['close'].ewm(span=13).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, 1e-10)))
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        import pandas as pd
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
        # VWAP
        df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
        
        # Supertrend bands
        mult = 2.0
        df['upper_band'] = (df['high'] + df['low']) / 2 + mult * df['atr']
        df['lower_band'] = (df['high'] + df['low']) / 2 - mult * df['atr']
        
        return df
    
    def _run_backtest_epoch(self, data: 'pd.DataFrame', weights: 'np.ndarray', 
                            strategy_names: list) -> Tuple[list, Dict]:
        """Run single backtest epoch."""
        import numpy as np
        
        tick_size = 0.25
        tick_value = 0.50
        account = 50000.0
        daily_loss_limit = 1100.0
        max_dd = 2000.0
        
        trades = []
        position = None
        daily_pnl = 0.0
        high_water = account
        
        for i in range(50, len(data)):
            row = data.iloc[i]
            
            # Check prop firm rules
            if daily_pnl <= -daily_loss_limit * 0.9:
                if position:
                    self._close_backtest_position(position, i, data, trades, account, 'RULE')
                    position = None
                continue
            
            # Check position
            if position:
                if position['direction'] == 'LONG':
                    if row['low'] <= position['sl']:
                        self._close_backtest_position(position, i, data, trades, account, 'SL', position['sl'])
                        position = None
                        continue
                    if row['high'] >= position['tp']:
                        self._close_backtest_position(position, i, data, trades, account, 'TP', position['tp'])
                        position = None
                        continue
                else:
                    if row['high'] >= position['sl']:
                        self._close_backtest_position(position, i, data, trades, account, 'SL', position['sl'])
                        position = None
                        continue
                    if row['low'] <= position['tp']:
                        self._close_backtest_position(position, i, data, trades, account, 'TP', position['tp'])
                        position = None
                        continue
            
            # No position - look for entry
            if position is None:
                signal = self._generate_backtest_signal(data.iloc[max(0,i-50):i+1], weights, strategy_names)
                
                if signal and signal.get('confidence', 0) >= 0.25:  # Match signal threshold
                    direction = signal['direction']
                    entry = row['close']
                    sl_ticks, tp_ticks = 8, 16
                    
                    if direction == 'LONG':
                        sl = entry - (sl_ticks * tick_size)
                        tp = entry + (tp_ticks * tick_size)
                    else:
                        sl = entry + (sl_ticks * tick_size)
                        tp = entry - (tp_ticks * tick_size)
                    
                    position = {
                        'direction': direction, 'entry': entry, 'entry_idx': i,
                        'sl': sl, 'tp': tp, 'strategy_scores': signal.get('strategy_scores', {}),
                        'primary_strategy': signal.get('primary_strategy', 'unknown'),
                        'confidence': signal.get('confidence', 0.5)
                    }
        
        # Close remaining position
        if position:
            self._close_backtest_position(position, len(data)-1, data, trades, account, 'END')
        
        # Calculate metrics
        wins = [t for t in trades if t['win']]
        losses = [t for t in trades if not t['win']]
        
        win_rate = len(wins) / len(trades) if trades else 0
        
        total_win = sum(t['pnl_pct'] for t in wins)
        total_loss = abs(sum(t['pnl_pct'] for t in losses))
        profit_factor = total_win / total_loss if total_loss > 0 else 0
        
        returns = [t['pnl_pct'] for t in trades]
        sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252 * 5) if returns else 0
        
        return trades, {
            'total_trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe': sharpe,
            'total_pnl': sum(returns)
        }
    
    def _close_backtest_position(self, position, exit_idx, data, trades, account, reason, exit_price=None):
        """Close backtest position and record trade."""
        if exit_price is None:
            exit_price = data.iloc[exit_idx]['close']
        
        tick_size, tick_value = 0.25, 0.50
        
        if position['direction'] == 'LONG':
            pnl_ticks = (exit_price - position['entry']) / tick_size
        else:
            pnl_ticks = (position['entry'] - exit_price) / tick_size
        
        pnl_dollars = pnl_ticks * tick_value
        pnl_pct = pnl_dollars / account
        
        trades.append({
            'entry': position['entry'],
            'exit': exit_price,
            'direction': position['direction'],
            'pnl_ticks': pnl_ticks,
            'pnl_dollars': pnl_dollars,
            'pnl_pct': pnl_pct,
            'win': pnl_ticks > 0.5,
            'exit_reason': reason,
            'strategy_scores': position.get('strategy_scores', {}),
            'primary_strategy': position.get('primary_strategy', 'unknown'),
            'confidence': position.get('confidence', 0.5)
        })
    
    def _generate_backtest_signal(self, data, weights, strategy_names):
        """Generate signal for backtesting."""
        import numpy as np
        
        if len(data) < 30:
            return None
        
        row = data.iloc[-1]
        prev_row = data.iloc[-2] if len(data) > 1 else row
        signals = {}
        scores = {}
        
        # More lenient strategies for synthetic data
        if 'ema5' in data.columns and 'ema13' in data.columns:
            ema5, ema13 = row['ema5'], row['ema13']
            prev_ema5 = prev_row['ema5']
            if not np.isnan(ema5) and not np.isnan(ema13):
                # Trend direction based on EMA relationship
                if ema5 > ema13:
                    signals['TREND_FOLLOWING'] = 'LONG'
                    scores['TREND_FOLLOWING'] = 0.6
                    # Add momentum if close is moving in trend direction
                    if row['close'] > prev_row['close']:
                        signals['MOMENTUM_BREAKOUT'] = 'LONG'
                        scores['MOMENTUM_BREAKOUT'] = 0.65
                else:
                    signals['TREND_FOLLOWING'] = 'SHORT'
                    scores['TREND_FOLLOWING'] = 0.6
                    if row['close'] < prev_row['close']:
                        signals['MOMENTUM_BREAKOUT'] = 'SHORT'
                        scores['MOMENTUM_BREAKOUT'] = 0.65
        
        if 'rsi' in data.columns:
            rsi = row['rsi']
            if not np.isnan(rsi):
                if rsi < 40:  # More lenient
                    signals['MEAN_REVERSION'] = 'LONG'
                    scores['MEAN_REVERSION'] = 0.55 + (40 - rsi) / 100
                elif rsi > 60:
                    signals['MEAN_REVERSION'] = 'SHORT'
                    scores['MEAN_REVERSION'] = 0.55 + (rsi - 60) / 100
        
        if 'vwap' in data.columns:
            vwap = row['vwap']
            if not np.isnan(vwap) and vwap > 0:
                dist = (row['close'] - vwap) / vwap
                if dist < -0.001:  # Below VWAP
                    signals['VWAP_BOUNCE'] = 'LONG'
                    scores['VWAP_BOUNCE'] = 0.55
                elif dist > 0.001:  # Above VWAP
                    signals['VWAP_BOUNCE'] = 'SHORT'
                    scores['VWAP_BOUNCE'] = 0.55
        
        # Supertrend signals
        if 'atr' in data.columns and not np.isnan(row['atr']):
            mid = (row['high'] + row['low']) / 2
            upper = mid + 1.5 * row['atr']
            lower = mid - 1.5 * row['atr']
            if row['close'] > upper:
                signals['SUPERTREND'] = 'LONG'
                scores['SUPERTREND'] = 0.55
            elif row['close'] < lower:
                signals['SUPERTREND'] = 'SHORT'
                scores['SUPERTREND'] = 0.55
        
        if not signals:
            return None
        
        # Weighted vote
        weighted_scores = {'LONG': 0.0, 'SHORT': 0.0}
        
        for strat, direction in signals.items():
            try:
                idx = strategy_names.index(strat)
                weight = float(weights[idx])
            except (ValueError, IndexError):
                weight = 0.1
            score = scores.get(strat, 0.5)
            weighted_scores[direction] += weight * score
        
        # Return signal if above threshold
        threshold = 0.25  # Lower threshold
        if weighted_scores['LONG'] > weighted_scores['SHORT'] and weighted_scores['LONG'] > threshold:
            return {
                'direction': 'LONG',
                'confidence': float(weighted_scores['LONG']),
                'strategy_scores': {k: float(v) for k, v in scores.items()},
                'primary_strategy': max(scores, key=scores.get)
            }
        elif weighted_scores['SHORT'] > weighted_scores['LONG'] and weighted_scores['SHORT'] > threshold:
            return {
                'direction': 'SHORT',
                'confidence': float(weighted_scores['SHORT']),
                'strategy_scores': {k: float(v) for k, v in scores.items()},
                'primary_strategy': max(scores, key=scores.get)
            }
        
        return None
    
    def _update_ensemble_from_training(self, weights, strategy_names, strategy_stats):
        """Update neural model ensemble weights from training results."""
        # Map strategies to model types
        model_map = {
            'MOMENTUM_BREAKOUT': 'lstm', 'TREND_FOLLOWING': 'lstm', 'SUPERTREND': 'lstm',
            'SMC_ORDER_BLOCKS': 'lstm', 'MEAN_REVERSION': 'cnn', 'TRAPPED_TRADERS': 'cnn',
            'DELTA_DIVERGENCE': 'cnn', 'VWAP_BOUNCE': 'transformer', 'ORB': 'transformer',
            'SMC_FVG': 'transformer'
        }
        
        contributions = {'lstm': 0, 'transformer': 0, 'cnn': 0}
        for i, name in enumerate(strategy_names):
            model_type = model_map.get(name, 'lstm')
            contributions[model_type] += weights[i]
        
        total = sum(contributions.values()) or 1
        for model in contributions:
            contributions[model] /= total
        
        if hasattr(self, 'ensemble_weights'):
            self.ensemble_weights = contributions
            print(f"[BRAIN] Updated ensemble weights: {contributions}")
    
    # =========================================================================
    # SLIDE DOCTRINE VALIDATION
    # =========================================================================
    
    def validate_slide_doctrine(self, training_results: Dict = None) -> Dict:
        """
        Validate training against Slide Doctrine principles:
        
        1. Data Quality: Was training data valid and fresh?
        2. Optimization Stability: Did training converge?
        3. Model Generalization: Is there overfitting?
        4. Risk Management: Are prop firm rules respected?
        5. Persistence: Are weights saved properly?
        
        Returns validation report with pass/fail for each principle.
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'checks': [],
            'passed': True,
            'score': 0.0
        }
        
        # Check 1: Data Quality
        data_check = {
            'name': 'DATA_QUALITY',
            'description': 'Training data is valid and representative',
            'passed': True,
            'details': []
        }
        
        if training_results:
            total_trades = training_results.get('final_metrics', {}).get('total_trades', 0)
            if total_trades < 50:
                data_check['passed'] = False
                data_check['details'].append(f'Insufficient trades: {total_trades} < 50')
        else:
            data_check['details'].append('No training results to validate')
        
        report['checks'].append(data_check)
        
        # Check 2: Optimization Stability
        stability_check = {
            'name': 'OPTIMIZATION_STABILITY',
            'description': 'Training converged and weights are stable',
            'passed': True,
            'details': []
        }
        
        if training_results:
            sharpe = training_results.get('best_sharpe', 0)
            if sharpe < 0.5:
                stability_check['passed'] = False
                stability_check['details'].append(f'Low Sharpe ratio: {sharpe:.2f} < 0.5')
            elif sharpe > 0:
                stability_check['details'].append(f'Sharpe ratio OK: {sharpe:.2f}')
            
            weights = training_results.get('strategy_weights', {})
            if weights:
                max_w = max(weights.values())
                if max_w > 0.5:
                    stability_check['passed'] = False
                    stability_check['details'].append(f'Weight concentration: {max_w:.2f} > 0.5')
        
        report['checks'].append(stability_check)
        
        # Check 3: Model Generalization
        generalization_check = {
            'name': 'GENERALIZATION',
            'description': 'Model generalizes and avoids overfitting',
            'passed': True,
            'details': []
        }
        
        if training_results:
            metrics = training_results.get('final_metrics', {})
            win_rate = metrics.get('win_rate', 0)
            
            if win_rate > 0.95:
                generalization_check['passed'] = False
                generalization_check['details'].append(f'Suspiciously high win rate: {win_rate:.1%} (overfitting?)')
            elif win_rate < 0.40:
                generalization_check['passed'] = False
                generalization_check['details'].append(f'Low win rate: {win_rate:.1%} < 40%')
            else:
                generalization_check['details'].append(f'Win rate OK: {win_rate:.1%}')
        
        report['checks'].append(generalization_check)
        
        # Check 4: Risk Management
        risk_check = {
            'name': 'RISK_MANAGEMENT',
            'description': 'Prop firm rules are respected',
            'passed': True,
            'details': []
        }
        
        if training_results:
            pf = training_results.get('final_metrics', {}).get('profit_factor', 0)
            if pf < 1.0:
                risk_check['passed'] = False
                risk_check['details'].append(f'Negative expectancy: PF={pf:.2f} < 1.0')
            elif pf >= 1.5:
                risk_check['details'].append(f'Profit factor OK: {pf:.2f}')
        
        report['checks'].append(risk_check)
        
        # Check 5: Persistence
        persistence_check = {
            'name': 'PERSISTENCE',
            'description': 'Weights and state are properly saved',
            'passed': True,
            'details': []
        }
        
        weights_dir = ROOT / "weights" / "futures_rl"
        if weights_dir.exists():
            files = list(weights_dir.glob("*.pkl")) + list(weights_dir.glob("*.json"))
            if files:
                persistence_check['details'].append(f'Found {len(files)} weight files')
            else:
                persistence_check['passed'] = False
                persistence_check['details'].append('No weight files found')
        else:
            persistence_check['passed'] = False
            persistence_check['details'].append('Weights directory not found')
        
        report['checks'].append(persistence_check)
        
        # Calculate overall
        passed_checks = sum(1 for c in report['checks'] if c['passed'])
        report['score'] = passed_checks / len(report['checks'])
        report['passed'] = report['score'] >= 0.8  # 80% threshold
        
        # Print report
        print("\n" + "=" * 60)
        print("  SLIDE DOCTRINE VALIDATION REPORT")
        print("=" * 60)
        
        for check in report['checks']:
            status = "[PASS]" if check['passed'] else "[FAIL]"
            print(f"\n  {status} {check['name']}")
            print(f"          {check['description']}")
            for detail in check['details']:
                print(f"          - {detail}")
        
        print("\n" + "-" * 60)
        print(f"  Overall Score: {report['score']:.0%}")
        print(f"  Status: {'PASSED' if report['passed'] else 'FAILED'}")
        print("=" * 60)
        
        return report


# =============================================================================
# QUICK START FUNCTIONS
# =============================================================================

def create_enhanced_futures_brain(account_size: str = '50k') -> EnhancedFuturesPropFirmBrain:
    """
    Factory function to create enhanced futures brain.
    
    Args:
        account_size: '50k', '100k', or '150k'
    
    Returns:
        EnhancedFuturesPropFirmBrain instance
    """
    rulesets = {
        '50k': PropFirmRuleset.get_tpt_50k(),
        '100k': PropFirmRuleset.get_tpt_100k(),
        '150k': PropFirmRuleset.get_tpt_150k(),
    }
    return EnhancedFuturesPropFirmBrain(rulesets.get(account_size, rulesets['50k']))


def get_stock_brain_strategies() -> Dict:
    """Quick function to get strategies from stock ML brain."""
    if HAS_EVOLUTION:
        return get_knowledge_from_stock_brain()
    return {}


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_futures_brain_instance = None
_futures_brain_lock = threading.Lock()

def get_futures_brain(account_size: str = 'tpt_50k') -> FuturesPropFirmBrain:
    """
    Get singleton instance of FuturesPropFirmBrain.
    
    Args:
        account_size: 'tpt_50k', 'tpt_100k', 'tpt_150k', or '50k', '100k', '150k'
    
    Returns:
        FuturesPropFirmBrain singleton instance
    """
    global _futures_brain_instance
    
    if _futures_brain_instance is None:
        with _futures_brain_lock:
            if _futures_brain_instance is None:
                # Map account size to ruleset
                size_map = {
                    'tpt_50k': PropFirmRuleset.get_tpt_50k(),
                    '50k': PropFirmRuleset.get_tpt_50k(),
                    'tpt_100k': PropFirmRuleset.get_tpt_100k(),
                    '100k': PropFirmRuleset.get_tpt_100k(),
                    'tpt_150k': PropFirmRuleset.get_tpt_150k(),
                    '150k': PropFirmRuleset.get_tpt_150k(),
                }
                ruleset = size_map.get(account_size.lower(), PropFirmRuleset.get_tpt_50k())
                _futures_brain_instance = FuturesPropFirmBrain(ruleset)
    
    return _futures_brain_instance


# =============================================================================
# MAIN EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ENHANCED FUTURES PROP FIRM BRAIN TEST")
    print("=" * 70)
    
    # Create enhanced brain
    brain = create_enhanced_futures_brain('50k')
    
    # Get stock brain knowledge
    knowledge = brain.get_stock_brain_knowledge()
    print(f"\nStock Brain Knowledge:")
    print(f"  Indicators: {len(knowledge.get('indicator_weights', {}))}")
    print(f"  Strategy params: {len(knowledge.get('strategy_params', {}))}")
    
    # Simulate trade
    import numpy as np
    
    features = torch.randn(1, 100, 64).to(DEVICE)
    indicators = {
        'rsi': 45,
        'trend': 0.3,
        'smc_bias': 0.5,
        'delta': 200,
        'vwap_distance': -0.2,
    }
    internals = {'add': 300, 'tick': 150}
    
    signal = brain.get_enhanced_signal(
        features, indicators, internals, 'MNQ', 'RTH'
    )
    
    print(f"\nEnhanced Signal:")
    print(f"  Should Trade: {signal.get('should_trade')}")
    print(f"  Confidence: {signal.get('confidence', 0):.1%}")
    print(f"  Neural: {signal.get('neural_confidence', 0):.1%}")
    print(f"  Evolution: {signal.get('evolution_confidence', 0):.1%}")
    
    print("\n✅ Enhanced Brain Test Complete!")
