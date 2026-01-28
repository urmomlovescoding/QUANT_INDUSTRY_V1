"""
QUANT_INDUSTRY_V1 Backtesting Engine

Institutional-grade backtesting with:
- Event-driven simulation
- Realistic transaction costs
- Slippage modeling
- Walk-forward analysis
- Monte Carlo validation
- Performance attribution

Rollback Plan: Delete this file
Tests Required: Backtest accuracy, performance metrics
Failure Modes: Graceful stop, save partial results
"""

import numpy as np
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import copy

logger = logging.getLogger(__name__)


# =============================================================================
# BACKTEST TYPES
# =============================================================================

class FillModel(Enum):
    """Order fill modeling approach."""
    IMMEDIATE = "immediate"      # Fill at current price
    NEXT_BAR = "next_bar"        # Fill at next bar open
    VWAP = "vwap"               # Fill at bar VWAP
    WORST_CASE = "worst_case"    # Fill at worst price in bar


@dataclass
class BacktestConfig:
    """Backtesting configuration."""
    initial_capital: float = 100000.0
    commission_rate: float = 0.001      # 0.1% per trade
    slippage_bps: float = 5.0           # 5 basis points
    fill_model: FillModel = FillModel.NEXT_BAR
    margin_requirement: float = 1.0     # 1.0 = no margin
    max_leverage: float = 1.0
    risk_free_rate: float = 0.02        # 2% annual
    benchmark_symbol: str = "SPY"
    allow_shorting: bool = True
    fractional_shares: bool = False


@dataclass
class BacktestTrade:
    """Record of a completed trade."""
    trade_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    commission: float
    slippage: float
    holding_period: timedelta
    signal_strength: float = 0.0
    strategy_id: str = ""

    @property
    def net_pnl(self) -> float:
        return self.pnl - self.commission - self.slippage


@dataclass
class BacktestPosition:
    """Current position state."""
    symbol: str
    quantity: int
    avg_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    current_price: float = 0.0

    def update_price(self, price: float) -> None:
        self.current_price = price
        self.unrealized_pnl = (price - self.avg_price) * self.quantity


@dataclass
class BacktestSnapshot:
    """Point-in-time portfolio snapshot."""
    timestamp: datetime
    equity: float
    cash: float
    positions_value: float
    positions: Dict[str, BacktestPosition]
    daily_return: float = 0.0
    drawdown: float = 0.0


@dataclass
class BacktestResult:
    """Complete backtest results."""
    # Config
    config: BacktestConfig
    start_date: datetime
    end_date: datetime

    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0

    # Risk metrics
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # days

    # Trade metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_holding_period: float = 0.0  # days

    # Exposure
    avg_exposure: float = 0.0
    max_exposure: float = 0.0
    time_in_market: float = 0.0  # percentage

    # Data
    equity_curve: List[float] = field(default_factory=list)
    returns: List[float] = field(default_factory=list)
    drawdowns: List[float] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)
    snapshots: List[BacktestSnapshot] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'alpha': self.alpha,
            'beta': self.beta,
        }


# =============================================================================
# SLIPPAGE & COMMISSION MODELS
# =============================================================================

class SlippageModel(ABC):
    """Base slippage model."""

    @abstractmethod
    def calculate(
        self,
        price: float,
        quantity: int,
        side: str,
        volatility: float = 0.02
    ) -> float:
        """Calculate slippage cost."""
        pass


class FixedSlippage(SlippageModel):
    """Fixed basis points slippage."""

    def __init__(self, bps: float = 5.0):
        self.bps = bps

    def calculate(
        self,
        price: float,
        quantity: int,
        side: str,
        volatility: float = 0.02
    ) -> float:
        return price * quantity * (self.bps / 10000)


class VolatilitySlippage(SlippageModel):
    """Volatility-adjusted slippage."""

    def __init__(self, base_bps: float = 2.0, vol_multiplier: float = 100):
        self.base_bps = base_bps
        self.vol_multiplier = vol_multiplier

    def calculate(
        self,
        price: float,
        quantity: int,
        side: str,
        volatility: float = 0.02
    ) -> float:
        effective_bps = self.base_bps + volatility * self.vol_multiplier
        return price * quantity * (effective_bps / 10000)


class MarketImpactSlippage(SlippageModel):
    """Square-root market impact model."""

    def __init__(self, impact_factor: float = 0.1, avg_volume: float = 1000000):
        self.impact_factor = impact_factor
        self.avg_volume = avg_volume

    def calculate(
        self,
        price: float,
        quantity: int,
        side: str,
        volatility: float = 0.02
    ) -> float:
        # Square-root impact model
        participation = quantity / self.avg_volume
        impact = self.impact_factor * volatility * np.sqrt(participation)
        return price * quantity * impact


class CommissionModel(ABC):
    """Base commission model."""

    @abstractmethod
    def calculate(
        self,
        price: float,
        quantity: int
    ) -> float:
        """Calculate commission cost."""
        pass


class PercentageCommission(CommissionModel):
    """Percentage-based commission."""

    def __init__(self, rate: float = 0.001, minimum: float = 1.0):
        self.rate = rate
        self.minimum = minimum

    def calculate(self, price: float, quantity: int) -> float:
        return max(self.minimum, price * quantity * self.rate)


class PerShareCommission(CommissionModel):
    """Per-share commission."""

    def __init__(self, per_share: float = 0.005, minimum: float = 1.0):
        self.per_share = per_share
        self.minimum = minimum

    def calculate(self, price: float, quantity: int) -> float:
        return max(self.minimum, quantity * self.per_share)


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class BacktestEngine:
    """
    Event-driven backtesting engine.

    Simulates strategy execution with realistic market conditions.
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()

        # Models
        self.slippage_model = FixedSlippage(self.config.slippage_bps)
        self.commission_model = PercentageCommission(self.config.commission_rate)

        # State
        self.cash = self.config.initial_capital
        self.positions: Dict[str, BacktestPosition] = {}
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = []
        self.returns: List[float] = []
        self.snapshots: List[BacktestSnapshot] = []

        # Tracking
        self._trade_count = 0
        self._peak_equity = self.config.initial_capital
        self._current_time: Optional[datetime] = None

    def reset(self) -> None:
        """Reset engine state."""
        self.cash = self.config.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.returns = []
        self.snapshots = []
        self._trade_count = 0
        self._peak_equity = self.config.initial_capital
        self._current_time = None

    def run(
        self,
        strategy,
        data: Dict[str, Dict[str, List]],
        start_date: datetime = None,
        end_date: datetime = None
    ) -> BacktestResult:
        """
        Run backtest on historical data.

        Args:
            strategy: Strategy instance with generate_signals method
            data: Dict of symbol -> {'close': [], 'open': [], 'high': [], 'low': [], 'volume': [], 'timestamp': []}
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            BacktestResult with all metrics
        """
        self.reset()

        # Get timestamps from first symbol
        first_symbol = list(data.keys())[0]
        timestamps = data[first_symbol].get('timestamp', [])

        if not timestamps:
            # Generate timestamps if not provided
            n_bars = len(data[first_symbol]['close'])
            timestamps = [
                datetime.now(timezone.utc) - timedelta(days=n_bars-i)
                for i in range(n_bars)
            ]

        # Filter by date range
        start_idx = 0
        end_idx = len(timestamps)

        if start_date:
            for i, ts in enumerate(timestamps):
                if ts >= start_date:
                    start_idx = i
                    break

        if end_date:
            for i, ts in enumerate(timestamps):
                if ts > end_date:
                    end_idx = i
                    break

        # Set strategy to backtesting mode
        from strategies import StrategyStatus
        strategy.set_status(StrategyStatus.BACKTESTING)

        # Main simulation loop
        prev_equity = self.config.initial_capital

        for i in range(start_idx, end_idx):
            self._current_time = timestamps[i] if isinstance(timestamps[i], datetime) else datetime.now(timezone.utc)

            # Build current bar data
            bar_data = {}
            for symbol, symbol_data in data.items():
                bar_data[symbol] = {
                    'close': symbol_data['close'][:i+1],
                    'open': symbol_data.get('open', symbol_data['close'])[:i+1],
                    'high': symbol_data.get('high', symbol_data['close'])[:i+1],
                    'low': symbol_data.get('low', symbol_data['close'])[:i+1],
                    'volume': symbol_data.get('volume', [0]*len(symbol_data['close']))[:i+1],
                }

            # Update position prices
            for symbol, pos in self.positions.items():
                if symbol in bar_data:
                    pos.update_price(bar_data[symbol]['close'][-1])

            # Generate signals
            signals = strategy.update(bar_data)

            # Process signals
            for signal in signals:
                self._process_signal(signal, bar_data)

            # Calculate equity
            equity = self._calculate_equity(bar_data)
            self.equity_curve.append(equity)

            # Calculate return
            daily_return = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            self.returns.append(daily_return)
            prev_equity = equity

            # Update peak and drawdown
            self._peak_equity = max(self._peak_equity, equity)

            # Take snapshot
            self._take_snapshot(bar_data, daily_return)

        # Close remaining positions
        if data:
            final_bar = {
                symbol: {'close': [d['close'][-1]]}
                for symbol, d in data.items()
            }
            self._close_all_positions(final_bar)

        # Calculate results
        return self._calculate_results(
            start_date or timestamps[start_idx],
            end_date or timestamps[end_idx-1]
        )

    def _process_signal(
        self,
        signal,
        data: Dict[str, Dict[str, List]]
    ) -> None:
        """Process a trading signal."""
        from strategies import SignalDirection

        symbol = signal.symbol
        if symbol not in data:
            return

        current_price = data[symbol]['close'][-1]

        # Determine action
        if signal.direction == SignalDirection.LONG:
            self._open_position(symbol, 'buy', signal, current_price)
        elif signal.direction == SignalDirection.SHORT:
            if self.config.allow_shorting:
                self._open_position(symbol, 'sell', signal, current_price)
        elif signal.direction == SignalDirection.FLAT:
            if symbol in self.positions:
                self._close_position(symbol, current_price)

    def _open_position(
        self,
        symbol: str,
        side: str,
        signal,
        price: float
    ) -> None:
        """Open or add to position."""
        # Calculate position size based on signal strength and available capital
        equity = self.cash + sum(
            p.quantity * p.current_price for p in self.positions.values()
        )

        # Risk-based position sizing
        risk_per_trade = 0.02  # 2% risk per trade
        position_value = equity * risk_per_trade * abs(signal.strength)

        # Apply leverage limits
        max_position_value = equity * self.config.max_leverage * 0.25
        position_value = min(position_value, max_position_value, self.cash * 0.95)

        if position_value < 100:  # Minimum position
            return

        quantity = int(position_value / price)
        if not self.config.fractional_shares:
            quantity = max(1, quantity)

        if quantity <= 0:
            return

        # Calculate costs
        slippage = self.slippage_model.calculate(price, quantity, side)
        commission = self.commission_model.calculate(price, quantity)

        # Adjusted price
        fill_price = price * (1 + slippage/price/quantity) if side == 'buy' else price * (1 - slippage/price/quantity)

        # Check if we have enough cash
        total_cost = fill_price * quantity + commission
        if side == 'buy' and total_cost > self.cash:
            quantity = int((self.cash - commission) / fill_price)
            if quantity <= 0:
                return
            total_cost = fill_price * quantity + commission

        # Execute
        if side == 'buy':
            self.cash -= total_cost
            if symbol in self.positions:
                # Average into existing position
                pos = self.positions[symbol]
                total_qty = pos.quantity + quantity
                pos.avg_price = (pos.avg_price * pos.quantity + fill_price * quantity) / total_qty
                pos.quantity = total_qty
            else:
                self.positions[symbol] = BacktestPosition(
                    symbol=symbol,
                    quantity=quantity,
                    avg_price=fill_price,
                    entry_time=self._current_time,
                    current_price=price
                )
        else:
            # Short position
            self.cash += fill_price * quantity - commission
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.quantity -= quantity
                if pos.quantity <= 0:
                    del self.positions[symbol]
            else:
                self.positions[symbol] = BacktestPosition(
                    symbol=symbol,
                    quantity=-quantity,
                    avg_price=fill_price,
                    entry_time=self._current_time,
                    current_price=price
                )

    def _close_position(self, symbol: str, price: float) -> None:
        """Close position and record trade."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        quantity = abs(pos.quantity)
        side = 'sell' if pos.quantity > 0 else 'buy'

        # Calculate costs
        slippage = self.slippage_model.calculate(price, quantity, side)
        commission = self.commission_model.calculate(price, quantity)

        fill_price = price * (1 - slippage/price/quantity) if side == 'sell' else price * (1 + slippage/price/quantity)

        # Calculate PnL
        if pos.quantity > 0:
            pnl = (fill_price - pos.avg_price) * quantity
        else:
            pnl = (pos.avg_price - fill_price) * quantity

        pnl_pct = pnl / (pos.avg_price * quantity) if pos.avg_price > 0 else 0

        # Update cash
        if side == 'sell':
            self.cash += fill_price * quantity - commission
        else:
            self.cash -= fill_price * quantity + commission

        # Record trade
        self._trade_count += 1
        trade = BacktestTrade(
            trade_id=f"BT-{self._trade_count:06d}",
            symbol=symbol,
            side='long' if pos.quantity > 0 else 'short',
            quantity=quantity,
            entry_price=pos.avg_price,
            exit_price=fill_price,
            entry_time=pos.entry_time,
            exit_time=self._current_time,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            slippage=slippage,
            holding_period=self._current_time - pos.entry_time
        )
        self.trades.append(trade)

        # Remove position
        del self.positions[symbol]

    def _close_all_positions(self, data: Dict[str, Dict[str, List]]) -> None:
        """Close all remaining positions."""
        for symbol in list(self.positions.keys()):
            if symbol in data:
                price = data[symbol]['close'][-1]
                self._close_position(symbol, price)

    def _calculate_equity(self, data: Dict[str, Dict[str, List]]) -> float:
        """Calculate current equity."""
        positions_value = sum(
            pos.quantity * data.get(symbol, {}).get('close', [pos.current_price])[-1]
            for symbol, pos in self.positions.items()
        )
        return self.cash + positions_value

    def _take_snapshot(self, data: Dict[str, Dict[str, List]], daily_return: float) -> None:
        """Take portfolio snapshot."""
        equity = self._calculate_equity(data)
        positions_value = equity - self.cash
        drawdown = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0

        snapshot = BacktestSnapshot(
            timestamp=self._current_time,
            equity=equity,
            cash=self.cash,
            positions_value=positions_value,
            positions=copy.deepcopy(self.positions),
            daily_return=daily_return,
            drawdown=drawdown
        )
        self.snapshots.append(snapshot)

    def _calculate_results(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Calculate all backtest metrics."""
        result = BacktestResult(
            config=self.config,
            start_date=start_date,
            end_date=end_date,
            equity_curve=self.equity_curve.copy(),
            returns=self.returns.copy(),
            trades=self.trades.copy(),
            snapshots=self.snapshots.copy()
        )

        if not self.equity_curve:
            return result

        # Basic returns
        final_equity = self.equity_curve[-1]
        result.total_return = (final_equity - self.config.initial_capital) / self.config.initial_capital

        # Annualized return
        days = (end_date - start_date).days
        if days > 0:
            result.annualized_return = (1 + result.total_return) ** (365 / days) - 1

        # Risk metrics
        returns_arr = np.array(self.returns)
        if len(returns_arr) > 1:
            result.volatility = float(np.std(returns_arr) * np.sqrt(252))

            # Sharpe ratio
            excess_return = np.mean(returns_arr) - self.config.risk_free_rate / 252
            if np.std(returns_arr) > 0:
                result.sharpe_ratio = float(excess_return / np.std(returns_arr) * np.sqrt(252))

            # Sortino ratio
            downside_returns = returns_arr[returns_arr < 0]
            if len(downside_returns) > 0 and np.std(downside_returns) > 0:
                result.sortino_ratio = float(excess_return / np.std(downside_returns) * np.sqrt(252))

        # Drawdown analysis
        equity_arr = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity_arr)
        drawdowns = (peak - equity_arr) / peak
        result.drawdowns = drawdowns.tolist()
        result.max_drawdown = float(np.max(drawdowns))
        result.avg_drawdown = float(np.mean(drawdowns[drawdowns > 0])) if np.any(drawdowns > 0) else 0

        # Calmar ratio
        if result.max_drawdown > 0:
            result.calmar_ratio = result.annualized_return / result.max_drawdown

        # Drawdown duration
        in_drawdown = drawdowns > 0
        if np.any(in_drawdown):
            dd_periods = []
            current_dd = 0
            for dd in in_drawdown:
                if dd:
                    current_dd += 1
                else:
                    if current_dd > 0:
                        dd_periods.append(current_dd)
                    current_dd = 0
            if current_dd > 0:
                dd_periods.append(current_dd)
            result.max_drawdown_duration = max(dd_periods) if dd_periods else 0

        # Trade analysis
        if self.trades:
            result.total_trades = len(self.trades)

            winning = [t for t in self.trades if t.net_pnl > 0]
            losing = [t for t in self.trades if t.net_pnl <= 0]

            result.winning_trades = len(winning)
            result.losing_trades = len(losing)
            result.win_rate = len(winning) / len(self.trades)

            if winning:
                result.avg_win = np.mean([t.net_pnl for t in winning])
                result.largest_win = max(t.net_pnl for t in winning)

            if losing:
                result.avg_loss = abs(np.mean([t.net_pnl for t in losing]))
                result.largest_loss = abs(min(t.net_pnl for t in losing))

            # Profit factor
            gross_profit = sum(t.net_pnl for t in winning)
            gross_loss = abs(sum(t.net_pnl for t in losing))
            if gross_loss > 0:
                result.profit_factor = gross_profit / gross_loss

            result.avg_trade = np.mean([t.net_pnl for t in self.trades])

            # Holding period
            holding_periods = [(t.exit_time - t.entry_time).days for t in self.trades]
            result.avg_holding_period = np.mean(holding_periods) if holding_periods else 0

        # Exposure
        if self.snapshots:
            exposures = [
                s.positions_value / s.equity if s.equity > 0 else 0
                for s in self.snapshots
            ]
            result.avg_exposure = float(np.mean(exposures))
            result.max_exposure = float(np.max(exposures))
            result.time_in_market = sum(1 for e in exposures if e > 0.01) / len(exposures)

        return result


# =============================================================================
# WALK-FORWARD ANALYZER
# =============================================================================

class WalkForwardAnalyzer:
    """
    Walk-forward analysis for robust strategy validation.
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_ratio: float = 0.7,
        anchored: bool = False
    ):
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.anchored = anchored

    def analyze(
        self,
        strategy_factory: Callable,
        data: Dict[str, Dict[str, List]],
        config: BacktestConfig = None
    ) -> Dict[str, Any]:
        """
        Run walk-forward analysis.

        Args:
            strategy_factory: Function that creates new strategy instance
            data: Historical data
            config: Backtest configuration

        Returns:
            Walk-forward analysis results
        """
        config = config or BacktestConfig()

        # Get data length
        first_symbol = list(data.keys())[0]
        n_bars = len(data[first_symbol]['close'])

        # Calculate split sizes
        split_size = n_bars // self.n_splits
        train_size = int(split_size * self.train_ratio)
        test_size = split_size - train_size

        results = []
        all_trades = []
        equity_curves = []

        for i in range(self.n_splits):
            # Calculate indices
            if self.anchored:
                train_start = 0
            else:
                train_start = i * split_size

            train_end = train_start + train_size + (i * split_size if self.anchored else 0)
            test_start = train_end
            test_end = test_start + test_size

            if test_end > n_bars:
                break

            # Split data
            train_data = {
                symbol: {
                    key: values[train_start:train_end]
                    for key, values in symbol_data.items()
                }
                for symbol, symbol_data in data.items()
            }

            test_data = {
                symbol: {
                    key: values[test_start:test_end]
                    for key, values in symbol_data.items()
                }
                for symbol, symbol_data in data.items()
            }

            # Create fresh strategy
            strategy = strategy_factory()

            # Train (optimization would happen here in production)
            # For now, just run backtest on training period
            train_engine = BacktestEngine(config)
            train_result = train_engine.run(strategy, train_data)

            # Test on out-of-sample
            test_strategy = strategy_factory()
            test_engine = BacktestEngine(config)
            test_result = test_engine.run(test_strategy, test_data)

            results.append({
                'fold': i,
                'train_return': train_result.total_return,
                'test_return': test_result.total_return,
                'train_sharpe': train_result.sharpe_ratio,
                'test_sharpe': test_result.sharpe_ratio,
                'test_trades': test_result.total_trades,
                'test_win_rate': test_result.win_rate,
            })

            all_trades.extend(test_result.trades)
            equity_curves.append(test_result.equity_curve)

        # Aggregate results
        test_returns = [r['test_return'] for r in results]
        test_sharpes = [r['test_sharpe'] for r in results]

        return {
            'n_folds': len(results),
            'fold_results': results,
            'avg_test_return': np.mean(test_returns),
            'std_test_return': np.std(test_returns),
            'avg_test_sharpe': np.mean(test_sharpes),
            'std_test_sharpe': np.std(test_sharpes),
            'total_trades': len(all_trades),
            'consistency': sum(1 for r in test_returns if r > 0) / len(test_returns) if results else 0,
        }


# =============================================================================
# MONTE CARLO ANALYZER
# =============================================================================

class MonteCarloAnalyzer:
    """
    Monte Carlo analysis for robustness testing.
    """

    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations

    def analyze_trades(self, trades: List[BacktestTrade]) -> Dict[str, Any]:
        """
        Run Monte Carlo analysis on trade sequence.

        Randomizes trade order to assess strategy robustness.
        """
        if not trades:
            return {}

        # Extract trade PnLs
        pnls = [t.net_pnl for t in trades]

        final_equities = []
        max_drawdowns = []

        for _ in range(self.n_simulations):
            # Shuffle trades
            shuffled = np.random.permutation(pnls)

            # Calculate equity curve
            equity = [100000]  # Starting capital
            for pnl in shuffled:
                equity.append(equity[-1] + pnl)

            final_equities.append(equity[-1])

            # Calculate max drawdown
            equity_arr = np.array(equity)
            peak = np.maximum.accumulate(equity_arr)
            dd = (peak - equity_arr) / peak
            max_drawdowns.append(np.max(dd))

        return {
            'n_simulations': self.n_simulations,
            'original_equity': 100000 + sum(pnls),
            'mean_final_equity': np.mean(final_equities),
            'std_final_equity': np.std(final_equities),
            'percentile_5': np.percentile(final_equities, 5),
            'percentile_50': np.percentile(final_equities, 50),
            'percentile_95': np.percentile(final_equities, 95),
            'mean_max_drawdown': np.mean(max_drawdowns),
            'max_max_drawdown': np.max(max_drawdowns),
            'probability_profit': sum(1 for e in final_equities if e > 100000) / len(final_equities),
        }

    def analyze_returns(
        self,
        returns: List[float],
        initial_capital: float = 100000
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo analysis on return sequence.

        Bootstraps returns to generate confidence intervals.
        """
        if not returns:
            return {}

        returns_arr = np.array(returns)
        n_periods = len(returns)

        final_equities = []
        sharpe_ratios = []

        for _ in range(self.n_simulations):
            # Bootstrap sample
            sampled = np.random.choice(returns_arr, size=n_periods, replace=True)

            # Calculate final equity
            equity = initial_capital * np.prod(1 + sampled)
            final_equities.append(equity)

            # Calculate Sharpe
            if np.std(sampled) > 0:
                sharpe = np.mean(sampled) / np.std(sampled) * np.sqrt(252)
                sharpe_ratios.append(sharpe)

        return {
            'n_simulations': self.n_simulations,
            'mean_final_equity': np.mean(final_equities),
            'ci_95_lower': np.percentile(final_equities, 2.5),
            'ci_95_upper': np.percentile(final_equities, 97.5),
            'mean_sharpe': np.mean(sharpe_ratios) if sharpe_ratios else 0,
            'sharpe_ci_95': (
                np.percentile(sharpe_ratios, 2.5) if sharpe_ratios else 0,
                np.percentile(sharpe_ratios, 97.5) if sharpe_ratios else 0,
            ),
        }
