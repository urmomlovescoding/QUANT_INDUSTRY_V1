"""
Comprehensive Compliance Monitoring System
QUANT_INDUSTRY_V1 - P2 Task 17

Real-time compliance validation and alerting for trading operations.

Features:
- Pre-trade compliance checks
- Position limit monitoring
- Regulatory rule validation (SEC, FINRA)
- Restricted list management
- Trade surveillance
- Audit trail logging
- Real-time alerting

Rollback Plan: Delete this file
Tests Required: Rule validation, alert generation, position limit checks
Failure Modes: Block trades, escalate alerts
"""

import logging
import threading
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & DATA CLASSES
# =============================================================================

class ComplianceStatus(Enum):
    """Compliance check status."""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    WARNING = "warning"


class RuleCategory(Enum):
    """Categories of compliance rules."""
    POSITION_LIMITS = "position_limits"
    TRADING_RESTRICTIONS = "trading_restrictions"
    REGULATORY = "regulatory"
    INTERNAL_POLICY = "internal_policy"
    MARKET_ABUSE = "market_abuse"
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class TradeDirection(Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class ComplianceRule:
    """Definition of a compliance rule."""
    rule_id: str
    name: str
    category: RuleCategory
    description: str
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=lambda: ["warn"])  # warn, block, escalate, log


@dataclass
class ComplianceViolation:
    """Record of a compliance violation."""
    violation_id: str
    rule_id: str
    rule_name: str
    category: RuleCategory
    severity: AlertSeverity
    timestamp: datetime
    details: Dict[str, Any]
    trade_details: Optional[Dict[str, Any]] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'violation_id': self.violation_id,
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'category': self.category.value,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'trade_details': self.trade_details,
            'resolved': self.resolved,
            'resolution_notes': self.resolution_notes,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
        }


@dataclass
class ComplianceCheckResult:
    """Result of a compliance check."""
    status: ComplianceStatus
    passed_rules: List[str]
    failed_rules: List[str]
    warnings: List[str]
    violations: List[ComplianceViolation]
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status.value,
            'passed_rules': self.passed_rules,
            'failed_rules': self.failed_rules,
            'warnings': self.warnings,
            'violations': [v.to_dict() for v in self.violations],
            'message': self.message,
            'metadata': self.metadata,
        }


@dataclass
class TradeRequest:
    """Trade request for compliance check."""
    symbol: str
    direction: TradeDirection
    quantity: float
    price: float
    account_id: str
    trader_id: str
    order_type: str = "market"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def notional_value(self) -> float:
        return self.quantity * self.price


# =============================================================================
# ABSTRACT RULE VALIDATOR
# =============================================================================

class RuleValidator(ABC):
    """Abstract base class for rule validators."""

    def __init__(self, rule: ComplianceRule):
        self.rule = rule

    @abstractmethod
    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        """
        Validate a trade against this rule.
        
        Returns:
            Tuple of (passed, violation_if_failed)
        """
        pass

    def _create_violation(
        self,
        severity: AlertSeverity,
        details: Dict[str, Any],
        trade: TradeRequest
    ) -> ComplianceViolation:
        """Helper to create a violation record."""
        return ComplianceViolation(
            violation_id=self._generate_violation_id(trade),
            rule_id=self.rule.rule_id,
            rule_name=self.rule.name,
            category=self.rule.category,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            details=details,
            trade_details={
                'symbol': trade.symbol,
                'direction': trade.direction.value,
                'quantity': trade.quantity,
                'price': trade.price,
                'notional': trade.notional_value,
                'account': trade.account_id,
                'trader': trade.trader_id,
            }
        )

    def _generate_violation_id(self, trade: TradeRequest) -> str:
        """Generate unique violation ID."""
        data = f"{self.rule.rule_id}:{trade.symbol}:{trade.timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


# =============================================================================
# RULE IMPLEMENTATIONS
# =============================================================================

class PositionLimitValidator(RuleValidator):
    """Validates position limits."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        positions = context.get('positions', {})
        limits = self.rule.parameters

        max_position_pct = limits.get('max_position_pct', 0.10)
        max_position_value = limits.get('max_position_value', 100000)
        portfolio_value = context.get('portfolio_value', 1000000)

        current_position = positions.get(trade.symbol, 0)
        new_position = current_position + trade.quantity if trade.direction == TradeDirection.BUY else current_position - trade.quantity
        new_position_value = new_position * trade.price

        # Check percentage limit
        position_pct = abs(new_position_value) / portfolio_value
        if position_pct > max_position_pct:
            return False, self._create_violation(
                AlertSeverity.CRITICAL,
                {
                    'reason': 'Position size exceeds maximum percentage limit',
                    'current_pct': position_pct,
                    'limit_pct': max_position_pct,
                    'position_value': new_position_value,
                },
                trade
            )

        # Check absolute value limit
        if abs(new_position_value) > max_position_value:
            return False, self._create_violation(
                AlertSeverity.CRITICAL,
                {
                    'reason': 'Position value exceeds maximum dollar limit',
                    'position_value': new_position_value,
                    'limit_value': max_position_value,
                },
                trade
            )

        return True, None


class RestrictedListValidator(RuleValidator):
    """Validates against restricted securities list."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        restricted_list: Set[str] = context.get('restricted_list', set())
        watch_list: Set[str] = context.get('watch_list', set())

        if trade.symbol in restricted_list:
            return False, self._create_violation(
                AlertSeverity.EMERGENCY,
                {
                    'reason': 'Security is on restricted list',
                    'symbol': trade.symbol,
                    'list_type': 'restricted',
                },
                trade
            )

        if trade.symbol in watch_list:
            # Warning only - don't block
            logger.warning(f"Trade in watch list security: {trade.symbol}")

        return True, None


class WashSaleValidator(RuleValidator):
    """Validates for potential wash sale violations."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        trade_history = context.get('trade_history', [])
        wash_sale_window = self.rule.parameters.get('window_days', 30)

        cutoff_date = trade.timestamp - timedelta(days=wash_sale_window)

        # Check for opposing trades within window
        recent_trades = [
            t for t in trade_history
            if t.get('symbol') == trade.symbol
            and datetime.fromisoformat(t.get('timestamp', '2000-01-01')) >= cutoff_date
        ]

        for recent_trade in recent_trades:
            recent_direction = TradeDirection(recent_trade.get('direction', 'buy'))
            if recent_direction != trade.direction:
                # Potential wash sale
                if recent_trade.get('realized_loss', 0) < 0:
                    return False, self._create_violation(
                        AlertSeverity.WARNING,
                        {
                            'reason': 'Potential wash sale violation',
                            'symbol': trade.symbol,
                            'prior_trade_date': recent_trade.get('timestamp'),
                            'prior_loss': recent_trade.get('realized_loss'),
                            'window_days': wash_sale_window,
                        },
                        trade
                    )

        return True, None


class ConcentrationValidator(RuleValidator):
    """Validates sector/industry concentration limits."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        sector_exposures = context.get('sector_exposures', {})
        symbol_sectors = context.get('symbol_sectors', {})
        portfolio_value = context.get('portfolio_value', 1000000)

        max_sector_pct = self.rule.parameters.get('max_sector_pct', 0.25)
        sector = symbol_sectors.get(trade.symbol, 'Unknown')

        current_exposure = sector_exposures.get(sector, 0)
        trade_value = trade.notional_value
        new_exposure = current_exposure + trade_value

        exposure_pct = new_exposure / portfolio_value
        if exposure_pct > max_sector_pct:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Sector concentration exceeds limit',
                    'sector': sector,
                    'current_exposure_pct': exposure_pct,
                    'limit_pct': max_sector_pct,
                },
                trade
            )

        return True, None


class MarketImpactValidator(RuleValidator):
    """Validates for potential market impact concerns."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        market_data = context.get('market_data', {}).get(trade.symbol, {})
        avg_daily_volume = market_data.get('adv', 1000000)

        max_adv_pct = self.rule.parameters.get('max_adv_pct', 0.10)

        volume_pct = trade.quantity / avg_daily_volume if avg_daily_volume > 0 else 1.0

        if volume_pct > max_adv_pct:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Trade size exceeds ADV threshold',
                    'symbol': trade.symbol,
                    'trade_quantity': trade.quantity,
                    'adv': avg_daily_volume,
                    'adv_pct': volume_pct,
                    'limit_pct': max_adv_pct,
                },
                trade
            )

        return True, None


class DailyLossLimitValidator(RuleValidator):
    """Validates daily loss limits."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        daily_pnl = context.get('daily_pnl', 0)
        portfolio_value = context.get('portfolio_value', 1000000)

        max_daily_loss_pct = self.rule.parameters.get('max_daily_loss_pct', 0.02)
        max_daily_loss = portfolio_value * max_daily_loss_pct

        if daily_pnl < -max_daily_loss:
            return False, self._create_violation(
                AlertSeverity.CRITICAL,
                {
                    'reason': 'Daily loss limit exceeded',
                    'daily_pnl': daily_pnl,
                    'limit': -max_daily_loss,
                    'limit_pct': max_daily_loss_pct,
                },
                trade
            )

        return True, None


class PreMarketHoursValidator(RuleValidator):
    """Validates trading during market hours."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        allow_extended_hours = self.rule.parameters.get('allow_extended_hours', False)

        # Simple market hours check (9:30 AM - 4:00 PM ET)
        trade_hour = trade.timestamp.hour
        trade_minute = trade.timestamp.minute
        trade_time = trade_hour * 60 + trade_minute

        market_open = 9 * 60 + 30  # 9:30 AM
        market_close = 16 * 60     # 4:00 PM

        if not allow_extended_hours:
            if trade_time < market_open or trade_time >= market_close:
                return False, self._create_violation(
                    AlertSeverity.WARNING,
                    {
                        'reason': 'Trade attempted outside market hours',
                        'trade_time': trade.timestamp.isoformat(),
                        'market_hours': '9:30 AM - 4:00 PM ET',
                    },
                    trade
                )

        return True, None


# =============================================================================
# COMPLIANCE MONITOR
# =============================================================================

class ComplianceMonitor:
    """
    Real-time compliance monitoring system.
    
    Coordinates all compliance rules and provides unified interface
    for pre-trade and post-trade compliance checks.
    """

    def __init__(self):
        self._rules: Dict[str, ComplianceRule] = {}
        self._validators: Dict[str, RuleValidator] = {}
        self._violations: List[ComplianceViolation] = []
        self._alert_handlers: List[Callable[[ComplianceViolation], None]] = []
        self._lock = threading.RLock()

        # Context data
        self._restricted_list: Set[str] = set()
        self._watch_list: Set[str] = set()

        # Initialize default rules
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Setup default compliance rules."""
        default_rules = [
            ComplianceRule(
                rule_id="POS_LIMIT_001",
                name="Position Size Limit",
                category=RuleCategory.POSITION_LIMITS,
                description="Maximum position size as percentage of portfolio",
                parameters={'max_position_pct': 0.10, 'max_position_value': 100000},
                actions=['block', 'log']
            ),
            ComplianceRule(
                rule_id="RESTRICT_001",
                name="Restricted Securities",
                category=RuleCategory.TRADING_RESTRICTIONS,
                description="Block trading in restricted securities",
                parameters={},
                actions=['block', 'escalate', 'log']
            ),
            ComplianceRule(
                rule_id="WASH_001",
                name="Wash Sale Prevention",
                category=RuleCategory.REGULATORY,
                description="Prevent wash sale violations",
                parameters={'window_days': 30},
                actions=['warn', 'log']
            ),
            ComplianceRule(
                rule_id="CONC_001",
                name="Sector Concentration",
                category=RuleCategory.CONCENTRATION,
                description="Maximum sector exposure limit",
                parameters={'max_sector_pct': 0.25},
                actions=['warn', 'log']
            ),
            ComplianceRule(
                rule_id="IMPACT_001",
                name="Market Impact",
                category=RuleCategory.LIQUIDITY,
                description="Maximum trade size relative to ADV",
                parameters={'max_adv_pct': 0.10},
                actions=['warn', 'log']
            ),
            ComplianceRule(
                rule_id="LOSS_001",
                name="Daily Loss Limit",
                category=RuleCategory.INTERNAL_POLICY,
                description="Maximum daily loss limit",
                parameters={'max_daily_loss_pct': 0.02},
                actions=['block', 'escalate', 'log']
            ),
            ComplianceRule(
                rule_id="HOURS_001",
                name="Market Hours",
                category=RuleCategory.TRADING_RESTRICTIONS,
                description="Restrict trading to market hours",
                parameters={'allow_extended_hours': False},
                actions=['warn', 'log'],
                enabled=False  # Disabled by default
            ),
        ]

        validator_map = {
            "POS_LIMIT_001": PositionLimitValidator,
            "RESTRICT_001": RestrictedListValidator,
            "WASH_001": WashSaleValidator,
            "CONC_001": ConcentrationValidator,
            "IMPACT_001": MarketImpactValidator,
            "LOSS_001": DailyLossLimitValidator,
            "HOURS_001": PreMarketHoursValidator,
        }

        for rule in default_rules:
            self._rules[rule.rule_id] = rule
            validator_class = validator_map.get(rule.rule_id)
            if validator_class:
                self._validators[rule.rule_id] = validator_class(rule)

    def add_rule(self, rule: ComplianceRule, validator: RuleValidator) -> None:
        """Add a custom compliance rule."""
        with self._lock:
            self._rules[rule.rule_id] = rule
            self._validators[rule.rule_id] = validator
            logger.info(f"Added compliance rule: {rule.rule_id} - {rule.name}")

    def enable_rule(self, rule_id: str) -> None:
        """Enable a compliance rule."""
        with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].enabled = True
                logger.info(f"Enabled compliance rule: {rule_id}")

    def disable_rule(self, rule_id: str) -> None:
        """Disable a compliance rule."""
        with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].enabled = False
                logger.info(f"Disabled compliance rule: {rule_id}")

    def update_restricted_list(self, symbols: Set[str]) -> None:
        """Update the restricted securities list."""
        with self._lock:
            self._restricted_list = symbols
            logger.info(f"Updated restricted list: {len(symbols)} securities")

    def update_watch_list(self, symbols: Set[str]) -> None:
        """Update the watch list."""
        with self._lock:
            self._watch_list = symbols
            logger.info(f"Updated watch list: {len(symbols)} securities")

    def add_alert_handler(self, handler: Callable[[ComplianceViolation], None]) -> None:
        """Add an alert handler for violations."""
        self._alert_handlers.append(handler)

    def check_trade(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> ComplianceCheckResult:
        """
        Perform pre-trade compliance check.
        
        Args:
            trade: Trade request to check
            context: Additional context (positions, portfolio value, etc.)
            
        Returns:
            ComplianceCheckResult with status and any violations
        """
        passed_rules: List[str] = []
        failed_rules: List[str] = []
        warnings: List[str] = []
        violations: List[ComplianceViolation] = []

        # Enhance context with monitor data
        enhanced_context = {
            **context,
            'restricted_list': self._restricted_list,
            'watch_list': self._watch_list,
        }

        with self._lock:
            for rule_id, rule in self._rules.items():
                if not rule.enabled:
                    continue

                validator = self._validators.get(rule_id)
                if not validator:
                    continue

                try:
                    passed, violation = validator.validate(trade, enhanced_context)

                    if passed:
                        passed_rules.append(rule_id)
                    else:
                        if violation:
                            violations.append(violation)
                            self._violations.append(violation)
                            self._trigger_alerts(violation)

                        if 'block' in rule.actions:
                            failed_rules.append(rule_id)
                        else:
                            warnings.append(rule_id)

                except Exception as e:
                    logger.error(f"Error validating rule {rule_id}: {e}")
                    warnings.append(f"{rule_id} (error)")

        # Determine overall status
        if failed_rules:
            status = ComplianceStatus.REJECTED
            message = f"Trade rejected: {', '.join(failed_rules)}"
        elif warnings:
            status = ComplianceStatus.WARNING
            message = f"Trade approved with warnings: {', '.join(warnings)}"
        else:
            status = ComplianceStatus.APPROVED
            message = "Trade approved - all compliance checks passed"

        return ComplianceCheckResult(
            status=status,
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            warnings=warnings,
            violations=violations,
            message=message,
            metadata={
                'trade_symbol': trade.symbol,
                'trade_value': trade.notional_value,
                'checked_at': datetime.now(timezone.utc).isoformat(),
            }
        )

    def _trigger_alerts(self, violation: ComplianceViolation) -> None:
        """Trigger alert handlers for a violation."""
        for handler in self._alert_handlers:
            try:
                handler(violation)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")

    def get_violations(
        self,
        since: Optional[datetime] = None,
        category: Optional[RuleCategory] = None,
        unresolved_only: bool = False
    ) -> List[ComplianceViolation]:
        """Get violations with optional filtering."""
        with self._lock:
            violations = self._violations.copy()

        if since:
            violations = [v for v in violations if v.timestamp >= since]

        if category:
            violations = [v for v in violations if v.category == category]

        if unresolved_only:
            violations = [v for v in violations if not v.resolved]

        return violations

    def resolve_violation(
        self,
        violation_id: str,
        notes: str,
        resolved_by: str
    ) -> bool:
        """Mark a violation as resolved."""
        with self._lock:
            for violation in self._violations:
                if violation.violation_id == violation_id:
                    violation.resolved = True
                    violation.resolution_notes = notes
                    violation.resolved_at = datetime.now(timezone.utc)
                    violation.resolved_by = resolved_by
                    logger.info(f"Resolved violation {violation_id} by {resolved_by}")
                    return True
        return False

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get compliance monitoring summary."""
        with self._lock:
            total_violations = len(self._violations)
            unresolved = len([v for v in self._violations if not v.resolved])

            by_category = {}
            for cat in RuleCategory:
                cat_violations = [v for v in self._violations if v.category == cat]
                by_category[cat.value] = {
                    'total': len(cat_violations),
                    'unresolved': len([v for v in cat_violations if not v.resolved]),
                }

            by_severity = {}
            for sev in AlertSeverity:
                sev_violations = [v for v in self._violations if v.severity == sev]
                by_severity[sev.value] = len(sev_violations)

            return {
                'total_rules': len(self._rules),
                'enabled_rules': len([r for r in self._rules.values() if r.enabled]),
                'restricted_securities': len(self._restricted_list),
                'watch_list_securities': len(self._watch_list),
                'total_violations': total_violations,
                'unresolved_violations': unresolved,
                'violations_by_category': by_category,
                'violations_by_severity': by_severity,
            }

    def generate_audit_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate compliance audit report for a date range."""
        with self._lock:
            period_violations = [
                v for v in self._violations
                if start_date <= v.timestamp <= end_date
            ]

        return {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_violations': len(period_violations),
                'resolved': len([v for v in period_violations if v.resolved]),
                'unresolved': len([v for v in period_violations if not v.resolved]),
            },
            'violations': [v.to_dict() for v in period_violations],
            'rules_configuration': {
                rule_id: {
                    'name': rule.name,
                    'category': rule.category.value,
                    'enabled': rule.enabled,
                    'parameters': rule.parameters,
                }
                for rule_id, rule in self._rules.items()
            },
        }


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_compliance_monitor: Optional[ComplianceMonitor] = None


def get_compliance_monitor() -> ComplianceMonitor:
    """Get or create global compliance monitor."""
    global _compliance_monitor
    if _compliance_monitor is None:
        _compliance_monitor = ComplianceMonitor()
    return _compliance_monitor


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ComplianceStatus',
    'RuleCategory',
    'AlertSeverity',
    'TradeDirection',
    'ComplianceRule',
    'ComplianceViolation',
    'ComplianceCheckResult',
    'TradeRequest',
    'RuleValidator',
    'ComplianceMonitor',
    'get_compliance_monitor',
]
