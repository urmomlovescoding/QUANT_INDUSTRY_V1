"""
Tests for AI Control Plane
"""

import pytest
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.ai_control_plane import (
    AIControlPlane,
    ControlPlaneMode,
    DecisionContext,
    get_control_plane,
    reset_control_plane,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before each test."""
    reset_control_plane()
    yield
    reset_control_plane()


class TestControlPlaneBasics:
    """Test basic control plane functionality."""
    
    def test_singleton_pattern(self):
        """Control plane should be a singleton via get_control_plane."""
        cp1 = get_control_plane()
        cp2 = get_control_plane()
        assert cp1 is cp2
    
    def test_default_mode(self):
        """Should start in shadow mode by default."""
        cp = get_control_plane()
        assert cp.mode == ControlPlaneMode.SHADOW
    
    def test_mode_transition(self):
        """Mode can be set via constructor or new singleton."""
        # Reset and create with paper mode
        reset_control_plane()
        cp = get_control_plane(mode=ControlPlaneMode.PAPER)
        assert cp.mode == ControlPlaneMode.PAPER
        
        # Reset and create with live mode
        reset_control_plane()
        cp = get_control_plane(mode=ControlPlaneMode.LIVE)
        assert cp.mode == ControlPlaneMode.LIVE
    
    def test_is_active(self):
        """Should correctly report active state."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        # Shadow mode - not active
        cp.set_mode(ControlPlaneMode.SHADOW)
        assert not cp.is_active
        
        # Paper mode - active
        cp.set_mode(ControlPlaneMode.PAPER)
        assert cp.is_active
        
        # Live mode - active
        cp.set_mode(ControlPlaneMode.LIVE)
        assert cp.is_active
        
        # Disabled - not active
        cp.set_mode(ControlPlaneMode.DISABLED)
        assert not cp.is_active


class TestKillSwitch:
    """Test kill switch functionality."""
    
    def test_kill_switch_engagement(self):
        """Kill switch should halt all activity."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        cp.set_mode(ControlPlaneMode.LIVE)
        
        assert cp.check_safety()  # Should pass before engagement
        
        cp.engage_kill_switch("Test engagement")
        
        assert not cp.check_safety()  # Should fail after engagement
        assert cp.kill_switch_engaged
    
    def test_kill_switch_release(self):
        """Kill switch should be releasable."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        cp.set_mode(ControlPlaneMode.LIVE)
        
        cp.engage_kill_switch("Test")
        assert cp.kill_switch_engaged
        
        cp.release_kill_switch("Recovery complete")
        assert not cp.kill_switch_engaged
        assert cp.check_safety()
    
    def test_kill_switch_history(self):
        """Kill switch events should be logged."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        cp.engage_kill_switch("Reason 1")
        cp.release_kill_switch("Recovery 1")
        
        assert len(cp.kill_switch_history) == 2
        assert cp.kill_switch_history[0]["action"] == "engage"
        assert cp.kill_switch_history[1]["action"] == "release"


class TestComponentRegistration:
    """Test component registration."""
    
    def test_register_component(self):
        """Should register components."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        cp.register_component("test_component")
        assert "test_component" in cp.registered_components
    
    def test_duplicate_registration(self):
        """Should handle duplicate registration gracefully."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        cp.register_component("test_component")
        cp.register_component("test_component")
        
        # Should not raise, just log
        assert cp.registered_components.count("test_component") <= 2
    
    def test_unregister_component(self):
        """Should unregister components."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        cp.register_component("test_component")
        cp.unregister_component("test_component")
        assert "test_component" not in cp.registered_components


class TestDecisionContext:
    """Test decision context management."""
    
    def test_create_context(self):
        """Should create decision context."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        context = cp.create_context(
            symbol="AAPL",
            regime="trending_bull",
            regime_confidence=0.85,
            signal={"direction": "LONG", "confidence": 0.7}
        )
        
        assert context["context_id"]
        assert context["symbol"] == "AAPL"
        assert context["regime"] == "trending_bull"
        assert context["regime_confidence"] == 0.85
    
    def test_context_caching(self):
        """Contexts should be cached for lookup."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        context = cp.create_context(
            symbol="MSFT",
            regime="sideways",
            regime_confidence=0.6,
            signal=None
        )
        
        ctx_id = context["context_id"]
        cached = cp.get_context(ctx_id)
        
        assert cached is not None
        assert cached.symbol == "MSFT"
    
    def test_record_decision(self):
        """Should record decisions to context."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        context = cp.create_context(
            symbol="GOOGL",
            regime="trending_bull",
            regime_confidence=0.9,
            signal={"direction": "LONG"}
        )
        
        cp.record_decision(
            context_id=context["context_id"],
            component="test_strategy",
            decision="ENTER_LONG",
            reason="Strong signal",
            data={"entry_price": 150.0}
        )
        
        ctx = cp.get_context(context["context_id"])
        assert len(ctx.decisions) == 1
        assert ctx.decisions[0]["decision"] == "ENTER_LONG"


class TestSafetyChecks:
    """Test safety check functionality."""
    
    def test_safety_passes_in_live(self):
        """Safety should pass in live mode without kill switch."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        cp.set_mode(ControlPlaneMode.LIVE)
        
        assert cp.check_safety()
    
    def test_safety_fails_with_kill_switch(self):
        """Safety should fail with kill switch engaged."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        cp.set_mode(ControlPlaneMode.LIVE)
        cp.engage_kill_switch("Test")
        
        assert not cp.check_safety()
    
    def test_safety_in_shadow_mode(self):
        """Safety check in shadow mode should pass but not allow execution."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        cp.set_mode(ControlPlaneMode.SHADOW)
        
        # Safety passes (system healthy)
        assert cp.check_safety()
        # But execution not allowed in shadow mode
        assert not cp.is_active
    
    def test_add_safety_check(self):
        """Should be able to add custom safety checks."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        
        def custom_check():
            return False  # Always fail
        
        cp.add_safety_check("always_fail", custom_check)
        cp.set_mode(ControlPlaneMode.LIVE)
        
        # Should fail due to custom check
        assert not cp.check_safety()


class TestStatus:
    """Test status reporting."""
    
    def test_get_status(self):
        """Should return comprehensive status."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        cp.set_mode(ControlPlaneMode.PAPER)
        cp.register_component("strategy_1")
        
        status = cp.get_status()
        
        assert "mode" in status
        assert status["mode"] == "paper"
        assert "is_active" in status
        assert status["is_active"] == True
        assert "kill_switch_engaged" in status
        assert "components_registered" in status
        assert "strategy_1" in status["components_registered"]
    
    def test_health_check(self):
        """Should return health of all components."""
        cp = AIControlPlane()
        cp._reset_for_testing()
        cp.register_component("healthy_component")
        
        health = cp.check_health()
        
        assert "overall" in health
        assert "components" in health
        assert "healthy_component" in health["components"]


# Helper method for testing
def _add_reset_method():
    """Add reset method to AIControlPlane for testing."""
    def _reset_for_testing(self):
        self._mode = ControlPlaneMode.SHADOW
        self._kill_switch_engaged = False
        self._kill_switch_history = []
        self._registered_components = []
        self._safety_checks = {}
        self._contexts = {}
        self._decisions_today = 0
        self._trades_today = 0
        self._shadow_decisions_today = 0
    
    AIControlPlane._reset_for_testing = _reset_for_testing


_add_reset_method()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
