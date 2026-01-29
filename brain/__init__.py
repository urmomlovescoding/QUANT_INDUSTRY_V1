"""
QUANT_INDUSTRY_V1 Brain Module

ML/AI components for signal generation:
- Feature engineering (40+ technical indicators)
- Regime detection (HMM, volatility, trend-based)
- Model training pipeline (walk-forward validation)
- Reinforcement learning (PPO, A2C)
- Safety monitoring

Usage:
    from brain import FeatureComputer, EnsembleRegimeDetector, SafetyMonitor
"""

# Features - only import what exists
from .features import (
    FeatureCategory,
    FeatureDefinition,
    FeatureVector,
    sma,
    ema,
    rsi,
    macd,
    bollinger_bands,
    atr,
    adx,
    stochastic,
    obv,
    vwap,
    williams_r,
    cci,
    mfi,
    FeatureComputer,
)

# Alias for compatibility
FeatureConfig = FeatureDefinition

# Models
from .models import (
    ModelType,
    PredictionType,
    Prediction,
    ModelMetrics,
    BaseModel,
    XGBoostModel,
    LightGBMModel,
    RandomForestModel,
    RuleBasedModel,
    EnsembleModel,
)
# Alias for compatibility
ModelConfig = ModelType

# Regime detection
from .regime import (
    MarketRegime,
    RegimeState,
    RegimeTransition,
    BaseRegimeDetector,
    HMMRegimeDetector,
    VolatilityRegimeDetector,
    TrendRegimeDetector,
    EnsembleRegimeDetector,
    RegimeFilter,
)

# Training
from .training import (
    ValidationMethod,
    TrainingConfig,
    TrainingMetrics,
    TrainingResult,
    TimeSeriesSplitter,
    MetricsCalculator,
    ModelTrainer,
    ModelSelector,
    HyperparameterTuner,
)

# RL Environment
from .rl_env import (
    ActionType,
    EnvConfig,
    EnvState,
    RewardFunction,
    SimpleReturnReward,
    SharpeReward,
    RiskAdjustedReward,
    ProfitFactorReward,
    TradingEnvironment,
    VectorizedTradingEnv,
)

# RL Agents
from .rl_agent import (
    NeuralNetwork,
    ActivationFunction,
    PPOConfig,
    RolloutBuffer,
    PPOAgent,
    A2CAgent,
)

# RL Training
from .rl_trainer import (
    TrainerConfig,
    RLTrainer,
    WalkForwardRLTrainer,
    CurriculumScheduler,
)

# Statistics
from .statistics import (
    BayesianPrior,
    BayesianPosterior,
    BayesianEstimator,
    BayesianSharpeEstimator,
    MCResult,
    MonteCarloSimulator,
    StatisticalTests,
    DistributionFitter,
    CorrelationAnalyzer,
)

# Physics models
from .physics import (
    IsingMarket,
    MeanFieldMarket,
    OrnsteinUhlenbeckProcess,
    AgentType,
    Agent,
    AgentBasedMarket,
    ContagionNetwork,
    OrderBook,
)

# Explainability
from .explainability import (
    FeatureContribution,
    PredictionExplanation,
    CounterfactualExplanation,
    FeatureImportanceAnalyzer,
    SHAPExplainer,
    DecisionPathExplainer,
    CounterfactualExplainer,
    ExplanationGenerator,
)

# Safety
from .safety import (
    HealthStatus,
    HealthCheck,
    SystemHealth,
    DriftType,
    DriftResult,
    DriftDetector,
    AnomalyDetector,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    SelfDiagnostics,
    DegradationLevel,
    GracefulDegradation,
    SafetyMonitor,
)

# Ensemble
from .ensemble import (
    EnsembleMethod,
    ModelPrediction,
    EnsemblePrediction,
    ModelPerformance,
    WeightedAverageEnsemble,
    StackingEnsemble,
    BayesianModelAveraging,
    DynamicWeightOptimizer,
    RegimeAdaptiveEnsemble,
    DiversityWeightedEnsemble,
    EnsembleCombiner,
)

# Feedback Loop (Learn-Log-Repeat Cycle)
from .feedback_loop import (
    TradeOutcome,
    LearningPhase,
    TradeResult,
    ConvergenceTargets,
    PerformanceMetrics,
    LearningState,
    FeedbackEvent,
    MetricsDatabase,
    OnlineLearner,
    ConvergenceTracker,
    FeedbackLoop,
    get_feedback_loop,
    reset_feedback_loop,
)

# PyTorch Neural Networks (import subpackage)
from . import nn
from . import rl

__all__ = [
    # Features
    'FeatureCategory',
    'FeatureDefinition',
    'FeatureVector',
    'FeatureConfig',
    'sma', 'ema', 'rsi', 'macd', 'bollinger_bands',
    'atr', 'adx', 'stochastic', 'obv', 'vwap',
    'williams_r', 'cci', 'mfi',
    'FeatureComputer',
    # Models
    'ModelConfig', 'Prediction', 'ModelMetrics',
    'BaseModel', 'XGBoostModel', 'LightGBMModel',
    'RandomForestModel', 'RuleBasedModel', 'EnsembleModel',
    # Regime
    'MarketRegime', 'RegimeState', 'RegimeTransition',
    'BaseRegimeDetector', 'HMMRegimeDetector',
    'VolatilityRegimeDetector', 'TrendRegimeDetector',
    'EnsembleRegimeDetector', 'RegimeFilter',
    # Training
    'ValidationMethod', 'TrainingConfig', 'TrainingMetrics', 'TrainingResult',
    'TimeSeriesSplitter', 'MetricsCalculator',
    'ModelTrainer', 'ModelSelector', 'HyperparameterTuner',
    # RL Env
    'ActionType', 'EnvConfig', 'EnvState',
    'RewardFunction', 'SimpleReturnReward', 'SharpeReward',
    'RiskAdjustedReward', 'ProfitFactorReward',
    'TradingEnvironment', 'VectorizedTradingEnv',
    # RL Agents
    'NeuralNetwork', 'ActivationFunction',
    'PPOConfig', 'RolloutBuffer', 'PPOAgent', 'A2CAgent',
    # RL Training
    'TrainerConfig', 'RLTrainer', 'WalkForwardRLTrainer', 'CurriculumScheduler',
    # Statistics
    'BayesianPrior', 'BayesianPosterior', 'BayesianEstimator', 'BayesianSharpeEstimator',
    'MCResult', 'MonteCarloSimulator', 'StatisticalTests',
    'DistributionFitter', 'CorrelationAnalyzer',
    # Physics
    'IsingMarket', 'MeanFieldMarket', 'OrnsteinUhlenbeckProcess',
    'AgentType', 'Agent', 'AgentBasedMarket', 'ContagionNetwork', 'OrderBook',
    # Explainability
    'FeatureContribution', 'PredictionExplanation', 'CounterfactualExplanation',
    'FeatureImportanceAnalyzer', 'SHAPExplainer', 'DecisionPathExplainer',
    'CounterfactualExplainer', 'ExplanationGenerator',
    # Safety
    'HealthStatus', 'HealthCheck', 'SystemHealth',
    'DriftType', 'DriftResult', 'DriftDetector', 'AnomalyDetector',
    'CircuitState', 'CircuitBreakerConfig', 'CircuitBreaker',
    'SelfDiagnostics', 'DegradationLevel', 'GracefulDegradation', 'SafetyMonitor',
    # Ensemble
    'EnsembleMethod', 'ModelPrediction', 'EnsemblePrediction', 'ModelPerformance',
    'WeightedAverageEnsemble', 'StackingEnsemble', 'BayesianModelAveraging',
    'DynamicWeightOptimizer', 'RegimeAdaptiveEnsemble', 'DiversityWeightedEnsemble',
    'EnsembleCombiner',
    # Feedback Loop
    'TradeOutcome', 'LearningPhase', 'TradeResult', 'ConvergenceTargets',
    'PerformanceMetrics', 'LearningState', 'FeedbackEvent',
    'MetricsDatabase', 'OnlineLearner', 'ConvergenceTracker',
    'FeedbackLoop', 'get_feedback_loop', 'reset_feedback_loop',
]
