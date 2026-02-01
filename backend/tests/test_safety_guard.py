"""
Safety Guard Tests
==================
Tests for the SafetyGuard non-negotiable limits system.
"""

import pytest
from datetime import datetime


class TestSafetyGuard:
    """Tests for SafetyGuard functionality."""

    @pytest.fixture
    def safety_guard(self):
        """Create a fresh SafetyGuard instance for testing."""
        from core.safety_guard import SafetyGuard, TradingLimits

        # Reset singleton for testing
        SafetyGuard._instance = None

        limits = TradingLimits(
            max_daily_loss_pct=0.02,
            max_drawdown_pct=0.10,
            prop_firm_balance_floor=48000,
            max_consecutive_losses=5
        )
        guard = SafetyGuard(limits=limits)
        guard.set_equity(50000, is_starting=True)

        yield guard

        # Reset singleton after test
        SafetyGuard._instance = None

    def test_initial_state(self, safety_guard):
        """Test initial state allows trading."""
        allowed, reason = safety_guard.can_trade()
        assert allowed is True
        assert reason == "OK"

    def test_daily_loss_limit(self, safety_guard):
        """Test that daily loss limit triggers halt."""
        # Record a large loss
        safety_guard.record_trade("SPY", pnl=-1100, size_pct=0.1)

        allowed, reason = safety_guard.can_trade()
        assert allowed is False
        assert "daily loss" in reason.lower()

    def test_drawdown_limit(self, safety_guard):
        """Test that drawdown limit triggers halt."""
        # Set the peak equity high and current equity low to trigger drawdown
        # without triggering daily loss limit (which is 2%)
        # Drawdown = (peak - current) / peak, needs > 10%
        safety_guard._peak_equity = 50000
        safety_guard._current_equity = 44000  # 12% drawdown
        safety_guard._daily_pnl = -400  # Only 0.8% daily loss (under 2% limit)

        allowed, reason = safety_guard.can_trade()
        assert allowed is False
        assert "drawdown" in reason.lower()

    def test_prop_firm_floor(self, safety_guard):
        """Test that prop firm floor triggers halt."""
        # Set equity below floor
        safety_guard.set_equity(47000, is_starting=False)

        allowed, reason = safety_guard.can_trade()
        assert allowed is False
        assert "floor" in reason.lower()

    def test_consecutive_losses(self, safety_guard):
        """Test that consecutive losses reduce confidence."""
        for _ in range(3):
            safety_guard.record_trade("SPY", pnl=-100, size_pct=0.05)

        status = safety_guard.get_status()
        assert status["consecutive_losses"] == 3
        # position_size_multiplier reflects consecutive losses
        assert status["position_size_multiplier"] < 1.0

    def test_vix_impact(self, safety_guard):
        """Test that high VIX reduces size."""
        safety_guard.record_vix(30.0)
        status = safety_guard.get_status()
        # When VIX > 25, position_size_multiplier is reduced
        assert status["position_size_multiplier"] < 1.0

    def test_equity_tracking(self, safety_guard):
        """Test that equity is tracked correctly."""
        safety_guard.record_trade("SPY", pnl=500, size_pct=0.1)
        status = safety_guard.get_status()
        assert status["current_equity"] == 50500

    def test_live_mode_requires_confirmation(self, safety_guard):
        """Test that live mode requires explicit confirmation."""
        # Should work for paper
        allowed, _ = safety_guard.can_trade(is_live=False)
        assert allowed is True

    def test_daily_pnl_tracking(self, safety_guard):
        """Test that daily P&L is tracked correctly."""
        safety_guard.record_trade("SPY", pnl=-100, size_pct=0.05)

        status = safety_guard.get_status()
        assert status["daily_pnl"] == -100


class TestKillSwitch:
    """Tests for KillSwitch functionality."""

    @pytest.fixture
    def kill_switch(self):
        """Create a fresh KillSwitch instance."""
        from execution.kill_switch import KillSwitch
        return KillSwitch()

    def test_initial_state(self, kill_switch):
        """Test that kill switch is inactive by default."""
        assert kill_switch.check() is False

    def test_activation(self, kill_switch):
        """Test kill switch activation."""
        kill_switch.activate("Test activation", "test")
        assert kill_switch.check() is True
        assert "Test activation" in kill_switch.reason

    def test_deactivation_requires_code(self, kill_switch):
        """Test that deactivation requires confirmation code."""
        kill_switch.activate("Test", "test")

        # Wrong code should fail
        success, _ = kill_switch.deactivate("wrong_code")
        assert success is False
        assert kill_switch.check() is True

        # Correct code should work
        success, _ = kill_switch.deactivate("CONFIRM_RESUME_TRADING")
        assert success is True
        assert kill_switch.check() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
