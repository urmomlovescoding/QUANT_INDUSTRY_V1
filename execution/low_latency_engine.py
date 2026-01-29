"""
QUANT_INDUSTRY_V1 Low-Latency Execution Engine

Latency-optimized execution engine for high-frequency trading:
- Async order processing with asyncio
- ZeroMQ-ready messaging patterns
- Lock-free order queue
- Pre-allocated memory pools
- Sub-10ms order submission target

Rollback Plan: Delete this file, revert to engine.py
Tests Required: Latency benchmarks, concurrent order handling
Failure Modes: Graceful degradation to sync, alert on latency spikes
"""

import asyncio
import time
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import queue

logger = logging.getLogger(__name__)

# Optional ZeroMQ import
try:
    import zmq
    import zmq.asyncio
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    logger.info("ZeroMQ not available - using fallback queue")


# =============================================================================
# ORDER TYPES (compatible with engine.py)
# =============================================================================

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class LowLatencyOrder:
    """
    Minimal order structure for low-latency processing.
    
    Pre-allocated fields for zero-alloc path.
    """
    __slots__ = [
        'order_id', 'symbol', 'quantity', 'side', 'order_type',
        'limit_price', 'stop_price', 'status', 'created_ns',
        'submitted_ns', 'filled_ns', 'filled_quantity', 'filled_avg_price',
        'metadata'
    ]
    
    order_id: str
    symbol: str
    quantity: float
    side: OrderSide
    order_type: OrderType
    limit_price: Optional[float]
    stop_price: Optional[float]
    status: OrderStatus
    created_ns: int  # Nanosecond timestamp for precision
    submitted_ns: int
    filled_ns: int
    filled_quantity: float
    filled_avg_price: float
    metadata: Dict[str, Any]
    
    @classmethod
    def create(
        cls,
        symbol: str,
        quantity: float,
        side: OrderSide,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None,
        stop_price: float = None,
    ) -> 'LowLatencyOrder':
        """Factory method with pre-initialized fields."""
        return cls(
            order_id=uuid.uuid4().hex[:12],
            symbol=symbol,
            quantity=quantity,
            side=side,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            status=OrderStatus.PENDING,
            created_ns=time.time_ns(),
            submitted_ns=0,
            filled_ns=0,
            filled_quantity=0.0,
            filled_avg_price=0.0,
            metadata={},
        )
    
    @property
    def latency_us(self) -> float:
        """Get submission latency in microseconds."""
        if self.submitted_ns and self.created_ns:
            return (self.submitted_ns - self.created_ns) / 1000
        return 0.0
    
    @property
    def fill_latency_us(self) -> float:
        """Get fill latency in microseconds."""
        if self.filled_ns and self.submitted_ns:
            return (self.filled_ns - self.submitted_ns) / 1000
        return 0.0


@dataclass
class ExecutionResult:
    """Result of order execution."""
    success: bool
    order: LowLatencyOrder
    message: str = ""
    latency_us: float = 0.0
    queue_depth: int = 0


# =============================================================================
# LOCK-FREE QUEUE (SPSC optimized)
# =============================================================================

class LockFreeOrderQueue:
    """
    High-performance single-producer single-consumer queue.
    
    Uses ring buffer for minimal allocation.
    """
    
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self._buffer: List[Optional[LowLatencyOrder]] = [None] * capacity
        self._head = 0  # Consumer reads from here
        self._tail = 0  # Producer writes here
        self._size = 0
    
    def push(self, order: LowLatencyOrder) -> bool:
        """Add order to queue. Returns False if full."""
        if self._size >= self.capacity:
            return False
            
        self._buffer[self._tail] = order
        self._tail = (self._tail + 1) % self.capacity
        self._size += 1
        return True
    
    def pop(self) -> Optional[LowLatencyOrder]:
        """Remove and return order from queue. Returns None if empty."""
        if self._size == 0:
            return None
            
        order = self._buffer[self._head]
        self._buffer[self._head] = None
        self._head = (self._head + 1) % self.capacity
        self._size -= 1
        return order
    
    def peek(self) -> Optional[LowLatencyOrder]:
        """View next order without removing."""
        if self._size == 0:
            return None
        return self._buffer[self._head]
    
    @property
    def size(self) -> int:
        return self._size
    
    @property
    def is_empty(self) -> bool:
        return self._size == 0
    
    @property
    def is_full(self) -> bool:
        return self._size >= self.capacity


# =============================================================================
# ZEROMQ MESSAGE TRANSPORT
# =============================================================================

class ZMQTransport:
    """
    ZeroMQ-based message transport for ultra-low latency.
    
    Supports:
    - PUSH/PULL for order flow
    - PUB/SUB for market data
    - REQ/REP for synchronous operations
    """
    
    def __init__(self, endpoint: str = "tcp://127.0.0.1:5555"):
        if not ZMQ_AVAILABLE:
            raise RuntimeError("ZeroMQ not installed. pip install pyzmq")
            
        self.endpoint = endpoint
        self._context: Optional[zmq.asyncio.Context] = None
        self._socket: Optional[zmq.asyncio.Socket] = None
        self._running = False
    
    async def connect_push(self) -> None:
        """Connect as PUSH socket for sending orders."""
        self._context = zmq.asyncio.Context()
        self._socket = self._context.socket(zmq.PUSH)
        self._socket.setsockopt(zmq.SNDHWM, 10000)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.connect(self.endpoint)
        self._running = True
        logger.info(f"ZMQ PUSH connected to {self.endpoint}")
    
    async def connect_pull(self) -> None:
        """Connect as PULL socket for receiving orders."""
        self._context = zmq.asyncio.Context()
        self._socket = self._context.socket(zmq.PULL)
        self._socket.setsockopt(zmq.RCVHWM, 10000)
        self._socket.bind(self.endpoint)
        self._running = True
        logger.info(f"ZMQ PULL bound to {self.endpoint}")
    
    async def send(self, data: bytes) -> bool:
        """Send data with zero-copy if possible."""
        if not self._socket:
            return False
        try:
            await self._socket.send(data, zmq.NOBLOCK)
            return True
        except zmq.Again:
            return False
    
    async def receive(self, timeout_ms: int = 100) -> Optional[bytes]:
        """Receive data with timeout."""
        if not self._socket:
            return None
        try:
            self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            return await self._socket.recv()
        except zmq.Again:
            return None
    
    async def close(self) -> None:
        """Close connection."""
        self._running = False
        if self._socket:
            self._socket.close()
        if self._context:
            self._context.term()


class FallbackTransport:
    """Fallback async queue when ZMQ not available."""
    
    def __init__(self):
        self._queue: asyncio.Queue = None
        self._running = False
    
    async def connect_push(self) -> None:
        self._queue = asyncio.Queue(maxsize=10000)
        self._running = True
    
    async def connect_pull(self) -> None:
        self._queue = asyncio.Queue(maxsize=10000)
        self._running = True
    
    async def send(self, data: bytes) -> bool:
        if not self._queue:
            return False
        try:
            self._queue.put_nowait(data)
            return True
        except asyncio.QueueFull:
            return False
    
    async def receive(self, timeout_ms: int = 100) -> Optional[bytes]:
        if not self._queue:
            return None
        try:
            return await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout_ms / 1000
            )
        except asyncio.TimeoutError:
            return None
    
    async def close(self) -> None:
        self._running = False


# =============================================================================
# LOW-LATENCY EXECUTION ENGINE
# =============================================================================

class LowLatencyExecutionEngine:
    """
    Async execution engine optimized for <10ms latency.
    
    Features:
    - Lock-free order queue
    - Async processing with dedicated event loop
    - ZeroMQ transport (optional)
    - Latency monitoring and alerts
    - Graceful degradation
    """
    
    # Latency thresholds (microseconds)
    LATENCY_TARGET_US = 10000  # 10ms target
    LATENCY_WARN_US = 5000     # 5ms warning
    
    def __init__(
        self,
        broker_adapter: Callable = None,
        use_zmq: bool = False,
        zmq_endpoint: str = "tcp://127.0.0.1:5555",
        max_queue_size: int = 10000,
    ):
        self.broker_adapter = broker_adapter
        self.use_zmq = use_zmq and ZMQ_AVAILABLE
        self.zmq_endpoint = zmq_endpoint
        
        # Order management
        self._order_queue = LockFreeOrderQueue(max_queue_size)
        self._pending_orders: Dict[str, LowLatencyOrder] = {}
        self._completed_orders: Dict[str, LowLatencyOrder] = {}
        
        # Async infrastructure
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._transport = None
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        
        # Thread pool for blocking operations
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="exec")
        
        # Latency tracking
        self._latencies: deque = deque(maxlen=10000)
        self._latency_violations = 0
        
        # Callbacks
        self._on_fill: List[Callable] = []
        self._on_reject: List[Callable] = []
        
        logger.info(f"LowLatencyExecutionEngine initialized (ZMQ: {self.use_zmq})")
    
    async def start(self) -> None:
        """Start the execution engine."""
        self._running = True
        self._loop = asyncio.get_event_loop()
        
        # Initialize transport
        if self.use_zmq:
            self._transport = ZMQTransport(self.zmq_endpoint)
            await self._transport.connect_push()
        else:
            self._transport = FallbackTransport()
            await self._transport.connect_push()
        
        # Start order processor
        self._processor_task = asyncio.create_task(self._process_orders())
        
        logger.info("LowLatencyExecutionEngine started")
    
    async def stop(self) -> None:
        """Stop the execution engine."""
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        if self._transport:
            await self._transport.close()
        
        self._executor.shutdown(wait=False)
        logger.info("LowLatencyExecutionEngine stopped")
    
    async def submit_order(self, order: LowLatencyOrder) -> ExecutionResult:
        """
        Submit order for execution.
        
        Target: <10ms end-to-end latency.
        """
        start_ns = time.time_ns()
        
        # Validate order
        if not self._validate_order(order):
            order.status = OrderStatus.REJECTED
            return ExecutionResult(
                success=False,
                order=order,
                message="Validation failed",
                latency_us=(time.time_ns() - start_ns) / 1000
            )
        
        # Queue order
        order.status = OrderStatus.QUEUED
        if not self._order_queue.push(order):
            order.status = OrderStatus.REJECTED
            return ExecutionResult(
                success=False,
                order=order,
                message="Queue full",
                latency_us=(time.time_ns() - start_ns) / 1000,
                queue_depth=self._order_queue.size
            )
        
        self._pending_orders[order.order_id] = order
        
        # Process immediately if possible
        await self._process_single_order(order)
        
        latency_us = (time.time_ns() - start_ns) / 1000
        self._record_latency(latency_us)
        
        return ExecutionResult(
            success=order.status != OrderStatus.REJECTED,
            order=order,
            message="Submitted",
            latency_us=latency_us,
            queue_depth=self._order_queue.size
        )
    
    def submit_order_sync(self, order: LowLatencyOrder) -> ExecutionResult:
        """Synchronous order submission (for non-async contexts)."""
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.submit_order(order),
                self._loop
            )
            return future.result(timeout=1.0)
        else:
            return asyncio.run(self.submit_order(order))
    
    async def _process_orders(self) -> None:
        """Background order processor."""
        while self._running:
            try:
                order = self._order_queue.pop()
                if order:
                    await self._process_single_order(order)
                else:
                    await asyncio.sleep(0.0001)  # 100us sleep when idle
            except Exception as e:
                logger.error(f"Order processor error: {e}")
    
    async def _process_single_order(self, order: LowLatencyOrder) -> None:
        """Process a single order."""
        try:
            order.submitted_ns = time.time_ns()
            order.status = OrderStatus.SUBMITTED
            
            if self.broker_adapter:
                # Execute via broker adapter
                result = await self._execute_via_broker(order)
                if result:
                    order.filled_ns = time.time_ns()
                    order.status = OrderStatus.FILLED
                    order.filled_quantity = order.quantity
                    order.filled_avg_price = result.get('price', 0)
                    self._notify_fill(order)
                else:
                    order.status = OrderStatus.REJECTED
                    self._notify_reject(order)
            else:
                # Simulated execution
                await self._simulate_execution(order)
            
            # Move to completed
            self._complete_order(order)
            
        except Exception as e:
            logger.error(f"Order execution error: {e}")
            order.status = OrderStatus.REJECTED
            self._notify_reject(order)
    
    async def _execute_via_broker(self, order: LowLatencyOrder) -> Optional[Dict[str, Any]]:
        """Execute order via broker adapter."""
        if asyncio.iscoroutinefunction(self.broker_adapter):
            return await self.broker_adapter(order)
        else:
            # Run blocking adapter in thread pool
            return await self._loop.run_in_executor(
                self._executor,
                self.broker_adapter,
                order
            )
    
    async def _simulate_execution(self, order: LowLatencyOrder) -> None:
        """Simulate order execution for testing."""
        # Simulate minimal latency
        await asyncio.sleep(0.0001)  # 100us
        
        order.filled_ns = time.time_ns()
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_avg_price = order.limit_price or 100.0
        
        self._notify_fill(order)
    
    def _validate_order(self, order: LowLatencyOrder) -> bool:
        """Fast order validation."""
        if order.quantity <= 0:
            return False
        if not order.symbol:
            return False
        if order.order_type == OrderType.LIMIT and order.limit_price is None:
            return False
        return True
    
    def _complete_order(self, order: LowLatencyOrder) -> None:
        """Move order to completed state."""
        self._pending_orders.pop(order.order_id, None)
        self._completed_orders[order.order_id] = order
    
    def _record_latency(self, latency_us: float) -> None:
        """Record and monitor latency."""
        self._latencies.append(latency_us)
        
        if latency_us > self.LATENCY_TARGET_US:
            self._latency_violations += 1
            logger.warning(f"Latency violation: {latency_us:.0f}us (target: {self.LATENCY_TARGET_US}us)")
    
    def _notify_fill(self, order: LowLatencyOrder) -> None:
        """Notify fill callbacks."""
        for callback in self._on_fill:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Fill callback error: {e}")
    
    def _notify_reject(self, order: LowLatencyOrder) -> None:
        """Notify reject callbacks."""
        for callback in self._on_reject:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Reject callback error: {e}")
    
    def on_fill(self, callback: Callable[[LowLatencyOrder], None]) -> None:
        """Register fill callback."""
        self._on_fill.append(callback)
    
    def on_reject(self, callback: Callable[[LowLatencyOrder], None]) -> None:
        """Register reject callback."""
        self._on_reject.append(callback)
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self._pending_orders.get(order_id)
        if not order:
            return False
        
        order.status = OrderStatus.CANCELLED
        self._complete_order(order)
        return True
    
    def get_order(self, order_id: str) -> Optional[LowLatencyOrder]:
        """Get order by ID."""
        return self._pending_orders.get(order_id) or self._completed_orders.get(order_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        latencies = list(self._latencies)
        
        import numpy as np
        
        return {
            'pending_orders': len(self._pending_orders),
            'completed_orders': len(self._completed_orders),
            'queue_depth': self._order_queue.size,
            'latency_violations': self._latency_violations,
            'avg_latency_us': np.mean(latencies) if latencies else 0,
            'p50_latency_us': np.percentile(latencies, 50) if latencies else 0,
            'p99_latency_us': np.percentile(latencies, 99) if latencies else 0,
            'max_latency_us': max(latencies) if latencies else 0,
            'min_latency_us': min(latencies) if latencies else 0,
            'total_orders': len(latencies),
            'target_latency_us': self.LATENCY_TARGET_US,
            'zmq_enabled': self.use_zmq,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_low_latency_engine(broker_adapter: Callable = None) -> LowLatencyExecutionEngine:
    """Create a low-latency execution engine."""
    return LowLatencyExecutionEngine(
        broker_adapter=broker_adapter,
        use_zmq=ZMQ_AVAILABLE,
    )


async def benchmark_latency(engine: LowLatencyExecutionEngine, n_orders: int = 1000) -> Dict[str, float]:
    """Benchmark execution latency."""
    latencies = []
    
    for i in range(n_orders):
        order = LowLatencyOrder.create(
            symbol="TEST",
            quantity=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        result = await engine.submit_order(order)
        latencies.append(result.latency_us)
    
    import numpy as np
    
    return {
        'n_orders': n_orders,
        'avg_latency_us': np.mean(latencies),
        'p50_latency_us': np.percentile(latencies, 50),
        'p95_latency_us': np.percentile(latencies, 95),
        'p99_latency_us': np.percentile(latencies, 99),
        'max_latency_us': max(latencies),
        'under_10ms_pct': sum(1 for l in latencies if l < 10000) / len(latencies) * 100,
    }
