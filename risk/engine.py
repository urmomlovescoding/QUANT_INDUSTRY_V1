"""
QUANT_INDUSTRY_V1 Risk Engine

Comprehensive risk management:
- Position sizing
- Risk limits and checks
- Exposure monitoring
- VaR/CVaR calculation
- Drawdown controls

Rollback Plan: Delete this file
Tests Required: Risk limit enforcement, position sizing accuracy
Failure Modes: Block trades, reduce positions
"""

import numpy as np
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# RISK TYPES
# =============================================================================

class RiskLevel(Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LimitType(Enum):
    """Types of risk limits."""
    MAX_POSITION_SIZE = "max_position_size"
    MAX_POSITION_VALUE = "max_position_value"
    MAX_PORTFOLIO_EXPOSURE = "max_portfolio_exposure"
    MAX_SECTOR_EXPOSURE = "max_sector_exposure"
    MAX_SINGLE_TRADE = "max_single_trade"
    MAX_DAILY_LOSS = "max_daily_loss"
    MAX_DRAWDOWN = "max_drawdown"
    MAX_VAR = "max_var"
    MAX_LEVERAGE = "max_leverage"
    MIN_CASH = "min_cash"


@dataclass
class RiskLimit:
    """A risk limit definition."""
    limit_type: LimitType
    value: float
    current_value: float = 0.0
    breached: bool = False
    breach_count: int = 0
    last_breach: Optional[datetime] = None
    action: str = "warn"  # warn, block, reduce


@dataclass
class RiskCheck:
    """Result of a risk check."""
    passed: bool
    limit_type: LimitType
    current_value: float
    limit_value: float
    utilization: float  # percentage of limit used
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskAssessment:
    """Complete risk assessment for a trade."""
    approved: bool
    checks: List[RiskCheck]
    risk_score: float  # 0-100
    risk_level: RiskLevel
    position_size_adjustment: float = 1.0  # Multiplier for position sizing
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'approved': self.approved,
            'checks': [
                {
                    'limit_type': c.limit_type.value,
                    'passed': c.passed,
                    'current': c.current_value,
                    'limit': c.limit_value,
                    'utilization': c.utilization,
                    'message': c.message,
                }
                for c in self.checks
            ],
            'risk_score': self.risk_score,
            'risk_level': self.risk_level.value,
            'position_size_adjustment': self.position_size_adjustment,
            'message': self.message,
        }


# =============================================================================
# POSITION SIZER
# =============================================================================

class PositionSizer(ABC):
    """Abstract position sizing strategy."""

    @abstractmethod
    def calculate_size(
        self,
        signal_strength: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
        risk_params: Dict[str, Any]
    ) -> float:
        """Calculate position size."""
        pass


class FixedFractionSizer(PositionSizer):
    """Fixed fraction position sizing (Kelly-like)."""

    def __init__(
        self,
        max_fraction: float = 0.1,
        scale_by_confidence: bool = True
    ):
        self.max_fraction = max_fraction
        self.scale_by_confidence = scale_by_confidence

    def calculate_size(
        self,
        signal_strength: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
        risk_params: Dict[str, Any]
    ) -> float:
        # Base size
        base_size = portfolio_value * self.max_fraction

        # Scale by signal strength (confidence)
        if self.scale_by_confidence:
            base_size *= abs(signal_strength)

        return base_size


class VolatilityScaledSizer(PositionSizer):
    """Volatility-adjusted position sizing."""

    def __init__(
        self,
        target_risk: float = 0.02,  # 2% daily risk
        vol_lookback: int = 20
    ):
        self.target_risk = target_risk
        self.vol_lookback = vol_lookback

    def calculate_size(
        self,
        signal_strength: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
        risk_params: Dict[str, Any]
    ) -> float:
        if volatility <= 0:
            volatility = 0.02  # Default 2% vol

        # Size to achieve target risk
        position_value = portfolio_value * self.target_risk / volatility

        # Scale by confidence
        position_value *= abs(signal_strength)

        return position_value


class KellyCriterionSizer(PositionSizer):
    """Kelly criterion position sizing."""

    def __init__(
        self,
        fraction: float = 0.25,  # Fractional Kelly
        max_position: float = 0.25
    ):
        self.fraction = fraction
        self.max_position = max_position

    def calculate_size(
        self,
        signal_strength: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
        risk_params: Dict[str, Any]
    ) -> float:
        win_rate = risk_params.get('win_rate', 0.5)
        avg_win = risk_params.get('avg_win', 0.02)
        avg_loss = risk_params.get('avg_loss', 0.01)

        if avg_loss == 0:
            return 0

        # Kelly formula: f = (p * b - q) / b
        # where p = win rate, q = 1-p, b = win/loss ratio
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p

        kelly_fraction = (p * b - q) / b if b > 0 else 0

        # Apply fractional Kelly
        kelly_fraction *= self.fraction

        # Cap at max position
        kelly_fraction = min(kelly_fraction, self.max_position)

        # Scale by signal strength
        kelly_fraction *= abs(signal_strength)

        return portfolio_value * max(0, kelly_fraction)


# =============================================================================
# RISK ENGINE
# =============================================================================

class RiskEngine:
    """
    Main risk management engine.

    Enforces risk limits and calculates position sizes.
    """

    def __init__(
        self,
        portfolio_value: float = 100000.0,
        position_sizer: PositionSizer = None
    ):
        self.portfolio_value = portfolio_value
        self.position_sizer = position_sizer or VolatilityScaledSizer()

        # Risk limits
        self.limits: Dict[LimitType, RiskLimit] = {}
        self._setup_default_limits()

        # Positions tracking
        self.positions: Dict[str, float] = {}  # symbol -> value
        self.sector_exposures: Dict[str, float] = {}  # sector -> value

        # P&L tracking
        self.daily_pnl = 0.0
        self.peak_value = portfolio_value
        self.current_drawdown = 0.0

        # History
        self.breach_history: List[Dict[str, Any]] = []

        self._lock = threading.RLock()

    def _setup_default_limits(self) -> None:
        """Setup default risk limits."""
        self.limits = {
            LimitType.MAX_POSITION_SIZE: RiskLimit(
                limit_type=LimitType.MAX_POSITION_SIZE,
                value=0.10,  # 10% max position
                action="reduce"
            ),
            LimitType.MAX_POSITION_VALUE: RiskLimit(
                limit_type=LimitType.MAX_POSITION_VALUE,
                value=25000,  # $25k max
                action="reduce"
            ),
            LimitType.MAX_PORTFOLIO_EXPOSURE: RiskLimit(
                limit_type=LimitType.MAX_PORTFOLIO_EXPOSURE,
                value=1.0,  # 100% exposure
                action="block"
            ),
            LimitType.MAX_SECTOR_EXPOSURE: RiskLimit(
                limit_type=LimitType.MAX_SECTOR_EXPOSURE,
                value=0.30,  # 30% sector limit
                action="warn"
            ),
            LimitType.MAX_SINGLE_TRADE: RiskLimit(
                limit_type=LimitType.MAX_SINGLE_TRADE,
                value=0.05,  # 5% single trade
                action="reduce"
            ),
            LimitType.MAX_DAILY_LOSS: RiskLimit(
                limit_type=LimitType.MAX_DAILY_LOSS,
                value=0.02,  # 2% daily loss limit
                action="block"
            ),
            LimitType.MAX_DRAWDOWN: RiskLimit(
                limit_type=LimitType.MAX_DRAWDOWN,
                value=0.10,  # 10% max drawdown
                action="block"
            ),
            LimitType.MAX_VAR: RiskLimit(
                limit_type=LimitType.MAX_VAR,
                value=0.03,  # 3% VaR limit
                action="warn"
            ),
            LimitType.MAX_LEVERAGE: RiskLimit(
                limit_type=LimitType.MAX_LEVERAGE,
                value=2.0,  # 2x leverage
                action="block"
            ),
            LimitType.MIN_CASH: RiskLimit(
                limit_type=LimitType.MIN_CASH,
                value=0.05,  # 5% min cash
                action="warn"
            ),
        }

    def set_limit(
        self,
        limit_type: LimitType,
        value: float,
        action: str = "warn"
    ) -> None:
        """Set or update a risk limit."""
        self.limits[limit_type] = RiskLimit(
            limit_type=limit_type,
            value=value,
            action=action
        )

    def check_pre_trade(
        self,
        symbol: str,
        proposed_value: float,
        side: str,
        sector: str = None
    ) -> RiskAssessment:
        """
        Pre-trade risk check.

        Args:
            symbol: Trading symbol
            proposed_value: Proposed trade value (positive for buy, negative for sell)
            side: 'buy' or 'sell'
            sector: Sector for sector exposure check

        Returns:
            RiskAssessment with approval decision
        """
        checks = []
        all_passed = True
        adjustment = 1.0

        with self._lock:
            # Current position
            current_position = self.positions.get(symbol, 0.0)
            new_position = current_position + proposed_value if side == 'buy' else current_position - abs(proposed_value)

            # Total exposure
            total_exposure = sum(abs(v) for v in self.positions.values())
            new_exposure = total_exposure + abs(proposed_value) - abs(current_position) + abs(new_position)

            # Check 1: Single trade size
            check = self._check_limit(
                LimitType.MAX_SINGLE_TRADE,
                abs(proposed_value) / self.portfolio_value,
                f"Trade size {abs(proposed_value):.2f}"
            )
            checks.append(check)
            if not check.passed:
                all_passed = False
                if self.limits[LimitType.MAX_SINGLE_TRADE].action == "reduce":
                    adjustment *= check.limit_value / check.current_value

            # Check 2: Position size
            check = self._check_limit(
                LimitType.MAX_POSITION_SIZE,
                abs(new_position) / self.portfolio_value,
                f"Position size for {symbol}"
            )
            checks.append(check)
            if not check.passed:
                if self.limits[LimitType.MAX_POSITION_SIZE].action == "reduce":
                    max_pos = self.portfolio_value * self.limits[LimitType.MAX_POSITION_SIZE].value
                    allowed = max_pos - abs(current_position)
                    if allowed > 0:
                        adjustment *= allowed / abs(proposed_value)
                    else:
                        all_passed = False

            # Check 3: Position value
            check = self._check_limit(
                LimitType.MAX_POSITION_VALUE,
                abs(new_position),
                f"Position value for {symbol}"
            )
            checks.append(check)
            if not check.passed and self.limits[LimitType.MAX_POSITION_VALUE].action == "block":
                all_passed = False

            # Check 4: Portfolio exposure
            check = self._check_limit(
                LimitType.MAX_PORTFOLIO_EXPOSURE,
                new_exposure / self.portfolio_value,
                "Portfolio exposure"
            )
            checks.append(check)
            if not check.passed and self.limits[LimitType.MAX_PORTFOLIO_EXPOSURE].action == "block":
                all_passed = False

            # Check 5: Sector exposure
            if sector:
                sector_exp = self.sector_exposures.get(sector, 0.0) + abs(proposed_value)
                check = self._check_limit(
                    LimitType.MAX_SECTOR_EXPOSURE,
                    sector_exp / self.portfolio_value,
                    f"Sector exposure for {sector}"
                )
                checks.append(check)
                if not check.passed and self.limits[LimitType.MAX_SECTOR_EXPOSURE].action == "block":
                    all_passed = False

            # Check 6: Daily loss limit
            check = self._check_limit(
                LimitType.MAX_DAILY_LOSS,
                abs(self.daily_pnl) / self.portfolio_value if self.daily_pnl < 0 else 0,
                "Daily loss"
            )
            checks.append(check)
            if not check.passed and self.limits[LimitType.MAX_DAILY_LOSS].action == "block":
                all_passed = False

            # Check 7: Drawdown limit
            check = self._check_limit(
                LimitType.MAX_DRAWDOWN,
                self.current_drawdown,
                "Current drawdown"
            )
            checks.append(check)
            if not check.passed and self.limits[LimitType.MAX_DRAWDOWN].action == "block":
                all_passed = False

        # Calculate risk score
        risk_score = self._calculate_risk_score(checks)
        risk_level = self._get_risk_level(risk_score)

        # Generate message
        failed_checks = [c for c in checks if not c.passed]
        if failed_checks:
            message = "; ".join(c.message for c in failed_checks[:3])
        else:
            message = "All risk checks passed"

        return RiskAssessment(
            approved=all_passed,
            checks=checks,
            risk_score=risk_score,
            risk_level=risk_level,
            position_size_adjustment=max(0, min(1, adjustment)),
            message=message,
        )

    def _check_limit(
        self,
        limit_type: LimitType,
        current_value: float,
        context: str
    ) -> RiskCheck:
        """Check a single limit."""
        limit = self.limits.get(limit_type)
        if not limit:
            return RiskCheck(
                passed=True,
                limit_type=limit_type,
                current_value=current_value,
                limit_value=float('inf'),
                utilization=0,
                message=f"No limit set for {limit_type.value}"
            )

        passed = current_value <= limit.value
        utilization = current_value / limit.value if limit.value > 0 else 0

        if not passed:
            limit.breached = True
            limit.breach_count += 1
            limit.last_breach = datetime.now(timezone.utc)

            self.breach_history.append({
                'limit_type': limit_type.value,
                'current_value': current_value,
                'limit_value': limit.value,
                'context': context,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })

        return RiskCheck(
            passed=passed,
            limit_type=limit_type,
            current_value=current_value,
            limit_value=limit.value,
            utilization=min(1.0, utilization),
            message=f"{context}: {current_value:.2%} of {limit.value:.2%} limit" if limit.value < 100 else f"{context}: {current_value:.2f} / {limit.value:.2f}",
        )

    def _calculate_risk_score(self, checks: List[RiskCheck]) -> float:
        """Calculate overall risk score from checks."""
        if not checks:
            return 0.0

        # Weight by utilization
        total_util = sum(c.utilization for c in checks)
        avg_util = total_util / len(checks)

        # Higher score = higher risk
        risk_score = avg_util * 100

        # Penalty for failed checks
        failed = sum(1 for c in checks if not c.passed)
        risk_score += failed * 10

        return min(100, risk_score)

    def _get_risk_level(self, score: float) -> RiskLevel:
        """Get risk level from score."""
        if score < 30:
            return RiskLevel.LOW
        elif score < 60:
            return RiskLevel.MEDIUM
        elif score < 80:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def calculate_position_size(
        self,
        symbol: str,
        signal_strength: float,
        volatility: float,
        side: str,
        risk_params: Dict[str, Any] = None
    ) -> Tuple[float, RiskAssessment]:
        """
        Calculate appropriate position size.

        Args:
            symbol: Trading symbol
            signal_strength: Signal strength (-1 to 1)
            volatility: Asset volatility
            side: 'buy' or 'sell'
            risk_params: Additional risk parameters

        Returns:
            Tuple of (position_size, risk_assessment)
        """
        risk_params = risk_params or {}

        current_position = self.positions.get(symbol, 0.0)

        # Calculate base size
        base_size = self.position_sizer.calculate_size(
            signal_strength=signal_strength,
            volatility=volatility,
            portfolio_value=self.portfolio_value,
            current_position=current_position,
            risk_params=risk_params,
        )

        # Run pre-trade check
        assessment = self.check_pre_trade(symbol, base_size, side)

        # Apply adjustment
        final_size = base_size * assessment.position_size_adjustment

        return final_size, assessment

    def update_position(self, symbol: str, value: float, sector: str = None) -> None:
        """Update position tracking."""
        with self._lock:
            self.positions[symbol] = value

            if sector:
                self.sector_exposures[sector] = sum(
                    v for s, v in self.positions.items()
                    # Would need symbol-to-sector mapping
                )

    def update_pnl(self, pnl: float) -> None:
        """Update P&L tracking."""
        with self._lock:
            self.daily_pnl = pnl
            self.portfolio_value = self.peak_value + pnl

            # Update peak and drawdown
            if self.portfolio_value > self.peak_value:
                self.peak_value = self.portfolio_value

            self.current_drawdown = (self.peak_value - self.portfolio_value) / self.peak_value

    def reset_daily(self) -> None:
        """Reset daily counters."""
        with self._lock:
            self.daily_pnl = 0.0

    def calculate_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
        horizon: int = 1
    ) -> float:
        """Calculate Value at Risk."""
        if len(returns) < 20:
            return 0.0

        # Historical VaR
        percentile = (1 - confidence) * 100
        var = np.percentile(returns, percentile)

        # Scale to horizon
        var *= np.sqrt(horizon)

        return abs(var)

    def calculate_cvar(
        self,
        returns: np.ndarray,
        confidence: float = 0.95
    ) -> float:
        """Calculate Conditional VaR (Expected Shortfall)."""
        if len(returns) < 20:
            return 0.0

        var = self.calculate_var(returns, confidence)
        cvar = np.mean(returns[returns <= -var])

        return abs(cvar)

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary."""
        with self._lock:
            total_exposure = sum(abs(v) for v in self.positions.values())

            return {
                'portfolio_value': self.portfolio_value,
                'total_exposure': total_exposure,
                'exposure_pct': total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0,
                'position_count': len([p for p in self.positions.values() if p != 0]),
                'daily_pnl': self.daily_pnl,
                'daily_return': self.daily_pnl / (self.portfolio_value - self.daily_pnl) if self.portfolio_value > self.daily_pnl else 0,
                'current_drawdown': self.current_drawdown,
                'peak_value': self.peak_value,
                'limits': {
                    lt.value: {
                        'value': lim.value,
                        'breached': lim.breached,
                        'breach_count': lim.breach_count,
                    }
                    for lt, lim in self.limits.items()
                },
                'sector_exposures': self.sector_exposures.copy(),
            }
