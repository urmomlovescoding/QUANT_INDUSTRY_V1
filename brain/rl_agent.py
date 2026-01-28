"""
QUANT_INDUSTRY_V1 Reinforcement Learning Agent

PPO (Proximal Policy Optimization) and A2C implementation:
- Actor-Critic architecture
- Generalized Advantage Estimation (GAE)
- Clip-based policy updates
- Value function clipping
- Entropy bonus for exploration

Rollback Plan: Delete this file
Tests Required: Policy gradient computation, value estimation
Failure Modes: Fall back to random policy
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import pickle

logger = logging.getLogger(__name__)


# =============================================================================
# NEURAL NETWORK (Numpy-based for minimal dependencies)
# =============================================================================

class ActivationFunction:
    """Activation functions."""

    @staticmethod
    def relu(x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)

    @staticmethod
    def relu_derivative(x: np.ndarray) -> np.ndarray:
        return (x > 0).astype(np.float32)

    @staticmethod
    def tanh(x: np.ndarray) -> np.ndarray:
        return np.tanh(x)

    @staticmethod
    def tanh_derivative(x: np.ndarray) -> np.ndarray:
        return 1 - np.tanh(x) ** 2

    @staticmethod
    def sigmoid(x: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))

    @staticmethod
    def softmax(x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


class NeuralNetwork:
    """
    Simple feedforward neural network.

    For production, replace with PyTorch/TensorFlow.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dims: List[int],
        output_dim: int,
        activation: str = 'relu',
        output_activation: str = 'none',
        learning_rate: float = 3e-4,
    ):
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.output_dim = output_dim
        self.lr = learning_rate

        # Activation functions
        self.activation = getattr(ActivationFunction, activation)
        self.activation_derivative = getattr(ActivationFunction, f"{activation}_derivative", lambda x: np.ones_like(x))
        self.output_activation = getattr(ActivationFunction, output_activation, lambda x: x)

        # Initialize weights (Xavier initialization)
        self.weights = []
        self.biases = []

        dims = [input_dim] + hidden_dims + [output_dim]

        for i in range(len(dims) - 1):
            scale = np.sqrt(2.0 / dims[i])
            self.weights.append(np.random.randn(dims[i], dims[i+1]).astype(np.float32) * scale)
            self.biases.append(np.zeros(dims[i+1], dtype=np.float32))

        # Adam optimizer state
        self.m_weights = [np.zeros_like(w) for w in self.weights]
        self.v_weights = [np.zeros_like(w) for w in self.weights]
        self.m_biases = [np.zeros_like(b) for b in self.biases]
        self.v_biases = [np.zeros_like(b) for b in self.biases]
        self.t = 0

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass."""
        self.activations = [x]

        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            z = x @ w + b

            if i < len(self.weights) - 1:
                x = self.activation(z)
            else:
                x = self.output_activation(z)

            self.activations.append(x)

        return x

    def backward(self, loss_gradient: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """Backward pass."""
        weight_grads = []
        bias_grads = []

        delta = loss_gradient

        for i in range(len(self.weights) - 1, -1, -1):
            # Gradient for weights and biases
            w_grad = self.activations[i].T @ delta / len(delta)
            b_grad = delta.mean(axis=0)

            weight_grads.insert(0, w_grad)
            bias_grads.insert(0, b_grad)

            if i > 0:
                # Propagate gradient
                delta = delta @ self.weights[i].T
                delta = delta * self.activation_derivative(self.activations[i])

        return weight_grads, bias_grads

    def update(self, weight_grads: List[np.ndarray], bias_grads: List[np.ndarray]) -> None:
        """Update weights using Adam optimizer."""
        self.t += 1
        beta1, beta2 = 0.9, 0.999
        eps = 1e-8

        for i, (w_grad, b_grad) in enumerate(zip(weight_grads, bias_grads)):
            # Update moments for weights
            self.m_weights[i] = beta1 * self.m_weights[i] + (1 - beta1) * w_grad
            self.v_weights[i] = beta2 * self.v_weights[i] + (1 - beta2) * (w_grad ** 2)

            # Bias correction
            m_hat = self.m_weights[i] / (1 - beta1 ** self.t)
            v_hat = self.v_weights[i] / (1 - beta2 ** self.t)

            # Update weights
            self.weights[i] -= self.lr * m_hat / (np.sqrt(v_hat) + eps)

            # Same for biases
            self.m_biases[i] = beta1 * self.m_biases[i] + (1 - beta1) * b_grad
            self.v_biases[i] = beta2 * self.v_biases[i] + (1 - beta2) * (b_grad ** 2)

            m_hat = self.m_biases[i] / (1 - beta1 ** self.t)
            v_hat = self.v_biases[i] / (1 - beta2 ** self.t)

            self.biases[i] -= self.lr * m_hat / (np.sqrt(v_hat) + eps)

    def get_params(self) -> Dict[str, Any]:
        """Get all parameters."""
        return {
            'weights': [w.copy() for w in self.weights],
            'biases': [b.copy() for b in self.biases],
        }

    def set_params(self, params: Dict[str, Any]) -> None:
        """Set all parameters."""
        self.weights = [w.copy() for w in params['weights']]
        self.biases = [b.copy() for b in params['biases']]


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

@dataclass
class PPOConfig:
    """PPO hyperparameters."""
    # Network architecture
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256])
    activation: str = 'relu'

    # PPO specific
    clip_epsilon: float = 0.2
    clip_value: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    max_grad_norm: float = 0.5

    # GAE
    gamma: float = 0.99
    gae_lambda: float = 0.95

    # Training
    learning_rate: float = 3e-4
    batch_size: int = 64
    n_epochs: int = 10
    n_steps: int = 2048  # Steps per update

    # Exploration
    initial_std: float = 1.0
    min_std: float = 0.1
    std_decay: float = 0.995


@dataclass
class RolloutBuffer:
    """Buffer to store rollout data."""
    observations: List[np.ndarray] = field(default_factory=list)
    actions: List[np.ndarray] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    log_probs: List[float] = field(default_factory=list)
    dones: List[bool] = field(default_factory=list)

    # Computed during finalization
    returns: Optional[np.ndarray] = None
    advantages: Optional[np.ndarray] = None

    def add(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        reward: float,
        value: float,
        log_prob: float,
        done: bool
    ) -> None:
        """Add a transition."""
        self.observations.append(obs)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)

    def compute_returns_and_advantages(
        self,
        last_value: float,
        gamma: float,
        gae_lambda: float
    ) -> None:
        """Compute returns and GAE advantages."""
        n = len(self.rewards)

        self.returns = np.zeros(n, dtype=np.float32)
        self.advantages = np.zeros(n, dtype=np.float32)

        # GAE computation
        last_gae = 0.0

        for t in reversed(range(n)):
            if t == n - 1:
                next_value = last_value
                next_done = 1.0
            else:
                next_value = self.values[t + 1]
                next_done = 1.0 - float(self.dones[t + 1])

            delta = self.rewards[t] + gamma * next_value * next_done - self.values[t]
            self.advantages[t] = last_gae = delta + gamma * gae_lambda * next_done * last_gae

        self.returns = self.advantages + np.array(self.values)

        # Normalize advantages
        self.advantages = (self.advantages - self.advantages.mean()) / (self.advantages.std() + 1e-8)

    def get_batches(self, batch_size: int) -> List[Dict[str, np.ndarray]]:
        """Generate random minibatches."""
        n = len(self.observations)
        indices = np.random.permutation(n)

        batches = []
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            batch_indices = indices[start:end]

            batches.append({
                'observations': np.array([self.observations[i] for i in batch_indices]),
                'actions': np.array([self.actions[i] for i in batch_indices]),
                'returns': self.returns[batch_indices],
                'advantages': self.advantages[batch_indices],
                'old_log_probs': np.array([self.log_probs[i] for i in batch_indices]),
                'old_values': np.array([self.values[i] for i in batch_indices]),
            })

        return batches

    def clear(self) -> None:
        """Clear buffer."""
        self.observations.clear()
        self.actions.clear()
        self.rewards.clear()
        self.values.clear()
        self.log_probs.clear()
        self.dones.clear()
        self.returns = None
        self.advantages = None


# =============================================================================
# PPO AGENT
# =============================================================================

class PPOAgent:
    """
    Proximal Policy Optimization agent.

    Uses Actor-Critic architecture with clipped objective.
    """

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        config: PPOConfig = None,
        continuous: bool = True,
    ):
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.config = config or PPOConfig()
        self.continuous = continuous

        # Actor network (policy)
        if continuous:
            # Output: mean of action distribution
            self.actor = NeuralNetwork(
                input_dim=obs_dim,
                hidden_dims=self.config.hidden_dims,
                output_dim=action_dim,
                activation=self.config.activation,
                output_activation='tanh',  # Bound actions to [-1, 1]
                learning_rate=self.config.learning_rate,
            )
            # Log standard deviation (learnable)
            self.log_std = np.full(action_dim, np.log(self.config.initial_std), dtype=np.float32)
        else:
            # Output: action logits
            self.actor = NeuralNetwork(
                input_dim=obs_dim,
                hidden_dims=self.config.hidden_dims,
                output_dim=action_dim,
                activation=self.config.activation,
                output_activation='none',  # Softmax applied separately
                learning_rate=self.config.learning_rate,
            )

        # Critic network (value function)
        self.critic = NeuralNetwork(
            input_dim=obs_dim,
            hidden_dims=self.config.hidden_dims,
            output_dim=1,
            activation=self.config.activation,
            output_activation='none',
            learning_rate=self.config.learning_rate,
        )

        # Rollout buffer
        self.buffer = RolloutBuffer()

        # Training stats
        self.total_steps = 0
        self.total_episodes = 0
        self.training_history: List[Dict[str, float]] = []

    def get_action(
        self,
        obs: np.ndarray,
        deterministic: bool = False
    ) -> Tuple[np.ndarray, float, float]:
        """
        Get action from policy.

        Args:
            obs: Observation
            deterministic: If True, return mean action

        Returns:
            Tuple of (action, log_prob, value)
        """
        obs = obs.reshape(1, -1).astype(np.float32)

        # Get value
        value = float(self.critic.forward(obs)[0, 0])

        if self.continuous:
            # Get action mean
            action_mean = self.actor.forward(obs)[0]
            std = np.exp(self.log_std)

            if deterministic:
                action = action_mean
            else:
                # Sample from Gaussian
                action = action_mean + std * np.random.randn(self.action_dim)

            # Clip action
            action = np.clip(action, -1.0, 1.0)

            # Compute log probability
            log_prob = self._gaussian_log_prob(action, action_mean, std)

        else:
            # Discrete action
            logits = self.actor.forward(obs)[0]
            probs = ActivationFunction.softmax(logits)

            if deterministic:
                action = np.array([np.argmax(probs)])
            else:
                action = np.array([np.random.choice(self.action_dim, p=probs)])

            log_prob = np.log(probs[action[0]] + 1e-8)

        return action, float(log_prob), value

    def _gaussian_log_prob(
        self,
        action: np.ndarray,
        mean: np.ndarray,
        std: np.ndarray
    ) -> float:
        """Compute Gaussian log probability."""
        var = std ** 2
        log_prob = -0.5 * np.sum(
            np.log(2 * np.pi * var) + (action - mean) ** 2 / var
        )
        return float(log_prob)

    def store_transition(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        reward: float,
        value: float,
        log_prob: float,
        done: bool
    ) -> None:
        """Store transition in buffer."""
        self.buffer.add(obs, action, reward, value, log_prob, done)
        self.total_steps += 1

    def update(self) -> Dict[str, float]:
        """
        Perform PPO update.

        Returns:
            Dictionary of training metrics
        """
        if len(self.buffer.observations) < self.config.batch_size:
            return {}

        # Get last value for GAE
        last_obs = self.buffer.observations[-1].reshape(1, -1)
        last_value = float(self.critic.forward(last_obs)[0, 0])

        # Compute returns and advantages
        self.buffer.compute_returns_and_advantages(
            last_value,
            self.config.gamma,
            self.config.gae_lambda
        )

        # Training metrics
        all_policy_loss = []
        all_value_loss = []
        all_entropy = []

        # Multiple epochs of updates
        for epoch in range(self.config.n_epochs):
            batches = self.buffer.get_batches(self.config.batch_size)

            for batch in batches:
                policy_loss, value_loss, entropy = self._update_batch(batch)
                all_policy_loss.append(policy_loss)
                all_value_loss.append(value_loss)
                all_entropy.append(entropy)

        # Clear buffer
        self.buffer.clear()

        # Decay exploration std
        if self.continuous:
            self.log_std = np.maximum(
                self.log_std - np.log(1 / self.config.std_decay),
                np.log(self.config.min_std)
            )

        metrics = {
            'policy_loss': float(np.mean(all_policy_loss)),
            'value_loss': float(np.mean(all_value_loss)),
            'entropy': float(np.mean(all_entropy)),
            'std': float(np.exp(self.log_std).mean()) if self.continuous else 0.0,
        }

        self.training_history.append(metrics)

        return metrics

    def _update_batch(self, batch: Dict[str, np.ndarray]) -> Tuple[float, float, float]:
        """Update on a single batch."""
        obs = batch['observations']
        actions = batch['actions']
        returns = batch['returns']
        advantages = batch['advantages']
        old_log_probs = batch['old_log_probs']
        old_values = batch['old_values']

        # Forward pass
        values = self.critic.forward(obs).flatten()

        if self.continuous:
            action_means = self.actor.forward(obs)
            std = np.exp(self.log_std)

            # Current log probs
            var = std ** 2
            log_probs = -0.5 * np.sum(
                np.log(2 * np.pi * var) + (actions - action_means) ** 2 / var,
                axis=1
            )

            # Entropy
            entropy = 0.5 * np.sum(np.log(2 * np.pi * np.e * var))

        else:
            logits = self.actor.forward(obs)
            probs = ActivationFunction.softmax(logits)

            # Get log probs for taken actions
            log_probs = np.log(probs[np.arange(len(actions)), actions.flatten()] + 1e-8)

            # Entropy
            entropy = -np.sum(probs * np.log(probs + 1e-8), axis=1).mean()

        # PPO clipped objective
        ratio = np.exp(log_probs - old_log_probs)
        clipped_ratio = np.clip(ratio, 1 - self.config.clip_epsilon, 1 + self.config.clip_epsilon)

        policy_loss = -np.minimum(
            ratio * advantages,
            clipped_ratio * advantages
        ).mean()

        # Value loss with clipping
        value_clipped = old_values + np.clip(
            values - old_values,
            -self.config.clip_value,
            self.config.clip_value
        )
        value_loss1 = (values - returns) ** 2
        value_loss2 = (value_clipped - returns) ** 2
        value_loss = 0.5 * np.maximum(value_loss1, value_loss2).mean()

        # Total loss
        loss = policy_loss + self.config.value_coef * value_loss - self.config.entropy_coef * entropy

        # Backward pass for actor
        if self.continuous:
            # Gradient of log prob w.r.t. action mean
            d_log_prob = (actions - action_means) / (std ** 2)

            # Policy gradient
            d_policy = -d_log_prob * advantages.reshape(-1, 1) * np.minimum(
                ratio.reshape(-1, 1),
                np.where(
                    advantages.reshape(-1, 1) >= 0,
                    (1 + self.config.clip_epsilon),
                    (1 - self.config.clip_epsilon)
                )
            )

            weight_grads, bias_grads = self.actor.backward(d_policy / len(obs))
            self.actor.update(weight_grads, bias_grads)

            # Update log_std with gradient
            d_std = -1 / std + (actions - action_means) ** 2 / (std ** 3)
            d_std = d_std.mean(axis=0) * self.config.learning_rate
            self.log_std -= np.clip(d_std, -0.1, 0.1)

        else:
            # Discrete action gradient
            probs = ActivationFunction.softmax(self.actor.forward(obs))
            d_logits = probs.copy()
            d_logits[np.arange(len(actions)), actions.flatten()] -= 1
            d_logits *= (ratio * advantages).reshape(-1, 1)

            weight_grads, bias_grads = self.actor.backward(d_logits / len(obs))
            self.actor.update(weight_grads, bias_grads)

        # Backward pass for critic
        d_values = (values - returns).reshape(-1, 1) * self.config.value_coef
        weight_grads, bias_grads = self.critic.backward(d_values / len(obs))
        self.critic.update(weight_grads, bias_grads)

        return float(policy_loss), float(value_loss), float(entropy)

    def save(self, path: str) -> None:
        """Save agent to file."""
        state = {
            'actor_params': self.actor.get_params(),
            'critic_params': self.critic.get_params(),
            'log_std': self.log_std if self.continuous else None,
            'config': self.config,
            'obs_dim': self.obs_dim,
            'action_dim': self.action_dim,
            'continuous': self.continuous,
            'total_steps': self.total_steps,
            'training_history': self.training_history,
        }

        with open(path, 'wb') as f:
            pickle.dump(state, f)

        logger.info(f"Agent saved to {path}")

    @classmethod
    def load(cls, path: str) -> 'PPOAgent':
        """Load agent from file."""
        with open(path, 'rb') as f:
            state = pickle.load(f)

        agent = cls(
            obs_dim=state['obs_dim'],
            action_dim=state['action_dim'],
            config=state['config'],
            continuous=state['continuous'],
        )

        agent.actor.set_params(state['actor_params'])
        agent.critic.set_params(state['critic_params'])

        if state['continuous']:
            agent.log_std = state['log_std']

        agent.total_steps = state['total_steps']
        agent.training_history = state['training_history']

        logger.info(f"Agent loaded from {path}")

        return agent


# =============================================================================
# A2C AGENT (Synchronous Advantage Actor-Critic)
# =============================================================================

class A2CAgent:
    """
    Advantage Actor-Critic agent.

    Simpler alternative to PPO without clipping.
    """

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        config: PPOConfig = None,
        continuous: bool = True,
    ):
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.config = config or PPOConfig()
        self.continuous = continuous

        # Networks (same architecture as PPO)
        if continuous:
            self.actor = NeuralNetwork(
                input_dim=obs_dim,
                hidden_dims=self.config.hidden_dims,
                output_dim=action_dim,
                activation=self.config.activation,
                output_activation='tanh',
                learning_rate=self.config.learning_rate,
            )
            self.log_std = np.full(action_dim, np.log(self.config.initial_std), dtype=np.float32)
        else:
            self.actor = NeuralNetwork(
                input_dim=obs_dim,
                hidden_dims=self.config.hidden_dims,
                output_dim=action_dim,
                activation=self.config.activation,
                output_activation='none',
                learning_rate=self.config.learning_rate,
            )

        self.critic = NeuralNetwork(
            input_dim=obs_dim,
            hidden_dims=self.config.hidden_dims,
            output_dim=1,
            activation=self.config.activation,
            output_activation='none',
            learning_rate=self.config.learning_rate,
        )

        self.total_steps = 0
        self.training_history: List[Dict[str, float]] = []

    def get_action(
        self,
        obs: np.ndarray,
        deterministic: bool = False
    ) -> Tuple[np.ndarray, float, float]:
        """Get action from policy."""
        obs = obs.reshape(1, -1).astype(np.float32)
        value = float(self.critic.forward(obs)[0, 0])

        if self.continuous:
            action_mean = self.actor.forward(obs)[0]
            std = np.exp(self.log_std)

            if deterministic:
                action = action_mean
            else:
                action = action_mean + std * np.random.randn(self.action_dim)

            action = np.clip(action, -1.0, 1.0)

            var = std ** 2
            log_prob = -0.5 * np.sum(np.log(2 * np.pi * var) + (action - action_mean) ** 2 / var)

        else:
            logits = self.actor.forward(obs)[0]
            probs = ActivationFunction.softmax(logits)

            if deterministic:
                action = np.array([np.argmax(probs)])
            else:
                action = np.array([np.random.choice(self.action_dim, p=probs)])

            log_prob = np.log(probs[action[0]] + 1e-8)

        return action, float(log_prob), value

    def update(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_obs: np.ndarray,
        done: bool
    ) -> Dict[str, float]:
        """
        Single-step A2C update.

        Args:
            obs: Current observation
            action: Action taken
            reward: Reward received
            next_obs: Next observation
            done: Episode done flag

        Returns:
            Training metrics
        """
        obs = obs.reshape(1, -1).astype(np.float32)
        next_obs = next_obs.reshape(1, -1).astype(np.float32)

        # Compute values
        value = self.critic.forward(obs)[0, 0]
        next_value = 0.0 if done else self.critic.forward(next_obs)[0, 0]

        # TD error / advantage
        target = reward + self.config.gamma * next_value
        advantage = target - value

        # Value loss
        value_loss = 0.5 * advantage ** 2

        # Policy gradient
        if self.continuous:
            action_mean = self.actor.forward(obs)[0]
            std = np.exp(self.log_std)

            d_log_prob = (action - action_mean) / (std ** 2)
            d_policy = -d_log_prob * advantage

            weight_grads, bias_grads = self.actor.backward(d_policy.reshape(1, -1))
            self.actor.update(weight_grads, bias_grads)

        else:
            logits = self.actor.forward(obs)
            probs = ActivationFunction.softmax(logits)

            d_logits = probs.copy()
            d_logits[0, action[0]] -= 1
            d_logits *= advantage

            weight_grads, bias_grads = self.actor.backward(d_logits)
            self.actor.update(weight_grads, bias_grads)

        # Update critic
        d_value = np.array([[advantage * self.config.value_coef]])
        weight_grads, bias_grads = self.critic.backward(d_value)
        self.critic.update(weight_grads, bias_grads)

        self.total_steps += 1

        return {
            'value_loss': float(value_loss),
            'advantage': float(advantage),
        }

    def save(self, path: str) -> None:
        """Save agent."""
        state = {
            'actor_params': self.actor.get_params(),
            'critic_params': self.critic.get_params(),
            'log_std': self.log_std if self.continuous else None,
            'config': self.config,
            'obs_dim': self.obs_dim,
            'action_dim': self.action_dim,
            'continuous': self.continuous,
            'total_steps': self.total_steps,
        }

        with open(path, 'wb') as f:
            pickle.dump(state, f)

    @classmethod
    def load(cls, path: str) -> 'A2CAgent':
        """Load agent."""
        with open(path, 'rb') as f:
            state = pickle.load(f)

        agent = cls(
            obs_dim=state['obs_dim'],
            action_dim=state['action_dim'],
            config=state['config'],
            continuous=state['continuous'],
        )

        agent.actor.set_params(state['actor_params'])
        agent.critic.set_params(state['critic_params'])

        if state['continuous']:
            agent.log_std = state['log_std']

        agent.total_steps = state['total_steps']

        return agent
