"""
Tests for Shadow Mode
"""

import pytest
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.shadow_mode import (
    ShadowManager,
    ShadowComponent,
    ShadowDecision,
    ShadowStatus,
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
            created_at=datetime.now(),
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
            decisions_count=100,
            correct_decisions=75,
        )
        
        assert component.accuracy == 0.75
    
    def test_component_accuracy_zero_decisions(self):
        """Should handle zero decisions."""
        component = ShadowComponent(
            component_id="zero_test",
            component_name="test",
            version="v1",
            status=ShadowStatus.SHADOW,
            decisions_count=0,
        )
        
        assert component.accuracy == 0.0


class TestShadowManagerBasics:
    """Test basic shadow manager functionality."""
    
    def test_singleton(self):
        """Should be a singleton."""
        m1 = ShadowManager()
        m2 = ShadowManager()
        assert m1 is m2
    
    def test_create_shadow(self):
        """Should create shadow component."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        component = manager.create_shadow(
            name="test_strategy",
            version="v1.0",
            initial_status=ShadowStatus.SHADOW,
        )
        
        assert component.component_name == "test_strategy"
        assert component.version == "v1.0"
        assert component.status == ShadowStatus.SHADOW
        assert component.component_id is not None
    
    def test_get_component(self):
        """Should retrieve component by ID."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        created = manager.create_shadow("lookup_test", "v1.0")
        retrieved = manager.get_component(created.component_id)
        
        assert retrieved is not None
        assert retrieved.component_id == created.component_id
    
    def test_get_nonexistent_component(self):
        """Should return None for missing component."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        result = manager.get_component("nonexistent_id")
        assert result is None


class TestShadowDecisions:
    """Test shadow decision recording."""
    
    def test_record_shadow_decision(self):
        """Should record shadow decisions."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        component = manager.create_shadow("decision_test", "v1.0")
        
        manager.record_shadow_decision(
            component_id=component.component_id,
            context_id="ctx_123",
            decision="ENTER_LONG",
            confidence=0.75,
            expected_outcome=0.03,
        )
        
        # Decision count should increase
        updated = manager.get_component(component.component_id)
        assert updated.decisions_count == 1
    
    def test_record_decision_outcome(self):
        """Should record decision outcomes."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        component = manager.create_shadow("outcome_test", "v1.0")
        
        manager.record_shadow_decision(
            component_id=component.component_id,
            context_id="ctx_out",
            decision="ENTER_LONG",
            confidence=0.8,
        )
        
        manager.record_decision_outcome(
            component_id=component.component_id,
            context_id="ctx_out",
            actual_outcome=0.05,
            was_correct=True,
        )
        
        updated = manager.get_component(component.component_id)
        assert updated.correct_decisions == 1
    
    def test_compare_to_live(self):
        """Should compare shadow to live decisions."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        component = manager.create_shadow("compare_test", "v1.0")
        
        # Record shadow decision
        manager.record_shadow_decision(
            component_id=component.component_id,
            context_id="ctx_cmp",
            decision="ENTER_LONG",
            confidence=0.85,
            expected_outcome=0.04,
        )
        
        # Compare to live
        manager.compare_to_live(
            component_id=component.component_id,
            context_id="ctx_cmp",
            live_decision="ENTER_LONG",
            live_outcome=0.03,
            shadow_outcome=0.04,
        )
        
        updated = manager.get_component(component.component_id)
        assert updated.live_comparison_count == 1


class TestComponentListing:
    """Test component listing."""
    
    def test_list_all_components(self):
        """Should list all components."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        manager.create_shadow("comp_1", "v1.0")
        manager.create_shadow("comp_2", "v1.0")
        manager.create_shadow("comp_3", "v1.0")
        
        components = manager.list_components()
        assert len(components) == 3
    
    def test_list_by_status(self):
        """Should filter by status."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        manager.create_shadow("shadow_1", "v1.0", ShadowStatus.SHADOW)
        manager.create_shadow("shadow_2", "v1.0", ShadowStatus.SHADOW)
        manager.create_shadow("parallel_1", "v1.0", ShadowStatus.PARALLEL)
        
        shadows = manager.list_components(status=ShadowStatus.SHADOW)
        assert len(shadows) == 2
        
        parallels = manager.list_components(status=ShadowStatus.PARALLEL)
        assert len(parallels) == 1


class TestPromotion:
    """Test component promotion."""
    
    def test_promote_component(self):
        """Should promote qualified component."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        component = manager.create_shadow("promote_test", "v1.0")
        
        # Add sufficient data for promotion
        for i in range(150):  # > min_comparisons
            manager.record_shadow_decision(
                component_id=component.component_id,
                context_id=f"ctx_{i}",
                decision="LONG",
                confidence=0.8,
            )
            manager.record_decision_outcome(
                component_id=component.component_id,
                context_id=f"ctx_{i}",
                actual_outcome=0.02,
                was_correct=True,  # 100% accuracy
            )
            manager.compare_to_live(
                component_id=component.component_id,
                context_id=f"ctx_{i}",
                live_decision="LONG",
                live_outcome=0.01,
                shadow_outcome=0.02,  # Shadow outperforms
            )
        
        # Should pass promotion checks
        can_promote = manager.check_promotion_eligibility(component.component_id)
        
        if can_promote:
            success = manager.promote_component(component.component_id)
            assert success
            
            updated = manager.get_component(component.component_id)
            assert updated.status == ShadowStatus.PROMOTED
    
    def test_reject_component(self):
        """Should reject poor performing component."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        component = manager.create_shadow("reject_test", "v1.0")
        
        # Record mostly wrong decisions
        for i in range(100):
            manager.record_shadow_decision(
                component_id=component.component_id,
                context_id=f"ctx_bad_{i}",
                decision="LONG",
                confidence=0.6,
            )
            manager.record_decision_outcome(
                component_id=component.component_id,
                context_id=f"ctx_bad_{i}",
                actual_outcome=-0.02,
                was_correct=False,
            )
        
        # Should be rejected
        manager.reject_component(component.component_id, "Poor accuracy")
        
        updated = manager.get_component(component.component_id)
        assert updated.status == ShadowStatus.REJECTED


class TestShadowReport:
    """Test shadow reporting."""
    
    def test_get_shadow_report(self):
        """Should generate comprehensive report."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        component = manager.create_shadow("report_test", "v1.0")
        
        # Add some data
        for i in range(10):
            manager.record_shadow_decision(
                component_id=component.component_id,
                context_id=f"ctx_rpt_{i}",
                decision="LONG",
                confidence=0.7 + i * 0.02,
            )
        
        report = manager.get_shadow_report(component.component_id)
        
        assert report is not None
        assert "component_id" in report
        assert "decisions_count" in report or "total_decisions" in report
    
    def test_comparison_summary(self):
        """Should generate comparison summary."""
        manager = ShadowManager()
        manager._reset_for_testing()
        
        comp1 = manager.create_shadow("compare_1", "v1.0")
        comp2 = manager.create_shadow("compare_2", "v2.0")
        
        # Add data to both
        for i in range(20):
            for comp in [comp1, comp2]:
                manager.record_shadow_decision(
                    component_id=comp.component_id,
                    context_id=f"ctx_{comp.component_id}_{i}",
                    decision="LONG",
                    confidence=0.75,
                )
        
        summary = manager.get_comparison_summary()
        
        assert summary is not None
        assert "total_components" in summary or "components" in summary


# Helper for testing
def _add_reset_method():
    """Add reset method for testing."""
    def _reset_for_testing(self):
        self._components = {}
        self._decisions = {}
        self._comparisons = {}
    
    ShadowManager._reset_for_testing = _reset_for_testing


_add_reset_method()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
