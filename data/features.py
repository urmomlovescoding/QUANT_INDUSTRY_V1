"""
QUANT_INDUSTRY_V1 Feature Engineering

Comprehensive feature engineering for trading:
- Technical indicators
- Statistical features
- Market microstructure
- Cross-sectional features
- Time-series features

Rollback Plan: Delete this file
Tests Required: Feature accuracy, edge cases
Failure Modes: Return empty features, alert operators
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE TYPES
# =============================================================================

class FeatureCategory(Enum):
    """Feature categories."""
    PRICE = "price"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    MOMENTUM = "momentum"
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    MICROSTRUCTURE = "microstructure"
    CROSS_SECTIONAL = "cross_sectional"
    CALENDAR = "calendar"


@dataclass
class FeatureConfig:
    """Configuration for feature computation."""
    lookback_periods: List[int] = field(default_factory=lambda: [5, 10, 20, 60])
    include_categories: List[FeatureCategory] = field(default_factory=list)
    normalize: bool = True
    fill_method: str = "ffill"  # ffill, bfill, mean, zero


@dataclass
class FeatureSet:
    """Computed feature set."""
    features: Dict[str, np.ndarray]
    feature_names: List[str]
    timestamps: List[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_matrix(self) -> np.ndarray:
        """Convert to feature matrix (n_samples x n_features)."""
        return np.column_stack([self.features[name] for name in self.feature_names])

    def get_latest(self) -> Dict[str, float]:
        """Get latest feature values."""
        return {name: self.features[name][-1] for name in self.feature_names}


# =============================================================================
# BASE FEATURE COMPUTER
# =============================================================================

class FeatureComputer(ABC):
    """Base class for feature computation."""

    def __init__(self, name: str, category: FeatureCategory):
        self.name = name
        self.category = category

    @abstractmethod
    def compute(self, data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Compute features from data."""
        pass


# =============================================================================
# TECHNICAL INDICATORS
# =============================================================================

class MovingAverages(FeatureComputer):
    """Moving average features."""

    def __init__(self, periods: List[int] = None):
        super().__init__("moving_averages", FeatureCategory.TREND)
        self.periods = periods or [5, 10, 20, 50, 200]

    def compute(self, data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        close = data['close']
        features = {}

        for period in self.periods:
            # SMA
            sma = self._sma(close, period)
            features[f'sma_{period}'] = sma

            # EMA
            ema = self._ema(close, period)
            features[f'ema_{period}'] = ema

            # Price relative to MA
            features[f'price_sma_{period}_ratio'] = close / (sma + 1e-8) - 1
            features[f'price_ema_{period}_ratio'] = close / (ema + 1e-8) - 1

        # MA crossovers
        for i, short in enumerate(self.periods[:-1]):
            long = self.periods[i + 1]
            features[f'sma_{short}_{long}_cross'] = (
                self._sma(close, short) - self._sma(close, long)
            )

        return features

    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Simple moving average."""
        result = np.full_like(data, np.nan)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average."""
        result = np.full_like(data, np.nan)
        alpha = 2 / (period + 1)

        result[period - 1] = np.mean(data[:period])
        for i in range(period, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]

        return result


class MomentumIndicators(FeatureComputer):
    """Momentum-based features."""

    def __init__(self, periods: List[int] = None):
        super().__init__("momentum", FeatureCategory.MOMENTUM)
        self.periods = periods or [5, 10, 20, 60]

    def compute(self, data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        close = data['close']
        high = data.get('high', close)
        low = data.get('low', close)
        volume = data.get('volume', np.ones_like(close))

        features = {}

        for period in self.periods:
            # Returns
            features[f'return_{period}'] = self._returns(close, period)

            # Rate of change
            features[f'roc_{period}'] = (close - np.roll(close, period)) / (np.roll(close, period) + 1e-8)

            # Momentum
            features[f'momentum_{period}'] = close - np.roll(close, period)

        # RSI
        for period in [14, 28]:
            features[f'rsi_{period}'] = self._rsi(close, period)

        # Stochastic
        features['stoch_k'], features['stoch_d'] = self._stochastic(high, low, close)

        # Williams %R
        features['williams_r'] = self._williams_r(high, low, close)

        # CCI
        features['cci'] = self._cci(high, low, close)

        # MFI (Money Flow Index)
        if 'volume' in data:
            features['mfi'] = self._mfi(high, low, close, volume)

        return features

    def _returns(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate returns over period."""
        returns = np.zeros_like(prices)
        returns[period:] = (prices[period:] - prices[:-period]) / (prices[:-period] + 1e-8)
        return returns

    def _rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        deltas = np.diff(prices, prepend=prices[0])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = self._ema_array(gains, period)
        avg_loss = self._ema_array(losses, period)

        rs = avg_gain / (avg_loss + 1e-8)
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _stochastic(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        k_period: int = 14,
        d_period: int = 3
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Stochastic oscillator."""
        k = np.zeros_like(close)

        for i in range(k_period - 1, len(close)):
            h = np.max(high[i - k_period + 1:i + 1])
            l = np.min(low[i - k_period + 1:i + 1])
            k[i] = 100 * (close[i] - l) / (h - l + 1e-8)

        d = self._sma_array(k, d_period)
        return k, d

    def _williams_r(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Williams %R."""
        wr = np.zeros_like(close)

        for i in range(period - 1, len(close)):
            h = np.max(high[i - period + 1:i + 1])
            l = np.min(low[i - period + 1:i + 1])
            wr[i] = -100 * (h - close[i]) / (h - l + 1e-8)

        return wr

    def _cci(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 20
    ) -> np.ndarray:
        """Commodity Channel Index."""
        tp = (high + low + close) / 3
        sma = self._sma_array(tp, period)
        mad = self._mad_array(tp, period)

        return (tp - sma) / (0.015 * mad + 1e-8)

    def _mfi(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Money Flow Index."""
        tp = (high + low + close) / 3
        mf = tp * volume

        tp_diff = np.diff(tp, prepend=tp[0])
        pos_mf = np.where(tp_diff > 0, mf, 0)
        neg_mf = np.where(tp_diff < 0, mf, 0)

        pos_sum = self._rolling_sum(pos_mf, period)
        neg_sum = self._rolling_sum(neg_mf, period)

        mfi = 100 - (100 / (1 + pos_sum / (neg_sum + 1e-8)))
        return mfi

    def _ema_array(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        alpha = 2 / (period + 1)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    def _sma_array(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result

    def _mad_array(self, data: np.ndarray, period: int) -> np.ndarray:
        """Mean absolute deviation."""
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            window = data[i - period + 1:i + 1]
            result[i] = np.mean(np.abs(window - np.mean(window)))
        return result

    def _rolling_sum(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.sum(data[i - period + 1:i + 1])
        return result


class VolatilityIndicators(FeatureComputer):
    """Volatility-based features."""

    def __init__(self, periods: List[int] = None):
        super().__init__("volatility", FeatureCategory.VOLATILITY)
        self.periods = periods or [5, 10, 20, 60]

    def compute(self, data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        close = data['close']
        high = data.get('high', close)
        low = data.get('low', close)

        features = {}

        # Returns for volatility calculation
        returns = np.diff(np.log(close + 1e-8), prepend=0)

        for period in self.periods:
            # Historical volatility
            features[f'volatility_{period}'] = self._rolling_std(returns, period) * np.sqrt(252)

            # Realized variance
            features[f'realized_var_{period}'] = self._rolling_var(returns, period) * 252

        # ATR (Average True Range)
        for period in [14, 20]:
            features[f'atr_{period}'] = self._atr(high, low, close, period)
            features[f'atr_{period}_pct'] = features[f'atr_{period}'] / (close + 1e-8)

        # Bollinger Bands
        sma = self._sma(close, 20)
        std = self._rolling_std(close, 20)
        features['bb_upper'] = sma + 2 * std
        features['bb_lower'] = sma - 2 * std
        features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / (sma + 1e-8)
        features['bb_position'] = (close - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'] + 1e-8)

        # Keltner Channels
        atr = self._atr(high, low, close, 20)
        ema = self._ema(close, 20)
        features['kc_upper'] = ema + 2 * atr
        features['kc_lower'] = ema - 2 * atr

        # Parkinson volatility (using high-low)
        features['parkinson_vol'] = self._parkinson_volatility(high, low)

        # Garman-Klass volatility
        if 'open' in data:
            features['gk_vol'] = self._garman_klass(data['open'], high, low, close)

        return features

    def _rolling_std(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.std(data[i - period + 1:i + 1])
        return result

    def _rolling_var(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.var(data[i - period + 1:i + 1])
        return result

    def _atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Average True Range."""
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - np.roll(close, 1)),
                np.abs(low - np.roll(close, 1))
            )
        )
        tr[0] = high[0] - low[0]

        return self._ema(tr, period)

    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result

    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        alpha = 2 / (period + 1)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    def _parkinson_volatility(
        self,
        high: np.ndarray,
        low: np.ndarray,
        period: int = 20
    ) -> np.ndarray:
        """Parkinson volatility estimator."""
        log_hl = np.log(high / (low + 1e-8)) ** 2
        factor = 1 / (4 * np.log(2))

        result = np.zeros_like(high)
        for i in range(period - 1, len(high)):
            result[i] = np.sqrt(factor * np.mean(log_hl[i - period + 1:i + 1]) * 252)

        return result

    def _garman_klass(
        self,
        open_: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 20
    ) -> np.ndarray:
        """Garman-Klass volatility estimator."""
        log_hl = np.log(high / (low + 1e-8)) ** 2
        log_co = np.log(close / (open_ + 1e-8)) ** 2

        gk = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co

        result = np.zeros_like(close)
        for i in range(period - 1, len(close)):
            result[i] = np.sqrt(np.mean(gk[i - period + 1:i + 1]) * 252)

        return result


class VolumeIndicators(FeatureComputer):
    """Volume-based features."""

    def __init__(self, periods: List[int] = None):
        super().__init__("volume", FeatureCategory.VOLUME)
        self.periods = periods or [5, 10, 20]

    def compute(self, data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        close = data['close']
        volume = data.get('volume', np.ones_like(close))
        high = data.get('high', close)
        low = data.get('low', close)

        features = {}

        for period in self.periods:
            # Volume SMA
            vol_sma = self._sma(volume, period)
            features[f'volume_sma_{period}'] = vol_sma
            features[f'volume_ratio_{period}'] = volume / (vol_sma + 1e-8)

        # On-Balance Volume
        features['obv'] = self._obv(close, volume)

        # Volume-Price Trend
        features['vpt'] = self._vpt(close, volume)

        # Accumulation/Distribution
        features['ad'] = self._ad(high, low, close, volume)

        # Chaikin Money Flow
        features['cmf'] = self._cmf(high, low, close, volume)

        # VWAP
        if 'high' in data and 'low' in data:
            features['vwap'] = self._vwap(high, low, close, volume)
            features['vwap_deviation'] = (close - features['vwap']) / (features['vwap'] + 1e-8)

        return features

    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data, dtype=float)
        for i in range(period - 1, len(data)):
            result[i] = np.mean(data[i - period + 1:i + 1])
        return result

    def _obv(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """On-Balance Volume."""
        direction = np.sign(np.diff(close, prepend=close[0]))
        obv = np.cumsum(direction * volume)
        return obv

    def _vpt(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """Volume-Price Trend."""
        pct_change = np.diff(close, prepend=close[0]) / (np.roll(close, 1) + 1e-8)
        pct_change[0] = 0
        return np.cumsum(pct_change * volume)

    def _ad(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray
    ) -> np.ndarray:
        """Accumulation/Distribution Line."""
        mfm = ((close - low) - (high - close)) / (high - low + 1e-8)
        mfv = mfm * volume
        return np.cumsum(mfv)

    def _cmf(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        period: int = 20
    ) -> np.ndarray:
        """Chaikin Money Flow."""
        mfm = ((close - low) - (high - close)) / (high - low + 1e-8)
        mfv = mfm * volume

        result = np.zeros_like(close)
        for i in range(period - 1, len(close)):
            result[i] = np.sum(mfv[i - period + 1:i + 1]) / (np.sum(volume[i - period + 1:i + 1]) + 1e-8)

        return result

    def _vwap(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray
    ) -> np.ndarray:
        """Volume Weighted Average Price."""
        tp = (high + low + close) / 3
        return np.cumsum(tp * volume) / (np.cumsum(volume) + 1e-8)


# =============================================================================
# STATISTICAL FEATURES
# =============================================================================

class StatisticalFeatures(FeatureComputer):
    """Statistical features."""

    def __init__(self, periods: List[int] = None):
        super().__init__("statistical", FeatureCategory.MEAN_REVERSION)
        self.periods = periods or [10, 20, 60]

    def compute(self, data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        close = data['close']
        returns = np.diff(np.log(close + 1e-8), prepend=0)

        features = {}

        for period in self.periods:
            # Z-score
            features[f'zscore_{period}'] = self._zscore(close, period)

            # Skewness
            features[f'skew_{period}'] = self._rolling_skew(returns, period)

            # Kurtosis
            features[f'kurt_{period}'] = self._rolling_kurt(returns, period)

            # Autocorrelation
            features[f'autocorr_{period}'] = self._autocorrelation(returns, period)

        # Hurst exponent (long memory)
        features['hurst'] = self._hurst_exponent(close)

        return features

    def _zscore(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            window = data[i - period + 1:i + 1]
            mean = np.mean(window)
            std = np.std(window)
            result[i] = (data[i] - mean) / (std + 1e-8)
        return result

    def _rolling_skew(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            window = data[i - period + 1:i + 1]
            mean = np.mean(window)
            std = np.std(window)
            if std > 1e-8:
                result[i] = np.mean(((window - mean) / std) ** 3)
        return result

    def _rolling_kurt(self, data: np.ndarray, period: int) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            window = data[i - period + 1:i + 1]
            mean = np.mean(window)
            std = np.std(window)
            if std > 1e-8:
                result[i] = np.mean(((window - mean) / std) ** 4) - 3
        return result

    def _autocorrelation(self, data: np.ndarray, period: int, lag: int = 1) -> np.ndarray:
        result = np.zeros_like(data)
        for i in range(period - 1 + lag, len(data)):
            window = data[i - period + 1:i + 1]
            lagged = data[i - period + 1 - lag:i + 1 - lag]
            if np.std(window) > 1e-8 and np.std(lagged) > 1e-8:
                result[i] = np.corrcoef(window, lagged)[0, 1]
        return result

    def _hurst_exponent(self, data: np.ndarray, max_lag: int = 100) -> np.ndarray:
        """Simplified Hurst exponent estimation."""
        result = np.full_like(data, 0.5)
        min_window = 50

        for i in range(min_window, len(data)):
            window = data[max(0, i - max_lag):i + 1]
            if len(window) < 20:
                continue

            # R/S analysis
            lags = range(10, min(len(window) // 2, 50))
            if len(lags) < 3:
                continue

            rs_values = []
            for lag in lags:
                rs = self._rs_statistic(window, lag)
                if rs > 0:
                    rs_values.append((np.log(lag), np.log(rs)))

            if len(rs_values) >= 3:
                x = np.array([v[0] for v in rs_values])
                y = np.array([v[1] for v in rs_values])
                slope = np.polyfit(x, y, 1)[0]
                result[i] = max(0, min(1, slope))

        return result

    def _rs_statistic(self, data: np.ndarray, lag: int) -> float:
        """R/S statistic for Hurst exponent."""
        if len(data) < lag:
            return 0

        # Calculate mean-adjusted cumulative deviation
        mean = np.mean(data[:lag])
        cumdev = np.cumsum(data[:lag] - mean)
        r = np.max(cumdev) - np.min(cumdev)
        s = np.std(data[:lag])

        return r / (s + 1e-8)


# =============================================================================
# FEATURE ENGINE
# =============================================================================

class FeatureEngine:
    """
    Main feature engineering engine.

    Computes comprehensive feature sets for trading.
    """

    def __init__(self, config: FeatureConfig = None):
        self.config = config or FeatureConfig()

        # Initialize feature computers
        self.computers: List[FeatureComputer] = [
            MovingAverages(self.config.lookback_periods),
            MomentumIndicators(self.config.lookback_periods),
            VolatilityIndicators(self.config.lookback_periods),
            VolumeIndicators(self.config.lookback_periods),
            StatisticalFeatures(self.config.lookback_periods),
        ]

        # Filter by category if specified
        if self.config.include_categories:
            self.computers = [
                c for c in self.computers
                if c.category in self.config.include_categories
            ]

    def compute(
        self,
        data: Dict[str, np.ndarray],
        timestamps: List[datetime] = None
    ) -> FeatureSet:
        """
        Compute all features.

        Args:
            data: Dict with 'open', 'high', 'low', 'close', 'volume' arrays
            timestamps: Optional list of timestamps

        Returns:
            FeatureSet with all computed features
        """
        all_features = {}

        for computer in self.computers:
            try:
                features = computer.compute(data)
                all_features.update(features)
            except Exception as e:
                logger.warning(f"Feature computation failed for {computer.name}: {e}")

        # Handle missing values
        for name, values in all_features.items():
            all_features[name] = self._fill_missing(values)

        # Normalize if requested
        if self.config.normalize:
            all_features = self._normalize_features(all_features)

        feature_names = list(all_features.keys())

        return FeatureSet(
            features=all_features,
            feature_names=feature_names,
            timestamps=timestamps or [],
            metadata={
                'n_features': len(feature_names),
                'n_samples': len(data['close']),
                'lookback_periods': self.config.lookback_periods,
            }
        )

    def _fill_missing(self, data: np.ndarray) -> np.ndarray:
        """Fill missing values."""
        result = data.copy()

        if self.config.fill_method == 'ffill':
            for i in range(1, len(result)):
                if np.isnan(result[i]):
                    result[i] = result[i - 1]
        elif self.config.fill_method == 'bfill':
            for i in range(len(result) - 2, -1, -1):
                if np.isnan(result[i]):
                    result[i] = result[i + 1]
        elif self.config.fill_method == 'mean':
            mean_val = np.nanmean(result)
            result[np.isnan(result)] = mean_val
        elif self.config.fill_method == 'zero':
            result[np.isnan(result)] = 0

        return result

    def _normalize_features(
        self,
        features: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Normalize features to zero mean, unit variance."""
        normalized = {}

        for name, values in features.items():
            mean = np.nanmean(values)
            std = np.nanstd(values)

            if std > 1e-8:
                normalized[name] = (values - mean) / std
            else:
                normalized[name] = values - mean

        return normalized

    def get_feature_importance(
        self,
        feature_set: FeatureSet,
        target: np.ndarray
    ) -> Dict[str, float]:
        """Calculate feature importance via correlation."""
        importance = {}

        for name in feature_set.feature_names:
            values = feature_set.features[name]

            # Ensure same length
            min_len = min(len(values), len(target))
            v = values[-min_len:]
            t = target[-min_len:]

            # Remove NaN
            mask = ~(np.isnan(v) | np.isnan(t))
            if mask.sum() > 10:
                corr = np.corrcoef(v[mask], t[mask])[0, 1]
                importance[name] = abs(corr)
            else:
                importance[name] = 0

        return importance
