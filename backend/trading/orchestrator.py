"""
QUANT INDUSTRY - Live Trading Orchestrator
==========================================
Central orchestrator for live trading operations:
- Strategy lifecycle management
- Signal aggregation and routing
- Order management
- Position synchronization
- Risk monitoring
- Performance tracking
- Graceful shutdown

This is the mission control for your trading operation.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import asyncio
import logging
import signal
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class TradingState(Enum):
    """Orchestrator state"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class SignalType(Enum):
    """Types of trading signals"""
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT = "exit"
    SCALE_IN = "scale_in"
    SCALE_OUT = "scale_out"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    REBALANCE = "rebalance"


@dataclass
class TradingSignal:
    """Signal from a strategy"""
    timestamp: datetime
    strategy_id: str
    symbol: str
    signal_type: SignalType
    direction: int          # 1 = long, -1 = short, 0 = flat
    confidence: float       # 0 to 1
    target_quantity: int = 0
    price_limit: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    @property
    def id(self) -> str:
        return f"{self.strategy_id}_{self.symbol}_{self.timestamp.timestamp()}"


@dataclass
class Position:
    """Current position"""
    symbol: str
    quantity: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    strategy_id: str = ""
    
    @property
    def side(self) -> str:
        if self.quantity > 0:
            return "LONG"
        elif self.quantity < 0:
            return "SHORT"
        return "FLAT"


@dataclass
class StrategyConfig:
    """Configuration for a strategy"""
    strategy_id: str
    name: str
    symbols: List[str]
    
    # Allocation
    max_capital_pct: float = 10.0    # Max % of portfolio
    max_positions: int = 5
    
    # Risk
    max_loss_pct: float = 2.0        # Daily loss limit
    position_size_pct: float = 5.0   # Per-position size
    
    # Timing
    check_interval_seconds: float = 60.0
    market_hours_only: bool = True
    
    # State
    enabled: bool = True
    paper_only: bool = True


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator"""
    # Capital
    initial_capital: float = 100_000.0
    
    # Risk limits
    max_daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 15.0
    max_total_positions: int = 20
    
    # Timing
    main_loop_interval: float = 1.0  # Seconds
    signal_timeout_seconds: float = 60.0
    
    # Market hours (EST)
    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    
    # Features
    enable_paper_trading: bool = True
    enable_live_trading: bool = False
    
    # Logging
    log_signals: bool = True
    log_orders: bool = True


class Strategy:
    """Base strategy interface"""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.last_signal_time: Dict[str, datetime] = {}
    
    @property
    def strategy_id(self) -> str:
        return self.config.strategy_id
    
    def generate_signals(
        self,
        market_data: Dict[str, Any]
    ) -> List[TradingSignal]:
        """Generate trading signals - override in subclass"""
        return []
    
    def on_fill(self, symbol: str, fill_price: float, quantity: int):
        """Called when an order is filled"""
        pass
    
    def on_market_open(self):
        """Called at market open"""
        pass
    
    def on_market_close(self):
        """Called at market close"""
        pass


class TradingOrchestrator:
    """
    Central orchestrator for live trading.
    
    Coordinates strategies, aggregates signals, manages risk,
    and routes orders to execution.
    
    Usage:
    ------
    >>> orchestrator = TradingOrchestrator()
    >>>
    >>> # Register strategies
    >>> orchestrator.register_strategy(my_momentum_strategy)
    >>> orchestrator.register_strategy(my_mean_reversion_strategy)
    >>>
    >>> # Start trading
    >>> orchestrator.start()
    >>>
    >>> # Check status
    >>> print(orchestrator.get_status())
    >>>
    >>> # Graceful shutdown
    >>> orchestrator.stop()
    """
    
    def __init__(
        self,
        config: OrchestratorConfig = None,
        data_provider: Any = None,
        order_executor: Any = None
    ):
        """
        Initialize orchestrator.
        
        Args:
            config: Orchestrator configuration
            data_provider: Data source for market data
            order_executor: Order execution engine
        """
        self.config = config or OrchestratorConfig()
        self.data_provider = data_provider
        self.order_executor = order_executor
        
        # State
        self.state = TradingState.STOPPED
        self.start_time: Optional[datetime] = None
        
        # Strategies
        self.strategies: Dict[str, Strategy] = {}
        
        # Positions and P&L
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.high_water_mark = self.config.initial_capital
        self.current_capital = self.config.initial_capital
        
        # Signal queue
        self.pending_signals: deque = deque(maxlen=1000)
        self.processed_signals: deque = deque(maxlen=10000)
        
        # Threading
        self._main_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Callbacks
        self._on_signal_callbacks: List[Callable] = []
        self._on_fill_callbacks: List[Callable] = []
        self._on_error_callbacks: List[Callable] = []
        
        # Performance tracking
        self.metrics = {
            "signals_generated": 0,
            "signals_executed": 0,
            "signals_rejected": 0,
            "orders_filled": 0,
            "orders_failed": 0,
        }
        
        logger.info("TradingOrchestrator initialized")
    
    def register_strategy(self, strategy: Strategy):
        """
        Register a strategy with the orchestrator.
        
        Args:
            strategy: Strategy instance to register
        """
        self.strategies[strategy.strategy_id] = strategy
        logger.info(f"Registered strategy: {strategy.strategy_id}")
    
    def unregister_strategy(self, strategy_id: str):
        """Remove a strategy"""
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            logger.info(f"Unregistered strategy: {strategy_id}")
    
    def start(self, blocking: bool = False):
        """
        Start the orchestrator.
        
        Args:
            blocking: If True, blocks until stopped
        """
        if self.state != TradingState.STOPPED:
            logger.warning(f"Cannot start from state: {self.state}")
            return
        
        self.state = TradingState.STARTING
        self._stop_event.clear()
        self.start_time = datetime.now()
        
        # Reset daily metrics
        self._reset_daily_metrics()
        
        # Start main loop
        self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._main_thread.start()
        
        self.state = TradingState.RUNNING
        logger.info("Orchestrator started")
        
        if blocking:
            try:
                while not self._stop_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
    
    def stop(self, timeout: float = 30.0):
        """
        Stop the orchestrator gracefully.
        
        Args:
            timeout: Max seconds to wait for shutdown
        """
        if self.state not in [TradingState.RUNNING, TradingState.PAUSED]:
            return
        
        logger.info("Stopping orchestrator...")
        self.state = TradingState.STOPPING
        self._stop_event.set()
        
        if self._main_thread:
            self._main_thread.join(timeout=timeout)
        
        self.state = TradingState.STOPPED
        logger.info("Orchestrator stopped")
    
    def pause(self):
        """Pause trading (keeps data flowing, stops new orders)"""
        if self.state == TradingState.RUNNING:
            self.state = TradingState.PAUSED
            logger.info("Orchestrator paused")
    
    def resume(self):
        """Resume trading after pause"""
        if self.state == TradingState.PAUSED:
            self.state = TradingState.RUNNING
            logger.info("Orchestrator resumed")
    
    def _main_loop(self):
        """Main trading loop"""
        logger.info("Main loop started")
        
        while not self._stop_event.is_set():
            try:
                loop_start = time.time()
                
                # Skip if paused
                if self.state == TradingState.PAUSED:
                    time.sleep(self.config.main_loop_interval)
                    continue
                
                # Check market hours
                if not self._is_market_open():
                    time.sleep(self.config.main_loop_interval)
                    continue
                
                # Check risk limits
                if self._check_risk_limits():
                    logger.warning("Risk limits breached, pausing trading")
                    self.pause()
                    continue
                
                # Get market data
                market_data = self._get_market_data()
                
                # Generate signals from all strategies
                for strategy_id, strategy in self.strategies.items():
                    if not strategy.config.enabled:
                        continue
                    
                    try:
                        signals = strategy.generate_signals(market_data)
                        for signal in signals:
                            self._process_signal(signal)
                    except Exception as e:
                        logger.error(f"Strategy {strategy_id} error: {e}")
                        self._handle_error(strategy_id, e)
                
                # Process pending signals
                self._execute_pending_signals()
                
                # Update positions and P&L
                self._update_positions(market_data)
                
                # Sleep for remainder of interval
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.config.main_loop_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                self._handle_error("orchestrator", e)
        
        logger.info("Main loop exited")
    
    def _process_signal(self, signal: TradingSignal):
        """Process a trading signal"""
        self.metrics["signals_generated"] += 1
        
        if self.config.log_signals:
            logger.info(f"Signal: {signal.strategy_id} {signal.signal_type.value} {signal.symbol}")
        
        # Validate signal
        if not self._validate_signal(signal):
            self.metrics["signals_rejected"] += 1
            return
        
        # Check strategy limits
        strategy = self.strategies.get(signal.strategy_id)
        if strategy and not self._check_strategy_limits(strategy, signal):
            self.metrics["signals_rejected"] += 1
            return
        
        # Add to pending queue
        self.pending_signals.append(signal)
        
        # Fire callbacks
        for callback in self._on_signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Signal callback error: {e}")
    
    def _validate_signal(self, signal: TradingSignal) -> bool:
        """Validate a signal"""
        # Check timeout
        age = (datetime.now() - signal.timestamp).total_seconds()
        if age > self.config.signal_timeout_seconds:
            logger.debug(f"Signal expired: {signal.id}")
            return False
        
        # Check confidence
        if signal.confidence < 0.5:
            logger.debug(f"Low confidence signal: {signal.confidence}")
            return False
        
        return True
    
    def _check_strategy_limits(
        self,
        strategy: Strategy,
        signal: TradingSignal
    ) -> bool:
        """Check if signal respects strategy limits"""
        config = strategy.config
        
        # Count positions for this strategy
        strategy_positions = [
            p for p in self.positions.values()
            if p.strategy_id == strategy.strategy_id
        ]
        
        if len(strategy_positions) >= config.max_positions:
            if signal.signal_type in [SignalType.ENTRY_LONG, SignalType.ENTRY_SHORT]:
                logger.debug(f"Strategy {strategy.strategy_id} at max positions")
                return False
        
        return True
    
    def _check_risk_limits(self) -> bool:
        """Check if risk limits are breached"""
        # Daily loss limit
        daily_loss_pct = -self.daily_pnl / self.config.initial_capital * 100
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            logger.warning(f"Daily loss limit hit: {daily_loss_pct:.1f}%")
            return True
        
        # Drawdown limit
        drawdown_pct = (self.high_water_mark - self.current_capital) / self.high_water_mark * 100
        if drawdown_pct >= self.config.max_drawdown_pct:
            logger.warning(f"Max drawdown hit: {drawdown_pct:.1f}%")
            return True
        
        return False
    
    def _execute_pending_signals(self):
        """Execute pending signals"""
        while self.pending_signals:
            signal = self.pending_signals.popleft()
            
            try:
                # Convert signal to order
                if signal.signal_type in [SignalType.ENTRY_LONG, SignalType.ENTRY_SHORT]:
                    self._execute_entry(signal)
                elif signal.signal_type in [SignalType.EXIT, SignalType.STOP_LOSS, SignalType.TAKE_PROFIT]:
                    self._execute_exit(signal)
                elif signal.signal_type in [SignalType.SCALE_IN, SignalType.SCALE_OUT]:
                    self._execute_scale(signal)
                
                self.metrics["signals_executed"] += 1
                self.processed_signals.append(signal)
                
            except Exception as e:
                logger.error(f"Signal execution error: {e}")
                self.metrics["signals_rejected"] += 1
    
    def _execute_entry(self, signal: TradingSignal):
        """Execute an entry signal"""
        # Calculate position size
        position_value = self.current_capital * 0.05  # 5% per position
        price = signal.price_limit if signal.price_limit > 0 else self._get_current_price(signal.symbol)
        quantity = int(position_value / price) if price > 0 else 0
        
        if quantity == 0:
            return
        
        if signal.signal_type == SignalType.ENTRY_SHORT:
            quantity = -quantity
        
        # Execute (paper or live)
        fill_price = self._submit_order(signal.symbol, quantity, price)
        
        if fill_price:
            # Create/update position
            self.positions[signal.symbol] = Position(
                symbol=signal.symbol,
                quantity=quantity,
                avg_cost=fill_price,
                market_value=quantity * fill_price,
                unrealized_pnl=0,
                realized_pnl=0,
                strategy_id=signal.strategy_id
            )
            
            self.metrics["orders_filled"] += 1
            
            # Notify strategy
            strategy = self.strategies.get(signal.strategy_id)
            if strategy:
                strategy.on_fill(signal.symbol, fill_price, quantity)
    
    def _execute_exit(self, signal: TradingSignal):
        """Execute an exit signal"""
        if signal.symbol not in self.positions:
            return
        
        position = self.positions[signal.symbol]
        quantity = -position.quantity  # Close full position
        
        price = signal.price_limit if signal.price_limit > 0 else self._get_current_price(signal.symbol)
        fill_price = self._submit_order(signal.symbol, quantity, price)
        
        if fill_price:
            # Calculate P&L
            if position.quantity > 0:
                pnl = (fill_price - position.avg_cost) * abs(position.quantity)
            else:
                pnl = (position.avg_cost - fill_price) * abs(position.quantity)
            
            self.daily_pnl += pnl
            self.total_pnl += pnl
            
            # Remove position
            del self.positions[signal.symbol]
            
            self.metrics["orders_filled"] += 1
    
    def _execute_scale(self, signal: TradingSignal):
        """Execute a scale in/out signal"""
        # Simplified: treat as entry/exit
        if signal.signal_type == SignalType.SCALE_IN:
            self._execute_entry(signal)
        else:
            self._execute_exit(signal)
    
    def _submit_order(
        self,
        symbol: str,
        quantity: int,
        price: float
    ) -> Optional[float]:
        """
        Submit order to executor.
        
        Returns fill price or None if failed.
        """
        if self.config.log_orders:
            side = "BUY" if quantity > 0 else "SELL"
            logger.info(f"Order: {side} {abs(quantity)} {symbol} @ {price:.2f}")
        
        # Paper trading (simulate immediate fill with slippage)
        if self.config.enable_paper_trading and not self.config.enable_live_trading:
            slippage = 0.0005  # 5 bps
            if quantity > 0:
                fill_price = price * (1 + slippage)
            else:
                fill_price = price * (1 - slippage)
            return fill_price
        
        # Live trading
        if self.config.enable_live_trading and self.order_executor:
            try:
                result = self.order_executor.submit_order(
                    symbol=symbol,
                    quantity=quantity,
                    price=price
                )
                return result.get("fill_price")
            except Exception as e:
                logger.error(f"Order submission failed: {e}")
                self.metrics["orders_failed"] += 1
                return None
        
        return None
    
    def _get_market_data(self) -> Dict[str, Any]:
        """Get current market data for all symbols"""
        if self.data_provider is None:
            return {}
        
        symbols = set()
        for strategy in self.strategies.values():
            symbols.update(strategy.config.symbols)
        
        data = {}
        for symbol in symbols:
            try:
                data[symbol] = self.data_provider.get_quote(symbol)
            except Exception as e:
                logger.debug(f"Failed to get data for {symbol}: {e}")
        
        return data
    
    def _get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        if self.data_provider:
            try:
                quote = self.data_provider.get_quote(symbol)
                if quote:
                    return quote.last
            except:
                pass
        
        # Fallback to position avg cost
        if symbol in self.positions:
            return self.positions[symbol].avg_cost
        
        return 0.0
    
    def _update_positions(self, market_data: Dict[str, Any]):
        """Update position values and P&L"""
        total_value = self.config.initial_capital - sum(
            abs(p.quantity) * p.avg_cost for p in self.positions.values()
        )
        
        for symbol, position in self.positions.items():
            if symbol in market_data and market_data[symbol]:
                current_price = market_data[symbol].last
                position.market_value = position.quantity * current_price
                
                if position.quantity > 0:
                    position.unrealized_pnl = (current_price - position.avg_cost) * position.quantity
                else:
                    position.unrealized_pnl = (position.avg_cost - current_price) * abs(position.quantity)
                
                total_value += position.market_value
        
        self.current_capital = total_value
        self.high_water_mark = max(self.high_water_mark, self.current_capital)
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now()
        
        # Weekend check
        if now.weekday() >= 5:
            return False
        
        # Hour check (simplified, doesn't handle holidays)
        market_open = now.replace(
            hour=self.config.market_open_hour,
            minute=self.config.market_open_minute,
            second=0
        )
        market_close = now.replace(
            hour=self.config.market_close_hour,
            minute=self.config.market_close_minute,
            second=0
        )
        
        return market_open <= now <= market_close
    
    def _reset_daily_metrics(self):
        """Reset daily tracking metrics"""
        self.daily_pnl = 0.0
    
    def _handle_error(self, source: str, error: Exception):
        """Handle errors"""
        for callback in self._on_error_callbacks:
            try:
                callback(source, error)
            except:
                pass
    
    def on_signal(self, callback: Callable[[TradingSignal], None]):
        """Register signal callback"""
        self._on_signal_callbacks.append(callback)
    
    def on_fill(self, callback: Callable):
        """Register fill callback"""
        self._on_fill_callbacks.append(callback)
    
    def on_error(self, callback: Callable[[str, Exception], None]):
        """Register error callback"""
        self._on_error_callbacks.append(callback)
    
    def get_status(self) -> Dict:
        """Get current orchestrator status"""
        return {
            "state": self.state.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            "strategies": len(self.strategies),
            "positions": len(self.positions),
            "capital": {
                "initial": self.config.initial_capital,
                "current": self.current_capital,
                "daily_pnl": self.daily_pnl,
                "total_pnl": self.total_pnl,
            },
            "metrics": self.metrics,
        }
    
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        return [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "side": p.side,
                "avg_cost": p.avg_cost,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "strategy": p.strategy_id,
            }
            for p in self.positions.values()
        ]


# ============== FACTORY ==============

def create_orchestrator(
    initial_capital: float = 100_000,
    paper_trading: bool = True
) -> TradingOrchestrator:
    """Create a new orchestrator with default settings"""
    config = OrchestratorConfig(
        initial_capital=initial_capital,
        enable_paper_trading=paper_trading,
        enable_live_trading=not paper_trading
    )
    
    return TradingOrchestrator(config)
