"""
Trading Brain - Unified Neural Architecture
============================================
End-to-end model combining feature extraction, context encoding,
policy decisions, and risk-aware position sizing.

Architecture:
    Market Data -> TCN (local patterns) -> Transformer (regime/context)
                                      v
                              RL Policy Head -> Action distribution
                                      v
                              Risk Head -> Position sizing with uncertainty
                                      v
                              Meta-Learner -> Online adaptation
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical, Normal
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
import math


class ActionType(Enum):
    """Trading action types."""
    DISCRETE = "discrete"      # Buy/Hold/Sell
    CONTINUOUS = "continuous"  # Position allocation [-1, 1]


@dataclass
class TradingBrainConfig:
    """Configuration for the unified trading brain."""
    # Input
    input_dim: int = 32
    seq_len: int = 60
    
    # TCN Feature Extractor
    tcn_channels: List[int] = field(default_factory=lambda: [64, 64, 64])
    tcn_kernel_size: int = 3
    
    # Transformer Context Encoder
    transformer_dim: int = 128
    transformer_heads: int = 4
    transformer_layers: int = 2
    transformer_ff_dim: int = 256
    
    # Policy Head
    action_type: ActionType = ActionType.DISCRETE
    num_actions: int = 3  # For discrete: Sell, Hold, Buy
    
    # Risk Head
    risk_hidden_dim: int = 64
    use_uncertainty: bool = True
    
    # Meta-Learner
    use_meta_learner: bool = True
    meta_hidden_dim: int = 32
    adaptation_rate: float = 0.01
    
    # Training
    dropout: float = 0.1


class CausalConv1d(nn.Module):
    """Causal convolution for TCN."""
    
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int = 1):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, 
                              padding=self.padding, dilation=dilation)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)
        return out[:, :, :-self.padding] if self.padding > 0 else out


class TCNBlock(nn.Module):
    """Temporal Convolutional Block with residual."""
    
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float):
        super().__init__()
        self.conv1 = CausalConv1d(in_channels, out_channels, kernel_size, dilation)
        self.conv2 = CausalConv1d(out_channels, out_channels, kernel_size, dilation)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.dropout = nn.Dropout(dropout)
        self.residual = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x if self.residual is None else self.residual(x)
        out = self.dropout(F.gelu(self.bn1(self.conv1(x))))
        out = self.dropout(F.gelu(self.bn2(self.conv2(out))))
        return F.gelu(out + residual)


class FeatureExtractor(nn.Module):
    """TCN-based feature extractor for local temporal patterns."""
    
    def __init__(self, config: TradingBrainConfig):
        super().__init__()
        channels = [config.input_dim] + config.tcn_channels
        
        self.blocks = nn.ModuleList([
            TCNBlock(
                channels[i], channels[i+1],
                config.tcn_kernel_size,
                dilation=2**i,
                dropout=config.dropout
            )
            for i in range(len(channels) - 1)
        ])
        
        self.output_dim = config.tcn_channels[-1]
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [batch, seq, features] -> [batch, features, seq]
        x = x.transpose(1, 2)
        for block in self.blocks:
            x = block(x)
        return x.transpose(1, 2)  # Back to [batch, seq, channels]


class ContextEncoder(nn.Module):
    """Transformer-based context encoder for regime understanding."""
    
    def __init__(self, config: TradingBrainConfig):
        super().__init__()
        self.input_proj = nn.Linear(config.tcn_channels[-1], config.transformer_dim)
        
        # Learnable positional encoding
        self.pos_embedding = nn.Parameter(torch.randn(1, config.seq_len, config.transformer_dim) * 0.02)
        
        # Transformer layers
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.transformer_dim,
            nhead=config.transformer_heads,
            dim_feedforward=config.transformer_ff_dim,
            dropout=config.dropout,
            activation='gelu',
            batch_first=True,
            norm_first=True  # Pre-LN for stability
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, config.transformer_layers)
        
        # CLS token for aggregation
        self.cls_token = nn.Parameter(torch.randn(1, 1, config.transformer_dim) * 0.02)
        
        self.norm = nn.LayerNorm(config.transformer_dim)
        self.output_dim = config.transformer_dim
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size, seq_len, _ = x.shape
        
        # Project and add positional encoding
        x = self.input_proj(x)
        x = x + self.pos_embedding[:, :seq_len, :]
        
        # Add CLS token
        cls_tokens = self.cls_token.expand(batch_size, -1, -1)
        x = torch.cat([cls_tokens, x], dim=1)
        
        # Transformer encoding
        x = self.transformer(x)
        x = self.norm(x)
        
        # Return both CLS (global) and sequence (local) representations
        cls_output = x[:, 0]           # [batch, dim] - global context
        seq_output = x[:, 1:]          # [batch, seq, dim] - local context
        
        return cls_output, seq_output


class PolicyHead(nn.Module):
    """RL policy head for action selection."""
    
    def __init__(self, config: TradingBrainConfig):
        super().__init__()
        self.action_type = config.action_type
        
        hidden_dim = config.transformer_dim
        
        self.shared = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
        )
        
        if config.action_type == ActionType.DISCRETE:
            self.actor = nn.Linear(hidden_dim, config.num_actions)
        else:
            self.actor_mean = nn.Linear(hidden_dim, 1)
            self.actor_logstd = nn.Parameter(torch.zeros(1))
        
        self.critic = nn.Linear(hidden_dim, 1)
    
    def forward(self, context: torch.Tensor) -> Dict[str, torch.Tensor]:
        h = self.shared(context)
        
        value = self.critic(h).squeeze(-1)
        
        if self.action_type == ActionType.DISCRETE:
            logits = self.actor(h)
            return {
                'logits': logits,
                'value': value,
                'action_type': 'discrete'
            }
        else:
            mean = torch.tanh(self.actor_mean(h))  # Bounded [-1, 1]
            std = F.softplus(self.actor_logstd).expand_as(mean)
            return {
                'mean': mean,
                'std': std,
                'value': value,
                'action_type': 'continuous'
            }
    
    def get_action(self, policy_output: Dict, deterministic: bool = False) -> Tuple[torch.Tensor, torch.Tensor]:
        """Sample action and compute log probability."""
        if policy_output['action_type'] == 'discrete':
            logits = policy_output['logits']
            if deterministic:
                action = logits.argmax(dim=-1)
                log_prob = torch.zeros_like(action, dtype=torch.float)
            else:
                dist = Categorical(logits=logits)
                action = dist.sample()
                log_prob = dist.log_prob(action)
        else:
            mean, std = policy_output['mean'], policy_output['std']
            if deterministic:
                action = mean
                log_prob = torch.zeros(mean.shape[0], device=mean.device)
            else:
                dist = Normal(mean, std)
                action = dist.sample()
                log_prob = dist.log_prob(action).sum(-1)
        
        return action, log_prob


class RiskHead(nn.Module):
    """Risk-aware position sizing with uncertainty estimation."""
    
    def __init__(self, config: TradingBrainConfig):
        super().__init__()
        self.use_uncertainty = config.use_uncertainty
        
        input_dim = config.transformer_dim
        hidden_dim = config.risk_hidden_dim
        
        # Risk factors network
        self.risk_net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
        )
        
        # Position size output (0 to 1)
        self.position_head = nn.Sequential(
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()
        )
        
        # Uncertainty estimation (epistemic + aleatoric)
        if config.use_uncertainty:
            self.uncertainty_head = nn.Linear(hidden_dim, 2)  # [epistemic, aleatoric]
        
        # Regime-dependent risk scaling
        self.regime_scale = nn.Sequential(
            nn.Linear(input_dim, 4),  # 4 regime types
            nn.Softmax(dim=-1)
        )
        
        # Risk multipliers per regime: [trending_up, trending_down, ranging, volatile]
        self.regime_multipliers = nn.Parameter(torch.tensor([1.2, 0.8, 1.0, 0.5]))
    
    def forward(self, context: torch.Tensor, policy_output: Dict) -> Dict[str, torch.Tensor]:
        h = self.risk_net(context)
        
        # Base position size
        base_position = self.position_head(h).squeeze(-1)
        
        # Regime-based scaling
        regime_probs = self.regime_scale(context)
        regime_multiplier = (regime_probs * self.regime_multipliers).sum(dim=-1)
        
        # Uncertainty-based scaling
        if self.use_uncertainty:
            uncertainty = self.uncertainty_head(h)
            epistemic = F.softplus(uncertainty[:, 0])   # Model uncertainty
            aleatoric = F.softplus(uncertainty[:, 1])   # Data uncertainty
            total_uncertainty = epistemic + aleatoric
            
            # Reduce position size when uncertain
            uncertainty_scale = torch.exp(-total_uncertainty * 0.5)
        else:
            epistemic = torch.zeros_like(base_position)
            aleatoric = torch.zeros_like(base_position)
            uncertainty_scale = torch.ones_like(base_position)
        
        # Final position size
        position_size = base_position * regime_multiplier * uncertainty_scale
        position_size = torch.clamp(position_size, 0.0, 1.0)
        
        return {
            'position_size': position_size,
            'base_position': base_position,
            'regime_probs': regime_probs,
            'regime_multiplier': regime_multiplier,
            'epistemic_uncertainty': epistemic,
            'aleatoric_uncertainty': aleatoric,
        }


class MetaLearner(nn.Module):
    """
    Meta-learner for online adaptation based on performance feedback.
    
    Learns to adjust model behavior based on recent trading performance.
    """
    
    def __init__(self, config: TradingBrainConfig):
        super().__init__()
        self.adaptation_rate = config.adaptation_rate
        
        # Performance encoding
        self.perf_encoder = nn.Sequential(
            nn.Linear(8, config.meta_hidden_dim),  # 8 performance metrics
            nn.LayerNorm(config.meta_hidden_dim),
            nn.GELU(),
            nn.Linear(config.meta_hidden_dim, config.meta_hidden_dim),
        )
        
        # Adaptation vectors for each component
        self.feature_adapter = nn.Linear(config.meta_hidden_dim, config.tcn_channels[-1])
        self.context_adapter = nn.Linear(config.meta_hidden_dim, config.transformer_dim)
        self.risk_adapter = nn.Linear(config.meta_hidden_dim, 1)
        
        # Running performance buffer
        self.register_buffer('perf_buffer', torch.zeros(100, 8))
        self.register_buffer('buffer_idx', torch.tensor(0))
    
    def encode_performance(self, metrics: Dict[str, float]) -> torch.Tensor:
        """Encode performance metrics into adaptation signal."""
        # Expected metrics: sharpe, returns, drawdown, win_rate, profit_factor, 
        #                   volatility, trade_count, avg_trade_duration
        perf_vector = torch.tensor([
            metrics.get('sharpe', 0.0),
            metrics.get('returns', 0.0),
            metrics.get('drawdown', 0.0),
            metrics.get('win_rate', 0.5),
            metrics.get('profit_factor', 1.0),
            metrics.get('volatility', 0.02),
            metrics.get('trade_count', 0.0) / 100,  # Normalize
            metrics.get('avg_duration', 1.0) / 24,  # Normalize to days
        ], dtype=torch.float32)
        
        return perf_vector
    
    def update_buffer(self, perf_vector: torch.Tensor):
        """Update rolling performance buffer."""
        idx = self.buffer_idx.item() % 100
        self.perf_buffer[idx] = perf_vector
        self.buffer_idx += 1
    
    def get_adaptation(self) -> Dict[str, torch.Tensor]:
        """Get current adaptation vectors based on recent performance."""
        # Use recent performance (exponential weighting)
        n = min(self.buffer_idx.item(), 100)
        if n == 0:
            return {
                'feature_adapt': torch.zeros(1),
                'context_adapt': torch.zeros(1),
                'risk_adapt': torch.zeros(1),
            }
        
        weights = torch.exp(torch.linspace(-2, 0, n))
        weights = weights / weights.sum()
        
        recent_perf = self.perf_buffer[:n]
        weighted_perf = (recent_perf * weights.unsqueeze(1)).sum(dim=0)
        
        # Encode and generate adaptations
        encoded = self.perf_encoder(weighted_perf.unsqueeze(0))
        
        return {
            'feature_adapt': torch.tanh(self.feature_adapter(encoded)) * self.adaptation_rate,
            'context_adapt': torch.tanh(self.context_adapter(encoded)) * self.adaptation_rate,
            'risk_adapt': torch.sigmoid(self.risk_adapter(encoded)),
        }


class TradingBrain(nn.Module):
    """
    Unified Trading Brain combining all components.
    
    Pipeline:
        Market Data -> Feature Extractor (TCN) -> Context Encoder (Transformer)
                                             v
                                    Policy Head -> Action
                                             v
                                    Risk Head -> Position Size
                                             v
                                    Meta-Learner -> Adaptation (optional)
    """
    
    def __init__(self, config: TradingBrainConfig):
        super().__init__()
        self.config = config
        
        # Core components
        self.feature_extractor = FeatureExtractor(config)
        self.context_encoder = ContextEncoder(config)
        self.policy_head = PolicyHead(config)
        self.risk_head = RiskHead(config)
        
        # Meta-learner (optional)
        if config.use_meta_learner:
            self.meta_learner = MetaLearner(config)
        else:
            self.meta_learner = None
        
        # Initialize weights
        self.apply(self._init_weights)
        
        # Track parameters
        self._log_parameters()
    
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.orthogonal_(module.weight, gain=0.5)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Conv1d):
            nn.init.kaiming_normal_(module.weight, mode='fan_out', nonlinearity='relu')
    
    def _log_parameters(self):
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"TradingBrain: {total:,} total params, {trainable:,} trainable")
    
    def forward(
        self,
        market_data: torch.Tensor,
        deterministic: bool = False,
        return_internals: bool = False
    ) -> Dict[str, Any]:
        """
        Full forward pass through the trading brain.
        
        Args:
            market_data: [batch, seq_len, features]
            deterministic: Use deterministic action selection
            return_internals: Return intermediate representations
            
        Returns:
            Dictionary with actions, position sizes, and optional internals
        """
        # 1. Extract local features
        features = self.feature_extractor(market_data)
        
        # 2. Encode global context
        global_context, local_context = self.context_encoder(features)
        
        # 3. Apply meta-learning adaptation if available
        if self.meta_learner is not None:
            adaptation = self.meta_learner.get_adaptation()
            global_context = global_context + adaptation['context_adapt']
        
        # 4. Get policy output
        policy_output = self.policy_head(global_context)
        
        # 5. Sample action
        action, log_prob = self.policy_head.get_action(policy_output, deterministic)
        
        # 6. Compute risk-aware position size
        risk_output = self.risk_head(global_context, policy_output)
        
        # Combine outputs
        result = {
            'action': action,
            'log_prob': log_prob,
            'value': policy_output['value'],
            'position_size': risk_output['position_size'],
            'regime_probs': risk_output['regime_probs'],
            'uncertainty': risk_output['epistemic_uncertainty'] + risk_output['aleatoric_uncertainty'],
        }
        
        if return_internals:
            result['features'] = features
            result['global_context'] = global_context
            result['local_context'] = local_context
            result['policy_output'] = policy_output
            result['risk_output'] = risk_output
        
        return result
    
    def update_performance(self, metrics: Dict[str, float]):
        """Update meta-learner with new performance metrics."""
        if self.meta_learner is not None:
            perf_vector = self.meta_learner.encode_performance(metrics)
            self.meta_learner.update_buffer(perf_vector)
    
    def get_trading_signal(
        self,
        market_data: torch.Tensor,
        current_position: float = 0.0
    ) -> Dict[str, float]:
        """
        Get trading signal for live trading.
        
        Args:
            market_data: Recent market data [1, seq_len, features]
            current_position: Current position (-1 to 1)
            
        Returns:
            Trading signal dict with action, size, confidence
        """
        self.eval()
        with torch.no_grad():
            output = self(market_data, deterministic=True, return_internals=True)
            
            action = output['action'].item()
            position_size = output['position_size'].item()
            uncertainty = output['uncertainty'].item()
            regime_probs = output['regime_probs'][0].cpu().numpy()
            
            # Map action to signal
            if self.config.action_type == ActionType.DISCRETE:
                action_map = {0: 'sell', 1: 'hold', 2: 'buy'}
                signal = action_map.get(action, 'hold')
            else:
                signal = 'buy' if action > 0.1 else ('sell' if action < -0.1 else 'hold')
            
            # Calculate target position
            if signal == 'buy':
                target_position = position_size
            elif signal == 'sell':
                target_position = -position_size
            else:
                target_position = current_position * 0.9  # Decay towards flat
            
            return {
                'signal': signal,
                'action_raw': action,
                'target_position': target_position,
                'position_size': position_size,
                'confidence': 1.0 - min(uncertainty, 1.0),
                'regime': {
                    'trending_up': regime_probs[0],
                    'trending_down': regime_probs[1],
                    'ranging': regime_probs[2],
                    'volatile': regime_probs[3],
                },
                'value_estimate': output['value'].item(),
            }


def create_trading_brain(
    input_dim: int = 32,
    seq_len: int = 60,
    action_type: str = "discrete",
    use_meta_learner: bool = True,
    **kwargs
) -> TradingBrain:
    """
    Factory function to create a TradingBrain with sensible defaults.
    
    Args:
        input_dim: Number of input features
        seq_len: Sequence length (lookback window)
        action_type: "discrete" or "continuous"
        use_meta_learner: Enable online adaptation
        **kwargs: Additional config overrides
        
    Returns:
        Configured TradingBrain instance
    """
    config = TradingBrainConfig(
        input_dim=input_dim,
        seq_len=seq_len,
        action_type=ActionType.DISCRETE if action_type == "discrete" else ActionType.CONTINUOUS,
        use_meta_learner=use_meta_learner,
        **kwargs
    )
    
    return TradingBrain(config)
