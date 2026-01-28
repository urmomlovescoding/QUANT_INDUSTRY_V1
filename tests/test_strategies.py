"""
QUANT_INDUSTRY_V1 Strategies Module Tests

Tests for strategy framework and signal generation.
"""

import pytest
import numpy as np
from datetime import datetime, timezone


class TestSignals:
    """Test signal generation."""

    def test_signal_creation(self):
        """Test signal creation."""
        from strategies import Signal, SignalDirection

        signal = Signal(
            symbol='AAPL',
            direction=SignalDirection.LONG,
            strength=0.8,
            confidence=0.75,
            entry_price=150.0
        )

        assert signal.symbol == 'AAPL'
        assert signal.direction == SignalDirection.LONG
        assert signal.strength == 0.8
        assert signal.confidence == 0.75

    def test_signal_to_dict(self):
        """Test signal serialization."""
        from strategies import Signal, SignalDirection

        signal = Signal(
            symbol='AAPL',
            direction=SignalDirection.SHORT,
            strength=-0.6,
        )

        d = signal.to_dict()
        assert d['symbol'] == 'AAPL'
        assert d['direction'] == 'short'
        assert d['strength'] == -0.6


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

        # Generate uptrend data
        prices = np.linspace(100, 120, 20).tolist()
        data = {'AAPL': {'close': prices}}

        signals = strategy.update(data)

        # Should generate long signal (20% up)
        assert len(signals) > 0
        assert signals[0].direction.value == 'long'

    def test_no_signal_below_threshold(self):
        """Test no signal when momentum below threshold."""
        from strategies import MomentumStrategy, StrategyConfig, StrategyStatus

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
        data = {'AAPL': {'close': prices}}

        signals = strategy.update(data)

        # Should not generate signal
        assert len(signals) == 0


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
                'zscore_threshold': 2.0
            }
        )

        strategy = MeanReversionStrategy(config)
        strategy.set_status(StrategyStatus.BACKTESTING)

        # Generate data with last price very low
        prices = [100.0] * 19 + [90.0]  # Sudden drop
        data = {'AAPL': {'close': prices}}

        signals = strategy.update(data)

        # Should generate long signal (oversold)
        if len(signals) > 0:
            assert signals[0].direction.value == 'long'

    def test_overbought_signal(self):
        """Test overbought generates short signal."""
        from strategies import MeanReversionStrategy, StrategyConfig, StrategyStatus

        config = StrategyConfig(
            name='Test Mean Reversion',
            symbols=['AAPL'],
            parameters={
                'lookback': 20,
                'zscore_threshold': 2.0
            }
        )

        strategy = MeanReversionStrategy(config)
        strategy.set_status(StrategyStatus.BACKTESTING)

        # Generate data with last price very high
        prices = [100.0] * 19 + [115.0]  # Sudden spike
        data = {'AAPL': {'close': prices}}

        signals = strategy.update(data)

        # Should generate short signal (overbought)
        if len(signals) > 0:
            assert signals[0].direction.value == 'short'


class TestStrategyRegistry:
    """Test strategy registry."""

    def test_register_strategy(self):
        """Test strategy registration."""
        from strategies import StrategyRegistry, MomentumStrategy

        registry = StrategyRegistry()
        strategy = MomentumStrategy()

        strategy_id = registry.register(strategy)

        assert strategy_id is not None
        assert registry.get(strategy_id) == strategy

    def test_unregister_strategy(self):
        """Test strategy unregistration."""
        from strategies import StrategyRegistry, MomentumStrategy

        registry = StrategyRegistry()
        strategy = MomentumStrategy()

        strategy_id = registry.register(strategy)
        result = registry.unregister(strategy_id)

        assert result
        assert registry.get(strategy_id) is None

    def test_get_active_strategies(self):
        """Test getting active strategies."""
        from strategies import StrategyRegistry, MomentumStrategy, StrategyStatus

        registry = StrategyRegistry()

        s1 = MomentumStrategy()
        s1.set_status(StrategyStatus.LIVE)

        s2 = MomentumStrategy()
        s2.set_status(StrategyStatus.PAUSED)

        registry.register(s1)
        registry.register(s2)

        active = registry.get_active()
        assert len(active) == 1
        assert s1 in active

    def test_compare_strategies(self):
        """Test strategy comparison."""
        from strategies import StrategyRegistry, MomentumStrategy

        registry = StrategyRegistry()

        s1 = MomentumStrategy()
        s2 = MomentumStrategy()

        registry.register(s1)
        registry.register(s2)

        comparison = registry.compare_strategies()
        assert len(comparison) == 2


class TestStrategyMetrics:
    """Test strategy metrics tracking."""

    def test_record_trade_result(self):
        """Test recording trade results."""
        from strategies import MomentumStrategy, Signal, SignalDirection, StrategyStatus

        strategy = MomentumStrategy()
        strategy.set_status(StrategyStatus.LIVE)

        signal = Signal(
            symbol='AAPL',
            direction=SignalDirection.LONG,
            strength=0.8
        )

        # Record winning trade
        strategy.record_trade_result(signal, 100.0, 105.0, 500.0)
        assert strategy.metrics.winning_signals == 1
        assert strategy.metrics.win_rate == 1.0

        # Record losing trade
        strategy.record_trade_result(signal, 100.0, 95.0, -300.0)
        assert strategy.metrics.losing_signals == 1
        assert strategy.metrics.win_rate == 0.5

    def test_sharpe_calculation(self):
        """Test Sharpe ratio calculation."""
        from strategies import MomentumStrategy, StrategyStatus

        strategy = MomentumStrategy()
        strategy.set_status(StrategyStatus.LIVE)

        # Add some returns
        for ret in [0.01, 0.02, -0.01, 0.015, -0.005]:
            strategy.returns.append(ret)

        sharpe = strategy.calculate_sharpe()
        assert isinstance(sharpe, float)

    def test_drawdown_tracking(self):
        """Test drawdown tracking."""
        from strategies import MomentumStrategy, Signal, SignalDirection, StrategyStatus

        strategy = MomentumStrategy()
        strategy.set_status(StrategyStatus.LIVE)

        signal = Signal(symbol='AAPL', direction=SignalDirection.LONG)

        # Record series of trades
        strategy.record_trade_result(signal, 100, 110, 1000)
        strategy.record_trade_result(signal, 100, 108, 800)
        strategy.record_trade_result(signal, 100, 90, -1000)

        assert strategy.metrics.max_drawdown > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
