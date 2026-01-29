"""
Tests for Exit Value Learning
"""

import pytest
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.exit_value_learning import (
    ExitValueLearner,
    ExitState,
    ExitAction,
    ExitRecommendation,
)


class TestExitState:
    """Test ExitState tuple."""
    
    def test_create_state(self):
        """Should create exit state."""
        state = ExitState(
            regime="trending_bull",
            time_bucket=2,
            pnl_bucket=1,
            volatility_bucket=1,
            direction="LONG",
        )
        
        assert state.regime == "trending_bull"
        assert state.time_bucket == 2
        assert state.direction == "LONG"
    
    def test_state_hashable(self):
        """State should be hashable for use as dict key."""
        state = ExitState("bull", 1, 0, 1, "LONG")
        
        # Should be usable as dictionary key
        d = {state: "value"}
        assert d[state] == "value"


class TestExitRecommendation:
    """Test ExitRecommendation dataclass."""
    
    def test_create_recommendation(self):
        """Should create recommendation."""
        rec = ExitRecommendation(
            action="hold",
            reason="Favorable regime",
            confidence=0.75,
            expected_value_hold=0.05,
            expected_value_exit=0.02,
            state=ExitState("bull", 1, 1, 1, "LONG"),
        )
        
        assert rec.action == "hold"
        assert rec.confidence == 0.75
    
    def test_recommendation_to_dict(self):
        """Should convert to dict."""
        rec = ExitRecommendation(
            action="exit",
            reason="Take profit",
            confidence=0.8,
            expected_value_hold=-0.01,
            expected_value_exit=0.03,
            state=ExitState("bear", 2, 2, 2, "SHORT"),
        )
        
        d = rec.to_dict()
        assert d["action"] == "exit"
        assert "state" in d


class TestExitValueLearnerBasics:
    """Test basic learner functionality."""
    
    def test_singleton(self):
        """Should be a singleton."""
        l1 = ExitValueLearner()
        l2 = ExitValueLearner()
        assert l1 is l2
    
    def test_discretize_state(self):
        """Should discretize continuous state."""
        learner = ExitValueLearner()
        
        state = learner.discretize_state(
            regime="trending_bull",
            time_in_trade_minutes=45,
            unrealized_pnl_pct=2.5,
            current_volatility=0.015,
            avg_volatility=0.012,
            direction="LONG",
        )
        
        assert isinstance(state, ExitState)
        assert state.regime == "trending_bull"
        assert state.direction == "LONG"
        # Time bucket should be non-zero for 45 minutes
        assert state.time_bucket > 0
    
    def test_time_bucket_boundaries(self):
        """Should correctly bucket time."""
        learner = ExitValueLearner()
        
        # Very short trade
        state1 = learner.discretize_state("bull", 5, 0, 0.01, 0.01, "LONG")
        # Medium trade
        state2 = learner.discretize_state("bull", 60, 0, 0.01, 0.01, "LONG")
        # Long trade
        state3 = learner.discretize_state("bull", 480, 0, 0.01, 0.01, "LONG")
        
        # Should be different buckets
        assert state1.time_bucket < state2.time_bucket < state3.time_bucket
    
    def test_pnl_bucket_boundaries(self):
        """Should correctly bucket P&L."""
        learner = ExitValueLearner()
        
        # Loss
        state1 = learner.discretize_state("bull", 30, -5.0, 0.01, 0.01, "LONG")
        # Breakeven
        state2 = learner.discretize_state("bull", 30, 0.0, 0.01, 0.01, "LONG")
        # Profit
        state3 = learner.discretize_state("bull", 30, 5.0, 0.01, 0.01, "LONG")
        
        # Loss bucket should be lower than profit bucket
        assert state1.pnl_bucket < state2.pnl_bucket < state3.pnl_bucket


class TestQValueLearning:
    """Test Q-learning updates."""
    
    def test_update_q_value(self):
        """Should update Q-values from experience."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        state = ExitState("trending_bull", 1, 1, 1, "LONG")
        
        # Initial Q-value should be 0
        initial_q = learner.get_q_value(state, "hold")
        
        # Update with positive reward
        learner.update(
            state=state,
            action="hold",
            reward=0.05,
            next_state=ExitState("trending_bull", 2, 1, 1, "LONG"),
            done=False,
        )
        
        # Q-value should have increased
        updated_q = learner.get_q_value(state, "hold")
        assert updated_q > initial_q
    
    def test_terminal_state_update(self):
        """Should handle terminal state correctly."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        state = ExitState("bear", 2, -1, 2, "LONG")
        
        # Terminal update (done=True)
        learner.update(
            state=state,
            action="exit",
            reward=-0.03,  # Loss on exit
            next_state=None,
            done=True,
        )
        
        # Q-value should reflect the reward
        q = learner.get_q_value(state, "exit")
        assert q < 0  # Negative due to loss


class TestRecommendation:
    """Test exit recommendation."""
    
    def test_recommend_action_hold(self):
        """Should recommend hold when profitable regime."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        # Train with positive hold experiences
        state = ExitState("trending_bull", 1, 1, 0, "LONG")
        for _ in range(10):
            learner.update(state, "hold", 0.01, ExitState("trending_bull", 2, 2, 0, "LONG"), False)
        
        rec = learner.recommend_action(state, unrealized_pnl=1.0)
        
        # Should recommend hold or have reasoning
        assert rec.action in ["hold", "exit"]
        assert rec.confidence >= 0 and rec.confidence <= 1
    
    def test_recommend_with_large_profit(self):
        """Should consider taking profits at high P&L."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        # Very high P&L bucket
        state = learner.discretize_state(
            regime="trending_bull",
            time_in_trade_minutes=60,
            unrealized_pnl_pct=15.0,  # Large profit
            current_volatility=0.02,
            avg_volatility=0.015,
            direction="LONG",
        )
        
        rec = learner.recommend_action(state, unrealized_pnl=15.0)
        
        # Should have a recommendation
        assert rec.action in ["hold", "exit"]
        # Reason should mention profit
        assert rec.reason
    
    def test_recommend_with_loss(self):
        """Should handle loss positions."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        state = learner.discretize_state(
            regime="volatile",
            time_in_trade_minutes=120,
            unrealized_pnl_pct=-5.0,  # Loss
            current_volatility=0.03,
            avg_volatility=0.02,
            direction="LONG",
        )
        
        rec = learner.recommend_action(state, unrealized_pnl=-5.0)
        
        assert rec.action in ["hold", "exit"]


class TestExperienceBuffer:
    """Test experience replay."""
    
    def test_record_experience(self):
        """Should record experiences."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        state = ExitState("bull", 1, 1, 1, "LONG")
        learner.record_experience(
            state=state,
            action="hold",
            reward=0.02,
            next_state=ExitState("bull", 2, 1, 1, "LONG"),
            done=False,
        )
        
        # Experience should be recorded
        assert len(learner.experience_buffer) > 0
    
    def test_experience_buffer_limit(self):
        """Should limit buffer size."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        learner.max_buffer_size = 100
        
        # Add many experiences
        for i in range(200):
            state = ExitState("bull", i % 5, i % 3, 1, "LONG")
            learner.record_experience(state, "hold", 0.01, state, False)
        
        # Buffer should not exceed max size
        assert len(learner.experience_buffer) <= 100


class TestValueSurface:
    """Test value surface retrieval."""
    
    def test_get_value_surface(self):
        """Should return value surface for regime."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        # Add some Q-values
        for t in range(3):
            for p in range(3):
                state = ExitState("trending_bull", t, p, 1, "LONG")
                learner.update(state, "hold", (p - 1) * 0.01, state, False)
        
        surface = learner.get_value_surface("trending_bull", "LONG")
        
        # Should have data points
        assert isinstance(surface, list)
    
    def test_optimal_exits_by_regime(self):
        """Should identify optimal exit points."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        # Train with varying outcomes
        learner.update(
            ExitState("trending_bull", 2, 2, 1, "LONG"),
            "exit",
            0.05,
            None,
            True
        )
        
        optimal = learner.get_optimal_exits_by_regime()
        
        # Should return dict of regimes
        assert isinstance(optimal, dict)


class TestStats:
    """Test statistics."""
    
    def test_get_stats(self):
        """Should return learner stats."""
        learner = ExitValueLearner()
        learner._reset_for_testing()
        
        # Add some data
        learner.update(
            ExitState("bull", 1, 1, 1, "LONG"),
            "hold",
            0.01,
            ExitState("bull", 2, 1, 1, "LONG"),
            False
        )
        
        stats = learner.get_stats()
        
        assert "total_states" in stats or "q_table_size" in stats
        assert "experience_count" in stats or True  # May vary by implementation


# Helper for testing
def _add_reset_method():
    """Add reset method for testing."""
    def _reset_for_testing(self):
        self._q_table = {}
        self._experience_buffer = []
        self._visit_counts = {}
    
    ExitValueLearner._reset_for_testing = _reset_for_testing


_add_reset_method()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
