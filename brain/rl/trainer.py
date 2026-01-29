"""
RL Training Pipeline
====================
Complete training loop for trading agents.
"""

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Tuple
from dataclasses import dataclass
import logging
import json
import time

from .env import TradingEnv, TradingEnvConfig
from .agent import PPOAgent, A2CAgent, DQNAgent, AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class TrainerConfig:
    """Training configuration."""
    # Training
    total_timesteps: int = 1_000_000
    n_envs: int = 1  # Parallel environments
    rollout_length: int = 2048  # Steps before update (PPO/A2C)
    
    # Evaluation
    eval_freq: int = 10_000
    n_eval_episodes: int = 10
    
    # Logging
    log_freq: int = 1000
    save_freq: int = 50_000
    log_dir: str = "runs"
    checkpoint_dir: str = "checkpoints/rl"
    
    # Early stopping
    patience: int = 10  # Eval rounds without improvement
    min_improvement: float = 0.01


class RLTrainer:
    """
    Complete RL training pipeline.
    
    Features:
    - Multiple agent types (PPO, A2C, DQN)
    - TensorBoard logging
    - Checkpointing
    - Evaluation during training
    - Early stopping
    - Curriculum learning support
    """
    
    def __init__(
        self,
        env: TradingEnv,
        agent_type: str = "ppo",
        agent_config: Optional[AgentConfig] = None,
        trainer_config: Optional[TrainerConfig] = None,
        eval_env: Optional[TradingEnv] = None,
    ):
        self.env = env
        self.eval_env = eval_env or env
        self.agent_config = agent_config or AgentConfig()
        self.config = trainer_config or TrainerConfig()
        
        # Get dimensions
        obs_dim = env.observation_space.shape[0]
        if hasattr(env.action_space, 'n'):
            action_dim = env.action_space.n
            continuous = False
        else:
            action_dim = env.action_space.shape[0]
            continuous = True
        
        # Create agent
        if agent_type.lower() == "ppo":
            self.agent = PPOAgent(obs_dim, action_dim, self.agent_config, continuous)
        elif agent_type.lower() == "a2c":
            self.agent = A2CAgent(obs_dim, action_dim, self.agent_config, continuous)
        elif agent_type.lower() == "dqn":
            assert not continuous, "DQN requires discrete actions"
            self.agent = DQNAgent(obs_dim, action_dim, self.agent_config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        self.agent_type = agent_type.lower()
        
        # Setup logging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = Path(self.config.log_dir) / f"{agent_type}_{timestamp}"
        self.writer = SummaryWriter(self.log_path)
        
        # Checkpointing
        self.ckpt_dir = Path(self.config.checkpoint_dir)
        self.ckpt_dir.mkdir(parents=True, exist_ok=True)
        
        # Training state
        self.total_steps = 0
        self.episodes = 0
        self.best_eval_return = -np.inf
        self.patience_counter = 0
        
        logger.info(f"RLTrainer initialized: {agent_type}")
        logger.info(f"Observation dim: {obs_dim}, Action dim: {action_dim}")
        logger.info(f"TensorBoard: {self.log_path}")
    
    def train(
        self,
        callbacks: Optional[List[Callable]] = None
    ) -> Dict[str, Any]:
        """
        Train the agent.
        
        Args:
            callbacks: Optional callbacks after each update
            
        Returns:
            Training statistics
        """
        start_time = time.time()
        episode_rewards = []
        episode_lengths = []
        
        obs, _ = self.env.reset()
        episode_reward = 0
        episode_length = 0
        
        logger.info(f"Starting training for {self.config.total_timesteps:,} steps")
        
        while self.total_steps < self.config.total_timesteps:
            # Collect rollout
            if self.agent_type in ["ppo", "a2c"]:
                stats = self._collect_rollout(obs, episode_reward, episode_length)
                obs = stats['obs']
                episode_reward = stats['episode_reward']
                episode_length = stats['episode_length']
                episode_rewards.extend(stats.get('completed_rewards', []))
                episode_lengths.extend(stats.get('completed_lengths', []))
                
                # Update policy
                update_stats = self.agent.update()
                
            else:  # DQN
                stats = self._collect_dqn_step(obs)
                obs = stats['obs']
                if stats['done']:
                    episode_rewards.append(stats['episode_reward'])
                    episode_lengths.append(stats['episode_length'])
                    episode_reward = 0
                    episode_length = 0
                else:
                    episode_reward = stats['episode_reward']
                    episode_length = stats['episode_length']
                
                update_stats = self.agent.update()
            
            # Logging
            if self.total_steps % self.config.log_freq == 0 and episode_rewards:
                self._log_training(episode_rewards[-100:], episode_lengths[-100:], update_stats)
            
            # Evaluation
            if self.total_steps % self.config.eval_freq == 0:
                eval_return = self._evaluate()
                
                # Early stopping check
                if eval_return > self.best_eval_return + self.config.min_improvement:
                    self.best_eval_return = eval_return
                    self.patience_counter = 0
                    self._save_checkpoint("best")
                else:
                    self.patience_counter += 1
                
                if self.patience_counter >= self.config.patience:
                    logger.info(f"Early stopping at step {self.total_steps}")
                    break
            
            # Checkpointing
            if self.total_steps % self.config.save_freq == 0:
                self._save_checkpoint(f"step_{self.total_steps}")
            
            # Callbacks
            if callbacks:
                for cb in callbacks:
                    cb(self, self.total_steps, update_stats)
        
        # Final evaluation
        final_return = self._evaluate()
        
        # Close
        self.writer.close()
        
        total_time = time.time() - start_time
        
        results = {
            'total_steps': self.total_steps,
            'total_episodes': len(episode_rewards),
            'total_time': total_time,
            'steps_per_second': self.total_steps / total_time,
            'final_eval_return': final_return,
            'best_eval_return': self.best_eval_return,
            'mean_episode_reward': np.mean(episode_rewards[-100:]) if episode_rewards else 0,
        }
        
        logger.info(f"Training complete: {results}")
        
        return results
    
    def _collect_rollout(
        self,
        obs: np.ndarray,
        episode_reward: float,
        episode_length: int
    ) -> Dict[str, Any]:
        """Collect rollout for on-policy algorithms."""
        completed_rewards = []
        completed_lengths = []
        
        for _ in range(self.config.rollout_length):
            # Get action
            action, log_prob, value = self.agent.select_action(obs)
            
            # Step environment
            next_obs, reward, terminated, truncated, info = self.env.step(action)
            done = terminated or truncated
            
            # Store transition
            self.agent.store_transition(obs, action, reward, done, log_prob, value)
            
            episode_reward += reward
            episode_length += 1
            self.total_steps += 1
            
            if done:
                completed_rewards.append(episode_reward)
                completed_lengths.append(episode_length)
                self.episodes += 1
                episode_reward = 0
                episode_length = 0
                next_obs, _ = self.env.reset()
            
            obs = next_obs
        
        return {
            'obs': obs,
            'episode_reward': episode_reward,
            'episode_length': episode_length,
            'completed_rewards': completed_rewards,
            'completed_lengths': completed_lengths,
        }
    
    def _collect_dqn_step(self, obs: np.ndarray) -> Dict[str, Any]:
        """Collect single step for DQN."""
        action = self.agent.select_action(obs)
        next_obs, reward, terminated, truncated, info = self.env.step(action)
        done = terminated or truncated
        
        self.agent.store_transition(obs, action, reward, next_obs, done)
        self.total_steps += 1
        
        episode_reward = info.get('episode_reward', reward)
        episode_length = info.get('episode_length', 1)
        
        if done:
            next_obs, _ = self.env.reset()
            self.episodes += 1
        
        return {
            'obs': next_obs,
            'done': done,
            'episode_reward': episode_reward,
            'episode_length': episode_length,
        }
    
    def _evaluate(self) -> float:
        """Evaluate agent."""
        returns = []
        
        for _ in range(self.config.n_eval_episodes):
            obs, _ = self.eval_env.reset()
            episode_return = 0
            done = False
            
            while not done:
                action = self.agent.select_action(obs, deterministic=True)
                if isinstance(action, tuple):
                    action = action[0]
                obs, reward, terminated, truncated, _ = self.eval_env.step(action)
                episode_return += reward
                done = terminated or truncated
            
            returns.append(episode_return)
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        self.writer.add_scalar('Eval/mean_return', mean_return, self.total_steps)
        self.writer.add_scalar('Eval/std_return', std_return, self.total_steps)
        
        logger.info(f"Eval @ {self.total_steps}: {mean_return:.2f} ± {std_return:.2f}")
        
        return mean_return
    
    def _log_training(
        self,
        rewards: List[float],
        lengths: List[int],
        update_stats: Dict[str, float]
    ):
        """Log training metrics."""
        if rewards:
            self.writer.add_scalar('Train/mean_reward', np.mean(rewards), self.total_steps)
            self.writer.add_scalar('Train/mean_length', np.mean(lengths), self.total_steps)
        
        for key, value in update_stats.items():
            self.writer.add_scalar(f'Train/{key}', value, self.total_steps)
        
        self.writer.add_scalar('Train/episodes', self.episodes, self.total_steps)
    
    def _save_checkpoint(self, name: str):
        """Save checkpoint."""
        path = self.ckpt_dir / f"{self.agent_type}_{name}.pt"
        self.agent.save(str(path))
        
        # Save training state
        state = {
            'total_steps': self.total_steps,
            'episodes': self.episodes,
            'best_eval_return': self.best_eval_return,
        }
        state_path = self.ckpt_dir / f"{self.agent_type}_{name}_state.json"
        with open(state_path, 'w') as f:
            json.dump(state, f)
        
        logger.info(f"Saved checkpoint: {path}")
    
    def load_checkpoint(self, name: str):
        """Load checkpoint."""
        path = self.ckpt_dir / f"{self.agent_type}_{name}.pt"
        self.agent.load(str(path))
        
        state_path = self.ckpt_dir / f"{self.agent_type}_{name}_state.json"
        if state_path.exists():
            with open(state_path, 'r') as f:
                state = json.load(f)
            self.total_steps = state['total_steps']
            self.episodes = state['episodes']
            self.best_eval_return = state['best_eval_return']
        
        logger.info(f"Loaded checkpoint: {path}")


def train_trading_agent(
    data: np.ndarray,
    agent_type: str = "ppo",
    total_timesteps: int = 500_000,
    eval_data: Optional[np.ndarray] = None,
    **kwargs
) -> Tuple[Any, Dict]:
    """
    Convenience function to train a trading agent.
    
    Args:
        data: Training price data [timesteps, features]
        agent_type: "ppo", "a2c", or "dqn"
        total_timesteps: Total training steps
        eval_data: Optional separate evaluation data
        **kwargs: Additional config overrides
        
    Returns:
        Trained agent and training results
    """
    # Create environments
    env_config = TradingEnvConfig(**{k: v for k, v in kwargs.items() if hasattr(TradingEnvConfig, k)})
    env = TradingEnv(data, config=env_config)
    
    eval_env = None
    if eval_data is not None:
        eval_env = TradingEnv(eval_data, config=env_config)
    
    # Create trainer config
    trainer_config = TrainerConfig(
        total_timesteps=total_timesteps,
        **{k: v for k, v in kwargs.items() if hasattr(TrainerConfig, k)}
    )
    
    # Create agent config
    agent_config = AgentConfig(**{k: v for k, v in kwargs.items() if hasattr(AgentConfig, k)})
    
    # Create trainer
    trainer = RLTrainer(
        env=env,
        agent_type=agent_type,
        agent_config=agent_config,
        trainer_config=trainer_config,
        eval_env=eval_env,
    )
    
    # Train
    results = trainer.train()
    
    return trainer.agent, results
