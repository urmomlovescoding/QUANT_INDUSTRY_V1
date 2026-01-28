# QUANT INDUSTRY Backtest Package
# Strategy backtesting and performance analysis
#
# v10.1: Added RealisticBacktestEngine with Almgren-Chriss slippage

from .engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    Equity,
    PerformanceMetrics,
    Trade,
)
from .strategies import MACrossoverStrategy, MomentumStrategy, RSIStrategy, Strategy

# NEW: Realistic backtesting with proper cost modeling
from .realistic_engine import (
    SlippageMode,
    RealisticBacktestConfig,
    RealisticTrade,
    RealisticMetrics,
    RealisticBacktestEngine,
    run_realistic_backtest,
    compare_slippage_modes,
)

__all__ = [
    # Original engine
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "Equity",
    "PerformanceMetrics",
    "Trade",
    # Strategies
    "MACrossoverStrategy",
    "MomentumStrategy",
    "RSIStrategy",
    "Strategy",
    # NEW: Realistic engine
    "SlippageMode",
    "RealisticBacktestConfig",
    "RealisticTrade",
    "RealisticMetrics",
    "RealisticBacktestEngine",
    "run_realistic_backtest",
    "compare_slippage_modes",
]
