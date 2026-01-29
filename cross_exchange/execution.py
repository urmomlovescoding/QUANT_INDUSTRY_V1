"""
Cross-Exchange Execution Engine
===============================
Executes arbitrage trades across multiple exchanges.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import logging
import uuid

from .price_feeds import Exchange
from .arb_detector import ArbOpportunity, ArbStatus

logger = logging.getLogger(__name__)


class LegStatus(Enum):
    """Status of execution leg."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ExecutionStrategy(Enum):
    """Execution strategy for arb."""
    SIMULTANEOUS = "simultaneous"  # Submit both legs at once
    SEQUENTIAL = "sequential"  # Fill one leg, then the other
    MAKER_TAKER = "maker_taker"  # One leg maker, one taker
    SMART = "smart"  # Adaptive based on conditions


@dataclass
class LegExecution:
    """Single leg of arbitrage execution."""
    leg_id: str
    exchange: Exchange
    symbol: str
    side: str  # "buy" or "sell"
    
    # Order details
    quantity: float
    limit_price: Optional[float] = None
    order_type: str = "market"
    
    # Fill info
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    
    # Timing
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Status
    status: LegStatus = LegStatus.PENDING
    exchange_order_id: str = ""
    error_message: str = ""
    
    @property
    def is_complete(self) -> bool:
        return self.status in (LegStatus.FILLED, LegStatus.CANCELLED, LegStatus.FAILED)
    
    @property
    def fill_rate(self) -> float:
        return self.filled_quantity / self.quantity if self.quantity > 0 else 0
    
    @property
    def slippage_bps(self) -> float:
        """Slippage in basis points."""
        if self.limit_price and self.avg_fill_price:
            diff = abs(self.avg_fill_price - self.limit_price)
            return (diff / self.limit_price) * 10000
        return 0.0
    
    @property
    def execution_time_ms(self) -> float:
        """Execution time in milliseconds."""
        if self.submitted_at and self.filled_at:
            return (self.filled_at - self.submitted_at).total_seconds() * 1000
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "leg_id": self.leg_id,
            "exchange": self.exchange.value,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "commission": self.commission,
            "status": self.status.value,
            "slippage_bps": self.slippage_bps,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class ExecutionPlan:
    """Plan for executing an arbitrage opportunity."""
    plan_id: str
    opportunity: ArbOpportunity
    strategy: ExecutionStrategy
    
    # Legs
    buy_leg: LegExecution
    sell_leg: LegExecution
    
    # Overall status
    status: str = "pending"  # pending, executing, completed, failed
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Risk limits
    max_slippage_bps: float = 10.0
    timeout_seconds: float = 5.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity.id,
            "strategy": self.strategy.value,
            "status": self.status,
            "buy_leg": self.buy_leg.to_dict(),
            "sell_leg": self.sell_leg.to_dict(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ExecutionResult:
    """Result of arbitrage execution."""
    plan: ExecutionPlan
    success: bool
    
    # P&L
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    total_commission: float = 0.0
    total_slippage: float = 0.0
    
    # Execution quality
    buy_slippage_bps: float = 0.0
    sell_slippage_bps: float = 0.0
    total_execution_time_ms: float = 0.0
    
    # Comparison to expected
    expected_profit: float = 0.0
    actual_vs_expected_pct: float = 0.0
    
    # Error info
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan.plan_id,
            "success": self.success,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "total_commission": self.total_commission,
            "buy_slippage_bps": self.buy_slippage_bps,
            "sell_slippage_bps": self.sell_slippage_bps,
            "total_execution_time_ms": self.total_execution_time_ms,
            "expected_profit": self.expected_profit,
            "actual_vs_expected_pct": self.actual_vs_expected_pct,
            "error_message": self.error_message,
        }


@dataclass
class ExecutorConfig:
    """Configuration for execution engine."""
    # Strategy defaults
    default_strategy: ExecutionStrategy = ExecutionStrategy.SIMULTANEOUS
    
    # Risk limits
    max_slippage_bps: float = 15.0
    max_position_usd: float = 50_000.0
    
    # Timing
    order_timeout_seconds: float = 5.0
    retry_count: int = 2
    retry_delay_ms: float = 100.0
    
    # Order types
    use_limit_orders: bool = False
    limit_offset_bps: float = 2.0  # How far from market to place limits
    
    # Safety
    require_confirmation: bool = True
    max_concurrent_executions: int = 3


class CrossExchangeExecutor:
    """
    Executes arbitrage trades across exchanges.
    
    Features:
    - Simultaneous or sequential execution
    - Slippage protection
    - Automatic retry
    - Position management
    - Execution analytics
    """
    
    def __init__(
        self,
        config: Optional[ExecutorConfig] = None,
    ):
        self.config = config or ExecutorConfig()
        
        # Exchange connectors (to be injected)
        self._connectors: Dict[Exchange, Any] = {}
        
        # Execution state
        self._active_plans: Dict[str, ExecutionPlan] = {}
        self._completed_plans: List[ExecutionPlan] = []
        self._results: List[ExecutionResult] = []
        
        # Position tracking
        self._positions: Dict[str, Dict[Exchange, float]] = {}
        
        # Callbacks
        self._callbacks: List[Callable[[ExecutionResult], None]] = []
        
    def register_connector(self, exchange: Exchange, connector: Any):
        """Register exchange connector for order submission."""
        self._connectors[exchange] = connector
        
    def register_callback(self, callback: Callable[[ExecutionResult], None]):
        """Register callback for execution results."""
        self._callbacks.append(callback)
        
    def _notify(self, result: ExecutionResult):
        """Notify callbacks of result."""
        for cb in self._callbacks:
            try:
                cb(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def create_plan(
        self,
        opportunity: ArbOpportunity,
        strategy: Optional[ExecutionStrategy] = None,
    ) -> ExecutionPlan:
        """Create execution plan from opportunity."""
        plan_id = str(uuid.uuid4())[:8]
        
        buy_leg = LegExecution(
            leg_id=f"{plan_id}-BUY",
            exchange=opportunity.buy_exchange,
            symbol=opportunity.symbol,
            side="buy",
            quantity=opportunity.max_size,
            limit_price=opportunity.buy_price if self.config.use_limit_orders else None,
        )
        
        sell_leg = LegExecution(
            leg_id=f"{plan_id}-SELL",
            exchange=opportunity.sell_exchange,
            symbol=opportunity.symbol,
            side="sell",
            quantity=opportunity.max_size,
            limit_price=opportunity.sell_price if self.config.use_limit_orders else None,
        )
        
        return ExecutionPlan(
            plan_id=plan_id,
            opportunity=opportunity,
            strategy=strategy or self.config.default_strategy,
            buy_leg=buy_leg,
            sell_leg=sell_leg,
            max_slippage_bps=self.config.max_slippage_bps,
            timeout_seconds=self.config.order_timeout_seconds,
        )
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute arbitrage plan."""
        logger.info(f"Executing plan {plan.plan_id} for {plan.opportunity.id}")
        
        # Check concurrent limit
        if len(self._active_plans) >= self.config.max_concurrent_executions:
            return self._create_failed_result(plan, "Max concurrent executions reached")
            
        # Check connectors
        if plan.buy_leg.exchange not in self._connectors:
            return self._create_failed_result(plan, f"No connector for {plan.buy_leg.exchange}")
        if plan.sell_leg.exchange not in self._connectors:
            return self._create_failed_result(plan, f"No connector for {plan.sell_leg.exchange}")
            
        # Register active plan
        self._active_plans[plan.plan_id] = plan
        plan.status = "executing"
        plan.started_at = datetime.now()
        
        try:
            if plan.strategy == ExecutionStrategy.SIMULTANEOUS:
                result = await self._execute_simultaneous(plan)
            elif plan.strategy == ExecutionStrategy.SEQUENTIAL:
                result = await self._execute_sequential(plan)
            else:
                result = await self._execute_simultaneous(plan)
                
        except Exception as e:
            logger.error(f"Execution error: {e}")
            result = self._create_failed_result(plan, str(e))
            
        finally:
            del self._active_plans[plan.plan_id]
            
        plan.completed_at = datetime.now()
        plan.status = "completed" if result.success else "failed"
        
        self._completed_plans.append(plan)
        self._results.append(result)
        self._notify(result)
        
        return result
    
    async def _execute_simultaneous(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute both legs simultaneously."""
        # Submit both orders
        buy_task = self._submit_order(plan.buy_leg)
        sell_task = self._submit_order(plan.sell_leg)
        
        # Wait for both with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(buy_task, sell_task),
                timeout=plan.timeout_seconds,
            )
        except asyncio.TimeoutError:
            # Cancel unfilled orders
            await self._cancel_order(plan.buy_leg)
            await self._cancel_order(plan.sell_leg)
            return self._create_failed_result(plan, "Execution timeout")
            
        # Wait for fills
        fill_tasks = [
            self._wait_for_fill(plan.buy_leg),
            self._wait_for_fill(plan.sell_leg),
        ]
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*fill_tasks),
                timeout=plan.timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self._cancel_order(plan.buy_leg)
            await self._cancel_order(plan.sell_leg)
            
        return self._calculate_result(plan)
    
    async def _execute_sequential(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute legs sequentially (fill one, then the other)."""
        # Execute buy leg first
        await self._submit_order(plan.buy_leg)
        
        try:
            await asyncio.wait_for(
                self._wait_for_fill(plan.buy_leg),
                timeout=plan.timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self._cancel_order(plan.buy_leg)
            return self._create_failed_result(plan, "Buy leg timeout")
            
        if plan.buy_leg.status != LegStatus.FILLED:
            return self._create_failed_result(plan, "Buy leg not filled")
            
        # Execute sell leg
        await self._submit_order(plan.sell_leg)
        
        try:
            await asyncio.wait_for(
                self._wait_for_fill(plan.sell_leg),
                timeout=plan.timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self._cancel_order(plan.sell_leg)
            # We have inventory risk now - buy filled but sell didn't
            return self._create_failed_result(plan, "Sell leg timeout - inventory risk!")
            
        return self._calculate_result(plan)
    
    async def _submit_order(self, leg: LegExecution):
        """Submit order to exchange."""
        connector = self._connectors.get(leg.exchange)
        if not connector:
            leg.status = LegStatus.FAILED
            leg.error_message = "No connector"
            return
            
        leg.submitted_at = datetime.now()
        leg.status = LegStatus.SUBMITTED
        
        # Simulated - in production this calls the exchange API
        logger.info(f"Submitting {leg.side} {leg.quantity} {leg.symbol} on {leg.exchange.value}")
        
    async def _wait_for_fill(self, leg: LegExecution):
        """Wait for order to fill."""
        # Simulated - in production this monitors order status
        await asyncio.sleep(0.1)
        
        # Simulate fill
        leg.filled_quantity = leg.quantity
        leg.avg_fill_price = leg.limit_price or 0
        leg.filled_at = datetime.now()
        leg.status = LegStatus.FILLED
        
    async def _cancel_order(self, leg: LegExecution):
        """Cancel order if not filled."""
        if leg.status in (LegStatus.SUBMITTED, LegStatus.PARTIAL):
            leg.status = LegStatus.CANCELLED
            logger.info(f"Cancelled order {leg.leg_id}")
    
    def _calculate_result(self, plan: ExecutionPlan) -> ExecutionResult:
        """Calculate execution result."""
        buy = plan.buy_leg
        sell = plan.sell_leg
        
        # Check if both legs filled
        success = (
            buy.status == LegStatus.FILLED
            and sell.status == LegStatus.FILLED
        )
        
        if not success:
            return self._create_failed_result(plan, "Not all legs filled")
            
        # Calculate P&L
        buy_cost = buy.filled_quantity * buy.avg_fill_price
        sell_proceeds = sell.filled_quantity * sell.avg_fill_price
        gross_pnl = sell_proceeds - buy_cost
        
        total_commission = buy.commission + sell.commission
        net_pnl = gross_pnl - total_commission
        
        # Slippage
        buy_slippage = buy.slippage_bps
        sell_slippage = sell.slippage_bps
        total_slippage = (buy_slippage + sell_slippage) / 10000 * buy_cost
        
        # Expected vs actual
        expected = plan.opportunity.profit_usd
        actual_vs_expected = (net_pnl / expected * 100) if expected > 0 else 0
        
        return ExecutionResult(
            plan=plan,
            success=True,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            total_commission=total_commission,
            total_slippage=total_slippage,
            buy_slippage_bps=buy_slippage,
            sell_slippage_bps=sell_slippage,
            total_execution_time_ms=buy.execution_time_ms + sell.execution_time_ms,
            expected_profit=expected,
            actual_vs_expected_pct=actual_vs_expected,
        )
    
    def _create_failed_result(
        self,
        plan: ExecutionPlan,
        error: str,
    ) -> ExecutionResult:
        """Create failed execution result."""
        return ExecutionResult(
            plan=plan,
            success=False,
            error_message=error,
        )
    
    def get_active_plans(self) -> List[ExecutionPlan]:
        """Get currently executing plans."""
        return list(self._active_plans.values())
    
    def get_recent_results(self, limit: int = 100) -> List[ExecutionResult]:
        """Get recent execution results."""
        return self._results[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self._results:
            return {"total_executions": 0}
            
        successful = [r for r in self._results if r.success]
        failed = [r for r in self._results if not r.success]
        
        return {
            "total_executions": len(self._results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(self._results) * 100,
            "total_gross_pnl": sum(r.gross_pnl for r in successful),
            "total_net_pnl": sum(r.net_pnl for r in successful),
            "total_commission": sum(r.total_commission for r in successful),
            "avg_slippage_bps": (
                sum(r.buy_slippage_bps + r.sell_slippage_bps for r in successful) / 
                len(successful) / 2
            ) if successful else 0,
            "avg_execution_time_ms": (
                sum(r.total_execution_time_ms for r in successful) / len(successful)
            ) if successful else 0,
        }
