"""
Broker Adapter Parity Tests
===========================
Verifies broker adapters match quant-platform behavior.
"""
import pytest
from datetime import datetime


class TestOrderTypeParity:
    """Test order type enum."""

    def test_order_type_values(self):
        """Verify all order types exist."""
        from backend.execution import OrderType

        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"
        assert OrderType.STOP_LIMIT.value == "stop_limit"


class TestOrderSideParity:
    """Test order side enum."""

    def test_order_side_values(self):
        """Verify order side values."""
        from backend.execution import OrderSide

        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"


class TestOrderStatusParity:
    """Test order status enum."""

    def test_order_status_values(self):
        """Verify all status values exist."""
        from backend.execution import OrderStatus

        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.SUBMITTED.value == "submitted"
        assert OrderStatus.PARTIAL.value == "partial"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.REJECTED.value == "rejected"


class TestTimeInForceParity:
    """Test time in force enum."""

    def test_tif_values(self):
        """Verify TIF values."""
        from backend.execution import TimeInForce

        assert TimeInForce.DAY.value == "day"
        assert TimeInForce.GTC.value == "gtc"
        assert TimeInForce.IOC.value == "ioc"
        assert TimeInForce.FOK.value == "fok"


class TestOrderParity:
    """Test Order dataclass."""

    def test_order_structure(self):
        """Verify order has required fields."""
        from backend.execution import Order, OrderType, OrderSide, OrderStatus

        order = Order(
            order_id="test_001",
            symbol="ES",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=2,
        )

        assert hasattr(order, "order_id")
        assert hasattr(order, "symbol")
        assert hasattr(order, "side")
        assert hasattr(order, "order_type")
        assert hasattr(order, "quantity")
        assert hasattr(order, "limit_price")
        assert hasattr(order, "stop_price")
        assert hasattr(order, "status")
        assert hasattr(order, "filled_qty")

    def test_order_serialization(self):
        """Verify order serialization."""
        from backend.execution import Order, OrderType, OrderSide

        order = Order(
            order_id="test_002",
            symbol="NQ",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=1,
            limit_price=18000.0,
        )

        data = order.to_dict()
        assert data["order_id"] == "test_002"
        assert data["symbol"] == "NQ"
        assert data["side"] == "sell"
        assert data["limit_price"] == 18000.0


class TestPositionParity:
    """Test Position dataclass."""

    def test_position_structure(self):
        """Verify position has required fields."""
        from backend.execution import Position

        pos = Position(
            symbol="ES",
            quantity=2,
            side="long",
            avg_entry_price=5000.0,
        )

        assert hasattr(pos, "symbol")
        assert hasattr(pos, "quantity")
        assert hasattr(pos, "side")
        assert hasattr(pos, "avg_entry_price")
        assert hasattr(pos, "current_price")
        assert hasattr(pos, "unrealized_pnl")
        assert hasattr(pos, "market_value")


class TestAccountInfoParity:
    """Test AccountInfo dataclass."""

    def test_account_info_structure(self):
        """Verify account info has required fields."""
        from backend.execution import AccountInfo

        account = AccountInfo(
            account_id="test_account",
            buying_power=100000.0,
            cash=50000.0,
            portfolio_value=100000.0,
            equity=100000.0,
        )

        assert hasattr(account, "account_id")
        assert hasattr(account, "buying_power")
        assert hasattr(account, "cash")
        assert hasattr(account, "portfolio_value")
        assert hasattr(account, "equity")
        assert hasattr(account, "initial_margin")
        assert hasattr(account, "trading_blocked")


class TestPaperBrokerParity:
    """Test PaperBroker implementation."""

    def test_paper_broker_initialization(self):
        """Verify paper broker initializes correctly."""
        from backend.execution import PaperBroker

        broker = PaperBroker(initial_capital=100000.0)

        assert broker.name == "paper"
        assert broker.connected is True
        assert broker.cash == 100000.0

    def test_paper_broker_connect(self):
        """Verify connection management."""
        from backend.execution import PaperBroker

        broker = PaperBroker()
        assert broker.is_connected() is True

        broker.disconnect()
        assert broker.is_connected() is False

        broker.connect()
        assert broker.is_connected() is True

    def test_paper_broker_market_order(self):
        """Verify market order execution."""
        from backend.execution import PaperBroker, OrderSide, OrderStatus

        broker = PaperBroker()
        broker.set_price("ES", 5000.0, 5000.25)

        order = broker.create_market_order("ES", OrderSide.BUY, 2)
        result = broker.submit_order(order)

        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 2
        assert result.avg_fill_price == 5000.25  # Buy at ask

    def test_paper_broker_position_tracking(self):
        """Verify position tracking."""
        from backend.execution import PaperBroker, OrderSide

        broker = PaperBroker()
        broker.set_price("ES", 5000.0, 5000.25)

        # Open position
        order = broker.create_market_order("ES", OrderSide.BUY, 2)
        broker.submit_order(order)

        pos = broker.get_position("ES")
        assert pos is not None
        assert pos.quantity == 2
        assert pos.side == "long"

    def test_paper_broker_close_position(self):
        """Verify position closing."""
        from backend.execution import PaperBroker, OrderSide

        broker = PaperBroker()
        broker.set_price("ES", 5000.0, 5000.25)

        # Open position
        order = broker.create_market_order("ES", OrderSide.BUY, 2)
        broker.submit_order(order)

        # Close position
        broker.close_position("ES")

        pos = broker.get_position("ES")
        assert pos is None

    def test_paper_broker_pnl_calculation(self):
        """Verify P&L calculation."""
        from backend.execution import PaperBroker, OrderSide

        broker = PaperBroker(initial_capital=100000.0)
        broker.set_price("ES", 5000.0, 5000.25)

        # Buy at 5000.25
        order = broker.create_market_order("ES", OrderSide.BUY, 2)
        broker.submit_order(order)

        # Price moves up
        broker.set_price("ES", 5010.0, 5010.25)

        # Sell at 5010.0 (bid)
        order = broker.create_market_order("ES", OrderSide.SELL, 2)
        broker.submit_order(order)

        # P&L = (5010 - 5000.25) * 2 = 19.50
        assert broker.realized_pnl == pytest.approx(19.50, rel=0.01)

    def test_paper_broker_account_info(self):
        """Verify account info."""
        from backend.execution import PaperBroker

        broker = PaperBroker(initial_capital=100000.0)
        account = broker.get_account()

        assert account.account_id == "paper_account"
        assert account.cash == 100000.0
        assert account.equity == 100000.0

    def test_paper_broker_limit_order(self):
        """Verify limit order creation."""
        from backend.execution import PaperBroker, OrderSide, OrderType, TimeInForce

        broker = PaperBroker()

        order = broker.create_limit_order(
            "ES", OrderSide.BUY, 2, 4990.0, TimeInForce.GTC
        )

        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == 4990.0
        assert order.time_in_force == TimeInForce.GTC

    def test_paper_broker_bracket_order(self):
        """Verify bracket order creation."""
        from backend.execution import PaperBroker, OrderSide

        broker = PaperBroker()

        orders = broker.create_bracket_order(
            symbol="ES",
            side=OrderSide.BUY,
            quantity=2,
            entry_price=5000.0,
            stop_loss=4990.0,
            take_profit=5020.0,
        )

        assert "entry" in orders
        assert "stop_loss" in orders
        assert "take_profit" in orders
        assert orders["entry"].limit_price == 5000.0
        assert orders["stop_loss"].stop_price == 4990.0
        assert orders["take_profit"].limit_price == 5020.0

    def test_paper_broker_cancel_order(self):
        """Verify order cancellation."""
        from backend.execution import PaperBroker, OrderSide, OrderStatus

        broker = PaperBroker()

        # Create limit order (won't auto-fill)
        order = broker.create_limit_order("ES", OrderSide.BUY, 2, 4990.0)
        broker.submit_order(order)

        # Cancel
        result = broker.cancel_order(order.order_id)
        assert result is True

        # Verify cancelled
        updated = broker.get_order(order.order_id)
        assert updated.status == OrderStatus.CANCELLED


class TestAlpacaBrokerParity:
    """Test AlpacaBroker structure."""

    def test_alpaca_broker_initialization(self):
        """Verify Alpaca broker initializes correctly."""
        from backend.execution import AlpacaBroker

        broker = AlpacaBroker(paper=True)

        assert broker.name == "alpaca"
        assert broker.paper is True
        assert broker.connected is False  # Not connected until connect() called

    def test_alpaca_broker_paper_url(self):
        """Verify paper trading URL."""
        from backend.execution import AlpacaBroker

        broker = AlpacaBroker(paper=True)
        assert "paper" in broker.base_url

    def test_alpaca_broker_live_url(self):
        """Verify live trading URL."""
        from backend.execution import AlpacaBroker

        broker = AlpacaBroker(paper=False)
        assert "paper" not in broker.base_url

    def test_alpaca_broker_status(self):
        """Verify status reporting."""
        from backend.execution import AlpacaBroker

        broker = AlpacaBroker()
        status = broker.get_status()

        assert status["name"] == "alpaca"
        assert "paper" in status
        assert "api_configured" in status
