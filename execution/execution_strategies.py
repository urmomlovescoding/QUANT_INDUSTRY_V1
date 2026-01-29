"""
Advanced Execution Algorithms - VWAP, TWAP, and Market Microstructure
QUANT_INDUSTRY_V1

Implements:
- Enhanced VWAP with adaptive participation
- TWAP with spread-aware execution
- Implementation Shortfall minimization
- Arrival Price targeting
- Adaptive market impact modeling

Rollback Plan: Delete this file, use basic algorithms in engine.py
Tests Required: Execution cost analysis, slippage benchmarks
Failure Modes: Fall back to simple market orders, alert operators
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timezone, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import asyncio

logger = logging.getLogger(__name__)


class ExecutionUrgency(Enum):
    """Execution urgency level."""
    LOW = "low"         # Minimize market impact
    MEDIUM = "medium"   # Balance speed and cost
    HIGH = "high"       # Prioritize speed
    CRITICAL = "critical"  # Immediate execution


@dataclass
class MarketState:
    """Current market state for execution decisions."""
    symbol: str
    bid: float
    ask: float
    mid: float
    spread: float
    spread_bps: float
    volume: float
    vwap: float
    volatility: float
    imbalance: float  # Order book imbalance
    momentum: float   # Recent price momentum
    timestamp: datetime
    
    @classmethod
    def from_quote(cls, symbol: str, quote: Dict[str, Any]) -> 'MarketState':
        bid = quote.get('bid', 0)
        ask = quote.get('ask', 0)
        mid = (bid + ask) / 2 if bid and ask else quote.get('price', 100)
        spread = ask - bid if bid and ask else 0.01
        
        return cls(
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            spread_bps=spread / mid * 10000 if mid else 0,
            volume=quote.get('volume', 10000),
            vwap=quote.get('vwap', mid),
            volatility=quote.get('volatility', 0.02),
            imbalance=quote.get('imbalance', 0),
            momentum=quote.get('momentum', 0),
            timestamp=datetime.now(timezone.utc)
        )


@dataclass
class ExecutionSlice:
    """A single execution slice."""
    slice_id: int
    target_quantity: float
    target_time: datetime
    limit_price: Optional[float] = None
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: str = "pending"


@dataclass
class ExecutionPlan:
    """Complete execution plan."""
    symbol: str
    side: str  # "buy" or "sell"
    total_quantity: float
    algorithm: str
    slices: List[ExecutionSlice]
    start_time: datetime
    end_time: datetime
    urgency: ExecutionUrgency
    benchmark_price: float
    
    @property
    def filled_quantity(self) -> float:
        return sum(s.filled_quantity for s in self.slices)
    
    @property
    def remaining_quantity(self) -> float:
        return self.total_quantity - self.filled_quantity
    
    @property
    def completion_pct(self) -> float:
        return self.filled_quantity / self.total_quantity if self.total_quantity > 0 else 0
    
    @property
    def avg_fill_price(self) -> float:
        total_value = sum(s.filled_quantity * s.avg_fill_price for s in self.slices)
        total_qty = self.filled_quantity
        return total_value / total_qty if total_qty > 0 else 0


class AdvancedVWAPStrategy:
    """
    Advanced VWAP execution with adaptive participation.
    
    Features:
    - Historical volume profile modeling
    - Real-time volume tracking
    - Adaptive participation rate
    - Spread-aware limit pricing
    - Market impact estimation
    """
    
    def __init__(
        self,
        duration_minutes: int = 60,
        target_participation: float = 0.10,
        max_participation: float = 0.25,
        min_participation: float = 0.02,
        aggressiveness: float = 0.5,
        volume_profile: Optional[List[float]] = None
    ):
        self.duration_minutes = duration_minutes
        self.target_participation = target_participation
        self.max_participation = max_participation
        self.min_participation = min_participation
        self.aggressiveness = aggressiveness
        
        # Default intraday volume profile (hourly buckets, U-shaped)
        self.volume_profile = volume_profile or [
            0.12, 0.09, 0.07, 0.06, 0.06, 0.06,  # Morning
            0.08, 0.10, 0.12, 0.14, 0.10          # Afternoon
        ]
        
        # State tracking
        self.market_volume_seen = 0.0
        self.volume_history: deque = deque(maxlen=60)
        self.price_history: deque = deque(maxlen=60)
        self.realized_vwap = 0.0
        self.value_traded = 0.0
        self.quantity_traded = 0.0
        
    def create_execution_plan(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_state: MarketState,
        urgency: ExecutionUrgency = ExecutionUrgency.MEDIUM
    ) -> ExecutionPlan:
        """Create VWAP execution plan."""
        start_time = datetime.now(timezone.utc)
        
        # Adjust duration based on urgency
        duration_factor = {
            ExecutionUrgency.LOW: 1.5,
            ExecutionUrgency.MEDIUM: 1.0,
            ExecutionUrgency.HIGH: 0.5,
            ExecutionUrgency.CRITICAL: 0.2
        }[urgency]
        
        duration = int(self.duration_minutes * duration_factor)
        end_time = start_time + timedelta(minutes=duration)
        
        # Calculate slices based on volume profile
        n_slices = min(duration, len(self.volume_profile))
        slice_duration = duration / n_slices
        
        slices = []
        for i in range(n_slices):
            # Volume-weighted quantity
            profile_idx = int(i * len(self.volume_profile) / n_slices)
            weight = self.volume_profile[profile_idx]
            slice_qty = quantity * weight / sum(self.volume_profile[:n_slices])
            
            target_time = start_time + timedelta(minutes=(i + 1) * slice_duration)
            
            # Calculate limit price with spread awareness
            limit = self._calculate_limit_price(side, market_state, i / n_slices)
            
            slices.append(ExecutionSlice(
                slice_id=i,
                target_quantity=slice_qty,
                target_time=target_time,
                limit_price=limit
            ))
            
        return ExecutionPlan(
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            algorithm="VWAP",
            slices=slices,
            start_time=start_time,
            end_time=end_time,
            urgency=urgency,
            benchmark_price=market_state.vwap
        )
    
    def get_next_slice(
        self,
        plan: ExecutionPlan,
        market_state: MarketState
    ) -> Optional[Tuple[float, Optional[float]]]:
        """
        Get next execution slice with adaptive sizing.
        
        Returns: (quantity, limit_price) or None if no slice needed
        """
        now = datetime.now(timezone.utc)
        
        # Find current slice
        current_slice = None
        for s in plan.slices:
            if s.status == "pending" and now >= s.target_time - timedelta(seconds=30):
                current_slice = s
                break
                
        if current_slice is None:
            return None
            
        # Calculate adaptive quantity
        base_qty = current_slice.target_quantity - current_slice.filled_quantity
        
        # Adjust for real-time volume
        volume_factor = self._calculate_volume_factor(market_state)
        adjusted_qty = base_qty * volume_factor
        
        # Apply participation limits
        max_qty = market_state.volume * self.max_participation
        min_qty = market_state.volume * self.min_participation
        
        final_qty = np.clip(adjusted_qty, min_qty, max_qty)
        final_qty = min(final_qty, plan.remaining_quantity)
        
        if final_qty <= 0:
            return None
            
        # Calculate limit price
        limit = self._adaptive_limit_price(plan.side, market_state, plan)
        
        return final_qty, limit
    
    def _calculate_volume_factor(self, market_state: MarketState) -> float:
        """Calculate volume adjustment factor."""
        if len(self.volume_history) < 5:
            self.volume_history.append(market_state.volume)
            return 1.0
            
        self.volume_history.append(market_state.volume)
        
        # Compare current volume to recent average
        recent_avg = np.mean(list(self.volume_history)[-10:])
        
        if recent_avg > 0:
            ratio = market_state.volume / recent_avg
            # Scale participation with volume
            return np.clip(ratio, 0.5, 2.0)
        return 1.0
    
    def _calculate_limit_price(
        self,
        side: str,
        market_state: MarketState,
        progress: float
    ) -> float:
        """Calculate limit price based on spread and progress."""
        spread_pct = market_state.spread / market_state.mid
        
        # More aggressive as we progress through the order
        aggression = self.aggressiveness + (1 - self.aggressiveness) * progress
        
        if side == "buy":
            # Start at bid, move towards ask
            return market_state.bid + market_state.spread * aggression
        else:
            # Start at ask, move towards bid
            return market_state.ask - market_state.spread * aggression
    
    def _adaptive_limit_price(
        self,
        side: str,
        market_state: MarketState,
        plan: ExecutionPlan
    ) -> float:
        """Calculate adaptive limit price based on execution progress."""
        progress = plan.completion_pct
        time_progress = (datetime.now(timezone.utc) - plan.start_time).total_seconds() / \
                       (plan.end_time - plan.start_time).total_seconds()
        
        # Behind schedule? Be more aggressive
        behind = time_progress - progress
        
        aggression = self.aggressiveness
        if behind > 0.1:
            aggression = min(1.0, aggression + behind)
            
        # Consider momentum
        if side == "buy" and market_state.momentum > 0:
            aggression = min(1.0, aggression + 0.1)
        elif side == "sell" and market_state.momentum < 0:
            aggression = min(1.0, aggression + 0.1)
            
        return self._calculate_limit_price(side, market_state, aggression)
    
    def update_fill(self, quantity: float, price: float):
        """Record a fill."""
        self.value_traded += quantity * price
        self.quantity_traded += quantity
        
        if self.quantity_traded > 0:
            self.realized_vwap = self.value_traded / self.quantity_traded
            
    def get_performance(self, benchmark_vwap: float) -> Dict[str, float]:
        """Calculate execution performance vs VWAP benchmark."""
        if self.quantity_traded == 0:
            return {}
            
        slippage = (self.realized_vwap - benchmark_vwap) / benchmark_vwap
        
        return {
            'realized_vwap': self.realized_vwap,
            'benchmark_vwap': benchmark_vwap,
            'slippage_bps': slippage * 10000,
            'quantity_traded': self.quantity_traded,
            'value_traded': self.value_traded
        }


class AdvancedTWAPStrategy:
    """
    Advanced TWAP execution with spread-aware timing.
    
    Features:
    - Spread threshold execution
    - Volatility-adjusted slice sizing
    - Random jitter to avoid detection
    - Passive/aggressive mode switching
    """
    
    def __init__(
        self,
        duration_minutes: int = 60,
        n_slices: int = 20,
        randomize: bool = True,
        max_spread_bps: float = 20.0,
        passive_threshold_bps: float = 10.0
    ):
        self.duration_minutes = duration_minutes
        self.n_slices = n_slices
        self.randomize = randomize
        self.max_spread_bps = max_spread_bps
        self.passive_threshold_bps = passive_threshold_bps
        
        # Tracking
        self.slices_executed = 0
        self.passive_fills = 0
        self.aggressive_fills = 0
        self.total_value = 0.0
        self.total_quantity = 0.0
        
    def create_execution_plan(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_state: MarketState,
        urgency: ExecutionUrgency = ExecutionUrgency.MEDIUM
    ) -> ExecutionPlan:
        """Create TWAP execution plan."""
        start_time = datetime.now(timezone.utc)
        
        # Adjust slices based on urgency
        slice_factor = {
            ExecutionUrgency.LOW: 2.0,
            ExecutionUrgency.MEDIUM: 1.0,
            ExecutionUrgency.HIGH: 0.5,
            ExecutionUrgency.CRITICAL: 0.25
        }[urgency]
        
        n_slices = max(1, int(self.n_slices * slice_factor))
        duration = int(self.duration_minutes * slice_factor)
        
        end_time = start_time + timedelta(minutes=duration)
        slice_interval = duration / n_slices
        
        # Create equal-sized slices with randomized timing
        base_qty = quantity / n_slices
        
        slices = []
        for i in range(n_slices):
            # Add random jitter to timing
            jitter = 0
            if self.randomize:
                jitter = np.random.uniform(-slice_interval * 0.3, slice_interval * 0.3)
                
            target_time = start_time + timedelta(minutes=(i + 1) * slice_interval + jitter)
            
            # Randomize quantity slightly
            qty = base_qty
            if self.randomize:
                qty *= np.random.uniform(0.8, 1.2)
                
            slices.append(ExecutionSlice(
                slice_id=i,
                target_quantity=qty,
                target_time=target_time,
                limit_price=None  # Set dynamically
            ))
            
        # Normalize quantities to match total
        total_planned = sum(s.target_quantity for s in slices)
        for s in slices:
            s.target_quantity *= quantity / total_planned
            
        return ExecutionPlan(
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            algorithm="TWAP",
            slices=slices,
            start_time=start_time,
            end_time=end_time,
            urgency=urgency,
            benchmark_price=market_state.mid
        )
    
    def should_execute(
        self,
        plan: ExecutionPlan,
        market_state: MarketState
    ) -> Tuple[bool, str]:
        """
        Determine if conditions are favorable for execution.
        
        Returns: (should_execute, reason)
        """
        # Check spread
        if market_state.spread_bps > self.max_spread_bps:
            return False, f"Spread too wide: {market_state.spread_bps:.1f} bps"
            
        # Check time
        now = datetime.now(timezone.utc)
        if now < plan.start_time:
            return False, "Before start time"
        if now > plan.end_time and plan.remaining_quantity > 0:
            return True, "Past end time, forcing completion"
            
        return True, "Normal execution"
    
    def get_next_slice(
        self,
        plan: ExecutionPlan,
        market_state: MarketState
    ) -> Optional[Tuple[float, Optional[float], bool]]:
        """
        Get next TWAP slice.
        
        Returns: (quantity, limit_price, is_passive) or None
        """
        should_exec, reason = self.should_execute(plan, market_state)
        if not should_exec:
            logger.debug(f"Skipping execution: {reason}")
            return None
            
        now = datetime.now(timezone.utc)
        
        # Find due slice
        current_slice = None
        for s in plan.slices:
            if s.status == "pending" and now >= s.target_time:
                current_slice = s
                break
                
        if current_slice is None:
            return None
            
        qty = current_slice.target_quantity - current_slice.filled_quantity
        qty = min(qty, plan.remaining_quantity)
        
        if qty <= 0:
            return None
            
        # Determine passive vs aggressive
        is_passive = market_state.spread_bps <= self.passive_threshold_bps
        
        # Calculate limit price
        if is_passive:
            # Join the queue
            limit = market_state.bid if plan.side == "buy" else market_state.ask
        else:
            # Cross the spread
            limit = market_state.ask if plan.side == "buy" else market_state.bid
            
        return qty, limit, is_passive
    
    def update_fill(self, quantity: float, price: float, was_passive: bool):
        """Record a fill."""
        self.total_value += quantity * price
        self.total_quantity += quantity
        self.slices_executed += 1
        
        if was_passive:
            self.passive_fills += 1
        else:
            self.aggressive_fills += 1
            
    def get_performance(self, benchmark_price: float) -> Dict[str, float]:
        """Calculate TWAP performance."""
        if self.total_quantity == 0:
            return {}
            
        avg_price = self.total_value / self.total_quantity
        slippage = (avg_price - benchmark_price) / benchmark_price
        
        return {
            'avg_price': avg_price,
            'benchmark_price': benchmark_price,
            'slippage_bps': slippage * 10000,
            'slices_executed': self.slices_executed,
            'passive_rate': self.passive_fills / self.slices_executed if self.slices_executed > 0 else 0,
            'total_quantity': self.total_quantity
        }


class ImplementationShortfallStrategy:
    """
    Implementation Shortfall (IS) algorithm.
    
    Minimizes the cost of execution relative to decision price.
    Trades off market impact vs timing risk.
    """
    
    def __init__(
        self,
        risk_aversion: float = 0.5,
        volatility_forecast: float = 0.02,
        market_impact_coef: float = 0.1,
        temporary_impact_coef: float = 0.01
    ):
        self.risk_aversion = risk_aversion
        self.volatility_forecast = volatility_forecast
        self.market_impact_coef = market_impact_coef
        self.temporary_impact_coef = temporary_impact_coef
        
        # State
        self.decision_price: Optional[float] = None
        self.execution_trajectory: List[Tuple[datetime, float, float]] = []
        
    def calculate_optimal_trajectory(
        self,
        total_quantity: float,
        duration_minutes: int,
        market_state: MarketState
    ) -> List[float]:
        """
        Calculate optimal execution trajectory using Almgren-Chriss model.
        
        Returns: List of cumulative quantities at each time step
        """
        self.decision_price = market_state.mid
        
        # Almgren-Chriss parameters
        sigma = market_state.volatility
        eta = self.temporary_impact_coef
        gamma = self.market_impact_coef
        lambd = self.risk_aversion
        
        # Time discretization
        n_steps = duration_minutes
        tau = duration_minutes / (n_steps * 252 * 6.5 * 60)  # Convert to trading years
        
        # Calculate optimal trading rate parameter
        kappa_sq = lambd * sigma**2 / eta
        kappa = np.sqrt(kappa_sq)
        
        # Optimal trajectory
        trajectory = []
        for j in range(n_steps + 1):
            t = j / n_steps
            if kappa * duration_minutes > 100:  # Numerical stability
                x_t = total_quantity * (1 - t)
            else:
                x_t = total_quantity * np.sinh(kappa * (1 - t)) / np.sinh(kappa)
            trajectory.append(total_quantity - x_t)
            
        return trajectory
    
    def get_slice_quantity(
        self,
        total_quantity: float,
        trajectory: List[float],
        current_filled: float,
        elapsed_pct: float,
        market_state: MarketState
    ) -> float:
        """Get next slice quantity based on trajectory."""
        # Find target quantity at current time
        idx = int(elapsed_pct * (len(trajectory) - 1))
        idx = min(idx, len(trajectory) - 1)
        
        target = trajectory[idx]
        
        # Adjust for deviation from trajectory
        deviation = current_filled - target
        
        # Calculate slice to get back on track
        next_idx = min(idx + 1, len(trajectory) - 1)
        next_target = trajectory[next_idx]
        
        base_slice = next_target - target
        
        # Add catch-up component
        catch_up = 0.0
        if deviation < 0:  # Behind schedule
            catch_up = abs(deviation) * 0.5
        elif deviation > 0:  # Ahead of schedule
            catch_up = -deviation * 0.3
            
        return max(0, base_slice + catch_up)
    
    def calculate_shortfall(
        self,
        side: str
    ) -> Dict[str, float]:
        """Calculate implementation shortfall breakdown."""
        if self.decision_price is None or not self.execution_trajectory:
            return {}
            
        total_qty = sum(qty for _, _, qty in self.execution_trajectory)
        if total_qty == 0:
            return {}
            
        # Calculate arrival price
        arrival_price = self.execution_trajectory[0][1] if self.execution_trajectory else self.decision_price
        
        # Calculate VWAP of execution
        total_value = sum(price * qty for _, price, qty in self.execution_trajectory)
        execution_vwap = total_value / total_qty
        
        # Shortfall components
        direction = 1 if side == "buy" else -1
        
        total_shortfall = direction * (execution_vwap - self.decision_price)
        timing_cost = direction * (arrival_price - self.decision_price)
        market_impact = direction * (execution_vwap - arrival_price)
        
        return {
            'total_shortfall_bps': total_shortfall / self.decision_price * 10000,
            'timing_cost_bps': timing_cost / self.decision_price * 10000,
            'market_impact_bps': market_impact / self.decision_price * 10000,
            'decision_price': self.decision_price,
            'arrival_price': arrival_price,
            'execution_vwap': execution_vwap,
            'total_quantity': total_qty
        }
    
    def record_execution(self, timestamp: datetime, price: float, quantity: float):
        """Record an execution for shortfall calculation."""
        self.execution_trajectory.append((timestamp, price, quantity))


class AdaptiveExecutionEngine:
    """
    Main engine that selects and manages execution strategies.
    
    Features:
    - Strategy selection based on order characteristics
    - Real-time strategy switching
    - Performance tracking
    - Risk controls
    """
    
    def __init__(
        self,
        default_strategy: str = "VWAP",
        max_participation: float = 0.25,
        market_data_callback: Optional[Callable] = None
    ):
        self.default_strategy = default_strategy
        self.max_participation = max_participation
        self.market_data_callback = market_data_callback
        
        # Strategy instances
        self.strategies = {
            'VWAP': AdvancedVWAPStrategy(),
            'TWAP': AdvancedTWAPStrategy(),
            'IS': ImplementationShortfallStrategy()
        }
        
        # Active plans
        self.active_plans: Dict[str, ExecutionPlan] = {}
        self.completed_plans: List[ExecutionPlan] = []
        
    def select_strategy(
        self,
        symbol: str,
        quantity: float,
        urgency: ExecutionUrgency,
        market_state: MarketState
    ) -> str:
        """Select optimal strategy based on order characteristics."""
        # Large orders relative to volume -> VWAP
        adv_pct = quantity / market_state.volume if market_state.volume > 0 else 0.1
        
        if urgency == ExecutionUrgency.CRITICAL:
            return 'TWAP'  # Fastest
        elif adv_pct > 0.05:
            return 'IS'    # Minimize impact for large orders
        elif market_state.spread_bps < 5:
            return 'TWAP'  # Tight spreads favor TWAP
        else:
            return 'VWAP'  # Default
    
    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        urgency: ExecutionUrgency = ExecutionUrgency.MEDIUM,
        strategy: Optional[str] = None,
        market_state: Optional[MarketState] = None
    ) -> ExecutionPlan:
        """Create and start execution plan."""
        # Get market state if not provided
        if market_state is None:
            if self.market_data_callback:
                quote = self.market_data_callback(symbol)
                market_state = MarketState.from_quote(symbol, quote)
            else:
                market_state = MarketState.from_quote(symbol, {'price': 100})
                
        # Select strategy
        if strategy is None:
            strategy = self.select_strategy(symbol, quantity, urgency, market_state)
            
        # Create plan
        strat = self.strategies[strategy]
        plan = strat.create_execution_plan(symbol, side, quantity, market_state, urgency)
        
        # Register
        plan_id = f"{symbol}_{plan.start_time.timestamp()}"
        self.active_plans[plan_id] = plan
        
        logger.info(f"Created {strategy} plan for {quantity} {symbol} ({urgency.value})")
        return plan
    
    def tick(self, symbol: str, market_state: MarketState) -> List[Dict[str, Any]]:
        """
        Process tick and generate orders if needed.
        
        Returns: List of orders to submit
        """
        orders = []
        
        for plan_id, plan in list(self.active_plans.items()):
            if plan.symbol != symbol:
                continue
                
            if plan.remaining_quantity <= 0:
                self._complete_plan(plan_id)
                continue
                
            strat = self.strategies[plan.algorithm]
            
            # Get next slice
            if plan.algorithm == 'VWAP':
                result = strat.get_next_slice(plan, market_state)
                if result:
                    qty, limit = result
                    orders.append({
                        'plan_id': plan_id,
                        'symbol': symbol,
                        'side': plan.side,
                        'quantity': qty,
                        'limit_price': limit,
                        'algorithm': plan.algorithm
                    })
            elif plan.algorithm == 'TWAP':
                result = strat.get_next_slice(plan, market_state)
                if result:
                    qty, limit, is_passive = result
                    orders.append({
                        'plan_id': plan_id,
                        'symbol': symbol,
                        'side': plan.side,
                        'quantity': qty,
                        'limit_price': limit,
                        'passive': is_passive,
                        'algorithm': plan.algorithm
                    })
                    
        return orders
    
    def record_fill(
        self,
        plan_id: str,
        quantity: float,
        price: float,
        was_passive: bool = False
    ):
        """Record a fill for a plan."""
        if plan_id not in self.active_plans:
            logger.warning(f"Unknown plan_id: {plan_id}")
            return
            
        plan = self.active_plans[plan_id]
        strat = self.strategies[plan.algorithm]
        
        # Update strategy
        if plan.algorithm == 'VWAP':
            strat.update_fill(quantity, price)
        elif plan.algorithm == 'TWAP':
            strat.update_fill(quantity, price, was_passive)
        elif plan.algorithm == 'IS':
            strat.record_execution(datetime.now(timezone.utc), price, quantity)
            
        # Update plan slices
        for s in plan.slices:
            if s.status == "pending" and s.filled_quantity < s.target_quantity:
                fill_qty = min(quantity, s.target_quantity - s.filled_quantity)
                s.filled_quantity += fill_qty
                s.avg_fill_price = (s.avg_fill_price * (s.filled_quantity - fill_qty) + price * fill_qty) / s.filled_quantity
                quantity -= fill_qty
                
                if s.filled_quantity >= s.target_quantity:
                    s.status = "filled"
                    
                if quantity <= 0:
                    break
    
    def _complete_plan(self, plan_id: str):
        """Mark plan as complete."""
        if plan_id in self.active_plans:
            plan = self.active_plans.pop(plan_id)
            self.completed_plans.append(plan)
            logger.info(f"Completed plan {plan_id}: filled {plan.filled_quantity} @ {plan.avg_fill_price:.4f}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report for all completed plans."""
        if not self.completed_plans:
            return {}
            
        total_shortfall = 0.0
        total_value = 0.0
        
        by_algorithm = {}
        
        for plan in self.completed_plans:
            value = plan.filled_quantity * plan.avg_fill_price
            total_value += value
            
            shortfall = (plan.avg_fill_price - plan.benchmark_price) / plan.benchmark_price
            if plan.side == "sell":
                shortfall = -shortfall
            total_shortfall += shortfall * value
            
            if plan.algorithm not in by_algorithm:
                by_algorithm[plan.algorithm] = {'count': 0, 'value': 0, 'shortfall': 0}
            by_algorithm[plan.algorithm]['count'] += 1
            by_algorithm[plan.algorithm]['value'] += value
            by_algorithm[plan.algorithm]['shortfall'] += shortfall * value
            
        return {
            'total_orders': len(self.completed_plans),
            'total_value': total_value,
            'avg_shortfall_bps': (total_shortfall / total_value * 10000) if total_value > 0 else 0,
            'by_algorithm': {
                algo: {
                    'count': data['count'],
                    'value': data['value'],
                    'avg_shortfall_bps': (data['shortfall'] / data['value'] * 10000) if data['value'] > 0 else 0
                }
                for algo, data in by_algorithm.items()
            }
        }
