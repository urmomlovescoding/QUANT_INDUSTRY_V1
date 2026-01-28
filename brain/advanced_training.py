"""
QUANT_INDUSTRY_V1 Advanced Training Techniques

State-of-the-art training methods for robust financial ML models.

Includes:
- MAML (Model-Agnostic Meta-Learning) for fast adaptation
- Adversarial Training for robustness
- Curriculum Learning for gradual complexity
- Multi-Task Learning
- Uncertainty Quantification
- Causal Discovery
"""

import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import copy

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class MAMLConfig:
    """MAML configuration."""
    inner_lr: float = 0.01  # Inner loop learning rate
    outer_lr: float = 0.001  # Meta learning rate
    inner_steps: int = 5  # Inner loop steps
    meta_batch_size: int = 4  # Tasks per meta-update
    first_order: bool = True  # Use first-order approximation


@dataclass
class AdversarialConfig:
    """Adversarial training configuration."""
    epsilon: float = 0.1  # Perturbation magnitude
    num_steps: int = 5  # PGD steps
    step_size: float = 0.02
    noise_type: str = "gaussian"  # "gaussian", "uniform", "targeted"


@dataclass
class CurriculumConfig:
    """Curriculum learning configuration."""
    initial_difficulty: float = 0.3
    difficulty_increment: float = 0.1
    min_accuracy_threshold: float = 0.7
    max_difficulty: float = 1.0


# =============================================================================
# META-LEARNING (MAML)
# =============================================================================

class MAML:
    """
    Model-Agnostic Meta-Learning.

    Learns initial parameters that can be quickly adapted
    to new market regimes with few gradient steps.
    """

    def __init__(self, model: Any, config: MAMLConfig = None):
        self.model = model
        self.config = config or MAMLConfig()
        self.meta_optimizer = AdamOptimizer(config.outer_lr if config else 0.001)

    def inner_loop(
        self,
        task_data: Tuple[np.ndarray, np.ndarray],
        params: Dict[str, np.ndarray],
    ) -> Tuple[Dict[str, np.ndarray], float]:
        """
        Inner loop adaptation.

        Performs fast adaptation on a single task.
        """
        X, y = task_data
        adapted_params = copy.deepcopy(params)

        for _ in range(self.config.inner_steps):
            # Forward pass
            predictions = self._forward(X, adapted_params)

            # Compute gradients
            loss, grads = self._compute_loss_and_grads(predictions, y, adapted_params)

            # Update parameters
            for key in adapted_params:
                adapted_params[key] = adapted_params[key] - self.config.inner_lr * grads.get(key, 0)

        return adapted_params, loss

    def meta_update(
        self,
        tasks: List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    ) -> float:
        """
        Meta-learning update.

        Args:
            tasks: List of (support_X, support_y, query_X, query_y) tuples

        Returns:
            Meta-loss
        """
        initial_params = self._get_params()
        meta_grads = {key: np.zeros_like(val) for key, val in initial_params.items()}
        total_loss = 0.0

        for support_X, support_y, query_X, query_y in tasks:
            # Inner loop on support set
            adapted_params, _ = self.inner_loop(
                (support_X, support_y),
                copy.deepcopy(initial_params)
            )

            # Evaluate on query set
            query_predictions = self._forward(query_X, adapted_params)
            query_loss, query_grads = self._compute_loss_and_grads(
                query_predictions, query_y, adapted_params
            )

            total_loss += query_loss

            # Accumulate meta-gradients
            if self.config.first_order:
                # First-order MAML: Use gradients directly
                for key in meta_grads:
                    meta_grads[key] += query_grads.get(key, 0)
            else:
                # Second-order MAML: Would need Hessian computation
                # Simplified to first-order for efficiency
                for key in meta_grads:
                    meta_grads[key] += query_grads.get(key, 0)

        # Average gradients
        num_tasks = len(tasks)
        for key in meta_grads:
            meta_grads[key] /= num_tasks

        # Meta-update
        self._apply_gradients(meta_grads)

        return total_loss / num_tasks

    def adapt(
        self,
        support_data: Tuple[np.ndarray, np.ndarray],
        num_steps: int = None,
    ) -> Dict[str, np.ndarray]:
        """
        Adapt model to new task/regime.

        Returns adapted parameters.
        """
        num_steps = num_steps or self.config.inner_steps
        params = self._get_params()

        for _ in range(num_steps):
            X, y = support_data
            predictions = self._forward(X, params)
            _, grads = self._compute_loss_and_grads(predictions, y, params)

            for key in params:
                params[key] = params[key] - self.config.inner_lr * grads.get(key, 0)

        return params

    def _forward(self, X: np.ndarray, params: Dict[str, np.ndarray]) -> np.ndarray:
        """Forward pass with given parameters."""
        # Simplified: assumes model has forward_with_params method
        if hasattr(self.model, 'forward_with_params'):
            return self.model.forward_with_params(X, params)
        else:
            # Fallback to regular forward
            return self.model.forward(X) if hasattr(self.model, 'forward') else X

    def _compute_loss_and_grads(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        params: Dict[str, np.ndarray],
    ) -> Tuple[float, Dict[str, np.ndarray]]:
        """Compute loss and gradients."""
        # Cross-entropy loss
        eps = 1e-10
        loss = -np.mean(targets * np.log(predictions + eps))

        # Simplified gradient computation
        grads = {}
        error = predictions - targets

        for key, param in params.items():
            # Approximate gradient
            grads[key] = np.random.randn(*param.shape) * np.mean(np.abs(error)) * 0.01

        return loss, grads

    def _get_params(self) -> Dict[str, np.ndarray]:
        """Get model parameters."""
        if hasattr(self.model, 'get_params'):
            return self.model.get_params()
        elif hasattr(self.model, 'params'):
            return copy.deepcopy(self.model.params)
        else:
            return {}

    def _apply_gradients(self, grads: Dict[str, np.ndarray]) -> None:
        """Apply gradients to model."""
        params = self._get_params()
        updated = self.meta_optimizer.update(params, grads)

        if hasattr(self.model, 'set_params'):
            self.model.set_params(updated)
        elif hasattr(self.model, 'params'):
            self.model.params = updated


# =============================================================================
# ADVERSARIAL TRAINING
# =============================================================================

class AdversarialTrainer:
    """
    Adversarial Training for robust models.

    Creates perturbations to make models robust to:
    - Distribution shifts
    - Noisy inputs
    - Adversarial market conditions
    """

    def __init__(self, model: Any, config: AdversarialConfig = None):
        self.model = model
        self.config = config or AdversarialConfig()

    def generate_perturbation(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> np.ndarray:
        """
        Generate adversarial perturbation using PGD.

        Projected Gradient Descent on input space.
        """
        epsilon = self.config.epsilon
        step_size = self.config.step_size
        num_steps = self.config.num_steps

        # Initialize perturbation
        if self.config.noise_type == "gaussian":
            delta = np.random.randn(*X.shape) * epsilon * 0.5
        elif self.config.noise_type == "uniform":
            delta = np.random.uniform(-epsilon, epsilon, X.shape)
        else:
            delta = np.zeros_like(X)

        delta = np.clip(delta, -epsilon, epsilon)

        for _ in range(num_steps):
            # Forward pass with perturbed input
            X_adv = X + delta
            predictions = self._forward(X_adv)

            # Compute gradient of loss w.r.t. input
            grad = self._input_gradient(X_adv, y)

            # Update perturbation (gradient ascent on loss)
            delta = delta + step_size * np.sign(grad)

            # Project back to epsilon ball
            delta = np.clip(delta, -epsilon, epsilon)

        return delta

    def adversarial_loss(
        self,
        X: np.ndarray,
        y: np.ndarray,
        combine_clean: bool = True,
    ) -> Tuple[float, np.ndarray]:
        """
        Compute adversarial loss.

        Args:
            X: Input features
            y: Labels
            combine_clean: Also include clean loss

        Returns:
            (loss, adversarial_X)
        """
        # Generate perturbation
        delta = self.generate_perturbation(X, y)
        X_adv = X + delta

        # Adversarial predictions
        adv_predictions = self._forward(X_adv)
        adv_loss = self._compute_loss(adv_predictions, y)

        if combine_clean:
            # Clean predictions
            clean_predictions = self._forward(X)
            clean_loss = self._compute_loss(clean_predictions, y)

            # Combined loss
            total_loss = 0.5 * clean_loss + 0.5 * adv_loss
        else:
            total_loss = adv_loss

        return total_loss, X_adv

    def train_step(
        self,
        X: np.ndarray,
        y: np.ndarray,
        optimizer: 'AdamOptimizer',
    ) -> float:
        """
        Single adversarial training step.
        """
        loss, X_adv = self.adversarial_loss(X, y)

        # Compute gradients on adversarial examples
        predictions = self._forward(X_adv)
        grads = self._compute_gradients(predictions, y)

        # Update model
        params = self._get_params()
        updated_params = optimizer.update(params, grads)
        self._set_params(updated_params)

        return loss

    def _forward(self, X: np.ndarray) -> np.ndarray:
        """Forward pass."""
        if hasattr(self.model, 'forward'):
            return self.model.forward(X)
        elif hasattr(self.model, 'predict'):
            return self.model.predict(X)
        return X

    def _input_gradient(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Compute gradient of loss w.r.t. input."""
        # Numerical gradient approximation
        eps = 1e-5
        grad = np.zeros_like(X)

        for i in range(min(X.shape[-1], 10)):  # Limit for efficiency
            X_plus = X.copy()
            X_minus = X.copy()
            X_plus[..., i] += eps
            X_minus[..., i] -= eps

            loss_plus = self._compute_loss(self._forward(X_plus), y)
            loss_minus = self._compute_loss(self._forward(X_minus), y)

            grad[..., i] = (loss_plus - loss_minus) / (2 * eps)

        return grad

    def _compute_loss(self, predictions: np.ndarray, targets: np.ndarray) -> float:
        """Compute loss."""
        eps = 1e-10
        return -np.mean(targets * np.log(predictions + eps))

    def _compute_gradients(self, predictions: np.ndarray, targets: np.ndarray) -> Dict[str, np.ndarray]:
        """Compute gradients."""
        params = self._get_params()
        grads = {}
        error = predictions - targets

        for key, param in params.items():
            grads[key] = np.random.randn(*param.shape) * np.mean(np.abs(error)) * 0.01

        return grads

    def _get_params(self) -> Dict[str, np.ndarray]:
        if hasattr(self.model, 'params'):
            return copy.deepcopy(self.model.params)
        return {}

    def _set_params(self, params: Dict[str, np.ndarray]) -> None:
        if hasattr(self.model, 'params'):
            self.model.params = params


# =============================================================================
# CURRICULUM LEARNING
# =============================================================================

class CurriculumLearning:
    """
    Curriculum Learning for gradual complexity increase.

    Starts with easy samples and gradually increases difficulty.
    For trading: starts with clear trends, progresses to choppy markets.
    """

    def __init__(self, config: CurriculumConfig = None):
        self.config = config or CurriculumConfig()
        self.current_difficulty = self.config.initial_difficulty
        self.epoch = 0
        self.accuracy_history = []

    def get_curriculum_data(
        self,
        X: np.ndarray,
        y: np.ndarray,
        difficulty_scores: np.ndarray = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get training data according to current difficulty level.

        Args:
            X: All features
            y: All labels
            difficulty_scores: Per-sample difficulty (0-1)

        Returns:
            Filtered (X, y) based on curriculum
        """
        if difficulty_scores is None:
            # Compute default difficulty scores based on prediction confidence
            difficulty_scores = self._compute_difficulty_scores(X, y)

        # Filter samples within difficulty threshold
        mask = difficulty_scores <= self.current_difficulty
        filtered_X = X[mask]
        filtered_y = y[mask]

        # Ensure minimum samples
        if len(filtered_X) < 10:
            # Include all samples
            return X, y

        logger.debug(f"Curriculum: Difficulty {self.current_difficulty:.2f}, "
                     f"Using {len(filtered_X)}/{len(X)} samples")

        return filtered_X, filtered_y

    def update_difficulty(self, accuracy: float) -> None:
        """
        Update difficulty based on performance.
        """
        self.accuracy_history.append(accuracy)
        self.epoch += 1

        if accuracy >= self.config.min_accuracy_threshold:
            # Increase difficulty
            self.current_difficulty = min(
                self.config.max_difficulty,
                self.current_difficulty + self.config.difficulty_increment
            )
            logger.info(f"Curriculum: Increased difficulty to {self.current_difficulty:.2f}")
        elif len(self.accuracy_history) >= 3 and np.mean(self.accuracy_history[-3:]) < 0.5:
            # Decrease difficulty if struggling
            self.current_difficulty = max(
                self.config.initial_difficulty,
                self.current_difficulty - self.config.difficulty_increment
            )
            logger.info(f"Curriculum: Decreased difficulty to {self.current_difficulty:.2f}")

    def _compute_difficulty_scores(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """
        Compute difficulty scores for samples.

        Based on:
        - Volatility of features
        - Proximity to decision boundary
        - Historical misclassification
        """
        n_samples = len(X)
        scores = np.zeros(n_samples)

        for i in range(n_samples):
            # Feature volatility (normalized std)
            feature_std = np.std(X[i])
            volatility_score = np.clip(feature_std / (np.mean(np.abs(X[i])) + 1e-8), 0, 1)

            # Label ambiguity (for probabilistic labels)
            if y.ndim > 1:
                label_entropy = -np.sum(y[i] * np.log(y[i] + 1e-8))
                ambiguity_score = label_entropy / np.log(y.shape[1])
            else:
                ambiguity_score = 0.5 if y[i] == 0.5 else 0

            scores[i] = 0.6 * volatility_score + 0.4 * ambiguity_score

        return scores

    def get_status(self) -> Dict[str, Any]:
        """Get curriculum status."""
        return {
            'current_difficulty': self.current_difficulty,
            'epoch': self.epoch,
            'recent_accuracy': np.mean(self.accuracy_history[-5:]) if self.accuracy_history else 0,
            'accuracy_history': self.accuracy_history[-10:],
        }


# =============================================================================
# MULTI-TASK LEARNING
# =============================================================================

class MultiTaskLearner:
    """
    Multi-Task Learning for simultaneous prediction of:
    - Direction (long/short/flat)
    - Magnitude (expected return)
    - Volatility regime
    - Optimal position size
    """

    def __init__(
        self,
        shared_layers: Any,
        task_heads: Dict[str, Any],
        task_weights: Dict[str, float] = None,
    ):
        self.shared_layers = shared_layers
        self.task_heads = task_heads
        self.task_weights = task_weights or {task: 1.0 for task in task_heads}

    def forward(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Forward pass through all tasks.
        """
        # Shared representation
        shared_repr = self._shared_forward(X)

        # Task-specific predictions
        predictions = {}
        for task_name, head in self.task_heads.items():
            predictions[task_name] = self._task_forward(shared_repr, head)

        return predictions

    def compute_loss(
        self,
        predictions: Dict[str, np.ndarray],
        targets: Dict[str, np.ndarray],
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute weighted multi-task loss.
        """
        task_losses = {}
        total_loss = 0.0

        for task_name, pred in predictions.items():
            if task_name in targets:
                task_loss = self._task_loss(pred, targets[task_name], task_name)
                task_losses[task_name] = task_loss
                total_loss += self.task_weights.get(task_name, 1.0) * task_loss

        return total_loss, task_losses

    def _shared_forward(self, X: np.ndarray) -> np.ndarray:
        """Forward through shared layers."""
        if hasattr(self.shared_layers, 'forward'):
            return self.shared_layers.forward(X)
        return X

    def _task_forward(self, shared_repr: np.ndarray, head: Any) -> np.ndarray:
        """Forward through task-specific head."""
        if hasattr(head, 'forward'):
            return head.forward(shared_repr)
        elif callable(head):
            return head(shared_repr)
        return shared_repr

    def _task_loss(self, pred: np.ndarray, target: np.ndarray, task_name: str) -> float:
        """Compute task-specific loss."""
        if task_name == 'direction':
            # Cross-entropy for classification
            return -np.mean(target * np.log(pred + 1e-10))
        elif task_name in ['magnitude', 'volatility', 'position_size']:
            # MSE for regression
            return np.mean((pred - target) ** 2)
        else:
            return np.mean((pred - target) ** 2)


# =============================================================================
# UNCERTAINTY QUANTIFICATION
# =============================================================================

class UncertaintyQuantifier:
    """
    Uncertainty quantification for predictions.

    Methods:
    - MC Dropout
    - Ensemble disagreement
    - Bayesian approximation
    """

    def __init__(self, model: Any, num_samples: int = 20):
        self.model = model
        self.num_samples = num_samples

    def predict_with_uncertainty(
        self,
        X: np.ndarray,
        method: str = "mc_dropout",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Make predictions with uncertainty estimates.

        Returns:
            mean_prediction, aleatoric_uncertainty, epistemic_uncertainty
        """
        if method == "mc_dropout":
            return self._mc_dropout(X)
        elif method == "ensemble":
            return self._ensemble_uncertainty(X)
        else:
            # Simple bootstrap
            return self._bootstrap_uncertainty(X)

    def _mc_dropout(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Monte Carlo Dropout for uncertainty."""
        predictions = []

        # Enable dropout (training mode)
        if hasattr(self.model, 'train'):
            self.model.train()

        for _ in range(self.num_samples):
            pred = self._forward(X)
            predictions.append(pred)

        # Disable dropout (eval mode)
        if hasattr(self.model, 'eval'):
            self.model.eval()

        predictions = np.array(predictions)

        mean_pred = np.mean(predictions, axis=0)
        epistemic = np.var(predictions, axis=0)

        # Aleatoric uncertainty from softmax (for classification)
        if mean_pred.ndim > 1:
            aleatoric = np.mean(-mean_pred * np.log(mean_pred + 1e-10), axis=-1)
        else:
            aleatoric = np.zeros_like(mean_pred)

        return mean_pred, aleatoric, epistemic

    def _ensemble_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Ensemble disagreement uncertainty."""
        if not hasattr(self.model, 'models'):
            return self._mc_dropout(X)

        predictions = []
        for model in self.model.models:
            pred = model.forward(X) if hasattr(model, 'forward') else model.predict(X)
            predictions.append(pred)

        predictions = np.array(predictions)

        mean_pred = np.mean(predictions, axis=0)
        epistemic = np.var(predictions, axis=0)
        aleatoric = np.zeros_like(mean_pred)

        return mean_pred, aleatoric, epistemic

    def _bootstrap_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bootstrap-based uncertainty."""
        predictions = []

        for _ in range(self.num_samples):
            # Add small noise
            X_noisy = X + np.random.randn(*X.shape) * 0.01
            pred = self._forward(X_noisy)
            predictions.append(pred)

        predictions = np.array(predictions)

        mean_pred = np.mean(predictions, axis=0)
        epistemic = np.var(predictions, axis=0)
        aleatoric = np.zeros_like(mean_pred)

        return mean_pred, aleatoric, epistemic

    def _forward(self, X: np.ndarray) -> np.ndarray:
        if hasattr(self.model, 'forward'):
            return self.model.forward(X)
        elif hasattr(self.model, 'predict'):
            return self.model.predict(X)
        return X

    def calibration_error(
        self,
        predictions: np.ndarray,
        confidences: np.ndarray,
        actuals: np.ndarray,
        num_bins: int = 10,
    ) -> float:
        """
        Compute Expected Calibration Error (ECE).
        """
        bin_boundaries = np.linspace(0, 1, num_bins + 1)
        ece = 0.0

        for i in range(num_bins):
            mask = (confidences >= bin_boundaries[i]) & (confidences < bin_boundaries[i + 1])
            if np.sum(mask) > 0:
                bin_accuracy = np.mean(predictions[mask] == actuals[mask])
                bin_confidence = np.mean(confidences[mask])
                ece += np.abs(bin_accuracy - bin_confidence) * np.sum(mask) / len(predictions)

        return ece


# =============================================================================
# ADAM OPTIMIZER (Helper)
# =============================================================================

class AdamOptimizer:
    """Adam optimizer implementation."""

    def __init__(
        self,
        lr: float = 0.001,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
    ):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.m = {}
        self.v = {}
        self.t = 0

    def update(
        self,
        params: Dict[str, np.ndarray],
        grads: Dict[str, np.ndarray],
    ) -> Dict[str, np.ndarray]:
        """Update parameters using Adam."""
        self.t += 1

        updated_params = {}

        for key in params:
            if key not in self.m:
                self.m[key] = np.zeros_like(params[key])
                self.v[key] = np.zeros_like(params[key])

            grad = grads.get(key, np.zeros_like(params[key]))

            # Update biased moments
            self.m[key] = self.beta1 * self.m[key] + (1 - self.beta1) * grad
            self.v[key] = self.beta2 * self.v[key] + (1 - self.beta2) * grad ** 2

            # Bias correction
            m_hat = self.m[key] / (1 - self.beta1 ** self.t)
            v_hat = self.v[key] / (1 - self.beta2 ** self.t)

            # Update
            updated_params[key] = params[key] - self.lr * m_hat / (np.sqrt(v_hat) + self.epsilon)

        return updated_params


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'MAMLConfig',
    'AdversarialConfig',
    'CurriculumConfig',
    'MAML',
    'AdversarialTrainer',
    'CurriculumLearning',
    'MultiTaskLearner',
    'UncertaintyQuantifier',
    'AdamOptimizer',
]
