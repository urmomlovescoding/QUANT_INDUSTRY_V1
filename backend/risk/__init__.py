# QUANT INDUSTRY Risk Module
# Institutional-grade risk management and analysis

from .monte_carlo import (
    MonteCarloSimulator,
    PortfolioMonteCarloSimulator,
    MonteCarloResult,
    StressScenario,
    StressParameters,
    STRESS_SCENARIOS,
    quick_var,
    stress_test_portfolio,
)

from .realtime_monitor import (
    RealTimeRiskMonitor,
    RiskAlert,
    RiskThresholds,
    PortfolioState,
    AlertSeverity,
    AlertType,
    get_risk_monitor,
)

from .tail_risk import (
    TailRiskManager,
    TailRiskMetrics,
    TailRiskRegime,
    LiquidityAdjustedVaR,
    LiquidityMetrics,
    quick_tail_risk_check,
    calculate_liq_var,
)

# Risk Decomposition & Scenario Engine
from .factor_model import FactorRiskModel, get_factor_model
from .scenario_engine import ScenarioEngine, get_scenario_engine
from .attribution import AttributionEngine, get_attribution_engine
from .risk_budget import RiskBudgetManager, get_risk_budget_manager
from .correlation_monitor import CorrelationMonitor, get_correlation_monitor

__all__ = [
    # Monte Carlo
    "MonteCarloSimulator",
    "PortfolioMonteCarloSimulator",
    "MonteCarloResult",
    "StressScenario",
    "StressParameters",
    "STRESS_SCENARIOS",
    "quick_var",
    "stress_test_portfolio",
    # Real-time monitoring
    "RealTimeRiskMonitor",
    "RiskAlert",
    "RiskThresholds",
    "PortfolioState",
    "AlertSeverity",
    "AlertType",
    "get_risk_monitor",
    # Tail Risk & Liquidity
    "TailRiskManager",
    "TailRiskMetrics",
    "TailRiskRegime",
    "LiquidityAdjustedVaR",
    "LiquidityMetrics",
    "quick_tail_risk_check",
    "calculate_liq_var",
    # Factor Risk Model
    "FactorRiskModel",
    "get_factor_model",
    # Scenario Engine
    "ScenarioEngine",
    "get_scenario_engine",
    # Attribution
    "AttributionEngine",
    "get_attribution_engine",
    # Risk Budget
    "RiskBudgetManager",
    "get_risk_budget_manager",
    # Correlation Monitor
    "CorrelationMonitor",
    "get_correlation_monitor",
]
