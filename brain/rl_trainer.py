"""
QUANT_INDUSTRY_V1 Reinforcement Learning Trainer

Training pipeline for RL agents:
- Walk-forward training
- Episode management
- Evaluation and benchmarking
- Hyperparameter search
- Curriculum learning

Rollback Plan: Delete this file
Tests Required: Training loop, episode rollout
Failure Modes: Early stopping on poor performance
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
import json
import pickle

from .rl_env import TradingEnvironment, EnvConfig, VectorizedTradingEnv
from .rl_agent import PPOAgent, A2CAgent, PPOConfig

logger = logging.getLogger(__name__)


# =============================================================================
# TRAINER CONFIGURATION
# =============================================================================

@dataclass
class TrainerConfig:
    """Configuration for RL trainer."""
    # Training
    total_timesteps: int = 100000
    eval_freq: int = 5000
    eval_episodes: int = 10
    save_freq: int = 10000

    # Walk-forward
    walk_forward: bool = True
    train_window: int = 252 * 2  # 2 years
    test_window: int = 63  # 3 months
    step_size: int = 21  # 1 month

    # Early stopping
    early_stopping: bool = True
    patience: int = 5
    min_improvement: float = 0.01

    # Logging
    log_interval: int = 1000
    verbose: int = 1

    # Paths
    model_dir: str = None
    log_dir: str = None


@dataclass
class TrainingMetrics:
    """Metrics from training."""
    episode_rewards: List[float] = field(default_factory=list)
    episode_lengths: List[int] = field(default_factory=list)
    eval_rewards: List[float] = field(default_factory=list)
    policy_losses: List[float] = field(default_factory=list)
    value_losses: List[float] = field(default_factory=list)
    sharpe_ratios: List[float] = field(default_factory=list)
    max_drawdowns: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode_rewards': self.episode_rewards,
            'episode_lengths': self.episode_lengths,
            'eval_rewards': self.eval_rewards,
            'policy_losses': self.policy_losses,
            'value_losses': self.value_losses,
            'sharpe_ratios': self.sharpe_ratios,
            'max_drawdowns': self.max_drawdowns,
        }


# =============================================================================
# RL TRAINER
# =============================================================================

class RLTrainer:
    """
    Trainer for reinforcement learning agents.

    Handles training loop, evaluation, and model management.
    """

    def __init__(
        self,
        env: TradingEnvironment,
        agent: PPOAgent,
        config: TrainerConfig = None,
        eval_env: TradingEnvironment = None,
    ):
        self.env = env
        self.agent = agent
        self.config = config or TrainerConfig()
        self.eval_env = eval_env

        # Setup directories
        self.model_dir = Path(self.config.model_dir) if self.config.model_dir else Path.home() / "QUANT_INDUSTRY_V1" / "models" / "rl"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        if self.config.log_dir:
            self.log_dir = Path(self.config.log_dir)
            self.log_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.log_dir = None

        # Training state
        self.total_timesteps = 0
        self.total_episodes = 0
        self.metrics = TrainingMetrics()

        # Early stopping
        self.best_eval_reward = float('-inf')
        self.patience_counter = 0

    def train(self) -> TrainingMetrics:
        """
        Train the agent.

        Returns:
            TrainingMetrics with training history
        """
        logger.info(f"Starting training for {self.config.total_timesteps} timesteps")

        obs, info = self.env.reset()

        episode_reward = 0.0
        episode_length = 0

        while self.total_timesteps < self.config.total_timesteps:
            # Get action
            action, log_prob, value = self.agent.get_action(obs)

            # Step environment
            next_obs, reward, terminated, truncated, info = self.env.step(action)
            done = terminated or truncated

            # Store transition
            self.agent.store_transition(obs, action, reward, value, log_prob, done)

            episode_reward += reward
            episode_length += 1
            self.total_timesteps += 1

            # Update agent periodically
            if len(self.agent.buffer.observations) >= self.agent.config.n_steps:
                update_metrics = self.agent.update()

                if update_metrics:
                    self.metrics.policy_losses.append(update_metrics.get('policy_loss', 0))
                    self.metrics.value_losses.append(update_metrics.get('value_loss', 0))

            # Handle episode end
            if done:
                self.metrics.episode_rewards.append(episode_reward)
                self.metrics.episode_lengths.append(episode_length)
                self.total_episodes += 1

                if self.config.verbose >= 1 and self.total_episodes % 10 == 0:
                    logger.info(
                        f"Episode {self.total_episodes}: "
                        f"reward={episode_reward:.2f}, "
                        f"length={episode_length}, "
                        f"total_steps={self.total_timesteps}"
                    )

                obs, info = self.env.reset()
                episode_reward = 0.0
                episode_length = 0
            else:
                obs = next_obs

            # Periodic evaluation
            if self.total_timesteps % self.config.eval_freq == 0:
                eval_results = self.evaluate()
                self.metrics.eval_rewards.append(eval_results['mean_reward'])
                self.metrics.sharpe_ratios.append(eval_results.get('sharpe_ratio', 0))
                self.metrics.max_drawdowns.append(eval_results.get('max_drawdown', 0))

                if self.config.verbose >= 1:
                    logger.info(
                        f"Evaluation at {self.total_timesteps}: "
                        f"mean_reward={eval_results['mean_reward']:.2f}, "
                        f"sharpe={eval_results.get('sharpe_ratio', 0):.2f}"
                    )

                # Early stopping check
                if self.config.early_stopping:
                    if eval_results['mean_reward'] > self.best_eval_reward * (1 + self.config.min_improvement):
                        self.best_eval_reward = eval_results['mean_reward']
                        self.patience_counter = 0
                        self._save_best_model()
                    else:
                        self.patience_counter += 1

                    if self.patience_counter >= self.config.patience:
                        logger.info(f"Early stopping triggered at {self.total_timesteps} timesteps")
                        break

            # Periodic save
            if self.total_timesteps % self.config.save_freq == 0:
                self._save_checkpoint()

        logger.info(f"Training complete: {self.total_timesteps} timesteps, {self.total_episodes} episodes")

        # Save final model
        self._save_checkpoint(final=True)
        self._save_metrics()

        return self.metrics

    def evaluate(
        self,
        n_episodes: int = None,
        deterministic: bool = True
    ) -> Dict[str, float]:
        """
        Evaluate agent performance.

        Args:
            n_episodes: Number of episodes to evaluate
            deterministic: Use deterministic policy

        Returns:
            Dictionary of evaluation metrics
        """
        n_episodes = n_episodes or self.config.eval_episodes
        eval_env = self.eval_env or self.env

        episode_rewards = []
        episode_lengths = []
        episode_returns = []
        episode_drawdowns = []

        for _ in range(n_episodes):
            obs, info = eval_env.reset()
            episode_reward = 0.0
            episode_length = 0
            done = False

            while not done:
                action, _, _ = self.agent.get_action(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, info = eval_env.step(action)
                done = terminated or truncated

                episode_reward += reward
                episode_length += 1

            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
            episode_returns.append(info.get('total_return', 0))
            episode_drawdowns.append(info.get('drawdown', 0))

        # Calculate metrics
        mean_reward = float(np.mean(episode_rewards))
        std_reward = float(np.std(episode_rewards))

        # Sharpe ratio approximation
        if std_reward > 0:
            sharpe_ratio = mean_reward / std_reward
        else:
            sharpe_ratio = 0.0

        return {
            'mean_reward': mean_reward,
            'std_reward': std_reward,
            'mean_length': float(np.mean(episode_lengths)),
            'mean_return': float(np.mean(episode_returns)),
            'max_drawdown': float(np.max(episode_drawdowns)),
            'sharpe_ratio': sharpe_ratio,
            'n_episodes': n_episodes,
        }

    def _save_checkpoint(self, final: bool = False) -> None:
        """Save model checkpoint."""
        if final:
            path = self.model_dir / "final_model.pkl"
        else:
            path = self.model_dir / f"checkpoint_{self.total_timesteps}.pkl"

        self.agent.save(str(path))
        logger.info(f"Checkpoint saved: {path}")

    def _save_best_model(self) -> None:
        """Save best model."""
        path = self.model_dir / "best_model.pkl"
        self.agent.save(str(path))
        logger.info(f"Best model saved: {path}")

    def _save_metrics(self) -> None:
        """Save training metrics."""
        if self.log_dir:
            path = self.log_dir / "training_metrics.json"
        else:
            path = self.model_dir / "training_metrics.json"

        with open(path, 'w') as f:
            json.dump(self.metrics.to_dict(), f, indent=2)

        logger.info(f"Metrics saved: {path}")


# =============================================================================
# WALK-FORWARD TRAINER
# =============================================================================

class WalkForwardRLTrainer:
    """
    Walk-forward training for RL agents.

    Trains on rolling windows and tests on out-of-sample data.
    """

    def __init__(
        self,
        prices: np.ndarray,
        features: np.ndarray = None,
        agent_config: PPOConfig = None,
        env_config: EnvConfig = None,
        trainer_config: TrainerConfig = None,
    ):
        self.prices = prices
        self.features = features
        self.agent_config = agent_config or PPOConfig()
        self.env_config = env_config or EnvConfig()
        self.trainer_config = trainer_config or TrainerConfig()

        self.n_samples = len(prices)

        # Results
        self.fold_results: List[Dict[str, Any]] = []
        self.all_predictions: List[np.ndarray] = []
        self.all_returns: List[float] = []

    def train(self) -> Dict[str, Any]:
        """
        Run walk-forward training.

        Returns:
            Aggregated results from all folds
        """
        train_window = self.trainer_config.train_window
        test_window = self.trainer_config.test_window
        step_size = self.trainer_config.step_size

        fold = 0
        train_start = 0

        while train_start + train_window + test_window <= self.n_samples:
            train_end = train_start + train_window
            test_start = train_end
            test_end = test_start + test_window

            logger.info(f"Fold {fold}: train=[{train_start}:{train_end}], test=[{test_start}:{test_end}]")

            # Get data slices
            train_prices = self.prices[train_start:train_end]
            test_prices = self.prices[test_start:test_end]

            train_features = None
            test_features = None
            if self.features is not None:
                train_features = self.features[train_start:train_end]
                test_features = self.features[test_start:test_end]

            # Train on this fold
            fold_result = self._train_fold(
                train_prices, test_prices,
                train_features, test_features,
                fold
            )

            self.fold_results.append(fold_result)

            # Move window
            train_start += step_size
            fold += 1

        # Aggregate results
        return self._aggregate_results()

    def _train_fold(
        self,
        train_prices: np.ndarray,
        test_prices: np.ndarray,
        train_features: np.ndarray = None,
        test_features: np.ndarray = None,
        fold: int = 0
    ) -> Dict[str, Any]:
        """Train on a single fold."""
        # Create environments
        train_env = TradingEnvironment(
            prices=train_prices,
            features=train_features,
            config=self.env_config,
        )

        test_env = TradingEnvironment(
            prices=test_prices,
            features=test_features,
            config=self.env_config,
        )

        # Create agent
        agent = PPOAgent(
            obs_dim=train_env.observation_dim,
            action_dim=train_env.n_assets,
            config=self.agent_config,
            continuous=True,
        )

        # Create trainer with reduced timesteps for each fold
        fold_config = TrainerConfig(
            total_timesteps=self.trainer_config.total_timesteps // max(1, self.n_samples // self.trainer_config.step_size),
            eval_freq=self.trainer_config.eval_freq,
            eval_episodes=5,
            early_stopping=True,
            patience=3,
            verbose=0,
        )

        trainer = RLTrainer(
            env=train_env,
            agent=agent,
            config=fold_config,
            eval_env=test_env,
        )

        # Train
        metrics = trainer.train()

        # Evaluate on test set
        eval_results = trainer.evaluate(n_episodes=10)

        # Get predictions on test set
        predictions = self._get_predictions(agent, test_env)
        self.all_predictions.append(predictions)

        # Calculate test returns
        test_returns = self._calculate_test_returns(predictions, test_prices)
        self.all_returns.extend(test_returns)

        return {
            'fold': fold,
            'train_episodes': trainer.total_episodes,
            'train_reward': float(np.mean(metrics.episode_rewards[-10:])) if metrics.episode_rewards else 0,
            'test_reward': eval_results['mean_reward'],
            'test_sharpe': eval_results['sharpe_ratio'],
            'test_drawdown': eval_results['max_drawdown'],
            'test_return': eval_results['mean_return'],
        }

    def _get_predictions(
        self,
        agent: PPOAgent,
        env: TradingEnvironment
    ) -> np.ndarray:
        """Get agent predictions on environment."""
        obs, _ = env.reset()
        predictions = []

        done = False
        while not done:
            action, _, _ = agent.get_action(obs, deterministic=True)
            predictions.append(action)

            obs, _, terminated, truncated, _ = env.step(action)
            done = terminated or truncated

        return np.array(predictions)

    def _calculate_test_returns(
        self,
        predictions: np.ndarray,
        prices: np.ndarray
    ) -> List[float]:
        """Calculate returns from predictions."""
        if len(predictions) == 0:
            return []

        # Calculate price returns
        if prices.ndim == 1:
            prices = prices.reshape(-1, 1)

        returns = np.zeros(len(prices) - 1)
        returns = (prices[1:, 0] - prices[:-1, 0]) / prices[:-1, 0]

        # Strategy returns = prediction * market return
        # Align lengths
        min_len = min(len(predictions), len(returns))
        strategy_returns = predictions[:min_len, 0] * returns[:min_len]

        return strategy_returns.tolist()

    def _aggregate_results(self) -> Dict[str, Any]:
        """Aggregate results from all folds."""
        if not self.fold_results:
            return {}

        return {
            'n_folds': len(self.fold_results),
            'mean_test_reward': float(np.mean([r['test_reward'] for r in self.fold_results])),
            'mean_test_sharpe': float(np.mean([r['test_sharpe'] for r in self.fold_results])),
            'mean_test_drawdown': float(np.mean([r['test_drawdown'] for r in self.fold_results])),
            'mean_test_return': float(np.mean([r['test_return'] for r in self.fold_results])),
            'total_strategy_return': float(np.sum(self.all_returns)) if self.all_returns else 0,
            'strategy_sharpe': self._calculate_sharpe(self.all_returns),
            'fold_results': self.fold_results,
        }

    def _calculate_sharpe(self, returns: List[float], rf: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0

        returns_arr = np.array(returns)
        mean_ret = np.mean(returns_arr)
        std_ret = np.std(returns_arr)

        if std_ret < 1e-8:
            return 0.0

        daily_rf = rf / 252
        return float(np.sqrt(252) * (mean_ret - daily_rf) / std_ret)


# =============================================================================
# CURRICULUM LEARNING
# =============================================================================

class CurriculumScheduler:
    """
    Curriculum learning scheduler for RL.

    Gradually increases environment difficulty.
    """

    def __init__(
        self,
        stages: List[Dict[str, Any]] = None,
        progress_threshold: float = 0.8,
    ):
        self.stages = stages or self._default_stages()
        self.current_stage = 0
        self.progress_threshold = progress_threshold

        self.stage_metrics: List[Dict[str, float]] = []

    def _default_stages(self) -> List[Dict[str, Any]]:
        """Default curriculum stages."""
        return [
            {
                'name': 'basic',
                'description': 'Low volatility, no costs',
                'config': {
                    'transaction_cost_pct': 0.0,
                    'slippage_pct': 0.0,
                    'max_drawdown_limit': 0.5,
                }
            },
            {
                'name': 'intermediate',
                'description': 'Normal volatility, low costs',
                'config': {
                    'transaction_cost_pct': 0.0005,
                    'slippage_pct': 0.0002,
                    'max_drawdown_limit': 0.3,
                }
            },
            {
                'name': 'advanced',
                'description': 'High volatility, realistic costs',
                'config': {
                    'transaction_cost_pct': 0.001,
                    'slippage_pct': 0.0005,
                    'max_drawdown_limit': 0.2,
                }
            },
            {
                'name': 'expert',
                'description': 'Full difficulty',
                'config': {
                    'transaction_cost_pct': 0.001,
                    'slippage_pct': 0.001,
                    'max_drawdown_limit': 0.15,
                }
            },
        ]

    def get_current_config(self) -> Dict[str, Any]:
        """Get configuration for current stage."""
        if self.current_stage >= len(self.stages):
            return self.stages[-1]['config']
        return self.stages[self.current_stage]['config']

    def get_current_stage_name(self) -> str:
        """Get current stage name."""
        if self.current_stage >= len(self.stages):
            return self.stages[-1]['name']
        return self.stages[self.current_stage]['name']

    def update(self, metrics: Dict[str, float]) -> bool:
        """
        Update curriculum based on metrics.

        Args:
            metrics: Current training metrics

        Returns:
            True if advanced to next stage
        """
        self.stage_metrics.append(metrics)

        # Check if should advance
        success_rate = metrics.get('success_rate', 0)
        mean_reward = metrics.get('mean_reward', 0)

        # Simple advancement criteria
        if success_rate >= self.progress_threshold or mean_reward > 0:
            if self.current_stage < len(self.stages) - 1:
                self.current_stage += 1
                logger.info(f"Advanced to curriculum stage: {self.get_current_stage_name()}")
                return True

        return False

    def reset(self) -> None:
        """Reset to first stage."""
        self.current_stage = 0
        self.stage_metrics = []
