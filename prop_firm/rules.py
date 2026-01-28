"""
QUANT_INDUSTRY_V1 Prop Firm Rules Engine

Immutable rule enforcement for prop firm trading.
Supports multiple prop firms with their specific rule sets.

Supported Firms:
- TopStep Trader (TPT)
- Apex Trader Funding
- FTMO
- Earn2Trade
- The5ers
"""

import numpy as np
import logging
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# PROP FIRM TYPES
# =============================================================================

class PropFirm(Enum):
    """Supported prop firms."""
    TPT = "topstep"
    APEX = "apex"
    FTMO = "ftmo"
    EARN2TRADE = "earn2trade"
    THE5ERS = "the5ers"
    CUSTOM = "custom"


class AccountTier(Enum):
    """Account tiers/sizes."""
    MICRO = "micro"
    SMALL = "small"
    STANDARD = "standard"
    LARGE = "large"
    ELITE = "elite"


class EvaluationPhase(Enum):
    """Evaluation phases."""
    COMBINE = "combine"  # TPT
    EVALUATION = "evaluation"  # Generic
    VERIFICATION = "verification"  # FTMO Phase 2
    FUNDED = "funded"
    FAILED = "failed"


@dataclass
class AccountConfig:
    """Prop firm account configuration."""
    firm: PropFirm
    tier: AccountTier
    account_size: float
    profit_target: float
    daily_loss_limit: float
    max_drawdown: float
    trailing_drawdown: bool = True
    min_trading_days: int = 0
    max_trading_days: int = 0  # 0 = unlimited
    consistency_rule: float = 0.5  # Max single day profit as % of target
    max_position_size: int = 10  # Contracts
    scaling_plan: Dict[str, int] = field(default_factory=dict)

    # Session restrictions
    allowed_sessions: List[str] = field(default_factory=list)
    news_trading_allowed: bool = True
    weekend_holding_allowed: bool = False


# =============================================================================
# PRE-CONFIGURED ACCOUNT TEMPLATES
# =============================================================================

TPT_ACCOUNTS = {
    "50K": AccountConfig(
        firm=PropFirm.TPT,
        tier=AccountTier.SMALL,
        account_size=50000,
        profit_target=3000,
        daily_loss_limit=1100,
        max_drawdown=2500,
        trailing_drawdown=True,
        consistency_rule=0.5,
        max_position_size=5,
        scaling_plan={
            "0-1500": 2,
            "1500-2500": 3,
            "2500+": 5,
        },
    ),
    "100K": AccountConfig(
        firm=PropFirm.TPT,
        tier=AccountTier.STANDARD,
        account_size=100000,
        profit_target=6000,
        daily_loss_limit=2200,
        max_drawdown=5000,
        trailing_drawdown=True,
        consistency_rule=0.5,
        max_position_size=10,
        scaling_plan={
            "0-3000": 4,
            "3000-5000": 7,
            "5000+": 10,
        },
    ),
    "150K": AccountConfig(
        firm=PropFirm.TPT,
        tier=AccountTier.LARGE,
        account_size=150000,
        profit_target=9000,
        daily_loss_limit=3300,
        max_drawdown=7500,
        trailing_drawdown=True,
        consistency_rule=0.5,
        max_position_size=15,
        scaling_plan={
            "0-4500": 6,
            "4500-7500": 10,
            "7500+": 15,
        },
    ),
}

APEX_ACCOUNTS = {
    "25K": AccountConfig(
        firm=PropFirm.APEX,
        tier=AccountTier.MICRO,
        account_size=25000,
        profit_target=1500,
        daily_loss_limit=500,
        max_drawdown=1500,
        trailing_drawdown=True,
        consistency_rule=0.3,
        max_position_size=2,
    ),
    "50K": AccountConfig(
        firm=PropFirm.APEX,
        tier=AccountTier.SMALL,
        account_size=50000,
        profit_target=3000,
        daily_loss_limit=1100,
        max_drawdown=2500,
        trailing_drawdown=True,
        consistency_rule=0.3,
        max_position_size=4,
    ),
    "100K": AccountConfig(
        firm=PropFirm.APEX,
        tier=AccountTier.STANDARD,
        account_size=100000,
        profit_target=6000,
        daily_loss_limit=2200,
        max_drawdown=5000,
        trailing_drawdown=True,
        consistency_rule=0.3,
        max_position_size=8,
    ),
}

FTMO_ACCOUNTS = {
    "10K": AccountConfig(
        firm=PropFirm.FTMO,
        tier=AccountTier.MICRO,
        account_size=10000,
        profit_target=1000,
        daily_loss_limit=500,
        max_drawdown=1000,
        trailing_drawdown=False,
        min_trading_days=4,
        max_trading_days=30,
        consistency_rule=0.0,  # No consistency rule
        max_position_size=10,
    ),
    "100K": AccountConfig(
        firm=PropFirm.FTMO,
        tier=AccountTier.STANDARD,
        account_size=100000,
        profit_target=10000,
        daily_loss_limit=5000,
        max_drawdown=10000,
        trailing_drawdown=False,
        min_trading_days=4,
        max_trading_days=30,
        consistency_rule=0.0,
        max_position_size=40,
    ),
}


# =============================================================================
# RULE VIOLATIONS
# =============================================================================

@dataclass
class RuleViolation:
    """Record of a rule violation."""
    timestamp: datetime
    rule_name: str
    severity: str  # 'warning', 'violation', 'fatal'
    description: str
    current_value: float
    limit_value: float
    action_taken: str = ""


# =============================================================================
# PROP FIRM RULES ENGINE
# =============================================================================

class PropFirmRules:
    """
    Immutable prop firm rule enforcement.

    These rules CANNOT be bypassed - they are enforced at the execution layer.
    """

    def __init__(self, config: AccountConfig):
        self.config = config
        self.violations: List[RuleViolation] = []

        # Tracking state
        self.starting_balance = config.account_size
        self.current_balance = config.account_size
        self.high_water_mark = config.account_size
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.current_drawdown = 0.0
        self.trailing_stop_level = config.account_size - config.max_drawdown

        # Daily tracking
        self.daily_trades: List[Dict] = []
        self.daily_profits: Dict[date, float] = {}
        self.trading_days: int = 0

        # Status
        self.is_halted = False
        self.halt_reason = ""
        self.phase = EvaluationPhase.EVALUATION

    # =========================================================================
    # CORE RULE CHECKS (IMMUTABLE)
    # =========================================================================

    def check_daily_loss_limit(self, potential_loss: float = 0) -> Tuple[bool, str]:
        """
        Check if daily loss limit would be breached.

        Returns (allowed, reason)
        """
        projected_loss = self.daily_pnl - potential_loss

        if projected_loss <= -self.config.daily_loss_limit:
            reason = f"Daily loss limit breach: ${projected_loss:.2f} <= -${self.config.daily_loss_limit:.2f}"
            self._record_violation("daily_loss_limit", "fatal", reason,
                                   projected_loss, -self.config.daily_loss_limit)
            return False, reason

        # Warning at 75%
        if projected_loss <= -self.config.daily_loss_limit * 0.75:
            return True, f"WARNING: Approaching daily loss limit ({abs(projected_loss/self.config.daily_loss_limit)*100:.1f}%)"

        return True, ""

    def check_max_drawdown(self, potential_loss: float = 0) -> Tuple[bool, str]:
        """
        Check if max drawdown would be breached.

        For trailing drawdown accounts, this is from the high water mark.
        """
        if self.config.trailing_drawdown:
            # Trailing drawdown
            projected_balance = self.current_balance - potential_loss
            if projected_balance <= self.trailing_stop_level:
                reason = f"Trailing drawdown breach: ${projected_balance:.2f} <= ${self.trailing_stop_level:.2f}"
                self._record_violation("max_drawdown", "fatal", reason,
                                       projected_balance, self.trailing_stop_level)
                return False, reason
        else:
            # Fixed drawdown from starting balance
            total_dd = self.starting_balance - (self.current_balance - potential_loss)
            if total_dd >= self.config.max_drawdown:
                reason = f"Max drawdown breach: ${total_dd:.2f} >= ${self.config.max_drawdown:.2f}"
                self._record_violation("max_drawdown", "fatal", reason,
                                       total_dd, self.config.max_drawdown)
                return False, reason

        return True, ""

    def check_position_size(self, requested_size: int) -> Tuple[bool, str, int]:
        """
        Check if position size is allowed.

        Returns (allowed, reason, adjusted_size)
        """
        # Check scaling plan if applicable
        max_allowed = self._get_scaled_position_limit()

        if requested_size > max_allowed:
            reason = f"Position size {requested_size} exceeds limit {max_allowed}"
            self._record_violation("position_size", "warning", reason,
                                   requested_size, max_allowed)
            return True, reason, max_allowed  # Adjusted, not rejected

        return True, "", requested_size

    def check_consistency_rule(self, trade_profit: float) -> Tuple[bool, str]:
        """
        Check if trade would violate consistency rule.

        Single day profit cannot exceed X% of profit target.
        """
        if self.config.consistency_rule <= 0:
            return True, ""

        max_daily_profit = self.config.profit_target * self.config.consistency_rule
        projected_daily = self.daily_pnl + trade_profit

        if projected_daily > max_daily_profit:
            reason = f"Consistency rule: Daily profit ${projected_daily:.2f} would exceed ${max_daily_profit:.2f} ({self.config.consistency_rule*100}% of target)"
            # This is a warning, not a hard stop
            return True, reason

        return True, ""

    def check_session_allowed(self, timestamp: datetime = None) -> Tuple[bool, str]:
        """Check if trading is allowed in current session."""
        if not self.config.allowed_sessions:
            return True, ""

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        current_hour = timestamp.hour

        # Define sessions (UTC)
        sessions = {
            'asian': (0, 8),
            'london': (7, 16),
            'new_york': (13, 22),
            'all': (0, 24),
        }

        for allowed_session in self.config.allowed_sessions:
            if allowed_session.lower() in sessions:
                start, end = sessions[allowed_session.lower()]
                if start <= current_hour < end:
                    return True, ""

        return False, f"Trading not allowed in current session (hour {current_hour} UTC)"

    # =========================================================================
    # PRE-TRADE VALIDATION
    # =========================================================================

    def validate_trade(
        self,
        direction: str,
        size: int,
        potential_loss: float,
        potential_profit: float = 0,
    ) -> Dict[str, Any]:
        """
        Comprehensive pre-trade validation.

        Returns validation result with any adjustments needed.
        """
        result = {
            'allowed': True,
            'adjusted_size': size,
            'warnings': [],
            'errors': [],
            'halt_trading': False,
        }

        if self.is_halted:
            result['allowed'] = False
            result['errors'].append(f"Trading halted: {self.halt_reason}")
            result['halt_trading'] = True
            return result

        # Check session
        session_ok, session_msg = self.check_session_allowed()
        if not session_ok:
            result['warnings'].append(session_msg)

        # Check daily loss limit
        dll_ok, dll_msg = self.check_daily_loss_limit(potential_loss)
        if not dll_ok:
            result['allowed'] = False
            result['errors'].append(dll_msg)
            result['halt_trading'] = True
            self._halt("Daily loss limit reached")
            return result
        elif dll_msg:
            result['warnings'].append(dll_msg)

        # Check max drawdown
        dd_ok, dd_msg = self.check_max_drawdown(potential_loss)
        if not dd_ok:
            result['allowed'] = False
            result['errors'].append(dd_msg)
            result['halt_trading'] = True
            self._halt("Max drawdown reached")
            return result

        # Check position size
        size_ok, size_msg, adjusted_size = self.check_position_size(size)
        if size_msg:
            result['warnings'].append(size_msg)
        result['adjusted_size'] = adjusted_size

        # Check consistency rule
        cons_ok, cons_msg = self.check_consistency_rule(potential_profit)
        if cons_msg:
            result['warnings'].append(cons_msg)

        return result

    # =========================================================================
    # TRADE RECORDING
    # =========================================================================

    def record_trade(
        self,
        pnl: float,
        timestamp: datetime = None,
    ) -> None:
        """Record completed trade and update state."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        trade_date = timestamp.date()

        # Update PnL
        self.daily_pnl += pnl
        self.total_pnl += pnl
        self.current_balance += pnl

        # Update high water mark (for trailing drawdown)
        if self.current_balance > self.high_water_mark:
            self.high_water_mark = self.current_balance
            if self.config.trailing_drawdown:
                self.trailing_stop_level = self.high_water_mark - self.config.max_drawdown

        # Update drawdown
        self.current_drawdown = self.high_water_mark - self.current_balance

        # Record daily profit
        if trade_date not in self.daily_profits:
            self.daily_profits[trade_date] = 0
            self.trading_days += 1
        self.daily_profits[trade_date] += pnl

        # Check for target reached
        if self.total_pnl >= self.config.profit_target:
            self._check_evaluation_complete()

        # Log trade
        self.daily_trades.append({
            'timestamp': timestamp,
            'pnl': pnl,
            'balance': self.current_balance,
            'drawdown': self.current_drawdown,
        })

    def start_new_day(self) -> None:
        """Reset daily metrics for new trading day."""
        self.daily_pnl = 0.0
        self.daily_trades = []

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_scaled_position_limit(self) -> int:
        """Get position limit based on current profit (scaling plan)."""
        if not self.config.scaling_plan:
            return self.config.max_position_size

        for range_str, limit in self.config.scaling_plan.items():
            if '+' in range_str:
                threshold = float(range_str.replace('+', ''))
                if self.total_pnl >= threshold:
                    return limit
            elif '-' in range_str:
                low, high = range_str.split('-')
                if float(low) <= self.total_pnl < float(high):
                    return limit

        return self.config.max_position_size

    def _halt(self, reason: str) -> None:
        """Halt all trading."""
        self.is_halted = True
        self.halt_reason = reason
        self.phase = EvaluationPhase.FAILED
        logger.critical(f"TRADING HALTED: {reason}")

    def _record_violation(
        self,
        rule_name: str,
        severity: str,
        description: str,
        current_value: float,
        limit_value: float,
    ) -> None:
        """Record a rule violation."""
        violation = RuleViolation(
            timestamp=datetime.now(timezone.utc),
            rule_name=rule_name,
            severity=severity,
            description=description,
            current_value=current_value,
            limit_value=limit_value,
        )
        self.violations.append(violation)
        logger.warning(f"Rule violation: {description}")

    def _check_evaluation_complete(self) -> None:
        """Check if evaluation is complete."""
        # Check minimum trading days
        if self.config.min_trading_days > 0:
            if self.trading_days < self.config.min_trading_days:
                return

        # Check consistency rule compliance
        if self.config.consistency_rule > 0:
            max_allowed = self.config.profit_target * self.config.consistency_rule
            for day_profit in self.daily_profits.values():
                if day_profit > max_allowed:
                    logger.warning(f"Consistency rule violated: Day with ${day_profit:.2f} profit")
                    # Don't fail, just warn

        logger.info("EVALUATION TARGET REACHED!")
        self.phase = EvaluationPhase.FUNDED

    # =========================================================================
    # STATUS & REPORTING
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get current account status."""
        progress = (self.total_pnl / self.config.profit_target * 100) if self.config.profit_target > 0 else 0

        return {
            'phase': self.phase.value,
            'is_halted': self.is_halted,
            'halt_reason': self.halt_reason,

            # Balances
            'starting_balance': self.starting_balance,
            'current_balance': self.current_balance,
            'high_water_mark': self.high_water_mark,

            # PnL
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'progress_pct': progress,

            # Risk metrics
            'current_drawdown': self.current_drawdown,
            'trailing_stop_level': self.trailing_stop_level,
            'daily_loss_remaining': self.config.daily_loss_limit + self.daily_pnl,
            'drawdown_remaining': self.config.max_drawdown - self.current_drawdown,

            # Limits
            'max_position_size': self._get_scaled_position_limit(),

            # Trading stats
            'trading_days': self.trading_days,
            'violations_count': len(self.violations),
        }

    def get_risk_metrics(self) -> Dict[str, float]:
        """Get current risk metrics."""
        return {
            'daily_loss_used_pct': abs(min(0, self.daily_pnl)) / self.config.daily_loss_limit * 100,
            'drawdown_used_pct': self.current_drawdown / self.config.max_drawdown * 100,
            'distance_to_target_pct': (self.config.profit_target - self.total_pnl) / self.config.profit_target * 100,
            'risk_score': self._calculate_risk_score(),
        }

    def _calculate_risk_score(self) -> float:
        """Calculate overall risk score (0-100, higher = riskier)."""
        daily_risk = abs(min(0, self.daily_pnl)) / self.config.daily_loss_limit
        dd_risk = self.current_drawdown / self.config.max_drawdown

        # Weighted combination
        score = (daily_risk * 0.6 + dd_risk * 0.4) * 100
        return min(100, score)


# =============================================================================
# EVALUATION TRACKER
# =============================================================================

class EvaluationTracker:
    """
    Track evaluation progress across multiple accounts.
    """

    def __init__(self):
        self.accounts: Dict[str, PropFirmRules] = {}
        self.history: List[Dict] = []

    def add_account(self, account_id: str, config: AccountConfig) -> PropFirmRules:
        """Add a new account to track."""
        rules = PropFirmRules(config)
        self.accounts[account_id] = rules
        return rules

    def get_account(self, account_id: str) -> Optional[PropFirmRules]:
        """Get account rules by ID."""
        return self.accounts.get(account_id)

    def get_all_status(self) -> Dict[str, Dict]:
        """Get status for all accounts."""
        return {
            account_id: rules.get_status()
            for account_id, rules in self.accounts.items()
        }

    def get_best_performer(self) -> Optional[str]:
        """Get best performing account."""
        if not self.accounts:
            return None

        best_id = None
        best_progress = -float('inf')

        for account_id, rules in self.accounts.items():
            status = rules.get_status()
            if not status['is_halted'] and status['progress_pct'] > best_progress:
                best_progress = status['progress_pct']
                best_id = account_id

        return best_id


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PropFirm',
    'AccountTier',
    'EvaluationPhase',
    'AccountConfig',
    'RuleViolation',
    'PropFirmRules',
    'EvaluationTracker',
    'TPT_ACCOUNTS',
    'APEX_ACCOUNTS',
    'FTMO_ACCOUNTS',
]
