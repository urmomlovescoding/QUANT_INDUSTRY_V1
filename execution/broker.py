"""
QUANT_INDUSTRY_V1 Broker Integrations

Broker connections for order execution:
- Simulated broker for backtesting
- Alpaca broker for live/paper trading
- Abstract interface for other brokers

Rollback Plan: Delete this file
Tests Required: Connection handling, order lifecycle
Failure Modes: Reject orders, retry logic
"""

import numpy as np
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import os

from .engine import Order, OrderStatus, OrderSide, OrderType, Fill

logger = logging.getLogger(__name__)


# =============================================================================
# BROKER CONFIGURATION
# =============================================================================

@dataclass
class BrokerConfig:
    """Broker configuration."""
    api_key: str = ""
    api_secret: str = ""
    base_url: str = ""
    paper_trading: bool = True
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


@dataclass
class AccountInfo:
    """Broker account information."""
    account_id: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    margin_used: float = 0.0
    margin_available: float = 0.0
    day_trades_remaining: int = 3
    status: str = "active"
    currency: str = "USD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'account_id': self.account_id,
            'buying_power': self.buying_power,
            'cash': self.cash,
            'portfolio_value': self.portfolio_value,
            'equity': self.equity,
            'margin_used': self.margin_used,
            'margin_available': self.margin_available,
            'day_trades_remaining': self.day_trades_remaining,
            'status': self.status,
            'currency': self.currency,
        }


@dataclass
class OrderResponse:
    """Response from broker order submission."""
    success: bool
    order_id: str
    status: OrderStatus
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    fills: List[Fill] = field(default_factory=list)
    message: str = ""


@dataclass
class Position:
    """Broker position."""
    symbol: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    side: str = "long"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'side': self.side,
        }


# =============================================================================
# BASE BROKER
# =============================================================================

class BaseBroker(ABC):
    """Abstract base class for brokers."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker."""
        pass

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Get account information."""
        pass

    @abstractmethod
    def submit_order(self, order: Order) -> OrderResponse:
        """Submit order to broker."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order status."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current positions."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get current quote for symbol."""
        pass


# =============================================================================
# SIMULATED BROKER
# =============================================================================

class SimulatedBroker(BaseBroker):
    """
    Simulated broker for backtesting.

    Simulates realistic order execution with configurable parameters.
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
        commission_per_share: float = 0.005,
        min_commission: float = 1.0,
        slippage_bps: float = 5.0,
        fill_probability: float = 0.95,
        partial_fill_probability: float = 0.1,
    ):
        self.initial_cash = initial_cash
        self.commission_per_share = commission_per_share
        self.min_commission = min_commission
        self.slippage_bps = slippage_bps
        self.fill_probability = fill_probability
        self.partial_fill_probability = partial_fill_probability

        # Account state
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}

        # Market data (simulated)
        self.prices: Dict[str, float] = {}

        self._connected = False
        self._lock = threading.RLock()

    def connect(self) -> bool:
        """Connect (no-op for simulated)."""
        self._connected = True
        logger.info("Simulated broker connected")
        return True

    def disconnect(self) -> None:
        """Disconnect."""
        self._connected = False

    def get_account(self) -> AccountInfo:
        """Get simulated account info."""
        portfolio_value = self.cash

        for pos in self.positions.values():
            price = self.prices.get(pos.symbol, pos.avg_cost)
            pos.market_value = pos.quantity * price
            pos.unrealized_pnl = pos.market_value - pos.quantity * pos.avg_cost
            portfolio_value += pos.market_value

        return AccountInfo(
            account_id="SIM001",
            buying_power=self.cash,
            cash=self.cash,
            portfolio_value=portfolio_value,
            equity=portfolio_value,
        )

    def submit_order(self, order: Order) -> OrderResponse:
        """Simulate order execution."""
        if not self._connected:
            return OrderResponse(
                success=False,
                order_id=order.order_id,
                status=OrderStatus.REJECTED,
                message="Not connected",
            )

        with self._lock:
            self.orders[order.order_id] = order

            # Get price
            price = self.prices.get(order.symbol, 100.0)

            # Random fill determination
            if np.random.random() > self.fill_probability:
                order.status = OrderStatus.REJECTED
                return OrderResponse(
                    success=False,
                    order_id=order.order_id,
                    status=OrderStatus.REJECTED,
                    message="Simulated rejection",
                )

            # Partial fill?
            fill_ratio = 1.0
            if np.random.random() < self.partial_fill_probability:
                fill_ratio = np.random.uniform(0.3, 0.9)

            # Calculate execution price with slippage
            slippage = self.slippage_bps / 10000
            if order.side == OrderSide.BUY:
                exec_price = price * (1 + slippage)
            else:
                exec_price = price * (1 - slippage)

            # Check limit price
            if order.order_type == OrderType.LIMIT:
                if order.side == OrderSide.BUY and exec_price > order.limit_price:
                    order.status = OrderStatus.SUBMITTED  # Pending
                    return OrderResponse(
                        success=True,
                        order_id=order.order_id,
                        status=OrderStatus.SUBMITTED,
                        message="Limit order pending",
                    )
                if order.side == OrderSide.SELL and exec_price < order.limit_price:
                    order.status = OrderStatus.SUBMITTED
                    return OrderResponse(
                        success=True,
                        order_id=order.order_id,
                        status=OrderStatus.SUBMITTED,
                        message="Limit order pending",
                    )

            # Execute fill
            fill_qty = order.quantity * fill_ratio
            commission = max(self.min_commission, fill_qty * self.commission_per_share)

            # Update position
            self._update_position(order.symbol, fill_qty if order.side == OrderSide.BUY else -fill_qty, exec_price)

            # Update cash
            if order.side == OrderSide.BUY:
                self.cash -= fill_qty * exec_price + commission
            else:
                self.cash += fill_qty * exec_price - commission

            # Create fill
            fill = Fill(
                fill_id=f"{order.order_id}_fill",
                order_id=order.order_id,
                symbol=order.symbol,
                quantity=fill_qty,
                price=exec_price,
                side=order.side,
                timestamp=datetime.now(timezone.utc),
                commission=commission,
                exchange="SIM",
            )

            order.filled_quantity = fill_qty
            order.filled_avg_price = exec_price
            order.commission = commission
            order.status = OrderStatus.FILLED if fill_ratio == 1.0 else OrderStatus.PARTIAL

            return OrderResponse(
                success=True,
                order_id=order.order_id,
                status=order.status,
                filled_quantity=fill_qty,
                avg_price=exec_price,
                fills=[fill],
            )

    def _update_position(self, symbol: str, quantity_delta: float, price: float) -> None:
        """Update position after fill."""
        if symbol in self.positions:
            pos = self.positions[symbol]
            old_value = pos.quantity * pos.avg_cost
            new_value = old_value + quantity_delta * price
            pos.quantity += quantity_delta

            if pos.quantity > 0:
                pos.avg_cost = new_value / pos.quantity
            elif pos.quantity == 0:
                del self.positions[symbol]
        else:
            if quantity_delta != 0:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity_delta,
                    avg_cost=price,
                    market_value=quantity_delta * price,
                    unrealized_pnl=0.0,
                    side="long" if quantity_delta > 0 else "short",
                )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel simulated order."""
        with self._lock:
            if order_id in self.orders:
                order = self.orders[order_id]
                if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                    order.status = OrderStatus.CANCELLED
                    return True
        return False

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_positions(self) -> List[Position]:
        """Get current positions."""
        # Update market values
        for pos in self.positions.values():
            price = self.prices.get(pos.symbol, pos.avg_cost)
            pos.market_value = pos.quantity * price
            pos.unrealized_pnl = pos.market_value - pos.quantity * pos.avg_cost

        return list(self.positions.values())

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get simulated quote."""
        price = self.prices.get(symbol, 100.0)
        spread = price * 0.001  # 10 bps spread

        return {
            'symbol': symbol,
            'price': price,
            'bid': price - spread / 2,
            'ask': price + spread / 2,
            'spread': spread,
            'volume': 100000,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def set_price(self, symbol: str, price: float) -> None:
        """Set simulated price for symbol."""
        self.prices[symbol] = price


# =============================================================================
# ALPACA BROKER
# =============================================================================

class AlpacaBroker(BaseBroker):
    """
    Alpaca broker integration.

    Supports both paper and live trading.
    """

    def __init__(self, config: BrokerConfig = None):
        self.config = config or BrokerConfig()

        # Load from environment if not provided
        if not self.config.api_key:
            self.config.api_key = os.environ.get('ALPACA_API_KEY', '')
        if not self.config.api_secret:
            self.config.api_secret = os.environ.get('ALPACA_API_SECRET', '')
        if not self.config.base_url:
            if self.config.paper_trading:
                self.config.base_url = 'https://paper-api.alpaca.markets'
            else:
                self.config.base_url = 'https://api.alpaca.markets'

        self._api = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            import alpaca_trade_api as tradeapi

            self._api = tradeapi.REST(
                self.config.api_key,
                self.config.api_secret,
                self.config.base_url,
                api_version='v2'
            )

            # Test connection
            account = self._api.get_account()
            self._connected = account.status == 'ACTIVE'

            logger.info(f"Connected to Alpaca ({'paper' if self.config.paper_trading else 'live'})")
            return self._connected

        except ImportError:
            logger.error("alpaca-trade-api not installed")
            return False
        except Exception as e:
            logger.error(f"Alpaca connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Alpaca."""
        self._api = None
        self._connected = False

    def get_account(self) -> AccountInfo:
        """Get Alpaca account info."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")

        account = self._api.get_account()

        return AccountInfo(
            account_id=account.id,
            buying_power=float(account.buying_power),
            cash=float(account.cash),
            portfolio_value=float(account.portfolio_value),
            equity=float(account.equity),
            margin_used=float(getattr(account, 'maintenance_margin', 0)),
            day_trades_remaining=int(getattr(account, 'daytrade_count', 0)),
            status=account.status,
            currency=account.currency,
        )

    def submit_order(self, order: Order) -> OrderResponse:
        """Submit order to Alpaca."""
        if not self._connected:
            return OrderResponse(
                success=False,
                order_id=order.order_id,
                status=OrderStatus.REJECTED,
                message="Not connected",
            )

        try:
            # Map order type
            alpaca_type = {
                OrderType.MARKET: 'market',
                OrderType.LIMIT: 'limit',
                OrderType.STOP: 'stop',
                OrderType.STOP_LIMIT: 'stop_limit',
                OrderType.TRAILING_STOP: 'trailing_stop',
            }.get(order.order_type, 'market')

            # Map time in force
            alpaca_tif = {
                'day': 'day',
                'gtc': 'gtc',
                'ioc': 'ioc',
                'fok': 'fok',
            }.get(order.time_in_force.value, 'day')

            # Submit order
            alpaca_order = self._api.submit_order(
                symbol=order.symbol,
                qty=order.quantity,
                side=order.side.value,
                type=alpaca_type,
                time_in_force=alpaca_tif,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
                client_order_id=order.client_order_id or order.order_id,
            )

            # Map status
            status_map = {
                'new': OrderStatus.SUBMITTED,
                'partially_filled': OrderStatus.PARTIAL,
                'filled': OrderStatus.FILLED,
                'cancelled': OrderStatus.CANCELLED,
                'expired': OrderStatus.EXPIRED,
                'rejected': OrderStatus.REJECTED,
                'pending_new': OrderStatus.PENDING,
            }

            return OrderResponse(
                success=True,
                order_id=alpaca_order.id,
                status=status_map.get(alpaca_order.status, OrderStatus.SUBMITTED),
                filled_quantity=float(alpaca_order.filled_qty or 0),
                avg_price=float(alpaca_order.filled_avg_price or 0),
            )

        except Exception as e:
            logger.error(f"Alpaca order error: {e}")
            return OrderResponse(
                success=False,
                order_id=order.order_id,
                status=OrderStatus.REJECTED,
                message=str(e),
            )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel Alpaca order."""
        if not self._connected:
            return False

        try:
            self._api.cancel_order(order_id)
            return True
        except Exception as e:
            logger.error(f"Alpaca cancel error: {e}")
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order from Alpaca."""
        if not self._connected:
            return None

        try:
            alpaca_order = self._api.get_order(order_id)

            order_type_map = {
                'market': OrderType.MARKET,
                'limit': OrderType.LIMIT,
                'stop': OrderType.STOP,
                'stop_limit': OrderType.STOP_LIMIT,
                'trailing_stop': OrderType.TRAILING_STOP,
            }

            status_map = {
                'new': OrderStatus.SUBMITTED,
                'partially_filled': OrderStatus.PARTIAL,
                'filled': OrderStatus.FILLED,
                'cancelled': OrderStatus.CANCELLED,
                'expired': OrderStatus.EXPIRED,
                'rejected': OrderStatus.REJECTED,
            }

            return Order(
                symbol=alpaca_order.symbol,
                quantity=float(alpaca_order.qty),
                side=OrderSide.BUY if alpaca_order.side == 'buy' else OrderSide.SELL,
                order_type=order_type_map.get(alpaca_order.type, OrderType.MARKET),
                limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
                stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
                order_id=alpaca_order.id,
                status=status_map.get(alpaca_order.status, OrderStatus.SUBMITTED),
                filled_quantity=float(alpaca_order.filled_qty or 0),
                filled_avg_price=float(alpaca_order.filled_avg_price or 0),
            )

        except Exception as e:
            logger.error(f"Alpaca get_order error: {e}")
            return None

    def get_positions(self) -> List[Position]:
        """Get positions from Alpaca."""
        if not self._connected:
            return []

        try:
            alpaca_positions = self._api.list_positions()

            return [
                Position(
                    symbol=p.symbol,
                    quantity=float(p.qty),
                    avg_cost=float(p.avg_entry_price),
                    market_value=float(p.market_value),
                    unrealized_pnl=float(p.unrealized_pl),
                    side=p.side,
                )
                for p in alpaca_positions
            ]

        except Exception as e:
            logger.error(f"Alpaca positions error: {e}")
            return []

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get quote from Alpaca."""
        if not self._connected:
            return {}

        try:
            quote = self._api.get_latest_quote(symbol)

            return {
                'symbol': symbol,
                'bid': float(quote.bp),
                'ask': float(quote.ap),
                'price': (float(quote.bp) + float(quote.ap)) / 2,
                'spread': float(quote.ap) - float(quote.bp),
                'bid_size': int(quote.bs),
                'ask_size': int(quote.as_),
                'timestamp': quote.t.isoformat() if hasattr(quote, 't') else None,
            }

        except Exception as e:
            logger.error(f"Alpaca quote error: {e}")
            return {}
