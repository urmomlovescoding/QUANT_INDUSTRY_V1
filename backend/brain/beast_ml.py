"""
QUANT INDUSTRY - BEAST ML Engine
Institutional-Grade Machine Learning Trading Engine

Features:
- 100+ Feature Engineering Pipeline
- XGBoost, LightGBM, Neural Network Ensemble
- Walk-Forward Validation
- Prop Firm Compliance
- Adaptive Position Sizing
"""

import json
import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ML Libraries - with fallbacks
try:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.preprocessing import RobustScaler, StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

try:
    import torch
    from torch import nn, optim
    from torch.utils.data import DataLoader, TensorDataset
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class BEASTConfig:
    """BEAST ML Engine Configuration"""
    # Model weights
    xgboost_weight: float = 0.40
    lightgbm_weight: float = 0.30
    neural_net_weight: float = 0.30

    # XGBoost parameters
    xgb_n_estimators: int = 200
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.05
    xgb_subsample: float = 0.8
    xgb_colsample_bytree: float = 0.8

    # LightGBM parameters
    lgb_n_estimators: int = 200
    lgb_max_depth: int = 6
    lgb_learning_rate: float = 0.05
    lgb_num_leaves: int = 31

    # Neural Network parameters
    nn_hidden_layers: List[int] = field(default_factory=lambda: [128, 64, 32])
    nn_dropout: float = 0.3
    nn_learning_rate: float = 0.001
    nn_epochs: int = 100
    nn_batch_size: int = 32

    # Walk-Forward parameters
    train_period: int = 252  # 1 year
    test_period: int = 63   # 3 months
    n_splits: int = 5

    # Trading parameters
    confidence_threshold: float = 0.65
    min_trades_validation: int = 30

    # Prop Firm parameters
    max_daily_drawdown: float = 0.05  # 5%
    max_total_drawdown: float = 0.10  # 10%
    profit_target: float = 0.08  # 8%

    # Position sizing
    risk_per_trade: float = 0.01  # 1%
    max_position_size: float = 0.15  # 15% of portfolio


class FeatureEngineer:
    """
    100+ Feature Engineering Pipeline
    Creates comprehensive features from OHLCV data
    """

    def __init__(self):
        self.scaler = RobustScaler() if SKLEARN_AVAILABLE else None
        self.feature_names: List[str] = []

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create all features from OHLCV data"""
        features = pd.DataFrame(index=df.index)

        # ========== RETURNS ==========
        for period in [1, 2, 3, 5, 10, 20, 60]:
            features[f'return_{period}d'] = df['close'].pct_change(period)
            features[f'log_return_{period}d'] = np.log(df['close'] / df['close'].shift(period))

        # ========== MOVING AVERAGES ==========
        for period in [5, 10, 20, 50, 100, 200]:
            # SMA
            features[f'sma_{period}'] = df['close'].rolling(period).mean()
            features[f'sma_{period}_dist'] = (df['close'] - features[f'sma_{period}']) / features[f'sma_{period}']

            # EMA
            features[f'ema_{period}'] = df['close'].ewm(span=period).mean()
            features[f'ema_{period}_dist'] = (df['close'] - features[f'ema_{period}']) / features[f'ema_{period}']

        # MA Crossovers
        features['sma_5_20_cross'] = (features['sma_5'] > features['sma_20']).astype(int)
        features['sma_20_50_cross'] = (features['sma_20'] > features['sma_50']).astype(int)
        features['sma_50_200_cross'] = (features['sma_50'] > features['sma_200']).astype(int)
        features['ema_12_26_cross'] = (features['ema_10'] > features['ema_20']).astype(int)

        # ========== MOMENTUM INDICATORS ==========
        # RSI
        for period in [7, 14, 21]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            features[f'rsi_{period}'] = 100 - (100 / (1 + rs))

        # Stochastic
        for period in [14, 21]:
            low_min = df['low'].rolling(period).min()
            high_max = df['high'].rolling(period).max()
            features[f'stoch_k_{period}'] = 100 * (df['close'] - low_min) / (high_max - low_min)
            features[f'stoch_d_{period}'] = features[f'stoch_k_{period}'].rolling(3).mean()

        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = features['macd'].ewm(span=9).mean()
        features['macd_histogram'] = features['macd'] - features['macd_signal']

        # Williams %R
        for period in [14, 21]:
            high_max = df['high'].rolling(period).max()
            low_min = df['low'].rolling(period).min()
            features[f'williams_r_{period}'] = -100 * (high_max - df['close']) / (high_max - low_min)

        # CCI (Commodity Channel Index)
        for period in [14, 20]:
            tp = (df['high'] + df['low'] + df['close']) / 3
            sma_tp = tp.rolling(period).mean()
            mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
            features[f'cci_{period}'] = (tp - sma_tp) / (0.015 * mad)

        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            features[f'roc_{period}'] = df['close'].pct_change(period) * 100

        # ========== VOLATILITY INDICATORS ==========
        # ATR
        for period in [7, 14, 21]:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            features[f'atr_{period}'] = tr.rolling(period).mean()
            features[f'atr_{period}_pct'] = features[f'atr_{period}'] / df['close']

        # Bollinger Bands
        for period in [20]:
            sma = df['close'].rolling(period).mean()
            std = df['close'].rolling(period).std()
            features[f'bb_upper_{period}'] = sma + (2 * std)
            features[f'bb_lower_{period}'] = sma - (2 * std)
            features[f'bb_width_{period}'] = (features[f'bb_upper_{period}'] - features[f'bb_lower_{period}']) / sma
            features[f'bb_position_{period}'] = (df['close'] - features[f'bb_lower_{period}']) / (features[f'bb_upper_{period}'] - features[f'bb_lower_{period}'])

        # Keltner Channels
        atr_10 = features['atr_14']
        ema_20 = features['ema_20']
        features['keltner_upper'] = ema_20 + (2 * atr_10)
        features['keltner_lower'] = ema_20 - (2 * atr_10)
        features['keltner_width'] = (features['keltner_upper'] - features['keltner_lower']) / ema_20

        # Historical Volatility
        for period in [10, 20, 60]:
            features[f'volatility_{period}'] = features['return_1d'].rolling(period).std() * np.sqrt(252)

        # ========== VOLUME INDICATORS ==========
        # OBV
        obv = np.where(df['close'] > df['close'].shift(), df['volume'],
                       np.where(df['close'] < df['close'].shift(), -df['volume'], 0))
        features['obv'] = pd.Series(obv, index=df.index).cumsum()
        features['obv_sma_20'] = features['obv'].rolling(20).mean()
        features['obv_trend'] = (features['obv'] - features['obv_sma_20']) / features['obv_sma_20'].abs()

        # VWAP
        features['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        features['vwap_dist'] = (df['close'] - features['vwap']) / features['vwap']

        # Money Flow Index
        for period in [14]:
            tp = (df['high'] + df['low'] + df['close']) / 3
            mf = tp * df['volume']
            pos_mf = mf.where(tp > tp.shift(), 0).rolling(period).sum()
            neg_mf = mf.where(tp < tp.shift(), 0).rolling(period).sum()
            mf_ratio = pos_mf / neg_mf
            features[f'mfi_{period}'] = 100 - (100 / (1 + mf_ratio))

        # Volume ratios
        for period in [5, 10, 20]:
            features[f'volume_sma_{period}'] = df['volume'].rolling(period).mean()
            features[f'volume_ratio_{period}'] = df['volume'] / features[f'volume_sma_{period}']

        # ========== TREND INDICATORS ==========
        # ADX
        for period in [14]:
            plus_dm = df['high'].diff()
            minus_dm = -df['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

            tr = features[f'atr_{period}'] * period  # Using ATR
            plus_di = 100 * (plus_dm.rolling(period).sum() / tr)
            minus_di = 100 * (minus_dm.rolling(period).sum() / tr)

            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
            features[f'adx_{period}'] = dx.rolling(period).mean()
            features[f'plus_di_{period}'] = plus_di
            features[f'minus_di_{period}'] = minus_di

        # Supertrend
        atr = features['atr_10']
        hl2 = (df['high'] + df['low']) / 2
        features['supertrend_upper'] = hl2 + (3 * atr)
        features['supertrend_lower'] = hl2 - (3 * atr)

        # ========== CANDLESTICK PATTERNS ==========
        body = df['close'] - df['open']
        body_size = np.abs(body)
        upper_shadow = df['high'] - np.maximum(df['close'], df['open'])
        lower_shadow = np.minimum(df['close'], df['open']) - df['low']

        # Doji
        features['doji'] = (body_size / (df['high'] - df['low']) < 0.1).astype(int)

        # Hammer
        features['hammer'] = ((lower_shadow > 2 * body_size) & (upper_shadow < body_size * 0.3) & (body > 0)).astype(int)

        # Engulfing
        features['bullish_engulfing'] = ((body > 0) & (body.shift() < 0) & (df['close'] > df['open'].shift()) & (df['open'] < df['close'].shift())).astype(int)
        features['bearish_engulfing'] = ((body < 0) & (body.shift() > 0) & (df['open'] > df['close'].shift()) & (df['close'] < df['open'].shift())).astype(int)

        # ========== PRICE PATTERNS ==========
        # Higher highs/lows
        features['higher_high'] = (df['high'] > df['high'].shift()).astype(int)
        features['higher_low'] = (df['low'] > df['low'].shift()).astype(int)
        features['lower_high'] = (df['high'] < df['high'].shift()).astype(int)
        features['lower_low'] = (df['low'] < df['low'].shift()).astype(int)

        # 52-week high/low
        features['dist_52w_high'] = (df['close'] - df['high'].rolling(252).max()) / df['high'].rolling(252).max()
        features['dist_52w_low'] = (df['close'] - df['low'].rolling(252).min()) / df['low'].rolling(252).min()

        # Gap analysis
        features['gap'] = (df['open'] - df['close'].shift()) / df['close'].shift()
        features['gap_fill'] = ((df['low'] <= df['close'].shift()) & (features['gap'] > 0)).astype(int)

        # ========== ADVANCED STATISTICAL FEATURES ==========
        # Autocorrelation
        for lag in [1, 5, 10]:
            features[f'autocorr_{lag}'] = features['return_1d'].rolling(20).apply(lambda x: x.autocorr(lag=lag))

        # Skewness and Kurtosis
        for period in [20, 60]:
            features[f'skewness_{period}'] = features['return_1d'].rolling(period).skew()
            features[f'kurtosis_{period}'] = features['return_1d'].rolling(period).kurt()

        # Price acceleration
        features['price_acceleration'] = features['return_1d'].diff()

        # Z-score
        for period in [20, 50]:
            mean = df['close'].rolling(period).mean()
            std = df['close'].rolling(period).std()
            features[f'zscore_{period}'] = (df['close'] - mean) / std

        # Store feature names
        self.feature_names = features.columns.tolist()

        return features

    def normalize_features(self, features: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        """Normalize features using RobustScaler"""
        if self.scaler is None:
            return features

        if fit:
            normalized = pd.DataFrame(
                self.scaler.fit_transform(features),
                columns=features.columns,
                index=features.index
            )
        else:
            normalized = pd.DataFrame(
                self.scaler.transform(features),
                columns=features.columns,
                index=features.index
            )

        return normalized


class NeuralNetworkModel(nn.Module):
    """PyTorch Neural Network for trading signals"""

    def __init__(self, input_size: int, hidden_layers: List[int], dropout: float = 0.3):
        super().__init__()

        layers = []
        prev_size = input_size

        for hidden_size in hidden_layers:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.BatchNorm1d(hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            prev_size = hidden_size

        # Output layer (3 classes: sell, hold, buy)
        layers.append(nn.Linear(prev_size, 3))

        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)


class BEASTMLEngine:
    """
    BEAST ML Engine - Institutional Grade Trading System

    Combines:
    - XGBoost (40%)
    - LightGBM (30%)
    - Neural Network (30%)

    With walk-forward validation and prop firm compliance.
    """

    def __init__(self, config: Optional[BEASTConfig] = None):
        self.config = config or BEASTConfig()
        self.feature_engineer = FeatureEngineer()

        # Models
        self.xgb_model = None
        self.lgb_model = None
        self.nn_model = None

        # Training state
        self.is_trained = False
        self.training_history: List[Dict] = []
        self.walk_forward_results: List[Dict] = []

        # Performance tracking
        self.predictions: List[Dict] = []
        self.trades: List[Dict] = []

        # Storage paths
        self.model_dir = Path("models/beast")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        logger.info("BEAST ML Engine initialized")
        logger.info(f"  XGBoost available: {XGBOOST_AVAILABLE}")
        logger.info(f"  LightGBM available: {LIGHTGBM_AVAILABLE}")
        logger.info(f"  PyTorch available: {PYTORCH_AVAILABLE}")

    def prepare_data(self, df: pd.DataFrame, target_horizon: int = 5) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features and target for training"""
        # Create features
        features = self.feature_engineer.create_features(df)

        # Create target (future returns classification)
        future_return = df['close'].pct_change(target_horizon).shift(-target_horizon)

        # Classify into 3 classes: 0=sell, 1=hold, 2=buy
        threshold = future_return.std()
        target = pd.Series(1, index=future_return.index)  # Default: hold
        target[future_return > threshold] = 2  # Buy
        target[future_return < -threshold] = 0  # Sell

        # Remove NaN rows
        valid_idx = features.dropna().index.intersection(target.dropna().index)
        features = features.loc[valid_idx]
        target = target.loc[valid_idx]

        return features, target

    def train_xgboost(self, X_train: np.ndarray, y_train: np.ndarray,
                      X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        """Train XGBoost model"""
        if not XGBOOST_AVAILABLE:
            logger.warning("XGBoost not available, skipping")
            return {}

        params = {
            'objective': 'multi:softprob',
            'num_class': 3,
            'max_depth': self.config.xgb_max_depth,
            'learning_rate': self.config.xgb_learning_rate,
            'subsample': self.config.xgb_subsample,
            'colsample_bytree': self.config.xgb_colsample_bytree,
            'eval_metric': 'mlogloss',
            'use_label_encoder': False,
            'verbosity': 0
        }

        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)

        self.xgb_model = xgb.train(
            params,
            dtrain,
            num_boost_round=self.config.xgb_n_estimators,
            evals=[(dval, 'val')],
            early_stopping_rounds=20,
            verbose_eval=False
        )

        # Evaluate
        y_pred = np.argmax(self.xgb_model.predict(dval), axis=1)
        accuracy = accuracy_score(y_val, y_pred)

        logger.info(f"XGBoost trained - Accuracy: {accuracy:.4f}")
        return {'accuracy': accuracy, 'model': 'xgboost'}

    def train_lightgbm(self, X_train: np.ndarray, y_train: np.ndarray,
                       X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        """Train LightGBM model"""
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available, skipping")
            return {}

        params = {
            'objective': 'multiclass',
            'num_class': 3,
            'max_depth': self.config.lgb_max_depth,
            'learning_rate': self.config.lgb_learning_rate,
            'num_leaves': self.config.lgb_num_leaves,
            'metric': 'multi_logloss',
            'verbosity': -1
        }

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        self.lgb_model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.lgb_n_estimators,
            valid_sets=[val_data],
            callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)]
        )

        # Evaluate
        y_pred = np.argmax(self.lgb_model.predict(X_val), axis=1)
        accuracy = accuracy_score(y_val, y_pred)

        logger.info(f"LightGBM trained - Accuracy: {accuracy:.4f}")
        return {'accuracy': accuracy, 'model': 'lightgbm'}

    def train_neural_network(self, X_train: np.ndarray, y_train: np.ndarray,
                            X_val: np.ndarray, y_val: np.ndarray) -> Dict:
        """Train PyTorch Neural Network"""
        if not PYTORCH_AVAILABLE:
            logger.warning("PyTorch not available, skipping neural network")
            return {}

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Training neural network on {device}")

        # Create model
        input_size = X_train.shape[1]
        self.nn_model = NeuralNetworkModel(
            input_size,
            self.config.nn_hidden_layers,
            self.config.nn_dropout
        ).to(device)

        # Prepare data
        X_train_t = torch.FloatTensor(X_train).to(device)
        y_train_t = torch.LongTensor(y_train).to(device)
        X_val_t = torch.FloatTensor(X_val).to(device)
        y_val_t = torch.LongTensor(y_val).to(device)

        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=self.config.nn_batch_size, shuffle=True)

        # Training
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.nn_model.parameters(), lr=self.config.nn_learning_rate)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

        best_val_acc = 0
        patience_counter = 0

        for epoch in range(self.config.nn_epochs):
            self.nn_model.train()
            total_loss = 0

            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = self.nn_model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            # Validation
            self.nn_model.eval()
            with torch.no_grad():
                val_outputs = self.nn_model(X_val_t)
                val_pred = torch.argmax(val_outputs, dim=1)
                val_acc = (val_pred == y_val_t).float().mean().item()

            scheduler.step(1 - val_acc)

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= 20:
                    break

        logger.info(f"Neural Network trained - Accuracy: {best_val_acc:.4f}")
        return {'accuracy': best_val_acc, 'model': 'neural_network'}

    def walk_forward_train(self, df: pd.DataFrame) -> Dict:
        """
        Walk-Forward Training with multiple splits
        Prevents overfitting by training on rolling windows
        """
        logger.info("Starting walk-forward training...")

        features, target = self.prepare_data(df)

        # Normalize features
        features_normalized = self.feature_engineer.normalize_features(features)

        X = features_normalized.values
        y = target.values

        # Time series split
        tscv = TimeSeriesSplit(n_splits=self.config.n_splits)

        all_results = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            logger.info(f"Training fold {fold + 1}/{self.config.n_splits}")

            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            fold_results = {
                'fold': fold + 1,
                'train_size': len(train_idx),
                'val_size': len(val_idx),
                'models': {}
            }

            # Train all models
            if XGBOOST_AVAILABLE:
                fold_results['models']['xgboost'] = self.train_xgboost(X_train, y_train, X_val, y_val)

            if LIGHTGBM_AVAILABLE:
                fold_results['models']['lightgbm'] = self.train_lightgbm(X_train, y_train, X_val, y_val)

            if PYTORCH_AVAILABLE:
                fold_results['models']['neural_network'] = self.train_neural_network(X_train, y_train, X_val, y_val)

            all_results.append(fold_results)

        self.walk_forward_results = all_results
        self.is_trained = True

        # Calculate average performance
        avg_performance = self._calculate_average_performance(all_results)

        logger.info(f"Walk-forward training complete. Average accuracy: {avg_performance['avg_accuracy']:.4f}")

        return {
            'folds': all_results,
            'average_performance': avg_performance
        }

    def _calculate_average_performance(self, results: List[Dict]) -> Dict:
        """Calculate average performance across folds"""
        accuracies = []

        for fold in results:
            for model_name, metrics in fold['models'].items():
                if 'accuracy' in metrics:
                    accuracies.append(metrics['accuracy'])

        return {
            'avg_accuracy': np.mean(accuracies) if accuracies else 0,
            'std_accuracy': np.std(accuracies) if accuracies else 0,
            'min_accuracy': np.min(accuracies) if accuracies else 0,
            'max_accuracy': np.max(accuracies) if accuracies else 0
        }

    def predict(self, df: pd.DataFrame) -> Dict:
        """
        Generate ensemble prediction
        Combines XGBoost, LightGBM, and Neural Network predictions
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call walk_forward_train() first.")

        # Create features
        features = self.feature_engineer.create_features(df)
        features = features.dropna()

        if len(features) == 0:
            return {'signal': SignalType.HOLD, 'confidence': 0.0}

        # Normalize
        features_normalized = self.feature_engineer.normalize_features(features, fit=False)
        X = features_normalized.values[-1:].astype(np.float32)  # Latest row

        predictions = []
        weights = []

        # XGBoost prediction
        if self.xgb_model is not None and XGBOOST_AVAILABLE:
            dtest = xgb.DMatrix(X)
            xgb_probs = self.xgb_model.predict(dtest)[0]
            predictions.append(xgb_probs)
            weights.append(self.config.xgboost_weight)

        # LightGBM prediction
        if self.lgb_model is not None and LIGHTGBM_AVAILABLE:
            lgb_probs = self.lgb_model.predict(X)[0]
            predictions.append(lgb_probs)
            weights.append(self.config.lightgbm_weight)

        # Neural Network prediction
        if self.nn_model is not None and PYTORCH_AVAILABLE:
            device = next(self.nn_model.parameters()).device
            X_t = torch.FloatTensor(X).to(device)
            self.nn_model.eval()
            with torch.no_grad():
                nn_probs = torch.softmax(self.nn_model(X_t), dim=1)[0].cpu().numpy()
            predictions.append(nn_probs)
            weights.append(self.config.neural_net_weight)

        if not predictions:
            return {'signal': SignalType.HOLD, 'confidence': 0.0}

        # Weighted ensemble
        weights = np.array(weights)
        weights = weights / weights.sum()

        ensemble_probs = np.zeros(3)
        for prob, weight in zip(predictions, weights):
            ensemble_probs += prob * weight

        # Get prediction and confidence
        predicted_class = np.argmax(ensemble_probs)
        confidence = ensemble_probs[predicted_class]

        # Map to signal type
        signal_map = {0: SignalType.SELL, 1: SignalType.HOLD, 2: SignalType.BUY}
        signal = signal_map[predicted_class]

        # Adjust for strong signals
        if confidence > 0.8:
            if signal == SignalType.BUY:
                signal = SignalType.STRONG_BUY
            elif signal == SignalType.SELL:
                signal = SignalType.STRONG_SELL

        result = {
            'signal': signal,
            'confidence': float(confidence),
            'probabilities': {
                'sell': float(ensemble_probs[0]),
                'hold': float(ensemble_probs[1]),
                'buy': float(ensemble_probs[2])
            },
            'timestamp': datetime.now().isoformat()
        }

        self.predictions.append(result)

        return result

    def calculate_position_size(self, portfolio_value: float, current_price: float,
                               confidence: float, volatility: float) -> int:
        """
        Calculate position size using Kelly Criterion with adjustments

        Args:
            portfolio_value: Total portfolio value
            current_price: Current asset price
            confidence: Model confidence (0-1)
            volatility: Asset volatility (annualized)

        Returns:
            Number of shares to trade
        """
        # Base risk per trade
        risk_amount = portfolio_value * self.config.risk_per_trade

        # Kelly fraction (simplified)
        # f* = (p * b - q) / b where p=win_prob, q=1-p, b=win/loss ratio
        win_prob = confidence
        win_loss_ratio = 2.0  # Target 2:1

        kelly_fraction = (win_prob * win_loss_ratio - (1 - win_prob)) / win_loss_ratio
        kelly_fraction = max(0, min(0.25, kelly_fraction))  # Cap at 25%

        # Volatility adjustment
        vol_adjustment = min(1.0, 0.15 / volatility) if volatility > 0 else 1.0

        # Confidence adjustment
        conf_adjustment = confidence if confidence > self.config.confidence_threshold else 0

        # Final position size
        position_value = portfolio_value * kelly_fraction * vol_adjustment * conf_adjustment
        position_value = min(position_value, portfolio_value * self.config.max_position_size)

        shares = int(position_value / current_price) if current_price > 0 else 0

        return shares

    def check_risk_limits(self, current_drawdown: float, daily_drawdown: float) -> Dict:
        """
        Check if trade is allowed based on prop firm risk limits

        Returns:
            Dict with 'allowed' boolean and 'reason' if not allowed
        """
        if daily_drawdown >= self.config.max_daily_drawdown:
            return {
                'allowed': False,
                'reason': f'Daily drawdown limit reached ({daily_drawdown:.2%} >= {self.config.max_daily_drawdown:.2%})'
            }

        if current_drawdown >= self.config.max_total_drawdown:
            return {
                'allowed': False,
                'reason': f'Total drawdown limit reached ({current_drawdown:.2%} >= {self.config.max_total_drawdown:.2%})'
            }

        return {'allowed': True, 'reason': None}

    def save_models(self, path: Optional[str] = None) -> str:
        """Save all trained models"""
        save_path = Path(path) if path else self.model_dir
        save_path.mkdir(parents=True, exist_ok=True)

        # Save XGBoost
        if self.xgb_model is not None:
            self.xgb_model.save_model(str(save_path / 'xgboost_model.json'))

        # Save LightGBM
        if self.lgb_model is not None:
            self.lgb_model.save_model(str(save_path / 'lightgbm_model.txt'))

        # Save Neural Network
        if self.nn_model is not None and PYTORCH_AVAILABLE:
            torch.save(self.nn_model.state_dict(), save_path / 'neural_network.pt')

        # Save scaler
        if self.feature_engineer.scaler is not None:
            with open(save_path / 'scaler.pkl', 'wb') as f:
                pickle.dump(self.feature_engineer.scaler, f)

        # Save config
        with open(save_path / 'config.json', 'w') as f:
            json.dump(self.config.__dict__, f, indent=2)

        logger.info(f"Models saved to {save_path}")
        return str(save_path)

    def load_models(self, path: Optional[str] = None) -> bool:
        """Load trained models"""
        load_path = Path(path) if path else self.model_dir

        try:
            # Load XGBoost
            xgb_path = load_path / 'xgboost_model.json'
            if xgb_path.exists() and XGBOOST_AVAILABLE:
                self.xgb_model = xgb.Booster()
                self.xgb_model.load_model(str(xgb_path))

            # Load LightGBM
            lgb_path = load_path / 'lightgbm_model.txt'
            if lgb_path.exists() and LIGHTGBM_AVAILABLE:
                self.lgb_model = lgb.Booster(model_file=str(lgb_path))

            # Load Neural Network
            nn_path = load_path / 'neural_network.pt'
            if nn_path.exists() and PYTORCH_AVAILABLE:
                # Need to recreate model architecture first
                config_path = load_path / 'config.json'
                if config_path.exists():
                    with open(config_path) as f:
                        config_dict = json.load(f)
                    self.config = BEASTConfig(**config_dict)

                # This would need the input size - storing separately would be better
                # For now, we'll skip loading the NN if architecture is unknown

            # Load scaler
            scaler_path = load_path / 'scaler.pkl'
            if scaler_path.exists():
                with open(scaler_path, 'rb') as f:
                    self.feature_engineer.scaler = pickle.load(f)

            self.is_trained = True
            logger.info(f"Models loaded from {load_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            return False

    def get_feature_importance(self) -> Dict[str, List[Tuple[str, float]]]:
        """Get feature importance from all models"""
        importance = {}

        # XGBoost importance
        if self.xgb_model is not None and XGBOOST_AVAILABLE:
            xgb_importance = self.xgb_model.get_score(importance_type='gain')
            importance['xgboost'] = sorted(xgb_importance.items(), key=lambda x: x[1], reverse=True)

        # LightGBM importance
        if self.lgb_model is not None and LIGHTGBM_AVAILABLE:
            lgb_importance = dict(zip(
                self.feature_engineer.feature_names,
                self.lgb_model.feature_importance(importance_type='gain')
            ))
            importance['lightgbm'] = sorted(lgb_importance.items(), key=lambda x: x[1], reverse=True)

        return importance

    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            'is_trained': self.is_trained,
            'xgboost_available': XGBOOST_AVAILABLE and self.xgb_model is not None,
            'lightgbm_available': LIGHTGBM_AVAILABLE and self.lgb_model is not None,
            'neural_network_available': PYTORCH_AVAILABLE and self.nn_model is not None,
            'num_features': len(self.feature_engineer.feature_names),
            'num_predictions': len(self.predictions),
            'walk_forward_folds': len(self.walk_forward_results),
            'config': {
                'confidence_threshold': self.config.confidence_threshold,
                'max_daily_drawdown': self.config.max_daily_drawdown,
                'max_total_drawdown': self.config.max_total_drawdown
            }
        }


# Singleton instance
_beast_engine: Optional[BEASTMLEngine] = None


def get_beast_engine() -> BEASTMLEngine:
    """Get or create BEAST ML Engine singleton"""
    global _beast_engine
    if _beast_engine is None:
        _beast_engine = BEASTMLEngine()
    return _beast_engine
