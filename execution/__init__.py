"""
QUANT_INDUSTRY_V1 Execution Module

Order execution and management:
- Smart order routing
- Order types (market, limit, stop, etc.)
- Execution algorithms (TWAP, VWAP, etc.)
- Fill tracking and reconciliation
- Slippage modeling

Usage:
    from execution import ExecutionEngine, Order, OrderType

    engine = ExecutionEngine(broker)
    order = Order(symbol='AAPL', quantity=100, order_type=OrderType.MARKET)
    result = engine.submit(order)
"""

from .engine import (
    # Types
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    # Orders
    Order,
    OrderResult,
    Fill,
    # Engine
    ExecutionEngine,
    # Slippage
    SlippageModel,
    # Algorithms
    ExecutionAlgorithm,
    TWAPAlgorithm,
    VWAPAlgorithm,
    POVAlgorithm,
)

from .broker import (
    # Base
    BaseBroker,
    # Implementations
    SimulatedBroker,
    AlpacaBroker,
    # Types
    BrokerConfig,
    AccountInfo,
    OrderResponse,
    Position,
)

__all__ = [
    # Types
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'TimeInForce',
    # Orders
    'Order',
    'OrderResult',
    'Fill',
    # Engine
    'ExecutionEngine',
    'SlippageModel',
    # Algorithms
    'ExecutionAlgorithm',
    'TWAPAlgorithm',
    'VWAPAlgorithm',
    'POVAlgorithm',
    # Broker
    'BaseBroker',
    'SimulatedBroker',
    'AlpacaBroker',
    'BrokerConfig',
    'AccountInfo',
    'OrderResponse',
    'Position',
]
