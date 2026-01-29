"""
Trading Bot Base Classes
========================
Base classes for trading bots that receive signals from ML Brain
and execute trades according to their specific strategies.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class BotStatus(Enum):
    """Bot operational status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class TradeStatus(Enum):
    """Status of a trade."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class Trade:
    """Represents a single trade."""
    trade_id: str
    signal_id: str
    symbol: str
    
    # Entry
    direction: int  # 1 = long, -1 = short
    entry_price: float
    entry_time: datetime
    quantity: float
    
    # Exit (filled when closed)
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    
    # Risk levels
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # P&L
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    # Status
    status: TradeStatus = TradeStatus.PENDING
    
    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN
    
    @property
    def holding_period(self) -> float:
        """Holding period in hours."""
        if self.exit_time:
            return (self.exit_time - self.entry_time).total_seconds() / 3600
        return (datetime.now() - self.entry_time).total_seconds() / 3600
    
    def calculate_pnl(self, current_price: float) -> float:
        """Calculate current P&L."""
        price_change = current_price - self.entry_price
        self.pnl = price_change * self.quantity * self.direction
        self.pnl_pct = (price_change / self.entry_price) * self.direction
        return self.pnl


@dataclass
class BotConfig:
    """Configuration for a trading bot."""
    bot_id: str
    name: str
    
    # Trading parameters
    max_positions: int = 5
    max_position_size: float = 0.1  # Fraction of portfolio
    min_signal_confidence: float = 0.5
    
    # Risk management
    default_stop_loss_pct: float = 0.02
    default_take_profit_pct: float = 0.03
    max_holding_hours: float = 24
    
    # Execution
    use_limit_orders: bool = True
    limit_offset_bps: float = 5.0
    
    # Filtering
    valid_regimes: List[str] = field(default_factory=lambda: ["trending_up", "trending_down", "ranging"])
    valid_signal_types: List[str] = field(default_factory=lambda: ["composite", "directional"])


class TradingBot(ABC):
    """
    Base class for all trading bots.
    
    Receives signals from ML Brain, applies its own logic,
    executes trades, and reports back performance.
    """
    
    def __init__(
        self,
        config: BotConfig,
        brain_interface,  # BrainBotInterface
        broker  # Broker instance for execution
    ):
        self.config = config
        self.brain = brain_interface
        self.broker = broker
        
        # State
        self.status = BotStatus.STOPPED
        self.open_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.portfolio_value = 100000.0
        
        # Tracking
        self._trade_counter = 0
        self._running = False
        
        logger.info(f"Bot initialized: {config.bot_id} ({config.name})")
    
    async def start(self):
        """Start the bot."""
        self.status = BotStatus.STARTING
        self._running = True
        
        # Initialize
        await self._on_start()
        
        self.status = BotStatus.RUNNING
        logger.info(f"Bot started: {self.config.bot_id}")
        
        # Main loop
        while self._running:
            try:
                await self._tick()
                await asyncio.sleep(1.0)  # Tick interval
            except Exception as e:
                logger.error(f"Bot error: {e}")
                self.status = BotStatus.ERROR
                await asyncio.sleep(5.0)
                self.status = BotStatus.RUNNING
    
    async def stop(self):
        """Stop the bot."""
        self._running = False
        
        # Close all positions
        for trade_id in list(self.open_trades.keys()):
            await self._close_trade(trade_id, "bot_shutdown")
        
        await self._on_stop()
        
        self.status = BotStatus.STOPPED
        logger.info(f"Bot stopped: {self.config.bot_id}")
    
    async def _tick(self):
        """Main tick - process signals and manage trades."""
        # 1. Check for new signals from brain
        signals = self.brain.get_pending_signals()
        
        for signal in signals:
            if self._should_trade(signal):
                await self._process_signal(signal)
        
        # 2. Monitor open trades
        await self._monitor_trades()
    
    def _should_trade(self, signal) -> bool:
        """Determine if we should act on this signal."""
        # Check confidence threshold
        if signal.confidence < self.config.min_signal_confidence:
            return False
        
        # Check regime
        if signal.regime not in self.config.valid_regimes:
            return False
        
        # Check signal type
        if signal.signal_type.value not in self.config.valid_signal_types:
            return False
        
        # Check position limits
        if len(self.open_trades) >= self.config.max_positions:
            return False
        
        # Check if we already have position in this symbol
        for trade in self.open_trades.values():
            if trade.symbol == signal.symbol:
                return False
        
        # Apply bot-specific filtering
        return self._custom_filter(signal)
    
    @abstractmethod
    def _custom_filter(self, signal) -> bool:
        """Bot-specific signal filtering. Override in subclass."""
        pass
    
    @abstractmethod
    async def _calculate_position_size(self, signal) -> float:
        """Calculate position size for this signal. Override in subclass."""
        pass
    
    async def _process_signal(self, signal):
        """Process a trading signal and potentially open a trade."""
        if signal.direction == 0:
            return
        
        # Calculate position size
        size = await self._calculate_position_size(signal)
        
        if size <= 0:
            return
        
        # Create trade
        self._trade_counter += 1
        trade = Trade(
            trade_id=f"{self.config.bot_id}_T{self._trade_counter:06d}",
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=signal.entry_price,
            entry_time=datetime.now(),
            quantity=size,
            stop_loss=signal.stop_loss or signal.entry_price * (1 - self.config.default_stop_loss_pct * signal.direction),
            take_profit=signal.take_profit or signal.entry_price * (1 + self.config.default_take_profit_pct * signal.direction),
            status=TradeStatus.PENDING
        )
        
        # Execute via broker
        try:
            result = await self._execute_entry(trade)
            
            if result['success']:
                trade.entry_price = result['fill_price']
                trade.status = TradeStatus.OPEN
                self.open_trades[trade.trade_id] = trade
                
                # Report to brain
                self.brain.report_execution(
                    signal_id=signal.signal_id,
                    executed=True,
                    execution_price=result['fill_price'],
                    slippage=abs(result['fill_price'] - signal.entry_price) / signal.entry_price
                )
                
                logger.info(f"Trade opened: {trade.trade_id} | {trade.symbol} | {'LONG' if trade.direction > 0 else 'SHORT'} | {trade.quantity:.4f}")
            else:
                self.brain.report_execution(signal_id=signal.signal_id, executed=False)
                
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            self.brain.report_execution(signal_id=signal.signal_id, executed=False)
    
    async def _execute_entry(self, trade: Trade) -> Dict[str, Any]:
        """Execute trade entry via broker."""
        side = "buy" if trade.direction > 0 else "sell"
        
        result = await self.broker.submit_order(
            symbol=trade.symbol,
            side=side,
            quantity=trade.quantity,
            order_type="limit" if self.config.use_limit_orders else "market",
            limit_price=trade.entry_price * (1 + self.config.limit_offset_bps / 10000 * trade.direction)
        )
        
        return {
            'success': True,
            'fill_price': result.get('filled_price', trade.entry_price),
        }
    
    async def _monitor_trades(self):
        """Monitor and manage open trades."""
        for trade_id, trade in list(self.open_trades.items()):
            current_price = await self._get_current_price(trade.symbol)
            
            trade.calculate_pnl(current_price)
            
            # Check stop loss
            if trade.stop_loss:
                if (trade.direction > 0 and current_price <= trade.stop_loss) or \
                   (trade.direction < 0 and current_price >= trade.stop_loss):
                    await self._close_trade(trade_id, "stop_loss")
                    continue
            
            # Check take profit
            if trade.take_profit:
                if (trade.direction > 0 and current_price >= trade.take_profit) or \
                   (trade.direction < 0 and current_price <= trade.take_profit):
                    await self._close_trade(trade_id, "take_profit")
                    continue
            
            # Check max holding time
            if trade.holding_period > self.config.max_holding_hours:
                await self._close_trade(trade_id, "timeout")
                continue
            
            # Bot-specific monitoring
            await self._custom_monitor(trade, current_price)
    
    async def _close_trade(self, trade_id: str, reason: str):
        """Close an open trade."""
        if trade_id not in self.open_trades:
            return
        
        trade = self.open_trades[trade_id]
        current_price = await self._get_current_price(trade.symbol)
        
        # Execute exit
        side = "sell" if trade.direction > 0 else "buy"
        
        try:
            result = await self.broker.submit_order(
                symbol=trade.symbol,
                side=side,
                quantity=trade.quantity,
                order_type="market"
            )
            
            trade.exit_price = result.get('filled_price', current_price)
            trade.exit_time = datetime.now()
            trade.exit_reason = reason
            trade.calculate_pnl(trade.exit_price)
            trade.status = TradeStatus.CLOSED
            
            # Move to closed trades
            del self.open_trades[trade_id]
            self.closed_trades.append(trade)
            
            # Report to brain
            self.brain.report_outcome(
                signal_id=trade.signal_id,
                pnl=trade.pnl,
                pnl_pct=trade.pnl_pct,
                holding_period=trade.holding_period,
                signal_was_correct=trade.pnl > 0,
                exit_reason=reason
            )
            
            logger.info(
                f"Trade closed: {trade_id} | {reason} | "
                f"PnL: {trade.pnl_pct:.2%}"
            )
            
        except Exception as e:
            logger.error(f"Failed to close trade {trade_id}: {e}")
    
    async def _get_current_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        # Would call broker or data feed
        return await self.broker.get_price(symbol)
    
    async def _custom_monitor(self, trade: Trade, current_price: float):
        """Bot-specific trade monitoring. Override in subclass."""
        pass
    
    async def _on_start(self):
        """Called when bot starts. Override in subclass."""
        pass
    
    async def _on_stop(self):
        """Called when bot stops. Override in subclass."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get bot status summary."""
        open_pnl = sum(t.pnl_pct for t in self.open_trades.values())
        closed_pnl = sum(t.pnl_pct for t in self.closed_trades)
        
        return {
            'bot_id': self.config.bot_id,
            'status': self.status.value,
            'open_trades': len(self.open_trades),
            'closed_trades': len(self.closed_trades),
            'open_pnl_pct': open_pnl,
            'closed_pnl_pct': closed_pnl,
            'total_pnl_pct': open_pnl + closed_pnl,
            'win_rate': self._calculate_win_rate(),
        }
    
    def _calculate_win_rate(self) -> float:
        """Calculate win rate from closed trades."""
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t.pnl > 0)
        return wins / len(self.closed_trades)
