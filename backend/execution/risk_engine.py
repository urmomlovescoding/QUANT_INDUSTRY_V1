"""
Risk Engine
===========
P0 Critical Feature: Risk management for trade execution.

Implements parity with quant-platform/execution/risk_engine.py
"""
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger("RISK_ENGINE")


class RiskMode(Enum):
    """Risk mode - how aggressively to manage risk."""
    CONSERVATIVE = "conservative"  # Strict limits
    MODERATE = "moderate"          # Balanced
    AGGRESSIVE = "aggressive"      # Looser limits (for paper trading)


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    approved: bool
    reason: str
    adjusted_size_pct: float
    warnings: List[str] = field(default_factory=list)
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "adjusted_size_pct": self.adjusted_size_pct,
            "warnings": self.warnings,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
        }


class RiskEngine:
    """
    Risk engine for trade execution.

    Implements risk checks before any trade execution:
    - Position limits
    - Daily loss limits
    - Drawdown limits
    - Concentration limits
    - Volatility adjustments

    Matches quant-platform behavior for APP_MODE=platform_compat.
    """

    def __init__(self, mode: RiskMode = RiskMode.MODERATE):
        self.mode = mode

        # Position limits
        self.max_position_pct: float = 0.20  # 20% of portfolio max per position
        self.max_total_exposure_pct: float = 0.80  # 80% total exposure

        # Loss limits
        self.daily_loss_limit_pct: float = 0.02  # 2% daily loss limit
        self.max_drawdown_pct: float = 0.10  # 10% max drawdown

        # Trade limits
        self.min_confidence: float = 0.55  # Minimum signal confidence
        self.max_trades_per_day: int = 20

        # State tracking
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.current_drawdown: float = 0.0
        self.positions: Dict[str, float] = {}  # ticker -> size_pct

        # Adjust limits based on mode
        self._apply_mode_adjustments()

        logger.info(f"RiskEngine initialized in {mode.value} mode")

    def _apply_mode_adjustments(self) -> None:
        """Adjust limits based on risk mode."""
        if self.mode == RiskMode.CONSERVATIVE:
            self.max_position_pct = 0.10
            self.max_total_exposure_pct = 0.50
            self.daily_loss_limit_pct = 0.01
            self.min_confidence = 0.65
            self.max_trades_per_day = 10

        elif self.mode == RiskMode.AGGRESSIVE:
            self.max_position_pct = 0.30
            self.max_total_exposure_pct = 1.00
            self.daily_loss_limit_pct = 0.05
            self.min_confidence = 0.50
            self.max_trades_per_day = 50

    def check_trade(
        self,
        ticker: str,
        direction: str,
        size_pct: float,
        confidence: float,
        portfolio_value: float = 100000.0,
    ) -> RiskCheckResult:
        """
        Check if a trade passes risk requirements.

        Args:
            ticker: Symbol to trade
            direction: 'BUY' or 'SELL'
            size_pct: Position size as percentage of portfolio
            confidence: Signal confidence (0.0 - 1.0)
            portfolio_value: Current portfolio value

        Returns:
            RiskCheckResult with approval status and adjusted size
        """
        checks_passed = []
        checks_failed = []
        warnings = []
        adjusted_size = size_pct

        # Check 1: Signal confidence
        if confidence < self.min_confidence:
            checks_failed.append(f"confidence_too_low: {confidence:.2f} < {self.min_confidence:.2f}")
        else:
            checks_passed.append("confidence_ok")

        # Check 2: Position size limit
        if size_pct > self.max_position_pct:
            warnings.append(f"Position size reduced: {size_pct:.1%} -> {self.max_position_pct:.1%}")
            adjusted_size = self.max_position_pct
            checks_passed.append("position_size_adjusted")
        else:
            checks_passed.append("position_size_ok")

        # Check 3: Total exposure
        current_exposure = sum(abs(v) for v in self.positions.values())
        if current_exposure + adjusted_size > self.max_total_exposure_pct:
            remaining = max(0, self.max_total_exposure_pct - current_exposure)
            if remaining > 0:
                adjusted_size = min(adjusted_size, remaining)
                warnings.append(f"Exposure limit: reduced to {adjusted_size:.1%}")
                checks_passed.append("exposure_adjusted")
            else:
                checks_failed.append(f"exposure_limit_exceeded: {current_exposure:.1%}")

        # Check 4: Daily loss limit
        if self.daily_pnl < -self.daily_loss_limit_pct * portfolio_value:
            checks_failed.append(f"daily_loss_limit: ${self.daily_pnl:.2f}")

        # Check 5: Max drawdown
        if self.current_drawdown > self.max_drawdown_pct:
            checks_failed.append(f"max_drawdown: {self.current_drawdown:.1%}")

        # Check 6: Daily trade limit
        if self.daily_trades >= self.max_trades_per_day:
            checks_failed.append(f"daily_trade_limit: {self.daily_trades}")
        else:
            checks_passed.append("trade_count_ok")

        # Determine approval
        approved = len(checks_failed) == 0
        if approved:
            reason = "All risk checks passed"
        else:
            reason = f"Risk checks failed: {', '.join(checks_failed)}"

        return RiskCheckResult(
            approved=approved,
            reason=reason,
            adjusted_size_pct=adjusted_size if approved else 0.0,
            warnings=warnings,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )

    def record_trade(self, ticker: str, size_pct: float, pnl: float = 0.0) -> None:
        """Record a completed trade for tracking."""
        self.positions[ticker] = self.positions.get(ticker, 0) + size_pct
        self.daily_trades += 1
        self.daily_pnl += pnl

        if pnl < 0:
            self.current_drawdown = max(self.current_drawdown, abs(pnl))

        logger.debug(f"Trade recorded: {ticker} {size_pct:.1%} PnL=${pnl:.2f}")

    def close_position(self, ticker: str, pnl: float = 0.0) -> None:
        """Record position close."""
        if ticker in self.positions:
            del self.positions[ticker]
        self.daily_pnl += pnl

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of trading day)."""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info("Daily risk counters reset")

    def get_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        current_exposure = sum(abs(v) for v in self.positions.values())

        return {
            "mode": self.mode.value,
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "current_exposure": current_exposure,
            "max_exposure": self.max_total_exposure_pct,
            "exposure_remaining": self.max_total_exposure_pct - current_exposure,
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown_pct,
            "positions": dict(self.positions),
            "limits": {
                "max_position_pct": self.max_position_pct,
                "daily_loss_limit_pct": self.daily_loss_limit_pct,
                "min_confidence": self.min_confidence,
                "max_trades_per_day": self.max_trades_per_day,
            },
        }
