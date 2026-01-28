"""
QUANT INDUSTRY - Regime-Aware Ensemble
======================================
Adaptive model ensemble that switches strategies based on market regime.

This is the REAL edge:
- Trend models in trending markets
- Mean reversion in ranging markets  
- Defensive models in crisis
- Dynamic weight allocation

One model can't win in all regimes. An adaptive ensemble can.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOL = "high_vol"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


class ModelType(Enum):
    """Types of models in ensemble"""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    ML_CLASSIFIER = "ml_classifier"
    NEURAL_NET = "neural_net"
    DEFENSIVE = "defensive"


@dataclass
class RegimeConfig:
    """Configuration for regime-specific behavior"""
    regime: MarketRegime
    
    # Model weights for this regime
    model_weights: Dict[ModelType, float] = field(default_factory=dict)
    
    # Risk parameters for this regime
    position_scale: float = 1.0      # Scale position sizes
    max_positions: int = 10
    stop_loss_mult: float = 1.0      # Multiply normal stop loss
    take_profit_mult: float = 1.0
    
    # Trading behavior
    trade_frequency: str = "normal"  # "high", "normal", "low", "none"
    prefer_direction: str = "both"   # "long", "short", "both"


# Default regime configurations
DEFAULT_REGIME_CONFIGS = {
    MarketRegime.TRENDING_UP: RegimeConfig(
        regime=MarketRegime.TRENDING_UP,
        model_weights={
            ModelType.TREND_FOLLOWING: 0.4,
            ModelType.MOMENTUM: 0.3,
            ModelType.NEURAL_NET: 0.2,
            ModelType.MEAN_REVERSION: 0.1,
        },
        position_scale=1.2,
        prefer_direction="long"
    ),
    MarketRegime.TRENDING_DOWN: RegimeConfig(
        regime=MarketRegime.TRENDING_DOWN,
        model_weights={
            ModelType.TREND_FOLLOWING: 0.35,
            ModelType.DEFENSIVE: 0.3,
            ModelType.VOLATILITY: 0.2,
            ModelType.MOMENTUM: 0.15,
        },
        position_scale=0.8,
        prefer_direction="short"
    ),
    MarketRegime.RANGING: RegimeConfig(
        regime=MarketRegime.RANGING,
        model_weights={
            ModelType.MEAN_REVERSION: 0.5,
            ModelType.ML_CLASSIFIER: 0.3,
            ModelType.VOLATILITY: 0.2,
        },
        position_scale=1.0,
        trade_frequency="high"
    ),
    MarketRegime.HIGH_VOL: RegimeConfig(
        regime=MarketRegime.HIGH_VOL,
        model_weights={
            ModelType.VOLATILITY: 0.4,
            ModelType.DEFENSIVE: 0.3,
            ModelType.NEURAL_NET: 0.2,
            ModelType.MEAN_REVERSION: 0.1,
        },
        position_scale=0.5,
        stop_loss_mult=1.5
    ),
    MarketRegime.CRISIS: RegimeConfig(
        regime=MarketRegime.CRISIS,
        model_weights={
            ModelType.DEFENSIVE: 0.6,
            ModelType.VOLATILITY: 0.3,
            ModelType.TREND_FOLLOWING: 0.1,
        },
        position_scale=0.2,
        max_positions=3,
        trade_frequency="low"
    ),
}


@dataclass
class ModelSignal:
    """Signal from a single model"""
    model_type: ModelType
    direction: int          # 1 = long, -1 = short, 0 = neutral
    confidence: float       # 0 to 1
    metadata: Dict = field(default_factory=dict)


@dataclass
class EnsembleSignal:
    """Combined signal from ensemble"""
    direction: int
    confidence: float
    regime: MarketRegime
    contributing_models: List[ModelSignal]
    
    # Risk adjustments from regime
    position_scale: float
    stop_loss_mult: float
    take_profit_mult: float
    
    def should_trade(self, min_confidence: float = 0.55) -> bool:
        return abs(self.direction) > 0 and self.confidence >= min_confidence
    
    def to_dict(self) -> Dict:
        return {
            "direction": "LONG" if self.direction > 0 else "SHORT" if self.direction < 0 else "FLAT",
            "confidence": f"{self.confidence:.1%}",
            "regime": self.regime.value,
            "position_scale": self.position_scale,
            "models": [
                {"type": m.model_type.value, "direction": m.direction, "confidence": m.confidence}
                for m in self.contributing_models
            ]
        }


class RegimeDetector:
    """
    Detect market regime from price/volume data.
    
    Uses multiple indicators:
    - Trend strength (ADX, moving average slopes)
    - Volatility regime (ATR, realized vol)
    - Market breadth
    - VIX/fear indicators
    """
    
    def __init__(
        self,
        lookback_short: int = 20,
        lookback_long: int = 60,
        vol_threshold_high: float = 0.025,
        vol_threshold_crisis: float = 0.04,
        trend_threshold: float = 0.6
    ):
        self.lookback_short = lookback_short
        self.lookback_long = lookback_long
        self.vol_threshold_high = vol_threshold_high
        self.vol_threshold_crisis = vol_threshold_crisis
        self.trend_threshold = trend_threshold
        
        # History
        self.regime_history: deque = deque(maxlen=100)
        self.current_regime = MarketRegime.UNKNOWN
        
        logger.info("RegimeDetector initialized")
    
    def detect(
        self,
        prices: np.ndarray,
        volumes: np.ndarray = None,
        vix: np.ndarray = None
    ) -> MarketRegime:
        """
        Detect current market regime.
        
        Args:
            prices: Price series (most recent last)
            volumes: Volume series (optional)
            vix: VIX/volatility index (optional)
            
        Returns:
            Current MarketRegime
        """
        if len(prices) < self.lookback_long:
            return MarketRegime.UNKNOWN
        
        # Calculate features
        returns = np.diff(prices) / prices[:-1]
        
        # Volatility
        vol_short = np.std(returns[-self.lookback_short:]) * np.sqrt(252)
        vol_long = np.std(returns[-self.lookback_long:]) * np.sqrt(252)
        
        # Check for crisis first
        if vol_short > self.vol_threshold_crisis or (vix is not None and vix[-1] > 35):
            regime = MarketRegime.CRISIS
        elif vol_short > self.vol_threshold_high:
            regime = MarketRegime.HIGH_VOL
        else:
            # Trend detection
            sma_short = np.mean(prices[-self.lookback_short:])
            sma_long = np.mean(prices[-self.lookback_long:])
            
            trend_strength = self._calculate_trend_strength(prices)
            
            if trend_strength > self.trend_threshold:
                if sma_short > sma_long:
                    regime = MarketRegime.TRENDING_UP
                else:
                    regime = MarketRegime.TRENDING_DOWN
            else:
                regime = MarketRegime.RANGING
        
        self.current_regime = regime
        self.regime_history.append((datetime.now(), regime))
        
        return regime
    
    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calculate ADX-like trend strength [0, 1]"""
        if len(prices) < self.lookback_short * 2:
            return 0.5
        
        # Simple trend strength: directional consistency
        returns = np.diff(prices[-self.lookback_short * 2:])
        
        up_moves = np.sum(returns > 0)
        down_moves = np.sum(returns < 0)
        total_moves = len(returns)
        
        # Directional consistency
        consistency = abs(up_moves - down_moves) / total_moves
        
        # Price distance from mean
        mean_price = np.mean(prices[-self.lookback_short:])
        current_price = prices[-1]
        deviation = abs(current_price - mean_price) / mean_price
        
        # Combine
        trend_strength = 0.7 * consistency + 0.3 * min(deviation * 10, 1)
        
        return min(trend_strength, 1.0)
    
    def get_regime_probabilities(
        self,
        prices: np.ndarray
    ) -> Dict[MarketRegime, float]:
        """Get soft probabilities for each regime"""
        # This is a simplified version - production would use ML
        regime = self.detect(prices)
        
        probs = {r: 0.05 for r in MarketRegime if r != MarketRegime.UNKNOWN}
        probs[regime] = 0.7
        
        # Redistribute remaining probability
        remaining = 1.0 - sum(probs.values())
        for r in probs:
            if r != regime:
                probs[r] += remaining / (len(probs) - 1)
        
        return probs


class ModelWrapper:
    """Wrapper for individual models in ensemble"""
    
    def __init__(
        self,
        model_type: ModelType,
        predict_fn: Callable[[np.ndarray], Tuple[int, float]],
        name: str = None
    ):
        """
        Args:
            model_type: Type of model
            predict_fn: Function that takes features and returns (direction, confidence)
            name: Optional model name
        """
        self.model_type = model_type
        self.predict_fn = predict_fn
        self.name = name or model_type.value
        
        # Performance tracking
        self.predictions: deque = deque(maxlen=1000)
        self.correct_predictions = 0
        self.total_predictions = 0
    
    def predict(self, features: np.ndarray) -> ModelSignal:
        """Generate signal from model"""
        direction, confidence = self.predict_fn(features)
        
        self.total_predictions += 1
        
        return ModelSignal(
            model_type=self.model_type,
            direction=direction,
            confidence=confidence,
            metadata={"model_name": self.name}
        )
    
    def record_outcome(self, predicted_direction: int, actual_direction: int):
        """Record prediction outcome for tracking"""
        was_correct = (predicted_direction * actual_direction) > 0
        self.predictions.append(was_correct)
        if was_correct:
            self.correct_predictions += 1
    
    @property
    def accuracy(self) -> float:
        if self.total_predictions == 0:
            return 0.5
        return self.correct_predictions / self.total_predictions
    
    @property
    def recent_accuracy(self) -> float:
        if not self.predictions:
            return 0.5
        return sum(self.predictions) / len(self.predictions)


class RegimeAwareEnsemble:
    """
    Adaptive model ensemble that weights models based on market regime.
    
    Usage:
    ------
    >>> ensemble = RegimeAwareEnsemble()
    >>> 
    >>> # Add models
    >>> ensemble.add_model(
    ...     ModelType.TREND_FOLLOWING,
    ...     lambda x: my_trend_model.predict(x)
    ... )
    >>> ensemble.add_model(
    ...     ModelType.MEAN_REVERSION,
    ...     lambda x: my_mr_model.predict(x)
    ... )
    >>>
    >>> # Generate signal
    >>> signal = ensemble.get_signal(features, prices)
    >>> if signal.should_trade():
    ...     execute_trade(signal)
    """
    
    def __init__(
        self,
        regime_configs: Dict[MarketRegime, RegimeConfig] = None,
        min_models: int = 1,
        use_performance_weighting: bool = True
    ):
        """
        Args:
            regime_configs: Custom regime configurations
            min_models: Minimum models needed for signal
            use_performance_weighting: Adjust weights by recent performance
        """
        self.regime_configs = regime_configs or DEFAULT_REGIME_CONFIGS
        self.min_models = min_models
        self.use_performance_weighting = use_performance_weighting
        
        self.models: Dict[ModelType, ModelWrapper] = {}
        self.regime_detector = RegimeDetector()
        
        # History
        self.signal_history: deque = deque(maxlen=1000)
        
        logger.info("RegimeAwareEnsemble initialized")
    
    def add_model(
        self,
        model_type: ModelType,
        predict_fn: Callable[[np.ndarray], Tuple[int, float]],
        name: str = None
    ):
        """
        Add a model to the ensemble.
        
        Args:
            model_type: Type of model
            predict_fn: Function returning (direction, confidence)
            name: Optional model name
        """
        wrapper = ModelWrapper(model_type, predict_fn, name)
        self.models[model_type] = wrapper
        
        logger.info(f"Added model: {model_type.value}")
    
    def get_signal(
        self,
        features: np.ndarray,
        prices: np.ndarray,
        volumes: np.ndarray = None
    ) -> EnsembleSignal:
        """
        Generate ensemble signal.
        
        Args:
            features: Feature array for models
            prices: Price series for regime detection
            volumes: Volume series (optional)
            
        Returns:
            EnsembleSignal with combined prediction
        """
        # Detect regime
        regime = self.regime_detector.detect(prices, volumes)
        config = self.regime_configs.get(regime, DEFAULT_REGIME_CONFIGS[MarketRegime.RANGING])
        
        # Get signals from all models
        signals: List[ModelSignal] = []
        for model_type, wrapper in self.models.items():
            try:
                signal = wrapper.predict(features)
                signals.append(signal)
            except Exception as e:
                logger.warning(f"Model {model_type.value} failed: {e}")
        
        if len(signals) < self.min_models:
            return self._neutral_signal(regime, config)
        
        # Weight signals by regime config and performance
        weighted_direction = 0.0
        total_weight = 0.0
        
        for signal in signals:
            base_weight = config.model_weights.get(signal.model_type, 0.1)
            
            # Adjust by recent performance if enabled
            if self.use_performance_weighting:
                wrapper = self.models.get(signal.model_type)
                if wrapper:
                    perf_adj = 0.5 + wrapper.recent_accuracy  # 0.5 to 1.5x
                    base_weight *= perf_adj
            
            # Apply confidence
            weight = base_weight * signal.confidence
            weighted_direction += signal.direction * weight
            total_weight += weight
        
        # Normalize
        if total_weight > 0:
            final_direction = weighted_direction / total_weight
        else:
            final_direction = 0.0
        
        # Calculate confidence (agreement + individual confidences)
        direction_sign = np.sign(final_direction) if final_direction != 0 else 0
        agreeing = sum(1 for s in signals if s.direction == direction_sign)
        agreement_ratio = agreeing / len(signals) if signals else 0
        avg_confidence = np.mean([s.confidence for s in signals]) if signals else 0
        
        final_confidence = 0.5 * agreement_ratio + 0.5 * avg_confidence
        
        # Apply regime-based direction preference
        if config.prefer_direction == "long" and final_direction < 0:
            final_confidence *= 0.5  # Reduce confidence for shorts in bullish regime
        elif config.prefer_direction == "short" and final_direction > 0:
            final_confidence *= 0.5  # Reduce confidence for longs in bearish regime
        
        # Discretize direction
        if abs(final_direction) > 0.3:
            discrete_direction = int(np.sign(final_direction))
        else:
            discrete_direction = 0
        
        ensemble_signal = EnsembleSignal(
            direction=discrete_direction,
            confidence=final_confidence,
            regime=regime,
            contributing_models=signals,
            position_scale=config.position_scale,
            stop_loss_mult=config.stop_loss_mult,
            take_profit_mult=config.take_profit_mult
        )
        
        self.signal_history.append((datetime.now(), ensemble_signal))
        
        return ensemble_signal
    
    def _neutral_signal(
        self,
        regime: MarketRegime,
        config: RegimeConfig
    ) -> EnsembleSignal:
        """Return neutral signal when insufficient models"""
        return EnsembleSignal(
            direction=0,
            confidence=0.0,
            regime=regime,
            contributing_models=[],
            position_scale=config.position_scale,
            stop_loss_mult=config.stop_loss_mult,
            take_profit_mult=config.take_profit_mult
        )
    
    def record_outcomes(
        self,
        actual_direction: int
    ):
        """
        Record actual outcome to update model performance.
        
        Call after a trade resolves.
        """
        if not self.signal_history:
            return
        
        _, last_signal = self.signal_history[-1]
        
        for model_signal in last_signal.contributing_models:
            wrapper = self.models.get(model_signal.model_type)
            if wrapper:
                wrapper.record_outcome(model_signal.direction, actual_direction)
    
    def get_model_performance(self) -> Dict[str, Dict]:
        """Get performance stats for all models"""
        stats = {}
        
        for model_type, wrapper in self.models.items():
            stats[model_type.value] = {
                "total_predictions": wrapper.total_predictions,
                "accuracy": f"{wrapper.accuracy:.1%}",
                "recent_accuracy": f"{wrapper.recent_accuracy:.1%}",
            }
        
        return stats
    
    def get_regime_stats(self) -> Dict[MarketRegime, int]:
        """Get regime occurrence counts from history"""
        counts = {r: 0 for r in MarketRegime}
        
        for _, regime in self.regime_detector.regime_history:
            counts[regime] += 1
        
        return counts


# ============== SIMPLE MODEL FACTORIES ==============

def create_trend_model() -> Callable[[np.ndarray], Tuple[int, float]]:
    """Create simple trend-following model"""
    def predict(features: np.ndarray) -> Tuple[int, float]:
        # Assume features contain price data
        if len(features) < 50:
            return 0, 0.5
        
        sma_20 = np.mean(features[-20:])
        sma_50 = np.mean(features[-50:])
        current = features[-1]
        
        if current > sma_20 > sma_50:
            direction = 1
            confidence = min((current - sma_50) / sma_50 * 10, 1)
        elif current < sma_20 < sma_50:
            direction = -1
            confidence = min((sma_50 - current) / sma_50 * 10, 1)
        else:
            direction = 0
            confidence = 0.4
        
        return direction, max(0.3, min(confidence, 0.9))
    
    return predict


def create_mean_reversion_model() -> Callable[[np.ndarray], Tuple[int, float]]:
    """Create simple mean reversion model"""
    def predict(features: np.ndarray) -> Tuple[int, float]:
        if len(features) < 20:
            return 0, 0.5
        
        mean = np.mean(features[-20:])
        std = np.std(features[-20:])
        current = features[-1]
        
        if std == 0:
            return 0, 0.5
        
        z_score = (current - mean) / std
        
        if z_score > 2:
            direction = -1  # Overbought, expect reversion
            confidence = min(abs(z_score) / 4, 0.9)
        elif z_score < -2:
            direction = 1   # Oversold, expect reversion
            confidence = min(abs(z_score) / 4, 0.9)
        else:
            direction = 0
            confidence = 0.4
        
        return direction, confidence
    
    return predict


def create_momentum_model() -> Callable[[np.ndarray], Tuple[int, float]]:
    """Create momentum model"""
    def predict(features: np.ndarray) -> Tuple[int, float]:
        if len(features) < 60:
            return 0, 0.5
        
        # 12-1 month momentum
        ret_12m = (features[-1] / features[-252]) - 1 if len(features) >= 252 else 0
        ret_1m = (features[-1] / features[-21]) - 1 if len(features) >= 21 else 0
        
        momentum = ret_12m - ret_1m
        
        if momentum > 0.1:
            direction = 1
            confidence = min(momentum, 0.9)
        elif momentum < -0.1:
            direction = -1
            confidence = min(abs(momentum), 0.9)
        else:
            direction = 0
            confidence = 0.4
        
        return direction, max(0.3, confidence)
    
    return predict


def create_default_ensemble() -> RegimeAwareEnsemble:
    """Create ensemble with default models"""
    ensemble = RegimeAwareEnsemble()
    
    ensemble.add_model(ModelType.TREND_FOLLOWING, create_trend_model())
    ensemble.add_model(ModelType.MEAN_REVERSION, create_mean_reversion_model())
    ensemble.add_model(ModelType.MOMENTUM, create_momentum_model())
    
    return ensemble
