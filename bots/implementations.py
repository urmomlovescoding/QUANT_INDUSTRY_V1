"""
Trading Bot Implementations
===========================
Specific bot implementations that receive signals from ML Brain.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import numpy as np

from .base import TradingBot, BotConfig, Trade, TradeStatus

logger = logging.getLogger(__name__)


class TPTBot(TradingBot):
    """
    Trend + Pullback + Trigger Bot
    
    Trades pullbacks in established trends:
    - Waits for trend confirmation from ML Brain
    - Enters on pullbacks to key levels
    - Tight stops, wider targets
    """
    
    def __init__(self, brain_interface, broker, **kwargs):
        config = BotConfig(
            bot_id="tpt_bot",
            name="TPT Strategy Bot",
            max_positions=3,
            max_position_size=0.15,
            min_signal_confidence=0.6,
            default_stop_loss_pct=0.015,
            default_take_profit_pct=0.045,  # 3:1 RR
            max_holding_hours=48,
            valid_regimes=["trending_up", "trending_down"],
            valid_signal_types=["composite", "directional", "momentum"],
            **kwargs
        )
        super().__init__(config, brain_interface, broker)
        
        # TPT-specific state
        self.trend_confirmations: Dict[str, int] = {}  # Symbol -> confirmation count
        self.pullback_levels: Dict[str, List[float]] = {}
    
    def _custom_filter(self, signal) -> bool:
        """TPT: Only trade strong trends with pullback opportunities."""
        # Need high strength for trends
        if signal.strength < 0.6:
            return False
        
        # Track trend confirmations
        symbol = signal.symbol
        if symbol not in self.trend_confirmations:
            self.trend_confirmations[symbol] = 0
        
        # Same direction increases confirmation
        if self.trend_confirmations[symbol] == 0:
            self.trend_confirmations[symbol] = signal.direction
            return False  # Wait for confirmation
        
        if self.trend_confirmations[symbol] == signal.direction:
            return True  # Confirmed trend
        else:
            self.trend_confirmations[symbol] = signal.direction
            return False  # Trend changed, wait
    
    async def _calculate_position_size(self, signal) -> float:
        """TPT: Scale size by confidence and trend strength."""
        base_size = self.config.max_position_size * signal.suggested_size
        
        # Scale by confidence
        confidence_scale = 0.5 + 0.5 * signal.confidence
        
        # Scale by strength
        strength_scale = 0.5 + 0.5 * signal.strength
        
        return base_size * confidence_scale * strength_scale
    
    async def _custom_monitor(self, trade: Trade, current_price: float):
        """TPT: Trail stops in profit."""
        if trade.pnl_pct > 0.02:  # 2% profit
            # Trail stop to break even
            new_stop = trade.entry_price
            if trade.direction > 0:
                trade.stop_loss = max(trade.stop_loss or 0, new_stop)
            else:
                trade.stop_loss = min(trade.stop_loss or float('inf'), new_stop)


class MomentumBot(TradingBot):
    """
    Momentum Bot
    
    Trades momentum signals:
    - Enters on strong momentum
    - Quick exits on momentum fade
    - Wider stops, tighter targets
    """
    
    def __init__(self, brain_interface, broker, **kwargs):
        config = BotConfig(
            bot_id="momentum_bot",
            name="Momentum Strategy Bot",
            max_positions=5,
            max_position_size=0.1,
            min_signal_confidence=0.5,
            default_stop_loss_pct=0.025,
            default_take_profit_pct=0.02,  # Quick profits
            max_holding_hours=12,
            valid_regimes=["trending_up", "trending_down", "volatile"],
            valid_signal_types=["composite", "momentum"],
            **kwargs
        )
        super().__init__(config, brain_interface, broker)
        
        # Track momentum
        self.momentum_history: Dict[str, List[float]] = {}
    
    def _custom_filter(self, signal) -> bool:
        """Momentum: Trade when momentum is accelerating."""
        symbol = signal.symbol
        
        if symbol not in self.momentum_history:
            self.momentum_history[symbol] = []
        
        self.momentum_history[symbol].append(signal.strength)
        
        # Keep last 5
        if len(self.momentum_history[symbol]) > 5:
            self.momentum_history[symbol] = self.momentum_history[symbol][-5:]
        
        # Check for accelerating momentum
        if len(self.momentum_history[symbol]) >= 3:
            recent = self.momentum_history[symbol][-3:]
            if recent[-1] > recent[-2] > recent[-3]:  # Accelerating
                return True
        
        return signal.strength > 0.7  # Or just very strong
    
    async def _calculate_position_size(self, signal) -> float:
        """Momentum: Size by momentum strength."""
        return self.config.max_position_size * signal.strength * signal.confidence


class SwingBot(TradingBot):
    """
    Swing Trading Bot
    
    Longer-term trades based on regime changes:
    - Enters on regime shifts
    - Holds through minor pullbacks
    - Wider everything
    """
    
    def __init__(self, brain_interface, broker, **kwargs):
        config = BotConfig(
            bot_id="swing_bot",
            name="Swing Strategy Bot",
            max_positions=2,
            max_position_size=0.2,
            min_signal_confidence=0.7,  # High confidence needed
            default_stop_loss_pct=0.05,
            default_take_profit_pct=0.15,  # 3:1 RR
            max_holding_hours=168,  # 1 week
            valid_regimes=["trending_up", "trending_down"],
            valid_signal_types=["composite", "regime"],
            **kwargs
        )
        super().__init__(config, brain_interface, broker)
        
        # Track regimes
        self.last_regime: Dict[str, str] = {}
    
    def _custom_filter(self, signal) -> bool:
        """Swing: Trade on regime changes."""
        symbol = signal.symbol
        current_regime = signal.regime
        
        if symbol not in self.last_regime:
            self.last_regime[symbol] = current_regime
            return False  # Need baseline
        
        previous = self.last_regime[symbol]
        self.last_regime[symbol] = current_regime
        
        # Trade on regime change to trending
        if previous in ['ranging', 'volatile']:
            if current_regime in ['trending_up', 'trending_down']:
                return True
        
        return False
    
    async def _calculate_position_size(self, signal) -> float:
        """Swing: Conservative sizing."""
        return self.config.max_position_size * 0.5 * signal.confidence


class MeanReversionBot(TradingBot):
    """
    Mean Reversion Bot
    
    Trades reversals in ranging markets:
    - Only trades in ranging regime
    - Fades extremes
    - Quick exits
    """
    
    def __init__(self, brain_interface, broker, **kwargs):
        config = BotConfig(
            bot_id="mean_reversion_bot",
            name="Mean Reversion Bot",
            max_positions=4,
            max_position_size=0.1,
            min_signal_confidence=0.5,
            default_stop_loss_pct=0.015,
            default_take_profit_pct=0.01,  # Small targets
            max_holding_hours=6,
            valid_regimes=["ranging"],
            valid_signal_types=["composite", "mean_reversion"],
            **kwargs
        )
        super().__init__(config, brain_interface, broker)
    
    def _custom_filter(self, signal) -> bool:
        """Mean Reversion: Only trade extremes."""
        # Opposite of signal direction (fading)
        # Higher strength = more extreme = better
        return signal.strength > 0.65 and signal.regime == 'ranging'
    
    async def _calculate_position_size(self, signal) -> float:
        """Mean Reversion: Size by how extreme the move."""
        return self.config.max_position_size * (signal.strength - 0.5) * 2


class ScalpBot(TradingBot):
    """
    Scalping Bot
    
    High frequency, small profits:
    - Quick in/out
    - Tiny targets and stops
    - Volume-based signals
    """
    
    def __init__(self, brain_interface, broker, **kwargs):
        config = BotConfig(
            bot_id="scalp_bot",
            name="Scalping Bot",
            max_positions=1,
            max_position_size=0.05,
            min_signal_confidence=0.6,
            default_stop_loss_pct=0.003,
            default_take_profit_pct=0.002,
            max_holding_hours=0.5,  # 30 minutes
            valid_regimes=["trending_up", "trending_down", "ranging", "volatile"],
            valid_signal_types=["composite"],
            use_limit_orders=True,
            limit_offset_bps=2.0,
            **kwargs
        )
        super().__init__(config, brain_interface, broker)
        
        # Rate limiting
        self.last_trade_time: Optional[datetime] = None
        self.min_interval = timedelta(minutes=5)
    
    def _custom_filter(self, signal) -> bool:
        """Scalp: Rate limit trades."""
        if self.last_trade_time:
            if datetime.now() - self.last_trade_time < self.min_interval:
                return False
        
        self.last_trade_time = datetime.now()
        return signal.confidence > 0.7
    
    async def _calculate_position_size(self, signal) -> float:
        """Scalp: Fixed small size."""
        return self.config.max_position_size


class BotFactory:
    """Factory for creating trading bots."""
    
    BOT_TYPES = {
        'tpt': TPTBot,
        'momentum': MomentumBot,
        'swing': SwingBot,
        'mean_reversion': MeanReversionBot,
        'scalp': ScalpBot,
    }
    
    @classmethod
    def create(cls, bot_type: str, brain_interface, broker, **kwargs) -> TradingBot:
        """Create a bot by type."""
        if bot_type not in cls.BOT_TYPES:
            raise ValueError(f"Unknown bot type: {bot_type}. Available: {list(cls.BOT_TYPES.keys())}")
        
        return cls.BOT_TYPES[bot_type](brain_interface, broker, **kwargs)
    
    @classmethod
    def create_all(cls, brain_interface, broker, **kwargs) -> Dict[str, TradingBot]:
        """Create all bot types."""
        return {
            name: cls.create(name, brain_interface, broker, **kwargs)
            for name in cls.BOT_TYPES
        }
