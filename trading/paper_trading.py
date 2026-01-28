"""
Paper Trading System
QUANT_INDUSTRY_V1

Industry Problem: No safe way to test strategies with real market data.
Jump from backtest to live trading with real money - disaster waiting to happen.

Our Solution:
- Full paper trading environment with simulated execution
- Realistic slippage and fill simulation
- Real-time market data integration
- Complete order management (limit, stop, bracket)
- Position and P&L tracking
- Performance analytics identical to live
- Easy promotion to live trading when ready
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import asyncio
from collections import defaultdict
import uuid
import threading

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
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
    OPG = "opg"  # At open
    CLS = "cls"  # At close


@dataclass
class PaperOrder:
    """Paper trading order."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    
    # Prices
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trail_amount: Optional[float] = None  # For trailing stops
    trail_percent: Optional[float] = None
    
    # Time in force
    time_in_force: TimeInForce = TimeInForce.DAY
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_avg_price: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    
    # Execution details
    fills: List[Dict[str, Any]] = field(default_factory=list)
    commission: float = 0.0
    
    # Bracket order links
    parent_order_id: Optional[str] = None
    take_profit_order_id: Optional[str] = None
    stop_loss_order_id: Optional[str] = None
    
    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity
        
    @property
    def is_complete(self) -> bool:
        return self.status in [
            OrderStatus.FILLED, OrderStatus.CANCELLED,
            OrderStatus.REJECTED, OrderStatus.EXPIRED
        ]
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_avg_price': self.filled_avg_price,
            'created_at': self.created_at.isoformat(),
            'commission': self.commission
        }


@dataclass
class PaperPosition:
    """Paper trading position."""
    symbol: str
    quantity: float
    avg_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Timestamps
    opened_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def side(self) -> str:
        return "long" if self.quantity > 0 else "short"
        
    @property
    def cost_basis(self) -> float:
        return abs(self.quantity) * self.avg_cost
        
    def update_market_value(self, current_price: float):
        """Update position with current market price."""
        self.market_value = self.quantity * current_price
        self.unrealized_pnl = self.market_value - (self.quantity * self.avg_cost)
        self.last_updated = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'side': self.side,
            'cost_basis': self.cost_basis,
            'opened_at': self.opened_at.isoformat()
        }


@dataclass
class PaperAccount:
    """Paper trading account."""
    account_id: str
    initial_cash: float
    cash: float
    
    # Performance
    portfolio_value: float = 0.0
    day_trading_buying_power: float = 0.0
    
    # Tracking
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    
    # High water mark for drawdown
    high_water_mark: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    
    # Created
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'account_id': self.account_id,
            'cash': self.cash,
            'portfolio_value': self.portfolio_value,
            'initial_cash': self.initial_cash,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl / self.initial_cash if self.initial_cash > 0 else 0,
            'total_trades': self.total_trades,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0,
            'max_drawdown': self.max_drawdown,
            'current_drawdown': self.current_drawdown
        }


class FillSimulator:
    """
    Simulate realistic order fills.
    
    Models:
    - Slippage based on order size and volatility
    - Partial fills for large orders
    - Bid-ask spread crossing
    - Market impact
    """
    
    def __init__(
        self,
        base_slippage_bps: float = 2.0,
        volatility_factor: float = 0.5,
        size_impact_factor: float = 0.1,
        partial_fill_probability: float = 0.05,
        rejection_probability: float = 0.01
    ):
        self.base_slippage_bps = base_slippage_bps
        self.volatility_factor = volatility_factor
        self.size_impact_factor = size_impact_factor
        self.partial_fill_probability = partial_fill_probability
        self.rejection_probability = rejection_probability
        
    def simulate_fill(
        self,
        order: PaperOrder,
        market_price: float,
        bid: float,
        ask: float,
        volume: float,
        volatility: float
    ) -> Tuple[bool, float, float, str]:
        """
        Simulate order fill.
        
        Returns: (filled, fill_price, fill_quantity, message)
        """
        # Random rejection
        if np.random.random() < self.rejection_probability:
            return False, 0, 0, "Order rejected (simulated)"
            
        # Calculate slippage
        spread = ask - bid
        spread_bps = (spread / market_price) * 10000
        
        # Base slippage
        slippage_bps = self.base_slippage_bps
        
        # Volatility adjustment
        slippage_bps += volatility * self.volatility_factor * 100
        
        # Size impact (larger orders = more slippage)
        participation = order.quantity * market_price / (volume * market_price)
        slippage_bps += participation * self.size_impact_factor * 100
        
        slippage = slippage_bps / 10000 * market_price
        
        # Determine fill price
        if order.order_type == OrderType.MARKET:
            if order.side == OrderSide.BUY:
                fill_price = ask + slippage  # Cross the spread + slippage
            else:
                fill_price = bid - slippage
                
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY:
                if ask <= order.limit_price:
                    fill_price = min(ask + slippage, order.limit_price)
                else:
                    return False, 0, 0, "Limit not reached"
            else:
                if bid >= order.limit_price:
                    fill_price = max(bid - slippage, order.limit_price)
                else:
                    return False, 0, 0, "Limit not reached"
                    
        elif order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY and market_price >= order.stop_price:
                fill_price = ask + slippage
            elif order.side == OrderSide.SELL and market_price <= order.stop_price:
                fill_price = bid - slippage
            else:
                return False, 0, 0, "Stop not triggered"
                
        else:
            fill_price = market_price
            
        # Determine fill quantity
        fill_qty = order.remaining_quantity
        
        # Partial fill simulation
        if np.random.random() < self.partial_fill_probability:
            fill_qty = order.remaining_quantity * np.random.uniform(0.3, 0.9)
            
        return True, fill_price, fill_qty, "Filled"


class PaperTradingEngine:
    """
    Paper trading execution engine.
    """
    
    def __init__(
        self,
        initial_cash: float = 100000,
        commission_per_share: float = 0.005,
        min_commission: float = 1.0,
        fill_simulator: Optional[FillSimulator] = None
    ):
        self.commission_per_share = commission_per_share
        self.min_commission = min_commission
        self.fill_simulator = fill_simulator or FillSimulator()
        
        # Account
        self.account = PaperAccount(
            account_id=f"paper_{uuid.uuid4().hex[:8]}",
            initial_cash=initial_cash,
            cash=initial_cash,
            portfolio_value=initial_cash,
            high_water_mark=initial_cash
        )
        
        # State
        self.orders: Dict[str, PaperOrder] = {}
        self.positions: Dict[str, PaperPosition] = {}
        self.prices: Dict[str, Dict[str, float]] = {}  # {symbol: {bid, ask, last, volume}}
        
        # History
        self.trade_history: List[Dict[str, Any]] = []
        self.equity_history: List[Tuple[datetime, float]] = []
        
        # Callbacks
        self.on_fill: List[Callable[[PaperOrder], None]] = []
        self.on_order_update: List[Callable[[PaperOrder], None]] = []
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
    def update_price(
        self,
        symbol: str,
        bid: float,
        ask: float,
        last: float,
        volume: float,
        volatility: float = 0.02
    ):
        """Update market data for a symbol."""
        with self._lock:
            self.prices[symbol] = {
                'bid': bid,
                'ask': ask,
                'last': last,
                'volume': volume,
                'volatility': volatility,
                'timestamp': datetime.now()
            }
            
            # Update position market values
            if symbol in self.positions:
                self.positions[symbol].update_market_value(last)
                
            # Check for triggered orders
            self._check_pending_orders(symbol)
            
            # Update account value
            self._update_account_value()
            
    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY
    ) -> PaperOrder:
        """Submit a paper order."""
        with self._lock:
            order = PaperOrder(
                order_id=f"ORD{uuid.uuid4().hex[:8].upper()}",
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=time_in_force
            )
            
            # Validate order
            if not self._validate_order(order):
                order.status = OrderStatus.REJECTED
                return order
                
            self.orders[order.order_id] = order
            order.status = OrderStatus.OPEN
            
            # Try immediate fill for market orders
            if order_type == OrderType.MARKET and symbol in self.prices:
                self._try_fill_order(order)
                
            return order
            
    def submit_bracket_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        take_profit_price: float,
        stop_loss_price: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None
    ) -> Tuple[PaperOrder, PaperOrder, PaperOrder]:
        """
        Submit a bracket order (entry + take profit + stop loss).
        
        Returns: (entry_order, take_profit_order, stop_loss_order)
        """
        with self._lock:
            # Entry order
            entry = self.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price
            )
            
            # Opposite side for exit orders
            exit_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
            
            # Take profit (limit order)
            tp = PaperOrder(
                order_id=f"ORD{uuid.uuid4().hex[:8].upper()}",
                symbol=symbol,
                side=exit_side,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                limit_price=take_profit_price,
                parent_order_id=entry.order_id,
                status=OrderStatus.PENDING  # Pending until entry fills
            )
            
            # Stop loss (stop order)
            sl = PaperOrder(
                order_id=f"ORD{uuid.uuid4().hex[:8].upper()}",
                symbol=symbol,
                side=exit_side,
                order_type=OrderType.STOP,
                quantity=quantity,
                stop_price=stop_loss_price,
                parent_order_id=entry.order_id,
                status=OrderStatus.PENDING
            )
            
            # Link orders
            entry.take_profit_order_id = tp.order_id
            entry.stop_loss_order_id = sl.order_id
            
            self.orders[tp.order_id] = tp
            self.orders[sl.order_id] = sl
            
            return entry, tp, sl
            
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        with self._lock:
            if order_id not in self.orders:
                return False
                
            order = self.orders[order_id]
            if order.is_complete:
                return False
                
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            
            # Cancel linked bracket orders
            if order.take_profit_order_id:
                self._cancel_order_internal(order.take_profit_order_id)
            if order.stop_loss_order_id:
                self._cancel_order_internal(order.stop_loss_order_id)
                
            return True
            
    def _cancel_order_internal(self, order_id: str):
        """Internal cancel without lock."""
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            
    def _validate_order(self, order: PaperOrder) -> bool:
        """Validate order before submission."""
        # Check buying power
        if order.side == OrderSide.BUY:
            price = order.limit_price or self.prices.get(order.symbol, {}).get('ask', 0)
            required = order.quantity * price
            if required > self.account.cash:
                logger.warning(f"Insufficient buying power: need {required}, have {self.account.cash}")
                return False
                
        # Check position for sells
        elif order.side == OrderSide.SELL:
            position = self.positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                logger.warning(f"Insufficient position to sell")
                return False
                
        return True
        
    def _check_pending_orders(self, symbol: str):
        """Check for orders that can be filled."""
        for order in self.orders.values():
            if order.symbol == symbol and order.status == OrderStatus.OPEN:
                self._try_fill_order(order)
                
    def _try_fill_order(self, order: PaperOrder):
        """Try to fill an order."""
        if order.symbol not in self.prices:
            return
            
        price_data = self.prices[order.symbol]
        
        filled, fill_price, fill_qty, message = self.fill_simulator.simulate_fill(
            order=order,
            market_price=price_data['last'],
            bid=price_data['bid'],
            ask=price_data['ask'],
            volume=price_data['volume'],
            volatility=price_data.get('volatility', 0.02)
        )
        
        if filled:
            self._execute_fill(order, fill_price, fill_qty)
            
    def _execute_fill(self, order: PaperOrder, fill_price: float, fill_qty: float):
        """Execute a fill."""
        # Calculate commission
        commission = max(self.min_commission, fill_qty * self.commission_per_share)
        
        # Record fill
        fill = {
            'fill_id': f"FILL{uuid.uuid4().hex[:8].upper()}",
            'order_id': order.order_id,
            'timestamp': datetime.now(),
            'price': fill_price,
            'quantity': fill_qty,
            'commission': commission
        }
        order.fills.append(fill)
        
        # Update order
        old_filled = order.filled_quantity
        order.filled_quantity += fill_qty
        order.filled_avg_price = (
            (old_filled * order.filled_avg_price + fill_qty * fill_price) /
            order.filled_quantity
        )
        order.commission += commission
        order.updated_at = datetime.now()
        
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now()
        else:
            order.status = OrderStatus.PARTIAL
            
        # Update position
        self._update_position(order.symbol, order.side, fill_qty, fill_price)
        
        # Update cash
        if order.side == OrderSide.BUY:
            self.account.cash -= fill_qty * fill_price + commission
        else:
            self.account.cash += fill_qty * fill_price - commission
            
        # Record trade
        self.trade_history.append({
            'timestamp': datetime.now(),
            'symbol': order.symbol,
            'side': order.side.value,
            'quantity': fill_qty,
            'price': fill_price,
            'commission': commission,
            'order_id': order.order_id
        })
        
        self.account.total_trades += 1
        
        # Activate bracket orders if entry filled
        if order.take_profit_order_id and order.status == OrderStatus.FILLED:
            tp = self.orders.get(order.take_profit_order_id)
            sl = self.orders.get(order.stop_loss_order_id)
            if tp:
                tp.status = OrderStatus.OPEN
            if sl:
                sl.status = OrderStatus.OPEN
                
        # Cancel other bracket order if one fills
        if order.parent_order_id:
            parent = self.orders.get(order.parent_order_id)
            if parent:
                # Cancel the other exit order
                if parent.take_profit_order_id == order.order_id:
                    self._cancel_order_internal(parent.stop_loss_order_id)
                elif parent.stop_loss_order_id == order.order_id:
                    self._cancel_order_internal(parent.take_profit_order_id)
                    
        # Callbacks
        for callback in self.on_fill:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Fill callback error: {e}")
                
    def _update_position(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float
    ):
        """Update position after fill."""
        delta = quantity if side == OrderSide.BUY else -quantity
        
        if symbol in self.positions:
            pos = self.positions[symbol]
            old_qty = pos.quantity
            new_qty = old_qty + delta
            
            if new_qty == 0:
                # Position closed
                realized = (price - pos.avg_cost) * quantity
                if side == OrderSide.SELL:
                    realized = (price - pos.avg_cost) * quantity
                else:
                    realized = (pos.avg_cost - price) * quantity
                    
                pos.realized_pnl += realized
                self.account.total_pnl += realized
                
                if realized > 0:
                    self.account.winning_trades += 1
                else:
                    self.account.losing_trades += 1
                    
                del self.positions[symbol]
                
            elif (old_qty > 0 and new_qty > 0) or (old_qty < 0 and new_qty < 0):
                # Adding to position
                pos.avg_cost = (pos.avg_cost * abs(old_qty) + price * quantity) / abs(new_qty)
                pos.quantity = new_qty
                
            else:
                # Reducing or reversing position
                if abs(delta) <= abs(old_qty):
                    # Just reducing
                    realized = (price - pos.avg_cost) * quantity * (1 if old_qty > 0 else -1)
                    pos.realized_pnl += realized
                    self.account.total_pnl += realized
                    pos.quantity = new_qty
                else:
                    # Closing and reversing
                    close_qty = abs(old_qty)
                    open_qty = abs(delta) - close_qty
                    
                    realized = (price - pos.avg_cost) * close_qty * (1 if old_qty > 0 else -1)
                    pos.realized_pnl += realized
                    self.account.total_pnl += realized
                    
                    pos.quantity = new_qty
                    pos.avg_cost = price
                    
        else:
            # New position
            self.positions[symbol] = PaperPosition(
                symbol=symbol,
                quantity=delta,
                avg_cost=price
            )
            
    def _update_account_value(self):
        """Update total account value."""
        position_value = sum(
            pos.market_value for pos in self.positions.values()
        )
        
        self.account.portfolio_value = self.account.cash + position_value
        
        # Update high water mark and drawdown
        if self.account.portfolio_value > self.account.high_water_mark:
            self.account.high_water_mark = self.account.portfolio_value
            
        self.account.current_drawdown = (
            (self.account.high_water_mark - self.account.portfolio_value) /
            self.account.high_water_mark
        )
        
        self.account.max_drawdown = max(
            self.account.max_drawdown,
            self.account.current_drawdown
        )
        
        # Record equity
        self.equity_history.append((datetime.now(), self.account.portfolio_value))
        
    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get position for symbol."""
        return self.positions.get(symbol)
        
    def get_all_positions(self) -> List[PaperPosition]:
        """Get all positions."""
        return list(self.positions.values())
        
    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Get order by ID."""
        return self.orders.get(order_id)
        
    def get_open_orders(self, symbol: Optional[str] = None) -> List[PaperOrder]:
        """Get open orders."""
        orders = [o for o in self.orders.values() if not o.is_complete]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders
        
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary."""
        return self.account.to_dict()
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if not self.equity_history:
            return {}
            
        equity = pd.Series([e[1] for e in self.equity_history])
        returns = equity.pct_change().dropna()
        
        if len(returns) < 2:
            return {}
            
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        return {
            'total_return': (equity.iloc[-1] / equity.iloc[0] - 1),
            'sharpe_ratio': sharpe,
            'max_drawdown': self.account.max_drawdown,
            'win_rate': self.account.winning_trades / self.account.total_trades if self.account.total_trades > 0 else 0,
            'total_trades': self.account.total_trades,
            'profit_factor': abs(self.account.total_pnl / self.account.losing_trades) if self.account.losing_trades > 0 else 0,
            'avg_trade_pnl': self.account.total_pnl / self.account.total_trades if self.account.total_trades > 0 else 0
        }
        
    def reset(self):
        """Reset paper trading account."""
        with self._lock:
            self.account = PaperAccount(
                account_id=self.account.account_id,
                initial_cash=self.account.initial_cash,
                cash=self.account.initial_cash,
                portfolio_value=self.account.initial_cash,
                high_water_mark=self.account.initial_cash
            )
            self.orders.clear()
            self.positions.clear()
            self.trade_history.clear()
            self.equity_history.clear()
            logger.info("Paper trading account reset")
