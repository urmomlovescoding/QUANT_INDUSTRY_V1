"""
Portfolio Manager
=================
Real-time portfolio tracking, position management, and risk monitoring.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import pandas as pd
import numpy as np
from collections import defaultdict
import logging
import asyncio

logger = logging.getLogger(__name__)


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """Individual position in portfolio"""
    symbol: str
    quantity: float
    avg_entry_price: float
    side: PositionSide
    opened_at: datetime = field(default_factory=datetime.now)
    
    # Updated values
    current_price: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Metadata
    strategy_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    @property
    def market_value(self) -> float:
        """Current market value of position"""
        value = self.quantity * self.current_price
        return value if self.side == PositionSide.LONG else -value
    
    @property
    def cost_basis(self) -> float:
        """Original cost of position"""
        return self.quantity * self.avg_entry_price
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L"""
        if self.side == PositionSide.LONG:
            return self.quantity * (self.current_price - self.avg_entry_price)
        else:
            return self.quantity * (self.avg_entry_price - self.current_price)
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as percentage"""
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis
    
    @property
    def holding_period(self) -> timedelta:
        """Time since position opened"""
        return datetime.now() - self.opened_at
    
    def to_dict(self) -> dict:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'side': self.side.value,
            'avg_entry_price': self.avg_entry_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'cost_basis': self.cost_basis,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'opened_at': self.opened_at.isoformat(),
            'holding_period_days': self.holding_period.days,
            'strategy_id': self.strategy_id,
        }


@dataclass
class Trade:
    """Executed trade record"""
    trade_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0
    slippage: float = 0.0
    
    # P&L for closing trades
    realized_pnl: Optional[float] = None
    
    # Metadata
    strategy_id: Optional[str] = None
    order_id: Optional[str] = None
    
    @property
    def gross_value(self) -> float:
        return self.quantity * self.price
    
    @property
    def net_value(self) -> float:
        return self.gross_value - self.commission - abs(self.slippage)
    
    def to_dict(self) -> dict:
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'gross_value': self.gross_value,
            'commission': self.commission,
            'slippage': self.slippage,
            'net_value': self.net_value,
            'realized_pnl': self.realized_pnl,
            'timestamp': self.timestamp.isoformat(),
            'strategy_id': self.strategy_id,
        }


@dataclass
class RiskMetrics:
    """Portfolio risk metrics"""
    # Value metrics
    total_value: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    
    # P&L
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    
    # Risk metrics
    var_95: float = 0.0  # 95% Value at Risk
    var_99: float = 0.0  # 99% Value at Risk
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    
    # Exposure
    gross_exposure: float = 0.0  # Long + |Short|
    net_exposure: float = 0.0    # Long - |Short|
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    leverage: float = 0.0
    
    # Concentration
    largest_position_pct: float = 0.0
    top_5_concentration: float = 0.0
    position_count: int = 0
    
    # Performance
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'value': {
                'total': self.total_value,
                'cash': self.cash,
                'positions': self.positions_value,
            },
            'pnl': {
                'unrealized': self.unrealized_pnl,
                'realized': self.realized_pnl,
                'total': self.total_pnl,
            },
            'risk': {
                'var_95': self.var_95,
                'var_99': self.var_99,
                'max_drawdown': self.max_drawdown,
                'current_drawdown': self.current_drawdown,
            },
            'exposure': {
                'gross': self.gross_exposure,
                'net': self.net_exposure,
                'long': self.long_exposure,
                'short': self.short_exposure,
                'leverage': self.leverage,
            },
            'concentration': {
                'largest_position_pct': self.largest_position_pct,
                'top_5_pct': self.top_5_concentration,
                'position_count': self.position_count,
            },
            'performance': {
                'sharpe': self.sharpe_ratio,
                'sortino': self.sortino_ratio,
                'beta': self.beta,
                'alpha': self.alpha,
            },
            'timestamp': self.timestamp.isoformat(),
        }


class PortfolioManager:
    """
    Central portfolio management system.
    
    Responsibilities:
    - Position tracking and management
    - Trade execution and recording
    - P&L calculation
    - Risk metrics computation
    - Portfolio rebalancing
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        price_provider: Callable[[str], float] = None,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.price_provider = price_provider or (lambda x: 0)
        
        # State
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_history: List[tuple] = []  # (timestamp, equity)
        self.realized_pnl = 0.0
        
        # Callbacks
        self.on_trade: Optional[Callable[[Trade], None]] = None
        self.on_position_change: Optional[Callable[[Position], None]] = None
        
        # Risk limits
        self.max_position_size = 0.1  # 10% max
        self.max_drawdown_limit = 0.2  # 20% stop
        self.max_leverage = 1.0  # No leverage
        
        logger.info(f"Portfolio initialized with ${initial_capital:,.2f}")
    
    @property
    def equity(self) -> float:
        """Total portfolio value"""
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value
    
    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L"""
        return sum(p.unrealized_pnl for p in self.positions.values())
    
    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl
    
    def update_prices(self, prices: Dict[str, float]):
        """Update position prices"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price
                self.positions[symbol].last_updated = datetime.now()
        
        # Record equity
        self.equity_history.append((datetime.now(), self.equity))
    
    def execute_trade(
        self,
        symbol: str,
        quantity: float,
        side: str,  # 'buy' or 'sell'
        price: Optional[float] = None,
        strategy_id: Optional[str] = None,
    ) -> Optional[Trade]:
        """
        Execute a trade.
        
        Args:
            symbol: Symbol to trade
            quantity: Number of shares (always positive)
            side: 'buy' or 'sell'
            price: Execution price (uses price_provider if not given)
            strategy_id: Associated strategy
            
        Returns:
            Trade record if successful
        """
        quantity = abs(quantity)
        if quantity == 0:
            return None
        
        # Get execution price
        if price is None:
            price = self.price_provider(symbol)
            if price <= 0:
                logger.error(f"Invalid price for {symbol}")
                return None
        
        # Apply slippage
        if side == 'buy':
            exec_price = price * (1 + self.slippage_rate)
        else:
            exec_price = price * (1 - self.slippage_rate)
        
        # Calculate costs
        gross_value = quantity * exec_price
        commission = gross_value * self.commission_rate
        slippage = abs(exec_price - price) * quantity
        
        # Check capital for buys
        if side == 'buy' and gross_value + commission > self.cash:
            logger.warning(f"Insufficient cash for {symbol} buy")
            return None
        
        # Create trade record
        import uuid
        trade = Trade(
            trade_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=exec_price,
            timestamp=datetime.now(),
            commission=commission,
            slippage=slippage,
            strategy_id=strategy_id,
        )
        
        # Update position
        realized_pnl = self._update_position(trade)
        trade.realized_pnl = realized_pnl
        
        # Record trade
        self.trades.append(trade)
        
        # Callback
        if self.on_trade:
            self.on_trade(trade)
        
        logger.info(
            f"Trade executed: {side.upper()} {quantity} {symbol} @ ${exec_price:.2f}"
            f" (commission: ${commission:.2f})"
        )
        
        return trade
    
    def _update_position(self, trade: Trade) -> float:
        """Update position after trade, return realized P&L"""
        symbol = trade.symbol
        quantity = trade.quantity
        price = trade.price
        realized_pnl = 0.0
        
        if trade.side == 'buy':
            # Buying
            self.cash -= trade.net_value
            
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.side == PositionSide.LONG:
                    # Adding to long
                    total_cost = pos.cost_basis + (quantity * price)
                    total_qty = pos.quantity + quantity
                    pos.avg_entry_price = total_cost / total_qty
                    pos.quantity = total_qty
                else:
                    # Covering short
                    if quantity >= pos.quantity:
                        # Close and possibly reverse
                        realized_pnl = pos.quantity * (pos.avg_entry_price - price)
                        remaining = quantity - pos.quantity
                        
                        if remaining > 0:
                            # Open long with remaining
                            self.positions[symbol] = Position(
                                symbol=symbol,
                                quantity=remaining,
                                avg_entry_price=price,
                                side=PositionSide.LONG,
                                current_price=price,
                                strategy_id=trade.strategy_id,
                            )
                        else:
                            del self.positions[symbol]
                    else:
                        # Partial cover
                        realized_pnl = quantity * (pos.avg_entry_price - price)
                        pos.quantity -= quantity
            else:
                # New long position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    avg_entry_price=price,
                    side=PositionSide.LONG,
                    current_price=price,
                    strategy_id=trade.strategy_id,
                )
        
        else:  # sell
            self.cash += trade.net_value
            
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.side == PositionSide.LONG:
                    # Selling long
                    if quantity >= pos.quantity:
                        # Close and possibly reverse
                        realized_pnl = pos.quantity * (price - pos.avg_entry_price)
                        remaining = quantity - pos.quantity
                        
                        if remaining > 0:
                            # Open short with remaining
                            self.positions[symbol] = Position(
                                symbol=symbol,
                                quantity=remaining,
                                avg_entry_price=price,
                                side=PositionSide.SHORT,
                                current_price=price,
                                strategy_id=trade.strategy_id,
                            )
                        else:
                            del self.positions[symbol]
                    else:
                        # Partial sell
                        realized_pnl = quantity * (price - pos.avg_entry_price)
                        pos.quantity -= quantity
                else:
                    # Adding to short
                    total_value = pos.cost_basis + (quantity * price)
                    total_qty = pos.quantity + quantity
                    pos.avg_entry_price = total_value / total_qty
                    pos.quantity = total_qty
            else:
                # New short position
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    avg_entry_price=price,
                    side=PositionSide.SHORT,
                    current_price=price,
                    strategy_id=trade.strategy_id,
                )
        
        # Update realized P&L
        self.realized_pnl += realized_pnl
        
        # Position change callback
        if symbol in self.positions and self.on_position_change:
            self.on_position_change(self.positions[symbol])
        
        return realized_pnl
    
    def close_position(self, symbol: str, price: Optional[float] = None) -> Optional[Trade]:
        """Close entire position in a symbol"""
        if symbol not in self.positions:
            return None
        
        pos = self.positions[symbol]
        side = 'sell' if pos.side == PositionSide.LONG else 'buy'
        
        return self.execute_trade(
            symbol=symbol,
            quantity=pos.quantity,
            side=side,
            price=price,
            strategy_id=pos.strategy_id,
        )
    
    def close_all_positions(self) -> List[Trade]:
        """Close all positions"""
        trades = []
        for symbol in list(self.positions.keys()):
            trade = self.close_position(symbol)
            if trade:
                trades.append(trade)
        return trades
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol"""
        return self.positions.get(symbol)
    
    def get_positions(self) -> List[Position]:
        """Get all positions"""
        return list(self.positions.values())
    
    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        metrics = RiskMetrics()
        
        # Value metrics
        metrics.total_value = self.equity
        metrics.cash = self.cash
        metrics.positions_value = self.equity - self.cash
        
        # P&L
        metrics.unrealized_pnl = self.unrealized_pnl
        metrics.realized_pnl = self.realized_pnl
        metrics.total_pnl = self.total_pnl
        
        # Exposure
        long_value = sum(
            p.market_value for p in self.positions.values()
            if p.side == PositionSide.LONG
        )
        short_value = sum(
            abs(p.market_value) for p in self.positions.values()
            if p.side == PositionSide.SHORT
        )
        
        metrics.long_exposure = long_value / metrics.total_value if metrics.total_value > 0 else 0
        metrics.short_exposure = short_value / metrics.total_value if metrics.total_value > 0 else 0
        metrics.gross_exposure = metrics.long_exposure + metrics.short_exposure
        metrics.net_exposure = metrics.long_exposure - metrics.short_exposure
        metrics.leverage = metrics.gross_exposure
        
        # Concentration
        metrics.position_count = len(self.positions)
        if self.positions:
            position_pcts = sorted(
                [abs(p.market_value) / metrics.total_value for p in self.positions.values()],
                reverse=True
            )
            metrics.largest_position_pct = position_pcts[0] if position_pcts else 0
            metrics.top_5_concentration = sum(position_pcts[:5])
        
        # Drawdown
        if self.equity_history:
            equities = [e for _, e in self.equity_history]
            peak = max(equities)
            metrics.max_drawdown = (peak - min(equities)) / peak if peak > 0 else 0
            metrics.current_drawdown = (peak - self.equity) / peak if peak > 0 else 0
        
        # VaR (simple historical)
        if len(self.equity_history) > 20:
            equities = pd.Series([e for _, e in self.equity_history])
            returns = equities.pct_change().dropna()
            metrics.var_95 = returns.quantile(0.05) * metrics.total_value
            metrics.var_99 = returns.quantile(0.01) * metrics.total_value
        
        return metrics
    
    def get_trade_stats(self) -> dict:
        """Calculate trading statistics"""
        if not self.trades:
            return {}
        
        # Filter closing trades (have realized P&L)
        closing_trades = [t for t in self.trades if t.realized_pnl is not None]
        
        if not closing_trades:
            return {
                'total_trades': len(self.trades),
                'closing_trades': 0,
            }
        
        pnls = [t.realized_pnl for t in closing_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        return {
            'total_trades': len(self.trades),
            'closing_trades': len(closing_trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(closing_trades) if closing_trades else 0,
            'avg_win': np.mean(wins) if wins else 0,
            'avg_loss': np.mean(losses) if losses else 0,
            'profit_factor': abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float('inf'),
            'total_commission': sum(t.commission for t in self.trades),
            'avg_trade_duration_days': np.mean([
                t.timestamp.day for t in closing_trades
            ]) if closing_trades else 0,
        }
    
    def to_dict(self) -> dict:
        """Serialize portfolio state"""
        return {
            'initial_capital': self.initial_capital,
            'cash': self.cash,
            'equity': self.equity,
            'positions': [p.to_dict() for p in self.positions.values()],
            'total_pnl': self.total_pnl,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'risk_metrics': self.calculate_risk_metrics().to_dict(),
            'trade_stats': self.get_trade_stats(),
        }
