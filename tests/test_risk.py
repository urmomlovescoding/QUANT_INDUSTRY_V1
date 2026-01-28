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

        sizer = FixedFractionSizer(fraction=0.02)

        size = sizer.calculate(
            portfolio_value=100000,
            signal_strength=1.0,
            price=50.0
        )

        # 2% of $100k = $2000, at $50 = 40 shares
        assert size == 40

    def test_volatility_scaled_sizer(self):
        """Test volatility-scaled position sizer."""
        from risk import VolatilityScaledSizer

        sizer = VolatilityScaledSizer(target_volatility=0.15)

        # Low volatility asset should get larger position
        low_vol_size = sizer.calculate(
            portfolio_value=100000,
            volatility=0.10,
            price=50.0
        )

        high_vol_size = sizer.calculate(
            portfolio_value=100000,
            volatility=0.30,
            price=50.0
        )

        assert low_vol_size > high_vol_size

    def test_kelly_criterion_sizer(self):
        """Test Kelly criterion position sizer."""
        from risk import KellyCriterionSizer

        sizer = KellyCriterionSizer(fraction=0.5)  # Half Kelly

        size = sizer.calculate(
            portfolio_value=100000,
            win_rate=0.55,
            avg_win=0.02,
            avg_loss=0.01,
            price=50.0
        )

        assert size > 0
        assert size < 100000 / 50  # Less than full portfolio


class TestRiskEngine:
    """Test risk engine."""

    def test_risk_check_position_limit(self):
        """Test position limit check."""
        from risk import RiskEngine, RiskLevel

        engine = RiskEngine(
            portfolio_value=100000,
            max_position_pct=0.10
        )

        # Within limit
        result = engine.check_position_limit('AAPL', 100, 100.0)
        assert result.passed

        # Exceeds limit
        result = engine.check_position_limit('AAPL', 200, 100.0)
        assert not result.passed

    def test_risk_check_drawdown(self):
        """Test drawdown check."""
        from risk import RiskEngine

        engine = RiskEngine(
            portfolio_value=100000,
            max_drawdown=0.10
        )

        # Record some equity values
        engine.record_equity(100000)
        engine.record_equity(95000)

        result = engine.check_drawdown()
        assert result.passed  # 5% < 10%

        engine.record_equity(88000)
        result = engine.check_drawdown()
        assert not result.passed  # 12% > 10%

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

    def test_correlation_risk(self):
        """Test correlation-based risk assessment."""
        from risk import RiskEngine

        engine = RiskEngine(portfolio_value=100000)

        # Highly correlated positions
        positions = {
            'AAPL': 50000,
            'MSFT': 30000,
            'GOOGL': 20000,
        }

        # Mock correlation matrix
        correlations = np.array([
            [1.0, 0.8, 0.7],
            [0.8, 1.0, 0.6],
            [0.7, 0.6, 1.0],
        ])

        concentration_risk = engine.calculate_concentration_risk(
            positions,
            correlations
        )

        assert concentration_risk > 0


class TestRiskAssessment:
    """Test risk assessment workflow."""

    def test_full_assessment(self):
        """Test full pre-trade risk assessment."""
        from risk import RiskEngine

        engine = RiskEngine(
            portfolio_value=100000,
            max_position_pct=0.10,
            max_drawdown=0.15,
            max_daily_loss=0.03
        )

        assessment = engine.assess_trade(
            symbol='AAPL',
            quantity=50,
            price=150.0,
            side='buy'
        )

        assert 'passed' in assessment
        assert 'checks' in assessment
        assert 'recommended_size' in assessment

    def test_risk_limits(self):
        """Test risk limit management."""
        from risk import RiskEngine, LimitType

        engine = RiskEngine(portfolio_value=100000)

        # Add custom limit
        engine.add_limit(
            LimitType.POSITION,
            value=5000,
            symbol='AAPL'
        )

        # Check limit
        result = engine.check_limit(LimitType.POSITION, 4000, 'AAPL')
        assert result.passed

        result = engine.check_limit(LimitType.POSITION, 6000, 'AAPL')
        assert not result.passed


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
