"""
QUANT_INDUSTRY_V1 Supervised Models

Ensemble of ML models for signal generation.

Rollback Plan: Delete this file
Tests Required: Model training, prediction accuracy, ensemble weights
Failure Modes: Model error -> fallback to rule-based
"""

import numpy as np
import pickle
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


# =============================================================================
# MODEL TYPES
# =============================================================================

class ModelType(Enum):
    """Types of models."""
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    NEURAL_NET = "neural_net"
    RULE_BASED = "rule_based"


class PredictionType(Enum):
    """Types of predictions."""
    DIRECTION = "direction"  # Long/Short/Neutral
    PROBABILITY = "probability"  # P(up)
    RETURNS = "returns"  # Expected return
    VOLATILITY = "volatility"  # Expected volatility


@dataclass
class Prediction:
    """Model prediction with confidence."""
    direction: int  # 1=long, -1=short, 0=neutral
    probability: float  # P(direction correct)
    expected_return: float
    confidence: float
    model_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'direction': self.direction,
            'probability': self.probability,
            'expected_return': self.expected_return,
            'confidence': self.confidence,
            'model_id': self.model_id,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
        }


# =============================================================================
# BASE MODEL
# =============================================================================

class BaseModel(ABC):
    """Abstract base class for all models."""

    def __init__(self, model_id: str = None, model_type: ModelType = None):
        self.model_id = model_id or self._generate_id()
        self.model_type = model_type
        self.is_trained = False
        self.feature_names: List[str] = []
        self.metrics = ModelMetrics()
        self.hyperparams: Dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc)
        self.trained_at: Optional[datetime] = None

    def _generate_id(self) -> str:
        """Generate unique model ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_suffix = hashlib.md5(str(np.random.random()).encode()).hexdigest()[:6]
        return f"{self.model_type.value if self.model_type else 'model'}_{timestamp}_{random_suffix}"

    @abstractmethod
    def train(self, X: np.ndarray, y: np.ndarray, **kwargs) -> 'BaseModel':
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions."""
        pass

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities."""
        pass

    def save(self, path: str) -> None:
        """Save model to disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        logger.info(f"Model saved to {path}")

    @classmethod
    def load(cls, path: str) -> 'BaseModel':
        """Load model from disk."""
        with open(path, 'rb') as f:
            model = pickle.load(f)
        logger.info(f"Model loaded from {path}")
        return model

    def get_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            'model_id': self.model_id,
            'model_type': self.model_type.value if self.model_type else None,
            'is_trained': self.is_trained,
            'feature_names': self.feature_names,
            'metrics': self.metrics.to_dict(),
            'hyperparams': self.hyperparams,
            'created_at': self.created_at.isoformat(),
            'trained_at': self.trained_at.isoformat() if self.trained_at else None,
        }


# =============================================================================
# GRADIENT BOOSTING MODELS
# =============================================================================

class XGBoostModel(BaseModel):
    """XGBoost classifier for direction prediction."""

    def __init__(self, **hyperparams):
        super().__init__(model_type=ModelType.XGBOOST)
        self.hyperparams = {
            'n_estimators': 100,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'use_label_encoder': False,
            'random_state': 42,
            **hyperparams
        }
        self._model = None

    def train(self, X: np.ndarray, y: np.ndarray, **kwargs) -> 'XGBoostModel':
        """Train XGBoost model."""
        try:
            import xgboost as xgb

            self._model = xgb.XGBClassifier(**self.hyperparams)
            self._model.fit(X, y, **kwargs)
            self.is_trained = True
            self.trained_at = datetime.now(timezone.utc)

            logger.info(f"XGBoost model trained: {self.model_id}")
            return self

        except ImportError:
            logger.error("XGBoost not installed")
            raise

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict direction."""
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self._model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities."""
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self._model.predict_proba(X)

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance."""
        if not self.is_trained:
            return {}
        importance = self._model.feature_importances_
        return dict(zip(self.feature_names, importance))


class LightGBMModel(BaseModel):
    """LightGBM classifier."""

    def __init__(self, **hyperparams):
        super().__init__(model_type=ModelType.LIGHTGBM)
        self.hyperparams = {
            'n_estimators': 100,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'objective': 'binary',
            'metric': 'binary_logloss',
            'random_state': 42,
            'verbose': -1,
            **hyperparams
        }
        self._model = None

    def train(self, X: np.ndarray, y: np.ndarray, **kwargs) -> 'LightGBMModel':
        """Train LightGBM model."""
        try:
            import lightgbm as lgb

            self._model = lgb.LGBMClassifier(**self.hyperparams)
            self._model.fit(X, y, **kwargs)
            self.is_trained = True
            self.trained_at = datetime.now(timezone.utc)

            logger.info(f"LightGBM model trained: {self.model_id}")
            return self

        except ImportError:
            logger.error("LightGBM not installed")
            raise

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self._model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self._model.predict_proba(X)


class RandomForestModel(BaseModel):
    """Random Forest classifier."""

    def __init__(self, **hyperparams):
        super().__init__(model_type=ModelType.RANDOM_FOREST)
        self.hyperparams = {
            'n_estimators': 100,
            'max_depth': 10,
            'min_samples_split': 5,
            'min_samples_leaf': 2,
            'random_state': 42,
            'n_jobs': -1,
            **hyperparams
        }
        self._model = None

    def train(self, X: np.ndarray, y: np.ndarray, **kwargs) -> 'RandomForestModel':
        """Train Random Forest model."""
        from sklearn.ensemble import RandomForestClassifier

        self._model = RandomForestClassifier(**self.hyperparams)
        self._model.fit(X, y)
        self.is_trained = True
        self.trained_at = datetime.now(timezone.utc)

        logger.info(f"Random Forest model trained: {self.model_id}")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self._model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self._model.predict_proba(X)


# =============================================================================
# RULE-BASED MODEL (FALLBACK)
# =============================================================================

class RuleBasedModel(BaseModel):
    """
    Rule-based model as fallback.

    Uses simple technical rules when ML models fail.
    """

    def __init__(self):
        super().__init__(model_type=ModelType.RULE_BASED)
        self.is_trained = True  # Always "trained"
        self.rules = {
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'macd_threshold': 0,
            'trend_threshold': 0.01,
        }

    def train(self, X: np.ndarray, y: np.ndarray, **kwargs) -> 'RuleBasedModel':
        """No training needed for rule-based."""
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict using rules."""
        predictions = []
        for features in X:
            pred = self._apply_rules(features)
            predictions.append(pred)
        return np.array(predictions)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return confidence based on signal strength."""
        probas = []
        for features in X:
            pred = self._apply_rules(features)
            # Convert to probability
            if pred == 1:
                probas.append([0.3, 0.7])
            elif pred == 0:
                probas.append([0.7, 0.3])
            else:
                probas.append([0.5, 0.5])
        return np.array(probas)

    def _apply_rules(self, features: np.ndarray) -> int:
        """Apply trading rules to features."""
        # Assume standard feature order
        # This is a simplified rule set
        try:
            rsi = features[10] * 100 if len(features) > 10 else 50  # rsi_14
            macd = features[12] if len(features) > 12 else 0  # macd
            trend = features[28] if len(features) > 28 else 0  # trend_strength

            # Bullish signals
            bullish_count = 0
            if rsi < self.rules['rsi_oversold']:
                bullish_count += 1
            if macd > self.rules['macd_threshold']:
                bullish_count += 1
            if trend > self.rules['trend_threshold']:
                bullish_count += 1

            # Bearish signals
            bearish_count = 0
            if rsi > self.rules['rsi_overbought']:
                bearish_count += 1
            if macd < -self.rules['macd_threshold']:
                bearish_count += 1
            if trend < -self.rules['trend_threshold']:
                bearish_count += 1

            if bullish_count >= 2:
                return 1
            elif bearish_count >= 2:
                return 0
            else:
                return -1  # Neutral

        except Exception:
            return -1  # Neutral on error


# =============================================================================
# ENSEMBLE MODEL
# =============================================================================

class EnsembleModel:
    """
    Ensemble of multiple models with weighted voting.

    Features:
    - Multiple model types
    - Configurable weights
    - Automatic weight optimization
    - Fallback to rule-based
    """

    def __init__(
        self,
        models: List[BaseModel] = None,
        weights: List[float] = None,
        fallback: BaseModel = None,
    ):
        self.models = models or []
        self.weights = weights or [1.0 / len(self.models)] * len(self.models) if self.models else []
        self.fallback = fallback or RuleBasedModel()
        self.model_id = f"ensemble_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def add_model(self, model: BaseModel, weight: float = 1.0) -> None:
        """Add a model to the ensemble."""
        self.models.append(model)
        self.weights.append(weight)
        self._normalize_weights()

    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1."""
        total = sum(self.weights)
        if total > 0:
            self.weights = [w / total for w in self.weights]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make weighted ensemble prediction."""
        if not self.models:
            return self.fallback.predict(X)

        predictions = []
        for model in self.models:
            try:
                if model.is_trained:
                    pred = model.predict(X)
                    predictions.append(pred)
            except Exception as e:
                logger.warning(f"Model {model.model_id} prediction failed: {e}")

        if not predictions:
            return self.fallback.predict(X)

        # Weighted voting
        predictions = np.array(predictions)
        weights = np.array(self.weights[:len(predictions)])
        weights = weights / weights.sum()

        # Weighted sum
        weighted_pred = np.zeros(len(X))
        for i, pred in enumerate(predictions):
            weighted_pred += weights[i] * pred

        # Threshold
        return (weighted_pred > 0.5).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Get weighted probability estimates."""
        if not self.models:
            return self.fallback.predict_proba(X)

        probas = []
        valid_weights = []

        for i, model in enumerate(self.models):
            try:
                if model.is_trained:
                    proba = model.predict_proba(X)
                    probas.append(proba)
                    valid_weights.append(self.weights[i])
            except Exception as e:
                logger.warning(f"Model {model.model_id} proba failed: {e}")

        if not probas:
            return self.fallback.predict_proba(X)

        # Weighted average
        probas = np.array(probas)
        weights = np.array(valid_weights)
        weights = weights / weights.sum()

        weighted_proba = np.zeros_like(probas[0])
        for i, proba in enumerate(probas):
            weighted_proba += weights[i] * proba

        return weighted_proba

    def get_prediction(self, X: np.ndarray) -> Prediction:
        """Get structured prediction."""
        proba = self.predict_proba(X)

        if proba.shape[1] >= 2:
            prob_up = proba[0, 1]
        else:
            prob_up = proba[0, 0]

        direction = 1 if prob_up > 0.5 else (-1 if prob_up < 0.5 else 0)
        confidence = abs(prob_up - 0.5) * 2  # 0-1 scale

        return Prediction(
            direction=direction,
            probability=prob_up,
            expected_return=(prob_up - 0.5) * 0.02,  # Rough estimate
            confidence=confidence,
            model_id=self.model_id,
        )

    def update_weights(self, performance: List[float]) -> None:
        """Update weights based on recent performance."""
        if len(performance) != len(self.models):
            return

        # Simple performance-based weighting
        total_perf = sum(max(0, p) for p in performance)
        if total_perf > 0:
            self.weights = [max(0, p) / total_perf for p in performance]
        else:
            self._normalize_weights()

    def save(self, directory: str) -> None:
        """Save ensemble to directory."""
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)

        # Save metadata
        metadata = {
            'model_id': self.model_id,
            'model_count': len(self.models),
            'weights': self.weights,
        }
        with open(dir_path / 'ensemble_meta.json', 'w') as f:
            json.dump(metadata, f)

        # Save each model
        for i, model in enumerate(self.models):
            model.save(str(dir_path / f'model_{i}.pkl'))

        if self.fallback:
            self.fallback.save(str(dir_path / 'fallback.pkl'))

    @classmethod
    def load(cls, directory: str) -> 'EnsembleModel':
        """Load ensemble from directory."""
        dir_path = Path(directory)

        with open(dir_path / 'ensemble_meta.json', 'r') as f:
            metadata = json.load(f)

        models = []
        for i in range(metadata['model_count']):
            model_path = dir_path / f'model_{i}.pkl'
            if model_path.exists():
                models.append(BaseModel.load(str(model_path)))

        fallback = None
        fallback_path = dir_path / 'fallback.pkl'
        if fallback_path.exists():
            fallback = BaseModel.load(str(fallback_path))

        ensemble = cls(models=models, weights=metadata['weights'], fallback=fallback)
        ensemble.model_id = metadata['model_id']
        return ensemble
