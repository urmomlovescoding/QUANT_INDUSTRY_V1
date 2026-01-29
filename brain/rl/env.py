"""
Trading Environments for Reinforcement Learning
================================================
Gymnasium-compatible environments for training trading agents.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, List
from enum import IntEnum
import logging

logger = logging.getLogger(__name__)


class Action(IntEnum):
    """Trading actions."""
    SELL = 0
    HOLD = 1
    BUY = 2


@dataclass
class TradingEnvConfig:
    """Trading environment configuration."""
    initial_balance: float = 100_000.0
    max_position: float = 1.0  # Maximum position as fraction of portfolio
    transaction_cost: float = 0.001  # 0.1% per trade
    slippage: float = 0.0005  # 0.05% slippage
    
    # Reward shaping
    reward_scaling: float = 100.0
    risk_penalty: float = 0.1  # Penalty for high volatility
    drawdown_penalty: float = 0.5  # Penalty for drawdowns
    
    # Features
    lookback_window: int = 60
    include_position: bool = True
    include_pnl: bool = True
    
    # Episode settings
    max_episode_steps: int = 252  # ~1 trading year
    random_start: bool = True


class TradingEnv(gym.Env):
    """
    Single-asset trading environment.
    
    Observation Space:
    - Price features (OHLCV normalized)
    - Technical indicators
    - Current position
    - Unrealized PnL
    - Time features
    
    Action Space:
    - 0: Sell (go short or reduce long)
    - 1: Hold (maintain position)
    - 2: Buy (go long or reduce short)
    
    Reward:
    - Realized PnL from trades
    - Risk-adjusted returns (Sharpe-like)
    - Penalties for drawdowns and excessive trading
    """
    
    metadata = {'render_modes': ['human', 'rgb_array']}
    
    def __init__(
        self,
        data: np.ndarray,
        feature_names: Optional[List[str]] = None,
        config: Optional[TradingEnvConfig] = None,
        render_mode: Optional[str] = None
    ):
        """
        Initialize trading environment.
        
        Args:
            data: Price/feature data [timesteps, features]
                  First 5 columns assumed to be OHLCV
            feature_names: Names of feature columns
            config: Environment configuration
            render_mode: Render mode ('human' or 'rgb_array')
        """
        super().__init__()
        
        self.data = data
        self.feature_names = feature_names
        self.config = config or TradingEnvConfig()
        self.render_mode = render_mode
        
        self.n_steps = len(data)
        self.n_features = data.shape[1]
        
        # Observation space: features + position + pnl + time
        obs_dim = self.config.lookback_window * self.n_features
        if self.config.include_position:
            obs_dim += 1
        if self.config.include_pnl:
            obs_dim += 2  # unrealized + realized
        obs_dim += 2  # time features (day progress, episode progress)
        
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32
        )
        
        # Action space: Sell, Hold, Buy
        self.action_space = spaces.Discrete(3)
        
        # State variables
        self._reset_state()
    
    def _reset_state(self):
        """Reset internal state."""
        self.current_step = self.config.lookback_window
        self.balance = self.config.initial_balance
        self.position = 0.0  # -1 to 1
        self.entry_price = 0.0
        self.realized_pnl = 0.0
        self.peak_value = self.config.initial_balance
        self.trades = []
        self.returns_history = []
    
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict] = None
    ) -> Tuple[np.ndarray, Dict]:
        """Reset environment."""
        super().reset(seed=seed)
        self._reset_state()
        
        # Random starting point
        if self.config.random_start:
            max_start = self.n_steps - self.config.max_episode_steps - 1
            if max_start > self.config.lookback_window:
                self.current_step = self.np_random.integers(
                    self.config.lookback_window,
                    max_start
                )
        
        obs = self._get_observation()
        info = self._get_info()
        
        return obs, info
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one step.
        
        Args:
            action: 0=Sell, 1=Hold, 2=Buy
            
        Returns:
            observation, reward, terminated, truncated, info
        """
        # Current price (use close)
        current_price = self.data[self.current_step, 3]  # Close
        
        # Calculate unrealized PnL before action
        prev_portfolio_value = self._get_portfolio_value(current_price)
        
        # Execute action
        reward = self._execute_action(action, current_price)
        
        # Move to next step
        self.current_step += 1
        
        # New price after step
        if self.current_step < self.n_steps:
            new_price = self.data[self.current_step, 3]
        else:
            new_price = current_price
        
        # Calculate new portfolio value
        portfolio_value = self._get_portfolio_value(new_price)
        
        # Calculate step return
        step_return = (portfolio_value - prev_portfolio_value) / prev_portfolio_value
        self.returns_history.append(step_return)
        
        # Update peak for drawdown calculation
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
        
        # Shape reward
        reward += self._shape_reward(step_return, portfolio_value)
        
        # Check termination
        terminated = False
        truncated = False
        
        # Terminate on bankruptcy
        if portfolio_value < self.config.initial_balance * 0.5:
            terminated = True
            reward -= 10.0  # Large penalty
        
        # Truncate at max steps
        if self.current_step >= min(self.n_steps - 1, 
                                     self.config.lookback_window + self.config.max_episode_steps):
            truncated = True
        
        obs = self._get_observation()
        info = self._get_info()
        
        return obs, float(reward), terminated, truncated, info
    
    def _execute_action(self, action: int, price: float) -> float:
        """Execute trading action and return immediate reward."""
        reward = 0.0
        
        if action == Action.BUY:
            if self.position < self.config.max_position:
                # Close short or open long
                if self.position < 0:
                    # Close short position
                    pnl = -self.position * (price - self.entry_price)
                    pnl -= abs(self.position) * price * self.config.transaction_cost
                    self.realized_pnl += pnl
                    reward = pnl / self.config.initial_balance * self.config.reward_scaling
                    self.position = 0
                
                # Open long
                self.position = self.config.max_position
                self.entry_price = price * (1 + self.config.slippage)
                self.trades.append({'step': self.current_step, 'action': 'buy', 'price': price})
                
        elif action == Action.SELL:
            if self.position > -self.config.max_position:
                # Close long or open short
                if self.position > 0:
                    # Close long position
                    pnl = self.position * (price - self.entry_price)
                    pnl -= abs(self.position) * price * self.config.transaction_cost
                    self.realized_pnl += pnl
                    reward = pnl / self.config.initial_balance * self.config.reward_scaling
                    self.position = 0
                
                # Open short
                self.position = -self.config.max_position
                self.entry_price = price * (1 - self.config.slippage)
                self.trades.append({'step': self.current_step, 'action': 'sell', 'price': price})
        
        return reward
    
    def _shape_reward(self, step_return: float, portfolio_value: float) -> float:
        """Apply reward shaping."""
        shaped_reward = 0.0
        
        # Reward for positive returns
        shaped_reward += step_return * self.config.reward_scaling
        
        # Penalty for drawdown
        drawdown = (self.peak_value - portfolio_value) / self.peak_value
        if drawdown > 0.1:  # >10% drawdown
            shaped_reward -= drawdown * self.config.drawdown_penalty
        
        # Penalty for high volatility
        if len(self.returns_history) > 10:
            recent_vol = np.std(self.returns_history[-10:])
            if recent_vol > 0.02:  # >2% daily vol
                shaped_reward -= recent_vol * self.config.risk_penalty
        
        return shaped_reward
    
    def _get_portfolio_value(self, current_price: float) -> float:
        """Calculate current portfolio value."""
        unrealized_pnl = 0.0
        if self.position != 0:
            unrealized_pnl = self.position * (current_price - self.entry_price)
        return self.balance + self.realized_pnl + unrealized_pnl
    
    def _get_observation(self) -> np.ndarray:
        """Construct observation vector."""
        # Price features (normalized)
        start_idx = max(0, self.current_step - self.config.lookback_window)
        price_window = self.data[start_idx:self.current_step]
        
        # Normalize by current close
        current_close = self.data[self.current_step - 1, 3]
        normalized = price_window / current_close
        
        obs = normalized.flatten()
        
        # Pad if needed
        expected_len = self.config.lookback_window * self.n_features
        if len(obs) < expected_len:
            obs = np.pad(obs, (expected_len - len(obs), 0))
        
        obs_list = [obs]
        
        # Position
        if self.config.include_position:
            obs_list.append(np.array([self.position]))
        
        # PnL
        if self.config.include_pnl:
            current_price = self.data[self.current_step - 1, 3]
            portfolio_value = self._get_portfolio_value(current_price)
            unrealized = (portfolio_value - self.balance - self.realized_pnl) / self.config.initial_balance
            realized = self.realized_pnl / self.config.initial_balance
            obs_list.append(np.array([unrealized, realized]))
        
        # Time features
        day_progress = (self.current_step % 252) / 252  # Progress within year
        episode_progress = (self.current_step - self.config.lookback_window) / self.config.max_episode_steps
        obs_list.append(np.array([day_progress, episode_progress]))
        
        return np.concatenate(obs_list).astype(np.float32)
    
    def _get_info(self) -> Dict[str, Any]:
        """Get info dict."""
        current_price = self.data[min(self.current_step, self.n_steps - 1), 3]
        portfolio_value = self._get_portfolio_value(current_price)
        
        return {
            'portfolio_value': portfolio_value,
            'position': self.position,
            'realized_pnl': self.realized_pnl,
            'total_return': (portfolio_value - self.config.initial_balance) / self.config.initial_balance,
            'n_trades': len(self.trades),
            'current_step': self.current_step,
        }
    
    def render(self):
        """Render environment state."""
        if self.render_mode == 'human':
            info = self._get_info()
            print(f"Step: {info['current_step']} | "
                  f"Value: ${info['portfolio_value']:,.2f} | "
                  f"Position: {info['position']:.2f} | "
                  f"Return: {info['total_return']:.2%}")


class MultiAssetTradingEnv(TradingEnv):
    """
    Multi-asset trading environment.
    
    Extends single-asset env to handle multiple assets with
    portfolio allocation decisions.
    """
    
    def __init__(
        self,
        data: Dict[str, np.ndarray],  # {symbol: data}
        config: Optional[TradingEnvConfig] = None,
        render_mode: Optional[str] = None
    ):
        self.assets = list(data.keys())
        self.n_assets = len(self.assets)
        
        # Combine data
        combined = np.stack([data[s] for s in self.assets], axis=-1)
        self.multi_data = combined  # [timesteps, features, assets]
        
        # Use first asset's data for parent class
        super().__init__(data[self.assets[0]], config=config, render_mode=render_mode)
        
        # Override action space for multi-asset
        # Actions: allocation weights for each asset
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(self.n_assets,),
            dtype=np.float32
        )
        
        # Positions per asset
        self.positions = np.zeros(self.n_assets)
        self.entry_prices = np.zeros(self.n_assets)
    
    def _reset_state(self):
        """Reset multi-asset state."""
        super()._reset_state()
        self.positions = np.zeros(self.n_assets)
        self.entry_prices = np.zeros(self.n_assets)
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute multi-asset step with continuous allocation."""
        # Normalize action to valid allocations
        action = np.clip(action, -1, 1)
        target_positions = action / (np.abs(action).sum() + 1e-8)  # Normalize
        
        # Get current prices
        current_prices = self.multi_data[self.current_step, 3, :]  # Close prices
        
        # Calculate trades needed
        position_diff = target_positions - self.positions
        
        # Execute trades and calculate costs
        total_cost = 0.0
        total_pnl = 0.0
        
        for i, (diff, price) in enumerate(zip(position_diff, current_prices)):
            if abs(diff) > 0.01:  # Minimum trade threshold
                # Close existing position PnL
                if self.positions[i] != 0:
                    pnl = self.positions[i] * (price - self.entry_prices[i])
                    total_pnl += pnl
                
                # Transaction cost
                total_cost += abs(diff) * price * self.config.transaction_cost
                
                # Update position
                self.positions[i] = target_positions[i]
                self.entry_prices[i] = price
        
        self.realized_pnl += total_pnl - total_cost
        
        # Move to next step
        self.current_step += 1
        
        # Calculate portfolio return
        new_prices = self.multi_data[min(self.current_step, self.n_steps - 1), 3, :]
        portfolio_return = np.sum(self.positions * (new_prices - current_prices) / current_prices)
        
        # Reward
        reward = portfolio_return * self.config.reward_scaling
        
        # Check termination
        terminated = self.current_step >= self.n_steps - 1
        truncated = False
        
        obs = self._get_observation()
        info = self._get_info()
        info['positions'] = self.positions.copy()
        
        return obs, float(reward), terminated, truncated, info
