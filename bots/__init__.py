"""
Trading Bots Module
===================
Automated trading bots that receive signals from ML Brain.
"""

from .base import TradingBot, BotConfig, Trade, TradeStatus, BotStatus
from .implementations import (
    TPTBot,
    MomentumBot,
    SwingBot,
    MeanReversionBot,
    ScalpBot,
    BotFactory,
)

__all__ = [
    # Base
    'TradingBot',
    'BotConfig',
    'Trade',
    'TradeStatus',
    'BotStatus',
    # Implementations
    'TPTBot',
    'MomentumBot',
    'SwingBot',
    'MeanReversionBot',
    'ScalpBot',
    'BotFactory',
]
