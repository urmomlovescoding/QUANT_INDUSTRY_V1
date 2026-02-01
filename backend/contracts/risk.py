"""
Risk Contract
=============
Canonical interface for risk management.

Risk checks are NON-NEGOTIABLE. No component may bypass them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


class RiskLevel(Enum):
    """Risk severity levels."""
    NORMAL = "normal"       # Within all limits
    ELEVATED = "elevated"   # Approaching limits
    WARNING = "warning"     # Near limits, reduce exposure
    CRITICAL = "critical"   # At limits, no new positions
    HALTED = "halted"       # Trading halted


@dataclass
class RiskLimits:
    """Non-negotiable risk limits."""
    # Loss limits
    max_daily_loss_pct: float = 0.02      # 2%
    max_weekly_loss_pct: float = 0.05     # 5%
    max_drawdown_pct: float = 0.10        # 10%

    # Position limits
    max_position_pct: float = 0.25        # 25% single position
    max_positions: int = 20
    max_gross_exposure: float = 1.5       # 150%
    max_contracts: int = 6                # Prop firm limit

    # Frequency limits
    max_trades_per_day: int = 100
    max_trades_per_hour: int = 20
    min_trade_interval_sec: int = 60

    # Volatility limits
    vix_warning_threshold: float = 25.0
    vix_critical_threshold: float = 40.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_weekly_loss_pct": self.max_weekly_loss_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_position_pct": self.max_position_pct,
            "max_positions": self.max_positions,
            "max_gross_exposure": self.max_gross_exposure,
            "max_contracts": self.max_contracts,
            "max_trades_per_day": self.max_trades_per_day,
            "vix_critical_threshold": self.vix_critical_threshold,
        }


@dataclass
class RiskMetrics:
    """Current risk state."""
    # P&L
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    weekly_pnl: float = 0.0
    weekly_pnl_pct: float = 0.0
    drawdown: float = 0.0
    drawdown_pct: float = 0.0

    # Exposure
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    position_count: int = 0
    largest_position_pct: float = 0.0

    # Activity
    trades_today: int = 0
    trades_this_hour: int = 0
    consecutive_losses: int = 0

    # Volatility
    current_vix: float = 15.0
    portfolio_volatility: float = 0.0

    # Status
    risk_level: RiskLevel = RiskLevel.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": self.daily_pnl_pct,
            "weekly_pnl": self.weekly_pnl,
            "weekly_pnl_pct": self.weekly_pnl_pct,
            "drawdown": self.drawdown,
            "drawdown_pct": self.drawdown_pct,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "position_count": self.position_count,
            "trades_today": self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "current_vix": self.current_vix,
            "risk_level": self.risk_level.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RiskCheck:
    """Result of a risk check."""
    passed: bool
    risk_level: RiskLevel
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    position_size_multiplier: float = 1.0  # Reduce size in high risk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "risk_level": self.risk_level.value,
            "violations": self.violations,
            "warnings": self.warnings,
            "position_size_multiplier": self.position_size_multiplier,
        }


class RiskContract(ABC):
    """
    Risk Service Contract.

    All implementations MUST:
    1. Enforce limits - no exceptions
    2. Block trades when limits breached
    3. Track all risk metrics in real-time
    4. Integrate with SafetyGuard
    """

    @property
    @abstractmethod
    def limits(self) -> RiskLimits:
        """Get current risk limits."""
        pass

    @abstractmethod
    def get_metrics(self) -> RiskMetrics:
        """Get current risk metrics."""
        pass

    @abstractmethod
    def check_trade(
        self,
        symbol: str,
        quantity: int,
        side: str,
        price: float
    ) -> RiskCheck:
        """
        Check if a trade is allowed.

        MUST check:
        1. Daily loss limit
        2. Drawdown limit
        3. Position size limit
        4. Trade frequency limit
        5. VIX/volatility conditions
        """
        pass

    @abstractmethod
    def record_trade_result(
        self,
        symbol: str,
        pnl: float,
        is_win: bool
    ) -> None:
        """
        Record trade result for risk tracking.

        Updates:
        - Daily/weekly P&L
        - Consecutive loss count
        - Trade counts
        """
        pass

    @abstractmethod
    def update_vix(self, vix: float) -> None:
        """Update current VIX level."""
        pass

    @abstractmethod
    def get_position_size_limit(self, symbol: str) -> float:
        """
        Get maximum position size for symbol.

        Considers:
        - Current exposure
        - VIX level
        - Recent losses
        """
        pass

    @abstractmethod
    def is_trading_allowed(self) -> Tuple[bool, str]:
        """
        Check if trading is currently allowed.

        Returns (allowed, reason).
        """
        pass

    @abstractmethod
    def trigger_halt(self, reason: str) -> None:
        """Trigger trading halt."""
        pass

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """Get risk system health."""
        pass
