"""
P&L Attribution - Brinson-Fachler Attribution Analysis

This module provides comprehensive P&L attribution including
Brinson-Fachler attribution and factor contribution analysis.

Key Features:
- Brinson-Fachler attribution (allocation + selection + interaction)
- Factor-based attribution
- Real-time streaming updates
- Historical attribution analysis
- Sector and asset-level breakdown

Usage:
    from backend.analytics.pnl_attribution import PnLAttributor

    attributor = PnLAttributor()
    attribution = attributor.compute_brinson_fachler(
        portfolio_weights, benchmark_weights,
        portfolio_returns, benchmark_returns
    )
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BrinsonAttribution:
    """Brinson-Fachler attribution results."""
    timestamp: datetime
    period: str
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_active_return: float
    portfolio_return: float
    benchmark_return: float
    sector_attribution: Dict[str, Dict[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'period': self.period,
            'allocation_effect': self.allocation_effect,
            'selection_effect': self.selection_effect,
            'interaction_effect': self.interaction_effect,
            'total_active_return': self.total_active_return,
            'portfolio_return': self.portfolio_return,
            'benchmark_return': self.benchmark_return,
            'sector_attribution': self.sector_attribution,
        }


@dataclass
class FactorAttribution:
    """Factor-based attribution results."""
    timestamp: datetime
    period: str
    factor_contributions: Dict[str, float]
    residual: float
    total_return: float
    factor_exposures: Dict[str, float]
    r_squared: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'period': self.period,
            'factor_contributions': self.factor_contributions,
            'residual': self.residual,
            'total_return': self.total_return,
            'factor_exposures': self.factor_exposures,
            'r_squared': self.r_squared,
        }


@dataclass
class PnLBreakdown:
    """Detailed P&L breakdown."""
    timestamp: datetime
    gross_pnl: float
    trading_costs: float
    slippage: float
    financing_costs: float
    net_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    by_asset: Dict[str, float]
    by_strategy: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'gross_pnl': self.gross_pnl,
            'trading_costs': self.trading_costs,
            'slippage': self.slippage,
            'financing_costs': self.financing_costs,
            'net_pnl': self.net_pnl,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'by_asset': self.by_asset,
            'by_strategy': self.by_strategy,
        }


class PnLAttributor:
    """
    Comprehensive P&L attribution analysis.

    Provides Brinson-Fachler attribution, factor-based attribution,
    and detailed P&L breakdown for performance analysis.

    Example:
        attributor = PnLAttributor()

        # Brinson-Fachler attribution
        brinson = attributor.compute_brinson_fachler(
            portfolio_weights={'tech': 0.4, 'finance': 0.3, 'healthcare': 0.3},
            benchmark_weights={'tech': 0.3, 'finance': 0.35, 'healthcare': 0.35},
            portfolio_returns={'tech': 0.05, 'finance': 0.02, 'healthcare': 0.03},
            benchmark_returns={'tech': 0.04, 'finance': 0.025, 'healthcare': 0.028}
        )

        # Factor attribution
        factor_attr = attributor.compute_factor_attribution(
            portfolio_returns=returns_series,
            factor_returns=factor_df
        )
    """

    def __init__(self, history_size: int = 10000):
        self._brinson_history: deque = deque(maxlen=history_size)
        self._factor_history: deque = deque(maxlen=history_size)
        self._pnl_history: deque = deque(maxlen=history_size)

        # Streaming state
        self._cumulative_pnl = 0.0
        self._cumulative_attribution = {}

        logger.info("PnLAttributor initialized")

    def compute_brinson_fachler(
        self,
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        portfolio_returns: Dict[str, float],
        benchmark_returns: Dict[str, float],
        period: str = "daily",
    ) -> BrinsonAttribution:
        """
        Compute Brinson-Fachler attribution.

        Attribution formula:
        - Allocation = (wp - wb) * (Rb - RB)
        - Selection = wb * (Rp - Rb)
        - Interaction = (wp - wb) * (Rp - Rb)
        - Total = Allocation + Selection + Interaction

        Args:
            portfolio_weights: Portfolio weights by sector/asset
            benchmark_weights: Benchmark weights by sector/asset
            portfolio_returns: Portfolio returns by sector/asset
            benchmark_returns: Benchmark returns by sector/asset
            period: Time period label

        Returns:
            BrinsonAttribution with decomposed effects
        """
        # Get all sectors
        sectors = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        # Compute benchmark total return
        benchmark_return = sum(
            benchmark_weights.get(s, 0) * benchmark_returns.get(s, 0)
            for s in sectors
        )

        # Compute portfolio total return
        portfolio_return = sum(
            portfolio_weights.get(s, 0) * portfolio_returns.get(s, 0)
            for s in sectors
        )

        # Compute sector-level attribution
        sector_attribution = {}
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sector in sectors:
            wp = portfolio_weights.get(sector, 0)
            wb = benchmark_weights.get(sector, 0)
            rp = portfolio_returns.get(sector, 0)
            rb = benchmark_returns.get(sector, 0)

            # Brinson-Fachler decomposition
            allocation = (wp - wb) * (rb - benchmark_return)
            selection = wb * (rp - rb)
            interaction = (wp - wb) * (rp - rb)

            sector_attribution[sector] = {
                'portfolio_weight': wp,
                'benchmark_weight': wb,
                'portfolio_return': rp,
                'benchmark_return': rb,
                'allocation_effect': allocation,
                'selection_effect': selection,
                'interaction_effect': interaction,
                'total_effect': allocation + selection + interaction,
            }

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

        result = BrinsonAttribution(
            timestamp=datetime.now(timezone.utc),
            period=period,
            allocation_effect=total_allocation,
            selection_effect=total_selection,
            interaction_effect=total_interaction,
            total_active_return=total_allocation + total_selection + total_interaction,
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
            sector_attribution=sector_attribution,
        )

        self._brinson_history.append(result)

        return result

    def compute_factor_attribution(
        self,
        portfolio_returns: pd.Series,
        factor_returns: pd.DataFrame,
        period: str = "daily",
    ) -> FactorAttribution:
        """
        Compute factor-based attribution using regression.

        Args:
            portfolio_returns: Portfolio return series
            factor_returns: DataFrame of factor returns
            period: Time period label

        Returns:
            FactorAttribution with factor contributions
        """
        # Align data
        common_idx = portfolio_returns.index.intersection(factor_returns.index)
        if len(common_idx) < 10:
            logger.warning("Insufficient data for factor attribution")
            return self._empty_factor_attribution(period)

        y = portfolio_returns.loc[common_idx].values
        X = factor_returns.loc[common_idx].values

        # Add intercept
        X_with_intercept = np.column_stack([np.ones(len(X)), X])

        # OLS regression
        try:
            coefficients, residuals, rank, s = np.linalg.lstsq(
                X_with_intercept, y, rcond=None
            )
        except Exception as e:
            logger.error(f"Factor regression failed: {e}")
            return self._empty_factor_attribution(period)

        alpha = coefficients[0]
        betas = coefficients[1:]

        # Compute contributions
        factor_names = factor_returns.columns.tolist()
        mean_factor_returns = factor_returns.loc[common_idx].mean()

        factor_contributions = {}
        factor_exposures = {}
        total_factor_contribution = 0.0

        for i, (name, beta) in enumerate(zip(factor_names, betas)):
            contribution = beta * mean_factor_returns[name]
            factor_contributions[name] = contribution
            factor_exposures[name] = beta
            total_factor_contribution += contribution

        # Compute residual and R-squared
        predicted = X_with_intercept @ coefficients
        ss_res = np.sum((y - predicted) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        residual = portfolio_returns.loc[common_idx].mean() - total_factor_contribution - alpha

        result = FactorAttribution(
            timestamp=datetime.now(timezone.utc),
            period=period,
            factor_contributions=factor_contributions,
            residual=residual,
            total_return=portfolio_returns.loc[common_idx].mean(),
            factor_exposures=factor_exposures,
            r_squared=r_squared,
        )

        self._factor_history.append(result)

        return result

    def _empty_factor_attribution(self, period: str) -> FactorAttribution:
        """Return empty factor attribution."""
        return FactorAttribution(
            timestamp=datetime.now(timezone.utc),
            period=period,
            factor_contributions={},
            residual=0.0,
            total_return=0.0,
            factor_exposures={},
            r_squared=0.0,
        )

    def compute_pnl_breakdown(
        self,
        trades: List[Dict[str, Any]],
        positions: Dict[str, Dict[str, float]],
        prices: Dict[str, float],
        cost_rate: float = 0.001,
        financing_rate: float = 0.05 / 252,
    ) -> PnLBreakdown:
        """
        Compute detailed P&L breakdown.

        Args:
            trades: List of trade dictionaries
            positions: Current positions {symbol: {quantity, avg_cost}}
            prices: Current prices
            cost_rate: Trading cost rate
            financing_rate: Financing cost rate (daily)

        Returns:
            PnLBreakdown with detailed decomposition
        """
        gross_pnl = 0.0
        trading_costs = 0.0
        slippage = 0.0
        realized_pnl = 0.0
        unrealized_pnl = 0.0
        by_asset = {}
        by_strategy = {}

        # Process trades for realized P&L
        for trade in trades:
            symbol = trade.get('symbol', 'UNKNOWN')
            quantity = trade.get('quantity', 0)
            price = trade.get('price', 0)
            cost = trade.get('cost', 0)
            strategy = trade.get('strategy', 'default')
            expected_price = trade.get('expected_price', price)

            trade_value = abs(quantity * price)
            trade_cost = trade_value * cost_rate
            trade_slippage = abs(quantity) * abs(price - expected_price)

            trading_costs += trade_cost
            slippage += trade_slippage

            # Track by strategy
            if strategy not in by_strategy:
                by_strategy[strategy] = 0.0

        # Compute unrealized P&L from positions
        for symbol, position in positions.items():
            quantity = position.get('quantity', 0)
            avg_cost = position.get('avg_cost', 0)
            current_price = prices.get(symbol, avg_cost)

            position_pnl = quantity * (current_price - avg_cost)
            unrealized_pnl += position_pnl

            by_asset[symbol] = position_pnl

        # Compute gross and net
        gross_pnl = realized_pnl + unrealized_pnl

        # Estimate financing costs
        total_long_exposure = sum(
            p['quantity'] * prices.get(s, 0)
            for s, p in positions.items()
            if p.get('quantity', 0) > 0
        )
        financing_costs = total_long_exposure * financing_rate

        net_pnl = gross_pnl - trading_costs - slippage - financing_costs

        result = PnLBreakdown(
            timestamp=datetime.now(timezone.utc),
            gross_pnl=gross_pnl,
            trading_costs=trading_costs,
            slippage=slippage,
            financing_costs=financing_costs,
            net_pnl=net_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            by_asset=by_asset,
            by_strategy=by_strategy,
        )

        self._pnl_history.append(result)
        self._cumulative_pnl += net_pnl

        return result

    def get_cumulative_attribution(
        self,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get cumulative attribution over period.

        Args:
            lookback_days: Number of days to aggregate

        Returns:
            Cumulative attribution summary
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Aggregate Brinson attribution
        brinson_records = [
            r for r in self._brinson_history
            if r.timestamp >= cutoff
        ]

        if brinson_records:
            cum_allocation = sum(r.allocation_effect for r in brinson_records)
            cum_selection = sum(r.selection_effect for r in brinson_records)
            cum_interaction = sum(r.interaction_effect for r in brinson_records)
            cum_active = cum_allocation + cum_selection + cum_interaction
        else:
            cum_allocation = cum_selection = cum_interaction = cum_active = 0.0

        # Aggregate factor attribution
        factor_records = [
            r for r in self._factor_history
            if r.timestamp >= cutoff
        ]

        factor_totals = {}
        if factor_records:
            for r in factor_records:
                for factor, contrib in r.factor_contributions.items():
                    if factor not in factor_totals:
                        factor_totals[factor] = 0.0
                    factor_totals[factor] += contrib

        return {
            'period_days': lookback_days,
            'brinson': {
                'allocation': cum_allocation,
                'selection': cum_selection,
                'interaction': cum_interaction,
                'total_active': cum_active,
                'num_periods': len(brinson_records),
            },
            'factor': {
                'contributions': factor_totals,
                'num_periods': len(factor_records),
            },
            'cumulative_pnl': self._cumulative_pnl,
        }

    def get_attribution_timeseries(
        self,
        attribution_type: str = 'brinson',
        lookback_days: int = 30,
    ) -> pd.DataFrame:
        """
        Get attribution as time series.

        Args:
            attribution_type: 'brinson' or 'factor'
            lookback_days: Lookback period

        Returns:
            DataFrame with attribution time series
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        if attribution_type == 'brinson':
            records = [
                r for r in self._brinson_history
                if r.timestamp >= cutoff
            ]

            if not records:
                return pd.DataFrame()

            data = [{
                'timestamp': r.timestamp,
                'allocation': r.allocation_effect,
                'selection': r.selection_effect,
                'interaction': r.interaction_effect,
                'total_active': r.total_active_return,
            } for r in records]

        else:  # factor
            records = [
                r for r in self._factor_history
                if r.timestamp >= cutoff
            ]

            if not records:
                return pd.DataFrame()

            data = []
            for r in records:
                row = {'timestamp': r.timestamp, 'residual': r.residual}
                row.update(r.factor_contributions)
                data.append(row)

        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def get_sector_contribution_matrix(
        self,
        lookback_days: int = 30,
    ) -> pd.DataFrame:
        """
        Get sector contribution matrix over time.

        Returns:
            DataFrame with sectors as columns, dates as rows
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        records = [
            r for r in self._brinson_history
            if r.timestamp >= cutoff
        ]

        if not records:
            return pd.DataFrame()

        data = []
        for r in records:
            row = {'timestamp': r.timestamp}
            for sector, attr in r.sector_attribution.items():
                row[f"{sector}_total"] = attr['total_effect']
            data.append(row)

        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def get_stats(self) -> Dict[str, Any]:
        """Get attributor statistics."""
        return {
            'brinson_records': len(self._brinson_history),
            'factor_records': len(self._factor_history),
            'pnl_records': len(self._pnl_history),
            'cumulative_pnl': self._cumulative_pnl,
        }
