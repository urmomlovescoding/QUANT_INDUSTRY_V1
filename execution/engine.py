"""
Execution Engine
================
Connects the TradingBrain to live/paper trading with proper
order management, risk controls, and performance tracking.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from collections import deque
import numpy as np
import torch

# Import slippage model from backend
try:
    from backend.execution.execution_algorithms import (
        AlmgrenChrissSlippageModel,
        SlippageEstimate
    )
    HAS_SLIPPAGE_MODEL = True
except ImportError:
    HAS_SLIPPAGE_MODEL = False
    AlmgrenChrissSlippageModel = None
    SlippageEstimate = None

logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


@dataclass
class Order:
    """Order representation."""
    id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    filled_avg_price: float = 0.0  # Average fill price
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    client_order_id: Optional[str] = None
    time_in_force: TimeInForce = TimeInForce.DAY

    @property
    def order_id(self) -> str:
        """Alias for id for broker compatibility."""
        return self.id

    @property
    def remaining_quantity(self) -> float:
        """Calculate remaining quantity to fill."""
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize order to dictionary."""
        return {
            'order_id': self.id,
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'remaining_quantity': self.remaining_quantity,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.metadata,
        }


@dataclass
class Fill:
    """Order fill representation."""
    fill_id: str
    order_id: str
    symbol: str
    quantity: float
    price: float
    side: OrderSide
    timestamp: datetime
    commission: float = 0.0
    exchange: str = ""


@dataclass
class Position:
    """Current position in an asset."""
    symbol: str
    quantity: float  # Positive = long, negative = short
    avg_entry_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionConfig:
    """Execution engine configuration."""
    # Position limits
    max_position_size: float = 1.0  # Max position as fraction of portfolio
    max_single_trade: float = 0.25  # Max single trade size
    
    # Risk controls
    max_drawdown: float = 0.10  # 10% max drawdown
    daily_loss_limit: float = 0.03  # 3% daily loss limit
    max_open_orders: int = 10
    
    # Execution
    slippage_estimate: float = 0.001  # 0.1% slippage (legacy fallback)
    min_trade_interval: float = 60.0  # Minimum seconds between trades
    use_limit_orders: bool = True
    limit_offset_bps: float = 5.0  # Basis points from mid
    
    # Almgren-Chriss Slippage Model Parameters
    use_almgren_chriss: bool = True  # Use sophisticated slippage model
    slippage_eta: float = 0.10  # Temporary impact coefficient (0.05-0.30)
    slippage_gamma: float = 0.10  # Permanent impact coefficient (0.05-0.20)
    slippage_min_bps: float = 0.5  # Floor for bid-ask spread
    default_daily_volume: float = 50000.0  # Default ADV if unknown
    default_volatility: float = 0.02  # Default daily vol (2%)
    
    # Circuit breaker
    circuit_breaker_threshold: float = 0.05  # 5% rapid loss
    circuit_breaker_window: int = 300  # 5 minutes
    circuit_breaker_cooldown: int = 1800  # 30 minutes


class RiskGuard:
    """
    Real-time risk monitoring and circuit breaker.
    
    Monitors:
    - Position limits
    - Drawdown
    - Daily P&L
    - Rapid loss detection
    """
    
    def __init__(self, config: ExecutionConfig):
        self.config = config
        
        # State
        self.peak_value = 0.0
        self.daily_start_value = 0.0
        self.daily_pnl = 0.0
        self.circuit_breaker_active = False
        self.circuit_breaker_until: Optional[datetime] = None
        
        # Recent P&L for rapid loss detection
        self.pnl_history = deque(maxlen=1000)
        
    def update_portfolio_value(self, value: float, timestamp: datetime):
        """Update with new portfolio value."""
        # Update peak
        if value > self.peak_value:
            self.peak_value = value
        
        # Check drawdown
        drawdown = (self.peak_value - value) / self.peak_value if self.peak_value > 0 else 0
        if drawdown > self.config.max_drawdown:
            logger.warning(f"Drawdown limit hit: {drawdown:.2%}")
            self._trigger_circuit_breaker("max_drawdown")
        
        # Track P&L
        self.pnl_history.append((timestamp, value))
        
        # Check rapid loss
        self._check_rapid_loss(timestamp)
    
    def check_daily_limit(self, current_value: float) -> bool:
        """Check if daily loss limit is hit."""
        if self.daily_start_value > 0:
            daily_return = (current_value - self.daily_start_value) / self.daily_start_value
            if daily_return < -self.config.daily_loss_limit:
                logger.warning(f"Daily loss limit hit: {daily_return:.2%}")
                return False
        return True
    
    def reset_daily(self, portfolio_value: float):
        """Reset daily tracking (call at market open)."""
        self.daily_start_value = portfolio_value
        self.daily_pnl = 0.0
    
    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed."""
        if self.circuit_breaker_active:
            if datetime.now() > self.circuit_breaker_until:
                self.circuit_breaker_active = False
                logger.info("Circuit breaker cooldown complete")
            else:
                remaining = (self.circuit_breaker_until - datetime.now()).seconds
                return False, f"Circuit breaker active ({remaining}s remaining)"
        
        return True, "OK"
    
    def validate_order(
        self,
        order: Order,
        current_position: float,
        portfolio_value: float
    ) -> tuple[bool, str]:
        """Validate order against risk limits."""
        can_trade, reason = self.can_trade()
        if not can_trade:
            return False, reason
        
        # Check position limit
        if order.side == OrderSide.BUY:
            new_position = current_position + order.quantity
        else:
            new_position = current_position - order.quantity
        
        position_pct = abs(new_position) / portfolio_value if portfolio_value > 0 else 0
        if position_pct > self.config.max_position_size:
            return False, f"Position limit exceeded: {position_pct:.2%} > {self.config.max_position_size:.2%}"
        
        # Check single trade size
        trade_pct = order.quantity / portfolio_value if portfolio_value > 0 else 0
        if trade_pct > self.config.max_single_trade:
            return False, f"Trade size limit exceeded: {trade_pct:.2%}"
        
        return True, "OK"
    
    def _check_rapid_loss(self, current_time: datetime):
        """Check for rapid losses triggering circuit breaker."""
        if len(self.pnl_history) < 2:
            return
        
        window_start = current_time - timedelta(seconds=self.config.circuit_breaker_window)
        
        # Get values in window
        values_in_window = [v for t, v in self.pnl_history if t >= window_start]
        
        if len(values_in_window) >= 2:
            start_value = values_in_window[0]
            current_value = values_in_window[-1]
            
            if start_value > 0:
                window_return = (current_value - start_value) / start_value
                if window_return < -self.config.circuit_breaker_threshold:
                    logger.warning(f"Rapid loss detected: {window_return:.2%} in {self.config.circuit_breaker_window}s")
                    self._trigger_circuit_breaker("rapid_loss")
    
    def _trigger_circuit_breaker(self, reason: str):
        """Trigger circuit breaker."""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(seconds=self.config.circuit_breaker_cooldown)
        logger.error(f"CIRCUIT BREAKER TRIGGERED: {reason}. Cooldown until {self.circuit_breaker_until}")


class ExecutionEngine:
    """
    Main execution engine connecting TradingBrain to markets.
    
    Responsibilities:
    - Receive signals from TradingBrain
    - Apply risk controls
    - Generate and manage orders
    - Track positions and P&L
    - Feed performance back to meta-learner
    """
    
    def __init__(
        self,
        brain: Any,  # TradingBrain instance
        broker: Any,  # Broker interface
        config: Optional[ExecutionConfig] = None
    ):
        self.brain = brain
        self.broker = broker
        self.config = config or ExecutionConfig()
        
        # Risk management
        self.risk_guard = RiskGuard(self.config)
        
        # Initialize Almgren-Chriss slippage model
        self.slippage_model = None
        if HAS_SLIPPAGE_MODEL and self.config.use_almgren_chriss:
            self.slippage_model = AlmgrenChrissSlippageModel(
                eta=self.config.slippage_eta,
                gamma=self.config.slippage_gamma,
                min_slippage_bps=self.config.slippage_min_bps
            )
            logger.info(
                f"Almgren-Chriss slippage model initialized: "
                f"eta={self.config.slippage_eta}, gamma={self.config.slippage_gamma}"
            )
        else:
            logger.warning("Slippage model unavailable, using fixed estimate")
        
        # Market data cache for slippage calculations
        self._volume_cache: Dict[str, float] = {}  # symbol -> daily volume
        self._volatility_cache: Dict[str, float] = {}  # symbol -> daily vol
        
        # State
        self.positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        self.last_trade_time: Dict[str, datetime] = {}
        
        # Performance tracking
        self.trades: List[Dict] = []
        self.equity_curve: List[tuple[datetime, float]] = []
        
        # Slippage tracking for analysis
        self.total_slippage_dollars: float = 0.0
        self.slippage_history: List[Dict] = []
        
        # Running state
        self.running = False
        self._order_counter = 0
    
    async def start(self):
        """Start the execution engine."""
        self.running = True
        logger.info("Execution engine started")
        
        # Initialize daily tracking
        portfolio_value = await self._get_portfolio_value()
        self.risk_guard.reset_daily(portfolio_value)
        self.risk_guard.peak_value = portfolio_value
    
    async def stop(self):
        """Stop the execution engine."""
        self.running = False
        
        # Cancel pending orders
        for order_id in list(self.pending_orders.keys()):
            await self.cancel_order(order_id)
        
        logger.info("Execution engine stopped")
    
    async def process_signal(
        self,
        symbol: str,
        market_data: torch.Tensor,
        current_price: float
    ) -> Optional[Order]:
        """
        Process a trading signal from the brain.
        
        Args:
            symbol: Trading symbol
            market_data: Recent market data for the brain
            current_price: Current market price
            
        Returns:
            Executed order if any
        """
        if not self.running:
            return None
        
        # Check if we can trade
        can_trade, reason = self.risk_guard.can_trade()
        if not can_trade:
            logger.debug(f"Trading blocked: {reason}")
            return None
        
        # Check trade interval
        if symbol in self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time[symbol]).total_seconds()
            if elapsed < self.config.min_trade_interval:
                return None
        
        # Get signal from brain
        signal = self.brain.get_trading_signal(
            market_data,
            current_position=self._get_position_pct(symbol)
        )
        
        # Decide on action
        if signal['confidence'] < 0.3:
            logger.debug(f"Low confidence signal ({signal['confidence']:.2f}), skipping")
            return None
        
        # Calculate order
        order = await self._signal_to_order(symbol, signal, current_price)
        
        if order is None:
            return None
        
        # Validate through risk guard
        portfolio_value = await self._get_portfolio_value()
        current_pos = self.positions.get(symbol, Position(symbol, 0, 0)).quantity
        
        valid, reason = self.risk_guard.validate_order(order, current_pos, portfolio_value)
        if not valid:
            logger.warning(f"Order rejected by risk guard: {reason}")
            return None
        
        # Submit order
        filled_order = await self.submit_order(order)
        
        if filled_order and filled_order.status == OrderStatus.FILLED:
            self.last_trade_time[symbol] = datetime.now()
            
            # Log trade
            self._record_trade(filled_order, signal)
            
            # Update meta-learner
            self._update_brain_performance()
        
        return filled_order
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to broker with slippage estimation.
        
        The Almgren-Chriss model estimates expected slippage BEFORE execution,
        allowing for better decision-making and performance tracking.
        """
        order.status = OrderStatus.SUBMITTED
        self.pending_orders[order.id] = order
        
        # Estimate expected slippage BEFORE execution
        expected_slippage = await self._estimate_slippage(order)
        order.metadata['expected_slippage_bps'] = expected_slippage.total_slippage_bps if expected_slippage else 0
        order.metadata['expected_slippage_dollars'] = expected_slippage.total_slippage_dollars if expected_slippage else 0
        order.metadata['participation_rate'] = expected_slippage.participation_rate if expected_slippage else 0
        
        # Log pre-trade analysis
        if expected_slippage and expected_slippage.total_slippage_bps > 5.0:
            logger.warning(
                f"High expected slippage for {order.symbol}: "
                f"{expected_slippage.total_slippage_bps:.1f} bps "
                f"(${expected_slippage.total_slippage_dollars:.2f})"
            )
        
        try:
            # Call broker API
            result = await self.broker.submit_order(
                symbol=order.symbol,
                side=order.side.value,
                quantity=order.quantity,
                order_type=order.order_type.value,
                limit_price=order.limit_price,
                stop_price=order.stop_price
            )
            
            # Update order from result
            order.filled_quantity = result.get('filled_quantity', order.quantity)
            order.filled_price = result.get('filled_price', order.limit_price or 0)
            order.status = OrderStatus.FILLED if order.filled_quantity >= order.quantity else OrderStatus.PARTIAL
            order.updated_at = datetime.now()
            
            # Calculate realized slippage (if we have expected price)
            expected_price = order.limit_price or order.metadata.get('expected_price', order.filled_price)
            if expected_price > 0 and order.filled_price > 0:
                if order.side == OrderSide.BUY:
                    realized_slippage_bps = (order.filled_price - expected_price) / expected_price * 10000
                else:
                    realized_slippage_bps = (expected_price - order.filled_price) / expected_price * 10000
                
                order.metadata['realized_slippage_bps'] = realized_slippage_bps
                
                # Track total slippage
                notional = order.filled_price * order.filled_quantity
                realized_slippage_dollars = notional * abs(realized_slippage_bps) / 10000
                self.total_slippage_dollars += realized_slippage_dollars
                
                # Log slippage history for analysis
                self.slippage_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'symbol': order.symbol,
                    'side': order.side.value,
                    'quantity': order.filled_quantity,
                    'expected_bps': order.metadata.get('expected_slippage_bps', 0),
                    'realized_bps': realized_slippage_bps,
                    'expected_dollars': order.metadata.get('expected_slippage_dollars', 0),
                    'realized_dollars': realized_slippage_dollars,
                })
            
            # Update position
            self._update_position(order)
            
            logger.info(
                f"Order filled: {order.side.value} {order.quantity} {order.symbol} @ {order.filled_price} "
                f"(slippage: {order.metadata.get('realized_slippage_bps', 0):.1f} bps)"
            )
            
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.metadata['reject_reason'] = str(e)
            logger.error(f"Order rejected: {e}")
        
        finally:
            del self.pending_orders[order.id]
            self.order_history.append(order)
        
        return order
    
    async def _estimate_slippage(self, order: Order) -> Optional[SlippageEstimate]:
        """
        Estimate expected slippage using Almgren-Chriss model.
        
        Uses cached volume and volatility data, falling back to defaults.
        """
        if not self.slippage_model:
            return None
        
        # Get market data for the symbol
        daily_volume = self._volume_cache.get(
            order.symbol, 
            self.config.default_daily_volume
        )
        volatility = self._volatility_cache.get(
            order.symbol,
            self.config.default_volatility
        )
        
        # Get current price
        price = order.limit_price or order.metadata.get('expected_price', 0)
        if price <= 0:
            # Try to get from broker or use a fallback
            try:
                quote = await self.broker.get_quote(order.symbol)
                price = quote.get('mid', quote.get('last', 100.0))
            except Exception:
                price = 100.0  # Fallback
        
        # Calculate slippage
        estimate = self.slippage_model.calculate_slippage(
            order_size=order.quantity,
            daily_volume=daily_volume,
            volatility=volatility,
            price=price
        )
        
        return estimate
    
    def update_market_data(self, symbol: str, daily_volume: float, volatility: float):
        """
        Update cached market data for slippage estimation.
        
        Call this with real market data to improve slippage accuracy.
        
        Args:
            symbol: Trading symbol
            daily_volume: Average daily volume
            volatility: Daily volatility (decimal, e.g., 0.02 for 2%)
        """
        self._volume_cache[symbol] = daily_volume
        self._volatility_cache[symbol] = volatility
    
    def get_slippage_report(self) -> Dict[str, Any]:
        """
        Get slippage analysis report.
        
        Returns summary of slippage performance including:
        - Total slippage in dollars
        - Average slippage in bps
        - Model accuracy (expected vs realized)
        """
        if not self.slippage_history:
            return {'total_slippage_dollars': 0, 'average_slippage_bps': 0}
        
        total_expected_bps = sum(s['expected_bps'] for s in self.slippage_history)
        total_realized_bps = sum(s['realized_bps'] for s in self.slippage_history)
        n_trades = len(self.slippage_history)
        
        return {
            'total_slippage_dollars': self.total_slippage_dollars,
            'average_slippage_bps': total_realized_bps / n_trades if n_trades > 0 else 0,
            'average_expected_bps': total_expected_bps / n_trades if n_trades > 0 else 0,
            'model_accuracy': (
                1 - abs(total_expected_bps - total_realized_bps) / max(total_realized_bps, 1)
                if total_realized_bps > 0 else 1.0
            ),
            'n_trades': n_trades,
            'history': self.slippage_history[-100:]  # Last 100 trades
        }
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id not in self.pending_orders:
            return False
        
        order = self.pending_orders[order_id]
        
        try:
            await self.broker.cancel_order(order_id)
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            del self.pending_orders[order_id]
            self.order_history.append(order)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def _signal_to_order(
        self,
        symbol: str,
        signal: Dict,
        current_price: float
    ) -> Optional[Order]:
        """Convert trading signal to order."""
        action = signal['signal']
        target_position = signal['target_position']
        
        current_pos = self.positions.get(symbol, Position(symbol, 0, 0)).quantity
        portfolio_value = await self._get_portfolio_value()
        
        # Calculate position change needed
        position_change = target_position - (current_pos / portfolio_value if portfolio_value > 0 else 0)
        
        # Minimum threshold
        if abs(position_change) < 0.01:
            return None
        
        # Convert to quantity
        quantity = abs(position_change * portfolio_value / current_price)
        
        # Determine side
        if position_change > 0:
            side = OrderSide.BUY
        else:
            side = OrderSide.SELL
        
        # Calculate limit price if using limit orders
        limit_price = None
        order_type = OrderType.MARKET
        
        if self.config.use_limit_orders:
            order_type = OrderType.LIMIT
            offset = current_price * self.config.limit_offset_bps / 10000
            if side == OrderSide.BUY:
                limit_price = current_price + offset  # Slightly above for buys
            else:
                limit_price = current_price - offset  # Slightly below for sells
        
        # Create order
        self._order_counter += 1
        order = Order(
            id=f"ORD_{self._order_counter:06d}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            metadata={
                'signal': signal,
                'target_position': target_position,
            }
        )
        
        return order
    
    def _update_position(self, order: Order):
        """Update position after order fill."""
        symbol = order.symbol
        
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol, 0, 0)
        
        pos = self.positions[symbol]
        
        if order.side == OrderSide.BUY:
            # Update average entry for buys
            total_cost = pos.avg_entry_price * pos.quantity + order.filled_price * order.filled_quantity
            pos.quantity += order.filled_quantity
            if pos.quantity > 0:
                pos.avg_entry_price = total_cost / pos.quantity
        else:
            # Calculate realized P&L for sells
            pnl = (order.filled_price - pos.avg_entry_price) * min(order.filled_quantity, pos.quantity)
            pos.realized_pnl += pnl
            pos.quantity -= order.filled_quantity
        
        pos.last_update = datetime.now()
    
    def _record_trade(self, order: Order, signal: Dict):
        """Record trade for performance tracking."""
        trade = {
            'timestamp': datetime.now(),
            'symbol': order.symbol,
            'side': order.side.value,
            'quantity': order.filled_quantity,
            'price': order.filled_price,
            'signal_confidence': signal['confidence'],
            'regime': signal['regime'],
        }
        self.trades.append(trade)
    
    def _update_brain_performance(self):
        """Update brain's meta-learner with performance metrics."""
        if len(self.trades) < 5:
            return
        
        # Calculate recent metrics
        recent_trades = self.trades[-50:]
        
        returns = []
        wins = 0
        for i in range(1, len(recent_trades)):
            if recent_trades[i]['side'] == 'sell':
                ret = (recent_trades[i]['price'] - recent_trades[i-1]['price']) / recent_trades[i-1]['price']
                returns.append(ret)
                if ret > 0:
                    wins += 1
        
        if returns:
            metrics = {
                'sharpe': np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252),
                'returns': np.sum(returns),
                'win_rate': wins / len(returns),
                'trade_count': len(recent_trades),
            }
            
            self.brain.update_performance(metrics)
    
    def _get_position_pct(self, symbol: str) -> float:
        """Get position as percentage of portfolio."""
        if symbol not in self.positions:
            return 0.0
        # Simplified - would need portfolio value
        return self.positions[symbol].quantity
    
    async def _get_portfolio_value(self) -> float:
        """Get current portfolio value from broker."""
        try:
            return await self.broker.get_portfolio_value()
        except Exception as e:
            logger.warning(f"Could not fetch portfolio value, using default: {e}")
            return 100000.0
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.trades:
            return {}
        
        total_trades = len(self.trades)
        
        # Calculate P&L
        total_pnl = sum(p.realized_pnl for p in self.positions.values())
        
        return {
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'positions': {s: {'quantity': p.quantity, 'pnl': p.realized_pnl} 
                         for s, p in self.positions.items()},
            'pending_orders': len(self.pending_orders),
            'circuit_breaker_active': self.risk_guard.circuit_breaker_active,
        }


class PaperBroker:
    """Paper trading broker for testing."""
    
    def __init__(self, initial_balance: float = 100_000):
        self.balance = initial_balance
        self.positions: Dict[str, float] = {}
        self.prices: Dict[str, float] = {}
    
    def set_price(self, symbol: str, price: float):
        """Set current price for symbol."""
        self.prices[symbol] = price
    
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        positions_value = sum(
            qty * self.prices.get(sym, 0) 
            for sym, qty in self.positions.items()
        )
        return self.balance + positions_value
    
    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Dict:
        """Execute paper trade."""
        price = self.prices.get(symbol, limit_price or 100)
        
        # Apply slippage
        slippage = 0.001
        if side == 'buy':
            fill_price = price * (1 + slippage)
            self.balance -= fill_price * quantity
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:
            fill_price = price * (1 - slippage)
            self.balance += fill_price * quantity
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
        
        return {
            'filled_quantity': quantity,
            'filled_price': fill_price,
        }
    
    async def cancel_order(self, order_id: str):
        """Cancel order (no-op for paper)."""
        pass
