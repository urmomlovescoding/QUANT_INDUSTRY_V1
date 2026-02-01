"""
Tests for Exit Value Learning
"""

import pytest
from datetime import datetime, timezone
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from decision_intelligence.exit_value_learning import (
    ExitValueLearner,
    ExitState,
    ExitAction,
    ExitReason,
    ExitRecommendation,
    TradeEpisode,
)


class TestExitState:
    """Test ExitState dataclass."""

    def test_create_state(self):
        """Should create state with all fields."""
        state = ExitState(
            regime="trending_bull",
            time_in_trade_bucket=2,
            pnl_bucket=1,
            volatility_bucket=1,
            direction="LONG",
        )

        assert state.regime == "trending_bull"
        assert state.time_in_trade_bucket == 2
        assert state.pnl_bucket == 1
        assert state.volatility_bucket == 1
        assert state.direction == "LONG"

    def test_state_hashable(self):
        """Should be usable as dict key (frozen dataclass)."""
        state = ExitState("bull", 1, 1, 1, "LONG")

        # Should be usable as dictionary key
        d = {state: "value"}
        assert d[state] == "value"

    def test_state_to_tuple(self):
        """Should convert to tuple."""
        state = ExitState("bull", 1, 1, 1, "LONG")
        t = state.to_tuple()
        assert t == ("bull", 1, 1, 1, "LONG")

    def test_state_from_tuple(self):
        """Should create from tuple."""
        t = ("bear", 2, -1, 2, "SHORT")
        state = ExitState.from_tuple(t)
        assert state.regime == "bear"
        assert state.direction == "SHORT"


class TestExitRecommendation:
    """Test ExitRecommendation dataclass."""

    def test_create_recommendation(self):
        """Should create recommendation."""
        rec = ExitRecommendation(
            action=ExitAction.HOLD,
            reason=ExitReason.VALUE_OPTIMAL,
            confidence=0.75,
            expected_value_hold=0.05,
            expected_value_exit=0.02,
            current_state=ExitState("bull", 1, 1, 1, "LONG"),
        )

        assert rec.action == ExitAction.HOLD
        assert rec.confidence == 0.75

    def test_recommendation_to_dict(self):
        """Should convert to dict."""
        rec = ExitRecommendation(
            action=ExitAction.EXIT,
            reason=ExitReason.TARGET_HIT,
            confidence=0.8,
            expected_value_hold=-0.01,
            expected_value_exit=0.03,
            current_state=ExitState("bear", 2, 2, 2, "SHORT"),
        )

        d = rec.to_dict()
        assert d["action"] == "exit"
        assert "state" in d
        assert d["reason"] == "target_hit"


class TestTradeEpisode:
    """Test TradeEpisode dataclass."""

    def test_create_episode(self):
        """Should create trade episode."""
        episode = TradeEpisode(
            episode_id="ep_123",
            symbol="AAPL",
            direction="LONG",
            entry_time=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc),
            final_pnl=0.025,
            exit_reason=ExitReason.TARGET_HIT,
        )

        assert episode.symbol == "AAPL"
        assert episode.final_pnl == 0.025


class TestExitValueLearnerBasics:
    """Test basic learner functionality."""

    @pytest.fixture
    def learner(self, tmp_path):
        """Create a fresh learner with temp database."""
        db_path = tmp_path / "test_exit_values.db"
        return ExitValueLearner(db_path=db_path)

    def test_initialization(self, learner):
        """Should initialize with default parameters."""
        assert learner.learning_rate == 0.1
        assert learner.discount_factor == 0.95
        assert learner.exploration_rate == 0.1

    def test_discretize_state(self, learner):
        """Should discretize continuous state."""
        state = learner.discretize_state(
            regime="trending_bull",
            time_in_trade_minutes=45,
            unrealized_pnl_pct=0.015,
            current_volatility=0.02,
            avg_volatility=0.02,
            direction="LONG",
        )

        assert isinstance(state, ExitState)
        assert state.regime == "trending_bull"
        assert state.time_in_trade_bucket == 1  # 15-60 min bucket
        assert state.pnl_bucket == 1  # 0.5% to 2% bucket
        assert state.volatility_bucket == 1  # normal volatility
        assert state.direction == "LONG"

    def test_time_bucket_boundaries(self, learner):
        """Should correctly bucket time values."""
        # 0-15 min -> bucket 0
        state1 = learner.discretize_state("bull", 10, 0, 0.02, 0.02, "LONG")
        assert state1.time_in_trade_bucket == 0

        # 15-60 min -> bucket 1
        state2 = learner.discretize_state("bull", 30, 0, 0.02, 0.02, "LONG")
        assert state2.time_in_trade_bucket == 1

        # 1-4 hours -> bucket 2
        state3 = learner.discretize_state("bull", 120, 0, 0.02, 0.02, "LONG")
        assert state3.time_in_trade_bucket == 2

        # 4-24 hours -> bucket 3
        state4 = learner.discretize_state("bull", 600, 0, 0.02, 0.02, "LONG")
        assert state4.time_in_trade_bucket == 3

        # >24 hours -> bucket 4
        state5 = learner.discretize_state("bull", 2000, 0, 0.02, 0.02, "LONG")
        assert state5.time_in_trade_bucket == 4

    def test_pnl_bucket_boundaries(self, learner):
        """Should correctly bucket P&L values."""
        # < -2% -> bucket -2
        state1 = learner.discretize_state("bull", 30, -0.03, 0.02, 0.02, "LONG")
        assert state1.pnl_bucket == -2

        # -2% to -0.5% -> bucket -1
        state2 = learner.discretize_state("bull", 30, -0.01, 0.02, 0.02, "LONG")
        assert state2.pnl_bucket == -1

        # -0.5% to 0.5% -> bucket 0
        state3 = learner.discretize_state("bull", 30, 0.001, 0.02, 0.02, "LONG")
        assert state3.pnl_bucket == 0

        # 0.5% to 2% -> bucket 1
        state4 = learner.discretize_state("bull", 30, 0.01, 0.02, 0.02, "LONG")
        assert state4.pnl_bucket == 1

        # > 2% -> bucket 2
        state5 = learner.discretize_state("bull", 30, 0.03, 0.02, 0.02, "LONG")
        assert state5.pnl_bucket == 2


class TestRecommendation:
    """Test recommendation generation."""

    @pytest.fixture
    def learner(self, tmp_path):
        """Create a fresh learner with temp database."""
        db_path = tmp_path / "test_exit_values.db"
        return ExitValueLearner(db_path=db_path)

    def test_recommend_action_default(self, learner):
        """Should return recommendation for any state."""
        state = ExitState("trending_bull", 1, 1, 1, "LONG")
        rec = learner.recommend_action(state)

        assert isinstance(rec, ExitRecommendation)
        assert rec.action in [ExitAction.HOLD, ExitAction.EXIT]
        assert rec.is_shadow is True

    def test_stop_loss_triggers_exit(self, learner):
        """Should recommend exit when stop loss hit."""
        state = ExitState("bear", 2, -2, 2, "LONG")
        rec = learner.recommend_action(state, unrealized_pnl=-0.025)

        assert rec.action == ExitAction.EXIT
        assert rec.reason == ExitReason.STOP_HIT
        assert rec.confidence == 1.0

    def test_take_profit_triggers_exit(self, learner):
        """Should recommend exit when take profit hit."""
        state = ExitState("bull", 2, 2, 1, "LONG")
        rec = learner.recommend_action(state, unrealized_pnl=0.05)

        assert rec.action == ExitAction.EXIT
        assert rec.reason == ExitReason.TARGET_HIT
        assert rec.confidence == 0.9

    def test_time_decay_triggers_exit(self, learner):
        """Should recommend exit on time decay."""
        state = ExitState("bull", 4, 0, 1, "LONG")  # time bucket 4, flat P&L
        rec = learner.recommend_action(state, unrealized_pnl=0.0)

        assert rec.action == ExitAction.EXIT
        assert rec.reason == ExitReason.TIME_DECAY

    def test_volatility_spike_triggers_exit(self, learner):
        """Should recommend exit on volatility spike with loss."""
        state = ExitState("volatile", 2, -1, 2, "LONG")  # high vol, small loss
        rec = learner.recommend_action(state, unrealized_pnl=-0.01)

        assert rec.action == ExitAction.EXIT
        assert rec.reason == ExitReason.VOLATILITY_SPIKE


class TestLearning:
    """Test Q-learning updates."""

    @pytest.fixture
    def learner(self, tmp_path):
        """Create a fresh learner with temp database."""
        db_path = tmp_path / "test_exit_values.db"
        return ExitValueLearner(db_path=db_path)

    def test_update_from_episode(self, learner):
        """Should update Q-values from episode."""
        state = ExitState("bull", 1, 1, 1, "LONG")
        episode = TradeEpisode(
            episode_id="ep_001",
            symbol="AAPL",
            direction="LONG",
            entry_time=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc),
            states=[state],
            actions=[ExitAction.EXIT],
            final_pnl=0.02,
            exit_reason=ExitReason.TARGET_HIT,
        )

        # Update from episode
        learner.update_from_episode(episode)

        # Check that state was visited
        assert learner.visit_counts[state.to_tuple()] > 0

    def test_batch_update(self, learner):
        """Should handle batch updates."""
        episodes = []
        for i in range(5):
            state = ExitState("bull", 1, 1, 1, "LONG")
            episode = TradeEpisode(
                episode_id=f"ep_{i:03d}",
                symbol="AAPL",
                direction="LONG",
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc),
                states=[state],
                actions=[ExitAction.EXIT],
                final_pnl=0.01 * (i + 1),
                exit_reason=ExitReason.TARGET_HIT,
            )
            episodes.append(episode)

        learner.batch_update(episodes)

        # Check visits accumulated
        state = ExitState("bull", 1, 1, 1, "LONG")
        assert learner.visit_counts[state.to_tuple()] == 5


class TestAnalytics:
    """Test analytics and reporting."""

    @pytest.fixture
    def learner(self, tmp_path):
        """Create a fresh learner with temp database."""
        db_path = tmp_path / "test_exit_values.db"
        return ExitValueLearner(db_path=db_path)

    def test_get_stats(self, learner):
        """Should return stats dictionary."""
        stats = learner.get_stats()

        assert "total_states" in stats
        assert "episodes_learned" in stats
        assert "learning_rate" in stats
        assert "discount_factor" in stats

    def test_get_value_surface(self, learner):
        """Should return value surface for regime."""
        surface = learner.get_value_surface("trending_bull", "LONG")
        assert isinstance(surface, list)

    def test_get_optimal_exits_by_regime(self, learner):
        """Should return optimal exits per regime."""
        optimal = learner.get_optimal_exits_by_regime()
        assert isinstance(optimal, dict)
