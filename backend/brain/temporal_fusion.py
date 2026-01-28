"""
QUANT INDUSTRY - Temporal Fusion Transformer
=============================================
State-of-the-art time series forecasting with attention.

Based on Google's Temporal Fusion Transformer (TFT) architecture:
- Multi-horizon forecasting
- Interpretable attention weights
- Variable selection networks
- Static covariate encoding
- Gated residual networks

This is what's actually working in production at quant funds.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Check for PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available - TFT models disabled")


@dataclass
class TFTConfig:
    """Configuration for Temporal Fusion Transformer"""
    # Input dimensions
    n_static_features: int = 5        # Time-invariant features (sector, etc.)
    n_temporal_features: int = 20     # Time-varying features
    n_known_future: int = 5           # Known future inputs (day of week, etc.)
    
    # Architecture
    hidden_size: int = 64
    attention_heads: int = 4
    dropout: float = 0.1
    num_lstm_layers: int = 2
    
    # Sequence lengths
    encoder_length: int = 60          # Historical lookback
    decoder_length: int = 10          # Forecast horizon
    
    # Quantile outputs
    quantiles: Tuple[float, ...] = (0.1, 0.5, 0.9)
    
    # Training
    learning_rate: float = 0.001
    batch_size: int = 64


if TORCH_AVAILABLE:
    
    class GatedLinearUnit(nn.Module):
        """GLU activation with learnable gate"""
        def __init__(self, input_dim: int, output_dim: int, dropout: float = 0.0):
            super().__init__()
            self.fc1 = nn.Linear(input_dim, output_dim)
            self.fc2 = nn.Linear(input_dim, output_dim)
            self.sigmoid = nn.Sigmoid()
            self.dropout = nn.Dropout(dropout)
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.dropout(self.sigmoid(self.fc1(x)) * self.fc2(x))
    
    
    class GatedResidualNetwork(nn.Module):
        """
        Gated Residual Network (GRN) from TFT paper.
        
        Key component that provides non-linear processing with
        skip connections and gating for gradient flow.
        """
        def __init__(
            self,
            input_dim: int,
            hidden_dim: int,
            output_dim: int = None,
            context_dim: int = None,
            dropout: float = 0.1
        ):
            super().__init__()
            self.input_dim = input_dim
            self.output_dim = output_dim or input_dim
            
            self.fc1 = nn.Linear(input_dim, hidden_dim)
            
            if context_dim is not None:
                self.context_fc = nn.Linear(context_dim, hidden_dim, bias=False)
            else:
                self.context_fc = None
            
            self.fc2 = nn.Linear(hidden_dim, hidden_dim)
            self.glu = GatedLinearUnit(hidden_dim, self.output_dim, dropout)
            
            self.layer_norm = nn.LayerNorm(self.output_dim)
            
            # Skip connection projection if dims differ
            if input_dim != self.output_dim:
                self.skip_proj = nn.Linear(input_dim, self.output_dim)
            else:
                self.skip_proj = None
            
            self.dropout = nn.Dropout(dropout)
        
        def forward(
            self,
            x: torch.Tensor,
            context: torch.Tensor = None
        ) -> torch.Tensor:
            # Primary path
            hidden = self.fc1(x)
            
            if context is not None and self.context_fc is not None:
                hidden = hidden + self.context_fc(context)
            
            hidden = F.elu(hidden)
            hidden = self.fc2(hidden)
            hidden = self.dropout(hidden)
            hidden = self.glu(hidden)
            
            # Skip connection
            if self.skip_proj is not None:
                x = self.skip_proj(x)
            
            return self.layer_norm(x + hidden)
    
    
    class VariableSelectionNetwork(nn.Module):
        """
        Variable Selection Network (VSN).
        
        Learns to weight input features by importance.
        Critical for interpretability.
        """
        def __init__(
            self,
            input_dim: int,
            n_features: int,
            hidden_dim: int,
            context_dim: int = None,
            dropout: float = 0.1
        ):
            super().__init__()
            self.n_features = n_features
            self.hidden_dim = hidden_dim
            
            # Per-feature GRNs
            self.feature_grns = nn.ModuleList([
                GatedResidualNetwork(input_dim // n_features, hidden_dim, hidden_dim, dropout=dropout)
                for _ in range(n_features)
            ])
            
            # Selection weights
            self.softmax = nn.Softmax(dim=-1)
            self.selection_grn = GatedResidualNetwork(
                hidden_dim * n_features,
                hidden_dim,
                n_features,
                context_dim,
                dropout
            )
        
        def forward(
            self,
            x: torch.Tensor,
            context: torch.Tensor = None
        ) -> Tuple[torch.Tensor, torch.Tensor]:
            # x shape: (batch, seq, n_features * feature_dim)
            batch_size, seq_len, _ = x.shape
            
            # Split into features
            feature_dim = x.shape[-1] // self.n_features
            features = x.view(batch_size, seq_len, self.n_features, feature_dim)
            
            # Process each feature
            processed = []
            for i, grn in enumerate(self.feature_grns):
                processed.append(grn(features[:, :, i, :]))
            
            # Stack and flatten for selection
            processed = torch.stack(processed, dim=-2)  # (batch, seq, n_features, hidden)
            flat_processed = processed.view(batch_size, seq_len, -1)
            
            # Calculate selection weights
            weights = self.selection_grn(flat_processed, context)
            weights = self.softmax(weights).unsqueeze(-1)  # (batch, seq, n_features, 1)
            
            # Weighted combination
            selected = (processed * weights).sum(dim=-2)  # (batch, seq, hidden)
            
            return selected, weights.squeeze(-1)
    
    
    class InterpretableMultiHeadAttention(nn.Module):
        """
        Multi-head attention with interpretable weights.
        
        Returns attention weights for analysis.
        """
        def __init__(
            self,
            embed_dim: int,
            num_heads: int,
            dropout: float = 0.1
        ):
            super().__init__()
            self.embed_dim = embed_dim
            self.num_heads = num_heads
            self.head_dim = embed_dim // num_heads
            
            assert self.head_dim * num_heads == embed_dim, "embed_dim must be divisible by num_heads"
            
            self.q_proj = nn.Linear(embed_dim, embed_dim)
            self.k_proj = nn.Linear(embed_dim, embed_dim)
            self.v_proj = nn.Linear(embed_dim, embed_dim)
            self.out_proj = nn.Linear(embed_dim, embed_dim)
            
            self.dropout = nn.Dropout(dropout)
            self.scale = self.head_dim ** -0.5
        
        def forward(
            self,
            query: torch.Tensor,
            key: torch.Tensor,
            value: torch.Tensor,
            mask: torch.Tensor = None
        ) -> Tuple[torch.Tensor, torch.Tensor]:
            batch_size, seq_len, _ = query.shape
            
            # Project and reshape
            q = self.q_proj(query).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
            k = self.k_proj(key).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
            v = self.v_proj(value).view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
            
            # Attention scores
            scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale
            
            if mask is not None:
                scores = scores.masked_fill(mask == 0, float('-inf'))
            
            attn_weights = F.softmax(scores, dim=-1)
            attn_weights = self.dropout(attn_weights)
            
            # Apply attention
            out = torch.matmul(attn_weights, v)
            out = out.transpose(1, 2).contiguous().view(batch_size, -1, self.embed_dim)
            out = self.out_proj(out)
            
            # Return average attention weights across heads for interpretability
            avg_weights = attn_weights.mean(dim=1)
            
            return out, avg_weights
    
    
    class TemporalFusionTransformer(nn.Module):
        """
        Temporal Fusion Transformer for multi-horizon forecasting.
        
        Architecture:
        1. Variable Selection Networks for feature importance
        2. LSTM encoder-decoder for local patterns
        3. Self-attention for long-range dependencies
        4. Quantile outputs for uncertainty
        
        Usage:
        ------
        >>> config = TFTConfig(
        ...     n_temporal_features=20,
        ...     encoder_length=60,
        ...     decoder_length=10
        ... )
        >>> model = TemporalFusionTransformer(config)
        >>> 
        >>> # Forward pass
        >>> outputs, attention = model(
        ...     static_inputs=static,       # (batch, n_static)
        ...     temporal_inputs=temporal,   # (batch, seq, n_temporal)
        ...     future_inputs=future        # (batch, future_len, n_future)
        ... )
        >>> 
        >>> # outputs shape: (batch, decoder_length, n_quantiles)
        >>> # attention: interpretable weights
        """
        
        def __init__(self, config: TFTConfig):
            super().__init__()
            self.config = config
            
            hidden = config.hidden_size
            
            # Static covariate encoders
            self.static_encoder = nn.Sequential(
                nn.Linear(config.n_static_features, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden * 4)  # For c_s, c_e, c_h, c_c
            )
            
            # Temporal input embeddings
            self.temporal_embed = nn.Linear(config.n_temporal_features, hidden)
            self.future_embed = nn.Linear(config.n_known_future, hidden)
            
            # Variable selection
            self.temporal_vsn = VariableSelectionNetwork(
                hidden, 1, hidden, hidden, config.dropout
            )
            
            # LSTM encoder-decoder
            self.encoder_lstm = nn.LSTM(
                hidden, hidden,
                num_layers=config.num_lstm_layers,
                batch_first=True,
                dropout=config.dropout if config.num_lstm_layers > 1 else 0
            )
            
            self.decoder_lstm = nn.LSTM(
                hidden, hidden,
                num_layers=config.num_lstm_layers,
                batch_first=True,
                dropout=config.dropout if config.num_lstm_layers > 1 else 0
            )
            
            # GLU for post-LSTM
            self.post_lstm_gate = GatedLinearUnit(hidden, hidden, config.dropout)
            self.post_lstm_norm = nn.LayerNorm(hidden)
            
            # Self-attention
            self.self_attention = InterpretableMultiHeadAttention(
                hidden, config.attention_heads, config.dropout
            )
            self.post_attn_gate = GatedLinearUnit(hidden, hidden, config.dropout)
            self.post_attn_norm = nn.LayerNorm(hidden)
            
            # Position-wise feedforward
            self.ff_grn = GatedResidualNetwork(hidden, hidden, hidden, dropout=config.dropout)
            
            # Output projection (quantile outputs)
            self.output_proj = nn.Linear(hidden, len(config.quantiles))
            
            self._init_weights()
        
        def _init_weights(self):
            """Initialize weights"""
            for module in self.modules():
                if isinstance(module, nn.Linear):
                    nn.init.xavier_uniform_(module.weight)
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)
                elif isinstance(module, nn.LSTM):
                    for name, param in module.named_parameters():
                        if 'weight' in name:
                            nn.init.orthogonal_(param)
                        elif 'bias' in name:
                            nn.init.zeros_(param)
        
        def forward(
            self,
            static_inputs: torch.Tensor,
            temporal_inputs: torch.Tensor,
            future_inputs: torch.Tensor = None
        ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
            """
            Forward pass.
            
            Args:
                static_inputs: Static features (batch, n_static)
                temporal_inputs: Historical features (batch, encoder_len, n_temporal)
                future_inputs: Known future features (batch, decoder_len, n_future)
                
            Returns:
                Tuple of (predictions, attention_weights)
            """
            batch_size = static_inputs.shape[0]
            encoder_len = self.config.encoder_length
            decoder_len = self.config.decoder_length
            
            # 1. Static encoding
            static_encoded = self.static_encoder(static_inputs)
            c_s, c_e, c_h, c_c = static_encoded.chunk(4, dim=-1)
            
            # 2. Temporal embeddings
            temporal_embedded = self.temporal_embed(temporal_inputs)
            
            # 3. Variable selection
            temporal_selected, temporal_weights = self.temporal_vsn(
                temporal_embedded, c_s
            )
            
            # 4. LSTM encoder
            h0 = c_h.unsqueeze(0).repeat(self.config.num_lstm_layers, 1, 1)
            c0 = c_c.unsqueeze(0).repeat(self.config.num_lstm_layers, 1, 1)
            
            encoder_out, (h_n, c_n) = self.encoder_lstm(temporal_selected, (h0, c0))
            
            # 5. Decoder (using future inputs if available)
            if future_inputs is not None:
                future_embedded = self.future_embed(future_inputs)
                decoder_in = future_embedded
            else:
                # Use zeros if no future inputs
                decoder_in = torch.zeros(batch_size, decoder_len, self.config.hidden_size, device=static_inputs.device)
            
            decoder_out, _ = self.decoder_lstm(decoder_in, (h_n, c_n))
            
            # 6. Combine encoder and decoder outputs
            lstm_out = torch.cat([encoder_out, decoder_out], dim=1)
            
            # 7. Post-LSTM gating
            lstm_gated = self.post_lstm_gate(lstm_out)
            lstm_out = self.post_lstm_norm(temporal_selected[:, :encoder_len].repeat(1, 1, 1)[:, :lstm_out.shape[1], :] + lstm_gated)
            
            # 8. Self-attention (decoder attends to full sequence)
            attn_out, attn_weights = self.self_attention(
                lstm_out[:, -decoder_len:, :],  # Query: decoder positions
                lstm_out,                        # Key: full sequence
                lstm_out                         # Value: full sequence
            )
            
            # 9. Post-attention gating
            decoder_positions = lstm_out[:, -decoder_len:, :]
            attn_gated = self.post_attn_gate(attn_out)
            attn_out = self.post_attn_norm(decoder_positions + attn_gated)
            
            # 10. Feed-forward
            ff_out = self.ff_grn(attn_out)
            
            # 11. Output projection
            outputs = self.output_proj(ff_out)
            
            return outputs, {
                "temporal_weights": temporal_weights,
                "attention_weights": attn_weights
            }
        
        def predict(
            self,
            static_inputs: torch.Tensor,
            temporal_inputs: torch.Tensor,
            future_inputs: torch.Tensor = None
        ) -> Dict[str, np.ndarray]:
            """
            Generate predictions with uncertainty.
            
            Returns:
                Dict with 'low', 'mid', 'high' predictions
            """
            self.eval()
            with torch.no_grad():
                outputs, _ = self.forward(static_inputs, temporal_inputs, future_inputs)
                outputs = outputs.cpu().numpy()
            
            return {
                "low": outputs[:, :, 0],     # 10th percentile
                "mid": outputs[:, :, 1],     # Median
                "high": outputs[:, :, 2],    # 90th percentile
            }


class TFTTrainer:
    """
    Trainer for Temporal Fusion Transformer.
    
    Handles:
    - Quantile loss
    - Learning rate scheduling
    - Early stopping
    - Gradient clipping
    """
    
    def __init__(
        self,
        model: 'TemporalFusionTransformer',
        config: TFTConfig,
        device: str = "cuda" if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required for TFT training")
        
        self.model = model.to(device)
        self.config = config
        self.device = device
        
        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=config.learning_rate
        )
        
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5
        )
    
    def quantile_loss(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Quantile loss for probabilistic forecasting.
        """
        quantiles = torch.tensor(self.config.quantiles, device=self.device)
        
        errors = targets.unsqueeze(-1) - predictions
        
        losses = torch.max(
            quantiles * errors,
            (quantiles - 1) * errors
        )
        
        return losses.mean()
    
    def train_epoch(
        self,
        dataloader,
        clip_grad: float = 1.0
    ) -> float:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0.0
        n_batches = 0
        
        for batch in dataloader:
            static = batch['static'].to(self.device)
            temporal = batch['temporal'].to(self.device)
            future = batch.get('future')
            if future is not None:
                future = future.to(self.device)
            targets = batch['targets'].to(self.device)
            
            self.optimizer.zero_grad()
            
            outputs, _ = self.model(static, temporal, future)
            loss = self.quantile_loss(outputs, targets)
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), clip_grad)
            self.optimizer.step()
            
            total_loss += loss.item()
            n_batches += 1
        
        return total_loss / n_batches if n_batches > 0 else 0.0
    
    def validate(self, dataloader) -> float:
        """Validate model"""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0
        
        with torch.no_grad():
            for batch in dataloader:
                static = batch['static'].to(self.device)
                temporal = batch['temporal'].to(self.device)
                future = batch.get('future')
                if future is not None:
                    future = future.to(self.device)
                targets = batch['targets'].to(self.device)
                
                outputs, _ = self.model(static, temporal, future)
                loss = self.quantile_loss(outputs, targets)
                
                total_loss += loss.item()
                n_batches += 1
        
        return total_loss / n_batches if n_batches > 0 else 0.0


# ============== SIMPLIFIED NON-PYTORCH VERSION ==============

class SimpleTFT:
    """
    Simplified TFT-inspired model using numpy.
    
    For environments without PyTorch.
    Uses attention-weighted historical features for prediction.
    """
    
    def __init__(
        self,
        n_features: int = 10,
        lookback: int = 60,
        n_heads: int = 4
    ):
        self.n_features = n_features
        self.lookback = lookback
        self.n_heads = n_heads
        
        # Learnable attention weights (simplified)
        self.attention_weights = np.ones(lookback) / lookback
        self.feature_weights = np.ones(n_features) / n_features
        
        # Simple linear coefficients
        self.coefficients = np.zeros(n_features)
        self.bias = 0.0
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 100,
        lr: float = 0.01
    ):
        """
        Fit model using gradient descent.
        
        Args:
            X: Features (n_samples, lookback, n_features)
            y: Targets (n_samples,)
        """
        n_samples = len(y)
        
        for epoch in range(epochs):
            # Forward pass with current weights
            predictions = self._predict(X)
            
            # MSE loss
            errors = predictions - y
            loss = np.mean(errors ** 2)
            
            # Gradient for coefficients
            weighted_features = self._apply_attention(X)
            grad_coef = 2 * np.mean(errors[:, np.newaxis] * weighted_features, axis=0)
            
            # Update
            self.coefficients -= lr * grad_coef
            self.bias -= lr * 2 * np.mean(errors)
            
            if epoch % 20 == 0:
                logger.debug(f"Epoch {epoch}: Loss = {loss:.6f}")
    
    def _apply_attention(self, X: np.ndarray) -> np.ndarray:
        """Apply attention weights to features"""
        # X: (n_samples, lookback, n_features)
        
        # Time attention
        time_weighted = np.sum(X * self.attention_weights[np.newaxis, :, np.newaxis], axis=1)
        
        # Feature attention
        feature_weighted = time_weighted * self.feature_weights
        
        return feature_weighted
    
    def _predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        weighted = self._apply_attention(X)
        return np.dot(weighted, self.coefficients) + self.bias
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Public predict method"""
        return self._predict(X)


# ============== FACTORY FUNCTIONS ==============

def create_tft_model(config: TFTConfig = None) -> 'TemporalFusionTransformer':
    """Create TFT model"""
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required for TFT. Install with: pip install torch")
    
    config = config or TFTConfig()
    return TemporalFusionTransformer(config)


def create_simple_tft(n_features: int = 10, lookback: int = 60) -> SimpleTFT:
    """Create simplified TFT (no PyTorch required)"""
    return SimpleTFT(n_features=n_features, lookback=lookback)
