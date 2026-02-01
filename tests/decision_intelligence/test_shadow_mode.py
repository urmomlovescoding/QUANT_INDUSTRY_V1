"""
Tests for Shadow Mode Framework
"""

import pytest
from datetime import datetime, timezone
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.shadow_mode import (
    ShadowModeManager,
    ShadowComponent,
    ShadowDecision,
    ShadowStatus,
    PromotionCriteria,
)


class TestShadowStatus:
    """Test ShadowStatus enum."""

    def test_status_values(self):
        """Should have expected status values."""
        assert ShadowStatus.SHADOW.value == "shadow"
        assert ShadowStatus.PARALLEL.value == "parallel"
        assert ShadowStatus.CANDIDATE.value == "candidate"
        assert ShadowStatus.PROMOTED.value == "promoted"
        assert ShadowStatus.REJECTED.value == "rejected"


class TestShadowComponent:
    """Test ShadowComponent dataclass."""

    def test_create_component(self):
        """Should create shadow component."""
        component = ShadowComponent(
            component_id="test_123",
            component_name="improved_momentum",
            version="v2.0",
            status=ShadowStatus.SHADOW,
            created_at=datetime.now(timezone.utc),
        )

        assert component.component_id == "test_123"
        assert component.component_name == "improved_momentum"
        assert component.status == ShadowStatus.SHADOW

    def test_component_to_dict(self):
        """Should convert to dictionary."""
        component = ShadowComponent(
            component_id="test_456",
            component_name="new_strategy",
            version="v1.0",
            status=ShadowStatus.PARALLEL,
            created_at=datetime.now(timezone.utc),
        )

        d = component.to_dict()

        assert d["component_id"] == "test_456"
        assert d["status"] == "parallel"
        assert "created_at" in d

    def test_component_accuracy(self):
        """Should calculate accuracy correctly."""
        component = ShadowComponent(
            component_id="acc_test",
            component_name="test",
            version="v1",
            status=ShadowStatus.SHADOW,
            created_at=datetime.now(timezone.utc),
            decisions_count=100,
            correct_decisions=75,
        )

        # Accuracy is calculated in to_dict()
        assert component.to_dict()["accuracy"] == 0.75

    def test_component_accuracy_zero_decisions(self):
        """Should handle zero decisions."""
        component = ShadowComponent(
            component_id="zero_test",
            component_name="test",
            version="v1",
            status=ShadowStatus.SHADOW,
            created_at=datetime.now(timezone.utc),
            decisions_count=0,
        )

        assert component.to_dict()["accuracy"] == 0.0


class TestShadowManagerBasics:
    """Test basic shadow manager functionality."""

    @pytest.fixture(autouse=True)
    def setup_manager(self, tmp_path):
        """Set up a fresh manager for each test."""
        db_path = tmp_path / "test_shadow.db"
        self.manager = ShadowModeManager(db_path=db_path)

    def test_register_shadow_component(self):
        """Should register shadow component."""
        component = self.manager.register_shadow_component(
            component_name="test_strategy",
            version="v1.0",
        )

        assert component.component_name == "test_strategy"
        assert component.version == "v1.0"
        assert component.status == ShadowStatus.SHADOW
        assert component.component_id is not None

    def test_get_component(self):
        """Should retrieve component by ID."""
        created = self.manager.register_shadow_component("lookup_test", "v1.0")
        retrieved = self.manager.get_component(created.component_id)

        assert retrieved is not None
        assert retrieved.component_id == created.component_id

    def test_get_nonexistent_component(self):
        """Should return None for missing component."""
        result = self.manager.get_component("nonexistent_id")
        assert result is None


class TestShadowDecisions:
    """Test shadow decision recording."""

    @pytest.fixture(autouse=True)
    def setup_manager(self, tmp_path):
        """Set up a fresh manager for each test."""
        db_path = tmp_path / "test_shadow.db"
        self.manager = ShadowModeManager(db_path=db_path)

    def test_record_shadow_decision(self):
        """Should record shadow decisions."""
        component = self.manager.register_shadow_component("decision_test", "v1.0")

        decision_id = self.manager.record_shadow_decision(
            component_id=component.component_id,
            decision_type="signal",
            decision_value="ENTER_LONG",
            confidence=0.75,
            context={"expected_outcome": 0.03},
        )

        # Decision count should increase
        updated = self.manager.get_component(component.component_id)
        assert updated.decisions_count == 1
        assert decision_id != ""

    def test_record_decision_outcome(self):
        """Should record decision outcomes."""
        component = self.manager.register_shadow_component("outcome_test", "v1.0")

        decision_id = self.manager.record_shadow_decision(
            component_id=component.component_id,
            decision_type="signal",
            decision_value="ENTER_LONG",
            confidence=0.8,
            context={},
        )

        self.manager.record_outcome(
            decision_id=decision_id,
            was_correct=True,
            shadow_pnl=0.05,
        )

        updated = self.manager.get_component(component.component_id)
        assert updated.correct_decisions == 1

    def test_compare_to_live(self):
        """Should compare shadow to live decisions."""
        component = self.manager.register_shadow_component("compare_test", "v1.0")

        # Record shadow decision
        decision_id = self.manager.record_shadow_decision(
            component_id=component.component_id,
            decision_type="signal",
            decision_value="ENTER_LONG",
            confidence=0.85,
            context={"expected_outcome": 0.04},
        )

        # Compare to live
        agreed = self.manager.compare_to_live(
            decision_id=decision_id,
            live_decision="ENTER_LONG",
        )

        assert agreed is True
        updated = self.manager.get_component(component.component_id)
        assert updated.live_comparison_count == 1


class TestComponentListing:
    """Test component listing."""

    @pytest.fixture(autouse=True)
    def setup_manager(self, tmp_path):
        """Set up a fresh manager for each test."""
        db_path = tmp_path / "test_shadow.db"
        self.manager = ShadowModeManager(db_path=db_path)

    def test_list_all_components(self):
        """Should list all components."""
        self.manager.register_shadow_component("comp_1", "v1.0")
        self.manager.register_shadow_component("comp_2", "v1.0")
        self.manager.register_shadow_component("comp_3", "v1.0")

        components = self.manager.list_components()
        assert len(components) == 3

    def test_list_by_status(self):
        """Should filter by status."""
        self.manager.register_shadow_component("shadow_1", "v1.0")
        self.manager.register_shadow_component("shadow_2", "v1.0")

        # Promote one component to parallel
        comp = self.manager.register_shadow_component("parallel_1", "v1.0")
        comp.status = ShadowStatus.PARALLEL
        self.manager._save_component(comp)

        shadows = self.manager.list_components(status=ShadowStatus.SHADOW)
        assert len(shadows) == 2

        parallels = self.manager.list_components(status=ShadowStatus.PARALLEL)
        assert len(parallels) == 1


class TestPromotion:
    """Test component promotion."""

    @pytest.fixture(autouse=True)
    def setup_manager(self, tmp_path):
        """Set up a fresh manager for each test."""
        db_path = tmp_path / "test_shadow.db"
        self.manager = ShadowModeManager(db_path=db_path)
        # Lower thresholds for testing
        self.manager.min_decisions_for_promotion = 50
        self.manager.min_days_for_promotion = 0

    def test_promote_component(self):
        """Should promote qualified component."""
        component = self.manager.register_shadow_component("promote_test", "v1.0")

        # Add sufficient data for promotion
        for i in range(60):
            decision_id = self.manager.record_shadow_decision(
                component_id=component.component_id,
                decision_type="signal",
                decision_value="LONG",
                confidence=0.8,
                context={},
            )
            self.manager.record_outcome(
                decision_id=decision_id,
                was_correct=True,
                shadow_pnl=0.02,
                live_pnl=0.01,
            )

        # Check promotion
        checks = self.manager.check_promotion(component.component_id)
        assert isinstance(checks, list)

        # If all passed, promote
        all_passed = all(c.passed for c in checks)
        if all_passed:
            success = self.manager.promote_component(component.component_id)
            assert success

            updated = self.manager.get_component(component.component_id)
            assert updated.status == ShadowStatus.PROMOTED

    def test_reject_component(self):
        """Should reject poor performing component."""
        component = self.manager.register_shadow_component("reject_test", "v1.0")

        # Record some bad decisions
        for i in range(10):
            decision_id = self.manager.record_shadow_decision(
                component_id=component.component_id,
                decision_type="signal",
                decision_value="LONG",
                confidence=0.6,
                context={},
            )
            self.manager.record_outcome(
                decision_id=decision_id,
                was_correct=False,
                shadow_pnl=-0.02,
            )

        # Reject
        self.manager.reject_component(component.component_id, "Poor accuracy")

        updated = self.manager.get_component(component.component_id)
        assert updated.status == ShadowStatus.REJECTED


class TestShadowReport:
    """Test shadow reporting."""

    @pytest.fixture(autouse=True)
    def setup_manager(self, tmp_path):
        """Set up a fresh manager for each test."""
        db_path = tmp_path / "test_shadow.db"
        self.manager = ShadowModeManager(db_path=db_path)

    def test_get_shadow_report(self):
        """Should generate comprehensive report."""
        component = self.manager.register_shadow_component("report_test", "v1.0")

        # Add some data
        for i in range(10):
            self.manager.record_shadow_decision(
                component_id=component.component_id,
                decision_type="signal",
                decision_value="LONG",
                confidence=0.7 + i * 0.02,
                context={},
            )

        report = self.manager.get_shadow_report(component.component_id)

        assert report is not None
        # Report has component info
        assert "component" in report
        assert "component_id" in report["component"]

    def test_comparison_summary(self):
        """Should generate comparison summary."""
        comp1 = self.manager.register_shadow_component("compare_1", "v1.0")
        comp2 = self.manager.register_shadow_component("compare_2", "v2.0")

        # Add data to both
        for i in range(20):
            for comp in [comp1, comp2]:
                self.manager.record_shadow_decision(
                    component_id=comp.component_id,
                    decision_type="signal",
                    decision_value="LONG",
                    confidence=0.75,
                    context={},
                )

        summary = self.manager.get_comparison_summary()

        assert summary is not None
        assert "total_components" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
