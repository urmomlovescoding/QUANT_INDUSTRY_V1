"""
QUANT_INDUSTRY_V1 WaveNet Temporal CNN

Dilated causal convolutions for multi-scale temporal pattern detection.
Based on WaveNet architecture adapted for financial time series.

Features:
- Dilated causal convolutions (no future leakage)
- Exponentially increasing dilation for large receptive fields
- Residual and skip connections
- Multi-scale pattern detection

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
class WaveNetConfig:
    """WaveNet configuration."""
    # Input
    input_channels: int = 96
    sequence_length: int = 120

    # Architecture
    residual_channels: int = 64
    skip_channels: int = 128
    output_channels: int = 3  # Direction classes
    num_layers: int = 8  # Layers per block
    num_blocks: int = 2  # Stacked blocks
    kernel_size: int = 3

    # Regularization
    dropout_rate: float = 0.1

    # Dilation pattern
    dilation_base: int = 2  # Dilation grows as base^layer

    @property
    def receptive_field(self) -> int:
        """Calculate receptive field size."""
        rf = 1
        for _ in range(self.num_blocks):
            for i in range(self.num_layers):
                dilation = self.dilation_base ** i
                rf += (self.kernel_size - 1) * dilation
        return rf


# =============================================================================
# WAVENET COMPONENTS
# =============================================================================

def causal_conv1d(
    x: np.ndarray,
    kernel: np.ndarray,
    dilation: int = 1,
) -> np.ndarray:
    """
    Causal 1D convolution with dilation.

    Args:
        x: Input [batch, channels, length]
        kernel: Weights [out_channels, in_channels, kernel_size]
        dilation: Dilation factor

    Returns:
        Output [batch, out_channels, length]
    """
    batch_size, in_channels, length = x.shape
    out_channels, _, kernel_size = kernel.shape

    # Calculate padding for causal conv
    padding = (kernel_size - 1) * dilation

    # Pad input (left padding only for causal)
    x_padded = np.pad(x, ((0, 0), (0, 0), (padding, 0)), mode='constant')

    # Output array
    output = np.zeros((batch_size, out_channels, length))

    # Perform convolution
    for b in range(batch_size):
        for oc in range(out_channels):
            for t in range(length):
                val = 0.0
                for ic in range(in_channels):
                    for k in range(kernel_size):
                        # Dilated index
                        idx = t + padding - k * dilation
                        if 0 <= idx < x_padded.shape[2]:
                            val += x_padded[b, ic, idx] * kernel[oc, ic, kernel_size - 1 - k]
                output[b, oc, t] = val

    return output


def gated_activation(x: np.ndarray) -> np.ndarray:
    """Gated activation: tanh(x1) * sigmoid(x2)."""
    half = x.shape[1] // 2
    tanh_part = np.tanh(x[:, :half, :])
    sigmoid_part = 1 / (1 + np.exp(-x[:, half:, :]))
    return tanh_part * sigmoid_part


class CausalConv1D:
    """Causal 1D convolution layer."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int = 1,
    ):
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.dilation = dilation

        # Initialize weights
        fan_in = in_channels * kernel_size
        std = np.sqrt(2.0 / fan_in)
        self.weight = np.random.randn(out_channels, in_channels, kernel_size).astype(np.float32) * std
        self.bias = np.zeros(out_channels, dtype=np.float32)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        output = causal_conv1d(x, self.weight, self.dilation)
        return output + self.bias.reshape(1, -1, 1)


class Conv1x1:
    """1x1 convolution for channel transformation."""

    def __init__(self, in_channels: int, out_channels: int):
        self.in_channels = in_channels
        self.out_channels = out_channels

        std = np.sqrt(2.0 / in_channels)
        self.weight = np.random.randn(out_channels, in_channels).astype(np.float32) * std
        self.bias = np.zeros(out_channels, dtype=np.float32)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        # x: [batch, channels, length]
        # Reshape for matmul
        batch, channels, length = x.shape
        x_flat = x.transpose(0, 2, 1).reshape(-1, channels)
        output = np.dot(x_flat, self.weight.T) + self.bias
        return output.reshape(batch, length, self.out_channels).transpose(0, 2, 1)


class WaveNetResidualBlock:
    """
    WaveNet residual block with gated activation.

    dilated_conv -> gated_activation -> 1x1 conv -> residual + skip
    """

    def __init__(
        self,
        residual_channels: int,
        skip_channels: int,
        kernel_size: int,
        dilation: int,
        dropout_rate: float = 0.1,
    ):
        self.residual_channels = residual_channels
        self.skip_channels = skip_channels
        self.dilation = dilation
        self.dropout_rate = dropout_rate

        # Dilated convolution (2x channels for gated activation)
        self.dilated_conv = CausalConv1D(
            residual_channels,
            residual_channels * 2,
            kernel_size,
            dilation,
        )

        # 1x1 convolutions for residual and skip
        self.residual_conv = Conv1x1(residual_channels, residual_channels)
        self.skip_conv = Conv1x1(residual_channels, skip_channels)

        self.training = True

    def __call__(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Forward pass.

        Args:
            x: Input [batch, residual_channels, length]

        Returns:
            residual: Output for next layer
            skip: Skip connection output
        """
        # Dilated convolution
        h = self.dilated_conv(x)

        # Gated activation
        h = gated_activation(h)

        # Dropout
        if self.training and self.dropout_rate > 0:
            mask = np.random.binomial(1, 1 - self.dropout_rate, h.shape) / (1 - self.dropout_rate)
            h = h * mask

        # Residual connection
        residual = self.residual_conv(h) + x

        # Skip connection
        skip = self.skip_conv(h)

        return residual, skip


class WaveNetModel:
    """
    WaveNet model for financial time series.

    Architecture:
    1. Input embedding (1x1 conv)
    2. Stacked residual blocks with increasing dilation
    3. Skip connection aggregation
    4. Output layers (ReLU + 1x1 + ReLU + 1x1)
    """

    def __init__(self, config: WaveNetConfig = None):
        self.config = config or WaveNetConfig()
        self.training = True

        # Input embedding
        self.input_conv = Conv1x1(
            self.config.input_channels,
            self.config.residual_channels,
        )

        # Residual blocks
        self.blocks = []
        for block_idx in range(self.config.num_blocks):
            for layer_idx in range(self.config.num_layers):
                dilation = self.config.dilation_base ** layer_idx
                self.blocks.append(WaveNetResidualBlock(
                    self.config.residual_channels,
                    self.config.skip_channels,
                    self.config.kernel_size,
                    dilation,
                    self.config.dropout_rate,
                ))

        # Output layers
        self.output_conv1 = Conv1x1(self.config.skip_channels, self.config.skip_channels)
        self.output_conv2 = Conv1x1(self.config.skip_channels, self.config.output_channels)

        # Store intermediate outputs for analysis
        self.layer_outputs = []
        self.skip_outputs = []

    def forward(self, x: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Forward pass.

        Args:
            x: Input [batch, length, features] or [batch, features, length]

        Returns:
            Dictionary with predictions and intermediate outputs
        """
        # Ensure correct shape [batch, channels, length]
        if x.ndim == 2:
            x = np.expand_dims(x, 0)

        if x.shape[1] == self.config.sequence_length:
            x = x.transpose(0, 2, 1)

        batch_size = x.shape[0]
        length = x.shape[2]

        # Input embedding
        h = self.input_conv(x)

        # Process through residual blocks
        skip_sum = np.zeros((batch_size, self.config.skip_channels, length))
        self.layer_outputs = []
        self.skip_outputs = []

        for block in self.blocks:
            block.training = self.training
            h, skip = block(h)
            skip_sum += skip
            self.layer_outputs.append(h.copy())
            self.skip_outputs.append(skip.copy())

        # Output processing
        h = np.maximum(skip_sum, 0)  # ReLU
        h = self.output_conv1(h)
        h = np.maximum(h, 0)  # ReLU
        logits = self.output_conv2(h)

        # Apply softmax for probabilities
        logits_max = np.max(logits, axis=1, keepdims=True)
        exp_logits = np.exp(logits - logits_max)
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

        # Get prediction at last timestep
        final_logits = logits[:, :, -1]
        final_probs = probs[:, :, -1]

        return {
            'logits': logits,
            'probabilities': probs,
            'final_logits': final_logits,
            'final_probabilities': final_probs,
            'prediction': np.argmax(final_probs, axis=1),
            'confidence': np.max(final_probs, axis=1),
            'layer_outputs': self.layer_outputs,
        }

    def predict(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make predictions.

        Returns:
            predictions: Class predictions
            confidences: Prediction confidences
        """
        self.training = False
        output = self.forward(x)
        return output['prediction'], output['confidence']

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Get probability distribution over classes."""
        self.training = False
        output = self.forward(x)
        return output['final_probabilities']

    def get_receptive_field_analysis(self, x: np.ndarray) -> Dict[str, Any]:
        """
        Analyze which input timesteps influence the prediction most.
        """
        self.training = False
        output = self.forward(x)

        # Compute gradient-like importance
        # Simplified: use skip connection magnitudes
        skip_importance = np.zeros((len(self.skip_outputs), x.shape[2] if x.ndim > 2 else x.shape[1]))

        for i, skip in enumerate(self.skip_outputs):
            # Average across channels and batch
            skip_importance[i] = np.mean(np.abs(skip), axis=(0, 1))

        # Layer-wise dilation patterns
        dilations = []
        for block_idx in range(self.config.num_blocks):
            for layer_idx in range(self.config.num_layers):
                dilations.append(self.config.dilation_base ** layer_idx)

        return {
            'skip_importance': skip_importance,
            'dilations': dilations,
            'receptive_field': self.config.receptive_field,
            'effective_context': min(self.config.receptive_field, x.shape[-1]),
        }

    def train_mode(self):
        """Set to training mode."""
        self.training = True
        for block in self.blocks:
            block.training = True

    def eval_mode(self):
        """Set to evaluation mode."""
        self.training = False
        for block in self.blocks:
            block.training = False

    def save(self, path: str) -> None:
        """Save model."""
        state = {
            'config': self.config,
            'input_conv': {'weight': self.input_conv.weight, 'bias': self.input_conv.bias},
            'output_conv1': {'weight': self.output_conv1.weight, 'bias': self.output_conv1.bias},
            'output_conv2': {'weight': self.output_conv2.weight, 'bias': self.output_conv2.bias},
            'blocks': [
                {
                    'dilated_conv': {'weight': b.dilated_conv.weight, 'bias': b.dilated_conv.bias},
                    'residual_conv': {'weight': b.residual_conv.weight, 'bias': b.residual_conv.bias},
                    'skip_conv': {'weight': b.skip_conv.weight, 'bias': b.skip_conv.bias},
                }
                for b in self.blocks
            ],
        }
        with open(path, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"WaveNet model saved to {path}")

    def load(self, path: str) -> None:
        """Load model."""
        with open(path, 'rb') as f:
            state = pickle.load(f)

        self.config = state['config']
        self.input_conv.weight = state['input_conv']['weight']
        self.input_conv.bias = state['input_conv']['bias']
        self.output_conv1.weight = state['output_conv1']['weight']
        self.output_conv1.bias = state['output_conv1']['bias']
        self.output_conv2.weight = state['output_conv2']['weight']
        self.output_conv2.bias = state['output_conv2']['bias']

        for i, block_state in enumerate(state['blocks']):
            self.blocks[i].dilated_conv.weight = block_state['dilated_conv']['weight']
            self.blocks[i].dilated_conv.bias = block_state['dilated_conv']['bias']
            self.blocks[i].residual_conv.weight = block_state['residual_conv']['weight']
            self.blocks[i].residual_conv.bias = block_state['residual_conv']['bias']
            self.blocks[i].skip_conv.weight = block_state['skip_conv']['weight']
            self.blocks[i].skip_conv.bias = block_state['skip_conv']['bias']

        logger.info(f"WaveNet model loaded from {path}")

    def count_parameters(self) -> int:
        """Count total parameters."""
        total = 0
        total += self.input_conv.weight.size + self.input_conv.bias.size
        total += self.output_conv1.weight.size + self.output_conv1.bias.size
        total += self.output_conv2.weight.size + self.output_conv2.bias.size

        for block in self.blocks:
            total += block.dilated_conv.weight.size + block.dilated_conv.bias.size
            total += block.residual_conv.weight.size + block.residual_conv.bias.size
            total += block.skip_conv.weight.size + block.skip_conv.bias.size

        return total


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ['WaveNetModel', 'WaveNetConfig']
