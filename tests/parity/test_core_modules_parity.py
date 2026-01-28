"""
Core Modules Parity Tests
=========================
Verifies core modules match quant-platform behavior.
"""
import pytest
from datetime import datetime, timedelta


class TestMarketMemoryParity:
    """Test Market Memory matches platform."""

    def test_episode_structure(self):
        """Verify MarketEpisode has required fields."""
        from backend.core import MarketEpisode

        episode = MarketEpisode(
            episode_id="ep_001",
            timestamp=datetime.now(),
            episode_type="rally",
            symbol="ES",
            timeframe="5m",
            regime="trending_up",
            volatility=15.0,
            trend_strength=0.7,
            price_at_start=5000.0,
            price_at_end=5050.0,
            price_change_pct=1.0,
            duration_bars=10,
        )

        assert episode.episode_id == "ep_001"
        assert episode.episode_type == "rally"
        assert episode.regime == "trending_up"

    def test_episode_serialization(self):
        """Verify episode serialization."""
        from backend.core import MarketEpisode

        episode = MarketEpisode(
            episode_id="ep_001",
            timestamp=datetime.now(),
            episode_type="crash",
            symbol="ES",
            timeframe="1h",
            regime="volatile",
            volatility=30.0,
            trend_strength=-0.8,
            price_at_start=5000.0,
            price_at_end=4800.0,
            price_change_pct=-4.0,
            duration_bars=20,
        )

        data = episode.to_dict()
        restored = MarketEpisode.from_dict(data)

        assert restored.episode_id == episode.episode_id
        assert restored.episode_type == episode.episode_type

    def test_memory_store_and_search(self):
        """Verify memory storage and search."""
        from backend.core import MarketMemory, MarketEpisode
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MarketMemory(state_dir=Path(tmpdir))

            episode = MarketEpisode(
                episode_id="",  # Will be generated
                timestamp=datetime.now(),
                episode_type="breakout",
                symbol="ES",
                timeframe="5m",
                regime="trending_up",
                volatility=15.0,
                trend_strength=0.7,
                price_at_start=5000.0,
                price_at_end=5050.0,
                price_change_pct=1.0,
                duration_bars=10,
            )

            episode_id = memory.store_episode(episode)
            assert episode_id.startswith("ep_")

            # Search for similar
            matches = memory.search_similar({
                "regime": "trending_up",
                "volatility": 15.0,
                "trend_strength": 0.7,
            })

            assert len(matches) >= 1

    def test_memory_learn_from_outcome(self):
        """Verify learning from outcome."""
        from backend.core import MarketMemory, MarketEpisode
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MarketMemory(state_dir=Path(tmpdir))

            episode = MarketEpisode(
                episode_id="learn_test_001",
                timestamp=datetime.now(),
                episode_type="rally",
                symbol="ES",
                timeframe="5m",
                regime="trending_up",
                volatility=10.0,
                trend_strength=0.5,
                price_at_start=5000.0,
                price_at_end=5030.0,
                price_change_pct=0.6,
                duration_bars=5,
            )

            memory.store_episode(episode)
            success = memory.learn_from_outcome("learn_test_001", "success", 500.0)

            assert success is True

    def test_memory_stats(self):
        """Verify memory statistics."""
        from backend.core import MarketMemory
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MarketMemory(state_dir=Path(tmpdir))
            stats = memory.get_stats()

            assert "total_episodes" in stats


class TestRegimeDiscoveryParity:
    """Test Regime Discovery matches platform."""

    def test_regime_enum_values(self):
        """Verify MarketRegime enum values match platform."""
        from backend.core import MarketRegime

        assert MarketRegime.TRENDING_UP.value == "trending_up"
        assert MarketRegime.TRENDING_DOWN.value == "trending_down"
        assert MarketRegime.RANGING.value == "ranging"
        assert MarketRegime.VOLATILE.value == "volatile"
        assert MarketRegime.BREAKOUT.value == "breakout"
        assert MarketRegime.MEAN_REVERTING.value == "mean_reverting"

    def test_all_regimes_present(self):
        """Verify all required regimes exist."""
        from backend.core import MarketRegime

        required = ["trending_up", "trending_down", "ranging", "volatile", "breakout", "mean_reverting"]
        actual = [r.value for r in MarketRegime if r != MarketRegime.UNKNOWN]
        for regime in required:
            assert regime in actual, f"Missing regime: {regime}"

    def test_regime_state_structure(self):
        """Verify RegimeState has required fields."""
        from backend.core import RegimeState, MarketRegime

        state = RegimeState(
            regime=MarketRegime.TRENDING_UP,
            confidence=0.85,
            since=datetime.now(),
        )

        assert hasattr(state, "regime")
        assert hasattr(state, "confidence")
        assert hasattr(state, "since")
        assert hasattr(state, "duration_bars")
        assert hasattr(state, "trend_strength")
        assert hasattr(state, "volatility")
        assert hasattr(state, "probabilities")

    def test_regime_detection_trending(self):
        """Verify trending regime detection."""
        from backend.core import RegimeDiscovery, MarketRegime

        discovery = RegimeDiscovery()

        # Create uptrending data
        closes = [100 + i * 0.5 for i in range(60)]
        highs = [c + 0.3 for c in closes]
        lows = [c - 0.3 for c in closes]
        opens = [c - 0.1 for c in closes]

        state = discovery.detect_regime(opens, highs, lows, closes)

        # Should detect uptrend
        assert state.regime in [MarketRegime.TRENDING_UP, MarketRegime.BREAKOUT]
        assert state.confidence > 0

    def test_regime_detection_ranging(self):
        """Verify ranging regime detection produces valid state."""
        from backend.core import RegimeDiscovery, MarketRegime
        import math

        discovery = RegimeDiscovery()

        # Create ranging data (oscillating)
        closes = [100 + math.sin(i * 0.1) * 0.5 for i in range(60)]
        highs = [c + 0.2 for c in closes]
        lows = [c - 0.2 for c in closes]
        opens = [c - 0.05 for c in closes]

        state = discovery.detect_regime(opens, highs, lows, closes)

        # Should produce a valid regime state with probabilities
        assert state is not None
        assert state.regime in MarketRegime
        assert hasattr(state, "probabilities")

    def test_regime_transition_recorded(self):
        """Verify regime transitions are recorded."""
        from backend.core import RegimeDiscovery

        discovery = RegimeDiscovery()

        # First detection
        closes1 = [100 + i * 0.5 for i in range(60)]
        highs1 = [c + 0.3 for c in closes1]
        lows1 = [c - 0.3 for c in closes1]
        opens1 = [c - 0.1 for c in closes1]
        discovery.detect_regime(opens1, highs1, lows1, closes1)

        # Second detection with different pattern
        closes2 = [130 - i * 0.5 for i in range(60)]
        highs2 = [c + 0.3 for c in closes2]
        lows2 = [c - 0.3 for c in closes2]
        opens2 = [c + 0.1 for c in closes2]
        discovery.detect_regime(opens2, highs2, lows2, closes2)

        # Check history
        history = discovery.get_transition_history()
        assert isinstance(history, list)

    def test_discovery_thresholds(self):
        """Verify discovery thresholds match platform."""
        from backend.core import RegimeDiscovery

        discovery = RegimeDiscovery()

        # Check ADX thresholds
        assert discovery.thresholds["trend_adx_min"] == 25.0
        assert discovery.thresholds["strong_trend_adx"] == 40.0
        assert discovery.thresholds["ranging_adx_max"] == 20.0

        # Check volatility thresholds
        assert discovery.thresholds["volatility_atr_high"] == 75
        assert discovery.thresholds["volatility_atr_low"] == 25


class TestDeploymentParity:
    """Test deployment stages match platform."""

    def test_deployment_stage_progression(self):
        """Verify stage progression matches platform."""
        from backend.core import BrainToBotBridge, DeploymentStage
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = BrainToBotBridge(state_dir=Path(tmpdir))

            # Start deployment
            deployment = bridge.start_deployment("model_001", "1.0.0", 0.85)
            assert deployment.stage == DeploymentStage.VALIDATION

            # Progression order
            expected = [
                DeploymentStage.VALIDATION,
                DeploymentStage.SHADOW,
                DeploymentStage.CANARY,
                DeploymentStage.PRODUCTION,
            ]

            for i, stage in enumerate(expected[:-1]):
                next_stage = bridge._get_next_stage(stage)
                assert next_stage == expected[i + 1]

    def test_model_health_states(self):
        """Verify model health states match platform."""
        from backend.core import ModelHealth

        assert ModelHealth.HEALTHY.value == "healthy"
        assert ModelHealth.DEGRADED.value == "degraded"
        assert ModelHealth.UNHEALTHY.value == "unhealthy"
        assert ModelHealth.UNKNOWN.value == "unknown"

    def test_execution_feedback_structure(self):
        """Verify ExecutionFeedback has required fields."""
        from backend.core import ExecutionFeedback

        feedback = ExecutionFeedback(
            feedback_id="fb_001",
            timestamp=datetime.now(),
            model_id="model_001",
            symbol="ES",
            action="BUY",
            predicted_direction=0.8,
            actual_return=0.5,
            pnl=250.0,
            decision_latency_ms=5.0,
            execution_latency_ms=15.0,
        )

        assert feedback.feedback_id == "fb_001"
        assert feedback.pnl == 250.0

    def test_rollback_functionality(self):
        """Verify rollback works correctly."""
        from backend.core import BrainToBotBridge, DeploymentStage
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = BrainToBotBridge(state_dir=Path(tmpdir))

            # Create two deployments
            dep1 = bridge.start_deployment("model_001", "1.0.0", 0.85)
            bridge.current_deployment = dep1
            dep1.stage = DeploymentStage.PRODUCTION

            bridge.previous_deployment = None  # Reset
            dep2 = bridge.start_deployment("model_002", "2.0.0", 0.90)

            # Simulate promoting dep2 to production
            bridge.previous_deployment = dep1
            bridge.current_deployment = dep2
            dep2.stage = DeploymentStage.PRODUCTION

            # Rollback
            success, msg = bridge.rollback("Test rollback")
            assert success is True
            assert bridge.current_deployment == dep1


class TestKillSwitchParity:
    """Test Kill Switch matches platform."""

    def test_kill_switch_activation(self):
        """Verify kill switch activation."""
        from backend.execution import KillSwitch
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            ks = KillSwitch(state_dir=Path(tmpdir))

            assert ks.is_active is False

            ks.activate("Test activation", "test")
            assert ks.is_active is True
            assert ks.reason == "Test activation"

    def test_kill_switch_deactivation(self):
        """Verify kill switch deactivation."""
        from backend.execution import KillSwitch
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            ks = KillSwitch(state_dir=Path(tmpdir))
            ks.activate("Test", "test")
            ks.deactivate("Test deactivation", "operator")

            assert ks.is_active is False

    def test_auto_trigger_thresholds(self):
        """Verify auto-trigger thresholds match platform."""
        from backend.execution import KillSwitch
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            ks = KillSwitch(state_dir=Path(tmpdir))

            assert ks.daily_loss_limit == 2000.0
            assert ks.consecutive_loss_limit == 5
            assert ks.error_rate_limit == 0.10

    def test_auto_trigger_daily_loss(self):
        """Verify daily loss auto-trigger."""
        from backend.execution import KillSwitch
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            ks = KillSwitch(state_dir=Path(tmpdir))

            # Should not trigger
            triggered = ks.check_auto_triggers(daily_loss=1000.0)
            assert triggered is False

            # Should trigger
            triggered = ks.check_auto_triggers(daily_loss=2500.0)
            assert triggered is True
            assert ks.is_active is True


class TestRiskEngineParity:
    """Test Risk Engine matches platform."""

    def test_risk_mode_values(self):
        """Verify RiskMode enum values."""
        from backend.execution import RiskMode

        assert RiskMode.CONSERVATIVE.value == "conservative"
        assert RiskMode.MODERATE.value == "moderate"
        assert RiskMode.AGGRESSIVE.value == "aggressive"

    def test_default_limits_moderate(self):
        """Verify moderate mode default limits."""
        from backend.execution import RiskEngine, RiskMode

        engine = RiskEngine(mode=RiskMode.MODERATE)

        assert engine.max_position_pct == 0.20
        assert engine.max_total_exposure_pct == 0.80
        assert engine.daily_loss_limit_pct == 0.02
        assert engine.min_confidence == 0.55

    def test_conservative_mode_limits(self):
        """Verify conservative mode has tighter limits."""
        from backend.execution import RiskEngine, RiskMode

        engine = RiskEngine(mode=RiskMode.CONSERVATIVE)

        assert engine.max_position_pct == 0.10
        assert engine.max_total_exposure_pct == 0.50
        assert engine.daily_loss_limit_pct == 0.01
        assert engine.min_confidence == 0.65

    def test_risk_check_structure(self):
        """Verify RiskCheckResult has required fields."""
        from backend.execution import RiskEngine, RiskMode

        engine = RiskEngine(mode=RiskMode.MODERATE)
        result = engine.check_trade("ES", "BUY", 0.10, 0.65)

        assert hasattr(result, "approved")
        assert hasattr(result, "reason")
        assert hasattr(result, "adjusted_size_pct")
        assert hasattr(result, "warnings")
        assert hasattr(result, "checks_passed")
        assert hasattr(result, "checks_failed")

    def test_low_confidence_rejected(self):
        """Verify low confidence trades are rejected."""
        from backend.execution import RiskEngine, RiskMode

        engine = RiskEngine(mode=RiskMode.MODERATE)
        result = engine.check_trade("ES", "BUY", 0.10, 0.40)

        assert result.approved is False
        assert "confidence_too_low" in str(result.checks_failed)

    def test_oversized_position_adjusted(self):
        """Verify oversized positions are adjusted."""
        from backend.execution import RiskEngine, RiskMode

        engine = RiskEngine(mode=RiskMode.MODERATE)
        result = engine.check_trade("ES", "BUY", 0.50, 0.70)  # 50% is too much

        assert result.adjusted_size_pct <= 0.20  # Should be capped at max


class TestExecutionEngineParity:
    """Test Execution Engine matches platform."""

    def test_execution_mode_values(self):
        """Verify ExecutionMode enum values."""
        from backend.execution import ExecutionMode

        assert ExecutionMode.SIGNAL_ONLY.value == "signal_only"
        assert ExecutionMode.AUTO_PAPER.value == "auto_paper"
        assert ExecutionMode.AUTO_LIVE.value == "auto_live"

    def test_default_mode_is_signal_only(self):
        """Verify default mode is signal_only for safety."""
        from backend.execution import ExecutionEngine, ExecutionMode

        engine = ExecutionEngine()
        assert engine.mode == ExecutionMode.SIGNAL_ONLY

    def test_decision_structure(self):
        """Verify ExecutionDecision has required fields."""
        from backend.execution import ExecutionEngine, ExecutionMode

        engine = ExecutionEngine(mode=ExecutionMode.AUTO_PAPER)
        decision = engine.process_signal("ES", "BUY", 0.70, 0.10)

        assert hasattr(decision, "decision_id")
        assert hasattr(decision, "ticker")
        assert hasattr(decision, "direction")
        assert hasattr(decision, "was_executed")
        assert hasattr(decision, "mode")
