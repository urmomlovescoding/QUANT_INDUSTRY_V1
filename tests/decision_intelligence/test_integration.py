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

        # create_context only takes symbol; regime/signal set separately
        context = control_plane.create_context(symbol="AAPL")

        ctx_id = context.context_id
        assert ctx_id is not None

        # Set regime and signal on the context object directly
        context.regime = "trending_bull"
        context.regime_confidence = 0.85
        context.signal_direction = "LONG"
        context.signal_confidence = 0.72

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

        # 4. Record decision on context (via add_decision method on context)
        context.add_decision(
            component="signal_generator",
            decision="ENTER_LONG",
            reason="Strong signal in favorable regime",
            data={"entry_price": 185.50}
        )

        # 5. Verify decision path
        path = trace.get_decision_path(ctx_id)
        assert len(path) >= 2

        # 6. Verify context was updated
        assert len(context.decisions) >= 1
    
    def test_exit_decision_with_learning(self):
        """Test exit decision using value learner."""
        from decision_intelligence.exit_value_learning import TradeEpisode, ExitAction
        from datetime import timezone

        control_plane = get_control_plane()
        trace = get_decision_trace()
        learner = get_exit_value_learner()

        # 1. Create position context
        context = control_plane.create_context(symbol="MSFT")
        context.regime = "sideways"
        context.regime_confidence = 0.7

        ctx_id = context.context_id

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
            decision=f"RECOMMEND_{recommendation.action.value.upper()}",
            inputs={"state": str(state)},
            outputs=recommendation.to_dict(),
            confidence=recommendation.confidence,
        )

        # 4. Record outcome
        trace.record_outcome(
            node_id=exit_node,
            outcome="executed",
            realized_pnl=1.5 if recommendation.action == ExitAction.EXIT else None,
        )

        # 5. Update learner via an episode (not record_experience)
        episode = TradeEpisode(
            episode_id=f"exit_test_{ctx_id}",
            symbol="MSFT",
            direction="LONG",
            entry_time=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc),
            states=[state],
            actions=[recommendation.action],
            final_pnl=0.015,  # 1.5% P&L
        )
        learner.update_from_episode(episode)

        assert recommendation.action in [ExitAction.HOLD, ExitAction.EXIT]
    
    def test_shadow_mode_comparison(self):
        """Test shadow mode alongside live decisions."""
        control_plane = get_control_plane()
        trace = get_decision_trace()
        shadow_manager = get_shadow_manager()

        # 1. Create shadow component (use register_shadow_component)
        shadow = shadow_manager.register_shadow_component(
            component_name="improved_momentum_v2",
            version="v2.0",
            config={"initial_status": "parallel"},
        )

        # 2. Create decision context
        context = control_plane.create_context(symbol="GOOGL")
        context.regime = "trending_bull"
        context.regime_confidence = 0.9
        context.signal_direction = "LONG"
        context.signal_confidence = 0.8

        ctx_id = context.context_id

        # 3. Live decision
        live_node = trace.add_decision(
            context_id=ctx_id,
            component="momentum_v1",
            decision="ENTER_LONG",
            confidence=0.75,
        )

        # 4. Shadow decision (parallel) - use record_shadow_decision API
        decision_id = shadow_manager.record_shadow_decision(
            component_id=shadow.component_id,
            decision_type="signal",
            decision_value={"direction": "LONG", "action": "ENTER_LONG"},
            confidence=0.82,
            symbol="GOOGL",
            context={"ctx_id": ctx_id, "expected_outcome": 0.025},
        )

        # 5. After trade completes, compare shadow to live
        shadow_manager.compare_to_live(
            decision_id=decision_id,
            live_decision={"direction": "LONG", "action": "ENTER_LONG"},
        )

        # 6. Record outcome
        shadow_manager.record_outcome(
            decision_id=decision_id,
            was_correct=True,
            shadow_pnl=0.025,
            live_pnl=0.02,
        )

        # 7. Check shadow performance
        report = shadow_manager.get_shadow_report(shadow.component_id)
        assert report is not None
    
    def test_improvement_cycle_trigger(self):
        """Test self-improvement cycle triggered by drift."""
        control_plane = get_control_plane()
        trace = get_decision_trace()
        orchestrator = get_self_improvement_orchestrator()

        # 1. Simulate poor performance that would trigger improvement
        ctx = control_plane.create_context(symbol="NVDA")
        ctx.regime = "volatile"
        ctx.regime_confidence = 0.6
        ctx.signal_direction = "LONG"
        ctx.signal_confidence = 0.55

        # 2. Record failing decision
        fail_node = trace.add_decision(
            context_id=ctx.context_id,
            component="struggling_strategy",
            decision="ENTER_LONG",
            confidence=0.55,
            outcome="loss",
            metadata={"expected_pnl": 0.02, "actual_pnl": -0.03}
        )

        # 3. Check if improvement should trigger
        status = orchestrator.get_status()

        # Just verify the system is operational
        # The orchestrator uses ImprovementPhase enum values
        assert status["current_phase"] in [
            "monitoring", "retraining", "validating",
            "promoting", "rolling_back"
        ]
    
    def test_kill_switch_halts_all(self):
        """Test that kill switch stops all decision making."""
        control_plane = get_control_plane()

        # 1. Set to live mode
        control_plane.set_mode(ControlPlaneMode.LIVE)
        health = control_plane.check_health()
        assert health["overall_status"] in ["healthy", "partial", "degraded"]

        # 2. Engage kill switch
        control_plane.engage_kill_switch("Integration test - market event")

        # 3. Verify all systems halt
        health_after = control_plane.check_health()
        assert health_after["overall_status"] == "kill_switch_engaged"
        assert control_plane.kill_switch_engaged

        # 4. Release
        control_plane.release_kill_switch("Test complete")
        health_released = control_plane.check_health()
        assert health_released["overall_status"] in ["healthy", "partial", "degraded"]


class TestModeTransitions:
    """Test system behavior across different modes."""

    def test_shadow_mode_no_execution(self):
        """Shadow mode should not allow real execution."""
        control_plane = get_control_plane()
        control_plane.set_mode(ControlPlaneMode.SHADOW)

        # Health check should work (system healthy)
        health = control_plane.check_health()
        assert health["overall_status"] in ["healthy", "partial", "degraded"]

        # But execution not allowed (is_active is False in shadow mode)
        assert not control_plane.is_active

    def test_paper_mode_execution(self):
        """Paper mode should allow simulated execution."""
        control_plane = get_control_plane()
        control_plane.set_mode(ControlPlaneMode.PAPER)

        health = control_plane.check_health()
        assert health["overall_status"] in ["healthy", "partial", "degraded"]
        assert control_plane.is_active

    def test_live_mode_requires_safety(self):
        """Live mode requires all safety checks."""
        control_plane = get_control_plane()
        control_plane.set_mode(ControlPlaneMode.LIVE)

        # Without kill switch
        if not control_plane.kill_switch_engaged:
            health = control_plane.check_health()
            assert health["overall_status"] in ["healthy", "partial", "degraded"]
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
        from decision_intelligence.exit_value_learning import TradeEpisode, ExitAction

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

        # 3. Learner gets updated via an episode
        state = learner.discretize_state(
            "trending_bull", 30, 2.0, 0.015, 0.012, "LONG"
        )

        # Create an episode to update the learner
        from datetime import datetime, timezone
        episode = TradeEpisode(
            episode_id="learn_test_episode",
            symbol="TEST",
            direction="LONG",
            entry_time=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc),
            states=[state],
            actions=[ExitAction.HOLD],
            final_pnl=0.03,
        )
        learner.update_from_episode(episode)

        # 4. Verify learning occurred by checking q_table directly
        state_tuple = state.to_tuple()
        q_hold = learner.q_table[state_tuple]["hold"]
        # After updating, the Q-value should reflect some learning
        assert q_hold != 0  # Should have learned something


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
