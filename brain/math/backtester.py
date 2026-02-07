"""
Backtesting Engine
==================
Runs TradingBrain through historical data with full PnL tracking.

Features:
- Event-driven simulation
- Realistic fills with slippage/impact
- Full integration with Phase 1-3 components
- Performance analytics (Sharpe, Sortino, Max DD, etc.)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Order representation."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: str = "MARKET"  # MARKET, LIMIT
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    # Execution details
    slippage: float = 0.0
    commission: float = 0.0


@dataclass
class Position:
    """Position tracking."""
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Risk tracking
    entry_time: Optional[datetime] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.avg_price
    
    @property
    def is_long(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        return self.quantity < 0


@dataclass
class Trade:
    """Completed trade record."""
    trade_id: str
    symbol: str
    side: OrderSide
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    holding_period: timedelta
    
    # Attribution
    strategy_signal: Optional[str] = None
    regime_at_entry: Optional[str] = None


@dataclass
class BacktestConfig:
    """Backtesting configuration."""
    initial_capital: float = 100000.0
    commission_per_share: float = 0.005  # $0.005/share
    slippage_pct: float = 0.001  # 0.1% slippage
    
    # Risk limits
    max_position_pct: float = 0.10  # 10% max per position
    max_drawdown_halt: float = 0.20  # Stop at 20% DD
    
    # Execution
    use_market_impact: bool = True
    impact_model: str = "sqrt"  # sqrt, linear, kyle
    
    # Data
    lookback_required: int = 60  # Bars needed before trading


@dataclass
class BacktestResult:
    """Backtesting results."""
    # Returns
    total_return: float
    annual_return: float
    
    # Risk metrics
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    
    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    
    # Time series
    equity_curve: np.ndarray
    drawdown_curve: np.ndarray
    returns: np.ndarray
    
    # Trade log
    trades: List[Trade]
    
    def to_dict(self) -> Dict:
        return {
            "total_return": f"{self.total_return:.2%}",
            "annual_return": f"{self.annual_return:.2%}",
            "volatility": f"{self.volatility:.2%}",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "sortino_ratio": f"{self.sortino_ratio:.2f}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "max_dd_duration_days": self.max_drawdown_duration,
            "total_trades": self.total_trades,
            "win_rate": f"{self.win_rate:.1%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "avg_win": f"{self.avg_win:.2%}",
            "avg_loss": f"{self.avg_loss:.2%}",
        }


class Portfolio:
    """Portfolio state manager."""
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.trades: List[Trade] = []
        
        # Tracking
        self.equity_history: List[float] = [initial_capital]
        self.timestamp_history: List[datetime] = []
        self._trade_counter = 0
        self._order_counter = 0
    
    @property
    def equity(self) -> float:
        """Total portfolio value."""
        positions_value = sum(
            pos.quantity * pos.avg_price 
            for pos in self.positions.values()
        )
        return self.cash + positions_value
    
    @property
    def total_pnl(self) -> float:
        return self.equity - self.initial_capital
    
    @property
    def total_return(self) -> float:
        return self.total_pnl / self.initial_capital
    
    def update_position_prices(self, prices: Dict[str, float]):
        """Update unrealized PnL with current prices."""
        for symbol, pos in self.positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                if pos.quantity != 0:
                    pos.unrealized_pnl = (current_price - pos.avg_price) * pos.quantity
    
    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: float = None,
        stop_loss: float = None,
        take_profit: float = None
    ) -> Order:
        """Submit a new order."""
        self._order_counter += 1
        order = Order(
            order_id=f"ORD-{self._order_counter:06d}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_loss
        )
        self.orders.append(order)
        return order
    
    def fill_order(
        self,
        order: Order,
        fill_price: float,
        fill_time: datetime,
        slippage: float = 0.0,
        commission: float = 0.0
    ):
        """Execute order fill."""
        order.status = OrderStatus.FILLED
        order.filled_price = fill_price
        order.filled_at = fill_time
        order.slippage = slippage
        order.commission = commission
        
        # Update position
        symbol = order.symbol
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        
        pos = self.positions[symbol]
        
        # Calculate trade value
        trade_value = order.quantity * fill_price + commission
        
        if order.side == OrderSide.BUY:
            # Buying
            if pos.quantity >= 0:
                # Adding to long or new long
                total_cost = pos.quantity * pos.avg_price + trade_value
                pos.quantity += order.quantity
                pos.avg_price = total_cost / pos.quantity if pos.quantity > 0 else 0
                pos.entry_time = fill_time
            else:
                # Covering short
                pnl = (pos.avg_price - fill_price) * min(order.quantity, abs(pos.quantity))
                pos.realized_pnl += pnl - commission
                pos.quantity += order.quantity
                if pos.quantity > 0:
                    pos.avg_price = fill_price
                    pos.entry_time = fill_time
            self.cash -= trade_value
            
        else:  # SELL
            if pos.quantity <= 0:
                # Adding to short or new short
                total_value = abs(pos.quantity) * pos.avg_price + trade_value
                pos.quantity -= order.quantity
                pos.avg_price = total_value / abs(pos.quantity) if pos.quantity != 0 else 0
                pos.entry_time = fill_time
            else:
                # Closing long
                pnl = (fill_price - pos.avg_price) * min(order.quantity, pos.quantity)
                pos.realized_pnl += pnl - commission
                
                # Record trade
                self._trade_counter += 1
                trade = Trade(
                    trade_id=f"TRD-{self._trade_counter:06d}",
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=min(order.quantity, pos.quantity),
                    entry_price=pos.avg_price,
                    exit_price=fill_price,
                    entry_time=pos.entry_time or fill_time,
                    exit_time=fill_time,
                    pnl=pnl - commission,
                    pnl_pct=(fill_price - pos.avg_price) / pos.avg_price,
                    holding_period=fill_time - (pos.entry_time or fill_time)
                )
                self.trades.append(trade)
                
                pos.quantity -= order.quantity
                if pos.quantity < 0:
                    pos.avg_price = fill_price
                    pos.entry_time = fill_time
            
            self.cash += trade_value - 2 * commission  # Net of buy-side commission
        
        # Clean up zero positions
        if abs(pos.quantity) < 0.0001:
            del self.positions[symbol]
    
    def record_equity(self, timestamp: datetime):
        """Record equity for time series."""
        self.equity_history.append(self.equity)
        self.timestamp_history.append(timestamp)


class BacktestEngine:
    """
    Event-driven backtesting engine.
    
    Runs TradingBrain through historical data bar-by-bar.
    """
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.portfolio = Portfolio(self.config.initial_capital)
        
        # State
        self.current_bar = 0
        self.current_time: Optional[datetime] = None
        self.is_halted = False
        self.halt_reason: Optional[str] = None
        
        # Data
        self.data: Dict[str, List[Dict]] = {}  # symbol -> OHLCV bars
        self.current_prices: Dict[str, float] = {}
        
        # Brain reference (set in run())
        self.brain = None
    
    def load_data(self, symbol: str, ohlcv: List[Dict]):
        """Load historical data for a symbol."""
        self.data[symbol] = ohlcv
        logger.info(f"Loaded {len(ohlcv)} bars for {symbol}")
    
    def _get_market_data_for_brain(
        self,
        symbol: str,
        bar_idx: int
    ) -> Dict:
        """Prepare market data dict for TradingBrain.think()."""
        ohlcv = self.data[symbol][:bar_idx + 1]
        
        # Calculate average volume
        volumes = [bar.get('volume', 1000000) for bar in ohlcv[-20:]]
        avg_volume = np.mean(volumes) if volumes else 1000000
        
        return {
            'ohlcv': ohlcv,
            'quote': {
                'price': ohlcv[-1].get('close', 0),
                'bid': ohlcv[-1].get('close', 0) * 0.999,
                'ask': ohlcv[-1].get('close', 0) * 1.001,
            },
            'avg_volume': avg_volume
        }
    
    def _calculate_fill_price(
        self,
        order: Order,
        bar: Dict,
        avg_volume: float
    ) -> float:
        """Calculate realistic fill price with slippage/impact."""
        base_price = bar.get('close', 0)
        
        # Base slippage
        slippage = base_price * self.config.slippage_pct
        if order.side == OrderSide.BUY:
            fill_price = base_price + slippage
        else:
            fill_price = base_price - slippage
        
        # Market impact (if enabled)
        if self.config.use_market_impact and avg_volume > 0:
            participation = order.quantity / avg_volume
            
            if self.config.impact_model == "sqrt":
                impact = 0.5 * np.sqrt(participation) * base_price
            elif self.config.impact_model == "linear":
                impact = 0.1 * participation * base_price
            else:
                impact = 0
            
            if order.side == OrderSide.BUY:
                fill_price += impact
            else:
                fill_price -= impact
        
        return fill_price
    
    def _check_stops(self, bar: Dict, symbol: str):
        """Check and execute stop orders."""
        if symbol not in self.portfolio.positions:
            return
        
        pos = self.portfolio.positions[symbol]
        high = bar.get('high', bar.get('close', 0))
        low = bar.get('low', bar.get('close', 0))
        
        # Stop loss
        if pos.stop_loss:
            if pos.is_long and low <= pos.stop_loss:
                # Long stop hit
                order = self.portfolio.submit_order(
                    symbol, OrderSide.SELL, abs(pos.quantity)
                )
                self.portfolio.fill_order(
                    order, pos.stop_loss, self.current_time,
                    commission=abs(pos.quantity) * self.config.commission_per_share
                )
                logger.info(f"Stop loss hit for {symbol} at {pos.stop_loss}")
            
            elif pos.is_short and high >= pos.stop_loss:
                # Short stop hit
                order = self.portfolio.submit_order(
                    symbol, OrderSide.BUY, abs(pos.quantity)
                )
                self.portfolio.fill_order(
                    order, pos.stop_loss, self.current_time,
                    commission=abs(pos.quantity) * self.config.commission_per_share
                )
                logger.info(f"Stop loss hit for {symbol} at {pos.stop_loss}")
        
        # Take profit
        if pos.take_profit:
            if pos.is_long and high >= pos.take_profit:
                order = self.portfolio.submit_order(
                    symbol, OrderSide.SELL, abs(pos.quantity)
                )
                self.portfolio.fill_order(
                    order, pos.take_profit, self.current_time,
                    commission=abs(pos.quantity) * self.config.commission_per_share
                )
                logger.info(f"Take profit hit for {symbol} at {pos.take_profit}")
            
            elif pos.is_short and low <= pos.take_profit:
                order = self.portfolio.submit_order(
                    symbol, OrderSide.BUY, abs(pos.quantity)
                )
                self.portfolio.fill_order(
                    order, pos.take_profit, self.current_time,
                    commission=abs(pos.quantity) * self.config.commission_per_share
                )
    
    def _check_drawdown_halt(self):
        """Check if drawdown circuit breaker should trigger."""
        if len(self.portfolio.equity_history) < 2:
            return
        
        peak = max(self.portfolio.equity_history)
        current = self.portfolio.equity
        drawdown = (peak - current) / peak
        
        if drawdown >= self.config.max_drawdown_halt:
            self.is_halted = True
            self.halt_reason = f"Max drawdown {drawdown:.1%} exceeded limit"
            logger.warning(f"BACKTEST HALTED: {self.halt_reason}")
    
    def run(
        self,
        brain,
        symbols: List[str],
        start_idx: int = None,
        end_idx: int = None,
        progress_callback: Callable = None
    ) -> BacktestResult:
        """
        Run backtest.
        
        Args:
            brain: TradingBrain instance
            symbols: List of symbols to trade
            start_idx: Starting bar index (default: lookback_required)
            end_idx: Ending bar index (default: all data)
            progress_callback: Optional callback(current, total)
        
        Returns:
            BacktestResult with performance metrics
        """
        self.brain = brain
        
        # Determine data range
        min_bars = min(len(self.data.get(s, [])) for s in symbols)
        start_idx = start_idx or self.config.lookback_required
        end_idx = end_idx or min_bars
        
        logger.info(f"Running backtest from bar {start_idx} to {end_idx}")
        
        # Main loop
        for bar_idx in range(start_idx, end_idx):
            if self.is_halted:
                break
            
            # Update current bar
            self.current_bar = bar_idx
            
            # Get timestamp from first symbol
            first_symbol = symbols[0]
            bar = self.data[first_symbol][bar_idx]
            self.current_time = datetime.fromisoformat(
                bar.get('timestamp', bar.get('date', '2020-01-01'))
            ) if isinstance(bar.get('timestamp', bar.get('date')), str) else datetime.now()
            
            # Update current prices
            for symbol in symbols:
                if bar_idx < len(self.data.get(symbol, [])):
                    self.current_prices[symbol] = self.data[symbol][bar_idx].get('close', 0)
            
            # Update position prices
            self.portfolio.update_position_prices(self.current_prices)
            
            # Check stops first
            for symbol in symbols:
                if bar_idx < len(self.data.get(symbol, [])):
                    self._check_stops(self.data[symbol][bar_idx], symbol)
            
            # Process each symbol through brain
            for symbol in symbols:
                if symbol not in self.data or bar_idx >= len(self.data[symbol]):
                    continue
                
                # Prepare market data
                market_data = self._get_market_data_for_brain(symbol, bar_idx)
                
                # Get brain decision
                try:
                    decision = self.brain.think(symbol, market_data)
                except Exception as e:
                    logger.error(f"Brain error for {symbol}: {e}")
                    continue
                
                # Execute decision
                self._execute_decision(decision, symbol, market_data)
            
            # Update equity tracking
            brain.update_equity(self.portfolio.equity)
            
            # Check circuit breaker
            self._check_drawdown_halt()
            
            # Record equity
            self.portfolio.record_equity(self.current_time)
            
            # Progress callback
            if progress_callback and bar_idx % 100 == 0:
                progress_callback(bar_idx - start_idx, end_idx - start_idx)
        
        # Calculate results
        return self._calculate_results()
    
    def _execute_decision(
        self,
        decision,
        symbol: str,
        market_data: Dict
    ):
        """Execute a brain decision."""
        # Skip non-actionable decisions
        if decision.decision_type.value in ["HOLD", "AVOID"]:
            return
        
        # Get current position
        current_pos = self.portfolio.positions.get(symbol)
        current_qty = current_pos.quantity if current_pos else 0
        
        # Calculate position size
        target_value = self.portfolio.equity * (decision.position_size_pct / 100)
        current_price = market_data['quote']['price']
        target_qty = target_value / current_price if current_price > 0 else 0
        
        # Adjust for direction
        if decision.direction == "SHORT":
            target_qty = -target_qty
        elif decision.direction == "NEUTRAL":
            target_qty = 0
        
        # Calculate order quantity
        order_qty = target_qty - current_qty
        
        if abs(order_qty) < 1:
            return  # Skip tiny orders
        
        # Determine side
        side = OrderSide.BUY if order_qty > 0 else OrderSide.SELL
        
        # Submit and fill order
        order = self.portfolio.submit_order(
            symbol=symbol,
            side=side,
            quantity=abs(order_qty)
        )
        
        # Calculate fill price
        bar = self.data[symbol][self.current_bar]
        avg_volume = market_data.get('avg_volume', 1000000)
        fill_price = self._calculate_fill_price(order, bar, avg_volume)
        commission = abs(order_qty) * self.config.commission_per_share
        
        # Fill order
        self.portfolio.fill_order(
            order, fill_price, self.current_time,
            slippage=abs(fill_price - current_price),
            commission=commission
        )
        
        # Set stops on new position
        if symbol in self.portfolio.positions:
            pos = self.portfolio.positions[symbol]
            pos.stop_loss = decision.suggested_stop
            pos.take_profit = decision.suggested_target
        
        logger.debug(
            f"Executed {side.value} {abs(order_qty):.0f} {symbol} @ {fill_price:.2f}"
        )
    
    def _calculate_results(self) -> BacktestResult:
        """Calculate performance metrics."""
        equity_curve = np.array(self.portfolio.equity_history)
        
        # Returns
        returns = np.diff(equity_curve) / equity_curve[:-1]
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        
        # Annualized (assume 252 trading days)
        n_days = len(returns)
        annual_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1
        
        # Volatility
        volatility = np.std(returns) * np.sqrt(252)
        
        # Sharpe (assume 0% risk-free)
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        # Sortino (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0.01
        sortino = annual_return / downside_std if downside_std > 0 else 0
        
        # Drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak
        max_drawdown = np.max(drawdown)
        
        # Max DD duration
        dd_duration = 0
        max_dd_duration = 0
        for i, dd in enumerate(drawdown):
            if dd > 0:
                dd_duration += 1
                max_dd_duration = max(max_dd_duration, dd_duration)
            else:
                dd_duration = 0
        
        # Trade stats
        trades = self.portfolio.trades
        total_trades = len(trades)
        
        if total_trades > 0:
            winning_trades = [t for t in trades if t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl <= 0]
            
            win_rate = len(winning_trades) / total_trades
            avg_win = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t.pnl_pct for t in losing_trades]) if losing_trades else 0
            
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        else:
            winning_trades = []
            losing_trades = []
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            equity_curve=equity_curve,
            drawdown_curve=drawdown,
            returns=returns,
            trades=trades
        )


# Convenience function
def run_backtest(
    brain,
    data: Dict[str, List[Dict]],
    config: BacktestConfig = None,
    symbols: List[str] = None
) -> BacktestResult:
    """
    Run a backtest with minimal setup.
    
    Args:
        brain: TradingBrain instance
        data: Dict of symbol -> OHLCV list
        config: Optional BacktestConfig
        symbols: Optional list of symbols (default: all in data)
    
    Returns:
        BacktestResult
    """
    engine = BacktestEngine(config)
    
    # Load all data
    for symbol, ohlcv in data.items():
        engine.load_data(symbol, ohlcv)
    
    symbols = symbols or list(data.keys())
    
    return engine.run(brain, symbols)


# ==============================================================================
# PHASE 4: ADVANCED BACKTESTING FEATURES
# ==============================================================================

class StrategyDSL:
    """
    Domain-Specific Language for defining trading strategies.
    
    Example:
        strategy = StrategyDSL()
        strategy.define('''
            # Momentum Strategy
            entry_long: rsi(14) < 30 AND sma(20) > sma(50)
            entry_short: rsi(14) > 70 AND sma(20) < sma(50)
            exit_long: rsi(14) > 70 OR price < sma(50)
            exit_short: rsi(14) < 30 OR price > sma(50)
            position_size: kelly(0.5)
            stop_loss: atr(14) * 2
            take_profit: atr(14) * 3
        ''')
    """
    
    def __init__(self):
        self.rules = {
            'entry_long': None,
            'entry_short': None,
            'exit_long': None,
            'exit_short': None,
            'position_size': 0.02,  # 2% default
            'stop_loss': None,
            'take_profit': None
        }
        self.indicators = {}
        self._compiled = False
    
    def define(self, dsl_code: str):
        """Parse DSL strategy definition."""
        lines = [l.strip() for l in dsl_code.strip().split('\n') if l.strip() and not l.strip().startswith('#')]
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                if key in self.rules:
                    self.rules[key] = value
        
        self._compiled = True
        return self
    
    def evaluate(self, data: Dict, current_idx: int) -> Dict:
        """
        Evaluate strategy rules against current market data.
        
        Returns dict with signals: entry_long, entry_short, exit_long, exit_short
        """
        if not self._compiled:
            raise ValueError("Strategy not defined. Call define() first.")
        
        # Build indicator context
        ctx = self._build_context(data, current_idx)
        
        result = {
            'entry_long': self._eval_condition(self.rules['entry_long'], ctx) if self.rules['entry_long'] else False,
            'entry_short': self._eval_condition(self.rules['entry_short'], ctx) if self.rules['entry_short'] else False,
            'exit_long': self._eval_condition(self.rules['exit_long'], ctx) if self.rules['exit_long'] else False,
            'exit_short': self._eval_condition(self.rules['exit_short'], ctx) if self.rules['exit_short'] else False,
            'position_size': self._eval_size(self.rules['position_size'], ctx),
            'stop_loss': self._eval_price(self.rules['stop_loss'], ctx),
            'take_profit': self._eval_price(self.rules['take_profit'], ctx)
        }
        
        return result
    
    def _build_context(self, data: Dict, idx: int) -> Dict:
        """Build evaluation context with indicators."""
        closes = np.array([d['close'] for d in data[:idx+1]])
        highs = np.array([d['high'] for d in data[:idx+1]])
        lows = np.array([d['low'] for d in data[:idx+1]])
        volumes = np.array([d.get('volume', 0) for d in data[:idx+1]])
        
        ctx = {
            'price': closes[-1] if len(closes) > 0 else 0,
            'close': closes,
            'high': highs,
            'low': lows,
            'volume': volumes,
            'idx': idx
        }
        
        # Pre-compute common indicators
        ctx['sma'] = lambda n: np.mean(closes[-n:]) if len(closes) >= n else closes[-1]
        ctx['ema'] = lambda n: self._ema(closes, n)
        ctx['rsi'] = lambda n: self._rsi(closes, n)
        ctx['atr'] = lambda n: self._atr(highs, lows, closes, n)
        ctx['bb_upper'] = lambda n, std=2: ctx['sma'](n) + std * np.std(closes[-n:])
        ctx['bb_lower'] = lambda n, std=2: ctx['sma'](n) - std * np.std(closes[-n:])
        ctx['macd'] = lambda: self._macd(closes)
        ctx['momentum'] = lambda n: (closes[-1] / closes[-n] - 1) * 100 if len(closes) >= n else 0
        
        return ctx
    
    def _eval_condition(self, condition: str, ctx: Dict) -> bool:
        """Evaluate a condition string."""
        if not condition:
            return False
        
        try:
            # Replace DSL syntax with Python
            expr = condition.upper()
            expr = expr.replace('AND', 'and').replace('OR', 'or')
            expr = expr.replace('PRICE', 'ctx["price"]')
            
            # Handle function calls like sma(20)
            import re
            for func in ['sma', 'ema', 'rsi', 'atr', 'momentum', 'bb_upper', 'bb_lower']:
                pattern = rf'{func}\s*\(\s*(\d+)\s*\)'
                expr = re.sub(pattern, rf'ctx["{func}"](\1)', expr, flags=re.IGNORECASE)
            
            return eval(expr)
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
            return False
    
    def _eval_size(self, size_rule: str, ctx: Dict) -> float:
        """Evaluate position size rule."""
        if not size_rule:
            return 0.02
        
        try:
            if 'kelly' in size_rule.lower():
                # Extract Kelly fraction: kelly(0.5)
                import re
                match = re.search(r'kelly\s*\(\s*([\d.]+)\s*\)', size_rule, re.IGNORECASE)
                if match:
                    fraction = float(match.group(1))
                    return min(fraction * 0.1, 0.2)  # Cap at 20%
            return float(size_rule)
        except (ValueError, TypeError, KeyError):
            return 0.02
    
    def _eval_price(self, price_rule: str, ctx: Dict) -> Optional[float]:
        """Evaluate stop/target price rule."""
        if not price_rule:
            return None
        
        try:
            import re
            # Handle ATR-based rules: atr(14) * 2
            match = re.search(r'atr\s*\(\s*(\d+)\s*\)\s*\*\s*([\d.]+)', price_rule, re.IGNORECASE)
            if match:
                period = int(match.group(1))
                multiplier = float(match.group(2))
                atr_val = ctx['atr'](period)
                return atr_val * multiplier
            
            return float(price_rule)
        except (ValueError, TypeError, KeyError):
            return None
    
    # Indicator calculations
    @staticmethod
    def _ema(data: np.ndarray, period: int) -> float:
        if len(data) < period:
            return data[-1] if len(data) > 0 else 0
        multiplier = 2 / (period + 1)
        ema = data[-period]
        for price in data[-period+1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    @staticmethod
    def _rsi(data: np.ndarray, period: int = 14) -> float:
        if len(data) < period + 1:
            return 50
        deltas = np.diff(data[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        if len(closes) < period + 1:
            return highs[-1] - lows[-1] if len(highs) > 0 else 0
        tr = np.maximum(
            highs[-period:] - lows[-period:],
            np.maximum(
                np.abs(highs[-period:] - closes[-period-1:-1]),
                np.abs(lows[-period:] - closes[-period-1:-1])
            )
        )
        return np.mean(tr)
    
    @staticmethod
    def _macd(data: np.ndarray) -> Tuple[float, float, float]:
        if len(data) < 26:
            return 0, 0, 0
        fast = StrategyDSL._ema(data, 12)
        slow = StrategyDSL._ema(data, 26)
        macd_line = fast - slow
        # Signal line would need history, simplified here
        return macd_line, 0, macd_line


@dataclass
class WalkForwardResult:
    """Results from walk-forward optimization."""
    in_sample_results: List[BacktestResult]
    out_of_sample_results: List[BacktestResult]
    combined_equity: np.ndarray
    
    # Metrics
    avg_is_sharpe: float
    avg_oos_sharpe: float
    efficiency_ratio: float  # OOS/IS performance ratio
    
    # Best parameters per window
    best_params: List[Dict]
    
    def to_dict(self) -> Dict:
        return {
            "windows": len(self.in_sample_results),
            "avg_is_sharpe": f"{self.avg_is_sharpe:.2f}",
            "avg_oos_sharpe": f"{self.avg_oos_sharpe:.2f}",
            "efficiency_ratio": f"{self.efficiency_ratio:.1%}",
            "total_oos_return": f"{(self.combined_equity[-1]/self.combined_equity[0]-1):.2%}" if len(self.combined_equity) > 0 else "0%"
        }


class WalkForwardOptimizer:
    """
    Walk-Forward Optimization Engine.
    
    Splits data into rolling windows of in-sample (training) and 
    out-of-sample (validation) periods to avoid overfitting.
    """
    
    def __init__(
        self,
        in_sample_pct: float = 0.70,  # 70% for training
        n_windows: int = 5,           # Number of walk-forward windows
        anchored: bool = False         # If True, IS always starts at beginning
    ):
        self.in_sample_pct = in_sample_pct
        self.n_windows = n_windows
        self.anchored = anchored
    
    def optimize(
        self,
        brain_factory: Callable,  # Function that creates brain with params
        data: Dict[str, List[Dict]],
        param_grid: Dict[str, List],  # Parameter search space
        config: BacktestConfig = None
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.
        
        Args:
            brain_factory: Callable(params) -> TradingBrain
            data: Market data
            param_grid: Dict of param_name -> list of values to try
            config: Backtest configuration
        
        Returns:
            WalkForwardResult
        """
        # Get data length (use first symbol)
        first_symbol = list(data.keys())[0]
        total_bars = len(data[first_symbol])
        
        # Calculate window sizes
        window_size = total_bars // self.n_windows
        is_size = int(window_size * self.in_sample_pct)
        oos_size = window_size - is_size
        
        is_results = []
        oos_results = []
        best_params_list = []
        combined_equity = [config.initial_capital if config else 100000]
        
        for window in range(self.n_windows):
            # Define window boundaries
            if self.anchored:
                is_start = 0
            else:
                is_start = window * window_size
            
            is_end = is_start + is_size
            oos_start = is_end
            oos_end = min(oos_start + oos_size, total_bars)
            
            logger.info(f"Window {window+1}/{self.n_windows}: IS[{is_start}:{is_end}], OOS[{oos_start}:{oos_end}]")
            
            # Find best params on in-sample
            best_sharpe = -999
            best_params = {}
            best_is_result = None
            
            # Grid search
            param_combinations = self._generate_param_combinations(param_grid)
            
            for params in param_combinations:
                brain = brain_factory(params)
                engine = BacktestEngine(config)
                
                for symbol, ohlcv in data.items():
                    engine.load_data(symbol, ohlcv[is_start:is_end])
                
                try:
                    result = engine.run(brain, list(data.keys()))
                    if result.sharpe_ratio > best_sharpe:
                        best_sharpe = result.sharpe_ratio
                        best_params = params
                        best_is_result = result
                except Exception as e:
                    logger.warning(f"Backtest failed for params {params}: {e}")
                    continue
            
            if best_is_result is None:
                continue
            
            is_results.append(best_is_result)
            best_params_list.append(best_params)
            
            # Run out-of-sample with best params
            brain = brain_factory(best_params)
            engine = BacktestEngine(config)
            
            for symbol, ohlcv in data.items():
                engine.load_data(symbol, ohlcv[oos_start:oos_end])
            
            try:
                oos_result = engine.run(brain, list(data.keys()))
                oos_results.append(oos_result)
                
                # Chain equity curves
                scale = combined_equity[-1] / oos_result.equity_curve[0] if oos_result.equity_curve[0] > 0 else 1
                scaled_equity = oos_result.equity_curve * scale
                combined_equity.extend(scaled_equity[1:].tolist())
                
            except Exception as e:
                logger.warning(f"OOS backtest failed: {e}")
        
        # Calculate summary metrics
        avg_is_sharpe = np.mean([r.sharpe_ratio for r in is_results]) if is_results else 0
        avg_oos_sharpe = np.mean([r.sharpe_ratio for r in oos_results]) if oos_results else 0
        efficiency_ratio = avg_oos_sharpe / avg_is_sharpe if avg_is_sharpe > 0 else 0
        
        return WalkForwardResult(
            in_sample_results=is_results,
            out_of_sample_results=oos_results,
            combined_equity=np.array(combined_equity),
            avg_is_sharpe=avg_is_sharpe,
            avg_oos_sharpe=avg_oos_sharpe,
            efficiency_ratio=efficiency_ratio,
            best_params=best_params_list
        )
    
    @staticmethod
    def _generate_param_combinations(param_grid: Dict[str, List]) -> List[Dict]:
        """Generate all combinations of parameters."""
        if not param_grid:
            return [{}]
        
        import itertools
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""
    simulations: int
    
    # Return distributions
    mean_return: float
    median_return: float
    std_return: float
    percentile_5: float
    percentile_95: float
    
    # Risk metrics
    probability_of_loss: float
    max_drawdown_mean: float
    max_drawdown_95: float
    
    # VaR
    var_95: float  # 5% VaR
    cvar_95: float  # Expected shortfall
    
    # All equity curves (for visualization)
    equity_curves: np.ndarray
    
    def to_dict(self) -> Dict:
        return {
            "simulations": self.simulations,
            "mean_return": f"{self.mean_return:.2%}",
            "median_return": f"{self.median_return:.2%}",
            "return_std": f"{self.std_return:.2%}",
            "5th_percentile": f"{self.percentile_5:.2%}",
            "95th_percentile": f"{self.percentile_95:.2%}",
            "prob_of_loss": f"{self.probability_of_loss:.1%}",
            "max_dd_mean": f"{self.max_drawdown_mean:.2%}",
            "max_dd_95": f"{self.max_drawdown_95:.2%}",
            "var_95": f"{self.var_95:.2%}",
            "cvar_95": f"{self.cvar_95:.2%}"
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy performance analysis.
    
    Generates multiple possible paths by:
    1. Trade resampling (bootstrap)
    2. Return shuffling
    3. Parametric simulation (normal/student-t)
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        method: str = "bootstrap"  # bootstrap, shuffle, parametric
    ):
        self.n_simulations = n_simulations
        self.method = method
    
    def simulate_from_trades(
        self,
        trades: List[Trade],
        initial_capital: float = 100000,
        n_trades_per_sim: int = None
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation by resampling trades.
        """
        if not trades:
            raise ValueError("No trades provided for simulation")
        
        n_trades = n_trades_per_sim or len(trades)
        trade_returns = np.array([t.pnl_pct for t in trades])
        
        equity_curves = np.zeros((self.n_simulations, n_trades + 1))
        equity_curves[:, 0] = initial_capital
        
        for sim in range(self.n_simulations):
            if self.method == "bootstrap":
                # Random sampling with replacement
                sampled_returns = np.random.choice(trade_returns, size=n_trades, replace=True)
            elif self.method == "shuffle":
                # Random permutation
                sampled_returns = np.random.permutation(trade_returns)
                if len(sampled_returns) < n_trades:
                    sampled_returns = np.tile(sampled_returns, n_trades // len(sampled_returns) + 1)[:n_trades]
            else:  # parametric
                # Fit distribution and sample
                mu, sigma = np.mean(trade_returns), np.std(trade_returns)
                sampled_returns = np.random.normal(mu, sigma, n_trades)
            
            # Build equity curve
            for i, ret in enumerate(sampled_returns):
                equity_curves[sim, i + 1] = equity_curves[sim, i] * (1 + ret)
        
        # Calculate metrics
        final_equity = equity_curves[:, -1]
        total_returns = (final_equity - initial_capital) / initial_capital
        
        # Max drawdowns per simulation
        max_drawdowns = []
        for sim in range(self.n_simulations):
            curve = equity_curves[sim]
            peak = np.maximum.accumulate(curve)
            dd = (peak - curve) / peak
            max_drawdowns.append(np.max(dd))
        max_drawdowns = np.array(max_drawdowns)
        
        return MonteCarloResult(
            simulations=self.n_simulations,
            mean_return=np.mean(total_returns),
            median_return=np.median(total_returns),
            std_return=np.std(total_returns),
            percentile_5=np.percentile(total_returns, 5),
            percentile_95=np.percentile(total_returns, 95),
            probability_of_loss=np.mean(total_returns < 0),
            max_drawdown_mean=np.mean(max_drawdowns),
            max_drawdown_95=np.percentile(max_drawdowns, 95),
            var_95=np.percentile(total_returns, 5),  # 5% worst case
            cvar_95=np.mean(total_returns[total_returns <= np.percentile(total_returns, 5)]),
            equity_curves=equity_curves
        )
    
    def simulate_from_returns(
        self,
        daily_returns: np.ndarray,
        initial_capital: float = 100000,
        days_forward: int = 252
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation using daily returns.
        """
        equity_curves = np.zeros((self.n_simulations, days_forward + 1))
        equity_curves[:, 0] = initial_capital
        
        mu = np.mean(daily_returns)
        sigma = np.std(daily_returns)
        
        for sim in range(self.n_simulations):
            if self.method == "bootstrap":
                sampled_returns = np.random.choice(daily_returns, size=days_forward, replace=True)
            elif self.method == "shuffle":
                sampled_returns = np.random.permutation(daily_returns)
                if len(sampled_returns) < days_forward:
                    sampled_returns = np.tile(sampled_returns, days_forward // len(sampled_returns) + 1)[:days_forward]
            else:  # parametric (GBM-like)
                sampled_returns = np.random.normal(mu, sigma, days_forward)
            
            # Build equity curve
            equity_curves[sim, 1:] = initial_capital * np.cumprod(1 + sampled_returns)
        
        # Calculate metrics
        final_equity = equity_curves[:, -1]
        total_returns = (final_equity - initial_capital) / initial_capital
        
        max_drawdowns = []
        for sim in range(self.n_simulations):
            curve = equity_curves[sim]
            peak = np.maximum.accumulate(curve)
            dd = (peak - curve) / peak
            max_drawdowns.append(np.max(dd))
        max_drawdowns = np.array(max_drawdowns)
        
        return MonteCarloResult(
            simulations=self.n_simulations,
            mean_return=np.mean(total_returns),
            median_return=np.median(total_returns),
            std_return=np.std(total_returns),
            percentile_5=np.percentile(total_returns, 5),
            percentile_95=np.percentile(total_returns, 95),
            probability_of_loss=np.mean(total_returns < 0),
            max_drawdown_mean=np.mean(max_drawdowns),
            max_drawdown_95=np.percentile(max_drawdowns, 95),
            var_95=np.percentile(total_returns, 5),
            cvar_95=np.mean(total_returns[total_returns <= np.percentile(total_returns, 5)]),
            equity_curves=equity_curves
        )
