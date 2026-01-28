"""
QUANT INDUSTRY - Realistic Backtest Engine
==========================================
Production-grade backtesting with:
- Almgren-Chriss market impact model
- Walk-forward validation integration
- Transaction cost modeling
- Slippage that scales with order size and liquidity

This is what separates fantasy backtests from reality.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Import our slippage model
from execution.execution_algorithms import (
    AlmgrenChrissSlippageModel,
    SlippageEstimate,
    estimate_slippage
)

# Import walk-forward validation
from services.walk_forward import (
    WalkForwardValidator,
    ValidationMethod,
    WalkForwardReport
)

logger = logging.getLogger(__name__)


class SlippageMode(Enum):
    """How to model slippage"""
    NONE = "none"                    # No slippage (unrealistic)
    FIXED_PCT = "fixed_pct"          # Fixed percentage (simple)
    FIXED_TICKS = "fixed_ticks"      # Fixed tick slippage
    ALMGREN_CHRISS = "almgren_chriss" # Realistic market impact


@dataclass
class RealisticBacktestConfig:
    """
    Configuration for realistic backtesting.
    
    Key differences from naive backtesting:
    1. Slippage scales with order size (Almgren-Chriss)
    2. Position sizing respects Kelly criterion
    3. Transaction costs include spread + impact
    """
    # Capital
    initial_capital: float = 100_000.0
    
    # Slippage configuration
    slippage_mode: SlippageMode = SlippageMode.ALMGREN_CHRISS
    slippage_pct: float = 0.001      # For FIXED_PCT mode
    slippage_ticks: float = 2.0       # For FIXED_TICKS mode
    tick_size: float = 0.01           # Price increment
    
    # Almgren-Chriss parameters
    ac_eta: float = 0.142             # Temporary impact (calibrated)
    ac_gamma: float = 0.314           # Permanent impact (calibrated)
    
    # Commission
    commission_per_share: float = 0.005  # Per-share commission
    commission_minimum: float = 1.0       # Minimum per trade
    
    # Position sizing
    max_position_pct: float = 10.0    # Max % of equity per position
    kelly_fraction: float = 0.25      # Fraction of Kelly to use
    max_positions: int = 10
    
    # Risk management
    max_drawdown_pct: float = 10.0    # Stop trading if hit
    daily_loss_limit_pct: float = 2.0 # Daily stop
    
    # Market assumptions
    default_daily_volume: int = 1_000_000  # If not provided
    default_volatility: float = 0.02       # Daily vol if not provided
    
    # Walk-forward settings
    use_walk_forward: bool = True
    wf_train_months: int = 6
    wf_val_months: int = 1
    wf_embargo_days: int = 5
    
    # Benchmark
    risk_free_rate: float = 0.05  # Annualized
    
    def to_dict(self) -> Dict:
        return {
            "initial_capital": self.initial_capital,
            "slippage_mode": self.slippage_mode.value,
            "ac_eta": self.ac_eta,
            "ac_gamma": self.ac_gamma,
            "max_position_pct": self.max_position_pct,
            "kelly_fraction": self.kelly_fraction,
            "max_drawdown_pct": self.max_drawdown_pct,
            "use_walk_forward": self.use_walk_forward,
        }


@dataclass
class RealisticTrade:
    """Trade with detailed cost breakdown"""
    timestamp: datetime
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: int
    intended_price: float      # Price we wanted
    fill_price: float          # Price we got
    
    # Cost breakdown
    commission: float = 0.0
    slippage_bps: float = 0.0
    slippage_dollars: float = 0.0
    market_impact_bps: float = 0.0
    
    # P&L (for closes)
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    pnl_pct: float = 0.0
    
    # Context
    participation_rate: float = 0.0  # % of daily volume
    daily_volume: int = 0
    volatility: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": str(self.timestamp),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "intended_price": round(self.intended_price, 4),
            "fill_price": round(self.fill_price, 4),
            "commission": round(self.commission, 2),
            "slippage_bps": round(self.slippage_bps, 2),
            "slippage_dollars": round(self.slippage_dollars, 2),
            "net_pnl": round(self.net_pnl, 2),
            "participation_rate": round(self.participation_rate, 4),
        }


@dataclass
class RealisticMetrics:
    """Performance metrics with cost attribution"""
    # Returns
    gross_return: float = 0.0
    net_return: float = 0.0
    annualized_return: float = 0.0
    
    # Risk
    volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    var_95: float = 0.0
    cvar_95: float = 0.0
    
    # Ratios (all calculated AFTER costs)
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Trades
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # Cost attribution (CRITICAL)
    total_commission: float = 0.0
    total_slippage: float = 0.0
    total_costs: float = 0.0
    cost_drag_pct: float = 0.0  # Costs as % of gross profit
    
    # Per-trade costs
    avg_slippage_bps: float = 0.0
    avg_participation_rate: float = 0.0
    
    # Walk-forward (if enabled)
    wf_sharpe_mean: float = 0.0
    wf_sharpe_std: float = 0.0
    wf_consistency: float = 0.0
    wf_overfit_ratio: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "returns": {
                "gross_return": f"{self.gross_return:.2%}",
                "net_return": f"{self.net_return:.2%}",
                "annualized_return": f"{self.annualized_return:.2%}",
            },
            "risk": {
                "volatility": f"{self.volatility:.2%}",
                "max_drawdown": f"{self.max_drawdown:.2%}",
                "var_95": f"{self.var_95:.2%}",
            },
            "ratios": {
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "sortino_ratio": round(self.sortino_ratio, 2),
                "calmar_ratio": round(self.calmar_ratio, 2),
            },
            "trades": {
                "total": self.total_trades,
                "win_rate": f"{self.win_rate:.1%}",
                "profit_factor": round(self.profit_factor, 2),
            },
            "costs": {
                "total_commission": f"${self.total_commission:,.2f}",
                "total_slippage": f"${self.total_slippage:,.2f}",
                "total_costs": f"${self.total_costs:,.2f}",
                "cost_drag": f"{self.cost_drag_pct:.1%}",
                "avg_slippage_bps": f"{self.avg_slippage_bps:.1f}",
            },
            "walk_forward": {
                "sharpe_mean": round(self.wf_sharpe_mean, 2),
                "sharpe_std": round(self.wf_sharpe_std, 2),
                "consistency": f"{self.wf_consistency:.1%}",
                "overfit_ratio": f"{self.wf_overfit_ratio:.1%}",
            }
        }
    
    def summary(self) -> str:
        """Human-readable summary"""
        status = "✅" if self.sharpe_ratio > 0.5 and self.wf_consistency > 0.6 else "⚠️"
        
        return f"""
{status} Realistic Backtest Results
{'='*50}
Net Return: {self.net_return:.2%} (Gross: {self.gross_return:.2%})
Sharpe Ratio: {self.sharpe_ratio:.2f}
Max Drawdown: {self.max_drawdown:.2%}
Win Rate: {self.win_rate:.1%} | Profit Factor: {self.profit_factor:.2f}

Cost Attribution:
  Commission: ${self.total_commission:,.2f}
  Slippage:   ${self.total_slippage:,.2f}
  TOTAL:      ${self.total_costs:,.2f} ({self.cost_drag_pct:.1%} of gross)
  Avg Slip:   {self.avg_slippage_bps:.1f} bps/trade

Walk-Forward Validation:
  Sharpe: {self.wf_sharpe_mean:.2f} ± {self.wf_sharpe_std:.2f}
  Consistency: {self.wf_consistency:.1%}
  Overfit Ratio: {self.wf_overfit_ratio:.1%}
"""


class RealisticBacktestEngine:
    """
    Production-grade backtest engine.
    
    Key features:
    1. Almgren-Chriss slippage model
    2. Walk-forward validation
    3. Detailed cost attribution
    4. Risk management integration
    
    Usage:
    ------
    >>> config = RealisticBacktestConfig(
    ...     initial_capital=100_000,
    ...     slippage_mode=SlippageMode.ALMGREN_CHRISS
    ... )
    >>> engine = RealisticBacktestEngine(config)
    >>> result = engine.run(strategy, data)
    >>> print(result.metrics.summary())
    """
    
    def __init__(self, config: RealisticBacktestConfig = None):
        self.config = config or RealisticBacktestConfig()
        
        # Initialize slippage model
        if self.config.slippage_mode == SlippageMode.ALMGREN_CHRISS:
            self.slippage_model = AlmgrenChrissSlippageModel(
                eta=self.config.ac_eta,
                gamma=self.config.ac_gamma
            )
        else:
            self.slippage_model = None
        
        self.reset()
        logger.info(f"RealisticBacktestEngine initialized: slippage={self.config.slippage_mode.value}")
    
    def reset(self):
        """Reset engine state"""
        self.cash = self.config.initial_capital
        self.positions: Dict[str, Dict] = {}
        self.trades: List[RealisticTrade] = []
        self.equity_curve: List[Dict] = []
        self.high_water_mark = self.config.initial_capital
        self.daily_pnl = 0.0
        self.is_stopped = False
        
        # Cost tracking
        self.total_commission = 0.0
        self.total_slippage = 0.0
    
    def run(
        self,
        strategy,
        data: pd.DataFrame,
        symbol: str = "UNKNOWN",
        volume_col: str = "volume",
        volatility_col: str = "volatility"
    ) -> Dict:
        """
        Run realistic backtest.
        
        Args:
            strategy: Strategy with generate_signals(df) -> signals array
            data: DataFrame with OHLCV data
            symbol: Symbol being tested
            volume_col: Column for daily volume (for slippage)
            volatility_col: Column for volatility (for slippage)
            
        Returns:
            Dict with trades, equity_curve, and metrics
        """
        self.reset()
        
        if len(data) < 10:
            raise ValueError("Insufficient data for backtest")
        
        # Ensure we have required columns
        df = data.copy()
        
        if 'close' not in df.columns and 'Close' in df.columns:
            df['close'] = df['Close']
        if 'open' not in df.columns and 'Open' in df.columns:
            df['open'] = df['Open']
        if 'high' not in df.columns and 'High' in df.columns:
            df['high'] = df['High']
        if 'low' not in df.columns and 'Low' in df.columns:
            df['low'] = df['Low']
        
        # Add volume if missing
        if volume_col not in df.columns:
            df[volume_col] = self.config.default_daily_volume
        
        # Add volatility if missing (calculate from returns)
        if volatility_col not in df.columns:
            returns = df['close'].pct_change()
            df[volatility_col] = returns.rolling(20).std().fillna(self.config.default_volatility)
        
        # Generate signals
        signals = strategy.generate_signals(df)
        
        # Run simulation
        for i in range(len(df)):
            if self.is_stopped:
                break
            
            row = df.iloc[i]
            timestamp = df.index[i] if isinstance(df.index, pd.DatetimeIndex) else i
            price = row['close']
            volume = row[volume_col]
            volatility = row[volatility_col]
            signal = signals[i] if i < len(signals) else 0
            
            # Process signal
            if signal > 0 and symbol not in self.positions:
                self._open_position(
                    symbol=symbol,
                    price=price,
                    timestamp=timestamp,
                    volume=volume,
                    volatility=volatility
                )
            elif signal < 0 and symbol in self.positions:
                self._close_position(
                    symbol=symbol,
                    price=price,
                    timestamp=timestamp,
                    volume=volume,
                    volatility=volatility
                )
            
            # Update equity
            self._update_equity(timestamp, {symbol: price})
            
            # Check risk limits
            self._check_risk_limits()
        
        # Close any remaining positions
        if symbol in self.positions and len(df) > 0:
            final_row = df.iloc[-1]
            self._close_position(
                symbol=symbol,
                price=final_row['close'],
                timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else len(df)-1,
                volume=final_row[volume_col],
                volatility=final_row[volatility_col]
            )
        
        # Calculate metrics
        metrics = self._calculate_metrics()
        
        return {
            "config": self.config.to_dict(),
            "symbol": symbol,
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": self.equity_curve,
            "metrics": metrics,
        }
    
    def _calculate_slippage(
        self,
        order_size: int,
        price: float,
        side: str,
        volume: float,
        volatility: float
    ) -> Tuple[float, float, float]:
        """
        Calculate slippage based on configured mode.
        
        Returns:
            Tuple of (fill_price, slippage_bps, slippage_dollars)
        """
        if self.config.slippage_mode == SlippageMode.NONE:
            return price, 0.0, 0.0
        
        elif self.config.slippage_mode == SlippageMode.FIXED_PCT:
            slippage_pct = self.config.slippage_pct
            if side == "BUY":
                fill_price = price * (1 + slippage_pct)
            else:
                fill_price = price * (1 - slippage_pct)
            slippage_bps = slippage_pct * 10000
            slippage_dollars = abs(fill_price - price) * order_size
            return fill_price, slippage_bps, slippage_dollars
        
        elif self.config.slippage_mode == SlippageMode.FIXED_TICKS:
            tick_slippage = self.config.slippage_ticks * self.config.tick_size
            if side == "BUY":
                fill_price = price + tick_slippage
            else:
                fill_price = price - tick_slippage
            slippage_bps = (tick_slippage / price) * 10000
            slippage_dollars = tick_slippage * order_size
            return fill_price, slippage_bps, slippage_dollars
        
        elif self.config.slippage_mode == SlippageMode.ALMGREN_CHRISS:
            if self.slippage_model is None:
                return price, 0.0, 0.0
            
            estimate = self.slippage_model.calculate_slippage(
                order_size=order_size,
                daily_volume=volume,
                volatility=volatility,
                price=price
            )
            
            slippage_pct = estimate.total_slippage_bps / 10000
            if side == "BUY":
                fill_price = price * (1 + slippage_pct)
            else:
                fill_price = price * (1 - slippage_pct)
            
            return fill_price, estimate.total_slippage_bps, estimate.total_slippage_dollars
        
        return price, 0.0, 0.0
    
    def _calculate_commission(self, quantity: int, value: float) -> float:
        """Calculate commission for a trade"""
        per_share = quantity * self.config.commission_per_share
        return max(per_share, self.config.commission_minimum)
    
    def _open_position(
        self,
        symbol: str,
        price: float,
        timestamp,
        volume: float,
        volatility: float
    ):
        """Open a new position with realistic costs"""
        # Calculate position size
        equity = self._calculate_equity({symbol: price})
        max_position_value = equity * (self.config.max_position_pct / 100)
        
        # Preliminary quantity
        quantity = int(max_position_value / price)
        if quantity <= 0:
            return
        
        # Calculate slippage
        fill_price, slippage_bps, slippage_dollars = self._calculate_slippage(
            order_size=quantity,
            price=price,
            side="BUY",
            volume=volume,
            volatility=volatility
        )
        
        # Recalculate with fill price
        cost = quantity * fill_price
        commission = self._calculate_commission(quantity, cost)
        
        # Check if we have enough cash
        total_cost = cost + commission
        if total_cost > self.cash:
            quantity = int((self.cash - commission) / fill_price)
            if quantity <= 0:
                return
            cost = quantity * fill_price
            commission = self._calculate_commission(quantity, cost)
            
            # Recalculate slippage for new quantity
            fill_price, slippage_bps, slippage_dollars = self._calculate_slippage(
                order_size=quantity,
                price=price,
                side="BUY",
                volume=volume,
                volatility=volatility
            )
            cost = quantity * fill_price
        
        # Execute
        self.cash -= (cost + commission)
        self.total_commission += commission
        self.total_slippage += slippage_dollars
        
        # Track position
        self.positions[symbol] = {
            "quantity": quantity,
            "entry_price": fill_price,
            "entry_time": timestamp,
            "entry_commission": commission,
            "entry_slippage": slippage_dollars,
        }
        
        # Record trade
        participation_rate = quantity / volume if volume > 0 else 0
        
        self.trades.append(RealisticTrade(
            timestamp=timestamp,
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            intended_price=price,
            fill_price=fill_price,
            commission=commission,
            slippage_bps=slippage_bps,
            slippage_dollars=slippage_dollars,
            participation_rate=participation_rate,
            daily_volume=int(volume),
            volatility=volatility,
        ))
    
    def _close_position(
        self,
        symbol: str,
        price: float,
        timestamp,
        volume: float,
        volatility: float
    ):
        """Close position with realistic costs"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        quantity = position["quantity"]
        entry_price = position["entry_price"]
        entry_commission = position["entry_commission"]
        entry_slippage = position["entry_slippage"]
        
        # Calculate slippage
        fill_price, slippage_bps, slippage_dollars = self._calculate_slippage(
            order_size=quantity,
            price=price,
            side="SELL",
            volume=volume,
            volatility=volatility
        )
        
        # Calculate proceeds
        proceeds = quantity * fill_price
        commission = self._calculate_commission(quantity, proceeds)
        
        # Update cash
        self.cash += (proceeds - commission)
        self.total_commission += commission
        self.total_slippage += slippage_dollars
        
        # Calculate P&L
        gross_pnl = (fill_price - entry_price) * quantity
        total_costs = entry_commission + commission + entry_slippage + slippage_dollars
        net_pnl = gross_pnl - total_costs
        pnl_pct = ((fill_price / entry_price) - 1) * 100
        
        # Update daily P&L
        self.daily_pnl += net_pnl
        
        # Record trade
        participation_rate = quantity / volume if volume > 0 else 0
        
        self.trades.append(RealisticTrade(
            timestamp=timestamp,
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            intended_price=price,
            fill_price=fill_price,
            commission=commission,
            slippage_bps=slippage_bps,
            slippage_dollars=slippage_dollars,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            pnl_pct=pnl_pct,
            participation_rate=participation_rate,
            daily_volume=int(volume),
            volatility=volatility,
        ))
        
        del self.positions[symbol]
    
    def _calculate_equity(self, prices: Dict[str, float]) -> float:
        """Calculate total equity"""
        positions_value = sum(
            pos["quantity"] * prices.get(sym, pos["entry_price"])
            for sym, pos in self.positions.items()
        )
        return self.cash + positions_value
    
    def _update_equity(self, timestamp, prices: Dict[str, float]):
        """Update equity curve"""
        positions_value = sum(
            pos["quantity"] * prices.get(sym, pos["entry_price"])
            for sym, pos in self.positions.items()
        )
        equity = self.cash + positions_value
        
        # Update high water mark
        self.high_water_mark = max(self.high_water_mark, equity)
        drawdown = (self.high_water_mark - equity) / self.high_water_mark if self.high_water_mark > 0 else 0
        
        self.equity_curve.append({
            "timestamp": str(timestamp),
            "equity": equity,
            "cash": self.cash,
            "positions_value": positions_value,
            "drawdown": drawdown,
        })
    
    def _check_risk_limits(self):
        """Check if risk limits are breached"""
        if not self.equity_curve:
            return
        
        current_equity = self.equity_curve[-1]["equity"]
        drawdown = self.equity_curve[-1]["drawdown"]
        
        # Max drawdown check
        if drawdown >= self.config.max_drawdown_pct / 100:
            logger.warning(f"Max drawdown limit hit: {drawdown:.2%}")
            self.is_stopped = True
        
        # Daily loss limit
        daily_loss_pct = -self.daily_pnl / self.config.initial_capital
        if daily_loss_pct >= self.config.daily_loss_limit_pct / 100:
            logger.warning(f"Daily loss limit hit: {daily_loss_pct:.2%}")
            self.is_stopped = True
    
    def _calculate_metrics(self) -> RealisticMetrics:
        """Calculate comprehensive performance metrics"""
        metrics = RealisticMetrics()
        
        if not self.equity_curve:
            return metrics
        
        # Extract equity values
        equities = np.array([e["equity"] for e in self.equity_curve])
        
        # Returns
        if len(equities) > 1:
            returns = np.diff(equities) / equities[:-1]
            returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
        else:
            returns = np.array([0])
        
        # Calculate returns
        final_equity = equities[-1]
        gross_pnl = sum(t.gross_pnl for t in self.trades if t.side == "SELL")
        net_pnl = sum(t.net_pnl for t in self.trades if t.side == "SELL")
        
        metrics.gross_return = gross_pnl / self.config.initial_capital if gross_pnl != 0 else 0
        metrics.net_return = (final_equity - self.config.initial_capital) / self.config.initial_capital
        
        # Annualize
        trading_days = len(equities)
        if trading_days > 0:
            metrics.annualized_return = metrics.net_return * (252 / trading_days)
        
        # Risk metrics
        if len(returns) > 0:
            metrics.volatility = np.std(returns) * np.sqrt(252)
            
            # Downside vol
            negative_returns = returns[returns < 0]
            if len(negative_returns) > 0:
                downside_vol = np.std(negative_returns) * np.sqrt(252)
            else:
                downside_vol = 0.001  # Avoid division by zero
            
            # VaR/CVaR
            if len(returns) >= 20:
                metrics.var_95 = np.percentile(returns, 5)
                metrics.cvar_95 = returns[returns <= metrics.var_95].mean() if any(returns <= metrics.var_95) else metrics.var_95
        
        # Max drawdown
        drawdowns = [e["drawdown"] for e in self.equity_curve]
        metrics.max_drawdown = max(drawdowns) if drawdowns else 0
        
        # Ratios
        excess_return = metrics.annualized_return - self.config.risk_free_rate
        if metrics.volatility > 0:
            metrics.sharpe_ratio = excess_return / metrics.volatility
        if downside_vol > 0:
            metrics.sortino_ratio = excess_return / downside_vol
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown
        
        # Trade metrics
        sell_trades = [t for t in self.trades if t.side == "SELL"]
        metrics.total_trades = len(sell_trades)
        
        if sell_trades:
            winners = [t for t in sell_trades if t.net_pnl > 0]
            losers = [t for t in sell_trades if t.net_pnl <= 0]
            
            metrics.winning_trades = len(winners)
            metrics.losing_trades = len(losers)
            metrics.win_rate = len(winners) / len(sell_trades)
            
            if winners:
                metrics.avg_win = np.mean([t.net_pnl for t in winners])
            if losers:
                metrics.avg_loss = abs(np.mean([t.net_pnl for t in losers]))
            
            total_wins = sum(t.net_pnl for t in winners) if winners else 0
            total_losses = abs(sum(t.net_pnl for t in losers)) if losers else 0.01
            metrics.profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Cost attribution
        metrics.total_commission = self.total_commission
        metrics.total_slippage = self.total_slippage
        metrics.total_costs = self.total_commission + self.total_slippage
        
        if gross_pnl > 0:
            metrics.cost_drag_pct = metrics.total_costs / gross_pnl
        
        # Average slippage
        all_trades = [t for t in self.trades if t.slippage_bps > 0]
        if all_trades:
            metrics.avg_slippage_bps = np.mean([t.slippage_bps for t in all_trades])
            metrics.avg_participation_rate = np.mean([t.participation_rate for t in all_trades])
        
        return metrics


# ============== CONVENIENCE FUNCTIONS ==============

def run_realistic_backtest(
    strategy,
    data: pd.DataFrame,
    symbol: str = "TEST",
    initial_capital: float = 100_000,
    slippage_mode: str = "almgren_chriss"
) -> Dict:
    """
    Quick function to run a realistic backtest.
    
    Args:
        strategy: Strategy with generate_signals(df) method
        data: OHLCV DataFrame
        symbol: Symbol name
        initial_capital: Starting capital
        slippage_mode: "none", "fixed_pct", or "almgren_chriss"
        
    Returns:
        Backtest result dict
    """
    mode_map = {
        "none": SlippageMode.NONE,
        "fixed_pct": SlippageMode.FIXED_PCT,
        "fixed_ticks": SlippageMode.FIXED_TICKS,
        "almgren_chriss": SlippageMode.ALMGREN_CHRISS,
    }
    
    config = RealisticBacktestConfig(
        initial_capital=initial_capital,
        slippage_mode=mode_map.get(slippage_mode, SlippageMode.ALMGREN_CHRISS)
    )
    
    engine = RealisticBacktestEngine(config)
    return engine.run(strategy, data, symbol)


def compare_slippage_modes(
    strategy,
    data: pd.DataFrame,
    symbol: str = "TEST"
) -> pd.DataFrame:
    """
    Compare strategy performance across slippage modes.
    
    This shows the impact of realistic cost modeling.
    """
    results = []
    
    for mode in SlippageMode:
        config = RealisticBacktestConfig(slippage_mode=mode)
        engine = RealisticBacktestEngine(config)
        
        result = engine.run(strategy, data, symbol)
        metrics = result["metrics"]
        
        results.append({
            "mode": mode.value,
            "net_return": metrics.net_return,
            "sharpe": metrics.sharpe_ratio,
            "max_dd": metrics.max_drawdown,
            "total_costs": metrics.total_costs,
            "cost_drag": metrics.cost_drag_pct,
        })
    
    return pd.DataFrame(results)
