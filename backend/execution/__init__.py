"""
Execution Module for QUANT INDUSTRY
===================================
P0 Critical Feature: Execution modes and trade execution.

Implements parity with quant-platform execution system:
- ExecutionMode enum (SIGNAL_ONLY, AUTO_PAPER, AUTO_LIVE)
- ExecutionEngine with risk integration
- Kill switch for emergency stops
- Trade Journal for audit trail
- Broker adapters (Paper, Alpaca)
- Trade tracking and audit trail

NEW (v10.1):
- Almgren-Chriss slippage model
- VWAP/TWAP/Implementation Shortfall algorithms
- Dynamic position sizing with vol targeting
- Kelly criterion sizing
"""

from .executor import (
    ExecutionMode,
    ExecutionDecision,
    OrderTracker,
    ExecutionEngine,
)
from .kill_switch import KillSwitch, KillSwitchEvent, get_kill_switch
from .risk_engine import RiskEngine, RiskCheckResult, RiskMode
from .trade_journal import (
    TradeAction,
    TradeResult,
    JournalEntry,
    DailySummary,
    TradeJournal,
    get_trade_journal,
)
from .broker_adapter import (
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    Order,
    Position,
    AccountInfo,
    BrokerAdapter,
    PaperBroker,
)
from .alpaca_broker import AlpacaBroker

# New institutional-grade modules
from .execution_algorithms import (
    AlmgrenChrissSlippageModel,
    SlippageEstimate,
    estimate_slippage,
    ExecutionStrategy,
    VWAPAlgorithm,
    TWAPAlgorithm,
    ImplementationShortfallAlgorithm,
    IcebergAlgorithm,
    AdaptiveExecutionAlgorithm,
    ExecutionEngine as AlgoExecutionEngine,
    get_execution_engine,
)
from .position_sizing import (
    SizingMethod,
    PositionSizeResult,
    DynamicPositionSizer,
    VolatilityScaler,
    calculate_position_size,
    get_kelly_size,
)

__all__ = [
    # Execution
    "ExecutionMode",
    "ExecutionDecision",
    "OrderTracker",
    "ExecutionEngine",
    # Kill Switch
    "KillSwitch",
    "KillSwitchEvent",
    "get_kill_switch",
    # Risk
    "RiskEngine",
    "RiskCheckResult",
    "RiskMode",
    # Trade Journal
    "TradeAction",
    "TradeResult",
    "JournalEntry",
    "DailySummary",
    "TradeJournal",
    "get_trade_journal",
    # Broker Adapter
    "OrderType",
    "OrderSide",
    "OrderStatus",
    "TimeInForce",
    "Order",
    "Position",
    "AccountInfo",
    "BrokerAdapter",
    "PaperBroker",
    "AlpacaBroker",
    # NEW: Slippage & Execution Algorithms
    "AlmgrenChrissSlippageModel",
    "SlippageEstimate",
    "estimate_slippage",
    "ExecutionStrategy",
    "VWAPAlgorithm",
    "TWAPAlgorithm",
    "ImplementationShortfallAlgorithm",
    "IcebergAlgorithm",
    "AdaptiveExecutionAlgorithm",
    "AlgoExecutionEngine",
    "get_execution_engine",
    # NEW: Position Sizing
    "SizingMethod",
    "PositionSizeResult",
    "DynamicPositionSizer",
    "VolatilityScaler",
    "calculate_position_size",
    "get_kelly_size",
]
