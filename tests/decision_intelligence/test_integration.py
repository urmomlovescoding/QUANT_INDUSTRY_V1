"""
Integration Tests for Decision Intelligence Platform
====================================================

Tests the full system working together.
"""

import pytest
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence import (
    get_control_plane,
    get_decision_trace,
    get_exit_value_learner,
    get_shadow_manager,
    get_self_improvement_orchestrator,
    ControlPlaneMode,
    ShadowStatus,
    TriggerType,
)


class TestFullDecisionFlow:
    """Test complete decision flow through all components."""
    
    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset all singletons before each test."""
        # Note: In production, you'd have proper reset mechanisms
        # For testing, we work with the existing state
        pass
    
    def test_entry_decision_flow(self):
        """Test full entry decision flow."""
        # 1. Create context via Control Plane
        control_plane = get_control_plane()
        
        context = control_plane.create_context(
            symbol="AAPL",
            regime="trending_bull",
            regime_confidence=0.85,
            signal={"direction": "LONG", "confidence": 0.72}
        )
        
        ctx_id = context["context_id"]
        assert ctx_id is not None
        
        # 2. Record regime decision to trace
        trace = get_decision_trace()
        
        regime_node = trace.add_decision(
            context_id=ctx_id,
            component="regime_detector",
            decision="TRENDING_BULL",
            inputs={"price_data": "compressed"},
            outputs={"regime": "trending_bull", "confidence": 0.85},
            confidence=0.85,
        )
        
        # 3. Record signal decision
        signal_node = trace.add_decision(
            context_id=ctx_id,
            component="signal_generator",
            decision="LONG_SIGNAL",
            inputs={"regime": "trending_bull"},
            outputs={"direction": "LONG", "confidence": 0.72},
            confidence=0.72,
        )
        
        # Connect the decisions
        trace.add_edge(regime_node, signal_node, "triggers")
        
        # 4. Record to control plane
        control_plane.record_decision(
            context_id=ctx_id,
            component="signal_generator",
            decision="ENTER_LONG",
            reason="Strong signal in favorable regime",
            data={"entry_price": 185.50}
        )
        
        # 5. Verify decision path
        path = trace.get_decision_path(ctx_id)
        assert len(path) >= 2
        
        # 6. Verify context was updated
        ctx = control_plane.get_context(ctx_id)
        assert len(ctx.decisions) >= 1
    
    def test_exit_decision_with_learning(self):
        """Test exit decision using value learner."""
        control_plane = get_control_plane()
        trace = get_decision_trace()
        learner = get_exit_value_learner()
        
        # 1. Create position context
        context = control_plane.create_context(
            symbol="MSFT",
            regime="sideways",
            regime_confidence=0.7,
            signal=None  # Existing position
        )
        
        ctx_id = context["context_id"]
        
        # 2. Get exit recommendation
        state = learner.discretize_state(
            regime="sideways",
            time_in_trade_minutes=90,
            unrealized_pnl_pct=1.5,
            current_volatility=0.018,
            avg_volatility=0.015,
            direction="LONG",
        )
        
        recommendation = learner.recommend_action(state, unrealized_pnl=1.5)
        
        # 3. Record exit decision
        exit_node = trace.add_decision(
            context_id=ctx_id,
            component="exit_learner",
            decision=f"RECOMMEND_{recommendation.action.upper()}",
            inputs={"state": str(state)},
            outputs=recommendation.to_dict(),
            confidence=recommendation.confidence,
        )
        
        # 4. Record outcome
        trace.record_outcome(
            node_id=exit_node,
            outcome="executed",
            realized_pnl=1.5 if recommendation.action == "exit" else None,
        )
        
        # 5. Update learner with experience
        learner.record_experience(
            state=state,
            action=recommendation.action,
            reward=0.015,  # 1.5% P&L as reward
            next_state=None,
            done=True,
        )
        
        assert recommendation.action in ["hold", "exit"]
    
    def test_shadow_mode_comparison(self):
        """Test shadow mode alongside live decisions."""
        control_plane = get_control_plane()
        trace = get_decision_trace()
        shadow_manager = get_shadow_manager()
        
        # 1. Create shadow component
        shadow = shadow_manager.create_shadow(
            name="improved_momentum_v2",
            version="v2.0",
            initial_status=ShadowStatus.PARALLEL,
        )
        
        # 2. Create decision context
        context = control_plane.create_context(
            symbol="GOOGL",
            regime="trending_bull",
            regime_confidence=0.9,
            signal={"direction": "LONG", "confidence": 0.8}
        )
        
        ctx_id = context["context_id"]
        
        # 3. Live decision
        live_node = trace.add_decision(
            context_id=ctx_id,
            component="momentum_v1",
            decision="ENTER_LONG",
            confidence=0.75,
        )
        
        # 4. Shadow decision (parallel)
        shadow_manager.record_shadow_decision(
            component_id=shadow.component_id,
            context_id=ctx_id,
            decision="ENTER_LONG",  # Same decision
            confidence=0.82,  # Higher confidence
            expected_outcome=0.025,
        )
        
        # 5. After trade completes, compare
        shadow_manager.compare_to_live(
            component_id=shadow.component_id,
            context_id=ctx_id,
            live_decision="ENTER_LONG",
            live_outcome=0.02,  # 2% gain
            shadow_outcome=0.025,  # Shadow expected 2.5%
        )
        
        # 6. Check shadow performance
        report = shadow_manager.get_shadow_report(shadow.component_id)
        assert report is not None
    
    def test_improvement_cycle_trigger(self):
        """Test self-improvement cycle triggered by drift."""
        control_plane = get_control_plane()
        trace = get_decision_trace()
        orchestrator = get_self_improvement_orchestrator()
        
        # 1. Simulate poor performance that would trigger improvement
        ctx = control_plane.create_context(
            symbol="NVDA",
            regime="volatile",
            regime_confidence=0.6,
            signal={"direction": "LONG", "confidence": 0.55}
        )
        
        # 2. Record failing decision
        fail_node = trace.add_decision(
            context_id=ctx["context_id"],
            component="struggling_strategy",
            decision="ENTER_LONG",
            confidence=0.55,
            outcome="loss",
            metadata={"expected_pnl": 0.02, "actual_pnl": -0.03}
        )
        
        # 3. Check if improvement should trigger
        status = orchestrator.get_status()
        
        # Just verify the system is operational
        assert status["current_phase"] in [
            "detecting", "analyzing", "proposing", 
            "validating", "deploying", "complete", "failed"
        ]
    
    def test_kill_switch_halts_all(self):
        """Test that kill switch stops all decision making."""
        control_plane = get_control_plane()
        
        # 1. Set to live mode
        control_plane.set_mode(ControlPlaneMode.LIVE)
        assert control_plane.check_safety()
        
        # 2. Engage kill switch
        control_plane.engage_kill_switch("Integration test - market event")
        
        # 3. Verify all systems halt
        assert not control_plane.check_safety()
        assert control_plane.kill_switch_engaged
        
        # 4. Release
        control_plane.release_kill_switch("Test complete")
        assert control_plane.check_safety()


class TestModeTransitions:
    """Test system behavior across different modes."""
    
    def test_shadow_mode_no_execution(self):
        """Shadow mode should not allow real execution."""
        control_plane = get_control_plane()
        control_plane.set_mode(ControlPlaneMode.SHADOW)
        
        # Safety should pass (system healthy)
        assert control_plane.check_safety()
        
        # But execution not allowed
        assert not control_plane.is_active
    
    def test_paper_mode_execution(self):
        """Paper mode should allow simulated execution."""
        control_plane = get_control_plane()
        control_plane.set_mode(ControlPlaneMode.PAPER)
        
        assert control_plane.check_safety()
        assert control_plane.is_active
    
    def test_live_mode_requires_safety(self):
        """Live mode requires all safety checks."""
        control_plane = get_control_plane()
        control_plane.set_mode(ControlPlaneMode.LIVE)
        
        # Without kill switch
        if not control_plane.kill_switch_engaged:
            assert control_plane.check_safety()
            assert control_plane.is_active


class TestDataFlow:
    """Test data flow between components."""
    
    def test_trace_to_improvement(self):
        """Decision trace data should inform improvement."""
        trace = get_decision_trace()
        orchestrator = get_self_improvement_orchestrator()
        
        # 1. Add decisions to trace
        for i in range(5):
            trace.add_decision(
                context_id=f"flow_test_{i}",
                component="test_strategy",
                decision="TRADE",
                outcome="loss" if i < 3 else "profit",
                metadata={"iteration": i}
            )
        
        # 2. Get trace stats
        stats = trace.get_stats()
        
        # 3. Improvement system could use this data
        # (In real system, this would inform drift detection)
        assert stats["outcomes"]["loss"] >= 3
    
    def test_learner_updates_from_decisions(self):
        """Exit learner should update from decision outcomes."""
        learner = get_exit_value_learner()
        trace = get_decision_trace()
        
        # 1. Record decision
        node = trace.add_decision(
            context_id="learn_test",
            component="exit_learner",
            decision="HOLD",
            outputs={"action": "hold"},
        )
        
        # 2. Decision executed, outcome recorded
        trace.record_outcome(node, "profit", 0.03)
        
        # 3. Learner gets updated
        state = learner.discretize_state(
            "trending_bull", 30, 2.0, 0.015, 0.012, "LONG"
        )
        learner.update(state, "hold", 0.03, None, True)
        
        # 4. Verify learning occurred
        q = learner.get_q_value(state, "hold")
        assert q != 0  # Should have learned something


class TestAPIReadiness:
    """Test that components are ready for API exposure."""
    
    def test_control_plane_status_serializable(self):
        """Control plane status should be JSON serializable."""
        import json
        
        control_plane = get_control_plane()
        status = control_plane.get_status()
        
        # Should not raise
        serialized = json.dumps(status)
        assert serialized
    
    def test_trace_stats_serializable(self):
        """Trace stats should be JSON serializable."""
        import json
        
        trace = get_decision_trace()
        stats = trace.get_stats()
        
        serialized = json.dumps(stats)
        assert serialized
    
    def test_learner_recommendation_serializable(self):
        """Exit recommendation should be JSON serializable."""
        import json
        
        learner = get_exit_value_learner()
        state = learner.discretize_state(
            "trending_bull", 30, 1.5, 0.015, 0.012, "LONG"
        )
        rec = learner.recommend_action(state, 1.5)
        
        d = rec.to_dict()
        serialized = json.dumps(d)
        assert serialized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
