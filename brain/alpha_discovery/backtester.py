"""
QUANT_INDUSTRY_V1 Fast Vectorized Backtester

High-performance backtesting engine for hypothesis validation.

Features:
- Fully vectorized operations
- Multiple strategy types
- Transaction cost modeling
- Slippage simulation
- Walk-forward analysis
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import logging

from .hypothesis import AlphaHypothesis, HypothesisCondition

logger = logging.getLogger(__name__)


# =============================================================================
# BACKTEST RESULT
# =============================================================================

@dataclass
class BacktestResult:
    """Results from a backtest."""
    hypothesis_id: str
    start_date: datetime
    end_date: datetime

    # Returns
    total_return: float
    annualized_return: float
    daily_returns: np.ndarray

    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # In days
    volatility: float
    downside_volatility: float

    # Trade statistics
    num_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_trade_return: float
    avg_holding_period: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Statistical tests
    t_statistic: float
    p_value: float

    # Equity curve
    equity_curve: np.ndarray
    drawdown_curve: np.ndarray

    # Trade list
    trades: List[Dict[str, Any]] = field(default_factory=list)

    def is_valid(
        self,
        min_sharpe: float = 0.5,
        max_drawdown: float = -0.25,
        min_trades: int = 30,
        max_p_value: float = 0.05,
    ) -> bool:
        """Check if backtest passes validation criteria."""
        return (
            self.sharpe_ratio >= min_sharpe and
            self.max_drawdown >= max_drawdown and
            self.num_trades >= min_trades and
            self.p_value <= max_p_value
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'hypothesis_id': self.hypothesis_id,
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'max_drawdown': self.max_drawdown,
            'volatility': self.volatility,
            'num_trades': self.num_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'avg_trade_return': self.avg_trade_return,
            't_statistic': self.t_statistic,
            'p_value': self.p_value,
        }


# =============================================================================
# FAST BACKTESTER
# =============================================================================

class FastBacktester:
    """
    Vectorized backtesting engine for rapid hypothesis testing.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.001,  # 0.1% per trade
        slippage_rate: float = 0.0005,   # 0.05% slippage
        margin_requirement: float = 1.0,  # 1.0 = no margin
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.margin_requirement = margin_requirement

    def backtest(
        self,
        hypothesis: AlphaHypothesis,
        prices: np.ndarray,
        features: Dict[str, np.ndarray],
        dates: Optional[np.ndarray] = None,
    ) -> BacktestResult:
        """
        Run vectorized backtest of a hypothesis.

        Args:
            hypothesis: The trading hypothesis to test
            prices: Price array (close prices)
            features: Dictionary of feature arrays
            dates: Optional date array

        Returns:
            BacktestResult with all metrics
        """
        n = len(prices)
        if n < 10:
            return self._empty_result(hypothesis.hypothesis_id)

        # Calculate returns
        returns = np.diff(prices) / prices[:-1]

        # Generate signals
        entry_signals = hypothesis.evaluate_entry(features)
        exit_signals = hypothesis.evaluate_exit(features)

        # Trim to match returns length
        entry_signals = entry_signals[:n - 1]
        exit_signals = exit_signals[:n - 1]

        # Simulate trading
        positions, trades = self._simulate_trades(
            hypothesis=hypothesis,
            prices=prices,
            returns=returns,
            entry_signals=entry_signals,
            exit_signals=exit_signals,
        )

        # Calculate strategy returns
        strategy_returns = positions[:-1] * returns * hypothesis.direction

        # Apply transaction costs
        position_changes = np.abs(np.diff(np.concatenate([[0], positions])))
        costs = position_changes[:-1] * (self.commission_rate + self.slippage_rate)
        strategy_returns = strategy_returns - costs

        # Calculate metrics
        result = self._calculate_metrics(
            hypothesis_id=hypothesis.hypothesis_id,
            returns=strategy_returns,
            trades=trades,
            dates=dates,
        )

        return result

    def _simulate_trades(
        self,
        hypothesis: AlphaHypothesis,
        prices: np.ndarray,
        returns: np.ndarray,
        entry_signals: np.ndarray,
        exit_signals: np.ndarray,
    ) -> Tuple[np.ndarray, List[Dict]]:
        """
        Simulate trades based on signals.

        Returns: (positions array, list of trades)
        """
        n = len(prices)
        positions = np.zeros(n)
        trades = []

        in_position = False
        entry_price = 0.0
        entry_idx = 0
        holding_days = 0

        for i in range(n - 1):
            if not in_position:
                # Check entry
                if entry_signals[i]:
                    in_position = True
                    entry_price = prices[i]
                    entry_idx = i
                    positions[i] = hypothesis.position_size_pct
                    holding_days = 0
            else:
                holding_days += 1
                positions[i] = hypothesis.position_size_pct

                # Calculate current P&L
                current_return = (prices[i] - entry_price) / entry_price

                # Check exit conditions
                should_exit = False
                exit_reason = ""

                # Stop loss
                if hypothesis.direction * current_return <= -hypothesis.stop_loss_pct:
                    should_exit = True
                    exit_reason = "stop_loss"

                # Take profit
                elif hypothesis.direction * current_return >= hypothesis.take_profit_pct:
                    should_exit = True
                    exit_reason = "take_profit"

                # Max holding period
                elif holding_days >= hypothesis.max_holding_days:
                    should_exit = True
                    exit_reason = "max_holding"

                # Exit signal
                elif exit_signals[i]:
                    should_exit = True
                    exit_reason = "signal"

                if should_exit:
                    in_position = False
                    exit_price = prices[i]

                    trade_return = (exit_price - entry_price) / entry_price * hypothesis.direction

                    trades.append({
                        'entry_idx': entry_idx,
                        'exit_idx': i,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'return': trade_return,
                        'holding_days': holding_days,
                        'exit_reason': exit_reason,
                    })

        # Handle open position at end
        if in_position:
            positions[-1] = hypothesis.position_size_pct

        return positions, trades

    def _calculate_metrics(
        self,
        hypothesis_id: str,
        returns: np.ndarray,
        trades: List[Dict],
        dates: Optional[np.ndarray],
    ) -> BacktestResult:
        """Calculate all backtest metrics."""
        n = len(returns)

        if n == 0 or len(trades) == 0:
            return self._empty_result(hypothesis_id)

        # Basic stats
        total_return = np.prod(1 + returns) - 1
        mean_return = np.mean(returns)
        volatility = np.std(returns) * np.sqrt(252)

        # Annualized return
        trading_days = n
        years = trading_days / 252
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Sharpe ratio
        sharpe = mean_return / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        # Sortino ratio
        downside_returns = returns[returns < 0]
        downside_vol = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else volatility
        sortino = mean_return * 252 / downside_vol if downside_vol > 0 else sharpe

        # Drawdown analysis
        equity_curve = self.initial_capital * np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(equity_curve)
        drawdown_curve = (equity_curve - running_max) / running_max
        max_drawdown = np.min(drawdown_curve)

        # Max drawdown duration
        dd_duration = self._max_drawdown_duration(drawdown_curve)

        # Calmar ratio
        calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Trade statistics
        trade_returns = np.array([t['return'] for t in trades])
        num_trades = len(trades)

        winning_trades = trade_returns[trade_returns > 0]
        losing_trades = trade_returns[trade_returns <= 0]

        win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0
        avg_win = np.mean(winning_trades) if len(winning_trades) > 0 else 0
        avg_loss = np.mean(losing_trades) if len(losing_trades) > 0 else 0
        avg_trade_return = np.mean(trade_returns) if num_trades > 0 else 0

        # Profit factor
        gross_profit = np.sum(winning_trades) if len(winning_trades) > 0 else 0
        gross_loss = abs(np.sum(losing_trades)) if len(losing_trades) > 0 else 1e-10
        profit_factor = gross_profit / gross_loss

        # Consecutive wins/losses
        max_wins, max_losses = self._consecutive_trades(trade_returns)

        # Avg holding period
        avg_holding = np.mean([t['holding_days'] for t in trades])

        # Statistical tests
        t_stat, p_value = self._t_test(trade_returns)

        # Dates
        start_date = dates[0] if dates is not None else datetime.now(timezone.utc)
        end_date = dates[-1] if dates is not None else datetime.now(timezone.utc)

        return BacktestResult(
            hypothesis_id=hypothesis_id,
            start_date=start_date,
            end_date=end_date,
            total_return=total_return,
            annualized_return=annualized_return,
            daily_returns=returns,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_drawdown,
            max_drawdown_duration=dd_duration,
            volatility=volatility,
            downside_volatility=downside_vol,
            num_trades=num_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade_return=avg_trade_return,
            avg_holding_period=avg_holding,
            max_consecutive_wins=max_wins,
            max_consecutive_losses=max_losses,
            t_statistic=t_stat,
            p_value=p_value,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            trades=trades,
        )

    def _empty_result(self, hypothesis_id: str) -> BacktestResult:
        """Create empty result for invalid backtests."""
        return BacktestResult(
            hypothesis_id=hypothesis_id,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            total_return=0.0,
            annualized_return=0.0,
            daily_returns=np.array([]),
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            volatility=0.0,
            downside_volatility=0.0,
            num_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            avg_trade_return=0.0,
            avg_holding_period=0.0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            t_statistic=0.0,
            p_value=1.0,
            equity_curve=np.array([]),
            drawdown_curve=np.array([]),
        )

    def _max_drawdown_duration(self, drawdown_curve: np.ndarray) -> int:
        """Calculate maximum drawdown duration in days."""
        in_drawdown = drawdown_curve < 0
        max_duration = 0
        current_duration = 0

        for dd in in_drawdown:
            if dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return max_duration

    def _consecutive_trades(self, trade_returns: np.ndarray) -> Tuple[int, int]:
        """Calculate max consecutive wins and losses."""
        if len(trade_returns) == 0:
            return 0, 0

        wins = trade_returns > 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for is_win in wins:
            if is_win:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def _t_test(self, returns: np.ndarray) -> Tuple[float, float]:
        """Perform t-test on returns."""
        n = len(returns)
        if n < 2:
            return 0.0, 1.0

        mean = np.mean(returns)
        std = np.std(returns, ddof=1)

        if std == 0:
            return 0.0, 1.0

        t_stat = mean / (std / np.sqrt(n))

        # Approximate p-value
        p_value = 2 * (1 - self._normal_cdf(abs(t_stat)))

        return t_stat, p_value

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF."""
        return 0.5 * (1 + np.tanh(0.797884560802865 * x * (1 + 0.0356774 * x * x)))


# =============================================================================
# WALK-FORWARD ANALYZER
# =============================================================================

class WalkForwardAnalyzer:
    """
    Walk-forward analysis for robust out-of-sample validation.
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_ratio: float = 0.7,
        min_train_samples: int = 252,
    ):
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.min_train_samples = min_train_samples

    def analyze(
        self,
        hypothesis: AlphaHypothesis,
        prices: np.ndarray,
        features: Dict[str, np.ndarray],
        backtester: FastBacktester,
    ) -> Dict[str, Any]:
        """
        Perform walk-forward analysis.

        Returns aggregated out-of-sample statistics.
        """
        n = len(prices)
        split_size = n // self.n_splits

        if split_size < self.min_train_samples:
            return {'valid': False, 'reason': 'insufficient_data'}

        oos_results = []

        for i in range(self.n_splits):
            split_start = i * split_size
            split_end = min((i + 1) * split_size, n)

            train_end = split_start + int((split_end - split_start) * self.train_ratio)

            # Test on out-of-sample portion
            test_prices = prices[train_end:split_end]
            test_features = {k: v[train_end:split_end] for k, v in features.items()}

            if len(test_prices) < 20:
                continue

            result = backtester.backtest(
                hypothesis=hypothesis,
                prices=test_prices,
                features=test_features,
            )

            if result.num_trades > 0:
                oos_results.append(result)

        if len(oos_results) == 0:
            return {'valid': False, 'reason': 'no_oos_trades'}

        # Aggregate results
        all_returns = np.concatenate([r.daily_returns for r in oos_results])
        total_trades = sum(r.num_trades for r in oos_results)

        aggregate_sharpe = np.mean([r.sharpe_ratio for r in oos_results])
        aggregate_sortino = np.mean([r.sortino_ratio for r in oos_results])
        aggregate_dd = np.min([r.max_drawdown for r in oos_results])
        aggregate_win_rate = np.mean([r.win_rate for r in oos_results])

        # Consistency across splits
        profitable_splits = sum(1 for r in oos_results if r.total_return > 0)
        consistency = profitable_splits / len(oos_results)

        return {
            'valid': True,
            'n_splits': len(oos_results),
            'total_trades': total_trades,
            'oos_sharpe': aggregate_sharpe,
            'oos_sortino': aggregate_sortino,
            'oos_max_drawdown': aggregate_dd,
            'oos_win_rate': aggregate_win_rate,
            'consistency': consistency,
            'profitable_splits': profitable_splits,
            'split_results': [r.to_dict() for r in oos_results],
        }


# =============================================================================
# MONTE CARLO SIMULATOR
# =============================================================================

class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy robustness testing.
    """

    def __init__(self, n_simulations: int = 1000, seed: int = None):
        self.n_simulations = n_simulations
        self.rng = np.random.default_rng(seed)

    def simulate_returns(
        self,
        base_returns: np.ndarray,
        method: str = "bootstrap",
    ) -> np.ndarray:
        """
        Generate simulated return paths.

        Methods:
        - bootstrap: Random sampling with replacement
        - shuffle: Random permutation
        - parametric: Fit distribution and sample

        Returns: (n_simulations, n_periods) array
        """
        n = len(base_returns)

        if method == "bootstrap":
            indices = self.rng.integers(0, n, size=(self.n_simulations, n))
            return base_returns[indices]

        elif method == "shuffle":
            simulated = np.zeros((self.n_simulations, n))
            for i in range(self.n_simulations):
                simulated[i] = self.rng.permutation(base_returns)
            return simulated

        elif method == "parametric":
            mean = np.mean(base_returns)
            std = np.std(base_returns)
            return self.rng.normal(mean, std, size=(self.n_simulations, n))

        return np.tile(base_returns, (self.n_simulations, 1))

    def run_simulation(
        self,
        backtest_result: BacktestResult,
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation on backtest results.
        """
        if len(backtest_result.daily_returns) < 30:
            return {'valid': False, 'reason': 'insufficient_data'}

        # Simulate paths
        simulated_returns = self.simulate_returns(
            backtest_result.daily_returns,
            method="bootstrap"
        )

        # Calculate metrics for each simulation
        sharpes = []
        max_dds = []
        total_returns = []

        for sim_returns in simulated_returns:
            mean_ret = np.mean(sim_returns)
            std_ret = np.std(sim_returns)

            sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0
            sharpes.append(sharpe)

            equity = np.cumprod(1 + sim_returns)
            running_max = np.maximum.accumulate(equity)
            dd = (equity - running_max) / running_max
            max_dds.append(np.min(dd))

            total_returns.append(equity[-1] - 1)

        sharpes = np.array(sharpes)
        max_dds = np.array(max_dds)
        total_returns = np.array(total_returns)

        # Calculate confidence intervals
        return {
            'valid': True,
            'sharpe_mean': np.mean(sharpes),
            'sharpe_std': np.std(sharpes),
            'sharpe_5pct': np.percentile(sharpes, 5),
            'sharpe_95pct': np.percentile(sharpes, 95),
            'max_dd_mean': np.mean(max_dds),
            'max_dd_5pct': np.percentile(max_dds, 5),
            'max_dd_95pct': np.percentile(max_dds, 95),
            'return_mean': np.mean(total_returns),
            'return_5pct': np.percentile(total_returns, 5),
            'return_95pct': np.percentile(total_returns, 95),
            'prob_profitable': np.mean(total_returns > 0),
            'prob_sharpe_positive': np.mean(sharpes > 0),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BacktestResult',
    'FastBacktester',
    'WalkForwardAnalyzer',
    'MonteCarloSimulator',
]
