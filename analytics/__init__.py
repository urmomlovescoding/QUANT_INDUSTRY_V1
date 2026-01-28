"""
QUANT_INDUSTRY_V1 Analytics Module

Comprehensive analytics, portfolio optimization, and market analysis.
"""

from .options import (
    BlackScholes,
    GammaExposure,
    OptionsAnalyzer,
)
from .microstructure import (
    TradeClassifier,
    VPINCalculator,
    KyleLambdaEstimator,
    OrderFlowImbalanceAnalyzer,
    MicrostructureAnalyzer,
)
from .portfolio_optimization import (
    PortfolioResult,
    RiskParityOptimizer,
    BlackLittermanOptimizer,
    HierarchicalRiskParity,
    MeanCVaROptimizer,
    KellyCriterionOptimizer,
    MaxDiversificationOptimizer,
    PortfolioOptimizer,
)
from .regime_detection import (
    MarketRegime,
    VolatilityRegime,
    TrendRegime,
    RegimeState,
    HMMRegimeDetector,
    VolatilityRegimeClassifier,
    TrendRegimeClassifier,
    RiskOnOffDetector,
    MarketRegimeDetector,
    MultiTimeframeRegimeFusion,
)
from .attribution import (
    AttributionMethod,
    BrinsonAttribution,
    FactorExposure,
    RiskAttribution,
    BrinsonAttributor,
    FactorAttributor,
    RiskAttributor,
    TransactionCostAnalyzer,
    StrategyAttributor,
    PerformanceAnalyzer,
)

__all__ = [
    # Options
    'BlackScholes',
    'GammaExposure',
    'OptionsAnalyzer',
    # Microstructure
    'TradeClassifier',
    'VPINCalculator',
    'KyleLambdaEstimator',
    'OrderFlowImbalanceAnalyzer',
    'MicrostructureAnalyzer',
    # Portfolio Optimization
    'PortfolioResult',
    'RiskParityOptimizer',
    'BlackLittermanOptimizer',
    'HierarchicalRiskParity',
    'MeanCVaROptimizer',
    'KellyCriterionOptimizer',
    'MaxDiversificationOptimizer',
    'PortfolioOptimizer',
    # Regime Detection
    'MarketRegime',
    'VolatilityRegime',
    'TrendRegime',
    'RegimeState',
    'HMMRegimeDetector',
    'VolatilityRegimeClassifier',
    'TrendRegimeClassifier',
    'RiskOnOffDetector',
    'MarketRegimeDetector',
    'MultiTimeframeRegimeFusion',
    # Attribution
    'AttributionMethod',
    'BrinsonAttribution',
    'FactorExposure',
    'RiskAttribution',
    'BrinsonAttributor',
    'FactorAttributor',
    'RiskAttributor',
    'TransactionCostAnalyzer',
    'StrategyAttributor',
    'PerformanceAnalyzer',
]
