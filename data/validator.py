"""
QUANT_INDUSTRY_V1 Data Validator

Data quality validation with comprehensive checks.

Rollback Plan: Delete this file
Tests Required: Unit tests for each validation rule
Failure Modes: Validation error -> quarantine data, log, continue
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

from .fetcher import MarketData, Bar, Timeframe

logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION TYPES
# =============================================================================

class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationCategory(Enum):
    """Categories of validation checks."""
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    OUTLIER = "outlier"
    FRESHNESS = "freshness"
    INTEGRITY = "integrity"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    bar_index: Optional[int] = None
    timestamp: Optional[datetime] = None
    value: Optional[Any] = None
    expected: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category.value,
            'severity': self.severity.value,
            'message': self.message,
            'field': self.field,
            'bar_index': self.bar_index,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'value': self.value,
            'expected': self.expected,
        }


@dataclass
class ValidationResult:
    """Result of data validation."""
    valid: bool
    quality_score: float  # 0.0 to 1.0
    issues: List[ValidationIssue] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    bars_checked: int = 0
    bars_quarantined: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.CRITICAL)

    def has_critical(self) -> bool:
        return self.critical_count > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'quality_score': self.quality_score,
            'issues': [i.to_dict() for i in self.issues],
            'checked_at': self.checked_at.isoformat(),
            'bars_checked': self.bars_checked,
            'bars_quarantined': self.bars_quarantined,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'critical_count': self.critical_count,
        }


# =============================================================================
# VALIDATION RULES
# =============================================================================

@dataclass
class ValidationConfig:
    """Configuration for data validation."""

    # OHLC consistency
    check_ohlc_consistency: bool = True

    # Price outliers
    check_price_outliers: bool = True
    price_zscore_threshold: float = 4.0  # Standard deviations
    price_change_threshold: float = 0.20  # 20% max single-bar change

    # Volume outliers
    check_volume_outliers: bool = True
    volume_zscore_threshold: float = 5.0

    # Gaps and missing data
    check_gaps: bool = True
    max_gap_multiplier: float = 3.0  # Max gap as multiple of expected interval

    # Staleness
    check_staleness: bool = True
    max_staleness_seconds: float = 300.0  # 5 minutes

    # Negative values
    check_negative_values: bool = True

    # Zero values
    check_zero_prices: bool = True
    check_zero_volume: bool = True  # Warning only

    # Minimum bars
    min_bars_required: int = 5

    # Quality score weights
    weight_completeness: float = 0.3
    weight_consistency: float = 0.3
    weight_outliers: float = 0.2
    weight_freshness: float = 0.2


class DataValidator:
    """
    Comprehensive data validator.

    Features:
    - OHLC consistency checks (High >= Low, etc.)
    - Price outlier detection (z-score, max change)
    - Volume outlier detection
    - Gap detection
    - Staleness checking
    - Quality scoring
    """

    def __init__(self, config: ValidationConfig = None):
        self.config = config or ValidationConfig()

    def validate(self, data: MarketData) -> ValidationResult:
        """
        Validate market data.

        Args:
            data: MarketData to validate

        Returns:
            ValidationResult with issues and quality score
        """
        issues: List[ValidationIssue] = []
        bars = data.bars
        bars_quarantined = 0

        # Check minimum bars
        if len(bars) < self.config.min_bars_required:
            issues.append(ValidationIssue(
                category=ValidationCategory.COMPLETENESS,
                severity=ValidationSeverity.ERROR,
                message=f"Insufficient bars: {len(bars)} < {self.config.min_bars_required}",
                value=len(bars),
                expected=self.config.min_bars_required,
            ))

        if not bars:
            return ValidationResult(
                valid=False,
                quality_score=0.0,
                issues=issues,
                bars_checked=0,
            )

        # Run validation checks
        if self.config.check_ohlc_consistency:
            issues.extend(self._check_ohlc_consistency(bars))

        if self.config.check_negative_values:
            issues.extend(self._check_negative_values(bars))

        if self.config.check_zero_prices:
            issues.extend(self._check_zero_prices(bars))

        if self.config.check_zero_volume:
            issues.extend(self._check_zero_volume(bars))

        if self.config.check_price_outliers:
            issues.extend(self._check_price_outliers(bars))

        if self.config.check_volume_outliers:
            issues.extend(self._check_volume_outliers(bars))

        if self.config.check_gaps:
            issues.extend(self._check_gaps(bars, data.timeframe))

        if self.config.check_staleness:
            issues.extend(self._check_staleness(bars))

        # Count quarantined bars (those with critical issues)
        critical_indices = set()
        for issue in issues:
            if issue.severity == ValidationSeverity.CRITICAL and issue.bar_index is not None:
                critical_indices.add(issue.bar_index)
        bars_quarantined = len(critical_indices)

        # Calculate quality score
        quality_score = self._calculate_quality_score(issues, len(bars))

        # Determine validity
        valid = (
            quality_score >= 0.5 and
            not any(i.severity == ValidationSeverity.CRITICAL for i in issues)
        )

        return ValidationResult(
            valid=valid,
            quality_score=quality_score,
            issues=issues,
            bars_checked=len(bars),
            bars_quarantined=bars_quarantined,
        )

    def _check_ohlc_consistency(self, bars: List[Bar]) -> List[ValidationIssue]:
        """Check OHLC value consistency."""
        issues = []

        for i, bar in enumerate(bars):
            # High should be >= Open, Close, Low
            if bar.high < bar.open or bar.high < bar.close or bar.high < bar.low:
                issues.append(ValidationIssue(
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.ERROR,
                    message="High is not the highest value",
                    field="high",
                    bar_index=i,
                    timestamp=bar.timestamp,
                    value=bar.high,
                ))

            # Low should be <= Open, Close, High
            if bar.low > bar.open or bar.low > bar.close or bar.low > bar.high:
                issues.append(ValidationIssue(
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.ERROR,
                    message="Low is not the lowest value",
                    field="low",
                    bar_index=i,
                    timestamp=bar.timestamp,
                    value=bar.low,
                ))

        return issues

    def _check_negative_values(self, bars: List[Bar]) -> List[ValidationIssue]:
        """Check for negative prices or volumes."""
        issues = []

        for i, bar in enumerate(bars):
            for field in ['open', 'high', 'low', 'close']:
                value = getattr(bar, field)
                if value < 0:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.INTEGRITY,
                        severity=ValidationSeverity.CRITICAL,
                        message=f"Negative {field} value",
                        field=field,
                        bar_index=i,
                        timestamp=bar.timestamp,
                        value=value,
                    ))

            if bar.volume < 0:
                issues.append(ValidationIssue(
                    category=ValidationCategory.INTEGRITY,
                    severity=ValidationSeverity.CRITICAL,
                    message="Negative volume",
                    field="volume",
                    bar_index=i,
                    timestamp=bar.timestamp,
                    value=bar.volume,
                ))

        return issues

    def _check_zero_prices(self, bars: List[Bar]) -> List[ValidationIssue]:
        """Check for zero prices."""
        issues = []

        for i, bar in enumerate(bars):
            for field in ['open', 'high', 'low', 'close']:
                value = getattr(bar, field)
                if value == 0:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.INTEGRITY,
                        severity=ValidationSeverity.CRITICAL,
                        message=f"Zero {field} value",
                        field=field,
                        bar_index=i,
                        timestamp=bar.timestamp,
                        value=value,
                    ))

        return issues

    def _check_zero_volume(self, bars: List[Bar]) -> List[ValidationIssue]:
        """Check for zero volume (warning only)."""
        issues = []

        for i, bar in enumerate(bars):
            if bar.volume == 0:
                issues.append(ValidationIssue(
                    category=ValidationCategory.COMPLETENESS,
                    severity=ValidationSeverity.WARNING,
                    message="Zero volume",
                    field="volume",
                    bar_index=i,
                    timestamp=bar.timestamp,
                ))

        return issues

    def _check_price_outliers(self, bars: List[Bar]) -> List[ValidationIssue]:
        """Check for price outliers using z-score and max change."""
        issues = []

        if len(bars) < 3:
            return issues

        # Calculate statistics
        closes = [bar.close for bar in bars]
        mean_price = sum(closes) / len(closes)
        variance = sum((p - mean_price) ** 2 for p in closes) / len(closes)
        std_price = math.sqrt(variance) if variance > 0 else 0

        # Z-score outliers
        if std_price > 0:
            for i, bar in enumerate(bars):
                zscore = abs(bar.close - mean_price) / std_price
                if zscore > self.config.price_zscore_threshold:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.OUTLIER,
                        severity=ValidationSeverity.WARNING,
                        message=f"Price outlier (z-score: {zscore:.2f})",
                        field="close",
                        bar_index=i,
                        timestamp=bar.timestamp,
                        value=bar.close,
                        expected=f"z < {self.config.price_zscore_threshold}",
                    ))

        # Max single-bar change
        for i in range(1, len(bars)):
            prev_close = bars[i-1].close
            curr_close = bars[i].close

            if prev_close > 0:
                change = abs(curr_close - prev_close) / prev_close
                if change > self.config.price_change_threshold:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.OUTLIER,
                        severity=ValidationSeverity.WARNING,
                        message=f"Large price change: {change*100:.1f}%",
                        field="close",
                        bar_index=i,
                        timestamp=bars[i].timestamp,
                        value=change,
                        expected=f"< {self.config.price_change_threshold*100}%",
                    ))

        return issues

    def _check_volume_outliers(self, bars: List[Bar]) -> List[ValidationIssue]:
        """Check for volume outliers using z-score."""
        issues = []

        if len(bars) < 3:
            return issues

        volumes = [bar.volume for bar in bars if bar.volume > 0]
        if not volumes:
            return issues

        mean_vol = sum(volumes) / len(volumes)
        variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
        std_vol = math.sqrt(variance) if variance > 0 else 0

        if std_vol > 0:
            for i, bar in enumerate(bars):
                if bar.volume > 0:
                    zscore = (bar.volume - mean_vol) / std_vol
                    if zscore > self.config.volume_zscore_threshold:
                        issues.append(ValidationIssue(
                            category=ValidationCategory.OUTLIER,
                            severity=ValidationSeverity.INFO,
                            message=f"Volume spike (z-score: {zscore:.2f})",
                            field="volume",
                            bar_index=i,
                            timestamp=bar.timestamp,
                            value=bar.volume,
                        ))

        return issues

    def _check_gaps(self, bars: List[Bar], timeframe: Timeframe) -> List[ValidationIssue]:
        """Check for time gaps in data."""
        issues = []

        if len(bars) < 2:
            return issues

        # Expected interval
        interval_map = {
            Timeframe.MIN_1: timedelta(minutes=1),
            Timeframe.MIN_5: timedelta(minutes=5),
            Timeframe.MIN_15: timedelta(minutes=15),
            Timeframe.MIN_30: timedelta(minutes=30),
            Timeframe.HOUR_1: timedelta(hours=1),
            Timeframe.HOUR_4: timedelta(hours=4),
            Timeframe.DAY_1: timedelta(days=1),
            Timeframe.WEEK_1: timedelta(weeks=1),
            Timeframe.MONTH_1: timedelta(days=30),
        }

        expected_interval = interval_map.get(timeframe, timedelta(days=1))
        max_gap = expected_interval * self.config.max_gap_multiplier

        for i in range(1, len(bars)):
            gap = bars[i].timestamp - bars[i-1].timestamp

            # Allow for weekends/holidays on daily data
            if timeframe == Timeframe.DAY_1:
                max_gap = timedelta(days=4)  # Allow 4 days for weekends + holidays

            if gap > max_gap:
                issues.append(ValidationIssue(
                    category=ValidationCategory.COMPLETENESS,
                    severity=ValidationSeverity.WARNING,
                    message=f"Data gap: {gap}",
                    bar_index=i,
                    timestamp=bars[i].timestamp,
                    value=gap.total_seconds(),
                    expected=f"< {max_gap.total_seconds()}s",
                ))

        return issues

    def _check_staleness(self, bars: List[Bar]) -> List[ValidationIssue]:
        """Check if data is stale."""
        issues = []

        if not bars:
            return issues

        latest = bars[-1].timestamp
        now = datetime.now(timezone.utc)
        staleness = (now - latest).total_seconds()

        if staleness > self.config.max_staleness_seconds:
            issues.append(ValidationIssue(
                category=ValidationCategory.FRESHNESS,
                severity=ValidationSeverity.WARNING,
                message=f"Data is stale: {staleness:.0f}s old",
                timestamp=latest,
                value=staleness,
                expected=f"< {self.config.max_staleness_seconds}s",
            ))

        return issues

    def _calculate_quality_score(self, issues: List[ValidationIssue], bar_count: int) -> float:
        """Calculate overall quality score from issues."""
        if bar_count == 0:
            return 0.0

        # Start with perfect score
        score = 1.0

        # Deductions by severity
        severity_weights = {
            ValidationSeverity.INFO: 0.01,
            ValidationSeverity.WARNING: 0.05,
            ValidationSeverity.ERROR: 0.15,
            ValidationSeverity.CRITICAL: 0.30,
        }

        for issue in issues:
            deduction = severity_weights.get(issue.severity, 0.05)
            score -= deduction

        # Never go below 0
        return max(0.0, score)


# =============================================================================
# DATA QUALITY FIREWALL
# =============================================================================

class DataQualityFirewall:
    """
    Firewall that blocks bad data from reaching models.

    Features:
    - Configurable validation rules
    - Quarantine for suspicious data
    - Quality thresholds
    - Logging and alerting
    """

    def __init__(
        self,
        config: ValidationConfig = None,
        min_quality_score: float = 0.7,
        block_on_critical: bool = True,
    ):
        self.validator = DataValidator(config)
        self.min_quality_score = min_quality_score
        self.block_on_critical = block_on_critical

        # Quarantine storage
        self._quarantine: Dict[str, List[Tuple[datetime, MarketData, ValidationResult]]] = {}

    def check(self, data: MarketData) -> Tuple[bool, ValidationResult]:
        """
        Check if data passes the firewall.

        Args:
            data: MarketData to check

        Returns:
            Tuple of (passed, ValidationResult)
        """
        result = self.validator.validate(data)

        # Check critical issues
        if self.block_on_critical and result.has_critical():
            self._quarantine_data(data, result)
            logger.warning(
                f"Data blocked for {data.symbol}: critical issues found"
            )
            return False, result

        # Check quality score
        if result.quality_score < self.min_quality_score:
            self._quarantine_data(data, result)
            logger.warning(
                f"Data blocked for {data.symbol}: "
                f"quality score {result.quality_score:.2f} < {self.min_quality_score}"
            )
            return False, result

        # Log warnings
        if result.warning_count > 0:
            logger.info(
                f"Data passed for {data.symbol} with {result.warning_count} warnings"
            )

        return True, result

    def _quarantine_data(self, data: MarketData, result: ValidationResult) -> None:
        """Add data to quarantine."""
        symbol = data.symbol
        if symbol not in self._quarantine:
            self._quarantine[symbol] = []

        self._quarantine[symbol].append((
            datetime.now(timezone.utc),
            data,
            result,
        ))

        # Keep only last 100 quarantined items per symbol
        if len(self._quarantine[symbol]) > 100:
            self._quarantine[symbol] = self._quarantine[symbol][-100:]

    def get_quarantine(self, symbol: str = None) -> Dict[str, List]:
        """Get quarantined data."""
        if symbol:
            return {symbol: self._quarantine.get(symbol, [])}
        return self._quarantine.copy()

    def clear_quarantine(self, symbol: str = None) -> None:
        """Clear quarantine."""
        if symbol:
            self._quarantine.pop(symbol, None)
        else:
            self._quarantine.clear()
