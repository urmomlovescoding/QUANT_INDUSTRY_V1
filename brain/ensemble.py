"""
QUANT_INDUSTRY_V1 Ensemble Model Combiner

Advanced ensemble methods for combining multiple model predictions.

Features:
- Weighted averaging
- Stacking (meta-learning)
- Bayesian Model Averaging
- Dynamic weight optimization
- Regime-adaptive ensembles
- Online learning ensemble
- Diversity-based weighting
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict
import logging
from scipy.optimize import minimize
from scipy.special import softmax

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class EnsembleMethod(Enum):
    """Ensemble combination methods."""
    SIMPLE_AVERAGE = "simple_average"
    WEIGHTED_AVERAGE = "weighted_average"
    STACKING = "stacking"
    BAYESIAN = "bayesian"
    BOOSTING = "boosting"
    DYNAMIC = "dynamic"
    REGIME_ADAPTIVE = "regime_adaptive"


@dataclass
class ModelPrediction:
    """Single model prediction."""
    model_id: str
    prediction: float  # -1 to 1 for direction/strength
    confidence: float  # 0 to 1
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnsemblePrediction:
    """Combined ensemble prediction."""
    prediction: float
    confidence: float
    timestamp: datetime
    method: EnsembleMethod
    model_weights: Dict[str, float]
    model_predictions: Dict[str, ModelPrediction]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelPerformance:
    """Model performance metrics."""
    model_id: str
    accuracy: float
    sharpe_ratio: float
    max_drawdown: float
    information_coefficient: float
    hit_rate: float
    avg_return: float
    volatility: float
    recent_accuracy: float  # Last N predictions
    timestamp: datetime


# =============================================================================
# WEIGHTED AVERAGE ENSEMBLE
# =============================================================================

class WeightedAverageEnsemble:
    """
    Basic weighted average ensemble.
    """

    def __init__(
        self,
        initial_weights: Dict[str, float] = None,
        confidence_weighted: bool = True,
    ):
        self.weights = initial_weights or {}
        self.confidence_weighted = confidence_weighted

    def combine(
        self,
        predictions: Dict[str, ModelPrediction],
    ) -> EnsemblePrediction:
        """Combine predictions using weighted average."""
        if not predictions:
            return self._empty_prediction()

        # Normalize weights
        if self.weights:
            total_weight = sum(self.weights.get(m, 1.0) for m in predictions.keys())
            weights = {m: self.weights.get(m, 1.0) / total_weight for m in predictions.keys()}
        else:
            weights = {m: 1.0 / len(predictions) for m in predictions.keys()}

        # Calculate weighted average
        weighted_sum = 0.0
        confidence_sum = 0.0
        total_weight = 0.0

        for model_id, pred in predictions.items():
            w = weights[model_id]
            if self.confidence_weighted:
                effective_weight = w * pred.confidence
            else:
                effective_weight = w

            weighted_sum += pred.prediction * effective_weight
            confidence_sum += pred.confidence * w
            total_weight += effective_weight

        if total_weight > 0:
            final_pred = weighted_sum / total_weight
            final_conf = confidence_sum
        else:
            final_pred = 0.0
            final_conf = 0.0

        return EnsemblePrediction(
            prediction=final_pred,
            confidence=final_conf,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.WEIGHTED_AVERAGE,
            model_weights=weights,
            model_predictions=predictions,
        )

    def _empty_prediction(self) -> EnsemblePrediction:
        return EnsemblePrediction(
            prediction=0.0,
            confidence=0.0,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.WEIGHTED_AVERAGE,
            model_weights={},
            model_predictions={},
        )


# =============================================================================
# STACKING ENSEMBLE
# =============================================================================

class StackingEnsemble:
    """
    Stacking ensemble with meta-learner.

    Uses model predictions as features for a meta-model.
    """

    def __init__(
        self,
        meta_learner: str = 'ridge',  # 'ridge', 'linear', 'mlp'
        regularization: float = 1.0,
    ):
        self.meta_learner = meta_learner
        self.regularization = regularization
        self.meta_weights: Optional[np.ndarray] = None
        self.meta_bias: float = 0.0
        self.model_order: List[str] = []
        self._fitted = False

    def fit(
        self,
        X: Dict[str, np.ndarray],  # model_id -> predictions array
        y: np.ndarray,  # actual targets
    ) -> 'StackingEnsemble':
        """
        Fit meta-learner on model predictions.

        Args:
            X: Dict mapping model_id to their prediction history
            y: Actual target values
        """
        self.model_order = sorted(X.keys())
        n_samples = len(y)
        n_models = len(self.model_order)

        # Stack predictions into matrix
        pred_matrix = np.column_stack([X[m] for m in self.model_order])

        if self.meta_learner == 'ridge':
            # Ridge regression
            XtX = pred_matrix.T @ pred_matrix
            XtX += self.regularization * np.eye(n_models)
            Xty = pred_matrix.T @ y
            self.meta_weights = np.linalg.solve(XtX, Xty)
            self.meta_bias = np.mean(y) - np.mean(pred_matrix @ self.meta_weights)

        elif self.meta_learner == 'linear':
            # OLS
            XtX = pred_matrix.T @ pred_matrix + 1e-6 * np.eye(n_models)
            Xty = pred_matrix.T @ y
            self.meta_weights = np.linalg.solve(XtX, Xty)
            self.meta_bias = np.mean(y) - np.mean(pred_matrix @ self.meta_weights)

        else:
            # Simple average as fallback
            self.meta_weights = np.ones(n_models) / n_models
            self.meta_bias = 0.0

        self._fitted = True
        return self

    def combine(
        self,
        predictions: Dict[str, ModelPrediction],
    ) -> EnsemblePrediction:
        """Combine predictions using trained meta-learner."""
        if not self._fitted:
            # Fall back to simple average
            preds = [p.prediction for p in predictions.values()]
            return EnsemblePrediction(
                prediction=np.mean(preds) if preds else 0.0,
                confidence=np.mean([p.confidence for p in predictions.values()]) if predictions else 0.0,
                timestamp=datetime.now(timezone.utc),
                method=EnsembleMethod.STACKING,
                model_weights={m: 1.0 / len(predictions) for m in predictions},
                model_predictions=predictions,
                metadata={'warning': 'meta-learner not fitted'},
            )

        # Build prediction vector
        pred_vector = np.array([
            predictions[m].prediction if m in predictions else 0.0
            for m in self.model_order
        ])

        # Apply meta-learner
        final_pred = float(pred_vector @ self.meta_weights + self.meta_bias)

        # Confidence from individual models
        confs = [predictions[m].confidence for m in self.model_order if m in predictions]
        final_conf = np.mean(confs) if confs else 0.0

        return EnsemblePrediction(
            prediction=np.clip(final_pred, -1, 1),
            confidence=final_conf,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.STACKING,
            model_weights={m: float(w) for m, w in zip(self.model_order, self.meta_weights)},
            model_predictions=predictions,
        )


# =============================================================================
# BAYESIAN MODEL AVERAGING
# =============================================================================

class BayesianModelAveraging:
    """
    Bayesian Model Averaging.

    Weights models by their posterior probability.
    """

    def __init__(
        self,
        prior_weights: Dict[str, float] = None,
        likelihood_window: int = 50,
    ):
        self.prior_weights = prior_weights or {}
        self.likelihood_window = likelihood_window

        # Store prediction history for likelihood estimation
        self.prediction_history: Dict[str, List[float]] = defaultdict(list)
        self.target_history: List[float] = []
        self.posterior_weights: Dict[str, float] = {}

    def update(
        self,
        predictions: Dict[str, float],
        actual: float,
    ) -> None:
        """Update with new observation."""
        for model_id, pred in predictions.items():
            self.prediction_history[model_id].append(pred)

        self.target_history.append(actual)

        # Keep only recent history
        for model_id in list(self.prediction_history.keys()):
            if len(self.prediction_history[model_id]) > self.likelihood_window:
                self.prediction_history[model_id] = self.prediction_history[model_id][-self.likelihood_window:]

        if len(self.target_history) > self.likelihood_window:
            self.target_history = self.target_history[-self.likelihood_window:]

        # Update posteriors
        self._update_posteriors()

    def _update_posteriors(self) -> None:
        """Update posterior weights based on likelihood."""
        if len(self.target_history) < 10:
            return

        targets = np.array(self.target_history)
        log_likelihoods = {}

        for model_id, preds in self.prediction_history.items():
            if len(preds) < len(targets):
                continue

            preds_arr = np.array(preds[-len(targets):])

            # Estimate likelihood (Gaussian assumption)
            errors = targets - preds_arr
            mse = np.mean(errors ** 2)
            std = np.sqrt(mse) + 1e-6

            # Log-likelihood
            log_lik = -0.5 * len(targets) * np.log(2 * np.pi * std ** 2) - np.sum(errors ** 2) / (2 * std ** 2)
            log_likelihoods[model_id] = log_lik

        if not log_likelihoods:
            return

        # Add log prior
        log_posteriors = {}
        for model_id, log_lik in log_likelihoods.items():
            prior = self.prior_weights.get(model_id, 1.0 / len(log_likelihoods))
            log_posteriors[model_id] = log_lik + np.log(prior + 1e-10)

        # Normalize (softmax)
        max_log = max(log_posteriors.values())
        posteriors = {m: np.exp(lp - max_log) for m, lp in log_posteriors.items()}
        total = sum(posteriors.values())
        self.posterior_weights = {m: p / total for m, p in posteriors.items()}

    def combine(
        self,
        predictions: Dict[str, ModelPrediction],
    ) -> EnsemblePrediction:
        """Combine using Bayesian model averaging."""
        if not predictions:
            return self._empty_prediction()

        # Use posterior weights if available
        if self.posterior_weights:
            weights = {m: self.posterior_weights.get(m, 0.0) for m in predictions.keys()}
        else:
            weights = {m: 1.0 / len(predictions) for m in predictions.keys()}

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {m: w / total for m, w in weights.items()}

        # Weighted average
        weighted_sum = sum(
            weights[m] * p.prediction
            for m, p in predictions.items()
        )

        avg_conf = np.mean([p.confidence for p in predictions.values()])

        return EnsemblePrediction(
            prediction=weighted_sum,
            confidence=avg_conf,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.BAYESIAN,
            model_weights=weights,
            model_predictions=predictions,
            metadata={'posterior_weights': self.posterior_weights},
        )

    def _empty_prediction(self) -> EnsemblePrediction:
        return EnsemblePrediction(
            prediction=0.0,
            confidence=0.0,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.BAYESIAN,
            model_weights={},
            model_predictions={},
        )


# =============================================================================
# DYNAMIC WEIGHT OPTIMIZER
# =============================================================================

class DynamicWeightOptimizer:
    """
    Dynamically optimize ensemble weights based on recent performance.
    """

    def __init__(
        self,
        lookback: int = 100,
        optimization_method: str = 'sharpe',  # 'sharpe', 'accuracy', 'mse'
        update_frequency: int = 10,
        regularization: float = 0.01,
    ):
        self.lookback = lookback
        self.optimization_method = optimization_method
        self.update_frequency = update_frequency
        self.regularization = regularization

        self.prediction_history: Dict[str, List[float]] = defaultdict(list)
        self.target_history: List[float] = []
        self.optimal_weights: Dict[str, float] = {}
        self._update_counter = 0

    def update(
        self,
        predictions: Dict[str, float],
        actual: float,
    ) -> None:
        """Update with new observation."""
        for model_id, pred in predictions.items():
            self.prediction_history[model_id].append(pred)

        self.target_history.append(actual)

        # Trim history
        for model_id in list(self.prediction_history.keys()):
            if len(self.prediction_history[model_id]) > self.lookback:
                self.prediction_history[model_id] = self.prediction_history[model_id][-self.lookback:]

        if len(self.target_history) > self.lookback:
            self.target_history = self.target_history[-self.lookback:]

        # Periodic optimization
        self._update_counter += 1
        if self._update_counter >= self.update_frequency:
            self._optimize_weights()
            self._update_counter = 0

    def _optimize_weights(self) -> None:
        """Optimize weights based on historical performance."""
        if len(self.target_history) < 20:
            return

        model_ids = list(self.prediction_history.keys())
        n_models = len(model_ids)

        if n_models == 0:
            return

        targets = np.array(self.target_history)

        # Build prediction matrix
        min_len = min(len(self.prediction_history[m]) for m in model_ids)
        min_len = min(min_len, len(targets))

        pred_matrix = np.column_stack([
            np.array(self.prediction_history[m][-min_len:])
            for m in model_ids
        ])
        targets = targets[-min_len:]

        def objective(w):
            w = softmax(w)  # Ensure positive weights summing to 1
            combined = pred_matrix @ w

            if self.optimization_method == 'sharpe':
                # Maximize Sharpe-like ratio
                if np.std(combined) < 1e-6:
                    return 1e6
                correlation = np.corrcoef(combined, targets)[0, 1]
                return -correlation + self.regularization * np.sum(w ** 2)

            elif self.optimization_method == 'accuracy':
                # Maximize direction accuracy
                correct = np.sum(np.sign(combined) == np.sign(targets))
                return -(correct / len(targets)) + self.regularization * np.sum(w ** 2)

            else:  # mse
                mse = np.mean((combined - targets) ** 2)
                return mse + self.regularization * np.sum(w ** 2)

        # Optimize
        w0 = np.zeros(n_models)
        result = minimize(objective, w0, method='L-BFGS-B')

        if result.success:
            optimal = softmax(result.x)
            self.optimal_weights = {m: float(w) for m, w in zip(model_ids, optimal)}

    def get_weights(self) -> Dict[str, float]:
        """Get current optimal weights."""
        return self.optimal_weights.copy()


# =============================================================================
# REGIME-ADAPTIVE ENSEMBLE
# =============================================================================

class RegimeAdaptiveEnsemble:
    """
    Ensemble that adapts weights based on market regime.
    """

    def __init__(
        self,
        regime_weights: Dict[str, Dict[str, float]] = None,
    ):
        """
        Args:
            regime_weights: Dict mapping regime -> model_id -> weight
        """
        self.regime_weights = regime_weights or {}
        self.current_regime: Optional[str] = None

        # Performance tracking per regime
        self.regime_performance: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def set_regime(self, regime: str) -> None:
        """Set current market regime."""
        self.current_regime = regime

    def update_regime_weights(
        self,
        regime: str,
        weights: Dict[str, float],
    ) -> None:
        """Update weights for a specific regime."""
        self.regime_weights[regime] = weights

    def record_performance(
        self,
        regime: str,
        model_id: str,
        return_value: float,
    ) -> None:
        """Record model performance for regime."""
        self.regime_performance[regime][model_id].append(return_value)

        # Keep last 100
        if len(self.regime_performance[regime][model_id]) > 100:
            self.regime_performance[regime][model_id] = \
                self.regime_performance[regime][model_id][-100:]

    def combine(
        self,
        predictions: Dict[str, ModelPrediction],
        regime: str = None,
    ) -> EnsemblePrediction:
        """Combine predictions with regime-specific weights."""
        regime = regime or self.current_regime

        if not predictions:
            return self._empty_prediction()

        # Get regime-specific weights
        if regime and regime in self.regime_weights:
            weights = self.regime_weights[regime]
        else:
            # Equal weights if no regime-specific weights
            weights = {m: 1.0 / len(predictions) for m in predictions.keys()}

        # Normalize for available models
        available = {m: weights.get(m, 0.0) for m in predictions.keys()}
        total = sum(available.values())
        if total > 0:
            weights = {m: w / total for m, w in available.items()}
        else:
            weights = {m: 1.0 / len(predictions) for m in predictions.keys()}

        # Weighted combination
        weighted_sum = sum(
            weights[m] * p.prediction
            for m, p in predictions.items()
        )

        avg_conf = np.mean([p.confidence for p in predictions.values()])

        return EnsemblePrediction(
            prediction=weighted_sum,
            confidence=avg_conf,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.REGIME_ADAPTIVE,
            model_weights=weights,
            model_predictions=predictions,
            metadata={'regime': regime},
        )

    def _empty_prediction(self) -> EnsemblePrediction:
        return EnsemblePrediction(
            prediction=0.0,
            confidence=0.0,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.REGIME_ADAPTIVE,
            model_weights={},
            model_predictions={},
        )


# =============================================================================
# DIVERSITY-WEIGHTED ENSEMBLE
# =============================================================================

class DiversityWeightedEnsemble:
    """
    Weight models by their diversity contribution.

    Models that provide unique signals get higher weight.
    """

    def __init__(
        self,
        diversity_bonus: float = 0.3,
        correlation_lookback: int = 50,
    ):
        self.diversity_bonus = diversity_bonus
        self.correlation_lookback = correlation_lookback

        self.prediction_history: Dict[str, List[float]] = defaultdict(list)
        self.correlation_matrix: Optional[np.ndarray] = None
        self.model_order: List[str] = []

    def update(self, predictions: Dict[str, float]) -> None:
        """Update prediction history."""
        for model_id, pred in predictions.items():
            self.prediction_history[model_id].append(pred)

            if len(self.prediction_history[model_id]) > self.correlation_lookback:
                self.prediction_history[model_id] = \
                    self.prediction_history[model_id][-self.correlation_lookback:]

        # Update correlation matrix
        self._update_correlations()

    def _update_correlations(self) -> None:
        """Update inter-model correlation matrix."""
        model_ids = sorted(self.prediction_history.keys())
        n_models = len(model_ids)

        if n_models < 2:
            return

        min_len = min(len(self.prediction_history[m]) for m in model_ids)
        if min_len < 10:
            return

        pred_matrix = np.column_stack([
            np.array(self.prediction_history[m][-min_len:])
            for m in model_ids
        ])

        self.correlation_matrix = np.corrcoef(pred_matrix.T)
        self.model_order = model_ids

    def get_diversity_weights(self) -> Dict[str, float]:
        """Calculate diversity-based weights."""
        if self.correlation_matrix is None or len(self.model_order) == 0:
            return {}

        n_models = len(self.model_order)

        # Average absolute correlation with other models
        avg_correlations = []
        for i in range(n_models):
            correlations = []
            for j in range(n_models):
                if i != j:
                    correlations.append(abs(self.correlation_matrix[i, j]))
            avg_correlations.append(np.mean(correlations) if correlations else 0)

        # Lower correlation = higher diversity = higher weight
        diversity_scores = [1 - corr for corr in avg_correlations]

        # Normalize
        total = sum(diversity_scores)
        if total > 0:
            weights = {m: s / total for m, s in zip(self.model_order, diversity_scores)}
        else:
            weights = {m: 1.0 / n_models for m in self.model_order}

        return weights

    def combine(
        self,
        predictions: Dict[str, ModelPrediction],
        base_weights: Dict[str, float] = None,
    ) -> EnsemblePrediction:
        """Combine with diversity weighting."""
        if not predictions:
            return self._empty_prediction()

        # Get diversity weights
        diversity_weights = self.get_diversity_weights()

        # Combine with base weights
        if base_weights:
            final_weights = {}
            for m in predictions.keys():
                base = base_weights.get(m, 1.0 / len(predictions))
                diversity = diversity_weights.get(m, 1.0 / len(predictions))
                final_weights[m] = (1 - self.diversity_bonus) * base + self.diversity_bonus * diversity
        else:
            final_weights = diversity_weights

        # Normalize for available models
        available = {m: final_weights.get(m, 1.0 / len(predictions)) for m in predictions.keys()}
        total = sum(available.values())
        if total > 0:
            weights = {m: w / total for m, w in available.items()}
        else:
            weights = {m: 1.0 / len(predictions) for m in predictions.keys()}

        # Weighted combination
        weighted_sum = sum(
            weights[m] * p.prediction
            for m, p in predictions.items()
        )

        avg_conf = np.mean([p.confidence for p in predictions.values()])

        return EnsemblePrediction(
            prediction=weighted_sum,
            confidence=avg_conf,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.DYNAMIC,
            model_weights=weights,
            model_predictions=predictions,
            metadata={'diversity_weights': diversity_weights},
        )

    def _empty_prediction(self) -> EnsemblePrediction:
        return EnsemblePrediction(
            prediction=0.0,
            confidence=0.0,
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.DYNAMIC,
            model_weights={},
            model_predictions={},
        )


# =============================================================================
# UNIFIED ENSEMBLE COMBINER
# =============================================================================

class EnsembleCombiner:
    """
    Unified interface for all ensemble methods.
    """

    def __init__(
        self,
        default_method: EnsembleMethod = EnsembleMethod.WEIGHTED_AVERAGE,
    ):
        self.default_method = default_method

        # Initialize all methods
        self.weighted_avg = WeightedAverageEnsemble()
        self.stacking = StackingEnsemble()
        self.bayesian = BayesianModelAveraging()
        self.regime_adaptive = RegimeAdaptiveEnsemble()
        self.diversity = DiversityWeightedEnsemble()
        self.dynamic_optimizer = DynamicWeightOptimizer()

        # Performance tracking
        self.ensemble_history: List[EnsemblePrediction] = []

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Set weights for weighted average ensemble."""
        self.weighted_avg.weights = weights

    def fit_stacking(
        self,
        predictions: Dict[str, np.ndarray],
        targets: np.ndarray,
    ) -> None:
        """Fit stacking meta-learner."""
        self.stacking.fit(predictions, targets)

    def update(
        self,
        predictions: Dict[str, float],
        actual: float,
        regime: str = None,
    ) -> None:
        """Update all ensemble methods with new observation."""
        self.bayesian.update(predictions, actual)
        self.dynamic_optimizer.update(predictions, actual)
        self.diversity.update(predictions)

        if regime:
            for model_id, pred in predictions.items():
                # Simplified return calculation
                ret = pred * actual  # Positive if same direction
                self.regime_adaptive.record_performance(regime, model_id, ret)

    def combine(
        self,
        predictions: Dict[str, ModelPrediction],
        method: EnsembleMethod = None,
        regime: str = None,
    ) -> EnsemblePrediction:
        """
        Combine predictions using specified method.
        """
        method = method or self.default_method

        if method == EnsembleMethod.SIMPLE_AVERAGE:
            return self._simple_average(predictions)

        elif method == EnsembleMethod.WEIGHTED_AVERAGE:
            return self.weighted_avg.combine(predictions)

        elif method == EnsembleMethod.STACKING:
            return self.stacking.combine(predictions)

        elif method == EnsembleMethod.BAYESIAN:
            return self.bayesian.combine(predictions)

        elif method == EnsembleMethod.REGIME_ADAPTIVE:
            return self.regime_adaptive.combine(predictions, regime)

        elif method == EnsembleMethod.DYNAMIC:
            # Use dynamically optimized weights
            weights = self.dynamic_optimizer.get_weights()
            if weights:
                self.weighted_avg.weights = weights
            return self.weighted_avg.combine(predictions)

        else:
            return self.weighted_avg.combine(predictions)

    def _simple_average(
        self,
        predictions: Dict[str, ModelPrediction],
    ) -> EnsemblePrediction:
        """Simple equal-weight average."""
        if not predictions:
            return EnsemblePrediction(
                prediction=0.0,
                confidence=0.0,
                timestamp=datetime.now(timezone.utc),
                method=EnsembleMethod.SIMPLE_AVERAGE,
                model_weights={},
                model_predictions={},
            )

        preds = [p.prediction for p in predictions.values()]
        confs = [p.confidence for p in predictions.values()]

        return EnsemblePrediction(
            prediction=np.mean(preds),
            confidence=np.mean(confs),
            timestamp=datetime.now(timezone.utc),
            method=EnsembleMethod.SIMPLE_AVERAGE,
            model_weights={m: 1.0 / len(predictions) for m in predictions},
            model_predictions=predictions,
        )

    def get_model_rankings(self) -> Dict[str, float]:
        """Get current model rankings based on all methods."""
        rankings = defaultdict(float)

        # From Bayesian posteriors
        for model_id, weight in self.bayesian.posterior_weights.items():
            rankings[model_id] += weight

        # From dynamic optimizer
        for model_id, weight in self.dynamic_optimizer.optimal_weights.items():
            rankings[model_id] += weight

        # From diversity
        diversity_weights = self.diversity.get_diversity_weights()
        for model_id, weight in diversity_weights.items():
            rankings[model_id] += weight

        # Normalize
        total = sum(rankings.values())
        if total > 0:
            rankings = {m: r / total for m, r in rankings.items()}

        return dict(rankings)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'EnsembleMethod',
    'ModelPrediction',
    'EnsemblePrediction',
    'ModelPerformance',
    'WeightedAverageEnsemble',
    'StackingEnsemble',
    'BayesianModelAveraging',
    'DynamicWeightOptimizer',
    'RegimeAdaptiveEnsemble',
    'DiversityWeightedEnsemble',
    'EnsembleCombiner',
]
