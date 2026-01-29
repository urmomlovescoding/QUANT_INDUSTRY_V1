"""
Base Strategy Framework
=======================
Abstract base class and utilities for building trading strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    LONG = 1
    SHORT = -1
    FLAT = 0
    HOLD = None  # No change


@dataclass
class Signal:
    """Trading signal with metadata"""
    symbol: str
    signal_type: SignalType
    strength: float = 1.0  # 0-1 confidence/sizing
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def position_size(self) -> float:
        """Returns position size (-1 to 1)"""
        if self.signal_type == SignalType.HOLD:
            return None
        return self.signal_type.value * self.strength


@dataclass
class StrategyConfig:
    """Configuration for strategy execution"""
    # Universe
    symbols: List[str] = field(default_factory=list)
    
    # Risk limits
    max_position_size: float = 0.1  # 10% max per position
    max_portfolio_leverage: float = 1.0  # No leverage
    max_drawdown_limit: float = 0.2  # 20% circuit breaker
    
    # Execution
    min_trade_value: float = 100  # Minimum trade size
    rebalance_frequency: str = "1D"  # How often to rebalance
    
    # Strategy-specific params
    params: Dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    Subclasses must implement:
    - generate_signals(data) -> Dict[str, Signal]
    - get_required_history() -> int (bars needed)
    
    Optional overrides:
    - on_data(data) -> Any preprocessing
    - validate_params() -> bool
    """
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.params = config.params
        self._state: Dict[str, Any] = {}
        self._history: List[Dict] = []
        
        if not self.validate_params():
            raise ValueError(f"Invalid parameters for {self.__class__.__name__}")
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Strategy description"""
        pass
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        """
        Generate trading signals from market data.
        
        Args:
            data: DataFrame with OHLCV data, columns are symbols
            
        Returns:
            Dict mapping symbol to Signal
        """
        pass
    
    @abstractmethod
    def get_required_history(self) -> int:
        """Return number of bars needed for signal generation"""
        pass
    
    def validate_params(self) -> bool:
        """Validate strategy parameters. Override for custom validation."""
        return True
    
    def on_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocessing hook called before signal generation.
        Override to add indicators, clean data, etc.
        """
        return data
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get persistent state value"""
        return self._state.get(key, default)
    
    def set_state(self, key: str, value: Any):
        """Set persistent state value"""
        self._state[key] = value
    
    def reset(self):
        """Reset strategy state"""
        self._state = {}
        self._history = []
    
    def __call__(self, data: pd.DataFrame) -> Dict[str, Signal]:
        """Execute strategy on data"""
        # Preprocess
        processed_data = self.on_data(data)
        
        # Check history requirements
        required = self.get_required_history()
        if len(processed_data) < required:
            logger.warning(f"{self.name}: Insufficient data ({len(processed_data)} < {required})")
            return {}
        
        # Generate signals
        signals = self.generate_signals(processed_data)
        
        # Apply position limits
        for symbol, signal in signals.items():
            if signal.signal_type != SignalType.HOLD:
                signal.strength = min(signal.strength, self.config.max_position_size)
        
        return signals


# =============================================================================
# Technical Indicator Utilities
# =============================================================================

def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD indicator"""
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    """Bollinger Bands"""
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def zscore(series: pd.Series, period: int) -> pd.Series:
    """Rolling Z-Score"""
    mean = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return (series - mean) / std


def returns(series: pd.Series, period: int = 1) -> pd.Series:
    """Period returns"""
    return series.pct_change(period)


def log_returns(series: pd.Series, period: int = 1) -> pd.Series:
    """Log returns"""
    return np.log(series / series.shift(period))


def volatility(series: pd.Series, period: int = 20, annualize: bool = True) -> pd.Series:
    """Rolling volatility"""
    vol = series.pct_change().rolling(window=period).std()
    if annualize:
        vol *= np.sqrt(252)
    return vol


def drawdown(equity: pd.Series) -> pd.Series:
    """Calculate drawdown series"""
    peak = equity.expanding().max()
    return (equity - peak) / peak


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.02, periods: int = 252) -> float:
    """Calculate Sharpe ratio"""
    excess_returns = returns - risk_free / periods
    if returns.std() == 0:
        return 0
    return np.sqrt(periods) * excess_returns.mean() / returns.std()
