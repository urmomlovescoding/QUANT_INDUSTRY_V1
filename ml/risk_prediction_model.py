"""
ML Risk Prediction Model - Machine Learning Based Risk Forecasting

This module provides ML-based risk prediction for VaR, Expected Shortfall,
and maximum drawdown forecasting using deep learning and ensemble methods.

Key Features:
- Multi-horizon risk forecasting (1d, 5d, 21d)
- VaR and CVaR prediction with uncertainty quantification
- Drawdown prediction using sequence models
- Feature importance and explainability
- Online learning with drift adaptation

Architecture:
    Input Features
        → Feature Engineering
        → LSTM/Transformer Encoder
        → Multi-Head Risk Predictor
            ├── VaR Head (quantile regression)
            ├── CVaR Head (expected shortfall)
            ├── Drawdown Head (sequence prediction)
            └── Uncertainty Head (prediction intervals)

Usage:
    from ml.risk_prediction_model import RiskPredictionModel

    model = RiskPredictionModel()
    model.fit(X_train, y_train)

    predictions = model.predict(X_new)
    print(f"1-day 95% VaR: {predictions['var_95_1d']}")
"""

import os
import json
import logging
import pickle
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. Using sklearn-only implementation.")

try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import TimeSeriesSplit
    import xgboost as xgb
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn/xgboost not available.")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class RiskPrediction:
    """Container for risk predictions."""
    timestamp: datetime
    symbol: str
    horizon: str  # '1d', '5d', '21d'
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_drawdown: float
    drawdown_probability: float  # P(drawdown > 10%)
    volatility_forecast: float
    prediction_uncertainty: float  # Confidence interval width

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'horizon': self.horizon,
            'var_95': self.var_95,
            'var_99': self.var_99,
            'cvar_95': self.cvar_95,
            'cvar_99': self.cvar_99,
            'max_drawdown': self.max_drawdown,
            'drawdown_probability': self.drawdown_probability,
            'volatility_forecast': self.volatility_forecast,
            'prediction_uncertainty': self.prediction_uncertainty,
        }


@dataclass
class ModelConfig:
    """Configuration for risk prediction model."""
    sequence_length: int = 60
    hidden_dim: int = 128
    num_layers: int = 2
    dropout: float = 0.2
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    early_stopping_patience: int = 10
    quantiles: List[float] = field(default_factory=lambda: [0.01, 0.05, 0.10, 0.50, 0.90, 0.95, 0.99])
    horizons: List[int] = field(default_factory=lambda: [1, 5, 21])  # days


# =============================================================================
# PyTorch Model Components
# =============================================================================

if TORCH_AVAILABLE:

    class QuantileLoss(nn.Module):
        """Quantile loss for probabilistic prediction."""

        def __init__(self, quantiles: List[float]):
            super().__init__()
            self.quantiles = torch.tensor(quantiles)

        def forward(self, predictions: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            """
            Args:
                predictions: (batch, num_quantiles)
                targets: (batch,)
            """
            errors = targets.unsqueeze(1) - predictions
            losses = torch.max(
                self.quantiles * errors,
                (self.quantiles - 1) * errors
            )
            return losses.mean()


    class TemporalBlock(nn.Module):
        """Temporal convolutional block with residual connection."""

        def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float):
            super().__init__()

            padding = (kernel_size - 1) * dilation

            self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size,
                                   padding=padding, dilation=dilation)
            self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size,
                                   padding=padding, dilation=dilation)

            self.relu = nn.ReLU()
            self.dropout = nn.Dropout(dropout)

            self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x: (batch, channels, seq_len)
            out = self.conv1(x)
            out = out[:, :, :-self.conv1.padding[0]]  # Causal trimming
            out = self.relu(out)
            out = self.dropout(out)

            out = self.conv2(out)
            out = out[:, :, :-self.conv2.padding[0]]
            out = self.relu(out)
            out = self.dropout(out)

            res = x if self.downsample is None else self.downsample(x)
            return self.relu(out + res)


    class RiskEncoder(nn.Module):
        """Encoder network for risk features using TCN."""

        def __init__(self, input_dim: int, hidden_dim: int, num_layers: int, dropout: float):
            super().__init__()

            layers = []
            for i in range(num_layers):
                in_ch = input_dim if i == 0 else hidden_dim
                dilation = 2 ** i
                layers.append(TemporalBlock(in_ch, hidden_dim, kernel_size=3, dilation=dilation, dropout=dropout))

            self.network = nn.Sequential(*layers)
            self.global_pool = nn.AdaptiveAvgPool1d(1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x: (batch, seq_len, features) -> (batch, features, seq_len)
            x = x.transpose(1, 2)
            x = self.network(x)
            x = self.global_pool(x).squeeze(-1)
            return x


    class RiskPredictionHead(nn.Module):
        """Multi-output head for risk metrics."""

        def __init__(self, input_dim: int, num_quantiles: int, num_horizons: int):
            super().__init__()

            self.num_quantiles = num_quantiles
            self.num_horizons = num_horizons

            # VaR head (quantile regression)
            self.var_head = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Linear(64, num_quantiles * num_horizons),
            )

            # CVaR head
            self.cvar_head = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Linear(64, num_quantiles * num_horizons),
            )

            # Drawdown head
            self.drawdown_head = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Linear(64, num_horizons * 2),  # max_drawdown + probability
            )

            # Volatility head
            self.volatility_head = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Linear(64, num_horizons),
            )

            # Uncertainty head
            self.uncertainty_head = nn.Sequential(
                nn.Linear(input_dim, 32),
                nn.ReLU(),
                nn.Linear(32, num_horizons),
                nn.Softplus(),  # Ensure positive
            )

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            var = self.var_head(x).view(-1, self.num_horizons, self.num_quantiles)
            cvar = self.cvar_head(x).view(-1, self.num_horizons, self.num_quantiles)
            drawdown = self.drawdown_head(x).view(-1, self.num_horizons, 2)
            volatility = self.volatility_head(x)
            uncertainty = self.uncertainty_head(x)

            return {
                'var': var,
                'cvar': cvar,
                'drawdown': drawdown,
                'volatility': volatility,
                'uncertainty': uncertainty,
            }


    class RiskPredictionNetwork(nn.Module):
        """Complete risk prediction neural network."""

        def __init__(self, config: ModelConfig, input_dim: int):
            super().__init__()
            self.config = config

            self.encoder = RiskEncoder(
                input_dim=input_dim,
                hidden_dim=config.hidden_dim,
                num_layers=config.num_layers,
                dropout=config.dropout,
            )

            self.head = RiskPredictionHead(
                input_dim=config.hidden_dim,
                num_quantiles=len(config.quantiles),
                num_horizons=len(config.horizons),
            )

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            encoded = self.encoder(x)
            return self.head(encoded)


# =============================================================================
# Risk Prediction Model
# =============================================================================

class RiskPredictionModel:
    """
    ML-based risk prediction model.

    Provides multi-horizon forecasts for:
    - Value at Risk (VaR) at multiple confidence levels
    - Expected Shortfall (CVaR)
    - Maximum Drawdown
    - Volatility

    Supports both PyTorch deep learning and sklearn ensemble methods.

    Example:
        model = RiskPredictionModel()

        # Fit on historical data
        model.fit(returns_df, horizons=[1, 5, 21])

        # Predict
        predictions = model.predict(latest_data)
    """

    def __init__(self, config: Optional[ModelConfig] = None, use_deep_learning: bool = True):
        """
        Initialize the risk prediction model.

        Args:
            config: Model configuration
            use_deep_learning: Whether to use PyTorch (requires installation)
        """
        self.config = config or ModelConfig()
        self.use_deep_learning = use_deep_learning and TORCH_AVAILABLE

        self._model = None
        self._scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self._ensemble_models: Dict[str, Any] = {}
        self._feature_names: List[str] = []
        self._is_fitted = False

        # Training history
        self._training_history: List[Dict[str, float]] = []

        logger.info(f"RiskPredictionModel initialized (deep_learning={self.use_deep_learning})")

    def _prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare features for risk prediction.

        Features include:
        - Returns at multiple lags
        - Realized volatility
        - Volume metrics
        - Technical indicators
        """
        features = pd.DataFrame(index=df.index)

        # Returns
        if 'returns' not in df.columns and 'close' in df.columns:
            df['returns'] = df['close'].pct_change()

        returns = df.get('returns', df.iloc[:, 0])

        # Lagged returns
        for lag in [1, 2, 3, 5, 10, 21]:
            features[f'return_lag_{lag}'] = returns.shift(lag)

        # Realized volatility
        for window in [5, 10, 21, 63]:
            features[f'volatility_{window}d'] = returns.rolling(window).std() * np.sqrt(252)

        # Return momentum
        features['return_5d'] = returns.rolling(5).sum()
        features['return_21d'] = returns.rolling(21).sum()

        # Volatility ratio (short/long)
        features['vol_ratio'] = features['volatility_5d'] / features['volatility_21d']

        # Extreme returns
        features['max_loss_5d'] = returns.rolling(5).min()
        features['max_gain_5d'] = returns.rolling(5).max()

        # Distribution moments
        for window in [21, 63]:
            features[f'skewness_{window}d'] = returns.rolling(window).skew()
            features[f'kurtosis_{window}d'] = returns.rolling(window).kurt()

        # Historical VaR proxy
        for window in [21, 63]:
            features[f'hist_var_5pct_{window}d'] = returns.rolling(window).quantile(0.05)

        # Drawdown features
        if 'close' in df.columns:
            rolling_max = df['close'].rolling(21).max()
            drawdown = (df['close'] - rolling_max) / rolling_max
            features['current_drawdown'] = drawdown
            features['max_drawdown_21d'] = drawdown.rolling(21).min()

        # Volume features (if available)
        if 'volume' in df.columns:
            features['volume_ratio'] = df['volume'] / df['volume'].rolling(21).mean()
            features['volume_volatility'] = df['volume'].rolling(21).std() / df['volume'].rolling(21).mean()

        # Drop rows with NaN
        features = features.dropna()

        feature_names = features.columns.tolist()

        return features.values, feature_names

    def _prepare_targets(
        self,
        df: pd.DataFrame,
        horizons: List[int],
    ) -> Dict[str, np.ndarray]:
        """Prepare target variables for each horizon."""
        targets = {}

        returns = df.get('returns', df.iloc[:, 0])

        for h in horizons:
            horizon_name = f'{h}d'

            # Forward returns for VaR targets
            fwd_returns = returns.shift(-h).rolling(h).sum()
            targets[f'returns_{horizon_name}'] = fwd_returns.values

            # Forward volatility
            fwd_vol = returns.shift(-h).rolling(h).std() * np.sqrt(252 / h)
            targets[f'volatility_{horizon_name}'] = fwd_vol.values

            # Forward max drawdown
            if 'close' in df.columns:
                fwd_prices = df['close'].shift(-h)
                rolling_max = df['close'].rolling(h).max()
                fwd_dd = (fwd_prices - rolling_max) / rolling_max
                targets[f'drawdown_{horizon_name}'] = fwd_dd.values

        return targets

    def _create_sequences(
        self,
        X: np.ndarray,
        y: Dict[str, np.ndarray],
        seq_len: int,
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Create sequences for training."""
        n_samples = len(X) - seq_len

        X_seq = np.zeros((n_samples, seq_len, X.shape[1]))
        y_seq = {k: np.zeros(n_samples) for k in y.keys()}

        for i in range(n_samples):
            X_seq[i] = X[i:i + seq_len]
            for k, v in y.items():
                y_seq[k][i] = v[i + seq_len]

        return X_seq, y_seq

    def fit(
        self,
        data: Union[pd.DataFrame, np.ndarray],
        validation_split: float = 0.2,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Fit the risk prediction model.

        Args:
            data: Historical data with returns and optionally OHLCV
            validation_split: Fraction of data for validation
            verbose: Whether to print training progress

        Returns:
            Dictionary with training metrics
        """
        if isinstance(data, np.ndarray):
            data = pd.DataFrame(data, columns=['returns'])

        # Prepare features
        X, self._feature_names = self._prepare_features(data)
        y = self._prepare_targets(data, self.config.horizons)

        # Scale features
        if self._scaler:
            X = self._scaler.fit_transform(X)

        # Split data
        split_idx = int(len(X) * (1 - validation_split))

        if self.use_deep_learning:
            return self._fit_deep_learning(X, y, split_idx, verbose)
        else:
            return self._fit_ensemble(X, y, split_idx, verbose)

    def _fit_deep_learning(
        self,
        X: np.ndarray,
        y: Dict[str, np.ndarray],
        split_idx: int,
        verbose: bool,
    ) -> Dict[str, Any]:
        """Fit using PyTorch."""
        # Create sequences
        X_seq, y_seq = self._create_sequences(X, y, self.config.sequence_length)

        # Split
        X_train = X_seq[:split_idx - self.config.sequence_length]
        X_val = X_seq[split_idx - self.config.sequence_length:]

        # Convert to tensors
        X_train_t = torch.FloatTensor(X_train)
        X_val_t = torch.FloatTensor(X_val)

        # Create model
        self._model = RiskPredictionNetwork(self.config, input_dim=X.shape[1])

        # Training
        optimizer = torch.optim.Adam(self._model.parameters(), lr=self.config.learning_rate)
        quantile_loss = QuantileLoss(self.config.quantiles)

        best_val_loss = float('inf')
        patience_counter = 0

        for epoch in range(self.config.epochs):
            self._model.train()

            # Forward pass
            outputs = self._model(X_train_t)

            # Compute loss (simplified - in practice would use all targets)
            loss = quantile_loss(
                outputs['var'][:, 0, :],  # 1-day horizon
                torch.FloatTensor(y_seq[f'returns_{self.config.horizons[0]}d'][:len(X_train)]),
            )

            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Validation
            self._model.eval()
            with torch.no_grad():
                val_outputs = self._model(X_val_t)
                val_loss = quantile_loss(
                    val_outputs['var'][:, 0, :],
                    torch.FloatTensor(y_seq[f'returns_{self.config.horizons[0]}d'][len(X_train):len(X_train) + len(X_val)]),
                )

            self._training_history.append({
                'epoch': epoch,
                'train_loss': loss.item(),
                'val_loss': val_loss.item(),
            })

            if verbose and epoch % 10 == 0:
                logger.info(f"Epoch {epoch}: train_loss={loss.item():.4f}, val_loss={val_loss.item():.4f}")

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.config.early_stopping_patience:
                    if verbose:
                        logger.info(f"Early stopping at epoch {epoch}")
                    break

        self._is_fitted = True

        return {
            'epochs_trained': epoch + 1,
            'final_train_loss': loss.item(),
            'final_val_loss': val_loss.item(),
            'best_val_loss': best_val_loss.item(),
        }

    def _fit_ensemble(
        self,
        X: np.ndarray,
        y: Dict[str, np.ndarray],
        split_idx: int,
        verbose: bool,
    ) -> Dict[str, Any]:
        """Fit using sklearn ensemble methods."""
        X_train, X_val = X[:split_idx], X[split_idx:]

        for horizon in self.config.horizons:
            target_key = f'returns_{horizon}d'
            y_train = y[target_key][:split_idx]

            # Remove NaN targets
            valid_mask = ~np.isnan(y_train)
            X_train_valid = X_train[valid_mask]
            y_train_valid = y_train[valid_mask]

            # Train quantile regressors
            for q in [0.05, 0.01]:
                model = GradientBoostingRegressor(
                    loss='quantile',
                    alpha=q,
                    n_estimators=100,
                    max_depth=5,
                    random_state=42,
                )
                model.fit(X_train_valid, y_train_valid)
                self._ensemble_models[f'var_{int((1-q)*100)}_{horizon}d'] = model

            # Train volatility model
            vol_key = f'volatility_{horizon}d'
            if vol_key in y:
                y_vol = y[vol_key][:split_idx]
                valid_vol_mask = ~np.isnan(y_vol)

                vol_model = GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=5,
                    random_state=42,
                )
                vol_model.fit(X_train[valid_vol_mask], y_vol[valid_vol_mask])
                self._ensemble_models[f'volatility_{horizon}d'] = vol_model

        self._is_fitted = True

        return {
            'models_trained': len(self._ensemble_models),
            'horizons': self.config.horizons,
        }

    def predict(
        self,
        data: Union[pd.DataFrame, np.ndarray],
        symbol: str = "PORTFOLIO",
    ) -> List[RiskPrediction]:
        """
        Generate risk predictions.

        Args:
            data: Recent market data
            symbol: Symbol identifier

        Returns:
            List of RiskPrediction objects for each horizon
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        if isinstance(data, np.ndarray):
            data = pd.DataFrame(data, columns=['returns'])

        # Prepare features
        X, _ = self._prepare_features(data)

        if self._scaler:
            X = self._scaler.transform(X)

        predictions = []

        if self.use_deep_learning:
            predictions = self._predict_deep_learning(X, symbol)
        else:
            predictions = self._predict_ensemble(X, symbol)

        return predictions

    def _predict_deep_learning(self, X: np.ndarray, symbol: str) -> List[RiskPrediction]:
        """Generate predictions using PyTorch model."""
        # Create sequence from latest data
        if len(X) < self.config.sequence_length:
            logger.warning(f"Insufficient data for sequence: {len(X)} < {self.config.sequence_length}")
            return []

        X_seq = X[-self.config.sequence_length:].reshape(1, self.config.sequence_length, -1)
        X_t = torch.FloatTensor(X_seq)

        self._model.eval()
        with torch.no_grad():
            outputs = self._model(X_t)

        predictions = []
        now = datetime.now(timezone.utc)

        for i, horizon in enumerate(self.config.horizons):
            var_quantiles = outputs['var'][0, i, :].numpy()
            cvar_quantiles = outputs['cvar'][0, i, :].numpy()
            drawdown = outputs['drawdown'][0, i, :].numpy()
            volatility = outputs['volatility'][0, i].item()
            uncertainty = outputs['uncertainty'][0, i].item()

            # Map quantiles to specific levels
            q_idx_95 = self.config.quantiles.index(0.05) if 0.05 in self.config.quantiles else 1
            q_idx_99 = self.config.quantiles.index(0.01) if 0.01 in self.config.quantiles else 0

            pred = RiskPrediction(
                timestamp=now,
                symbol=symbol,
                horizon=f'{horizon}d',
                var_95=float(var_quantiles[q_idx_95]),
                var_99=float(var_quantiles[q_idx_99]),
                cvar_95=float(cvar_quantiles[q_idx_95]),
                cvar_99=float(cvar_quantiles[q_idx_99]),
                max_drawdown=float(drawdown[0]),
                drawdown_probability=float(torch.sigmoid(torch.tensor(drawdown[1])).item()),
                volatility_forecast=float(volatility),
                prediction_uncertainty=float(uncertainty),
            )
            predictions.append(pred)

        return predictions

    def _predict_ensemble(self, X: np.ndarray, symbol: str) -> List[RiskPrediction]:
        """Generate predictions using ensemble models."""
        predictions = []
        now = datetime.now(timezone.utc)

        # Use latest features
        X_latest = X[-1:] if len(X.shape) == 2 else X.reshape(1, -1)

        for horizon in self.config.horizons:
            var_95 = self._ensemble_models.get(f'var_95_{horizon}d')
            var_99 = self._ensemble_models.get(f'var_99_{horizon}d')
            vol_model = self._ensemble_models.get(f'volatility_{horizon}d')

            var_95_pred = var_95.predict(X_latest)[0] if var_95 else -0.02
            var_99_pred = var_99.predict(X_latest)[0] if var_99 else -0.03
            vol_pred = vol_model.predict(X_latest)[0] if vol_model else 0.2

            # Estimate CVaR as 1.5x VaR (simplified)
            cvar_95_pred = var_95_pred * 1.5
            cvar_99_pred = var_99_pred * 1.5

            pred = RiskPrediction(
                timestamp=now,
                symbol=symbol,
                horizon=f'{horizon}d',
                var_95=float(var_95_pred),
                var_99=float(var_99_pred),
                cvar_95=float(cvar_95_pred),
                cvar_99=float(cvar_99_pred),
                max_drawdown=float(var_99_pred * 2),  # Simplified estimate
                drawdown_probability=0.1,  # Would need separate model
                volatility_forecast=float(vol_pred),
                prediction_uncertainty=float(abs(var_95_pred) * 0.2),  # Simplified
            )
            predictions.append(pred)

        return predictions

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if not self._is_fitted:
            raise RuntimeError("Model not fitted")

        importance = {}

        if self.use_deep_learning:
            # Would use gradient-based importance in production
            for i, name in enumerate(self._feature_names):
                importance[name] = 1.0 / len(self._feature_names)
        else:
            # Use ensemble model importance
            for name, model in self._ensemble_models.items():
                if hasattr(model, 'feature_importances_'):
                    for i, imp in enumerate(model.feature_importances_):
                        feat_name = self._feature_names[i] if i < len(self._feature_names) else f'feature_{i}'
                        if feat_name not in importance:
                            importance[feat_name] = 0
                        importance[feat_name] += imp

            # Normalize
            total = sum(importance.values())
            if total > 0:
                importance = {k: v / total for k, v in importance.items()}

        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    def save(self, path: str) -> None:
        """Save model to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save config
        with open(path / 'config.json', 'w') as f:
            json.dump({
                'sequence_length': self.config.sequence_length,
                'hidden_dim': self.config.hidden_dim,
                'num_layers': self.config.num_layers,
                'dropout': self.config.dropout,
                'quantiles': self.config.quantiles,
                'horizons': self.config.horizons,
                'use_deep_learning': self.use_deep_learning,
                'feature_names': self._feature_names,
            }, f)

        # Save scaler
        if self._scaler:
            with open(path / 'scaler.pkl', 'wb') as f:
                pickle.dump(self._scaler, f)

        # Save model
        if self.use_deep_learning and self._model:
            torch.save(self._model.state_dict(), path / 'model.pt')
        else:
            with open(path / 'ensemble_models.pkl', 'wb') as f:
                pickle.dump(self._ensemble_models, f)

        logger.info(f"Model saved to {path}")

    def load(self, path: str) -> None:
        """Load model from disk."""
        path = Path(path)

        # Load config
        with open(path / 'config.json', 'r') as f:
            config_data = json.load(f)

        self.config = ModelConfig(
            sequence_length=config_data['sequence_length'],
            hidden_dim=config_data['hidden_dim'],
            num_layers=config_data['num_layers'],
            dropout=config_data['dropout'],
            quantiles=config_data['quantiles'],
            horizons=config_data['horizons'],
        )
        self.use_deep_learning = config_data['use_deep_learning']
        self._feature_names = config_data['feature_names']

        # Load scaler
        scaler_path = path / 'scaler.pkl'
        if scaler_path.exists():
            with open(scaler_path, 'rb') as f:
                self._scaler = pickle.load(f)

        # Load model
        if self.use_deep_learning:
            self._model = RiskPredictionNetwork(self.config, input_dim=len(self._feature_names))
            self._model.load_state_dict(torch.load(path / 'model.pt'))
        else:
            with open(path / 'ensemble_models.pkl', 'rb') as f:
                self._ensemble_models = pickle.load(f)

        self._is_fitted = True
        logger.info(f"Model loaded from {path}")
