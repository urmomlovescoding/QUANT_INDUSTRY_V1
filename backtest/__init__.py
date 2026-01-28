"""
QUANT_INDUSTRY_V1 Backtesting Module

Institutional-grade backtesting and portfolio optimization:
- Event-driven simulation
- Walk-forward analysis
- Monte Carlo validation
- Portfolio optimization (MV, Risk Parity, HRP, Black-Litterman)

Usage:
    from backtest import BacktestEngine, BacktestConfig, WalkForwardAnalyzer
    from backtest import MeanVarianceOptimizer, RiskParityOptimizer

    # Run backtest
    engine = BacktestEngine(BacktestConfig(initial_capital=100000))
    result = engine.run(strategy, data)
    print(f"Sharpe: {result.sharpe_ratio:.2f}")

    # Optimize portfolio
    optimizer = RiskParityOptimizer()
    weights = optimizer.optimize(returns, symbols)
"""

from .engine import (
    # Types
    FillModel,
    BacktestConfig,
    BacktestTrade,
    BacktestPosition,
    BacktestSnapshot,
    BacktestResult,
    # Slippage models
    SlippageModel,
    FixedSlippage,
    VolatilitySlippage,
    MarketImpactSlippage,
    # Commission models
    CommissionModel,
    PercentageCommission,
    PerShareCommission,
    # Engine
    BacktestEngine,
    # Analysis
    WalkForwardAnalyzer,
    MonteCarloAnalyzer,
)

from .portfolio import (
    # Types
    OptimizationObjective,
    PortfolioConstraints,
    PortfolioWeights,
    # Covariance
    CovarianceEstimator,
    SampleCovariance,
    ExponentialCovariance,
    LedoitWolfCovariance,
    # Optimizers
    PortfolioOptimizer,
    MeanVarianceOptimizer,
    RiskParityOptimizer,
    HierarchicalRiskParity,
    BlackLittermanOptimizer,
    # Analysis
    PortfolioAnalyzer,
)

__all__ = [
    # Backtest types
    'FillModel',
    'BacktestConfig',
    'BacktestTrade',
    'BacktestPosition',
    'BacktestSnapshot',
    'BacktestResult',
    # Slippage
    'SlippageModel',
    'FixedSlippage',
    'VolatilitySlippage',
    'MarketImpactSlippage',
    # Commission
    'CommissionModel',
    'PercentageCommission',
    'PerShareCommission',
    # Engine
    'BacktestEngine',
    # Walk-forward
    'WalkForwardAnalyzer',
    'MonteCarloAnalyzer',
    # Portfolio types
    'OptimizationObjective',
    'PortfolioConstraints',
    'PortfolioWeights',
    # Covariance
    'CovarianceEstimator',
    'SampleCovariance',
    'ExponentialCovariance',
    'LedoitWolfCovariance',
    # Optimizers
    'PortfolioOptimizer',
    'MeanVarianceOptimizer',
    'RiskParityOptimizer',
    'HierarchicalRiskParity',
    'BlackLittermanOptimizer',
    # Analysis
    'PortfolioAnalyzer',
]
