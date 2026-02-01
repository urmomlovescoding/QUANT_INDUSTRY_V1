"""
UNIFIED BRAIN v2.0 - PROPER TRAIN/EVAL SPLIT WITH STRATEGY-SPECIFIC FEATURES
=============================================================================
FIXES:
1. Train on 80%, evaluate on 20% with TRAINED weights (not random predictions)
2. Strategy-specific feature extraction (ICT gets ICT features, momentum gets momentum)
3. Adaptive thresholds based on market volatility

- GPU: Neural network training (matrix ops)
- CPU: Parallel feature extraction
- ACTUALLY TRACKS: Win rates, expectancy, trade outcomes
"""

import numpy as np
import pandas as pd
import sqlite3
import json
import logging
import threading
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os

logger = logging.getLogger("UNIFIED_BRAIN")

# Paths
ROOT = Path(__file__).parent.parent
METRICS_DIR = ROOT / "metrics"
WEIGHTS_DIR = ROOT / "weights"
DATA_DIR = ROOT / "data"
WAIT_DIR = ROOT / "wait"
for d in [METRICS_DIR, WEIGHTS_DIR, DATA_DIR, WAIT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

REALTIME_METRICS_FILE = METRICS_DIR / "realtime_metrics.json"
STRATEGY_TRADES_FILE = METRICS_DIR / "strategy_trades.json"

# GPU/CPU Detection
USE_GPU = False
GPU_DEVICE = None
TORCH_AVAILABLE = False
GPU_NAME = "N/A"
CPU_CORES = mp.cpu_count()
GPU_MEMORY_TOTAL = 0

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
    if torch.cuda.is_available():
        torch.cuda.init()
        USE_GPU = True
        GPU_DEVICE = torch.device('cuda')
        GPU_NAME = torch.cuda.get_device_name(0)
        GPU_MEMORY_TOTAL = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        torch.backends.cudnn.benchmark = True
    else:
        GPU_DEVICE = torch.device('cpu')
except ImportError:
    pass

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

CPU_WORKERS = max(1, CPU_CORES - 2)
print(f"[BRAIN v2] HYBRID Mode: GPU={USE_GPU} ({GPU_NAME}) + CPU Workers={CPU_WORKERS}/{CPU_CORES}")


def get_system_usage() -> Dict[str, float]:
    """Get actual CPU and GPU utilization."""
    usage = {'cpu_percent': 0.0, 'gpu_percent': 0.0, 'gpu_memory_percent': 0.0, 'memory_percent': 0.0}
    if HAS_PSUTIL:
        usage['cpu_percent'] = psutil.cpu_percent(interval=0.1)
        usage['memory_percent'] = psutil.virtual_memory().percent
    if USE_GPU and TORCH_AVAILABLE:
        try:
            mem_used = torch.cuda.memory_allocated() / (1024**3)
            usage['gpu_memory_percent'] = (mem_used / GPU_MEMORY_TOTAL * 100) if GPU_MEMORY_TOTAL > 0 else 0
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=1
            )
            if result.returncode == 0:
                usage['gpu_percent'] = float(result.stdout.strip())
        except:
            pass
    return usage


# =============================================================================
# STRATEGY TYPES WITH CATEGORY MAPPING
# =============================================================================
class StrategyCategory(Enum):
    ICT = 'ict'           # Inner Circle Trader concepts
    SMC = 'smc'           # Smart Money Concepts
    TREND = 'trend'       # Trend following
    MOMENTUM = 'momentum' # Momentum indicators
    VOLUME = 'volume'     # Volume analysis
    PATTERN = 'pattern'   # Pattern recognition
    ML = 'ml'             # Machine learning


class StrategyType(Enum):
    ICT_FVG = 'ict_fvg'
    ICT_ORDER_BLOCK = 'ict_order_block'
    ICT_LIQUIDITY = 'ict_liquidity'
    ICT_MSS = 'ict_mss'
    SMC_PREMIUM_DISCOUNT = 'smc_premium_discount'
    SMC_DISPLACEMENT = 'smc_displacement'
    TREND_EMA_CROSS = 'trend_ema_cross'
    TREND_SUPERTREND = 'trend_supertrend'
    TREND_ADX = 'trend_adx'
    TREND_ICHIMOKU = 'trend_ichimoku'
    MOM_RSI = 'mom_rsi'
    MOM_MACD = 'mom_macd'
    MOM_STOCH = 'mom_stoch'
    VOL_OBV = 'vol_obv'
    VOL_VWAP = 'vol_vwap'
    PATTERN_CANDLE = 'pattern_candle'
    PATTERN_ENGULFING = 'pattern_engulfing'
    PATTERN_HARMONIC = 'pattern_harmonic'
    ML_ENSEMBLE = 'ml_ensemble'
    ML_SELF_DISCOVERED = 'ml_self_discovered'


# Map strategies to categories for feature selection
STRATEGY_CATEGORIES = {
    StrategyType.ICT_FVG: StrategyCategory.ICT,
    StrategyType.ICT_ORDER_BLOCK: StrategyCategory.ICT,
    StrategyType.ICT_LIQUIDITY: StrategyCategory.ICT,
    StrategyType.ICT_MSS: StrategyCategory.ICT,
    StrategyType.SMC_PREMIUM_DISCOUNT: StrategyCategory.SMC,
    StrategyType.SMC_DISPLACEMENT: StrategyCategory.SMC,
    StrategyType.TREND_EMA_CROSS: StrategyCategory.TREND,
    StrategyType.TREND_SUPERTREND: StrategyCategory.TREND,
    StrategyType.TREND_ADX: StrategyCategory.TREND,
    StrategyType.TREND_ICHIMOKU: StrategyCategory.TREND,
    StrategyType.MOM_RSI: StrategyCategory.MOMENTUM,
    StrategyType.MOM_MACD: StrategyCategory.MOMENTUM,
    StrategyType.MOM_STOCH: StrategyCategory.MOMENTUM,
    StrategyType.VOL_OBV: StrategyCategory.VOLUME,
    StrategyType.VOL_VWAP: StrategyCategory.VOLUME,
    StrategyType.PATTERN_CANDLE: StrategyCategory.PATTERN,
    StrategyType.PATTERN_ENGULFING: StrategyCategory.PATTERN,
    StrategyType.PATTERN_HARMONIC: StrategyCategory.PATTERN,
    StrategyType.ML_ENSEMBLE: StrategyCategory.ML,
    StrategyType.ML_SELF_DISCOVERED: StrategyCategory.ML,
}

ALL_STRATEGIES = list(StrategyType)
N_STRATEGIES = len(ALL_STRATEGIES)



# =============================================================================
# STRATEGY PERFORMANCE TRACKING
# =============================================================================
@dataclass
class StrategyPerformance:
    """Tracks actual trade performance with win/loss tracking."""
    name: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    weight: float = 0.05
    training_samples: int = 0
    eval_samples: int = 0
    predictions_made: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    pnl_history: List[float] = field(default_factory=list)
    
    def record_trade(self, pnl: float, predicted_direction: int, actual_direction: int):
        """Record a simulated trade with actual outcome."""
        self.trades += 1
        self.predictions_made += 1
        self.total_pnl += pnl
        self.pnl_history.append(pnl)
        
        # Check if prediction was correct (allowing HOLD flexibility)
        was_correct = (predicted_direction == actual_direction)
        
        if was_correct:
            self.correct_predictions += 1
        
        # Track wins/losses based on PnL (only for non-HOLD trades)
        if predicted_direction != 1:  # Not HOLD
            if pnl > 0:
                self.wins += 1
            elif pnl < 0:
                self.losses += 1
        
        self._recalculate_metrics()
    
    def _recalculate_metrics(self):
        """Recalculate all performance metrics."""
        actual_trades = self.wins + self.losses
        if actual_trades > 0:
            self.win_rate = self.wins / actual_trades
        
        if self.predictions_made > 0:
            self.accuracy = self.correct_predictions / self.predictions_made
        
        # Calculate profit factor
        wins_sum = sum(p for p in self.pnl_history if p > 0)
        losses_sum = abs(sum(p for p in self.pnl_history if p < 0))
        self.profit_factor = wins_sum / losses_sum if losses_sum > 0 else (999 if wins_sum > 0 else 0)
        
        # Calculate avg win/loss
        win_trades = [p for p in self.pnl_history if p > 0]
        loss_trades = [p for p in self.pnl_history if p < 0]
        self.avg_win = np.mean(win_trades) if win_trades else 0
        self.avg_loss = abs(np.mean(loss_trades)) if loss_trades else 0
        
        # Calculate expectancy: E = (Win% × AvgWin) - (Loss% × AvgLoss)
        if actual_trades > 0:
            self.expectancy = (self.win_rate * self.avg_win) - ((1 - self.win_rate) * self.avg_loss)
    
    def reset_eval_stats(self):
        """Reset stats for fresh evaluation (after training)."""
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.predictions_made = 0
        self.correct_predictions = 0
        self.pnl_history = []
        self.eval_samples = 0
        self._recalculate_metrics()
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name, 'trades': self.trades, 'wins': self.wins, 'losses': self.losses,
            'training_samples': self.training_samples, 'eval_samples': self.eval_samples,
            'predictions_made': self.predictions_made, 'correct_predictions': self.correct_predictions,
            'total_pnl': round(self.total_pnl, 2),
            'win_rate': round(self.win_rate * 100, 1), 'accuracy': round(self.accuracy * 100, 1),
            'profit_factor': round(min(self.profit_factor, 999), 2),
            'avg_win': round(self.avg_win, 2), 'avg_loss': round(self.avg_loss, 2),
            'expectancy': round(self.expectancy, 2), 'weight': round(self.weight * 100, 1)
        }



# =============================================================================
# STRATEGY-SPECIFIC FEATURE EXTRACTION
# =============================================================================

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Compute Average True Range."""
    if len(close) < period + 1:
        return 0.01
    tr = np.maximum(
        high[-period:] - low[-period:],
        np.maximum(
            np.abs(high[-period:] - close[-period-1:-1]),
            np.abs(low[-period:] - close[-period-1:-1])
        )
    )
    return float(np.mean(tr))


def compute_adaptive_threshold(close: np.ndarray, high: np.ndarray, low: np.ndarray, 
                                base_threshold: float = 0.003) -> float:
    """
    FIX #3: Adaptive threshold based on recent volatility.
    High volatility = higher threshold to filter noise.
    Low volatility = lower threshold to capture moves.
    """
    if len(close) < 20:
        return base_threshold
    
    atr = compute_atr(high, low, close, 14)
    atr_pct = atr / (close[-1] + 1e-10)
    
    # Scale threshold: if ATR% is 1%, threshold is ~1%. If ATR% is 0.5%, threshold is ~0.5%
    # Clamp between 0.1% and 2%
    adaptive = np.clip(atr_pct * 0.5, 0.001, 0.02)
    return float(adaptive)


def extract_base_features(close: np.ndarray, high: np.ndarray, low: np.ndarray, 
                          volume: np.ndarray) -> np.ndarray:
    """Extract 30 base features common to all strategies."""
    n = len(close)
    features = np.zeros(30)
    if n < 50:
        return features
    
    # Price momentum (0-4)
    features[0] = (close[-1] - close[-2]) / (close[-2] + 1e-10)
    features[1] = (close[-1] - close[-5]) / (close[-5] + 1e-10) if n >= 5 else 0
    features[2] = (close[-1] - close[-10]) / (close[-10] + 1e-10) if n >= 10 else 0
    features[3] = (close[-1] - close[-20]) / (close[-20] + 1e-10) if n >= 20 else 0
    features[4] = (close[-1] - close[-50]) / (close[-50] + 1e-10) if n >= 50 else 0
    
    # Volatility (5-7)
    features[5] = np.std(close[-20:]) / (close[-1] + 1e-10) if n >= 20 else 0
    features[6] = np.std(close[-5:]) / (close[-1] + 1e-10) if n >= 5 else 0
    atr = compute_atr(high, low, close)
    features[7] = atr / (close[-1] + 1e-10)
    
    # Position in range (8-10)
    if n >= 20:
        lo20, hi20 = np.min(low[-20:]), np.max(high[-20:])
        features[8] = (close[-1] - lo20) / (hi20 - lo20 + 1e-10)
    if n >= 50:
        lo50, hi50 = np.min(low[-50:]), np.max(high[-50:])
        features[9] = (close[-1] - lo50) / (hi50 - lo50 + 1e-10)
    features[10] = (close[-1] - low[-1]) / (high[-1] - low[-1] + 1e-10)  # Intrabar position
    
    # Volume (11-14)
    if n >= 20:
        vol_avg = np.mean(volume[-20:])
        features[11] = volume[-1] / (vol_avg + 1e-10) - 1
        features[12] = 1 if volume[-1] > volume[-2] else -1
        features[13] = np.std(volume[-20:]) / (vol_avg + 1e-10)
    features[14] = 1 if volume[-1] > np.mean(volume[-5:]) else -1 if n >= 5 else 0
    
    # Candle structure (15-19)
    body = close[-1] - close[-2] if n >= 2 else 0
    upper_wick = high[-1] - max(close[-1], close[-2] if n >= 2 else close[-1])
    lower_wick = min(close[-1], close[-2] if n >= 2 else close[-1]) - low[-1]
    candle_range = high[-1] - low[-1]
    features[15] = body / (candle_range + 1e-10)  # Body ratio
    features[16] = upper_wick / (candle_range + 1e-10)
    features[17] = lower_wick / (candle_range + 1e-10)
    features[18] = 1 if close[-1] > close[-2] else -1 if n >= 2 else 0  # Direction
    features[19] = candle_range / (close[-1] + 1e-10)  # Range as % of price
    
    # Recent returns for lagged features (20-29)
    for k in range(10):
        if k + 1 < n:
            features[20 + k] = (close[-(k+1)] - close[-(k+2)]) / (close[-(k+2)] + 1e-10)
    
    return np.nan_to_num(features, nan=0, posinf=1, neginf=-1)



def extract_ict_features(close: np.ndarray, high: np.ndarray, low: np.ndarray, 
                         volume: np.ndarray) -> np.ndarray:
    """FIX #2: ICT-specific features (Fair Value Gaps, Order Blocks, Liquidity)."""
    n = len(close)
    features = np.zeros(20)
    if n < 50:
        return features
    
    # Fair Value Gap detection (0-4)
    # FVG up: low[i] > high[i-2] (gap between candle i-2 high and candle i low)
    fvg_up_count = 0
    fvg_down_count = 0
    nearest_fvg_up = 0
    nearest_fvg_down = 0
    
    for i in range(3, min(20, n)):
        if low[-i] > high[-i-2]:  # Bullish FVG
            fvg_up_count += 1
            if nearest_fvg_up == 0:
                nearest_fvg_up = (low[-i] + high[-i-2]) / 2
        if high[-i] < low[-i-2]:  # Bearish FVG
            fvg_down_count += 1
            if nearest_fvg_down == 0:
                nearest_fvg_down = (high[-i] + low[-i-2]) / 2
    
    features[0] = fvg_up_count / 10
    features[1] = fvg_down_count / 10
    features[2] = (close[-1] - nearest_fvg_up) / (close[-1] + 1e-10) if nearest_fvg_up > 0 else 0
    features[3] = (close[-1] - nearest_fvg_down) / (close[-1] + 1e-10) if nearest_fvg_down > 0 else 0
    features[4] = 1 if fvg_up_count > fvg_down_count else (-1 if fvg_down_count > fvg_up_count else 0)
    
    # Order Block detection (5-9)
    # Bullish OB: Last down candle before a strong up move
    # Bearish OB: Last up candle before a strong down move
    bullish_ob = 0
    bearish_ob = 0
    
    for i in range(3, min(30, n-2)):
        if close[-i] < close[-i-1]:  # Down candle
            # Check if followed by strong up move
            future_ret = (close[-i+2] - close[-i]) / (close[-i] + 1e-10) if i >= 3 else 0
            if future_ret > 0.01:  # 1% move up
                bullish_ob = (high[-i] + low[-i]) / 2
                break
    
    for i in range(3, min(30, n-2)):
        if close[-i] > close[-i-1]:  # Up candle
            future_ret = (close[-i+2] - close[-i]) / (close[-i] + 1e-10) if i >= 3 else 0
            if future_ret < -0.01:  # 1% move down
                bearish_ob = (high[-i] + low[-i]) / 2
                break
    
    features[5] = (close[-1] - bullish_ob) / (close[-1] + 1e-10) if bullish_ob > 0 else 0
    features[6] = (close[-1] - bearish_ob) / (close[-1] + 1e-10) if bearish_ob > 0 else 0
    features[7] = 1 if bullish_ob > 0 and close[-1] > bullish_ob else 0
    features[8] = -1 if bearish_ob > 0 and close[-1] < bearish_ob else 0
    features[9] = 1 if abs(features[5]) < abs(features[6]) else -1
    
    # Liquidity levels (10-14) - Previous highs/lows that could be liquidity targets
    swing_highs = []
    swing_lows = []
    
    for i in range(2, min(30, n-2)):
        if high[-i] > high[-i-1] and high[-i] > high[-i+1]:
            swing_highs.append(high[-i])
        if low[-i] < low[-i-1] and low[-i] < low[-i+1]:
            swing_lows.append(low[-i])
    
    if swing_highs:
        nearest_high = min(swing_highs, key=lambda x: abs(x - close[-1]))
        features[10] = (nearest_high - close[-1]) / (close[-1] + 1e-10)
        features[11] = 1 if close[-1] > nearest_high else 0
    
    if swing_lows:
        nearest_low = min(swing_lows, key=lambda x: abs(x - close[-1]))
        features[12] = (close[-1] - nearest_low) / (close[-1] + 1e-10)
        features[13] = -1 if close[-1] < nearest_low else 0
    
    features[14] = len(swing_highs) - len(swing_lows)  # Bias
    
    # Market Structure Shift (15-19)
    # MSS: Break of recent swing high (bullish) or swing low (bearish)
    if n >= 20:
        recent_high = np.max(high[-20:-1])
        recent_low = np.min(low[-20:-1])
        features[15] = 1 if close[-1] > recent_high else 0  # Bullish MSS
        features[16] = -1 if close[-1] < recent_low else 0  # Bearish MSS
        features[17] = (close[-1] - recent_high) / (close[-1] + 1e-10)
        features[18] = (close[-1] - recent_low) / (close[-1] + 1e-10)
        features[19] = features[15] + features[16]  # Net MSS signal
    
    return np.nan_to_num(features, nan=0, posinf=1, neginf=-1)


def extract_momentum_features(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                               volume: np.ndarray) -> np.ndarray:
    """FIX #2: Momentum-specific features (RSI, MACD, Stochastic)."""
    n = len(close)
    features = np.zeros(20)
    if n < 50:
        return features
    
    # RSI (0-4)
    delta = np.diff(close[-15:])
    gains = delta[delta > 0]
    losses = -delta[delta < 0]
    avg_gain = np.mean(gains) if len(gains) > 0 else 0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    features[0] = (rsi - 50) / 50  # Normalized RSI (-1 to 1)
    features[1] = 1 if rsi < 30 else (-1 if rsi > 70 else 0)  # Oversold/Overbought
    features[2] = 1 if rsi < 20 else (-1 if rsi > 80 else 0)  # Extreme
    
    # RSI divergence
    if n >= 10:
        price_trend = close[-1] - close[-10]
        rsi_5_ago = 50  # Approximate
        delta_old = np.diff(close[-20:-5])
        gains_old = delta_old[delta_old > 0]
        losses_old = -delta_old[delta_old < 0]
        if len(gains_old) > 0 and len(losses_old) > 0:
            rs_old = np.mean(gains_old) / (np.mean(losses_old) + 0.0001)
            rsi_5_ago = 100 - (100 / (1 + rs_old))
        rsi_trend = rsi - rsi_5_ago
        features[3] = 1 if price_trend > 0 and rsi_trend < 0 else 0  # Bearish divergence
        features[4] = 1 if price_trend < 0 and rsi_trend > 0 else 0  # Bullish divergence
    
    # MACD (5-9)
    if n >= 26:
        ema12 = pd.Series(close).ewm(span=12).mean().values[-1]
        ema26 = pd.Series(close).ewm(span=26).mean().values[-1]
        macd_line = ema12 - ema26
        signal_line = pd.Series(close).ewm(span=12).mean().ewm(span=9).mean().values[-1] - \
                      pd.Series(close).ewm(span=26).mean().ewm(span=9).mean().values[-1]
        
        features[5] = macd_line / (close[-1] + 1e-10) * 100  # MACD as % of price
        features[6] = (macd_line - signal_line) / (close[-1] + 1e-10) * 100  # Histogram
        features[7] = 1 if macd_line > signal_line else -1  # Signal
        features[8] = 1 if macd_line > 0 else -1  # Above/below zero
        features[9] = 1 if features[6] > 0 and features[7] > 0 else (-1 if features[6] < 0 and features[7] < 0 else 0)
    
    # Stochastic (10-14)
    if n >= 14:
        low14 = np.min(low[-14:])
        high14 = np.max(high[-14:])
        stoch_k = (close[-1] - low14) / (high14 - low14 + 1e-10) * 100
        stoch_d = np.mean([(close[-i] - np.min(low[-14-i:-i])) / (np.max(high[-14-i:-i]) - np.min(low[-14-i:-i]) + 1e-10) * 100 
                          for i in range(1, 4) if n >= 14 + i])
        
        features[10] = (stoch_k - 50) / 50  # Normalized
        features[11] = (stoch_d - 50) / 50 if stoch_d else 0
        features[12] = 1 if stoch_k < 20 else (-1 if stoch_k > 80 else 0)  # Oversold/Overbought
        features[13] = 1 if stoch_k > stoch_d else -1  # K vs D
        features[14] = 1 if stoch_k < 20 and stoch_k > stoch_d else (-1 if stoch_k > 80 and stoch_k < stoch_d else 0)
    
    # Rate of Change (15-19)
    features[15] = (close[-1] - close[-5]) / (close[-5] + 1e-10) if n >= 5 else 0
    features[16] = (close[-1] - close[-10]) / (close[-10] + 1e-10) if n >= 10 else 0
    features[17] = (close[-1] - close[-20]) / (close[-20] + 1e-10) if n >= 20 else 0
    
    # Momentum acceleration
    if n >= 10:
        mom_now = close[-1] - close[-5]
        mom_prev = close[-5] - close[-10]
        features[18] = 1 if mom_now > mom_prev else (-1 if mom_now < mom_prev else 0)
    
    features[19] = np.sign(features[0]) * abs(features[5])  # RSI-MACD agreement
    
    return np.nan_to_num(features, nan=0, posinf=1, neginf=-1)



def extract_trend_features(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                           volume: np.ndarray) -> np.ndarray:
    """FIX #2: Trend-specific features (EMAs, ADX, Supertrend concepts)."""
    n = len(close)
    features = np.zeros(20)
    if n < 50:
        return features
    
    # EMA stack (0-4)
    ema9 = pd.Series(close).ewm(span=9).mean().values[-1]
    ema21 = pd.Series(close).ewm(span=21).mean().values[-1]
    ema50 = pd.Series(close).ewm(span=50).mean().values[-1]
    
    features[0] = (close[-1] - ema9) / (close[-1] + 1e-10)
    features[1] = (close[-1] - ema21) / (close[-1] + 1e-10)
    features[2] = (close[-1] - ema50) / (close[-1] + 1e-10)
    features[3] = (ema9 - ema21) / (close[-1] + 1e-10)
    features[4] = 1 if ema9 > ema21 > ema50 else (-1 if ema9 < ema21 < ema50 else 0)
    
    # ADX approximation (5-9)
    atr = compute_atr(high, low, close, 14)
    
    # +DM / -DM approximation
    plus_dm = np.maximum(high[-14:] - high[-15:-1], 0)
    minus_dm = np.maximum(low[-15:-1] - low[-14:], 0)
    plus_di = np.mean(plus_dm) / (atr + 1e-10) * 100
    minus_di = np.mean(minus_dm) / (atr + 1e-10) * 100
    dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
    
    features[5] = dx / 50  # Normalized ADX proxy (0-2 range)
    features[6] = (plus_di - minus_di) / 100  # DI difference
    features[7] = 1 if dx > 25 else 0  # Trending
    features[8] = 1 if plus_di > minus_di else -1  # Trend direction
    features[9] = features[7] * features[8]  # Strong trend signal
    
    # Supertrend concept (10-14)
    multiplier = 3.0
    upper_band = (high[-1] + low[-1]) / 2 + multiplier * atr
    lower_band = (high[-1] + low[-1]) / 2 - multiplier * atr
    
    features[10] = (close[-1] - lower_band) / (close[-1] + 1e-10)
    features[11] = (upper_band - close[-1]) / (close[-1] + 1e-10)
    features[12] = 1 if close[-1] > lower_band else -1
    
    # Trend persistence
    up_days = sum(1 for i in range(1, min(11, n)) if close[-i] > close[-i-1])
    features[13] = (up_days - 5) / 5  # -1 to 1
    features[14] = 1 if up_days >= 7 else (-1 if up_days <= 3 else 0)
    
    # Higher highs / Lower lows (15-19)
    if n >= 10:
        hh_count = sum(1 for i in range(1, 5) if high[-i] > high[-i-1])
        ll_count = sum(1 for i in range(1, 5) if low[-i] < low[-i-1])
        features[15] = (hh_count - 2) / 2
        features[16] = (ll_count - 2) / 2
        features[17] = 1 if hh_count >= 3 and ll_count <= 1 else 0  # Uptrend
        features[18] = -1 if ll_count >= 3 and hh_count <= 1 else 0  # Downtrend
        features[19] = features[17] + features[18]
    
    return np.nan_to_num(features, nan=0, posinf=1, neginf=-1)


def extract_volume_features(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                            volume: np.ndarray) -> np.ndarray:
    """FIX #2: Volume-specific features (OBV, VWAP concepts, Volume Profile)."""
    n = len(close)
    features = np.zeros(20)
    if n < 50:
        return features
    
    # OBV trend (0-4)
    obv = np.zeros(min(50, n))
    obv[0] = volume[-min(50, n)]
    for i in range(1, len(obv)):
        idx = -min(50, n) + i
        if close[idx] > close[idx - 1]:
            obv[i] = obv[i-1] + volume[idx]
        elif close[idx] < close[idx - 1]:
            obv[i] = obv[i-1] - volume[idx]
        else:
            obv[i] = obv[i-1]
    
    obv_sma = np.mean(obv[-20:]) if len(obv) >= 20 else obv[-1]
    features[0] = (obv[-1] - obv_sma) / (abs(obv_sma) + 1e-10)
    features[1] = 1 if obv[-1] > obv[-5] else -1 if len(obv) >= 5 else 0
    features[2] = 1 if obv[-1] > obv_sma else -1
    
    # Price-OBV divergence
    if len(obv) >= 10:
        price_trend = close[-1] - close[-10]
        obv_trend = obv[-1] - obv[-10]
        features[3] = 1 if price_trend > 0 and obv_trend < 0 else 0  # Bearish divergence
        features[4] = 1 if price_trend < 0 and obv_trend > 0 else 0  # Bullish divergence
    
    # VWAP approximation (5-9)
    typical_price = (high + low + close) / 3
    vwap_20 = np.sum(typical_price[-20:] * volume[-20:]) / (np.sum(volume[-20:]) + 1e-10) if n >= 20 else close[-1]
    
    features[5] = (close[-1] - vwap_20) / (close[-1] + 1e-10)
    features[6] = 1 if close[-1] > vwap_20 else -1
    
    # VWAP bands (1 std)
    vwap_std = np.std(typical_price[-20:]) if n >= 20 else 0.01
    features[7] = (close[-1] - (vwap_20 + vwap_std)) / (close[-1] + 1e-10)  # Distance to upper band
    features[8] = (close[-1] - (vwap_20 - vwap_std)) / (close[-1] + 1e-10)  # Distance to lower band
    features[9] = 1 if close[-1] > vwap_20 + vwap_std else (-1 if close[-1] < vwap_20 - vwap_std else 0)
    
    # Volume characteristics (10-14)
    vol_avg = np.mean(volume[-20:]) if n >= 20 else volume[-1]
    features[10] = volume[-1] / (vol_avg + 1e-10) - 1  # Relative volume
    features[11] = np.std(volume[-20:]) / (vol_avg + 1e-10) if n >= 20 else 0  # Volume volatility
    features[12] = 1 if volume[-1] > vol_avg * 1.5 else 0  # High volume
    features[13] = -1 if volume[-1] < vol_avg * 0.5 else 0  # Low volume
    
    # Volume trend
    vol_sma5 = np.mean(volume[-5:]) if n >= 5 else volume[-1]
    vol_sma20 = np.mean(volume[-20:]) if n >= 20 else volume[-1]
    features[14] = (vol_sma5 - vol_sma20) / (vol_sma20 + 1e-10)
    
    # CMF approximation (15-19)
    mfm = ((close[-1] - low[-1]) - (high[-1] - close[-1])) / (high[-1] - low[-1] + 1e-10)
    features[15] = mfm
    
    # Accumulation/Distribution
    ad = mfm * volume[-1]
    features[16] = ad / (vol_avg + 1e-10)
    
    # Volume-price confirmation
    features[17] = 1 if (close[-1] > close[-2] and volume[-1] > volume[-2]) else 0
    features[18] = -1 if (close[-1] < close[-2] and volume[-1] > volume[-2]) else 0
    features[19] = features[17] + features[18]
    
    return np.nan_to_num(features, nan=0, posinf=1, neginf=-1)


def extract_pattern_features(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                             volume: np.ndarray) -> np.ndarray:
    """FIX #2: Pattern-specific features (Candlestick patterns, Chart patterns)."""
    n = len(close)
    features = np.zeros(20)
    if n < 10:
        return features
    
    # Current candle analysis (0-4)
    body = close[-1] - close[-2] if n >= 2 else 0
    candle_range = high[-1] - low[-1]
    upper_wick = high[-1] - max(close[-1], close[-2] if n >= 2 else close[-1])
    lower_wick = min(close[-1], close[-2] if n >= 2 else close[-1]) - low[-1]
    
    body_ratio = abs(body) / (candle_range + 1e-10)
    features[0] = body_ratio
    features[1] = 1 if body_ratio < 0.1 else 0  # Doji
    features[2] = upper_wick / (candle_range + 1e-10)
    features[3] = lower_wick / (candle_range + 1e-10)
    features[4] = 1 if body > 0 else -1  # Bullish/Bearish
    
    # Hammer / Shooting Star (5-7)
    is_hammer = lower_wick > 2 * abs(body) and upper_wick < abs(body) * 0.5
    is_shooting_star = upper_wick > 2 * abs(body) and lower_wick < abs(body) * 0.5
    features[5] = 1 if is_hammer else 0
    features[6] = -1 if is_shooting_star else 0
    features[7] = features[5] + features[6]
    
    # Engulfing patterns (8-10)
    if n >= 3:
        prev_body = close[-2] - close[-3]
        curr_body = close[-1] - close[-2]
        bullish_engulf = prev_body < 0 and curr_body > 0 and abs(curr_body) > abs(prev_body) * 1.5
        bearish_engulf = prev_body > 0 and curr_body < 0 and abs(curr_body) > abs(prev_body) * 1.5
        features[8] = 1 if bullish_engulf else 0
        features[9] = -1 if bearish_engulf else 0
        features[10] = features[8] + features[9]
    
    # Three candle patterns (11-14)
    if n >= 4:
        # Morning Star / Evening Star approximation
        mid_doji = abs(close[-2] - close[-3]) / (high[-2] - low[-2] + 1e-10) < 0.3
        morning_star = close[-4] > close[-3] and mid_doji and close[-1] > close[-2]
        evening_star = close[-4] < close[-3] and mid_doji and close[-1] < close[-2]
        features[11] = 1 if morning_star else 0
        features[12] = -1 if evening_star else 0
        
        # Three soldiers / crows
        three_green = all(close[-i] > close[-i-1] for i in range(1, 4))
        three_red = all(close[-i] < close[-i-1] for i in range(1, 4))
        features[13] = 1 if three_green else 0
        features[14] = -1 if three_red else 0
    
    # Support/Resistance proximity (15-19)
    if n >= 20:
        recent_highs = [high[-i] for i in range(1, 20) if i+1 < n and high[-i] > high[-i-1] and high[-i] > high[-i+1]]
        recent_lows = [low[-i] for i in range(1, 20) if i+1 < n and low[-i] < low[-i-1] and low[-i] < low[-i+1]]
        
        if recent_highs:
            nearest_res = min(recent_highs, key=lambda x: abs(x - close[-1]))
            features[15] = (nearest_res - close[-1]) / (close[-1] + 1e-10)
            features[16] = 1 if abs(features[15]) < 0.01 else 0  # Near resistance
        
        if recent_lows:
            nearest_sup = min(recent_lows, key=lambda x: abs(x - close[-1]))
            features[17] = (close[-1] - nearest_sup) / (close[-1] + 1e-10)
            features[18] = 1 if abs(features[17]) < 0.01 else 0  # Near support
        
        features[19] = features[16] - features[18]  # Net S/R signal
    
    return np.nan_to_num(features, nan=0, posinf=1, neginf=-1)



def extract_features_for_strategy(strategy: StrategyType, close: np.ndarray, high: np.ndarray,
                                   low: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """
    FIX #2: Extract strategy-specific features.
    Returns 50 features: 30 base + 20 strategy-specific.
    """
    base = extract_base_features(close, high, low, volume)
    category = STRATEGY_CATEGORIES.get(strategy, StrategyCategory.ML)
    
    if category == StrategyCategory.ICT or category == StrategyCategory.SMC:
        specific = extract_ict_features(close, high, low, volume)
    elif category == StrategyCategory.MOMENTUM:
        specific = extract_momentum_features(close, high, low, volume)
    elif category == StrategyCategory.TREND:
        specific = extract_trend_features(close, high, low, volume)
    elif category == StrategyCategory.VOLUME:
        specific = extract_volume_features(close, high, low, volume)
    elif category == StrategyCategory.PATTERN:
        specific = extract_pattern_features(close, high, low, volume)
    else:
        # ML strategies get a mix of all
        specific = np.concatenate([
            extract_momentum_features(close, high, low, volume)[:5],
            extract_trend_features(close, high, low, volume)[:5],
            extract_ict_features(close, high, low, volume)[:5],
            extract_volume_features(close, high, low, volume)[:5]
        ])
    
    return np.concatenate([base, specific])


# =============================================================================
# NEURAL NETWORK
# =============================================================================
class StrategyNeuralNet:
    """Neural network for strategy signal prediction."""
    
    def __init__(self, input_size: int = 50, hidden_sizes: List[int] = [128, 64, 32], output_size: int = 3):
        self.input_size = input_size
        self.train_count = 0
        self.last_loss = 0.0
        
        if TORCH_AVAILABLE:
            self._init_torch(input_size, hidden_sizes, output_size)
        else:
            self._init_numpy(input_size, hidden_sizes, output_size)
    
    def _init_torch(self, input_size, hidden_sizes, output_size):
        layers = []
        prev = input_size
        for h in hidden_sizes:
            layers.extend([nn.Linear(prev, h), nn.BatchNorm1d(h), nn.LeakyReLU(0.1), nn.Dropout(0.15)])
            prev = h
        layers.append(nn.Linear(prev, output_size))
        self.model = nn.Sequential(*layers).to(GPU_DEVICE)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.001, weight_decay=0.01)
        self.criterion = nn.CrossEntropyLoss()
        self.use_torch = True
        self.scaler = torch.amp.GradScaler('cuda') if USE_GPU else None
        
        # Learning rate scheduler - warmup + cosine annealing
        self.scheduler = None
        self.warmup_scheduler = None
        self._init_scheduler()
    
    def _init_scheduler(self, total_epochs: int = 100, warmup_epochs: int = 5, min_lr: float = 1e-6):
        """Initialize learning rate scheduler with warmup."""
        if not self.use_torch:
            return
        
        try:
            from torch.optim.lr_scheduler import CosineAnnealingLR, LambdaLR
            
            # Warmup scheduler
            def warmup_fn(epoch):
                if epoch < warmup_epochs:
                    return (epoch + 1) / warmup_epochs
                return 1.0
            self.warmup_scheduler = LambdaLR(self.optimizer, warmup_fn)
            
            # Main scheduler - cosine annealing
            self.scheduler = CosineAnnealingLR(
                self.optimizer,
                T_max=total_epochs - warmup_epochs,
                eta_min=min_lr
            )
            self.warmup_epochs = warmup_epochs
            self.current_epoch = 0
        except Exception as e:
            logger.warning(f"Failed to initialize scheduler: {e}")
            self.scheduler = None
            self.warmup_scheduler = None
    
    def step_scheduler(self, epoch: int = None, loss: float = None):
        """Step the learning rate scheduler."""
        if not self.use_torch or self.scheduler is None:
            return
        
        if epoch is not None:
            self.current_epoch = epoch
        else:
            self.current_epoch += 1
        
        try:
            if self.current_epoch < getattr(self, 'warmup_epochs', 5):
                if self.warmup_scheduler:
                    self.warmup_scheduler.step()
            else:
                self.scheduler.step()
        except Exception as e:
            logger.debug(f"Scheduler step error: {e}")
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        if self.use_torch:
            return self.optimizer.param_groups[0]['lr']
        return self.lr

    
    def _init_numpy(self, input_size, hidden_sizes, output_size):
        self.weights, self.biases = [], []
        prev = input_size
        for h in hidden_sizes + [output_size]:
            self.weights.append(np.random.randn(prev, h) * np.sqrt(2.0 / prev))
            self.biases.append(np.zeros(h))
            prev = h
        self.use_torch = False
        self.lr = 0.001
    
    def _prepare(self, features: np.ndarray) -> np.ndarray:
        x = np.asarray(features).flatten()
        if len(x) >= self.input_size:
            return x[:self.input_size]
        return np.pad(x, (0, self.input_size - len(x)))
    
    def predict(self, features: np.ndarray) -> Tuple[int, float, np.ndarray]:
        """Returns (predicted_class, confidence, probabilities)."""
        x = self._prepare(features)
        if self.use_torch:
            self.model.eval()
            with torch.no_grad():
                x_t = torch.FloatTensor(x).unsqueeze(0).to(GPU_DEVICE)
                probs = torch.softmax(self.model(x_t), dim=-1).cpu().numpy()[0]
        else:
            for i, (w, b) in enumerate(zip(self.weights, self.biases)):
                x = np.dot(x, w) + b
                if i < len(self.weights) - 1:
                    x = np.maximum(0.1 * x, x)  # LeakyReLU
            exp_x = np.exp(x - np.max(x))
            probs = exp_x / (np.sum(exp_x) + 1e-10)
        idx = np.argmax(probs)
        return int(idx), float(probs[idx]), probs
    
    def train_batch(self, batch: List[Tuple[np.ndarray, int, float]]) -> float:
        """Train on batch. Returns loss."""
        if not batch:
            return 0.0
        loss = 0.0
        if self.use_torch:
            self.model.train()
            X = torch.FloatTensor(np.array([self._prepare(f) for f, t, r in batch])).to(GPU_DEVICE)
            Y = torch.LongTensor([t for f, t, r in batch]).to(GPU_DEVICE)
            self.optimizer.zero_grad()
            if self.scaler and USE_GPU:
                with torch.amp.autocast('cuda'):
                    out = self.model(X)
                    loss_t = self.criterion(out, Y)
                self.scaler.scale(loss_t).backward()
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                out = self.model(X)
                loss_t = self.criterion(out, Y)
                loss_t.backward()
                self.optimizer.step()
            loss = loss_t.item()
        else:
            for features, target, _ in batch:
                x = self._prepare(features)
                acts = [x.copy()]
                for i, (w, b) in enumerate(zip(self.weights, self.biases)):
                    z = np.dot(x, w) + b
                    x = np.maximum(0.1 * z, z) if i < len(self.weights) - 1 else z
                    acts.append(x)
                exp_z = np.exp(acts[-1] - np.max(acts[-1]))
                probs = exp_z / (np.sum(exp_z) + 1e-10)
                target_vec = np.zeros(3)
                target_vec[min(target, 2)] = 1.0
                grad = probs - target_vec
                for i in range(len(self.weights) - 1, -1, -1):
                    self.weights[i] -= self.lr * np.clip(np.outer(acts[i], grad), -1, 1)
                    self.biases[i] -= self.lr * np.clip(grad, -1, 1)
                    if i > 0:
                        grad = np.dot(grad, self.weights[i].T) * (acts[i] > 0)
                loss += np.sum(grad ** 2)
            loss /= len(batch)
        self.last_loss = loss
        self.train_count += len(batch)
        return loss
    
    def save_weights(self, filepath: Path):
        """Save model weights to disk."""
        try:
            if self.use_torch:
                save_dict = {
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'train_count': self.train_count,
                    'last_loss': self.last_loss,
                    'current_epoch': getattr(self, 'current_epoch', 0)
                }
                # Save scheduler state if available
                if self.scheduler is not None:
                    save_dict['scheduler_state_dict'] = self.scheduler.state_dict()
                if self.warmup_scheduler is not None:
                    save_dict['warmup_scheduler_state_dict'] = self.warmup_scheduler.state_dict()
                torch.save(save_dict, filepath)
            else:
                import pickle
                with open(filepath, 'wb') as f:
                    pickle.dump({
                        'weights': self.weights,
                        'biases': self.biases,
                        'train_count': self.train_count,
                        'last_loss': self.last_loss
                    }, f)
            return True
        except Exception as e:
            logger.error(f"Failed to save weights: {e}")
            return False
    
    def load_weights(self, filepath: Path) -> bool:
        """Load model weights from disk."""
        try:
            if not filepath.exists():
                return False
            
            if self.use_torch:
                checkpoint = torch.load(filepath, map_location=GPU_DEVICE, weights_only=False)
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                self.train_count = checkpoint.get('train_count', 0)
                self.last_loss = checkpoint.get('last_loss', 0.0)
                self.current_epoch = checkpoint.get('current_epoch', 0)
                # Restore scheduler state if available
                if 'scheduler_state_dict' in checkpoint and self.scheduler is not None:
                    try:
                        self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
                    except Exception as e:
                        logger.debug(f"Could not restore scheduler state: {e}")
                if 'warmup_scheduler_state_dict' in checkpoint and self.warmup_scheduler is not None:
                    try:
                        self.warmup_scheduler.load_state_dict(checkpoint['warmup_scheduler_state_dict'])
                    except Exception as e:
                        logger.debug(f"Could not restore warmup scheduler state: {e}")
            else:
                import pickle
                with open(filepath, 'rb') as f:
                    data = pickle.load(f)
                self.weights = data['weights']
                self.biases = data['biases']
                self.train_count = data.get('train_count', 0)
                self.last_loss = data.get('last_loss', 0.0)
            return True
        except Exception as e:
            logger.error(f"Failed to load weights: {e}")
            return False



class TrainingStatusManager:
    def __init__(self):
        self.status = "IDLE"
        self.progress = 0.0
        self.current_epoch = 0
        self.total_epochs = 0
        self.current_sample = 0
        self.total_samples = 0
        self.current_strategy = ""
        self.eta_seconds = 0
        self.start_time = None
        self.cpu_usage = 0.0
        self.gpu_usage = 0.0
        self.samples_per_second = 0.0
        self.phase = "IDLE"  # TRAINING or EVALUATION
        self._lock = threading.Lock()
    
    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)
            if self.total_samples > 0:
                self.progress = (self.current_sample / self.total_samples) * 100
            usage = get_system_usage()
            self.cpu_usage = usage['cpu_percent']
            self.gpu_usage = usage['gpu_percent']
            if self.start_time and self.current_sample > 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                self.samples_per_second = self.current_sample / elapsed if elapsed > 0 else 0
                remaining = self.total_samples - self.current_sample
                self.eta_seconds = remaining / self.samples_per_second if self.samples_per_second > 0 else 0
    
    def to_dict(self) -> Dict:
        return {
            'status': self.status, 'phase': self.phase, 'progress': round(self.progress, 1),
            'current_epoch': self.current_epoch, 'total_epochs': self.total_epochs,
            'current_sample': self.current_sample, 'total_samples': self.total_samples,
            'current_strategy': self.current_strategy, 'eta_seconds': int(self.eta_seconds),
            'eta_formatted': f"{int(self.eta_seconds // 60)}m {int(self.eta_seconds % 60)}s",
            'cpu_usage': round(self.cpu_usage, 1), 'gpu_usage': round(self.gpu_usage, 1),
            'samples_per_second': round(self.samples_per_second, 1),
            'device': 'HYBRID GPU+CPU' if USE_GPU else 'CPU', 'gpu_name': GPU_NAME
        }
    
    def save(self):
        try:
            with open(REALTIME_METRICS_FILE, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
        except:
            pass


# =============================================================================
# UNIFIED TRAINING BRAIN - MAIN CLASS
# =============================================================================
class UnifiedTrainingBrain:
    """
    Unified Brain v2.0 with PROPER train/eval split.
    
    KEY FIXES:
    1. Train on 80% of data, evaluate on 20% with TRAINED weights
    2. Strategy-specific features for each strategy category
    3. Adaptive thresholds based on market volatility
    """
    
    def __init__(self, save_dir: str = None):
        self.save_dir = Path(save_dir) if save_dir else DATA_DIR
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize strategies
        self.strategies: Dict[str, StrategyPerformance] = {
            s.value: StrategyPerformance(name=s.value) for s in StrategyType
        }
        
        # Initialize neural networks
        self.neural_nets: Dict[str, StrategyNeuralNet] = {
            s.value: StrategyNeuralNet() for s in StrategyType
        }
        
        self.strategy_weights: Dict[str, float] = {s.value: 1.0/N_STRATEGIES for s in StrategyType}
        self.training_iterations = 0
        self.status_manager = TrainingStatusManager()
        self.cpu_executor = ThreadPoolExecutor(max_workers=CPU_WORKERS)
        self.batch_size = 64 if USE_GPU else 32
        
        self._load_existing()
        logger.info(f"UnifiedTrainingBrain v2: GPU={USE_GPU} ({GPU_NAME}) | CPU Workers={CPU_WORKERS}")
    
    def _load_existing(self):
        try:
            if STRATEGY_TRADES_FILE.exists():
                with open(STRATEGY_TRADES_FILE) as f:
                    data = json.load(f)
                    for name, metrics in data.items():
                        if name in self.strategies:
                            s = self.strategies[name]
                            s.trades = metrics.get('trades', 0)
                            s.wins = metrics.get('wins', 0)
                            s.losses = metrics.get('losses', 0)
                            s.training_samples = metrics.get('training_samples', 0)
                            s.eval_samples = metrics.get('eval_samples', 0)
                            s.predictions_made = metrics.get('predictions_made', 0)
                            s.correct_predictions = metrics.get('correct_predictions', 0)
                            s.total_pnl = metrics.get('total_pnl', 0.0)
                            # Load calculated metrics directly
                            s.win_rate = metrics.get('win_rate', 0) / 100  # Stored as percentage
                            s.accuracy = metrics.get('accuracy', 0) / 100  # Stored as percentage
                            s.expectancy = metrics.get('expectancy', 0)
                            s.profit_factor = metrics.get('profit_factor', 0)
                            s.avg_win = metrics.get('avg_win', 0)
                            s.avg_loss = metrics.get('avg_loss', 0)
                            s.weight = metrics.get('weight', 5) / 100  # Stored as percentage
                    
                    # Update strategy weights from loaded data
                    total_weight = sum(s.weight for s in self.strategies.values())
                    if total_weight > 0:
                        for name, s in self.strategies.items():
                            self.strategy_weights[name] = s.weight
            
            # Load neural network weights if available
            loaded = self.load_all_weights()
            if loaded > 0:
                print(f"[BRAIN] Loaded {loaded} pre-trained neural networks")
        except Exception as e:
            logger.warning(f"Error loading existing data: {e}")



    def train_on_history(self, df: pd.DataFrame, lookahead: int = 5, max_samples: int = 5000,
                         epochs: int = 3, verbose: bool = True, progress_callback: Callable = None,
                         data_source: str = "unknown", symbol: str = "UNKNOWN",
                         train_ratio: float = 0.8, skip_integrity_check: bool = False) -> Dict:
        """
        FIX #1: PROPER TRAIN/EVAL SPLIT
        
        1. Split data: 80% training, 20% evaluation
        2. Train on training set (multiple epochs)
        3. Evaluate on held-out test set with TRAINED weights
        4. Record performance metrics from EVALUATION only
        
        This ensures win rates reflect actual model performance, not random guessing.
        
        Args:
            skip_integrity_check: If True, skip data integrity validation (for backtesting)
        """
        result = {'success': False, 'total_trained': 0, 'strategies_trained': [], 'eval_results': {}}
        
        # === DATA INTEGRITY GATE (Training Mode - relaxed) ===
        if not skip_integrity_check:
            try:
                from .data_integrity import get_integrity_guard
                guard = get_integrity_guard()
                # Use mode="training" to skip freshness check for historical data
                report = guard.validate(df, data_source, symbol, datetime.now(), mode="training")
                
                if not report.can_trade:
                    if verbose:
                        print(f"[TRAIN] DATA INTEGRITY FAILED for {symbol}")
                    result['error'] = 'Data integrity failed'
                    return result
                if verbose:
                    print(f"[TRAIN] Data integrity PASSED for {symbol}")
            except ImportError:
                if verbose:
                    print("[TRAIN] Data integrity module not loaded, proceeding")
        
        if len(df) < 200:
            if verbose:
                print(f"[TRAIN] Not enough data ({len(df)} bars, need 200+)")
            return result
        
        start_time = datetime.now()
        self.status_manager.start_time = start_time
        self.status_manager.update(status="TRAINING", phase="TRAINING", progress=0)
        
        # Extract OHLCV
        close = df['Close'].values
        high = df['High'].values if 'High' in df.columns else close
        low = df['Low'].values if 'Low' in df.columns else close
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(df))
        
        # FIX #3: Compute adaptive threshold based on volatility
        adaptive_threshold = compute_adaptive_threshold(close, high, low)
        
        if verbose:
            print(f"\n{'='*70}")
            print(f"UNIFIED BRAIN v2.0 - PROPER TRAIN/EVAL SPLIT")
            print(f"{'='*70}")
            print(f"Data: {len(df)} bars | Train: {train_ratio*100:.0f}% | Eval: {(1-train_ratio)*100:.0f}%")
            print(f"GPU: {GPU_NAME if USE_GPU else 'None'} | CPU Workers: {CPU_WORKERS}")
            print(f"Adaptive Threshold: {adaptive_threshold*100:.2f}% (based on ATR)")
            print(f"Lookahead: {lookahead} bars | Epochs: {epochs} | Batch: {self.batch_size}")
            print(f"{'='*70}\n")
        
        # =====================================================================
        # PHASE 1: SPLIT DATA
        # =====================================================================
        n_total = len(df)
        split_idx = int(n_total * train_ratio)
        
        # Training indices: first 80%
        train_start = 50
        train_end = split_idx - lookahead
        train_step = max(1, (train_end - train_start) // max_samples)
        train_indices = list(range(train_start, train_end, train_step))
        
        # Evaluation indices: last 20%
        eval_start = split_idx
        eval_end = n_total - lookahead
        eval_step = max(1, (eval_end - eval_start) // (max_samples // 4))  # Fewer eval samples
        eval_indices = list(range(eval_start, eval_end, eval_step))
        
        if verbose:
            print(f"[SPLIT] Training samples: {len(train_indices)} (bars 50-{split_idx})")
            print(f"[SPLIT] Evaluation samples: {len(eval_indices)} (bars {split_idx}-{n_total})")
        
        total_train_iterations = len(train_indices) * epochs * N_STRATEGIES
        total_eval_iterations = len(eval_indices) * N_STRATEGIES
        total_iterations = total_train_iterations + total_eval_iterations
        self.status_manager.update(total_epochs=epochs, total_samples=total_iterations)
        
        # =====================================================================
        # PHASE 2: TRAINING (on first 80%)
        # =====================================================================
        if verbose:
            print(f"\n[PHASE 1/2] TRAINING on {len(train_indices)} samples x {epochs} epochs...")
        
        total_trained = 0
        
        for epoch in range(epochs):
            epoch_start = time.time()
            self.status_manager.update(current_epoch=epoch + 1, phase="TRAINING")
            
            np.random.shuffle(train_indices)
            batch_queues = {s.value: [] for s in StrategyType}
            
            for idx_num, i in enumerate(train_indices):
                # FIX #2: Extract strategy-specific features
                future_ret = (close[i + lookahead] - close[i]) / close[i]
                
                # FIX #3: Use adaptive threshold
                if future_ret > adaptive_threshold:
                    actual_direction = 0  # BUY
                elif future_ret < -adaptive_threshold:
                    actual_direction = 2  # SELL
                else:
                    actual_direction = 1  # HOLD
                
                for strategy in StrategyType:
                    strat_name = strategy.value
                    
                    # FIX #2: Strategy-specific features
                    features = extract_features_for_strategy(
                        strategy, close[:i+1], high[:i+1], low[:i+1], volume[:i+1]
                    )
                    
                    # Add to batch (NO prediction during training - just collect data)
                    batch_queues[strat_name].append((features, actual_direction, future_ret * 100))
                    self.strategies[strat_name].training_samples += 1
                    
                    # Train when batch full
                    if len(batch_queues[strat_name]) >= self.batch_size:
                        self.neural_nets[strat_name].train_batch(batch_queues[strat_name])
                        total_trained += len(batch_queues[strat_name])
                        batch_queues[strat_name] = []
                
                # Progress update
                if idx_num % 100 == 0:
                    progress = epoch * len(train_indices) * N_STRATEGIES + idx_num * N_STRATEGIES
                    self.status_manager.update(current_sample=progress, current_strategy="training")
                    if progress_callback:
                        try:
                            progress_callback(self.status_manager.to_dict())
                        except:
                            pass
            
            # Flush remaining batches
            for strat_name, batch in batch_queues.items():
                if len(batch) >= 2:
                    self.neural_nets[strat_name].train_batch(batch)
                    total_trained += len(batch)
            
            # Step learning rate scheduler at end of each epoch
            for strat_name in self.neural_nets:
                net = self.neural_nets[strat_name]
                if hasattr(net, 'step_scheduler'):
                    net.step_scheduler(epoch=epoch)
            
            epoch_duration = time.time() - epoch_start
            lr_info = ""
            if hasattr(next(iter(self.neural_nets.values())), 'get_lr'):
                current_lr = next(iter(self.neural_nets.values())).get_lr()
                lr_info = f" | LR: {current_lr:.2e}"
            if verbose:
                print(f"  [Epoch {epoch+1}/{epochs}] {len(train_indices)*N_STRATEGIES:,} samples in {epoch_duration:.1f}s{lr_info}")
        
        if verbose:
            print(f"[PHASE 1/2] Training complete: {total_trained:,} total training iterations\n")



        # =====================================================================
        # PHASE 3: EVALUATION (on last 20%) - WITH TRAINED WEIGHTS
        # =====================================================================
        if verbose:
            print(f"[PHASE 2/2] EVALUATING on {len(eval_indices)} held-out samples...")
        
        self.status_manager.update(phase="EVALUATION")
        
        # Reset evaluation stats for clean measurement
        for strat_name in self.strategies:
            self.strategies[strat_name].reset_eval_stats()
        
        eval_results = {s.value: {'trades': 0, 'wins': 0, 'pnl': 0.0} for s in StrategyType}
        
        for idx_num, i in enumerate(eval_indices):
            future_ret = (close[i + lookahead] - close[i]) / close[i]
            
            # Use adaptive threshold for labeling
            if future_ret > adaptive_threshold:
                actual_direction = 0  # BUY
            elif future_ret < -adaptive_threshold:
                actual_direction = 2  # SELL
            else:
                actual_direction = 1  # HOLD
            
            for strategy in StrategyType:
                strat_name = strategy.value
                net = self.neural_nets[strat_name]
                perf = self.strategies[strat_name]
                
                # Extract strategy-specific features
                features = extract_features_for_strategy(
                    strategy, close[:i+1], high[:i+1], low[:i+1], volume[:i+1]
                )
                
                # NOW predict with TRAINED weights
                pred_class, confidence, probs = net.predict(features)
                
                # Calculate PnL based on prediction
                if pred_class == 0:  # BUY
                    pnl = future_ret * 100  # Long position
                elif pred_class == 2:  # SELL
                    pnl = -future_ret * 100  # Short position
                else:  # HOLD
                    pnl = 0
                
                # Record trade outcome
                perf.record_trade(pnl, pred_class, actual_direction)
                perf.eval_samples += 1
                
                # Track for summary
                if pred_class != 1:  # Non-HOLD trades
                    eval_results[strat_name]['trades'] += 1
                    eval_results[strat_name]['pnl'] += pnl
                    if pnl > 0:
                        eval_results[strat_name]['wins'] += 1
            
            # Progress update
            if idx_num % 50 == 0:
                progress = total_train_iterations + idx_num * N_STRATEGIES
                self.status_manager.update(current_sample=progress, current_strategy="evaluating")
        
        if verbose:
            print(f"[PHASE 2/2] Evaluation complete\n")
        
        # =====================================================================
        # PHASE 4: RESULTS & WEIGHT UPDATE
        # =====================================================================
        self._update_weights()
        
        duration = (datetime.now() - start_time).total_seconds()
        self.training_iterations += total_trained
        self.status_manager.update(status="COMPLETE", progress=100, current_sample=total_iterations)
        self.status_manager.save()
        
        # Sort strategies by expectancy
        sorted_strats = sorted(self.strategies.values(), key=lambda x: x.expectancy, reverse=True)
        
        if verbose:
            print(f"{'='*70}")
            print(f"TRAINING COMPLETE: {total_trained:,} iterations in {duration:.1f}s")
            print(f"{'='*70}")
            print(f"\n{'='*70}")
            print(f"EVALUATION RESULTS (on held-out 20%)")
            print(f"{'='*70}")
            print(f"{'Strategy':<25} {'Trades':>8} {'WinRate':>10} {'Accuracy':>10} {'Expectancy':>12}")
            print(f"{'-'*70}")
            
            for s in sorted_strats[:10]:
                trades = s.wins + s.losses
                wr = f"{s.win_rate*100:.1f}%" if trades > 0 else "N/A"
                print(f"{s.name:<25} {trades:>8} {wr:>10} {s.accuracy*100:>9.1f}% {s.expectancy:>12.2f}")
            
            print(f"\n{'='*70}")
            print(f"TOP 5 STRATEGIES BY EXPECTANCY:")
            for i, s in enumerate(sorted_strats[:5], 1):
                print(f"  {i}. {s.name}: WinRate={s.win_rate*100:.1f}% Exp={s.expectancy:.2f}")
            print(f"{'='*70}\n")
        
        result = {
            'success': True,
            'total_trained': total_trained,
            'duration_seconds': round(duration, 2),
            'samples_per_second': round(total_trained / duration, 2) if duration > 0 else 0,
            'strategies_trained': [s.value for s in StrategyType],
            'adaptive_threshold': round(adaptive_threshold * 100, 3),
            'train_samples': len(train_indices) * epochs,
            'eval_samples': len(eval_indices),
            'top_strategies': [
                {'name': s.name, 'win_rate': round(s.win_rate * 100, 1), 
                 'expectancy': round(s.expectancy, 2), 'trades': s.wins + s.losses}
                for s in sorted_strats[:5]
            ],
            'eval_results': {
                name: {
                    'win_rate': round(self.strategies[name].win_rate * 100, 1),
                    'accuracy': round(self.strategies[name].accuracy * 100, 1),
                    'expectancy': round(self.strategies[name].expectancy, 2),
                    'trades': self.strategies[name].wins + self.strategies[name].losses
                }
                for name in self.strategies
            }
        }
        
        self.save_all_reports()
        return result

    def train_multi_symbol(self, symbol_data: Dict[str, pd.DataFrame], lookahead: int = 5,
                           max_samples_per_symbol: int = 2000, epochs: int = 3,
                           verbose: bool = True, progress_callback: Callable = None) -> Dict:
        """
        Train on multiple symbols separately then combine results.
        This prevents one symbol from dominating and improves generalization.
        
        Args:
            symbol_data: Dict mapping symbol -> DataFrame with OHLCV
            lookahead: Bars to look ahead for labeling
            max_samples_per_symbol: Max training samples per symbol
            epochs: Training epochs per symbol
            verbose: Print progress
            progress_callback: Optional callback for UI updates
        """
        if verbose:
            print(f"\n{'='*70}")
            print(f"MULTI-SYMBOL TRAINING - {len(symbol_data)} symbols")
            print(f"{'='*70}\n")
        
        all_results = []
        total_trained = 0
        
        for i, (symbol, df) in enumerate(symbol_data.items()):
            if len(df) < 200:
                if verbose:
                    print(f"[{i+1}/{len(symbol_data)}] {symbol}: SKIP (only {len(df)} bars)")
                continue
            
            if verbose:
                print(f"\n[{i+1}/{len(symbol_data)}] Training on {symbol} ({len(df)} bars)...")
            
            result = self.train_on_history(
                df=df,
                lookahead=lookahead,
                max_samples=max_samples_per_symbol,
                epochs=epochs,
                verbose=False,  # Reduce noise
                progress_callback=progress_callback,
                data_source='yfinance',
                symbol=symbol,
                train_ratio=0.8
            )
            
            if result.get('success'):
                all_results.append(result)
                total_trained += result.get('total_trained', 0)
                
                # Get top strategy for this symbol
                top = result.get('top_strategies', [{}])[0]
                if verbose:
                    print(f"    [OK] {symbol}: Top={top.get('name','?')} WR={top.get('win_rate',0):.1f}%")
            else:
                if verbose:
                    print(f"    [FAIL] {symbol}: {result.get('error', 'Unknown')}")
        
        # Final summary
        if verbose and all_results:
            print(f"\n{'='*70}")
            print(f"MULTI-SYMBOL TRAINING COMPLETE")
            print(f"{'='*70}")
            print(f"Symbols trained: {len(all_results)}/{len(symbol_data)}")
            print(f"Total iterations: {total_trained:,}")
            
            # Show final top strategies
            sorted_strats = sorted(self.strategies.values(), key=lambda x: x.expectancy, reverse=True)
            print(f"\nFINAL TOP 5 STRATEGIES:")
            for i, s in enumerate(sorted_strats[:5], 1):
                print(f"  {i}. {s.name}: WR={s.win_rate*100:.1f}% Exp={s.expectancy:.2f}")
            print(f"{'='*70}\n")
        
        return {
            'success': len(all_results) > 0,
            'symbols_trained': len(all_results),
            'total_symbols': len(symbol_data),
            'total_trained': total_trained,
            'symbol_results': all_results
        }



    def _update_weights(self):
        """Update strategy weights based on evaluation performance."""
        total_score = 0
        scores = {}
        
        for name, perf in self.strategies.items():
            actual_trades = perf.wins + perf.losses
            if actual_trades >= 5:  # Need at least 5 trades for meaningful stats
                # Score based on: win_rate (40%) + accuracy (30%) + expectancy (30%)
                # Expectancy normalized to 0-1 scale
                exp_score = min(1.0, max(0, (perf.expectancy + 2) / 4))  # Map -2 to +2 → 0 to 1
                
                score = (
                    perf.win_rate * 0.4 +
                    perf.accuracy * 0.3 +
                    exp_score * 0.3
                )
                scores[name] = max(0.01, score)
                total_score += scores[name]
        
        if total_score > 0:
            for name, score in scores.items():
                self.strategy_weights[name] = score / total_score
                self.strategies[name].weight = self.strategy_weights[name]
    
    def get_ensemble_signal(self, features: np.ndarray, strategy: StrategyType = None) -> Tuple[str, float, Dict]:
        """Get weighted ensemble signal from all strategies."""
        votes = {'BUY': 0.0, 'HOLD': 0.0, 'SELL': 0.0}
        signals = {}
        signal_map = {0: 'BUY', 1: 'HOLD', 2: 'SELL'}
        
        for strat_type in StrategyType:
            strat_name = strat_type.value
            net = self.neural_nets[strat_name]
            
            # Use strategy-specific features if we have OHLCV, otherwise use provided features
            pred_class, conf, probs = net.predict(features)
            weight = self.strategy_weights.get(strat_name, 0.05)
            signal = signal_map[pred_class]
            votes[signal] += weight * conf
            signals[strat_name] = {
                'signal': signal, 
                'confidence': round(conf, 3), 
                'weight': round(weight, 4),
                'probs': {'BUY': round(probs[0], 3), 'HOLD': round(probs[1], 3), 'SELL': round(probs[2], 3)}
            }
        
        total = sum(votes.values())
        if total > 0:
            for k in votes:
                votes[k] /= total
        
        final_signal = max(votes, key=votes.get)
        return final_signal, votes[final_signal], signals
    
    def generate_signal(self, df: pd.DataFrame, use_top_n: int = 5) -> Dict:
        """
        Generate a trading signal from raw OHLCV DataFrame.
        
        This is the main API for live trading - takes a DataFrame and returns
        a complete signal with confidence and strategy breakdown.
        
        Args:
            df: DataFrame with Close, High, Low, Volume columns (at least 50 bars)
            use_top_n: Only use top N strategies by expectancy (0 = all)
            
        Returns:
            Dict with signal, confidence, votes, top_strategies, and metadata
        """
        if len(df) < 50:
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'error': f'Not enough data: {len(df)} bars (need 50+)',
                'votes': {'BUY': 0.33, 'HOLD': 0.34, 'SELL': 0.33}
            }
        
        close = df['Close'].values
        high = df['High'].values if 'High' in df.columns else close
        low = df['Low'].values if 'Low' in df.columns else close
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(df))
        
        # Get strategies sorted by expectancy
        sorted_strats = sorted(
            [(s, self.strategies[s.value]) for s in StrategyType],
            key=lambda x: x[1].expectancy,
            reverse=True
        )
        
        # Filter to top N if specified
        if use_top_n > 0:
            active_strats = sorted_strats[:use_top_n]
        else:
            active_strats = sorted_strats
        
        votes = {'BUY': 0.0, 'HOLD': 0.0, 'SELL': 0.0}
        signals = {}
        signal_map = {0: 'BUY', 1: 'HOLD', 2: 'SELL'}
        total_weight = 0
        
        for strat_type, perf in active_strats:
            strat_name = strat_type.value
            net = self.neural_nets[strat_name]
            
            # Extract strategy-specific features
            features = extract_features_for_strategy(strat_type, close, high, low, volume)
            
            # Get prediction
            pred_class, conf, probs = net.predict(features)
            weight = self.strategy_weights.get(strat_name, 0.05)
            signal = signal_map[pred_class]
            
            votes[signal] += weight * conf
            total_weight += weight
            
            signals[strat_name] = {
                'signal': signal,
                'confidence': round(conf, 3),
                'weight': round(weight, 4),
                'expectancy': round(perf.expectancy, 2),
                'win_rate': round(perf.win_rate * 100, 1)
            }
        
        # Normalize votes
        if total_weight > 0:
            for k in votes:
                votes[k] /= total_weight
        
        final_signal = max(votes, key=votes.get)
        final_confidence = votes[final_signal]
        
        # Compute signal strength: how much stronger is the winning signal?
        sorted_votes = sorted(votes.values(), reverse=True)
        signal_strength = sorted_votes[0] - sorted_votes[1] if len(sorted_votes) > 1 else 0
        
        return {
            'signal': final_signal,
            'confidence': round(final_confidence, 3),
            'signal_strength': round(signal_strength, 3),
            'votes': {k: round(v, 3) for k, v in votes.items()},
            'strategies_used': len(active_strats),
            'top_strategies': [
                {'name': s.value, 'signal': signals[s.value]['signal'], 
                 'confidence': signals[s.value]['confidence']}
                for s, _ in active_strats[:3]
            ],
            'all_signals': signals,
            'data_bars': len(df)
        }

    def get_ml_brain_stats(self) -> Dict:
        """Get comprehensive ML brain statistics."""
        usage = get_system_usage()
        strategy_stats = []
        
        for name, perf in self.strategies.items():
            strategy_stats.append({
                'name': name,
                'trades': perf.wins + perf.losses,
                'wins': perf.wins,
                'losses': perf.losses,
                'training_samples': perf.training_samples,
                'eval_samples': perf.eval_samples,
                'win_rate': round(perf.win_rate * 100, 1),
                'accuracy': round(perf.accuracy * 100, 1),
                'profit_factor': round(min(perf.profit_factor, 999), 2),
                'expectancy': round(perf.expectancy, 2),
                'avg_win': round(perf.avg_win, 2),
                'avg_loss': round(perf.avg_loss, 2),
                'weight': round(perf.weight * 100, 1)
            })
        
        strategy_stats.sort(key=lambda x: x['expectancy'], reverse=True)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'version': '2.0',
            'system': {
                'gpu_enabled': USE_GPU,
                'gpu_name': GPU_NAME,
                'cpu_cores': CPU_CORES,
                'cpu_workers': CPU_WORKERS,
                'cpu_usage': round(usage['cpu_percent'], 1),
                'gpu_usage': round(usage['gpu_percent'], 1)
            },
            'training': {
                'total_iterations': self.training_iterations,
                'status': self.status_manager.status,
                'phase': self.status_manager.phase,
                'progress': round(self.status_manager.progress, 1)
            },
            'strategies': strategy_stats,
            'top_5': strategy_stats[:5],
            'weights': {k: round(v * 100, 2) for k, v in self.strategy_weights.items()}
        }
    
    def save_all_reports(self):
        """Save all performance reports to metrics and wait directories."""
        # Strategy trades
        strategy_trades = {name: perf.to_dict() for name, perf in self.strategies.items()}
        
        with open(STRATEGY_TRADES_FILE, 'w') as f:
            json.dump(strategy_trades, f, indent=2)
        
        # Also save to wait directory
        with open(WAIT_DIR / "strategy_trades.json", 'w') as f:
            json.dump(strategy_trades, f, indent=2)
        
        # Individual strategy files
        for name, perf in self.strategies.items():
            filepath = METRICS_DIR / f"{name}_metrics.json"
            with open(filepath, 'w') as f:
                json.dump(perf.to_dict(), f, indent=2)
        
        # ML brain stats
        stats = self.get_ml_brain_stats()
        with open(METRICS_DIR / "ml_brain_stats.json", 'w') as f:
            json.dump(stats, f, indent=2)
        with open(WAIT_DIR / "ml_brain_stats.json", 'w') as f:
            json.dump(stats, f, indent=2)
        
        # Rankings
        rankings = sorted(
            [{'name': k, 'expectancy': v.expectancy, 'win_rate': v.win_rate, 
              'trades': v.wins + v.losses, 'accuracy': v.accuracy}
             for k, v in self.strategies.items()],
            key=lambda x: x['expectancy'], reverse=True
        )
        
        with open(METRICS_DIR / "strategy_rankings.json", 'w') as f:
            json.dump({'timestamp': datetime.now().isoformat(), 'rankings': rankings}, f, indent=2)
        with open(WAIT_DIR / "strategy_rankings.json", 'w') as f:
            json.dump({'timestamp': datetime.now().isoformat(), 'rankings': rankings}, f, indent=2)
        
        # Save neural network weights
        self.save_all_weights()
        
        self.status_manager.save()
        print(f"[BRAIN] Reports saved to {METRICS_DIR} and {WAIT_DIR}")
    
    def save_all_weights(self):
        """Save all neural network weights to disk for persistence."""
        weights_dir = WEIGHTS_DIR / "neural_nets"
        weights_dir.mkdir(parents=True, exist_ok=True)
        
        saved = 0
        for strat_name, net in self.neural_nets.items():
            ext = '.pt' if net.use_torch else '.pkl'
            filepath = weights_dir / f"{strat_name}{ext}"
            if net.save_weights(filepath):
                saved += 1
        
        print(f"[BRAIN] Saved {saved}/{len(self.neural_nets)} neural network weights")
        return saved
    
    def load_all_weights(self) -> int:
        """Load all neural network weights from disk."""
        weights_dir = WEIGHTS_DIR / "neural_nets"
        if not weights_dir.exists():
            return 0
        
        loaded = 0
        for strat_name, net in self.neural_nets.items():
            # Try both extensions
            for ext in ['.pt', '.pkl']:
                filepath = weights_dir / f"{strat_name}{ext}"
                if filepath.exists() and net.load_weights(filepath):
                    loaded += 1
                    break
        
        if loaded > 0:
            print(f"[BRAIN] Loaded {loaded}/{len(self.neural_nets)} neural network weights")
        return loaded
    
    def train_multi_symbol(self, symbol_data: Dict[str, pd.DataFrame], epochs: int = 3,
                           verbose: bool = True, max_samples_per_symbol: int = 2000) -> Dict:
        """
        Train on multiple symbols with proper data separation.
        
        Each symbol is trained/evaluated separately to prevent data leakage,
        then results are aggregated.
        
        Args:
            symbol_data: Dict of {symbol: DataFrame}
            epochs: Training epochs per symbol
            verbose: Print progress
            max_samples_per_symbol: Max samples per symbol
            
        Returns:
            Aggregated training result
        """
        if not symbol_data:
            return {'success': False, 'error': 'No data provided'}
        
        start_time = datetime.now()
        total_trained = 0
        all_results = {}
        
        if verbose:
            print(f"\n{'='*70}")
            print(f"MULTI-SYMBOL TRAINING - {len(symbol_data)} symbols")
            print(f"{'='*70}\n")
        
        for i, (symbol, df) in enumerate(symbol_data.items(), 1):
            if verbose:
                print(f"[{i}/{len(symbol_data)}] Training on {symbol} ({len(df)} bars)...")
            
            result = self.train_on_history(
                df,
                epochs=epochs,
                max_samples=max_samples_per_symbol,
                verbose=False,  # Suppress per-symbol output
                symbol=symbol,
                data_source='yfinance'
            )
            
            if result.get('success'):
                total_trained += result.get('total_trained', 0)
                all_results[symbol] = {
                    'success': True,
                    'samples': result.get('total_trained', 0),
                    'top_strategy': result.get('top_strategies', [{}])[0].get('name', 'N/A')
                }
                if verbose:
                    top = result.get('top_strategies', [{}])[0]
                    print(f"    [OK] {result.get('total_trained', 0):,} samples | "
                          f"Top: {top.get('name', 'N/A')} ({top.get('win_rate', 0):.1f}%)")
            else:
                all_results[symbol] = {'success': False, 'error': result.get('error', 'Unknown')}
                if verbose:
                    print(f"    [FAIL] {result.get('error', 'Unknown')}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Save everything
        self.save_all_reports()
        
        # Get final stats
        sorted_strats = sorted(self.strategies.values(), key=lambda x: x.expectancy, reverse=True)
        
        if verbose:
            print(f"\n{'='*70}")
            print(f"MULTI-SYMBOL TRAINING COMPLETE")
            print(f"{'='*70}")
            print(f"Total: {total_trained:,} iterations in {duration:.1f}s")
            print(f"\nTOP 5 STRATEGIES (aggregated):")
            for i, s in enumerate(sorted_strats[:5], 1):
                print(f"  {i}. {s.name}: WR={s.win_rate*100:.1f}% Exp={s.expectancy:.2f}")
            print(f"{'='*70}\n")
        
        return {
            'success': True,
            'total_trained': total_trained,
            'duration_seconds': round(duration, 2),
            'symbols_trained': len([r for r in all_results.values() if r.get('success')]),
            'symbol_results': all_results,
            'top_strategies': [
                {'name': s.name, 'win_rate': round(s.win_rate * 100, 1), 
                 'expectancy': round(s.expectancy, 2)}
                for s in sorted_strats[:5]
            ]
        }




# =============================================================================
# SINGLETON INSTANCE & EXPORTS
# =============================================================================
_unified_brain_instance = None


def get_unified_brain() -> UnifiedTrainingBrain:
    """Get or create the singleton UnifiedTrainingBrain instance."""
    global _unified_brain_instance
    if _unified_brain_instance is None:
        _unified_brain_instance = UnifiedTrainingBrain()
    return _unified_brain_instance


def reset_unified_brain():
    """Reset the singleton instance (for testing)."""
    global _unified_brain_instance
    _unified_brain_instance = None


def quick_train(symbols: List[str] = None, period: str = '1y', epochs: int = 3,
                verbose: bool = True) -> Dict:
    """
    Quick training helper that fetches data and trains the unified brain.
    
    Args:
        symbols: List of ticker symbols (default: major indices/stocks)
        period: YFinance period string ('1y', '2y', '6mo', etc.)
        epochs: Training epochs
        verbose: Print progress
        
    Returns:
        Training result dict
    """
    if symbols is None:
        symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'AMD', 'GOOGL', 'AMZN']
    
    try:
        import yfinance as yf
    except ImportError:
        return {'success': False, 'error': 'yfinance not installed'}
    
    if verbose:
        print(f"[QUICK TRAIN] Fetching {len(symbols)} symbols ({period})...")
    
    symbol_data = {}
    for symbol in symbols:
        try:
            df = yf.Ticker(symbol).history(period=period)
            if len(df) >= 200:
                symbol_data[symbol] = df
                if verbose:
                    print(f"  [OK] {symbol}: {len(df)} bars")
            else:
                if verbose:
                    print(f"  [SKIP] {symbol}: only {len(df)} bars")
        except Exception as e:
            if verbose:
                print(f"  [ERROR] {symbol}: {e}")
    
    if not symbol_data:
        return {'success': False, 'error': 'No valid data fetched'}
    
    brain = get_unified_brain()
    return brain.train_multi_symbol(symbol_data, epochs=epochs, verbose=verbose)


# Legacy compatibility
def extract_features(close: np.ndarray, high: np.ndarray, low: np.ndarray, 
                     volume: np.ndarray) -> np.ndarray:
    """Legacy feature extraction - returns base features only."""
    return extract_base_features(close, high, low, volume)


__all__ = [
    # Core classes
    'StrategyType', 'StrategyCategory', 'ALL_STRATEGIES', 'N_STRATEGIES',
    'StrategyPerformance', 'StrategyNeuralNet', 'TrainingStatusManager',
    'UnifiedTrainingBrain',
    
    # Functions
    'get_unified_brain', 'reset_unified_brain', 'get_system_usage', 'quick_train',
    'extract_features', 'extract_features_for_strategy',
    'extract_base_features', 'extract_ict_features', 'extract_momentum_features',
    'extract_trend_features', 'extract_volume_features', 'extract_pattern_features',
    'compute_adaptive_threshold', 'compute_atr',
    
    # Constants
    'USE_GPU', 'GPU_DEVICE', 'GPU_NAME', 'CPU_CORES', 'CPU_WORKERS', 'TORCH_AVAILABLE',
    'METRICS_DIR', 'WEIGHTS_DIR', 'DATA_DIR', 'WAIT_DIR', 'STRATEGY_CATEGORIES'
]


if __name__ == "__main__":
    # Quick test
    print("=" * 60)
    print("UNIFIED BRAIN v2.0 - TEST")
    print("=" * 60)
    
    brain = get_unified_brain()
    print(f"Initialized: {N_STRATEGIES} strategies")
    print(f"GPU: {USE_GPU} ({GPU_NAME})")
    print(f"CPU Workers: {CPU_WORKERS}")
    
    # Test with synthetic data
    np.random.seed(42)
    n = 500
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    volume = np.random.randint(1000, 10000, n).astype(float)
    
    df = pd.DataFrame({
        'Close': close, 'High': high, 'Low': low, 'Volume': volume
    })
    
    print(f"\nTest data: {len(df)} bars")
    print("Starting training...")
    
    result = brain.train_on_history(df, epochs=2, max_samples=200, verbose=True)
    
    if result['success']:
        print(f"\n[OK] Training successful!")
        print(f"  Top strategy: {result['top_strategies'][0]['name']}")
        print(f"  Win rate: {result['top_strategies'][0]['win_rate']}%")
        
        # Test generate_signal
        print("\n[TEST] generate_signal()...")
        signal = brain.generate_signal(df, use_top_n=5)
        print(f"  Signal: {signal['signal']} (conf={signal['confidence']:.2f})")
        print(f"  Votes: BUY={signal['votes']['BUY']:.2f} HOLD={signal['votes']['HOLD']:.2f} SELL={signal['votes']['SELL']:.2f}")
        print(f"  Top 3: {[s['name'] for s in signal['top_strategies']]}")
    else:
        print(f"\n[FAIL] Training failed: {result.get('error', 'Unknown')}")
