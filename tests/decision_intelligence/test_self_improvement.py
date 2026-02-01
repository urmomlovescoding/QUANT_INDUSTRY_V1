"""
Tests for Self-Improvement Orchestrator
"""

import pytest
from datetime import datetime, timedelta, timezone
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.self_improvement import (
    SelfImprovementOrchestrator,
    ImprovementCycle,
    ImprovementPhase,
    TriggerType,
    ImprovementConfig,
    get_self_improvement_orchestrator,
)


class TestImprovementPhase:
    """Test ImprovementPhase enum."""

    def test_phase_values(self):
        """Should have expected phase values."""
        assert ImprovementPhase.MONITORING.value == "monitoring"
        assert ImprovementPhase.RETRAINING.value == "retraining"
        assert ImprovementPhase.VALIDATING.value == "validating"
        assert ImprovementPhase.PROMOTING.value == "promoting"
        assert ImprovementPhase.ROLLING_BACK.value == "rolling_back"


class TestTriggerType:
    """Test TriggerType enum."""

    def test_trigger_values(self):
        """Should have expected trigger values."""
        assert TriggerType.DRIFT_DETECTED.value == "drift_detected"
        assert TriggerType.SCHEDULED.value == "scheduled"
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.PERFORMANCE_DECLINE.value == "performance_decline"


class TestImprovementCycle:
    """Test ImprovementCycle dataclass."""

    def test_create_cycle(self):
        """Should create improvement cycle."""
        cycle = ImprovementCycle(
            cycle_id="cycle_123",
            trigger=TriggerType.DRIFT_DETECTED,
            started_at=datetime.now(timezone.utc),
            phase=ImprovementPhase.VALIDATING,
            component_name="regime_detector",
            old_version="v1.0",
        )

        assert cycle.cycle_id == "cycle_123"
        assert cycle.trigger == TriggerType.DRIFT_DETECTED
        assert cycle.phase == ImprovementPhase.VALIDATING

    def test_cycle_to_dict(self):
        """Should convert to dictionary."""
        cycle = ImprovementCycle(
            cycle_id="cycle_456",
            trigger=TriggerType.MANUAL,
            started_at=datetime.now(timezone.utc),
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

    def test_cycle_fields(self):
        """Should have expected fields."""
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        end = datetime.now(timezone.utc)

        cycle = ImprovementCycle(
            cycle_id="dur_test",
            trigger=TriggerType.DRIFT_DETECTED,
            started_at=start,
            completed_at=end,
            phase=ImprovementPhase.MONITORING,
            component_name="test",
            old_version="v1.0",
            success=True,
        )

        d = cycle.to_dict()
        assert d["success"] is True
        assert d["completed_at"] is not None


class TestImprovementConfig:
    """Test ImprovementConfig dataclass."""

    def test_default_config(self):
        """Should have default values."""
        config = ImprovementConfig()

        assert config.drift_score_threshold == 2.0
        assert config.performance_decline_threshold == 0.15
        assert config.min_training_samples == 100
        assert config.improvement_threshold == 0.05
        assert config.max_consecutive_failures == 3

    def test_custom_config(self):
        """Should allow custom values."""
        config = ImprovementConfig(
            drift_score_threshold=3.0,
            improvement_threshold=0.10,
        )

        assert config.drift_score_threshold == 3.0
        assert config.improvement_threshold == 0.10


class TestOrchestratorBasics:
    """Test basic orchestrator functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh orchestrator for each test."""
        self.db_path = tmp_path / "test_improvement.db"
        self.orch = SelfImprovementOrchestrator(db_path=self.db_path)

    def test_initial_state(self):
        """Should start in monitoring phase."""
        status = self.orch.get_status()
        assert status["current_phase"] == "monitoring"
        assert status["active_cycle"] is None

    def test_get_status(self):
        """Should return comprehensive status."""
        status = self.orch.get_status()

        assert "current_phase" in status
        assert "active_cycle" in status
        assert "total_cycles" in status
        assert "config" in status
        assert "consecutive_failures" in status


class TestSingleton:
    """Test singleton pattern."""

    def test_get_singleton(self):
        """Should get singleton instance."""
        # Reset global for test
        import decision_intelligence.self_improvement as module
        module._orchestrator = None

        o1 = get_self_improvement_orchestrator()
        o2 = get_self_improvement_orchestrator()

        assert o1 is o2

        # Clean up
        module._orchestrator = None


class TestTriggerImprovement:
    """Test improvement triggering."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh orchestrator for each test."""
        self.db_path = tmp_path / "test_improvement.db"
        self.orch = SelfImprovementOrchestrator(db_path=self.db_path)
        # Register a mock callback to allow retraining
        self.orch.register_retrain_callback(
            "test_component",
            lambda config: {"version": "v2.0"}
        )

    def test_manual_trigger(self):
        """Should trigger improvement manually."""
        cycle = self.orch.trigger_improvement(
            component_name="test_component",
            trigger=TriggerType.MANUAL,
        )

        assert cycle is not None
        assert cycle.trigger == TriggerType.MANUAL
        assert cycle.component_name == "test_component"

    def test_drift_trigger(self):
        """Should handle drift trigger."""
        self.orch.register_retrain_callback(
            "drifting_component",
            lambda config: {"version": "v2.0"}
        )

        cycle = self.orch.trigger_improvement(
            component_name="drifting_component",
            trigger=TriggerType.DRIFT_DETECTED,
            drift_score=0.25,
        )

        assert cycle is not None
        assert cycle.trigger == TriggerType.DRIFT_DETECTED
        assert cycle.drift_score == 0.25


class TestConsecutiveFailures:
    """Test consecutive failure tracking."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh orchestrator for each test."""
        self.db_path = tmp_path / "test_improvement.db"
        self.orch = SelfImprovementOrchestrator(db_path=self.db_path)

    def test_max_failures_prevents_trigger(self):
        """Should prevent triggering after max consecutive failures."""
        # Set consecutive failures to max
        self.orch.consecutive_failures = 3

        with pytest.raises(RuntimeError, match="Max consecutive improvement failures"):
            self.orch.trigger_improvement(
                "test",
                TriggerType.MANUAL,
            )


class TestComponentRegistration:
    """Test component registration."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh orchestrator for each test."""
        self.db_path = tmp_path / "test_improvement.db"
        self.orch = SelfImprovementOrchestrator(db_path=self.db_path)

    def test_register_drift_detector(self):
        """Should register drift detector."""
        mock_detector = MagicMock()
        self.orch.register_drift_detector(mock_detector)

        assert self.orch._drift_detector is mock_detector

    def test_register_evolution_engine(self):
        """Should register evolution engine."""
        mock_engine = MagicMock()
        self.orch.register_evolution_engine(mock_engine)

        assert self.orch._evolution_engine is mock_engine

    def test_register_feedback_loop(self):
        """Should register feedback loop."""
        mock_loop = MagicMock()
        self.orch.register_feedback_loop(mock_loop)

        assert self.orch._feedback_loop is mock_loop

    def test_register_shadow_manager(self):
        """Should register shadow manager."""
        mock_manager = MagicMock()
        self.orch.register_shadow_manager(mock_manager)

        assert self.orch._shadow_manager is mock_manager
        assert self.orch.shadow_manager is mock_manager

    def test_register_control_plane(self):
        """Should register control plane."""
        mock_plane = MagicMock()
        self.orch.register_control_plane(mock_plane)

        assert self.orch._control_plane is mock_plane
        assert self.orch.control_plane is mock_plane

    def test_register_retrain_callback(self):
        """Should register retrain callback."""
        callback = lambda x: {"version": "v2.0"}
        self.orch.register_retrain_callback("test_component", callback)

        assert "test_component" in self.orch._retrain_callbacks


class TestDriftDetection:
    """Test drift detection."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh orchestrator for each test."""
        self.db_path = tmp_path / "test_improvement.db"
        self.orch = SelfImprovementOrchestrator(db_path=self.db_path)

    def test_check_drift_without_detector(self):
        """Should return None without drift detector."""
        result = self.orch.check_for_drift("test_component")
        assert result is None

    def test_check_drift_with_detector(self):
        """Should check drift with registered detector."""
        mock_detector = MagicMock()
        # The detector doesn't have 'analyze' method, so it uses get_status
        mock_detector.analyze = None  # Ensure hasattr returns False
        del mock_detector.analyze  # Remove analyze attribute
        mock_detector.get_status.return_value = {
            "is_drifting": True,
            "drift_score": 2.5,
        }
        self.orch.register_drift_detector(mock_detector)

        result = self.orch.check_for_drift("test_component")
        assert result == 2.5

    def test_check_drift_with_analyze_method(self):
        """Should check drift with detector that has analyze method."""
        mock_detector = MagicMock()
        mock_report = MagicMock()
        mock_report.is_drifting = True
        mock_report.return_gap_zscore = 3.0
        mock_detector.analyze.return_value = mock_report
        self.orch.register_drift_detector(mock_detector)

        result = self.orch.check_for_drift("test_component")
        assert result == 3.0

    def test_monitor_and_trigger_no_drift(self):
        """Should not trigger without drift."""
        # No drift detector registered, should return None
        cycle = self.orch.monitor_and_trigger()
        assert cycle is None


class TestHistory:
    """Test improvement history."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh orchestrator for each test."""
        self.db_path = tmp_path / "test_improvement.db"
        self.orch = SelfImprovementOrchestrator(db_path=self.db_path)

    def test_get_empty_history(self):
        """Should return empty history initially."""
        history = self.orch.get_improvement_history(limit=10)
        assert len(history) == 0

    def test_history_after_cycle(self):
        """Should record completed cycles in history."""
        # Add a completed cycle directly to history
        cycle = ImprovementCycle(
            cycle_id="test_cycle",
            trigger=TriggerType.MANUAL,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            phase=ImprovementPhase.MONITORING,
            component_name="test",
            old_version="v1.0",
            new_version="v2.0",
            success=True,
        )
        self.orch.cycle_history.append(cycle)

        history = self.orch.get_improvement_history(limit=10)
        assert len(history) == 1
        assert history[0]["cycle_id"] == "test_cycle"

    def test_history_limit(self):
        """Should respect history limit."""
        # Add multiple cycles
        for i in range(10):
            cycle = ImprovementCycle(
                cycle_id=f"cycle_{i}",
                trigger=TriggerType.MANUAL,
                started_at=datetime.now(timezone.utc),
                phase=ImprovementPhase.MONITORING,
                component_name=f"comp_{i}",
                old_version="v1.0",
                success=True,
            )
            self.orch.cycle_history.append(cycle)

        history = self.orch.get_improvement_history(limit=5)
        assert len(history) == 5


class TestValidation:
    """Test validation functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Create a fresh orchestrator for each test."""
        self.db_path = tmp_path / "test_improvement.db"
        self.orch = SelfImprovementOrchestrator(db_path=self.db_path)

    def test_check_validation_no_active_cycle(self):
        """Should return None without active cycle."""
        result = self.orch.check_validation_progress()
        assert result is None

    def test_complete_validation_no_active_cycle(self):
        """Should return None without active cycle."""
        result = self.orch.complete_validation()
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
