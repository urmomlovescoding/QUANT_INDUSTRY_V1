"""
QUANT_INDUSTRY_V1 Multi-Broker Execution Engine

Unified interface for multiple brokers:
- Alpaca
- Interactive Brokers
- NinjaTrader
- Paper Trading

Features:
- Smart order routing
- Execution quality analysis
- Failover handling
- Position reconciliation
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
import time

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES
# =============================================================================

class BrokerType(Enum):
    """Supported brokers."""
    ALPACA = "alpaca"
    INTERACTIVE_BROKERS = "interactive_brokers"
    NINJATRADER = "ninjatrader"
    PAPER = "paper"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(Enum):
    """Time in force."""
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


@dataclass
class Order:
    """Universal order representation."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    limit_price: float = None
    stop_price: float = None
    time_in_force: TimeInForce = TimeInForce.DAY

    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0

    broker: BrokerType = None
    broker_order_id: str = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: datetime = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Position representation."""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    market_value: float = 0.0
    broker: BrokerType = None


@dataclass
class AccountInfo:
    """Account information."""
    broker: BrokerType
    account_id: str
    equity: float
    cash: float
    buying_power: float
    positions: Dict[str, Position] = field(default_factory=dict)


# =============================================================================
# BROKER ADAPTER (Abstract)
# =============================================================================

class BrokerAdapter(ABC):
    """Abstract broker adapter interface."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker."""
        pass

    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        """Submit order to broker."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Get all positions."""
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Get account information."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, float]:
        """Get current quote for symbol."""
        pass


# =============================================================================
# PAPER TRADING ADAPTER
# =============================================================================

class PaperBrokerAdapter(BrokerAdapter):
    """
    Paper trading broker adapter.

    Full simulation without real money.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_per_share: float = 0.005,
        slippage_pct: float = 0.001,
    ):
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.slippage_pct = slippage_pct

        # Account state
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0

        # Simulated prices (would be fed from data source)
        self.prices: Dict[str, float] = {}

        self.connected = False

    def connect(self) -> bool:
        self.connected = True
        logger.info("Paper broker connected")
        return True

    def disconnect(self) -> None:
        self.connected = False
        logger.info("Paper broker disconnected")

    def set_price(self, symbol: str, price: float) -> None:
        """Set current price for symbol (for simulation)."""
        self.prices[symbol] = price

    def submit_order(self, order: Order) -> Order:
        """Simulate order submission."""
        self.order_counter += 1
        order.broker_order_id = f"PAPER_{self.order_counter}"
        order.broker = BrokerType.PAPER

        # Get current price
        price = self.prices.get(order.symbol, 100.0)

        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = price * (1 + self.slippage_pct)
        else:
            fill_price = price * (1 - self.slippage_pct)

        # Check if order can be filled
        if order.order_type == OrderType.MARKET:
            # Fill immediately
            order = self._fill_order(order, fill_price)
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and price <= order.limit_price:
                order = self._fill_order(order, order.limit_price)
            elif order.side == OrderSide.SELL and price >= order.limit_price:
                order = self._fill_order(order, order.limit_price)
            else:
                order.status = OrderStatus.SUBMITTED
        else:
            order.status = OrderStatus.SUBMITTED

        self.orders[order.order_id] = order
        return order

    def _fill_order(self, order: Order, fill_price: float) -> Order:
        """Fill an order."""
        order.avg_fill_price = fill_price
        order.filled_qty = order.quantity
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now(timezone.utc)

        # Calculate commission
        order.commission = order.quantity * self.commission_per_share

        # Update position
        self._update_position(order)

        return order

    def _update_position(self, order: Order) -> None:
        """Update positions after order fill."""
        symbol = order.symbol
        fill_qty = order.filled_qty if order.side == OrderSide.BUY else -order.filled_qty
        fill_value = fill_qty * order.avg_fill_price

        if symbol in self.positions:
            pos = self.positions[symbol]
            old_qty = pos.quantity
            old_cost = pos.avg_cost * old_qty

            new_qty = old_qty + fill_qty

            if abs(new_qty) < 1e-8:
                # Position closed
                realized_pnl = (order.avg_fill_price - pos.avg_cost) * old_qty if old_qty > 0 else (pos.avg_cost - order.avg_fill_price) * abs(old_qty)
                pos.realized_pnl += realized_pnl
                del self.positions[symbol]
            else:
                # Update average cost
                if fill_qty > 0:
                    pos.avg_cost = (old_cost + fill_value) / new_qty if new_qty != 0 else pos.avg_cost
                pos.quantity = new_qty
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=fill_qty,
                avg_cost=order.avg_fill_price,
                broker=BrokerType.PAPER,
            )

        # Update cash
        self.cash -= fill_value + order.commission

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                return True
        return False

    def get_order_status(self, order_id: str) -> Order:
        return self.orders.get(order_id)

    def get_positions(self) -> Dict[str, Position]:
        # Update current prices and PnL
        for symbol, pos in self.positions.items():
            if symbol in self.prices:
                pos.current_price = self.prices[symbol]
                pos.market_value = pos.quantity * pos.current_price
                pos.unrealized_pnl = (pos.current_price - pos.avg_cost) * pos.quantity

        return self.positions.copy()

    def get_account_info(self) -> AccountInfo:
        positions = self.get_positions()
        market_value = sum(p.market_value for p in positions.values())

        return AccountInfo(
            broker=BrokerType.PAPER,
            account_id="PAPER_001",
            equity=self.cash + market_value,
            cash=self.cash,
            buying_power=self.cash,
            positions=positions,
        )

    def get_quote(self, symbol: str) -> Dict[str, float]:
        price = self.prices.get(symbol, 100.0)
        return {
            'symbol': symbol,
            'bid': price * 0.999,
            'ask': price * 1.001,
            'last': price,
            'volume': 1000000,
        }


# =============================================================================
# ALPACA ADAPTER
# =============================================================================

class AlpacaAdapter(BrokerAdapter):
    """
    Alpaca broker adapter.

    Requires alpaca-py package.
    """

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        paper: bool = True,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.client = None
        self.connected = False

    def connect(self) -> bool:
        try:
            from alpaca.trading.client import TradingClient
            self.client = TradingClient(self.api_key, self.api_secret, paper=self.paper)
            self.connected = True
            logger.info("Alpaca connected")
            return True
        except ImportError:
            logger.error("alpaca-py not installed")
            return False
        except Exception as e:
            logger.error(f"Alpaca connection failed: {e}")
            return False

    def disconnect(self) -> None:
        self.client = None
        self.connected = False
        logger.info("Alpaca disconnected")

    def submit_order(self, order: Order) -> Order:
        if not self.connected or not self.client:
            order.status = OrderStatus.REJECTED
            return order

        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce as AlpacaTIF

            side = AlpacaSide.BUY if order.side == OrderSide.BUY else AlpacaSide.SELL
            tif = AlpacaTIF.DAY

            if order.order_type == OrderType.MARKET:
                req = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    time_in_force=tif,
                )
            else:
                req = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    time_in_force=tif,
                    limit_price=order.limit_price,
                )

            result = self.client.submit_order(req)
            order.broker_order_id = result.id
            order.broker = BrokerType.ALPACA
            order.status = OrderStatus.SUBMITTED

            logger.info(f"Alpaca order submitted: {result.id}")

        except Exception as e:
            logger.error(f"Alpaca order failed: {e}")
            order.status = OrderStatus.REJECTED

        return order

    def cancel_order(self, order_id: str) -> bool:
        try:
            self.client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error(f"Alpaca cancel failed: {e}")
            return False

    def get_order_status(self, order_id: str) -> Order:
        try:
            result = self.client.get_order_by_id(order_id)
            # Convert Alpaca order to our Order type
            order = Order(
                order_id=order_id,
                symbol=result.symbol,
                side=OrderSide.BUY if str(result.side) == 'buy' else OrderSide.SELL,
                quantity=float(result.qty),
                order_type=OrderType.MARKET,
                broker=BrokerType.ALPACA,
                broker_order_id=order_id,
            )
            order.filled_qty = float(result.filled_qty) if result.filled_qty else 0
            order.avg_fill_price = float(result.filled_avg_price) if result.filled_avg_price else 0

            status_map = {
                'new': OrderStatus.SUBMITTED,
                'partially_filled': OrderStatus.PARTIAL,
                'filled': OrderStatus.FILLED,
                'canceled': OrderStatus.CANCELLED,
                'rejected': OrderStatus.REJECTED,
            }
            order.status = status_map.get(str(result.status), OrderStatus.PENDING)

            return order
        except Exception as e:
            logger.error(f"Alpaca get order failed: {e}")
            return None

    def get_positions(self) -> Dict[str, Position]:
        positions = {}
        try:
            alpaca_positions = self.client.get_all_positions()
            for p in alpaca_positions:
                positions[p.symbol] = Position(
                    symbol=p.symbol,
                    quantity=float(p.qty),
                    avg_cost=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                    unrealized_pnl=float(p.unrealized_pl),
                    market_value=float(p.market_value),
                    broker=BrokerType.ALPACA,
                )
        except Exception as e:
            logger.error(f"Alpaca get positions failed: {e}")

        return positions

    def get_account_info(self) -> AccountInfo:
        try:
            account = self.client.get_account()
            return AccountInfo(
                broker=BrokerType.ALPACA,
                account_id=account.account_number,
                equity=float(account.equity),
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                positions=self.get_positions(),
            )
        except Exception as e:
            logger.error(f"Alpaca get account failed: {e}")
            return None

    def get_quote(self, symbol: str) -> Dict[str, float]:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestQuoteRequest

            data_client = StockHistoricalDataClient(self.api_key, self.api_secret)
            req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = data_client.get_stock_latest_quote(req)[symbol]

            return {
                'symbol': symbol,
                'bid': float(quote.bid_price),
                'ask': float(quote.ask_price),
                'last': (float(quote.bid_price) + float(quote.ask_price)) / 2,
            }
        except Exception as e:
            logger.error(f"Alpaca quote failed: {e}")
            return {'symbol': symbol, 'bid': 0, 'ask': 0, 'last': 0}


# =============================================================================
# MULTI-BROKER ENGINE
# =============================================================================

class MultiBrokerEngine:
    """
    Multi-broker execution engine.

    Manages multiple broker connections and routes orders optimally.
    """

    def __init__(self):
        self.adapters: Dict[BrokerType, BrokerAdapter] = {}
        self.primary_broker: BrokerType = None
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0

        # Callbacks
        self.on_fill: List[Callable[[Order], None]] = []
        self.on_rejection: List[Callable[[Order], None]] = []

        # Monitoring thread
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def add_broker(
        self,
        broker_type: BrokerType,
        adapter: BrokerAdapter,
        primary: bool = False,
    ) -> bool:
        """Add a broker adapter."""
        if adapter.connect():
            self.adapters[broker_type] = adapter
            if primary or self.primary_broker is None:
                self.primary_broker = broker_type
            logger.info(f"Added broker: {broker_type.value}")
            return True
        return False

    def remove_broker(self, broker_type: BrokerType) -> None:
        """Remove a broker adapter."""
        if broker_type in self.adapters:
            self.adapters[broker_type].disconnect()
            del self.adapters[broker_type]

            if self.primary_broker == broker_type:
                self.primary_broker = next(iter(self.adapters.keys()), None)

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None,
        stop_price: float = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        broker: BrokerType = None,
    ) -> Order:
        """
        Submit order through the engine.
        """
        self.order_counter += 1
        order_id = f"MBE_{int(time.time())}_{self.order_counter}"

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force=time_in_force,
        )

        # Select broker
        target_broker = broker or self.primary_broker
        if target_broker not in self.adapters:
            order.status = OrderStatus.REJECTED
            logger.error(f"No broker available for order {order_id}")
            return order

        # Submit to broker
        adapter = self.adapters[target_broker]
        order = adapter.submit_order(order)

        self.orders[order_id] = order

        # Handle immediate fill
        if order.status == OrderStatus.FILLED:
            for callback in self.on_fill:
                try:
                    callback(order)
                except Exception as e:
                    logger.error(f"Fill callback error: {e}")

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        if order.broker in self.adapters:
            return self.adapters[order.broker].cancel_order(order.broker_order_id)

        return False

    def cancel_all_orders(self) -> int:
        """Cancel all open orders."""
        cancelled = 0
        for order_id, order in self.orders.items():
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                if self.cancel_order(order_id):
                    cancelled += 1
        return cancelled

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get consolidated positions across all brokers."""
        all_positions = {}

        for broker_type, adapter in self.adapters.items():
            try:
                positions = adapter.get_positions()
                for symbol, pos in positions.items():
                    if symbol in all_positions:
                        # Combine positions
                        existing = all_positions[symbol]
                        total_qty = existing.quantity + pos.quantity
                        if total_qty != 0:
                            combined_cost = (
                                (existing.avg_cost * existing.quantity + pos.avg_cost * pos.quantity) /
                                total_qty
                            )
                            existing.quantity = total_qty
                            existing.avg_cost = combined_cost
                            existing.unrealized_pnl += pos.unrealized_pnl
                    else:
                        all_positions[symbol] = pos
            except Exception as e:
                logger.error(f"Failed to get positions from {broker_type}: {e}")

        return all_positions

    def get_account_summary(self) -> Dict[str, Any]:
        """Get consolidated account summary."""
        total_equity = 0
        total_cash = 0
        total_buying_power = 0
        broker_accounts = {}

        for broker_type, adapter in self.adapters.items():
            try:
                info = adapter.get_account_info()
                if info:
                    broker_accounts[broker_type.value] = {
                        'equity': info.equity,
                        'cash': info.cash,
                        'buying_power': info.buying_power,
                    }
                    total_equity += info.equity
                    total_cash += info.cash
                    total_buying_power += info.buying_power
            except Exception as e:
                logger.error(f"Failed to get account from {broker_type}: {e}")

        positions = self.get_all_positions()

        return {
            'total_equity': total_equity,
            'total_cash': total_cash,
            'total_buying_power': total_buying_power,
            'broker_accounts': broker_accounts,
            'positions': {s: {'qty': p.quantity, 'value': p.market_value} for s, p in positions.items()},
            'num_positions': len(positions),
            'brokers_connected': list(self.adapters.keys()),
        }

    def get_best_quote(self, symbol: str) -> Dict[str, Any]:
        """Get best quote across all brokers."""
        best_bid = 0
        best_ask = float('inf')
        quotes = {}

        for broker_type, adapter in self.adapters.items():
            try:
                quote = adapter.get_quote(symbol)
                quotes[broker_type.value] = quote

                if quote['bid'] > best_bid:
                    best_bid = quote['bid']
                if quote['ask'] < best_ask:
                    best_ask = quote['ask']
            except:
                pass

        return {
            'symbol': symbol,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'spread': best_ask - best_bid,
            'mid': (best_bid + best_ask) / 2,
            'broker_quotes': quotes,
        }

    def start_monitoring(self) -> None:
        """Start order monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop monitoring thread."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)

    def _monitor_loop(self) -> None:
        """Monitor open orders for fills."""
        while not self._stop_event.is_set():
            for order_id, order in list(self.orders.items()):
                if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL]:
                    self._check_order_status(order)

            time.sleep(1)

    def _check_order_status(self, order: Order) -> None:
        """Check and update order status."""
        if order.broker in self.adapters:
            try:
                updated = self.adapters[order.broker].get_order_status(order.broker_order_id)
                if updated and updated.status != order.status:
                    old_status = order.status
                    order.status = updated.status
                    order.filled_qty = updated.filled_qty
                    order.avg_fill_price = updated.avg_fill_price
                    order.updated_at = datetime.now(timezone.utc)

                    if order.status == OrderStatus.FILLED:
                        order.filled_at = datetime.now(timezone.utc)
                        for callback in self.on_fill:
                            callback(order)

                    logger.info(f"Order {order.order_id}: {old_status} -> {order.status}")
            except Exception as e:
                logger.error(f"Order status check failed: {e}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BrokerType',
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'TimeInForce',
    'Order',
    'Position',
    'AccountInfo',
    'BrokerAdapter',
    'PaperBrokerAdapter',
    'AlpacaAdapter',
    'MultiBrokerEngine',
]
