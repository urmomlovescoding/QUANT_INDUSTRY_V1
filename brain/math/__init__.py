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
    IntegratedRegimeDetector,
    IntegratedPositionSizer,
    RiskManager,
    RegimeState,
    MarketRegime,
    PositionSizeResult,
    create_regime_detector,
    create_position_sizer,
    create_risk_manager,
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
    # Integration (TradingBrain bridge)
    'IntegratedRegimeDetector', 'IntegratedPositionSizer', 'RiskManager',
    'RegimeState', 'MarketRegime', 'PositionSizeResult',
    'create_regime_detector', 'create_position_sizer', 'create_risk_manager',
]
