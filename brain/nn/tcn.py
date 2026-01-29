"""
Temporal Convolutional Network (TCN)
====================================
Dilated causal convolutions for sequence modeling.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Optional, List
from .base import BaseModel, ModelConfig


@dataclass
class TCNConfig(ModelConfig):
    """TCN-specific configuration."""
    num_channels: List[int] = None
    kernel_size: int = 3
    dilation_base: int = 2
    
    def __post_init__(self):
        if self.num_channels is None:
            self.num_channels = [self.hidden_dim] * self.num_layers


class CausalConv1d(nn.Module):
    """Causal convolution - only uses past information."""
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int = 1
    ):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size,
            padding=self.padding,
            dilation=dilation
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)
        # Remove future information
        if self.padding > 0:
            out = out[:, :, :-self.padding]
        return out


class TemporalBlock(nn.Module):
    """
    Residual block with dilated causal convolutions.
    
    Structure:
    - Causal Conv -> BatchNorm -> ReLU -> Dropout
    - Causal Conv -> BatchNorm -> ReLU -> Dropout
    - Residual connection
    """
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float = 0.2
    ):
        super().__init__()
        
        self.conv1 = CausalConv1d(
            in_channels, out_channels, kernel_size, dilation
        )
        self.bn1 = nn.BatchNorm1d(out_channels)
        
        self.conv2 = CausalConv1d(
            out_channels, out_channels, kernel_size, dilation
        )
        self.bn2 = nn.BatchNorm1d(out_channels)
        
        self.dropout = nn.Dropout(dropout)
        
        # Residual connection
        self.residual = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        
        self.relu = nn.ReLU()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x if self.residual is None else self.residual(x)
        
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.dropout(out)
        out = self.relu(self.bn2(self.conv2(out)))
        out = self.dropout(out)
        
        return self.relu(out + residual)


class TCNPredictor(BaseModel):
    """
    Temporal Convolutional Network for time series prediction.
    
    Advantages over RNNs:
    - Parallelizable (no sequential dependency)
    - Long receptive field with dilations
    - Stable gradients (no vanishing/exploding)
    - Faster training
    
    Architecture:
    - Input projection
    - Stack of temporal blocks with increasing dilation
    - Global pooling
    - Output head
    """
    
    def __init__(self, config: TCNConfig):
        super().__init__(config)
        self.config = config
        
        # Input projection
        self.input_proj = nn.Linear(config.input_dim, config.num_channels[0])
        
        # Temporal blocks
        layers = []
        num_levels = len(config.num_channels)
        
        for i in range(num_levels):
            in_channels = config.num_channels[0] if i == 0 else config.num_channels[i-1]
            out_channels = config.num_channels[i]
            dilation = config.dilation_base ** i
            
            layers.append(
                TemporalBlock(
                    in_channels,
                    out_channels,
                    config.kernel_size,
                    dilation,
                    config.dropout
                )
            )
        
        self.tcn = nn.Sequential(*layers)
        
        # Output head
        final_channels = config.num_channels[-1]
        output_dim = config.num_classes if config.task == "classification" else config.output_dim
        
        self.output_head = nn.Sequential(
            nn.Linear(final_channels * 2, final_channels),  # *2 for concat pooling
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(final_channels, output_dim)
        )
        
        self.apply(self._init_weights)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor [batch, seq_len, features]
            
        Returns:
            predictions [batch, num_classes] or [batch, output_dim]
        """
        # Project and transpose for conv
        h = self.input_proj(x)  # [batch, seq, channels]
        h = h.transpose(1, 2)   # [batch, channels, seq]
        
        # TCN
        h = self.tcn(h)
        
        # Global pooling: last + mean
        last = h[:, :, -1]
        mean = h.mean(dim=2)
        pooled = torch.cat([last, mean], dim=1)
        
        # Output
        return self.output_head(pooled)
    
    @property
    def receptive_field(self) -> int:
        """Calculate the receptive field of the TCN."""
        rf = 1
        for i in range(len(self.config.num_channels)):
            dilation = self.config.dilation_base ** i
            rf += (self.config.kernel_size - 1) * dilation * 2
        return rf


class WaveNet(BaseModel):
    """
    WaveNet-style architecture adapted for trading.
    
    Features:
    - Gated activations (tanh * sigmoid)
    - Skip connections for gradient flow
    - Residual connections
    """
    
    def __init__(self, config: TCNConfig):
        super().__init__(config)
        self.config = config
        
        # Input projection
        self.input_proj = nn.Conv1d(config.input_dim, config.hidden_dim, 1)
        
        # Dilated conv layers
        self.dilated_convs = nn.ModuleList()
        self.gate_convs = nn.ModuleList()
        self.residual_convs = nn.ModuleList()
        self.skip_convs = nn.ModuleList()
        
        for i in range(config.num_layers):
            dilation = config.dilation_base ** (i % 10)  # Reset dilation periodically
            
            self.dilated_convs.append(
                CausalConv1d(config.hidden_dim, config.hidden_dim, config.kernel_size, dilation)
            )
            self.gate_convs.append(
                CausalConv1d(config.hidden_dim, config.hidden_dim, config.kernel_size, dilation)
            )
            self.residual_convs.append(
                nn.Conv1d(config.hidden_dim, config.hidden_dim, 1)
            )
            self.skip_convs.append(
                nn.Conv1d(config.hidden_dim, config.hidden_dim, 1)
            )
        
        # Output
        output_dim = config.num_classes if config.task == "classification" else config.output_dim
        self.output = nn.Sequential(
            nn.ReLU(),
            nn.Conv1d(config.hidden_dim, config.hidden_dim, 1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(config.hidden_dim, output_dim)
        )
        
        self.apply(self._init_weights)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward with gated activations and skip connections."""
        x = x.transpose(1, 2)  # [batch, features, seq]
        x = self.input_proj(x)
        
        skip_sum = 0
        
        for dilated, gate, residual, skip in zip(
            self.dilated_convs, self.gate_convs, self.residual_convs, self.skip_convs
        ):
            # Gated activation
            filter_out = torch.tanh(dilated(x))
            gate_out = torch.sigmoid(gate(x))
            gated = filter_out * gate_out
            
            # Skip connection
            skip_sum = skip_sum + skip(gated)
            
            # Residual
            x = x + residual(gated)
        
        return self.output(skip_sum)
