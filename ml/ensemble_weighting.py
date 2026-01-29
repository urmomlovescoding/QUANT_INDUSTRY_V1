"""
Ensemble Model Weighting - RL-based Dynamic Weight Optimization
QUANT_INDUSTRY_V1

Implements:
- Reinforcement Learning-based dynamic weight adjustment
- Multi-armed bandit approach for model selection
- Thompson Sampling for exploration/exploitation
- Online learning for real-time weight updates
- Performance-based weight decay

Rollback Plan: Delete this file, revert to static weights
Tests Required: Weight convergence, regret bounds, portfolio metrics
Failure Modes: Fall back to equal weights, alert operators
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timezone
from enum import Enum
import json

logger = logging.getLogger(__name__)


class WeightingStrategy(Enum):
    """Weighting strategy types."""
    EQUAL = "equal"
    PERFORMANCE = "performance"
    THOMPSON_SAMPLING = "thompson_sampling"
    UCB = "ucb"
    EXP3 = "exp3"
    SOFTMAX = "softmax"


@dataclass
class ModelPerformance:
    """Track individual model performance."""
    model_id: str
    total_predictions: int = 0
    correct_predictions: int = 0
    total_pnl: float = 0.0
    total_sharpe: float = 0.0
    recent_returns: deque = field(default_factory=lambda: deque(maxlen=100))
    alpha: float = 1.0  # Beta distribution parameter
    beta: float = 1.0   # Beta distribution parameter
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def accuracy(self) -> float:
        if self.total_predictions == 0:
            return 0.5
        return self.correct_predictions / self.total_predictions
    
    @property
    def avg_return(self) -> float:
        if not self.recent_returns:
            return 0.0
        return np.mean(self.recent_returns)
    
    @property
    def return_std(self) -> float:
        if len(self.recent_returns) < 2:
            return 1.0
        return max(np.std(self.recent_returns), 1e-6)


@dataclass
class EnsembleState:
    """State of the ensemble weighting system."""
    weights: Dict[str, float]
    strategy: WeightingStrategy
    total_rounds: int
    cumulative_reward: float
    exploration_rate: float
    timestamp: datetime


class ThompsonSamplingWeighter:
    """
    Thompson Sampling for model selection.
    
    Uses Beta distribution to model uncertainty about model quality.
    Balances exploration and exploitation naturally.
    """
    
    def __init__(self, model_ids: List[str], prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.model_ids = model_ids
        self.performances = {
            mid: ModelPerformance(model_id=mid, alpha=prior_alpha, beta=prior_beta)
            for mid in model_ids
        }
        
    def sample_weights(self) -> Dict[str, float]:
        """Sample weights from posterior distributions."""
        samples = {}
        for mid, perf in self.performances.items():
            # Sample from Beta distribution
            sample = np.random.beta(perf.alpha, perf.beta)
            samples[mid] = sample
            
        # Normalize to weights
        total = sum(samples.values())
        if total == 0:
            return {mid: 1.0 / len(self.model_ids) for mid in self.model_ids}
        return {mid: s / total for mid, s in samples.items()}
    
    def update(self, model_id: str, reward: float):
        """
        Update posterior based on observed reward.
        
        Args:
            model_id: Model that made prediction
            reward: Reward signal (0-1 for binary, can be normalized)
        """
        if model_id not in self.performances:
            logger.warning(f"Unknown model_id: {model_id}")
            return
            
        perf = self.performances[model_id]
        
        # Bernoulli reward interpretation
        if reward > 0.5:
            perf.alpha += 1
        else:
            perf.beta += 1
            
        perf.total_predictions += 1
        perf.last_updated = datetime.now(timezone.utc)


class UCBWeighter:
    """
    Upper Confidence Bound (UCB1) algorithm for model weighting.
    
    Provides optimistic estimates with exploration bonus.
    """
    
    def __init__(self, model_ids: List[str], c: float = 2.0):
        self.model_ids = model_ids
        self.c = c  # Exploration parameter
        self.performances = {mid: ModelPerformance(model_id=mid) for mid in model_ids}
        self.total_rounds = 0
        
    def get_weights(self) -> Dict[str, float]:
        """Calculate UCB-based weights."""
        ucb_values = {}
        
        for mid, perf in self.performances.items():
            if perf.total_predictions == 0:
                # Unseen model gets high UCB
                ucb_values[mid] = float('inf')
            else:
                # UCB = empirical mean + exploration bonus
                mean = perf.avg_return
                exploration = self.c * np.sqrt(
                    np.log(self.total_rounds + 1) / perf.total_predictions
                )
                ucb_values[mid] = mean + exploration
                
        # Handle infinite values
        if any(v == float('inf') for v in ucb_values.values()):
            inf_models = [m for m, v in ucb_values.items() if v == float('inf')]
            return {mid: 1.0 / len(inf_models) if mid in inf_models else 0.0 
                    for mid in self.model_ids}
        
        # Softmax over UCB values
        max_ucb = max(ucb_values.values())
        exp_values = {mid: np.exp(v - max_ucb) for mid, v in ucb_values.items()}
        total = sum(exp_values.values())
        
        return {mid: v / total for mid, v in exp_values.items()}
    
    def update(self, model_id: str, reward: float):
        """Update model statistics."""
        if model_id not in self.performances:
            return
            
        perf = self.performances[model_id]
        perf.recent_returns.append(reward)
        perf.total_predictions += 1
        perf.total_pnl += reward
        perf.last_updated = datetime.now(timezone.utc)
        
        self.total_rounds += 1


class EXP3Weighter:
    """
    EXP3 (Exponential-weight algorithm for Exploration and Exploitation).
    
    Adversarial bandit algorithm suitable for non-stationary environments.
    """
    
    def __init__(self, model_ids: List[str], gamma: float = 0.1, eta: float = 0.1):
        self.model_ids = model_ids
        self.gamma = gamma  # Exploration rate
        self.eta = eta      # Learning rate
        self.n_models = len(model_ids)
        
        # Exponential weights
        self.log_weights = {mid: 0.0 for mid in model_ids}
        self.total_rounds = 0
        
    def get_weights(self) -> Dict[str, float]:
        """Get probability distribution over models."""
        # Softmax with exploration
        max_w = max(self.log_weights.values())
        exp_weights = {mid: np.exp(w - max_w) for mid, w in self.log_weights.items()}
        total = sum(exp_weights.values())
        
        # Mix with uniform for exploration
        probs = {}
        for mid in self.model_ids:
            p = (1 - self.gamma) * (exp_weights[mid] / total) + self.gamma / self.n_models
            probs[mid] = p
            
        return probs
    
    def update(self, model_id: str, reward: float, selected_weight: float):
        """
        Update weights with importance-weighted reward.
        
        Args:
            model_id: Selected model
            reward: Observed reward
            selected_weight: Probability with which model was selected
        """
        if model_id not in self.log_weights:
            return
            
        # Importance-weighted estimator
        estimated_reward = reward / max(selected_weight, 1e-6)
        
        # Clip for stability
        estimated_reward = np.clip(estimated_reward, -10, 10)
        
        # Update log weight
        self.log_weights[model_id] += self.eta * estimated_reward
        
        self.total_rounds += 1


class DynamicEnsembleWeighter:
    """
    Main class for RL-based dynamic ensemble weighting.
    
    Combines multiple weighting strategies with meta-learning.
    
    Example:
        weighter = DynamicEnsembleWeighter(
            model_ids=['momentum', 'mean_reversion', 'ml_predictor'],
            strategy=WeightingStrategy.THOMPSON_SAMPLING
        )
        
        # Get weights for current round
        weights = weighter.get_weights()
        
        # Make ensemble prediction
        predictions = {mid: models[mid].predict(X) for mid in model_ids}
        ensemble_pred = sum(weights[mid] * predictions[mid] for mid in model_ids)
        
        # Update based on reward
        actual_return = calculate_return(ensemble_pred, actual)
        weighter.update_all(predictions, actual, actual_return)
    """
    
    def __init__(
        self,
        model_ids: List[str],
        strategy: WeightingStrategy = WeightingStrategy.THOMPSON_SAMPLING,
        learning_rate: float = 0.1,
        decay_rate: float = 0.99,
        min_weight: float = 0.05,
        lookback_window: int = 100
    ):
        self.model_ids = model_ids
        self.strategy = strategy
        self.learning_rate = learning_rate
        self.decay_rate = decay_rate
        self.min_weight = min_weight
        self.lookback_window = lookback_window
        
        # Initialize strategy-specific weighters
        self._init_weighters()
        
        # Track history
        self.weight_history: List[Dict[str, float]] = []
        self.reward_history: List[float] = []
        self.total_rounds = 0
        
    def _init_weighters(self):
        """Initialize weighting algorithms."""
        self.thompson = ThompsonSamplingWeighter(self.model_ids)
        self.ucb = UCBWeighter(self.model_ids)
        self.exp3 = EXP3Weighter(self.model_ids)
        
        # Performance-based weights
        self.perf_weights = {mid: 1.0 / len(self.model_ids) for mid in self.model_ids}
        
    def get_weights(self) -> Dict[str, float]:
        """Get current ensemble weights based on strategy."""
        if self.strategy == WeightingStrategy.EQUAL:
            weights = {mid: 1.0 / len(self.model_ids) for mid in self.model_ids}
            
        elif self.strategy == WeightingStrategy.THOMPSON_SAMPLING:
            weights = self.thompson.sample_weights()
            
        elif self.strategy == WeightingStrategy.UCB:
            weights = self.ucb.get_weights()
            
        elif self.strategy == WeightingStrategy.EXP3:
            weights = self.exp3.get_weights()
            
        elif self.strategy == WeightingStrategy.PERFORMANCE:
            weights = self._get_performance_weights()
            
        elif self.strategy == WeightingStrategy.SOFTMAX:
            weights = self._get_softmax_weights()
            
        else:
            weights = {mid: 1.0 / len(self.model_ids) for mid in self.model_ids}
            
        # Apply minimum weight constraint
        weights = self._apply_min_weight(weights)
        
        # Record
        self.weight_history.append(weights.copy())
        
        return weights
    
    def _get_performance_weights(self) -> Dict[str, float]:
        """Calculate performance-based weights."""
        performances = {}
        for mid in self.model_ids:
            perf = self.thompson.performances[mid]
            # Combine accuracy and returns
            score = 0.5 * perf.accuracy + 0.5 * (perf.avg_return + 1) / 2
            performances[mid] = max(score, 0.01)
            
        total = sum(performances.values())
        return {mid: p / total for mid, p in performances.items()}
    
    def _get_softmax_weights(self, temperature: float = 1.0) -> Dict[str, float]:
        """Softmax weights based on recent performance."""
        scores = {}
        for mid in self.model_ids:
            perf = self.thompson.performances[mid]
            scores[mid] = perf.avg_return / temperature
            
        max_score = max(scores.values()) if scores else 0
        exp_scores = {mid: np.exp(s - max_score) for mid, s in scores.items()}
        total = sum(exp_scores.values())
        
        if total == 0:
            return {mid: 1.0 / len(self.model_ids) for mid in self.model_ids}
        return {mid: s / total for mid, s in exp_scores.items()}
    
    def _apply_min_weight(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Ensure minimum weight constraint."""
        n = len(weights)
        total_min = self.min_weight * n
        
        if total_min >= 1.0:
            return {mid: 1.0 / n for mid in weights}
            
        # Redistribute weight above minimum
        adjusted = {}
        excess = 0.0
        
        for mid, w in weights.items():
            if w < self.min_weight:
                adjusted[mid] = self.min_weight
                excess += self.min_weight - w
            else:
                adjusted[mid] = w
                
        # Redistribute excess proportionally
        if excess > 0:
            above_min = {mid: w for mid, w in adjusted.items() if w > self.min_weight}
            total_above = sum(above_min.values())
            
            if total_above > 0:
                for mid in above_min:
                    adjusted[mid] -= excess * (adjusted[mid] / total_above)
                    
        # Normalize
        total = sum(adjusted.values())
        return {mid: w / total for mid, w in adjusted.items()}
    
    def update(
        self,
        model_id: str,
        prediction: float,
        actual: float,
        reward: Optional[float] = None
    ):
        """
        Update weights based on single model's performance.
        
        Args:
            model_id: Model that made prediction
            prediction: Model's prediction
            actual: Actual outcome
            reward: Optional explicit reward (computed if not provided)
        """
        if reward is None:
            # Compute reward as prediction accuracy
            error = abs(prediction - actual)
            reward = np.exp(-error)  # Exponential reward
            
        # Update all weighters
        self.thompson.update(model_id, reward)
        self.ucb.update(model_id, reward)
        
        # For EXP3, need the weight used for selection
        if self.weight_history:
            selected_weight = self.weight_history[-1].get(model_id, 0.1)
            self.exp3.update(model_id, reward, selected_weight)
            
        # Update performance weights
        self._update_perf_weights(model_id, reward)
        
    def update_all(
        self,
        predictions: Dict[str, float],
        actual: float,
        ensemble_reward: float
    ):
        """
        Update all models based on their predictions.
        
        Args:
            predictions: Dict of model_id -> prediction
            actual: Actual outcome
            ensemble_reward: Reward for ensemble prediction
        """
        for model_id, pred in predictions.items():
            # Individual model reward
            error = abs(pred - actual)
            model_reward = np.exp(-error)
            self.update(model_id, pred, actual, model_reward)
            
        self.reward_history.append(ensemble_reward)
        self.total_rounds += 1
        
        # Apply weight decay
        self._apply_decay()
    
    def _update_perf_weights(self, model_id: str, reward: float):
        """Update performance-based weights."""
        # Exponential moving average
        old_weight = self.perf_weights[model_id]
        new_weight = old_weight + self.learning_rate * (reward - old_weight)
        self.perf_weights[model_id] = new_weight
        
    def _apply_decay(self):
        """Apply time decay to reduce weight of old observations."""
        for mid in self.model_ids:
            perf = self.thompson.performances[mid]
            # Soft reset towards prior
            perf.alpha = 1 + self.decay_rate * (perf.alpha - 1)
            perf.beta = 1 + self.decay_rate * (perf.beta - 1)
            
    def get_state(self) -> EnsembleState:
        """Get current state of the weighting system."""
        return EnsembleState(
            weights=self.get_weights() if not self.weight_history else self.weight_history[-1],
            strategy=self.strategy,
            total_rounds=self.total_rounds,
            cumulative_reward=sum(self.reward_history),
            exploration_rate=self._get_exploration_rate(),
            timestamp=datetime.now(timezone.utc)
        )
    
    def _get_exploration_rate(self) -> float:
        """Estimate current exploration rate."""
        if not self.weight_history or len(self.weight_history) < 2:
            return 1.0
            
        # Measure weight volatility as proxy for exploration
        recent_weights = self.weight_history[-min(10, len(self.weight_history)):]
        volatility = []
        
        for mid in self.model_ids:
            weights = [w[mid] for w in recent_weights]
            volatility.append(np.std(weights))
            
        return np.mean(volatility) * len(self.model_ids)
    
    def get_model_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for each model."""
        stats = {}
        for mid in self.model_ids:
            perf = self.thompson.performances[mid]
            stats[mid] = {
                'accuracy': perf.accuracy,
                'avg_return': perf.avg_return,
                'total_predictions': perf.total_predictions,
                'alpha': perf.alpha,
                'beta': perf.beta,
                'current_weight': self.weight_history[-1][mid] if self.weight_history else 1.0/len(self.model_ids)
            }
        return stats
    
    def save_state(self, path: str):
        """Save weighter state to file."""
        state = {
            'model_ids': self.model_ids,
            'strategy': self.strategy.value,
            'total_rounds': self.total_rounds,
            'perf_weights': self.perf_weights,
            'thompson_params': {
                mid: {'alpha': p.alpha, 'beta': p.beta, 'predictions': p.total_predictions}
                for mid, p in self.thompson.performances.items()
            },
            'reward_history': list(self.reward_history[-1000:]),  # Last 1000
        }
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"Saved ensemble weighter state to {path}")
        
    def load_state(self, path: str):
        """Load weighter state from file."""
        with open(path, 'r') as f:
            state = json.load(f)
            
        self.total_rounds = state['total_rounds']
        self.perf_weights = state['perf_weights']
        self.reward_history = deque(state['reward_history'], maxlen=1000)
        
        for mid, params in state['thompson_params'].items():
            if mid in self.thompson.performances:
                perf = self.thompson.performances[mid]
                perf.alpha = params['alpha']
                perf.beta = params['beta']
                perf.total_predictions = params['predictions']
                
        logger.info(f"Loaded ensemble weighter state from {path}")


class AdaptiveStrategySelector:
    """
    Meta-learner that selects the best weighting strategy.
    
    Runs multiple strategies in parallel and selects based on performance.
    """
    
    def __init__(self, model_ids: List[str], evaluation_window: int = 50):
        self.model_ids = model_ids
        self.evaluation_window = evaluation_window
        
        # Create weighters for each strategy
        self.weighters = {
            strategy: DynamicEnsembleWeighter(model_ids, strategy=strategy)
            for strategy in [
                WeightingStrategy.THOMPSON_SAMPLING,
                WeightingStrategy.UCB,
                WeightingStrategy.EXP3,
                WeightingStrategy.PERFORMANCE
            ]
        }
        
        # Track strategy performance
        self.strategy_rewards: Dict[WeightingStrategy, deque] = {
            s: deque(maxlen=evaluation_window) for s in self.weighters
        }
        
        self.current_strategy = WeightingStrategy.THOMPSON_SAMPLING
        self.selection_count = 0
        
    def get_weights(self) -> Tuple[Dict[str, float], WeightingStrategy]:
        """Get weights from best strategy."""
        # Periodically re-evaluate best strategy
        if self.selection_count % self.evaluation_window == 0:
            self._select_best_strategy()
            
        self.selection_count += 1
        weights = self.weighters[self.current_strategy].get_weights()
        
        return weights, self.current_strategy
    
    def update(
        self,
        predictions: Dict[str, float],
        actual: float,
        returns: Dict[WeightingStrategy, float]
    ):
        """
        Update all strategies.
        
        Args:
            predictions: Model predictions
            actual: Actual outcome
            returns: Dict of strategy -> realized return
        """
        for strategy, weighter in self.weighters.items():
            reward = returns.get(strategy, 0.0)
            weighter.update_all(predictions, actual, reward)
            self.strategy_rewards[strategy].append(reward)
            
    def _select_best_strategy(self):
        """Select best performing strategy."""
        avg_rewards = {}
        
        for strategy, rewards in self.strategy_rewards.items():
            if len(rewards) >= 10:
                avg_rewards[strategy] = np.mean(rewards)
            else:
                avg_rewards[strategy] = 0.0
                
        if avg_rewards:
            self.current_strategy = max(avg_rewards, key=avg_rewards.get)
            logger.info(f"Selected strategy: {self.current_strategy.value} "
                       f"(avg reward: {avg_rewards[self.current_strategy]:.4f})")
