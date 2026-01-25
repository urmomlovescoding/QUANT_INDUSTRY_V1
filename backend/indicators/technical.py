"""
QUANT INDUSTRY - Technical Indicators
Comprehensive technical analysis calculations
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


def calculate_sma(data: Union[List[float], np.ndarray], period: int) -> np.ndarray:
    """Calculate Simple Moving Average"""
    data = np.array(data)
    if len(data) < period:
        return np.array([np.nan] * len(data))

    sma = np.full(len(data), np.nan)
    for i in range(period - 1, len(data)):
        sma[i] = np.mean(data[i - period + 1:i + 1])

    return sma


def calculate_ema(data: Union[List[float], np.ndarray], period: int) -> np.ndarray:
    """Calculate Exponential Moving Average"""
    data = np.array(data)
    if len(data) < period:
        return np.array([np.nan] * len(data))

    ema = np.full(len(data), np.nan)
    multiplier = 2 / (period + 1)

    # First EMA is SMA
    ema[period - 1] = np.mean(data[:period])

    for i in range(period, len(data)):
        ema[i] = (data[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

    return ema


def calculate_rsi(data: Union[List[float], np.ndarray], period: int = 14) -> np.ndarray:
    """Calculate Relative Strength Index"""
    data = np.array(data)
    if len(data) < period + 1:
        return np.array([np.nan] * len(data))

    deltas = np.diff(data)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    rsi = np.full(len(data), np.nan)

    # Initial averages
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        rsi[period] = 100
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100 - (100 / (1 + rs))

    # Calculate remaining RSI values
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi[i + 1] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(
    data: Union[List[float], np.ndarray],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate MACD, Signal Line, and Histogram

    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    data = np.array(data)

    ema_fast = calculate_ema(data, fast_period)
    ema_slow = calculate_ema(data, slow_period)

    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line[~np.isnan(macd_line)], signal_period)

    # Pad signal line to match length
    padded_signal = np.full(len(data), np.nan)
    start_idx = len(data) - len(signal_line)
    padded_signal[start_idx:] = signal_line

    histogram = macd_line - padded_signal

    return macd_line, padded_signal, histogram


def calculate_bollinger_bands(
    data: Union[List[float], np.ndarray],
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    data = np.array(data)

    middle = calculate_sma(data, period)
    std = np.full(len(data), np.nan)

    for i in range(period - 1, len(data)):
        std[i] = np.std(data[i - period + 1:i + 1])

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return upper, middle, lower


def calculate_atr(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    period: int = 14
) -> np.ndarray:
    """Calculate Average True Range"""
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)

    tr = np.full(len(high), np.nan)
    tr[0] = high[0] - low[0]

    for i in range(1, len(high)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )

    atr = np.full(len(high), np.nan)
    atr[period - 1] = np.mean(tr[:period])

    for i in range(period, len(high)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def calculate_adx(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    period: int = 14
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Average Directional Index

    Returns:
        Tuple of (adx, plus_di, minus_di)
    """
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    n = len(high)

    # True Range
    tr = np.full(n, np.nan)
    tr[0] = high[0] - low[0]

    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )

    # +DM and -DM
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Smoothed TR, +DM, -DM
    smoothed_tr = np.full(n, np.nan)
    smoothed_plus_dm = np.full(n, np.nan)
    smoothed_minus_dm = np.full(n, np.nan)

    smoothed_tr[period - 1] = np.sum(tr[:period])
    smoothed_plus_dm[period - 1] = np.sum(plus_dm[:period])
    smoothed_minus_dm[period - 1] = np.sum(minus_dm[:period])

    for i in range(period, n):
        smoothed_tr[i] = smoothed_tr[i - 1] - (smoothed_tr[i - 1] / period) + tr[i]
        smoothed_plus_dm[i] = smoothed_plus_dm[i - 1] - (smoothed_plus_dm[i - 1] / period) + plus_dm[i]
        smoothed_minus_dm[i] = smoothed_minus_dm[i - 1] - (smoothed_minus_dm[i - 1] / period) + minus_dm[i]

    # +DI and -DI
    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)

    for i in range(period - 1, n):
        if smoothed_tr[i] > 0:
            plus_di[i] = 100 * smoothed_plus_dm[i] / smoothed_tr[i]
            minus_di[i] = 100 * smoothed_minus_dm[i] / smoothed_tr[i]

    # DX and ADX
    dx = np.full(n, np.nan)
    adx = np.full(n, np.nan)

    for i in range(period - 1, n):
        if plus_di[i] + minus_di[i] > 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i])

    # First ADX is average of first 'period' DX values
    valid_dx = dx[~np.isnan(dx)]
    if len(valid_dx) >= period:
        first_adx_idx = period - 1 + period - 1
        if first_adx_idx < n:
            adx[first_adx_idx] = np.mean(valid_dx[:period])

            for i in range(first_adx_idx + 1, n):
                if not np.isnan(dx[i]):
                    adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return adx, plus_di, minus_di


def calculate_stochastic(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    k_period: int = 14,
    d_period: int = 3
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate Stochastic Oscillator

    Returns:
        Tuple of (k_line, d_line)
    """
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    n = len(high)

    k_line = np.full(n, np.nan)

    for i in range(k_period - 1, n):
        highest_high = np.max(high[i - k_period + 1:i + 1])
        lowest_low = np.min(low[i - k_period + 1:i + 1])

        if highest_high - lowest_low > 0:
            k_line[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
        else:
            k_line[i] = 50

    d_line = calculate_sma(k_line[~np.isnan(k_line)], d_period)

    # Pad d_line
    padded_d = np.full(n, np.nan)
    start_idx = n - len(d_line)
    padded_d[start_idx:] = d_line

    return k_line, padded_d


def calculate_vwap(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    volume: Union[List[float], np.ndarray]
) -> np.ndarray:
    """Calculate Volume Weighted Average Price"""
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    volume = np.array(volume)

    typical_price = (high + low + close) / 3
    cumulative_tpv = np.cumsum(typical_price * volume)
    cumulative_volume = np.cumsum(volume)

    vwap = cumulative_tpv / cumulative_volume

    return vwap


def calculate_obv(
    close: Union[List[float], np.ndarray],
    volume: Union[List[float], np.ndarray]
) -> np.ndarray:
    """Calculate On-Balance Volume"""
    close = np.array(close)
    volume = np.array(volume)
    n = len(close)

    obv = np.zeros(n)
    obv[0] = volume[0]

    for i in range(1, n):
        if close[i] > close[i - 1]:
            obv[i] = obv[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv[i] = obv[i - 1] - volume[i]
        else:
            obv[i] = obv[i - 1]

    return obv


def calculate_williams_r(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    period: int = 14
) -> np.ndarray:
    """Calculate Williams %R"""
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    n = len(high)

    williams_r = np.full(n, np.nan)

    for i in range(period - 1, n):
        highest_high = np.max(high[i - period + 1:i + 1])
        lowest_low = np.min(low[i - period + 1:i + 1])

        if highest_high - lowest_low > 0:
            williams_r[i] = -100 * (highest_high - close[i]) / (highest_high - lowest_low)
        else:
            williams_r[i] = -50

    return williams_r


def calculate_cci(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    period: int = 20
) -> np.ndarray:
    """Calculate Commodity Channel Index"""
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    n = len(high)

    typical_price = (high + low + close) / 3
    cci = np.full(n, np.nan)

    for i in range(period - 1, n):
        tp_slice = typical_price[i - period + 1:i + 1]
        sma = np.mean(tp_slice)
        mean_deviation = np.mean(np.abs(tp_slice - sma))

        if mean_deviation > 0:
            cci[i] = (typical_price[i] - sma) / (0.015 * mean_deviation)
        else:
            cci[i] = 0

    return cci


def calculate_mfi(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    volume: Union[List[float], np.ndarray],
    period: int = 14
) -> np.ndarray:
    """Calculate Money Flow Index"""
    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    volume = np.array(volume)
    n = len(high)

    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume

    mfi = np.full(n, np.nan)

    for i in range(period, n):
        positive_flow = 0
        negative_flow = 0

        for j in range(i - period + 1, i + 1):
            if typical_price[j] > typical_price[j - 1]:
                positive_flow += raw_money_flow[j]
            elif typical_price[j] < typical_price[j - 1]:
                negative_flow += raw_money_flow[j]

        if negative_flow > 0:
            money_ratio = positive_flow / negative_flow
            mfi[i] = 100 - (100 / (1 + money_ratio))
        else:
            mfi[i] = 100

    return mfi


def calculate_pivot_points(
    high: float,
    low: float,
    close: float
) -> Dict[str, float]:
    """Calculate Pivot Points"""
    pivot = (high + low + close) / 3

    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)

    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)

    return {
        "pivot": pivot,
        "r1": r1, "r2": r2, "r3": r3,
        "s1": s1, "s2": s2, "s3": s3,
    }


def calculate_fibonacci_levels(
    high: float,
    low: float
) -> Dict[str, float]:
    """Calculate Fibonacci Retracement Levels"""
    diff = high - low

    return {
        "0%": low,
        "23.6%": low + diff * 0.236,
        "38.2%": low + diff * 0.382,
        "50%": low + diff * 0.5,
        "61.8%": low + diff * 0.618,
        "78.6%": low + diff * 0.786,
        "100%": high,
        "161.8%": low + diff * 1.618,
        "261.8%": low + diff * 2.618,
    }


@dataclass
class TechnicalIndicators:
    """Container for all technical indicators"""
    symbol: str
    timestamp: str

    # Moving Averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None

    # Momentum
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None

    # Volatility
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None

    # Trend
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None

    # Volume
    vwap: Optional[float] = None
    obv: Optional[float] = None

    # Other
    williams_r: Optional[float] = None
    cci: Optional[float] = None
    mfi: Optional[float] = None

    # Levels
    pivot_points: Optional[Dict[str, float]] = None
    fibonacci: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "moving_averages": {
                "sma_20": self.sma_20,
                "sma_50": self.sma_50,
                "sma_200": self.sma_200,
                "ema_12": self.ema_12,
                "ema_26": self.ema_26,
            },
            "momentum": {
                "rsi_14": self.rsi_14,
                "macd": self.macd,
                "macd_signal": self.macd_signal,
                "macd_histogram": self.macd_histogram,
                "stoch_k": self.stoch_k,
                "stoch_d": self.stoch_d,
            },
            "volatility": {
                "bb_upper": self.bb_upper,
                "bb_middle": self.bb_middle,
                "bb_lower": self.bb_lower,
                "atr_14": self.atr_14,
            },
            "trend": {
                "adx": self.adx,
                "plus_di": self.plus_di,
                "minus_di": self.minus_di,
            },
            "volume": {
                "vwap": self.vwap,
                "obv": self.obv,
            },
            "other": {
                "williams_r": self.williams_r,
                "cci": self.cci,
                "mfi": self.mfi,
            },
            "levels": {
                "pivot_points": self.pivot_points,
                "fibonacci": self.fibonacci,
            },
        }


def calculate_all_indicators(
    high: Union[List[float], np.ndarray],
    low: Union[List[float], np.ndarray],
    close: Union[List[float], np.ndarray],
    volume: Union[List[float], np.ndarray],
    symbol: str = "UNKNOWN"
) -> TechnicalIndicators:
    """Calculate all technical indicators"""
    from datetime import datetime

    high = np.array(high)
    low = np.array(low)
    close = np.array(close)
    volume = np.array(volume)

    n = len(close)
    if n < 2:
        return TechnicalIndicators(symbol=symbol, timestamp=datetime.now().isoformat())

    # Moving Averages
    sma_20 = calculate_sma(close, 20)
    sma_50 = calculate_sma(close, 50)
    sma_200 = calculate_sma(close, 200)
    ema_12 = calculate_ema(close, 12)
    ema_26 = calculate_ema(close, 26)

    # RSI
    rsi = calculate_rsi(close, 14)

    # MACD
    macd_line, macd_signal, macd_hist = calculate_macd(close)

    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close)

    # ATR
    atr = calculate_atr(high, low, close)

    # ADX
    adx, plus_di, minus_di = calculate_adx(high, low, close)

    # Stochastic
    stoch_k, stoch_d = calculate_stochastic(high, low, close)

    # VWAP
    vwap = calculate_vwap(high, low, close, volume)

    # OBV
    obv = calculate_obv(close, volume)

    # Williams %R
    williams_r = calculate_williams_r(high, low, close)

    # CCI
    cci = calculate_cci(high, low, close)

    # MFI
    mfi = calculate_mfi(high, low, close, volume)

    # Pivot Points (using last values)
    pivots = calculate_pivot_points(high[-1], low[-1], close[-1])

    # Fibonacci (using recent high/low)
    recent_high = np.max(high[-20:]) if n >= 20 else np.max(high)
    recent_low = np.min(low[-20:]) if n >= 20 else np.min(low)
    fib = calculate_fibonacci_levels(recent_high, recent_low)

    def safe_last(arr):
        if arr is not None and len(arr) > 0 and not np.isnan(arr[-1]):
            return float(arr[-1])
        return None

    return TechnicalIndicators(
        symbol=symbol,
        timestamp=datetime.now().isoformat(),
        sma_20=safe_last(sma_20),
        sma_50=safe_last(sma_50),
        sma_200=safe_last(sma_200),
        ema_12=safe_last(ema_12),
        ema_26=safe_last(ema_26),
        rsi_14=safe_last(rsi),
        macd=safe_last(macd_line),
        macd_signal=safe_last(macd_signal),
        macd_histogram=safe_last(macd_hist),
        stoch_k=safe_last(stoch_k),
        stoch_d=safe_last(stoch_d),
        bb_upper=safe_last(bb_upper),
        bb_middle=safe_last(bb_middle),
        bb_lower=safe_last(bb_lower),
        atr_14=safe_last(atr),
        adx=safe_last(adx),
        plus_di=safe_last(plus_di),
        minus_di=safe_last(minus_di),
        vwap=safe_last(vwap),
        obv=safe_last(obv),
        williams_r=safe_last(williams_r),
        cci=safe_last(cci),
        mfi=safe_last(mfi),
        pivot_points=pivots,
        fibonacci=fib,
    )
