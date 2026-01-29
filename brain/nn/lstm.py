"""
LSTM Models for Time Series Prediction
======================================
Bidirectional LSTM with attention for trading signal prediction.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Optional, Tuple
from .base import BaseModel, ModelConfig


@dataclass
class LSTMConfig(ModelConfig):
    """LSTM-specific configuration."""
    bidirectional: bool = True
    use_attention: bool = True
    num_heads: int = 4
    residual: bool = True


class Attention(nn.Module):
    """Multi-head self-attention for sequence data."""
    
    def __init__(self, hidden_dim: int, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads
        
        assert hidden_dim % num_heads == 0, "hidden_dim must be divisible by num_heads"
        
        self.query = nn.Linear(hidden_dim, hidden_dim)
        self.key = nn.Linear(hidden_dim, hidden_dim)
        self.value = nn.Linear(hidden_dim, hidden_dim)
        self.out = nn.Linear(hidden_dim, hidden_dim)
        
        self.dropout = nn.Dropout(dropout)
        self.scale = self.head_dim ** -0.5
    
    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape
        
        # Project to Q, K, V
        Q = self.query(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.key(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.value(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        
        # Attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, float('-inf'))
        
        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)
        
        # Apply attention to values
        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(batch_size, seq_len, -1)
        
        return self.out(out)


class LSTMPredictor(BaseModel):
    """
    Bidirectional LSTM with optional attention for trading predictions.
    
    Architecture:
    - Input projection
    - Stacked Bi-LSTM layers with residual connections
    - Multi-head self-attention (optional)
    - Output MLP head
    
    Supports both classification (buy/sell/hold) and regression (returns).
    """
    
    def __init__(self, config: LSTMConfig):
        super().__init__(config)
        self.config = config
        
        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(config.input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout)
        )
        
        # LSTM layers
        self.lstm_layers = nn.ModuleList()
        self.layer_norms = nn.ModuleList()
        
        lstm_hidden = config.hidden_dim // 2 if config.bidirectional else config.hidden_dim
        
        for i in range(config.num_layers):
            input_size = config.hidden_dim
            self.lstm_layers.append(
                nn.LSTM(
                    input_size=input_size,
                    hidden_size=lstm_hidden,
                    batch_first=True,
                    bidirectional=config.bidirectional,
                    dropout=config.dropout if i < config.num_layers - 1 else 0
                )
            )
            self.layer_norms.append(nn.LayerNorm(config.hidden_dim))
        
        # Attention
        if config.use_attention:
            self.attention = Attention(
                config.hidden_dim,
                num_heads=config.num_heads,
                dropout=config.dropout
            )
            self.attn_norm = nn.LayerNorm(config.hidden_dim)
        
        # Output head
        if config.task == "classification":
            self.output_head = nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim // 2, config.num_classes)
            )
        else:
            self.output_head = nn.Sequential(
                nn.Linear(config.hidden_dim, config.hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim // 2, config.output_dim)
            )
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor [batch, seq_len, features]
            
        Returns:
            predictions [batch, num_classes] or [batch, output_dim]
        """
        # Input projection
        h = self.input_proj(x)
        
        # LSTM layers with residual
        for i, (lstm, norm) in enumerate(zip(self.lstm_layers, self.layer_norms)):
            residual = h
            h, _ = lstm(h)
            h = norm(h)
            
            if self.config.residual and i > 0:
                h = h + residual
        
        # Attention
        if self.config.use_attention:
            residual = h
            h = self.attention(h)
            h = self.attn_norm(h + residual)
        
        # Pool sequence: use last timestep + mean
        last_hidden = h[:, -1, :]
        mean_hidden = h.mean(dim=1)
        pooled = (last_hidden + mean_hidden) / 2
        
        # Output
        return self.output_head(pooled)
    
    def get_attention_weights(self, x: torch.Tensor) -> torch.Tensor:
        """Get attention weights for interpretability."""
        if not self.config.use_attention:
            raise ValueError("Model doesn't use attention")
        
        self.eval()
        with torch.no_grad():
            h = self.input_proj(x)
            for lstm, norm in zip(self.lstm_layers, self.layer_norms):
                h, _ = lstm(h)
                h = norm(h)
            
            # Get attention
            batch_size, seq_len, _ = h.shape
            Q = self.attention.query(h).view(batch_size, seq_len, self.attention.num_heads, -1).transpose(1, 2)
            K = self.attention.key(h).view(batch_size, seq_len, self.attention.num_heads, -1).transpose(1, 2)
            
            scores = torch.matmul(Q, K.transpose(-2, -1)) * self.attention.scale
            attn_weights = F.softmax(scores, dim=-1)
        
        return attn_weights.mean(dim=1)  # Average across heads
