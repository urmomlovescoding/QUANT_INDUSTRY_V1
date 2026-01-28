"""
QUANT_INDUSTRY_V1 Temporal Fusion Transformer

State-of-the-art architecture for multi-horizon time series forecasting.
Based on "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting"

Features:
- Variable selection networks for feature importance
- Gated residual networks for skip connections
- Multi-head attention for temporal patterns
- Quantile predictions for uncertainty
- Interpretable attention weights

Pure NumPy implementation (no PyTorch/TensorFlow required).
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import pickle
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TFTConfig:
    """Temporal Fusion Transformer configuration."""
    # Input dimensions
    num_features: int = 96
    num_static_features: int = 8
    num_known_features: int = 16  # Known future inputs (e.g., time features)

    # Architecture
    hidden_size: int = 256
    num_attention_heads: int = 4
    num_encoder_layers: int = 2
    num_decoder_layers: int = 2
    dropout_rate: float = 0.1

    # Sequence lengths
    encoder_length: int = 60  # Past context
    decoder_length: int = 12  # Future horizon

    # Output
    num_quantiles: int = 3  # [0.1, 0.5, 0.9]
    quantiles: List[float] = field(default_factory=lambda: [0.1, 0.5, 0.9])

    # Training
    learning_rate: float = 0.001
    batch_size: int = 64
    max_gradient_norm: float = 1.0


# =============================================================================
# NEURAL NETWORK PRIMITIVES (Pure NumPy)
# =============================================================================

class NumpyModule:
    """Base class for NumPy neural network modules."""

    def __init__(self):
        self.training = True
        self.params = {}
        self.grads = {}
        self.cache = {}

    def __call__(self, *args, **kwargs):
        return self.forward(*args, **kwargs)

    def forward(self, x: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def train(self):
        self.training = True

    def eval(self):
        self.training = False


def glorot_uniform(shape: Tuple[int, ...]) -> np.ndarray:
    """Glorot/Xavier uniform initialization."""
    fan_in = shape[0] if len(shape) > 1 else shape[0]
    fan_out = shape[1] if len(shape) > 1 else shape[0]
    limit = np.sqrt(6 / (fan_in + fan_out))
    return np.random.uniform(-limit, limit, shape).astype(np.float32)


def layer_norm(x: np.ndarray, gamma: np.ndarray, beta: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Layer normalization."""
    mean = np.mean(x, axis=-1, keepdims=True)
    var = np.var(x, axis=-1, keepdims=True)
    x_norm = (x - mean) / np.sqrt(var + eps)
    return gamma * x_norm + beta


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax."""
    x_max = np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x - x_max)
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


def gelu(x: np.ndarray) -> np.ndarray:
    """Gaussian Error Linear Unit activation."""
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))


def dropout(x: np.ndarray, rate: float, training: bool = True) -> np.ndarray:
    """Dropout regularization."""
    if not training or rate == 0:
        return x
    mask = np.random.binomial(1, 1 - rate, x.shape) / (1 - rate)
    return x * mask


class Linear(NumpyModule):
    """Linear (fully connected) layer."""

    def __init__(self, in_features: int, out_features: int, bias: bool = True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.use_bias = bias

        self.params['weight'] = glorot_uniform((in_features, out_features))
        if bias:
            self.params['bias'] = np.zeros(out_features, dtype=np.float32)

    def forward(self, x: np.ndarray) -> np.ndarray:
        self.cache['input'] = x
        output = np.dot(x, self.params['weight'])
        if self.use_bias:
            output += self.params['bias']
        return output


class LayerNorm(NumpyModule):
    """Layer normalization."""

    def __init__(self, normalized_shape: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.params['gamma'] = np.ones(normalized_shape, dtype=np.float32)
        self.params['beta'] = np.zeros(normalized_shape, dtype=np.float32)

    def forward(self, x: np.ndarray) -> np.ndarray:
        return layer_norm(x, self.params['gamma'], self.params['beta'], self.eps)


# =============================================================================
# TFT COMPONENTS
# =============================================================================

class GatedLinearUnit(NumpyModule):
    """
    Gated Linear Unit (GLU).

    Splits input in half, applies sigmoid to one half as gate.
    """

    def __init__(self, input_size: int, hidden_size: int, dropout_rate: float = 0.0):
        super().__init__()
        self.fc1 = Linear(input_size, hidden_size * 2)
        self.dropout_rate = dropout_rate

    def forward(self, x: np.ndarray) -> np.ndarray:
        x = self.fc1(x)
        x = dropout(x, self.dropout_rate, self.training)

        # Split and apply gate
        value, gate = np.split(x, 2, axis=-1)
        gate = 1 / (1 + np.exp(-gate))  # Sigmoid
        return value * gate


class GatedResidualNetwork(NumpyModule):
    """
    Gated Residual Network (GRN).

    Core building block of TFT with skip connections and gating.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        output_size: int = None,
        context_size: int = None,
        dropout_rate: float = 0.1,
    ):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size or input_size
        self.context_size = context_size

        # Main layers
        self.fc1 = Linear(input_size, hidden_size)
        self.fc2 = Linear(hidden_size, self.output_size * 2)  # For GLU

        # Context projection
        if context_size is not None:
            self.context_fc = Linear(context_size, hidden_size, bias=False)
        else:
            self.context_fc = None

        # Skip connection
        if input_size != self.output_size:
            self.skip_fc = Linear(input_size, self.output_size)
        else:
            self.skip_fc = None

        # Layer norm
        self.layer_norm = LayerNorm(self.output_size)
        self.dropout_rate = dropout_rate

    def forward(self, x: np.ndarray, context: np.ndarray = None) -> np.ndarray:
        # Skip connection
        skip = x if self.skip_fc is None else self.skip_fc(x)

        # First layer with ELU activation
        hidden = self.fc1(x)

        # Add context if provided
        if context is not None and self.context_fc is not None:
            context_proj = self.context_fc(context)
            if context_proj.ndim < hidden.ndim:
                context_proj = np.expand_dims(context_proj, axis=1)
            hidden = hidden + context_proj

        # ELU activation
        hidden = np.where(hidden > 0, hidden, np.exp(hidden) - 1)

        # Second layer with GLU
        hidden = self.fc2(hidden)
        hidden = dropout(hidden, self.dropout_rate, self.training)

        # GLU: split and gate
        value, gate = np.split(hidden, 2, axis=-1)
        gate = 1 / (1 + np.exp(-gate))  # Sigmoid
        hidden = value * gate

        # Residual connection and layer norm
        return self.layer_norm(skip + hidden)


class VariableSelectionNetwork(NumpyModule):
    """
    Variable Selection Network.

    Learns feature importance weights for interpretability.
    """

    def __init__(
        self,
        input_size: int,
        num_inputs: int,
        hidden_size: int,
        context_size: int = None,
        dropout_rate: float = 0.1,
    ):
        super().__init__()
        self.input_size = input_size
        self.num_inputs = num_inputs
        self.hidden_size = hidden_size

        # GRN for each input variable
        self.variable_grns = [
            GatedResidualNetwork(input_size, hidden_size, hidden_size, dropout_rate=dropout_rate)
            for _ in range(num_inputs)
        ]

        # GRN for variable weights
        self.weight_grn = GatedResidualNetwork(
            input_size * num_inputs,
            hidden_size,
            num_inputs,
            context_size=context_size,
            dropout_rate=dropout_rate,
        )

    def forward(self, x: np.ndarray, context: np.ndarray = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Args:
            x: Input tensor [batch, time, num_inputs, input_size]
            context: Optional context [batch, context_size]

        Returns:
            selected: Selected features [batch, time, hidden_size]
            weights: Variable importance weights [batch, time, num_inputs]
        """
        batch_size = x.shape[0]
        time_steps = x.shape[1] if x.ndim > 2 else 1

        # Flatten for weight computation
        if x.ndim == 4:
            x_flat = x.reshape(batch_size, time_steps, -1)
        else:
            x_flat = x.reshape(batch_size, -1)
            time_steps = 1

        # Compute variable weights
        weights = self.weight_grn(x_flat, context)
        weights = softmax(weights, axis=-1)

        # Process each variable
        if x.ndim == 4:
            processed = []
            for i, grn in enumerate(self.variable_grns):
                var_input = x[:, :, i, :]
                processed.append(grn(var_input))
            processed = np.stack(processed, axis=2)  # [batch, time, num_inputs, hidden]

            # Weighted sum
            weights_expanded = np.expand_dims(weights, axis=-1)
            selected = np.sum(processed * weights_expanded, axis=2)
        else:
            # Handle 2D input
            processed = []
            for i, grn in enumerate(self.variable_grns):
                var_input = x[:, i*self.input_size:(i+1)*self.input_size]
                processed.append(grn(var_input))
            processed = np.stack(processed, axis=1)

            weights_expanded = np.expand_dims(weights, axis=-1)
            selected = np.sum(processed * weights_expanded, axis=1)

        return selected, weights


class InterpretableMultiHeadAttention(NumpyModule):
    """
    Interpretable Multi-Head Attention.

    Modified attention that shares values across heads for interpretability.
    """

    def __init__(self, hidden_size: int, num_heads: int, dropout_rate: float = 0.1):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.dropout_rate = dropout_rate

        assert hidden_size % num_heads == 0, "hidden_size must be divisible by num_heads"

        # Q, K for each head, V shared
        self.q_proj = Linear(hidden_size, hidden_size)
        self.k_proj = Linear(hidden_size, hidden_size)
        self.v_proj = Linear(hidden_size, hidden_size)
        self.out_proj = Linear(hidden_size, hidden_size)

    def forward(
        self,
        query: np.ndarray,
        key: np.ndarray,
        value: np.ndarray,
        mask: np.ndarray = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Args:
            query: [batch, query_len, hidden]
            key: [batch, key_len, hidden]
            value: [batch, key_len, hidden]
            mask: Optional attention mask

        Returns:
            output: [batch, query_len, hidden]
            attention_weights: [batch, num_heads, query_len, key_len]
        """
        batch_size = query.shape[0]
        query_len = query.shape[1]
        key_len = key.shape[1]

        # Project Q, K, V
        Q = self.q_proj(query)
        K = self.k_proj(key)
        V = self.v_proj(value)

        # Reshape for multi-head attention
        Q = Q.reshape(batch_size, query_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        K = K.reshape(batch_size, key_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        V = V.reshape(batch_size, key_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)

        # Scaled dot-product attention
        scale = np.sqrt(self.head_dim)
        scores = np.matmul(Q, K.transpose(0, 1, 3, 2)) / scale

        # Apply mask if provided
        if mask is not None:
            scores = scores + mask * -1e9

        attention_weights = softmax(scores, axis=-1)
        attention_weights = dropout(attention_weights, self.dropout_rate, self.training)

        # Apply attention to values
        context = np.matmul(attention_weights, V)

        # Reshape back
        context = context.transpose(0, 2, 1, 3).reshape(batch_size, query_len, self.hidden_size)

        output = self.out_proj(context)

        return output, attention_weights


class TemporalSelfAttention(NumpyModule):
    """
    Temporal self-attention layer with interpretable attention.
    """

    def __init__(self, hidden_size: int, num_heads: int, dropout_rate: float = 0.1):
        super().__init__()
        self.attention = InterpretableMultiHeadAttention(hidden_size, num_heads, dropout_rate)
        self.layer_norm = LayerNorm(hidden_size)
        self.grn = GatedResidualNetwork(hidden_size, hidden_size, hidden_size, dropout_rate=dropout_rate)

    def forward(self, x: np.ndarray, mask: np.ndarray = None) -> Tuple[np.ndarray, np.ndarray]:
        # Self-attention
        attn_output, attn_weights = self.attention(x, x, x, mask)

        # Residual and norm
        x = self.layer_norm(x + attn_output)

        # GRN
        x = self.grn(x)

        return x, attn_weights


# =============================================================================
# TEMPORAL FUSION TRANSFORMER
# =============================================================================

class TemporalFusionTransformer(NumpyModule):
    """
    Temporal Fusion Transformer for time series forecasting.

    Architecture:
    1. Variable Selection Networks for feature importance
    2. LSTM Encoder-Decoder for temporal processing
    3. Gated skip connections
    4. Interpretable multi-head attention
    5. Quantile output for uncertainty estimation
    """

    def __init__(self, config: TFTConfig = None):
        super().__init__()
        self.config = config or TFTConfig()

        hidden = self.config.hidden_size

        # Static variable selection
        self.static_vsn = VariableSelectionNetwork(
            input_size=1,
            num_inputs=self.config.num_static_features,
            hidden_size=hidden,
        )

        # Static context encoders
        self.static_context_grn = GatedResidualNetwork(hidden, hidden, hidden)
        self.static_enrichment_grn = GatedResidualNetwork(hidden, hidden, hidden)

        # Temporal variable selection (encoder)
        self.encoder_vsn = VariableSelectionNetwork(
            input_size=1,
            num_inputs=self.config.num_features,
            hidden_size=hidden,
            context_size=hidden,
        )

        # Temporal variable selection (decoder)
        self.decoder_vsn = VariableSelectionNetwork(
            input_size=1,
            num_inputs=self.config.num_known_features,
            hidden_size=hidden,
            context_size=hidden,
        )

        # LSTM Encoder
        self.encoder_lstm_hidden = np.zeros((1, hidden))
        self.encoder_lstm_cell = np.zeros((1, hidden))
        self.encoder_lstm_fc = Linear(hidden * 2, hidden * 4)  # For LSTM gates

        # LSTM Decoder
        self.decoder_lstm_hidden = np.zeros((1, hidden))
        self.decoder_lstm_cell = np.zeros((1, hidden))
        self.decoder_lstm_fc = Linear(hidden * 2, hidden * 4)

        # Gated skip connection
        self.encoder_grn = GatedResidualNetwork(hidden, hidden, hidden)
        self.decoder_grn = GatedResidualNetwork(hidden, hidden, hidden)

        # Static enrichment
        self.static_enrichment = GatedResidualNetwork(
            hidden, hidden, hidden, context_size=hidden
        )

        # Temporal self-attention
        self.attention = TemporalSelfAttention(
            hidden, self.config.num_attention_heads, self.config.dropout_rate
        )

        # Position-wise feed-forward
        self.ff_grn = GatedResidualNetwork(hidden, hidden, hidden)

        # Output layer
        self.output_fc = Linear(hidden, self.config.num_quantiles)

        # Layer norms
        self.pre_attention_norm = LayerNorm(hidden)
        self.pre_output_norm = LayerNorm(hidden)

        # Store for interpretability
        self.variable_importances = {}
        self.attention_weights = None

    def _lstm_step(
        self,
        x: np.ndarray,
        hidden: np.ndarray,
        cell: np.ndarray,
        fc: Linear,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Single LSTM step."""
        combined = np.concatenate([x, hidden], axis=-1)
        gates = fc(combined)

        # Split gates
        i, f, g, o = np.split(gates, 4, axis=-1)

        # Apply activations
        i = 1 / (1 + np.exp(-i))  # Sigmoid
        f = 1 / (1 + np.exp(-f))  # Sigmoid
        g = np.tanh(g)
        o = 1 / (1 + np.exp(-o))  # Sigmoid

        # Update cell and hidden
        new_cell = f * cell + i * g
        new_hidden = o * np.tanh(new_cell)

        return new_hidden, new_cell

    def _encode(
        self,
        x: np.ndarray,
        static_context: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Encode past observations."""
        batch_size = x.shape[0]
        seq_len = x.shape[1]
        hidden = self.config.hidden_size

        # Variable selection
        selected, var_weights = self.encoder_vsn(x, static_context)
        self.variable_importances['encoder'] = var_weights

        # LSTM encoding
        h = np.zeros((batch_size, hidden))
        c = np.zeros((batch_size, hidden))
        outputs = []

        for t in range(seq_len):
            h, c = self._lstm_step(selected[:, t], h, c, self.encoder_lstm_fc)
            outputs.append(h)

        lstm_output = np.stack(outputs, axis=1)

        # Gated skip connection
        encoder_output = self.encoder_grn(lstm_output) + selected

        return encoder_output, (h, c)

    def _decode(
        self,
        known_inputs: np.ndarray,
        encoder_output: np.ndarray,
        encoder_state: Tuple[np.ndarray, np.ndarray],
        static_context: np.ndarray,
    ) -> np.ndarray:
        """Decode future predictions."""
        batch_size = known_inputs.shape[0]
        seq_len = known_inputs.shape[1]
        hidden = self.config.hidden_size

        # Variable selection for known future inputs
        selected, var_weights = self.decoder_vsn(known_inputs, static_context)
        self.variable_importances['decoder'] = var_weights

        # LSTM decoding
        h, c = encoder_state
        outputs = []

        for t in range(seq_len):
            h, c = self._lstm_step(selected[:, t], h, c, self.decoder_lstm_fc)
            outputs.append(h)

        lstm_output = np.stack(outputs, axis=1)

        # Gated skip connection
        decoder_output = self.decoder_grn(lstm_output) + selected

        return decoder_output

    def forward(
        self,
        past_inputs: np.ndarray,
        known_future_inputs: np.ndarray = None,
        static_inputs: np.ndarray = None,
    ) -> Dict[str, np.ndarray]:
        """
        Forward pass.

        Args:
            past_inputs: [batch, encoder_length, num_features]
            known_future_inputs: [batch, decoder_length, num_known_features]
            static_inputs: [batch, num_static_features]

        Returns:
            Dictionary with:
            - predictions: [batch, decoder_length, num_quantiles]
            - attention_weights: [batch, heads, decoder_length, total_length]
            - variable_importances: dict of importance weights
        """
        batch_size = past_inputs.shape[0]

        # Process static features
        if static_inputs is not None:
            static_reshaped = static_inputs.reshape(batch_size, self.config.num_static_features, 1)
            static_selected, static_weights = self.static_vsn(static_reshaped)
            self.variable_importances['static'] = static_weights
            static_context = self.static_context_grn(static_selected)
            static_enrichment = self.static_enrichment_grn(static_selected)
        else:
            static_context = np.zeros((batch_size, self.config.hidden_size))
            static_enrichment = np.zeros((batch_size, self.config.hidden_size))

        # Reshape past inputs for variable selection
        past_reshaped = past_inputs.reshape(
            batch_size,
            past_inputs.shape[1],
            self.config.num_features,
            1
        )

        # Encode past
        encoder_output, encoder_state = self._encode(past_reshaped, static_context)

        # Decode future
        if known_future_inputs is not None:
            known_reshaped = known_future_inputs.reshape(
                batch_size,
                known_future_inputs.shape[1],
                self.config.num_known_features,
                1
            )
            decoder_output = self._decode(
                known_reshaped, encoder_output, encoder_state, static_context
            )
        else:
            # Auto-regressive decoding
            decoder_length = self.config.decoder_length
            decoder_output = np.zeros((batch_size, decoder_length, self.config.hidden_size))
            h, c = encoder_state

            for t in range(decoder_length):
                h, c = self._lstm_step(h, h, c, self.decoder_lstm_fc)
                decoder_output[:, t] = h

        # Concatenate encoder and decoder outputs for attention
        temporal_features = np.concatenate([encoder_output, decoder_output], axis=1)

        # Static enrichment
        static_expanded = np.expand_dims(static_enrichment, axis=1)
        temporal_features = self.static_enrichment(temporal_features, static_expanded)

        # Pre-attention normalization
        temporal_features = self.pre_attention_norm(temporal_features)

        # Create causal mask for decoder
        total_len = temporal_features.shape[1]
        decoder_start = encoder_output.shape[1]
        mask = np.zeros((total_len, total_len))
        # Decoder can only attend to encoder + past decoder positions
        for i in range(decoder_start, total_len):
            mask[i, i+1:] = 1

        # Self-attention
        attn_output, attn_weights = self.attention(temporal_features, mask)
        self.attention_weights = attn_weights

        # Position-wise feed-forward
        ff_output = self.ff_grn(attn_output)

        # Get decoder positions only
        decoder_features = ff_output[:, decoder_start:]

        # Output normalization
        decoder_features = self.pre_output_norm(decoder_features)

        # Quantile predictions
        predictions = self.output_fc(decoder_features)

        return {
            'predictions': predictions,
            'attention_weights': attn_weights,
            'variable_importances': self.variable_importances.copy(),
            'encoder_output': encoder_output,
            'decoder_output': decoder_output,
        }

    def predict(
        self,
        past_inputs: np.ndarray,
        known_future_inputs: np.ndarray = None,
        static_inputs: np.ndarray = None,
    ) -> np.ndarray:
        """
        Make predictions (inference mode).

        Returns median prediction (quantile 0.5).
        """
        self.eval()
        output = self.forward(past_inputs, known_future_inputs, static_inputs)

        # Return median prediction (middle quantile)
        median_idx = len(self.config.quantiles) // 2
        return output['predictions'][:, :, median_idx]

    def get_feature_importance(self) -> Dict[str, np.ndarray]:
        """Get learned feature importance weights."""
        return self.variable_importances.copy()

    def get_attention_patterns(self) -> np.ndarray:
        """Get attention patterns for interpretability."""
        return self.attention_weights

    def save(self, path: str) -> None:
        """Save model parameters."""
        state = {
            'config': self.config,
            'params': self._collect_params(),
        }
        with open(path, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"TFT model saved to {path}")

    def load(self, path: str) -> None:
        """Load model parameters."""
        with open(path, 'rb') as f:
            state = pickle.load(f)
        self.config = state['config']
        self._load_params(state['params'])
        logger.info(f"TFT model loaded from {path}")

    def _collect_params(self) -> Dict[str, Any]:
        """Collect all parameters for saving."""
        params = {}
        for name in dir(self):
            obj = getattr(self, name)
            if isinstance(obj, NumpyModule):
                params[name] = obj.params
        return params

    def _load_params(self, params: Dict[str, Any]) -> None:
        """Load parameters."""
        for name, param_dict in params.items():
            if hasattr(self, name):
                obj = getattr(self, name)
                if isinstance(obj, NumpyModule):
                    obj.params = param_dict


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ['TemporalFusionTransformer', 'TFTConfig']
