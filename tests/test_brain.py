"""
QUANT_INDUSTRY_V1 Brain Module Tests

Tests for AI/ML, regime detection, and safety components.
"""

import pytest
import numpy as np
from datetime import datetime, timezone


class TestRegimeDetection:
    """Test regime detection components."""

    def test_volatility_regime_detector(self):
        """Test volatility-based regime detection."""
        from brain.regime import VolatilityRegimeDetector

        detector = VolatilityRegimeDetector()

        # Generate test data
        np.random.seed(42)
        low_vol = np.random.randn(50) * 0.01
        high_vol = np.random.randn(50) * 0.05
        data = {'returns': np.concatenate([low_vol, high_vol])}

        regime = detector.detect(data)
        assert regime in ['low_volatility', 'medium_volatility', 'high_volatility']

    def test_trend_regime_detector(self):
        """Test trend-based regime detection."""
        from brain.regime import TrendRegimeDetector

        detector = TrendRegimeDetector()

        # Generate trending data
        prices = np.cumsum(np.ones(100) * 0.01) + 100
        data = {'close': prices}

        regime = detector.detect(data)
        assert regime in ['strong_uptrend', 'weak_uptrend', 'sideways', 'weak_downtrend', 'strong_downtrend']

    def test_ensemble_regime_detector(self):
        """Test ensemble regime detection."""
        from brain.regime import EnsembleRegimeDetector

        detector = EnsembleRegimeDetector()

        data = {
            'close': np.random.randn(100).cumsum() + 100,
            'returns': np.random.randn(100) * 0.02,
        }

        regime, confidence, details = detector.detect(data)
        assert isinstance(regime, str)
        assert 0 <= confidence <= 1
        assert isinstance(details, dict)


class TestSafety:
    """Test safety components."""

    def test_drift_detector(self):
        """Test drift detection."""
        from brain.safety import DriftDetector

        detector = DriftDetector()

        # Set baseline
        baseline = np.random.randn(100)
        detector.set_baseline(baseline)

        # Test with similar data
        similar = np.random.randn(50)
        result = detector.check_drift(similar)
        assert 'is_drifted' in result
        assert 'drift_score' in result

    def test_circuit_breaker(self):
        """Test circuit breaker."""
        from brain.safety import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

        assert breaker.is_closed()

        # Trigger failures
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open()

    def test_anomaly_detector(self):
        """Test anomaly detection."""
        from brain.safety import AnomalyDetector

        detector = AnomalyDetector()

        # Fit on normal data
        normal_data = np.random.randn(100, 5)
        detector.fit(normal_data)

        # Test normal point
        normal_point = np.random.randn(5)
        result = detector.predict(normal_point)
        assert 'is_anomaly' in result
        assert 'anomaly_score' in result


class TestStatistics:
    """Test statistical components."""

    def test_monte_carlo_simulator(self):
        """Test Monte Carlo simulation."""
        from brain.statistics import MonteCarloSimulator

        simulator = MonteCarloSimulator()

        # GBM simulation
        paths = simulator.gbm(
            s0=100,
            mu=0.05,
            sigma=0.2,
            T=1.0,
            n_steps=252,
            n_paths=100
        )

        assert paths.shape == (100, 253)  # n_paths x (n_steps + 1)
        assert paths[:, 0].mean() == pytest.approx(100, abs=0.01)

    def test_bayesian_estimator(self):
        """Test Bayesian estimation."""
        from brain.statistics import BayesianEstimator

        estimator = BayesianEstimator()

        # Update with observations
        observations = np.random.randn(100) * 0.02 + 0.001
        for obs in observations:
            estimator.update(obs)

        stats = estimator.get_stats()
        assert 'mean' in stats
        assert 'std' in stats
        assert 'credible_interval' in stats


class TestExplainability:
    """Test explainability components."""

    def test_feature_importance(self):
        """Test feature importance calculation."""
        from brain.explainability import FeatureImportanceCalculator

        calculator = FeatureImportanceCalculator()

        # Generate test data
        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = X[:, 0] * 2 + X[:, 1] * 0.5 + np.random.randn(100) * 0.1

        importance = calculator.permutation_importance(
            model=lambda x: x[:, 0] * 2 + x[:, 1] * 0.5,
            X=X,
            y=y
        )

        assert len(importance) == 5
        assert importance[0] > importance[2]  # First feature more important


class TestTraining:
    """Test training pipeline components."""

    def test_time_series_splitter(self):
        """Test time series cross-validation splitter."""
        from brain.training import TimeSeriesSplitter

        splitter = TimeSeriesSplitter(n_splits=3, test_size=20)

        data = np.random.randn(100, 5)
        splits = list(splitter.split(data))

        assert len(splits) == 3
        for train_idx, test_idx in splits:
            assert len(test_idx) == 20
            assert train_idx[-1] < test_idx[0]  # No leakage

    def test_metrics_calculator(self):
        """Test metrics calculation."""
        from brain.training import MetricsCalculator

        calculator = MetricsCalculator()

        y_true = np.array([1, 0, 1, 1, 0])
        y_pred = np.array([1, 0, 0, 1, 0])

        metrics = calculator.classification_metrics(y_true, y_pred)
        assert 'accuracy' in metrics
        assert 'precision' in metrics
        assert 'recall' in metrics
        assert metrics['accuracy'] == 0.8


class TestPhysics:
    """Test physics-inspired models."""

    def test_ising_market(self):
        """Test Ising market model."""
        from brain.physics import IsingMarket

        market = IsingMarket(n_agents=50)
        market.initialize()

        # Run simulation
        for _ in range(10):
            market.step()

        magnetization = market.get_magnetization()
        assert -1 <= magnetization <= 1

    def test_ou_process(self):
        """Test Ornstein-Uhlenbeck process."""
        from brain.physics import OrnsteinUhlenbeckProcess

        ou = OrnsteinUhlenbeckProcess(theta=0.1, mu=100, sigma=2)

        path = ou.simulate(x0=105, n_steps=100)
        assert len(path) == 101

        # Should mean-revert
        assert abs(path[-1] - 100) < abs(105 - 100) * 2  # Loose check


class TestRL:
    """Test reinforcement learning components."""

    def test_trading_environment(self):
        """Test trading environment."""
        from brain.rl_env import TradingEnvironment

        data = {
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.abs(np.random.randn(100)) * 1000000,
        }

        env = TradingEnvironment(data, initial_cash=10000)
        obs, info = env.reset()

        assert obs is not None
        assert env.cash == 10000

        # Take action
        obs, reward, done, truncated, info = env.step(1)  # Buy
        assert isinstance(reward, (int, float))

    def test_ppo_agent(self):
        """Test PPO agent."""
        from brain.rl_agent import PPOAgent

        agent = PPOAgent(
            state_dim=10,
            action_dim=3,
            hidden_dims=[32, 32]
        )

        state = np.random.randn(10)
        action, log_prob = agent.select_action(state)

        assert 0 <= action < 3
        assert isinstance(log_prob, float)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
