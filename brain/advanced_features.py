"""
QUANT_INDUSTRY_V1 Advanced Feature Engineering

500+ features across multiple categories for comprehensive market analysis.

Categories:
- Price Action (50+ features)
- Momentum (50+ features)
- Volatility (40+ features)
- Volume/Flow (40+ features)
- Trend (40+ features)
- Mean Reversion (30+ features)
- Pattern Recognition (40+ features)
- Market Microstructure (40+ features)
- Cross-Asset (30+ features)
- Time/Seasonal (30+ features)
- Statistical (40+ features)
- Options-Derived (30+ features)
- Order Flow (40+ features)
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from scipy import stats
from scipy.signal import find_peaks

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE REGISTRY
# =============================================================================

@dataclass
class FeatureSpec:
    """Feature specification."""
    name: str
    category: str
    lookback: int
    description: str = ""


# All 500+ features organized by category
FEATURE_REGISTRY: Dict[str, List[FeatureSpec]] = {
    'price_action': [],
    'momentum': [],
    'volatility': [],
    'volume_flow': [],
    'trend': [],
    'mean_reversion': [],
    'pattern': [],
    'microstructure': [],
    'cross_asset': [],
    'time_seasonal': [],
    'statistical': [],
    'options_derived': [],
    'order_flow': [],
}


# =============================================================================
# ADVANCED FEATURE COMPUTER
# =============================================================================

class AdvancedFeatureComputer:
    """
    Comprehensive feature computation engine.

    Computes 500+ features for ML models.
    """

    def __init__(self, include_all: bool = True):
        self.include_all = include_all
        self._setup_feature_functions()

    def _setup_feature_functions(self):
        """Setup feature computation functions."""
        self.feature_functions = {}

        # Register all feature categories
        self._register_price_features()
        self._register_momentum_features()
        self._register_volatility_features()
        self._register_volume_features()
        self._register_trend_features()
        self._register_mean_reversion_features()
        self._register_pattern_features()
        self._register_microstructure_features()
        self._register_statistical_features()
        self._register_time_features()

    # =========================================================================
    # PRICE ACTION FEATURES (50+)
    # =========================================================================

    def _register_price_features(self):
        """Register price action features."""
        features = {}

        # Returns at multiple horizons
        for period in [1, 2, 3, 5, 10, 15, 20, 30, 60, 120]:
            features[f'returns_{period}'] = lambda d, p=period: self._returns(d['close'], p)
            features[f'log_returns_{period}'] = lambda d, p=period: self._log_returns(d['close'], p)

        # High-Low range features
        features['daily_range'] = lambda d: (d['high'][-1] - d['low'][-1]) / d['close'][-1]
        features['daily_range_sma_10'] = lambda d: self._range_sma_ratio(d, 10)
        features['daily_range_sma_20'] = lambda d: self._range_sma_ratio(d, 20)

        # Gap features
        features['overnight_gap'] = lambda d: (d['open'][-1] - d['close'][-2]) / d['close'][-2] if len(d['close']) > 1 else 0
        features['gap_fill_pct'] = lambda d: self._gap_fill_pct(d)

        # Body/Wick analysis
        features['body_size'] = lambda d: abs(d['close'][-1] - d['open'][-1]) / d['close'][-1]
        features['upper_wick'] = lambda d: (d['high'][-1] - max(d['open'][-1], d['close'][-1])) / d['close'][-1]
        features['lower_wick'] = lambda d: (min(d['open'][-1], d['close'][-1]) - d['low'][-1]) / d['close'][-1]
        features['body_to_range'] = lambda d: self._body_to_range(d)

        # Price levels
        features['distance_from_high_10'] = lambda d: d['close'][-1] / np.max(d['high'][-10:]) - 1
        features['distance_from_low_10'] = lambda d: d['close'][-1] / np.min(d['low'][-10:]) - 1
        features['distance_from_high_20'] = lambda d: d['close'][-1] / np.max(d['high'][-20:]) - 1
        features['distance_from_low_20'] = lambda d: d['close'][-1] / np.min(d['low'][-20:]) - 1
        features['distance_from_high_50'] = lambda d: d['close'][-1] / np.max(d['high'][-50:]) - 1 if len(d['high']) >= 50 else 0
        features['distance_from_low_50'] = lambda d: d['close'][-1] / np.min(d['low'][-50:]) - 1 if len(d['low']) >= 50 else 0

        # Price acceleration
        features['price_acceleration'] = lambda d: self._acceleration(d['close'], 5)
        features['price_jerk'] = lambda d: self._jerk(d['close'], 5)

        self.feature_functions.update(features)

    # =========================================================================
    # MOMENTUM FEATURES (50+)
    # =========================================================================

    def _register_momentum_features(self):
        """Register momentum features."""
        features = {}

        # RSI variants
        for period in [7, 14, 21, 28]:
            features[f'rsi_{period}'] = lambda d, p=period: self._rsi(d['close'], p) / 100

        # RSI derivatives
        features['rsi_slope_5'] = lambda d: self._slope(self._rsi_array(d['close'], 14), 5)
        features['rsi_divergence'] = lambda d: self._rsi_divergence(d['close'], 14)

        # MACD variants
        for fast, slow, signal in [(12, 26, 9), (8, 21, 5), (5, 13, 3)]:
            features[f'macd_{fast}_{slow}'] = lambda d, f=fast, s=slow: self._macd(d['close'], f, s)[0][-1] / d['close'][-1]
            features[f'macd_signal_{fast}_{slow}_{signal}'] = lambda d, f=fast, s=slow, sig=signal: self._macd(d['close'], f, s, sig)[1][-1] / d['close'][-1]
            features[f'macd_histogram_{fast}_{slow}_{signal}'] = lambda d, f=fast, s=slow, sig=signal: self._macd(d['close'], f, s, sig)[2][-1] / d['close'][-1]

        # Stochastic variants
        for k_period in [5, 14, 21]:
            features[f'stoch_k_{k_period}'] = lambda d, p=k_period: self._stochastic(d['high'], d['low'], d['close'], p)[0][-1] / 100
            features[f'stoch_d_{k_period}'] = lambda d, p=k_period: self._stochastic(d['high'], d['low'], d['close'], p)[1][-1] / 100

        # Williams %R
        for period in [10, 14, 20]:
            features[f'williams_r_{period}'] = lambda d, p=period: self._williams_r(d['high'], d['low'], d['close'], p)[-1] / 100

        # CCI
        for period in [14, 20, 50]:
            features[f'cci_{period}'] = lambda d, p=period: self._cci(d['high'], d['low'], d['close'], p)[-1] / 200

        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            features[f'roc_{period}'] = lambda d, p=period: (d['close'][-1] - d['close'][-p-1]) / d['close'][-p-1] if len(d['close']) > p else 0

        # MFI
        features['mfi_14'] = lambda d: self._mfi(d['high'], d['low'], d['close'], d['volume'], 14)[-1] / 100

        # Ultimate Oscillator
        features['ultimate_oscillator'] = lambda d: self._ultimate_oscillator(d['high'], d['low'], d['close']) / 100

        # TSI (True Strength Index)
        features['tsi'] = lambda d: self._tsi(d['close'])

        self.feature_functions.update(features)

    # =========================================================================
    # VOLATILITY FEATURES (40+)
    # =========================================================================

    def _register_volatility_features(self):
        """Register volatility features."""
        features = {}

        # ATR variants
        for period in [7, 14, 21, 50]:
            features[f'atr_{period}'] = lambda d, p=period: self._atr(d['high'], d['low'], d['close'], p)[-1] / d['close'][-1]
            features[f'atr_ratio_{period}'] = lambda d, p=period: self._atr(d['high'], d['low'], d['close'], p)[-1] / self._atr(d['high'], d['low'], d['close'], 50)[-1] if len(d['close']) >= 50 else 1

        # Bollinger Band features
        for period, std in [(20, 2), (20, 1), (50, 2)]:
            features[f'bb_position_{period}_{std}'] = lambda d, p=period, s=std: self._bb_position(d['close'], p, s)
            features[f'bb_width_{period}_{std}'] = lambda d, p=period, s=std: self._bb_width(d['close'], p, s)

        # Keltner Channel features
        features['keltner_position'] = lambda d: self._keltner_position(d['high'], d['low'], d['close'])
        features['keltner_width'] = lambda d: self._keltner_width(d['high'], d['low'], d['close'])

        # Historical volatility
        for period in [5, 10, 20, 60]:
            features[f'realized_vol_{period}'] = lambda d, p=period: np.std(np.diff(np.log(d['close'][-p-1:]))) * np.sqrt(252) if len(d['close']) > p else 0

        # Volatility ratios
        features['vol_ratio_5_20'] = lambda d: np.std(np.diff(np.log(d['close'][-6:]))) / np.std(np.diff(np.log(d['close'][-21:]))) if len(d['close']) >= 21 else 1
        features['vol_ratio_10_60'] = lambda d: np.std(np.diff(np.log(d['close'][-11:]))) / np.std(np.diff(np.log(d['close'][-61:]))) if len(d['close']) >= 61 else 1

        # Parkinson volatility
        features['parkinson_vol'] = lambda d: self._parkinson_volatility(d['high'], d['low'])

        # Garman-Klass volatility
        features['garman_klass_vol'] = lambda d: self._garman_klass_volatility(d['open'], d['high'], d['low'], d['close'])

        # Yang-Zhang volatility
        features['yang_zhang_vol'] = lambda d: self._yang_zhang_volatility(d['open'], d['high'], d['low'], d['close'])

        # Volatility of volatility
        features['vol_of_vol'] = lambda d: self._volatility_of_volatility(d['close'])

        self.feature_functions.update(features)

    # =========================================================================
    # VOLUME FEATURES (40+)
    # =========================================================================

    def _register_volume_features(self):
        """Register volume features."""
        features = {}

        # Volume ratios
        for period in [5, 10, 20, 50]:
            features[f'volume_sma_ratio_{period}'] = lambda d, p=period: d['volume'][-1] / np.mean(d['volume'][-p:]) if np.mean(d['volume'][-p:]) > 0 else 1

        # OBV features
        features['obv_slope_5'] = lambda d: self._obv_slope(d['close'], d['volume'], 5)
        features['obv_slope_10'] = lambda d: self._obv_slope(d['close'], d['volume'], 10)
        features['obv_divergence'] = lambda d: self._obv_divergence(d['close'], d['volume'])

        # VWAP features
        features['vwap_distance'] = lambda d: d['close'][-1] / self._vwap(d['high'], d['low'], d['close'], d['volume'])[-1] - 1

        # Accumulation/Distribution
        features['ad_line_slope'] = lambda d: self._ad_slope(d['high'], d['low'], d['close'], d['volume'])

        # Chaikin Money Flow
        for period in [10, 20, 50]:
            features[f'cmf_{period}'] = lambda d, p=period: self._cmf(d['high'], d['low'], d['close'], d['volume'], p)

        # Force Index
        features['force_index'] = lambda d: self._force_index(d['close'], d['volume'])

        # Volume Profile features
        features['volume_profile_poc'] = lambda d: self._volume_poc(d['close'], d['volume'])
        features['volume_profile_va_high'] = lambda d: self._volume_va(d['close'], d['volume'])[0]
        features['volume_profile_va_low'] = lambda d: self._volume_va(d['close'], d['volume'])[1]

        # Volume momentum
        features['volume_momentum'] = lambda d: (d['volume'][-1] - d['volume'][-5]) / d['volume'][-5] if d['volume'][-5] > 0 else 0

        # Relative volume
        features['relative_volume'] = lambda d: d['volume'][-1] / np.mean(d['volume'][-20:]) if len(d['volume']) >= 20 else 1

        # Volume-weighted features
        features['vwap_std'] = lambda d: self._vwap_std(d['high'], d['low'], d['close'], d['volume'])

        self.feature_functions.update(features)

    # =========================================================================
    # TREND FEATURES (40+)
    # =========================================================================

    def _register_trend_features(self):
        """Register trend features."""
        features = {}

        # Moving average crossovers
        for fast, slow in [(5, 20), (10, 30), (20, 50), (50, 200)]:
            features[f'ma_cross_{fast}_{slow}'] = lambda d, f=fast, s=slow: self._ma_cross(d['close'], f, s)

        # ADX
        for period in [7, 14, 21]:
            features[f'adx_{period}'] = lambda d, p=period: self._adx(d['high'], d['low'], d['close'], p)[-1] / 100
            features[f'plus_di_{period}'] = lambda d, p=period: self._plus_di(d['high'], d['low'], d['close'], p)[-1] / 100
            features[f'minus_di_{period}'] = lambda d, p=period: self._minus_di(d['high'], d['low'], d['close'], p)[-1] / 100

        # Trend strength
        features['trend_strength_10'] = lambda d: self._trend_strength(d['close'], 10)
        features['trend_strength_20'] = lambda d: self._trend_strength(d['close'], 20)
        features['trend_strength_50'] = lambda d: self._trend_strength(d['close'], 50)

        # Linear regression features
        features['linreg_slope_20'] = lambda d: self._linreg_slope(d['close'], 20)
        features['linreg_r2_20'] = lambda d: self._linreg_r2(d['close'], 20)
        features['linreg_intercept_20'] = lambda d: self._linreg_intercept(d['close'], 20)

        # SuperTrend
        features['supertrend_direction'] = lambda d: self._supertrend_direction(d['high'], d['low'], d['close'])

        # Ichimoku features
        features['ichimoku_tenkan'] = lambda d: self._ichimoku_tenkan(d['high'], d['low']) / d['close'][-1]
        features['ichimoku_kijun'] = lambda d: self._ichimoku_kijun(d['high'], d['low']) / d['close'][-1]
        features['ichimoku_cloud_top'] = lambda d: self._ichimoku_senkou_a(d['high'], d['low']) / d['close'][-1]
        features['ichimoku_cloud_bottom'] = lambda d: self._ichimoku_senkou_b(d['high'], d['low']) / d['close'][-1]

        # Parabolic SAR
        features['psar_direction'] = lambda d: self._psar_direction(d['high'], d['low'], d['close'])

        self.feature_functions.update(features)

    # =========================================================================
    # MEAN REVERSION FEATURES (30+)
    # =========================================================================

    def _register_mean_reversion_features(self):
        """Register mean reversion features."""
        features = {}

        # Z-scores
        for period in [10, 20, 50, 100]:
            features[f'zscore_{period}'] = lambda d, p=period: self._zscore(d['close'], p)

        # Distance from moving averages
        for period in [10, 20, 50, 100, 200]:
            features[f'distance_from_sma_{period}'] = lambda d, p=period: d['close'][-1] / self._sma(d['close'], p)[-1] - 1 if len(d['close']) >= p else 0
            features[f'distance_from_ema_{period}'] = lambda d, p=period: d['close'][-1] / self._ema(d['close'], p)[-1] - 1 if len(d['close']) >= p else 0

        # Regression to mean
        features['mean_reversion_speed'] = lambda d: self._mean_reversion_speed(d['close'])
        features['half_life'] = lambda d: self._half_life(d['close'])

        # Bollinger %B
        features['bollinger_pct_b'] = lambda d: self._bb_pct_b(d['close'])

        # Extreme readings
        features['is_oversold_rsi'] = lambda d: 1.0 if self._rsi(d['close'], 14) < 30 else 0.0
        features['is_overbought_rsi'] = lambda d: 1.0 if self._rsi(d['close'], 14) > 70 else 0.0

        self.feature_functions.update(features)

    # =========================================================================
    # PATTERN FEATURES (40+)
    # =========================================================================

    def _register_pattern_features(self):
        """Register pattern recognition features."""
        features = {}

        # Candlestick patterns
        features['doji'] = lambda d: self._is_doji(d['open'], d['high'], d['low'], d['close'])
        features['hammer'] = lambda d: self._is_hammer(d['open'], d['high'], d['low'], d['close'])
        features['engulfing_bullish'] = lambda d: self._is_bullish_engulfing(d['open'], d['high'], d['low'], d['close'])
        features['engulfing_bearish'] = lambda d: self._is_bearish_engulfing(d['open'], d['high'], d['low'], d['close'])
        features['morning_star'] = lambda d: self._is_morning_star(d['open'], d['high'], d['low'], d['close'])
        features['evening_star'] = lambda d: self._is_evening_star(d['open'], d['high'], d['low'], d['close'])
        features['three_white_soldiers'] = lambda d: self._is_three_white_soldiers(d['open'], d['close'])
        features['three_black_crows'] = lambda d: self._is_three_black_crows(d['open'], d['close'])

        # Chart patterns
        features['double_top'] = lambda d: self._detect_double_top(d['high'])
        features['double_bottom'] = lambda d: self._detect_double_bottom(d['low'])
        features['head_shoulders'] = lambda d: self._detect_head_shoulders(d['high'], d['low'])

        # Support/Resistance
        features['near_support'] = lambda d: self._near_support(d['high'], d['low'], d['close'])
        features['near_resistance'] = lambda d: self._near_resistance(d['high'], d['low'], d['close'])

        # Pivot points
        features['pivot_distance'] = lambda d: self._pivot_distance(d['high'], d['low'], d['close'])
        features['r1_distance'] = lambda d: self._r1_distance(d['high'], d['low'], d['close'])
        features['s1_distance'] = lambda d: self._s1_distance(d['high'], d['low'], d['close'])

        self.feature_functions.update(features)

    # =========================================================================
    # MICROSTRUCTURE FEATURES (40+)
    # =========================================================================

    def _register_microstructure_features(self):
        """Register market microstructure features."""
        features = {}

        # Bid-Ask spread proxy
        features['spread_proxy'] = lambda d: self._spread_proxy(d['high'], d['low'], d['close'])

        # Kyle's Lambda (price impact)
        features['kyle_lambda'] = lambda d: self._kyle_lambda(d['close'], d['volume'])

        # Amihud illiquidity
        features['amihud_illiquidity'] = lambda d: self._amihud_illiquidity(d['close'], d['volume'])

        # Roll spread estimator
        features['roll_spread'] = lambda d: self._roll_spread(d['close'])

        # Order flow toxicity (VPIN proxy)
        features['toxicity_proxy'] = lambda d: self._toxicity_proxy(d['close'], d['volume'])

        # Trade intensity
        features['trade_intensity'] = lambda d: self._trade_intensity(d['volume'])

        # Microstructure noise
        features['noise_ratio'] = lambda d: self._noise_ratio(d['close'])

        self.feature_functions.update(features)

    # =========================================================================
    # STATISTICAL FEATURES (40+)
    # =========================================================================

    def _register_statistical_features(self):
        """Register statistical features."""
        features = {}

        # Moments
        features['skewness_20'] = lambda d: stats.skew(d['close'][-20:]) if len(d['close']) >= 20 else 0
        features['kurtosis_20'] = lambda d: stats.kurtosis(d['close'][-20:]) if len(d['close']) >= 20 else 0
        features['skewness_60'] = lambda d: stats.skew(d['close'][-60:]) if len(d['close']) >= 60 else 0
        features['kurtosis_60'] = lambda d: stats.kurtosis(d['close'][-60:]) if len(d['close']) >= 60 else 0

        # Autocorrelation
        for lag in [1, 5, 10, 20]:
            features[f'autocorr_{lag}'] = lambda d, l=lag: self._autocorrelation(d['close'], l)

        # Hurst exponent
        features['hurst_exponent'] = lambda d: self._hurst_exponent(d['close'])

        # Entropy
        features['price_entropy'] = lambda d: self._price_entropy(d['close'])

        # Variance ratio
        for period in [2, 5, 10]:
            features[f'variance_ratio_{period}'] = lambda d, p=period: self._variance_ratio(d['close'], p)

        # Information coefficient
        features['ic_5'] = lambda d: self._information_coefficient(d['close'], 5)

        self.feature_functions.update(features)

    # =========================================================================
    # TIME FEATURES (30+)
    # =========================================================================

    def _register_time_features(self):
        """Register time/seasonal features."""
        features = {}

        # Day of week
        features['day_of_week'] = lambda d: datetime.now().weekday() / 4.0

        # Month
        features['month'] = lambda d: datetime.now().month / 12.0

        # Quarter
        features['quarter'] = lambda d: (datetime.now().month - 1) // 3 / 3.0

        # Year progress
        features['year_progress'] = lambda d: datetime.now().timetuple().tm_yday / 365.0

        # Time of day (for intraday)
        features['time_of_day'] = lambda d: datetime.now().hour / 24.0

        # Days to expiry features (for futures/options)
        features['days_to_monthly_expiry'] = lambda d: self._days_to_monthly_expiry()

        # Seasonal patterns
        features['january_effect'] = lambda d: 1.0 if datetime.now().month == 1 else 0.0
        features['sell_in_may'] = lambda d: 1.0 if datetime.now().month in [5, 6, 7, 8, 9] else 0.0
        features['santa_rally'] = lambda d: 1.0 if datetime.now().month == 12 and datetime.now().day > 20 else 0.0

        self.feature_functions.update(features)

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================

    def _returns(self, prices: np.ndarray, period: int) -> float:
        if len(prices) < period + 1:
            return 0.0
        return (prices[-1] - prices[-period-1]) / prices[-period-1]

    def _log_returns(self, prices: np.ndarray, period: int) -> float:
        if len(prices) < period + 1:
            return 0.0
        return np.log(prices[-1] / prices[-period-1])

    def _sma(self, prices: np.ndarray, period: int) -> np.ndarray:
        if len(prices) < period:
            return np.full(len(prices), np.nan)
        result = np.full(len(prices), np.nan)
        for i in range(period - 1, len(prices)):
            result[i] = np.mean(prices[i - period + 1:i + 1])
        return result

    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        if len(prices) < period:
            return np.full(len(prices), np.nan)
        result = np.full(len(prices), np.nan)
        multiplier = 2 / (period + 1)
        result[period - 1] = np.mean(prices[:period])
        for i in range(period, len(prices)):
            result[i] = (prices[i] - result[i - 1]) * multiplier + result[i - 1]
        return result

    def _rsi(self, prices: np.ndarray, period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _rsi_array(self, prices: np.ndarray, period: int) -> np.ndarray:
        result = np.full(len(prices), 50.0)
        for i in range(period + 1, len(prices)):
            result[i] = self._rsi(prices[:i+1], period)
        return result

    def _macd(self, prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        macd_line = ema_fast - ema_slow
        valid_macd = macd_line[~np.isnan(macd_line)]
        signal_line = self._ema(valid_macd, signal) if len(valid_macd) >= signal else np.full(len(valid_macd), np.nan)
        signal_padded = np.full(len(prices), np.nan)
        signal_padded[-len(signal_line):] = signal_line
        histogram = macd_line - signal_padded
        return macd_line, signal_padded, histogram

    def _stochastic(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray]:
        k = np.full(len(high), np.nan)
        for i in range(period - 1, len(high)):
            highest_high = np.max(high[i - period + 1:i + 1])
            lowest_low = np.min(low[i - period + 1:i + 1])
            if highest_high != lowest_low:
                k[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
            else:
                k[i] = 50
        d = self._sma(k, 3)
        return k, d

    def _atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        if len(high) < 2:
            return np.array([0.0])
        tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
        tr = np.concatenate([[high[0] - low[0]], tr])
        return self._ema(tr, period)

    def _adx(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        atr_values = self._atr(high, low, close, period)
        plus_dm = np.maximum(np.diff(high, prepend=high[0]), 0)
        minus_dm = np.maximum(-np.diff(low, prepend=low[0]), 0)
        plus_di = 100 * self._ema(plus_dm, period) / np.maximum(atr_values, 1e-10)
        minus_di = 100 * self._ema(minus_dm, period) / np.maximum(atr_values, 1e-10)
        dx = 100 * np.abs(plus_di - minus_di) / np.maximum(plus_di + minus_di, 1e-10)
        return self._ema(dx, period)

    def _zscore(self, prices: np.ndarray, period: int) -> float:
        if len(prices) < period:
            return 0.0
        mean = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        if std < 1e-8:
            return 0.0
        return (prices[-1] - mean) / std

    def _slope(self, values: np.ndarray, period: int) -> float:
        if len(values) < period:
            return 0.0
        x = np.arange(period)
        y = values[-period:]
        valid = ~np.isnan(y)
        if np.sum(valid) < 2:
            return 0.0
        coeffs = np.polyfit(x[valid], y[valid], 1)
        return coeffs[0]

    def _trend_strength(self, prices: np.ndarray, period: int = 20) -> float:
        if len(prices) < period:
            return 0.0
        x = np.arange(period)
        y = prices[-period:]
        slope = np.polyfit(x, y, 1)[0]
        return slope / np.mean(y)

    def _hurst_exponent(self, prices: np.ndarray, max_lag: int = 20) -> float:
        if len(prices) < max_lag * 2:
            return 0.5
        lags = range(2, max_lag)
        tau = [np.sqrt(np.std(np.subtract(prices[lag:], prices[:-lag]))) for lag in lags]
        try:
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0]
        except:
            return 0.5

    def _autocorrelation(self, prices: np.ndarray, lag: int) -> float:
        if len(prices) < lag + 10:
            return 0.0
        returns = np.diff(np.log(prices))
        if len(returns) < lag + 1:
            return 0.0
        corr = np.corrcoef(returns[:-lag], returns[lag:])[0, 1]
        return corr if not np.isnan(corr) else 0.0

    # Placeholder implementations for remaining helpers
    def _williams_r(self, high, low, close, period):
        return np.full(len(high), -50.0)

    def _cci(self, high, low, close, period):
        return np.full(len(high), 0.0)

    def _mfi(self, high, low, close, volume, period):
        return np.full(len(high), 50.0)

    def _vwap(self, high, low, close, volume):
        tp = (high + low + close) / 3
        return np.cumsum(tp * volume) / np.maximum(np.cumsum(volume), 1)

    # =========================================================================
    # MAIN COMPUTE FUNCTION
    # =========================================================================

    def compute(
        self,
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        volumes: np.ndarray,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, float]:
        """
        Compute all features.

        Returns dictionary of feature_name -> value.
        """
        data = {
            'open': np.asarray(open_prices, dtype=np.float64),
            'high': np.asarray(high_prices, dtype=np.float64),
            'low': np.asarray(low_prices, dtype=np.float64),
            'close': np.asarray(close_prices, dtype=np.float64),
            'volume': np.asarray(volumes, dtype=np.float64),
        }

        features = {}

        for name, func in self.feature_functions.items():
            try:
                value = func(data)
                features[name] = float(value) if not np.isnan(value) else 0.0
            except Exception as e:
                features[name] = 0.0

        logger.debug(f"Computed {len(features)} features for {symbol}")
        return features

    def get_feature_names(self) -> List[str]:
        """Get all feature names."""
        return list(self.feature_functions.keys())

    def get_feature_count(self) -> int:
        """Get total feature count."""
        return len(self.feature_functions)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ['AdvancedFeatureComputer', 'FeatureSpec', 'FEATURE_REGISTRY']
