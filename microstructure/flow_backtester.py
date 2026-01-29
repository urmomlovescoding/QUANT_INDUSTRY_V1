"""
Order Flow Backtesting Framework
================================
Backtests order flow strategies with realistic market simulation.
"""

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Iterator, Tuple
from enum import Enum
import logging
from collections import defaultdict
import json
from pathlib import Path

from .order_flow_features import (
    OrderFlowFeatureEngine, OrderBookSnapshot, TradeEvent, FeatureSet
)
from .flow_models import FlowModel, ModelPrediction, PredictionTarget

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


class TradeStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """Order submitted to backtester."""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None  # For limit orders
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Execution
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    fill_timestamp: Optional[datetime] = None
    
    # Slippage and fees
    slippage: float = 0.0
    commission: float = 0.0
    
    @property
    def is_filled(self) -> bool:
        return self.filled_quantity == self.quantity


@dataclass
class Trade:
    """Executed trade (position)."""
    id: str
    symbol: str
    side: OrderSide
    entry_price: float
    entry_time: datetime
    quantity: int
    
    # Exit info
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    status: TradeStatus = TradeStatus.OPEN
    
    # P&L
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    
    # Signal info
    signal_confidence: float = 0.0
    features_at_entry: Optional[Dict[str, float]] = None
    prediction: Optional[ModelPrediction] = None
    
    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN
    
    @property
    def holding_period(self) -> Optional[timedelta]:
        if self.exit_time and self.entry_time:
            return self.exit_time - self.entry_time
        return None
    
    @property
    def gross_pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        if self.side == OrderSide.BUY:
            return (self.exit_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.exit_price) * self.quantity
    
    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.commission - self.slippage
    
    @property
    def return_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return self.gross_pnl / (self.entry_price * self.quantity) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "quantity": self.quantity,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "return_pct": self.return_pct,
            "holding_period_seconds": self.holding_period.total_seconds() if self.holding_period else None,
            "signal_confidence": self.signal_confidence,
        }


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    # Capital
    initial_capital: float = 100_000
    max_position_pct: float = 0.1  # Max 10% of capital per trade
    max_positions: int = 5
    
    # Execution
    slippage_bps: float = 1.0  # 0.01%
    commission_per_share: float = 0.005
    min_commission: float = 1.0
    
    # Risk management
    stop_loss_pct: float = 0.01  # 1%
    take_profit_pct: float = 0.02  # 2%
    max_holding_seconds: int = 300  # 5 minutes
    
    # Signal thresholds
    min_confidence: float = 0.6
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class BacktestResult:
    """Backtest results and metrics."""
    config: BacktestConfig
    trades: List[Trade]
    
    # Performance
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Trade statistics
    num_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_holding_seconds: float = 0.0
    
    # Risk metrics
    max_consecutive_losses: int = 0
    var_95: float = 0.0
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_pnl": self.total_pnl,
            "total_return_pct": self.total_return_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "num_trades": self.num_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_holding_seconds": self.avg_holding_seconds,
            "max_consecutive_losses": self.max_consecutive_losses,
            "var_95": self.var_95,
        }
    
    def summary(self) -> str:
        """Human-readable summary."""
        return f"""
Backtest Results
================
Period: {self.start_time} to {self.end_time}
Initial Capital: ${self.config.initial_capital:,.0f}

Performance:
  Total P&L: ${self.total_pnl:,.2f} ({self.total_return_pct:.2f}%)
  Sharpe Ratio: {self.sharpe_ratio:.2f}
  Sortino Ratio: {self.sortino_ratio:.2f}
  Max Drawdown: {self.max_drawdown_pct:.2f}%

Trades:
  Total Trades: {self.num_trades}
  Win Rate: {self.win_rate:.1f}%
  Profit Factor: {self.profit_factor:.2f}
  Avg Win: ${self.avg_win:.2f}
  Avg Loss: ${self.avg_loss:.2f}
  Avg Holding Time: {self.avg_holding_seconds:.1f}s

Risk:
  Max Consecutive Losses: {self.max_consecutive_losses}
  VaR (95%): ${self.var_95:.2f}
"""


class ExecutionSimulator:
    """
    Simulates realistic order execution.
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        
    def execute_market_order(
        self,
        order: Order,
        book: OrderBookSnapshot,
    ) -> Order:
        """Simulate market order execution."""
        if order.side == OrderSide.BUY:
            if not book.asks:
                return order  # Can't fill
            base_price = book.asks[0].price
        else:
            if not book.bids:
                return order
            base_price = book.bids[0].price
            
        # Apply slippage
        slippage_pct = self.config.slippage_bps / 10000
        if order.side == OrderSide.BUY:
            fill_price = base_price * (1 + slippage_pct)
        else:
            fill_price = base_price * (1 - slippage_pct)
            
        order.avg_fill_price = fill_price
        order.filled_quantity = order.quantity
        order.fill_timestamp = book.timestamp
        order.slippage = abs(fill_price - base_price) * order.quantity
        
        # Commission
        order.commission = max(
            self.config.min_commission,
            order.quantity * self.config.commission_per_share
        )
        
        return order
    
    def simulate_fill_walk(
        self,
        order: Order,
        book: OrderBookSnapshot,
    ) -> Order:
        """
        Simulate filling through multiple price levels.
        More realistic for larger orders.
        """
        remaining = order.quantity
        total_value = 0.0
        
        if order.side == OrderSide.BUY:
            levels = book.asks
        else:
            levels = book.bids
            
        for level in levels:
            if remaining <= 0:
                break
                
            fill_at_level = min(remaining, level.size)
            total_value += fill_at_level * level.price
            remaining -= fill_at_level
            
        if remaining > 0:
            # Couldn't fill entire order
            return order
            
        order.avg_fill_price = total_value / order.quantity
        order.filled_quantity = order.quantity
        order.fill_timestamp = book.timestamp
        
        # Slippage is the difference from best price
        best_price = levels[0].price if levels else 0
        order.slippage = abs(order.avg_fill_price - best_price) * order.quantity
        
        # Commission
        order.commission = max(
            self.config.min_commission,
            order.quantity * self.config.commission_per_share
        )
        
        return order


class OrderFlowBacktester:
    """
    Backtester for order flow strategies.
    
    Features:
    - Realistic execution simulation
    - Risk management (stops, position limits)
    - Detailed trade logging
    - Performance analytics
    """
    
    def __init__(
        self,
        model: FlowModel,
        config: Optional[BacktestConfig] = None,
    ):
        self.model = model
        self.config = config or BacktestConfig()
        self.feature_engine = OrderFlowFeatureEngine()
        self.executor = ExecutionSimulator(self.config)
        
        # State
        self._capital = self.config.initial_capital
        self._positions: Dict[str, Trade] = {}
        self._trades: List[Trade] = []
        self._equity_curve: List[Tuple[datetime, float]] = []
        self._trade_counter = 0
        
    def run(
        self,
        data_iterator: Iterator[Tuple[OrderBookSnapshot, List[TradeEvent]]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            data_iterator: Iterator yielding (book_snapshot, trades) tuples
            progress_callback: Optional callback(current, total) for progress
            
        Returns:
            BacktestResult with all metrics
        """
        logger.info("Starting backtest...")
        
        start_time = None
        end_time = None
        processed = 0
        
        for book, trades in data_iterator:
            if start_time is None:
                start_time = book.timestamp
            end_time = book.timestamp
            
            # Process trades through feature engine
            for trade in trades:
                self.feature_engine.process_trade(trade, book)
                
            # Get features
            features = self.feature_engine.process_book_update(book)
            
            # Update existing positions
            self._update_positions(book)
            
            # Generate prediction
            if self.model.is_trained:
                prediction = self.model.predict(features)
                
                # Check for entry signal
                if self._should_enter(prediction, book):
                    self._enter_trade(prediction, features, book)
                    
            # Track equity
            equity = self._calculate_equity(book)
            self._equity_curve.append((book.timestamp, equity))
            
            processed += 1
            if progress_callback and processed % 1000 == 0:
                progress_callback(processed, processed)
                
        # Close any remaining positions
        for trade in list(self._positions.values()):
            self._close_trade(trade, book.mid_price, book.timestamp, "end_of_backtest")
            
        # Calculate results
        result = self._calculate_results(start_time, end_time)
        
        logger.info(f"Backtest complete: {len(self._trades)} trades, "
                   f"PnL: ${result.total_pnl:,.2f}")
        
        return result
    
    def _should_enter(
        self,
        prediction: ModelPrediction,
        book: OrderBookSnapshot,
    ) -> bool:
        """Check if we should enter a new trade."""
        # Check position limits
        if len(self._positions) >= self.config.max_positions:
            return False
            
        # Check signal strength
        if prediction.direction_confidence < self.config.min_confidence:
            return False
            
        # Need a directional prediction
        if prediction.direction in (None, "neutral"):
            return False
            
        # Check if already have position in this symbol
        if prediction.symbol in self._positions:
            return False
            
        return True
    
    def _enter_trade(
        self,
        prediction: ModelPrediction,
        features: FeatureSet,
        book: OrderBookSnapshot,
    ):
        """Enter a new trade."""
        self._trade_counter += 1
        trade_id = f"T{self._trade_counter:06d}"
        
        # Determine side and quantity
        side = OrderSide.BUY if prediction.direction == "up" else OrderSide.SELL
        
        # Position size based on capital
        max_position_value = self._capital * self.config.max_position_pct
        quantity = int(max_position_value / book.mid_price)
        
        if quantity <= 0:
            return
            
        # Create and execute order
        order = Order(
            id=f"O{self._trade_counter:06d}",
            symbol=prediction.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            timestamp=book.timestamp,
        )
        
        order = self.executor.execute_market_order(order, book)
        
        if not order.is_filled:
            return
            
        # Create trade
        trade = Trade(
            id=trade_id,
            symbol=prediction.symbol,
            side=side,
            entry_price=order.avg_fill_price,
            entry_time=book.timestamp,
            quantity=order.filled_quantity,
            commission=order.commission,
            slippage=order.slippage,
            signal_confidence=prediction.direction_confidence,
            prediction=prediction,
            features_at_entry=features.to_dict(),
        )
        
        self._positions[prediction.symbol] = trade
        self._capital -= order.commission + order.slippage
        
        logger.debug(f"Entered {trade.side.value} {trade.quantity} {trade.symbol} "
                    f"@ {trade.entry_price:.2f}")
    
    def _update_positions(self, book: OrderBookSnapshot):
        """Update and manage open positions."""
        for symbol, trade in list(self._positions.items()):
            if trade.symbol != book.symbol:
                continue
                
            current_price = book.mid_price
            
            # Calculate unrealized P&L
            if trade.side == OrderSide.BUY:
                trade.unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
            else:
                trade.unrealized_pnl = (trade.entry_price - current_price) * trade.quantity
                
            # Check stop loss
            if trade.unrealized_pnl / (trade.entry_price * trade.quantity) < -self.config.stop_loss_pct:
                self._close_trade(trade, current_price, book.timestamp, "stop_loss")
                continue
                
            # Check take profit
            if trade.unrealized_pnl / (trade.entry_price * trade.quantity) > self.config.take_profit_pct:
                self._close_trade(trade, current_price, book.timestamp, "take_profit")
                continue
                
            # Check max holding time
            holding_time = (book.timestamp - trade.entry_time).total_seconds()
            if holding_time > self.config.max_holding_seconds:
                self._close_trade(trade, current_price, book.timestamp, "max_time")
    
    def _close_trade(
        self,
        trade: Trade,
        exit_price: float,
        exit_time: datetime,
        reason: str,
    ):
        """Close a trade."""
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.status = TradeStatus.CLOSED
        trade.realized_pnl = trade.net_pnl
        
        # Update capital
        self._capital += trade.realized_pnl
        
        # Move to completed trades
        if trade.symbol in self._positions:
            del self._positions[trade.symbol]
        self._trades.append(trade)
        
        logger.debug(f"Closed {trade.symbol} ({reason}): PnL=${trade.realized_pnl:.2f}")
    
    def _calculate_equity(self, book: OrderBookSnapshot) -> float:
        """Calculate current equity."""
        equity = self._capital
        
        for trade in self._positions.values():
            if trade.symbol == book.symbol:
                equity += trade.unrealized_pnl
                
        return equity
    
    def _calculate_results(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> BacktestResult:
        """Calculate backtest results and metrics."""
        result = BacktestResult(
            config=self.config,
            trades=self._trades,
            start_time=start_time,
            end_time=end_time,
        )
        
        if not self._trades:
            return result
            
        # Basic metrics
        pnls = [t.net_pnl for t in self._trades]
        result.num_trades = len(self._trades)
        result.total_pnl = sum(pnls)
        result.total_return_pct = result.total_pnl / self.config.initial_capital * 100
        
        # Win/loss
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        result.win_rate = len(wins) / len(pnls) * 100 if pnls else 0
        result.avg_win = np.mean(wins) if wins else 0
        result.avg_loss = np.mean(losses) if losses else 0
        
        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Holding time
        holding_times = [
            t.holding_period.total_seconds() 
            for t in self._trades if t.holding_period
        ]
        result.avg_holding_seconds = np.mean(holding_times) if holding_times else 0
        
        # Consecutive losses
        max_consecutive = 0
        current_consecutive = 0
        for pnl in pnls:
            if pnl < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        result.max_consecutive_losses = max_consecutive
        
        # Sharpe/Sortino (annualized)
        if len(pnls) > 1:
            returns = np.array(pnls) / self.config.initial_capital
            
            # Assume 252 trading days, ~6.5 hours = ~23400 5-second bars
            annual_factor = np.sqrt(252 * 4680)  # Rough scaling
            
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return > 0:
                result.sharpe_ratio = mean_return / std_return * annual_factor
                
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0:
                downside_std = np.std(downside_returns)
                if downside_std > 0:
                    result.sortino_ratio = mean_return / downside_std * annual_factor
                    
        # Max drawdown
        if self._equity_curve:
            equities = [e for _, e in self._equity_curve]
            peak = equities[0]
            max_dd = 0
            
            for equity in equities:
                peak = max(peak, equity)
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
                
            result.max_drawdown_pct = max_dd * 100
            
        # VaR
        if pnls:
            result.var_95 = np.percentile(pnls, 5)
            
        return result
    
    def get_trade_log(self) -> List[Dict[str, Any]]:
        """Get detailed trade log."""
        return [t.to_dict() for t in self._trades]
    
    def get_equity_curve(self) -> List[Tuple[datetime, float]]:
        """Get equity curve data."""
        return self._equity_curve.copy()
    
    def save_results(self, path: Path):
        """Save backtest results to file."""
        data = {
            "trades": self.get_trade_log(),
            "equity_curve": [
                (t.isoformat(), e) for t, e in self._equity_curve
            ],
            "config": {
                "initial_capital": self.config.initial_capital,
                "max_position_pct": self.config.max_position_pct,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
            },
        }
        path.write_text(json.dumps(data, indent=2))


class WalkForwardOptimizer:
    """
    Walk-forward analysis for robust strategy evaluation.
    """
    
    def __init__(
        self,
        model_factory: Callable[[], FlowModel],
        train_period_days: int = 30,
        test_period_days: int = 5,
    ):
        self.model_factory = model_factory
        self.train_period_days = train_period_days
        self.test_period_days = test_period_days
        
    def run(
        self,
        X: np.ndarray,
        y: np.ndarray,
        timestamps: List[datetime],
        data_iterator_factory: Callable[[datetime, datetime], Iterator],
    ) -> List[BacktestResult]:
        """
        Run walk-forward optimization.
        
        Trains on rolling windows, tests on out-of-sample periods.
        """
        results = []
        
        # Get date range
        start_date = min(timestamps).date()
        end_date = max(timestamps).date()
        
        current_date = start_date + timedelta(days=self.train_period_days)
        
        while current_date + timedelta(days=self.test_period_days) <= end_date:
            # Training window
            train_start = current_date - timedelta(days=self.train_period_days)
            train_end = current_date
            
            # Test window
            test_start = current_date
            test_end = current_date + timedelta(days=self.test_period_days)
            
            logger.info(f"Walk-forward: Train {train_start} to {train_end}, "
                       f"Test {test_start} to {test_end}")
            
            # Get training data
            train_mask = [
                train_start <= t.date() < train_end
                for t in timestamps
            ]
            X_train = X[train_mask]
            y_train = y[train_mask]
            
            # Train model
            model = self.model_factory()
            model.train(X_train, y_train)
            
            # Backtest on test period
            backtester = OrderFlowBacktester(model)
            data_iter = data_iterator_factory(
                datetime.combine(test_start, datetime.min.time()),
                datetime.combine(test_end, datetime.min.time()),
            )
            
            result = backtester.run(data_iter)
            results.append(result)
            
            # Move forward
            current_date += timedelta(days=self.test_period_days)
            
        return results
    
    def aggregate_results(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Aggregate walk-forward results."""
        if not results:
            return {}
            
        all_pnl = sum(r.total_pnl for r in results)
        all_trades = sum(r.num_trades for r in results)
        win_rates = [r.win_rate for r in results if r.num_trades > 0]
        sharpes = [r.sharpe_ratio for r in results if r.num_trades > 5]
        
        return {
            "num_periods": len(results),
            "total_pnl": all_pnl,
            "total_trades": all_trades,
            "avg_win_rate": np.mean(win_rates) if win_rates else 0,
            "win_rate_std": np.std(win_rates) if win_rates else 0,
            "avg_sharpe": np.mean(sharpes) if sharpes else 0,
            "sharpe_std": np.std(sharpes) if sharpes else 0,
            "profitable_periods": sum(1 for r in results if r.total_pnl > 0),
            "profitable_period_pct": sum(1 for r in results if r.total_pnl > 0) / len(results) * 100,
        }
