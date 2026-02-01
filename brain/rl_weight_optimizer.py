"""
RL Weight Optimizer - PPO-Based Ensemble Weight Optimization

This module provides reinforcement learning based optimization of
ensemble model weights using Proximal Policy Optimization (PPO).

Key Features:
- PPO algorithm for stable policy updates
- Continuous action space for weight adjustments
- State: model performances + regime features
- Reward: risk-adjusted returns (Sharpe-like)
- Online learning with experience replay

Architecture:
    State (Model Performances + Regime)
        → Policy Network (Actor)
        → Value Network (Critic)
        → PPO Update
        → New Weights

Usage:
    from brain.rl_weight_optimizer import RLWeightOptimizer

    optimizer = RLWeightOptimizer(n_models=5)
    weights = optimizer.get_optimal_weights(state)
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import random

import numpy as np

logger = logging.getLogger(__name__)

# Try to import PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.distributions import Normal
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. RL weight optimizer limited.")


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class PPOConfig:
    """Configuration for PPO algorithm."""
    n_models: int = 5
    state_dim: int = 20  # Model performances + regime features
    hidden_dim: int = 128
    learning_rate: float = 3e-4
    gamma: float = 0.99  # Discount factor
    gae_lambda: float = 0.95  # GAE parameter
    clip_epsilon: float = 0.2  # PPO clip
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 0.5
    ppo_epochs: int = 10
    batch_size: int = 64
    buffer_size: int = 2048
    update_frequency: int = 256


# =============================================================================
# Neural Network Components
# =============================================================================

if TORCH_AVAILABLE:

    class ActorNetwork(nn.Module):
        """Policy network that outputs weight distributions."""

        def __init__(self, state_dim: int, n_models: int, hidden_dim: int):
            super().__init__()

            self.shared = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
            )

            # Mean and log_std for each weight
            self.mean_head = nn.Linear(hidden_dim, n_models)
            self.log_std = nn.Parameter(torch.zeros(n_models))

        def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """
            Args:
                state: (batch, state_dim)

            Returns:
                mean: (batch, n_models)
                std: (batch, n_models)
            """
            features = self.shared(state)
            mean = torch.tanh(self.mean_head(features))  # Bounded [-1, 1]
            std = torch.exp(self.log_std.clamp(-20, 2))
            return mean, std.expand_as(mean)

        def get_distribution(self, state: torch.Tensor) -> Normal:
            """Get action distribution."""
            mean, std = self.forward(state)
            return Normal(mean, std)

        def sample_action(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """Sample action and compute log probability."""
            dist = self.get_distribution(state)
            action = dist.rsample()  # Reparameterized sample
            log_prob = dist.log_prob(action).sum(-1)
            return action, log_prob


    class CriticNetwork(nn.Module):
        """Value network that estimates state value."""

        def __init__(self, state_dim: int, hidden_dim: int):
            super().__init__()

            self.network = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, 1),
            )

        def forward(self, state: torch.Tensor) -> torch.Tensor:
            return self.network(state).squeeze(-1)


# =============================================================================
# Experience Buffer
# =============================================================================

@dataclass
class Experience:
    """Single experience tuple."""
    state: np.ndarray
    action: np.ndarray
    reward: float
    next_state: np.ndarray
    done: bool
    log_prob: float
    value: float


class ExperienceBuffer:
    """Buffer for storing and sampling experiences."""

    def __init__(self, capacity: int = 2048):
        self.capacity = capacity
        self.buffer: List[Experience] = []
        self.position = 0

    def push(self, exp: Experience) -> None:
        """Add experience to buffer."""
        if len(self.buffer) < self.capacity:
            self.buffer.append(exp)
        else:
            self.buffer[self.position] = exp
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int) -> List[Experience]:
        """Sample random batch."""
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))

    def get_all(self) -> List[Experience]:
        """Get all experiences."""
        return self.buffer.copy()

    def clear(self) -> None:
        """Clear buffer."""
        self.buffer.clear()
        self.position = 0

    def __len__(self) -> int:
        return len(self.buffer)


# =============================================================================
# RL Weight Optimizer
# =============================================================================

class RLWeightOptimizer:
    """
    PPO-based optimizer for ensemble model weights.

    Uses reinforcement learning to dynamically adjust model weights
    based on recent performance and market regime.

    State Space:
    - Recent returns for each model
    - Recent Sharpe for each model
    - Correlation between models
    - Regime indicators (volatility, trend)

    Action Space:
    - Continuous weight adjustments for each model

    Reward:
    - Risk-adjusted portfolio return

    Example:
        optimizer = RLWeightOptimizer(n_models=5)

        # During trading
        state = optimizer.compute_state(model_returns, regime_features)
        weights = optimizer.get_optimal_weights(state)

        # After observing outcome
        reward = compute_sharpe(portfolio_return)
        optimizer.update(state, weights, reward, next_state)
    """

    def __init__(self, config: Optional[PPOConfig] = None):
        """
        Initialize the RL weight optimizer.

        Args:
            config: PPO configuration
        """
        self.config = config or PPOConfig()

        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available. Using fallback uniform weights.")
            self._fallback_mode = True
            return

        self._fallback_mode = False

        # Networks
        self.actor = ActorNetwork(
            state_dim=self.config.state_dim,
            n_models=self.config.n_models,
            hidden_dim=self.config.hidden_dim,
        )

        self.critic = CriticNetwork(
            state_dim=self.config.state_dim,
            hidden_dim=self.config.hidden_dim,
        )

        # Optimizers
        self.actor_optimizer = torch.optim.Adam(
            self.actor.parameters(),
            lr=self.config.learning_rate,
        )
        self.critic_optimizer = torch.optim.Adam(
            self.critic.parameters(),
            lr=self.config.learning_rate,
        )

        # Experience buffer
        self.buffer = ExperienceBuffer(capacity=self.config.buffer_size)

        # Statistics
        self._update_count = 0
        self._episode_rewards: List[float] = []
        self._training_history: List[Dict[str, float]] = []

        logger.info(f"RLWeightOptimizer initialized with {self.config.n_models} models")

    def compute_state(
        self,
        model_returns: np.ndarray,
        model_sharpes: np.ndarray,
        correlations: Optional[np.ndarray] = None,
        regime_features: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Compute state vector from model performances and regime.

        Args:
            model_returns: Recent returns for each model (n_models,)
            model_sharpes: Recent Sharpe ratios (n_models,)
            correlations: Correlation matrix (n_models, n_models)
            regime_features: Additional regime features

        Returns:
            State vector (state_dim,)
        """
        state_parts = [
            model_returns.flatten(),
            model_sharpes.flatten(),
        ]

        # Add correlation features (upper triangle)
        if correlations is not None:
            n = correlations.shape[0]
            corr_features = correlations[np.triu_indices(n, k=1)]
            state_parts.append(corr_features)

        # Add regime features
        if regime_features is not None:
            state_parts.append(regime_features.flatten())

        state = np.concatenate(state_parts)

        # Pad or truncate to state_dim
        if len(state) < self.config.state_dim:
            state = np.pad(state, (0, self.config.state_dim - len(state)))
        else:
            state = state[:self.config.state_dim]

        return state.astype(np.float32)

    def get_optimal_weights(
        self,
        state: np.ndarray,
        deterministic: bool = False,
    ) -> np.ndarray:
        """
        Get optimal model weights for given state.

        Args:
            state: Current state vector
            deterministic: If True, use mean action (no exploration)

        Returns:
            Weights for each model (n_models,), sums to 1
        """
        if self._fallback_mode:
            return np.ones(self.config.n_models) / self.config.n_models

        state_t = torch.FloatTensor(state).unsqueeze(0)

        self.actor.eval()
        with torch.no_grad():
            if deterministic:
                mean, _ = self.actor(state_t)
                action = mean
            else:
                action, _ = self.actor.sample_action(state_t)

        # Convert action to weights (softmax to ensure sum to 1, positive)
        action_np = action.squeeze().numpy()
        weights = self._action_to_weights(action_np)

        return weights

    def _action_to_weights(self, action: np.ndarray) -> np.ndarray:
        """Convert action to valid weights."""
        # Softmax to ensure positive and sum to 1
        exp_action = np.exp(action - np.max(action))
        weights = exp_action / exp_action.sum()

        # Clip minimum weight
        min_weight = 0.05
        weights = np.clip(weights, min_weight, 1.0)
        weights = weights / weights.sum()

        return weights

    def store_experience(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """
        Store experience for training.

        Args:
            state: State when action was taken
            action: Action taken (raw, before softmax)
            reward: Reward received
            next_state: Next state
            done: Whether episode ended
        """
        if self._fallback_mode:
            return

        state_t = torch.FloatTensor(state).unsqueeze(0)

        with torch.no_grad():
            dist = self.actor.get_distribution(state_t)
            action_t = torch.FloatTensor(action).unsqueeze(0)
            log_prob = dist.log_prob(action_t).sum(-1).item()
            value = self.critic(state_t).item()

        exp = Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
            log_prob=log_prob,
            value=value,
        )

        self.buffer.push(exp)

        # Update if buffer is full enough
        if len(self.buffer) >= self.config.update_frequency:
            self._update()

    def _update(self) -> None:
        """Perform PPO update."""
        if len(self.buffer) < self.config.batch_size:
            return

        experiences = self.buffer.get_all()

        # Prepare tensors
        states = torch.FloatTensor([e.state for e in experiences])
        actions = torch.FloatTensor([e.action for e in experiences])
        rewards = torch.FloatTensor([e.reward for e in experiences])
        next_states = torch.FloatTensor([e.next_state for e in experiences])
        dones = torch.FloatTensor([1.0 if e.done else 0.0 for e in experiences])
        old_log_probs = torch.FloatTensor([e.log_prob for e in experiences])
        old_values = torch.FloatTensor([e.value for e in experiences])

        # Compute advantages using GAE
        advantages, returns = self._compute_gae(
            rewards, old_values, dones, next_states
        )

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO epochs
        for _ in range(self.config.ppo_epochs):
            # Sample mini-batches
            indices = torch.randperm(len(experiences))

            for start in range(0, len(experiences), self.config.batch_size):
                end = start + self.config.batch_size
                batch_idx = indices[start:end]

                batch_states = states[batch_idx]
                batch_actions = actions[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]

                # Actor loss
                dist = self.actor.get_distribution(batch_states)
                new_log_probs = dist.log_prob(batch_actions).sum(-1)
                entropy = dist.entropy().sum(-1).mean()

                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                clipped_ratio = torch.clamp(
                    ratio,
                    1.0 - self.config.clip_epsilon,
                    1.0 + self.config.clip_epsilon,
                )

                actor_loss = -torch.min(
                    ratio * batch_advantages,
                    clipped_ratio * batch_advantages,
                ).mean()

                actor_loss = actor_loss - self.config.entropy_coef * entropy

                # Critic loss
                values = self.critic(batch_states)
                critic_loss = F.mse_loss(values, batch_returns)

                # Update actor
                self.actor_optimizer.zero_grad()
                actor_loss.backward()
                nn.utils.clip_grad_norm_(
                    self.actor.parameters(),
                    self.config.max_grad_norm,
                )
                self.actor_optimizer.step()

                # Update critic
                self.critic_optimizer.zero_grad()
                critic_loss.backward()
                nn.utils.clip_grad_norm_(
                    self.critic.parameters(),
                    self.config.max_grad_norm,
                )
                self.critic_optimizer.step()

        # Record metrics
        self._training_history.append({
            'update': self._update_count,
            'actor_loss': actor_loss.item(),
            'critic_loss': critic_loss.item(),
            'entropy': entropy.item(),
            'avg_reward': rewards.mean().item(),
        })

        self._update_count += 1

        # Clear buffer after update
        self.buffer.clear()

        logger.debug(f"PPO update {self._update_count}: actor_loss={actor_loss.item():.4f}")

    def _compute_gae(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        dones: torch.Tensor,
        next_states: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute Generalized Advantage Estimation."""
        with torch.no_grad():
            next_values = self.critic(next_states)

        advantages = torch.zeros_like(rewards)
        last_gae = 0

        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = next_values[t]
            else:
                next_value = values[t + 1]

            delta = rewards[t] + self.config.gamma * next_value * (1 - dones[t]) - values[t]
            last_gae = delta + self.config.gamma * self.config.gae_lambda * (1 - dones[t]) * last_gae
            advantages[t] = last_gae

        returns = advantages + values

        return advantages, returns

    def compute_reward(
        self,
        portfolio_return: float,
        portfolio_volatility: float,
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Compute reward from portfolio performance.

        Uses a Sharpe-like reward that encourages both returns and risk management.

        Args:
            portfolio_return: Period return
            portfolio_volatility: Period volatility
            risk_free_rate: Risk-free rate

        Returns:
            Reward value
        """
        if portfolio_volatility < 1e-6:
            return portfolio_return * 10  # Just use return if no volatility

        sharpe = (portfolio_return - risk_free_rate) / portfolio_volatility

        # Scale Sharpe for RL (typically want rewards in [-1, 1] range)
        reward = np.tanh(sharpe)

        return reward

    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        stats = {
            'update_count': self._update_count,
            'buffer_size': len(self.buffer),
            'fallback_mode': self._fallback_mode,
        }

        if self._training_history:
            recent = self._training_history[-100:]
            stats['recent_avg_actor_loss'] = np.mean([h['actor_loss'] for h in recent])
            stats['recent_avg_critic_loss'] = np.mean([h['critic_loss'] for h in recent])
            stats['recent_avg_reward'] = np.mean([h['avg_reward'] for h in recent])

        return stats

    def save(self, path: str) -> None:
        """Save optimizer state."""
        if self._fallback_mode:
            return

        torch.save({
            'actor_state_dict': self.actor.state_dict(),
            'critic_state_dict': self.critic.state_dict(),
            'actor_optimizer': self.actor_optimizer.state_dict(),
            'critic_optimizer': self.critic_optimizer.state_dict(),
            'update_count': self._update_count,
            'config': self.config,
        }, path)
        logger.info(f"Saved RL optimizer to {path}")

    def load(self, path: str) -> None:
        """Load optimizer state."""
        if self._fallback_mode:
            return

        checkpoint = torch.load(path)
        self.actor.load_state_dict(checkpoint['actor_state_dict'])
        self.critic.load_state_dict(checkpoint['critic_state_dict'])
        self.actor_optimizer.load_state_dict(checkpoint['actor_optimizer'])
        self.critic_optimizer.load_state_dict(checkpoint['critic_optimizer'])
        self._update_count = checkpoint['update_count']
        logger.info(f"Loaded RL optimizer from {path}")


# =============================================================================
# Integration with Existing Ensemble
# =============================================================================

class DynamicEnsembleWithRL:
    """
    Ensemble manager that uses RL for weight optimization.

    Wraps existing ensemble with RL-based weight adjustment.

    Example:
        ensemble = DynamicEnsembleWithRL(model_names=['xgb', 'lgbm', 'lstm'])

        # Get predictions with RL-optimized weights
        predictions = ensemble.predict(features, regime_features)
    """

    def __init__(
        self,
        model_names: List[str],
        initial_weights: Optional[np.ndarray] = None,
        rl_config: Optional[PPOConfig] = None,
    ):
        """
        Initialize ensemble with RL weight optimization.

        Args:
            model_names: Names of models in ensemble
            initial_weights: Initial model weights
            rl_config: RL optimizer configuration
        """
        self.model_names = model_names
        self.n_models = len(model_names)

        # Initialize weights
        if initial_weights is not None:
            self.weights = initial_weights
        else:
            self.weights = np.ones(self.n_models) / self.n_models

        # RL optimizer
        config = rl_config or PPOConfig(n_models=self.n_models)
        self.rl_optimizer = RLWeightOptimizer(config)

        # Performance tracking
        self._model_returns: deque = deque(maxlen=50)
        self._model_predictions: Dict[str, List[float]] = {
            name: [] for name in model_names
        }

        logger.info(f"DynamicEnsembleWithRL initialized with models: {model_names}")

    def update_model_returns(self, returns: Dict[str, float]) -> None:
        """
        Update recent returns for each model.

        Args:
            returns: Dictionary of model name to return
        """
        returns_array = np.array([returns.get(name, 0.0) for name in self.model_names])
        self._model_returns.append(returns_array)

    def get_optimized_weights(
        self,
        regime_features: Optional[np.ndarray] = None,
        deterministic: bool = False,
    ) -> np.ndarray:
        """
        Get RL-optimized weights based on recent performance.

        Args:
            regime_features: Current regime features
            deterministic: Whether to use deterministic policy

        Returns:
            Optimized weights
        """
        if len(self._model_returns) < 5:
            # Not enough history, use equal weights
            return self.weights

        # Compute state
        returns_array = np.array(list(self._model_returns))

        model_returns = returns_array[-1]
        model_sharpes = np.array([
            returns_array[:, i].mean() / (returns_array[:, i].std() + 1e-6)
            for i in range(self.n_models)
        ])

        # Correlation matrix
        if len(returns_array) >= 10:
            correlations = np.corrcoef(returns_array.T)
        else:
            correlations = np.eye(self.n_models)

        state = self.rl_optimizer.compute_state(
            model_returns=model_returns,
            model_sharpes=model_sharpes,
            correlations=correlations,
            regime_features=regime_features,
        )

        # Get optimized weights
        self.weights = self.rl_optimizer.get_optimal_weights(state, deterministic)

        return self.weights

    def record_outcome(
        self,
        portfolio_return: float,
        portfolio_volatility: float,
        next_regime_features: Optional[np.ndarray] = None,
    ) -> None:
        """
        Record trading outcome for RL learning.

        Args:
            portfolio_return: Realized return
            portfolio_volatility: Realized volatility
            next_regime_features: Next period regime features
        """
        if len(self._model_returns) < 5:
            return

        # Compute current and next states
        returns_array = np.array(list(self._model_returns))

        model_returns = returns_array[-1]
        model_sharpes = np.array([
            returns_array[:, i].mean() / (returns_array[:, i].std() + 1e-6)
            for i in range(self.n_models)
        ])

        state = self.rl_optimizer.compute_state(
            model_returns=model_returns,
            model_sharpes=model_sharpes,
        )

        # Compute reward
        reward = self.rl_optimizer.compute_reward(
            portfolio_return=portfolio_return,
            portfolio_volatility=portfolio_volatility,
        )

        # Next state (simplified - use same features)
        next_state = self.rl_optimizer.compute_state(
            model_returns=model_returns,  # Would be updated in practice
            model_sharpes=model_sharpes,
            regime_features=next_regime_features,
        )

        # Store experience
        # Action is the log of weights (inverse of softmax)
        action = np.log(self.weights + 1e-6)

        self.rl_optimizer.store_experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=False,
        )

    def get_weighted_prediction(
        self,
        model_predictions: Dict[str, float],
    ) -> float:
        """
        Get weighted ensemble prediction.

        Args:
            model_predictions: Predictions from each model

        Returns:
            Weighted prediction
        """
        preds = np.array([
            model_predictions.get(name, 0.0)
            for name in self.model_names
        ])

        return np.dot(self.weights, preds)

    def get_stats(self) -> Dict[str, Any]:
        """Get ensemble statistics."""
        return {
            'weights': dict(zip(self.model_names, self.weights.tolist())),
            'rl_stats': self.rl_optimizer.get_stats(),
            'history_length': len(self._model_returns),
        }
