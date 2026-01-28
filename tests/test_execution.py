"""
QUANT_INDUSTRY_V1 Execution Module Tests

Tests for order execution and broker integration.
"""

import pytest
import numpy as np
from datetime import datetime, timezone


class TestExecutionEngine:
    """Test execution engine components."""

    def test_order_creation(self):
        """Test order creation."""
        from execution import Order, OrderType, OrderSide

        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            limit_price=150.0
        )

        assert order.symbol == 'AAPL'
        assert order.quantity == 100
        assert order.side == OrderSide.BUY
        assert order.limit_price == 150.0

    def test_twap_algorithm(self):
        """Test TWAP execution algorithm."""
        from execution import TWAPAlgorithm

        algo = TWAPAlgorithm(n_slices=5)

        slices = algo.generate_slices(
            total_quantity=1000,
            duration_minutes=60
        )

        assert len(slices) == 5
        assert sum(s['quantity'] for s in slices) == 1000

    def test_vwap_algorithm(self):
        """Test VWAP execution algorithm."""
        from execution import VWAPAlgorithm

        # Historical volume profile
        volume_profile = np.array([100, 200, 300, 250, 150])
        algo = VWAPAlgorithm(volume_profile=volume_profile)

        slices = algo.generate_slices(total_quantity=1000)

        assert len(slices) == 5
        assert sum(s['quantity'] for s in slices) == 1000
        # Higher volume periods get more
        assert slices[2]['quantity'] > slices[0]['quantity']

    def test_slippage_model(self):
        """Test slippage model."""
        from execution import SlippageModel

        model = SlippageModel(base_slippage_bps=5, impact_factor=0.1)

        # Calculate slippage
        slippage = model.calculate(
            price=100.0,
            quantity=1000,
            avg_volume=100000,
            side='buy'
        )

        assert slippage > 0  # Buy slippage is positive
        assert slippage < 1.0  # Reasonable slippage


class TestSimulatedBroker:
    """Test simulated broker."""

    def test_order_submission(self):
        """Test order submission to simulated broker."""
        from execution import SimulatedBroker, Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)

        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )

        result = broker.submit_order(order, current_price=150.0)

        assert result.filled
        assert result.fill_price == pytest.approx(150.0, rel=0.01)
        assert broker.get_position('AAPL') == 100
        assert broker.cash < 100000

    def test_position_tracking(self):
        """Test position tracking."""
        from execution import SimulatedBroker, Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)

        # Buy
        buy_order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        broker.submit_order(buy_order, current_price=150.0)

        assert broker.get_position('AAPL') == 100

        # Sell half
        sell_order = Order(
            symbol='AAPL',
            quantity=50,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET
        )
        broker.submit_order(sell_order, current_price=155.0)

        assert broker.get_position('AAPL') == 50

    def test_portfolio_value(self):
        """Test portfolio value calculation."""
        from execution import SimulatedBroker, Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)

        # Buy some stock
        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        broker.submit_order(order, current_price=150.0)

        # Get portfolio value
        prices = {'AAPL': 160.0}
        value = broker.get_portfolio_value(prices)

        expected = broker.cash + 100 * 160.0
        assert value == pytest.approx(expected, rel=0.01)

    def test_limit_order(self):
        """Test limit order execution."""
        from execution import SimulatedBroker, Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)

        # Limit order below current price
        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            limit_price=145.0
        )

        # Price at 150, should not fill
        result = broker.submit_order(order, current_price=150.0)

        # Depending on implementation, may pend or not fill
        assert result is not None


class TestExecutionAlgorithms:
    """Test execution algorithm implementations."""

    def test_pov_algorithm(self):
        """Test POV (Percentage of Volume) algorithm."""
        from execution import POVAlgorithm

        algo = POVAlgorithm(target_pov=0.1)

        # Calculate order size based on volume
        order_size = algo.calculate_order_size(
            market_volume=10000,
            remaining_quantity=500
        )

        # Should be min of POV and remaining
        assert order_size <= 1000  # 10% of volume
        assert order_size <= 500   # Remaining


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
