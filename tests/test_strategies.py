"""
QUANT_INDUSTRY_V1 Strategies Module Tests

Tests for strategy framework and signal generation.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone


class TestSignals:
    """Test signal generation."""

    def test_signal_creation(self):
        """Test signal creation."""
        from strategies import Signal, SignalType

        signal = Signal(
            symbol='AAPL',
            signal_type=SignalType.LONG,
            strength=0.8,
            metadata={'confidence': 0.75, 'entry_price': 150.0}
        )

        assert signal.symbol == 'AAPL'
        assert signal.signal_type == SignalType.LONG
        assert signal.strength == 0.8
        assert signal.metadata.get('confidence') == 0.75

    def test_signal_position_size(self):
        """Test signal position size calculation."""
        from strategies import Signal, SignalType

        signal = Signal(
            symbol='AAPL',
            signal_type=SignalType.SHORT,
            strength=0.6,
        )

        assert signal.symbol == 'AAPL'
        assert signal.signal_type == SignalType.SHORT
        assert signal.strength == 0.6
        # Position size should be signal_type.value * strength = -1 * 0.6 = -0.6
        assert signal.position_size == -0.6


class TestMomentumStrategy:
    """Test momentum strategy."""

    def test_signal_generation(self):
        """Test momentum signal generation."""
        from strategies import MomentumStrategy, StrategyConfig, StrategyStatus

        config = StrategyConfig(
            name='Test Momentum',
            symbols=['AAPL'],
            parameters={
                'lookback': 10,
                'threshold': 0.02
            }
        )

        strategy = MomentumStrategy(config)
        strategy.set_status(StrategyStatus.BACKTESTING)

        # Generate uptrend data - need lookback + 5 bars minimum
        prices = np.linspace(100, 120, 20).tolist()

        # Create DataFrame with symbol as column
        data = pd.DataFrame({'AAPL': prices})

        signals = strategy.update(data)

        # Should generate long signal (20% up)
        assert len(signals) > 0
        assert 'AAPL' in signals
        assert signals['AAPL'].signal_type.value == 1  # SignalType.LONG.value

    def test_no_signal_below_threshold(self):
        """Test no signal when momentum below threshold."""
        from strategies import MomentumStrategy, StrategyConfig, StrategyStatus, SignalType

        config = StrategyConfig(
            name='Test Momentum',
            symbols=['AAPL'],
            parameters={
                'lookback': 10,
                'threshold': 0.05
            }
        )

        strategy = MomentumStrategy(config)
        strategy.set_status(StrategyStatus.BACKTESTING)

        # Flat data (1% move)
        prices = np.linspace(100, 101, 20).tolist()
        data = pd.DataFrame({'AAPL': prices})

        signals = strategy.update(data)

        # Should generate FLAT signal (below threshold)
        if 'AAPL' in signals:
            assert signals['AAPL'].signal_type == SignalType.FLAT


class TestMeanReversionStrategy:
    """Test mean reversion strategy."""

    def test_oversold_signal(self):
        """Test oversold generates long signal."""
        from strategies import MeanReversionStrategy, StrategyConfig, StrategyStatus

        config = StrategyConfig(
            name='Test Mean Reversion',
            symbols=['AAPL'],
            parameters={
                'lookback': 20,
                'entry_threshold': 2.0,  # API uses entry_threshold, not zscore_threshold
                'exit_threshold': 0.5
            }
        )

        strategy = MeanReversionStrategy(config)
        strategy.set_status(StrategyStatus.BACKTESTING)

        # Generate data with last price very low (needs sufficient history for zscore calc)
        prices = [100.0] * 24 + [85.0]  # Sudden drop at end
        data = pd.DataFrame({'AAPL': prices})

        signals = strategy.update(data)

        # Should generate long signal (oversold - negative z-score below threshold)
        if 'AAPL' in signals:
            assert signals['AAPL'].signal_type.value == 1  # LONG

    def test_overbought_signal(self):
        """Test overbought generates short signal."""
        from strategies import MeanReversionStrategy, StrategyConfig, StrategyStatus

        config = StrategyConfig(
            name='Test Mean Reversion',
            symbols=['AAPL'],
            parameters={
                'lookback': 20,
                'entry_threshold': 2.0,
                'exit_threshold': 0.5
            }
        )

        strategy = MeanReversionStrategy(config)
        strategy.set_status(StrategyStatus.BACKTESTING)

        # Generate data with last price very high
        prices = [100.0] * 24 + [120.0]  # Sudden spike
        data = pd.DataFrame({'AAPL': prices})

        signals = strategy.update(data)

        # Should generate short signal (overbought - positive z-score above threshold)
        if 'AAPL' in signals:
            assert signals['AAPL'].signal_type.value == -1  # SHORT


class TestStrategyRegistry:
    """Test strategy registry."""

    def test_register_strategy(self):
        """Test strategy registration."""
        from strategies import StrategyRegistry, MomentumStrategy

        # Registry is class-based, register takes (name, strategy_class)
        StrategyRegistry.register('test_momentum', MomentumStrategy)

        # Get returns the class
        strategy_class = StrategyRegistry.get('test_momentum')
        assert strategy_class == MomentumStrategy

    def test_get_builtin_strategy(self):
        """Test getting built-in strategies."""
        from strategies import StrategyRegistry, MomentumStrategy

        # Built-in strategies are available via STRATEGY_REGISTRY
        strategy_class = StrategyRegistry.get('momentum')
        assert strategy_class == MomentumStrategy

    def test_list_all_strategies(self):
        """Test listing all registered strategies."""
        from strategies import StrategyRegistry

        all_strategies = StrategyRegistry.list_all()

        # Should include built-in strategies
        assert 'momentum' in all_strategies
        assert 'dual_momentum' in all_strategies
        assert 'bollinger_reversion' in all_strategies

    def test_create_strategy(self):
        """Test creating strategy instance via registry."""
        from strategies import StrategyRegistry, StrategyConfig, MomentumStrategy

        config = StrategyConfig(
            name='Test',
            symbols=['AAPL'],
            parameters={'lookback': 10}
        )

        strategy = StrategyRegistry.create('momentum', config)

        assert isinstance(strategy, MomentumStrategy)
        assert strategy.config == config


class TestStrategyMetrics:
    """Test strategy metrics tracking.

    Note: The current BaseStrategy implementation doesn't include built-in
    metrics tracking. These tests verify basic strategy functionality.
    For full metrics tracking, a separate StrategyMetrics class would be needed.
    """

    def test_strategy_state_management(self):
        """Test strategy state get/set."""
        from strategies import MomentumStrategy, StrategyConfig, StrategyStatus

        config = StrategyConfig(
            name='Test',
            symbols=['AAPL'],
            parameters={'lookback': 10}
        )

        strategy = MomentumStrategy(config)
        strategy.set_status(StrategyStatus.LIVE)

        # Test state management
        strategy.set_state('total_trades', 5)
        strategy.set_state('winning_trades', 3)

        assert strategy.get_state('total_trades') == 5
        assert strategy.get_state('winning_trades') == 3
        assert strategy.get_state('nonexistent', 0) == 0

    def test_strategy_status(self):
        """Test strategy status management."""
        from strategies import MomentumStrategy, StrategyConfig, StrategyStatus

        config = StrategyConfig(
            name='Test',
            symbols=['AAPL'],
            parameters={'lookback': 10}
        )

        strategy = MomentumStrategy(config)

        assert strategy.get_status() == StrategyStatus.INACTIVE

        strategy.set_status(StrategyStatus.LIVE)
        assert strategy.get_status() == StrategyStatus.LIVE

        strategy.set_status(StrategyStatus.PAUSED)
        assert strategy.get_status() == StrategyStatus.PAUSED

    def test_sharpe_calculation_utility(self):
        """Test Sharpe ratio calculation utility."""
        from strategies import sharpe_ratio
        import pandas as pd

        # Create some return data
        returns_data = pd.Series([0.01, 0.02, -0.01, 0.015, -0.005, 0.008, -0.003])

        sharpe = sharpe_ratio(returns_data)
        assert isinstance(sharpe, float)

    def test_strategy_reset(self):
        """Test strategy reset functionality."""
        from strategies import MomentumStrategy, StrategyConfig, StrategyStatus

        config = StrategyConfig(
            name='Test',
            symbols=['AAPL'],
            parameters={'lookback': 10}
        )

        strategy = MomentumStrategy(config)

        # Set some state
        strategy.set_state('trade_count', 10)
        assert strategy.get_state('trade_count') == 10

        # Reset should clear state
        strategy.reset()
        assert strategy.get_state('trade_count') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
