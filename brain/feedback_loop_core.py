"""
FEEDBACK LOOP CORE - ML Brain ↔ Trading Brain Closed-Loop System
================================================================
Architecture:
    ML Brain (Backtest/Learn) → Trading Brain (Execute) → Performance → ML Brain (Adapt)

Target Metrics:
    - Win Rate: 70%+
    - Win/Loss Ratio: 2:1 minimum
    - Sharpe Ratio: > 1.5
    
Author: QuantBrain Feedback System
Version: 1.0.0
"""

import numpy as np
import pandas as pd
import sqlite3
import json
import pickle
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
import warnings
import logging

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FeedbackLoop")

# ============================================================================
# CONFIGURATION
# ============================================================================

TARGET_WIN_RATE = 0.70  # 70%
TARGET_WL_RATIO = 2.0   # 2:1 W/L
TARGET_SHARPE = 1.5
MIN_TRADES_FOR_UPDATE = 10
LEARNING_RATE_ADAPTIVE = 0.01
MOMENTUM_DECAY = 0.95
MAX_STRATEGY_WEIGHT = 0.25
MIN_STRATEGY_WEIGHT = 0.001
CONFIDENCE_THRESHOLD = 0.65


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class FeedbackType(Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


@dataclass
class LiveTradeResult:
    """Result from live/paper trading."""
    trade_id: str
    symbol: str
    direction: str  # LONG/SHORT
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    quantity: float
    pnl: float
    pnl_pct: float
    strategy_name: str
    strategy_scores: Dict[str, float]  # All strategy contributions
    confidence: float
    exit_reason: str
    market_regime: str
    
    @property
    def feedback_type(self) -> FeedbackType:
        if self.pnl_pct > 0.1:  # >0.1% is a win
            return FeedbackType.WIN
        elif self.pnl_pct < -0.1:
            return FeedbackType.LOSS
        return FeedbackType.BREAKEVEN
    
    @property
    def is_win(self) -> bool:
        return self.feedback_type == FeedbackType.WIN
    
    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'quantity': self.quantity,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'strategy_name': self.strategy_name,
            'strategy_scores': self.strategy_scores,
            'confidence': self.confidence,
            'exit_reason': self.exit_reason,
            'market_regime': self.market_regime,
            'feedback_type': self.feedback_type.value,
            'is_win': self.is_win
        }


@dataclass
class StrategyPerformance:
    """Track strategy performance over time."""
    name: str
    weight: float = 0.05
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    returns: List[float] = field(default_factory=list)
    recent_returns: deque = field(default_factory=lambda: deque(maxlen=50))
    win_streak: int = 0
    loss_streak: int = 0
    max_win_streak: int = 0
    max_loss_streak: int = 0
    last_update: datetime = field(default_factory=datetime.now)
    
    @property
    def win_rate(self) -> float:
        return self.wins / max(1, self.total_trades)
    
    @property
    def avg_win(self) -> float:
        wins = [r for r in self.returns if r > 0]
        return np.mean(wins) if wins else 0.0
    
    @property
    def avg_loss(self) -> float:
        losses = [r for r in self.returns if r < 0]
        return abs(np.mean(losses)) if losses else 0.0
    
    @property
    def wl_ratio(self) -> float:
        return self.avg_win / max(0.001, self.avg_loss)
    
    @property
    def profit_factor(self) -> float:
        wins_sum = sum(r for r in self.returns if r > 0)
        losses_sum = abs(sum(r for r in self.returns if r < 0))
        return wins_sum / max(0.001, losses_sum)
    
    @property
    def sharpe_ratio(self) -> float:
        if len(self.recent_returns) < 5:
            return 0.0
        returns = np.array(list(self.recent_returns))
        if np.std(returns) == 0:
            return 0.0
        return np.mean(returns) / np.std(returns) * np.sqrt(252)
    
    @property
    def sortino_ratio(self) -> float:
        if len(self.recent_returns) < 5:
            return 0.0
        returns = np.array(list(self.recent_returns))
        neg_returns = returns[returns < 0]
        if len(neg_returns) == 0 or np.std(neg_returns) == 0:
            return self.sharpe_ratio
        return np.mean(returns) / np.std(neg_returns) * np.sqrt(252)
    
    @property
    def expectancy(self) -> float:
        """Expected return per trade."""
        return (self.win_rate * self.avg_win) - ((1 - self.win_rate) * self.avg_loss)
    
    @property
    def quality_score(self) -> float:
        """Composite quality score for ranking strategies."""
        # Weighted combination of key metrics
        wr_score = min(1.0, self.win_rate / TARGET_WIN_RATE)
        wl_score = min(1.0, self.wl_ratio / TARGET_WL_RATIO)
        pf_score = min(1.0, self.profit_factor / 2.0)
        sharpe_score = min(1.0, max(0, self.sharpe_ratio) / TARGET_SHARPE)
        
        # Penalize low trade count
        trade_factor = min(1.0, self.total_trades / 20)
        
        return (wr_score * 0.35 + wl_score * 0.25 + pf_score * 0.2 + 
                sharpe_score * 0.2) * trade_factor
    
    def add_trade(self, pnl_pct: float, is_win: bool):
        """Add a trade result."""
        self.total_trades += 1
        self.returns.append(pnl_pct)
        self.recent_returns.append(pnl_pct)
        self.total_pnl += pnl_pct
        
        if is_win:
            self.wins += 1
            self.loss_streak = 0
            self.win_streak += 1
            self.max_win_streak = max(self.max_win_streak, self.win_streak)
        else:
            self.losses += 1
            self.win_streak = 0
            self.loss_streak += 1
            self.max_loss_streak = max(self.max_loss_streak, self.loss_streak)
        
        self.last_update = datetime.now()



# ============================================================================
# ADAPTIVE WEIGHT OPTIMIZER
# ============================================================================

class AdaptiveWeightOptimizer:
    """
    Dynamically optimizes strategy weights based on live performance.
    Uses gradient-based optimization with momentum.
    """
    
    def __init__(self, strategies: List[str]):
        self.strategy_names = strategies
        n = len(strategies)
        
        # Initialize equal weights
        self.weights = np.ones(n) / n
        
        # Momentum tracking
        self.momentum = np.zeros(n)
        self.velocity = np.zeros(n)  # For Adam optimizer
        
        # Performance history
        self.performance_history: Dict[str, StrategyPerformance] = {
            name: StrategyPerformance(name=name, weight=1/n) 
            for name in strategies
        }
        
        # Learning parameters
        self.lr = LEARNING_RATE_ADAPTIVE
        self.beta1 = 0.9  # Momentum decay
        self.beta2 = 0.999  # Velocity decay
        self.epsilon = 1e-8
        self.t = 0  # Time step
        
        # Constraints
        self.min_weight = MIN_STRATEGY_WEIGHT
        self.max_weight = MAX_STRATEGY_WEIGHT
        
    def get_weights(self) -> Dict[str, float]:
        """Get current strategy weights."""
        return {name: float(w) for name, w in zip(self.strategy_names, self.weights)}
    
    def compute_gradient(self, trade_result: LiveTradeResult) -> np.ndarray:
        """
        Compute gradient for weight update based on trade result.
        
        Gradient = -reward * score_i for winning trades
        Gradient = +penalty * score_i for losing trades
        """
        n = len(self.strategy_names)
        gradient = np.zeros(n)
        
        # Get strategy contributions
        scores = np.array([
            trade_result.strategy_scores.get(name, 0.0) 
            for name in self.strategy_names
        ])
        
        # Normalize scores
        score_sum = np.sum(np.abs(scores)) + 1e-10
        norm_scores = scores / score_sum
        
        # Compute gradient based on trade outcome
        pnl = trade_result.pnl_pct
        
        if trade_result.is_win:
            # Reward: increase weights of contributing strategies
            # Larger reward for larger wins (up to 2x)
            reward_multiplier = min(2.0, 1.0 + pnl / 2.0)
            gradient = -reward_multiplier * norm_scores * pnl
        else:
            # Penalty: decrease weights of contributing strategies
            # Larger penalty for larger losses (up to 3x)
            penalty_multiplier = min(3.0, 1.0 + abs(pnl) / 1.0)
            gradient = penalty_multiplier * norm_scores * abs(pnl)
        
        return gradient
    
    def update_weights(self, trade_result: LiveTradeResult):
        """Update weights using Adam optimizer with trade feedback."""
        self.t += 1
        
        # Record trade in strategy performance
        primary = trade_result.strategy_name
        if primary in self.performance_history:
            self.performance_history[primary].add_trade(
                trade_result.pnl_pct, trade_result.is_win
            )
        
        # Also credit contributing strategies
        for strat_name, score in trade_result.strategy_scores.items():
            if strat_name in self.performance_history and abs(score) > 0.01:
                # Partial credit based on contribution
                perf = self.performance_history[strat_name]
                if strat_name != primary:
                    perf.add_trade(
                        trade_result.pnl_pct * abs(score), 
                        trade_result.is_win
                    )
        
        # Compute gradient
        gradient = self.compute_gradient(trade_result)
        
        # Adam optimizer update
        self.momentum = self.beta1 * self.momentum + (1 - self.beta1) * gradient
        self.velocity = self.beta2 * self.velocity + (1 - self.beta2) * (gradient ** 2)
        
        # Bias correction
        m_hat = self.momentum / (1 - self.beta1 ** self.t)
        v_hat = self.velocity / (1 - self.beta2 ** self.t)
        
        # Update weights
        self.weights -= self.lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
        
        # Apply constraints and normalize
        self.weights = np.clip(self.weights, self.min_weight, self.max_weight)
        self.weights = self.weights / np.sum(self.weights)  # Normalize to sum=1
        
        # Update weight in performance tracking
        for i, name in enumerate(self.strategy_names):
            if name in self.performance_history:
                self.performance_history[name].weight = self.weights[i]
    
    def rebalance_by_performance(self):
        """Periodic rebalancing based on quality scores."""
        quality_scores = np.array([
            self.performance_history[name].quality_score 
            for name in self.strategy_names
        ])
        
        # Only rebalance if we have enough data
        min_trades = min(
            self.performance_history[name].total_trades 
            for name in self.strategy_names
        )
        if min_trades < 5:
            return
        
        # Compute target weights from quality scores
        # Strategies with higher quality get more weight
        score_sum = np.sum(quality_scores) + 1e-10
        target_weights = quality_scores / score_sum
        
        # Smooth transition (blend 20% toward target)
        blend_factor = 0.2
        self.weights = (1 - blend_factor) * self.weights + blend_factor * target_weights
        
        # Apply constraints
        self.weights = np.clip(self.weights, self.min_weight, self.max_weight)
        self.weights = self.weights / np.sum(self.weights)



# ============================================================================
# FEEDBACK LOOP ENGINE - The Main System
# ============================================================================

class FeedbackLoopEngine:
    """
    Main feedback loop orchestrator.
    
    Flow:
    1. ML Brain generates signals from backtested strategies
    2. Trading Brain executes trades with position sizing
    3. Live results feed back to ML Brain
    4. ML Brain adapts weights and retrains models
    5. Repeat until target metrics achieved
    """
    
    def __init__(self, 
                 db_path: str = "data/feedback_loop.db",
                 weights_path: str = "learned_weights"):
        
        self.db_path = Path(db_path)
        self.weights_path = Path(weights_path)
        self.weights_path.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Strategy registry
        self.strategies = self._load_strategies()
        
        # Adaptive optimizer
        self.optimizer = AdaptiveWeightOptimizer(list(self.strategies.keys()))
        
        # Trade tracking
        self.pending_trades: Dict[str, Dict] = {}  # Open positions
        self.completed_trades: List[LiveTradeResult] = []
        
        # Performance metrics
        self.metrics = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'current_win_rate': 0.0,
            'current_wl_ratio': 0.0,
            'current_sharpe': 0.0,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'best_win_rate': 0.0,
            'target_achieved': False,
            'target_achieved_at': None
        }
        
        # State
        self.is_running = False
        self.last_rebalance = datetime.now()
        self.rebalance_interval = timedelta(hours=1)
        
        # Callbacks
        self.on_trade_complete: Optional[Callable] = None
        self.on_metrics_update: Optional[Callable] = None
        self.on_target_achieved: Optional[Callable] = None
        
        logger.info(f"FeedbackLoopEngine initialized with {len(self.strategies)} strategies")
    
    def _init_database(self):
        """Initialize SQLite database for persistence."""
        self.db_path.parent.mkdir(exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Trade history table
        c.execute('''CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            exit_price REAL,
            entry_time TEXT,
            exit_time TEXT,
            quantity REAL,
            pnl REAL,
            pnl_pct REAL,
            strategy_name TEXT,
            strategy_scores TEXT,
            confidence REAL,
            exit_reason TEXT,
            market_regime TEXT,
            feedback_type TEXT,
            is_win INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Strategy performance table
        c.execute('''CREATE TABLE IF NOT EXISTS strategy_performance (
            strategy_name TEXT PRIMARY KEY,
            weight REAL,
            total_trades INTEGER,
            wins INTEGER,
            losses INTEGER,
            win_rate REAL,
            avg_win REAL,
            avg_loss REAL,
            wl_ratio REAL,
            sharpe_ratio REAL,
            quality_score REAL,
            last_update TEXT
        )''')
        
        # Metrics history table
        c.execute('''CREATE TABLE IF NOT EXISTS metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            total_trades INTEGER,
            win_rate REAL,
            wl_ratio REAL,
            sharpe_ratio REAL,
            total_pnl REAL,
            target_achieved INTEGER
        )''')
        
        conn.commit()
        conn.close()
    
    def _load_strategies(self) -> Dict[str, Dict]:
        """Load strategy definitions."""
        # Default strategies - can be extended
        strategies = {
            # ICT Strategies
            'ict_fvg': {'category': 'ict', 'weight': 0.08, 'enabled': True},
            'ict_order_block': {'category': 'ict', 'weight': 0.08, 'enabled': True},
            'ict_liquidity': {'category': 'ict', 'weight': 0.07, 'enabled': True},
            'ict_mss': {'category': 'ict', 'weight': 0.07, 'enabled': True},
            'ict_killzone': {'category': 'ict', 'weight': 0.06, 'enabled': True},
            
            # Momentum Strategies
            'mom_rsi': {'category': 'momentum', 'weight': 0.06, 'enabled': True},
            'mom_macd': {'category': 'momentum', 'weight': 0.06, 'enabled': True},
            'mom_stoch': {'category': 'momentum', 'weight': 0.05, 'enabled': True},
            
            # Trend Strategies
            'trend_ema_cross': {'category': 'trend', 'weight': 0.06, 'enabled': True},
            'trend_supertrend': {'category': 'trend', 'weight': 0.06, 'enabled': True},
            'trend_adx': {'category': 'trend', 'weight': 0.05, 'enabled': True},
            'trend_ichimoku': {'category': 'trend', 'weight': 0.05, 'enabled': True},
            
            # Volume Strategies
            'vol_vwap': {'category': 'volume', 'weight': 0.05, 'enabled': True},
            'vol_obv': {'category': 'volume', 'weight': 0.04, 'enabled': True},
            
            # Mean Reversion
            'mr_bollinger': {'category': 'mean_revert', 'weight': 0.05, 'enabled': True},
            'mr_rsi_extreme': {'category': 'mean_revert', 'weight': 0.04, 'enabled': True},
            
            # ML Ensemble
            'ml_ensemble': {'category': 'ml', 'weight': 0.07, 'enabled': True},
        }
        
        # Try to load saved weights
        weights_file = self.weights_path / "feedback_weights.pkl"
        if weights_file.exists():
            try:
                with open(weights_file, 'rb') as f:
                    saved = pickle.load(f)
                for name, weight in saved.items():
                    if name in strategies:
                        strategies[name]['weight'] = weight
                logger.info("Loaded saved strategy weights")
            except Exception as e:
                logger.warning(f"Could not load saved weights: {e}")
        
        return strategies
    
    def save_weights(self):
        """Save current strategy weights."""
        weights = self.optimizer.get_weights()
        
        weights_file = self.weights_path / "feedback_weights.pkl"
        with open(weights_file, 'wb') as f:
            pickle.dump(weights, f)
        
        # Also save as JSON for readability
        json_file = self.weights_path / "feedback_weights.json"
        with open(json_file, 'w') as f:
            json.dump(weights, f, indent=2)
        
        logger.info("Saved strategy weights")
    

    # ========================================================================
    # SIGNAL GENERATION (ML Brain Interface)
    # ========================================================================
    
    def get_ml_signal(self, symbol: str, data: pd.DataFrame) -> Dict:
        """
        Get weighted signal from ML Brain strategies.
        
        Returns:
            {
                'action': 'BUY'|'SELL'|'HOLD',
                'confidence': float,
                'strategy_scores': Dict[str, float],
                'primary_strategy': str,
                'regime': str
            }
        """
        weights = self.optimizer.get_weights()
        strategy_scores = {}
        strategy_signals = {}  # BUY: +1, SELL: -1, HOLD: 0
        
        # Compute each strategy's signal
        for strat_name, strat_config in self.strategies.items():
            if not strat_config['enabled']:
                continue
            
            try:
                score, signal = self._compute_strategy_signal(strat_name, data)
                strategy_scores[strat_name] = score
                strategy_signals[strat_name] = signal
            except Exception as e:
                logger.debug(f"Strategy {strat_name} error: {e}")
                strategy_scores[strat_name] = 0.0
                strategy_signals[strat_name] = 0
        
        # Weighted ensemble signal
        weighted_signal = 0.0
        weighted_confidence = 0.0
        
        for strat_name, score in strategy_scores.items():
            w = weights.get(strat_name, 0.0)
            sig = strategy_signals.get(strat_name, 0)
            weighted_signal += w * sig * abs(score)
            weighted_confidence += w * abs(score)
        
        # Determine action
        if weighted_signal > CONFIDENCE_THRESHOLD * weighted_confidence:
            action = 'BUY'
            confidence = min(0.95, weighted_signal / max(0.001, weighted_confidence))
        elif weighted_signal < -CONFIDENCE_THRESHOLD * weighted_confidence:
            action = 'SELL'
            confidence = min(0.95, abs(weighted_signal) / max(0.001, weighted_confidence))
        else:
            action = 'HOLD'
            confidence = 1.0 - abs(weighted_signal) / max(0.001, weighted_confidence)
        
        # Find primary strategy (highest weighted contribution)
        if strategy_scores:
            contributions = {
                k: weights.get(k, 0) * abs(v) 
                for k, v in strategy_scores.items()
            }
            primary = max(contributions, key=contributions.get)
        else:
            primary = 'none'
        
        # Detect regime
        regime = self._detect_regime(data)
        
        return {
            'action': action,
            'confidence': confidence,
            'strategy_scores': strategy_scores,
            'primary_strategy': primary,
            'regime': regime,
            'weighted_signal': weighted_signal
        }
    
    def _compute_strategy_signal(self, name: str, data: pd.DataFrame) -> Tuple[float, int]:
        """Compute signal for a single strategy. Returns (score, direction)."""
        if len(data) < 50:
            return 0.0, 0
        
        close = data['Close'].values
        high = data['High'].values
        low = data['Low'].values
        volume = data['Volume'].values if 'Volume' in data else np.ones_like(close)
        
        # Category-based signal computation
        category = self.strategies[name]['category']
        
        if 'ict' in name:
            return self._ict_signal(name, close, high, low, volume)
        elif 'mom' in name:
            return self._momentum_signal(name, close, high, low)
        elif 'trend' in name:
            return self._trend_signal(name, close, high, low)
        elif 'vol' in name:
            return self._volume_signal(name, close, volume)
        elif 'mr' in name:
            return self._mean_revert_signal(name, close)
        elif 'ml' in name:
            return self._ml_signal(name, data)
        
        return 0.0, 0
    
    def _ict_signal(self, name: str, close: np.ndarray, high: np.ndarray, 
                    low: np.ndarray, volume: np.ndarray) -> Tuple[float, int]:
        """ICT strategy signals."""
        
        if name == 'ict_fvg':
            # Fair Value Gap detection
            for i in range(len(close) - 3, len(close)):
                gap_up = low[i] > high[i-2]  # Bullish FVG
                gap_down = high[i] < low[i-2]  # Bearish FVG
                
                if gap_up:
                    return 0.7, 1  # Bullish signal
                elif gap_down:
                    return 0.7, -1  # Bearish signal
            return 0.0, 0
        
        elif name == 'ict_order_block':
            # Order Block identification
            # Last bearish candle before rally = bullish OB
            # Last bullish candle before drop = bearish OB
            for i in range(len(close) - 5, len(close) - 1):
                candle_return = (close[i] - close[i-1]) / close[i-1]
                next_move = (close[i+1] - close[i]) / close[i]
                
                # Bullish OB: bearish candle followed by strong up
                if candle_return < -0.003 and next_move > 0.01:
                    if close[-1] > close[i]:  # Price above OB
                        return 0.65, 1
                
                # Bearish OB: bullish candle followed by strong down
                if candle_return > 0.003 and next_move < -0.01:
                    if close[-1] < close[i]:  # Price below OB
                        return 0.65, -1
            return 0.0, 0
        
        elif name == 'ict_liquidity':
            # Liquidity sweep detection
            recent_high = np.max(high[-20:-5])
            recent_low = np.min(low[-20:-5])
            
            # Sweep high then reject
            if high[-2] > recent_high and close[-1] < recent_high:
                return 0.75, -1  # Bearish after liquidity sweep
            
            # Sweep low then reject
            if low[-2] < recent_low and close[-1] > recent_low:
                return 0.75, 1  # Bullish after liquidity sweep
            
            return 0.0, 0
        
        elif name == 'ict_mss':
            # Market Structure Shift
            # Break of recent swing high/low with follow through
            swing_high = np.max(high[-15:-5])
            swing_low = np.min(low[-15:-5])
            
            # Bullish MSS
            if close[-1] > swing_high and close[-2] < swing_high:
                return 0.7, 1
            
            # Bearish MSS
            if close[-1] < swing_low and close[-2] > swing_low:
                return 0.7, -1
            
            return 0.0, 0
        
        elif name == 'ict_killzone':
            # Kill zone timing (simplified - check hour)
            hour = datetime.now().hour
            
            # London: 2-5 AM EST, NY Open: 8-11 AM EST, NY Close: 2-4 PM EST
            in_killzone = hour in [2, 3, 4, 5, 8, 9, 10, 11, 14, 15, 16]
            
            if not in_killzone:
                return 0.0, 0
            
            # Simple momentum in killzone
            momentum = (close[-1] - close[-10]) / close[-10]
            if momentum > 0.002:
                return 0.5, 1
            elif momentum < -0.002:
                return 0.5, -1
            return 0.3, 0
        
        return 0.0, 0
    
    def _momentum_signal(self, name: str, close: np.ndarray, 
                         high: np.ndarray, low: np.ndarray) -> Tuple[float, int]:
        """Momentum strategy signals."""
        
        if name == 'mom_rsi':
            rsi = self._calc_rsi(close, 14)
            if rsi < 30:
                return 0.7, 1  # Oversold
            elif rsi > 70:
                return 0.7, -1  # Overbought
            return 0.3, 0
        
        elif name == 'mom_macd':
            macd, signal, hist = self._calc_macd(close)
            if hist[-1] > 0 and hist[-2] < 0:  # Bullish cross
                return 0.65, 1
            elif hist[-1] < 0 and hist[-2] > 0:  # Bearish cross
                return 0.65, -1
            return abs(hist[-1]) / (np.std(hist) + 1e-10), np.sign(hist[-1])
        
        elif name == 'mom_stoch':
            k, d = self._calc_stochastic(close, high, low)
            if k[-1] < 20 and k[-1] > d[-1]:
                return 0.65, 1  # Oversold + bullish cross
            elif k[-1] > 80 and k[-1] < d[-1]:
                return 0.65, -1  # Overbought + bearish cross
            return 0.3, 0
        
        return 0.0, 0
    

    def _trend_signal(self, name: str, close: np.ndarray,
                      high: np.ndarray, low: np.ndarray) -> Tuple[float, int]:
        """Trend strategy signals."""
        
        if name == 'trend_ema_cross':
            ema_fast = self._calc_ema(close, 12)
            ema_slow = self._calc_ema(close, 26)
            
            if ema_fast[-1] > ema_slow[-1] and ema_fast[-2] < ema_slow[-2]:
                return 0.7, 1  # Bullish cross
            elif ema_fast[-1] < ema_slow[-1] and ema_fast[-2] > ema_slow[-2]:
                return 0.7, -1  # Bearish cross
            
            # Trend strength
            spread = (ema_fast[-1] - ema_slow[-1]) / close[-1]
            return min(0.6, abs(spread) * 50), np.sign(spread)
        
        elif name == 'trend_supertrend':
            atr = self._calc_atr(close, high, low, 10)
            multiplier = 3.0
            
            mid = (high + low) / 2
            upper = mid + multiplier * atr
            lower = mid - multiplier * atr
            
            # Simplified supertrend
            if close[-1] > upper[-1]:
                return 0.7, 1
            elif close[-1] < lower[-1]:
                return 0.7, -1
            return 0.3, 0
        
        elif name == 'trend_adx':
            adx, plus_di, minus_di = self._calc_adx(close, high, low, 14)
            
            if adx[-1] > 25:  # Strong trend
                if plus_di[-1] > minus_di[-1]:
                    return 0.7, 1
                else:
                    return 0.7, -1
            return 0.2, 0  # Weak trend
        
        elif name == 'trend_ichimoku':
            tenkan = (np.max(high[-9:]) + np.min(low[-9:])) / 2
            kijun = (np.max(high[-26:]) + np.min(low[-26:])) / 2
            
            if close[-1] > tenkan and close[-1] > kijun:
                return 0.6, 1
            elif close[-1] < tenkan and close[-1] < kijun:
                return 0.6, -1
            return 0.3, 0
        
        return 0.0, 0
    
    def _volume_signal(self, name: str, close: np.ndarray, 
                       volume: np.ndarray) -> Tuple[float, int]:
        """Volume strategy signals."""
        
        if name == 'vol_vwap':
            typical_price = close  # Simplified
            vwap = np.cumsum(typical_price * volume) / np.cumsum(volume)
            
            deviation = (close[-1] - vwap[-1]) / vwap[-1]
            
            if deviation < -0.02:  # Below VWAP
                return 0.6, 1  # Mean revert up
            elif deviation > 0.02:  # Above VWAP
                return 0.6, -1  # Mean revert down
            return 0.3, 0
        
        elif name == 'vol_obv':
            obv = np.zeros_like(close)
            for i in range(1, len(close)):
                if close[i] > close[i-1]:
                    obv[i] = obv[i-1] + volume[i]
                elif close[i] < close[i-1]:
                    obv[i] = obv[i-1] - volume[i]
                else:
                    obv[i] = obv[i-1]
            
            obv_trend = (obv[-1] - obv[-10]) / (np.std(obv[-20:]) + 1)
            
            if obv_trend > 1:
                return 0.55, 1
            elif obv_trend < -1:
                return 0.55, -1
            return 0.3, 0
        
        return 0.0, 0
    
    def _mean_revert_signal(self, name: str, close: np.ndarray) -> Tuple[float, int]:
        """Mean reversion signals."""
        
        if name == 'mr_bollinger':
            sma = np.mean(close[-20:])
            std = np.std(close[-20:])
            upper = sma + 2 * std
            lower = sma - 2 * std
            
            if close[-1] < lower:
                return 0.7, 1  # Below lower band
            elif close[-1] > upper:
                return 0.7, -1  # Above upper band
            
            # Position in band
            pct_b = (close[-1] - lower) / (upper - lower + 1e-10)
            if pct_b < 0.2:
                return 0.5, 1
            elif pct_b > 0.8:
                return 0.5, -1
            return 0.2, 0
        
        elif name == 'mr_rsi_extreme':
            rsi = self._calc_rsi(close, 7)  # Shorter RSI for extremes
            
            if rsi < 20:
                return 0.75, 1
            elif rsi > 80:
                return 0.75, -1
            return 0.2, 0
        
        return 0.0, 0
    
    def _ml_signal(self, name: str, data: pd.DataFrame) -> Tuple[float, int]:
        """ML ensemble signal."""
        # Use multiple technical features for simple ML-like scoring
        close = data['Close'].values
        
        features = []
        
        # RSI
        rsi = self._calc_rsi(close, 14)
        features.append((rsi - 50) / 50)
        
        # MACD
        macd, signal, hist = self._calc_macd(close)
        features.append(np.tanh(hist[-1] / (np.std(hist) + 1e-10)))
        
        # Trend
        ema12 = self._calc_ema(close, 12)
        ema26 = self._calc_ema(close, 26)
        trend = (ema12[-1] - ema26[-1]) / close[-1]
        features.append(np.tanh(trend * 100))
        
        # Momentum
        mom = (close[-1] - close[-10]) / close[-10]
        features.append(np.tanh(mom * 20))
        
        # Ensemble score
        score = np.mean(features)
        confidence = min(0.8, abs(score))
        
        if score > 0.2:
            return confidence, 1
        elif score < -0.2:
            return confidence, -1
        return 0.3, 0
    
    def _detect_regime(self, data: pd.DataFrame) -> str:
        """Detect market regime."""
        if len(data) < 50:
            return 'unknown'
        
        close = data['Close'].values
        
        # Volatility
        returns = np.diff(close) / close[:-1]
        vol = np.std(returns[-20:]) * np.sqrt(252)
        
        # Trend
        ema20 = self._calc_ema(close, 20)
        ema50 = self._calc_ema(close, 50)
        
        if ema20[-1] > ema50[-1]:
            if vol > 0.25:
                return 'volatile_uptrend'
            return 'uptrend'
        else:
            if vol > 0.25:
                return 'volatile_downtrend'
            return 'downtrend'
    

    # ========================================================================
    # TECHNICAL INDICATOR HELPERS
    # ========================================================================
    
    def _calc_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI."""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calc_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA."""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
        return ema
    
    def _calc_macd(self, prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate MACD."""
        ema12 = self._calc_ema(prices, 12)
        ema26 = self._calc_ema(prices, 26)
        macd = ema12 - ema26
        signal = self._calc_ema(macd, 9)
        hist = macd - signal
        return macd, signal, hist
    
    def _calc_atr(self, close: np.ndarray, high: np.ndarray, 
                  low: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate ATR."""
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        tr = np.concatenate([[tr[0]], tr])
        atr = np.zeros_like(close)
        atr[period] = np.mean(tr[:period])
        
        for i in range(period + 1, len(close)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        
        return atr
    
    def _calc_stochastic(self, close: np.ndarray, high: np.ndarray,
                         low: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate Stochastic %K and %D."""
        k = np.zeros_like(close)
        
        for i in range(period, len(close)):
            low_min = np.min(low[i-period:i+1])
            high_max = np.max(high[i-period:i+1])
            
            if high_max - low_min != 0:
                k[i] = 100 * (close[i] - low_min) / (high_max - low_min)
            else:
                k[i] = 50
        
        d = self._calc_ema(k, 3)
        return k, d
    
    def _calc_adx(self, close: np.ndarray, high: np.ndarray,
                  low: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate ADX, +DI, -DI."""
        n = len(close)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)
        
        for i in range(1, n):
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
        
        atr = self._calc_atr(close, high, low, period)
        
        plus_di = 100 * self._calc_ema(plus_dm, period) / (atr + 1e-10)
        minus_di = 100 * self._calc_ema(minus_dm, period) / (atr + 1e-10)
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = self._calc_ema(dx, period)
        
        return adx, plus_di, minus_di
    
    # ========================================================================
    # FEEDBACK PROCESSING (Trading Brain Reports Back)
    # ========================================================================
    
    def record_trade_entry(self, trade_id: str, symbol: str, direction: str,
                          entry_price: float, quantity: float, 
                          signal: Dict) -> None:
        """Record trade entry from Trading Brain."""
        self.pending_trades[trade_id] = {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'entry_time': datetime.now(),
            'quantity': quantity,
            'signal': signal
        }
        logger.info(f"Trade entry recorded: {trade_id} {direction} {symbol} @ {entry_price}")
    
    def record_trade_exit(self, trade_id: str, exit_price: float, 
                         exit_reason: str) -> Optional[LiveTradeResult]:
        """Record trade exit and process feedback."""
        if trade_id not in self.pending_trades:
            logger.warning(f"Trade {trade_id} not found in pending trades")
            return None
        
        entry = self.pending_trades.pop(trade_id)
        signal = entry['signal']
        
        # Calculate P&L
        if entry['direction'] == 'LONG':
            pnl = (exit_price - entry['entry_price']) * entry['quantity']
            pnl_pct = (exit_price - entry['entry_price']) / entry['entry_price'] * 100
        else:
            pnl = (entry['entry_price'] - exit_price) * entry['quantity']
            pnl_pct = (entry['entry_price'] - exit_price) / entry['entry_price'] * 100
        
        # Create trade result
        result = LiveTradeResult(
            trade_id=trade_id,
            symbol=entry['symbol'],
            direction=entry['direction'],
            entry_price=entry['entry_price'],
            exit_price=exit_price,
            entry_time=entry['entry_time'],
            exit_time=datetime.now(),
            quantity=entry['quantity'],
            pnl=pnl,
            pnl_pct=pnl_pct,
            strategy_name=signal.get('primary_strategy', 'unknown'),
            strategy_scores=signal.get('strategy_scores', {}),
            confidence=signal.get('confidence', 0.5),
            exit_reason=exit_reason,
            market_regime=signal.get('regime', 'unknown')
        )
        
        # Process feedback
        self._process_feedback(result)
        
        return result
    
    def _process_feedback(self, result: LiveTradeResult):
        """Process trade feedback and update ML Brain."""
        # Store trade
        self.completed_trades.append(result)
        
        # Update optimizer with new trade
        self.optimizer.update_weights(result)
        
        # Update metrics
        self.metrics['total_trades'] += 1
        self.metrics['total_pnl'] += result.pnl
        
        if result.is_win:
            self.metrics['wins'] += 1
            self.metrics['consecutive_wins'] += 1
            self.metrics['consecutive_losses'] = 0
        else:
            self.metrics['losses'] += 1
            self.metrics['consecutive_losses'] += 1
            self.metrics['consecutive_wins'] = 0
        
        # Recalculate metrics
        self._recalculate_metrics()
        
        # Save to database
        self._save_trade_to_db(result)
        
        # Check if targets achieved
        self._check_targets()
        
        # Periodic rebalancing
        if datetime.now() - self.last_rebalance > self.rebalance_interval:
            self.optimizer.rebalance_by_performance()
            self.save_weights()
            self.last_rebalance = datetime.now()
        
        # Trigger callbacks
        if self.on_trade_complete:
            self.on_trade_complete(result)
        if self.on_metrics_update:
            self.on_metrics_update(self.metrics)
    

    def _recalculate_metrics(self):
        """Recalculate performance metrics."""
        n = self.metrics['total_trades']
        
        if n == 0:
            return
        
        # Win rate
        self.metrics['current_win_rate'] = self.metrics['wins'] / n
        
        # W/L ratio
        if self.metrics['losses'] > 0:
            winning_trades = [t for t in self.completed_trades[-100:] if t.is_win]
            losing_trades = [t for t in self.completed_trades[-100:] if not t.is_win]
            
            avg_win = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
            avg_loss = abs(np.mean([t.pnl_pct for t in losing_trades])) if losing_trades else 0.001
            self.metrics['current_wl_ratio'] = avg_win / avg_loss
        
        # Sharpe ratio
        if len(self.completed_trades) >= 10:
            returns = [t.pnl_pct for t in self.completed_trades[-50:]]
            if np.std(returns) > 0:
                self.metrics['current_sharpe'] = np.mean(returns) / np.std(returns) * np.sqrt(252)
        
        # Track best
        if self.metrics['current_win_rate'] > self.metrics['best_win_rate']:
            self.metrics['best_win_rate'] = self.metrics['current_win_rate']
    
    def _check_targets(self):
        """Check if target metrics achieved."""
        if self.metrics['target_achieved']:
            return
        
        wr = self.metrics['current_win_rate']
        wl = self.metrics['current_wl_ratio']
        n = self.metrics['total_trades']
        
        # Need minimum trades and hit both targets
        if n >= MIN_TRADES_FOR_UPDATE and wr >= TARGET_WIN_RATE and wl >= TARGET_WL_RATIO:
            self.metrics['target_achieved'] = True
            self.metrics['target_achieved_at'] = datetime.now().isoformat()
            
            logger.info("=" * 60)
            logger.info("🎯 TARGET METRICS ACHIEVED!")
            logger.info(f"   Win Rate: {wr:.1%} (target: {TARGET_WIN_RATE:.0%})")
            logger.info(f"   W/L Ratio: {wl:.2f}:1 (target: {TARGET_WL_RATIO:.0f}:1)")
            logger.info(f"   Total Trades: {n}")
            logger.info("=" * 60)
            
            if self.on_target_achieved:
                self.on_target_achieved(self.metrics)
            
            # Save successful weights
            self.save_weights()
    
    def _save_trade_to_db(self, result: LiveTradeResult):
        """Save trade to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO trades (
            trade_id, symbol, direction, entry_price, exit_price,
            entry_time, exit_time, quantity, pnl, pnl_pct,
            strategy_name, strategy_scores, confidence, exit_reason,
            market_regime, feedback_type, is_win
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            result.trade_id,
            result.symbol,
            result.direction,
            result.entry_price,
            result.exit_price,
            result.entry_time.isoformat(),
            result.exit_time.isoformat(),
            result.quantity,
            result.pnl,
            result.pnl_pct,
            result.strategy_name,
            json.dumps(result.strategy_scores),
            result.confidence,
            result.exit_reason,
            result.market_regime,
            result.feedback_type.value,
            1 if result.is_win else 0
        ))
        
        conn.commit()
        conn.close()
    
    def save_metrics_snapshot(self):
        """Save current metrics to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''INSERT INTO metrics_history (
            timestamp, total_trades, win_rate, wl_ratio, sharpe_ratio, 
            total_pnl, target_achieved
        ) VALUES (?, ?, ?, ?, ?, ?, ?)''', (
            datetime.now().isoformat(),
            self.metrics['total_trades'],
            self.metrics['current_win_rate'],
            self.metrics['current_wl_ratio'],
            self.metrics['current_sharpe'],
            self.metrics['total_pnl'],
            1 if self.metrics['target_achieved'] else 0
        ))
        
        conn.commit()
        conn.close()
    
    def get_metrics_report(self) -> Dict:
        """Get current metrics report."""
        strategy_stats = {}
        for name, perf in self.optimizer.performance_history.items():
            strategy_stats[name] = {
                'weight': round(perf.weight, 4),
                'total_trades': perf.total_trades,
                'win_rate': round(perf.win_rate, 3),
                'wl_ratio': round(perf.wl_ratio, 2),
                'sharpe': round(perf.sharpe_ratio, 2),
                'quality_score': round(perf.quality_score, 3)
            }
        
        return {
            'overall': {
                'total_trades': self.metrics['total_trades'],
                'wins': self.metrics['wins'],
                'losses': self.metrics['losses'],
                'win_rate': round(self.metrics['current_win_rate'], 3),
                'wl_ratio': round(self.metrics['current_wl_ratio'], 2),
                'sharpe': round(self.metrics['current_sharpe'], 2),
                'total_pnl': round(self.metrics['total_pnl'], 2),
                'target_achieved': self.metrics['target_achieved'],
                'target_win_rate': TARGET_WIN_RATE,
                'target_wl_ratio': TARGET_WL_RATIO
            },
            'strategy_stats': strategy_stats,
            'pending_trades': len(self.pending_trades),
            'weights': self.optimizer.get_weights()
        }
    
    def print_status(self):
        """Print current status."""
        m = self.metrics
        
        # Progress bars
        wr_pct = min(100, m['current_win_rate'] / TARGET_WIN_RATE * 100)
        wl_pct = min(100, m['current_wl_ratio'] / TARGET_WL_RATIO * 100)
        
        wr_bar = "█" * int(wr_pct / 5) + "░" * (20 - int(wr_pct / 5))
        wl_bar = "█" * int(wl_pct / 5) + "░" * (20 - int(wl_pct / 5))
        
        print("\n" + "=" * 60)
        print("📊 FEEDBACK LOOP STATUS")
        print("=" * 60)
        print(f"Total Trades: {m['total_trades']}")
        print(f"Wins: {m['wins']} | Losses: {m['losses']}")
        print(f"\nWin Rate:  {m['current_win_rate']:.1%} [{wr_bar}] Target: {TARGET_WIN_RATE:.0%}")
        print(f"W/L Ratio: {m['current_wl_ratio']:.2f}:1 [{wl_bar}] Target: {TARGET_WL_RATIO:.0f}:1")
        print(f"Sharpe:    {m['current_sharpe']:.2f}")
        print(f"Total P&L: {m['total_pnl']:.2f}%")
        
        if m['target_achieved']:
            print("\n🎯 TARGETS ACHIEVED! ✓")
        else:
            print(f"\n⏳ Progress: WR {wr_pct:.0f}% | WL {wl_pct:.0f}%")
        
        print("=" * 60)




# ============================================================================
# BACKTESTING ENGINE
# ============================================================================

class BacktestEngine:
    """
    Fast backtesting to train the ML Brain before live trading.
    """
    
    def __init__(self, feedback_loop: FeedbackLoopEngine):
        self.loop = feedback_loop
        self.trade_counter = 0
    
    def run_backtest(self, data: pd.DataFrame, symbol: str = "TEST",
                    initial_capital: float = 100000,
                    position_size_pct: float = 0.1,
                    tp_pct: float = 2.0,
                    sl_pct: float = 1.0) -> Dict:
        """
        Run backtest on historical data.
        
        Args:
            data: DataFrame with OHLCV data
            symbol: Symbol name
            initial_capital: Starting capital
            position_size_pct: Position size as % of capital
            tp_pct: Take profit %
            sl_pct: Stop loss %
        """
        if len(data) < 100:
            return {'error': 'Insufficient data'}
        
        capital = initial_capital
        position = None
        trades = []
        
        # Iterate through data
        for i in range(50, len(data) - 1):
            current_data = data.iloc[:i+1]
            current_price = data.iloc[i]['Close']
            next_price = data.iloc[i+1]['Close']
            
            # Check for exit if in position
            if position:
                # Calculate current P&L
                if position['direction'] == 'LONG':
                    current_pnl_pct = (current_price - position['entry']) / position['entry'] * 100
                else:
                    current_pnl_pct = (position['entry'] - current_price) / position['entry'] * 100
                
                exit_reason = None
                exit_price = current_price
                
                # Check TP/SL
                if current_pnl_pct >= tp_pct:
                    exit_reason = 'TP_HIT'
                elif current_pnl_pct <= -sl_pct:
                    exit_reason = 'SL_HIT'
                
                if exit_reason:
                    # Record exit
                    result = self.loop.record_trade_exit(
                        position['trade_id'], exit_price, exit_reason
                    )
                    if result:
                        trades.append(result)
                        capital += result.pnl * position['quantity']
                    position = None
            
            # Get signal if no position
            if position is None:
                signal = self.loop.get_ml_signal(symbol, current_data)
                
                if signal['action'] in ['BUY', 'SELL'] and signal['confidence'] > CONFIDENCE_THRESHOLD:
                    # Enter position
                    self.trade_counter += 1
                    trade_id = f"BT_{symbol}_{self.trade_counter}"
                    quantity = (capital * position_size_pct) / current_price
                    direction = 'LONG' if signal['action'] == 'BUY' else 'SHORT'
                    
                    position = {
                        'trade_id': trade_id,
                        'direction': direction,
                        'entry': current_price,
                        'quantity': quantity
                    }
                    
                    self.loop.record_trade_entry(
                        trade_id, symbol, direction, current_price, quantity, signal
                    )
        
        # Close any open position at end
        if position:
            result = self.loop.record_trade_exit(
                position['trade_id'], data.iloc[-1]['Close'], 'END_OF_DATA'
            )
            if result:
                trades.append(result)
        
        return {
            'total_trades': len(trades),
            'final_capital': capital,
            'return_pct': (capital - initial_capital) / initial_capital * 100,
            'metrics': self.loop.get_metrics_report()
        }


# ============================================================================
# LIVE TRADING BRAIN (Enhanced)
# ============================================================================

class LiveTradingBrain:
    """
    Trading brain that executes trades and reports back to ML Brain.
    """
    
    def __init__(self, feedback_loop: FeedbackLoopEngine, 
                 broker_adapter = None,
                 paper_mode: bool = True):
        self.loop = feedback_loop
        self.broker = broker_adapter
        self.paper_mode = paper_mode
        
        self.trade_counter = 0
        self.active_positions: Dict[str, Dict] = {}
        
        # Risk parameters
        self.max_positions = 5
        self.position_size_pct = 0.1
        self.default_tp_pct = 2.0
        self.default_sl_pct = 1.0
        
        # Adaptive risk based on performance
        self.min_confidence = CONFIDENCE_THRESHOLD
    
    def evaluate_and_trade(self, symbol: str, data: pd.DataFrame,
                          current_price: float = None) -> Optional[Dict]:
        """
        Evaluate symbol and potentially enter/exit trades.
        """
        if len(data) < 50:
            return None
        
        if current_price is None:
            current_price = data.iloc[-1]['Close']
        
        # Check existing position
        if symbol in self.active_positions:
            return self._manage_position(symbol, current_price)
        
        # Check if we can take new positions
        if len(self.active_positions) >= self.max_positions:
            return {'action': 'HOLD', 'reason': 'Max positions reached'}
        
        # Get ML signal
        signal = self.loop.get_ml_signal(symbol, data)
        
        # Adjust confidence threshold based on recent performance
        adjusted_threshold = self._get_adjusted_threshold()
        
        if signal['confidence'] < adjusted_threshold:
            return {'action': 'HOLD', 'reason': 'Below confidence threshold'}
        
        if signal['action'] in ['BUY', 'SELL']:
            return self._enter_trade(symbol, signal, current_price)
        
        return {'action': 'HOLD', 'reason': 'No signal'}
    
    def _get_adjusted_threshold(self) -> float:
        """Adjust confidence threshold based on performance."""
        metrics = self.loop.metrics
        
        # If losing, be more conservative
        if metrics['consecutive_losses'] > 3:
            return min(0.85, self.min_confidence + 0.05 * metrics['consecutive_losses'])
        
        # If winning, can be slightly more aggressive
        if metrics['consecutive_wins'] > 3:
            return max(0.5, self.min_confidence - 0.02 * metrics['consecutive_wins'])
        
        return self.min_confidence
    
    def _enter_trade(self, symbol: str, signal: Dict, 
                     current_price: float) -> Dict:
        """Enter a new trade."""
        self.trade_counter += 1
        trade_id = f"LIVE_{symbol}_{self.trade_counter}_{int(time.time())}"
        
        direction = 'LONG' if signal['action'] == 'BUY' else 'SHORT'
        
        # Calculate position size (can be adjusted based on confidence)
        size_multiplier = min(1.5, 0.8 + signal['confidence'] * 0.7)
        position_size = self.position_size_pct * size_multiplier
        quantity = 100  # Simplified for paper trading
        
        # Calculate TP/SL
        tp_price = current_price * (1 + self.default_tp_pct/100) if direction == 'LONG' else \
                   current_price * (1 - self.default_tp_pct/100)
        sl_price = current_price * (1 - self.default_sl_pct/100) if direction == 'LONG' else \
                   current_price * (1 + self.default_sl_pct/100)
        
        # Record position
        self.active_positions[symbol] = {
            'trade_id': trade_id,
            'direction': direction,
            'entry_price': current_price,
            'quantity': quantity,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'signal': signal
        }
        
        # Report to feedback loop
        self.loop.record_trade_entry(
            trade_id, symbol, direction, current_price, quantity, signal
        )
        
        logger.info(f"📈 TRADE ENTERED: {direction} {symbol} @ {current_price}")
        logger.info(f"   TP: {tp_price:.2f} | SL: {sl_price:.2f} | Conf: {signal['confidence']:.2f}")
        
        return {
            'action': 'ENTERED',
            'trade_id': trade_id,
            'direction': direction,
            'entry_price': current_price,
            'tp': tp_price,
            'sl': sl_price
        }
    
    def _manage_position(self, symbol: str, current_price: float) -> Dict:
        """Manage existing position."""
        pos = self.active_positions[symbol]
        
        # Check TP/SL
        exit_reason = None
        
        if pos['direction'] == 'LONG':
            if current_price >= pos['tp_price']:
                exit_reason = 'TP_HIT'
            elif current_price <= pos['sl_price']:
                exit_reason = 'SL_HIT'
        else:  # SHORT
            if current_price <= pos['tp_price']:
                exit_reason = 'TP_HIT'
            elif current_price >= pos['sl_price']:
                exit_reason = 'SL_HIT'
        
        if exit_reason:
            return self._exit_trade(symbol, current_price, exit_reason)
        
        return {'action': 'HOLD', 'position': pos}
    
    def _exit_trade(self, symbol: str, exit_price: float, 
                    reason: str) -> Dict:
        """Exit a trade."""
        if symbol not in self.active_positions:
            return {'action': 'ERROR', 'reason': 'No position'}
        
        pos = self.active_positions.pop(symbol)
        
        # Report to feedback loop
        result = self.loop.record_trade_exit(pos['trade_id'], exit_price, reason)
        
        if result:
            emoji = "✅" if result.is_win else "❌"
            logger.info(f"{emoji} TRADE CLOSED: {symbol} @ {exit_price} ({reason})")
            logger.info(f"   P&L: {result.pnl_pct:.2f}%")
            
            return {
                'action': 'EXITED',
                'trade_id': pos['trade_id'],
                'exit_price': exit_price,
                'reason': reason,
                'pnl_pct': result.pnl_pct,
                'is_win': result.is_win
            }
        
        return {'action': 'EXITED', 'trade_id': pos['trade_id']}
    
    def force_close_all(self, current_prices: Dict[str, float]):
        """Force close all positions."""
        for symbol in list(self.active_positions.keys()):
            price = current_prices.get(symbol, self.active_positions[symbol]['entry_price'])
            self._exit_trade(symbol, price, 'FORCE_CLOSE')




# ============================================================================
# DATA FETCHER
# ============================================================================

def fetch_data(symbol: str, period: str = "6mo", interval: str = "1h") -> Optional[pd.DataFrame]:
    """Fetch OHLCV data."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        if len(data) > 0:
            return data
    except Exception as e:
        logger.warning(f"yfinance error for {symbol}: {e}")
    
    # Generate synthetic data for testing
    logger.info(f"Generating synthetic data for {symbol}")
    n = 1000
    dates = pd.date_range(end=datetime.now(), periods=n, freq='1h')
    
    base_price = 100
    returns = np.random.randn(n) * 0.01  # 1% daily vol
    prices = base_price * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'Open': prices * (1 - np.abs(np.random.randn(n) * 0.005)),
        'High': prices * (1 + np.abs(np.random.randn(n) * 0.01)),
        'Low': prices * (1 - np.abs(np.random.randn(n) * 0.01)),
        'Close': prices,
        'Volume': np.random.randint(100000, 1000000, n)
    }, index=dates)
    
    return data


# ============================================================================
# MAIN TRAINING LOOP
# ============================================================================

def run_training_loop(symbols: List[str] = None,
                     max_iterations: int = 1000,
                     backtest_first: bool = True) -> FeedbackLoopEngine:
    """
    Main training loop that runs until targets are achieved.
    
    Flow:
    1. Backtest on historical data to build initial weights
    2. Paper trade to refine weights
    3. Continue until 70% WR and 2:1 W/L achieved
    """
    
    if symbols is None:
        symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL', 
                   'AMZN', 'NVDA', 'META', 'TSLA', 'AMD']
    
    # Initialize feedback loop
    loop = FeedbackLoopEngine(
        db_path="data/feedback_loop.db",
        weights_path="learned_weights"
    )
    
    # Callbacks for status updates
    def on_trade(result):
        logger.debug(f"Trade: {result.symbol} {result.pnl_pct:.2f}%")
    
    def on_target():
        logger.info("🎯 TARGETS ACHIEVED! Saving model...")
        loop.save_weights()
    
    loop.on_trade_complete = on_trade
    loop.on_target_achieved = on_target
    
    # Phase 1: Backtest
    if backtest_first:
        logger.info("=" * 60)
        logger.info("PHASE 1: BACKTESTING")
        logger.info("=" * 60)
        
        backtest = BacktestEngine(loop)
        
        for symbol in symbols:
            data = fetch_data(symbol, period="1y", interval="1h")
            if data is not None and len(data) > 100:
                logger.info(f"Backtesting {symbol}...")
                result = backtest.run_backtest(data, symbol)
                
                # Print progress
                loop.print_status()
                
                if loop.metrics['target_achieved']:
                    logger.info("Targets achieved during backtest!")
                    return loop
    
    # Phase 2: Paper Trading Simulation
    logger.info("=" * 60)
    logger.info("PHASE 2: PAPER TRADING SIMULATION")
    logger.info("=" * 60)
    
    trading_brain = LiveTradingBrain(loop, paper_mode=True)
    
    iteration = 0
    status_interval = 50
    
    while not loop.metrics['target_achieved'] and iteration < max_iterations:
        iteration += 1
        
        # Cycle through symbols
        symbol = symbols[iteration % len(symbols)]
        
        # Fetch latest data
        data = fetch_data(symbol, period="3mo", interval="1h")
        if data is None or len(data) < 50:
            continue
        
        # Simulate price movement
        current_idx = min(len(data) - 1, 50 + iteration % (len(data) - 51))
        current_data = data.iloc[:current_idx+1]
        current_price = data.iloc[current_idx]['Close']
        
        # Evaluate and potentially trade
        result = trading_brain.evaluate_and_trade(symbol, current_data, current_price)
        
        # Simulate time passing and price movement for exits
        if trading_brain.active_positions:
            # Advance a few bars
            for j in range(1, min(5, len(data) - current_idx)):
                next_idx = current_idx + j
                if next_idx >= len(data):
                    break
                
                for sym in list(trading_brain.active_positions.keys()):
                    next_price = data.iloc[next_idx]['Close']
                    trading_brain._manage_position(sym, next_price)
        
        # Print status periodically
        if iteration % status_interval == 0:
            loop.print_status()
            loop.save_metrics_snapshot()
            
            # Save weights periodically
            if iteration % (status_interval * 2) == 0:
                loop.save_weights()
    
    # Final status
    loop.print_status()
    loop.save_weights()
    
    return loop


# ============================================================================
# EXPORTS AND GLOBAL ACCESS
# ============================================================================

_global_loop = None

def get_feedback_loop() -> FeedbackLoopEngine:
    """Get or create global feedback loop."""
    global _global_loop
    if _global_loop is None:
        _global_loop = FeedbackLoopEngine()
    return _global_loop


def get_ml_signal(symbol: str, data: pd.DataFrame) -> Dict:
    """Convenience function to get ML signal."""
    return get_feedback_loop().get_ml_signal(symbol, data)


def record_trade_result(trade_id: str, exit_price: float, exit_reason: str):
    """Record a trade result from external source."""
    return get_feedback_loop().record_trade_exit(trade_id, exit_price, exit_reason)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("QUANTBRAIN FEEDBACK LOOP - ML Brain ↔ Trading Brain")
    print("Target: 70% Win Rate | 2:1 W/L Ratio")
    print("=" * 60)
    
    # Run the training loop
    loop = run_training_loop(
        symbols=['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA'],
        max_iterations=500,
        backtest_first=True
    )
    
    # Print final report
    report = loop.get_metrics_report()
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(json.dumps(report['overall'], indent=2))
    print("\nTop 5 Strategies by Quality Score:")
    
    sorted_strats = sorted(
        report['strategy_stats'].items(),
        key=lambda x: x[1]['quality_score'],
        reverse=True
    )[:5]
    
    for name, stats in sorted_strats:
        print(f"  {name}: WR={stats['win_rate']:.1%} W/L={stats['wl_ratio']:.1f} "
              f"Quality={stats['quality_score']:.3f}")
