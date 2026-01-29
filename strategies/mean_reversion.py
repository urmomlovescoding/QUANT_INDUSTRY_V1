"""
Mean Reversion Strategies
=========================
Strategies that profit from price returning to equilibrium levels.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from .base import (
    BaseStrategy, Signal, SignalType, StrategyConfig,
    sma, ema, bollinger_bands, zscore, rsi, atr
)


class BollingerMeanReversion(BaseStrategy):
    """
    Bollinger Bands mean reversion strategy.
    
    Signals:
    - Price touches lower band: Long (oversold)
    - Price touches upper band: Short (overbought)
    - Price returns to middle band: Exit
    
    Parameters:
        period: int - Bollinger Bands period (default: 20)
        std_dev: float - Standard deviation multiplier (default: 2.0)
        exit_at_middle: bool - Exit when price reaches middle band (default: True)
    """
    
    @property
    def name(self) -> str:
        return "Bollinger Mean Reversion"
    
    @property
    def description(self) -> str:
        return "Trade reversions from Bollinger Band extremes"
    
    def get_required_history(self) -> int:
        return self.params.get('period', 20) + 5
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        period = self.params.get('period', 20)
        std_dev = self.params.get('std_dev', 2.0)
        
        signals = {}
        
        for symbol in data.columns:
            if symbol not in self.config.symbols:
                continue
            
            prices = data[symbol].dropna()
            if len(prices) < self.get_required_history():
                continue
            
            # Calculate Bollinger Bands
            upper, middle, lower = bollinger_bands(prices, period, std_dev)
            
            current_price = prices.iloc[-1]
            current_upper = upper.iloc[-1]
            current_middle = middle.iloc[-1]
            current_lower = lower.iloc[-1]
            
            # Calculate %B (where price is within bands)
            band_width = current_upper - current_lower
            if band_width > 0:
                percent_b = (current_price - current_lower) / band_width
            else:
                percent_b = 0.5
            
            # Generate signal based on band position
            if current_price <= current_lower:
                # At or below lower band - oversold, go long
                strength = min(1.0, (current_lower - current_price) / (band_width * 0.1) + 0.5)
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=strength,
                    metadata={
                        'percent_b': percent_b,
                        'price': current_price,
                        'lower': current_lower,
                        'middle': current_middle,
                        'upper': current_upper
                    }
                )
            elif current_price >= current_upper:
                # At or above upper band - overbought, go short
                strength = min(1.0, (current_price - current_upper) / (band_width * 0.1) + 0.5)
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    strength=strength,
                    metadata={
                        'percent_b': percent_b,
                        'price': current_price,
                        'lower': current_lower,
                        'middle': current_middle,
                        'upper': current_upper
                    }
                )
            elif 0.4 < percent_b < 0.6:
                # Near middle band - exit positions
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.FLAT,
                    metadata={'percent_b': percent_b, 'reason': 'at_middle'}
                )
            else:
                # In between - hold current position
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.HOLD,
                    metadata={'percent_b': percent_b}
                )
        
        return signals


class ZScoreMeanReversion(BaseStrategy):
    """
    Z-Score based mean reversion.
    
    Uses statistical deviation from the mean to identify
    extreme prices likely to revert.
    
    Parameters:
        lookback: int - Z-score calculation window (default: 20)
        entry_threshold: float - Z-score threshold for entry (default: 2.0)
        exit_threshold: float - Z-score threshold for exit (default: 0.5)
    """
    
    @property
    def name(self) -> str:
        return "Z-Score Mean Reversion"
    
    @property
    def description(self) -> str:
        return "Trade based on statistical deviation from mean"
    
    def get_required_history(self) -> int:
        return self.params.get('lookback', 20) + 5
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        lookback = self.params.get('lookback', 20)
        entry_threshold = self.params.get('entry_threshold', 2.0)
        exit_threshold = self.params.get('exit_threshold', 0.5)
        
        signals = {}
        
        for symbol in data.columns:
            if symbol not in self.config.symbols:
                continue
            
            prices = data[symbol].dropna()
            if len(prices) < self.get_required_history():
                continue
            
            # Calculate Z-score
            z = zscore(prices, lookback)
            current_z = z.iloc[-1]
            
            if pd.isna(current_z):
                continue
            
            # Entry signals
            if current_z < -entry_threshold:
                # Price is significantly below mean - buy
                strength = min(1.0, abs(current_z) / (entry_threshold * 2))
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=strength,
                    metadata={'zscore': current_z, 'threshold': entry_threshold}
                )
            elif current_z > entry_threshold:
                # Price is significantly above mean - sell
                strength = min(1.0, abs(current_z) / (entry_threshold * 2))
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    strength=strength,
                    metadata={'zscore': current_z, 'threshold': entry_threshold}
                )
            elif abs(current_z) < exit_threshold:
                # Price near mean - exit
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.FLAT,
                    metadata={'zscore': current_z, 'reason': 'reverted_to_mean'}
                )
            else:
                # Between entry and exit thresholds - hold
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.HOLD,
                    metadata={'zscore': current_z}
                )
        
        return signals


class RSIMeanReversion(BaseStrategy):
    """
    RSI mean reversion - trades extreme RSI levels.
    
    Unlike RSI momentum which follows trends, this strategy
    fades extreme moves expecting reversion.
    
    Parameters:
        rsi_period: int - RSI period (default: 14)
        oversold: float - Oversold threshold (default: 30)
        overbought: float - Overbought threshold (default: 70)
        extreme_oversold: float - Extreme oversold (default: 20)
        extreme_overbought: float - Extreme overbought (default: 80)
    """
    
    @property
    def name(self) -> str:
        return "RSI Mean Reversion"
    
    @property
    def description(self) -> str:
        return "Fade extreme RSI readings expecting reversion"
    
    def get_required_history(self) -> int:
        return self.params.get('rsi_period', 14) + 5
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        rsi_period = self.params.get('rsi_period', 14)
        oversold = self.params.get('oversold', 30)
        overbought = self.params.get('overbought', 70)
        extreme_oversold = self.params.get('extreme_oversold', 20)
        extreme_overbought = self.params.get('extreme_overbought', 80)
        
        signals = {}
        
        for symbol in data.columns:
            if symbol not in self.config.symbols:
                continue
            
            prices = data[symbol].dropna()
            if len(prices) < self.get_required_history():
                continue
            
            # Calculate RSI
            current_rsi = rsi(prices, rsi_period).iloc[-1]
            
            if pd.isna(current_rsi):
                continue
            
            # Generate reversal signals
            if current_rsi <= extreme_oversold:
                # Extremely oversold - strong long
                strength = (extreme_oversold - current_rsi) / extreme_oversold + 0.5
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=min(1.0, strength),
                    metadata={'rsi': current_rsi, 'level': 'extreme_oversold'}
                )
            elif current_rsi <= oversold:
                # Oversold - moderate long
                strength = (oversold - current_rsi) / (oversold - extreme_oversold) * 0.5
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.LONG,
                    strength=max(0.3, strength),
                    metadata={'rsi': current_rsi, 'level': 'oversold'}
                )
            elif current_rsi >= extreme_overbought:
                # Extremely overbought - strong short
                strength = (current_rsi - extreme_overbought) / (100 - extreme_overbought) + 0.5
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    strength=min(1.0, strength),
                    metadata={'rsi': current_rsi, 'level': 'extreme_overbought'}
                )
            elif current_rsi >= overbought:
                # Overbought - moderate short
                strength = (current_rsi - overbought) / (extreme_overbought - overbought) * 0.5
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.SHORT,
                    strength=max(0.3, strength),
                    metadata={'rsi': current_rsi, 'level': 'overbought'}
                )
            elif 45 < current_rsi < 55:
                # RSI near 50 - exit positions
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.FLAT,
                    metadata={'rsi': current_rsi, 'reason': 'neutral'}
                )
            else:
                # Hold current position
                signals[symbol] = Signal(
                    symbol=symbol,
                    signal_type=SignalType.HOLD,
                    metadata={'rsi': current_rsi}
                )
        
        return signals


class PairsTrading(BaseStrategy):
    """
    Statistical arbitrage pairs trading.
    
    Identifies cointegrated pairs and trades the spread
    when it deviates from equilibrium.
    
    Parameters:
        lookback: int - Period for spread calculation (default: 60)
        entry_zscore: float - Z-score entry threshold (default: 2.0)
        exit_zscore: float - Z-score exit threshold (default: 0.5)
        pair: tuple - Pair of symbols to trade (required)
    """
    
    @property
    def name(self) -> str:
        return "Pairs Trading"
    
    @property
    def description(self) -> str:
        return "Statistical arbitrage on cointegrated pairs"
    
    def get_required_history(self) -> int:
        return self.params.get('lookback', 60) + 10
    
    def validate_params(self) -> bool:
        pair = self.params.get('pair')
        return pair is not None and len(pair) == 2
    
    def generate_signals(self, data: pd.DataFrame) -> Dict[str, Signal]:
        lookback = self.params.get('lookback', 60)
        entry_z = self.params.get('entry_zscore', 2.0)
        exit_z = self.params.get('exit_zscore', 0.5)
        symbol_a, symbol_b = self.params.get('pair')
        
        signals = {}
        
        if symbol_a not in data.columns or symbol_b not in data.columns:
            return signals
        
        prices_a = data[symbol_a].dropna()
        prices_b = data[symbol_b].dropna()
        
        # Align data
        common_idx = prices_a.index.intersection(prices_b.index)
        if len(common_idx) < self.get_required_history():
            return signals
        
        prices_a = prices_a.loc[common_idx]
        prices_b = prices_b.loc[common_idx]
        
        # Calculate hedge ratio (simple ratio method)
        ratio = prices_a / prices_b
        
        # Calculate spread z-score
        spread_z = zscore(ratio, lookback)
        current_z = spread_z.iloc[-1]
        
        if pd.isna(current_z):
            return signals
        
        # Generate pairs signals
        if current_z < -entry_z:
            # Spread too low - long A, short B
            strength = min(1.0, abs(current_z) / (entry_z * 2))
            signals[symbol_a] = Signal(
                symbol=symbol_a,
                signal_type=SignalType.LONG,
                strength=strength,
                metadata={'pair_zscore': current_z, 'pair': f'{symbol_a}/{symbol_b}'}
            )
            signals[symbol_b] = Signal(
                symbol=symbol_b,
                signal_type=SignalType.SHORT,
                strength=strength,
                metadata={'pair_zscore': current_z, 'pair': f'{symbol_a}/{symbol_b}'}
            )
        elif current_z > entry_z:
            # Spread too high - short A, long B
            strength = min(1.0, abs(current_z) / (entry_z * 2))
            signals[symbol_a] = Signal(
                symbol=symbol_a,
                signal_type=SignalType.SHORT,
                strength=strength,
                metadata={'pair_zscore': current_z, 'pair': f'{symbol_a}/{symbol_b}'}
            )
            signals[symbol_b] = Signal(
                symbol=symbol_b,
                signal_type=SignalType.LONG,
                strength=strength,
                metadata={'pair_zscore': current_z, 'pair': f'{symbol_a}/{symbol_b}'}
            )
        elif abs(current_z) < exit_z:
            # Spread reverted - exit both
            signals[symbol_a] = Signal(
                symbol=symbol_a,
                signal_type=SignalType.FLAT,
                metadata={'pair_zscore': current_z, 'reason': 'spread_converged'}
            )
            signals[symbol_b] = Signal(
                symbol=symbol_b,
                signal_type=SignalType.FLAT,
                metadata={'pair_zscore': current_z, 'reason': 'spread_converged'}
            )
        else:
            # Hold current positions
            signals[symbol_a] = Signal(
                symbol=symbol_a,
                signal_type=SignalType.HOLD,
                metadata={'pair_zscore': current_z}
            )
            signals[symbol_b] = Signal(
                symbol=symbol_b,
                signal_type=SignalType.HOLD,
                metadata={'pair_zscore': current_z}
            )
        
        return signals
