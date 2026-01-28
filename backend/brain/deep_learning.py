"""
QUANT INDUSTRY - Deep Learning Trading Engine
LSTM, Transformer, and Attention-based Models

Features:
- LSTM for sequence modeling
- Transformer encoder for feature extraction
- Multi-head self-attention
- Temporal attention for time series
- GPU acceleration support
"""

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Deep Learning Libraries
try:
    import torch
    import torch.nn.functional as F
    from torch import nn, optim
    from torch.utils.data import DataLoader, Dataset, TensorDataset
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class DeepLearningConfig:
    """Deep Learning Configuration"""
    # LSTM parameters
    lstm_hidden_size: int = 128
    lstm_num_layers: int = 2
    lstm_dropout: float = 0.2
    lstm_bidirectional: bool = True

    # Transformer parameters
    transformer_d_model: int = 128
    transformer_nhead: int = 8
    transformer_num_layers: int = 4
    transformer_dim_feedforward: int = 512
    transformer_dropout: float = 0.1

    # Attention parameters
    attention_heads: int = 8
    attention_dropout: float = 0.1

    # Training parameters
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    sequence_length: int = 60  # 60 time steps
    prediction_horizon: int = 5  # Predict 5 steps ahead

    # Regularization
    weight_decay: float = 1e-5
    label_smoothing: float = 0.1
    gradient_clip: float = 1.0

    # Early stopping
    patience: int = 15
    min_delta: float = 0.0001


class PositionalEncoding(nn.Module):
    """Positional encoding for Transformer"""

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))

        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)

        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape [seq_len, batch_size, d_model]
        """
        x = x + self.pe[:x.size(0)]
        return self.dropout(x)


class MultiHeadAttention(nn.Module):
    """Multi-Head Self-Attention Layer"""

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.d_k)

    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size = query.size(0)

        # Linear projections
        Q = self.W_q(query).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        K = self.W_k(key).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = self.W_v(value).view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)

        # Attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)

        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # Apply attention to values
        context = torch.matmul(attention_weights, V)

        # Concatenate heads
        context = context.transpose(1, 2).contiguous().view(batch_size, -1, self.d_model)

        # Final linear projection
        output = self.W_o(context)

        return output, attention_weights


class TemporalAttention(nn.Module):
    """Temporal Attention for Time Series"""

    def __init__(self, hidden_size: int):
        super().__init__()
        self.attention = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.Tanh(),
            nn.Linear(hidden_size // 2, 1)
        )

    def forward(self, lstm_output: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            lstm_output: [batch_size, seq_len, hidden_size]

        Returns:
            context: [batch_size, hidden_size]
            attention_weights: [batch_size, seq_len]
        """
        # Calculate attention scores
        attention_scores = self.attention(lstm_output).squeeze(-1)  # [batch, seq_len]
        attention_weights = F.softmax(attention_scores, dim=1)

        # Weighted sum
        context = torch.bmm(attention_weights.unsqueeze(1), lstm_output).squeeze(1)

        return context, attention_weights


class LSTMModel(nn.Module):
    """LSTM Model for Time Series Prediction"""

    def __init__(self, input_size: int, config: DeepLearningConfig, num_classes: int = 3):
        super().__init__()
        self.config = config

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=config.lstm_hidden_size,
            num_layers=config.lstm_num_layers,
            dropout=config.lstm_dropout if config.lstm_num_layers > 1 else 0,
            bidirectional=config.lstm_bidirectional,
            batch_first=True
        )

        # Temporal attention
        lstm_output_size = config.lstm_hidden_size * (2 if config.lstm_bidirectional else 1)
        self.attention = TemporalAttention(lstm_output_size)

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(lstm_output_size, config.lstm_hidden_size),
            nn.ReLU(),
            nn.Dropout(config.lstm_dropout),
            nn.Linear(config.lstm_hidden_size, num_classes)
        )

        # Regression head (for price prediction)
        self.regressor = nn.Sequential(
            nn.Linear(lstm_output_size, config.lstm_hidden_size),
            nn.ReLU(),
            nn.Dropout(config.lstm_dropout),
            nn.Linear(config.lstm_hidden_size, 1)
        )

    def forward(self, x: torch.Tensor, task: str = 'classification') -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [batch_size, seq_len, input_size]
            task: 'classification' or 'regression'

        Returns:
            output: predictions
            attention_weights: temporal attention weights
        """
        # LSTM forward
        lstm_out, (hidden, cell) = self.lstm(x)

        # Apply temporal attention
        context, attention_weights = self.attention(lstm_out)

        # Task-specific output
        if task == 'classification':
            output = self.classifier(context)
        else:
            output = self.regressor(context)

        return output, attention_weights


class TransformerModel(nn.Module):
    """Transformer Model for Time Series"""

    def __init__(self, input_size: int, config: DeepLearningConfig, num_classes: int = 3):
        super().__init__()
        self.config = config

        # Input projection
        self.input_projection = nn.Linear(input_size, config.transformer_d_model)

        # Positional encoding
        self.pos_encoder = PositionalEncoding(
            config.transformer_d_model,
            max_len=config.sequence_length,
            dropout=config.transformer_dropout
        )

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.transformer_d_model,
            nhead=config.transformer_nhead,
            dim_feedforward=config.transformer_dim_feedforward,
            dropout=config.transformer_dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.transformer_num_layers
        )

        # Multi-head attention for final aggregation
        self.final_attention = MultiHeadAttention(
            config.transformer_d_model,
            config.attention_heads,
            config.attention_dropout
        )

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(config.transformer_d_model, config.transformer_d_model // 2),
            nn.ReLU(),
            nn.Dropout(config.transformer_dropout),
            nn.Linear(config.transformer_d_model // 2, num_classes)
        )

        # Regression head
        self.regressor = nn.Sequential(
            nn.Linear(config.transformer_d_model, config.transformer_d_model // 2),
            nn.ReLU(),
            nn.Dropout(config.transformer_dropout),
            nn.Linear(config.transformer_d_model // 2, 1)
        )

    def forward(self, x: torch.Tensor, task: str = 'classification') -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [batch_size, seq_len, input_size]
            task: 'classification' or 'regression'
        """
        # Project input
        x = self.input_projection(x)

        # Add positional encoding (transpose for pos_encoder)
        x = x.transpose(0, 1)
        x = self.pos_encoder(x)
        x = x.transpose(0, 1)

        # Transformer encoding
        encoded = self.transformer_encoder(x)

        # Self-attention aggregation
        context, attention_weights = self.final_attention(encoded, encoded, encoded)

        # Use mean of context for prediction
        pooled = context.mean(dim=1)

        # Task-specific output
        if task == 'classification':
            output = self.classifier(pooled)
        else:
            output = self.regressor(pooled)

        return output, attention_weights


class HybridLSTMTransformer(nn.Module):
    """Hybrid LSTM + Transformer Model"""

    def __init__(self, input_size: int, config: DeepLearningConfig, num_classes: int = 3):
        super().__init__()
        self.config = config

        # LSTM for local patterns
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=config.lstm_hidden_size,
            num_layers=2,
            dropout=config.lstm_dropout,
            bidirectional=True,
            batch_first=True
        )

        lstm_output_size = config.lstm_hidden_size * 2

        # Project LSTM output to transformer dimension
        self.projection = nn.Linear(lstm_output_size, config.transformer_d_model)

        # Positional encoding
        self.pos_encoder = PositionalEncoding(
            config.transformer_d_model,
            dropout=config.transformer_dropout
        )

        # Transformer for global patterns
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.transformer_d_model,
            nhead=config.transformer_nhead,
            dim_feedforward=config.transformer_dim_feedforward,
            dropout=config.transformer_dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)

        # Temporal attention
        self.temporal_attention = TemporalAttention(config.transformer_d_model)

        # Output heads
        self.classifier = nn.Sequential(
            nn.Linear(config.transformer_d_model, config.transformer_d_model // 2),
            nn.ReLU(),
            nn.Dropout(config.transformer_dropout),
            nn.Linear(config.transformer_d_model // 2, num_classes)
        )

        self.regressor = nn.Sequential(
            nn.Linear(config.transformer_d_model, config.transformer_d_model // 2),
            nn.ReLU(),
            nn.Dropout(config.transformer_dropout),
            nn.Linear(config.transformer_d_model // 2, 1)
        )

    def forward(self, x: torch.Tensor, task: str = 'classification') -> Tuple[torch.Tensor, torch.Tensor]:
        # LSTM encoding
        lstm_out, _ = self.lstm(x)

        # Project to transformer dimension
        projected = self.projection(lstm_out)

        # Add positional encoding
        projected = projected.transpose(0, 1)
        projected = self.pos_encoder(projected)
        projected = projected.transpose(0, 1)

        # Transformer encoding
        transformed = self.transformer(projected)

        # Temporal attention aggregation
        context, attention_weights = self.temporal_attention(transformed)

        # Output
        if task == 'classification':
            output = self.classifier(context)
        else:
            output = self.regressor(context)

        return output, attention_weights


class TimeSeriesDataset(Dataset):
    """Dataset for time series prediction"""

    def __init__(self, features: np.ndarray, targets: np.ndarray,
                 sequence_length: int = 60):
        self.features = torch.FloatTensor(features)
        self.targets = torch.LongTensor(targets) if targets.dtype == np.int64 else torch.FloatTensor(targets)
        self.sequence_length = sequence_length

    def __len__(self):
        return len(self.features) - self.sequence_length

    def __getitem__(self, idx):
        x = self.features[idx:idx + self.sequence_length]
        y = self.targets[idx + self.sequence_length - 1]
        return x, y


class DeepLearningEngine:
    """
    Deep Learning Trading Engine
    Manages LSTM, Transformer, and Hybrid models
    """

    def __init__(self, config: Optional[DeepLearningConfig] = None):
        self.config = config or DeepLearningConfig()

        # Models
        self.lstm_model: Optional[LSTMModel] = None
        self.transformer_model: Optional[TransformerModel] = None
        self.hybrid_model: Optional[HybridLSTMTransformer] = None

        # Active model
        self.active_model = None
        self.model_type = None

        # Training state
        self.is_trained = False
        self.training_history: List[Dict] = []

        # Device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Storage
        self.model_dir = Path("models/deep_learning")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Deep Learning Engine initialized on {self.device}")
        logger.info(f"  PyTorch available: {PYTORCH_AVAILABLE}")
        if PYTORCH_AVAILABLE and torch.cuda.is_available():
            logger.info(f"  GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    def prepare_data(self, df: pd.DataFrame, target_col: str = 'target',
                    feature_cols: Optional[List[str]] = None) -> Tuple[DataLoader, DataLoader]:
        """Prepare data for training"""
        if not PYTORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        # Select features
        if feature_cols is None:
            feature_cols = [c for c in df.columns if c not in [target_col, 'date', 'timestamp']]

        features = df[feature_cols].values.astype(np.float32)
        targets = df[target_col].values

        # Handle NaN
        features = np.nan_to_num(features, nan=0.0)

        # Normalize features
        mean = features.mean(axis=0)
        std = features.std(axis=0) + 1e-8
        features = (features - mean) / std

        # Split into train/val
        split_idx = int(len(features) * 0.8)

        train_dataset = TimeSeriesDataset(
            features[:split_idx],
            targets[:split_idx],
            self.config.sequence_length
        )
        val_dataset = TimeSeriesDataset(
            features[split_idx:],
            targets[split_idx:],
            self.config.sequence_length
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False
        )

        return train_loader, val_loader

    def create_model(self, model_type: str, input_size: int, num_classes: int = 3):
        """Create a deep learning model"""
        if not PYTORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        if model_type == 'lstm':
            self.active_model = LSTMModel(input_size, self.config, num_classes).to(self.device)
        elif model_type == 'transformer':
            self.active_model = TransformerModel(input_size, self.config, num_classes).to(self.device)
        elif model_type == 'hybrid':
            self.active_model = HybridLSTMTransformer(input_size, self.config, num_classes).to(self.device)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        self.model_type = model_type
        logger.info(f"Created {model_type} model with {sum(p.numel() for p in self.active_model.parameters())} parameters")

    def train(self, train_loader: DataLoader, val_loader: DataLoader,
             task: str = 'classification') -> Dict:
        """Train the active model"""
        if self.active_model is None:
            raise ValueError("No model created. Call create_model() first.")

        # Loss function
        if task == 'classification':
            criterion = nn.CrossEntropyLoss(label_smoothing=self.config.label_smoothing)
        else:
            criterion = nn.MSELoss()

        # Optimizer
        optimizer = optim.AdamW(
            self.active_model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )

        # Learning rate scheduler
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )

        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        training_history = []

        for epoch in range(self.config.epochs):
            # Train
            self.active_model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0

            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()
                output, _ = self.active_model(batch_x, task)

                loss = criterion(output, batch_y)
                loss.backward()

                # Gradient clipping
                nn.utils.clip_grad_norm_(
                    self.active_model.parameters(),
                    self.config.gradient_clip
                )

                optimizer.step()

                train_loss += loss.item()

                if task == 'classification':
                    _, predicted = torch.max(output, 1)
                    train_correct += (predicted == batch_y).sum().item()
                    train_total += batch_y.size(0)

            train_loss /= len(train_loader)
            train_acc = train_correct / train_total if train_total > 0 else 0

            # Validate
            self.active_model.eval()
            val_loss = 0.0
            val_correct = 0
            val_total = 0

            with torch.no_grad():
                for batch_x, batch_y in val_loader:
                    batch_x = batch_x.to(self.device)
                    batch_y = batch_y.to(self.device)

                    output, _ = self.active_model(batch_x, task)
                    loss = criterion(output, batch_y)
                    val_loss += loss.item()

                    if task == 'classification':
                        _, predicted = torch.max(output, 1)
                        val_correct += (predicted == batch_y).sum().item()
                        val_total += batch_y.size(0)

            val_loss /= len(val_loader)
            val_acc = val_correct / val_total if val_total > 0 else 0

            # Update scheduler
            scheduler.step(val_loss)

            # Log progress
            epoch_data = {
                'epoch': epoch + 1,
                'train_loss': train_loss,
                'val_loss': val_loss,
                'train_acc': train_acc,
                'val_acc': val_acc,
                'lr': optimizer.param_groups[0]['lr']
            }
            training_history.append(epoch_data)

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.config.epochs} - "
                           f"Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}, "
                           f"Train Acc: {train_acc:.4f}, Val Acc: {val_acc:.4f}")

            # Early stopping
            if val_loss < best_val_loss - self.config.min_delta:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best model
                self.save_model(self.model_dir / 'best_model.pt')
            else:
                patience_counter += 1
                if patience_counter >= self.config.patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break

        self.is_trained = True
        self.training_history = training_history

        # Load best model
        self.load_model(self.model_dir / 'best_model.pt')

        return {
            'final_train_loss': train_loss,
            'final_val_loss': val_loss,
            'best_val_loss': best_val_loss,
            'epochs_trained': len(training_history),
            'training_history': training_history[-10:]  # Last 10 epochs
        }

    def predict(self, x: np.ndarray, task: str = 'classification') -> Dict:
        """Generate prediction"""
        if not self.is_trained or self.active_model is None:
            raise ValueError("Model not trained")

        self.active_model.eval()

        # Prepare input
        if len(x.shape) == 2:
            x = x.reshape(1, *x.shape)

        x_tensor = torch.FloatTensor(x).to(self.device)

        with torch.no_grad():
            output, attention_weights = self.active_model(x_tensor, task)

            if task == 'classification':
                probabilities = F.softmax(output, dim=1)
                predicted_class = torch.argmax(probabilities, dim=1)

                return {
                    'prediction': int(predicted_class[0].item()),
                    'probabilities': probabilities[0].cpu().numpy().tolist(),
                    'confidence': float(probabilities[0].max().item()),
                    'attention_weights': attention_weights[0].cpu().numpy().tolist() if attention_weights is not None else None
                }
            else:
                return {
                    'prediction': float(output[0].item()),
                    'attention_weights': attention_weights[0].cpu().numpy().tolist() if attention_weights is not None else None
                }

    def save_model(self, path: Optional[Path] = None):
        """Save model to disk"""
        if self.active_model is None:
            return

        save_path = path or (self.model_dir / f'{self.model_type}_model.pt')

        torch.save({
            'model_state_dict': self.active_model.state_dict(),
            'model_type': self.model_type,
            'config': self.config.__dict__,
            'training_history': self.training_history
        }, save_path)

        logger.info(f"Model saved to {save_path}")

    def load_model(self, path: Path):
        """Load model from disk"""
        if not path.exists():
            logger.warning(f"Model file not found: {path}")
            return

        checkpoint = torch.load(path, map_location=self.device)

        # Recreate model if needed
        if self.active_model is None:
            self.model_type = checkpoint['model_type']
            # Need input_size - would be stored in checkpoint in production

        self.active_model.load_state_dict(checkpoint['model_state_dict'])
        self.training_history = checkpoint.get('training_history', [])
        self.is_trained = True

        logger.info(f"Model loaded from {path}")

    def get_status(self) -> Dict:
        """Get engine status"""
        gpu_info = {}
        if PYTORCH_AVAILABLE and torch.cuda.is_available():
            gpu_info = {
                'name': torch.cuda.get_device_name(0),
                'memory_allocated': f"{torch.cuda.memory_allocated(0) / 1e9:.2f} GB",
                'memory_cached': f"{torch.cuda.memory_reserved(0) / 1e9:.2f} GB"
            }

        return {
            'pytorch_available': PYTORCH_AVAILABLE,
            'device': str(self.device),
            'gpu_info': gpu_info,
            'model_type': self.model_type,
            'is_trained': self.is_trained,
            'epochs_trained': len(self.training_history),
            'config': self.config.__dict__
        }


# Singleton instance
_deep_learning_engine: Optional[DeepLearningEngine] = None


def get_deep_learning_engine() -> DeepLearningEngine:
    """Get or create Deep Learning Engine singleton"""
    global _deep_learning_engine
    if _deep_learning_engine is None:
        _deep_learning_engine = DeepLearningEngine()
    return _deep_learning_engine
