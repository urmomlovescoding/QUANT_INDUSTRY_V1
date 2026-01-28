# QUANT INDUSTRY Brain Package
# ML/AI modules for neural analysis, regime detection, and algorithmic trading
#
# v10.1: Added confidence calibration for signal reliability

from .algo_bot import AlgoBot, BotState, TradingStrategy
from .neural_engine import NeuralEngine, NeuralSignal, PatternType
from .regime_detector import MarketRegime, RegimeDetector, RegimeState
from .trading_brain import BrainCycle, BrainDecision, TradingBrain

# Model calibration
from .confidence_calibration import (
    ConfidenceCalibrator,
    CalibrationReport,
    CalibrationBin,
    PredictionRecord,
    TemperatureScaler,
    get_confidence_calibrator,
)

# Advanced ML/RL modules
try:
    from .beast_ml import BEASTConfig, BEASTMLEngine, get_beast_engine
    BEAST_AVAILABLE = True
except ImportError:
    BEAST_AVAILABLE = False

try:
    from .reinforcement_loop import (
        MLBrainCore,
        ReinforcementLoop,
        RLEngine,
        TradingBrainCore,
        get_reinforcement_loop,
        get_rl_engine,
    )
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False

try:
    from .deep_learning import (
        DeepLearningEngine,
        HybridLSTMTransformer,
        LSTMModel,
        TransformerModel,
        get_deep_learning_engine,
    )
    DL_AVAILABLE = True
except ImportError:
    DL_AVAILABLE = False

try:
    from .evolution_engine import (
        EvolutionConfig,
        EvolutionEngine,
        Individual,
        StrategyGenome,
        get_evolution_engine,
    )
    EVOLUTION_AVAILABLE = True
except ImportError:
    EVOLUTION_AVAILABLE = False

# PropFirm Brain V6 - Advanced ML/RL/DL Trading Brain
try:
    from .propfirm_brain_v6 import (
        APEX_50K,
        TPT_50K,
        TPT_100K,
        BayesianRegimeDetector,
        FeatureEngine,
        MarketRegime,
        ModelConfig,
        PPOAgent,
        PropFirmBrainV6,
        PropFirmRuleset,
        StrategyEnsemble,
        TradeRecord,
        TradingSignal,
        TradingTransformer,
        get_propfirm_brain_v6,
    )
    PROPFIRM_BRAIN_V6_AVAILABLE = True
except ImportError as e:
    PROPFIRM_BRAIN_V6_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning(f"PropFirm Brain V6 not available: {e}")

__all__ = [
    # Core modules
    "NeuralEngine", "PatternType", "NeuralSignal",
    "RegimeDetector", "MarketRegime", "RegimeState",
    "AlgoBot", "BotState", "TradingStrategy",
    "TradingBrain", "BrainCycle", "BrainDecision",

    # Model Calibration (NEW)
    "ConfidenceCalibrator", "CalibrationReport", "CalibrationBin",
    "PredictionRecord", "TemperatureScaler", "get_confidence_calibrator",

    # BEAST ML
    "BEASTMLEngine", "BEASTConfig", "get_beast_engine",

    # Reinforcement Learning
    "RLEngine", "ReinforcementLoop", "MLBrainCore", "TradingBrainCore",
    "get_rl_engine", "get_reinforcement_loop",

    # Deep Learning
    "DeepLearningEngine", "LSTMModel", "TransformerModel", "HybridLSTMTransformer",
    "get_deep_learning_engine",

    # Evolution
    "EvolutionEngine", "EvolutionConfig", "Individual", "StrategyGenome",
    "get_evolution_engine",

    # PropFirm Brain V6
    "PropFirmBrainV6", "PropFirmRuleset", "TradingSignal",
    "TradeRecord", "ModelConfig", "FeatureEngine", "StrategyEnsemble",
    "BayesianRegimeDetector", "TradingTransformer", "PPOAgent",
    "TPT_50K", "TPT_100K", "APEX_50K",
    "get_propfirm_brain_v6",

    # Availability flags
    "BEAST_AVAILABLE", "RL_AVAILABLE", "DL_AVAILABLE", "EVOLUTION_AVAILABLE",
    "PROPFIRM_BRAIN_V6_AVAILABLE",
]
