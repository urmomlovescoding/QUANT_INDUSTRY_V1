"""
FuturesRLAgent - Reinforcement Learning Agent for Optimal Execution
=================================================================
PPO-based agent that learns optimal entry/exit timing and position sizing.

Features:
- Proximal Policy Optimization (PPO) with clipped objectives
- Actor-Critic architecture with shared features
- Intrinsic curiosity module for exploration
- Risk-adjusted reward shaping
- Multi-timeframe state representation
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical
import numpy as np
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class RLConfig:
    """Configuration for RL agent"""
    # Architecture
    state_dim: int = 128
    hidden_dim: int = 256
    num_actions: int = 5  # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    
    # PPO hyperparameters
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    max_grad_norm: float = 0.5
    
    # Training
    learning_rate: float = 3e-4
    batch_size: int = 64
    n_epochs: int = 4
    n_steps: int = 2048
    
    # Risk management
    max_position: int = 6
    risk_penalty: float = 0.1
    drawdown_penalty: float = 0.5
    
    # Curiosity module
    use_curiosity: bool = True
    curiosity_coef: float = 0.1
    
    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


class SharedFeatureExtractor(nn.Module):
    """Shared feature extractor for actor and critic"""
    
    def __init__(self, state_dim: int, hidden_dim: int):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        
        # Attention for temporal features
        self.temporal_attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=4,
            dropout=0.1,
            batch_first=True
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (state_dim,) or (batch, state_dim) or (batch, seq, state_dim)
        if x.dim() == 1:
            # Single state vector
            x = x.unsqueeze(0)  # Add batch dimension
            return self.network(x).squeeze(0)
        elif x.dim() == 2:
            return self.network(x)
        else:
            # Apply network to each timestep
            batch, seq, dim = x.shape
            x = x.view(-1, dim)
            x = self.network(x)
            x = x.view(batch, seq, -1)
            
            # Temporal attention
            x, _ = self.temporal_attention(x, x, x)
            return x[:, -1, :]  # Return last timestep


class Actor(nn.Module):
    """Policy network - outputs action probabilities"""
    
    def __init__(self, hidden_dim: int, num_actions: int):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, num_actions),
        )
        
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        logits = self.network(features)
        return F.softmax(logits, dim=-1)


class Critic(nn.Module):
    """Value network - estimates state value"""
    
    def __init__(self, hidden_dim: int):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 1),
        )
        
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features).squeeze(-1)


class IntrinsicCuriosityModule(nn.Module):
    """
    Curiosity-driven exploration via prediction error
    Encourages exploration of novel market states
    """
    
    def __init__(self, state_dim: int, hidden_dim: int, num_actions: int):
        super().__init__()
        
        # Forward model: predicts next state given current state and action
        self.forward_model = nn.Sequential(
            nn.Linear(state_dim + num_actions, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, state_dim),
        )
        
        # Inverse model: predicts action given state and next state
        self.inverse_model = nn.Sequential(
            nn.Linear(state_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_actions),
        )
        
        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, state_dim),
        )
        
    def forward(
        self, 
        state: torch.Tensor, 
        next_state: torch.Tensor, 
        action: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            intrinsic_reward: Curiosity bonus
            forward_loss: Prediction error
            inverse_loss: Action prediction loss
        """
        # Encode states
        encoded_state = self.state_encoder(state)
        encoded_next = self.state_encoder(next_state)
        
        # Forward model prediction
        action_onehot = F.one_hot(action, num_classes=self.forward_model[0].in_features - state.shape[-1])
        forward_input = torch.cat([encoded_state, action_onehot.float()], dim=-1)
        predicted_next = self.forward_model(forward_input)
        
        # Intrinsic reward = prediction error
        forward_loss = F.mse_loss(predicted_next, encoded_next.detach(), reduction='none').mean(-1)
        intrinsic_reward = forward_loss.detach()
        
        # Inverse model
        inverse_input = torch.cat([encoded_state, encoded_next], dim=-1)
        predicted_action = self.inverse_model(inverse_input)
        inverse_loss = F.cross_entropy(predicted_action, action)
        
        return intrinsic_reward, forward_loss.mean(), inverse_loss


class RolloutBuffer:
    """Stores experience for PPO training"""
    
    def __init__(self, n_steps: int, state_dim: int, device: str):
        self.n_steps = n_steps
        self.device = device
        
        self.states = torch.zeros((n_steps, state_dim), device=device)
        self.actions = torch.zeros(n_steps, dtype=torch.long, device=device)
        self.rewards = torch.zeros(n_steps, device=device)
        self.dones = torch.zeros(n_steps, device=device)
        self.values = torch.zeros(n_steps, device=device)
        self.log_probs = torch.zeros(n_steps, device=device)
        self.advantages = torch.zeros(n_steps, device=device)
        self.returns = torch.zeros(n_steps, device=device)
        
        self.ptr = 0
        self.full = False
        
    def add(
        self,
        state: torch.Tensor,
        action: int,
        reward: float,
        done: bool,
        value: float,
        log_prob: float
    ):
        self.states[self.ptr] = state
        self.actions[self.ptr] = action
        self.rewards[self.ptr] = reward
        self.dones[self.ptr] = done
        self.values[self.ptr] = value
        self.log_probs[self.ptr] = log_prob
        
        self.ptr += 1
        if self.ptr >= self.n_steps:
            self.ptr = 0
            self.full = True
            
    def compute_returns_and_advantages(
        self,
        last_value: float,
        gamma: float,
        gae_lambda: float
    ):
        """Compute GAE advantages and returns"""
        last_gae = 0
        n = self.n_steps if self.full else self.ptr
        
        for t in reversed(range(n)):
            if t == n - 1:
                next_value = last_value
            else:
                next_value = self.values[t + 1]
                
            delta = self.rewards[t] + gamma * next_value * (1 - self.dones[t]) - self.values[t]
            last_gae = delta + gamma * gae_lambda * (1 - self.dones[t]) * last_gae
            self.advantages[t] = last_gae
            
        self.returns[:n] = self.advantages[:n] + self.values[:n]
        
        # Normalize advantages
        if n > 1:
            self.advantages[:n] = (self.advantages[:n] - self.advantages[:n].mean()) / (self.advantages[:n].std() + 1e-8)
            
    def get_batches(self, batch_size: int):
        """Generate random batches for training"""
        n = self.n_steps if self.full else self.ptr
        indices = torch.randperm(n, device=self.device)
        
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            batch_indices = indices[start:end]
            
            yield (
                self.states[batch_indices],
                self.actions[batch_indices],
                self.log_probs[batch_indices],
                self.advantages[batch_indices],
                self.returns[batch_indices],
            )
            
    def reset(self):
        self.ptr = 0
        self.full = False


@dataclass
class TradingState:
    """Trading environment state"""
    position: int = 0
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    peak_equity: float = 0.0
    drawdown: float = 0.0
    trades_today: int = 0
    
    def to_tensor(self, device: str = "cpu") -> torch.Tensor:
        return torch.tensor([
            self.position / 6,  # Normalize
            self.unrealized_pnl / 1000,
            self.realized_pnl / 1000,
            self.drawdown,
            self.trades_today / 20,
        ], dtype=torch.float32, device=device)


class FuturesRLAgent(nn.Module):
    """
    PPO-based RL agent for futures trading
    """
    
    def __init__(self, config: Optional[RLConfig] = None):
        super().__init__()
        
        self.config = config or RLConfig()
        self.device = torch.device(self.config.device)
        
        # Networks
        self.feature_extractor = SharedFeatureExtractor(
            self.config.state_dim,
            self.config.hidden_dim
        )
        self.actor = Actor(self.config.hidden_dim, self.config.num_actions)
        self.critic = Critic(self.config.hidden_dim)
        
        # Curiosity module
        if self.config.use_curiosity:
            self.curiosity = IntrinsicCuriosityModule(
                self.config.state_dim,
                self.config.hidden_dim,
                self.config.num_actions
            )
        else:
            self.curiosity = None
            
        # Move to device
        self.to(self.device)
        
        # Optimizer
        self.optimizer = torch.optim.AdamW(
            self.parameters(),
            lr=self.config.learning_rate,
            weight_decay=0.01
        )
        
        # Rollout buffer
        self.buffer = RolloutBuffer(
            self.config.n_steps,
            self.config.state_dim,
            self.device
        )
        
        # Trading state
        self.trading_state = TradingState()
        
        # Action mapping
        self.action_to_signal = {
            0: ("STRONG_BUY", 1.0),
            1: ("BUY", 0.5),
            2: ("HOLD", 0.0),
            3: ("SELL", -0.5),
            4: ("STRONG_SELL", -1.0),
        }
        
        # Statistics
        self.episode_rewards = deque(maxlen=100)
        self.episode_lengths = deque(maxlen=100)
        
        logger.info(f"FuturesRLAgent initialized on {self.device}")
        
    def get_features(self, state: torch.Tensor) -> torch.Tensor:
        """Extract features from state"""
        return self.feature_extractor(state)
        
    def get_action(
        self, 
        state: torch.Tensor,
        deterministic: bool = False
    ) -> Tuple[int, float, float]:
        """
        Get action from policy
        
        Returns:
            action: Selected action index
            log_prob: Log probability of action
            value: Estimated state value
        """
        with torch.no_grad():
            features = self.get_features(state)
            probs = self.actor(features)
            value = self.critic(features)
            
            if deterministic:
                action = probs.argmax(-1).item()
                log_prob = torch.log(probs[..., action] + 1e-8).item()
            else:
                dist = Categorical(probs)
                action = dist.sample().item()
                log_prob = dist.log_prob(torch.tensor(action, device=self.device)).item()
                
        return action, log_prob, value.item()
        
    def compute_reward(
        self,
        action: int,
        price_change: float,
        current_price: float,
        prev_position: int
    ) -> float:
        """
        Compute risk-adjusted reward
        
        Reward shaping:
        - PnL from position
        - Risk penalty for large positions
        - Drawdown penalty
        - Transaction cost
        """
        signal_name, signal_strength = self.action_to_signal[action]
        
        # Position change
        target_position = int(signal_strength * self.config.max_position)
        position_change = target_position - prev_position
        
        # PnL
        pnl = prev_position * price_change * 20  # $20 per point per contract
        
        # Update trading state
        self.trading_state.position = target_position
        self.trading_state.unrealized_pnl += pnl
        
        if position_change != 0:
            self.trading_state.trades_today += 1
            
        # Update peak and drawdown
        total_equity = self.trading_state.realized_pnl + self.trading_state.unrealized_pnl
        if total_equity > self.trading_state.peak_equity:
            self.trading_state.peak_equity = total_equity
        self.trading_state.drawdown = (self.trading_state.peak_equity - total_equity) / max(self.trading_state.peak_equity, 1)
        
        # Reward components
        reward = pnl / 100  # Scale PnL
        
        # Risk penalty
        risk_penalty = -self.config.risk_penalty * abs(target_position) / self.config.max_position
        
        # Drawdown penalty
        dd_penalty = -self.config.drawdown_penalty * self.trading_state.drawdown
        
        # Transaction cost
        transaction_cost = -abs(position_change) * 2.5 / 100  # ~$2.50 per contract round trip
        
        total_reward = reward + risk_penalty + dd_penalty + transaction_cost
        
        return total_reward
        
    def update(self) -> Dict[str, float]:
        """PPO update step"""
        # Get final value for GAE
        last_state = self.buffer.states[self.buffer.ptr - 1]
        with torch.no_grad():
            features = self.get_features(last_state.unsqueeze(0))
            last_value = self.critic(features).item()
            
        # Compute returns and advantages
        self.buffer.compute_returns_and_advantages(
            last_value,
            self.config.gamma,
            self.config.gae_lambda
        )
        
        # Training stats
        total_loss = 0
        total_policy_loss = 0
        total_value_loss = 0
        total_entropy = 0
        n_updates = 0
        
        # Multiple epochs
        for _ in range(self.config.n_epochs):
            for states, actions, old_log_probs, advantages, returns in self.buffer.get_batches(self.config.batch_size):
                # Forward pass
                features = self.get_features(states)
                probs = self.actor(features)
                values = self.critic(features)
                
                # Distribution
                dist = Categorical(probs)
                new_log_probs = dist.log_prob(actions)
                entropy = dist.entropy().mean()
                
                # Ratio for PPO
                ratio = torch.exp(new_log_probs - old_log_probs)
                
                # Clipped surrogate objective
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1 - self.config.clip_epsilon, 1 + self.config.clip_epsilon) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Value loss
                value_loss = F.mse_loss(values, returns)
                
                # Total loss
                loss = (
                    policy_loss 
                    + self.config.value_coef * value_loss 
                    - self.config.entropy_coef * entropy
                )
                
                # Curiosity loss
                if self.curiosity is not None and self.buffer.ptr > 1:
                    # Get next states
                    next_idx = torch.clamp(
                        torch.arange(len(states), device=self.device) + 1,
                        max=self.buffer.ptr - 1
                    )
                    next_states = self.buffer.states[next_idx]
                    
                    _, forward_loss, inverse_loss = self.curiosity(states, next_states, actions)
                    curiosity_loss = forward_loss + inverse_loss
                    loss = loss + self.config.curiosity_coef * curiosity_loss
                    
                # Optimize
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.parameters(), self.config.max_grad_norm)
                self.optimizer.step()
                
                # Stats
                total_loss += loss.item()
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                n_updates += 1
                
        # Reset buffer
        self.buffer.reset()
        
        return {
            "loss": total_loss / max(n_updates, 1),
            "policy_loss": total_policy_loss / max(n_updates, 1),
            "value_loss": total_value_loss / max(n_updates, 1),
            "entropy": total_entropy / max(n_updates, 1),
        }
        
    def get_signal(
        self,
        market_features: np.ndarray,
        deterministic: bool = True
    ) -> Dict:
        """
        Get trading signal from market features
        
        Args:
            market_features: Feature vector from FuturesFeatureExtractorV2
            deterministic: Use greedy action selection
            
        Returns:
            Signal dictionary with action, confidence, position size
        """
        # Prepare state
        state = torch.tensor(market_features, dtype=torch.float32, device=self.device)
        if state.dim() == 1:
            state = state.unsqueeze(0)
            
        # Pad/truncate to state_dim
        if state.shape[-1] < self.config.state_dim:
            padding = torch.zeros(
                state.shape[0], 
                self.config.state_dim - state.shape[-1],
                device=self.device
            )
            state = torch.cat([state, padding], dim=-1)
        elif state.shape[-1] > self.config.state_dim:
            state = state[..., :self.config.state_dim]
            
        # Get action
        action, log_prob, value = self.get_action(state.squeeze(0), deterministic)
        
        signal_name, signal_strength = self.action_to_signal[action]
        
        # Confidence from action probability
        with torch.no_grad():
            features = self.get_features(state)
            probs = self.actor(features)
            confidence = probs[0, action].item()
            
        return {
            "signal": signal_name,
            "signal_strength": signal_strength,
            "confidence": confidence,
            "value": value,
            "position_size": abs(signal_strength),
            "action": action,
            "log_prob": log_prob,
        }
        
    def reset_episode(self):
        """Reset trading state for new episode"""
        if self.trading_state.realized_pnl != 0 or self.trading_state.unrealized_pnl != 0:
            total_pnl = self.trading_state.realized_pnl + self.trading_state.unrealized_pnl
            self.episode_rewards.append(total_pnl)
            self.episode_lengths.append(self.trading_state.trades_today)
            
        self.trading_state = TradingState()
        
    def save(self, path: str):
        """Save agent state"""
        save_dict = {
            "config": self.config.__dict__,
            "model_state": self.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "episode_rewards": list(self.episode_rewards),
            "episode_lengths": list(self.episode_lengths),
        }
        torch.save(save_dict, path)
        logger.info(f"Saved RL agent to {path}")
        
    def load(self, path: str):
        """Load agent state"""
        checkpoint = torch.load(path, map_location=self.device)
        self.load_state_dict(checkpoint["model_state"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])
        self.episode_rewards = deque(checkpoint.get("episode_rewards", []), maxlen=100)
        self.episode_lengths = deque(checkpoint.get("episode_lengths", []), maxlen=100)
        logger.info(f"Loaded RL agent from {path}")


def create_rl_agent(
    state_dim: int = 128,
    device: str = None
) -> FuturesRLAgent:
    """Factory function to create RL agent"""
    config = RLConfig(
        state_dim=state_dim,
        device=device or ("cuda" if torch.cuda.is_available() else "cpu")
    )
    return FuturesRLAgent(config)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    
    agent = create_rl_agent(state_dim=96)
    print(f"Agent created on {agent.device}")
    
    # Test signal generation
    dummy_features = np.random.randn(96)
    signal = agent.get_signal(dummy_features)
    print(f"Signal: {signal}")
