"""
Cross-Exchange Arbitrage Module
===============================
Identifies and executes arbitrage opportunities across exchanges.

Components:
- price_feeds: Multi-exchange price aggregation
- arb_detector: Arbitrage opportunity detection
- triangular_arb: Triangular arbitrage for crypto
- cex_dex_arb: CEX vs DEX price gap arbitrage
- execution: Cross-exchange execution engine
- latency: Latency monitoring and optimization
"""

from .price_feeds import (
    PriceFeed,
    ExchangePrice,
    AggregatedBook,
    MultiExchangeFeed,
)
from .arb_detector import (
    ArbDetector,
    ArbOpportunity,
    ArbType,
    ArbConfig,
)
from .triangular_arb import (
    TriangularArbDetector,
    TriangularOpportunity,
    CurrencyTriangle,
)
from .cex_dex_arb import (
    CexDexArbDetector,
    CexDexOpportunity,
    DexQuote,
)
from .execution import (
    CrossExchangeExecutor,
    ExecutionPlan,
    ExecutionResult,
    LegExecution,
)
from .latency import (
    LatencyMonitor,
    LatencyStats,
    ExchangeLatency,
)

__all__ = [
    "PriceFeed",
    "ExchangePrice",
    "AggregatedBook",
    "MultiExchangeFeed",
    "ArbDetector",
    "ArbOpportunity",
    "ArbType",
    "ArbConfig",
    "TriangularArbDetector",
    "TriangularOpportunity",
    "CurrencyTriangle",
    "CexDexArbDetector",
    "CexDexOpportunity",
    "DexQuote",
    "CrossExchangeExecutor",
    "ExecutionPlan",
    "ExecutionResult",
    "LegExecution",
    "LatencyMonitor",
    "LatencyStats",
    "ExchangeLatency",
]

__version__ = "1.0.0"
