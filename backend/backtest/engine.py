"""
QUANT INDUSTRY - Backtest Engine
Strategy backtesting with comprehensive performance metrics
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class Trade:
    timestamp: str
    symbol: str
    side: str
    quantity: int
    price: float
    value: float
    commission: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": round(self.price, 2),
            "value": round(self.value, 2),
            "commission": round(self.commission, 2),
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
        }


@dataclass
class Equity:
    timestamp: str
    equity: float
    cash: float
    positions_value: float
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    drawdown: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(self.positions_value, 2),
            "daily_return": round(self.daily_return, 4),
            "cumulative_return": round(self.cumulative_return, 4),
            "drawdown": round(self.drawdown, 4),
        }


@dataclass
class PerformanceMetrics:
    # Returns
    total_return: float
    annualized_return: float
    daily_return_mean: float
    daily_return_std: float

    # Risk
    volatility: float
    downside_volatility: float
    max_drawdown: float
    max_drawdown_duration: int
    var_95: float
    cvar_95: float

    # Ratios
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    profit_factor: float

    # Trades
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    avg_trade: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Exposure
    avg_exposure: float
    max_exposure: float

    def to_dict(self) -> Dict:
        return {
            "returns": {
                "total_return": round(self.total_return, 4),
                "annualized_return": round(self.annualized_return, 4),
                "daily_return_mean": round(self.daily_return_mean, 6),
                "daily_return_std": round(self.daily_return_std, 6),
            },
            "risk": {
                "volatility": round(self.volatility, 4),
                "downside_volatility": round(self.downside_volatility, 4),
                "max_drawdown": round(self.max_drawdown, 4),
                "max_drawdown_duration": self.max_drawdown_duration,
                "var_95": round(self.var_95, 4),
                "cvar_95": round(self.cvar_95, 4),
            },
            "ratios": {
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "sortino_ratio": round(self.sortino_ratio, 2),
                "calmar_ratio": round(self.calmar_ratio, 2),
                "profit_factor": round(self.profit_factor, 2),
            },
            "trades": {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "win_rate": round(self.win_rate, 4),
                "avg_win": round(self.avg_win, 2),
                "avg_loss": round(self.avg_loss, 2),
                "avg_trade": round(self.avg_trade, 2),
                "max_consecutive_wins": self.max_consecutive_wins,
                "max_consecutive_losses": self.max_consecutive_losses,
            },
            "exposure": {
                "avg_exposure": round(self.avg_exposure, 4),
                "max_exposure": round(self.max_exposure, 4),
            },
        }


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    commission_pct: float = 0.001  # 0.1% per trade
    slippage_pct: float = 0.0005  # 0.05% slippage
    position_size_pct: float = 10.0  # % of equity per position
    max_positions: int = 10
    risk_free_rate: float = 0.05

    def to_dict(self) -> Dict:
        return {
            "initial_capital": self.initial_capital,
            "commission_pct": self.commission_pct,
            "slippage_pct": self.slippage_pct,
            "position_size_pct": self.position_size_pct,
            "max_positions": self.max_positions,
            "risk_free_rate": self.risk_free_rate,
        }


@dataclass
class BacktestResult:
    config: BacktestConfig
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    trades: List[Trade]
    equity_curve: List[Equity]
    metrics: PerformanceMetrics

    def to_dict(self) -> Dict:
        return {
            "config": self.config.to_dict(),
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [e.to_dict() for e in self.equity_curve],
            "metrics": self.metrics.to_dict(),
        }


class BacktestEngine:
    """
    Vectorized backtest engine for strategy testing
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.reset()
        logger.info("BacktestEngine initialized")

    def reset(self):
        """Reset engine state"""
        self.cash = self.config.initial_capital
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Equity] = []
        self.high_water_mark = self.config.initial_capital

    def run(
        self,
        strategy,
        data: List[Dict],
        symbol: str = "UNKNOWN"
    ) -> BacktestResult:
        """
        Run backtest with given strategy and data

        Args:
            strategy: Strategy object with generate_signals method
            data: List of OHLCV dictionaries
            symbol: Symbol being tested
        """
        self.reset()

        if not data or len(data) < 2:
            raise ValueError("Insufficient data for backtest")

        # Prepare data arrays
        timestamps = [d.get("timestamp", d.get("date", "")) for d in data]
        opens = np.array([d.get("open", d.get("Open", 0)) for d in data])
        highs = np.array([d.get("high", d.get("High", 0)) for d in data])
        lows = np.array([d.get("low", d.get("Low", 0)) for d in data])
        closes = np.array([d.get("close", d.get("Close", 0)) for d in data])
        volumes = np.array([d.get("volume", d.get("Volume", 0)) for d in data])

        # Generate signals
        signals = strategy.generate_signals(opens, highs, lows, closes, volumes)

        # Run simulation
        for i in range(len(data)):
            timestamp = timestamps[i]
            price = closes[i]
            signal = signals[i] if i < len(signals) else 0

            # Process signal
            if signal > 0 and symbol not in self.positions:
                # Buy signal
                self._open_position(symbol, price, timestamp)
            elif signal < 0 and symbol in self.positions:
                # Sell signal
                self._close_position(symbol, price, timestamp)

            # Update equity
            self._update_equity(timestamp, {symbol: price})

        # Close any remaining positions
        if symbol in self.positions:
            self._close_position(symbol, closes[-1], timestamps[-1])
            self._update_equity(timestamps[-1], {symbol: closes[-1]})

        # Calculate metrics
        metrics = self._calculate_metrics()

        return BacktestResult(
            config=self.config,
            strategy_name=strategy.name,
            symbol=symbol,
            start_date=timestamps[0] if timestamps else "",
            end_date=timestamps[-1] if timestamps else "",
            trades=self.trades,
            equity_curve=self.equity_curve,
            metrics=metrics,
        )

    def _open_position(self, symbol: str, price: float, timestamp: str):
        """Open a new position"""
        # Calculate position size
        equity = self._calculate_equity({symbol: price})
        position_value = equity * (self.config.position_size_pct / 100)

        # Apply slippage
        fill_price = price * (1 + self.config.slippage_pct)

        quantity = int(position_value / fill_price)
        if quantity <= 0:
            return

        cost = quantity * fill_price
        commission = cost * self.config.commission_pct

        if cost + commission > self.cash:
            # Not enough cash
            quantity = int((self.cash - commission) / fill_price)
            if quantity <= 0:
                return
            cost = quantity * fill_price
            commission = cost * self.config.commission_pct

        self.cash -= (cost + commission)

        self.positions[symbol] = {
            "quantity": quantity,
            "entry_price": fill_price,
            "entry_time": timestamp,
        }

        self.trades.append(Trade(
            timestamp=timestamp,
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=fill_price,
            value=cost,
            commission=commission,
        ))

    def _close_position(self, symbol: str, price: float, timestamp: str):
        """Close an existing position"""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        quantity = position["quantity"]
        entry_price = position["entry_price"]

        # Apply slippage
        fill_price = price * (1 - self.config.slippage_pct)

        proceeds = quantity * fill_price
        commission = proceeds * self.config.commission_pct

        self.cash += (proceeds - commission)

        # Calculate P&L
        pnl = (fill_price - entry_price) * quantity - commission
        pnl_pct = (fill_price / entry_price - 1) * 100

        self.trades.append(Trade(
            timestamp=timestamp,
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            price=fill_price,
            value=proceeds,
            commission=commission,
            pnl=pnl,
            pnl_pct=pnl_pct,
        ))

        del self.positions[symbol]

    def _calculate_equity(self, prices: Dict[str, float]) -> float:
        """Calculate total equity"""
        positions_value = sum(
            pos["quantity"] * prices.get(sym, pos["entry_price"])
            for sym, pos in self.positions.items()
        )
        return self.cash + positions_value

    def _update_equity(self, timestamp: str, prices: Dict[str, float]):
        """Update equity curve"""
        positions_value = sum(
            pos["quantity"] * prices.get(sym, pos["entry_price"])
            for sym, pos in self.positions.items()
        )
        equity = self.cash + positions_value

        # Calculate returns and drawdown
        if self.equity_curve:
            prev_equity = self.equity_curve[-1].equity
            daily_return = (equity / prev_equity - 1) if prev_equity > 0 else 0
            cumulative_return = (equity / self.config.initial_capital - 1)
        else:
            daily_return = 0
            cumulative_return = 0

        # Update high water mark
        self.high_water_mark = max(self.high_water_mark, equity)

        drawdown = (self.high_water_mark - equity) / self.high_water_mark if self.high_water_mark > 0 else 0

        self.equity_curve.append(Equity(
            timestamp=timestamp,
            equity=equity,
            cash=self.cash,
            positions_value=positions_value,
            daily_return=daily_return,
            cumulative_return=cumulative_return,
            drawdown=drawdown,
        ))

    def _calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics"""
        if not self.equity_curve:
            return self._empty_metrics()

        equities = np.array([e.equity for e in self.equity_curve])
        returns = np.array([e.daily_return for e in self.equity_curve])
        drawdowns = np.array([e.drawdown for e in self.equity_curve])

        # Filter out zero returns at start
        returns = returns[returns != 0] if len(returns) > 0 else returns

        # Total return
        total_return = (equities[-1] / self.config.initial_capital - 1) if len(equities) > 0 else 0

        # Annualized return
        n_days = len(self.equity_curve)
        annualized_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1

        # Volatility
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0

        # Downside volatility
        negative_returns = returns[returns < 0]
        downside_volatility = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0

        # Max drawdown
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0

        # Max drawdown duration
        max_dd_duration = self._calculate_max_dd_duration(drawdowns)

        # VaR and CVaR
        var_95 = np.percentile(returns, 5) if len(returns) > 0 else 0
        cvar_95 = np.mean(returns[returns <= var_95]) if len(returns[returns <= var_95]) > 0 else 0

        # Sharpe ratio
        risk_free_daily = self.config.risk_free_rate / 252
        excess_returns = returns - risk_free_daily
        sharpe_ratio = (np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)) if np.std(excess_returns) > 0 else 0

        # Sortino ratio
        sortino_ratio = (np.mean(excess_returns) / downside_volatility * np.sqrt(252)) if downside_volatility > 0 else 0

        # Calmar ratio
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        # Trade statistics
        sell_trades = [t for t in self.trades if t.side == "SELL"]
        winning_trades = [t for t in sell_trades if t.pnl > 0]
        losing_trades = [t for t in sell_trades if t.pnl <= 0]

        total_trades = len(sell_trades)
        n_winning = len(winning_trades)
        n_losing = len(losing_trades)

        win_rate = n_winning / total_trades if total_trades > 0 else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        avg_trade = np.mean([t.pnl for t in sell_trades]) if sell_trades else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Consecutive wins/losses
        max_consec_wins, max_consec_losses = self._calculate_consecutive(sell_trades)

        # Exposure
        exposures = [e.positions_value / e.equity for e in self.equity_curve if e.equity > 0]
        avg_exposure = np.mean(exposures) if exposures else 0
        max_exposure = np.max(exposures) if exposures else 0

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            daily_return_mean=np.mean(returns) if len(returns) > 0 else 0,
            daily_return_std=np.std(returns) if len(returns) > 0 else 0,
            volatility=volatility,
            downside_volatility=downside_volatility,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            var_95=var_95,
            cvar_95=cvar_95,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=n_winning,
            losing_trades=n_losing,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade=avg_trade,
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            avg_exposure=avg_exposure,
            max_exposure=max_exposure,
        )

    def _calculate_max_dd_duration(self, drawdowns: np.ndarray) -> int:
        """Calculate maximum drawdown duration in days"""
        if len(drawdowns) == 0:
            return 0

        max_duration = 0
        current_duration = 0

        for dd in drawdowns:
            if dd > 0:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return max_duration

    def _calculate_consecutive(self, trades: List[Trade]) -> Tuple[int, int]:
        """Calculate max consecutive wins and losses"""
        if not trades:
            return 0, 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics"""
        return PerformanceMetrics(
            total_return=0, annualized_return=0, daily_return_mean=0,
            daily_return_std=0, volatility=0, downside_volatility=0,
            max_drawdown=0, max_drawdown_duration=0, var_95=0, cvar_95=0,
            sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0, profit_factor=0,
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0,
            avg_win=0, avg_loss=0, avg_trade=0, max_consecutive_wins=0,
            max_consecutive_losses=0, avg_exposure=0, max_exposure=0,
        )


# Singleton instance
_backtest_engine: Optional[BacktestEngine] = None

def get_backtest_engine(config: BacktestConfig = None) -> BacktestEngine:
    global _backtest_engine
    if _backtest_engine is None or config is not None:
        _backtest_engine = BacktestEngine(config)
    return _backtest_engine
