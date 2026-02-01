"""
FUTURES FEATURE EXTRACTOR V2 - 96 Advanced Features for Deep Learning
======================================================================
Enhanced feature extraction for FuturesBrainV2 with:

1. Expanded Price Action (12 features)
2. Advanced Momentum (12 features)
3. Enhanced Trend Analysis (12 features)
4. Volatility & Regime (12 features)
5. Volume & Order Flow (12 features)
6. Time & Session Features (12 features)
7. Market Microstructure (12 features)
8. ML Signal Features (12 features)

Total: 96 features optimized for deep learning

Author: QuantBrain Futures V2
Version: 2.0.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, time
from dataclasses import dataclass
import logging
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger("FUTURES_FEATURES_V2")

# Try to import Numba, fall back to pure Python if not available
try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
    logger.info("Numba available - using JIT acceleration")
except ImportError:
    NUMBA_AVAILABLE = False
    logger.warning("Numba not available - using pure Python (slower)")
    # Create dummy decorators
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range


# =============================================================================
# ACCELERATED HELPERS (Numba JIT when available, pure Python fallback)
# =============================================================================

@jit(nopython=True, cache=True)
def _ema_numba(data: np.ndarray, period: int) -> np.ndarray:
    """Fast EMA calculation with Numba."""
    result = np.empty_like(data)
    multiplier = 2.0 / (period + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
    return result


@jit(nopython=True, cache=True)
def _rsi_numba(close: np.ndarray, period: int = 14) -> float:
    """Fast RSI calculation with Numba."""
    if len(close) < period + 1:
        return 50.0
    
    deltas = np.diff(close[-(period+1):])
    gains = np.zeros(period)
    losses = np.zeros(period)
    
    for i in range(period):
        if deltas[i] > 0:
            gains[i] = deltas[i]
        else:
            losses[i] = -deltas[i]
    
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@jit(nopython=True, cache=True)
def _atr_numba(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Fast ATR calculation with Numba."""
    n = len(close)
    if n < period + 1:
        return np.mean(high[-period:] - low[-period:])
    
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr[i] = max(hl, hc, lc)
    
    # Simple average for ATR
    return np.mean(tr[-period:])


@jit(nopython=True, cache=True)
def _stochastic_numba(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                      k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
    """Fast Stochastic calculation with Numba."""
    n = len(close)
    if n < k_period:
        return 50.0, 50.0
    
    # %K
    k_values = np.zeros(d_period)
    for i in range(d_period):
        idx = n - d_period + i
        highest = np.max(high[max(0, idx-k_period+1):idx+1])
        lowest = np.min(low[max(0, idx-k_period+1):idx+1])
        if highest == lowest:
            k_values[i] = 50.0
        else:
            k_values[i] = 100 * (close[idx] - lowest) / (highest - lowest)
    
    k = k_values[-1]
    d = np.mean(k_values)
    
    return k, d


@jit(nopython=True, cache=True)
def _adx_numba(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Fast ADX calculation with Numba."""
    n = len(close)
    if n < period + 1:
        return 25.0
    
    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    
    for i in range(1, n):
        h_diff = high[i] - high[i-1]
        l_diff = low[i-1] - low[i]
        
        plus_dm[i] = h_diff if h_diff > l_diff and h_diff > 0 else 0
        minus_dm[i] = l_diff if l_diff > h_diff and l_diff > 0 else 0
        
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr[i] = max(hl, hc, lc)
    
    atr = np.mean(tr[-period:])
    plus_di = 100 * np.mean(plus_dm[-period:]) / (atr + 1e-8)
    minus_di = 100 * np.mean(minus_dm[-period:]) / (atr + 1e-8)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
    return dx


# =============================================================================
# FEATURE GROUPS
# =============================================================================

@dataclass
class FeatureGroup:
    """Container for a group of features."""
    name: str
    features: List[str]
    values: np.ndarray


class FuturesFeatureExtractorV2:
    """
    Advanced 96-feature extractor for futures trading.
    Optimized for micro futures (MNQ, MES) and prop firm scalping.
    """
    
    def __init__(self):
        self.n_features = 96
        self.feature_names = self._build_feature_names()
        self._cache = {}
        
        # Feature group indices for easy access
        self.group_indices = {
            'price_action': slice(0, 12),
            'momentum': slice(12, 24),
            'trend': slice(24, 36),
            'volatility': slice(36, 48),
            'volume': slice(48, 60),
            'time': slice(60, 72),
            'microstructure': slice(72, 84),
            'ml_signals': slice(84, 96)
        }
    
    def _build_feature_names(self) -> List[str]:
        """Build list of all 96 feature names."""
        return [
            # ========== PRICE ACTION (12) ==========
            'returns_1', 'returns_3', 'returns_5', 'returns_15',
            'returns_30', 'returns_60', 'high_low_range', 'close_position',
            'gap', 'body_ratio', 'upper_wick', 'lower_wick',
            
            # ========== MOMENTUM (12) ==========
            'rsi_14', 'rsi_7', 'rsi_3', 'stoch_k',
            'stoch_d', 'roc_5', 'roc_10', 'roc_20',
            'momentum_5', 'momentum_10', 'cci_20', 'willr_14',
            
            # ========== TREND (12) ==========
            'ema_5_slope', 'ema_13_slope', 'ema_21_slope', 'ema_50_slope',
            'price_vs_ema5', 'price_vs_ema13', 'price_vs_ema21', 'price_vs_ema50',
            'trend_strength', 'adx', 'plus_di', 'minus_di',
            
            # ========== VOLATILITY & REGIME (12) ==========
            'atr_14_pct', 'atr_ratio', 'bb_width', 'bb_position',
            'volatility_5', 'volatility_15', 'range_expansion', 'squeeze',
            'keltner_position', 'volatility_regime', 'realized_vol', 'vol_of_vol',
            
            # ========== VOLUME & ORDER FLOW (12) ==========
            'volume_ratio', 'volume_trend', 'obv_slope', 'vwap_distance',
            'volume_momentum', 'buy_volume_pct', 'sell_volume_pct', 'volume_imbalance',
            'cumulative_delta', 'delta_divergence', 'money_flow', 'volume_pressure',
            
            # ========== TIME & SESSION (12) ==========
            'hour_sin', 'hour_cos', 'minute_sin', 'minute_cos',
            'day_of_week_sin', 'day_of_week_cos', 'session_type', 'time_to_close',
            'is_high_volume_time', 'is_news_window', 'bars_since_session_open', 'session_range_pct',
            
            # ========== MICROSTRUCTURE (12) ==========
            'pivot_distance', 'r1_distance', 's1_distance', 'r2_distance',
            's2_distance', 'daily_high_dist', 'daily_low_dist', 'prior_day_close_dist',
            'swing_high_dist', 'swing_low_dist', 'consolidation_score', 'breakout_probability',
            
            # ========== ML SIGNAL FEATURES (12) ==========
            'signal_strength', 'signal_persistence', 'signal_agreement', 'confidence_trend',
            'regime_stability', 'prediction_entropy', 'model_divergence', 'uncertainty_level',
            'trend_alignment', 'momentum_alignment', 'volume_confirmation', 'pattern_score'
        ]
    
    def extract_features(self, df: pd.DataFrame, timestamp: datetime = None,
                        ml_signals: Dict[str, float] = None) -> np.ndarray:
        """
        Extract all 96 features from OHLCV DataFrame.
        
        Args:
            df: DataFrame with columns [open, high, low, close, volume]
            timestamp: Optional timestamp for time features (default: now)
            ml_signals: Optional dict of ML signal features
        
        Returns:
            numpy array of shape (96,)
        """
        n = len(df)
        if n < 60:
            logger.warning(f"Insufficient data: {n} < 60 bars")
            return np.zeros(self.n_features)
        
        features = np.zeros(self.n_features)
        
        # Normalize column names
        close = df['close'].values if 'close' in df.columns else df['Close'].values
        high = df['high'].values if 'high' in df.columns else df['High'].values
        low = df['low'].values if 'low' in df.columns else df['Low'].values
        open_ = df['open'].values if 'open' in df.columns else df['Open'].values
        volume = df['volume'].values if 'volume' in df.columns else df.get('Volume', np.ones(n)).values
        
        timestamp = timestamp or datetime.now()
        
        # Pre-compute EMAs
        ema_5 = _ema_numba(close, 5)
        ema_13 = _ema_numba(close, 13)
        ema_21 = _ema_numba(close, 21)
        ema_50 = _ema_numba(close, 50) if n >= 50 else _ema_numba(close, n)
        
        idx = 0
        
        # ====================================================================
        # 1. PRICE ACTION (12 features)
        # ====================================================================
        features[idx] = (close[-1] / close[-2] - 1) * 100; idx += 1  # returns_1
        features[idx] = (close[-1] / close[-4] - 1) * 100; idx += 1  # returns_3
        features[idx] = (close[-1] / close[-6] - 1) * 100; idx += 1  # returns_5
        features[idx] = (close[-1] / close[max(0, -16)] - 1) * 100; idx += 1  # returns_15
        features[idx] = (close[-1] / close[max(0, -31)] - 1) * 100; idx += 1  # returns_30
        features[idx] = (close[-1] / close[max(0, -61)] - 1) * 100; idx += 1  # returns_60
        features[idx] = (high[-1] - low[-1]) / close[-1] * 100; idx += 1  # high_low_range
        features[idx] = (close[-1] - low[-1]) / (high[-1] - low[-1] + 1e-8); idx += 1  # close_position
        features[idx] = (open_[-1] - close[-2]) / close[-2] * 100; idx += 1  # gap
        features[idx] = abs(close[-1] - open_[-1]) / (high[-1] - low[-1] + 1e-8); idx += 1  # body_ratio
        
        # Upper and lower wicks
        body_high = max(open_[-1], close[-1])
        body_low = min(open_[-1], close[-1])
        features[idx] = (high[-1] - body_high) / (high[-1] - low[-1] + 1e-8); idx += 1  # upper_wick
        features[idx] = (body_low - low[-1]) / (high[-1] - low[-1] + 1e-8); idx += 1  # lower_wick
        
        # ====================================================================
        # 2. MOMENTUM (12 features)
        # ====================================================================
        features[idx] = _rsi_numba(close, 14); idx += 1  # rsi_14
        features[idx] = _rsi_numba(close, 7); idx += 1  # rsi_7
        features[idx] = _rsi_numba(close, 3); idx += 1  # rsi_3
        stoch_k, stoch_d = _stochastic_numba(high, low, close)
        features[idx] = stoch_k; idx += 1  # stoch_k
        features[idx] = stoch_d; idx += 1  # stoch_d
        features[idx] = (close[-1] / close[-6] - 1) * 100; idx += 1  # roc_5
        features[idx] = (close[-1] / close[-11] - 1) * 100; idx += 1  # roc_10
        features[idx] = (close[-1] / close[-21] - 1) * 100; idx += 1  # roc_20
        features[idx] = close[-1] - close[-6]; idx += 1  # momentum_5
        features[idx] = close[-1] - close[-11]; idx += 1  # momentum_10
        
        # CCI
        typical_price = (high[-20:] + low[-20:] + close[-20:]) / 3
        mean_tp = np.mean(typical_price)
        mean_dev = np.mean(np.abs(typical_price - mean_tp))
        features[idx] = (typical_price[-1] - mean_tp) / (0.015 * mean_dev + 1e-8); idx += 1  # cci_20
        
        # Williams %R
        highest_14 = np.max(high[-14:])
        lowest_14 = np.min(low[-14:])
        features[idx] = -100 * (highest_14 - close[-1]) / (highest_14 - lowest_14 + 1e-8); idx += 1  # willr_14
        
        # ====================================================================
        # 3. TREND (12 features)
        # ====================================================================
        features[idx] = (ema_5[-1] - ema_5[-6]) / ema_5[-6] * 100; idx += 1  # ema_5_slope
        features[idx] = (ema_13[-1] - ema_13[-6]) / ema_13[-6] * 100; idx += 1  # ema_13_slope
        features[idx] = (ema_21[-1] - ema_21[-6]) / ema_21[-6] * 100; idx += 1  # ema_21_slope
        features[idx] = (ema_50[-1] - ema_50[-6]) / ema_50[-6] * 100; idx += 1  # ema_50_slope
        features[idx] = (close[-1] / ema_5[-1] - 1) * 100; idx += 1  # price_vs_ema5
        features[idx] = (close[-1] / ema_13[-1] - 1) * 100; idx += 1  # price_vs_ema13
        features[idx] = (close[-1] / ema_21[-1] - 1) * 100; idx += 1  # price_vs_ema21
        features[idx] = (close[-1] / ema_50[-1] - 1) * 100; idx += 1  # price_vs_ema50
        
        # Trend strength
        if ema_5[-1] > ema_13[-1] > ema_21[-1] > ema_50[-1]:
            trend_str = 1.0  # Strong uptrend
        elif ema_5[-1] < ema_13[-1] < ema_21[-1] < ema_50[-1]:
            trend_str = -1.0  # Strong downtrend
        elif ema_5[-1] > ema_13[-1] > ema_21[-1]:
            trend_str = 0.5  # Moderate uptrend
        elif ema_5[-1] < ema_13[-1] < ema_21[-1]:
            trend_str = -0.5  # Moderate downtrend
        else:
            trend_str = 0.0  # No clear trend
        features[idx] = trend_str; idx += 1  # trend_strength
        
        features[idx] = _adx_numba(high, low, close, 14); idx += 1  # adx
        
        # +DI and -DI (simplified)
        tr_sum = _atr_numba(high, low, close, 14) * 14
        plus_dm = np.sum(np.maximum(np.diff(high[-15:]), 0))
        minus_dm = np.sum(np.maximum(-np.diff(low[-15:]), 0))
        features[idx] = 100 * plus_dm / (tr_sum + 1e-8); idx += 1  # plus_di
        features[idx] = 100 * minus_dm / (tr_sum + 1e-8); idx += 1  # minus_di
        
        # ====================================================================
        # 4. VOLATILITY & REGIME (12 features)
        # ====================================================================
        atr_14 = _atr_numba(high, low, close, 14)
        atr_7 = _atr_numba(high, low, close, 7)
        features[idx] = atr_14 / close[-1] * 100; idx += 1  # atr_14_pct
        features[idx] = atr_7 / atr_14 if atr_14 > 0 else 1; idx += 1  # atr_ratio
        
        # Bollinger Bands
        bb_period = 20
        bb_std = 2.0
        sma_20 = np.mean(close[-bb_period:])
        std_20 = np.std(close[-bb_period:])
        bb_upper = sma_20 + bb_std * std_20
        bb_lower = sma_20 - bb_std * std_20
        bb_width = (bb_upper - bb_lower) / sma_20
        bb_pos = (close[-1] - bb_lower) / (bb_upper - bb_lower + 1e-8)
        features[idx] = bb_width; idx += 1  # bb_width
        features[idx] = bb_pos; idx += 1  # bb_position
        
        features[idx] = np.std(close[-6:]) / close[-1] * 100; idx += 1  # volatility_5
        features[idx] = np.std(close[-16:]) / close[-1] * 100; idx += 1  # volatility_15
        
        recent_range = np.mean(high[-6:] - low[-6:])
        avg_range = np.mean(high[-21:] - low[-21:])
        features[idx] = recent_range / avg_range if avg_range > 0 else 1; idx += 1  # range_expansion
        
        # Squeeze detection (BB inside Keltner)
        keltner_mult = 1.5
        keltner_upper = ema_21[-1] + keltner_mult * atr_14
        keltner_lower = ema_21[-1] - keltner_mult * atr_14
        squeeze = 1 if (bb_lower > keltner_lower and bb_upper < keltner_upper) else 0
        features[idx] = squeeze; idx += 1  # squeeze
        
        # Keltner position
        features[idx] = (close[-1] - keltner_lower) / (keltner_upper - keltner_lower + 1e-8); idx += 1  # keltner_position
        
        # Volatility regime (0=quiet, 1=normal, 2=high, 3=extreme)
        vol_percentile = np.percentile(np.std(close[-60:].reshape(-1, 5), axis=1), 50)
        current_vol = np.std(close[-5:])
        if current_vol < vol_percentile * 0.5:
            vol_regime = 0
        elif current_vol < vol_percentile:
            vol_regime = 1
        elif current_vol < vol_percentile * 1.5:
            vol_regime = 2
        else:
            vol_regime = 3
        features[idx] = vol_regime; idx += 1  # volatility_regime
        
        # Realized volatility (annualized)
        returns = np.diff(np.log(close[-21:]))
        realized_vol = np.std(returns) * np.sqrt(252 * 78)  # 78 5-min bars per day
        features[idx] = realized_vol; idx += 1  # realized_vol
        
        # Vol of vol
        vol_series = np.array([np.std(close[max(0,i-5):i+1]) for i in range(n-20, n)])
        features[idx] = np.std(vol_series) / (np.mean(vol_series) + 1e-8); idx += 1  # vol_of_vol
        
        # ====================================================================
        # 5. VOLUME & ORDER FLOW (12 features)
        # ====================================================================
        vol_ma = np.mean(volume[-21:])
        features[idx] = volume[-1] / vol_ma if vol_ma > 0 else 1; idx += 1  # volume_ratio
        features[idx] = (np.mean(volume[-6:]) / vol_ma - 1) * 100 if vol_ma > 0 else 0; idx += 1  # volume_trend
        
        # OBV slope
        obv = np.cumsum(np.where(np.diff(close) > 0, volume[1:], 
                                 np.where(np.diff(close) < 0, -volume[1:], 0)))
        obv = np.concatenate([[0], obv])
        features[idx] = (obv[-1] - obv[-6]) / (abs(obv[-6]) + 1e-8) * 100; idx += 1  # obv_slope
        
        # VWAP distance
        vwap = np.sum(close[-20:] * volume[-20:]) / (np.sum(volume[-20:]) + 1e-8)
        features[idx] = (close[-1] / vwap - 1) * 100; idx += 1  # vwap_distance
        
        features[idx] = volume[-1] / (volume[-2] + 1e-8); idx += 1  # volume_momentum
        
        # Estimate buy/sell volume (price direction proxy)
        buy_mask = close > open_
        sell_mask = close < open_
        recent_vol = volume[-20:]
        recent_buy = buy_mask[-20:]
        recent_sell = sell_mask[-20:]
        total_vol = np.sum(recent_vol) + 1e-8
        features[idx] = np.sum(recent_vol[recent_buy]) / total_vol; idx += 1  # buy_volume_pct
        features[idx] = np.sum(recent_vol[recent_sell]) / total_vol; idx += 1  # sell_volume_pct
        
        # Volume imbalance
        features[idx] = features[idx-2] - features[idx-1]; idx += 1  # volume_imbalance
        
        # Cumulative delta (proxy)
        delta = np.where(close > open_, volume, np.where(close < open_, -volume, 0))
        cum_delta = np.cumsum(delta[-20:])
        features[idx] = cum_delta[-1] / (np.sum(np.abs(delta[-20:])) + 1e-8); idx += 1  # cumulative_delta
        
        # Delta divergence (price up, delta down or vice versa)
        price_change = close[-1] - close[-6]
        delta_change = cum_delta[-1] - cum_delta[0]
        divergence = 1 if (price_change > 0 and delta_change < 0) or (price_change < 0 and delta_change > 0) else 0
        features[idx] = divergence; idx += 1  # delta_divergence
        
        # Money flow
        raw_mf = typical_price[-1] * volume[-1]
        avg_mf = np.mean(typical_price[-14:] * volume[-14:])
        features[idx] = raw_mf / (avg_mf + 1e-8) - 1; idx += 1  # money_flow
        
        # Volume pressure (signed volume relative to average)
        signed_vol = np.where(close[-6:] > open_[-6:], volume[-6:], -volume[-6:])
        features[idx] = np.sum(signed_vol) / (vol_ma * 6 + 1e-8); idx += 1  # volume_pressure
        
        # ====================================================================
        # 6. TIME & SESSION (12 features)
        # ====================================================================
        hour = timestamp.hour + timestamp.minute / 60
        features[idx] = np.sin(2 * np.pi * hour / 24); idx += 1  # hour_sin
        features[idx] = np.cos(2 * np.pi * hour / 24); idx += 1  # hour_cos
        features[idx] = np.sin(2 * np.pi * timestamp.minute / 60); idx += 1  # minute_sin
        features[idx] = np.cos(2 * np.pi * timestamp.minute / 60); idx += 1  # minute_cos
        
        dow = timestamp.weekday()
        features[idx] = np.sin(2 * np.pi * dow / 5); idx += 1  # day_of_week_sin
        features[idx] = np.cos(2 * np.pi * dow / 5); idx += 1  # day_of_week_cos
        
        # Session type: 0=overnight, 1=premarket, 2=regular, 3=afterhours
        if 0 <= hour < 4:
            session = 0  # Overnight
        elif 4 <= hour < 9.5:
            session = 1  # Premarket
        elif 9.5 <= hour < 16:
            session = 2  # Regular
        else:
            session = 3  # After hours
        features[idx] = session; idx += 1  # session_type
        
        # Time to close (regular session)
        if 9.5 <= hour < 16:
            features[idx] = (16 - hour) / 6.5; idx += 1  # time_to_close
        else:
            features[idx] = 0; idx += 1  # time_to_close
        
        # High volume time windows
        is_high_vol = 1 if (9 <= hour <= 10.5) or (14.5 <= hour <= 16) else 0
        features[idx] = is_high_vol; idx += 1  # is_high_volume_time
        
        # News window (typically around major data releases)
        is_news = 1 if (8.25 <= hour <= 8.75) or (9.75 <= hour <= 10.25) else 0
        features[idx] = is_news; idx += 1  # is_news_window
        
        # Bars since session open (assuming 5-min bars)
        if hour >= 9.5:
            bars_since_open = int((hour - 9.5) * 12)  # 12 five-min bars per hour
        else:
            bars_since_open = 0
        features[idx] = min(bars_since_open / 78, 1.0); idx += 1  # bars_since_session_open (normalized)
        
        # Session range percentage used
        if session == 2:  # Regular session
            session_high = np.max(high[-min(bars_since_open+1, len(high)):])
            session_low = np.min(low[-min(bars_since_open+1, len(low)):])
            session_range = session_high - session_low
            typical_range = atr_14 * 3  # Rough estimate
            features[idx] = session_range / (typical_range + 1e-8); idx += 1  # session_range_pct
        else:
            features[idx] = 0; idx += 1  # session_range_pct
        
        # ====================================================================
        # 7. MICROSTRUCTURE (12 features)
        # ====================================================================
        # Daily pivot points (using prior day's high/low/close approximation)
        # Use last 78 bars (approx 1 day of 5-min bars) if available
        lookback = min(78, n-1)
        prior_high = np.max(high[-lookback-1:-1]) if lookback > 0 else high[-1]
        prior_low = np.min(low[-lookback-1:-1]) if lookback > 0 else low[-1]
        prior_close = close[-lookback-1] if lookback > 0 else close[-1]
        
        pivot = (prior_high + prior_low + prior_close) / 3
        r1 = 2 * pivot - prior_low
        s1 = 2 * pivot - prior_high
        r2 = pivot + (prior_high - prior_low)
        s2 = pivot - (prior_high - prior_low)
        
        features[idx] = (close[-1] - pivot) / (atr_14 + 1e-8); idx += 1  # pivot_distance
        features[idx] = (close[-1] - r1) / (atr_14 + 1e-8); idx += 1  # r1_distance
        features[idx] = (close[-1] - s1) / (atr_14 + 1e-8); idx += 1  # s1_distance
        features[idx] = (close[-1] - r2) / (atr_14 + 1e-8); idx += 1  # r2_distance
        features[idx] = (close[-1] - s2) / (atr_14 + 1e-8); idx += 1  # s2_distance
        
        # Daily high/low distance
        day_high = np.max(high[-lookback:]) if lookback > 0 else high[-1]
        day_low = np.min(low[-lookback:]) if lookback > 0 else low[-1]
        features[idx] = (close[-1] - day_high) / (atr_14 + 1e-8); idx += 1  # daily_high_dist
        features[idx] = (close[-1] - day_low) / (atr_14 + 1e-8); idx += 1  # daily_low_dist
        features[idx] = (close[-1] - prior_close) / (atr_14 + 1e-8); idx += 1  # prior_day_close_dist
        
        # Swing high/low detection
        swing_lookback = 20
        swing_highs = []
        swing_lows = []
        for i in range(-swing_lookback, -2):
            if high[i] > high[i-1] and high[i] > high[i+1]:
                swing_highs.append(high[i])
            if low[i] < low[i-1] and low[i] < low[i+1]:
                swing_lows.append(low[i])
        
        nearest_swing_high = min(swing_highs, default=high[-1]) if swing_highs else np.max(high[-swing_lookback:])
        nearest_swing_low = max(swing_lows, default=low[-1]) if swing_lows else np.min(low[-swing_lookback:])
        features[idx] = (close[-1] - nearest_swing_high) / (atr_14 + 1e-8); idx += 1  # swing_high_dist
        features[idx] = (close[-1] - nearest_swing_low) / (atr_14 + 1e-8); idx += 1  # swing_low_dist
        
        # Consolidation score (low range + low volume)
        range_score = 1 - min(recent_range / avg_range, 2) / 2  # Normalize to 0-1
        vol_score = 1 - min(np.mean(volume[-6:]) / vol_ma, 2) / 2
        features[idx] = (range_score + vol_score) / 2; idx += 1  # consolidation_score
        
        # Breakout probability
        at_resistance = close[-1] > nearest_swing_high * 0.998
        at_support = close[-1] < nearest_swing_low * 1.002
        volume_surge = volume[-1] > vol_ma * 1.5
        breakout_prob = 0.5
        if (at_resistance or at_support) and volume_surge:
            breakout_prob = 0.8
        elif at_resistance or at_support:
            breakout_prob = 0.6
        features[idx] = breakout_prob; idx += 1  # breakout_probability
        
        # ====================================================================
        # 8. ML SIGNAL FEATURES (12 features)
        # ====================================================================
        if ml_signals:
            features[idx] = ml_signals.get('signal_strength', 0.5); idx += 1
            features[idx] = ml_signals.get('signal_persistence', 0.5); idx += 1
            features[idx] = ml_signals.get('signal_agreement', 0.5); idx += 1
            features[idx] = ml_signals.get('confidence_trend', 0.5); idx += 1
            features[idx] = ml_signals.get('regime_stability', 0.5); idx += 1
            features[idx] = ml_signals.get('prediction_entropy', 0.5); idx += 1
            features[idx] = ml_signals.get('model_divergence', 0.5); idx += 1
            features[idx] = ml_signals.get('uncertainty_level', 0.5); idx += 1
            features[idx] = ml_signals.get('trend_alignment', 0.5); idx += 1
            features[idx] = ml_signals.get('momentum_alignment', 0.5); idx += 1
            features[idx] = ml_signals.get('volume_confirmation', 0.5); idx += 1
            features[idx] = ml_signals.get('pattern_score', 0.5); idx += 1
        else:
            # Default ML signals based on technical analysis
            features[idx] = abs(features[0]) / 2  # signal_strength from returns; idx += 1
            features[idx] = 0.5; idx += 1  # signal_persistence (placeholder)
            features[idx] = 0.5; idx += 1  # signal_agreement (placeholder)
            features[idx] = 0.5; idx += 1  # confidence_trend (placeholder)
            features[idx] = 0.5; idx += 1  # regime_stability (placeholder)
            features[idx] = 0.5; idx += 1  # prediction_entropy (placeholder)
            features[idx] = 0.0; idx += 1  # model_divergence (placeholder)
            features[idx] = 0.5; idx += 1  # uncertainty_level (placeholder)
            
            # Derive trend/momentum alignment from existing features
            trend_align = features[8]  # trend_strength
            mom_align = 1 if features[0] * trend_align > 0 else 0  # returns aligned with trend
            features[idx] = (trend_align + 1) / 2; idx += 1  # trend_alignment (normalized)
            features[idx] = mom_align; idx += 1  # momentum_alignment
            features[idx] = 1 if volume[-1] > vol_ma and abs(features[0]) > 0.1 else 0; idx += 1  # volume_confirmation
            features[idx] = 0.5; idx += 1  # pattern_score (placeholder)
        
        return features
    
    def extract_batch(self, df: pd.DataFrame, timestamps: List[datetime] = None) -> np.ndarray:
        """
        Extract features for multiple timestamps (sliding window).
        
        Args:
            df: Full DataFrame with OHLCV data
            timestamps: List of timestamps to extract features for
        
        Returns:
            numpy array of shape (len(timestamps), 96)
        """
        n = len(df)
        if timestamps is None:
            timestamps = [datetime.now()] * n
        
        batch_features = np.zeros((len(timestamps), self.n_features))
        
        for i, ts in enumerate(timestamps):
            # Use all data up to this point
            end_idx = min(i + 60, n)
            if end_idx - i < 30:
                continue
            batch_features[i] = self.extract_features(df.iloc[:end_idx], ts)
        
        return batch_features
    
    def get_feature_group(self, features: np.ndarray, group_name: str) -> np.ndarray:
        """Extract a specific feature group."""
        if group_name not in self.group_indices:
            raise ValueError(f"Unknown group: {group_name}. Available: {list(self.group_indices.keys())}")
        return features[..., self.group_indices[group_name]]
    
    def normalize_features(self, features: np.ndarray, 
                          means: np.ndarray = None, 
                          stds: np.ndarray = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Z-score normalize features.
        
        Returns: (normalized_features, means, stds)
        """
        if means is None:
            means = np.mean(features, axis=0, keepdims=True)
        if stds is None:
            stds = np.std(features, axis=0, keepdims=True) + 1e-8
        
        normalized = (features - means) / stds
        
        # Clip extreme values
        normalized = np.clip(normalized, -5, 5)
        
        return normalized, means.squeeze(), stds.squeeze()


# Factory function
def create_feature_extractor() -> FuturesFeatureExtractorV2:
    """Create feature extractor instance."""
    return FuturesFeatureExtractorV2()


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    extractor = create_feature_extractor()
    
    # Generate test data
    np.random.seed(42)
    n = 100
    test_df = pd.DataFrame({
        'open': 100 + np.cumsum(np.random.randn(n) * 0.1),
        'high': 100 + np.cumsum(np.random.randn(n) * 0.1) + 0.5,
        'low': 100 + np.cumsum(np.random.randn(n) * 0.1) - 0.5,
        'close': 100 + np.cumsum(np.random.randn(n) * 0.1),
        'volume': np.random.randint(100, 1000, n)
    })
    test_df['high'] = np.maximum(test_df['high'], test_df[['open', 'close']].max(axis=1))
    test_df['low'] = np.minimum(test_df['low'], test_df[['open', 'close']].min(axis=1))
    
    features = extractor.extract_features(test_df)
    
    print(f"\nExtracted {len(features)} features")
    print(f"Feature names: {extractor.feature_names[:10]}...")
    print(f"\nFeature groups:")
    for name, idx in extractor.group_indices.items():
        group_features = features[idx]
        print(f"  {name}: {len(group_features)} features, mean={np.mean(group_features):.3f}")
    
    # Test batch extraction
    batch = extractor.extract_batch(test_df)
    print(f"\nBatch shape: {batch.shape}")
