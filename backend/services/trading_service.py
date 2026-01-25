"""
QUANT INDUSTRY - Trading Service
Order execution and position management
"""

import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"


class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    strategy: str = ""
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "commission": self.commission,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "strategy": self.strategy,
            "notes": self.notes,
        }


@dataclass
class Position:
    symbol: str
    side: PositionSide
    quantity: int
    avg_price: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_time: datetime = field(default_factory=datetime.now)
    strategy: str = ""

    def update_price(self, price: float):
        self.current_price = price
        self.market_value = price * self.quantity

        cost_basis = self.avg_price * self.quantity
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = self.market_value - cost_basis
        else:
            self.unrealized_pnl = cost_basis - self.market_value

        self.unrealized_pnl_pct = (self.unrealized_pnl / cost_basis * 100) if cost_basis else 0

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "avg_price": self.avg_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "entry_time": self.entry_time.isoformat(),
            "strategy": self.strategy,
        }


@dataclass
class Trade:
    id: str
    symbol: str
    side: OrderSide
    quantity: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    strategy: str
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "strategy": self.strategy,
            "notes": self.notes,
        }


@dataclass
class AccountInfo:
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    day_pnl: float
    day_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float


class TradingService:
    """
    Paper trading service with order management and position tracking
    """

    def __init__(self, initial_capital: float = 100000, db_path: str = None):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.equity = initial_capital

        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []

        self.lock = threading.Lock()

        # Database for persistence
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "trades.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        logger.info(f"TradingService initialized with ${initial_capital:,.2f}")

    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                limit_price REAL,
                stop_price REAL,
                status TEXT NOT NULL,
                filled_quantity INTEGER DEFAULT 0,
                avg_fill_price REAL DEFAULT 0,
                commission REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                strategy TEXT,
                notes TEXT
            )
        """)

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                strategy TEXT,
                notes TEXT
            )
        """)

        # Positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                entry_time TEXT NOT NULL,
                strategy TEXT,
                realized_pnl REAL DEFAULT 0
            )
        """)

        # Daily P&L table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date TEXT PRIMARY KEY,
                starting_equity REAL,
                ending_equity REAL,
                pnl REAL,
                pnl_pct REAL,
                trades_count INTEGER
            )
        """)

        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(exit_time)")

        conn.commit()
        conn.close()

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None,
        stop_price: float = None,
        strategy: str = "",
        notes: str = ""
    ) -> Order:
        """Submit a new order"""
        with self.lock:
            order = Order(
                id=str(uuid.uuid4())[:8],
                symbol=symbol.upper(),
                side=side,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                stop_price=stop_price,
                strategy=strategy,
                notes=notes
            )

            self.orders[order.id] = order
            self._save_order(order)

            # For market orders in paper trading, execute immediately
            if order_type == OrderType.MARKET:
                self._execute_order(order)

            logger.info(f"Order submitted: {order.id} {side.value} {quantity} {symbol}")
            return order

    def _execute_order(self, order: Order, fill_price: float = None):
        """Execute an order (paper trading simulation)"""
        from .data_service import get_data_service

        # Get current price
        if fill_price is None:
            data_service = get_data_service()
            quote = data_service.get_quote(order.symbol)
            fill_price = quote.ask if order.side == OrderSide.BUY else quote.bid

        # Calculate commission (simulate broker commission)
        commission = 0.0  # Free commissions for paper trading

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.commission = commission
        order.updated_at = datetime.now()

        # Update position
        self._update_position(order, fill_price)

        # Update cash
        trade_value = fill_price * order.quantity
        if order.side == OrderSide.BUY:
            self.cash -= trade_value + commission
        else:
            self.cash += trade_value - commission

        self._save_order(order)
        logger.info(f"Order filled: {order.id} @ ${fill_price:.2f}")

    def _update_position(self, order: Order, fill_price: float):
        """Update position based on filled order"""
        symbol = order.symbol

        if symbol not in self.positions:
            # New position
            if order.side == OrderSide.BUY:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    quantity=order.quantity,
                    avg_price=fill_price,
                    current_price=fill_price,
                    entry_time=datetime.now(),
                    strategy=order.strategy
                )
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side=PositionSide.SHORT,
                    quantity=order.quantity,
                    avg_price=fill_price,
                    current_price=fill_price,
                    entry_time=datetime.now(),
                    strategy=order.strategy
                )
        else:
            pos = self.positions[symbol]

            if (order.side == OrderSide.BUY and pos.side == PositionSide.LONG) or \
               (order.side == OrderSide.SELL and pos.side == PositionSide.SHORT):
                # Adding to position
                total_value = pos.avg_price * pos.quantity + fill_price * order.quantity
                pos.quantity += order.quantity
                pos.avg_price = total_value / pos.quantity
            # Reducing/closing position
            elif order.quantity >= pos.quantity:
                # Close position
                pnl = self._calculate_pnl(pos, fill_price, pos.quantity)
                self._record_trade(pos, fill_price, pos.quantity, pnl)
                pos.realized_pnl += pnl

                remaining = order.quantity - pos.quantity
                if remaining > 0:
                    # Reverse position
                    new_side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        side=new_side,
                        quantity=remaining,
                        avg_price=fill_price,
                        current_price=fill_price,
                        entry_time=datetime.now(),
                        strategy=order.strategy
                    )
                else:
                    del self.positions[symbol]
            else:
                # Partial close
                pnl = self._calculate_pnl(pos, fill_price, order.quantity)
                self._record_trade(pos, fill_price, order.quantity, pnl)
                pos.realized_pnl += pnl
                pos.quantity -= order.quantity

            pos.update_price(fill_price)

        self._save_positions()

    def _calculate_pnl(self, position: Position, exit_price: float, quantity: int) -> float:
        """Calculate P&L for closing a position"""
        if position.side == PositionSide.LONG:
            return (exit_price - position.avg_price) * quantity
        else:
            return (position.avg_price - exit_price) * quantity

    def _record_trade(self, position: Position, exit_price: float, quantity: int, pnl: float):
        """Record a completed trade"""
        trade = Trade(
            id=str(uuid.uuid4())[:8],
            symbol=position.symbol,
            side=OrderSide.BUY if position.side == PositionSide.LONG else OrderSide.SELL,
            quantity=quantity,
            entry_price=position.avg_price,
            exit_price=exit_price,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            pnl=pnl,
            pnl_pct=(pnl / (position.avg_price * quantity)) * 100,
            strategy=position.strategy
        )
        self.trades.append(trade)
        self._save_trade(trade)
        logger.info(f"Trade recorded: {trade.symbol} P&L: ${pnl:.2f}")

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        with self.lock:
            if order_id not in self.orders:
                return False

            order = self.orders[order_id]
            if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                return False

            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            self._save_order(order)

            logger.info(f"Order cancelled: {order_id}")
            return True

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol"""
        return self.positions.get(symbol.upper())

    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return list(self.positions.values())

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self.orders.get(order_id)

    def get_orders(self, status: OrderStatus = None) -> List[Order]:
        """Get orders filtered by status"""
        orders = list(self.orders.values())
        if status:
            orders = [o for o in orders if o.status == status]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def get_trades(self, limit: int = 100) -> List[Trade]:
        """Get recent trades"""
        return sorted(self.trades, key=lambda t: t.exit_time, reverse=True)[:limit]

    def get_account_info(self) -> AccountInfo:
        """Get account information"""
        from .data_service import get_data_service

        # Update position prices
        data_service = get_data_service()
        symbols = [p.symbol for p in self.positions.values()]
        if symbols:
            quotes = data_service.get_quotes(symbols)
            for pos in self.positions.values():
                if pos.symbol in quotes:
                    pos.update_price(quotes[pos.symbol].price)

        # Calculate totals
        portfolio_value = sum(p.market_value for p in self.positions.values())
        equity = self.cash + portfolio_value
        unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        realized_pnl = sum(p.realized_pnl for p in self.positions.values())

        total_pnl = equity - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital) * 100

        return AccountInfo(
            equity=equity,
            cash=self.cash,
            buying_power=self.cash,
            portfolio_value=portfolio_value,
            day_pnl=unrealized_pnl,  # Simplified
            day_pnl_pct=(unrealized_pnl / self.initial_capital) * 100,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct
        )

    def _save_order(self, order: Order):
        """Save order to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO orders
            (id, symbol, side, order_type, quantity, limit_price, stop_price,
             status, filled_quantity, avg_fill_price, commission, created_at,
             updated_at, strategy, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order.id, order.symbol, order.side.value, order.order_type.value,
            order.quantity, order.limit_price, order.stop_price, order.status.value,
            order.filled_quantity, order.avg_fill_price, order.commission,
            order.created_at.isoformat(), order.updated_at.isoformat(),
            order.strategy, order.notes
        ))
        conn.commit()
        conn.close()

    def _save_trade(self, trade: Trade):
        """Save trade to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trades
            (id, symbol, side, quantity, entry_price, exit_price, entry_time,
             exit_time, pnl, pnl_pct, strategy, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.id, trade.symbol, trade.side.value, trade.quantity,
            trade.entry_price, trade.exit_price, trade.entry_time.isoformat(),
            trade.exit_time.isoformat(), trade.pnl, trade.pnl_pct,
            trade.strategy, trade.notes
        ))
        conn.commit()
        conn.close()

    def _save_positions(self):
        """Save positions to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Clear existing positions
        cursor.execute("DELETE FROM positions")

        # Insert current positions
        for pos in self.positions.values():
            cursor.execute("""
                INSERT INTO positions
                (symbol, side, quantity, avg_price, stop_loss, take_profit,
                 entry_time, strategy, realized_pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pos.symbol, pos.side.value, pos.quantity, pos.avg_price,
                pos.stop_loss, pos.take_profit, pos.entry_time.isoformat(),
                pos.strategy, pos.realized_pnl
            ))

        conn.commit()
        conn.close()


# Singleton instance
_trading_service: Optional[TradingService] = None

def get_trading_service() -> TradingService:
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingService()
    return _trading_service
