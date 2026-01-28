"""
QUANT_INDUSTRY_V1 Reinforcement Learning Environment

Custom trading environment compatible with Gymnasium:
- Multi-asset portfolio management
- Risk-aware reward shaping
- Realistic transaction costs
- Position sizing actions

Rollback Plan: Delete this file
Tests Required: Environment step validation, reward calculation
Failure Modes: Invalid actions clamped to valid range
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# ENVIRONMENT TYPES
# =============================================================================

class ActionType(Enum):
    """Type of trading action."""
    CONTINUOUS = "continuous"  # -1 to 1 position sizing
    DISCRETE = "discrete"  # {-1, 0, 1} for short/flat/long
    MULTI_DISCRETE = "multi_discrete"  # Multiple assets


@dataclass
class EnvConfig:
    """Configuration for trading environment."""
    initial_capital: float = 100000.0
    max_position_pct: float = 0.25  # Max position as % of capital
    transaction_cost_pct: float = 0.001  # 10 bps
    slippage_pct: float = 0.0005  # 5 bps
    risk_free_rate: float = 0.02  # Annual
    max_drawdown_limit: float = 0.20  # 20% max DD
    leverage_limit: float = 2.0
    lookback_window: int = 20  # Observation window
    episode_length: int = 252  # ~1 year
    action_type: ActionType = ActionType.CONTINUOUS
    reward_scaling: float = 1.0
    normalize_obs: bool = True
    include_positions: bool = True
    include_time: bool = True


@dataclass
class EnvState:
    """Current environment state."""
    step: int = 0
    capital: float = 100000.0
    positions: Dict[str, float] = field(default_factory=dict)
    position_values: Dict[str, float] = field(default_factory=dict)
    portfolio_value: float = 100000.0
    cash: float = 100000.0
    pnl: float = 0.0
    total_return: float = 0.0
    max_portfolio_value: float = 100000.0
    drawdown: float = 0.0
    trades_executed: int = 0
    transaction_costs: float = 0.0


# =============================================================================
# REWARD FUNCTIONS
# =============================================================================

class RewardFunction(ABC):
    """Abstract base class for reward functions."""

    @abstractmethod
    def calculate(
        self,
        state: EnvState,
        prev_state: EnvState,
        action: np.ndarray,
        prices: np.ndarray,
    ) -> float:
        """Calculate reward for this step."""
        pass


class SimpleReturnReward(RewardFunction):
    """Simple return-based reward."""

    def calculate(
        self,
        state: EnvState,
        prev_state: EnvState,
        action: np.ndarray,
        prices: np.ndarray,
    ) -> float:
        """Return = (current_value - prev_value) / prev_value."""
        if prev_state.portfolio_value <= 0:
            return 0.0

        return (state.portfolio_value - prev_state.portfolio_value) / prev_state.portfolio_value


class SharpeReward(RewardFunction):
    """Sharpe ratio approximation reward."""

    def __init__(self, risk_free_rate: float = 0.02, window: int = 20):
        self.risk_free_rate = risk_free_rate
        self.window = window
        self.returns_history: List[float] = []

    def calculate(
        self,
        state: EnvState,
        prev_state: EnvState,
        action: np.ndarray,
        prices: np.ndarray,
    ) -> float:
        if prev_state.portfolio_value <= 0:
            return 0.0

        ret = (state.portfolio_value - prev_state.portfolio_value) / prev_state.portfolio_value
        self.returns_history.append(ret)

        # Keep only recent window
        if len(self.returns_history) > self.window:
            self.returns_history = self.returns_history[-self.window:]

        if len(self.returns_history) < 2:
            return ret

        # Calculate Sharpe approximation
        mean_ret = np.mean(self.returns_history)
        std_ret = np.std(self.returns_history)

        if std_ret < 1e-8:
            return ret

        daily_rf = self.risk_free_rate / 252
        sharpe = (mean_ret - daily_rf) / std_ret

        return sharpe * 0.1  # Scale down for stability


class RiskAdjustedReward(RewardFunction):
    """
    Risk-adjusted reward with multiple components:
    - Return component
    - Drawdown penalty
    - Volatility penalty
    - Transaction cost penalty
    """

    def __init__(
        self,
        return_weight: float = 1.0,
        drawdown_penalty: float = 2.0,
        volatility_penalty: float = 0.5,
        cost_penalty: float = 0.1,
        max_dd_threshold: float = 0.1,
    ):
        self.return_weight = return_weight
        self.drawdown_penalty = drawdown_penalty
        self.volatility_penalty = volatility_penalty
        self.cost_penalty = cost_penalty
        self.max_dd_threshold = max_dd_threshold
        self.returns_history: List[float] = []

    def calculate(
        self,
        state: EnvState,
        prev_state: EnvState,
        action: np.ndarray,
        prices: np.ndarray,
    ) -> float:
        if prev_state.portfolio_value <= 0:
            return -1.0

        # Return component
        ret = (state.portfolio_value - prev_state.portfolio_value) / prev_state.portfolio_value
        self.returns_history.append(ret)

        # Keep history bounded
        if len(self.returns_history) > 100:
            self.returns_history = self.returns_history[-100:]

        reward = self.return_weight * ret

        # Drawdown penalty
        if state.drawdown > self.max_dd_threshold:
            dd_excess = state.drawdown - self.max_dd_threshold
            reward -= self.drawdown_penalty * dd_excess

        # Volatility penalty (if enough history)
        if len(self.returns_history) > 5:
            recent_vol = np.std(self.returns_history[-20:]) if len(self.returns_history) >= 20 else np.std(self.returns_history)
            if recent_vol > 0.02:  # Penalize high volatility
                reward -= self.volatility_penalty * (recent_vol - 0.02)

        # Transaction cost penalty
        step_costs = state.transaction_costs - prev_state.transaction_costs
        reward -= self.cost_penalty * step_costs / prev_state.portfolio_value

        return reward

    def reset(self):
        """Reset history for new episode."""
        self.returns_history = []


class ProfitFactorReward(RewardFunction):
    """Reward based on profit factor (gains/losses ratio)."""

    def __init__(self, window: int = 50):
        self.window = window
        self.gains: List[float] = []
        self.losses: List[float] = []

    def calculate(
        self,
        state: EnvState,
        prev_state: EnvState,
        action: np.ndarray,
        prices: np.ndarray,
    ) -> float:
        if prev_state.portfolio_value <= 0:
            return 0.0

        pnl = state.portfolio_value - prev_state.portfolio_value

        if pnl > 0:
            self.gains.append(pnl)
        elif pnl < 0:
            self.losses.append(abs(pnl))

        # Trim to window
        self.gains = self.gains[-self.window:]
        self.losses = self.losses[-self.window:]

        total_gains = sum(self.gains)
        total_losses = sum(self.losses)

        if total_losses == 0:
            pf = 2.0 if total_gains > 0 else 0.0
        else:
            pf = total_gains / total_losses

        # Normalize profit factor to reasonable reward range
        # PF of 1 = breakeven, PF of 2 = good
        return (pf - 1.0) * 0.1

    def reset(self):
        self.gains = []
        self.losses = []


# =============================================================================
# TRADING ENVIRONMENT
# =============================================================================

class TradingEnvironment:
    """
    Gymnasium-compatible trading environment.

    Supports single or multiple assets with continuous or discrete actions.
    """

    def __init__(
        self,
        prices: np.ndarray,  # Shape: (n_steps, n_assets) or (n_steps,)
        features: np.ndarray = None,  # Optional additional features
        symbols: List[str] = None,
        config: EnvConfig = None,
        reward_function: RewardFunction = None,
    ):
        self.config = config or EnvConfig()
        self.reward_function = reward_function or RiskAdjustedReward()

        # Handle single vs multi-asset
        if prices.ndim == 1:
            prices = prices.reshape(-1, 1)

        self.prices = prices
        self.n_steps, self.n_assets = prices.shape

        if features is not None and features.ndim == 1:
            features = features.reshape(-1, 1)
        self.features = features
        self.n_features = features.shape[1] if features is not None else 0

        self.symbols = symbols or [f"ASSET_{i}" for i in range(self.n_assets)]

        # Calculate returns
        self.returns = np.zeros_like(prices)
        self.returns[1:] = (prices[1:] - prices[:-1]) / prices[:-1]

        # Initialize state
        self.state = EnvState(capital=self.config.initial_capital)
        self.state.cash = self.config.initial_capital
        self.state.portfolio_value = self.config.initial_capital
        self.state.max_portfolio_value = self.config.initial_capital

        self.current_step = self.config.lookback_window

        # Episode tracking
        self.episode_count = 0
        self.done = False

        # Define spaces (for Gymnasium compatibility)
        self._define_spaces()

    def _define_spaces(self):
        """Define observation and action spaces."""
        # Observation space dimensions
        obs_dim = self.config.lookback_window * self.n_assets  # Price history
        if self.features is not None:
            obs_dim += self.config.lookback_window * self.n_features

        if self.config.include_positions:
            obs_dim += self.n_assets  # Current positions
            obs_dim += 1  # Cash ratio

        if self.config.include_time:
            obs_dim += 1  # Time remaining in episode

        self.observation_dim = obs_dim

        # Action space
        if self.config.action_type == ActionType.CONTINUOUS:
            self.action_dim = self.n_assets  # Continuous position sizing
        elif self.config.action_type == ActionType.DISCRETE:
            self.action_dim = 3 ** self.n_assets  # All combinations of {-1, 0, 1}
        else:
            self.action_dim = 3 * self.n_assets  # Multi-discrete

    def reset(
        self,
        seed: int = None,
        start_step: int = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset environment to initial state.

        Args:
            seed: Random seed
            start_step: Starting step (None = use lookback_window)

        Returns:
            Tuple of (observation, info)
        """
        if seed is not None:
            np.random.seed(seed)

        self.current_step = start_step if start_step is not None else self.config.lookback_window

        # Reset state
        self.state = EnvState(capital=self.config.initial_capital)
        self.state.cash = self.config.initial_capital
        self.state.portfolio_value = self.config.initial_capital
        self.state.max_portfolio_value = self.config.initial_capital
        self.state.positions = {s: 0.0 for s in self.symbols}
        self.state.position_values = {s: 0.0 for s in self.symbols}

        self.done = False
        self.episode_count += 1

        # Reset reward function
        if hasattr(self.reward_function, 'reset'):
            self.reward_function.reset()

        obs = self._get_observation()
        info = self._get_info()

        return obs, info

    def step(
        self,
        action: Union[np.ndarray, int, List[float]]
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.

        Args:
            action: Trading action (position sizes or discrete choice)

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        if self.done:
            logger.warning("Episode already done, please reset")
            return self._get_observation(), 0.0, True, False, self._get_info()

        # Convert action to target positions
        target_positions = self._process_action(action)

        # Save previous state
        prev_state = EnvState(
            step=self.state.step,
            capital=self.state.capital,
            positions=self.state.positions.copy(),
            position_values=self.state.position_values.copy(),
            portfolio_value=self.state.portfolio_value,
            cash=self.state.cash,
            pnl=self.state.pnl,
            total_return=self.state.total_return,
            max_portfolio_value=self.state.max_portfolio_value,
            drawdown=self.state.drawdown,
            trades_executed=self.state.trades_executed,
            transaction_costs=self.state.transaction_costs,
        )

        # Execute trades
        self._execute_trades(target_positions)

        # Update prices and portfolio value
        self.current_step += 1
        self.state.step = self.current_step

        self._update_portfolio_value()

        # Calculate reward
        current_prices = self.prices[min(self.current_step, self.n_steps - 1)]
        reward = self.reward_function.calculate(
            self.state, prev_state, target_positions, current_prices
        )
        reward *= self.config.reward_scaling

        # Check termination conditions
        terminated = self._check_terminated()
        truncated = self.current_step >= self.n_steps - 1

        self.done = terminated or truncated

        obs = self._get_observation()
        info = self._get_info()

        return obs, reward, terminated, truncated, info

    def _process_action(self, action: Union[np.ndarray, int, List[float]]) -> np.ndarray:
        """Convert action to target position array."""
        if self.config.action_type == ActionType.CONTINUOUS:
            # Continuous: action is already target positions as fractions
            if isinstance(action, (int, float)):
                target = np.array([action])
            else:
                target = np.array(action)

            # Clip to valid range
            target = np.clip(target, -1.0, 1.0)

        elif self.config.action_type == ActionType.DISCRETE:
            # Discrete: decode action index to positions
            if isinstance(action, np.ndarray):
                action = int(action[0]) if len(action) == 1 else action
            if isinstance(action, (list, np.ndarray)) and len(action) == 1:
                action = action[0]

            target = np.zeros(self.n_assets)
            remaining = int(action)

            for i in range(self.n_assets):
                target[i] = (remaining % 3) - 1  # Map 0,1,2 to -1,0,1
                remaining //= 3

        else:
            # Multi-discrete: each element is 0,1,2 mapping to -1,0,1
            target = np.array(action) - 1

        # Scale by max position
        target = target * self.config.max_position_pct

        return target

    def _execute_trades(self, target_positions: np.ndarray) -> None:
        """Execute trades to reach target positions."""
        current_prices = self.prices[min(self.current_step, self.n_steps - 1)]

        for i, symbol in enumerate(self.symbols):
            target_value = target_positions[i] * self.state.portfolio_value
            current_value = self.state.position_values.get(symbol, 0.0)

            trade_value = target_value - current_value

            if abs(trade_value) < 1.0:  # Minimum trade threshold
                continue

            # Calculate costs
            transaction_cost = abs(trade_value) * self.config.transaction_cost_pct
            slippage_cost = abs(trade_value) * self.config.slippage_pct
            total_cost = transaction_cost + slippage_cost

            # Execute trade
            self.state.cash -= trade_value + total_cost
            self.state.transaction_costs += total_cost
            self.state.trades_executed += 1

            # Update position
            if current_prices[i] > 0:
                new_shares = target_value / current_prices[i]
                self.state.positions[symbol] = new_shares
                self.state.position_values[symbol] = target_value

    def _update_portfolio_value(self) -> None:
        """Update portfolio value based on current prices."""
        current_prices = self.prices[min(self.current_step, self.n_steps - 1)]

        position_total = 0.0
        for i, symbol in enumerate(self.symbols):
            shares = self.state.positions.get(symbol, 0.0)
            value = shares * current_prices[i]
            self.state.position_values[symbol] = value
            position_total += value

        self.state.portfolio_value = self.state.cash + position_total

        # Update metrics
        self.state.pnl = self.state.portfolio_value - self.config.initial_capital
        self.state.total_return = self.state.pnl / self.config.initial_capital

        # Update max and drawdown
        if self.state.portfolio_value > self.state.max_portfolio_value:
            self.state.max_portfolio_value = self.state.portfolio_value

        if self.state.max_portfolio_value > 0:
            self.state.drawdown = (
                self.state.max_portfolio_value - self.state.portfolio_value
            ) / self.state.max_portfolio_value

    def _check_terminated(self) -> bool:
        """Check if episode should terminate."""
        # Max drawdown exceeded
        if self.state.drawdown >= self.config.max_drawdown_limit:
            logger.info(f"Max drawdown {self.state.drawdown:.2%} exceeded limit")
            return True

        # Bankrupt
        if self.state.portfolio_value <= 0:
            logger.info("Portfolio value <= 0, bankrupt")
            return True

        return False

    def _get_observation(self) -> np.ndarray:
        """Build observation array."""
        obs_parts = []

        # Price history (normalized returns)
        start_idx = max(0, self.current_step - self.config.lookback_window)
        end_idx = self.current_step

        price_history = self.returns[start_idx:end_idx].flatten()

        # Pad if necessary
        expected_len = self.config.lookback_window * self.n_assets
        if len(price_history) < expected_len:
            price_history = np.pad(
                price_history,
                (expected_len - len(price_history), 0),
                mode='constant'
            )

        if self.config.normalize_obs:
            # Normalize to [-1, 1] using tanh
            price_history = np.tanh(price_history * 10)

        obs_parts.append(price_history)

        # Additional features
        if self.features is not None:
            feat_history = self.features[start_idx:end_idx].flatten()
            expected_feat_len = self.config.lookback_window * self.n_features

            if len(feat_history) < expected_feat_len:
                feat_history = np.pad(
                    feat_history,
                    (expected_feat_len - len(feat_history), 0),
                    mode='constant'
                )

            if self.config.normalize_obs:
                feat_history = np.tanh(feat_history)

            obs_parts.append(feat_history)

        # Current positions
        if self.config.include_positions:
            positions = np.array([
                self.state.position_values.get(s, 0.0) / max(self.state.portfolio_value, 1.0)
                for s in self.symbols
            ])
            obs_parts.append(positions)

            cash_ratio = np.array([self.state.cash / max(self.state.portfolio_value, 1.0)])
            obs_parts.append(cash_ratio)

        # Time feature
        if self.config.include_time:
            max_steps = min(self.config.episode_length, self.n_steps - self.config.lookback_window)
            steps_remaining = max_steps - (self.current_step - self.config.lookback_window)
            time_feature = np.array([steps_remaining / max_steps])
            obs_parts.append(time_feature)

        return np.concatenate(obs_parts).astype(np.float32)

    def _get_info(self) -> Dict[str, Any]:
        """Get current info dictionary."""
        return {
            'step': self.state.step,
            'portfolio_value': self.state.portfolio_value,
            'cash': self.state.cash,
            'pnl': self.state.pnl,
            'total_return': self.state.total_return,
            'drawdown': self.state.drawdown,
            'trades_executed': self.state.trades_executed,
            'transaction_costs': self.state.transaction_costs,
            'positions': self.state.positions.copy(),
        }

    @property
    def observation_space_shape(self) -> Tuple[int]:
        """Return observation space shape."""
        return (self.observation_dim,)

    @property
    def action_space_shape(self) -> Tuple[int]:
        """Return action space shape."""
        return (self.n_assets,)

    def render(self, mode: str = 'human') -> Optional[str]:
        """Render environment state."""
        if mode == 'human':
            print(f"\nStep: {self.state.step}")
            print(f"Portfolio Value: ${self.state.portfolio_value:,.2f}")
            print(f"Cash: ${self.state.cash:,.2f}")
            print(f"PnL: ${self.state.pnl:,.2f} ({self.state.total_return:.2%})")
            print(f"Drawdown: {self.state.drawdown:.2%}")
            print(f"Positions: {self.state.positions}")
            return None
        elif mode == 'ansi':
            lines = [
                f"Step: {self.state.step}",
                f"Portfolio: ${self.state.portfolio_value:,.2f}",
                f"Return: {self.state.total_return:.2%}",
                f"DD: {self.state.drawdown:.2%}",
            ]
            return "\n".join(lines)


# =============================================================================
# VECTORIZED ENVIRONMENT
# =============================================================================

class VectorizedTradingEnv:
    """
    Vectorized environment for parallel training.

    Runs multiple environments simultaneously.
    """

    def __init__(
        self,
        prices_list: List[np.ndarray],
        features_list: List[np.ndarray] = None,
        config: EnvConfig = None,
    ):
        self.n_envs = len(prices_list)

        features_list = features_list or [None] * self.n_envs

        self.envs = [
            TradingEnvironment(
                prices=prices,
                features=features,
                config=config,
            )
            for prices, features in zip(prices_list, features_list)
        ]

    def reset(self) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Reset all environments."""
        obs_list = []
        info_list = []

        for env in self.envs:
            obs, info = env.reset()
            obs_list.append(obs)
            info_list.append(info)

        return np.stack(obs_list), info_list

    def step(
        self,
        actions: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[Dict[str, Any]]]:
        """Step all environments."""
        obs_list = []
        rewards = []
        terminateds = []
        truncateds = []
        info_list = []

        for i, env in enumerate(self.envs):
            obs, reward, terminated, truncated, info = env.step(actions[i])
            obs_list.append(obs)
            rewards.append(reward)
            terminateds.append(terminated)
            truncateds.append(truncated)
            info_list.append(info)

        return (
            np.stack(obs_list),
            np.array(rewards),
            np.array(terminateds),
            np.array(truncateds),
            info_list,
        )
