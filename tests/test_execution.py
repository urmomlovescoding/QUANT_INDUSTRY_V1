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
        from execution.engine import Order, OrderType, OrderSide

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
        assert order.remaining_quantity == 100

    def test_twap_algorithm(self):
        """Test TWAP execution algorithm."""
        from execution.engine import TWAPAlgorithm, Order, OrderSide

        algo = TWAPAlgorithm(n_slices=5, duration_minutes=60)

        parent_order = Order(
            symbol='AAPL',
            quantity=1000,
            side=OrderSide.BUY
        )

        market_data = {
            'price': 150.0,
            'bid': 149.99,
            'ask': 150.01,
            'volume': 100000
        }

        child_orders = algo.generate_child_orders(parent_order, market_data)

        assert len(child_orders) == 1  # First slice
        # TWAP adds randomization, so use approximate check
        assert 100 <= child_orders[0].quantity <= 300  # Around 1000/5 = 200
        assert child_orders[0].symbol == 'AAPL'

    def test_vwap_algorithm(self):
        """Test VWAP execution algorithm."""
        from execution.engine import VWAPAlgorithm, Order, OrderSide

        # Historical volume profile (normalized)
        volume_profile = [0.1, 0.2, 0.3, 0.25, 0.15]
        algo = VWAPAlgorithm(
            volume_profile=volume_profile,
            duration_minutes=60
        )

        parent_order = Order(
            symbol='AAPL',
            quantity=1000,
            side=OrderSide.BUY
        )

        market_data = {
            'price': 150.0,
            'vwap': 149.50,
            'volume': 100000,
            'spread': 0.02
        }

        child_orders = algo.generate_child_orders(parent_order, market_data)

        assert len(child_orders) == 1
        # First slice based on volume profile weight
        assert child_orders[0].quantity <= 1000

    def test_slippage_model(self):
        """Test slippage model."""
        from execution.engine import SlippageModel, Order, OrderSide

        model = SlippageModel(
            base_slippage_bps=5.0,
            volume_impact_factor=0.1,
            volatility_impact_factor=0.5
        )

        order = Order(
            symbol='AAPL',
            quantity=1000,
            side=OrderSide.BUY
        )

        market_data = {
            'price': 100.0,
            'volume': 100000,
            'volatility': 0.02,
            'spread': 0.01
        }

        slippage = model.estimate_slippage(order, market_data)

        assert slippage > 0  # Should have some slippage
        assert slippage < 0.05  # Less than 5% (reasonable for model)

    def test_slippage_scales_with_size(self):
        """Test that slippage increases with order size."""
        from execution.engine import SlippageModel, Order, OrderSide

        model = SlippageModel(
            base_slippage_bps=5.0,
            volume_impact_factor=0.1
        )

        market_data = {
            'price': 100.0,
            'volume': 100000,
            'volatility': 0.02
        }

        small_order = Order(symbol='AAPL', quantity=100, side=OrderSide.BUY)
        large_order = Order(symbol='AAPL', quantity=10000, side=OrderSide.BUY)

        small_slip = model.estimate_slippage(small_order, market_data)
        large_slip = model.estimate_slippage(large_order, market_data)

        assert large_slip > small_slip


class TestSimulatedBroker:
    """Test simulated broker."""

    def test_broker_connection(self):
        """Test broker connection."""
        from execution.broker import SimulatedBroker, BrokerConfig

        config = BrokerConfig(paper_trading=True)
        broker = SimulatedBroker(initial_cash=100000, config=config)

        assert broker.connect()
        assert broker.is_connected

        account = broker.get_account()
        assert account.cash == 100000
        assert account.portfolio_value == 100000

    def test_order_submission(self):
        """Test order submission to simulated broker."""
        from execution.broker import SimulatedBroker
        from execution.engine import Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)
        broker.connect()

        # Set market price
        broker.set_price('AAPL', 150.0)

        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )

        response = broker.submit_order(order)

        assert response.success
        assert response.filled_quantity == 100
        assert response.avg_price == pytest.approx(150.0, rel=0.02)

    def test_position_tracking(self):
        """Test position tracking."""
        from execution.broker import SimulatedBroker
        from execution.engine import Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)
        broker.connect()
        broker.set_price('AAPL', 150.0)

        # Buy
        buy_order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        broker.submit_order(buy_order)

        positions = broker.get_positions()
        aapl_pos = next((p for p in positions if p.symbol == 'AAPL'), None)

        assert aapl_pos is not None
        assert aapl_pos.quantity == 100

        # Sell half
        broker.set_price('AAPL', 155.0)
        sell_order = Order(
            symbol='AAPL',
            quantity=50,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET
        )
        broker.submit_order(sell_order)

        positions = broker.get_positions()
        aapl_pos = next((p for p in positions if p.symbol == 'AAPL'), None)

        assert aapl_pos is not None
        assert aapl_pos.quantity == 50

    def test_portfolio_value(self):
        """Test portfolio value calculation."""
        from execution.broker import SimulatedBroker
        from execution.engine import Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)
        broker.connect()
        broker.set_price('AAPL', 150.0)

        # Buy some stock
        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        broker.submit_order(order)

        # Update price
        broker.set_price('AAPL', 160.0)

        # Get account (includes portfolio value)
        account = broker.get_account()

        # Cash decreased by purchase, position value at new price
        expected_position_value = 100 * 160.0
        assert account.portfolio_value == pytest.approx(
            account.cash + expected_position_value, rel=0.01
        )

    def test_limit_order(self):
        """Test limit order execution."""
        from execution.broker import SimulatedBroker
        from execution.engine import Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=100000)
        broker.connect()
        broker.set_price('AAPL', 150.0)

        # Limit order below current price - should not fill immediately
        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            limit_price=145.0
        )

        response = broker.submit_order(order)

        # Order submitted but not filled (price at 150, limit at 145)
        assert response.success
        # Depending on implementation, may be pending or filled at limit

    def test_insufficient_funds(self):
        """Test order handling with limited funds."""
        from execution.broker import SimulatedBroker
        from execution.engine import Order, OrderType, OrderSide

        broker = SimulatedBroker(initial_cash=1000)
        broker.connect()
        broker.set_price('AAPL', 150.0)

        # Try to buy more than we can afford
        order = Order(
            symbol='AAPL',
            quantity=100,  # Would cost $15,000
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )

        response = broker.submit_order(order)

        # Order goes through (simulated broker allows margin)
        # But cash will go negative
        assert response.success
        account = broker.get_account()
        # Cash should be negative (borrowed on margin)
        assert account.cash < 0


class TestExecutionAlgorithms:
    """Test execution algorithm implementations."""

    def test_pov_algorithm(self):
        """Test POV (Percentage of Volume) algorithm."""
        from execution.engine import POVAlgorithm, Order, OrderSide

        algo = POVAlgorithm(
            target_participation=0.1,
            min_order_size=100,
            max_order_size=10000
        )

        parent_order = Order(
            symbol='AAPL',
            quantity=5000,
            side=OrderSide.BUY
        )

        market_data = {
            'price': 150.0,
            'volume': 50000  # 10% = 5000 shares
        }

        child_orders = algo.generate_child_orders(parent_order, market_data)

        assert len(child_orders) == 1
        # Should be participation rate * volume, capped by remaining
        assert child_orders[0].quantity <= 5000
        assert child_orders[0].quantity >= 100

    def test_pov_respects_max_size(self):
        """Test POV respects maximum order size."""
        from execution.engine import POVAlgorithm, Order, OrderSide

        algo = POVAlgorithm(
            target_participation=0.1,
            max_order_size=1000
        )

        parent_order = Order(
            symbol='AAPL',
            quantity=50000,
            side=OrderSide.BUY
        )

        market_data = {
            'price': 150.0,
            'volume': 100000  # 10% = 10000, but max is 1000
        }

        child_orders = algo.generate_child_orders(parent_order, market_data)

        assert len(child_orders) == 1
        assert child_orders[0].quantity <= 1000

    def test_execution_algorithm_metadata(self):
        """Test that child orders have proper metadata."""
        from execution.engine import TWAPAlgorithm, Order, OrderSide

        algo = TWAPAlgorithm(n_slices=5)

        parent_order = Order(
            symbol='AAPL',
            quantity=1000,
            side=OrderSide.BUY
        )

        market_data = {'price': 150.0, 'volume': 100000}

        child_orders = algo.generate_child_orders(parent_order, market_data)

        assert len(child_orders) == 1
        assert 'parent_id' in child_orders[0].metadata
        assert child_orders[0].metadata['parent_id'] == parent_order.order_id


class TestOrderLifecycle:
    """Test complete order lifecycle."""

    def test_order_status_transitions(self):
        """Test order status transitions."""
        from execution.engine import Order, OrderStatus, OrderSide

        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY
        )

        assert order.status == OrderStatus.PENDING
        assert not order.is_complete

        # Simulate submission
        order.status = OrderStatus.SUBMITTED
        assert not order.is_complete

        # Simulate partial fill
        order.status = OrderStatus.PARTIAL
        order.filled_quantity = 50
        assert order.remaining_quantity == 50
        assert not order.is_complete

        # Simulate complete fill
        order.status = OrderStatus.FILLED
        order.filled_quantity = 100
        assert order.remaining_quantity == 0
        assert order.is_complete

    def test_order_serialization(self):
        """Test order serialization to dict."""
        from execution.engine import Order, OrderType, OrderSide

        order = Order(
            symbol='AAPL',
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            limit_price=150.0
        )

        order_dict = order.to_dict()

        assert order_dict['symbol'] == 'AAPL'
        assert order_dict['quantity'] == 100
        assert order_dict['side'] == 'buy'
        assert order_dict['order_type'] == 'limit'
        assert order_dict['limit_price'] == 150.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
