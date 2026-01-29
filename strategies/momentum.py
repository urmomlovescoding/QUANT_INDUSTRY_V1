"""
Momentum Strategies
===================
Time-series and cross-sectional momentum strategies.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from .base import (
    BaseStrategy, Signal, SignalType, StrategyConfig,
    sma, ema, rsi, macd, returns, volatility
)


class MomentumStrategy(BaseStrategy):
    """
    Classic momentum strategy - buy winners, sell losers.
    
    Parameters:
        lookback: int - Return calculation period (default: 20)
        holding: int - Holding period before rebalance (default: 5)
        top_n: int - Number of top/bottom stocks to trade (default: 3)
        threshold: float - Minimum return threshold (default: 0.02)
    """
    
    @property
    def name(self) -> str:
        return "Momentum"
    
    @property
    def description(self) -> str:
        return "Time-series momentum: buy assets with positive recent returns"
    
    def get_required_history(self) -> int:
        return self.params.get('lookback', 20) + 5
    
    def validate_params(self) -> bool:
        lookback = self.params.get('lookback', 20)
        return lookback > 0
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        lookback = self.params.get('lookback', 20)
        threshold = self.params.get('threshold', 0.02)
        
        signals = {}
        
        for symbol in data.columns:
            if symbol not in self.config.symbols:
                continue
            
            prices = data[symbol].dropna()
            if len(prices) < lookback + 1:
                continue
            
            # Calculate momentum (return over lookback period)
            ret = (prices.iloc[-1] / prices.iloc[-lookback] - 1)
            
            # Generate signal based on momentum
            if ret > threshold:
                strength = min(1.0, ret / (threshold * 3))  # Scale strength
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=strength,
                    metadata={'return': ret, 'lookback': lookback}
                )
            elif ret < -threshold:
                strength = min(1.0, abs(ret) / (threshold * 3))
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    strength=strength,
                    metadata={'return': ret, 'lookback': lookback}
                )
            else:
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.FLAT,
                    strength=0,
                    metadata={'return': ret, 'lookback': lookback}
                )
        
        return signals


class DualMomentumStrategy(BaseStrategy):
    """
    Gary Antonacci's Dual Momentum.
    
    Combines:
    1. Absolute momentum (time-series) - is asset trending up?
    2. Relative momentum (cross-sectional) - is asset outperforming?
    
    Parameters:
        lookback: int - Momentum lookback period (default: 252)
        risk_free_symbol: str - Risk-free proxy (default: 'SHY')
    """
    
    @property
    def name(self) -> str:
        return "Dual Momentum"
    
    @property
    def description(self) -> str:
        return "Combines absolute and relative momentum for robust signals"
    
    def get_required_history(self) -> int:
        return self.params.get('lookback', 252) + 10
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        lookback = self.params.get('lookback', 252)
        rf_symbol = self.params.get('risk_free_symbol', 'SHY')
        
        signals = {}
        
        # Calculate returns for all symbols
        returns_dict = {}
        for symbol in data.columns:
            prices = data[symbol].dropna()
            if len(prices) >= lookback:
                returns_dict[symbol] = prices.iloc[-1] / prices.iloc[-lookback] - 1
        
        if not returns_dict:
            return signals
        
        # Get risk-free return (or use 0 if not available)
        rf_return = returns_dict.get(rf_symbol, 0.02)
        
        # Rank symbols by return (excluding risk-free)
        tradeable = {k: v for k, v in returns_dict.items() 
                    if k in self.config.symbols and k != rf_symbol}
        
        if not tradeable:
            return signals
        
        ranked = sorted(tradeable.items(), key=lambda x: x[1], reverse=True)
        
        # Apply dual momentum rules
        for rank, (symbol, ret) in enumerate(ranked):
            # Absolute momentum: only go long if beating risk-free
            if ret > rf_return:
                # Relative momentum: strength based on rank
                strength = 1.0 - (rank / len(ranked)) * 0.5
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=strength,
                    metadata={
                        'return': ret,
                        'rank': rank + 1,
                        'vs_rf': ret - rf_return
                    }
                )
            else:
                # Failed absolute momentum - go to cash
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.FLAT,
                    metadata={'return': ret, 'reason': 'below_rf'}
                )
        
        return signals


class RSIMomentumStrategy(BaseStrategy):
    """
    RSI-based momentum strategy.
    
    Uses RSI to identify momentum extremes:
    - RSI > 70: Strong upward momentum (reduce/exit longs)
    - RSI < 30: Strong downward momentum (potential reversal)
    - RSI between 30-70: Follow trend direction
    
    Parameters:
        rsi_period: int - RSI calculation period (default: 14)
        overbought: float - Overbought threshold (default: 70)
        oversold: float - Oversold threshold (default: 30)
        trend_period: int - Trend confirmation period (default: 50)
    """
    
    @property
    def name(self) -> str:
        return "RSI Momentum"
    
    @property
    def description(self) -> str:
        return "Uses RSI to time momentum entries and exits"
    
    def get_required_history(self) -> int:
        return max(
            self.params.get('rsi_period', 14),
            self.params.get('trend_period', 50)
        ) + 10
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        rsi_period = self.params.get('rsi_period', 14)
        overbought = self.params.get('overbought', 70)
        oversold = self.params.get('oversold', 30)
        trend_period = self.params.get('trend_period', 50)
        
        signals = {}
        
        for symbol in data.columns:
            if symbol not in self.config.symbols:
                continue
            
            prices = data[symbol].dropna()
            if len(prices) < self.get_required_history():
                continue
            
            # Calculate RSI
            current_rsi = rsi(prices, rsi_period).iloc[-1]
            
            # Calculate trend (price vs SMA)
            trend_sma = sma(prices, trend_period).iloc[-1]
            is_uptrend = prices.iloc[-1] > trend_sma
            
            # Generate signal
            if current_rsi < oversold:
                # Oversold - potential long entry
                strength = (oversold - current_rsi) / oversold
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=strength,
                    metadata={'rsi': current_rsi, 'trend': 'up' if is_uptrend else 'down'}
                )
            elif current_rsi > overbought:
                # Overbought - potential short/exit
                strength = (current_rsi - overbought) / (100 - overbought)
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.SHORT if not is_uptrend else SignalType.FLAT,
                    strength=strength,
                    metadata={'rsi': current_rsi, 'trend': 'up' if is_uptrend else 'down'}
                )
            else:
                # Neutral RSI - follow trend
                if is_uptrend:
                    strength = (current_rsi - 50) / 50 * 0.5  # Moderate position
                    signals[symbol] = Signal(
                        symbol=symbol,
                        signal_type=SignalType.LONG,
                        strength=max(0.1, strength),
                        metadata={'rsi': current_rsi, 'trend': 'up'}
                    )
                else:
                    signals[symbol] = Signal(
                        symbol=symbol,
                        signal_type=SignalType.FLAT,
                        metadata={'rsi': current_rsi, 'trend': 'down'}
                    )
        
        return signals


class MACDMomentumStrategy(BaseStrategy):
    """
    MACD-based momentum strategy.
    
    Signals:
    - MACD line crosses above signal line: Long
    - MACD line crosses below signal line: Short/Exit
    - Histogram direction confirms momentum strength
    
    Parameters:
        fast_period: int - Fast EMA period (default: 12)
        slow_period: int - Slow EMA period (default: 26)
        signal_period: int - Signal line period (default: 9)
    """
    
    @property
    def name(self) -> str:
        return "MACD Momentum"
    
    @property
    def description(self) -> str:
        return "MACD crossover strategy with histogram confirmation"
    
    def get_required_history(self) -> int:
        return self.params.get('slow_period', 26) + self.params.get('signal_period', 9) + 5
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        fast = self.params.get('fast_period', 12)
        slow = self.params.get('slow_period', 26)
        signal_period = self.params.get('signal_period', 9)
        
        signals = {}
        
        for symbol in data.columns:
            if symbol not in self.config.symbols:
                continue
            
            prices = data[symbol].dropna()
            if len(prices) < self.get_required_history():
                continue
            
            # Calculate MACD
            macd_line, signal_line, histogram = macd(prices, fast, slow, signal_period)
            
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_hist = histogram.iloc[-1]
            prev_hist = histogram.iloc[-2] if len(histogram) > 1 else 0
            
            # Check for crossover
            prev_macd = macd_line.iloc[-2] if len(macd_line) > 1 else current_macd
            prev_signal = signal_line.iloc[-2] if len(signal_line) > 1 else current_signal
            
            bullish_cross = prev_macd <= prev_signal and current_macd > current_signal
            bearish_cross = prev_macd >= prev_signal and current_macd < current_signal
            
            # Histogram momentum
            hist_expanding = abs(current_hist) > abs(prev_hist)
            
            if bullish_cross or (current_macd > current_signal and current_hist > 0):
                strength = 0.8 if bullish_cross else 0.5
                if hist_expanding and current_hist > 0:
                    strength = min(1.0, strength + 0.2)
                    
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=strength,
                    metadata={
                        'macd': current_macd,
                        'signal': current_signal,
                        'histogram': current_hist,
                        'crossover': 'bullish' if bullish_cross else None
                    }
                )
            elif bearish_cross or (current_macd < current_signal and current_hist < 0):
                strength = 0.8 if bearish_cross else 0.5
                if hist_expanding and current_hist < 0:
                    strength = min(1.0, strength + 0.2)
                    
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    strength=strength,
                    metadata={
                        'macd': current_macd,
                        'signal': current_signal,
                        'histogram': current_hist,
                        'crossover': 'bearish' if bearish_cross else None
                    }
                )
            else:
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.HOLD,
                    metadata={'macd': current_macd, 'signal': current_signal}
                )
        
        return signals
