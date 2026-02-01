"""
QUANT_INDUSTRY_V1 Risk Module Tests

Tests for risk management and position sizing.
"""

import pytest
import numpy as np


class TestPositionSizers:
    """Test position sizing strategies."""

    def test_fixed_fraction_sizer(self):
        """Test fixed fraction position sizer."""
        from risk import FixedFractionSizer

        # API: max_fraction parameter, scale_by_confidence
        sizer = FixedFractionSizer(max_fraction=0.02, scale_by_confidence=False)

        # API: calculate_size() returns position VALUE (not shares)
        position_value = sizer.calculate_size(
            signal_strength=1.0,
            volatility=0.02,
            portfolio_value=100000,
            current_position=0.0,
            risk_params={}
        )

        # 2% of $100k = $2000 position value
        assert position_value == 2000

    def test_volatility_scaled_sizer(self):
        """Test volatility-scaled position sizer."""
        from risk import VolatilityScaledSizer

        # API: target_risk parameter (not target_volatility)
        sizer = VolatilityScaledSizer(target_risk=0.02)

        # Low volatility asset should get larger position
        low_vol_size = sizer.calculate_size(
            signal_strength=1.0,
            volatility=0.10,
            portfolio_value=100000,
            current_position=0.0,
            risk_params={}
        )

        high_vol_size = sizer.calculate_size(
            signal_strength=1.0,
            volatility=0.30,
            portfolio_value=100000,
            current_position=0.0,
            risk_params={}
        )

        assert low_vol_size > high_vol_size

    def test_kelly_criterion_sizer(self):
        """Test Kelly criterion position sizer."""
        from risk import KellyCriterionSizer

        sizer = KellyCriterionSizer(fraction=0.5)  # Half Kelly

        # API: win_rate, avg_win, avg_loss go in risk_params
        position_value = sizer.calculate_size(
            signal_strength=1.0,
            volatility=0.02,
            portfolio_value=100000,
            current_position=0.0,
            risk_params={
                'win_rate': 0.55,
                'avg_win': 0.02,
                'avg_loss': 0.01
            }
        )

        assert position_value > 0
        assert position_value < 100000  # Less than full portfolio value


class TestRiskEngine:
    """Test risk engine."""

    def test_risk_check_position_limit(self):
        """Test position limit check."""
        from risk import RiskEngine, LimitType

        engine = RiskEngine(portfolio_value=100000)

        # Set position limit using set_limit() with "reduce" action
        # The engine's position size logic uses "reduce" to adjust size, not block
        engine.set_limit(LimitType.MAX_POSITION_SIZE, value=0.10, action="reduce")
        # Relax other default limits that would interfere with this test
        engine.set_limit(LimitType.MAX_SINGLE_TRADE, value=0.50, action="warn")

        # Within limit: $10,000 is 10% of $100,000
        result = engine.check_pre_trade('AAPL', 10000, 'buy')
        # Check that position size check passed
        pos_check = next(c for c in result.checks if c.limit_type == LimitType.MAX_POSITION_SIZE)
        assert pos_check.passed

        # Exceeds limit: $20,000 is 20% of $100,000
        result = engine.check_pre_trade('AAPL', 20000, 'buy')
        # Check that position size check failed
        pos_check = next(c for c in result.checks if c.limit_type == LimitType.MAX_POSITION_SIZE)
        assert not pos_check.passed
        # Verify the adjustment was applied (should reduce to fit limit)
        assert result.position_size_adjustment < 1.0

    def test_risk_check_drawdown(self):
        """Test drawdown check."""
        from risk import RiskEngine, LimitType

        engine = RiskEngine(portfolio_value=100000)

        # Set drawdown limit
        engine.set_limit(LimitType.MAX_DRAWDOWN, value=0.10, action="block")
        # Relax other default limits that would interfere with this test
        engine.set_limit(LimitType.MAX_SINGLE_TRADE, value=0.50, action="warn")
        engine.set_limit(LimitType.MAX_DAILY_LOSS, value=0.50, action="warn")

        # Update P&L to simulate drawdown
        engine.update_pnl(-5000)  # 5% loss

        result = engine.check_pre_trade('AAPL', 5000, 'buy')
        assert result.approved  # 5% < 10%

        engine.update_pnl(-12000)  # 12% loss
        result = engine.check_pre_trade('AAPL', 5000, 'buy')
        assert not result.approved  # 12% > 10%

    def test_var_calculation(self):
        """Test VaR calculation."""
        from risk import RiskEngine

        engine = RiskEngine(portfolio_value=100000)

        # Generate returns
        np.random.seed(42)
        returns = np.random.randn(252) * 0.02

        var_95 = engine.calculate_var(returns, confidence=0.95)
        var_99 = engine.calculate_var(returns, confidence=0.99)

        assert var_99 > var_95  # 99% VaR should be larger
        assert var_95 > 0

    def test_cvar_calculation(self):
        """Test CVaR (Expected Shortfall) calculation."""
        from risk import RiskEngine

        engine = RiskEngine(portfolio_value=100000)

        np.random.seed(42)
        returns = np.random.randn(252) * 0.02

        var_95 = engine.calculate_var(returns, confidence=0.95)
        cvar_95 = engine.calculate_cvar(returns, confidence=0.95)

        assert cvar_95 > var_95  # CVaR >= VaR

    def test_risk_summary(self):
        """Test risk summary reporting."""
        from risk import RiskEngine

        engine = RiskEngine(portfolio_value=100000)

        # Update some positions
        engine.update_position('AAPL', 50000)
        engine.update_position('MSFT', 30000)

        summary = engine.get_risk_summary()

        assert 'portfolio_value' in summary
        assert 'total_exposure' in summary
        assert summary['total_exposure'] == 80000
        assert summary['position_count'] == 2


class TestRiskAssessment:
    """Test risk assessment workflow."""

    def test_full_assessment(self):
        """Test full pre-trade risk assessment."""
        from risk import RiskEngine, LimitType

        engine = RiskEngine(portfolio_value=100000)

        # Configure limits using set_limit()
        engine.set_limit(LimitType.MAX_POSITION_SIZE, value=0.10, action="reduce")
        engine.set_limit(LimitType.MAX_DRAWDOWN, value=0.15, action="block")
        engine.set_limit(LimitType.MAX_DAILY_LOSS, value=0.03, action="block")

        # API: check_pre_trade() returns RiskAssessment
        assessment = engine.check_pre_trade(
            symbol='AAPL',
            proposed_value=7500,  # $7500 trade value
            side='buy'
        )

        # RiskAssessment has 'approved' not 'passed'
        assert hasattr(assessment, 'approved')
        assert hasattr(assessment, 'checks')
        assert hasattr(assessment, 'position_size_adjustment')

        # Also test to_dict() method
        assessment_dict = assessment.to_dict()
        assert 'approved' in assessment_dict
        assert 'checks' in assessment_dict
        assert 'position_size_adjustment' in assessment_dict

    def test_risk_limits(self):
        """Test risk limit management."""
        from risk import RiskEngine, LimitType

        engine = RiskEngine(portfolio_value=100000)

        # API: use set_limit() instead of add_limit()
        # Use MAX_POSITION_VALUE instead of POSITION
        engine.set_limit(
            LimitType.MAX_POSITION_VALUE,
            value=5000,
            action="block"
        )

        # Check via pre-trade assessment
        # Within limit
        result = engine.check_pre_trade('AAPL', 4000, 'buy')
        # Check the specific position value check
        pos_value_check = next(
            (c for c in result.checks if c.limit_type == LimitType.MAX_POSITION_VALUE),
            None
        )
        assert pos_value_check is not None
        assert pos_value_check.passed

        # Exceeds limit
        result = engine.check_pre_trade('AAPL', 6000, 'buy')
        pos_value_check = next(
            (c for c in result.checks if c.limit_type == LimitType.MAX_POSITION_VALUE),
            None
        )
        assert pos_value_check is not None
        assert not pos_value_check.passed

    def test_position_size_calculation(self):
        """Test integrated position sizing with risk checks."""
        from risk import RiskEngine, VolatilityScaledSizer

        sizer = VolatilityScaledSizer(target_risk=0.02)
        engine = RiskEngine(portfolio_value=100000, position_sizer=sizer)

        # Calculate position size with risk assessment
        size, assessment = engine.calculate_position_size(
            symbol='AAPL',
            signal_strength=0.8,
            volatility=0.02,
            side='buy',
            risk_params={}
        )

        assert size > 0
        assert hasattr(assessment, 'approved')
        assert hasattr(assessment, 'risk_score')
        assert hasattr(assessment, 'risk_level')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
