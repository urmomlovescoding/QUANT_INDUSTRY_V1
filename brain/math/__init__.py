"""
Mathematical Foundations
========================
High-level ML/RL/DL mathematics for quantitative trading.

Includes:
- Markov Models (HMM, MDP, MCMC)
- Bayesian Inference
- Stochastic Processes
- Information Theory
- Statistical Tests
- Portfolio Optimization
- Factor Models
- Loss Functions
- Market Microstructure
"""

from .markov import (
    HiddenMarkovModel,
    MarkovRegimeDetector,
    MarkovDecisionProcess,
    BellmanOperator,
)
from .bayesian import (
    BayesianEstimator,
    KalmanFilter,
    ParticleFilter,
    GaussianProcess,
    VariationalInference,
)
from .stochastic import (
    OrnsteinUhlenbeck,
    GeometricBrownianMotion,
    JumpDiffusion,
    StochasticVolatility,
)
from .information import (
    MutualInformation,
    KLDivergence,
    EntropyEstimator,
    InformationGain,
)
from .statistics import (
    StationarityTest,
    CointegrationTest,
    CausalityTest,
    ChangePointDetection,
)
from .portfolio import (
    MeanVarianceOptimizer,
    BlackLitterman,
    RiskParity,
    HierarchicalRiskParity,
    KellyCriterion,
    CVaROptimizer,
)
from .factors import (
    CAPM,
    FamaFrench,
    StatisticalFactorModel,
    AlphaModel,
)
from .losses import (
    SharpeLoss,
    SortinoLoss,
    DrawdownLoss,
    CalmarLoss,
    DirectionalLoss,
    ProfitFactorLoss,
    RiskAdjustedReturnLoss,
    PolicyGradientLoss,
    PPOClipLoss,
    TradingRewardFunction,
)
from .microstructure import (
    KyleModel,
    AlmgrenChriss,
    RollModel,
    VPIN,
    MarketMaking,
    InformationShare,
)
from .integration import (
    # Phase 1
    IntegratedRegimeDetector,
    IntegratedPositionSizer,
    RiskManager,
    RegimeState,
    MarketRegime,
    PositionSizeResult,
    create_regime_detector,
    create_position_sizer,
    create_risk_manager,
    # Phase 2
    IntegratedAlphaGenerator,
    IntegratedExecutionOptimizer,
    AlphaSignal,
    ExecutionPlan,
    create_alpha_generator,
    create_execution_optimizer,
    # Phase 3
    IntegratedRiskMonitor,
    RegimeShiftDetector,
    RiskAlert,
    TailRiskMetrics,
    create_risk_monitor,
    create_regime_shift_detector,
)

__all__ = [
    # Markov
    'HiddenMarkovModel', 'MarkovRegimeDetector', 'MarkovDecisionProcess', 'BellmanOperator',
    # Bayesian
    'BayesianEstimator', 'KalmanFilter', 'ParticleFilter', 'GaussianProcess', 'VariationalInference',
    # Stochastic
    'OrnsteinUhlenbeck', 'GeometricBrownianMotion', 'JumpDiffusion', 'StochasticVolatility',
    # Information
    'MutualInformation', 'KLDivergence', 'EntropyEstimator', 'InformationGain',
    # Statistics
    'StationarityTest', 'CointegrationTest', 'CausalityTest', 'ChangePointDetection',
    # Portfolio
    'MeanVarianceOptimizer', 'BlackLitterman', 'RiskParity', 'HierarchicalRiskParity',
    'KellyCriterion', 'CVaROptimizer',
    # Factors
    'CAPM', 'FamaFrench', 'StatisticalFactorModel', 'AlphaModel',
    # Losses
    'SharpeLoss', 'SortinoLoss', 'DrawdownLoss', 'CalmarLoss', 'DirectionalLoss',
    'ProfitFactorLoss', 'RiskAdjustedReturnLoss', 'PolicyGradientLoss', 'PPOClipLoss',
    'TradingRewardFunction',
    # Microstructure
    'KyleModel', 'AlmgrenChriss', 'RollModel', 'VPIN', 'MarketMaking', 'InformationShare',
    # Integration Phase 1 (Regime + Position Sizing)
    'IntegratedRegimeDetector', 'IntegratedPositionSizer', 'RiskManager',
    'RegimeState', 'MarketRegime', 'PositionSizeResult',
    'create_regime_detector', 'create_position_sizer', 'create_risk_manager',
    # Integration Phase 2 (Alpha + Execution)
    'IntegratedAlphaGenerator', 'IntegratedExecutionOptimizer',
    'AlphaSignal', 'ExecutionPlan',
    'create_alpha_generator', 'create_execution_optimizer',
    # Integration Phase 3 (Risk Layer)
    'IntegratedRiskMonitor', 'RegimeShiftDetector',
    'RiskAlert', 'TailRiskMetrics',
    'create_risk_monitor', 'create_regime_shift_detector',
]
