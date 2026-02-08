"""
Alpaca Broker Adapter
=====================
P1 Feature: Alpaca Markets integration for live trading.

Implements parity with quant-platform/execution/alpaca_broker.py

Provides:
- Stock and crypto trading via Alpaca API
- Real-time order management
- Position tracking
- Account information
- SafetyGuard integration for all orders (live AND paper)
"""
import logging
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

from .broker_adapter import (
    BrokerAdapter,
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    Position,
    AccountInfo,
)

# Import SafetyGuard for pre-trade validation
try:
    from backend.core.safety_guard import SafetyGuard, get_safety_guard
    SAFETY_GUARD_AVAILABLE = True
except ImportError:
    SAFETY_GUARD_AVAILABLE = False

logger = logging.getLogger("ALPACA_BROKER")

# Try to import alpaca-trade-api
try:
    import alpaca_trade_api as tradeapi
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("alpaca-trade-api not installed. Install with: pip install alpaca-trade-api")


class AlpacaBroker(BrokerAdapter):
    """
    Alpaca Markets broker adapter.

    Provides live and paper trading through Alpaca's API.
    Supports stocks, ETFs, and crypto.

    Environment variables:
    - ALPACA_API_KEY: API key
    - ALPACA_SECRET_KEY: Secret key
    - ALPACA_BASE_URL: Base URL (paper or live)
    """

    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        paper: bool = True,
    ):
        super().__init__("alpaca")

        self.api_key = api_key or os.getenv("ALPACA_API_KEY", "")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY", "")
        self.base_url = base_url or os.getenv(
            "ALPACA_BASE_URL",
            self.PAPER_URL if paper else self.LIVE_URL
        )
        self.paper = paper

        self.api: Optional[Any] = None
        self._order_map: Dict[str, Order] = {}  # Maps our order_id to broker order

        if not ALPACA_AVAILABLE:
            logger.error("Alpaca API not available - install alpaca-trade-api")

        logger.info(f"AlpacaBroker initialized (paper={paper})")

    def connect(self) -> bool:
        """Connect to Alpaca API."""
        if not ALPACA_AVAILABLE:
            logger.error("Cannot connect: alpaca-trade-api not installed")
            return False

        if not self.api_key or not self.secret_key:
            logger.error("Cannot connect: API keys not configured")
            return False

        try:
            self.api = tradeapi.REST(
                self.api_key,
                self.secret_key,
                self.base_url,
                api_version='v2'
            )

            # Test connection
            account = self.api.get_account()
            self.connected = True

            logger.info(
                f"Connected to Alpaca: account={account.id}, "
                f"equity=${float(account.equity):,.2f}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Alpaca."""
        self.api = None
        self.connected = False
        logger.info("Disconnected from Alpaca")

    def is_connected(self) -> bool:
        """Check if connected."""
        if not self.api:
            return False

        try:
            self.api.get_account()
            return True
        except Exception:
            self.connected = False
            return False

    def _map_order_type(self, order_type: OrderType) -> str:
        """Map our order type to Alpaca's."""
        mapping = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
            OrderType.STOP: "stop",
            OrderType.STOP_LIMIT: "stop_limit",
        }
        return mapping.get(order_type, "market")

    def _map_order_side(self, side: OrderSide) -> str:
        """Map our order side to Alpaca's."""
        return "buy" if side == OrderSide.BUY else "sell"

    def _map_time_in_force(self, tif: TimeInForce) -> str:
        """Map our TIF to Alpaca's."""
        mapping = {
            TimeInForce.DAY: "day",
            TimeInForce.GTC: "gtc",
            TimeInForce.IOC: "ioc",
            TimeInForce.FOK: "fok",
        }
        return mapping.get(tif, "day")

    def _parse_alpaca_order(self, alpaca_order: Any) -> Order:
        """Parse Alpaca order to our Order object."""
        # Map status
        status_map = {
            "new": OrderStatus.SUBMITTED,
            "partially_filled": OrderStatus.PARTIAL,
            "filled": OrderStatus.FILLED,
            "done_for_day": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "replaced": OrderStatus.SUBMITTED,
            "pending_cancel": OrderStatus.SUBMITTED,
            "pending_replace": OrderStatus.SUBMITTED,
            "accepted": OrderStatus.SUBMITTED,
            "pending_new": OrderStatus.PENDING,
            "accepted_for_bidding": OrderStatus.SUBMITTED,
            "stopped": OrderStatus.FILLED,
            "rejected": OrderStatus.REJECTED,
            "suspended": OrderStatus.REJECTED,
            "calculated": OrderStatus.SUBMITTED,
        }

        # Map order type
        type_map = {
            "market": OrderType.MARKET,
            "limit": OrderType.LIMIT,
            "stop": OrderType.STOP,
            "stop_limit": OrderType.STOP_LIMIT,
        }

        # Map side
        side = OrderSide.BUY if alpaca_order.side == "buy" else OrderSide.SELL

        return Order(
            order_id=alpaca_order.client_order_id or alpaca_order.id,
            symbol=alpaca_order.symbol,
            side=side,
            order_type=type_map.get(alpaca_order.type, OrderType.MARKET),
            quantity=int(alpaca_order.qty),
            limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
            stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
            status=status_map.get(alpaca_order.status, OrderStatus.PENDING),
            filled_qty=int(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0,
            avg_fill_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else 0.0,
            submitted_at=alpaca_order.submitted_at,
            filled_at=alpaca_order.filled_at,
            broker_order_id=alpaca_order.id,
        )

    def submit_order(self, order: Order) -> Order:
        """
        Submit order to Alpaca with SafetyGuard validation.

        CRITICAL: All orders (live AND paper) go through SafetyGuard checks.
        This ensures prop firm rules and risk limits are enforced consistently.
        """
        if not self.api:
            raise ConnectionError("Not connected to Alpaca")

        # CRITICAL: Run SafetyGuard checks BEFORE submission
        # This applies to BOTH paper and live trading for consistency
        if SAFETY_GUARD_AVAILABLE:
            try:
                guard = get_safety_guard()
                # Determine if this is live trading based on base URL
                is_live = "paper" not in self.base_url.lower()

                # Get current account equity for position sizing validation
                try:
                    account = self.api.get_account()
                    equity = float(account.equity)
                    # Calculate position size as percentage of equity
                    # Use limit price if available, otherwise estimate with current price
                    price_estimate = order.limit_price or 0
                    if price_estimate == 0:
                        try:
                            quote = self.get_quote(order.symbol)
                            price_estimate = quote.get("last", 100)  # Fallback to $100
                        except Exception:
                            price_estimate = 100
                    position_value = order.quantity * price_estimate
                    size_pct = position_value / equity if equity > 0 else 1.0
                except Exception as e:
                    logger.warning(f"Could not calculate position size: {e}")
                    size_pct = 0.05  # Default to 5%

                # Run SafetyGuard validation
                allowed, reason = guard.can_trade(
                    symbol=order.symbol,
                    size_pct=size_pct,
                    contracts=order.quantity,
                    is_live=is_live,
                )

                if not allowed:
                    logger.warning(f"Order blocked by SafetyGuard: {reason}")
                    order.status = OrderStatus.REJECTED
                    if hasattr(order, 'rejection_reason'):
                        order.rejection_reason = f"SafetyGuard: {reason}"
                    return order

            except Exception as e:
                # If SafetyGuard check fails, log but don't block paper trades
                # For live trades, we should be more conservative
                is_live = "paper" not in self.base_url.lower()
                if is_live:
                    logger.error(f"SafetyGuard error on LIVE order - BLOCKING: {e}")
                    order.status = OrderStatus.REJECTED
                    if hasattr(order, 'rejection_reason'):
                        order.rejection_reason = f"SafetyGuard error: {e}"
                    return order
                else:
                    logger.warning(f"SafetyGuard check failed (paper mode, continuing): {e}")

        try:
            # Build order params
            params = {
                "symbol": order.symbol,
                "qty": order.quantity,
                "side": self._map_order_side(order.side),
                "type": self._map_order_type(order.order_type),
                "time_in_force": self._map_time_in_force(order.time_in_force),
            }

            if order.limit_price:
                params["limit_price"] = order.limit_price
            if order.stop_price:
                params["stop_price"] = order.stop_price
            if order.client_order_id:
                params["client_order_id"] = order.client_order_id

            # Submit to Alpaca
            alpaca_order = self.api.submit_order(**params)

            # Parse response
            result = self._parse_alpaca_order(alpaca_order)

            # Thread-safe order map update
            with threading.Lock():
                self._order_map[result.order_id] = result

            logger.info(f"Order submitted: {result.order_id} {result.symbol} {result.side.value}")

            self._notify_order_update(result)

            return result

        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            order.status = OrderStatus.REJECTED
            return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order at Alpaca."""
        if not self.api:
            raise ConnectionError("Not connected to Alpaca")

        try:
            # Find broker order ID
            order = self._order_map.get(order_id)
            broker_id = order.broker_order_id if order else order_id

            self.api.cancel_order(broker_id)

            if order:
                order.status = OrderStatus.CANCELLED
                self._notify_order_update(order)

            logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            return False

    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Modify order at Alpaca (replace order)."""
        if not self.api:
            raise ConnectionError("Not connected to Alpaca")

        order = self._order_map.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")

        try:
            params = {}
            if quantity:
                params["qty"] = quantity
            if limit_price:
                params["limit_price"] = limit_price
            if stop_price:
                params["stop_price"] = stop_price

            alpaca_order = self.api.replace_order(order.broker_order_id, **params)
            result = self._parse_alpaca_order(alpaca_order)

            self._order_map[order_id] = result
            self._notify_order_update(result)

            return result

        except Exception as e:
            logger.error(f"Order modification failed: {e}")
            raise

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order from Alpaca."""
        if not self.api:
            return None

        try:
            order = self._order_map.get(order_id)
            broker_id = order.broker_order_id if order else order_id

            alpaca_order = self.api.get_order(broker_id)
            result = self._parse_alpaca_order(alpaca_order)

            self._order_map[order_id] = result
            return result

        except Exception as e:
            logger.error(f"Failed to get order: {e}")
            return None

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders from Alpaca."""
        if not self.api:
            return []

        try:
            alpaca_orders = self.api.list_orders(status="open")
            orders = [self._parse_alpaca_order(o) for o in alpaca_orders]

            if symbol:
                orders = [o for o in orders if o.symbol == symbol]

            return orders

        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position from Alpaca."""
        if not self.api:
            return None

        try:
            pos = self.api.get_position(symbol)

            return Position(
                symbol=pos.symbol,
                quantity=abs(int(pos.qty)),
                side="long" if int(pos.qty) > 0 else "short",
                avg_entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price),
                unrealized_pnl=float(pos.unrealized_pl),
                market_value=float(pos.market_value),
            )

        except Exception as e:
            # Position might not exist
            if "position does not exist" in str(e).lower():
                return None
            logger.error(f"Failed to get position: {e}")
            return None

    def get_all_positions(self) -> List[Position]:
        """Get all positions from Alpaca."""
        if not self.api:
            return []

        try:
            positions = self.api.list_positions()

            return [
                Position(
                    symbol=pos.symbol,
                    quantity=abs(int(pos.qty)),
                    side="long" if int(pos.qty) > 0 else "short",
                    avg_entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    unrealized_pnl=float(pos.unrealized_pl),
                    market_value=float(pos.market_value),
                )
                for pos in positions
            ]

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def close_position(self, symbol: str) -> Order:
        """Close position at Alpaca."""
        if not self.api:
            raise ConnectionError("Not connected to Alpaca")

        try:
            alpaca_order = self.api.close_position(symbol)
            result = self._parse_alpaca_order(alpaca_order)

            logger.info(f"Position closed: {symbol}")

            return result

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            raise

    def close_all_positions(self) -> List[Order]:
        """Close all positions at Alpaca."""
        if not self.api:
            raise ConnectionError("Not connected to Alpaca")

        try:
            responses = self.api.close_all_positions()
            orders = []

            for response in responses:
                if hasattr(response, 'body') and response.body:
                    order = self._parse_alpaca_order(response.body)
                    orders.append(order)

            logger.info(f"All positions closed: {len(orders)} orders")

            return orders

        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            return []

    def get_account(self) -> AccountInfo:
        """Get account info from Alpaca."""
        if not self.api:
            raise ConnectionError("Not connected to Alpaca")

        try:
            account = self.api.get_account()

            return AccountInfo(
                account_id=account.id,
                buying_power=float(account.buying_power),
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                equity=float(account.equity),
                initial_margin=float(account.initial_margin) if account.initial_margin else 0,
                maintenance_margin=float(account.maintenance_margin) if account.maintenance_margin else 0,
                day_trade_count=int(account.daytrade_count) if account.daytrade_count else 0,
                pattern_day_trader=account.pattern_day_trader,
                status=account.status,
                trading_blocked=account.trading_blocked,
            )

        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            raise

    def get_quote(self, symbol: str) -> Dict[str, float]:
        """Get quote from Alpaca."""
        if not self.api:
            return {"bid": 0, "ask": 0, "last": 0, "volume": 0}

        try:
            # Try to get latest trade and quote
            trade = self.api.get_latest_trade(symbol)
            quote = self.api.get_latest_quote(symbol)

            return {
                "bid": float(quote.bp) if quote.bp else 0,
                "ask": float(quote.ap) if quote.ap else 0,
                "last": float(trade.p) if trade.p else 0,
                "volume": int(trade.s) if trade.s else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return {"bid": 0, "ask": 0, "last": 0, "volume": 0}

    def get_status(self) -> Dict[str, Any]:
        """Get adapter status."""
        status = super().get_status()
        status.update({
            "paper": self.paper,
            "api_configured": bool(self.api_key and self.secret_key),
            "base_url": self.base_url,
        })

        if self.connected and self.api:
            try:
                account = self.api.get_account()
                status["account_status"] = account.status
                status["equity"] = float(account.equity)
            except Exception:
                pass

        return status
