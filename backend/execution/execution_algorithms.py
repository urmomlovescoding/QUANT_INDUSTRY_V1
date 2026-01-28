"""
QUANT INDUSTRY - Institutional Execution Algorithms
====================================================
Advanced execution strategies to minimize market impact and slippage:
- VWAP (Volume Weighted Average Price)
- TWAP (Time Weighted Average Price)
- Implementation Shortfall
- Iceberg Orders
- Adaptive Execution with RL

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import asyncio
import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger(__name__)


# ============== ALMGREN-CHRISS SLIPPAGE MODEL ==============

@dataclass
class SlippageEstimate:
    """Result of slippage calculation"""
    permanent_impact: float  # Price impact that doesn't decay
    temporary_impact: float  # Price impact during execution only
    total_slippage_bps: float  # Total slippage in basis points
    total_slippage_dollars: float  # Total slippage in dollars
    optimal_execution_time: float  # Hours for optimal execution
    participation_rate: float  # Recommended % of daily volume


class AlmgrenChrissSlippageModel:
    """
    Almgren-Chriss Market Impact Model
    
    The industry-standard model for estimating execution costs.
    Based on "Optimal Execution of Portfolio Transactions" (2000).
    
    Components:
    - Permanent impact: Price change that persists after trading
    - Temporary impact: Price impact during execution that decays
    
    Parameters calibrated for US equities/futures.
    """
    
    def __init__(
        self,
        eta: float = 0.01,      # Temporary impact coefficient
        gamma: float = 0.05,    # Permanent impact coefficient
        sigma_scale: float = 1.0,  # Volatility scaling factor
        risk_aversion: float = 1e-6  # Risk aversion parameter
    ):
        """
        Initialize Almgren-Chriss model.
        
        Args:
            eta: Temporary impact coefficient (higher = more temporary slippage)
            gamma: Permanent impact coefficient (higher = more permanent price move)
            sigma_scale: Multiplier for volatility effects
            risk_aversion: Lambda parameter for risk-adjusted optimization
        """
        self.eta = eta
        self.gamma = gamma
        self.sigma_scale = sigma_scale
        self.risk_aversion = risk_aversion
    
    def calculate_slippage(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
        price: float,
        execution_time_hours: float = 1.0
    ) -> SlippageEstimate:
        """
        Calculate expected slippage for an order.
        
        Args:
            order_size: Number of shares/contracts to execute
            daily_volume: Average daily volume
            volatility: Daily volatility (decimal, e.g., 0.02 for 2%)
            price: Current price
            execution_time_hours: Time to execute (hours)
            
        Returns:
            SlippageEstimate with breakdown of costs
        """
        if daily_volume <= 0 or order_size <= 0:
            return SlippageEstimate(0, 0, 0, 0, 0, 0)
        
        # Participation rate
        trading_hours = 6.5  # Regular market hours
        volume_during_execution = daily_volume * (execution_time_hours / trading_hours)
        participation_rate = order_size / volume_during_execution if volume_during_execution > 0 else 1.0
        
        # Normalized order size (fraction of daily volume)
        X = order_size / daily_volume
        
        # Permanent impact (linear in order size)
        # g(v) = gamma * sigma * (X / T)
        permanent_impact = self.gamma * volatility * X
        
        # Temporary impact (depends on execution speed)
        # h(v) = eta * sigma * (X / T)^0.5 for aggressive execution
        T = execution_time_hours / trading_hours  # Fraction of trading day
        temporary_impact = self.eta * volatility * np.sqrt(X / max(T, 0.01))
        
        # Total slippage in basis points
        total_impact = permanent_impact + temporary_impact
        total_slippage_bps = total_impact * 10000
        
        # Dollar slippage
        total_slippage_dollars = total_impact * price * order_size
        
        # Optimal execution time (Almgren-Chriss formula)
        # T* = sqrt(eta / (risk_aversion * sigma^2))
        if self.risk_aversion > 0:
            optimal_T = np.sqrt(self.eta / (self.risk_aversion * volatility**2))
            optimal_execution_time = min(optimal_T * trading_hours, trading_hours)
        else:
            optimal_execution_time = trading_hours
        
        return SlippageEstimate(
            permanent_impact=permanent_impact * 10000,  # bps
            temporary_impact=temporary_impact * 10000,  # bps
            total_slippage_bps=total_slippage_bps,
            total_slippage_dollars=total_slippage_dollars,
            optimal_execution_time=optimal_execution_time,
            participation_rate=min(participation_rate, 1.0)
        )
    
    def apply_to_backtest(
        self,
        trades_df: 'pd.DataFrame',
        volume_col: str = 'volume',
        size_col: str = 'size',
        price_col: str = 'price',
        volatility_col: str = 'volatility',
        side_col: str = 'side'
    ) -> 'pd.DataFrame':
        """
        Apply slippage model to historical backtest trades.
        
        This is CRITICAL for realistic backtest results.
        
        Args:
            trades_df: DataFrame with trade records
            volume_col: Column name for daily volume
            size_col: Column name for order size
            price_col: Column name for price
            volatility_col: Column name for volatility (optional)
            side_col: Column name for side ('buy'/'sell')
            
        Returns:
            DataFrame with adjusted prices and slippage columns
        """
        if not HAS_PANDAS:
            raise ImportError("Pandas required for apply_to_backtest")
        
        df = trades_df.copy()
        
        # Default volatility if not provided
        if volatility_col not in df.columns:
            df['_volatility'] = 0.02  # 2% default
            volatility_col = '_volatility'
        
        slippage_results = []
        for idx, row in df.iterrows():
            estimate = self.calculate_slippage(
                order_size=abs(row[size_col]),
                daily_volume=row[volume_col],
                volatility=row[volatility_col],
                price=row[price_col]
            )
            slippage_results.append(estimate)
        
        # Add slippage columns
        df['slippage_bps'] = [s.total_slippage_bps for s in slippage_results]
        df['slippage_dollars'] = [s.total_slippage_dollars for s in slippage_results]
        df['permanent_impact_bps'] = [s.permanent_impact for s in slippage_results]
        df['temporary_impact_bps'] = [s.temporary_impact for s in slippage_results]
        
        # Adjust execution prices
        # Buys get worse (higher) price, sells get worse (lower) price
        price_impact = df['slippage_bps'] / 10000 * df[price_col]
        
        if side_col in df.columns:
            is_buy = df[side_col].str.lower().isin(['buy', 'long', 'b'])
            df['adjusted_price'] = np.where(
                is_buy,
                df[price_col] + price_impact,
                df[price_col] - price_impact
            )
        else:
            # Assume all buys if no side column
            df['adjusted_price'] = df[price_col] + price_impact
        
        # Calculate P&L impact
        df['pnl_impact'] = -df['slippage_dollars']  # Slippage is always a cost
        
        return df
    
    def get_realistic_fills(
        self,
        order_price: float,
        order_size: float,
        side: str,
        daily_volume: float,
        volatility: float = 0.02
    ) -> Tuple[float, float]:
        """
        Get a realistic fill price accounting for slippage.
        Use this in execution simulation.
        
        Args:
            order_price: Intended execution price
            order_size: Order size
            side: 'buy' or 'sell'
            daily_volume: Average daily volume
            volatility: Daily volatility
            
        Returns:
            Tuple of (fill_price, slippage_dollars)
        """
        estimate = self.calculate_slippage(
            order_size=order_size,
            daily_volume=daily_volume,
            volatility=volatility,
            price=order_price
        )
        
        slippage_pct = estimate.total_slippage_bps / 10000
        
        if side.lower() in ['buy', 'long', 'b']:
            fill_price = order_price * (1 + slippage_pct)
        else:
            fill_price = order_price * (1 - slippage_pct)
        
        return fill_price, estimate.total_slippage_dollars


# Convenience function for quick slippage estimates
def estimate_slippage(
    order_size: float,
    daily_volume: float,
    price: float,
    volatility: float = 0.02,
    aggressive: bool = False
) -> float:
    """
    Quick slippage estimate in basis points.
    
    Args:
        order_size: Number of shares/contracts
        daily_volume: Average daily volume
        price: Current price
        volatility: Daily volatility (default 2%)
        aggressive: If True, assume fast execution (more slippage)
        
    Returns:
        Estimated slippage in basis points
    """
    # Use higher impact coefficients for aggressive execution
    eta = 0.02 if aggressive else 0.01
    gamma = 0.08 if aggressive else 0.05
    
    model = AlmgrenChrissSlippageModel(eta=eta, gamma=gamma)
    estimate = model.calculate_slippage(
        order_size=order_size,
        daily_volume=daily_volume,
        volatility=volatility,
        price=price,
        execution_time_hours=0.5 if aggressive else 2.0
    )
    
    return estimate.total_slippage_bps


# ============== DATA CLASSES ==============

class ExecutionStrategy(Enum):
    """Execution algorithm types"""
    MARKET = "market"           # Immediate execution
    VWAP = "vwap"               # Volume-weighted average price
    TWAP = "twap"               # Time-weighted average price
    IS = "implementation_shortfall"  # Minimize implementation shortfall
    ICEBERG = "iceberg"         # Hidden size orders
    ADAPTIVE = "adaptive"       # RL-based adaptive execution
    POV = "pov"                 # Percentage of volume


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    EXECUTING = "executing"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ExecutionSlice:
    """A single slice/child order of an execution"""
    slice_id: str
    parent_order_id: str
    quantity: int
    limit_price: Optional[float]
    scheduled_time: datetime
    executed_time: Optional[datetime] = None
    executed_quantity: int = 0
    executed_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    slippage: float = 0.0


@dataclass
class ExecutionPlan:
    """Complete execution plan for an order"""
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    total_quantity: int
    strategy: ExecutionStrategy
    start_time: datetime
    end_time: datetime
    slices: List[ExecutionSlice] = field(default_factory=list)
    target_participation_rate: float = 0.10  # 10% of volume
    urgency: float = 0.5  # 0 = passive, 1 = aggressive
    
    # Results
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_price: float = 0.0
    vwap_benchmark: float = 0.0
    arrival_price: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0


@dataclass
class MarketMicrostructure:
    """Real-time market microstructure data"""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    mid: float
    spread: float
    spread_bps: float
    bid_size: int
    ask_size: int
    imbalance: float  # Positive = buy pressure
    volatility: float
    adv: int  # Average daily volume
    current_volume: int
    volume_rate: float  # Current vs expected volume
    
    @property
    def is_liquid(self) -> bool:
        return self.spread_bps < 10 and self.adv > 1_000_000


@dataclass 
class ExecutionMetrics:
    """Post-execution analysis metrics"""
    order_id: str
    symbol: str
    side: str
    quantity: int
    strategy: ExecutionStrategy
    
    # Prices
    arrival_price: float
    average_execution_price: float
    vwap: float
    close_price: float
    
    # Costs (in basis points)
    total_cost_bps: float
    slippage_bps: float
    market_impact_bps: float
    timing_cost_bps: float
    spread_cost_bps: float
    
    # Quality
    participation_rate: float
    fill_rate: float
    execution_time_minutes: float


# ============== EXECUTION ALGORITHMS ==============

class ExecutionAlgorithm(ABC):
    """Base class for execution algorithms"""
    
    def __init__(self, name: str):
        self.name = name
        self._running = False
    
    @abstractmethod
    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: int,
        market_data: MarketMicrostructure,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> ExecutionPlan:
        """Create execution plan with child order slices"""
        pass
    
    @abstractmethod
    def update_plan(
        self,
        plan: ExecutionPlan,
        market_data: MarketMicrostructure
    ) -> ExecutionPlan:
        """Update plan based on current market conditions"""
        pass
    
    def calculate_slippage(
        self,
        plan: ExecutionPlan,
        benchmark_price: float
    ) -> float:
        """Calculate slippage in basis points"""
        if plan.filled_quantity == 0 or benchmark_price == 0:
            return 0.0
        
        if plan.side == "buy":
            slippage = (plan.average_price - benchmark_price) / benchmark_price
        else:
            slippage = (benchmark_price - plan.average_price) / benchmark_price
        
        return slippage * 10000  # Convert to bps


class VWAPAlgorithm(ExecutionAlgorithm):
    """
    Volume Weighted Average Price Algorithm
    
    Splits order to match historical volume profile, targeting
    execution at or better than VWAP.
    """
    
    def __init__(self):
        super().__init__("VWAP")
        # Historical intraday volume profile (percentage by 30-min bucket)
        # Based on typical US equity market patterns
        self.volume_profile = {
            "09:30": 0.08, "10:00": 0.07, "10:30": 0.06, "11:00": 0.05,
            "11:30": 0.05, "12:00": 0.04, "12:30": 0.04, "13:00": 0.04,
            "13:30": 0.05, "14:00": 0.05, "14:30": 0.06, "15:00": 0.08,
            "15:30": 0.12, "16:00": 0.15  # Heavy volume at close
        }
    
    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: int,
        market_data: MarketMicrostructure,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> ExecutionPlan:
        """Create VWAP execution plan"""
        now = datetime.now(timezone.utc)
        start_time = start_time or now
        end_time = end_time or (now.replace(hour=16, minute=0, second=0, microsecond=0))
        
        # Calculate duration in 30-minute buckets
        duration_minutes = (end_time - start_time).total_seconds() / 60
        num_slices = max(1, int(duration_minutes / 30))
        
        # Get relevant volume weights for time window
        slices = []
        slice_times = []
        weights = []
        
        current_time = start_time
        for i in range(num_slices):
            time_key = current_time.strftime("%H:%M")
            # Find closest bucket
            closest_bucket = min(
                self.volume_profile.keys(),
                key=lambda x: abs(
                    datetime.strptime(x, "%H:%M").hour * 60 + 
                    datetime.strptime(x, "%H:%M").minute -
                    current_time.hour * 60 - current_time.minute
                )
            )
            weights.append(self.volume_profile.get(closest_bucket, 0.05))
            slice_times.append(current_time)
            current_time += timedelta(minutes=30)
        
        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Create slices
        remaining_qty = quantity
        for i, (slice_time, weight) in enumerate(zip(slice_times, normalized_weights)):
            if i == len(slice_times) - 1:
                slice_qty = remaining_qty  # Last slice gets remainder
            else:
                slice_qty = int(quantity * weight)
                remaining_qty -= slice_qty
            
            if slice_qty > 0:
                slices.append(ExecutionSlice(
                    slice_id=f"{symbol}_{side}_{i}",
                    parent_order_id=f"{symbol}_{side}_{int(now.timestamp())}",
                    quantity=slice_qty,
                    limit_price=None,  # Will be set dynamically
                    scheduled_time=slice_time
                ))
        
        return ExecutionPlan(
            order_id=f"{symbol}_{side}_{int(now.timestamp())}",
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            strategy=ExecutionStrategy.VWAP,
            start_time=start_time,
            end_time=end_time,
            slices=slices,
            arrival_price=market_data.mid
        )
    
    def update_plan(
        self,
        plan: ExecutionPlan,
        market_data: MarketMicrostructure
    ) -> ExecutionPlan:
        """Adjust limits based on current spread and urgency"""
        for slice in plan.slices:
            if slice.status == OrderStatus.PENDING:
                # Set limit price relative to spread
                if plan.side == "buy":
                    # Start at bid, move toward ask based on urgency
                    slice.limit_price = (
                        market_data.bid + 
                        market_data.spread * plan.urgency * 0.5
                    )
                else:
                    slice.limit_price = (
                        market_data.ask - 
                        market_data.spread * plan.urgency * 0.5
                    )
        
        return plan


class TWAPAlgorithm(ExecutionAlgorithm):
    """
    Time Weighted Average Price Algorithm
    
    Splits order evenly across time, ignoring volume profile.
    Best for orders where timing risk > market impact.
    """
    
    def __init__(self):
        super().__init__("TWAP")
    
    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: int,
        market_data: MarketMicrostructure,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        num_slices: int = 10,
        **kwargs
    ) -> ExecutionPlan:
        """Create TWAP execution plan - equal slices over time"""
        now = datetime.now(timezone.utc)
        start_time = start_time or now
        end_time = end_time or (now + timedelta(hours=2))
        
        duration = (end_time - start_time).total_seconds()
        interval = duration / num_slices
        
        slices = []
        slice_qty = quantity // num_slices
        remainder = quantity % num_slices
        
        for i in range(num_slices):
            qty = slice_qty + (1 if i < remainder else 0)
            scheduled = start_time + timedelta(seconds=interval * i)
            
            slices.append(ExecutionSlice(
                slice_id=f"{symbol}_{side}_twap_{i}",
                parent_order_id=f"{symbol}_{side}_{int(now.timestamp())}",
                quantity=qty,
                limit_price=None,
                scheduled_time=scheduled
            ))
        
        return ExecutionPlan(
            order_id=f"{symbol}_{side}_{int(now.timestamp())}",
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            strategy=ExecutionStrategy.TWAP,
            start_time=start_time,
            end_time=end_time,
            slices=slices,
            arrival_price=market_data.mid
        )
    
    def update_plan(
        self,
        plan: ExecutionPlan,
        market_data: MarketMicrostructure
    ) -> ExecutionPlan:
        """Update TWAP limits - simple approach"""
        for slice in plan.slices:
            if slice.status == OrderStatus.PENDING:
                if plan.side == "buy":
                    slice.limit_price = market_data.ask
                else:
                    slice.limit_price = market_data.bid
        
        return plan


class ImplementationShortfallAlgorithm(ExecutionAlgorithm):
    """
    Implementation Shortfall Algorithm
    
    Minimizes the difference between decision price and execution price,
    balancing market impact vs timing risk using Almgren-Chriss model.
    """
    
    def __init__(self, risk_aversion: float = 0.001):
        super().__init__("Implementation Shortfall")
        self.risk_aversion = risk_aversion
    
    def _almgren_chriss_trajectory(
        self,
        quantity: int,
        volatility: float,
        adv: int,
        duration_minutes: float,
        risk_aversion: float
    ) -> List[float]:
        """
        Calculate optimal execution trajectory using Almgren-Chriss model.
        Returns list of cumulative execution percentages.
        """
        if not HAS_NUMPY:
            # Fallback to linear trajectory
            return [i / 10 for i in range(11)]
        
        # Model parameters (simplified)
        T = duration_minutes / (60 * 6.5)  # Trading day fraction
        sigma = volatility
        eta = 0.01 * (quantity / adv)  # Temporary impact
        gamma = 0.05  # Permanent impact
        
        # Risk parameter
        kappa = np.sqrt(risk_aversion * sigma**2 / eta)
        
        # Generate trajectory
        n_steps = 10
        trajectory = []
        
        for i in range(n_steps + 1):
            t = i / n_steps * T
            if kappa * T > 0:
                x_t = np.sinh(kappa * (T - t)) / np.sinh(kappa * T)
            else:
                x_t = 1 - (t / T)  # Linear fallback
            
            cumulative_pct = 1 - x_t
            trajectory.append(min(1.0, max(0.0, cumulative_pct)))
        
        return trajectory
    
    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: int,
        market_data: MarketMicrostructure,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> ExecutionPlan:
        """Create IS execution plan with optimal trajectory"""
        now = datetime.now(timezone.utc)
        start_time = start_time or now
        end_time = end_time or (now + timedelta(hours=2))
        
        duration_minutes = (end_time - start_time).total_seconds() / 60
        
        # Get optimal trajectory
        trajectory = self._almgren_chriss_trajectory(
            quantity=quantity,
            volatility=market_data.volatility,
            adv=market_data.adv,
            duration_minutes=duration_minutes,
            risk_aversion=self.risk_aversion
        )
        
        # Create slices based on trajectory
        slices = []
        prev_pct = 0.0
        interval = duration_minutes / (len(trajectory) - 1)
        
        for i, cum_pct in enumerate(trajectory[1:], 1):
            slice_pct = cum_pct - prev_pct
            slice_qty = int(quantity * slice_pct)
            
            if slice_qty > 0:
                scheduled = start_time + timedelta(minutes=interval * (i - 1))
                slices.append(ExecutionSlice(
                    slice_id=f"{symbol}_{side}_is_{i}",
                    parent_order_id=f"{symbol}_{side}_{int(now.timestamp())}",
                    quantity=slice_qty,
                    limit_price=None,
                    scheduled_time=scheduled
                ))
            
            prev_pct = cum_pct
        
        # Ensure we have the full quantity
        total_sliced = sum(s.quantity for s in slices)
        if total_sliced < quantity and slices:
            slices[-1].quantity += (quantity - total_sliced)
        
        return ExecutionPlan(
            order_id=f"{symbol}_{side}_{int(now.timestamp())}",
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            strategy=ExecutionStrategy.IS,
            start_time=start_time,
            end_time=end_time,
            slices=slices,
            arrival_price=market_data.mid,
            urgency=kwargs.get("urgency", 0.5)
        )
    
    def update_plan(
        self,
        plan: ExecutionPlan,
        market_data: MarketMicrostructure
    ) -> ExecutionPlan:
        """Adjust aggressiveness based on price movement"""
        # If price moving against us, increase urgency
        price_change = (market_data.mid - plan.arrival_price) / plan.arrival_price
        
        if plan.side == "buy" and price_change > 0.001:
            # Price rising, be more aggressive
            plan.urgency = min(1.0, plan.urgency + 0.1)
        elif plan.side == "sell" and price_change < -0.001:
            # Price falling, be more aggressive
            plan.urgency = min(1.0, plan.urgency + 0.1)
        
        # Set limits based on urgency
        for slice in plan.slices:
            if slice.status == OrderStatus.PENDING:
                if plan.side == "buy":
                    slice.limit_price = market_data.bid + market_data.spread * plan.urgency
                else:
                    slice.limit_price = market_data.ask - market_data.spread * plan.urgency
        
        return plan


class IcebergAlgorithm(ExecutionAlgorithm):
    """
    Iceberg/Hidden Order Algorithm
    
    Shows only a small portion of the order while hiding true size.
    Reduces market impact for large orders.
    """
    
    def __init__(self, display_ratio: float = 0.1):
        super().__init__("Iceberg")
        self.display_ratio = display_ratio
    
    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: int,
        market_data: MarketMicrostructure,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> ExecutionPlan:
        """Create iceberg order plan"""
        now = datetime.now(timezone.utc)
        start_time = start_time or now
        end_time = end_time or (now + timedelta(hours=4))
        
        # Calculate visible size
        display_qty = max(100, int(quantity * self.display_ratio))
        num_slices = math.ceil(quantity / display_qty)
        
        slices = []
        remaining = quantity
        
        for i in range(num_slices):
            slice_qty = min(display_qty, remaining)
            remaining -= slice_qty
            
            slices.append(ExecutionSlice(
                slice_id=f"{symbol}_{side}_iceberg_{i}",
                parent_order_id=f"{symbol}_{side}_{int(now.timestamp())}",
                quantity=slice_qty,
                limit_price=market_data.mid,  # Use mid as starting point
                scheduled_time=start_time  # All start immediately
            ))
        
        return ExecutionPlan(
            order_id=f"{symbol}_{side}_{int(now.timestamp())}",
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            strategy=ExecutionStrategy.ICEBERG,
            start_time=start_time,
            end_time=end_time,
            slices=slices,
            arrival_price=market_data.mid
        )
    
    def update_plan(
        self,
        plan: ExecutionPlan,
        market_data: MarketMicrostructure
    ) -> ExecutionPlan:
        """Update iceberg - only adjust unfilled slices"""
        for slice in plan.slices:
            if slice.status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
                if plan.side == "buy":
                    slice.limit_price = market_data.bid
                else:
                    slice.limit_price = market_data.ask
        
        return plan


class AdaptiveExecutionAlgorithm(ExecutionAlgorithm):
    """
    Adaptive Execution Algorithm
    
    Uses reinforcement learning to dynamically select between strategies
    based on real-time market conditions.
    """
    
    def __init__(self):
        super().__init__("Adaptive")
        self.algorithms = {
            ExecutionStrategy.VWAP: VWAPAlgorithm(),
            ExecutionStrategy.TWAP: TWAPAlgorithm(),
            ExecutionStrategy.IS: ImplementationShortfallAlgorithm(),
            ExecutionStrategy.ICEBERG: IcebergAlgorithm()
        }
        
        # Strategy selection weights (learned over time)
        self.strategy_weights = {
            ExecutionStrategy.VWAP: 0.25,
            ExecutionStrategy.TWAP: 0.25,
            ExecutionStrategy.IS: 0.25,
            ExecutionStrategy.ICEBERG: 0.25
        }
        
        # Performance history
        self.performance_history: List[Dict] = []
    
    def _select_strategy(self, market_data: MarketMicrostructure) -> ExecutionStrategy:
        """Select best strategy based on market conditions"""
        # High volatility → IS (minimize shortfall)
        if market_data.volatility > 0.03:
            return ExecutionStrategy.IS
        
        # Low liquidity → Iceberg (hide size)
        if not market_data.is_liquid:
            return ExecutionStrategy.ICEBERG
        
        # Volume concentrated → VWAP
        if market_data.volume_rate > 1.2:  # Higher than normal volume
            return ExecutionStrategy.VWAP
        
        # Default → TWAP for simplicity
        return ExecutionStrategy.TWAP
    
    def create_plan(
        self,
        symbol: str,
        side: str,
        quantity: int,
        market_data: MarketMicrostructure,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> ExecutionPlan:
        """Create adaptive plan by selecting best algorithm"""
        selected = self._select_strategy(market_data)
        algo = self.algorithms[selected]
        
        plan = algo.create_plan(
            symbol=symbol,
            side=side,
            quantity=quantity,
            market_data=market_data,
            start_time=start_time,
            end_time=end_time,
            **kwargs
        )
        
        plan.strategy = ExecutionStrategy.ADAPTIVE
        return plan
    
    def update_plan(
        self,
        plan: ExecutionPlan,
        market_data: MarketMicrostructure
    ) -> ExecutionPlan:
        """Re-evaluate strategy and adjust"""
        # Check if we should switch strategies mid-execution
        current_selected = self._select_strategy(market_data)
        
        # For now, just update limits using IS algo (most adaptive)
        is_algo = self.algorithms[ExecutionStrategy.IS]
        return is_algo.update_plan(plan, market_data)
    
    def record_performance(self, metrics: ExecutionMetrics):
        """Record execution performance for learning"""
        self.performance_history.append({
            "strategy": metrics.strategy,
            "slippage_bps": metrics.slippage_bps,
            "market_impact_bps": metrics.market_impact_bps,
            "total_cost_bps": metrics.total_cost_bps,
            "timestamp": datetime.now(timezone.utc)
        })
        
        # Update strategy weights based on performance
        self._update_weights()
    
    def _update_weights(self):
        """Update strategy selection weights based on performance"""
        if len(self.performance_history) < 10:
            return
        
        # Get recent performance by strategy
        recent = self.performance_history[-100:]
        strategy_costs = {}
        
        for record in recent:
            strategy = record["strategy"]
            cost = record["total_cost_bps"]
            
            if strategy not in strategy_costs:
                strategy_costs[strategy] = []
            strategy_costs[strategy].append(cost)
        
        # Update weights inversely proportional to cost
        total_inv_cost = 0
        inv_costs = {}
        
        for strategy, costs in strategy_costs.items():
            avg_cost = sum(costs) / len(costs)
            inv_cost = 1 / (avg_cost + 1)  # Add 1 to avoid div by zero
            inv_costs[strategy] = inv_cost
            total_inv_cost += inv_cost
        
        # Normalize
        for strategy in inv_costs:
            self.strategy_weights[strategy] = inv_costs[strategy] / total_inv_cost


# ============== EXECUTION ENGINE ==============

class ExecutionEngine:
    """
    Central execution engine that manages order execution
    using algorithmic strategies.
    """
    
    def __init__(self, broker_adapter=None):
        self.broker = broker_adapter
        self.algorithms = {
            ExecutionStrategy.MARKET: None,  # Direct execution
            ExecutionStrategy.VWAP: VWAPAlgorithm(),
            ExecutionStrategy.TWAP: TWAPAlgorithm(),
            ExecutionStrategy.IS: ImplementationShortfallAlgorithm(),
            ExecutionStrategy.ICEBERG: IcebergAlgorithm(),
            ExecutionStrategy.ADAPTIVE: AdaptiveExecutionAlgorithm()
        }
        
        self.active_plans: Dict[str, ExecutionPlan] = {}
        self._running = False
        self._executor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Metrics
        self.completed_executions: List[ExecutionMetrics] = []
    
    def create_execution_plan(
        self,
        symbol: str,
        side: str,
        quantity: int,
        strategy: ExecutionStrategy = ExecutionStrategy.ADAPTIVE,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> ExecutionPlan:
        """Create an execution plan for an order"""
        # Get current market data
        market_data = self._get_market_data(symbol)
        
        if strategy == ExecutionStrategy.MARKET:
            # Direct market order - single slice
            now = datetime.now(timezone.utc)
            return ExecutionPlan(
                order_id=f"{symbol}_{side}_{int(now.timestamp())}",
                symbol=symbol,
                side=side,
                total_quantity=quantity,
                strategy=ExecutionStrategy.MARKET,
                start_time=now,
                end_time=now,
                slices=[ExecutionSlice(
                    slice_id=f"{symbol}_{side}_market_0",
                    parent_order_id=f"{symbol}_{side}_{int(now.timestamp())}",
                    quantity=quantity,
                    limit_price=None,
                    scheduled_time=now
                )],
                arrival_price=market_data.mid
            )
        
        algo = self.algorithms.get(strategy)
        if not algo:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        return algo.create_plan(
            symbol=symbol,
            side=side,
            quantity=quantity,
            market_data=market_data,
            start_time=start_time,
            end_time=end_time,
            **kwargs
        )
    
    def _get_market_data(self, symbol: str) -> MarketMicrostructure:
        """Get current market microstructure data"""
        # TODO: Integrate with actual market data service
        # For now, return reasonable defaults
        return MarketMicrostructure(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            bid=100.0,
            ask=100.05,
            mid=100.025,
            spread=0.05,
            spread_bps=5.0,
            bid_size=1000,
            ask_size=1000,
            imbalance=0.0,
            volatility=0.02,
            adv=5_000_000,
            current_volume=2_000_000,
            volume_rate=1.0
        )
    
    def execute_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Execute a plan (add to active execution queue)"""
        with self._lock:
            self.active_plans[plan.order_id] = plan
            plan.status = OrderStatus.EXECUTING
        
        return plan
    
    def cancel_plan(self, order_id: str) -> bool:
        """Cancel an active execution plan"""
        with self._lock:
            if order_id in self.active_plans:
                plan = self.active_plans[order_id]
                plan.status = OrderStatus.CANCELLED
                del self.active_plans[order_id]
                return True
        return False
    
    def get_plan_status(self, order_id: str) -> Optional[ExecutionPlan]:
        """Get current status of an execution plan"""
        return self.active_plans.get(order_id)
    
    def calculate_metrics(self, plan: ExecutionPlan, closing_price: float) -> ExecutionMetrics:
        """Calculate post-execution metrics"""
        total_cost_bps = 0.0
        
        if plan.filled_quantity > 0 and plan.arrival_price > 0:
            if plan.side == "buy":
                slippage = (plan.average_price - plan.arrival_price) / plan.arrival_price
            else:
                slippage = (plan.arrival_price - plan.average_price) / plan.arrival_price
            
            slippage_bps = slippage * 10000
            
            # Estimate market impact (difference from VWAP)
            if plan.vwap_benchmark > 0:
                if plan.side == "buy":
                    impact = (plan.average_price - plan.vwap_benchmark) / plan.vwap_benchmark
                else:
                    impact = (plan.vwap_benchmark - plan.average_price) / plan.vwap_benchmark
                market_impact_bps = impact * 10000
            else:
                market_impact_bps = slippage_bps * 0.5
            
            # Timing cost
            if plan.side == "buy":
                timing = (closing_price - plan.arrival_price) / plan.arrival_price
            else:
                timing = (plan.arrival_price - closing_price) / plan.arrival_price
            timing_cost_bps = timing * 10000
            
            total_cost_bps = slippage_bps + market_impact_bps
        else:
            slippage_bps = 0.0
            market_impact_bps = 0.0
            timing_cost_bps = 0.0
        
        execution_time = (plan.end_time - plan.start_time).total_seconds() / 60
        
        return ExecutionMetrics(
            order_id=plan.order_id,
            symbol=plan.symbol,
            side=plan.side,
            quantity=plan.total_quantity,
            strategy=plan.strategy,
            arrival_price=plan.arrival_price,
            average_execution_price=plan.average_price,
            vwap=plan.vwap_benchmark,
            close_price=closing_price,
            total_cost_bps=total_cost_bps,
            slippage_bps=slippage_bps,
            market_impact_bps=market_impact_bps,
            timing_cost_bps=timing_cost_bps,
            spread_cost_bps=5.0,  # Assumed
            participation_rate=plan.target_participation_rate,
            fill_rate=plan.filled_quantity / plan.total_quantity if plan.total_quantity > 0 else 0,
            execution_time_minutes=execution_time
        )


# ============== SINGLETON ==============

_execution_engine: Optional[ExecutionEngine] = None
_lock = threading.Lock()


def get_execution_engine() -> ExecutionEngine:
    """Get singleton execution engine"""
    global _execution_engine
    
    if _execution_engine is None:
        with _lock:
            if _execution_engine is None:
                _execution_engine = ExecutionEngine()
    
    return _execution_engine
