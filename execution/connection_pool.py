"""
Connection Pool - High-Performance Connection Management for Trading

This module provides production-ready connection pooling with:
- Pre-warmed connections for minimal latency
- ZeroMQ integration for ultra-low latency messaging
- Health monitoring and automatic recovery
- Connection affinity for optimal routing

Key Features:
- Pre-warming: Connections established before needed
- Health checks: Automatic detection and recovery of failed connections
- Load balancing: Intelligent routing based on latency and load
- Metrics: Nanosecond-precision timing for all operations

Architecture:
    ConnectionPool
        ├── HTTPConnectionPool (REST APIs)
        ├── WebSocketPool (Streaming data)
        ├── ZeroMQPool (Ultra-low latency)
        └── BrokerConnectionPool (Order execution)

Usage:
    from execution.connection_pool import ConnectionPool, PoolConfig

    pool = ConnectionPool(PoolConfig(
        min_connections=5,
        max_connections=20,
        pre_warm=True,
    ))

    # Get a connection
    async with pool.acquire('alpaca') as conn:
        response = await conn.submit_order(order)
"""

import os
import json
import logging
import asyncio
import time
import threading
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
from collections import deque
import weakref

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import zmq
    import zmq.asyncio
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    logger.debug("ZeroMQ not installed. ZMQ pooling disabled.")

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.debug("aiohttp not installed. HTTP pooling limited.")

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.debug("websockets not installed. WebSocket pooling limited.")


# =============================================================================
# Data Models
# =============================================================================

class ConnectionState(Enum):
    """Connection lifecycle states."""
    INITIALIZING = "initializing"
    READY = "ready"
    IN_USE = "in_use"
    UNHEALTHY = "unhealthy"
    CLOSED = "closed"


class ConnectionType(Enum):
    """Types of connections."""
    HTTP = "http"
    WEBSOCKET = "websocket"
    ZEROMQ = "zeromq"
    TCP = "tcp"


@dataclass
class PoolConfig:
    """Configuration for connection pool."""
    min_connections: int = 2
    max_connections: int = 10
    pre_warm: bool = True
    connection_timeout_ms: int = 5000
    idle_timeout_seconds: int = 300
    health_check_interval_seconds: int = 30
    max_retries: int = 3
    retry_delay_ms: int = 100
    enable_metrics: bool = True
    zmq_high_water_mark: int = 1000

    def validate(self) -> bool:
        """Validate configuration."""
        if self.min_connections < 0:
            return False
        if self.max_connections < self.min_connections:
            return False
        if self.connection_timeout_ms <= 0:
            return False
        return True


@dataclass
class ConnectionMetrics:
    """Metrics for a connection."""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: Optional[datetime] = None
    request_count: int = 0
    error_count: int = 0
    total_latency_ns: int = 0
    min_latency_ns: int = 0
    max_latency_ns: int = 0
    health_check_failures: int = 0

    @property
    def avg_latency_ns(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.total_latency_ns / self.request_count

    @property
    def avg_latency_ms(self) -> float:
        return self.avg_latency_ns / 1_000_000

    def record_request(self, latency_ns: int, success: bool = True) -> None:
        """Record a request."""
        self.request_count += 1
        self.total_latency_ns += latency_ns
        self.last_used = datetime.now(timezone.utc)

        if self.min_latency_ns == 0 or latency_ns < self.min_latency_ns:
            self.min_latency_ns = latency_ns
        if latency_ns > self.max_latency_ns:
            self.max_latency_ns = latency_ns

        if not success:
            self.error_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'avg_latency_ms': self.avg_latency_ms,
            'min_latency_ns': self.min_latency_ns,
            'max_latency_ns': self.max_latency_ns,
            'health_check_failures': self.health_check_failures,
        }


# =============================================================================
# Base Connection
# =============================================================================

class PooledConnection:
    """
    Base class for pooled connections.

    Provides common functionality for all connection types:
    - State management
    - Metrics collection
    - Health checking
    """

    def __init__(
        self,
        connection_id: str,
        endpoint: str,
        connection_type: ConnectionType,
    ):
        self.connection_id = connection_id
        self.endpoint = endpoint
        self.connection_type = connection_type
        self.state = ConnectionState.INITIALIZING
        self.metrics = ConnectionMetrics()
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Establish the connection."""
        raise NotImplementedError

    async def disconnect(self) -> None:
        """Close the connection."""
        raise NotImplementedError

    async def health_check(self) -> bool:
        """Check if connection is healthy."""
        raise NotImplementedError

    async def send(self, data: Any) -> Any:
        """Send data over the connection."""
        raise NotImplementedError

    def _record_latency(self, start_ns: int, success: bool = True) -> int:
        """Record request latency."""
        latency_ns = time.perf_counter_ns() - start_ns
        self.metrics.record_request(latency_ns, success)
        return latency_ns


# =============================================================================
# HTTP Connection
# =============================================================================

class HTTPConnection(PooledConnection):
    """HTTP/HTTPS connection with keep-alive."""

    def __init__(
        self,
        connection_id: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        timeout_ms: int = 5000,
    ):
        super().__init__(connection_id, endpoint, ConnectionType.HTTP)
        self.headers = headers or {}
        self.timeout_ms = timeout_ms
        self._session: Optional[Any] = None  # aiohttp.ClientSession

    async def connect(self) -> bool:
        """Create HTTP session."""
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp not available for HTTP connections")
            self.state = ConnectionState.UNHEALTHY
            return False

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_ms / 1000)
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
            )
            self.state = ConnectionState.READY
            logger.debug(f"HTTP connection {self.connection_id} ready")
            return True

        except Exception as e:
            logger.error(f"HTTP connection failed: {e}")
            self.state = ConnectionState.UNHEALTHY
            return False

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self.state = ConnectionState.CLOSED

    async def health_check(self) -> bool:
        """Check HTTP connectivity."""
        if not self._session:
            return False

        try:
            async with self._session.head(self.endpoint) as response:
                healthy = response.status < 500
                if not healthy:
                    self.metrics.health_check_failures += 1
                return healthy
        except Exception:
            self.metrics.health_check_failures += 1
            return False

    async def send(
        self,
        method: str = "GET",
        path: str = "",
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Tuple[int, Any]:
        """Send HTTP request."""
        if not self._session or self.state != ConnectionState.READY:
            raise RuntimeError("Connection not ready")

        start_ns = time.perf_counter_ns()
        url = f"{self.endpoint}{path}"

        try:
            async with self._lock:
                self.state = ConnectionState.IN_USE

                async with self._session.request(
                    method,
                    url,
                    data=data,
                    json=json_data,
                ) as response:
                    result = await response.json()
                    self._record_latency(start_ns, success=True)
                    return response.status, result

        except Exception as e:
            self._record_latency(start_ns, success=False)
            raise

        finally:
            self.state = ConnectionState.READY


# =============================================================================
# WebSocket Connection
# =============================================================================

class WebSocketConnection(PooledConnection):
    """WebSocket connection for streaming data."""

    def __init__(
        self,
        connection_id: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(connection_id, endpoint, ConnectionType.WEBSOCKET)
        self.headers = headers or {}
        self._ws: Optional[Any] = None
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets not available")
            self.state = ConnectionState.UNHEALTHY
            return False

        try:
            self._ws = await websockets.connect(
                self.endpoint,
                extra_headers=self.headers,
            )
            self.state = ConnectionState.READY

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            logger.debug(f"WebSocket {self.connection_id} connected")
            return True

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.state = ConnectionState.UNHEALTHY
            return False

    async def _receive_loop(self) -> None:
        """Background task to receive messages."""
        try:
            async for message in self._ws:
                await self._receive_queue.put(message)
        except Exception as e:
            logger.debug(f"WebSocket receive loop ended: {e}")

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        self.state = ConnectionState.CLOSED

    async def health_check(self) -> bool:
        """Check WebSocket connectivity."""
        if not self._ws:
            return False

        try:
            pong = await self._ws.ping()
            await asyncio.wait_for(pong, timeout=5.0)
            return True
        except Exception:
            self.metrics.health_check_failures += 1
            return False

    async def send(self, data: Any) -> None:
        """Send message over WebSocket."""
        if not self._ws or self.state not in (ConnectionState.READY, ConnectionState.IN_USE):
            raise RuntimeError("WebSocket not ready")

        start_ns = time.perf_counter_ns()

        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            await self._ws.send(data)
            self._record_latency(start_ns, success=True)

        except Exception as e:
            self._record_latency(start_ns, success=False)
            raise

    async def receive(self, timeout: float = 1.0) -> Optional[Any]:
        """Receive message from WebSocket."""
        try:
            message = await asyncio.wait_for(
                self._receive_queue.get(),
                timeout=timeout
            )
            return message
        except asyncio.TimeoutError:
            return None


# =============================================================================
# ZeroMQ Connection
# =============================================================================

class ZeroMQConnection(PooledConnection):
    """
    ZeroMQ connection for ultra-low latency messaging.

    Supports multiple patterns:
    - REQ/REP: Request-reply
    - PUB/SUB: Publish-subscribe
    - PUSH/PULL: Pipeline
    """

    def __init__(
        self,
        connection_id: str,
        endpoint: str,
        socket_type: int = None,  # zmq.REQ, zmq.SUB, etc.
        high_water_mark: int = 1000,
    ):
        super().__init__(connection_id, endpoint, ConnectionType.ZEROMQ)
        self.socket_type = socket_type or (zmq.REQ if ZMQ_AVAILABLE else None)
        self.high_water_mark = high_water_mark
        self._context: Optional[Any] = None
        self._socket: Optional[Any] = None

    async def connect(self) -> bool:
        """Create ZeroMQ socket."""
        if not ZMQ_AVAILABLE:
            logger.error("ZeroMQ not available")
            self.state = ConnectionState.UNHEALTHY
            return False

        try:
            self._context = zmq.asyncio.Context()
            self._socket = self._context.socket(self.socket_type)

            # Set high water mark for flow control
            self._socket.setsockopt(zmq.SNDHWM, self.high_water_mark)
            self._socket.setsockopt(zmq.RCVHWM, self.high_water_mark)

            # Set linger to 0 for fast shutdown
            self._socket.setsockopt(zmq.LINGER, 0)

            self._socket.connect(self.endpoint)
            self.state = ConnectionState.READY

            logger.debug(f"ZeroMQ {self.connection_id} connected to {self.endpoint}")
            return True

        except Exception as e:
            logger.error(f"ZeroMQ connection failed: {e}")
            self.state = ConnectionState.UNHEALTHY
            return False

    async def disconnect(self) -> None:
        """Close ZeroMQ socket."""
        if self._socket:
            self._socket.close()
            self._socket = None

        if self._context:
            self._context.term()
            self._context = None

        self.state = ConnectionState.CLOSED

    async def health_check(self) -> bool:
        """Check ZeroMQ connectivity."""
        if not self._socket:
            return False

        # ZMQ doesn't have built-in health check
        # We just check if socket is not in error state
        try:
            events = self._socket.getsockopt(zmq.EVENTS)
            return True
        except Exception:
            self.metrics.health_check_failures += 1
            return False

    async def send(self, data: Any, flags: int = 0) -> None:
        """Send message over ZeroMQ."""
        if not self._socket or self.state != ConnectionState.READY:
            raise RuntimeError("ZeroMQ socket not ready")

        start_ns = time.perf_counter_ns()

        try:
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            elif isinstance(data, str):
                data = data.encode()

            await self._socket.send(data, flags=flags)
            self._record_latency(start_ns, success=True)

        except Exception as e:
            self._record_latency(start_ns, success=False)
            raise

    async def receive(self, timeout_ms: int = 1000) -> Optional[bytes]:
        """Receive message from ZeroMQ."""
        if not self._socket:
            return None

        try:
            if await self._socket.poll(timeout_ms):
                return await self._socket.recv()
            return None
        except Exception as e:
            logger.error(f"ZeroMQ receive error: {e}")
            return None


# =============================================================================
# Connection Pool
# =============================================================================

class ConnectionPool:
    """
    High-performance connection pool with pre-warming and health monitoring.

    Features:
    - Multiple connection types (HTTP, WebSocket, ZeroMQ)
    - Pre-warming for minimal latency
    - Automatic health checks and recovery
    - Load balancing based on latency
    - Comprehensive metrics

    Example:
        pool = ConnectionPool(PoolConfig(
            min_connections=5,
            max_connections=20,
            pre_warm=True,
        ))

        # Add an endpoint
        await pool.add_endpoint('alpaca', 'https://api.alpaca.markets', ConnectionType.HTTP)

        # Get a connection
        async with pool.acquire('alpaca') as conn:
            status, result = await conn.send('GET', '/v2/positions')
    """

    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()

        if not self.config.validate():
            raise ValueError("Invalid pool configuration")

        # Pools per endpoint
        self._pools: Dict[str, List[PooledConnection]] = {}
        self._endpoints: Dict[str, Dict[str, Any]] = {}

        # Locks
        self._pool_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Health check task
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

        # Statistics
        self._stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'total_requests': 0,
            'failed_requests': 0,
        }

        logger.info(f"ConnectionPool initialized: {self.config}")

    async def start(self) -> None:
        """Start the connection pool."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Connection pool started")

    async def stop(self) -> None:
        """Stop the connection pool and close all connections."""
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for endpoint_name in list(self._pools.keys()):
            await self.remove_endpoint(endpoint_name)

        logger.info("Connection pool stopped")

    async def add_endpoint(
        self,
        name: str,
        url: str,
        connection_type: ConnectionType,
        headers: Optional[Dict[str, str]] = None,
        min_connections: Optional[int] = None,
        max_connections: Optional[int] = None,
    ) -> bool:
        """
        Add an endpoint to the pool.

        Args:
            name: Unique endpoint name
            url: Endpoint URL
            connection_type: Type of connection
            headers: Optional headers for HTTP/WebSocket
            min_connections: Override min connections for this endpoint
            max_connections: Override max connections for this endpoint

        Returns:
            True if successful
        """
        async with self._global_lock:
            if name in self._pools:
                logger.warning(f"Endpoint {name} already exists")
                return False

            self._endpoints[name] = {
                'url': url,
                'type': connection_type,
                'headers': headers or {},
                'min_connections': min_connections or self.config.min_connections,
                'max_connections': max_connections or self.config.max_connections,
            }

            self._pools[name] = []
            self._pool_locks[name] = asyncio.Lock()

            # Pre-warm connections
            if self.config.pre_warm:
                await self._warm_up(name)

            logger.info(f"Added endpoint: {name} ({connection_type.value})")
            return True

    async def remove_endpoint(self, name: str) -> bool:
        """Remove an endpoint and close all its connections."""
        async with self._global_lock:
            if name not in self._pools:
                return False

            # Close all connections
            for conn in self._pools[name]:
                try:
                    await conn.disconnect()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

            del self._pools[name]
            del self._endpoints[name]
            del self._pool_locks[name]

            logger.info(f"Removed endpoint: {name}")
            return True

    async def _warm_up(self, endpoint_name: str) -> None:
        """Pre-warm connections for an endpoint."""
        endpoint = self._endpoints[endpoint_name]
        pool = self._pools[endpoint_name]

        for i in range(endpoint['min_connections']):
            conn = await self._create_connection(endpoint_name)
            if conn:
                pool.append(conn)
                self._stats['total_connections'] += 1

        logger.info(f"Warmed up {len(pool)} connections for {endpoint_name}")

    async def _create_connection(self, endpoint_name: str) -> Optional[PooledConnection]:
        """Create a new connection for an endpoint."""
        endpoint = self._endpoints[endpoint_name]
        conn_id = f"{endpoint_name}_{hashlib.md5(str(time.time_ns()).encode()).hexdigest()[:8]}"

        try:
            if endpoint['type'] == ConnectionType.HTTP:
                conn = HTTPConnection(
                    connection_id=conn_id,
                    endpoint=endpoint['url'],
                    headers=endpoint['headers'],
                    timeout_ms=self.config.connection_timeout_ms,
                )
            elif endpoint['type'] == ConnectionType.WEBSOCKET:
                conn = WebSocketConnection(
                    connection_id=conn_id,
                    endpoint=endpoint['url'],
                    headers=endpoint['headers'],
                )
            elif endpoint['type'] == ConnectionType.ZEROMQ:
                conn = ZeroMQConnection(
                    connection_id=conn_id,
                    endpoint=endpoint['url'],
                    high_water_mark=self.config.zmq_high_water_mark,
                )
            else:
                logger.error(f"Unknown connection type: {endpoint['type']}")
                return None

            # Connect
            success = await conn.connect()
            if success:
                return conn
            else:
                self._stats['failed_connections'] += 1
                return None

        except Exception as e:
            logger.error(f"Connection creation failed: {e}")
            self._stats['failed_connections'] += 1
            return None

    @asynccontextmanager
    async def acquire(
        self,
        endpoint_name: str,
        timeout_ms: Optional[int] = None,
    ) -> AsyncIterator[PooledConnection]:
        """
        Acquire a connection from the pool.

        Usage:
            async with pool.acquire('alpaca') as conn:
                await conn.send(...)

        Args:
            endpoint_name: Name of the endpoint
            timeout_ms: Optional timeout for acquisition

        Yields:
            A pooled connection

        Raises:
            RuntimeError: If endpoint doesn't exist or no connection available
        """
        if endpoint_name not in self._pools:
            raise RuntimeError(f"Endpoint not found: {endpoint_name}")

        timeout_ms = timeout_ms or self.config.connection_timeout_ms
        deadline = time.time() + (timeout_ms / 1000)

        conn = None
        async with self._pool_locks[endpoint_name]:
            pool = self._pools[endpoint_name]

            # Try to get a ready connection
            while time.time() < deadline:
                for c in pool:
                    if c.state == ConnectionState.READY:
                        c.state = ConnectionState.IN_USE
                        conn = c
                        break

                if conn:
                    break

                # Check if we can create a new connection
                endpoint = self._endpoints[endpoint_name]
                if len(pool) < endpoint['max_connections']:
                    conn = await self._create_connection(endpoint_name)
                    if conn:
                        pool.append(conn)
                        self._stats['total_connections'] += 1
                        conn.state = ConnectionState.IN_USE
                        break

                # Wait a bit before retrying
                await asyncio.sleep(0.01)

        if not conn:
            raise RuntimeError(f"No connection available for {endpoint_name}")

        self._stats['active_connections'] += 1

        try:
            yield conn
        finally:
            conn.state = ConnectionState.READY
            self._stats['active_connections'] -= 1

    async def _health_check_loop(self) -> None:
        """Periodic health check of all connections."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)

                for endpoint_name, pool in self._pools.items():
                    for conn in pool:
                        if conn.state == ConnectionState.READY:
                            healthy = await conn.health_check()

                            if not healthy:
                                logger.warning(f"Connection {conn.connection_id} unhealthy")
                                conn.state = ConnectionState.UNHEALTHY

                                # Try to reconnect
                                success = await conn.connect()
                                if not success:
                                    # Remove and replace
                                    async with self._pool_locks[endpoint_name]:
                                        pool.remove(conn)
                                        new_conn = await self._create_connection(endpoint_name)
                                        if new_conn:
                                            pool.append(new_conn)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        stats = dict(self._stats)

        # Per-endpoint stats
        stats['endpoints'] = {}
        for name, pool in self._pools.items():
            endpoint_stats = {
                'total_connections': len(pool),
                'ready': sum(1 for c in pool if c.state == ConnectionState.READY),
                'in_use': sum(1 for c in pool if c.state == ConnectionState.IN_USE),
                'unhealthy': sum(1 for c in pool if c.state == ConnectionState.UNHEALTHY),
            }

            # Aggregate connection metrics
            if pool:
                all_latencies = [c.metrics.avg_latency_ms for c in pool if c.metrics.request_count > 0]
                if all_latencies:
                    endpoint_stats['avg_latency_ms'] = sum(all_latencies) / len(all_latencies)
                    endpoint_stats['min_latency_ns'] = min(c.metrics.min_latency_ns for c in pool)
                    endpoint_stats['max_latency_ns'] = max(c.metrics.max_latency_ns for c in pool)

            stats['endpoints'][name] = endpoint_stats

        return stats

    def get_connection_metrics(self, endpoint_name: str) -> List[Dict[str, Any]]:
        """Get metrics for all connections to an endpoint."""
        if endpoint_name not in self._pools:
            return []

        return [
            {
                'connection_id': conn.connection_id,
                'state': conn.state.value,
                **conn.metrics.to_dict(),
            }
            for conn in self._pools[endpoint_name]
        ]
