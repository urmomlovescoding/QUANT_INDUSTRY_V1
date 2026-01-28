"""
QUANT_INDUSTRY_V1 Risk Module

Risk management, position sizing, and exposure controls:
- Pre-trade risk checks
- Position sizing strategies
- VaR/CVaR calculation
- Drawdown monitoring
- Limit management

Usage:
    from risk import RiskEngine, VolatilityScaledSizer

    engine = RiskEngine(portfolio_value=100000)
    size, assessment = engine.calculate_position_size(
        symbol='AAPL',
        signal_strength=0.8,
        volatility=0.02,
        side='buy'
    )
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

__all__ = [
    # Types
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
]
