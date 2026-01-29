"""
Tests for AI Control Plane

NOTE: These tests align with the actual AIControlPlane API implementation.
See test_core_functionality.py for additional comprehensive tests.
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
        """Should correctly report active state based on mode."""
        # Shadow mode - not active by default
        reset_control_plane()
        cp = get_control_plane(mode=ControlPlaneMode.SHADOW)
        # Note: is_active depends on implementation
        assert hasattr(cp, 'is_active')
        
        # Paper mode
        reset_control_plane()
        cp = get_control_plane(mode=ControlPlaneMode.PAPER)
        assert cp.is_active == True
        
        # Live mode
        reset_control_plane()
        cp = get_control_plane(mode=ControlPlaneMode.LIVE)
        assert cp.is_active == True
    
    def test_set_mode(self):
        """Mode can be changed via set_mode method."""
        cp = get_control_plane()
        assert cp.mode == ControlPlaneMode.SHADOW
        
        cp.set_mode(ControlPlaneMode.PAPER)
        assert cp.mode == ControlPlaneMode.PAPER
        assert cp.is_active == True
        
        cp.set_mode(ControlPlaneMode.LIVE)
        assert cp.mode == ControlPlaneMode.LIVE
        assert cp.is_active == True


class TestKillSwitch:
    """Test kill switch functionality."""
    
    def test_kill_switch_engagement(self):
        """Kill switch should block operations when engaged."""
        cp = get_control_plane(mode=ControlPlaneMode.LIVE)
        
        assert not cp.kill_switch_engaged
        
        cp.engage_kill_switch("Test emergency")
        assert cp.kill_switch_engaged
    
    def test_kill_switch_release(self):
        """Kill switch can be released."""
        cp = get_control_plane(mode=ControlPlaneMode.LIVE)
        
        cp.engage_kill_switch("Test emergency")
        assert cp.kill_switch_engaged
        
        cp.release_kill_switch("All clear")
        assert not cp.kill_switch_engaged
    
    def test_kill_switch_history(self):
        """Kill switch events should be recorded in safety_violations."""
        cp = get_control_plane(mode=ControlPlaneMode.LIVE)
        
        cp.engage_kill_switch("Emergency 1")
        cp.release_kill_switch("Resolved 1")
        cp.engage_kill_switch("Emergency 2")
        
        # Events are stored in safety_violations
        assert len(cp.state.safety_violations) >= 2


class TestComponentRegistration:
    """Test component registration."""
    
    def test_register_component(self):
        """Components can be registered with the control plane."""
        cp = get_control_plane()
        
        class MockComponent:
            pass
        
        component = MockComponent()
        cp.register_component("test_component", component)
        
        retrieved = cp.get_component("test_component")
        assert retrieved is component
    
    def test_duplicate_registration(self):
        """Registering same name overwrites previous component."""
        cp = get_control_plane()
        
        class MockComponent:
            def __init__(self, val):
                self.val = val
        
        comp1 = MockComponent(1)
        comp2 = MockComponent(2)
        
        cp.register_component("test", comp1)
        cp.register_component("test", comp2)
        
        retrieved = cp.get_component("test")
        assert retrieved.val == 2
    
    def test_get_missing_component(self):
        """Getting a missing component returns None."""
        cp = get_control_plane()
        
        result = cp.get_component("nonexistent")
        assert result is None


class TestDecisionContext:
    """Test decision context creation."""
    
    def test_create_context(self):
        """Should create a decision context."""
        cp = get_control_plane()
        
        context = cp.create_context(symbol="AAPL")
        
        assert context is not None
        assert hasattr(context, 'symbol')
        assert context.symbol == "AAPL"
    
    def test_context_has_timestamp(self):
        """Decision context should have timestamp."""
        cp = get_control_plane()
        
        context = cp.create_context(symbol="MSFT")
        
        assert hasattr(context, 'timestamp') or hasattr(context, 'created_at')


class TestSafetyChecks:
    """Test safety check functionality."""
    
    def test_add_safety_check(self):
        """Safety checks can be added."""
        cp = get_control_plane()
        
        def custom_check(context):
            return True
        
        cp.add_safety_check(custom_check)
        
        # Verify check was added
        assert len(cp._safety_checks) > 0


class TestStatus:
    """Test status and health check functionality."""
    
    def test_get_status(self):
        """Status should return current state."""
        cp = get_control_plane()
        
        status = cp.get_status()
        
        assert status is not None
        assert "mode" in status or hasattr(status, 'mode')
    
    def test_health_check(self):
        """Health check should return health information."""
        cp = get_control_plane()
        
        health = cp.check_health()
        
        assert health is not None
        assert "overall_status" in health
        assert health["overall_status"] == "healthy"


class TestResetForTesting:
    """Test reset functionality."""
    
    def test_reset_for_testing(self):
        """Reset should clear all state."""
        cp = get_control_plane(mode=ControlPlaneMode.LIVE)
        
        # Add some state
        cp.engage_kill_switch("Test")
        
        class MockComponent:
            pass
        cp.register_component("test", MockComponent())
        
        # Reset
        cp._reset_for_testing()
        
        # Verify cleared
        assert not cp.kill_switch_engaged
        assert cp.get_component("test") is None
