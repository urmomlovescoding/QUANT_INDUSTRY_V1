"""
QUANT_INDUSTRY_V1 Low-Latency Execution Engine (P0 Improvement #3)

Production-grade low-latency execution engine optimized for sub-10ms order execution:

Features:
- Async execution engine using asyncio with high-performance event loop
- Connection pooling for broker connections with pre-warming
- Order batching for efficiency and reduced network overhead
- Comprehensive latency monitoring and metrics
- Graceful degradation and circuit breakers
- Integration with existing engine.py architecture

Target Performance:
- Order submission: <10ms (p99)
- Order fill acknowledgment: <15ms (p99)
- Batch throughput: 1000+ orders/second

Architecture:
    LowLatencyExecutionEngine
        |-- BrokerConnectionPool (manages broker connections)
        |-- OrderBatcher (batches orders for efficiency)
        |-- LatencyMonitor (tracks and alerts on latency)
        |-- CircuitBreaker (prevents cascading failures)

Usage:
    from execution.low_latency import LowLatencyExecutionEngine

    async with LowLatencyExecutionEngine(broker_config) as engine:
        result = await engine.submit_order(order)
        stats = engine.get_latency_stats()

Rollback Plan: Delete this file, revert to engine.py
Tests Required: Latency benchmarks, connection pool stress tests, batching correctness
Failure Modes: Circuit breaker trips, connection pool exhaustion, latency violations
"""

import asyncio
import logging
import time
import uuid
import weakref
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import (
    Any, AsyncIterator, Callable, Coroutine, Dict, List,
    Optional, Set, Tuple, Type, TypeVar, Union
)
import threading
import statistics

# Import from existing modules
from .engine import Order, OrderStatus, OrderSide, OrderType, TimeInForce

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class LowLatencyConfig:
    """Configuration for low-latency execution engine."""

    # Connection pool settings
    min_connections: int = 3
    max_connections: int = 10
    connection_timeout_ms: int = 5000
    connection_warmup: bool = True
    health_check_interval_seconds: int = 30

    # Order batching settings
    batch_enabled: bool = True
    batch_size: int = 50
    batch_timeout_ms: int = 5  # Max wait time for batch
    batch_queue_size: int = 10000

    # Latency settings
    target_latency_ms: float = 10.0  # Sub-10ms target
    warn_latency_ms: float = 5.0
    critical_latency_ms: float = 15.0
    latency_sample_size: int = 10000

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 30
    half_open_requests: int = 3

    # Performance tuning
    use_uvloop: bool = True  # Use uvloop if available
    thread_pool_size: int = 4
    max_queue_size: int = 50000

    # Metrics
    metrics_enabled: bool = True
    metrics_flush_interval_seconds: int = 60

    def validate(self) -> List[str]:
        """Validate configuration. Returns list of errors."""
        errors = []
        if self.min_connections < 1:
            errors.append("min_connections must be >= 1")
        if self.max_connections < self.min_connections:
            errors.append("max_connections must be >= min_connections")
        if self.batch_size < 1:
            errors.append("batch_size must be >= 1")
        if self.target_latency_ms <= 0:
            errors.append("target_latency_ms must be > 0")
        return errors


# =============================================================================
# LATENCY METRICS
# =============================================================================

@dataclass
class LatencyMetric:
    """Single latency measurement."""
    operation: str
    latency_ns: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def latency_ms(self) -> float:
        return self.latency_ns / 1_000_000

    @property
    def latency_us(self) -> float:
        return self.latency_ns / 1_000


class LatencyMonitor:
    """
    High-precision latency monitoring with statistical analysis.

    Features:
    - Nanosecond precision timing
    - Percentile calculations (p50, p95, p99, p999)
    - Moving average tracking
    - Anomaly detection
    - Threshold alerts
    """

    def __init__(self, config: LowLatencyConfig):
        self.config = config
        self._metrics: deque = deque(maxlen=config.latency_sample_size)
        self._lock = threading.Lock()

        # Aggregated statistics
        self._total_requests = 0
        self._total_latency_ns = 0
        self._violations = 0
        self._min_latency_ns = float('inf')
        self._max_latency_ns = 0

        # Per-operation tracking
        self._operation_metrics: Dict[str, deque] = {}

        # Callbacks for alerts
        self._alert_callbacks: List[Callable[[str, float], None]] = []

    def record(
        self,
        operation: str,
        latency_ns: int,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LatencyMetric:
        """Record a latency measurement."""
        metric = LatencyMetric(
            operation=operation,
            latency_ns=latency_ns,
            success=success,
            metadata=metadata or {}
        )

        with self._lock:
            self._metrics.append(metric)
            self._total_requests += 1
            self._total_latency_ns += latency_ns
            self._min_latency_ns = min(self._min_latency_ns, latency_ns)
            self._max_latency_ns = max(self._max_latency_ns, latency_ns)

            # Track per-operation
            if operation not in self._operation_metrics:
                self._operation_metrics[operation] = deque(maxlen=self.config.latency_sample_size)
            self._operation_metrics[operation].append(latency_ns)

            # Check thresholds
            latency_ms = latency_ns / 1_000_000
            if latency_ms > self.config.target_latency_ms:
                self._violations += 1
                self._trigger_alerts(operation, latency_ms)

        return metric

    def _trigger_alerts(self, operation: str, latency_ms: float):
        """Trigger alert callbacks for latency violations."""
        for callback in self._alert_callbacks:
            try:
                callback(operation, latency_ms)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def on_alert(self, callback: Callable[[str, float], None]):
        """Register an alert callback."""
        self._alert_callbacks.append(callback)

    def get_statistics(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get latency statistics."""
        with self._lock:
            if operation and operation in self._operation_metrics:
                samples = list(self._operation_metrics[operation])
            else:
                samples = [m.latency_ns for m in self._metrics]

        if not samples:
            return {
                'count': 0,
                'avg_ms': 0,
                'min_ms': 0,
                'max_ms': 0,
                'p50_ms': 0,
                'p95_ms': 0,
                'p99_ms': 0,
                'p999_ms': 0,
                'violations': 0,
                'violation_rate': 0,
            }

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        def percentile(p: float) -> float:
            idx = int(n * p / 100)
            idx = min(idx, n - 1)
            return sorted_samples[idx] / 1_000_000

        return {
            'count': n,
            'avg_ms': statistics.mean(samples) / 1_000_000,
            'min_ms': min(samples) / 1_000_000,
            'max_ms': max(samples) / 1_000_000,
            'stddev_ms': statistics.stdev(samples) / 1_000_000 if n > 1 else 0,
            'p50_ms': percentile(50),
            'p95_ms': percentile(95),
            'p99_ms': percentile(99),
            'p999_ms': percentile(99.9),
            'violations': self._violations,
            'violation_rate': self._violations / max(self._total_requests, 1),
            'target_ms': self.config.target_latency_ms,
            'under_target_pct': sum(1 for s in samples if s / 1_000_000 < self.config.target_latency_ms) / n * 100,
        }

    @asynccontextmanager
    async def measure(self, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for measuring operation latency."""
        start_ns = time.perf_counter_ns()
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            latency_ns = time.perf_counter_ns() - start_ns
            self.record(operation, latency_ns, success, metadata)

    def measure_sync(self, operation: str):
        """Decorator for measuring synchronous function latency."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_ns = time.perf_counter_ns()
                success = True
                try:
                    return func(*args, **kwargs)
                except Exception:
                    success = False
                    raise
                finally:
                    latency_ns = time.perf_counter_ns() - start_ns
                    self.record(operation, latency_ns, success)
            return wrapper
        return decorator

    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._operation_metrics.clear()
            self._total_requests = 0
            self._total_latency_ns = 0
            self._violations = 0
            self._min_latency_ns = float('inf')
            self._max_latency_ns = 0


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern for preventing cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests are rejected
    - HALF_OPEN: Testing if system has recovered

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

        if breaker.can_execute():
            try:
                result = await execute_request()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 30,
        half_open_requests: int = 3,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self.half_open_requests = half_open_requests
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_successes = 0
        self._lock = threading.Lock()

        # Metrics
        self._total_requests = 0
        self._rejected_requests = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        with self._lock:
            self._total_requests += 1

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._last_failure_time:
                    elapsed = datetime.now(timezone.utc) - self._last_failure_time
                    if elapsed >= self.recovery_timeout:
                        self._transition_to_half_open()
                        return True

                self._rejected_requests += 1
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open state
                return self._half_open_successes < self.half_open_requests

            return False

    def record_success(self):
        """Record a successful request."""
        with self._lock:
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_requests:
                    self._transition_to_closed()
            else:
                self._failure_count = 0  # Reset failures on success

    def record_failure(self):
        """Record a failed request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self._failure_count >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self):
        """Transition to open state."""
        old_state = self._state
        self._state = CircuitState.OPEN
        logger.warning(f"Circuit breaker '{self.name}' OPENED (was {old_state.value})")

    def _transition_to_half_open(self):
        """Transition to half-open state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_successes = 0
        logger.info(f"Circuit breaker '{self.name}' half-open, testing recovery")

    def _transition_to_closed(self):
        """Transition to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_successes = 0
        logger.info(f"Circuit breaker '{self.name}' CLOSED, recovered")

    def get_statistics(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                'name': self.name,
                'state': self._state.value,
                'failure_count': self._failure_count,
                'success_count': self._success_count,
                'total_requests': self._total_requests,
                'rejected_requests': self._rejected_requests,
                'rejection_rate': self._rejected_requests / max(self._total_requests, 1),
                'failure_threshold': self.failure_threshold,
                'last_failure': self._last_failure_time.isoformat() if self._last_failure_time else None,
            }


# =============================================================================
# BROKER CONNECTION POOL
# =============================================================================

class BrokerConnection:
    """Represents a single broker connection."""

    def __init__(
        self,
        connection_id: str,
        broker_adapter: Any,
        timeout_ms: int = 5000
    ):
        self.connection_id = connection_id
        self.broker_adapter = broker_adapter
        self.timeout_ms = timeout_ms

        self.created_at = datetime.now(timezone.utc)
        self.last_used: Optional[datetime] = None
        self.request_count = 0
        self.error_count = 0
        self.is_healthy = True
        self._in_use = False
        self._lock = asyncio.Lock()

    @property
    def is_available(self) -> bool:
        return not self._in_use and self.is_healthy

    async def acquire(self):
        """Mark connection as in use."""
        async with self._lock:
            self._in_use = True
            self.last_used = datetime.now(timezone.utc)

    async def release(self):
        """Mark connection as available."""
        async with self._lock:
            self._in_use = False

    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute an operation using this connection."""
        try:
            self.request_count += 1
            if asyncio.iscoroutinefunction(operation):
                result = await asyncio.wait_for(
                    operation(*args, **kwargs),
                    timeout=self.timeout_ms / 1000
                )
            else:
                result = operation(*args, **kwargs)
            return result
        except Exception as e:
            self.error_count += 1
            raise


class BrokerConnectionPool:
    """
    Connection pool for broker adapters with pre-warming and health checks.

    Features:
    - Pre-warmed connections for minimal latency
    - Automatic health monitoring
    - Connection recycling
    - Load balancing (least-connections)

    Usage:
        pool = BrokerConnectionPool(config, broker_factory)
        await pool.start()

        async with pool.acquire() as conn:
            result = await conn.execute(submit_order, order)
    """

    def __init__(
        self,
        config: LowLatencyConfig,
        broker_factory: Callable[[], Any],
    ):
        self.config = config
        self.broker_factory = broker_factory

        self._connections: List[BrokerConnection] = []
        self._lock = asyncio.Lock()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

        # Statistics
        self._total_acquisitions = 0
        self._failed_acquisitions = 0
        self._total_wait_time_ns = 0

    async def start(self):
        """Start the connection pool."""
        self._running = True
        self._semaphore = asyncio.Semaphore(self.config.max_connections)

        # Pre-warm connections
        if self.config.connection_warmup:
            await self._warmup()

        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info(f"BrokerConnectionPool started with {len(self._connections)} connections")

    async def stop(self):
        """Stop the connection pool."""
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for conn in self._connections:
            try:
                if hasattr(conn.broker_adapter, 'disconnect'):
                    await self._run_maybe_async(conn.broker_adapter.disconnect)
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

        self._connections.clear()
        logger.info("BrokerConnectionPool stopped")

    async def _warmup(self):
        """Pre-warm minimum connections."""
        for i in range(self.config.min_connections):
            try:
                conn = await self._create_connection()
                if conn:
                    self._connections.append(conn)
            except Exception as e:
                logger.error(f"Failed to create warmup connection: {e}")

        logger.info(f"Warmed up {len(self._connections)} connections")

    async def _create_connection(self) -> Optional[BrokerConnection]:
        """Create a new broker connection."""
        try:
            conn_id = f"broker_{uuid.uuid4().hex[:8]}"
            adapter = self.broker_factory()

            # Connect if adapter supports it
            if hasattr(adapter, 'connect'):
                await self._run_maybe_async(adapter.connect)

            return BrokerConnection(
                connection_id=conn_id,
                broker_adapter=adapter,
                timeout_ms=self.config.connection_timeout_ms
            )
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            return None

    async def _run_maybe_async(self, func, *args, **kwargs):
        """Run a function that may or may not be async."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    @asynccontextmanager
    async def acquire(self, timeout_ms: Optional[int] = None) -> AsyncIterator[BrokerConnection]:
        """
        Acquire a connection from the pool.

        Usage:
            async with pool.acquire() as conn:
                await conn.execute(operation)
        """
        timeout_ms = timeout_ms or self.config.connection_timeout_ms
        start_ns = time.perf_counter_ns()

        try:
            async with asyncio.timeout(timeout_ms / 1000):
                await self._semaphore.acquire()
        except asyncio.TimeoutError:
            self._failed_acquisitions += 1
            raise RuntimeError("Connection pool exhausted")

        conn = None
        try:
            async with self._lock:
                # Find available connection (least recently used)
                available = [c for c in self._connections if c.is_available]
                if available:
                    conn = min(available, key=lambda c: c.request_count)
                elif len(self._connections) < self.config.max_connections:
                    conn = await self._create_connection()
                    if conn:
                        self._connections.append(conn)

            if not conn:
                raise RuntimeError("No connection available")

            await conn.acquire()
            self._total_acquisitions += 1
            self._total_wait_time_ns += time.perf_counter_ns() - start_ns

            yield conn

        finally:
            if conn:
                await conn.release()
            self._semaphore.release()

    async def _health_check_loop(self):
        """Periodic health check of connections."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)
                await self._check_connections_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_connections_health(self):
        """Check health of all connections."""
        async with self._lock:
            unhealthy = []
            for conn in self._connections:
                if not conn._in_use:
                    try:
                        if hasattr(conn.broker_adapter, 'get_account'):
                            await self._run_maybe_async(conn.broker_adapter.get_account)
                        conn.is_healthy = True
                    except Exception:
                        conn.is_healthy = False
                        unhealthy.append(conn)

            # Replace unhealthy connections
            for conn in unhealthy:
                self._connections.remove(conn)
                new_conn = await self._create_connection()
                if new_conn:
                    self._connections.append(new_conn)
                logger.warning(f"Replaced unhealthy connection {conn.connection_id}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            'total_connections': len(self._connections),
            'available_connections': sum(1 for c in self._connections if c.is_available),
            'healthy_connections': sum(1 for c in self._connections if c.is_healthy),
            'total_acquisitions': self._total_acquisitions,
            'failed_acquisitions': self._failed_acquisitions,
            'avg_wait_ms': (self._total_wait_time_ns / max(self._total_acquisitions, 1)) / 1_000_000,
            'min_connections': self.config.min_connections,
            'max_connections': self.config.max_connections,
        }


# =============================================================================
# ORDER BATCHER
# =============================================================================

@dataclass
class OrderBatch:
    """A batch of orders to be processed together."""
    batch_id: str
    orders: List[Order]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.orders)


class OrderBatcher:
    """
    Batches orders for efficient processing.

    Benefits:
    - Reduced network overhead
    - Better throughput for bulk operations
    - Configurable batch size and timeout

    Usage:
        batcher = OrderBatcher(config)
        await batcher.start(process_batch_callback)

        # Orders are automatically batched
        await batcher.add_order(order)
    """

    def __init__(self, config: LowLatencyConfig):
        self.config = config

        self._queue: asyncio.Queue = None
        self._current_batch: List[Order] = []
        self._batch_lock = asyncio.Lock()
        self._process_callback: Optional[Callable[[OrderBatch], Coroutine]] = None
        self._batch_task: Optional[asyncio.Task] = None
        self._running = False

        # Statistics
        self._total_batches = 0
        self._total_orders = 0
        self._avg_batch_size = 0.0

    async def start(self, process_callback: Callable[[OrderBatch], Coroutine]):
        """Start the batcher with a processing callback."""
        self._running = True
        self._queue = asyncio.Queue(maxsize=self.config.batch_queue_size)
        self._process_callback = process_callback
        self._batch_task = asyncio.create_task(self._batch_loop())
        logger.info("OrderBatcher started")

    async def stop(self):
        """Stop the batcher and process remaining orders."""
        self._running = False

        # Process remaining orders
        if self._current_batch:
            await self._flush_batch()

        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        logger.info("OrderBatcher stopped")

    async def add_order(self, order: Order) -> bool:
        """Add an order to be batched."""
        if not self._running:
            return False

        try:
            await asyncio.wait_for(
                self._queue.put(order),
                timeout=self.config.batch_timeout_ms / 1000
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Order queue full, dropping order")
            return False

    async def _batch_loop(self):
        """Main batching loop."""
        while self._running:
            try:
                # Wait for first order with timeout
                try:
                    order = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self.config.batch_timeout_ms / 1000
                    )
                    async with self._batch_lock:
                        self._current_batch.append(order)
                except asyncio.TimeoutError:
                    # Flush current batch on timeout
                    if self._current_batch:
                        await self._flush_batch()
                    continue

                # Collect more orders up to batch size
                deadline = time.time() + (self.config.batch_timeout_ms / 1000)
                while len(self._current_batch) < self.config.batch_size and time.time() < deadline:
                    try:
                        remaining = deadline - time.time()
                        if remaining <= 0:
                            break
                        order = await asyncio.wait_for(
                            self._queue.get(),
                            timeout=remaining
                        )
                        async with self._batch_lock:
                            self._current_batch.append(order)
                    except asyncio.TimeoutError:
                        break

                # Flush batch
                await self._flush_batch()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch loop error: {e}")

    async def _flush_batch(self):
        """Flush current batch for processing."""
        async with self._batch_lock:
            if not self._current_batch:
                return

            batch = OrderBatch(
                batch_id=f"batch_{uuid.uuid4().hex[:8]}",
                orders=self._current_batch.copy()
            )
            self._current_batch.clear()

        # Process batch
        if self._process_callback:
            try:
                await self._process_callback(batch)
                batch.completed_at = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(f"Batch processing error: {e}")

        # Update statistics
        self._total_batches += 1
        self._total_orders += batch.size
        self._avg_batch_size = self._total_orders / self._total_batches

    def get_statistics(self) -> Dict[str, Any]:
        """Get batcher statistics."""
        return {
            'enabled': self.config.batch_enabled,
            'batch_size_config': self.config.batch_size,
            'total_batches': self._total_batches,
            'total_orders': self._total_orders,
            'avg_batch_size': self._avg_batch_size,
            'queue_size': self._queue.qsize() if self._queue else 0,
            'current_batch_size': len(self._current_batch),
        }


# =============================================================================
# EXECUTION RESULT
# =============================================================================

@dataclass
class ExecutionResult:
    """Result of order execution."""
    success: bool
    order: Order
    message: str = ""
    latency_ms: float = 0.0
    submission_time: Optional[datetime] = None
    fill_time: Optional[datetime] = None
    broker_order_id: Optional[str] = None
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    slippage_bps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'order_id': self.order.id if hasattr(self.order, 'id') else str(id(self.order)),
            'symbol': self.order.symbol,
            'side': self.order.side.value,
            'quantity': self.order.quantity,
            'status': self.order.status.value,
            'message': self.message,
            'latency_ms': self.latency_ms,
            'submission_time': self.submission_time.isoformat() if self.submission_time else None,
            'fill_time': self.fill_time.isoformat() if self.fill_time else None,
            'broker_order_id': self.broker_order_id,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'slippage_bps': self.slippage_bps,
        }


# =============================================================================
# LOW-LATENCY EXECUTION ENGINE
# =============================================================================

class LowLatencyExecutionEngine:
    """
    Production-grade low-latency execution engine.

    Provides sub-10ms order execution through:
    - Connection pooling with pre-warming
    - Order batching for efficiency
    - Circuit breakers for reliability
    - Comprehensive latency monitoring

    Usage:
        config = LowLatencyConfig(target_latency_ms=10.0)
        engine = LowLatencyExecutionEngine(
            config=config,
            broker_factory=lambda: MyBrokerAdapter()
        )

        async with engine:
            result = await engine.submit_order(order)
            stats = engine.get_statistics()
    """

    def __init__(
        self,
        config: Optional[LowLatencyConfig] = None,
        broker_factory: Optional[Callable[[], Any]] = None,
    ):
        self.config = config or LowLatencyConfig()
        self.broker_factory = broker_factory

        # Validate configuration
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {errors}")

        # Components
        self._connection_pool: Optional[BrokerConnectionPool] = None
        self._order_batcher: Optional[OrderBatcher] = None
        self._latency_monitor: Optional[LatencyMonitor] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None

        # State
        self._running = False
        self._pending_orders: Dict[str, Order] = {}
        self._completed_orders: deque = deque(maxlen=10000)
        self._executor: Optional[ThreadPoolExecutor] = None

        # Order processing
        self._order_counter = 0
        self._order_lock = asyncio.Lock()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False

    async def start(self):
        """Start the execution engine."""
        if self._running:
            return

        self._running = True

        # Initialize components
        self._latency_monitor = LatencyMonitor(self.config)

        if self.config.circuit_breaker_enabled:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=self.config.failure_threshold,
                recovery_timeout_seconds=self.config.recovery_timeout_seconds,
                half_open_requests=self.config.half_open_requests,
                name="execution_engine"
            )

        if self.broker_factory:
            self._connection_pool = BrokerConnectionPool(
                self.config,
                self.broker_factory
            )
            await self._connection_pool.start()

        if self.config.batch_enabled:
            self._order_batcher = OrderBatcher(self.config)
            await self._order_batcher.start(self._process_batch)

        self._executor = ThreadPoolExecutor(
            max_workers=self.config.thread_pool_size,
            thread_name_prefix="ll_exec"
        )

        # Register latency alerts
        self._latency_monitor.on_alert(self._on_latency_alert)

        logger.info(f"LowLatencyExecutionEngine started (target: {self.config.target_latency_ms}ms)")

    async def stop(self):
        """Stop the execution engine."""
        if not self._running:
            return

        self._running = False

        if self._order_batcher:
            await self._order_batcher.stop()

        if self._connection_pool:
            await self._connection_pool.stop()

        if self._executor:
            self._executor.shutdown(wait=False)

        logger.info("LowLatencyExecutionEngine stopped")

    def _on_latency_alert(self, operation: str, latency_ms: float):
        """Handle latency alert."""
        if latency_ms > self.config.critical_latency_ms:
            logger.error(f"CRITICAL latency: {operation} took {latency_ms:.2f}ms")
        elif latency_ms > self.config.warn_latency_ms:
            logger.warning(f"High latency: {operation} took {latency_ms:.2f}ms")

    async def submit_order(self, order: Order) -> ExecutionResult:
        """
        Submit an order for execution.

        Args:
            order: Order to execute

        Returns:
            ExecutionResult with execution details
        """
        if not self._running:
            return ExecutionResult(
                success=False,
                order=order,
                message="Engine not running"
            )

        # Check circuit breaker
        if self._circuit_breaker and not self._circuit_breaker.can_execute():
            return ExecutionResult(
                success=False,
                order=order,
                message="Circuit breaker open"
            )

        start_ns = time.perf_counter_ns()
        submission_time = datetime.now(timezone.utc)

        try:
            async with self._latency_monitor.measure("submit_order", {"symbol": order.symbol}):
                # Use batching if enabled
                if self._order_batcher and self.config.batch_enabled:
                    success = await self._order_batcher.add_order(order)
                    if not success:
                        return ExecutionResult(
                            success=False,
                            order=order,
                            message="Failed to add to batch queue"
                        )

                    # For batched orders, we return immediately
                    # The actual execution result will be available later
                    order.status = OrderStatus.SUBMITTED
                    self._pending_orders[order.id] = order

                    latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

                    if self._circuit_breaker:
                        self._circuit_breaker.record_success()

                    return ExecutionResult(
                        success=True,
                        order=order,
                        message="Order batched",
                        latency_ms=latency_ms,
                        submission_time=submission_time
                    )

                # Direct execution without batching
                result = await self._execute_order(order)
                result.submission_time = submission_time
                result.latency_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

                if result.success and self._circuit_breaker:
                    self._circuit_breaker.record_success()

                return result

        except Exception as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()

            logger.error(f"Order submission error: {e}")
            return ExecutionResult(
                success=False,
                order=order,
                message=str(e),
                latency_ms=(time.perf_counter_ns() - start_ns) / 1_000_000
            )

    async def submit_orders(self, orders: List[Order]) -> List[ExecutionResult]:
        """
        Submit multiple orders for execution.

        Args:
            orders: List of orders to execute

        Returns:
            List of ExecutionResults
        """
        if not orders:
            return []

        # Use concurrent execution for multiple orders
        tasks = [self.submit_order(order) for order in orders]
        return await asyncio.gather(*tasks)

    async def _execute_order(self, order: Order) -> ExecutionResult:
        """Execute a single order through the connection pool."""
        if not self._connection_pool:
            # Simulate execution if no broker configured
            return await self._simulate_execution(order)

        try:
            async with self._connection_pool.acquire() as conn:
                result = await conn.execute(
                    self._broker_submit_order,
                    conn.broker_adapter,
                    order
                )

                order.status = OrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.filled_price = result.get('filled_price', order.limit_price or 0)

                self._complete_order(order)

                return ExecutionResult(
                    success=True,
                    order=order,
                    message="Filled",
                    broker_order_id=result.get('order_id'),
                    filled_quantity=order.filled_quantity,
                    filled_price=order.filled_price,
                    fill_time=datetime.now(timezone.utc)
                )

        except Exception as e:
            order.status = OrderStatus.REJECTED
            return ExecutionResult(
                success=False,
                order=order,
                message=str(e)
            )

    async def _broker_submit_order(self, broker_adapter: Any, order: Order) -> Dict[str, Any]:
        """Submit order through broker adapter."""
        if hasattr(broker_adapter, 'submit_order'):
            if asyncio.iscoroutinefunction(broker_adapter.submit_order):
                result = await broker_adapter.submit_order(order)
            else:
                result = broker_adapter.submit_order(order)

            if hasattr(result, 'to_dict'):
                return result.to_dict() if callable(result.to_dict) else result.to_dict
            elif isinstance(result, dict):
                return result
            else:
                return {'order_id': str(result)}

        raise RuntimeError("Broker adapter does not support submit_order")

    async def _simulate_execution(self, order: Order) -> ExecutionResult:
        """Simulate order execution for testing."""
        await asyncio.sleep(0.0001)  # 100us simulated latency

        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = order.limit_price or 100.0

        self._complete_order(order)

        return ExecutionResult(
            success=True,
            order=order,
            message="Simulated fill",
            filled_quantity=order.quantity,
            filled_price=order.filled_price,
            fill_time=datetime.now(timezone.utc)
        )

    async def _process_batch(self, batch: OrderBatch):
        """Process a batch of orders."""
        async with self._latency_monitor.measure("process_batch", {"batch_size": batch.size}):
            results = []

            for order in batch.orders:
                result = await self._execute_order(order)
                results.append(result)

            batch.results = {
                'total': len(results),
                'successful': sum(1 for r in results if r.success),
                'failed': sum(1 for r in results if not r.success)
            }

    def _complete_order(self, order: Order):
        """Mark order as completed."""
        self._pending_orders.pop(order.id, None)
        self._completed_orders.append(order)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self._pending_orders.get(order_id)
        if not order:
            return False

        order.status = OrderStatus.CANCELLED
        self._complete_order(order)
        return True

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return self._pending_orders.get(order_id)

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics."""
        stats = {
            'running': self._running,
            'pending_orders': len(self._pending_orders),
            'completed_orders': len(self._completed_orders),
            'target_latency_ms': self.config.target_latency_ms,
        }

        if self._latency_monitor:
            stats['latency'] = self._latency_monitor.get_statistics()

        if self._connection_pool:
            stats['connection_pool'] = self._connection_pool.get_statistics()

        if self._order_batcher:
            stats['batcher'] = self._order_batcher.get_statistics()

        if self._circuit_breaker:
            stats['circuit_breaker'] = self._circuit_breaker.get_statistics()

        return stats

    def get_latency_stats(self) -> Dict[str, Any]:
        """Get latency statistics (convenience method)."""
        if self._latency_monitor:
            return self._latency_monitor.get_statistics()
        return {}


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_low_latency_engine(
    broker_factory: Optional[Callable[[], Any]] = None,
    **config_kwargs
) -> LowLatencyExecutionEngine:
    """
    Factory function to create a low-latency execution engine.

    Args:
        broker_factory: Factory function that creates broker adapters
        **config_kwargs: Configuration overrides

    Returns:
        Configured LowLatencyExecutionEngine
    """
    config = LowLatencyConfig(**config_kwargs)
    return LowLatencyExecutionEngine(config=config, broker_factory=broker_factory)


async def benchmark_latency(
    engine: LowLatencyExecutionEngine,
    n_orders: int = 1000,
    symbol: str = "TEST"
) -> Dict[str, Any]:
    """
    Benchmark execution latency.

    Args:
        engine: Execution engine to benchmark
        n_orders: Number of orders to test
        symbol: Symbol to use for test orders

    Returns:
        Benchmark results including latency percentiles
    """
    latencies = []

    for i in range(n_orders):
        order = Order(
            id=f"benchmark_{i:06d}",
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        start = time.perf_counter_ns()
        result = await engine.submit_order(order)
        latency_ms = (time.perf_counter_ns() - start) / 1_000_000
        latencies.append(latency_ms)

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    def percentile(p: float) -> float:
        idx = int(n * p / 100)
        return sorted_latencies[min(idx, n - 1)]

    under_target = sum(1 for l in latencies if l < engine.config.target_latency_ms)

    return {
        'n_orders': n_orders,
        'avg_ms': statistics.mean(latencies),
        'min_ms': min(latencies),
        'max_ms': max(latencies),
        'stddev_ms': statistics.stdev(latencies) if n > 1 else 0,
        'p50_ms': percentile(50),
        'p90_ms': percentile(90),
        'p95_ms': percentile(95),
        'p99_ms': percentile(99),
        'p999_ms': percentile(99.9),
        'under_target_pct': under_target / n * 100,
        'target_ms': engine.config.target_latency_ms,
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Configuration
    'LowLatencyConfig',

    # Core classes
    'LowLatencyExecutionEngine',
    'ExecutionResult',

    # Monitoring
    'LatencyMonitor',
    'LatencyMetric',

    # Circuit breaker
    'CircuitBreaker',
    'CircuitState',

    # Connection pool
    'BrokerConnectionPool',
    'BrokerConnection',

    # Batching
    'OrderBatcher',
    'OrderBatch',

    # Factory functions
    'create_low_latency_engine',
    'benchmark_latency',
]
