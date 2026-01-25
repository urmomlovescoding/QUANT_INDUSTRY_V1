"""
TPT Aggressive Strategy
=======================
P1 Critical Feature: Aggressive trading strategy for Take Profit Trader accounts.

Implements parity with quant-platform/brain/tpt_aggressive.py

This strategy is designed for TPT $50K evaluation accounts with:
- $3,000 profit target
- $2,000 trailing drawdown
- 6 max contracts
- 50% consistency rule
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("TPT_AGGRESSIVE")


class TPTStatus(Enum):
    """TPT account status."""
    ACTIVE = "active"
    PASSED = "passed"
    FAILED = "failed"
    PAUSED = "paused"


class SessionType(Enum):
    """Trading session type."""
    ASIAN = "asian"
    LONDON = "london"
    NY_OPEN = "ny_open"
    NY_CLOSE = "ny_close"
    OVERNIGHT = "overnight"


@dataclass
class TPTRules:
    """
    Take Profit Trader account rules.
    Matches quant-platform exactly.
    """
    # Account parameters
    name: str = "Take Profit Trader"
    initial_balance: float = 50000.0
    balance_floor: float = 48000.0  # $2K trailing drawdown
    profit_target: float = 3000.0

    # Contract limits
    max_contracts: int = 6
    min_contracts: int = 1

    # Trading rules
    min_trading_days: int = 5
    max_single_day_pct: float = 0.50  # 50% consistency rule
    trading_end_time: str = "17:00"  # Must close by 5PM ET

    # Permitted products
    permitted_products: List[str] = field(default_factory=lambda: [
        # Index Futures
        "ES", "MES", "NQ", "MNQ", "YM", "MYM", "RTY", "M2K",
        # Commodities
        "CL", "MCL", "GC", "MGC", "SI", "SIL", "HG", "NG",
        # Treasuries
        "ZB", "ZN", "ZF", "ZT",
        # Currencies
        "6E", "6J", "6B", "6A",
    ])

    # Contract multipliers
    contract_multipliers: Dict[str, float] = field(default_factory=lambda: {
        "ES": 50.0, "MES": 5.0,
        "NQ": 20.0, "MNQ": 2.0,
        "YM": 5.0, "MYM": 0.5,
        "RTY": 50.0, "M2K": 5.0,
        "CL": 1000.0, "MCL": 100.0,
        "GC": 100.0, "MGC": 10.0,
        "SI": 5000.0, "SIL": 1000.0,
        "HG": 25000.0,
        "NG": 10000.0,
        "ZB": 1000.0, "ZN": 1000.0, "ZF": 1000.0, "ZT": 2000.0,
        "6E": 125000.0, "6J": 12500000.0, "6B": 62500.0, "6A": 100000.0,
    })


@dataclass
class TPTState:
    """
    Current TPT account state.
    Tracks progress toward passing or failing.
    """
    status: TPTStatus = TPTStatus.ACTIVE
    current_balance: float = 50000.0
    high_water_mark: float = 50000.0
    total_pnl: float = 0.0
    trading_days: int = 0
    best_day_pnl: float = 0.0

    # Daily tracking
    daily_pnl: float = 0.0
    daily_trades: int = 0
    current_contracts: int = 0

    # History
    daily_pnl_history: List[float] = field(default_factory=list)

    def update_balance(self, pnl: float) -> None:
        """Update balance after trade."""
        self.current_balance += pnl
        self.total_pnl += pnl
        self.daily_pnl += pnl

        if pnl > 0:
            self.high_water_mark = max(self.high_water_mark, self.current_balance)

        if self.daily_pnl > self.best_day_pnl:
            self.best_day_pnl = self.daily_pnl

    def end_day(self) -> None:
        """End of trading day processing."""
        if self.daily_trades > 0:
            self.trading_days += 1
            self.daily_pnl_history.append(self.daily_pnl)

        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.current_contracts = 0

    def check_status(self, rules: TPTRules) -> TPTStatus:
        """Check and update account status."""
        # Check for failure
        if self.current_balance < rules.balance_floor:
            self.status = TPTStatus.FAILED
            return self.status

        # Check for pass
        if (
            self.total_pnl >= rules.profit_target
            and self.trading_days >= rules.min_trading_days
            and self._check_consistency(rules)
        ):
            self.status = TPTStatus.PASSED
            return self.status

        return self.status

    def _check_consistency(self, rules: TPTRules) -> bool:
        """Check 50% consistency rule."""
        if not self.daily_pnl_history or self.total_pnl <= 0:
            return True

        max_day = max(self.daily_pnl_history)
        return max_day <= self.total_pnl * rules.max_single_day_pct

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "current_balance": self.current_balance,
            "high_water_mark": self.high_water_mark,
            "total_pnl": self.total_pnl,
            "trading_days": self.trading_days,
            "best_day_pnl": self.best_day_pnl,
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
        }


@dataclass
class TradeSetup:
    """A potential trade setup identified by the strategy."""
    setup_id: str
    timestamp: datetime
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float

    # Sizing
    contracts: int = 1
    risk_amount: float = 0.0
    reward_amount: float = 0.0
    risk_reward: float = 0.0

    # Confidence
    confidence: float = 0.0
    setup_type: str = ""  # 'ict_fvg', 'ict_ob', 'momentum', etc.

    # Execution
    executed: bool = False
    result: Optional[str] = None  # 'win', 'loss', 'breakeven'
    actual_pnl: float = 0.0


class TPTAggressiveStrategy:
    """
    TPT Aggressive Trading Strategy.

    Designed to quickly pass TPT evaluation by:
    1. Trading high-probability setups
    2. Using optimal position sizing
    3. Managing risk per trade
    4. Respecting daily targets

    Matches quant-platform/brain/tpt_aggressive.py behavior.
    """

    def __init__(self, rules: Optional[TPTRules] = None):
        self.rules = rules or TPTRules()
        self.state = TPTState()

        # Strategy parameters
        self.daily_target: float = 300.0      # $300/day target
        self.daily_max: float = 600.0         # Stop at $600/day
        self.daily_min: float = -400.0        # Stop loss for day
        self.max_risk_per_trade: float = 0.01  # 1% risk per trade
        self.min_rr_ratio: float = 1.5        # Minimum R:R
        self.target_rr_ratio: float = 2.0     # Target R:R

        # Preferred contracts for each symbol
        self.preferred_contracts: Dict[str, int] = {
            "ES": 2, "MES": 4,
            "NQ": 1, "MNQ": 4,
            "CL": 1, "GC": 1,
        }

        # Stop loss points per symbol
        self.stop_points: Dict[str, float] = {
            "ES": 4.0, "MES": 4.0,
            "NQ": 16.0, "MNQ": 16.0,
            "YM": 20.0, "MYM": 20.0,
            "CL": 0.20, "GC": 3.0,
        }

        # Session preferences
        self.preferred_sessions: List[SessionType] = [
            SessionType.NY_OPEN,
            SessionType.LONDON,
        ]

        logger.info("TPTAggressiveStrategy initialized")

    def should_trade_now(self, current_time: time) -> Tuple[bool, str]:
        """
        Check if we should be trading now.

        Returns:
            (should_trade, reason)
        """
        # Check account status
        if self.state.status != TPTStatus.ACTIVE:
            return False, f"Account status: {self.state.status.value}"

        # Check daily limits
        if self.state.daily_pnl >= self.daily_max:
            return False, f"Daily max reached: ${self.state.daily_pnl:.2f}"

        if self.state.daily_pnl <= self.daily_min:
            return False, f"Daily loss limit: ${self.state.daily_pnl:.2f}"

        # Check trading hours
        end_time = time(17, 0)  # 5PM ET
        if current_time >= end_time:
            return False, "After trading hours"

        return True, "OK"

    def evaluate_signal(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Tuple[bool, TradeSetup]:
        """
        Evaluate a trading signal.

        Args:
            symbol: Trading symbol
            direction: 'LONG' or 'SHORT'
            confidence: Signal confidence (0-1)
            entry_price: Proposed entry
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            (should_take, setup)
        """
        # Validate symbol
        if symbol not in self.rules.permitted_products:
            setup = self._create_setup(symbol, direction, entry_price, stop_loss, take_profit)
            return False, setup

        # Calculate risk/reward
        if direction == "LONG":
            risk_points = entry_price - stop_loss
            reward_points = take_profit - entry_price
        else:
            risk_points = stop_loss - entry_price
            reward_points = entry_price - take_profit

        if risk_points <= 0 or reward_points <= 0:
            setup = self._create_setup(symbol, direction, entry_price, stop_loss, take_profit)
            return False, setup

        rr_ratio = reward_points / risk_points

        # Get contract sizing
        contracts = self._calculate_contracts(symbol, risk_points)
        multiplier = self.rules.contract_multipliers.get(symbol, 1.0)
        risk_amount = contracts * risk_points * multiplier
        reward_amount = contracts * reward_points * multiplier

        # Create setup
        setup = TradeSetup(
            setup_id=f"setup_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(),
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            contracts=contracts,
            risk_amount=risk_amount,
            reward_amount=reward_amount,
            risk_reward=rr_ratio,
            confidence=confidence,
        )

        # Evaluation criteria
        reasons_to_reject = []

        # 1. Minimum confidence
        if confidence < 0.55:
            reasons_to_reject.append(f"Low confidence: {confidence:.2f}")

        # 2. Minimum R:R
        if rr_ratio < self.min_rr_ratio:
            reasons_to_reject.append(f"Low R:R: {rr_ratio:.2f}")

        # 3. Risk amount check
        max_risk = self.state.current_balance * self.max_risk_per_trade
        if risk_amount > max_risk:
            reasons_to_reject.append(f"Risk too high: ${risk_amount:.2f}")

        # 4. Contract limits
        total_contracts = self.state.current_contracts + contracts
        if total_contracts > self.rules.max_contracts:
            reasons_to_reject.append(f"Contract limit: {total_contracts}")

        # 5. Daily target check (optional - be more aggressive if behind)
        if self.state.daily_pnl >= self.daily_target and confidence < 0.70:
            reasons_to_reject.append("Daily target met, need high confidence")

        if reasons_to_reject:
            logger.debug(f"Signal rejected: {', '.join(reasons_to_reject)}")
            return False, setup

        return True, setup

    def _create_setup(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop: float,
        target: float,
    ) -> TradeSetup:
        """Create a basic trade setup."""
        return TradeSetup(
            setup_id=f"setup_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(),
            symbol=symbol,
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
        )

    def _calculate_contracts(self, symbol: str, risk_points: float) -> int:
        """Calculate optimal contract size."""
        # Get preferred size for symbol
        preferred = self.preferred_contracts.get(symbol, 1)

        # Get multiplier
        multiplier = self.rules.contract_multipliers.get(symbol, 1.0)

        # Calculate max contracts based on risk
        max_risk = self.state.current_balance * self.max_risk_per_trade
        risk_per_contract = risk_points * multiplier
        max_contracts_by_risk = int(max_risk / risk_per_contract) if risk_per_contract > 0 else 1

        # Respect limits
        contracts = min(preferred, max_contracts_by_risk, self.rules.max_contracts)
        contracts = max(contracts, self.rules.min_contracts)

        # Don't exceed remaining capacity
        remaining = self.rules.max_contracts - self.state.current_contracts
        contracts = min(contracts, remaining)

        return max(0, contracts)

    def record_trade_result(
        self,
        setup: TradeSetup,
        exit_price: float,
        result: str,
    ) -> float:
        """
        Record trade result and update state.

        Args:
            setup: The trade setup
            exit_price: Exit price
            result: 'win', 'loss', or 'breakeven'

        Returns:
            P&L amount
        """
        multiplier = self.rules.contract_multipliers.get(setup.symbol, 1.0)

        if setup.direction == "LONG":
            pnl = (exit_price - setup.entry_price) * setup.contracts * multiplier
        else:
            pnl = (setup.entry_price - exit_price) * setup.contracts * multiplier

        setup.executed = True
        setup.result = result
        setup.actual_pnl = pnl

        # Update state
        self.state.update_balance(pnl)
        self.state.daily_trades += 1
        self.state.current_contracts -= setup.contracts

        # Check status
        self.state.check_status(self.rules)

        logger.info(
            f"Trade result: {setup.symbol} {setup.direction} "
            f"PnL=${pnl:.2f} Daily=${self.state.daily_pnl:.2f}"
        )

        return pnl

    def get_current_session(self, current_time: time) -> SessionType:
        """Determine current trading session."""
        if time(20, 0) <= current_time or current_time < time(0, 0):
            return SessionType.ASIAN
        elif time(2, 0) <= current_time < time(5, 0):
            return SessionType.LONDON
        elif time(7, 0) <= current_time < time(10, 0):
            return SessionType.NY_OPEN
        elif time(10, 0) <= current_time < time(12, 0):
            return SessionType.NY_CLOSE
        else:
            return SessionType.OVERNIGHT

    def get_daily_progress(self) -> Dict[str, Any]:
        """Get daily progress summary."""
        return {
            "daily_pnl": self.state.daily_pnl,
            "daily_target": self.daily_target,
            "target_pct": self.state.daily_pnl / self.daily_target * 100 if self.daily_target else 0,
            "daily_trades": self.state.daily_trades,
            "at_target": self.state.daily_pnl >= self.daily_target,
            "at_max": self.state.daily_pnl >= self.daily_max,
            "at_loss_limit": self.state.daily_pnl <= self.daily_min,
        }

    def get_account_progress(self) -> Dict[str, Any]:
        """Get overall account progress."""
        pct_to_target = (self.state.total_pnl / self.rules.profit_target * 100) if self.rules.profit_target else 0
        pct_to_floor = (
            (self.state.current_balance - self.rules.balance_floor) /
            (self.rules.initial_balance - self.rules.balance_floor) * 100
        )

        return {
            "status": self.state.status.value,
            "current_balance": self.state.current_balance,
            "total_pnl": self.state.total_pnl,
            "profit_target": self.rules.profit_target,
            "pct_to_target": pct_to_target,
            "trading_days": self.state.trading_days,
            "min_trading_days": self.rules.min_trading_days,
            "days_remaining": max(0, self.rules.min_trading_days - self.state.trading_days),
            "buffer_to_floor": self.state.current_balance - self.rules.balance_floor,
            "pct_buffer": pct_to_floor,
            "consistency_ok": self.state._check_consistency(self.rules),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get full strategy status."""
        return {
            "rules": {
                "initial_balance": self.rules.initial_balance,
                "profit_target": self.rules.profit_target,
                "balance_floor": self.rules.balance_floor,
                "max_contracts": self.rules.max_contracts,
            },
            "state": self.state.to_dict(),
            "daily_progress": self.get_daily_progress(),
            "account_progress": self.get_account_progress(),
            "strategy_params": {
                "daily_target": self.daily_target,
                "daily_max": self.daily_max,
                "daily_min": self.daily_min,
                "max_risk_per_trade": self.max_risk_per_trade,
                "min_rr_ratio": self.min_rr_ratio,
            },
        }
