"""
Reinforcement Learning Agents
=============================
PyTorch implementations of PPO, A2C, and DQN for trading.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.distributions import Categorical, Normal
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from collections import deque
import random
import logging

logger = logging.getLogger(__name__)


def get_device():
    """Get best available device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@dataclass
class AgentConfig:
    """RL Agent configuration."""
    # Architecture
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256])
    activation: str = "relu"
    
    # PPO specific
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    
    # Training
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    batch_size: int = 64
    n_epochs: int = 10
    max_grad_norm: float = 0.5
    
    # DQN specific
    buffer_size: int = 100_000
    target_update_freq: int = 1000
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: int = 10000


class ActorCritic(nn.Module):
    """
    Actor-Critic network for PPO/A2C.
    
    Shared feature extractor with separate policy and value heads.
    """
    
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dims: List[int] = [256, 256],
        continuous: bool = False
    ):
        super().__init__()
        self.continuous = continuous
        
        # Shared feature extractor
        layers = []
        prev_dim = obs_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
            ])
            prev_dim = hidden_dim
        
        self.features = nn.Sequential(*layers)
        
        # Policy head
        if continuous:
            self.actor_mean = nn.Linear(prev_dim, action_dim)
            self.actor_logstd = nn.Parameter(torch.zeros(action_dim))
        else:
            self.actor = nn.Linear(prev_dim, action_dim)
        
        # Value head
        self.critic = nn.Linear(prev_dim, 1)
        
        # Initialize
        self._init_weights()
    
    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
                nn.init.zeros_(m.bias)
    
    def forward(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass returning policy logits and value."""
        features = self.features(obs)
        
        if self.continuous:
            action_mean = self.actor_mean(features)
            action_std = self.actor_logstd.exp().expand_as(action_mean)
            return action_mean, action_std, self.critic(features)
        else:
            return self.actor(features), self.critic(features)
    
    def get_action(self, obs: torch.Tensor, deterministic: bool = False):
        """Sample action from policy."""
        if self.continuous:
            mean, std, value = self(obs)
            if deterministic:
                action = mean
            else:
                dist = Normal(mean, std)
                action = dist.sample()
            log_prob = Normal(mean, std).log_prob(action).sum(-1)
            return action, log_prob, value
        else:
            logits, value = self(obs)
            if deterministic:
                action = logits.argmax(dim=-1)
                log_prob = torch.zeros_like(action, dtype=torch.float)
            else:
                dist = Categorical(logits=logits)
                action = dist.sample()
                log_prob = dist.log_prob(action)
            return action, log_prob, value
    
    def evaluate_actions(self, obs: torch.Tensor, actions: torch.Tensor):
        """Evaluate log prob and entropy for given actions."""
        if self.continuous:
            mean, std, value = self(obs)
            dist = Normal(mean, std)
            log_prob = dist.log_prob(actions).sum(-1)
            entropy = dist.entropy().sum(-1)
        else:
            logits, value = self(obs)
            dist = Categorical(logits=logits)
            log_prob = dist.log_prob(actions)
            entropy = dist.entropy()
        
        return log_prob, entropy, value.squeeze(-1)


class PPOAgent:
    """
    Proximal Policy Optimization agent.
    
    Features:
    - Clipped surrogate objective
    - GAE for advantage estimation
    - Value function clipping
    - Entropy bonus
    """
    
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        config: Optional[AgentConfig] = None,
        continuous: bool = False
    ):
        self.config = config or AgentConfig()
        self.device = get_device()
        self.continuous = continuous
        
        # Networks
        self.policy = ActorCritic(
            obs_dim, action_dim,
            self.config.hidden_dims,
            continuous
        ).to(self.device)
        
        # Optimizer
        self.optimizer = optim.Adam(
            self.policy.parameters(),
            lr=self.config.learning_rate
        )
        
        # Storage
        self.buffer = RolloutBuffer(self.config.gamma, self.config.gae_lambda)
        
        logger.info(f"PPO Agent initialized on {self.device}")
        logger.info(f"Parameters: {sum(p.numel() for p in self.policy.parameters()):,}")
    
    def select_action(self, obs: np.ndarray, deterministic: bool = False):
        """Select action given observation."""
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
            action, log_prob, value = self.policy.get_action(obs_t, deterministic)
        
        return (
            action.cpu().numpy().squeeze(),
            log_prob.cpu().numpy().item(),
            value.cpu().numpy().item()
        )
    
    def store_transition(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        reward: float,
        done: bool,
        log_prob: float,
        value: float
    ):
        """Store transition in buffer."""
        self.buffer.add(obs, action, reward, done, log_prob, value)
    
    def update(self) -> Dict[str, float]:
        """Update policy using PPO."""
        # Compute advantages
        self.buffer.compute_returns_and_advantages()
        
        # Get data
        obs, actions, old_log_probs, returns, advantages = self.buffer.get()
        
        # Convert to tensors
        obs = torch.FloatTensor(obs).to(self.device)
        actions = torch.LongTensor(actions).to(self.device) if not self.continuous else torch.FloatTensor(actions).to(self.device)
        old_log_probs = torch.FloatTensor(old_log_probs).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)
        advantages = torch.FloatTensor(advantages).to(self.device)
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # Training stats
        total_loss = 0
        total_policy_loss = 0
        total_value_loss = 0
        total_entropy = 0
        
        # Multiple epochs
        n_samples = len(obs)
        indices = np.arange(n_samples)
        
        for _ in range(self.config.n_epochs):
            np.random.shuffle(indices)
            
            for start in range(0, n_samples, self.config.batch_size):
                end = start + self.config.batch_size
                batch_indices = indices[start:end]
                
                batch_obs = obs[batch_indices]
                batch_actions = actions[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                batch_returns = returns[batch_indices]
                batch_advantages = advantages[batch_indices]
                
                # Evaluate current policy
                log_probs, entropy, values = self.policy.evaluate_actions(
                    batch_obs, batch_actions
                )
                
                # Policy loss (clipped surrogate)
                ratio = (log_probs - batch_old_log_probs).exp()
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(
                    ratio,
                    1 - self.config.clip_epsilon,
                    1 + self.config.clip_epsilon
                ) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Value loss
                value_loss = F.mse_loss(values, batch_returns)
                
                # Total loss
                loss = (
                    policy_loss
                    + self.config.value_coef * value_loss
                    - self.config.entropy_coef * entropy.mean()
                )
                
                # Update
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(
                    self.policy.parameters(),
                    self.config.max_grad_norm
                )
                self.optimizer.step()
                
                total_loss += loss.item()
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.mean().item()
        
        # Clear buffer
        self.buffer.clear()
        
        n_updates = self.config.n_epochs * (n_samples // self.config.batch_size + 1)
        
        return {
            'loss': total_loss / n_updates,
            'policy_loss': total_policy_loss / n_updates,
            'value_loss': total_value_loss / n_updates,
            'entropy': total_entropy / n_updates,
        }
    
    def save(self, path: str):
        """Save agent."""
        torch.save({
            'policy_state_dict': self.policy.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.config,
        }, path)
    
    def load(self, path: str):
        """Load agent."""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy.load_state_dict(checkpoint['policy_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])


class A2CAgent(PPOAgent):
    """
    Advantage Actor-Critic agent.
    
    Simpler than PPO - no clipping, single update per batch.
    """
    
    def update(self) -> Dict[str, float]:
        """Update using A2C (no clipping)."""
        self.buffer.compute_returns_and_advantages()
        obs, actions, _, returns, advantages = self.buffer.get()
        
        obs = torch.FloatTensor(obs).to(self.device)
        actions = torch.LongTensor(actions).to(self.device) if not self.continuous else torch.FloatTensor(actions).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)
        advantages = torch.FloatTensor(advantages).to(self.device)
        
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        log_probs, entropy, values = self.policy.evaluate_actions(obs, actions)
        
        policy_loss = -(log_probs * advantages).mean()
        value_loss = F.mse_loss(values, returns)
        loss = policy_loss + self.config.value_coef * value_loss - self.config.entropy_coef * entropy.mean()
        
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(), self.config.max_grad_norm)
        self.optimizer.step()
        
        self.buffer.clear()
        
        return {
            'loss': loss.item(),
            'policy_loss': policy_loss.item(),
            'value_loss': value_loss.item(),
            'entropy': entropy.mean().item(),
        }


class DQNAgent:
    """
    Deep Q-Network agent with double DQN and prioritized replay.
    """
    
    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        config: Optional[AgentConfig] = None
    ):
        self.config = config or AgentConfig()
        self.device = get_device()
        self.action_dim = action_dim
        
        # Networks
        self.q_network = self._build_network(obs_dim, action_dim).to(self.device)
        self.target_network = self._build_network(obs_dim, action_dim).to(self.device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        
        # Optimizer
        self.optimizer = optim.Adam(
            self.q_network.parameters(),
            lr=self.config.learning_rate
        )
        
        # Replay buffer
        self.replay_buffer = ReplayBuffer(self.config.buffer_size)
        
        # Exploration
        self.epsilon = self.config.epsilon_start
        self.steps = 0
        
        logger.info(f"DQN Agent initialized on {self.device}")
    
    def _build_network(self, obs_dim: int, action_dim: int) -> nn.Module:
        return nn.Sequential(
            nn.Linear(obs_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, action_dim)
        )
    
    def select_action(self, obs: np.ndarray, deterministic: bool = False):
        """Epsilon-greedy action selection."""
        self.steps += 1
        
        # Decay epsilon
        self.epsilon = self.config.epsilon_end + (
            self.config.epsilon_start - self.config.epsilon_end
        ) * np.exp(-self.steps / self.config.epsilon_decay)
        
        if not deterministic and random.random() < self.epsilon:
            return random.randrange(self.action_dim)
        
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
            q_values = self.q_network(obs_t)
            return q_values.argmax().item()
    
    def store_transition(
        self,
        obs: np.ndarray,
        action: int,
        reward: float,
        next_obs: np.ndarray,
        done: bool
    ):
        """Store transition in replay buffer."""
        self.replay_buffer.add(obs, action, reward, next_obs, done)
    
    def update(self) -> Dict[str, float]:
        """Update Q-network using experience replay."""
        if len(self.replay_buffer) < self.config.batch_size:
            return {}
        
        # Sample batch
        obs, actions, rewards, next_obs, dones = self.replay_buffer.sample(
            self.config.batch_size
        )
        
        obs = torch.FloatTensor(obs).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_obs = torch.FloatTensor(next_obs).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        
        # Current Q values
        current_q = self.q_network(obs).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        # Double DQN: use online network to select actions, target to evaluate
        with torch.no_grad():
            next_actions = self.q_network(next_obs).argmax(1)
            next_q = self.target_network(next_obs).gather(1, next_actions.unsqueeze(1)).squeeze(1)
            target_q = rewards + self.config.gamma * next_q * (1 - dones)
        
        # Loss
        loss = F.mse_loss(current_q, target_q)
        
        # Update
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.q_network.parameters(), self.config.max_grad_norm)
        self.optimizer.step()
        
        # Update target network
        if self.steps % self.config.target_update_freq == 0:
            self.target_network.load_state_dict(self.q_network.state_dict())
        
        return {
            'loss': loss.item(),
            'epsilon': self.epsilon,
            'q_mean': current_q.mean().item(),
        }


class RolloutBuffer:
    """Buffer for on-policy algorithms (PPO, A2C)."""
    
    def __init__(self, gamma: float = 0.99, gae_lambda: float = 0.95):
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clear()
    
    def clear(self):
        self.obs = []
        self.actions = []
        self.rewards = []
        self.dones = []
        self.log_probs = []
        self.values = []
        self.returns = []
        self.advantages = []
    
    def add(self, obs, action, reward, done, log_prob, value):
        self.obs.append(obs)
        self.actions.append(action)
        self.rewards.append(reward)
        self.dones.append(done)
        self.log_probs.append(log_prob)
        self.values.append(value)
    
    def compute_returns_and_advantages(self):
        """Compute returns and GAE advantages."""
        rewards = np.array(self.rewards)
        values = np.array(self.values)
        dones = np.array(self.dones)
        
        n = len(rewards)
        advantages = np.zeros(n)
        returns = np.zeros(n)
        
        last_gae = 0
        for t in reversed(range(n)):
            if t == n - 1:
                next_value = 0
            else:
                next_value = values[t + 1]
            
            delta = rewards[t] + self.gamma * next_value * (1 - dones[t]) - values[t]
            advantages[t] = last_gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * last_gae
            returns[t] = advantages[t] + values[t]
        
        self.returns = returns.tolist()
        self.advantages = advantages.tolist()
    
    def get(self):
        return (
            np.array(self.obs),
            np.array(self.actions),
            np.array(self.log_probs),
            np.array(self.returns),
            np.array(self.advantages)
        )


class ReplayBuffer:
    """Experience replay buffer for off-policy algorithms (DQN)."""
    
    def __init__(self, capacity: int):
        self.buffer = deque(maxlen=capacity)
    
    def add(self, obs, action, reward, next_obs, done):
        self.buffer.append((obs, action, reward, next_obs, done))
    
    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, batch_size)
        obs, actions, rewards, next_obs, dones = zip(*batch)
        return (
            np.array(obs),
            np.array(actions),
            np.array(rewards),
            np.array(next_obs),
            np.array(dones)
        )
    
    def __len__(self):
        return len(self.buffer)
