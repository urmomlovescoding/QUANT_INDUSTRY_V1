"""
QUANT_INDUSTRY_V1 Risk Module

Comprehensive risk management, compliance monitoring, and position sizing:
- Pre-trade risk checks
- Position sizing strategies
- VaR/CVaR calculation
- Drawdown monitoring
- Limit management
- Compliance monitoring and validation
- Pattern detection for market abuse
- Audit trail logging
- Alert generation and escalation

Usage:
    from risk import RiskEngine, VolatilityScaledSizer

    engine = RiskEngine(portfolio_value=100000)
    size, assessment = engine.calculate_position_size(
        symbol='AAPL',
        signal_strength=0.8,
        volatility=0.02,
        side='buy'
    )

    # Compliance monitoring
    from risk import get_compliance_monitor, TradeRequest, TradeDirection

    monitor = get_compliance_monitor()
    trade = TradeRequest(
        symbol='AAPL',
        direction=TradeDirection.BUY,
        quantity=100,
        price=150.0,
        account_id='ACC001',
        trader_id='TRADER001'
    )
    result = monitor.check_trade(trade, context={'portfolio_value': 1000000})
"""

from .engine import (
    # Types
    RiskLevel,
    LimitType,
    RiskLimit,
    RiskCheck,
    RiskAssessment,
    # Position sizing
    PositionSizer,
    FixedFractionSizer,
    VolatilityScaledSizer,
    KellyCriterionSizer,
    # Engine
    RiskEngine,
)

from .compliance_monitor import (
    # Enums
    ComplianceStatus,
    RuleCategory,
    AlertSeverity,
    TradeDirection,
    PatternType,
    AuditEventType,
    EscalationLevel,
    # Data Classes
    ComplianceRule,
    ComplianceViolation,
    ComplianceCheckResult,
    TradeRequest,
    AuditRecord,
    AlertNotification,
    # Base Classes
    RuleValidator,
    # Validators
    PositionLimitValidator,
    RestrictedListValidator,
    WashSaleValidator,
    ConcentrationValidator,
    MarketImpactValidator,
    DailyLossLimitValidator,
    MarketHoursValidator,
    ShortSellingValidator,
    OrderSizeValidator,
    DuplicateOrderValidator,
    CounterpartyLimitValidator,
    # Managers
    PatternDetector,
    AuditTrailManager,
    AlertManager,
    # Main Class
    ComplianceMonitor,
    # Functions
    get_compliance_monitor,
    reset_compliance_monitor,
)

__all__ = [
    # Risk Engine Types
    'RiskLevel',
    'LimitType',
    'RiskLimit',
    'RiskCheck',
    'RiskAssessment',
    # Position sizing
    'PositionSizer',
    'FixedFractionSizer',
    'VolatilityScaledSizer',
    'KellyCriterionSizer',
    # Engine
    'RiskEngine',
    # Compliance Enums
    'ComplianceStatus',
    'RuleCategory',
    'AlertSeverity',
    'TradeDirection',
    'PatternType',
    'AuditEventType',
    'EscalationLevel',
    # Compliance Data Classes
    'ComplianceRule',
    'ComplianceViolation',
    'ComplianceCheckResult',
    'TradeRequest',
    'AuditRecord',
    'AlertNotification',
    # Compliance Base Classes
    'RuleValidator',
    # Compliance Validators
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
    # Compliance Managers
    'PatternDetector',
    'AuditTrailManager',
    'AlertManager',
    # Compliance Main Class
    'ComplianceMonitor',
    # Compliance Functions
    'get_compliance_monitor',
    'reset_compliance_monitor',
]
