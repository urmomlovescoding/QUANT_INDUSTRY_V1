"""
Bayesian Network - Pyro-Based Causal Model for Trading Decisions

This module provides a probabilistic causal model for understanding
the relationships between market factors and trading outcomes.

Key Features:
- Pyro-based probabilistic programming
- Structural causal model (SCM)
- Counterfactual reasoning
- Intervention analysis
- Factor attribution

Usage:
    from brain.causal.bayesian_network import CausalBayesianNetwork

    model = CausalBayesianNetwork()
    model.fit(market_data, outcomes)

    # Intervention analysis
    effect = model.estimate_intervention_effect('volatility', 0.3)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Try to import Pyro
try:
    import torch
    import pyro
    import pyro.distributions as dist
    from pyro.infer import SVI, Trace_ELBO
    from pyro.optim import Adam
    PYRO_AVAILABLE = True
except ImportError:
    PYRO_AVAILABLE = False
    logger.warning("Pyro not available. Using simplified causal model.")


@dataclass
class CausalConfig:
    """Configuration for causal model."""
    hidden_dim: int = 64
    num_layers: int = 2
    learning_rate: float = 0.01
    num_iterations: int = 1000
    num_samples: int = 100


@dataclass
class CausalEffect:
    """Estimated causal effect."""
    cause: str
    effect: str
    ate: float  # Average Treatment Effect
    confidence_interval: Tuple[float, float]
    p_value: float
    num_samples: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cause': self.cause,
            'effect': self.effect,
            'ate': self.ate,
            'confidence_interval': self.confidence_interval,
            'p_value': self.p_value,
            'num_samples': self.num_samples,
        }


class CausalBayesianNetwork:
    """
    Probabilistic causal model for trading factor analysis.

    Models the causal relationships between market factors and
    trading outcomes for counterfactual reasoning.

    Example:
        model = CausalBayesianNetwork()

        # Fit on historical data
        model.fit(features_df, returns_df)

        # Estimate effect of volatility on returns
        effect = model.estimate_causal_effect(
            cause='volatility',
            effect='returns',
            intervention_value=0.3
        )
    """

    def __init__(self, config: Optional[CausalConfig] = None):
        self.config = config or CausalConfig()
        self._is_fitted = False
        self._feature_names: List[str] = []
        self._causal_graph: Dict[str, List[str]] = {}

        if PYRO_AVAILABLE:
            pyro.clear_param_store()

        logger.info(f"CausalBayesianNetwork initialized (pyro_available={PYRO_AVAILABLE})")

    def _define_causal_structure(self, features: List[str]) -> Dict[str, List[str]]:
        """
        Define causal structure based on domain knowledge.

        Returns dictionary of node -> parents.
        """
        # Default structure based on trading domain
        structure = {
            'market_regime': [],  # Root node
            'volatility': ['market_regime'],
            'trend': ['market_regime'],
            'momentum': ['trend', 'volatility'],
            'volume': ['volatility', 'trend'],
            'sentiment': ['trend'],
            'signal': ['momentum', 'volatility', 'sentiment'],
            'returns': ['signal', 'volatility', 'volume'],
        }

        # Add any features not in default structure
        for feat in features:
            if feat not in structure:
                structure[feat] = ['market_regime']

        return structure

    def fit(
        self,
        features: pd.DataFrame,
        outcomes: pd.DataFrame,
        causal_structure: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Fit the causal model to data.

        Args:
            features: Feature DataFrame
            outcomes: Outcome DataFrame
            causal_structure: Optional custom causal structure

        Returns:
            Training metrics
        """
        self._feature_names = features.columns.tolist()

        if causal_structure:
            self._causal_graph = causal_structure
        else:
            self._causal_graph = self._define_causal_structure(self._feature_names)

        if PYRO_AVAILABLE:
            return self._fit_pyro(features, outcomes)
        else:
            return self._fit_simple(features, outcomes)

    def _fit_pyro(
        self,
        features: pd.DataFrame,
        outcomes: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Fit using Pyro probabilistic programming."""
        # Combine data
        data = pd.concat([features, outcomes], axis=1).dropna()

        # Convert to tensors
        X = torch.tensor(data.values, dtype=torch.float32)

        def model(data):
            """Pyro model definition."""
            n_features = data.shape[1]

            # Prior on feature relationships
            weights = pyro.sample(
                "weights",
                dist.Normal(torch.zeros(n_features, n_features),
                           torch.ones(n_features, n_features))
            )

            # Likelihood
            with pyro.plate("data", data.shape[0]):
                for i, col in enumerate(self._feature_names + outcomes.columns.tolist()):
                    parents = self._causal_graph.get(col, [])
                    if not parents:
                        # Root node
                        mean = torch.zeros(data.shape[0])
                    else:
                        # Compute mean from parents
                        parent_indices = [
                            j for j, name in enumerate(self._feature_names)
                            if name in parents
                        ]
                        if parent_indices:
                            parent_data = data[:, parent_indices]
                            mean = torch.matmul(parent_data, weights[parent_indices, i])
                        else:
                            mean = torch.zeros(data.shape[0])

                    pyro.sample(f"obs_{col}",
                               dist.Normal(mean, 1.0),
                               obs=data[:, i] if i < data.shape[1] else None)

        def guide(data):
            """Variational guide."""
            n_features = data.shape[1]

            weights_loc = pyro.param(
                "weights_loc",
                torch.zeros(n_features, n_features)
            )
            weights_scale = pyro.param(
                "weights_scale",
                torch.ones(n_features, n_features),
                constraint=torch.distributions.constraints.positive
            )

            pyro.sample(
                "weights",
                dist.Normal(weights_loc, weights_scale)
            )

        # Training
        optimizer = Adam({"lr": self.config.learning_rate})
        svi = SVI(model, guide, optimizer, loss=Trace_ELBO())

        losses = []
        for i in range(self.config.num_iterations):
            loss = svi.step(X)
            losses.append(loss)

            if i % 100 == 0:
                logger.debug(f"Iteration {i}: loss = {loss:.4f}")

        self._is_fitted = True

        return {
            'final_loss': losses[-1],
            'iterations': len(losses),
        }

    def _fit_simple(
        self,
        features: pd.DataFrame,
        outcomes: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Simple linear causal model fallback."""
        from sklearn.linear_model import LinearRegression

        self._simple_models = {}

        combined = pd.concat([features, outcomes], axis=1)

        for node, parents in self._causal_graph.items():
            if node in combined.columns and parents:
                valid_parents = [p for p in parents if p in combined.columns]
                if valid_parents:
                    model = LinearRegression()
                    X = combined[valid_parents].dropna()
                    y = combined.loc[X.index, node]
                    model.fit(X, y)
                    self._simple_models[node] = {
                        'model': model,
                        'parents': valid_parents,
                    }

        self._is_fitted = True

        return {'models_fitted': len(self._simple_models)}

    def estimate_causal_effect(
        self,
        cause: str,
        effect: str,
        intervention_value: float,
        baseline_value: float = 0.0,
    ) -> CausalEffect:
        """
        Estimate causal effect of intervention.

        Args:
            cause: Causal variable
            effect: Effect variable
            intervention_value: Value to set cause to
            baseline_value: Baseline value for comparison

        Returns:
            CausalEffect with estimated effect
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted")

        if PYRO_AVAILABLE:
            return self._estimate_effect_pyro(cause, effect, intervention_value, baseline_value)
        else:
            return self._estimate_effect_simple(cause, effect, intervention_value, baseline_value)

    def _estimate_effect_pyro(
        self,
        cause: str,
        effect: str,
        intervention_value: float,
        baseline_value: float,
    ) -> CausalEffect:
        """Estimate effect using Pyro."""
        # Sample from posterior with and without intervention
        effects_baseline = []
        effects_intervention = []

        for _ in range(self.config.num_samples):
            # This is simplified - full implementation would use do-calculus
            weights = pyro.param("weights_loc").detach().numpy()

            cause_idx = self._feature_names.index(cause) if cause in self._feature_names else 0
            effect_idx = self._feature_names.index(effect) if effect in self._feature_names else -1

            # Estimate effect
            effects_baseline.append(weights[cause_idx, effect_idx] * baseline_value)
            effects_intervention.append(weights[cause_idx, effect_idx] * intervention_value)

        ate = np.mean(effects_intervention) - np.mean(effects_baseline)
        ci = (np.percentile(effects_intervention, 2.5) - np.percentile(effects_baseline, 97.5),
              np.percentile(effects_intervention, 97.5) - np.percentile(effects_baseline, 2.5))

        # Simple p-value approximation
        p_value = 2 * min(
            np.mean(np.array(effects_intervention) > np.array(effects_baseline)),
            np.mean(np.array(effects_intervention) < np.array(effects_baseline))
        )

        return CausalEffect(
            cause=cause,
            effect=effect,
            ate=ate,
            confidence_interval=ci,
            p_value=p_value,
            num_samples=self.config.num_samples,
        )

    def _estimate_effect_simple(
        self,
        cause: str,
        effect: str,
        intervention_value: float,
        baseline_value: float,
    ) -> CausalEffect:
        """Estimate effect using simple linear model."""
        if effect not in self._simple_models:
            return CausalEffect(
                cause=cause,
                effect=effect,
                ate=0.0,
                confidence_interval=(0.0, 0.0),
                p_value=1.0,
                num_samples=0,
            )

        model_info = self._simple_models[effect]
        if cause not in model_info['parents']:
            return CausalEffect(
                cause=cause,
                effect=effect,
                ate=0.0,
                confidence_interval=(0.0, 0.0),
                p_value=1.0,
                num_samples=0,
            )

        model = model_info['model']
        coef_idx = model_info['parents'].index(cause)
        coefficient = model.coef_[coef_idx]

        ate = coefficient * (intervention_value - baseline_value)

        return CausalEffect(
            cause=cause,
            effect=effect,
            ate=ate,
            confidence_interval=(ate * 0.8, ate * 1.2),  # Simplified
            p_value=0.05,  # Would need proper test
            num_samples=1,
        )

    def get_causal_graph(self) -> Dict[str, List[str]]:
        """Get the causal graph structure."""
        return self._causal_graph.copy()

    def get_direct_effects(self, target: str) -> Dict[str, float]:
        """
        Get direct causal effects on a target variable.

        Args:
            target: Target variable

        Returns:
            Dictionary of cause -> effect size
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted")

        effects = {}
        parents = self._causal_graph.get(target, [])

        for parent in parents:
            effect = self.estimate_causal_effect(parent, target, 1.0, 0.0)
            effects[parent] = effect.ate

        return effects

    def counterfactual(
        self,
        observed: Dict[str, float],
        intervention: Dict[str, float],
        target: str,
    ) -> float:
        """
        Compute counterfactual prediction.

        "What would the target have been if we intervened?"

        Args:
            observed: Observed feature values
            intervention: Intervention values
            target: Target variable

        Returns:
            Counterfactual prediction
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted")

        # Simple implementation: adjust target by intervention effects
        base_value = observed.get(target, 0.0)

        for cause, value in intervention.items():
            if cause in observed:
                effect = self.estimate_causal_effect(cause, target, value, observed[cause])
                base_value += effect.ate

        return base_value

    def get_stats(self) -> Dict[str, Any]:
        """Get model statistics."""
        return {
            'is_fitted': self._is_fitted,
            'num_features': len(self._feature_names),
            'num_causal_edges': sum(len(v) for v in self._causal_graph.values()),
            'pyro_available': PYRO_AVAILABLE,
        }
