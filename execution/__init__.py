"""
Execution Module
================
Order management, risk controls, and broker integration.

Submodules:
- engine: Core execution engine with risk controls
- low_latency: Production-grade low-latency execution (P0 Improvement #3)
- connection_pool: High-performance connection pooling
- broker: Broker adapters (Alpaca, Simulated)
- multi_broker: Multi-broker execution routing
- ninjatrader: NinjaTrader integration
"""

from .engine import (
    ExecutionEngine,
    ExecutionConfig,
    RiskGuard,
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    Position,
    Fill,
    PaperBroker,
)

from .low_latency import (
    LowLatencyExecutionEngine,
    LowLatencyConfig,
    ExecutionResult,
    LatencyMonitor,
    LatencyMetric,
    CircuitBreaker,
    CircuitState,
    BrokerConnectionPool,
    BrokerConnection,
    OrderBatcher,
    OrderBatch,
    create_low_latency_engine,
    benchmark_latency,
)

__all__ = [
    # Core engine
    'ExecutionEngine',
    'ExecutionConfig',
    'RiskGuard',
    'Order',
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'TimeInForce',
    'Position',
    'Fill',
    'PaperBroker',

    # Low-latency engine (P0 Improvement #3)
    'LowLatencyExecutionEngine',
    'LowLatencyConfig',
    'ExecutionResult',
    'LatencyMonitor',
    'LatencyMetric',
    'CircuitBreaker',
    'CircuitState',
    'BrokerConnectionPool',
    'BrokerConnection',
    'OrderBatcher',
    'OrderBatch',
    'create_low_latency_engine',
    'benchmark_latency',
]
