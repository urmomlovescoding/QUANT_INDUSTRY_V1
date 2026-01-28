"""
QUANT_INDUSTRY_V1 Consistency Monitor

Monitors and enforces consistency rules for prop firm evaluations.
Ensures profitable days are distributed appropriately.
"""

import numpy as np
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class DailyRecord:
    """Record for a single trading day."""
    date: date
    pnl: float
    trades: int
    max_drawdown: float
    starting_balance: float
    ending_balance: float
    violations: List[str] = field(default_factory=list)


class ConsistencyMonitor:
    """
    Monitor consistency rule compliance.

    Tracks:
    - Daily profit distribution
    - Consistency rule violations
    - Optimal profit pacing
    - Target achievement probability
    """

    def __init__(
        self,
        profit_target: float,
        consistency_rule: float = 0.5,
        max_trading_days: int = 0,
    ):
        self.profit_target = profit_target
        self.consistency_rule = consistency_rule
        self.max_trading_days = max_trading_days

        # Maximum profit per day to stay consistent
        self.max_daily_profit = profit_target * consistency_rule

        # Daily records
        self.daily_records: Dict[date, DailyRecord] = {}
        self.current_day: date = None
        self.current_pnl: float = 0.0
        self.current_trades: int = 0

        # Consistency tracking
        self.consistency_violations = 0
        self.warning_issued = False

    def start_day(self, trading_date: date = None, starting_balance: float = 0) -> None:
        """Start tracking a new trading day."""
        if trading_date is None:
            trading_date = datetime.now(timezone.utc).date()

        self.current_day = trading_date
        self.current_pnl = 0.0
        self.current_trades = 0
        self.warning_issued = False

        if trading_date not in self.daily_records:
            self.daily_records[trading_date] = DailyRecord(
                date=trading_date,
                pnl=0.0,
                trades=0,
                max_drawdown=0.0,
                starting_balance=starting_balance,
                ending_balance=starting_balance,
            )

    def record_trade(self, pnl: float) -> Dict[str, Any]:
        """
        Record a trade and check consistency.

        Returns warning/action if needed.
        """
        self.current_pnl += pnl
        self.current_trades += 1

        if self.current_day in self.daily_records:
            record = self.daily_records[self.current_day]
            record.pnl = self.current_pnl
            record.trades = self.current_trades
            record.ending_balance = record.starting_balance + self.current_pnl

        result = {
            'daily_pnl': self.current_pnl,
            'max_allowed': self.max_daily_profit,
            'remaining_room': self.max_daily_profit - self.current_pnl,
            'warning': None,
            'should_stop': False,
            'consistency_score': self._calculate_consistency_score(),
        }

        # Check consistency rule
        if self.consistency_rule > 0:
            if self.current_pnl >= self.max_daily_profit * 0.8 and not self.warning_issued:
                result['warning'] = f"Approaching consistency limit: ${self.current_pnl:.2f} / ${self.max_daily_profit:.2f}"
                self.warning_issued = True

            if self.current_pnl >= self.max_daily_profit:
                result['should_stop'] = True
                result['warning'] = f"Consistency limit reached: ${self.current_pnl:.2f} >= ${self.max_daily_profit:.2f}. Consider stopping."

        return result

    def end_day(self) -> DailyRecord:
        """End current trading day and finalize records."""
        if self.current_day and self.current_day in self.daily_records:
            record = self.daily_records[self.current_day]
            record.pnl = self.current_pnl
            record.trades = self.current_trades

            # Check for consistency violation
            if self.consistency_rule > 0 and record.pnl > self.max_daily_profit:
                record.violations.append(f"Consistency rule violation: ${record.pnl:.2f} > ${self.max_daily_profit:.2f}")
                self.consistency_violations += 1

            return record

        return None

    def _calculate_consistency_score(self) -> float:
        """
        Calculate consistency score (0-100).

        Higher = more consistent profit distribution.
        """
        if len(self.daily_records) < 2:
            return 100.0

        profits = [r.pnl for r in self.daily_records.values() if r.pnl > 0]

        if not profits:
            return 100.0

        # Standard deviation of profits
        mean_profit = np.mean(profits)
        std_profit = np.std(profits)

        # CV (coefficient of variation)
        cv = std_profit / mean_profit if mean_profit > 0 else 0

        # Score: Lower CV = higher consistency
        score = max(0, 100 - cv * 100)

        return score

    def get_optimal_daily_target(self) -> float:
        """
        Calculate optimal daily profit target for consistent progress.
        """
        total_pnl = sum(r.pnl for r in self.daily_records.values())
        remaining_target = self.profit_target - total_pnl

        if self.max_trading_days > 0:
            days_used = len(self.daily_records)
            days_remaining = max(1, self.max_trading_days - days_used)
            optimal = remaining_target / days_remaining
        else:
            # Assume 20 trading days as default
            days_used = len(self.daily_records)
            days_remaining = max(1, 20 - days_used)
            optimal = remaining_target / days_remaining

        # Cap at consistency limit
        if self.consistency_rule > 0:
            optimal = min(optimal, self.max_daily_profit)

        return max(0, optimal)

    def get_progress_report(self) -> Dict[str, Any]:
        """Get comprehensive progress report."""
        total_pnl = sum(r.pnl for r in self.daily_records.values())
        profitable_days = sum(1 for r in self.daily_records.values() if r.pnl > 0)
        losing_days = sum(1 for r in self.daily_records.values() if r.pnl < 0)

        profits = [r.pnl for r in self.daily_records.values() if r.pnl > 0]
        losses = [abs(r.pnl) for r in self.daily_records.values() if r.pnl < 0]

        avg_win = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0

        return {
            'total_pnl': total_pnl,
            'profit_target': self.profit_target,
            'progress_pct': total_pnl / self.profit_target * 100 if self.profit_target > 0 else 0,
            'remaining': self.profit_target - total_pnl,

            'trading_days': len(self.daily_records),
            'profitable_days': profitable_days,
            'losing_days': losing_days,
            'win_rate': profitable_days / len(self.daily_records) if self.daily_records else 0,

            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': avg_win / avg_loss if avg_loss > 0 else float('inf'),

            'consistency_score': self._calculate_consistency_score(),
            'consistency_violations': self.consistency_violations,

            'optimal_daily_target': self.get_optimal_daily_target(),
            'max_daily_allowed': self.max_daily_profit,

            'daily_breakdown': [
                {
                    'date': r.date.isoformat(),
                    'pnl': r.pnl,
                    'trades': r.trades,
                    'pct_of_target': r.pnl / self.profit_target * 100 if self.profit_target > 0 else 0,
                }
                for r in sorted(self.daily_records.values(), key=lambda x: x.date)
            ],
        }

    def estimate_completion(self) -> Dict[str, Any]:
        """Estimate time to target completion."""
        if not self.daily_records:
            return {'estimated_days': None, 'probability': 0}

        total_pnl = sum(r.pnl for r in self.daily_records.values())
        remaining = self.profit_target - total_pnl

        if remaining <= 0:
            return {'estimated_days': 0, 'probability': 1.0}

        # Calculate average daily profit (only profitable days)
        profitable_days = [r.pnl for r in self.daily_records.values() if r.pnl > 0]

        if not profitable_days:
            return {'estimated_days': None, 'probability': 0}

        avg_daily_profit = np.mean(profitable_days)
        std_daily_profit = np.std(profitable_days) if len(profitable_days) > 1 else avg_daily_profit * 0.3

        # Days to target
        estimated_days = remaining / avg_daily_profit if avg_daily_profit > 0 else float('inf')

        # Monte Carlo probability (simplified)
        # Probability of hitting target given variance
        if std_daily_profit > 0:
            z_score = remaining / (std_daily_profit * np.sqrt(estimated_days + 1))
            from scipy import stats
            try:
                probability = 1 - stats.norm.cdf(z_score)
            except:
                probability = 0.5
        else:
            probability = 1.0 if avg_daily_profit > 0 else 0

        return {
            'estimated_days': round(estimated_days),
            'probability': probability,
            'avg_daily_profit': avg_daily_profit,
            'remaining_target': remaining,
        }

    def get_recommendations(self) -> List[str]:
        """Get recommendations for improving consistency."""
        recommendations = []

        report = self.get_progress_report()

        # Check consistency score
        if report['consistency_score'] < 70:
            recommendations.append(
                f"Consistency score is {report['consistency_score']:.1f}%. "
                "Try to distribute profits more evenly across days."
            )

        # Check for violations
        if self.consistency_violations > 0:
            recommendations.append(
                f"You have {self.consistency_violations} consistency violations. "
                f"Keep daily profits under ${self.max_daily_profit:.2f}."
            )

        # Check win rate
        if report['win_rate'] < 0.5:
            recommendations.append(
                f"Win rate is {report['win_rate']*100:.1f}%. "
                "Focus on trade selection and entry timing."
            )

        # Check optimal pacing
        optimal_daily = report['optimal_daily_target']
        if optimal_daily > self.max_daily_profit:
            recommendations.append(
                f"You need ${optimal_daily:.2f}/day to hit target, but consistency limit is ${self.max_daily_profit:.2f}. "
                "You may need more trading days."
            )

        # Check progress
        if report['progress_pct'] < 30 and len(self.daily_records) > 5:
            recommendations.append(
                f"Progress is {report['progress_pct']:.1f}% after {len(self.daily_records)} days. "
                "Consider reviewing strategy performance."
            )

        return recommendations


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ['ConsistencyMonitor', 'DailyRecord']
