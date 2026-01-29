"""
Multi-Timeframe Neural Architecture
===================================
Processes multiple timeframes simultaneously to generate signals
for different trading horizons: Scalp, Intraday, Swing, Macro.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    MARKET DATA                               │
    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐ │
    │  │  1min  │ │  5min  │ │  1hour │ │  4hour │ │  1day/week │ │
    │  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └─────┬──────┘ │
    └──────┼──────────┼──────────┼──────────┼────────────┼────────┘
           │          │          │          │            │
           ▼          ▼          ▼          ▼            ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              TIMEFRAME ENCODERS (TCN per timeframe)          │
    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐ │
    │  │Encoder │ │Encoder │ │Encoder │ │Encoder │ │  Encoder   │ │
    │  │ Scalp  │ │Intraday│ │ Swing  │ │Position│ │   Macro    │ │
    │  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └─────┬──────┘ │
    └──────┼──────────┼──────────┼──────────┼────────────┼────────┘
           │          │          │          │            │
           └──────────┴──────────┴──────────┴────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  CROSS-TIMEFRAME ATTENTION                   │
    │         (Learn relationships between timeframes)             │
    └────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    HORIZON-SPECIFIC HEADS                    │
    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                │
    │  │ Scalp  │ │Intraday│ │ Swing  │ │ Macro  │                │
    │  │ Signal │ │ Signal │ │ Signal │ │ Signal │                │
    │  └────────┘ └────────┘ └────────┘ └────────┘                │
    └─────────────────────────────────────────────────────────────┘
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import math


class TradingHorizon(Enum):
    """Trading time horizons."""
    SCALP = "scalp"           # Minutes to hour
    INTRADAY = "intraday"     # Hours to day
    SWING = "swing"           # Days to weeks
    POSITION = "position"     # Weeks to months
    MACRO = "macro"           # Months+


@dataclass
class TimeframeConfig:
    """Configuration for a single timeframe."""
    name: str
    interval: str  # e.g., "1m", "5m", "1h", "4h", "1d"
    lookback_bars: int  # How many bars to look back
    horizon: TradingHorizon
    weight: float = 1.0  # Relative importance


@dataclass
class MultiTimeframeConfig:
    """Configuration for multi-timeframe brain."""
    # Input
    input_dim: int = 32
    
    # Timeframes
    timeframes: List[TimeframeConfig] = field(default_factory=lambda: [
        TimeframeConfig("1m", "1m", 60, TradingHorizon.SCALP, 0.8),
        TimeframeConfig("5m", "5m", 60, TradingHorizon.SCALP, 1.0),
        TimeframeConfig("15m", "15m", 48, TradingHorizon.INTRADAY, 1.0),
        TimeframeConfig("1h", "1h", 48, TradingHorizon.INTRADAY, 1.2),
        TimeframeConfig("4h", "4h", 60, TradingHorizon.SWING, 1.2),
        TimeframeConfig("1d", "1d", 60, TradingHorizon.SWING, 1.5),
        TimeframeConfig("1w", "1w", 52, TradingHorizon.MACRO, 1.0),
    ])
    
    # Architecture
    encoder_dim: int = 64
    fusion_dim: int = 128
    num_attention_heads: int = 4
    num_fusion_layers: int = 2
    
    # Outputs
    num_actions: int = 3  # Sell, Hold, Buy per horizon
    
    # Training
    dropout: float = 0.1


class TimeframeEncoder(nn.Module):
    """
    Encoder for a single timeframe using TCN.
    
    Extracts temporal patterns specific to this timeframe's resolution.
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        num_layers: int = 3,
        kernel_size: int = 3,
        dropout: float = 0.1
    ):
        super().__init__()
        
        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        
        # TCN layers with increasing dilation
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        
        for i in range(num_layers):
            dilation = 2 ** i
            padding = (kernel_size - 1) * dilation
            
            self.convs.append(
                nn.Conv1d(hidden_dim, hidden_dim, kernel_size,
                         padding=padding, dilation=dilation)
            )
            self.norms.append(nn.BatchNorm1d(hidden_dim))
        
        self.dropout = nn.Dropout(dropout)
        self.output_dim = hidden_dim
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [batch, seq_len, features]
        Returns:
            encoded: [batch, hidden_dim]
        """
        # Project
        h = self.input_proj(x)  # [batch, seq, hidden]
        h = h.transpose(1, 2)   # [batch, hidden, seq]
        
        # TCN with residual
        for conv, norm in zip(self.convs, self.norms):
            residual = h
            h = conv(h)
            h = h[:, :, :residual.size(2)]  # Trim padding
            h = F.gelu(norm(h))
            h = self.dropout(h)
            h = h + residual
        
        # Global pooling: mean + last
        pooled = torch.cat([
            h.mean(dim=2),
            h[:, :, -1]
        ], dim=1)
        
        return pooled  # [batch, hidden_dim * 2]


class CrossTimeframeAttention(nn.Module):
    """
    Attention across timeframes to learn their relationships.
    
    Higher timeframes provide context, lower provide precision.
    """
    
    def __init__(
        self,
        input_dim: int,
        num_timeframes: int,
        num_heads: int = 4,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.num_timeframes = num_timeframes
        
        # Self-attention across timeframes
        self.attention = nn.MultiheadAttention(
            embed_dim=input_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # Learnable timeframe embeddings (hierarchical position)
        self.tf_embeddings = nn.Parameter(
            torch.randn(num_timeframes, input_dim) * 0.02
        )
        
        # Feed-forward
        self.ff = nn.Sequential(
            nn.Linear(input_dim, input_dim * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(input_dim * 4, input_dim),
            nn.Dropout(dropout)
        )
        
        self.norm1 = nn.LayerNorm(input_dim)
        self.norm2 = nn.LayerNorm(input_dim)
    
    def forward(self, timeframe_features: torch.Tensor) -> torch.Tensor:
        """
        Args:
            timeframe_features: [batch, num_timeframes, dim]
        Returns:
            fused: [batch, num_timeframes, dim]
        """
        batch_size = timeframe_features.size(0)
        
        # Add timeframe position embeddings
        tf_emb = self.tf_embeddings.unsqueeze(0).expand(batch_size, -1, -1)
        x = timeframe_features + tf_emb
        
        # Self-attention
        residual = x
        x = self.norm1(x)
        attn_out, _ = self.attention(x, x, x)
        x = residual + attn_out
        
        # Feed-forward
        residual = x
        x = residual + self.ff(self.norm2(x))
        
        return x


class HorizonHead(nn.Module):
    """
    Output head for a specific trading horizon.
    
    Produces action probabilities and confidence for this horizon.
    """
    
    def __init__(
        self,
        input_dim: int,
        num_actions: int = 3,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.net = nn.Sequential(
            nn.Linear(input_dim, input_dim // 2),
            nn.LayerNorm(input_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        
        # Action logits
        self.action_head = nn.Linear(input_dim // 2, num_actions)
        
        # Confidence (0-1)
        self.confidence_head = nn.Sequential(
            nn.Linear(input_dim // 2, 1),
            nn.Sigmoid()
        )
        
        # Position size suggestion
        self.size_head = nn.Sequential(
            nn.Linear(input_dim // 2, 1),
            nn.Sigmoid()
        )
        
        # Value estimate
        self.value_head = nn.Linear(input_dim // 2, 1)
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        h = self.net(x)
        
        return {
            'action_logits': self.action_head(h),
            'confidence': self.confidence_head(h).squeeze(-1),
            'suggested_size': self.size_head(h).squeeze(-1),
            'value': self.value_head(h).squeeze(-1),
        }


class MultiTimeframeBrain(nn.Module):
    """
    Multi-Timeframe Trading Brain.
    
    Processes data from multiple timeframes simultaneously and produces
    signals appropriate for different trading horizons.
    
    Key innovations:
    - Separate encoders per timeframe (learns timeframe-specific patterns)
    - Cross-timeframe attention (higher TFs inform lower TFs)
    - Horizon-specific output heads (scalp vs swing have different characteristics)
    - Regime awareness propagates from higher to lower timeframes
    """
    
    def __init__(self, config: MultiTimeframeConfig):
        super().__init__()
        self.config = config
        
        # Timeframe encoders
        self.encoders = nn.ModuleDict({
            tf.name: TimeframeEncoder(
                input_dim=config.input_dim,
                hidden_dim=config.encoder_dim,
                dropout=config.dropout
            )
            for tf in config.timeframes
        })
        
        # Project encoder outputs to fusion dim
        encoder_output_dim = config.encoder_dim * 2  # mean + last pooling
        self.tf_projections = nn.ModuleDict({
            tf.name: nn.Linear(encoder_output_dim, config.fusion_dim)
            for tf in config.timeframes
        })
        
        # Cross-timeframe attention layers
        self.cross_tf_attention = nn.ModuleList([
            CrossTimeframeAttention(
                config.fusion_dim,
                len(config.timeframes),
                config.num_attention_heads,
                config.dropout
            )
            for _ in range(config.num_fusion_layers)
        ])
        
        # Aggregate features per horizon
        self.horizon_aggregators = nn.ModuleDict()
        for horizon in TradingHorizon:
            # Get timeframes for this horizon
            tf_indices = [
                i for i, tf in enumerate(config.timeframes)
                if tf.horizon == horizon or self._is_relevant_horizon(tf.horizon, horizon)
            ]
            if tf_indices:
                self.horizon_aggregators[horizon.value] = nn.Linear(
                    config.fusion_dim * len(tf_indices),
                    config.fusion_dim
                )
        
        # Output heads per horizon
        self.horizon_heads = nn.ModuleDict({
            horizon.value: HorizonHead(
                config.fusion_dim,
                config.num_actions,
                config.dropout
            )
            for horizon in TradingHorizon
            if horizon.value in self.horizon_aggregators
        })
        
        # Regime detector (uses highest timeframes)
        self.regime_head = nn.Sequential(
            nn.Linear(config.fusion_dim, config.fusion_dim // 2),
            nn.GELU(),
            nn.Linear(config.fusion_dim // 2, 4),  # 4 regimes
            nn.Softmax(dim=-1)
        )
        
        # Initialize
        self.apply(self._init_weights)
        self._log_architecture()
    
    def _is_relevant_horizon(self, tf_horizon: TradingHorizon, target_horizon: TradingHorizon) -> bool:
        """Check if a timeframe's horizon is relevant to the target horizon."""
        # Higher timeframes inform lower timeframes
        order = [TradingHorizon.SCALP, TradingHorizon.INTRADAY, 
                 TradingHorizon.SWING, TradingHorizon.POSITION, TradingHorizon.MACRO]
        
        tf_idx = order.index(tf_horizon)
        target_idx = order.index(target_horizon)
        
        # Include timeframes that are same level or one level higher
        return tf_idx >= target_idx and tf_idx <= target_idx + 1
    
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight, gain=0.5)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
    
    def _log_architecture(self):
        total_params = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"MultiTimeframeBrain: {total_params:,} params ({trainable:,} trainable)")
        print(f"Timeframes: {[tf.name for tf in self.config.timeframes]}")
        print(f"Horizons: {list(self.horizon_heads.keys())}")
    
    def forward(
        self,
        timeframe_data: Dict[str, torch.Tensor],
        return_all_horizons: bool = True
    ) -> Dict[str, Any]:
        """
        Forward pass through multi-timeframe brain.
        
        Args:
            timeframe_data: Dict mapping timeframe name to data tensor
                           {name: [batch, seq_len, features]}
            return_all_horizons: Return signals for all horizons
            
        Returns:
            Dict with signals per horizon and regime probabilities
        """
        batch_size = next(iter(timeframe_data.values())).size(0)
        
        # 1. Encode each timeframe
        tf_features = []
        tf_names = []
        
        for tf in self.config.timeframes:
            if tf.name in timeframe_data:
                data = timeframe_data[tf.name]
                encoded = self.encoders[tf.name](data)
                projected = self.tf_projections[tf.name](encoded)
                tf_features.append(projected)
                tf_names.append(tf.name)
        
        # Stack: [batch, num_timeframes, fusion_dim]
        tf_stack = torch.stack(tf_features, dim=1)
        
        # 2. Cross-timeframe attention
        for attn_layer in self.cross_tf_attention:
            tf_stack = attn_layer(tf_stack)
        
        # 3. Get regime from highest timeframes
        # Use last few (highest) timeframes for regime
        high_tf_features = tf_stack[:, -2:, :].mean(dim=1)  # Last 2 TFs
        regime_probs = self.regime_head(high_tf_features)
        
        # 4. Generate signals per horizon
        outputs = {
            'regime_probs': regime_probs,
            'regime': self._regime_to_name(regime_probs),
        }
        
        for horizon in TradingHorizon:
            if horizon.value not in self.horizon_heads:
                continue
            
            # Get relevant timeframe features for this horizon
            relevant_indices = [
                i for i, tf in enumerate(self.config.timeframes)
                if tf.name in tf_names and (
                    tf.horizon == horizon or 
                    self._is_relevant_horizon(tf.horizon, horizon)
                )
            ]
            
            if not relevant_indices:
                continue
            
            # Aggregate relevant timeframes
            relevant_features = tf_stack[:, relevant_indices, :]
            aggregated = relevant_features.reshape(batch_size, -1)
            
            # Might need padding if fewer timeframes
            expected_size = self.horizon_aggregators[horizon.value].in_features
            if aggregated.size(1) < expected_size:
                padding = torch.zeros(batch_size, expected_size - aggregated.size(1), 
                                     device=aggregated.device)
                aggregated = torch.cat([aggregated, padding], dim=1)
            
            horizon_features = self.horizon_aggregators[horizon.value](aggregated)
            
            # Get horizon-specific output
            horizon_output = self.horizon_heads[horizon.value](horizon_features)
            
            outputs[horizon.value] = {
                'action_logits': horizon_output['action_logits'],
                'action_probs': F.softmax(horizon_output['action_logits'], dim=-1),
                'confidence': horizon_output['confidence'],
                'suggested_size': horizon_output['suggested_size'],
                'value': horizon_output['value'],
            }
        
        return outputs
    
    def _regime_to_name(self, regime_probs: torch.Tensor) -> List[str]:
        """Convert regime probabilities to names."""
        regime_names = ['trending_up', 'trending_down', 'ranging', 'volatile']
        indices = regime_probs.argmax(dim=-1)
        return [regime_names[i] for i in indices.tolist()]
    
    def get_signal(
        self,
        timeframe_data: Dict[str, torch.Tensor],
        horizon: TradingHorizon = TradingHorizon.INTRADAY
    ) -> Dict[str, Any]:
        """
        Get trading signal for a specific horizon.
        
        Args:
            timeframe_data: Market data per timeframe
            horizon: Target trading horizon
            
        Returns:
            Signal dict with action, confidence, size, regime
        """
        self.eval()
        with torch.no_grad():
            output = self(timeframe_data)
            
            if horizon.value not in output:
                return {'error': f'Horizon {horizon.value} not available'}
            
            horizon_out = output[horizon.value]
            action_probs = horizon_out['action_probs'][0]
            
            # Map action
            action_idx = action_probs.argmax().item()
            actions = ['sell', 'hold', 'buy']
            
            return {
                'horizon': horizon.value,
                'action': actions[action_idx],
                'action_probs': {
                    'sell': action_probs[0].item(),
                    'hold': action_probs[1].item(),
                    'buy': action_probs[2].item(),
                },
                'confidence': horizon_out['confidence'][0].item(),
                'suggested_size': horizon_out['suggested_size'][0].item(),
                'value_estimate': horizon_out['value'][0].item(),
                'regime': output['regime'][0],
                'regime_probs': {
                    'trending_up': output['regime_probs'][0, 0].item(),
                    'trending_down': output['regime_probs'][0, 1].item(),
                    'ranging': output['regime_probs'][0, 2].item(),
                    'volatile': output['regime_probs'][0, 3].item(),
                }
            }
    
    def get_all_signals(
        self,
        timeframe_data: Dict[str, torch.Tensor]
    ) -> Dict[str, Dict[str, Any]]:
        """Get signals for ALL trading horizons at once."""
        signals = {}
        
        for horizon in TradingHorizon:
            if horizon.value in self.horizon_heads:
                signals[horizon.value] = self.get_signal(timeframe_data, horizon)
        
        return signals


def create_multi_timeframe_brain(
    input_dim: int = 32,
    timeframes: Optional[List[str]] = None,
    **kwargs
) -> MultiTimeframeBrain:
    """
    Factory function to create a MultiTimeframeBrain.
    
    Args:
        input_dim: Number of input features
        timeframes: List of timeframe strings (e.g., ["1m", "5m", "1h", "4h", "1d"])
        **kwargs: Additional config overrides
    """
    # Default timeframes if not specified
    if timeframes is None:
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
    
    # Map timeframe strings to configs
    tf_mapping = {
        "1m": TimeframeConfig("1m", "1m", 60, TradingHorizon.SCALP, 0.8),
        "5m": TimeframeConfig("5m", "5m", 60, TradingHorizon.SCALP, 1.0),
        "15m": TimeframeConfig("15m", "15m", 48, TradingHorizon.INTRADAY, 1.0),
        "30m": TimeframeConfig("30m", "30m", 48, TradingHorizon.INTRADAY, 1.0),
        "1h": TimeframeConfig("1h", "1h", 48, TradingHorizon.INTRADAY, 1.2),
        "4h": TimeframeConfig("4h", "4h", 60, TradingHorizon.SWING, 1.2),
        "1d": TimeframeConfig("1d", "1d", 60, TradingHorizon.SWING, 1.5),
        "1w": TimeframeConfig("1w", "1w", 52, TradingHorizon.MACRO, 1.0),
        "1M": TimeframeConfig("1M", "1M", 24, TradingHorizon.MACRO, 0.8),
    }
    
    tf_configs = [tf_mapping[tf] for tf in timeframes if tf in tf_mapping]
    
    config = MultiTimeframeConfig(
        input_dim=input_dim,
        timeframes=tf_configs,
        **kwargs
    )
    
    return MultiTimeframeBrain(config)
