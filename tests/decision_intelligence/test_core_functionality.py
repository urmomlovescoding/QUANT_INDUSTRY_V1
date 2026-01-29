"""
Core Functionality Tests for Decision Intelligence
===================================================
These tests verify the actual implemented API works correctly.
"""

import pytest
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence import (
    # Control Plane
    AIControlPlane,
    ControlPlaneMode,
    DecisionContext,
    get_control_plane,
    reset_control_plane,
    
    # Decision Trace
    DecisionTrace,
    TraceNode,
    get_decision_trace,
    
    # Exit Value Learning
    ExitValueLearner,
    ExitRecommendation,
    get_exit_value_learner,
    
    # Shadow Mode
    ShadowModeManager,
    ShadowComponent,
    ShadowStatus,
    get_shadow_manager,
    
    # Self Improvement
    SelfImprovementOrchestrator,
    ImprovementPhase,
    get_self_improvement_orchestrator,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before and after each test."""
    reset_control_plane()
    yield
    reset_control_plane()


class TestControlPlane:
    """Test AI Control Plane core functionality."""
    
    def test_singleton_via_get_function(self):
        """get_control_plane returns the same instance."""
        cp1 = get_control_plane()
        cp2 = get_control_plane()
        assert cp1 is cp2
    
    def test_default_mode_is_shadow(self):
        """Default mode should be SHADOW for safety."""
        cp = get_control_plane()
        assert cp.mode == ControlPlaneMode.SHADOW
    
    def test_is_active_property(self):
        """is_active property should be accessible."""
        cp = get_control_plane()
        assert hasattr(cp, 'is_active')
        assert isinstance(cp.is_active, bool)
    
    def test_kill_switch_property(self):
        """kill_switch_engaged property should be accessible."""
        cp = get_control_plane()
        assert hasattr(cp, 'kill_switch_engaged')
        assert cp.kill_switch_engaged == False
    
    def test_engage_kill_switch(self):
        """Should be able to engage kill switch."""
        cp = get_control_plane()
        cp.engage_kill_switch("Test reason")
        assert cp.kill_switch_engaged == True
    
    def test_release_kill_switch(self):
        """Should be able to release kill switch."""
        cp = get_control_plane()
        cp.engage_kill_switch("Test")
        cp.release_kill_switch("Recovery")
        assert cp.kill_switch_engaged == False
    
    def test_create_context(self):
        """Should create decision context."""
        cp = get_control_plane()
        ctx = cp.create_context("AAPL")
        assert ctx is not None
        assert ctx.symbol == "AAPL"
        assert ctx.context_id is not None
    
    def test_register_component(self):
        """Should register components."""
        cp = get_control_plane()
        
        class MockComponent:
            pass
        
        cp.register_component("test", MockComponent())
        assert cp.get_component("test") is not None
    
    def test_get_status(self):
        """Should return status dict."""
        cp = get_control_plane()
        status = cp.get_status()
        assert isinstance(status, dict)
        assert 'mode' in status
        assert 'is_active' in status


class TestDecisionTrace:
    """Test Decision Trace functionality."""
    
    def test_singleton(self):
        """get_decision_trace returns the same instance."""
        dt1 = get_decision_trace()
        dt2 = get_decision_trace()
        assert dt1 is dt2
    
    def test_has_graph(self):
        """Should have a NetworkX graph."""
        dt = get_decision_trace()
        assert dt.graph is not None
    
    def test_get_stats(self):
        """Should return stats dict."""
        dt = get_decision_trace()
        stats = dt.get_stats()
        assert isinstance(stats, dict)
        assert 'total_nodes' in stats
        assert 'total_edges' in stats


class TestExitValueLearner:
    """Test Exit Value Learner functionality."""
    
    def test_singleton(self):
        """get_exit_value_learner returns the same instance."""
        evl1 = get_exit_value_learner()
        evl2 = get_exit_value_learner()
        assert evl1 is evl2
    
    def test_get_stats(self):
        """Should return stats dict."""
        evl = get_exit_value_learner()
        stats = evl.get_stats()
        assert isinstance(stats, dict)
        assert 'total_states' in stats
        assert 'learning_rate' in stats
    
    def test_discretize_state(self):
        """Should discretize state into buckets."""
        evl = get_exit_value_learner()
        state = evl.discretize_state(
            regime="trending",
            time_in_trade_minutes=30,
            unrealized_pnl_pct=0.5,
            current_volatility=0.02,
            avg_volatility=0.015,
            direction="LONG"
        )
        assert state is not None


class TestShadowManager:
    """Test Shadow Mode Manager functionality."""
    
    def test_singleton(self):
        """get_shadow_manager returns the same instance."""
        sm1 = get_shadow_manager()
        sm2 = get_shadow_manager()
        assert sm1 is sm2
    
    def test_list_components(self):
        """Should list components."""
        sm = get_shadow_manager()
        components = sm.list_components()
        assert isinstance(components, list)
    
    def test_get_comparison_summary(self):
        """Should return comparison summary."""
        sm = get_shadow_manager()
        summary = sm.get_comparison_summary()
        assert isinstance(summary, dict)


class TestSelfImprovement:
    """Test Self Improvement Orchestrator functionality."""
    
    def test_singleton(self):
        """get_self_improvement_orchestrator returns the same instance."""
        sio1 = get_self_improvement_orchestrator()
        sio2 = get_self_improvement_orchestrator()
        assert sio1 is sio2
    
    def test_initial_phase(self):
        """Should start in MONITORING phase."""
        sio = get_self_improvement_orchestrator()
        assert sio.current_phase == ImprovementPhase.MONITORING
    
    def test_get_status(self):
        """Should return status dict."""
        sio = get_self_improvement_orchestrator()
        status = sio.get_status()
        assert isinstance(status, dict)
        assert 'current_phase' in status
    
    def test_component_properties(self):
        """Should have component properties."""
        sio = get_self_improvement_orchestrator()
        assert hasattr(sio, 'control_plane')
        assert hasattr(sio, 'shadow_manager')


class TestIntegration:
    """Test component integration."""
    
    def test_wire_components_together(self):
        """Components should be wireable together."""
        cp = get_control_plane()
        dt = get_decision_trace()
        evl = get_exit_value_learner()
        sm = get_shadow_manager()
        sio = get_self_improvement_orchestrator()
        
        # Register components with control plane
        cp.register_component("decision_trace", dt)
        cp.register_component("exit_learner", evl)
        cp.register_component("shadow_manager", sm)
        
        # Verify they're accessible
        assert cp.decision_trace is dt
        assert cp.exit_learner is evl
        assert cp.shadow_manager is sm
        
        # Register with self improvement
        sio.register_control_plane(cp)
        sio.register_shadow_manager(sm)
        
        # Verify wiring
        assert sio.control_plane is cp
        assert sio.shadow_manager is sm
    
    def test_context_flow(self):
        """Decision context should flow through system."""
        cp = get_control_plane()
        
        # Create context
        ctx = cp.create_context("AAPL")
        
        # Add decisions
        ctx.add_decision("regime", "BULL", "Strong trend detected", {"trend_score": 0.8})
        ctx.add_decision("strategy", "LONG", "Momentum signal", {"confidence": 0.75})
        
        # Verify context
        assert len(ctx.decisions) == 2
        assert ctx.decisions[0]['component'] == 'regime'
        assert ctx.decisions[1]['component'] == 'strategy'
    
    def test_all_imports_work(self):
        """All expected exports should be importable."""
        from decision_intelligence import (
            AIControlPlane,
            ControlPlaneMode,
            ComponentStatus,
            DecisionContext,
            get_control_plane,
            reset_control_plane,
            DecisionTrace,
            TraceNode,
            TraceEdge,
            NodeType,
            EdgeType,
            get_decision_trace,
            ExitValueLearner,
            ExitState,
            ExitAction,
            ExitReason,
            ExitRecommendation,
            ExitValueIntegration,
            get_exit_value_learner,
            ShadowModeManager,
            ShadowComponent,
            ShadowDecision,
            ShadowStatus,
            PromotionCriteria,
            get_shadow_manager,
            SelfImprovementOrchestrator,
            ImprovementCycle,
            ImprovementPhase,
            TriggerType,
            ImprovementConfig,
            get_self_improvement_orchestrator,
        )
        # If we get here, all imports work
        assert True
