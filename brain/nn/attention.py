"""
Attention-based Models
======================
Various attention mechanisms for trading signals.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from dataclasses import dataclass
from typing import Optional, Tuple
from .base import BaseModel, ModelConfig


class MultiHeadAttention(nn.Module):
    """Multi-head attention with relative position encoding."""
    
    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        dropout: float = 0.1,
        max_len: int = 512
    ):
        super().__init__()
        assert d_model % num_heads == 0
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        
        self.dropout = nn.Dropout(dropout)
        self.scale = self.head_dim ** -0.5
        
        # Relative position bias
        self.relative_bias = nn.Embedding(2 * max_len - 1, num_heads)
    
    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size, seq_len, _ = query.shape
        
        # Project
        Q = self.q_proj(query).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(key).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(value).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        
        # Attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
        
        # Add relative position bias
        positions = torch.arange(seq_len, device=query.device)
        rel_pos = positions.unsqueeze(1) - positions.unsqueeze(0) + seq_len - 1
        rel_bias = self.relative_bias(rel_pos).permute(2, 0, 1)
        scores = scores + rel_bias.unsqueeze(0)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))
        
        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)
        
        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        out = self.out_proj(out)
        
        return out, attn


class CrossAttention(nn.Module):
    """Cross-attention between two sequences (e.g., price and volume)."""
    
    def __init__(self, d_model: int, num_heads: int = 8, dropout: float = 0.1):
        super().__init__()
        self.attention = MultiHeadAttention(d_model, num_heads, dropout)
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(
        self,
        query: torch.Tensor,
        context: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        attn_out, _ = self.attention(query, context, context, mask)
        return self.norm(query + self.dropout(attn_out))


class TemporalAttention(nn.Module):
    """Attention specifically designed for temporal patterns in trading."""
    
    def __init__(
        self,
        d_model: int,
        num_heads: int = 4,
        window_size: int = 20,
        dropout: float = 0.1
    ):
        super().__init__()
        self.window_size = window_size
        self.attention = MultiHeadAttention(d_model, num_heads, dropout)
        
        # Learnable temporal decay
        self.decay = nn.Parameter(torch.ones(num_heads))
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, d_model = x.shape
        
        # Create temporal mask with decay
        positions = torch.arange(seq_len, device=x.device)
        distance = positions.unsqueeze(0) - positions.unsqueeze(1)
        
        # Apply learned decay
        decay_mask = torch.exp(-torch.abs(distance).float() / self.window_size)
        decay_mask = decay_mask.unsqueeze(0).unsqueeze(0)  # [1, 1, seq, seq]
        
        out, attn = self.attention(x, x, x)
        
        # Weight by temporal proximity
        weighted_attn = attn * decay_mask
        weighted_attn = weighted_attn / (weighted_attn.sum(dim=-1, keepdim=True) + 1e-9)
        
        return out


@dataclass 
class AttentionConfig(ModelConfig):
    """Configuration for attention-based predictor."""
    num_heads: int = 8
    ff_dim: int = 512
    use_cross_attention: bool = False
    num_features_secondary: int = 32


class AttentionPredictor(BaseModel):
    """
    Pure attention-based predictor for trading signals.
    
    Features:
    - Multi-head self-attention with relative positions
    - Optional cross-attention for multi-modal data
    - Temporal decay weighting
    - Feature-wise attention pooling
    """
    
    def __init__(self, config: AttentionConfig):
        super().__init__(config)
        self.config = config
        
        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(config.input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.Dropout(config.dropout)
        )
        
        # Self-attention layers
        self.self_attn_layers = nn.ModuleList([
            nn.ModuleDict({
                'attn': MultiHeadAttention(config.hidden_dim, config.num_heads, config.dropout),
                'norm1': nn.LayerNorm(config.hidden_dim),
                'ff': nn.Sequential(
                    nn.Linear(config.hidden_dim, config.ff_dim),
                    nn.GELU(),
                    nn.Dropout(config.dropout),
                    nn.Linear(config.ff_dim, config.hidden_dim),
                    nn.Dropout(config.dropout)
                ),
                'norm2': nn.LayerNorm(config.hidden_dim)
            })
            for _ in range(config.num_layers)
        ])
        
        # Cross-attention (optional)
        if config.use_cross_attention:
            self.secondary_proj = nn.Linear(config.num_features_secondary, config.hidden_dim)
            self.cross_attn = CrossAttention(config.hidden_dim, config.num_heads, config.dropout)
        
        # Temporal attention for final pooling
        self.temporal_attn = TemporalAttention(config.hidden_dim, 4, 20, config.dropout)
        
        # Feature-wise attention pooling
        self.pool_attn = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 4),
            nn.Tanh(),
            nn.Linear(config.hidden_dim // 4, 1)
        )
        
        # Output head
        output_dim = config.num_classes if config.task == "classification" else config.output_dim
        self.output_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, output_dim)
        )
        
        self.apply(self._init_weights)
    
    def forward(
        self,
        x: torch.Tensor,
        x_secondary: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Primary input [batch, seq_len, features]
            x_secondary: Optional secondary input for cross-attention
            
        Returns:
            predictions [batch, num_classes] or [batch, output_dim]
        """
        # Input projection
        h = self.input_proj(x)
        
        # Self-attention layers
        for layer in self.self_attn_layers:
            # Self-attention
            residual = h
            attn_out, _ = layer['attn'](h, h, h)
            h = layer['norm1'](residual + attn_out)
            
            # Feed-forward
            residual = h
            h = layer['norm2'](residual + layer['ff'](h))
        
        # Cross-attention (if available)
        if self.config.use_cross_attention and x_secondary is not None:
            h_secondary = self.secondary_proj(x_secondary)
            h = self.cross_attn(h, h_secondary)
        
        # Temporal attention
        h = self.temporal_attn(h)
        
        # Attention pooling
        attn_weights = F.softmax(self.pool_attn(h).squeeze(-1), dim=1)
        pooled = torch.sum(h * attn_weights.unsqueeze(-1), dim=1)
        
        # Output
        return self.output_head(pooled)
    
    def get_feature_importance(self, x: torch.Tensor) -> torch.Tensor:
        """Get attention-based feature importance."""
        self.eval()
        with torch.no_grad():
            h = self.input_proj(x)
            
            for layer in self.self_attn_layers:
                residual = h
                attn_out, attn_weights = layer['attn'](h, h, h)
                h = layer['norm1'](residual + attn_out)
                residual = h
                h = layer['norm2'](residual + layer['ff'](h))
            
            # Pool attention weights
            pool_weights = F.softmax(self.pool_attn(h).squeeze(-1), dim=1)
        
        return pool_weights
