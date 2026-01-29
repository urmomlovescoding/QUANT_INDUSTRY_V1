"""
QUANT_INDUSTRY_V1 ML Risk Prediction Model

Machine learning model for predictive risk management:
- Drawdown prediction
- Volatility regime classification
- Risk event probability estimation
- Dynamic position adjustment signals

Target: Reduce drawdowns by 15%, increase Sharpe by 0.3

Rollback Plan: Delete this file, revert to rule-based risk
Tests Required: Prediction accuracy, false positive rate
Failure Modes: Fall back to conservative risk limits
"""

import time
import logging
import pickle
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

try:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# =============================================================================
# RISK PREDICTION TYPES
# =============================================================================

class RiskRegime(Enum):
    """Market risk regimes."""
    LOW = "low"           # Normal, low volatility
    ELEVATED = "elevated" # Above average volatility
    HIGH = "high"         # High volatility, increased risk
    CRISIS = "crisis"     # Extreme volatility, tail risk


class RiskEventType(Enum):
    """Types of risk events to predict."""
    DRAWDOWN_5PCT = "drawdown_5pct"    # 5% drawdown within N days
    DRAWDOWN_10PCT = "drawdown_10pct"  # 10% drawdown
    VOL_SPIKE = "vol_spike"            # Volatility spike >2x
    REGIME_CHANGE = "regime_change"    # Volatility regime shift
    CORRELATION_BREAK = "correlation_break"  # Correlation breakdown


@dataclass
class RiskPrediction:
    """Risk model prediction output."""
    timestamp: datetime
    regime: RiskRegime
    regime_confidence: float
    
    # Event probabilities (0-1)
    prob_drawdown_5pct: float
    prob_drawdown_10pct: float
    prob_vol_spike: float
    
    # Recommended actions
    position_scale: float  # 0-1, multiply positions by this
    hedge_signal: float    # 0-1, strength of hedge recommendation
    
    # Model metadata
    model_version: str
    prediction_latency_ms: float
    features_used: List[str] = field(default_factory=list)
    
    @property
    def overall_risk_score(self) -> float:
        """Composite risk score 0-1."""
        return (
            0.3 * self.prob_drawdown_5pct +
            0.3 * self.prob_drawdown_10pct +
            0.2 * self.prob_vol_spike +
            0.2 * (1 - self.position_scale)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'regime': self.regime.value,
            'regime_confidence': self.regime_confidence,
            'prob_drawdown_5pct': self.prob_drawdown_5pct,
            'prob_drawdown_10pct': self.prob_drawdown_10pct,
            'prob_vol_spike': self.prob_vol_spike,
            'position_scale': self.position_scale,
            'hedge_signal': self.hedge_signal,
            'overall_risk_score': self.overall_risk_score,
        }


@dataclass
class RiskFeatures:
    """Input features for risk prediction."""
    # Returns
    return_1d: float
    return_5d: float
    return_20d: float
    
    # Volatility
    realized_vol_5d: float
    realized_vol_20d: float
    vol_of_vol: float  # Volatility of volatility
    
    # Drawdown
    current_drawdown: float
    max_drawdown_20d: float
    drawdown_duration: int  # Days in drawdown
    
    # Market structure
    vix: float
    vix_term_structure: float  # VIX - VIX3M
    correlation_sp500: float
    
    # Momentum
    rsi_14: float
    macd_signal: float
    
    # Volume
    volume_ratio: float  # Current vs 20d avg
    
    def to_array(self) -> np.ndarray:
        """Convert to feature array."""
        return np.array([
            self.return_1d, self.return_5d, self.return_20d,
            self.realized_vol_5d, self.realized_vol_20d, self.vol_of_vol,
            self.current_drawdown, self.max_drawdown_20d, self.drawdown_duration,
            self.vix, self.vix_term_structure, self.correlation_sp500,
            self.rsi_14, self.macd_signal, self.volume_ratio,
        ])
    
    @classmethod
    def feature_names(cls) -> List[str]:
        return [
            'return_1d', 'return_5d', 'return_20d',
            'realized_vol_5d', 'realized_vol_20d', 'vol_of_vol',
            'current_drawdown', 'max_drawdown_20d', 'drawdown_duration',
            'vix', 'vix_term_structure', 'correlation_sp500',
            'rsi_14', 'macd_signal', 'volume_ratio',
        ]


# =============================================================================
# BASE RISK MODEL
# =============================================================================

class BaseRiskModel(ABC):
    """Abstract base for risk prediction models."""
    
    def __init__(self, model_id: str, version: str = "1.0.0"):
        self.model_id = model_id
        self.version = version
        self._is_trained = False
        self._scaler = None
    
    @abstractmethod
    def train(self, features: np.ndarray, labels: np.ndarray) -> Dict[str, float]:
        """Train the model."""
        pass
    
    @abstractmethod
    def predict(self, features: RiskFeatures) -> RiskPrediction:
        """Make prediction."""
        pass
    
    @abstractmethod
    def save(self, path: Path) -> None:
        """Save model to disk."""
        pass
    
    @abstractmethod
    def load(self, path: Path) -> None:
        """Load model from disk."""
        pass


# =============================================================================
# GRADIENT BOOSTING RISK MODEL
# =============================================================================

class GradientBoostingRiskModel(BaseRiskModel):
    """
    Gradient boosting model for risk prediction.
    
    Uses separate classifiers for:
    - Volatility regime classification
    - Drawdown probability estimation
    """
    
    def __init__(self, model_id: str = "gb_risk_v1"):
        super().__init__(model_id)
        
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn required. pip install scikit-learn")
        
        # Separate models for different tasks
        self._regime_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42
        )
        
        self._drawdown_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42
        )
        
        self._vol_spike_model = GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            random_state=42
        )
        
        self._scaler = StandardScaler()
    
    def train(
        self,
        features: np.ndarray,
        regime_labels: np.ndarray,
        drawdown_labels: np.ndarray,
        vol_spike_labels: np.ndarray,
    ) -> Dict[str, float]:
        """
        Train all risk models.
        
        Args:
            features: Feature matrix (n_samples, n_features)
            regime_labels: Regime class labels (0=low, 1=elevated, 2=high, 3=crisis)
            drawdown_labels: Binary drawdown occurrence labels
            vol_spike_labels: Binary volatility spike labels
            
        Returns:
            Dictionary of training metrics
        """
        logger.info(f"Training risk models on {len(features)} samples")
        
        # Fit scaler
        features_scaled = self._scaler.fit_transform(features)
        
        # Split data
        X_train, X_test, y_regime_train, y_regime_test = train_test_split(
            features_scaled, regime_labels, test_size=0.2, random_state=42
        )
        _, _, y_dd_train, y_dd_test = train_test_split(
            features_scaled, drawdown_labels, test_size=0.2, random_state=42
        )
        _, _, y_vol_train, y_vol_test = train_test_split(
            features_scaled, vol_spike_labels, test_size=0.2, random_state=42
        )
        
        # Train regime model
        self._regime_model.fit(X_train, y_regime_train)
        regime_acc = self._regime_model.score(X_test, y_regime_test)
        
        # Train drawdown model
        self._drawdown_model.fit(X_train, y_dd_train)
        dd_acc = self._drawdown_model.score(X_test, y_dd_test)
        
        # Train vol spike model
        self._vol_spike_model.fit(X_train, y_vol_train)
        vol_acc = self._vol_spike_model.score(X_test, y_vol_test)
        
        self._is_trained = True
        
        metrics = {
            'regime_accuracy': regime_acc,
            'drawdown_accuracy': dd_acc,
            'vol_spike_accuracy': vol_acc,
            'n_samples': len(features),
        }
        
        logger.info(f"Training complete: {metrics}")
        return metrics
    
    def predict(self, features: RiskFeatures) -> RiskPrediction:
        """Predict risk metrics from features."""
        start = time.perf_counter()
        
        if not self._is_trained:
            return self._default_prediction()
        
        # Scale features
        X = features.to_array().reshape(1, -1)
        X_scaled = self._scaler.transform(X)
        
        # Regime prediction
        regime_probs = self._regime_model.predict_proba(X_scaled)[0]
        regime_class = np.argmax(regime_probs)
        regime = [RiskRegime.LOW, RiskRegime.ELEVATED, RiskRegime.HIGH, RiskRegime.CRISIS][regime_class]
        
        # Drawdown probability
        dd_probs = self._drawdown_model.predict_proba(X_scaled)[0]
        prob_drawdown = dd_probs[1] if len(dd_probs) > 1 else 0.0
        
        # Vol spike probability
        vol_probs = self._vol_spike_model.predict_proba(X_scaled)[0]
        prob_vol_spike = vol_probs[1] if len(vol_probs) > 1 else 0.0
        
        # Calculate position scaling (inverse of risk)
        risk_score = (prob_drawdown + prob_vol_spike + regime_class / 3) / 3
        position_scale = max(0.2, 1.0 - risk_score * 0.8)
        
        # Hedge signal
        hedge_signal = min(1.0, prob_drawdown + prob_vol_spike * 0.5)
        
        latency_ms = (time.perf_counter() - start) * 1000
        
        return RiskPrediction(
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            regime_confidence=float(regime_probs[regime_class]),
            prob_drawdown_5pct=float(prob_drawdown * 0.7),  # Scaled for 5%
            prob_drawdown_10pct=float(prob_drawdown * 0.3),  # Scaled for 10%
            prob_vol_spike=float(prob_vol_spike),
            position_scale=float(position_scale),
            hedge_signal=float(hedge_signal),
            model_version=self.version,
            prediction_latency_ms=latency_ms,
            features_used=RiskFeatures.feature_names(),
        )
    
    def _default_prediction(self) -> RiskPrediction:
        """Return conservative prediction when model not trained."""
        return RiskPrediction(
            timestamp=datetime.now(timezone.utc),
            regime=RiskRegime.ELEVATED,
            regime_confidence=0.5,
            prob_drawdown_5pct=0.3,
            prob_drawdown_10pct=0.1,
            prob_vol_spike=0.2,
            position_scale=0.5,
            hedge_signal=0.3,
            model_version=self.version,
            prediction_latency_ms=0.0,
            features_used=[],
        )
    
    def save(self, path: Path) -> None:
        """Save model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        state = {
            'model_id': self.model_id,
            'version': self.version,
            'regime_model': self._regime_model,
            'drawdown_model': self._drawdown_model,
            'vol_spike_model': self._vol_spike_model,
            'scaler': self._scaler,
            'is_trained': self._is_trained,
        }
        
        with open(path, 'wb') as f:
            pickle.dump(state, f)
        
        logger.info(f"Risk model saved to {path}")
    
    def load(self, path: Path) -> None:
        """Load model from disk."""
        path = Path(path)
        
        with open(path, 'rb') as f:
            state = pickle.load(f)
        
        self.model_id = state['model_id']
        self.version = state['version']
        self._regime_model = state['regime_model']
        self._drawdown_model = state['drawdown_model']
        self._vol_spike_model = state['vol_spike_model']
        self._scaler = state['scaler']
        self._is_trained = state['is_trained']
        
        logger.info(f"Risk model loaded from {path}")


# =============================================================================
# NEURAL NETWORK RISK MODEL (TensorFlow)
# =============================================================================

class NeuralRiskModel(BaseRiskModel):
    """
    Neural network model for risk prediction.
    
    Architecture: MLP with attention for temporal features.
    """
    
    def __init__(self, model_id: str = "nn_risk_v1"):
        super().__init__(model_id)
        
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow required. pip install tensorflow")
        
        self._model = None
        self._scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self._build_model()
    
    def _build_model(self) -> None:
        """Build neural network architecture."""
        n_features = len(RiskFeatures.feature_names())
        
        inputs = tf.keras.Input(shape=(n_features,), name='features')
        
        # Hidden layers with dropout
        x = tf.keras.layers.Dense(64, activation='relu')(inputs)
        x = tf.keras.layers.BatchNormalization()(x)
        x = tf.keras.layers.Dropout(0.3)(x)
        
        x = tf.keras.layers.Dense(32, activation='relu')(x)
        x = tf.keras.layers.BatchNormalization()(x)
        x = tf.keras.layers.Dropout(0.2)(x)
        
        x = tf.keras.layers.Dense(16, activation='relu')(x)
        
        # Multi-task outputs
        regime_out = tf.keras.layers.Dense(4, activation='softmax', name='regime')(x)
        drawdown_out = tf.keras.layers.Dense(1, activation='sigmoid', name='drawdown')(x)
        vol_spike_out = tf.keras.layers.Dense(1, activation='sigmoid', name='vol_spike')(x)
        
        self._model = tf.keras.Model(
            inputs=inputs,
            outputs=[regime_out, drawdown_out, vol_spike_out]
        )
        
        self._model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss={
                'regime': 'sparse_categorical_crossentropy',
                'drawdown': 'binary_crossentropy',
                'vol_spike': 'binary_crossentropy',
            },
            loss_weights={'regime': 1.0, 'drawdown': 1.5, 'vol_spike': 1.0},
            metrics={'regime': 'accuracy', 'drawdown': 'accuracy', 'vol_spike': 'accuracy'}
        )
    
    def train(
        self,
        features: np.ndarray,
        regime_labels: np.ndarray,
        drawdown_labels: np.ndarray,
        vol_spike_labels: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
    ) -> Dict[str, float]:
        """Train neural network."""
        logger.info(f"Training neural risk model on {len(features)} samples")
        
        # Scale features
        if self._scaler:
            features_scaled = self._scaler.fit_transform(features)
        else:
            features_scaled = features
        
        # Split data
        n_train = int(len(features) * 0.8)
        
        X_train = features_scaled[:n_train]
        X_test = features_scaled[n_train:]
        
        history = self._model.fit(
            X_train,
            {
                'regime': regime_labels[:n_train],
                'drawdown': drawdown_labels[:n_train],
                'vol_spike': vol_spike_labels[:n_train],
            },
            validation_data=(
                X_test,
                {
                    'regime': regime_labels[n_train:],
                    'drawdown': drawdown_labels[n_train:],
                    'vol_spike': vol_spike_labels[n_train:],
                }
            ),
            epochs=epochs,
            batch_size=batch_size,
            verbose=0,
        )
        
        self._is_trained = True
        
        metrics = {
            'regime_accuracy': float(history.history['val_regime_accuracy'][-1]),
            'drawdown_accuracy': float(history.history['val_drawdown_accuracy'][-1]),
            'vol_spike_accuracy': float(history.history['val_vol_spike_accuracy'][-1]),
            'n_samples': len(features),
            'epochs': epochs,
        }
        
        logger.info(f"Training complete: {metrics}")
        return metrics
    
    def predict(self, features: RiskFeatures) -> RiskPrediction:
        """Predict risk using neural network."""
        start = time.perf_counter()
        
        if not self._is_trained:
            return self._default_prediction()
        
        # Scale features
        X = features.to_array().reshape(1, -1)
        if self._scaler:
            X = self._scaler.transform(X)
        
        # Predict
        regime_probs, drawdown_prob, vol_spike_prob = self._model.predict(X, verbose=0)
        
        regime_class = np.argmax(regime_probs[0])
        regime = [RiskRegime.LOW, RiskRegime.ELEVATED, RiskRegime.HIGH, RiskRegime.CRISIS][regime_class]
        
        prob_drawdown = float(drawdown_prob[0][0])
        prob_vol_spike = float(vol_spike_prob[0][0])
        
        # Position scaling
        risk_score = (prob_drawdown + prob_vol_spike + regime_class / 3) / 3
        position_scale = max(0.2, 1.0 - risk_score * 0.8)
        
        latency_ms = (time.perf_counter() - start) * 1000
        
        return RiskPrediction(
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            regime_confidence=float(regime_probs[0][regime_class]),
            prob_drawdown_5pct=prob_drawdown * 0.7,
            prob_drawdown_10pct=prob_drawdown * 0.3,
            prob_vol_spike=prob_vol_spike,
            position_scale=position_scale,
            hedge_signal=min(1.0, prob_drawdown + prob_vol_spike * 0.5),
            model_version=self.version,
            prediction_latency_ms=latency_ms,
            features_used=RiskFeatures.feature_names(),
        )
    
    def _default_prediction(self) -> RiskPrediction:
        """Return conservative prediction when model not trained."""
        return RiskPrediction(
            timestamp=datetime.now(timezone.utc),
            regime=RiskRegime.ELEVATED,
            regime_confidence=0.5,
            prob_drawdown_5pct=0.3,
            prob_drawdown_10pct=0.1,
            prob_vol_spike=0.2,
            position_scale=0.5,
            hedge_signal=0.3,
            model_version=self.version,
            prediction_latency_ms=0.0,
            features_used=[],
        )
    
    def save(self, path: Path) -> None:
        """Save model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save Keras model
        self._model.save(str(path / 'model.keras'))
        
        # Save scaler and metadata
        meta = {
            'model_id': self.model_id,
            'version': self.version,
            'is_trained': self._is_trained,
            'scaler': self._scaler,
        }
        with open(path / 'metadata.pkl', 'wb') as f:
            pickle.dump(meta, f)
        
        logger.info(f"Neural risk model saved to {path}")
    
    def load(self, path: Path) -> None:
        """Load model from disk."""
        path = Path(path)
        
        self._model = tf.keras.models.load_model(str(path / 'model.keras'))
        
        with open(path / 'metadata.pkl', 'rb') as f:
            meta = pickle.load(f)
        
        self.model_id = meta['model_id']
        self.version = meta['version']
        self._is_trained = meta['is_trained']
        self._scaler = meta['scaler']
        
        logger.info(f"Neural risk model loaded from {path}")


# =============================================================================
# RISK PREDICTION SERVICE
# =============================================================================

class RiskPredictionService:
    """
    High-level service for risk prediction.
    
    Features:
    - Model selection and fallback
    - Feature computation
    - Prediction caching
    - Model monitoring
    """
    
    def __init__(
        self,
        model: BaseRiskModel = None,
        cache_ttl_seconds: int = 60,
    ):
        self.model = model or self._create_default_model()
        self.cache_ttl_seconds = cache_ttl_seconds
        
        self._cache: Dict[str, Tuple[RiskPrediction, datetime]] = {}
        self._predictions_made = 0
        self._cache_hits = 0
        
        logger.info(f"RiskPredictionService initialized with {type(self.model).__name__}")
    
    def _create_default_model(self) -> BaseRiskModel:
        """Create default risk model."""
        if SKLEARN_AVAILABLE:
            return GradientBoostingRiskModel()
        else:
            # Return a simple rule-based fallback
            return RuleBasedRiskModel()
    
    def predict(
        self,
        features: RiskFeatures,
        symbol: str = "PORTFOLIO",
        use_cache: bool = True,
    ) -> RiskPrediction:
        """
        Get risk prediction.
        
        Args:
            features: Input features
            symbol: Symbol or portfolio ID for caching
            use_cache: Whether to use cached predictions
            
        Returns:
            RiskPrediction
        """
        # Check cache
        if use_cache and symbol in self._cache:
            cached_pred, cached_time = self._cache[symbol]
            age = (datetime.now(timezone.utc) - cached_time).total_seconds()
            if age < self.cache_ttl_seconds:
                self._cache_hits += 1
                return cached_pred
        
        # Make prediction
        prediction = self.model.predict(features)
        self._predictions_made += 1
        
        # Cache
        self._cache[symbol] = (prediction, datetime.now(timezone.utc))
        
        return prediction
    
    def compute_features_from_returns(
        self,
        returns: np.ndarray,
        vix: float = 20.0,
    ) -> RiskFeatures:
        """
        Compute risk features from return series.
        
        Args:
            returns: Array of daily returns
            vix: Current VIX level
            
        Returns:
            RiskFeatures for prediction
        """
        if len(returns) < 20:
            returns = np.concatenate([np.zeros(20 - len(returns)), returns])
        
        # Compute features
        prices = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(prices)
        drawdowns = (prices - running_max) / running_max
        
        return RiskFeatures(
            return_1d=returns[-1] if len(returns) > 0 else 0,
            return_5d=np.sum(returns[-5:]) if len(returns) >= 5 else 0,
            return_20d=np.sum(returns[-20:]) if len(returns) >= 20 else 0,
            realized_vol_5d=np.std(returns[-5:]) * np.sqrt(252) if len(returns) >= 5 else 0.2,
            realized_vol_20d=np.std(returns[-20:]) * np.sqrt(252) if len(returns) >= 20 else 0.2,
            vol_of_vol=np.std([np.std(returns[i:i+5]) for i in range(len(returns)-5)]) if len(returns) >= 10 else 0.05,
            current_drawdown=drawdowns[-1],
            max_drawdown_20d=np.min(drawdowns[-20:]) if len(drawdowns) >= 20 else 0,
            drawdown_duration=self._count_drawdown_duration(drawdowns),
            vix=vix,
            vix_term_structure=0.0,  # Would need VIX3M
            correlation_sp500=0.5,   # Would need SPY data
            rsi_14=self._compute_rsi(returns, 14),
            macd_signal=0.0,         # Simplified
            volume_ratio=1.0,        # Would need volume data
        )
    
    def _count_drawdown_duration(self, drawdowns: np.ndarray) -> int:
        """Count consecutive days in drawdown."""
        duration = 0
        for dd in reversed(drawdowns):
            if dd < -0.01:  # In drawdown (>1%)
                duration += 1
            else:
                break
        return duration
    
    def _compute_rsi(self, returns: np.ndarray, period: int = 14) -> float:
        """Compute RSI from returns."""
        if len(returns) < period:
            return 50.0
        
        gains = np.maximum(returns[-period:], 0)
        losses = np.maximum(-returns[-period:], 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            'model_type': type(self.model).__name__,
            'model_version': self.model.version,
            'predictions_made': self._predictions_made,
            'cache_hits': self._cache_hits,
            'cache_hit_rate': self._cache_hits / max(1, self._predictions_made),
            'cached_symbols': len(self._cache),
        }


# =============================================================================
# RULE-BASED FALLBACK
# =============================================================================

class RuleBasedRiskModel(BaseRiskModel):
    """Simple rule-based risk model as fallback."""
    
    def __init__(self):
        super().__init__("rule_based", "1.0.0")
        self._is_trained = True  # Always "trained"
    
    def train(self, features: np.ndarray, labels: np.ndarray) -> Dict[str, float]:
        return {'status': 'rule_based_no_training'}
    
    def predict(self, features: RiskFeatures) -> RiskPrediction:
        """Rule-based risk prediction."""
        # Regime based on volatility
        if features.realized_vol_20d > 0.4:
            regime = RiskRegime.CRISIS
        elif features.realized_vol_20d > 0.25:
            regime = RiskRegime.HIGH
        elif features.realized_vol_20d > 0.15:
            regime = RiskRegime.ELEVATED
        else:
            regime = RiskRegime.LOW
        
        # Drawdown probability based on current drawdown and momentum
        prob_dd = min(1.0, max(0.0, -features.current_drawdown + 0.1))
        if features.rsi_14 < 30:
            prob_dd *= 1.5
        
        # Vol spike based on vol of vol
        prob_vol = min(1.0, features.vol_of_vol / 0.1)
        
        # Position scaling
        position_scale = 1.0
        if regime == RiskRegime.CRISIS:
            position_scale = 0.3
        elif regime == RiskRegime.HIGH:
            position_scale = 0.5
        elif regime == RiskRegime.ELEVATED:
            position_scale = 0.7
        
        return RiskPrediction(
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            regime_confidence=0.6,
            prob_drawdown_5pct=prob_dd * 0.7,
            prob_drawdown_10pct=prob_dd * 0.3,
            prob_vol_spike=prob_vol,
            position_scale=position_scale,
            hedge_signal=prob_dd,
            model_version=self.version,
            prediction_latency_ms=0.1,
            features_used=RiskFeatures.feature_names(),
        )
    
    def save(self, path: Path) -> None:
        pass
    
    def load(self, path: Path) -> None:
        pass


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_risk_prediction_service() -> RiskPredictionService:
    """Create a risk prediction service with best available model."""
    if TF_AVAILABLE:
        try:
            model = NeuralRiskModel()
            return RiskPredictionService(model=model)
        except Exception:
            pass
    
    if SKLEARN_AVAILABLE:
        model = GradientBoostingRiskModel()
        return RiskPredictionService(model=model)
    
    # Fallback to rule-based
    return RiskPredictionService(model=RuleBasedRiskModel())
