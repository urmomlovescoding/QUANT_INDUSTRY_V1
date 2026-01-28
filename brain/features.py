"""
QUANT_INDUSTRY_V1 Feature Engineering

Technical indicator computation and feature extraction.

Rollback Plan: Delete this file
Tests Required: Unit tests for each indicator, hash reproducibility
Failure Modes: Invalid data -> return NaN, log warning
"""

import numpy as np
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import math

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE TYPES
# =============================================================================

class FeatureCategory(Enum):
    """Categories of features."""
    PRICE = "price"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    PATTERN = "pattern"
    CUSTOM = "custom"


@dataclass
class FeatureDefinition:
    """Definition of a single feature."""
    name: str
    category: FeatureCategory
    lookback: int  # Bars needed
    description: str = ""
    version: int = 1


@dataclass
class FeatureVector:
    """
    Computed feature vector with metadata.
    """
    symbol: str
    timestamp: datetime
    features: Dict[str, float]
    feature_names: List[str]
    lookback_used: int
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __len__(self) -> int:
        return len(self.features)

    def to_array(self) -> np.ndarray:
        """Convert to numpy array in consistent order."""
        return np.array([self.features.get(name, np.nan) for name in self.feature_names])

    def get_hash(self) -> str:
        """Get reproducible hash of feature configuration."""
        hash_input = "|".join([
            self.symbol,
            str(sorted(self.feature_names)),
            str(self.lookback_used),
        ])
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]


# =============================================================================
# TECHNICAL INDICATORS
# =============================================================================

def sma(prices: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    if len(prices) < period:
        return np.full(len(prices), np.nan)

    result = np.full(len(prices), np.nan)
    for i in range(period - 1, len(prices)):
        result[i] = np.mean(prices[i - period + 1:i + 1])
    return result


def ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    if len(prices) < period:
        return np.full(len(prices), np.nan)

    result = np.full(len(prices), np.nan)
    multiplier = 2 / (period + 1)

    # Initialize with SMA
    result[period - 1] = np.mean(prices[:period])

    # Calculate EMA
    for i in range(period, len(prices)):
        result[i] = (prices[i] - result[i - 1]) * multiplier + result[i - 1]

    return result


def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index."""
    if len(prices) < period + 1:
        return np.full(len(prices), np.nan)

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    result = np.full(len(prices), np.nan)

    # First RSI value
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        result[period] = 100
    else:
        rs = avg_gain / avg_loss
        result[period] = 100 - (100 / (1 + rs))

    # Subsequent values
    for i in range(period + 1, len(prices)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period

        if avg_loss == 0:
            result[i] = 100
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))

    return result


def macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD (Moving Average Convergence Divergence)."""
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)

    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line[~np.isnan(macd_line)], signal)

    # Pad signal line
    signal_padded = np.full(len(prices), np.nan)
    signal_padded[-len(signal_line):] = signal_line

    histogram = macd_line - signal_padded

    return macd_line, signal_padded, histogram


def bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger Bands."""
    middle = sma(prices, period)

    std = np.full(len(prices), np.nan)
    for i in range(period - 1, len(prices)):
        std[i] = np.std(prices[i - period + 1:i + 1])

    upper = middle + std_dev * std
    lower = middle - std_dev * std

    return upper, middle, lower


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range."""
    if len(high) < 2:
        return np.full(len(high), np.nan)

    # True range
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )

    # Pad with first value
    tr = np.concatenate([[high[0] - low[0]], tr])

    # ATR (EMA of TR)
    return ema(tr, period)


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average Directional Index."""
    if len(high) < period + 1:
        return np.full(len(high), np.nan)

    atr_values = atr(high, low, close, period)

    # +DM and -DM
    up_move = np.diff(high)
    down_move = -np.diff(low)

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    # Smooth +DI and -DI
    plus_di = 100 * ema(np.concatenate([[0], plus_dm]), period) / np.maximum(atr_values, 1e-10)
    minus_di = 100 * ema(np.concatenate([[0], minus_dm]), period) / np.maximum(atr_values, 1e-10)

    # DX and ADX
    dx = 100 * np.abs(plus_di - minus_di) / np.maximum(plus_di + minus_di, 1e-10)
    adx_values = ema(dx, period)

    return adx_values


def stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray, k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """Stochastic Oscillator."""
    if len(high) < k_period:
        return np.full(len(high), np.nan), np.full(len(high), np.nan)

    k = np.full(len(high), np.nan)

    for i in range(k_period - 1, len(high)):
        highest_high = np.max(high[i - k_period + 1:i + 1])
        lowest_low = np.min(low[i - k_period + 1:i + 1])

        if highest_high != lowest_low:
            k[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
        else:
            k[i] = 50

    d = sma(k, d_period)

    return k, d


def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """On-Balance Volume."""
    obv_values = np.zeros(len(close))

    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv_values[i] = obv_values[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv_values[i] = obv_values[i - 1] - volume[i]
        else:
            obv_values[i] = obv_values[i - 1]

    return obv_values


def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """Volume Weighted Average Price."""
    typical_price = (high + low + close) / 3
    cumulative_tp_vol = np.cumsum(typical_price * volume)
    cumulative_vol = np.cumsum(volume)

    return cumulative_tp_vol / np.maximum(cumulative_vol, 1)


def williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Williams %R."""
    if len(high) < period:
        return np.full(len(high), np.nan)

    result = np.full(len(high), np.nan)

    for i in range(period - 1, len(high)):
        highest_high = np.max(high[i - period + 1:i + 1])
        lowest_low = np.min(low[i - period + 1:i + 1])

        if highest_high != lowest_low:
            result[i] = -100 * (highest_high - close[i]) / (highest_high - lowest_low)
        else:
            result[i] = -50

    return result


def cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20) -> np.ndarray:
    """Commodity Channel Index."""
    typical_price = (high + low + close) / 3
    sma_tp = sma(typical_price, period)

    # Mean deviation
    mean_dev = np.full(len(high), np.nan)
    for i in range(period - 1, len(high)):
        mean_dev[i] = np.mean(np.abs(typical_price[i - period + 1:i + 1] - sma_tp[i]))

    return (typical_price - sma_tp) / (0.015 * np.maximum(mean_dev, 1e-10))


def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, period: int = 14) -> np.ndarray:
    """Money Flow Index."""
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume

    result = np.full(len(high), np.nan)

    for i in range(period, len(high)):
        positive_flow = 0
        negative_flow = 0

        for j in range(i - period + 1, i + 1):
            if j > 0:
                if typical_price[j] > typical_price[j - 1]:
                    positive_flow += raw_money_flow[j]
                else:
                    negative_flow += raw_money_flow[j]

        if negative_flow == 0:
            result[i] = 100
        else:
            money_ratio = positive_flow / negative_flow
            result[i] = 100 - (100 / (1 + money_ratio))

    return result


# =============================================================================
# FEATURE COMPUTER
# =============================================================================

class FeatureComputer:
    """
    Computes technical features from OHLCV data.

    Features:
    - 40+ technical indicators
    - Configurable feature sets
    - Reproducible hashing
    - NaN handling
    """

    # Standard feature set
    STANDARD_FEATURES = [
        # Price-based
        "returns_1", "returns_5", "returns_10", "returns_20",
        "log_returns_1",
        "price_sma_ratio_10", "price_sma_ratio_20", "price_sma_ratio_50",
        "price_ema_ratio_10", "price_ema_ratio_20",

        # Momentum
        "rsi_14", "rsi_7",
        "macd", "macd_signal", "macd_histogram",
        "stoch_k", "stoch_d",
        "williams_r_14",
        "cci_20",
        "mfi_14",

        # Volatility
        "atr_14", "atr_ratio",
        "bb_position", "bb_width",
        "volatility_10", "volatility_20",

        # Trend
        "adx_14",
        "sma_10_20_cross", "sma_20_50_cross",
        "ema_12_26_cross",
        "trend_strength",

        # Volume
        "volume_sma_ratio_10", "volume_sma_ratio_20",
        "obv_slope",
        "vwap_distance",

        # Mean reversion
        "zscore_20", "zscore_50",
        "distance_from_high_52w", "distance_from_low_52w",
    ]

    def __init__(self, feature_names: List[str] = None):
        self.feature_names = feature_names or self.STANDARD_FEATURES
        self._feature_funcs = self._build_feature_funcs()

    def _build_feature_funcs(self) -> Dict[str, Callable]:
        """Build mapping of feature names to computation functions."""
        return {
            # Returns
            "returns_1": lambda d: self._returns(d['close'], 1),
            "returns_5": lambda d: self._returns(d['close'], 5),
            "returns_10": lambda d: self._returns(d['close'], 10),
            "returns_20": lambda d: self._returns(d['close'], 20),
            "log_returns_1": lambda d: self._log_returns(d['close'], 1),

            # Price ratios
            "price_sma_ratio_10": lambda d: d['close'][-1] / sma(d['close'], 10)[-1] - 1,
            "price_sma_ratio_20": lambda d: d['close'][-1] / sma(d['close'], 20)[-1] - 1,
            "price_sma_ratio_50": lambda d: d['close'][-1] / sma(d['close'], 50)[-1] - 1,
            "price_ema_ratio_10": lambda d: d['close'][-1] / ema(d['close'], 10)[-1] - 1,
            "price_ema_ratio_20": lambda d: d['close'][-1] / ema(d['close'], 20)[-1] - 1,

            # RSI
            "rsi_14": lambda d: rsi(d['close'], 14)[-1] / 100,
            "rsi_7": lambda d: rsi(d['close'], 7)[-1] / 100,

            # MACD
            "macd": lambda d: macd(d['close'])[0][-1] / d['close'][-1],
            "macd_signal": lambda d: macd(d['close'])[1][-1] / d['close'][-1],
            "macd_histogram": lambda d: macd(d['close'])[2][-1] / d['close'][-1],

            # Stochastic
            "stoch_k": lambda d: stochastic(d['high'], d['low'], d['close'])[0][-1] / 100,
            "stoch_d": lambda d: stochastic(d['high'], d['low'], d['close'])[1][-1] / 100,

            # Williams %R
            "williams_r_14": lambda d: williams_r(d['high'], d['low'], d['close'], 14)[-1] / 100,

            # CCI
            "cci_20": lambda d: cci(d['high'], d['low'], d['close'], 20)[-1] / 200,

            # MFI
            "mfi_14": lambda d: mfi(d['high'], d['low'], d['close'], d['volume'], 14)[-1] / 100,

            # ATR
            "atr_14": lambda d: atr(d['high'], d['low'], d['close'], 14)[-1] / d['close'][-1],
            "atr_ratio": lambda d: atr(d['high'], d['low'], d['close'], 14)[-1] / atr(d['high'], d['low'], d['close'], 50)[-1],

            # Bollinger
            "bb_position": lambda d: self._bb_position(d['close']),
            "bb_width": lambda d: self._bb_width(d['close']),

            # Volatility
            "volatility_10": lambda d: np.std(self._returns_array(d['close'], 1)[-10:]),
            "volatility_20": lambda d: np.std(self._returns_array(d['close'], 1)[-20:]),

            # ADX
            "adx_14": lambda d: adx(d['high'], d['low'], d['close'], 14)[-1] / 100,

            # Crosses
            "sma_10_20_cross": lambda d: self._sma_cross(d['close'], 10, 20),
            "sma_20_50_cross": lambda d: self._sma_cross(d['close'], 20, 50),
            "ema_12_26_cross": lambda d: self._ema_cross(d['close'], 12, 26),

            # Trend
            "trend_strength": lambda d: self._trend_strength(d['close']),

            # Volume
            "volume_sma_ratio_10": lambda d: d['volume'][-1] / np.maximum(sma(d['volume'], 10)[-1], 1),
            "volume_sma_ratio_20": lambda d: d['volume'][-1] / np.maximum(sma(d['volume'], 20)[-1], 1),
            "obv_slope": lambda d: self._obv_slope(d['close'], d['volume']),
            "vwap_distance": lambda d: d['close'][-1] / vwap(d['high'], d['low'], d['close'], d['volume'])[-1] - 1,

            # Z-score
            "zscore_20": lambda d: self._zscore(d['close'], 20),
            "zscore_50": lambda d: self._zscore(d['close'], 50),

            # 52-week
            "distance_from_high_52w": lambda d: d['close'][-1] / np.max(d['high'][-252:]) - 1 if len(d['high']) >= 252 else np.nan,
            "distance_from_low_52w": lambda d: d['close'][-1] / np.min(d['low'][-252:]) - 1 if len(d['low']) >= 252 else np.nan,
        }

    def compute(
        self,
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        volumes: np.ndarray,
        symbol: str = "UNKNOWN",
        timestamp: datetime = None,
    ) -> FeatureVector:
        """
        Compute features from OHLCV data.

        Args:
            open_prices: Open prices
            high_prices: High prices
            low_prices: Low prices
            close_prices: Close prices
            volumes: Volumes
            symbol: Trading symbol
            timestamp: Timestamp for feature vector

        Returns:
            FeatureVector with computed features
        """
        data = {
            'open': np.asarray(open_prices, dtype=np.float64),
            'high': np.asarray(high_prices, dtype=np.float64),
            'low': np.asarray(low_prices, dtype=np.float64),
            'close': np.asarray(close_prices, dtype=np.float64),
            'volume': np.asarray(volumes, dtype=np.float64),
        }

        features = {}

        for name in self.feature_names:
            if name in self._feature_funcs:
                try:
                    value = self._feature_funcs[name](data)
                    features[name] = float(value) if not np.isnan(value) else 0.0
                except Exception as e:
                    logger.warning(f"Feature {name} computation failed: {e}")
                    features[name] = 0.0
            else:
                logger.warning(f"Unknown feature: {name}")
                features[name] = 0.0

        return FeatureVector(
            symbol=symbol,
            timestamp=timestamp or datetime.now(timezone.utc),
            features=features,
            feature_names=self.feature_names,
            lookback_used=len(close_prices),
        )

    # Helper methods
    def _returns(self, prices: np.ndarray, period: int) -> float:
        if len(prices) < period + 1:
            return 0.0
        return (prices[-1] - prices[-period - 1]) / prices[-period - 1]

    def _log_returns(self, prices: np.ndarray, period: int) -> float:
        if len(prices) < period + 1:
            return 0.0
        return np.log(prices[-1] / prices[-period - 1])

    def _returns_array(self, prices: np.ndarray, period: int) -> np.ndarray:
        if len(prices) < period + 1:
            return np.array([0.0])
        return np.diff(prices[::period]) / prices[:-period:period]

    def _bb_position(self, prices: np.ndarray) -> float:
        upper, middle, lower = bollinger_bands(prices)
        if np.isnan(upper[-1]) or upper[-1] == lower[-1]:
            return 0.5
        return (prices[-1] - lower[-1]) / (upper[-1] - lower[-1])

    def _bb_width(self, prices: np.ndarray) -> float:
        upper, middle, lower = bollinger_bands(prices)
        if np.isnan(middle[-1]) or middle[-1] == 0:
            return 0.0
        return (upper[-1] - lower[-1]) / middle[-1]

    def _sma_cross(self, prices: np.ndarray, fast: int, slow: int) -> float:
        sma_fast = sma(prices, fast)
        sma_slow = sma(prices, slow)
        if np.isnan(sma_slow[-1]) or sma_slow[-1] == 0:
            return 0.0
        return (sma_fast[-1] - sma_slow[-1]) / sma_slow[-1]

    def _ema_cross(self, prices: np.ndarray, fast: int, slow: int) -> float:
        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)
        if np.isnan(ema_slow[-1]) or ema_slow[-1] == 0:
            return 0.0
        return (ema_fast[-1] - ema_slow[-1]) / ema_slow[-1]

    def _trend_strength(self, prices: np.ndarray, period: int = 20) -> float:
        if len(prices) < period:
            return 0.0
        # Linear regression slope normalized
        x = np.arange(period)
        y = prices[-period:]
        slope = np.polyfit(x, y, 1)[0]
        return slope / np.mean(y)

    def _obv_slope(self, prices: np.ndarray, volumes: np.ndarray, period: int = 10) -> float:
        obv_values = obv(prices, volumes)
        if len(obv_values) < period:
            return 0.0
        # Normalized slope
        x = np.arange(period)
        y = obv_values[-period:]
        slope = np.polyfit(x, y, 1)[0]
        return slope / (np.std(y) + 1e-10)

    def _zscore(self, prices: np.ndarray, period: int) -> float:
        if len(prices) < period:
            return 0.0
        mean = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        if std == 0:
            return 0.0
        return (prices[-1] - mean) / std

    def get_feature_names(self) -> List[str]:
        """Get list of feature names."""
        return self.feature_names.copy()

    def get_lookback_required(self) -> int:
        """Get minimum lookback required for all features."""
        # 252 for 52-week features
        return 252
