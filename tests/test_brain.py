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
        from brain.regime import VolatilityRegimeDetector, MarketRegime

        detector = VolatilityRegimeDetector()

        # Generate test data
        np.random.seed(42)
        low_vol = np.random.randn(50) * 0.01
        high_vol = np.random.randn(50) * 0.05
        returns = np.concatenate([low_vol, high_vol])

        # Compute volatility from returns
        volatility = np.abs(returns)  # Simple proxy for volatility
        volume = np.ones_like(returns)  # Dummy volume

        # Fit the detector first
        detector.fit(returns, volatility, volume)

        # Detect regime
        regime_state = detector.detect(returns, volatility, volume)

        # Check result - regime_state.regime is a MarketRegime enum
        valid_regimes = [MarketRegime.LOW_VOLATILITY, MarketRegime.HIGH_VOLATILITY,
                        MarketRegime.CONSOLIDATION, MarketRegime.UNKNOWN]
        assert regime_state.regime in valid_regimes

    def test_trend_regime_detector(self):
        """Test trend-based regime detection."""
        from brain.regime import TrendRegimeDetector, MarketRegime

        detector = TrendRegimeDetector()

        # Generate trending data
        np.random.seed(42)
        returns = np.ones(100) * 0.01 + np.random.randn(100) * 0.001  # Uptrend with noise
        volatility = np.abs(returns)
        volume = np.ones_like(returns)

        # Fit detector
        detector.fit(returns, volatility, volume)

        # Detect regime
        regime_state = detector.detect(returns, volatility, volume)

        # Check result is a valid MarketRegime
        assert isinstance(regime_state.regime, MarketRegime)

    def test_ensemble_regime_detector(self):
        """Test ensemble regime detection."""
        from brain.regime import EnsembleRegimeDetector, MarketRegime

        detector = EnsembleRegimeDetector()

        np.random.seed(42)
        returns = np.random.randn(100) * 0.02
        volatility = np.abs(returns)
        volume = np.abs(np.random.randn(100))

        # Fit all detectors
        detector.fit(returns, volatility, volume)

        # Detect returns a RegimeState object
        regime_state = detector.detect(returns, volatility, volume)

        assert isinstance(regime_state.regime, MarketRegime)
        assert 0 <= regime_state.confidence <= 1
        assert isinstance(regime_state.metrics, dict)


class TestSafety:
    """Test safety components."""

    def test_drift_detector(self):
        """Test drift detection."""
        from brain.safety import DriftDetector

        np.random.seed(42)
        # Create reference data with 5 features
        reference_data = np.random.randn(100, 5)

        # Initialize detector with reference data
        detector = DriftDetector(reference_data=reference_data)

        # Update with new observations
        for _ in range(50):
            features = np.random.randn(5)  # Similar distribution
            detector.update(features=features)

        # Check for data drift
        result = detector.detect_data_drift()
        assert hasattr(result, 'is_drift_detected')
        assert hasattr(result, 'drift_score')

    def test_circuit_breaker(self):
        """Test circuit breaker."""
        from brain.safety import CircuitBreaker, CircuitBreakerConfig, CircuitState

        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=1)
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Initially should be closed (can execute)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute()

        # Trigger failures
        for _ in range(3):
            breaker.record_failure()

        # After threshold failures, should be open
        assert breaker.state == CircuitState.OPEN
        assert not breaker.can_execute()

    def test_anomaly_detector(self):
        """Test anomaly detection."""
        from brain.safety import AnomalyDetector

        n_features = 5
        detector = AnomalyDetector(n_features=n_features)

        np.random.seed(42)
        # Feed normal data to build statistics
        for _ in range(50):
            normal_point = np.random.randn(n_features)
            detector.check(normal_point)

        # Test with a normal point
        normal_point = np.random.randn(n_features)
        is_anomaly, details = detector.check(normal_point)

        assert isinstance(is_anomaly, bool)
        assert 'anomaly_rate' in details
        assert 'z_scores' in details


class TestStatistics:
    """Test statistical components."""

    def test_monte_carlo_simulator(self):
        """Test Monte Carlo simulation."""
        from brain.statistics import MonteCarloSimulator

        simulator = MonteCarloSimulator(seed=42)

        # GBM simulation using geometric_brownian_motion method
        # dt = T / n_steps, so for T=1 year with 252 steps, dt = 1/252
        paths = simulator.geometric_brownian_motion(
            s0=100,
            mu=0.05,
            sigma=0.2,
            dt=1.0 / 252,
            n_steps=252,
            n_paths=100
        )

        assert paths.shape == (100, 253)  # n_paths x (n_steps + 1)
        assert paths[:, 0].mean() == pytest.approx(100, abs=0.01)

    def test_bayesian_estimator(self):
        """Test Bayesian estimation."""
        from brain.statistics import BayesianEstimator

        estimator = BayesianEstimator()

        np.random.seed(42)
        # Update with observations - update() returns BayesianPosterior
        observations = np.random.randn(100) * 0.02 + 0.001
        posterior = None
        for obs in observations:
            posterior = estimator.update(obs)

        # BayesianPosterior has mean, std, ci_lower, ci_upper
        assert hasattr(posterior, 'mean')
        assert hasattr(posterior, 'std')
        assert hasattr(posterior, 'ci_lower')
        assert hasattr(posterior, 'ci_upper')


class TestExplainability:
    """Test explainability components."""

    def test_feature_importance(self):
        """Test feature importance calculation."""
        from brain.explainability import FeatureImportanceAnalyzer

        feature_names = ['f0', 'f1', 'f2', 'f3', 'f4']
        analyzer = FeatureImportanceAnalyzer(feature_names=feature_names)

        # Generate test data
        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = X[:, 0] * 2 + X[:, 1] * 0.5 + np.random.randn(100) * 0.1

        # Create a simple model class with predict method
        class SimpleModel:
            def predict(self, x):
                return x[:, 0] * 2 + x[:, 1] * 0.5

        model = SimpleModel()

        # Use MSE as metric (lower is better, so we negate for importance)
        def mse_metric(y_true, y_pred):
            return -np.mean((y_true - y_pred) ** 2)

        importance = analyzer.permutation_importance(
            model=model,
            X=X,
            y=y,
            metric=mse_metric
        )

        assert len(importance) == 5
        # importance is a dict with feature names as keys
        assert importance['f0'] > importance['f2']  # First feature more important


class TestTraining:
    """Test training pipeline components."""

    def test_time_series_splitter(self):
        """Test time series cross-validation splitter."""
        from brain.training import TimeSeriesSplitter, TrainingConfig

        # Configure with custom settings
        config = TrainingConfig(
            n_folds=3,
            min_train_samples=20,
            walk_forward_step=20,
            purge_window=2,
            embargo_window=2
        )
        splitter = TimeSeriesSplitter(config)

        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = np.random.randint(0, 2, 100)

        # Use time_series_cv_splits which returns list of ((X_train, y_train), (X_test, y_test))
        splits = splitter.time_series_cv_splits(X, y)

        assert len(splits) >= 1  # Should have at least one split
        for (X_train, y_train), (X_test, y_test) in splits:
            assert len(X_train) > 0
            assert len(X_test) > 0
            # Train should come before test (temporal ordering)

    def test_metrics_calculator(self):
        """Test metrics calculation."""
        from brain.training import MetricsCalculator

        calculator = MetricsCalculator()

        y_true = np.array([1, 0, 1, 1, 0])
        y_pred = np.array([1, 0, 0, 1, 0])

        # Returns TrainingMetrics object, not dict
        metrics = calculator.calculate_classification_metrics(y_true, y_pred)
        assert hasattr(metrics, 'accuracy')
        assert hasattr(metrics, 'precision')
        assert hasattr(metrics, 'recall')
        assert metrics.accuracy == 0.8


class TestPhysics:
    """Test physics-inspired models."""

    def test_ising_market(self):
        """Test Ising market model."""
        from brain.physics import IsingMarket

        np.random.seed(42)
        # IsingMarket initializes automatically in __init__
        market = IsingMarket(n_agents=50)

        # Run simulation using step() method
        for _ in range(10):
            market.step()

        # Method is magnetization(), not get_magnetization()
        magnetization = market.magnetization()
        assert -1 <= magnetization <= 1

    def test_ou_process(self):
        """Test Ornstein-Uhlenbeck process."""
        from brain.physics import OrnsteinUhlenbeckProcess

        np.random.seed(42)
        # x0 is a constructor parameter
        ou = OrnsteinUhlenbeckProcess(theta=0.1, mu=100, sigma=2, x0=105)

        # simulate takes n_steps and optional dt
        path = ou.simulate(n_steps=100)
        assert len(path) == 101

        # Should mean-revert (loose check due to randomness)
        # The path should generally move toward mu=100 from x0=105
        assert abs(path[-1] - 100) < abs(105 - 100) * 3  # Very loose check


class TestRL:
    """Test reinforcement learning components."""

    def test_trading_environment(self):
        """Test trading environment."""
        from brain.rl_env import TradingEnvironment, EnvConfig

        np.random.seed(42)
        # prices should be a numpy array, not a dict
        prices = np.random.randn(100).cumsum() + 100

        # Use EnvConfig for initial capital
        config = EnvConfig(initial_capital=10000.0)

        env = TradingEnvironment(prices=prices, config=config)
        obs, info = env.reset()

        assert obs is not None
        # Cash is accessed via env.state.cash
        assert env.state.cash == 10000.0

        # Take action - for continuous action type, action should be array
        action = np.array([0.5])  # 50% position
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(reward, (int, float))

    def test_ppo_agent(self):
        """Test PPO agent."""
        from brain.rl_agent import PPOAgent, PPOConfig

        # Use PPOConfig for hidden_dims
        config = PPOConfig(hidden_dims=[32, 32])

        # PPOAgent uses obs_dim and action_dim, not state_dim
        # For discrete actions, set continuous=False
        agent = PPOAgent(
            obs_dim=10,
            action_dim=3,
            config=config,
            continuous=False  # Discrete action space
        )

        np.random.seed(42)
        state = np.random.randn(10).astype(np.float32)
        # Method is get_action(), returns (action, log_prob, value)
        action, log_prob, value = agent.get_action(state)

        assert 0 <= action[0] < 3
        assert isinstance(log_prob, float)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
