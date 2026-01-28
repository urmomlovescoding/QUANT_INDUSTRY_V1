"""
QUANT_INDUSTRY_V1 Strategies Module

Strategy framework with:
- Base strategy interface
- Performance attribution
- Strategy registry
- Example strategies

Usage:
    from strategies import BaseStrategy, StrategyConfig, Signal

    class MyStrategy(BaseStrategy):
        def generate_signals(self, data, features, regime):
            # Your logic here
            return [Signal(...)]

    strategy = MyStrategy()
    signals = strategy.update(market_data)
"""

from .base import (
    # Types
    StrategyStatus,
    SignalDirection,
    Signal,
    StrategyConfig,
    StrategyMetrics,
    # Base
    BaseStrategy,
    # Registry
    StrategyRegistry,
    # Examples
    MomentumStrategy,
    MeanReversionStrategy,
)

__all__ = [
    # Types
    'StrategyStatus',
    'SignalDirection',
    'Signal',
    'StrategyConfig',
    'StrategyMetrics',
    # Base
    'BaseStrategy',
    # Registry
    'StrategyRegistry',
    # Examples
    'MomentumStrategy',
    'MeanReversionStrategy',
]
