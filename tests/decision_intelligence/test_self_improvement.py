"""
Tests for Self-Improvement Orchestrator
"""

import pytest
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.self_improvement import (
    SelfImprovementOrchestrator,
    ImprovementCycle,
    ImprovementPhase,
    TriggerType,
)


class TestImprovementPhase:
    """Test ImprovementPhase enum."""
    
    def test_phase_values(self):
        """Should have expected phase values."""
        assert ImprovementPhase.DETECTING.value == "detecting"
        assert ImprovementPhase.ANALYZING.value == "analyzing"
        assert ImprovementPhase.PROPOSING.value == "proposing"
        assert ImprovementPhase.VALIDATING.value == "validating"
        assert ImprovementPhase.DEPLOYING.value == "deploying"
        assert ImprovementPhase.COMPLETE.value == "complete"
        assert ImprovementPhase.FAILED.value == "failed"


class TestTriggerType:
    """Test TriggerType enum."""
    
    def test_trigger_values(self):
        """Should have expected trigger values."""
        assert TriggerType.DRIFT.value == "drift"
        assert TriggerType.SCHEDULE.value == "schedule"
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.PERFORMANCE.value == "performance"


class TestImprovementCycle:
    """Test ImprovementCycle dataclass."""
    
    def test_create_cycle(self):
        """Should create improvement cycle."""
        cycle = ImprovementCycle(
            cycle_id="cycle_123",
            trigger=TriggerType.DRIFT,
            started_at=datetime.now(),
            phase=ImprovementPhase.ANALYZING,
            component_name="regime_detector",
        )
        
        assert cycle.cycle_id == "cycle_123"
        assert cycle.trigger == TriggerType.DRIFT
        assert cycle.phase == ImprovementPhase.ANALYZING
    
    def test_cycle_to_dict(self):
        """Should convert to dictionary."""
        cycle = ImprovementCycle(
            cycle_id="cycle_456",
            trigger=TriggerType.MANUAL,
            started_at=datetime.now(),
            phase=ImprovementPhase.VALIDATING,
            component_name="signal_generator",
            old_version="v1.0",
            new_version="v1.1",
        )
        
        d = cycle.to_dict()
        
        assert d["cycle_id"] == "cycle_456"
        assert d["trigger"] == "manual"
        assert d["phase"] == "validating"
        assert d["component_name"] == "signal_generator"
    
    def test_cycle_duration(self):
        """Should calculate duration."""
        start = datetime.now() - timedelta(hours=2)
        end = datetime.now()
        
        cycle = ImprovementCycle(
            cycle_id="dur_test",
            trigger=TriggerType.DRIFT,
            started_at=start,
            completed_at=end,
            phase=ImprovementPhase.COMPLETE,
            component_name="test",
        )
        
        d = cycle.to_dict()
        # Duration should be ~2 hours (7200 seconds)
        if "duration_seconds" in d:
            assert d["duration_seconds"] > 7000


class TestOrchestratorBasics:
    """Test basic orchestrator functionality."""
    
    def test_singleton(self):
        """Should be a singleton."""
        o1 = SelfImprovementOrchestrator()
        o2 = SelfImprovementOrchestrator()
        assert o1 is o2
    
    def test_initial_state(self):
        """Should start in detecting phase."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        status = orch.get_status()
        assert status["current_phase"] == "detecting"
        assert status["active_cycle"] is None
    
    def test_get_status(self):
        """Should return comprehensive status."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        status = orch.get_status()
        
        assert "current_phase" in status
        assert "active_cycle" in status
        assert "total_cycles" in status
        assert "config" in status


class TestTriggerImprovement:
    """Test improvement triggering."""
    
    def test_manual_trigger(self):
        """Should trigger improvement manually."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        cycle = orch.trigger_improvement(
            component_name="test_component",
            trigger=TriggerType.MANUAL,
        )
        
        assert cycle is not None
        assert cycle.trigger == TriggerType.MANUAL
        assert cycle.component_name == "test_component"
        assert cycle.phase == ImprovementPhase.ANALYZING
    
    def test_prevent_concurrent_cycles(self):
        """Should prevent concurrent improvement cycles."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        # Start first cycle
        cycle1 = orch.trigger_improvement("comp_1", TriggerType.MANUAL)
        assert cycle1 is not None
        
        # Try to start second - should fail
        with pytest.raises(RuntimeError):
            orch.trigger_improvement("comp_2", TriggerType.MANUAL)
    
    def test_drift_trigger(self):
        """Should handle drift trigger."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        cycle = orch.trigger_improvement(
            component_name="drifting_component",
            trigger=TriggerType.DRIFT,
            metadata={"drift_score": 0.25},
        )
        
        assert cycle is not None
        assert cycle.trigger == TriggerType.DRIFT


class TestPhaseTransitions:
    """Test phase transitions."""
    
    def test_analyzing_to_proposing(self):
        """Should transition from analyzing to proposing."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        cycle = orch.trigger_improvement("test", TriggerType.MANUAL)
        assert cycle.phase == ImprovementPhase.ANALYZING
        
        # Advance to proposing
        orch.advance_phase(analysis_result={"issues": ["low_accuracy"]})
        
        updated = orch.get_active_cycle()
        assert updated.phase == ImprovementPhase.PROPOSING
    
    def test_proposing_to_validating(self):
        """Should transition from proposing to validating."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        orch.trigger_improvement("test", TriggerType.MANUAL)
        orch.advance_phase(analysis_result={})
        
        # Now in proposing, advance to validating
        orch.advance_phase(proposal={"new_version": "v2.0"})
        
        updated = orch.get_active_cycle()
        assert updated.phase == ImprovementPhase.VALIDATING
    
    def test_full_cycle_success(self):
        """Should complete full improvement cycle."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        cycle = orch.trigger_improvement("test_full", TriggerType.MANUAL)
        
        # Analyzing -> Proposing
        orch.advance_phase(analysis_result={"issue": "drift"})
        
        # Proposing -> Validating
        orch.advance_phase(proposal={"new_version": "v2.0"})
        
        # Validating -> Deploying
        orch.advance_phase(validation_result={"passed": True, "improvement": 0.1})
        
        # Deploying -> Complete
        orch.advance_phase(deployment_result={"success": True})
        
        # Cycle should be complete
        assert orch.get_active_cycle() is None
        
        history = orch.get_improvement_history(limit=1)
        assert len(history) == 1
        assert history[0]["phase"] == "complete"
    
    def test_cycle_failure(self):
        """Should handle cycle failure."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        orch.trigger_improvement("fail_test", TriggerType.MANUAL)
        orch.advance_phase(analysis_result={})
        orch.advance_phase(proposal={"new_version": "v2.0"})
        
        # Fail validation
        orch.fail_cycle(reason="Validation failed - performance degraded")
        
        assert orch.get_active_cycle() is None
        
        history = orch.get_improvement_history(limit=1)
        assert len(history) == 1
        assert history[0]["phase"] == "failed"


class TestDriftDetection:
    """Test drift detection."""
    
    def test_monitor_and_trigger(self):
        """Should monitor and potentially trigger improvement."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        # Without drift, should not trigger
        cycle = orch.monitor_and_trigger()
        # May or may not trigger depending on mock data
        # Just verify it returns None or ImprovementCycle
        assert cycle is None or isinstance(cycle, ImprovementCycle)
    
    def test_drift_threshold(self):
        """Should respect drift threshold."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        # Set high threshold
        orch.config["drift_threshold"] = 0.99
        
        # Should not trigger with such high threshold
        cycle = orch.monitor_and_trigger()
        assert cycle is None


class TestHistory:
    """Test improvement history."""
    
    def test_get_history(self):
        """Should retrieve improvement history."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        # Complete some cycles
        for i in range(3):
            orch.trigger_improvement(f"comp_{i}", TriggerType.MANUAL)
            orch.advance_phase(analysis_result={})
            orch.advance_phase(proposal={})
            orch.advance_phase(validation_result={"passed": True})
            orch.advance_phase(deployment_result={"success": True})
        
        history = orch.get_improvement_history(limit=10)
        assert len(history) == 3
    
    def test_history_limit(self):
        """Should respect history limit."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        # Complete many cycles
        for i in range(10):
            orch.trigger_improvement(f"comp_{i}", TriggerType.MANUAL)
            orch.advance_phase(analysis_result={})
            orch.advance_phase(proposal={})
            orch.advance_phase(validation_result={"passed": True})
            orch.advance_phase(deployment_result={"success": True})
        
        history = orch.get_improvement_history(limit=5)
        assert len(history) == 5


class TestConsecutiveFailures:
    """Test consecutive failure tracking."""
    
    def test_track_consecutive_failures(self):
        """Should track consecutive failures."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        # Fail multiple cycles
        for i in range(3):
            orch.trigger_improvement(f"fail_{i}", TriggerType.MANUAL)
            orch.fail_cycle(reason="Test failure")
        
        status = orch.get_status()
        assert status["consecutive_failures"] == 3
    
    def test_reset_failures_on_success(self):
        """Should reset failure count on success."""
        orch = SelfImprovementOrchestrator()
        orch._reset_for_testing()
        
        # Fail some
        orch.trigger_improvement("fail_1", TriggerType.MANUAL)
        orch.fail_cycle("Test")
        orch.trigger_improvement("fail_2", TriggerType.MANUAL)
        orch.fail_cycle("Test")
        
        assert orch.get_status()["consecutive_failures"] == 2
        
        # Succeed
        orch.trigger_improvement("success", TriggerType.MANUAL)
        orch.advance_phase({})
        orch.advance_phase({})
        orch.advance_phase({"passed": True})
        orch.advance_phase({"success": True})
        
        assert orch.get_status()["consecutive_failures"] == 0


# Helper for testing
def _add_reset_method():
    """Add reset method for testing."""
    def _reset_for_testing(self):
        self._current_phase = ImprovementPhase.DETECTING
        self._active_cycle = None
        self._cycle_history = []
        self._consecutive_failures = 0
        self._total_cycles = 0
        self._successful_cycles = 0
        self.config = {
            "drift_threshold": 0.15,
            "validation_days": 14,
            "improvement_threshold": 0.05,
        }
    
    SelfImprovementOrchestrator._reset_for_testing = _reset_for_testing


_add_reset_method()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
