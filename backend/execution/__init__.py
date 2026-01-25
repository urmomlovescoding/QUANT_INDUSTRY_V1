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
]
