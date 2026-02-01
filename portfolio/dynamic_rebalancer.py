"""
Dynamic Rebalancer - Intelligent Portfolio Rebalancing

This module provides dynamic rebalancing with threshold-based triggers,
predictive rebalancing, and tax-aware optimization.

Key Features:
- Threshold-based rebalancing triggers
- Predictive rebalancing (anticipate drift)
- Tax-aware rebalancing
- Transaction cost optimization
- Calendar-based scheduling

Usage:
    from portfolio.dynamic_rebalancer import DynamicRebalancer

    rebalancer = DynamicRebalancer()
    trades = rebalancer.generate_rebalance_trades(
        current_weights, target_weights, positions
    )
"""

import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RebalanceTrigger(Enum):
    """Types of rebalance triggers."""
    THRESHOLD = "threshold"
    CALENDAR = "calendar"
    PREDICTIVE = "predictive"
    RISK = "risk"
    TAX_LOSS = "tax_loss"


class TaxLotMethod(Enum):
    """Tax lot selection methods."""
    FIFO = "fifo"
    LIFO = "lifo"
    HIFO = "hifo"  # Highest cost first
    SPECIFIC = "specific"
    TAX_OPTIMAL = "tax_optimal"


@dataclass
class RebalanceTrade:
    """Proposed rebalance trade."""
    symbol: str
    action: str  # 'buy' or 'sell'
    shares: float
    notional: float
    current_weight: float
    target_weight: float
    weight_change: float
    estimated_cost: float
    tax_impact: Optional[float] = None
    priority: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'action': self.action,
            'shares': self.shares,
            'notional': self.notional,
            'current_weight': self.current_weight,
            'target_weight': self.target_weight,
            'weight_change': self.weight_change,
            'estimated_cost': self.estimated_cost,
            'tax_impact': self.tax_impact,
            'priority': self.priority,
        }


@dataclass
class RebalanceResult:
    """Result of rebalance operation."""
    timestamp: datetime
    trigger: RebalanceTrigger
    trades: List[RebalanceTrade]
    total_turnover: float
    estimated_cost: float
    estimated_tax: float
    tracking_error_before: float
    tracking_error_after: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'trigger': self.trigger.value,
            'trades': [t.to_dict() for t in self.trades],
            'total_turnover': self.total_turnover,
            'estimated_cost': self.estimated_cost,
            'estimated_tax': self.estimated_tax,
            'tracking_error_before': self.tracking_error_before,
            'tracking_error_after': self.tracking_error_after,
        }


@dataclass
class TaxLot:
    """Individual tax lot."""
    symbol: str
    purchase_date: date
    shares: float
    cost_basis: float
    current_value: float

    @property
    def gain_loss(self) -> float:
        return self.current_value - self.cost_basis

    @property
    def gain_loss_percent(self) -> float:
        return self.gain_loss / self.cost_basis if self.cost_basis > 0 else 0

    @property
    def is_long_term(self) -> bool:
        return (date.today() - self.purchase_date).days > 365


@dataclass
class RebalanceConfig:
    """Configuration for rebalancer."""
    threshold_percent: float = 0.05  # 5% drift threshold
    min_trade_size: float = 100.0
    max_turnover_percent: float = 0.20  # 20% max turnover
    transaction_cost_bps: float = 10.0
    short_term_tax_rate: float = 0.35
    long_term_tax_rate: float = 0.15
    tax_loss_threshold: float = -0.03  # -3% for tax loss harvesting
    calendar_frequency: str = 'quarterly'
    predictive_lookforward_days: int = 5


class DynamicRebalancer:
    """
    Intelligent portfolio rebalancer with multiple trigger types.

    Supports threshold-based, calendar-based, and predictive
    rebalancing with tax-awareness.

    Example:
        rebalancer = DynamicRebalancer()

        # Check if rebalance needed
        should_rebalance, trigger = rebalancer.should_rebalance(
            current_weights, target_weights
        )

        # Generate trades
        result = rebalancer.generate_rebalance_trades(
            current_weights, target_weights, positions, prices
        )

        # Tax-loss harvesting
        tax_trades = rebalancer.identify_tax_loss_opportunities(tax_lots)
    """

    def __init__(self, config: Optional[RebalanceConfig] = None):
        self.config = config or RebalanceConfig()
        self._rebalance_history: List[RebalanceResult] = []
        self._last_rebalance: Optional[datetime] = None

        logger.info("DynamicRebalancer initialized")

    def should_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        check_calendar: bool = True,
        check_predictive: bool = False,
        predicted_drift: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, Optional[RebalanceTrigger]]:
        """
        Determine if rebalancing is needed.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target weights
            check_calendar: Check calendar-based trigger
            check_predictive: Check predictive trigger
            predicted_drift: Predicted weight changes

        Returns:
            Tuple of (should_rebalance, trigger_type)
        """
        # Check threshold-based
        max_drift = self._calculate_max_drift(current_weights, target_weights)
        if max_drift >= self.config.threshold_percent:
            return True, RebalanceTrigger.THRESHOLD

        # Check calendar-based
        if check_calendar and self._check_calendar_trigger():
            return True, RebalanceTrigger.CALENDAR

        # Check predictive
        if check_predictive and predicted_drift:
            future_weights = {
                s: current_weights.get(s, 0) + predicted_drift.get(s, 0)
                for s in set(current_weights) | set(predicted_drift)
            }
            future_drift = self._calculate_max_drift(future_weights, target_weights)
            if future_drift >= self.config.threshold_percent * 0.8:  # 80% of threshold
                return True, RebalanceTrigger.PREDICTIVE

        return False, None

    def _calculate_max_drift(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> float:
        """Calculate maximum weight drift from target."""
        all_assets = set(current_weights) | set(target_weights)

        max_drift = 0.0
        for asset in all_assets:
            current = current_weights.get(asset, 0)
            target = target_weights.get(asset, 0)
            drift = abs(current - target)
            max_drift = max(max_drift, drift)

        return max_drift

    def _check_calendar_trigger(self) -> bool:
        """Check if calendar-based rebalance is due."""
        if self._last_rebalance is None:
            return True

        now = datetime.now(timezone.utc)
        days_since = (now - self._last_rebalance).days

        if self.config.calendar_frequency == 'daily':
            return days_since >= 1
        elif self.config.calendar_frequency == 'weekly':
            return days_since >= 7
        elif self.config.calendar_frequency == 'monthly':
            return days_since >= 30
        elif self.config.calendar_frequency == 'quarterly':
            return days_since >= 90
        elif self.config.calendar_frequency == 'annual':
            return days_since >= 365

        return False

    def generate_rebalance_trades(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        positions: Dict[str, float],
        prices: Dict[str, float],
        portfolio_value: float,
        tax_lots: Optional[Dict[str, List[TaxLot]]] = None,
        trigger: RebalanceTrigger = RebalanceTrigger.THRESHOLD,
    ) -> RebalanceResult:
        """
        Generate rebalancing trades.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target weights
            positions: Current positions (shares)
            prices: Current prices
            portfolio_value: Total portfolio value
            tax_lots: Tax lot information for tax-aware rebalancing
            trigger: Trigger type

        Returns:
            RebalanceResult with proposed trades
        """
        trades = []
        total_turnover = 0.0
        total_cost = 0.0
        total_tax = 0.0

        # Calculate tracking error before
        te_before = self._calculate_tracking_error(current_weights, target_weights)

        all_assets = set(current_weights) | set(target_weights)

        for asset in all_assets:
            current_weight = current_weights.get(asset, 0)
            target_weight = target_weights.get(asset, 0)
            weight_diff = target_weight - current_weight

            if abs(weight_diff) < 0.001:  # Less than 0.1%
                continue

            # Calculate trade
            notional = weight_diff * portfolio_value
            price = prices.get(asset, 1.0)
            shares = notional / price

            if abs(notional) < self.config.min_trade_size:
                continue

            # Estimate cost
            cost = abs(notional) * self.config.transaction_cost_bps / 10000

            # Estimate tax impact for sells
            tax_impact = None
            if weight_diff < 0 and tax_lots and asset in tax_lots:
                tax_impact = self._estimate_tax_impact(
                    tax_lots[asset],
                    abs(shares),
                    price,
                )
                total_tax += tax_impact or 0

            trade = RebalanceTrade(
                symbol=asset,
                action='buy' if weight_diff > 0 else 'sell',
                shares=abs(shares),
                notional=abs(notional),
                current_weight=current_weight,
                target_weight=target_weight,
                weight_change=weight_diff,
                estimated_cost=cost,
                tax_impact=tax_impact,
                priority=1 if abs(weight_diff) > self.config.threshold_percent else 2,
            )

            trades.append(trade)
            total_turnover += abs(notional)
            total_cost += cost

        # Apply turnover constraint
        if total_turnover > portfolio_value * self.config.max_turnover_percent:
            trades = self._constrain_turnover(
                trades,
                portfolio_value * self.config.max_turnover_percent,
            )
            total_turnover = sum(t.notional for t in trades)
            total_cost = sum(t.estimated_cost for t in trades)

        # Sort by priority
        trades.sort(key=lambda t: (t.priority, -abs(t.weight_change)))

        # Calculate tracking error after (estimated)
        new_weights = current_weights.copy()
        for trade in trades:
            if trade.action == 'buy':
                new_weights[trade.symbol] = new_weights.get(trade.symbol, 0) + trade.weight_change
            else:
                new_weights[trade.symbol] = new_weights.get(trade.symbol, 0) + trade.weight_change

        te_after = self._calculate_tracking_error(new_weights, target_weights)

        result = RebalanceResult(
            timestamp=datetime.now(timezone.utc),
            trigger=trigger,
            trades=trades,
            total_turnover=total_turnover,
            estimated_cost=total_cost,
            estimated_tax=total_tax,
            tracking_error_before=te_before,
            tracking_error_after=te_after,
        )

        self._rebalance_history.append(result)
        self._last_rebalance = result.timestamp

        return result

    def _constrain_turnover(
        self,
        trades: List[RebalanceTrade],
        max_turnover: float,
    ) -> List[RebalanceTrade]:
        """Constrain trades to max turnover."""
        # Sort by priority and magnitude
        sorted_trades = sorted(
            trades,
            key=lambda t: (t.priority, -abs(t.weight_change))
        )

        constrained = []
        remaining_turnover = max_turnover

        for trade in sorted_trades:
            if trade.notional <= remaining_turnover:
                constrained.append(trade)
                remaining_turnover -= trade.notional
            elif remaining_turnover > self.config.min_trade_size:
                # Partial trade
                scale = remaining_turnover / trade.notional
                partial = RebalanceTrade(
                    symbol=trade.symbol,
                    action=trade.action,
                    shares=trade.shares * scale,
                    notional=remaining_turnover,
                    current_weight=trade.current_weight,
                    target_weight=trade.current_weight + trade.weight_change * scale,
                    weight_change=trade.weight_change * scale,
                    estimated_cost=trade.estimated_cost * scale,
                    tax_impact=trade.tax_impact * scale if trade.tax_impact else None,
                    priority=trade.priority,
                )
                constrained.append(partial)
                break

        return constrained

    def _calculate_tracking_error(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> float:
        """Calculate tracking error from target."""
        all_assets = set(current_weights) | set(target_weights)

        sum_sq_diff = 0.0
        for asset in all_assets:
            diff = current_weights.get(asset, 0) - target_weights.get(asset, 0)
            sum_sq_diff += diff ** 2

        return np.sqrt(sum_sq_diff)

    def _estimate_tax_impact(
        self,
        tax_lots: List[TaxLot],
        shares_to_sell: float,
        current_price: float,
    ) -> float:
        """Estimate tax impact of selling shares."""
        # Use tax-optimal lot selection
        lots = sorted(tax_lots, key=lambda l: (not l.is_long_term, l.gain_loss_percent))

        remaining_shares = shares_to_sell
        total_tax = 0.0

        for lot in lots:
            if remaining_shares <= 0:
                break

            sell_shares = min(remaining_shares, lot.shares)
            sell_value = sell_shares * current_price
            cost_basis = (lot.cost_basis / lot.shares) * sell_shares
            gain = sell_value - cost_basis

            if gain > 0:
                rate = self.config.long_term_tax_rate if lot.is_long_term else self.config.short_term_tax_rate
                total_tax += gain * rate

            remaining_shares -= sell_shares

        return total_tax

    def identify_tax_loss_opportunities(
        self,
        tax_lots: Dict[str, List[TaxLot]],
        min_loss_amount: float = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Identify tax-loss harvesting opportunities.

        Args:
            tax_lots: Tax lots by symbol
            min_loss_amount: Minimum loss to consider

        Returns:
            List of harvesting opportunities
        """
        opportunities = []

        for symbol, lots in tax_lots.items():
            for lot in lots:
                if lot.gain_loss_percent <= self.config.tax_loss_threshold:
                    loss_amount = abs(lot.gain_loss)

                    if loss_amount >= min_loss_amount:
                        tax_benefit = loss_amount * (
                            self.config.short_term_tax_rate if not lot.is_long_term
                            else self.config.long_term_tax_rate
                        )

                        opportunities.append({
                            'symbol': symbol,
                            'shares': lot.shares,
                            'purchase_date': lot.purchase_date.isoformat(),
                            'cost_basis': lot.cost_basis,
                            'current_value': lot.current_value,
                            'loss': lot.gain_loss,
                            'loss_percent': lot.gain_loss_percent,
                            'is_long_term': lot.is_long_term,
                            'estimated_tax_benefit': tax_benefit,
                        })

        # Sort by tax benefit
        opportunities.sort(key=lambda x: x['estimated_tax_benefit'], reverse=True)

        return opportunities

    def predict_drift(
        self,
        current_weights: Dict[str, float],
        returns_forecast: Dict[str, float],
        days: int = 5,
    ) -> Dict[str, float]:
        """
        Predict portfolio drift based on return forecasts.

        Args:
            current_weights: Current weights
            returns_forecast: Expected returns by asset
            days: Forecast horizon

        Returns:
            Predicted weight changes
        """
        # Simple drift prediction
        predicted_values = {}
        total_new_value = 0

        for asset, weight in current_weights.items():
            expected_return = returns_forecast.get(asset, 0)
            new_value = weight * (1 + expected_return * days / 252)
            predicted_values[asset] = new_value
            total_new_value += new_value

        # Calculate new weights
        predicted_weights = {
            asset: value / total_new_value
            for asset, value in predicted_values.items()
        }

        # Calculate drift
        predicted_drift = {
            asset: predicted_weights.get(asset, 0) - current_weights.get(asset, 0)
            for asset in set(current_weights) | set(predicted_weights)
        }

        return predicted_drift

    def get_rebalance_schedule(
        self,
        start_date: date,
        end_date: date,
    ) -> List[date]:
        """
        Get scheduled rebalance dates.

        Args:
            start_date: Start of period
            end_date: End of period

        Returns:
            List of scheduled rebalance dates
        """
        dates = []
        current = start_date

        if self.config.calendar_frequency == 'quarterly':
            # First business day of each quarter
            while current <= end_date:
                if current.month in [1, 4, 7, 10] and current.day <= 5:
                    dates.append(current)
                    current = date(
                        current.year + (1 if current.month == 10 else 0),
                        (current.month + 3 - 1) % 12 + 1,
                        1
                    )
                else:
                    current += timedelta(days=1)
        elif self.config.calendar_frequency == 'monthly':
            while current <= end_date:
                if current.day == 1:
                    dates.append(current)
                    if current.month == 12:
                        current = date(current.year + 1, 1, 1)
                    else:
                        current = date(current.year, current.month + 1, 1)
                else:
                    current += timedelta(days=1)

        return dates

    def get_stats(self) -> Dict[str, Any]:
        """Get rebalancer statistics."""
        if not self._rebalance_history:
            return {
                'total_rebalances': 0,
                'last_rebalance': None,
            }

        return {
            'total_rebalances': len(self._rebalance_history),
            'last_rebalance': self._last_rebalance.isoformat() if self._last_rebalance else None,
            'avg_turnover': np.mean([r.total_turnover for r in self._rebalance_history]),
            'avg_cost': np.mean([r.estimated_cost for r in self._rebalance_history]),
            'avg_tracking_error_reduction': np.mean([
                r.tracking_error_before - r.tracking_error_after
                for r in self._rebalance_history
            ]),
        }
