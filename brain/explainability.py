"""
QUANT_INDUSTRY_V1 Model Explainability

Explainable AI for trading models:
- Feature importance analysis
- SHAP-like value decomposition
- Decision path explanation
- Counterfactual analysis
- Natural language explanations

Rollback Plan: Delete this file
Tests Required: Explanation consistency, attribution accuracy
Failure Modes: Generic explanations as fallback
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# EXPLANATION TYPES
# =============================================================================

@dataclass
class FeatureContribution:
    """Contribution of a feature to prediction."""
    feature_name: str
    feature_value: float
    contribution: float  # Impact on prediction
    direction: str  # 'bullish', 'bearish', 'neutral'
    importance_rank: int = 0


@dataclass
class PredictionExplanation:
    """Complete explanation of a prediction."""
    prediction: float
    prediction_label: str
    confidence: float
    base_value: float  # Expected value without features
    contributions: List[FeatureContribution]
    top_bullish_factors: List[str]
    top_bearish_factors: List[str]
    summary: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'prediction': self.prediction,
            'prediction_label': self.prediction_label,
            'confidence': self.confidence,
            'base_value': self.base_value,
            'contributions': [
                {
                    'feature': c.feature_name,
                    'value': c.feature_value,
                    'contribution': c.contribution,
                    'direction': c.direction,
                    'rank': c.importance_rank,
                }
                for c in self.contributions
            ],
            'top_bullish_factors': self.top_bullish_factors,
            'top_bearish_factors': self.top_bearish_factors,
            'summary': self.summary,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class CounterfactualExplanation:
    """What-if analysis for predictions."""
    original_prediction: float
    target_prediction: float
    required_changes: Dict[str, Tuple[float, float]]  # feature -> (original, new)
    feasibility_score: float
    explanation: str


# =============================================================================
# FEATURE IMPORTANCE ANALYZER
# =============================================================================

class FeatureImportanceAnalyzer:
    """
    Analyze feature importance using various methods.
    """

    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        self.n_features = len(feature_names)

    def permutation_importance(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        n_repeats: int = 10,
        metric: Callable = None
    ) -> Dict[str, float]:
        """
        Calculate permutation importance.

        Measures decrease in performance when feature is shuffled.
        """
        if metric is None:
            metric = lambda y_true, y_pred: np.mean(y_true == y_pred)

        # Baseline score
        y_pred = model.predict(X)
        baseline_score = metric(y, y_pred)

        importance = {}

        for i, feature in enumerate(self.feature_names):
            scores = []

            for _ in range(n_repeats):
                X_permuted = X.copy()
                np.random.shuffle(X_permuted[:, i])

                y_pred_permuted = model.predict(X_permuted)
                score = metric(y, y_pred_permuted)
                scores.append(baseline_score - score)

            importance[feature] = float(np.mean(scores))

        # Normalize
        total = sum(abs(v) for v in importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}

        return importance

    def drop_column_importance(
        self,
        model_factory: Callable,
        X: np.ndarray,
        y: np.ndarray,
        metric: Callable = None
    ) -> Dict[str, float]:
        """
        Calculate importance by retraining without each feature.

        More accurate but computationally expensive.
        """
        if metric is None:
            metric = lambda y_true, y_pred: np.mean(y_true == y_pred)

        # Baseline with all features
        model_full = model_factory()
        model_full.train(X, y)
        baseline_score = metric(y, model_full.predict(X))

        importance = {}

        for i, feature in enumerate(self.feature_names):
            # Remove feature
            X_reduced = np.delete(X, i, axis=1)

            # Retrain
            model_reduced = model_factory()
            model_reduced.train(X_reduced, y)

            score = metric(y, model_reduced.predict(X_reduced))
            importance[feature] = float(baseline_score - score)

        return importance

    def correlation_importance(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> Dict[str, float]:
        """
        Simple correlation-based importance.

        Fast but only captures linear relationships.
        """
        importance = {}

        for i, feature in enumerate(self.feature_names):
            corr = np.corrcoef(X[:, i], y)[0, 1]
            importance[feature] = float(abs(corr)) if not np.isnan(corr) else 0.0

        return importance


# =============================================================================
# SHAP-LIKE EXPLAINER
# =============================================================================

class SHAPExplainer:
    """
    Simplified SHAP (SHapley Additive exPlanations) implementation.

    Computes feature contributions based on marginal contributions.
    """

    def __init__(
        self,
        model: Any,
        background_data: np.ndarray,
        feature_names: List[str] = None,
        n_samples: int = 100
    ):
        self.model = model
        self.background = background_data
        self.feature_names = feature_names or [f"feature_{i}" for i in range(background_data.shape[1])]
        self.n_samples = n_samples
        self.n_features = background_data.shape[1]

        # Compute base value (expected prediction)
        predictions = model.predict(background_data)
        if hasattr(predictions, 'mean'):
            self.base_value = float(predictions.mean())
        else:
            self.base_value = float(np.mean(predictions))

    def explain(self, x: np.ndarray) -> PredictionExplanation:
        """
        Explain a single prediction.

        Args:
            x: Feature vector (1D)

        Returns:
            PredictionExplanation with feature contributions
        """
        if x.ndim == 1:
            x = x.reshape(1, -1)

        # Get prediction
        prediction = self.model.predict(x)
        if hasattr(prediction, '__len__'):
            prediction = prediction[0]

        # Get probability if available
        confidence = 0.5
        if hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(x)
            if hasattr(proba, '__len__') and len(proba) > 0:
                confidence = float(np.max(proba[0])) if hasattr(proba[0], '__len__') else float(proba[0])

        # Compute SHAP values using sampling
        shap_values = self._compute_shap_values(x[0])

        # Create contributions
        contributions = []
        for i, (name, shap_val) in enumerate(zip(self.feature_names, shap_values)):
            direction = 'bullish' if shap_val > 0 else 'bearish' if shap_val < 0 else 'neutral'
            contributions.append(FeatureContribution(
                feature_name=name,
                feature_value=float(x[0, i]),
                contribution=float(shap_val),
                direction=direction,
            ))

        # Sort by absolute contribution
        contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
        for i, c in enumerate(contributions):
            c.importance_rank = i + 1

        # Get top factors
        top_bullish = [c.feature_name for c in contributions if c.contribution > 0][:3]
        top_bearish = [c.feature_name for c in contributions if c.contribution < 0][:3]

        # Generate summary
        prediction_label = self._prediction_to_label(prediction)
        summary = self._generate_summary(prediction_label, contributions, confidence)

        return PredictionExplanation(
            prediction=float(prediction),
            prediction_label=prediction_label,
            confidence=confidence,
            base_value=self.base_value,
            contributions=contributions,
            top_bullish_factors=top_bullish,
            top_bearish_factors=top_bearish,
            summary=summary,
        )

    def _compute_shap_values(self, x: np.ndarray) -> np.ndarray:
        """Compute SHAP values using kernel approximation."""
        shap_values = np.zeros(self.n_features)

        for _ in range(self.n_samples):
            # Random coalition (subset of features)
            coalition = np.random.random(self.n_features) > 0.5

            # Create two samples: one with feature i, one without
            for i in range(self.n_features):
                if np.random.random() > 0.5:
                    # Sample with feature i included
                    coalition_with = coalition.copy()
                    coalition_with[i] = True

                    # Sample without feature i
                    coalition_without = coalition.copy()
                    coalition_without[i] = False

                    # Create input samples
                    x_with = self._create_masked_sample(x, coalition_with)
                    x_without = self._create_masked_sample(x, coalition_without)

                    # Marginal contribution
                    pred_with = self._predict_single(x_with)
                    pred_without = self._predict_single(x_without)

                    shap_values[i] += (pred_with - pred_without)

        # Average
        shap_values /= self.n_samples

        return shap_values

    def _create_masked_sample(self, x: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Create sample with some features from x, others from background."""
        bg_idx = np.random.randint(len(self.background))
        sample = self.background[bg_idx].copy()
        sample[mask] = x[mask]
        return sample

    def _predict_single(self, x: np.ndarray) -> float:
        """Get prediction for single sample."""
        pred = self.model.predict(x.reshape(1, -1))
        return float(pred[0]) if hasattr(pred, '__len__') else float(pred)

    def _prediction_to_label(self, prediction: float) -> str:
        """Convert prediction to human-readable label."""
        if prediction > 0.5:
            return "BULLISH"
        elif prediction < -0.5:
            return "BEARISH"
        elif prediction > 0:
            return "SLIGHTLY BULLISH"
        elif prediction < 0:
            return "SLIGHTLY BEARISH"
        else:
            return "NEUTRAL"

    def _generate_summary(
        self,
        label: str,
        contributions: List[FeatureContribution],
        confidence: float
    ) -> str:
        """Generate natural language summary."""
        conf_level = "high" if confidence > 0.7 else "moderate" if confidence > 0.5 else "low"

        if not contributions:
            return f"Prediction: {label} with {conf_level} confidence."

        top_positive = [c for c in contributions[:3] if c.contribution > 0]
        top_negative = [c for c in contributions[:3] if c.contribution < 0]

        parts = [f"Prediction: {label} with {conf_level} confidence ({confidence:.0%})."]

        if top_positive:
            factors = ", ".join(c.feature_name for c in top_positive)
            parts.append(f"Bullish factors: {factors}.")

        if top_negative:
            factors = ", ".join(c.feature_name for c in top_negative)
            parts.append(f"Bearish factors: {factors}.")

        return " ".join(parts)


# =============================================================================
# DECISION PATH EXPLAINER
# =============================================================================

class DecisionPathExplainer:
    """
    Explain decision paths for tree-based models.
    """

    def __init__(self, model: Any, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names

    def explain_path(self, x: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extract decision path for a prediction.

        Note: Works best with tree-based models that expose tree structure.
        For black-box models, uses approximation.
        """
        if hasattr(self.model, 'model') and hasattr(self.model.model, 'get_booster'):
            # XGBoost
            return self._explain_xgboost_path(x)
        elif hasattr(self.model, 'model') and hasattr(self.model.model, 'trees_to_dataframe'):
            # LightGBM
            return self._explain_lightgbm_path(x)
        else:
            # Generic approximation
            return self._explain_generic_path(x)

    def _explain_generic_path(self, x: np.ndarray) -> List[Dict[str, Any]]:
        """Generic path explanation using feature contributions."""
        if x.ndim == 1:
            x = x.reshape(1, -1)

        path = []

        # Sort features by absolute value (proxy for importance)
        sorted_indices = np.argsort(np.abs(x[0]))[::-1]

        for i, idx in enumerate(sorted_indices[:5]):  # Top 5 features
            feature_name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
            value = x[0, idx]

            # Determine threshold direction
            if value > 0:
                condition = f"{feature_name} > 0"
                direction = "positive"
            else:
                condition = f"{feature_name} <= 0"
                direction = "negative"

            path.append({
                'step': i + 1,
                'feature': feature_name,
                'value': float(value),
                'condition': condition,
                'direction': direction,
            })

        return path

    def _explain_xgboost_path(self, x: np.ndarray) -> List[Dict[str, Any]]:
        """XGBoost-specific path explanation."""
        # Would need access to booster internals
        # For now, use generic approach
        return self._explain_generic_path(x)

    def _explain_lightgbm_path(self, x: np.ndarray) -> List[Dict[str, Any]]:
        """LightGBM-specific path explanation."""
        return self._explain_generic_path(x)


# =============================================================================
# COUNTERFACTUAL EXPLAINER
# =============================================================================

class CounterfactualExplainer:
    """
    Generate counterfactual explanations.

    "What minimal changes would flip the prediction?"
    """

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        feature_ranges: Dict[str, Tuple[float, float]] = None
    ):
        self.model = model
        self.feature_names = feature_names
        self.n_features = len(feature_names)
        self.feature_ranges = feature_ranges or {}

    def find_counterfactual(
        self,
        x: np.ndarray,
        target_class: int = None,
        max_changes: int = 3,
        n_iterations: int = 100
    ) -> CounterfactualExplanation:
        """
        Find counterfactual explanation.

        Args:
            x: Original feature vector
            target_class: Desired prediction class
            max_changes: Maximum features to change
            n_iterations: Search iterations

        Returns:
            CounterfactualExplanation
        """
        if x.ndim == 1:
            x = x.reshape(1, -1)

        original_pred = self._get_prediction(x)

        if target_class is None:
            # Flip to opposite class
            target_class = 1 - int(original_pred > 0)

        best_cf = None
        best_distance = float('inf')

        for _ in range(n_iterations):
            # Random perturbation
            cf = x.copy()
            n_changes = np.random.randint(1, max_changes + 1)
            change_indices = np.random.choice(self.n_features, n_changes, replace=False)

            for idx in change_indices:
                feature = self.feature_names[idx]

                if feature in self.feature_ranges:
                    low, high = self.feature_ranges[feature]
                else:
                    low = x[0, idx] - 2 * abs(x[0, idx] + 0.1)
                    high = x[0, idx] + 2 * abs(x[0, idx] + 0.1)

                cf[0, idx] = np.random.uniform(low, high)

            # Check if prediction changed
            cf_pred = self._get_prediction(cf)

            if self._prediction_matches_target(cf_pred, target_class):
                distance = np.sum((cf - x) ** 2)

                if distance < best_distance:
                    best_distance = distance
                    best_cf = cf.copy()

        if best_cf is None:
            return CounterfactualExplanation(
                original_prediction=float(original_pred),
                target_prediction=float(target_class),
                required_changes={},
                feasibility_score=0.0,
                explanation="No counterfactual found within constraints.",
            )

        # Identify changes
        required_changes = {}
        for i in range(self.n_features):
            if abs(best_cf[0, i] - x[0, i]) > 1e-6:
                required_changes[self.feature_names[i]] = (
                    float(x[0, i]),
                    float(best_cf[0, i])
                )

        # Feasibility score (inverse of distance)
        feasibility = 1.0 / (1.0 + best_distance)

        # Generate explanation
        cf_pred = self._get_prediction(best_cf)
        explanation = self._generate_cf_explanation(required_changes, original_pred, cf_pred)

        return CounterfactualExplanation(
            original_prediction=float(original_pred),
            target_prediction=float(cf_pred),
            required_changes=required_changes,
            feasibility_score=float(feasibility),
            explanation=explanation,
        )

    def _get_prediction(self, x: np.ndarray) -> float:
        """Get model prediction."""
        pred = self.model.predict(x)
        return float(pred[0]) if hasattr(pred, '__len__') else float(pred)

    def _prediction_matches_target(self, pred: float, target: int) -> bool:
        """Check if prediction matches target."""
        if target == 1:
            return pred > 0
        else:
            return pred <= 0

    def _generate_cf_explanation(
        self,
        changes: Dict[str, Tuple[float, float]],
        original_pred: float,
        cf_pred: float
    ) -> str:
        """Generate natural language explanation."""
        if not changes:
            return "No changes required."

        parts = ["To change the prediction:"]

        for feature, (old_val, new_val) in changes.items():
            direction = "increase" if new_val > old_val else "decrease"
            parts.append(f"- {direction} {feature} from {old_val:.2f} to {new_val:.2f}")

        original_label = "BULLISH" if original_pred > 0 else "BEARISH"
        cf_label = "BULLISH" if cf_pred > 0 else "BEARISH"

        parts.append(f"This would change prediction from {original_label} to {cf_label}.")

        return "\n".join(parts)


# =============================================================================
# EXPLANATION GENERATOR
# =============================================================================

class ExplanationGenerator:
    """
    High-level explanation generator combining multiple methods.
    """

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        background_data: np.ndarray = None
    ):
        self.model = model
        self.feature_names = feature_names

        # Initialize explainers
        self.importance_analyzer = FeatureImportanceAnalyzer(feature_names)

        if background_data is not None:
            self.shap_explainer = SHAPExplainer(model, background_data, feature_names)
        else:
            self.shap_explainer = None

        self.path_explainer = DecisionPathExplainer(model, feature_names)
        self.cf_explainer = CounterfactualExplainer(model, feature_names)

    def explain(
        self,
        x: np.ndarray,
        include_counterfactual: bool = False
    ) -> Dict[str, Any]:
        """
        Generate comprehensive explanation.

        Args:
            x: Feature vector
            include_counterfactual: Whether to include counterfactual analysis

        Returns:
            Dictionary with all explanations
        """
        result = {}

        # SHAP explanation
        if self.shap_explainer is not None:
            result['prediction_explanation'] = self.shap_explainer.explain(x).to_dict()

        # Decision path
        result['decision_path'] = self.path_explainer.explain_path(x)

        # Counterfactual
        if include_counterfactual:
            cf = self.cf_explainer.find_counterfactual(x)
            result['counterfactual'] = {
                'original_prediction': cf.original_prediction,
                'target_prediction': cf.target_prediction,
                'required_changes': cf.required_changes,
                'feasibility_score': cf.feasibility_score,
                'explanation': cf.explanation,
            }

        return result

    def explain_batch(
        self,
        X: np.ndarray,
        top_n: int = 5
    ) -> Dict[str, Any]:
        """
        Explain batch of predictions with summary statistics.
        """
        if self.shap_explainer is None:
            return {'error': 'Background data required for batch explanation'}

        explanations = []
        for i in range(len(X)):
            exp = self.shap_explainer.explain(X[i])
            explanations.append(exp)

        # Aggregate feature importance
        feature_importance = {}
        for feature in self.feature_names:
            contribs = [
                c.contribution for exp in explanations
                for c in exp.contributions
                if c.feature_name == feature
            ]
            feature_importance[feature] = float(np.mean(np.abs(contribs))) if contribs else 0.0

        # Sort by importance
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return {
            'n_samples': len(X),
            'top_features': sorted_features[:top_n],
            'feature_importance': feature_importance,
            'prediction_distribution': {
                'bullish': sum(1 for e in explanations if e.prediction > 0),
                'bearish': sum(1 for e in explanations if e.prediction <= 0),
            },
        }
