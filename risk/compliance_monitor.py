"""
Comprehensive Compliance Monitoring System
QUANT_INDUSTRY_V1 - P2 Task 17

Real-time compliance validation and alerting for trading operations.

Features:
- Real-time rule validation (position limits, trading restrictions, etc.)
- Pattern detection for potential violations (wash sales, layering, spoofing)
- Alert generation for compliance breaches with escalation
- Audit trail logging with immutable records
- Configurable rule engine with dynamic rule management
- Integration with risk management infrastructure
- Regulatory compliance (SEC, FINRA, MiFID II)

Rollback Plan: Delete this file
Tests Required: Rule validation, alert generation, pattern detection, audit trail
Failure Modes: Block trades, escalate alerts, halt trading

Author: QUANT INDUSTRY AI Team
Version: 2.0.0
"""

import logging
import threading
import asyncio
import json
import hashlib
import uuid
import re
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta
from typing import (
    Dict, List, Optional, Any, Callable, Set, Tuple,
    Union, TypeVar, Generic, Protocol
)
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from abc import ABC, abstractmethod
from functools import wraps
from pathlib import Path
import copy

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ComplianceStatus(Enum):
    """Compliance check status."""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    WARNING = "warning"
    ESCALATED = "escalated"


class RuleCategory(Enum):
    """Categories of compliance rules."""
    POSITION_LIMITS = "position_limits"
    TRADING_RESTRICTIONS = "trading_restrictions"
    REGULATORY = "regulatory"
    INTERNAL_POLICY = "internal_policy"
    MARKET_ABUSE = "market_abuse"
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"
    COUNTERPARTY = "counterparty"
    SETTLEMENT = "settlement"
    BEST_EXECUTION = "best_execution"


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


class PatternType(Enum):
    """Types of suspicious patterns to detect."""
    WASH_TRADE = "wash_trade"
    LAYERING = "layering"
    SPOOFING = "spoofing"
    FRONT_RUNNING = "front_running"
    MARKING_CLOSE = "marking_close"
    MOMENTUM_IGNITION = "momentum_ignition"
    QUOTE_STUFFING = "quote_stuffing"
    CIRCULAR_TRADING = "circular_trading"


class AuditEventType(Enum):
    """Types of audit events."""
    TRADE_SUBMITTED = "trade_submitted"
    TRADE_APPROVED = "trade_approved"
    TRADE_REJECTED = "trade_rejected"
    TRADE_EXECUTED = "trade_executed"
    RULE_TRIGGERED = "rule_triggered"
    VIOLATION_CREATED = "violation_created"
    VIOLATION_RESOLVED = "violation_resolved"
    ALERT_GENERATED = "alert_generated"
    RULE_MODIFIED = "rule_modified"
    RESTRICTED_LIST_UPDATED = "restricted_list_updated"
    SYSTEM_EVENT = "system_event"
    MANUAL_OVERRIDE = "manual_override"


class EscalationLevel(Enum):
    """Escalation levels for compliance issues."""
    LEVEL_1 = 1  # Trading desk
    LEVEL_2 = 2  # Compliance officer
    LEVEL_3 = 3  # Chief Compliance Officer
    LEVEL_4 = 4  # Executive / Regulatory


# Regulatory frameworks
REGULATORY_FRAMEWORKS = {
    'SEC': 'US Securities and Exchange Commission',
    'FINRA': 'Financial Industry Regulatory Authority',
    'MIFID_II': 'Markets in Financial Instruments Directive II',
    'EMIR': 'European Market Infrastructure Regulation',
    'DODD_FRANK': 'Dodd-Frank Wall Street Reform',
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ComplianceRule:
    """Definition of a compliance rule."""
    rule_id: str
    name: str
    category: RuleCategory
    description: str
    enabled: bool = True
    priority: int = 100  # Lower = higher priority
    parameters: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=lambda: ["warn"])  # warn, block, escalate, log
    regulatory_reference: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"

    def is_active(self) -> bool:
        """Check if rule is currently active."""
        now = datetime.now(timezone.utc)
        if not self.enabled:
            return False
        if self.effective_date and now < self.effective_date:
            return False
        if self.expiry_date and now > self.expiry_date:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'rule_id': self.rule_id,
            'name': self.name,
            'category': self.category.value,
            'description': self.description,
            'enabled': self.enabled,
            'priority': self.priority,
            'parameters': self.parameters,
            'actions': self.actions,
            'regulatory_reference': self.regulatory_reference,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'created_by': self.created_by,
        }


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
    pattern_type: Optional[PatternType] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    escalated_at: Optional[datetime] = None
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    false_positive: bool = False
    regulatory_report_required: bool = False
    regulatory_report_submitted: bool = False

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
            'pattern_type': self.pattern_type.value if self.pattern_type else None,
            'resolved': self.resolved,
            'resolution_notes': self.resolution_notes,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'escalation_level': self.escalation_level.value,
            'escalated_at': self.escalated_at.isoformat() if self.escalated_at else None,
            'acknowledged': self.acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'false_positive': self.false_positive,
            'regulatory_report_required': self.regulatory_report_required,
            'regulatory_report_submitted': self.regulatory_report_submitted,
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
    check_duration_ms: float = 0.0
    check_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'check_id': self.check_id,
            'status': self.status.value,
            'passed_rules': self.passed_rules,
            'failed_rules': self.failed_rules,
            'warnings': self.warnings,
            'violations': [v.to_dict() for v in self.violations],
            'message': self.message,
            'metadata': self.metadata,
            'check_duration_ms': self.check_duration_ms,
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
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    venue: Optional[str] = None
    strategy_id: Optional[str] = None
    parent_order_id: Optional[str] = None

    @property
    def notional_value(self) -> float:
        return self.quantity * self.price

    def to_dict(self) -> Dict[str, Any]:
        return {
            'request_id': self.request_id,
            'symbol': self.symbol,
            'direction': self.direction.value,
            'quantity': self.quantity,
            'price': self.price,
            'notional_value': self.notional_value,
            'account_id': self.account_id,
            'trader_id': self.trader_id,
            'order_type': self.order_type,
            'timestamp': self.timestamp.isoformat(),
            'venue': self.venue,
            'strategy_id': self.strategy_id,
            'parent_order_id': self.parent_order_id,
            'metadata': self.metadata,
        }


@dataclass
class AuditRecord:
    """Immutable audit trail record."""
    record_id: str
    event_type: AuditEventType
    timestamp: datetime
    actor: str  # User/system that triggered the event
    entity_type: str  # trade, rule, violation, etc.
    entity_id: str
    action: str
    details: Dict[str, Any]
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute cryptographic checksum for integrity verification."""
        data = json.dumps({
            'record_id': self.record_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'actor': self.actor,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'details': self.details,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify record has not been tampered with."""
        return self.checksum == self._compute_checksum()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'record_id': self.record_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'actor': self.actor,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'details': self.details,
            'previous_state': self.previous_state,
            'new_state': self.new_state,
            'ip_address': self.ip_address,
            'session_id': self.session_id,
            'checksum': self.checksum,
        }


@dataclass
class AlertNotification:
    """Alert notification for external systems."""
    alert_id: str
    violation: ComplianceViolation
    timestamp: datetime
    recipients: List[str]
    channels: List[str]  # email, sms, slack, pagerduty
    message: str
    acknowledged: bool = False
    delivered: bool = False
    delivery_attempts: int = 0
    last_delivery_attempt: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'violation_id': self.violation.violation_id,
            'severity': self.violation.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'recipients': self.recipients,
            'channels': self.channels,
            'message': self.message,
            'acknowledged': self.acknowledged,
            'delivered': self.delivered,
            'delivery_attempts': self.delivery_attempts,
        }


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
        trade: TradeRequest,
        pattern_type: Optional[PatternType] = None
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
            trade_details=trade.to_dict(),
            pattern_type=pattern_type,
            regulatory_report_required=severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
        )

    def _generate_violation_id(self, trade: TradeRequest) -> str:
        """Generate unique violation ID."""
        data = f"{self.rule.rule_id}:{trade.symbol}:{trade.request_id}:{datetime.now(timezone.utc).isoformat()}"
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
        max_position_shares = limits.get('max_position_shares', float('inf'))
        portfolio_value = context.get('portfolio_value', 1000000)

        current_position = positions.get(trade.symbol, 0)
        current_position_shares = context.get('position_shares', {}).get(trade.symbol, 0)

        # Calculate new position
        if trade.direction == TradeDirection.BUY:
            new_position = current_position + trade.notional_value
            new_shares = current_position_shares + trade.quantity
        else:
            new_position = current_position - trade.notional_value
            new_shares = current_position_shares - trade.quantity

        new_position_value = abs(new_position)

        # Check percentage limit
        position_pct = new_position_value / portfolio_value if portfolio_value > 0 else 1.0
        if position_pct > max_position_pct:
            return False, self._create_violation(
                AlertSeverity.CRITICAL,
                {
                    'reason': 'Position size exceeds maximum percentage limit',
                    'current_pct': round(position_pct * 100, 2),
                    'limit_pct': round(max_position_pct * 100, 2),
                    'position_value': round(new_position_value, 2),
                    'portfolio_value': round(portfolio_value, 2),
                },
                trade
            )

        # Check absolute value limit
        if new_position_value > max_position_value:
            return False, self._create_violation(
                AlertSeverity.CRITICAL,
                {
                    'reason': 'Position value exceeds maximum dollar limit',
                    'position_value': round(new_position_value, 2),
                    'limit_value': max_position_value,
                },
                trade
            )

        # Check share limit
        if abs(new_shares) > max_position_shares:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Position shares exceed maximum limit',
                    'position_shares': abs(new_shares),
                    'limit_shares': max_position_shares,
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
        grey_list: Set[str] = context.get('grey_list', set())

        symbol = trade.symbol.upper()

        if symbol in restricted_list:
            return False, self._create_violation(
                AlertSeverity.EMERGENCY,
                {
                    'reason': 'Security is on restricted list - trading prohibited',
                    'symbol': symbol,
                    'list_type': 'restricted',
                    'restriction_reason': context.get('restriction_reasons', {}).get(symbol, 'Not specified'),
                },
                trade
            )

        if symbol in grey_list:
            # Grey list requires pre-approval
            if not context.get('pre_approved', False):
                return False, self._create_violation(
                    AlertSeverity.CRITICAL,
                    {
                        'reason': 'Security is on grey list - requires pre-approval',
                        'symbol': symbol,
                        'list_type': 'grey',
                    },
                    trade
                )

        if symbol in watch_list:
            # Warning only - enhanced surveillance required
            logger.warning(f"Trade in watch list security: {symbol}")

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
        min_loss_threshold = self.rule.parameters.get('min_loss_threshold', 0)

        cutoff_date = trade.timestamp - timedelta(days=wash_sale_window)

        # Check for opposing trades within window
        recent_trades = [
            t for t in trade_history
            if t.get('symbol') == trade.symbol
            and datetime.fromisoformat(t.get('timestamp', '2000-01-01T00:00:00+00:00')) >= cutoff_date
        ]

        for recent_trade in recent_trades:
            try:
                recent_direction = TradeDirection(recent_trade.get('direction', 'buy'))
            except ValueError:
                continue

            if recent_direction != trade.direction:
                realized_loss = recent_trade.get('realized_loss', 0)
                if realized_loss < -min_loss_threshold:
                    return False, self._create_violation(
                        AlertSeverity.WARNING,
                        {
                            'reason': 'Potential wash sale violation detected',
                            'symbol': trade.symbol,
                            'prior_trade_date': recent_trade.get('timestamp'),
                            'prior_trade_id': recent_trade.get('trade_id'),
                            'prior_loss': realized_loss,
                            'window_days': wash_sale_window,
                            'days_since_prior': (trade.timestamp - datetime.fromisoformat(recent_trade.get('timestamp', '2000-01-01T00:00:00+00:00'))).days,
                        },
                        trade,
                        pattern_type=PatternType.WASH_TRADE
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
        max_industry_pct = self.rule.parameters.get('max_industry_pct', 0.15)

        sector = symbol_sectors.get(trade.symbol, {}).get('sector', 'Unknown')
        industry = symbol_sectors.get(trade.symbol, {}).get('industry', 'Unknown')

        current_sector_exposure = sector_exposures.get(sector, 0)
        trade_value = trade.notional_value if trade.direction == TradeDirection.BUY else -trade.notional_value
        new_exposure = current_sector_exposure + trade_value

        exposure_pct = abs(new_exposure) / portfolio_value if portfolio_value > 0 else 1.0

        if exposure_pct > max_sector_pct:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Sector concentration exceeds limit',
                    'sector': sector,
                    'current_exposure': round(current_sector_exposure, 2),
                    'new_exposure': round(new_exposure, 2),
                    'exposure_pct': round(exposure_pct * 100, 2),
                    'limit_pct': round(max_sector_pct * 100, 2),
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
        avg_daily_value = market_data.get('adv_value', 10000000)

        max_adv_pct = self.rule.parameters.get('max_adv_pct', 0.10)
        max_adv_value_pct = self.rule.parameters.get('max_adv_value_pct', 0.05)

        volume_pct = trade.quantity / avg_daily_volume if avg_daily_volume > 0 else 1.0
        value_pct = trade.notional_value / avg_daily_value if avg_daily_value > 0 else 1.0

        if volume_pct > max_adv_pct:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Trade volume exceeds ADV threshold - potential market impact',
                    'symbol': trade.symbol,
                    'trade_quantity': trade.quantity,
                    'avg_daily_volume': avg_daily_volume,
                    'adv_pct': round(volume_pct * 100, 2),
                    'limit_pct': round(max_adv_pct * 100, 2),
                },
                trade
            )

        if value_pct > max_adv_value_pct:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Trade value exceeds ADV value threshold',
                    'symbol': trade.symbol,
                    'trade_value': round(trade.notional_value, 2),
                    'avg_daily_value': round(avg_daily_value, 2),
                    'adv_value_pct': round(value_pct * 100, 2),
                    'limit_pct': round(max_adv_value_pct * 100, 2),
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
                    'reason': 'Daily loss limit exceeded - trading halted',
                    'daily_pnl': round(daily_pnl, 2),
                    'limit': round(-max_daily_loss, 2),
                    'limit_pct': round(max_daily_loss_pct * 100, 2),
                    'action': 'Trading suspended for remainder of day',
                },
                trade
            )

        # Warning at 75% of limit
        if daily_pnl < -max_daily_loss * 0.75:
            logger.warning(f"Approaching daily loss limit: {daily_pnl:.2f} / {-max_daily_loss:.2f}")

        return True, None


class MarketHoursValidator(RuleValidator):
    """Validates trading during market hours."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        allow_extended_hours = self.rule.parameters.get('allow_extended_hours', False)
        allow_pre_market = self.rule.parameters.get('allow_pre_market', False)
        allow_after_hours = self.rule.parameters.get('allow_after_hours', False)

        # Get trade time in ET (market time)
        trade_hour = trade.timestamp.hour
        trade_minute = trade.timestamp.minute
        trade_time = trade_hour * 60 + trade_minute

        # Market hours (EST/EDT) - simplified without timezone conversion
        pre_market_start = 4 * 60       # 4:00 AM
        market_open = 9 * 60 + 30       # 9:30 AM
        market_close = 16 * 60          # 4:00 PM
        after_hours_end = 20 * 60       # 8:00 PM

        in_regular_hours = market_open <= trade_time < market_close
        in_pre_market = pre_market_start <= trade_time < market_open
        in_after_hours = market_close <= trade_time < after_hours_end

        if in_regular_hours:
            return True, None

        if in_pre_market and (allow_extended_hours or allow_pre_market):
            return True, None

        if in_after_hours and (allow_extended_hours or allow_after_hours):
            return True, None

        return False, self._create_violation(
            AlertSeverity.WARNING,
            {
                'reason': 'Trade attempted outside allowed market hours',
                'trade_time': trade.timestamp.isoformat(),
                'allowed_hours': 'Regular market hours only' if not allow_extended_hours else 'Extended hours',
            },
            trade
        )


class ShortSellingValidator(RuleValidator):
    """Validates short selling restrictions."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        if trade.direction != TradeDirection.SELL:
            return True, None

        positions = context.get('position_shares', {})
        current_shares = positions.get(trade.symbol, 0)

        # Check if this would be a short sale
        if current_shares - trade.quantity < 0:
            short_restricted = context.get('short_restricted_list', set())
            locate_obtained = context.get('short_locates', {}).get(trade.symbol, False)

            if trade.symbol in short_restricted:
                return False, self._create_violation(
                    AlertSeverity.CRITICAL,
                    {
                        'reason': 'Security is on short sale restricted list (SSR/Reg SHO)',
                        'symbol': trade.symbol,
                        'regulatory_rule': 'Regulation SHO',
                    },
                    trade
                )

            if not locate_obtained:
                if not self.rule.parameters.get('allow_naked_short', False):
                    return False, self._create_violation(
                        AlertSeverity.CRITICAL,
                        {
                            'reason': 'Short sale requires locate - no locate obtained',
                            'symbol': trade.symbol,
                            'current_position': current_shares,
                            'proposed_sale': trade.quantity,
                            'resulting_short': current_shares - trade.quantity,
                        },
                        trade
                    )

        return True, None


class OrderSizeValidator(RuleValidator):
    """Validates individual order size limits."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        max_order_value = self.rule.parameters.get('max_order_value', 500000)
        max_order_shares = self.rule.parameters.get('max_order_shares', 100000)
        min_order_value = self.rule.parameters.get('min_order_value', 0)

        if trade.notional_value > max_order_value:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Order value exceeds maximum single order limit',
                    'order_value': round(trade.notional_value, 2),
                    'limit': max_order_value,
                    'suggestion': 'Consider splitting into multiple orders',
                },
                trade
            )

        if trade.quantity > max_order_shares:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Order quantity exceeds maximum shares per order',
                    'order_quantity': trade.quantity,
                    'limit': max_order_shares,
                },
                trade
            )

        if trade.notional_value < min_order_value and min_order_value > 0:
            return False, self._create_violation(
                AlertSeverity.INFO,
                {
                    'reason': 'Order value below minimum threshold',
                    'order_value': round(trade.notional_value, 2),
                    'minimum': min_order_value,
                },
                trade
            )

        return True, None


class DuplicateOrderValidator(RuleValidator):
    """Detects potential duplicate orders."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        recent_orders = context.get('recent_orders', [])
        duplicate_window_seconds = self.rule.parameters.get('window_seconds', 5)

        cutoff = trade.timestamp - timedelta(seconds=duplicate_window_seconds)

        for order in recent_orders:
            order_time = datetime.fromisoformat(order.get('timestamp', '2000-01-01T00:00:00+00:00'))
            if order_time >= cutoff:
                if (order.get('symbol') == trade.symbol and
                    order.get('direction') == trade.direction.value and
                    abs(order.get('quantity', 0) - trade.quantity) < 0.001 and
                    abs(order.get('price', 0) - trade.price) < 0.01):
                    return False, self._create_violation(
                        AlertSeverity.WARNING,
                        {
                            'reason': 'Potential duplicate order detected',
                            'symbol': trade.symbol,
                            'prior_order_id': order.get('order_id'),
                            'prior_order_time': order.get('timestamp'),
                            'time_diff_seconds': (trade.timestamp - order_time).total_seconds(),
                        },
                        trade
                    )

        return True, None


class CounterpartyLimitValidator(RuleValidator):
    """Validates counterparty exposure limits."""

    def validate(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        counterparty_exposures = context.get('counterparty_exposures', {})
        portfolio_value = context.get('portfolio_value', 1000000)

        counterparty = trade.venue or 'default'
        max_counterparty_pct = self.rule.parameters.get('max_counterparty_pct', 0.25)

        current_exposure = counterparty_exposures.get(counterparty, 0)
        new_exposure = current_exposure + trade.notional_value

        exposure_pct = new_exposure / portfolio_value if portfolio_value > 0 else 1.0

        if exposure_pct > max_counterparty_pct:
            return False, self._create_violation(
                AlertSeverity.WARNING,
                {
                    'reason': 'Counterparty exposure limit exceeded',
                    'counterparty': counterparty,
                    'current_exposure': round(current_exposure, 2),
                    'new_exposure': round(new_exposure, 2),
                    'exposure_pct': round(exposure_pct * 100, 2),
                    'limit_pct': round(max_counterparty_pct * 100, 2),
                },
                trade
            )

        return True, None


# =============================================================================
# PATTERN DETECTOR
# =============================================================================

class PatternDetector:
    """
    Detects suspicious trading patterns that may indicate market manipulation.
    """

    def __init__(self):
        self._trade_history: deque = deque(maxlen=10000)
        self._order_history: deque = deque(maxlen=10000)
        self._cancel_history: deque = deque(maxlen=10000)
        self._lock = threading.RLock()

    def record_trade(self, trade: Dict[str, Any]) -> None:
        """Record a trade for pattern analysis."""
        with self._lock:
            self._trade_history.append({
                **trade,
                'recorded_at': datetime.now(timezone.utc).isoformat()
            })

    def record_order(self, order: Dict[str, Any]) -> None:
        """Record an order for pattern analysis."""
        with self._lock:
            self._order_history.append({
                **order,
                'recorded_at': datetime.now(timezone.utc).isoformat()
            })

    def record_cancel(self, cancel: Dict[str, Any]) -> None:
        """Record an order cancellation."""
        with self._lock:
            self._cancel_history.append({
                **cancel,
                'recorded_at': datetime.now(timezone.utc).isoformat()
            })

    def detect_patterns(
        self,
        symbol: str,
        account_id: str,
        window_minutes: int = 60
    ) -> List[Tuple[PatternType, Dict[str, Any]]]:
        """
        Analyze trading activity for suspicious patterns.

        Returns list of (pattern_type, details) tuples.
        """
        detected = []
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        with self._lock:
            # Filter relevant history
            trades = [
                t for t in self._trade_history
                if t.get('symbol') == symbol and
                t.get('account_id') == account_id and
                datetime.fromisoformat(t.get('timestamp', '2000-01-01T00:00:00+00:00')) >= cutoff
            ]

            orders = [
                o for o in self._order_history
                if o.get('symbol') == symbol and
                o.get('account_id') == account_id and
                datetime.fromisoformat(o.get('timestamp', '2000-01-01T00:00:00+00:00')) >= cutoff
            ]

            cancels = [
                c for c in self._cancel_history
                if c.get('symbol') == symbol and
                c.get('account_id') == account_id and
                datetime.fromisoformat(c.get('timestamp', '2000-01-01T00:00:00+00:00')) >= cutoff
            ]

        # Detect wash trading
        wash_trade = self._detect_wash_trade(trades)
        if wash_trade:
            detected.append((PatternType.WASH_TRADE, wash_trade))

        # Detect layering
        layering = self._detect_layering(orders, cancels)
        if layering:
            detected.append((PatternType.LAYERING, layering))

        # Detect spoofing
        spoofing = self._detect_spoofing(orders, cancels, trades)
        if spoofing:
            detected.append((PatternType.SPOOFING, spoofing))

        # Detect quote stuffing
        quote_stuffing = self._detect_quote_stuffing(orders, cancels)
        if quote_stuffing:
            detected.append((PatternType.QUOTE_STUFFING, quote_stuffing))

        # Detect marking the close
        marking_close = self._detect_marking_close(trades)
        if marking_close:
            detected.append((PatternType.MARKING_CLOSE, marking_close))

        return detected

    def _detect_wash_trade(self, trades: List[Dict]) -> Optional[Dict[str, Any]]:
        """Detect wash trading pattern - buying and selling same security with no change in beneficial ownership."""
        if len(trades) < 2:
            return None

        buys = [t for t in trades if t.get('direction') == 'buy']
        sells = [t for t in trades if t.get('direction') == 'sell']

        if not buys or not sells:
            return None

        # Check for matching buy/sell pairs within short time window
        for buy in buys:
            buy_time = datetime.fromisoformat(buy.get('timestamp', '2000-01-01T00:00:00+00:00'))
            buy_qty = buy.get('quantity', 0)

            for sell in sells:
                sell_time = datetime.fromisoformat(sell.get('timestamp', '2000-01-01T00:00:00+00:00'))
                sell_qty = sell.get('quantity', 0)

                time_diff = abs((buy_time - sell_time).total_seconds())

                # Same quantity, close in time
                if abs(buy_qty - sell_qty) < 0.001 and time_diff < 300:  # 5 minutes
                    return {
                        'buy_trade_id': buy.get('trade_id'),
                        'sell_trade_id': sell.get('trade_id'),
                        'quantity': buy_qty,
                        'time_diff_seconds': time_diff,
                        'confidence': 'high' if time_diff < 60 else 'medium',
                    }

        return None

    def _detect_layering(self, orders: List[Dict], cancels: List[Dict]) -> Optional[Dict[str, Any]]:
        """Detect layering - placing multiple orders at different price levels with intent to cancel."""
        if len(orders) < 5:
            return None

        # Group orders by direction
        buy_orders = [o for o in orders if o.get('direction') == 'buy']
        sell_orders = [o for o in orders if o.get('direction') == 'sell']

        for direction_orders in [buy_orders, sell_orders]:
            if len(direction_orders) < 4:
                continue

            # Check for multiple price levels
            prices = [o.get('price', 0) for o in direction_orders]
            unique_prices = len(set(prices))

            if unique_prices >= 4:
                # Check cancel rate
                order_ids = {o.get('order_id') for o in direction_orders}
                cancelled_ids = {c.get('order_id') for c in cancels if c.get('order_id') in order_ids}
                cancel_rate = len(cancelled_ids) / len(order_ids) if order_ids else 0

                if cancel_rate > 0.8:  # 80%+ cancel rate
                    return {
                        'direction': direction_orders[0].get('direction'),
                        'order_count': len(direction_orders),
                        'price_levels': unique_prices,
                        'cancel_rate': round(cancel_rate * 100, 1),
                        'confidence': 'high' if cancel_rate > 0.9 else 'medium',
                    }

        return None

    def _detect_spoofing(
        self,
        orders: List[Dict],
        cancels: List[Dict],
        trades: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Detect spoofing - placing orders with intent to cancel before execution."""
        if len(orders) < 3 or len(cancels) < 2:
            return None

        # Look for large orders that are cancelled shortly after smaller orders execute
        large_orders = [o for o in orders if o.get('quantity', 0) > 1000]

        for large_order in large_orders:
            order_id = large_order.get('order_id')
            order_time = datetime.fromisoformat(large_order.get('timestamp', '2000-01-01T00:00:00+00:00'))

            # Was it cancelled?
            cancel = next((c for c in cancels if c.get('order_id') == order_id), None)
            if not cancel:
                continue

            cancel_time = datetime.fromisoformat(cancel.get('timestamp', '2000-01-01T00:00:00+00:00'))
            order_duration = (cancel_time - order_time).total_seconds()

            if order_duration < 60:  # Cancelled within 1 minute
                # Check if trades happened on opposite side during this window
                opposite_trades = [
                    t for t in trades
                    if t.get('direction') != large_order.get('direction') and
                    order_time <= datetime.fromisoformat(t.get('timestamp', '2000-01-01T00:00:00+00:00')) <= cancel_time
                ]

                if opposite_trades:
                    return {
                        'spoofed_order_id': order_id,
                        'spoofed_quantity': large_order.get('quantity'),
                        'order_duration_seconds': order_duration,
                        'opposite_trades': len(opposite_trades),
                        'confidence': 'high' if order_duration < 10 else 'medium',
                    }

        return None

    def _detect_quote_stuffing(self, orders: List[Dict], cancels: List[Dict]) -> Optional[Dict[str, Any]]:
        """Detect quote stuffing - excessive order submissions to slow down other traders."""
        if len(orders) < 20:
            return None

        # Calculate order rate per second
        if not orders:
            return None

        times = [datetime.fromisoformat(o.get('timestamp', '2000-01-01T00:00:00+00:00')) for o in orders]
        min_time = min(times)
        max_time = max(times)
        duration = (max_time - min_time).total_seconds()

        if duration < 1:
            duration = 1

        order_rate = len(orders) / duration

        if order_rate > 10:  # More than 10 orders per second
            cancel_rate = len(cancels) / len(orders) if orders else 0

            if cancel_rate > 0.7:
                return {
                    'order_count': len(orders),
                    'duration_seconds': round(duration, 2),
                    'orders_per_second': round(order_rate, 2),
                    'cancel_rate': round(cancel_rate * 100, 1),
                    'confidence': 'high' if order_rate > 50 else 'medium',
                }

        return None

    def _detect_marking_close(self, trades: List[Dict]) -> Optional[Dict[str, Any]]:
        """Detect marking the close - trading at end of day to affect closing price."""
        if len(trades) < 3:
            return None

        # Get trades in last 15 minutes of trading (assuming 4 PM close)
        close_window_start = 15 * 60 + 45  # 3:45 PM in minutes
        close_window_end = 16 * 60  # 4:00 PM

        close_trades = []
        for trade in trades:
            trade_time = datetime.fromisoformat(trade.get('timestamp', '2000-01-01T00:00:00+00:00'))
            trade_minutes = trade_time.hour * 60 + trade_time.minute

            if close_window_start <= trade_minutes < close_window_end:
                close_trades.append(trade)

        if len(close_trades) < 3:
            return None

        # Calculate volume concentration
        total_volume = sum(t.get('quantity', 0) for t in trades)
        close_volume = sum(t.get('quantity', 0) for t in close_trades)

        if total_volume > 0:
            concentration = close_volume / total_volume

            if concentration > 0.5:  # More than 50% of volume in last 15 minutes
                return {
                    'close_trades': len(close_trades),
                    'close_volume': close_volume,
                    'total_volume': total_volume,
                    'concentration_pct': round(concentration * 100, 1),
                    'confidence': 'high' if concentration > 0.7 else 'medium',
                }

        return None


# =============================================================================
# AUDIT TRAIL MANAGER
# =============================================================================

class AuditTrailManager:
    """
    Manages immutable audit trail for compliance records.

    Features:
    - Cryptographic integrity verification
    - Tamper-evident logging
    - Efficient querying
    - Archival support
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self._records: deque = deque(maxlen=100000)
        self._lock = threading.RLock()
        self._storage_path = storage_path
        self._chain_hash = ""  # Hash of previous record for chaining

    def record(
        self,
        event_type: AuditEventType,
        actor: str,
        entity_type: str,
        entity_id: str,
        action: str,
        details: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AuditRecord:
        """Create an immutable audit record."""
        with self._lock:
            record = AuditRecord(
                record_id=str(uuid.uuid4()),
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                actor=actor,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                details={
                    **details,
                    'previous_chain_hash': self._chain_hash
                },
                previous_state=previous_state,
                new_state=new_state,
                ip_address=ip_address,
                session_id=session_id
            )

            self._records.append(record)
            self._chain_hash = record.checksum

            # Persist if storage configured
            if self._storage_path:
                self._persist_record(record)

            logger.debug(f"Audit record created: {event_type.value} - {action}")
            return record

    def _persist_record(self, record: AuditRecord) -> None:
        """Persist record to storage."""
        try:
            date_str = record.timestamp.strftime('%Y-%m-%d')
            log_file = self._storage_path / f"audit_{date_str}.jsonl"

            self._storage_path.mkdir(parents=True, exist_ok=True)

            with open(log_file, 'a') as f:
                f.write(json.dumps(record.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to persist audit record: {e}")

    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        actor: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[AuditRecord]:
        """Query audit records with filters."""
        with self._lock:
            results = []

            for record in reversed(list(self._records)):
                if len(results) >= limit:
                    break

                if event_type and record.event_type != event_type:
                    continue
                if actor and record.actor != actor:
                    continue
                if entity_type and record.entity_type != entity_type:
                    continue
                if entity_id and record.entity_id != entity_id:
                    continue
                if start_time and record.timestamp < start_time:
                    continue
                if end_time and record.timestamp > end_time:
                    continue

                results.append(record)

            return results

    def verify_chain_integrity(self) -> Tuple[bool, List[str]]:
        """Verify integrity of entire audit chain."""
        errors = []

        with self._lock:
            records = list(self._records)

        prev_hash = ""
        for i, record in enumerate(records):
            # Verify individual record
            if not record.verify_integrity():
                errors.append(f"Record {record.record_id}: checksum mismatch")

            # Verify chain
            if i > 0:
                chain_hash = record.details.get('previous_chain_hash', '')
                if chain_hash != prev_hash:
                    errors.append(f"Record {record.record_id}: chain hash mismatch")

            prev_hash = record.checksum

        return len(errors) == 0, errors

    def export(
        self,
        start_time: datetime,
        end_time: datetime,
        format: str = 'json'
    ) -> str:
        """Export audit records for regulatory reporting."""
        records = self.query(start_time=start_time, end_time=end_time, limit=100000)

        if format == 'json':
            return json.dumps([r.to_dict() for r in records], indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit trail statistics."""
        with self._lock:
            records = list(self._records)

        if not records:
            return {'record_count': 0}

        event_counts = defaultdict(int)
        actor_counts = defaultdict(int)
        entity_counts = defaultdict(int)

        for record in records:
            event_counts[record.event_type.value] += 1
            actor_counts[record.actor] += 1
            entity_counts[record.entity_type] += 1

        return {
            'record_count': len(records),
            'oldest_record': records[0].timestamp.isoformat() if records else None,
            'newest_record': records[-1].timestamp.isoformat() if records else None,
            'events_by_type': dict(event_counts),
            'events_by_actor': dict(actor_counts),
            'events_by_entity': dict(entity_counts),
        }


# =============================================================================
# ALERT MANAGER
# =============================================================================

class AlertManager:
    """
    Manages compliance alerts and notifications.

    Features:
    - Multi-channel notification (email, SMS, Slack, PagerDuty)
    - Escalation management
    - Alert deduplication
    - Delivery tracking
    """

    def __init__(self):
        self._alerts: deque = deque(maxlen=10000)
        self._handlers: Dict[str, List[Callable[[AlertNotification], bool]]] = {
            'email': [],
            'sms': [],
            'slack': [],
            'pagerduty': [],
            'webhook': [],
        }
        self._escalation_config: Dict[EscalationLevel, Dict[str, Any]] = {
            EscalationLevel.LEVEL_1: {
                'channels': ['slack'],
                'recipients': ['trading-desk'],
                'auto_escalate_minutes': 15,
            },
            EscalationLevel.LEVEL_2: {
                'channels': ['slack', 'email'],
                'recipients': ['compliance-officer'],
                'auto_escalate_minutes': 30,
            },
            EscalationLevel.LEVEL_3: {
                'channels': ['slack', 'email', 'sms'],
                'recipients': ['cco'],
                'auto_escalate_minutes': 60,
            },
            EscalationLevel.LEVEL_4: {
                'channels': ['slack', 'email', 'sms', 'pagerduty'],
                'recipients': ['executive', 'legal'],
                'auto_escalate_minutes': None,  # No auto-escalation
            },
        }
        self._lock = threading.RLock()
        self._dedup_window = timedelta(minutes=5)
        self._recent_alerts: Dict[str, datetime] = {}

    def register_handler(
        self,
        channel: str,
        handler: Callable[[AlertNotification], bool]
    ) -> None:
        """Register a notification handler for a channel."""
        if channel in self._handlers:
            self._handlers[channel].append(handler)

    def configure_escalation(
        self,
        level: EscalationLevel,
        config: Dict[str, Any]
    ) -> None:
        """Configure escalation settings for a level."""
        self._escalation_config[level] = config

    def create_alert(
        self,
        violation: ComplianceViolation,
        force: bool = False
    ) -> Optional[AlertNotification]:
        """Create and dispatch an alert for a violation."""
        with self._lock:
            # Deduplication check
            dedup_key = f"{violation.rule_id}:{violation.trade_details.get('symbol', '')}:{violation.severity.value}"

            if not force:
                last_alert = self._recent_alerts.get(dedup_key)
                if last_alert and (datetime.now(timezone.utc) - last_alert) < self._dedup_window:
                    logger.debug(f"Skipping duplicate alert: {dedup_key}")
                    return None

            self._recent_alerts[dedup_key] = datetime.now(timezone.utc)

            # Get escalation config
            level_config = self._escalation_config.get(
                violation.escalation_level,
                self._escalation_config[EscalationLevel.LEVEL_1]
            )

            # Create alert
            alert = AlertNotification(
                alert_id=str(uuid.uuid4())[:12],
                violation=violation,
                timestamp=datetime.now(timezone.utc),
                recipients=level_config['recipients'],
                channels=level_config['channels'],
                message=self._format_alert_message(violation),
            )

            self._alerts.append(alert)

            # Dispatch to handlers
            self._dispatch_alert(alert)

            return alert

    def _format_alert_message(self, violation: ComplianceViolation) -> str:
        """Format alert message for notification."""
        severity_emoji = {
            AlertSeverity.INFO: 'INFO',
            AlertSeverity.WARNING: 'WARNING',
            AlertSeverity.CRITICAL: 'CRITICAL',
            AlertSeverity.EMERGENCY: 'EMERGENCY',
        }

        return (
            f"[{severity_emoji.get(violation.severity, 'ALERT')}] Compliance Violation\n"
            f"Rule: {violation.rule_name}\n"
            f"Category: {violation.category.value}\n"
            f"Details: {violation.details.get('reason', 'No details')}\n"
            f"Symbol: {violation.trade_details.get('symbol', 'N/A') if violation.trade_details else 'N/A'}\n"
            f"Violation ID: {violation.violation_id}\n"
            f"Time: {violation.timestamp.isoformat()}"
        )

    def _dispatch_alert(self, alert: AlertNotification) -> None:
        """Dispatch alert to configured channels."""
        for channel in alert.channels:
            handlers = self._handlers.get(channel, [])

            for handler in handlers:
                try:
                    alert.delivery_attempts += 1
                    alert.last_delivery_attempt = datetime.now(timezone.utc)

                    success = handler(alert)
                    if success:
                        alert.delivered = True
                        logger.info(f"Alert {alert.alert_id} delivered via {channel}")
                except Exception as e:
                    logger.error(f"Failed to deliver alert via {channel}: {e}")

    def escalate(self, alert_id: str) -> bool:
        """Escalate an alert to the next level."""
        with self._lock:
            alert = next((a for a in self._alerts if a.alert_id == alert_id), None)

            if not alert:
                return False

            violation = alert.violation
            current_level = violation.escalation_level

            # Get next level
            next_level_value = current_level.value + 1
            if next_level_value > EscalationLevel.LEVEL_4.value:
                logger.warning(f"Alert {alert_id} already at maximum escalation level")
                return False

            next_level = EscalationLevel(next_level_value)
            violation.escalation_level = next_level
            violation.escalated_at = datetime.now(timezone.utc)

            # Create new alert with updated recipients/channels
            self.create_alert(violation, force=True)

            logger.info(f"Alert {alert_id} escalated to level {next_level.value}")
            return True

    def acknowledge(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        with self._lock:
            alert = next((a for a in self._alerts if a.alert_id == alert_id), None)

            if not alert:
                return False

            alert.acknowledged = True
            alert.violation.acknowledged = True
            alert.violation.acknowledged_by = acknowledged_by
            alert.violation.acknowledged_at = datetime.now(timezone.utc)

            return True

    def get_active_alerts(self) -> List[AlertNotification]:
        """Get all unacknowledged alerts."""
        with self._lock:
            return [a for a in self._alerts if not a.acknowledged]

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        with self._lock:
            alerts = list(self._alerts)

        total = len(alerts)
        acknowledged = sum(1 for a in alerts if a.acknowledged)
        delivered = sum(1 for a in alerts if a.delivered)

        by_severity = defaultdict(int)
        by_channel = defaultdict(int)

        for alert in alerts:
            by_severity[alert.violation.severity.value] += 1
            for channel in alert.channels:
                by_channel[channel] += 1

        return {
            'total_alerts': total,
            'acknowledged': acknowledged,
            'pending': total - acknowledged,
            'delivery_rate': (delivered / total * 100) if total > 0 else 0,
            'by_severity': dict(by_severity),
            'by_channel': dict(by_channel),
        }


# =============================================================================
# COMPLIANCE MONITOR (MAIN CLASS)
# =============================================================================

class ComplianceMonitor:
    """
    Comprehensive real-time compliance monitoring system.

    Coordinates all compliance rules, pattern detection, alerting,
    and audit trail for trading operations.

    Usage:
        monitor = ComplianceMonitor()

        # Check trade
        result = monitor.check_trade(trade_request, context)

        if result.status == ComplianceStatus.APPROVED:
            # Execute trade
            pass
        else:
            # Handle rejection/warning
            pass
    """

    def __init__(
        self,
        audit_storage_path: Optional[Path] = None,
        enable_pattern_detection: bool = True
    ):
        self._rules: Dict[str, ComplianceRule] = {}
        self._validators: Dict[str, RuleValidator] = {}
        self._violations: List[ComplianceViolation] = []
        self._lock = threading.RLock()

        # Initialize sub-systems
        self.audit_manager = AuditTrailManager(storage_path=audit_storage_path)
        self.alert_manager = AlertManager()
        self.pattern_detector = PatternDetector() if enable_pattern_detection else None

        # Context data
        self._restricted_list: Set[str] = set()
        self._watch_list: Set[str] = set()
        self._grey_list: Set[str] = set()
        self._restriction_reasons: Dict[str, str] = {}

        # Statistics
        self._stats = {
            'trades_checked': 0,
            'trades_approved': 0,
            'trades_rejected': 0,
            'trades_warned': 0,
            'patterns_detected': 0,
        }

        # Initialize default rules
        self._setup_default_rules()

        logger.info("ComplianceMonitor initialized with %d rules", len(self._rules))

    def _setup_default_rules(self) -> None:
        """Setup default compliance rules."""
        default_rules = [
            # Position Limits
            (ComplianceRule(
                rule_id="POS_LIMIT_001",
                name="Position Size Limit",
                category=RuleCategory.POSITION_LIMITS,
                description="Maximum position size as percentage of portfolio",
                priority=10,
                parameters={
                    'max_position_pct': 0.10,
                    'max_position_value': 100000,
                    'max_position_shares': 10000
                },
                actions=['block', 'log'],
                regulatory_reference='Internal Policy'
            ), PositionLimitValidator),

            # Restricted Securities
            (ComplianceRule(
                rule_id="RESTRICT_001",
                name="Restricted Securities",
                category=RuleCategory.TRADING_RESTRICTIONS,
                description="Block trading in restricted securities",
                priority=1,
                parameters={},
                actions=['block', 'escalate', 'log'],
                regulatory_reference='SEC Rule 10b-5'
            ), RestrictedListValidator),

            # Wash Sale Prevention
            (ComplianceRule(
                rule_id="WASH_001",
                name="Wash Sale Prevention",
                category=RuleCategory.REGULATORY,
                description="Prevent wash sale violations",
                priority=20,
                parameters={'window_days': 30, 'min_loss_threshold': 100},
                actions=['warn', 'log'],
                regulatory_reference='IRS Wash Sale Rule'
            ), WashSaleValidator),

            # Sector Concentration
            (ComplianceRule(
                rule_id="CONC_001",
                name="Sector Concentration",
                category=RuleCategory.CONCENTRATION,
                description="Maximum sector exposure limit",
                priority=30,
                parameters={'max_sector_pct': 0.25, 'max_industry_pct': 0.15},
                actions=['warn', 'log']
            ), ConcentrationValidator),

            # Market Impact
            (ComplianceRule(
                rule_id="IMPACT_001",
                name="Market Impact",
                category=RuleCategory.LIQUIDITY,
                description="Maximum trade size relative to ADV",
                priority=25,
                parameters={'max_adv_pct': 0.10, 'max_adv_value_pct': 0.05},
                actions=['warn', 'log']
            ), MarketImpactValidator),

            # Daily Loss Limit
            (ComplianceRule(
                rule_id="LOSS_001",
                name="Daily Loss Limit",
                category=RuleCategory.INTERNAL_POLICY,
                description="Maximum daily loss limit",
                priority=5,
                parameters={'max_daily_loss_pct': 0.02},
                actions=['block', 'escalate', 'log']
            ), DailyLossLimitValidator),

            # Market Hours
            (ComplianceRule(
                rule_id="HOURS_001",
                name="Market Hours",
                category=RuleCategory.TRADING_RESTRICTIONS,
                description="Restrict trading to market hours",
                priority=50,
                parameters={
                    'allow_extended_hours': False,
                    'allow_pre_market': False,
                    'allow_after_hours': False
                },
                actions=['warn', 'log'],
                enabled=False
            ), MarketHoursValidator),

            # Short Selling
            (ComplianceRule(
                rule_id="SHORT_001",
                name="Short Selling Restrictions",
                category=RuleCategory.REGULATORY,
                description="Enforce short selling rules and locate requirements",
                priority=15,
                parameters={'allow_naked_short': False},
                actions=['block', 'log'],
                regulatory_reference='Regulation SHO'
            ), ShortSellingValidator),

            # Order Size
            (ComplianceRule(
                rule_id="ORDER_001",
                name="Order Size Limits",
                category=RuleCategory.INTERNAL_POLICY,
                description="Maximum single order size",
                priority=40,
                parameters={
                    'max_order_value': 500000,
                    'max_order_shares': 100000,
                    'min_order_value': 0
                },
                actions=['warn', 'log']
            ), OrderSizeValidator),

            # Duplicate Orders
            (ComplianceRule(
                rule_id="DUP_001",
                name="Duplicate Order Detection",
                category=RuleCategory.INTERNAL_POLICY,
                description="Detect potential duplicate orders",
                priority=45,
                parameters={'window_seconds': 5},
                actions=['warn', 'log']
            ), DuplicateOrderValidator),

            # Counterparty Limits
            (ComplianceRule(
                rule_id="CNTRPTY_001",
                name="Counterparty Exposure",
                category=RuleCategory.COUNTERPARTY,
                description="Maximum counterparty exposure limit",
                priority=35,
                parameters={'max_counterparty_pct': 0.25},
                actions=['warn', 'log']
            ), CounterpartyLimitValidator),
        ]

        for rule, validator_class in default_rules:
            self._rules[rule.rule_id] = rule
            self._validators[rule.rule_id] = validator_class(rule)

    # =========================================================================
    # RULE MANAGEMENT
    # =========================================================================

    def add_rule(self, rule: ComplianceRule, validator: RuleValidator) -> None:
        """Add a custom compliance rule."""
        with self._lock:
            old_rule = self._rules.get(rule.rule_id)
            self._rules[rule.rule_id] = rule
            self._validators[rule.rule_id] = validator

            # Audit
            self.audit_manager.record(
                event_type=AuditEventType.RULE_MODIFIED,
                actor='system',
                entity_type='rule',
                entity_id=rule.rule_id,
                action='add' if old_rule is None else 'update',
                details={'rule_name': rule.name},
                previous_state=old_rule.to_dict() if old_rule else None,
                new_state=rule.to_dict()
            )

            logger.info(f"Added compliance rule: {rule.rule_id} - {rule.name}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a compliance rule."""
        with self._lock:
            if rule_id not in self._rules:
                return False

            old_rule = self._rules.pop(rule_id)
            self._validators.pop(rule_id, None)

            # Audit
            self.audit_manager.record(
                event_type=AuditEventType.RULE_MODIFIED,
                actor='system',
                entity_type='rule',
                entity_id=rule_id,
                action='remove',
                details={'rule_name': old_rule.name},
                previous_state=old_rule.to_dict()
            )

            logger.info(f"Removed compliance rule: {rule_id}")
            return True

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a compliance rule."""
        with self._lock:
            if rule_id not in self._rules:
                return False

            self._rules[rule_id].enabled = True
            self._rules[rule_id].modified_at = datetime.now(timezone.utc)

            self.audit_manager.record(
                event_type=AuditEventType.RULE_MODIFIED,
                actor='system',
                entity_type='rule',
                entity_id=rule_id,
                action='enable',
                details={'rule_name': self._rules[rule_id].name}
            )

            logger.info(f"Enabled compliance rule: {rule_id}")
            return True

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a compliance rule."""
        with self._lock:
            if rule_id not in self._rules:
                return False

            self._rules[rule_id].enabled = False
            self._rules[rule_id].modified_at = datetime.now(timezone.utc)

            self.audit_manager.record(
                event_type=AuditEventType.RULE_MODIFIED,
                actor='system',
                entity_type='rule',
                entity_id=rule_id,
                action='disable',
                details={'rule_name': self._rules[rule_id].name}
            )

            logger.info(f"Disabled compliance rule: {rule_id}")
            return True

    def update_rule_parameters(self, rule_id: str, parameters: Dict[str, Any]) -> bool:
        """Update rule parameters."""
        with self._lock:
            if rule_id not in self._rules:
                return False

            old_params = self._rules[rule_id].parameters.copy()
            self._rules[rule_id].parameters.update(parameters)
            self._rules[rule_id].modified_at = datetime.now(timezone.utc)
            self._rules[rule_id].version += 1

            self.audit_manager.record(
                event_type=AuditEventType.RULE_MODIFIED,
                actor='system',
                entity_type='rule',
                entity_id=rule_id,
                action='update_parameters',
                details={
                    'rule_name': self._rules[rule_id].name,
                    'changed_params': list(parameters.keys())
                },
                previous_state={'parameters': old_params},
                new_state={'parameters': self._rules[rule_id].parameters}
            )

            logger.info(f"Updated rule parameters: {rule_id}")
            return True

    def get_rule(self, rule_id: str) -> Optional[ComplianceRule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def get_all_rules(self) -> List[ComplianceRule]:
        """Get all rules."""
        return list(self._rules.values())

    # =========================================================================
    # RESTRICTED LIST MANAGEMENT
    # =========================================================================

    def update_restricted_list(
        self,
        symbols: Set[str],
        reasons: Optional[Dict[str, str]] = None
    ) -> None:
        """Update the restricted securities list."""
        with self._lock:
            old_list = self._restricted_list.copy()
            self._restricted_list = {s.upper() for s in symbols}

            if reasons:
                self._restriction_reasons.update(reasons)

            # Audit
            added = self._restricted_list - old_list
            removed = old_list - self._restricted_list

            self.audit_manager.record(
                event_type=AuditEventType.RESTRICTED_LIST_UPDATED,
                actor='system',
                entity_type='restricted_list',
                entity_id='main',
                action='update',
                details={
                    'total_securities': len(self._restricted_list),
                    'added': list(added),
                    'removed': list(removed)
                }
            )

            logger.info(f"Updated restricted list: {len(self._restricted_list)} securities")

    def add_to_restricted_list(self, symbol: str, reason: Optional[str] = None) -> None:
        """Add a single symbol to restricted list."""
        with self._lock:
            symbol = symbol.upper()
            if symbol not in self._restricted_list:
                self._restricted_list.add(symbol)
                if reason:
                    self._restriction_reasons[symbol] = reason

                self.audit_manager.record(
                    event_type=AuditEventType.RESTRICTED_LIST_UPDATED,
                    actor='system',
                    entity_type='restricted_list',
                    entity_id=symbol,
                    action='add',
                    details={'reason': reason}
                )

    def remove_from_restricted_list(self, symbol: str) -> bool:
        """Remove a symbol from restricted list."""
        with self._lock:
            symbol = symbol.upper()
            if symbol in self._restricted_list:
                self._restricted_list.remove(symbol)
                self._restriction_reasons.pop(symbol, None)

                self.audit_manager.record(
                    event_type=AuditEventType.RESTRICTED_LIST_UPDATED,
                    actor='system',
                    entity_type='restricted_list',
                    entity_id=symbol,
                    action='remove',
                    details={}
                )
                return True
            return False

    def update_watch_list(self, symbols: Set[str]) -> None:
        """Update the watch list."""
        with self._lock:
            self._watch_list = {s.upper() for s in symbols}
            logger.info(f"Updated watch list: {len(self._watch_list)} securities")

    def update_grey_list(self, symbols: Set[str]) -> None:
        """Update the grey list (requires pre-approval)."""
        with self._lock:
            self._grey_list = {s.upper() for s in symbols}
            logger.info(f"Updated grey list: {len(self._grey_list)} securities")

    # =========================================================================
    # TRADE CHECKING
    # =========================================================================

    def check_trade(
        self,
        trade: TradeRequest,
        context: Dict[str, Any]
    ) -> ComplianceCheckResult:
        """
        Perform comprehensive pre-trade compliance check.

        Args:
            trade: Trade request to check
            context: Additional context (positions, portfolio value, etc.)

        Returns:
            ComplianceCheckResult with status and any violations
        """
        import time
        start_time = time.time()

        passed_rules: List[str] = []
        failed_rules: List[str] = []
        warnings: List[str] = []
        violations: List[ComplianceViolation] = []

        # Enhance context with monitor data
        enhanced_context = {
            **context,
            'restricted_list': self._restricted_list,
            'watch_list': self._watch_list,
            'grey_list': self._grey_list,
            'restriction_reasons': self._restriction_reasons,
        }

        # Audit trade submission
        self.audit_manager.record(
            event_type=AuditEventType.TRADE_SUBMITTED,
            actor=trade.trader_id,
            entity_type='trade',
            entity_id=trade.request_id,
            action='check_requested',
            details=trade.to_dict()
        )

        with self._lock:
            # Sort rules by priority
            sorted_rules = sorted(
                self._rules.items(),
                key=lambda x: x[1].priority
            )

            for rule_id, rule in sorted_rules:
                if not rule.is_active():
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

                            # Create alert for violations
                            self.alert_manager.create_alert(violation)

                            # Audit violation
                            self.audit_manager.record(
                                event_type=AuditEventType.VIOLATION_CREATED,
                                actor='system',
                                entity_type='violation',
                                entity_id=violation.violation_id,
                                action='created',
                                details=violation.to_dict()
                            )

                        if 'block' in rule.actions:
                            failed_rules.append(rule_id)
                        else:
                            warnings.append(rule_id)

                except Exception as e:
                    logger.error(f"Error validating rule {rule_id}: {e}")
                    warnings.append(f"{rule_id} (error)")

            # Pattern detection
            if self.pattern_detector:
                patterns = self.pattern_detector.detect_patterns(
                    trade.symbol,
                    trade.account_id,
                    window_minutes=60
                )

                for pattern_type, details in patterns:
                    self._stats['patterns_detected'] += 1

                    pattern_violation = ComplianceViolation(
                        violation_id=str(uuid.uuid4())[:16],
                        rule_id=f"PATTERN_{pattern_type.value.upper()}",
                        rule_name=f"Suspicious Pattern: {pattern_type.value}",
                        category=RuleCategory.MARKET_ABUSE,
                        severity=AlertSeverity.CRITICAL,
                        timestamp=datetime.now(timezone.utc),
                        details=details,
                        trade_details=trade.to_dict(),
                        pattern_type=pattern_type,
                        regulatory_report_required=True
                    )

                    violations.append(pattern_violation)
                    self._violations.append(pattern_violation)
                    self.alert_manager.create_alert(pattern_violation)
                    failed_rules.append(f"PATTERN_{pattern_type.value}")

        # Determine overall status
        if failed_rules:
            status = ComplianceStatus.REJECTED
            message = f"Trade rejected: {', '.join(failed_rules)}"
            self._stats['trades_rejected'] += 1

            # Audit rejection
            self.audit_manager.record(
                event_type=AuditEventType.TRADE_REJECTED,
                actor='system',
                entity_type='trade',
                entity_id=trade.request_id,
                action='rejected',
                details={
                    'failed_rules': failed_rules,
                    'violations': [v.violation_id for v in violations]
                }
            )
        elif warnings:
            status = ComplianceStatus.WARNING
            message = f"Trade approved with warnings: {', '.join(warnings)}"
            self._stats['trades_warned'] += 1

            # Audit approval with warnings
            self.audit_manager.record(
                event_type=AuditEventType.TRADE_APPROVED,
                actor='system',
                entity_type='trade',
                entity_id=trade.request_id,
                action='approved_with_warnings',
                details={'warnings': warnings}
            )
        else:
            status = ComplianceStatus.APPROVED
            message = "Trade approved - all compliance checks passed"
            self._stats['trades_approved'] += 1

            # Audit clean approval
            self.audit_manager.record(
                event_type=AuditEventType.TRADE_APPROVED,
                actor='system',
                entity_type='trade',
                entity_id=trade.request_id,
                action='approved',
                details={'passed_rules': len(passed_rules)}
            )

        self._stats['trades_checked'] += 1
        check_duration = (time.time() - start_time) * 1000

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
                'rules_evaluated': len(passed_rules) + len(failed_rules) + len(warnings),
            },
            check_duration_ms=check_duration
        )

    def record_executed_trade(self, trade: TradeRequest, execution_details: Dict[str, Any]) -> None:
        """Record an executed trade for pattern detection and audit."""
        if self.pattern_detector:
            self.pattern_detector.record_trade({
                **trade.to_dict(),
                **execution_details
            })

        self.audit_manager.record(
            event_type=AuditEventType.TRADE_EXECUTED,
            actor=trade.trader_id,
            entity_type='trade',
            entity_id=trade.request_id,
            action='executed',
            details={
                'trade': trade.to_dict(),
                'execution': execution_details
            }
        )

    # =========================================================================
    # VIOLATION MANAGEMENT
    # =========================================================================

    def get_violations(
        self,
        since: Optional[datetime] = None,
        category: Optional[RuleCategory] = None,
        severity: Optional[AlertSeverity] = None,
        unresolved_only: bool = False,
        limit: int = 1000
    ) -> List[ComplianceViolation]:
        """Get violations with optional filtering."""
        with self._lock:
            violations = self._violations.copy()

        if since:
            violations = [v for v in violations if v.timestamp >= since]

        if category:
            violations = [v for v in violations if v.category == category]

        if severity:
            violations = [v for v in violations if v.severity == severity]

        if unresolved_only:
            violations = [v for v in violations if not v.resolved]

        return violations[:limit]

    def resolve_violation(
        self,
        violation_id: str,
        notes: str,
        resolved_by: str,
        false_positive: bool = False
    ) -> bool:
        """Mark a violation as resolved."""
        with self._lock:
            for violation in self._violations:
                if violation.violation_id == violation_id:
                    old_state = violation.to_dict()

                    violation.resolved = True
                    violation.resolution_notes = notes
                    violation.resolved_at = datetime.now(timezone.utc)
                    violation.resolved_by = resolved_by
                    violation.false_positive = false_positive

                    # Audit
                    self.audit_manager.record(
                        event_type=AuditEventType.VIOLATION_RESOLVED,
                        actor=resolved_by,
                        entity_type='violation',
                        entity_id=violation_id,
                        action='resolved',
                        details={
                            'notes': notes,
                            'false_positive': false_positive
                        },
                        previous_state=old_state,
                        new_state=violation.to_dict()
                    )

                    logger.info(f"Resolved violation {violation_id} by {resolved_by}")
                    return True
        return False

    # =========================================================================
    # REPORTING & STATISTICS
    # =========================================================================

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get comprehensive compliance monitoring summary."""
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
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'rules': {
                    'total': len(self._rules),
                    'enabled': len([r for r in self._rules.values() if r.enabled]),
                    'disabled': len([r for r in self._rules.values() if not r.enabled]),
                },
                'restricted_securities': len(self._restricted_list),
                'watch_list_securities': len(self._watch_list),
                'grey_list_securities': len(self._grey_list),
                'violations': {
                    'total': total_violations,
                    'unresolved': unresolved,
                    'by_category': by_category,
                    'by_severity': by_severity,
                },
                'statistics': self._stats.copy(),
                'alerts': self.alert_manager.get_alert_statistics(),
                'audit': self.audit_manager.get_statistics(),
            }

    def generate_audit_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate comprehensive compliance audit report for a date range."""
        with self._lock:
            period_violations = [
                v for v in self._violations
                if start_date <= v.timestamp <= end_date
            ]

        audit_records = self.audit_manager.query(
            start_time=start_date,
            end_time=end_date
        )

        return {
            'report_id': str(uuid.uuid4())[:12],
            'report_type': 'compliance_audit',
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_violations': len(period_violations),
                'resolved': len([v for v in period_violations if v.resolved]),
                'unresolved': len([v for v in period_violations if not v.resolved]),
                'false_positives': len([v for v in period_violations if v.false_positive]),
                'regulatory_reports_required': len([v for v in period_violations if v.regulatory_report_required]),
                'regulatory_reports_submitted': len([v for v in period_violations if v.regulatory_report_submitted]),
            },
            'violations': [v.to_dict() for v in period_violations],
            'rules_configuration': {
                rule_id: rule.to_dict()
                for rule_id, rule in self._rules.items()
            },
            'audit_trail': [r.to_dict() for r in audit_records[-1000:]],  # Last 1000 records
            'integrity_check': self.audit_manager.verify_chain_integrity(),
        }

    def get_regulatory_report(
        self,
        framework: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate regulatory-specific compliance report."""
        if framework not in REGULATORY_FRAMEWORKS:
            raise ValueError(f"Unknown regulatory framework: {framework}")

        with self._lock:
            violations = [
                v for v in self._violations
                if start_date <= v.timestamp <= end_date
                and v.regulatory_report_required
            ]

        return {
            'regulatory_framework': framework,
            'framework_name': REGULATORY_FRAMEWORKS[framework],
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'reportable_violations': len(violations),
            'violations': [v.to_dict() for v in violations],
            'compliance_officer_attestation': None,  # To be filled
        }


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_compliance_monitor: Optional[ComplianceMonitor] = None
_monitor_lock = threading.Lock()


def get_compliance_monitor() -> ComplianceMonitor:
    """Get or create global compliance monitor."""
    global _compliance_monitor
    with _monitor_lock:
        if _compliance_monitor is None:
            _compliance_monitor = ComplianceMonitor()
        return _compliance_monitor


def reset_compliance_monitor() -> None:
    """Reset the global compliance monitor (for testing)."""
    global _compliance_monitor
    with _monitor_lock:
        _compliance_monitor = None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    'ComplianceStatus',
    'RuleCategory',
    'AlertSeverity',
    'TradeDirection',
    'PatternType',
    'AuditEventType',
    'EscalationLevel',

    # Data Classes
    'ComplianceRule',
    'ComplianceViolation',
    'ComplianceCheckResult',
    'TradeRequest',
    'AuditRecord',
    'AlertNotification',

    # Base Classes
    'RuleValidator',

    # Validators
    'PositionLimitValidator',
    'RestrictedListValidator',
    'WashSaleValidator',
    'ConcentrationValidator',
    'MarketImpactValidator',
    'DailyLossLimitValidator',
    'MarketHoursValidator',
    'ShortSellingValidator',
    'OrderSizeValidator',
    'DuplicateOrderValidator',
    'CounterpartyLimitValidator',

    # Managers
    'PatternDetector',
    'AuditTrailManager',
    'AlertManager',

    # Main Class
    'ComplianceMonitor',

    # Functions
    'get_compliance_monitor',
    'reset_compliance_monitor',
]
