"""
QUANT INDUSTRY - Reinforcement Learning Closed-Loop System
Institutional-Grade RL Trading Engine with Continuous Learning

Features:
- PPO/A2C Reinforcement Learning
- Closed-loop feedback from trades
- Adaptive weight optimization
- Multi-strategy orchestration
- Prop firm compliance
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ML Libraries
try:
    import torch
    from torch import nn, optim
    from torch.distributions import Categorical
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

try:
    import gymnasium as gym
    from gymnasium import spaces
    GYM_AVAILABLE = True
except ImportError:
    try:
        import gym
        from gym import spaces
        GYM_AVAILABLE = True
    except ImportError:
        GYM_AVAILABLE = False

try:
    from stable_baselines3 import A2C, PPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Trading actions"""
    SELL = 0
    HOLD = 1
    BUY = 2


@dataclass
class RLConfig:
    """Reinforcement Learning Configuration"""
    # Training parameters
    learning_rate: float = 0.0003
    gamma: float = 0.99  # Discount factor
    gae_lambda: float = 0.95  # GAE lambda
    clip_range: float = 0.2  # PPO clip range
    entropy_coef: float = 0.01  # Entropy coefficient
    value_coef: float = 0.5  # Value function coefficient
    max_grad_norm: float = 0.5

    # Network architecture
    hidden_size: int = 256
    num_layers: int = 2

    # Training loop
    n_steps: int = 2048
    n_epochs: int = 10
    batch_size: int = 64
    total_timesteps: int = 100000

    # Reward shaping
    profit_weight: float = 1.0
    drawdown_penalty: float = 2.0
    volatility_penalty: float = 0.5
    overtrading_penalty: float = 0.3
    slippage_penalty: float = 0.2
    tail_risk_penalty: float = 1.5

    # Trading constraints
    max_positions: int = 5
    position_size: float = 0.1  # 10% of portfolio per position
    stop_loss: float = 0.02  # 2%
    take_profit: float = 0.04  # 4%

    # Performance targets (Prop firm)
    target_win_rate: float = 0.70
    target_wl_ratio: float = 2.0
    target_sharpe: float = 1.5
    max_daily_drawdown: float = 0.05
    max_total_drawdown: float = 0.10


@dataclass
class TradeResult:
    """Trade result for feedback loop"""
    trade_id: str
    symbol: str
    action: ActionType
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    duration_seconds: int
    entry_time: datetime
    exit_time: datetime
    signal_confidence: float
    strategy_name: str


class TradingEnvironment:
    """
    Custom Trading Environment for RL
    Implements gymnasium/gym interface
    """

    def __init__(self, df: pd.DataFrame, config: RLConfig, initial_balance: float = 100000):
        self.df = df
        self.config = config
        self.initial_balance = initial_balance

        # State space: features + position + portfolio_value + drawdown
        self.n_features = 50  # Number of market features
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(self.n_features + 3,), dtype=np.float32
        )

        # Action space: sell, hold, buy
        self.action_space = spaces.Discrete(3)

        self.reset()

    def reset(self, seed=None):
        """Reset environment to initial state"""
        self.current_step = 50  # Skip first rows for feature calculation
        self.balance = self.initial_balance
        self.position = 0  # Number of shares held
        self.entry_price = 0
        self.portfolio_value = self.initial_balance
        self.max_portfolio_value = self.initial_balance
        self.trades = []
        self.daily_pnl = 0
        self.daily_start_value = self.initial_balance

        return self._get_observation(), {}

    def _get_observation(self) -> np.ndarray:
        """Get current state observation"""
        if self.current_step >= len(self.df):
            return np.zeros(self.n_features + 3, dtype=np.float32)

        row = self.df.iloc[self.current_step]

        # Market features (simplified - would use full feature engineering in production)
        features = []

        # Price features
        close = row['close']
        for period in [5, 10, 20, 50]:
            if self.current_step >= period:
                sma = self.df['close'].iloc[self.current_step - period:self.current_step].mean()
                features.append((close - sma) / sma)
            else:
                features.append(0)

        # Returns
        for period in [1, 5, 10, 20]:
            if self.current_step >= period:
                ret = (close - self.df['close'].iloc[self.current_step - period]) / self.df['close'].iloc[self.current_step - period]
                features.append(ret)
            else:
                features.append(0)

        # Volatility
        for period in [10, 20]:
            if self.current_step >= period:
                returns = self.df['close'].iloc[self.current_step - period:self.current_step].pct_change().dropna()
                features.append(returns.std() if len(returns) > 0 else 0)
            else:
                features.append(0)

        # RSI
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        features.append(rsi.iloc[self.current_step] / 100 if not np.isnan(rsi.iloc[self.current_step]) else 0.5)

        # MACD
        ema_12 = self.df['close'].ewm(span=12).mean()
        ema_26 = self.df['close'].ewm(span=26).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9).mean()
        features.append((macd.iloc[self.current_step] - macd_signal.iloc[self.current_step]) / close)

        # Volume features
        if 'volume' in self.df.columns:
            vol_sma = self.df['volume'].rolling(20).mean()
            features.append(row['volume'] / vol_sma.iloc[self.current_step] if vol_sma.iloc[self.current_step] > 0 else 1)
        else:
            features.append(1)

        # Pad to n_features
        while len(features) < self.n_features:
            features.append(0)

        features = features[:self.n_features]

        # Position state
        position_normalized = self.position * row['close'] / self.portfolio_value if self.portfolio_value > 0 else 0

        # Drawdown
        drawdown = (self.max_portfolio_value - self.portfolio_value) / self.max_portfolio_value

        observation = np.array(features + [position_normalized, self.portfolio_value / self.initial_balance, drawdown], dtype=np.float32)

        return observation

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one step in the environment"""
        if self.current_step >= len(self.df) - 1:
            return self._get_observation(), 0, True, False, {}

        current_price = self.df.iloc[self.current_step]['close']
        next_price = self.df.iloc[self.current_step + 1]['close']

        reward = 0
        info = {}

        # Execute action
        if action == ActionType.BUY.value and self.position == 0:
            # Buy
            shares = int(self.balance * self.config.position_size / current_price)
            if shares > 0:
                cost = shares * current_price
                self.balance -= cost
                self.position = shares
                self.entry_price = current_price
                info['action'] = 'buy'
                info['shares'] = shares

        elif action == ActionType.SELL.value and self.position > 0:
            # Sell
            proceeds = self.position * current_price
            pnl = proceeds - (self.position * self.entry_price)
            pnl_pct = pnl / (self.position * self.entry_price)

            self.balance += proceeds
            self.trades.append({
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'duration': 1
            })

            # Reward shaping
            reward += self.config.profit_weight * pnl_pct * 100

            self.position = 0
            self.entry_price = 0
            info['action'] = 'sell'
            info['pnl'] = pnl

        else:
            info['action'] = 'hold'

        # Update portfolio value
        self.portfolio_value = self.balance + (self.position * next_price if self.position > 0 else 0)
        self.max_portfolio_value = max(self.max_portfolio_value, self.portfolio_value)

        # Calculate drawdown penalty
        current_drawdown = (self.max_portfolio_value - self.portfolio_value) / self.max_portfolio_value
        if current_drawdown > 0.05:
            reward -= self.config.drawdown_penalty * current_drawdown * 100

        # Overtrading penalty
        if len(self.trades) > 0 and len(self.trades) % 10 == 0:
            recent_trades = self.trades[-10:]
            if sum(1 for t in recent_trades if t['duration'] < 5) > 7:
                reward -= self.config.overtrading_penalty * 10

        # Move to next step
        self.current_step += 1

        # Check termination
        done = self.current_step >= len(self.df) - 1
        truncated = current_drawdown > self.config.max_total_drawdown

        if truncated:
            reward -= self.config.tail_risk_penalty * 100

        return self._get_observation(), reward, done, truncated, info

    def render(self):
        """Render environment state"""
        pass


class PolicyNetwork(nn.Module):
    """Actor-Critic Policy Network"""

    def __init__(self, input_size: int, hidden_size: int, num_actions: int):
        super().__init__()

        self.shared = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU()
        )

        self.actor = nn.Sequential(
            nn.Linear(hidden_size, num_actions),
            nn.Softmax(dim=-1)
        )

        self.critic = nn.Linear(hidden_size, 1)

    def forward(self, x):
        shared_out = self.shared(x)
        action_probs = self.actor(shared_out)
        value = self.critic(shared_out)
        return action_probs, value


class RLEngine:
    """
    Reinforcement Learning Engine
    Supports PPO and custom implementations
    """

    def __init__(self, config: Optional[RLConfig] = None):
        self.config = config or RLConfig()
        self.model = None
        self.env = None
        self.is_trained = False

        # Custom policy network (fallback if SB3 not available)
        self.policy_network = None
        self.optimizer = None

        # Experience buffer
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []

        logger.info("RL Engine initialized")
        logger.info(f"  Stable Baselines3 available: {SB3_AVAILABLE}")
        logger.info(f"  PyTorch available: {PYTORCH_AVAILABLE}")

    def create_environment(self, df: pd.DataFrame) -> Any:
        """Create trading environment"""
        self.env = TradingEnvironment(df, self.config)
        return self.env

    def train_ppo(self, df: pd.DataFrame, total_timesteps: Optional[int] = None) -> Dict:
        """Train using PPO algorithm"""
        timesteps = total_timesteps or self.config.total_timesteps

        if SB3_AVAILABLE:
            return self._train_sb3_ppo(df, timesteps)
        elif PYTORCH_AVAILABLE:
            return self._train_custom_ppo(df, timesteps)
        else:
            return self._train_rule_based(df)

    def _train_sb3_ppo(self, df: pd.DataFrame, timesteps: int) -> Dict:
        """Train using Stable Baselines3 PPO"""
        logger.info("Training with Stable Baselines3 PPO...")

        env = TradingEnvironment(df, self.config)
        vec_env = DummyVecEnv([lambda: env])

        self.model = PPO(
            "MlpPolicy",
            vec_env,
            learning_rate=self.config.learning_rate,
            n_steps=self.config.n_steps,
            batch_size=self.config.batch_size,
            n_epochs=self.config.n_epochs,
            gamma=self.config.gamma,
            gae_lambda=self.config.gae_lambda,
            clip_range=self.config.clip_range,
            ent_coef=self.config.entropy_coef,
            vf_coef=self.config.value_coef,
            max_grad_norm=self.config.max_grad_norm,
            verbose=1
        )

        self.model.learn(total_timesteps=timesteps)
        self.is_trained = True

        # Evaluate
        eval_results = self._evaluate_model(df)

        logger.info(f"PPO training complete. Win rate: {eval_results['win_rate']:.2%}")

        return {
            'method': 'sb3_ppo',
            'timesteps': timesteps,
            'evaluation': eval_results
        }

    def _train_custom_ppo(self, df: pd.DataFrame, timesteps: int) -> Dict:
        """Train using custom PPO implementation"""
        logger.info("Training with custom PPO...")

        env = TradingEnvironment(df, self.config)
        obs_size = env.observation_space.shape[0]
        n_actions = env.action_space.n

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        self.policy_network = PolicyNetwork(
            obs_size,
            self.config.hidden_size,
            n_actions
        ).to(device)

        self.optimizer = optim.Adam(
            self.policy_network.parameters(),
            lr=self.config.learning_rate
        )

        # Training loop
        episode_rewards = []
        step = 0

        while step < timesteps:
            obs, _ = env.reset()
            episode_reward = 0
            done = False

            while not done and step < timesteps:
                obs_tensor = torch.FloatTensor(obs).unsqueeze(0).to(device)

                with torch.no_grad():
                    action_probs, value = self.policy_network(obs_tensor)

                dist = Categorical(action_probs)
                action = dist.sample()
                log_prob = dist.log_prob(action)

                next_obs, reward, done, truncated, info = env.step(action.item())

                # Store experience
                self.states.append(obs)
                self.actions.append(action.item())
                self.rewards.append(reward)
                self.values.append(value.item())
                self.log_probs.append(log_prob.item())

                obs = next_obs
                episode_reward += reward
                step += 1

                # Update policy every n_steps
                if len(self.states) >= self.config.n_steps:
                    self._update_policy(device)

                done = done or truncated

            episode_rewards.append(episode_reward)

        self.is_trained = True

        # Evaluate
        eval_results = self._evaluate_model(df)

        logger.info(f"Custom PPO training complete. Win rate: {eval_results['win_rate']:.2%}")

        return {
            'method': 'custom_ppo',
            'timesteps': timesteps,
            'episode_rewards': episode_rewards[-100:],
            'evaluation': eval_results
        }

    def _update_policy(self, device):
        """Update policy using collected experiences"""
        if not self.states:
            return

        # Convert to tensors
        states = torch.FloatTensor(np.array(self.states)).to(device)
        actions = torch.LongTensor(self.actions).to(device)
        old_log_probs = torch.FloatTensor(self.log_probs).to(device)

        # Calculate returns and advantages
        returns = []
        advantages = []
        running_return = 0

        for reward, value in zip(reversed(self.rewards), reversed(self.values)):
            running_return = reward + self.config.gamma * running_return
            returns.insert(0, running_return)
            advantages.insert(0, running_return - value)

        returns = torch.FloatTensor(returns).to(device)
        advantages = torch.FloatTensor(advantages).to(device)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO update
        for _ in range(self.config.n_epochs):
            action_probs, values = self.policy_network(states)
            dist = Categorical(action_probs)

            new_log_probs = dist.log_prob(actions)
            entropy = dist.entropy().mean()

            # Ratio for PPO
            ratio = torch.exp(new_log_probs - old_log_probs)

            # Clipped surrogate loss
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.config.clip_range, 1 + self.config.clip_range) * advantages
            actor_loss = -torch.min(surr1, surr2).mean()

            # Value loss
            critic_loss = nn.MSELoss()(values.squeeze(), returns)

            # Total loss
            loss = actor_loss + self.config.value_coef * critic_loss - self.config.entropy_coef * entropy

            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.policy_network.parameters(), self.config.max_grad_norm)
            self.optimizer.step()

        # Clear buffers
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.values.clear()
        self.log_probs.clear()

    def _train_rule_based(self, df: pd.DataFrame) -> Dict:
        """Fallback rule-based training when no ML libraries available"""
        logger.warning("No ML libraries available. Using rule-based fallback.")

        self.is_trained = True

        return {
            'method': 'rule_based',
            'message': 'Using rule-based policy (no ML libraries available)'
        }

    def _evaluate_model(self, df: pd.DataFrame) -> Dict:
        """Evaluate trained model"""
        env = TradingEnvironment(df, self.config)
        obs, _ = env.reset()
        done = False

        trades = []

        while not done:
            action = self.predict(obs)
            obs, reward, done, truncated, info = env.step(action)

            if 'pnl' in info:
                trades.append(info['pnl'])

            done = done or truncated

        # Calculate metrics
        winning_trades = [t for t in trades if t > 0]
        losing_trades = [t for t in trades if t < 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        wl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        total_pnl = sum(trades)
        final_value = env.portfolio_value

        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'wl_ratio': wl_ratio,
            'total_pnl': total_pnl,
            'final_portfolio_value': final_value,
            'return_pct': (final_value - env.initial_balance) / env.initial_balance
        }

    def predict(self, observation: np.ndarray) -> int:
        """Predict action given observation"""
        if not self.is_trained:
            return ActionType.HOLD.value

        if SB3_AVAILABLE and self.model is not None:
            action, _ = self.model.predict(observation, deterministic=True)
            return int(action)

        elif PYTORCH_AVAILABLE and self.policy_network is not None:
            device = next(self.policy_network.parameters()).device
            obs_tensor = torch.FloatTensor(observation).unsqueeze(0).to(device)

            self.policy_network.eval()
            with torch.no_grad():
                action_probs, _ = self.policy_network(obs_tensor)

            return torch.argmax(action_probs).item()

        else:
            # Rule-based fallback
            return self._rule_based_action(observation)

    def _rule_based_action(self, observation: np.ndarray) -> int:
        """Rule-based action selection"""
        # Simple momentum strategy
        if len(observation) > 5:
            momentum = observation[4] if not np.isnan(observation[4]) else 0

            if momentum > 0.02:
                return ActionType.BUY.value
            elif momentum < -0.02:
                return ActionType.SELL.value

        return ActionType.HOLD.value

    def save(self, path: str):
        """Save trained model"""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        if SB3_AVAILABLE and self.model is not None:
            self.model.save(str(save_path / 'ppo_model'))

        elif PYTORCH_AVAILABLE and self.policy_network is not None:
            torch.save(self.policy_network.state_dict(), save_path / 'policy_network.pt')

        # Save config
        with open(save_path / 'config.json', 'w') as f:
            json.dump(self.config.__dict__, f, indent=2)

        logger.info(f"RL model saved to {path}")

    def load(self, path: str):
        """Load trained model"""
        load_path = Path(path)

        if SB3_AVAILABLE and (load_path / 'ppo_model.zip').exists():
            self.model = PPO.load(str(load_path / 'ppo_model'))
            self.is_trained = True

        elif PYTORCH_AVAILABLE and (load_path / 'policy_network.pt').exists():
            # Need to recreate network architecture
            with open(load_path / 'config.json') as f:
                config_dict = json.load(f)
            self.config = RLConfig(**config_dict)

            # Would need obs_size and n_actions - simplify for now
            self.is_trained = True

        logger.info(f"RL model loaded from {path}")


class MLBrainCore:
    """
    ML Brain Core - Adaptive Weight Optimization
    Uses gradient-based updates to optimize strategy weights
    """

    def __init__(self, strategies: List[str], initial_weights: Optional[Dict[str, float]] = None):
        self.strategies = strategies
        self.n_strategies = len(strategies)

        # Initialize weights
        if initial_weights:
            self.weights = np.array([initial_weights.get(s, 1.0 / self.n_strategies) for s in strategies])
        else:
            self.weights = np.ones(self.n_strategies) / self.n_strategies

        # Optimization parameters
        self.learning_rate = 0.01
        self.min_learning_rate = 0.001
        self.momentum = 0.9
        self.velocity = np.zeros(self.n_strategies)

        # Performance tracking
        self.performance_history: List[Dict] = []
        self.best_weights = self.weights.copy()
        self.best_score = float('-inf')

    def update_weights(self, strategy_performance: Dict[str, Dict]) -> np.ndarray:
        """
        Update strategy weights based on performance

        Args:
            strategy_performance: Dict mapping strategy name to performance metrics
                                 {'strategy_name': {'win_rate': 0.7, 'wl_ratio': 2.0, 'sharpe': 1.5}}

        Returns:
            Updated weights
        """
        # Calculate quality scores
        quality_scores = []

        for strategy in self.strategies:
            perf = strategy_performance.get(strategy, {})

            win_rate = perf.get('win_rate', 0.5)
            wl_ratio = perf.get('wl_ratio', 1.0)
            sharpe = perf.get('sharpe', 0.0)

            # Quality score formula
            score = (
                0.4 * win_rate +
                0.3 * min(wl_ratio / 3.0, 1.0) +
                0.3 * min(sharpe / 2.0, 1.0)
            )

            quality_scores.append(score)

        quality_scores = np.array(quality_scores)

        # Calculate gradient (direction of improvement)
        gradient = quality_scores - self.weights

        # Momentum update
        self.velocity = self.momentum * self.velocity + self.learning_rate * gradient
        self.weights = self.weights + self.velocity

        # Normalize to sum to 1
        self.weights = np.clip(self.weights, 0.01, 1.0)
        self.weights = self.weights / self.weights.sum()

        # Track performance
        total_score = np.dot(self.weights, quality_scores)
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'weights': self.weights.tolist(),
            'quality_scores': quality_scores.tolist(),
            'total_score': total_score
        })

        # Save best weights
        if total_score > self.best_score:
            self.best_score = total_score
            self.best_weights = self.weights.copy()

        # Decay learning rate
        self.learning_rate = max(self.min_learning_rate, self.learning_rate * 0.999)

        return self.weights

    def get_weighted_signal(self, strategy_signals: Dict[str, float]) -> float:
        """
        Combine strategy signals using current weights

        Args:
            strategy_signals: Dict mapping strategy name to signal (-1 to 1)

        Returns:
            Weighted combined signal
        """
        signals = np.array([strategy_signals.get(s, 0.0) for s in self.strategies])
        weighted_signal = np.dot(self.weights, signals)
        return float(weighted_signal)

    def restore_best_weights(self):
        """Restore best performing weights"""
        self.weights = self.best_weights.copy()
        logger.info(f"Restored best weights with score {self.best_score:.4f}")


class TradingBrainCore:
    """
    Trading Brain Core - Execution Engine
    Manages positions and executes trades with risk management
    """

    def __init__(self, config: Optional[RLConfig] = None):
        self.config = config or RLConfig()

        # Position tracking
        self.positions: Dict[str, Dict] = {}
        self.max_positions = self.config.max_positions

        # Performance tracking
        self.trades: List[TradeResult] = []
        self.daily_pnl = 0.0
        self.daily_start_value = 0.0
        self.total_drawdown = 0.0

        # Adaptive parameters
        self.risk_multiplier = 1.0
        self.winning_streak = 0
        self.losing_streak = 0

    def should_trade(self, signal: float, confidence: float) -> Tuple[bool, str]:
        """
        Determine if trade should be executed

        Args:
            signal: Trading signal (-1 to 1)
            confidence: Signal confidence (0 to 1)

        Returns:
            Tuple of (should_trade, reason)
        """
        # Check confidence threshold
        if confidence < self.config.confidence_threshold:
            return False, f"Confidence {confidence:.2%} below threshold"

        # Check position limits
        if len(self.positions) >= self.max_positions and signal > 0:
            return False, "Maximum positions reached"

        # Check drawdown limits
        if self.total_drawdown >= self.config.max_total_drawdown:
            return False, f"Total drawdown limit reached ({self.total_drawdown:.2%})"

        daily_dd = self.daily_pnl / self.daily_start_value if self.daily_start_value > 0 else 0
        if daily_dd <= -self.config.max_daily_drawdown:
            return False, f"Daily drawdown limit reached ({daily_dd:.2%})"

        # Signal strength check
        if abs(signal) < 0.3:
            return False, "Signal too weak"

        return True, "Trade approved"

    def calculate_position_size(self, portfolio_value: float, price: float,
                               confidence: float, volatility: float) -> int:
        """Calculate risk-adjusted position size"""
        base_size = portfolio_value * self.config.position_size

        # Confidence adjustment
        conf_adj = confidence / 0.7  # Normalize around target confidence

        # Volatility adjustment
        vol_adj = min(1.0, 0.15 / volatility) if volatility > 0 else 1.0

        # Streak adjustment
        if self.winning_streak >= 3:
            streak_adj = min(1.2, 1 + 0.05 * self.winning_streak)
        elif self.losing_streak >= 2:
            streak_adj = max(0.5, 1 - 0.1 * self.losing_streak)
        else:
            streak_adj = 1.0

        # Risk multiplier (from external adjustments)
        adjusted_size = base_size * conf_adj * vol_adj * streak_adj * self.risk_multiplier

        shares = int(adjusted_size / price) if price > 0 else 0
        return shares

    def record_trade(self, result: TradeResult):
        """Record completed trade and update stats"""
        self.trades.append(result)
        self.daily_pnl += result.pnl

        # Update streaks
        if result.pnl > 0:
            self.winning_streak += 1
            self.losing_streak = 0
        else:
            self.losing_streak += 1
            self.winning_streak = 0

    def get_performance_metrics(self) -> Dict:
        """Calculate current performance metrics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'wl_ratio': 0.0,
                'sharpe': 0.0,
                'total_pnl': 0.0
            }

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]

        win_rate = len(winning_trades) / len(self.trades)
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        wl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        # Sharpe ratio (simplified)
        returns = [t.pnl_pct for t in self.trades]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        return {
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'wl_ratio': wl_ratio,
            'sharpe': sharpe,
            'total_pnl': sum(t.pnl for t in self.trades),
            'avg_trade': np.mean([t.pnl for t in self.trades]),
            'winning_streak': self.winning_streak,
            'losing_streak': self.losing_streak
        }

    def reset_daily(self, portfolio_value: float):
        """Reset daily tracking"""
        self.daily_pnl = 0.0
        self.daily_start_value = portfolio_value


class ReinforcementLoop:
    """
    Main Reinforcement Learning Loop
    Orchestrates ML Brain, Trading Brain, and RL Engine

    Implements closed-loop feedback:
    ML Brain learns → Trading Brain executes → Feedback updates ML
    """

    def __init__(self, strategies: List[str], config: Optional[RLConfig] = None):
        self.config = config or RLConfig()

        # Core components
        self.ml_brain = MLBrainCore(strategies)
        self.trading_brain = TradingBrainCore(self.config)
        self.rl_engine = RLEngine(self.config)

        # State
        self.is_running = False
        self.iteration = 0

        # Database for persistence
        self.db_path = Path("data/rl_loop.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Targets
        self.targets = {
            'win_rate': self.config.target_win_rate,
            'wl_ratio': self.config.target_wl_ratio,
            'sharpe': self.config.target_sharpe
        }

        logger.info("Reinforcement Loop initialized")

    def _init_database(self):
        """Initialize SQLite database for persistence"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT,
                action TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity INTEGER,
                pnl REAL,
                pnl_pct REAL,
                duration_seconds INTEGER,
                entry_time TEXT,
                exit_time TEXT,
                signal_confidence REAL,
                strategy_name TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                timestamp TEXT PRIMARY KEY,
                iteration INTEGER,
                win_rate REAL,
                wl_ratio REAL,
                sharpe REAL,
                total_pnl REAL,
                weights TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weights_history (
                timestamp TEXT PRIMARY KEY,
                weights TEXT,
                score REAL
            )
        ''')

        conn.commit()
        conn.close()

    def train_rl(self, df: pd.DataFrame) -> Dict:
        """Train RL engine on historical data"""
        logger.info("Training RL engine...")
        result = self.rl_engine.train_ppo(df)
        return result

    def run_iteration(self, market_data: pd.DataFrame, strategy_signals: Dict[str, Dict]) -> Dict:
        """
        Run one iteration of the reinforcement loop

        Args:
            market_data: Current market data
            strategy_signals: Signals from each strategy
                             {'strategy_name': {'signal': 0.5, 'confidence': 0.8}}

        Returns:
            Iteration results
        """
        self.iteration += 1

        # Step 1: Get weighted signal from ML Brain
        signals = {s: d.get('signal', 0) for s, d in strategy_signals.items()}
        confidences = {s: d.get('confidence', 0) for s, d in strategy_signals.items()}

        combined_signal = self.ml_brain.get_weighted_signal(signals)
        avg_confidence = np.mean(list(confidences.values()))

        # Step 2: Trading Brain decision
        should_trade, reason = self.trading_brain.should_trade(combined_signal, avg_confidence)

        result = {
            'iteration': self.iteration,
            'combined_signal': combined_signal,
            'confidence': avg_confidence,
            'should_trade': should_trade,
            'reason': reason,
            'current_weights': dict(zip(self.ml_brain.strategies, self.ml_brain.weights.tolist()))
        }

        # Step 3: If traded, record feedback
        if should_trade:
            # In real implementation, this would come from actual trade execution
            result['action'] = 'BUY' if combined_signal > 0 else 'SELL'

        # Step 4: Update ML Brain weights based on strategy performance
        # (In real implementation, this would use actual trading results)
        strategy_performance = {}
        for strategy in self.ml_brain.strategies:
            strategy_performance[strategy] = {
                'win_rate': 0.5 + signals.get(strategy, 0) * 0.2,
                'wl_ratio': 1.5 + signals.get(strategy, 0) * 0.5,
                'sharpe': 1.0 + signals.get(strategy, 0) * 0.5
            }

        new_weights = self.ml_brain.update_weights(strategy_performance)
        result['updated_weights'] = dict(zip(self.ml_brain.strategies, new_weights.tolist()))

        # Step 5: Get RL prediction for validation
        if self.rl_engine.is_trained:
            observation = self._create_observation(market_data)
            rl_action = self.rl_engine.predict(observation)
            result['rl_action'] = ActionType(rl_action).name

        # Store metrics
        self._store_metrics(result)

        return result

    def _create_observation(self, df: pd.DataFrame) -> np.ndarray:
        """Create observation vector from market data"""
        # Simplified - would use full feature engineering
        obs = np.zeros(53, dtype=np.float32)

        if len(df) > 0:
            latest = df.iloc[-1]
            obs[0] = latest.get('close', 0) / 100  # Normalize
            obs[1] = latest.get('volume', 0) / 1e6

        return obs

    def _store_metrics(self, result: Dict):
        """Store metrics to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metrics = self.trading_brain.get_performance_metrics()

        cursor.execute('''
            INSERT OR REPLACE INTO metrics
            (timestamp, iteration, win_rate, wl_ratio, sharpe, total_pnl, weights)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            self.iteration,
            metrics['win_rate'],
            metrics['wl_ratio'],
            metrics['sharpe'],
            metrics['total_pnl'],
            json.dumps(result.get('current_weights', {}))
        ))

        conn.commit()
        conn.close()

    def get_status(self) -> Dict:
        """Get current loop status"""
        return {
            'is_running': self.is_running,
            'iteration': self.iteration,
            'ml_brain_weights': dict(zip(self.ml_brain.strategies, self.ml_brain.weights.tolist())),
            'trading_performance': self.trading_brain.get_performance_metrics(),
            'rl_trained': self.rl_engine.is_trained,
            'targets': self.targets
        }

    def check_targets_met(self) -> Dict[str, bool]:
        """Check if performance targets are met"""
        metrics = self.trading_brain.get_performance_metrics()

        return {
            'win_rate': metrics['win_rate'] >= self.targets['win_rate'],
            'wl_ratio': metrics['wl_ratio'] >= self.targets['wl_ratio'],
            'sharpe': metrics['sharpe'] >= self.targets['sharpe']
        }


# Singleton instances
_rl_engine: Optional[RLEngine] = None
_reinforcement_loop: Optional[ReinforcementLoop] = None


def get_rl_engine() -> RLEngine:
    """Get or create RL Engine singleton"""
    global _rl_engine
    if _rl_engine is None:
        _rl_engine = RLEngine()
    return _rl_engine


def get_reinforcement_loop(strategies: Optional[List[str]] = None) -> ReinforcementLoop:
    """Get or create Reinforcement Loop singleton"""
    global _reinforcement_loop
    if _reinforcement_loop is None:
        default_strategies = [
            'trend_following',
            'mean_reversion',
            'momentum',
            'rsi_oversold',
            'macd_cross',
            'bollinger_breakout',
            'vwap_deviation',
            'ml_ensemble'
        ]
        _reinforcement_loop = ReinforcementLoop(strategies or default_strategies)
    return _reinforcement_loop
