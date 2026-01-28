"""
QUANT_INDUSTRY_V1 Attention Flow Network

Order flow analysis using attention mechanisms to model
market microstructure and institutional activity patterns.

Features:
- Multi-head self-attention for order flow patterns
- Cross-attention between price and volume
- Positional encoding for temporal awareness
- Flow imbalance detection
- Institutional footprint analysis

Pure NumPy implementation.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import pickle

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AttentionFlowConfig:
    """Attention Flow Network configuration."""
    # Input dimensions
    price_features: int = 32  # OHLC + derived features
    volume_features: int = 16  # Volume + flow features
    order_flow_features: int = 24  # Order flow specific

    # Architecture
    hidden_dim: int = 128
    num_attention_heads: int = 4
    num_encoder_layers: int = 3
    feedforward_dim: int = 256
    dropout_rate: float = 0.1

    # Sequence
    sequence_length: int = 60
    max_position: int = 512

    # Output
    num_classes: int = 3  # Long, Short, Flat


# =============================================================================
# ATTENTION COMPONENTS
# =============================================================================

def positional_encoding(seq_length: int, d_model: int) -> np.ndarray:
    """
    Sinusoidal positional encoding.

    PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    """
    position = np.arange(seq_length)[:, np.newaxis]
    div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))

    pe = np.zeros((seq_length, d_model))
    pe[:, 0::2] = np.sin(position * div_term)
    pe[:, 1::2] = np.cos(position * div_term)

    return pe.astype(np.float32)


def scaled_dot_product_attention(
    query: np.ndarray,
    key: np.ndarray,
    value: np.ndarray,
    mask: np.ndarray = None,
    dropout_rate: float = 0.0,
    training: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Scaled dot-product attention.

    Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
    """
    d_k = query.shape[-1]
    scores = np.matmul(query, key.transpose(0, 1, 3, 2)) / np.sqrt(d_k)

    if mask is not None:
        scores = scores + mask * -1e9

    # Softmax
    scores_max = np.max(scores, axis=-1, keepdims=True)
    exp_scores = np.exp(scores - scores_max)
    attention_weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

    # Dropout
    if training and dropout_rate > 0:
        mask = np.random.binomial(1, 1 - dropout_rate, attention_weights.shape) / (1 - dropout_rate)
        attention_weights = attention_weights * mask

    output = np.matmul(attention_weights, value)

    return output, attention_weights


class MultiHeadAttention:
    """Multi-head attention mechanism."""

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        dropout_rate: float = 0.1,
    ):
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.dropout_rate = dropout_rate
        self.training = True

        assert d_model % num_heads == 0

        # Linear projections
        std = np.sqrt(2.0 / d_model)
        self.W_q = np.random.randn(d_model, d_model).astype(np.float32) * std
        self.W_k = np.random.randn(d_model, d_model).astype(np.float32) * std
        self.W_v = np.random.randn(d_model, d_model).astype(np.float32) * std
        self.W_o = np.random.randn(d_model, d_model).astype(np.float32) * std

        self.b_q = np.zeros(d_model, dtype=np.float32)
        self.b_k = np.zeros(d_model, dtype=np.float32)
        self.b_v = np.zeros(d_model, dtype=np.float32)
        self.b_o = np.zeros(d_model, dtype=np.float32)

    def __call__(
        self,
        query: np.ndarray,
        key: np.ndarray,
        value: np.ndarray,
        mask: np.ndarray = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        batch_size = query.shape[0]
        seq_len_q = query.shape[1]
        seq_len_kv = key.shape[1]

        # Linear projections
        Q = np.dot(query, self.W_q) + self.b_q
        K = np.dot(key, self.W_k) + self.b_k
        V = np.dot(value, self.W_v) + self.b_v

        # Reshape for multi-head
        Q = Q.reshape(batch_size, seq_len_q, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        K = K.reshape(batch_size, seq_len_kv, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        V = V.reshape(batch_size, seq_len_kv, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)

        # Attention
        attn_output, attn_weights = scaled_dot_product_attention(
            Q, K, V, mask, self.dropout_rate, self.training
        )

        # Reshape back
        attn_output = attn_output.transpose(0, 2, 1, 3).reshape(batch_size, seq_len_q, self.d_model)

        # Output projection
        output = np.dot(attn_output, self.W_o) + self.b_o

        return output, attn_weights


class FeedForward:
    """Position-wise feed-forward network."""

    def __init__(self, d_model: int, d_ff: int, dropout_rate: float = 0.1):
        self.d_model = d_model
        self.d_ff = d_ff
        self.dropout_rate = dropout_rate
        self.training = True

        std1 = np.sqrt(2.0 / d_model)
        std2 = np.sqrt(2.0 / d_ff)

        self.W1 = np.random.randn(d_model, d_ff).astype(np.float32) * std1
        self.b1 = np.zeros(d_ff, dtype=np.float32)
        self.W2 = np.random.randn(d_ff, d_model).astype(np.float32) * std2
        self.b2 = np.zeros(d_model, dtype=np.float32)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        # First linear + GELU
        h = np.dot(x, self.W1) + self.b1
        h = 0.5 * h * (1 + np.tanh(np.sqrt(2 / np.pi) * (h + 0.044715 * h**3)))

        # Dropout
        if self.training and self.dropout_rate > 0:
            mask = np.random.binomial(1, 1 - self.dropout_rate, h.shape) / (1 - self.dropout_rate)
            h = h * mask

        # Second linear
        return np.dot(h, self.W2) + self.b2


class LayerNorm:
    """Layer normalization."""

    def __init__(self, d_model: int, eps: float = 1e-6):
        self.d_model = d_model
        self.eps = eps
        self.gamma = np.ones(d_model, dtype=np.float32)
        self.beta = np.zeros(d_model, dtype=np.float32)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)
        x_norm = (x - mean) / np.sqrt(var + self.eps)
        return self.gamma * x_norm + self.beta


class TransformerEncoderLayer:
    """Single transformer encoder layer."""

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout_rate: float = 0.1,
    ):
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout_rate)
        self.ff = FeedForward(d_model, d_ff, dropout_rate)
        self.norm1 = LayerNorm(d_model)
        self.norm2 = LayerNorm(d_model)
        self.dropout_rate = dropout_rate
        self.training = True

    def __call__(self, x: np.ndarray, mask: np.ndarray = None) -> Tuple[np.ndarray, np.ndarray]:
        # Self-attention with residual
        attn_output, attn_weights = self.self_attn(x, x, x, mask)

        if self.training and self.dropout_rate > 0:
            drop_mask = np.random.binomial(1, 1 - self.dropout_rate, attn_output.shape) / (1 - self.dropout_rate)
            attn_output = attn_output * drop_mask

        x = self.norm1(x + attn_output)

        # Feed-forward with residual
        ff_output = self.ff(x)

        if self.training and self.dropout_rate > 0:
            drop_mask = np.random.binomial(1, 1 - self.dropout_rate, ff_output.shape) / (1 - self.dropout_rate)
            ff_output = ff_output * drop_mask

        x = self.norm2(x + ff_output)

        return x, attn_weights


class CrossAttentionLayer:
    """Cross-attention between two sequences."""

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        dropout_rate: float = 0.1,
    ):
        self.cross_attn = MultiHeadAttention(d_model, num_heads, dropout_rate)
        self.norm = LayerNorm(d_model)
        self.dropout_rate = dropout_rate
        self.training = True

    def __call__(
        self,
        query: np.ndarray,
        key_value: np.ndarray,
        mask: np.ndarray = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        attn_output, attn_weights = self.cross_attn(query, key_value, key_value, mask)

        if self.training and self.dropout_rate > 0:
            drop_mask = np.random.binomial(1, 1 - self.dropout_rate, attn_output.shape) / (1 - self.dropout_rate)
            attn_output = attn_output * drop_mask

        output = self.norm(query + attn_output)

        return output, attn_weights


# =============================================================================
# ORDER FLOW COMPONENTS
# =============================================================================

class OrderFlowProcessor:
    """
    Process raw order flow data into features.

    Computes:
    - Cumulative volume delta
    - Order imbalance
    - Large trade detection
    - Absorption patterns
    """

    def __init__(self, config: AttentionFlowConfig):
        self.config = config

    def compute_features(
        self,
        price: np.ndarray,  # [batch, seq, 4] OHLC
        volume: np.ndarray,  # [batch, seq]
        trades: np.ndarray = None,  # Optional trade-level data
    ) -> Dict[str, np.ndarray]:
        """Compute order flow features."""
        batch_size = price.shape[0]
        seq_len = price.shape[1]

        # Basic flow features
        open_p, high, low, close = price[:, :, 0], price[:, :, 1], price[:, :, 2], price[:, :, 3]

        # Price direction
        direction = np.sign(close - open_p)

        # Approximate buy/sell volume (simplified)
        buy_volume = np.where(direction > 0, volume, volume * 0.5)
        sell_volume = np.where(direction < 0, volume, volume * 0.5)

        # Cumulative Volume Delta (CVD)
        volume_delta = buy_volume - sell_volume
        cvd = np.cumsum(volume_delta, axis=1)

        # Order imbalance
        total_vol = buy_volume + sell_volume + 1e-8
        imbalance = (buy_volume - sell_volume) / total_vol

        # Volume relative to average
        vol_sma = np.zeros_like(volume)
        for i in range(seq_len):
            start = max(0, i - 20)
            vol_sma[:, i] = np.mean(volume[:, start:i+1], axis=1)
        relative_volume = volume / (vol_sma + 1e-8)

        # Large volume spikes
        volume_std = np.std(volume, axis=1, keepdims=True)
        volume_mean = np.mean(volume, axis=1, keepdims=True)
        large_volume = (volume > volume_mean + 2 * volume_std).astype(np.float32)

        # Price momentum
        returns = np.zeros_like(close)
        returns[:, 1:] = (close[:, 1:] - close[:, :-1]) / (close[:, :-1] + 1e-8)

        # Range as % of close
        range_pct = (high - low) / (close + 1e-8)

        # Body ratio (close - open) / (high - low)
        body = np.abs(close - open_p)
        wick = high - low + 1e-8
        body_ratio = body / wick

        # Absorption: Large volume with small price move
        absorption = large_volume * (1 - np.abs(returns) * 100)
        absorption = np.clip(absorption, 0, 1)

        return {
            'volume_delta': volume_delta,
            'cvd': cvd,
            'imbalance': imbalance,
            'relative_volume': relative_volume,
            'large_volume': large_volume,
            'returns': returns,
            'range_pct': range_pct,
            'body_ratio': body_ratio,
            'absorption': absorption,
            'direction': direction,
        }


# =============================================================================
# ATTENTION FLOW NETWORK
# =============================================================================

class AttentionFlowNetwork:
    """
    Attention Flow Network for order flow analysis.

    Architecture:
    1. Separate embeddings for price and volume features
    2. Self-attention within each stream
    3. Cross-attention between price and volume
    4. Order flow feature integration
    5. Classification head
    """

    def __init__(self, config: AttentionFlowConfig = None):
        self.config = config or AttentionFlowConfig()
        self.training = True

        d_model = self.config.hidden_dim
        n_heads = self.config.num_attention_heads
        d_ff = self.config.feedforward_dim
        dropout = self.config.dropout_rate

        # Input projections
        total_input = self.config.price_features + self.config.volume_features + self.config.order_flow_features
        std = np.sqrt(2.0 / total_input)
        self.input_proj = np.random.randn(total_input, d_model).astype(np.float32) * std
        self.input_bias = np.zeros(d_model, dtype=np.float32)

        # Price stream encoder
        self.price_encoder = [
            TransformerEncoderLayer(d_model, n_heads, d_ff, dropout)
            for _ in range(self.config.num_encoder_layers)
        ]

        # Volume stream encoder
        self.volume_encoder = [
            TransformerEncoderLayer(d_model, n_heads, d_ff, dropout)
            for _ in range(self.config.num_encoder_layers)
        ]

        # Cross-attention (price attending to volume)
        self.cross_attention = CrossAttentionLayer(d_model, n_heads, dropout)

        # Order flow processor
        self.flow_processor = OrderFlowProcessor(self.config)

        # Final encoder
        self.final_encoder = TransformerEncoderLayer(d_model, n_heads, d_ff, dropout)

        # Classification head
        self.classifier = np.random.randn(d_model, self.config.num_classes).astype(np.float32) * np.sqrt(2.0 / d_model)
        self.classifier_bias = np.zeros(self.config.num_classes, dtype=np.float32)

        # Positional encoding
        self.pos_encoding = positional_encoding(self.config.max_position, d_model)

        # Store attention weights for interpretability
        self.attention_weights = {}

    def forward(
        self,
        price_features: np.ndarray,
        volume_features: np.ndarray,
        order_flow_features: np.ndarray = None,
    ) -> Dict[str, np.ndarray]:
        """
        Forward pass.

        Args:
            price_features: [batch, seq, price_features]
            volume_features: [batch, seq, volume_features]
            order_flow_features: [batch, seq, order_flow_features]

        Returns:
            Dictionary with predictions and attention weights
        """
        batch_size = price_features.shape[0]
        seq_len = price_features.shape[1]

        # Concatenate all features
        if order_flow_features is None:
            order_flow_features = np.zeros(
                (batch_size, seq_len, self.config.order_flow_features),
                dtype=np.float32
            )

        combined = np.concatenate([price_features, volume_features, order_flow_features], axis=-1)

        # Input projection
        x = np.dot(combined, self.input_proj) + self.input_bias

        # Add positional encoding
        x = x + self.pos_encoding[:seq_len]

        # Process through price encoder
        price_repr = x.copy()
        for i, layer in enumerate(self.price_encoder):
            layer.training = self.training
            price_repr, attn_w = layer(price_repr)
            self.attention_weights[f'price_encoder_{i}'] = attn_w

        # Process through volume encoder
        volume_repr = x.copy()
        for i, layer in enumerate(self.volume_encoder):
            layer.training = self.training
            volume_repr, attn_w = layer(volume_repr)
            self.attention_weights[f'volume_encoder_{i}'] = attn_w

        # Cross-attention: price attending to volume
        self.cross_attention.training = self.training
        fused_repr, cross_attn_w = self.cross_attention(price_repr, volume_repr)
        self.attention_weights['cross_attention'] = cross_attn_w

        # Final encoding
        self.final_encoder.training = self.training
        final_repr, final_attn_w = self.final_encoder(fused_repr)
        self.attention_weights['final_encoder'] = final_attn_w

        # Global pooling (use last position or mean)
        pooled = final_repr[:, -1, :]  # Last position

        # Classification
        logits = np.dot(pooled, self.classifier) + self.classifier_bias

        # Softmax
        logits_max = np.max(logits, axis=-1, keepdims=True)
        exp_logits = np.exp(logits - logits_max)
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

        return {
            'logits': logits,
            'probabilities': probs,
            'prediction': np.argmax(probs, axis=-1),
            'confidence': np.max(probs, axis=-1),
            'price_representation': price_repr,
            'volume_representation': volume_repr,
            'fused_representation': fused_repr,
            'attention_weights': self.attention_weights.copy(),
        }

    def predict(self, price_features: np.ndarray, volume_features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions."""
        self.training = False
        output = self.forward(price_features, volume_features)
        return output['prediction'], output['confidence']

    def analyze_flow(
        self,
        price: np.ndarray,  # [batch, seq, 4] OHLC
        volume: np.ndarray,  # [batch, seq]
    ) -> Dict[str, Any]:
        """
        Full order flow analysis.

        Returns predictions plus detailed flow analysis.
        """
        self.training = False

        # Compute order flow features
        flow_features = self.flow_processor.compute_features(price, volume)

        # Prepare inputs
        price_feat = np.concatenate([
            price,  # OHLC
            np.expand_dims(flow_features['returns'], -1),
            np.expand_dims(flow_features['range_pct'], -1),
            np.expand_dims(flow_features['body_ratio'], -1),
        ], axis=-1)

        volume_feat = np.concatenate([
            np.expand_dims(volume, -1),
            np.expand_dims(flow_features['relative_volume'], -1),
            np.expand_dims(flow_features['large_volume'], -1),
        ], axis=-1)

        order_flow_feat = np.concatenate([
            np.expand_dims(flow_features['volume_delta'], -1),
            np.expand_dims(flow_features['cvd'], -1),
            np.expand_dims(flow_features['imbalance'], -1),
            np.expand_dims(flow_features['absorption'], -1),
        ], axis=-1)

        # Pad/truncate to expected dimensions
        price_feat = self._pad_features(price_feat, self.config.price_features)
        volume_feat = self._pad_features(volume_feat, self.config.volume_features)
        order_flow_feat = self._pad_features(order_flow_feat, self.config.order_flow_features)

        # Forward pass
        output = self.forward(price_feat, volume_feat, order_flow_feat)

        # Add flow analysis
        output['flow_features'] = flow_features
        output['flow_summary'] = {
            'cvd_trend': 'bullish' if flow_features['cvd'][:, -1].mean() > 0 else 'bearish',
            'imbalance_avg': float(np.mean(flow_features['imbalance'][:, -10:])),
            'large_volume_count': int(np.sum(flow_features['large_volume'][:, -10:])),
            'absorption_detected': bool(np.any(flow_features['absorption'][:, -5:] > 0.5)),
        }

        return output

    def _pad_features(self, x: np.ndarray, target_dim: int) -> np.ndarray:
        """Pad or truncate features to target dimension."""
        current_dim = x.shape[-1]
        if current_dim == target_dim:
            return x
        elif current_dim < target_dim:
            padding = np.zeros((*x.shape[:-1], target_dim - current_dim), dtype=np.float32)
            return np.concatenate([x, padding], axis=-1)
        else:
            return x[..., :target_dim]

    def get_attention_analysis(self) -> Dict[str, Any]:
        """Get attention weight analysis for interpretability."""
        analysis = {}

        for name, weights in self.attention_weights.items():
            if weights is not None:
                # Average across heads and batch
                avg_weights = np.mean(weights, axis=(0, 1))  # [query_len, key_len]

                # Find most attended positions
                last_pos_attention = avg_weights[-1] if len(avg_weights.shape) > 1 else avg_weights
                top_attended = np.argsort(last_pos_attention)[-5:][::-1]

                analysis[name] = {
                    'mean_attention': float(np.mean(weights)),
                    'max_attention': float(np.max(weights)),
                    'entropy': float(-np.sum(avg_weights * np.log(avg_weights + 1e-10))),
                    'top_attended_positions': top_attended.tolist(),
                }

        return analysis

    def train_mode(self):
        """Set to training mode."""
        self.training = True

    def eval_mode(self):
        """Set to evaluation mode."""
        self.training = False

    def save(self, path: str) -> None:
        """Save model."""
        state = {
            'config': self.config,
            'input_proj': self.input_proj,
            'input_bias': self.input_bias,
            'classifier': self.classifier,
            'classifier_bias': self.classifier_bias,
            'pos_encoding': self.pos_encoding,
        }
        with open(path, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"AttentionFlowNetwork saved to {path}")

    def load(self, path: str) -> None:
        """Load model."""
        with open(path, 'rb') as f:
            state = pickle.load(f)

        self.config = state['config']
        self.input_proj = state['input_proj']
        self.input_bias = state['input_bias']
        self.classifier = state['classifier']
        self.classifier_bias = state['classifier_bias']
        self.pos_encoding = state['pos_encoding']

        logger.info(f"AttentionFlowNetwork loaded from {path}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ['AttentionFlowNetwork', 'AttentionFlowConfig', 'OrderFlowProcessor']
