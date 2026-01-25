"""
QUANT INDUSTRY - Backtest Strategies
Pre-built trading strategies for backtesting
"""

import logging
from abc import ABC, abstractmethod
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class Strategy(ABC):
    """Base strategy class"""

    def __init__(self, name: str = "BaseStrategy"):
        self.name = name

    @abstractmethod
    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        """
        Generate trading signals

        Returns:
            Array of signals: 1 = buy, -1 = sell, 0 = hold
        """
        pass


class MACrossoverStrategy(Strategy):
    """
    Moving Average Crossover Strategy

    Buy when fast MA crosses above slow MA
    Sell when fast MA crosses below slow MA
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        super().__init__(name=f"MA_Crossover_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        n = len(closes)
        signals = np.zeros(n)

        if n < self.slow_period:
            return signals

        # Calculate MAs
        fast_ma = np.full(n, np.nan)
        slow_ma = np.full(n, np.nan)

        for i in range(self.fast_period - 1, n):
            fast_ma[i] = np.mean(closes[i - self.fast_period + 1:i + 1])

        for i in range(self.slow_period - 1, n):
            slow_ma[i] = np.mean(closes[i - self.slow_period + 1:i + 1])

        # Generate signals
        for i in range(self.slow_period, n):
            if np.isnan(fast_ma[i]) or np.isnan(slow_ma[i]):
                continue
            if np.isnan(fast_ma[i - 1]) or np.isnan(slow_ma[i - 1]):
                continue

            # Crossover
            if fast_ma[i] > slow_ma[i] and fast_ma[i - 1] <= slow_ma[i - 1]:
                signals[i] = 1  # Buy
            elif fast_ma[i] < slow_ma[i] and fast_ma[i - 1] >= slow_ma[i - 1]:
                signals[i] = -1  # Sell

        return signals


class RSIStrategy(Strategy):
    """
    RSI Strategy

    Buy when RSI crosses below oversold level
    Sell when RSI crosses above overbought level
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30,
        overbought: float = 70
    ):
        super().__init__(name=f"RSI_{period}_{oversold}_{overbought}")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        n = len(closes)
        signals = np.zeros(n)

        if n < self.period + 1:
            return signals

        # Calculate RSI
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        rsi = np.full(n, np.nan)

        avg_gain = np.mean(gains[:self.period])
        avg_loss = np.mean(losses[:self.period])

        if avg_loss == 0:
            rsi[self.period] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[self.period] = 100 - (100 / (1 + rs))

        for i in range(self.period, len(deltas)):
            avg_gain = (avg_gain * (self.period - 1) + gains[i]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i]) / self.period

            if avg_loss == 0:
                rsi[i + 1] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i + 1] = 100 - (100 / (1 + rs))

        # Generate signals
        for i in range(self.period + 1, n):
            if np.isnan(rsi[i]) or np.isnan(rsi[i - 1]):
                continue

            # Buy on oversold
            if rsi[i] > self.oversold and rsi[i - 1] <= self.oversold:
                signals[i] = 1
            # Sell on overbought
            elif rsi[i] < self.overbought and rsi[i - 1] >= self.overbought:
                signals[i] = -1

        return signals


class MomentumStrategy(Strategy):
    """
    Momentum Strategy

    Buy when price ROC is positive and above threshold
    Sell when price ROC turns negative
    """

    def __init__(self, lookback: int = 20, threshold: float = 5.0):
        super().__init__(name=f"Momentum_{lookback}_{threshold}")
        self.lookback = lookback
        self.threshold = threshold

    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        n = len(closes)
        signals = np.zeros(n)

        if n < self.lookback + 1:
            return signals

        # Calculate momentum (ROC)
        roc = np.full(n, np.nan)
        for i in range(self.lookback, n):
            if closes[i - self.lookback] > 0:
                roc[i] = (closes[i] / closes[i - self.lookback] - 1) * 100

        # Generate signals
        in_position = False
        for i in range(self.lookback + 1, n):
            if np.isnan(roc[i]):
                continue

            if not in_position and roc[i] > self.threshold:
                signals[i] = 1  # Buy
                in_position = True
            elif in_position and roc[i] < 0:
                signals[i] = -1  # Sell
                in_position = False

        return signals


class BollingerBandStrategy(Strategy):
    """
    Bollinger Band Mean Reversion Strategy

    Buy when price touches lower band
    Sell when price touches upper band
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__(name=f"BB_{period}_{std_dev}")
        self.period = period
        self.std_dev = std_dev

    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        n = len(closes)
        signals = np.zeros(n)

        if n < self.period:
            return signals

        # Calculate Bollinger Bands
        middle = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)

        for i in range(self.period - 1, n):
            window = closes[i - self.period + 1:i + 1]
            middle[i] = np.mean(window)
            std = np.std(window)
            upper[i] = middle[i] + self.std_dev * std
            lower[i] = middle[i] - self.std_dev * std

        # Generate signals
        for i in range(self.period, n):
            if np.isnan(lower[i]) or np.isnan(upper[i]):
                continue

            # Buy at lower band
            if closes[i] <= lower[i] and closes[i - 1] > lower[i - 1]:
                signals[i] = 1
            # Sell at upper band
            elif closes[i] >= upper[i] and closes[i - 1] < upper[i - 1]:
                signals[i] = -1

        return signals


class MACDStrategy(Strategy):
    """
    MACD Strategy

    Buy on MACD crossover above signal line
    Sell on MACD crossover below signal line
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ):
        super().__init__(name=f"MACD_{fast_period}_{slow_period}_{signal_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        n = len(data)
        ema = np.full(n, np.nan)

        if n < period:
            return ema

        multiplier = 2 / (period + 1)
        ema[period - 1] = np.mean(data[:period])

        for i in range(period, n):
            ema[i] = (data[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

        return ema

    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        n = len(closes)
        signals = np.zeros(n)

        if n < self.slow_period + self.signal_period:
            return signals

        # Calculate MACD
        ema_fast = self._ema(closes, self.fast_period)
        ema_slow = self._ema(closes, self.slow_period)
        macd_line = ema_fast - ema_slow

        # Calculate signal line (EMA of MACD)
        valid_macd = macd_line[~np.isnan(macd_line)]
        signal_line = self._ema(valid_macd, self.signal_period)

        # Pad signal line
        padded_signal = np.full(n, np.nan)
        start_idx = n - len(signal_line)
        padded_signal[start_idx:] = signal_line

        # Generate signals
        for i in range(self.slow_period + self.signal_period, n):
            if np.isnan(macd_line[i]) or np.isnan(padded_signal[i]):
                continue
            if np.isnan(macd_line[i - 1]) or np.isnan(padded_signal[i - 1]):
                continue

            # MACD crosses above signal
            if macd_line[i] > padded_signal[i] and macd_line[i - 1] <= padded_signal[i - 1]:
                signals[i] = 1
            # MACD crosses below signal
            elif macd_line[i] < padded_signal[i] and macd_line[i - 1] >= padded_signal[i - 1]:
                signals[i] = -1

        return signals


class BreakoutStrategy(Strategy):
    """
    Channel Breakout Strategy

    Buy on breakout above N-day high
    Sell on breakdown below N-day low
    """

    def __init__(self, lookback: int = 20):
        super().__init__(name=f"Breakout_{lookback}")
        self.lookback = lookback

    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        n = len(closes)
        signals = np.zeros(n)

        if n < self.lookback + 1:
            return signals

        for i in range(self.lookback, n):
            # N-day high/low (excluding current bar)
            channel_high = np.max(highs[i - self.lookback:i])
            channel_low = np.min(lows[i - self.lookback:i])

            # Breakout
            if closes[i] > channel_high:
                signals[i] = 1
            elif closes[i] < channel_low:
                signals[i] = -1

        return signals


class TrendFollowingStrategy(Strategy):
    """
    Combined Trend Following Strategy

    Uses MA trend, ADX filter, and momentum
    """

    def __init__(
        self,
        ma_period: int = 50,
        adx_period: int = 14,
        adx_threshold: float = 25
    ):
        super().__init__(name=f"TrendFollowing_{ma_period}_{adx_period}")
        self.ma_period = ma_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def generate_signals(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        n = len(closes)
        signals = np.zeros(n)

        if n < max(self.ma_period, self.adx_period * 2) + 1:
            return signals

        # Calculate MA
        ma = np.full(n, np.nan)
        for i in range(self.ma_period - 1, n):
            ma[i] = np.mean(closes[i - self.ma_period + 1:i + 1])

        # Calculate ADX (simplified)
        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )

        atr = np.full(n, np.nan)
        for i in range(self.adx_period - 1, n):
            atr[i] = np.mean(tr[i - self.adx_period + 1:i + 1])

        # Simplified ADX approximation based on trend consistency
        adx = np.full(n, np.nan)
        for i in range(self.adx_period * 2 - 1, n):
            price_change = abs(closes[i] - closes[i - self.adx_period])
            total_change = np.sum(np.abs(np.diff(closes[i - self.adx_period:i + 1])))
            if total_change > 0:
                adx[i] = (price_change / total_change) * 100

        # Generate signals
        in_position = False
        for i in range(max(self.ma_period, self.adx_period * 2), n):
            if np.isnan(ma[i]) or np.isnan(adx[i]):
                continue

            # Strong trend required
            if adx[i] < self.adx_threshold:
                continue

            if not in_position:
                # Buy in uptrend
                if closes[i] > ma[i] and closes[i - 1] <= ma[i - 1]:
                    signals[i] = 1
                    in_position = True
            # Sell when price crosses below MA
            elif closes[i] < ma[i]:
                signals[i] = -1
                in_position = False

        return signals


# Strategy registry
STRATEGIES = {
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "momentum": MomentumStrategy,
    "bollinger": BollingerBandStrategy,
    "macd": MACDStrategy,
    "breakout": BreakoutStrategy,
    "trend_following": TrendFollowingStrategy,
}


def get_strategy(name: str, **kwargs) -> Strategy:
    """Get strategy by name"""
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {name}")

    return STRATEGIES[name](**kwargs)


def list_strategies() -> List[str]:
    """List available strategies"""
    return list(STRATEGIES.keys())
