"""
Transformer Models for Time Series
===================================
Transformer encoder architecture optimized for financial time series.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from dataclasses import dataclass
from typing import Optional
from .base import BaseModel, ModelConfig


@dataclass
class TransformerConfig(ModelConfig):
    """Transformer-specific configuration."""
    num_heads: int = 8
    ff_dim: int = 1024
    num_layers: int = 4
    use_positional: bool = True
    max_seq_len: int = 512
    pre_norm: bool = True  # Pre-LayerNorm (more stable)


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding."""
    
    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        
        self.register_buffer('pe', pe)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class LearnedPositionalEncoding(nn.Module):
    """Learned positional encoding."""
    
    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        self.pe = nn.Embedding(max_len, d_model)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.size(1)
        positions = torch.arange(seq_len, device=x.device).unsqueeze(0)
        x = x + self.pe(positions)
        return self.dropout(x)


class TransformerBlock(nn.Module):
    """Single transformer encoder block with pre-norm."""
    
    def __init__(
        self,
        d_model: int,
        num_heads: int,
        ff_dim: int,
        dropout: float = 0.1,
        pre_norm: bool = True
    ):
        super().__init__()
        self.pre_norm = pre_norm
        
        self.attention = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        self.ff = nn.Sequential(
            nn.Linear(d_model, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, d_model),
            nn.Dropout(dropout)
        )
        
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        if self.pre_norm:
            # Pre-LayerNorm (more stable training)
            normed = self.norm1(x)
            attn_out, _ = self.attention(normed, normed, normed, attn_mask=mask)
            x = x + self.dropout(attn_out)
            
            normed = self.norm2(x)
            x = x + self.ff(normed)
        else:
            # Post-LayerNorm (original transformer)
            attn_out, _ = self.attention(x, x, x, attn_mask=mask)
            x = self.norm1(x + self.dropout(attn_out))
            x = self.norm2(x + self.ff(x))
        
        return x


class TransformerPredictor(BaseModel):
    """
    Transformer encoder for time series prediction.
    
    Architecture:
    - Input projection + positional encoding
    - Stack of transformer encoder blocks
    - Global pooling
    - Output MLP head
    
    Features:
    - Pre-LayerNorm for stable training
    - GELU activation
    - Learned or sinusoidal positional encoding
    """
    
    def __init__(self, config: TransformerConfig):
        super().__init__(config)
        self.config = config
        
        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(config.input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
        )
        
        # Positional encoding
        if config.use_positional:
            self.pos_encoding = LearnedPositionalEncoding(
                config.hidden_dim,
                max_len=config.max_seq_len,
                dropout=config.dropout
            )
        else:
            self.pos_encoding = nn.Dropout(config.dropout)
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(
                d_model=config.hidden_dim,
                num_heads=config.num_heads,
                ff_dim=config.ff_dim,
                dropout=config.dropout,
                pre_norm=config.pre_norm
            )
            for _ in range(config.num_layers)
        ])
        
        # Final norm (for pre-norm architecture)
        self.final_norm = nn.LayerNorm(config.hidden_dim)
        
        # CLS token for pooling
        self.cls_token = nn.Parameter(torch.randn(1, 1, config.hidden_dim))
        
        # Output head
        output_dim = config.num_classes if config.task == "classification" else config.output_dim
        self.output_head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, output_dim)
        )
        
        # Initialize
        self.apply(self._init_weights)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor [batch, seq_len, features]
            
        Returns:
            predictions [batch, num_classes] or [batch, output_dim]
        """
        batch_size = x.size(0)
        
        # Project input
        h = self.input_proj(x)
        
        # Add CLS token
        cls_tokens = self.cls_token.expand(batch_size, -1, -1)
        h = torch.cat([cls_tokens, h], dim=1)
        
        # Positional encoding
        h = self.pos_encoding(h)
        
        # Transformer blocks
        for block in self.blocks:
            h = block(h)
        
        # Final norm
        h = self.final_norm(h)
        
        # Use CLS token for classification
        cls_output = h[:, 0, :]
        
        # Output
        return self.output_head(cls_output)
    
    def get_attention_maps(self, x: torch.Tensor) -> list:
        """Get attention maps from all layers for interpretability."""
        self.eval()
        attention_maps = []
        
        with torch.no_grad():
            batch_size = x.size(0)
            h = self.input_proj(x)
            
            cls_tokens = self.cls_token.expand(batch_size, -1, -1)
            h = torch.cat([cls_tokens, h], dim=1)
            h = self.pos_encoding(h)
            
            for block in self.blocks:
                normed = block.norm1(h)
                _, attn_weights = block.attention(
                    normed, normed, normed, 
                    need_weights=True, 
                    average_attn_weights=False
                )
                attention_maps.append(attn_weights)
                h = block(h)
        
        return attention_maps


class TemporalTransformer(BaseModel):
    """
    Temporal Fusion Transformer variant optimized for trading.
    
    Adds:
    - Temporal convolutions before transformer
    - Multi-scale feature extraction
    - Uncertainty estimation (optional)
    """
    
    def __init__(self, config: TransformerConfig):
        super().__init__(config)
        self.config = config
        
        # Multi-scale temporal convolutions
        self.conv_layers = nn.ModuleList([
            nn.Conv1d(config.input_dim, config.hidden_dim // 4, kernel_size=k, padding=k//2)
            for k in [3, 5, 7, 9]
        ])
        
        # Combine conv outputs
        self.conv_proj = nn.Linear(config.hidden_dim, config.hidden_dim)
        
        # Standard transformer
        self.pos_encoding = LearnedPositionalEncoding(
            config.hidden_dim,
            max_len=config.max_seq_len,
            dropout=config.dropout
        )
        
        self.blocks = nn.ModuleList([
            TransformerBlock(
                d_model=config.hidden_dim,
                num_heads=config.num_heads,
                ff_dim=config.ff_dim,
                dropout=config.dropout,
                pre_norm=config.pre_norm
            )
            for _ in range(config.num_layers)
        ])
        
        self.final_norm = nn.LayerNorm(config.hidden_dim)
        
        # Output with uncertainty
        output_dim = config.num_classes if config.task == "classification" else config.output_dim
        self.mean_head = nn.Linear(config.hidden_dim, output_dim)
        self.var_head = nn.Linear(config.hidden_dim, output_dim)  # Log variance
        
        self.apply(self._init_weights)
    
    def forward(self, x: torch.Tensor, return_uncertainty: bool = False):
        """Forward pass with optional uncertainty estimation."""
        # Multi-scale convolutions
        x_t = x.transpose(1, 2)  # [batch, features, seq]
        conv_outs = [F.gelu(conv(x_t)) for conv in self.conv_layers]
        h = torch.cat(conv_outs, dim=1).transpose(1, 2)  # [batch, seq, hidden]
        h = self.conv_proj(h)
        
        # Transformer
        h = self.pos_encoding(h)
        for block in self.blocks:
            h = block(h)
        h = self.final_norm(h)
        
        # Global pooling
        pooled = h.mean(dim=1)
        
        # Predictions
        mean = self.mean_head(pooled)
        
        if return_uncertainty:
            log_var = self.var_head(pooled)
            std = torch.exp(0.5 * log_var)
            return mean, std
        
        return mean
