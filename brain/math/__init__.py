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
]
