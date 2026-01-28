"""
QUANT_INDUSTRY_V1 Real-Time Signal Aggregation System

Combines signals from multiple sources into unified trading decisions.

Features:
- Multi-source signal combination
- Dynamic weight adjustment
- Confidence-weighted averaging
- Signal decay and staleness detection
- Conflict resolution
- Ensemble voting
- Real-time signal streaming
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict
import logging
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class SignalSource(Enum):
    """Sources of trading signals."""
    ML_MODEL = "ml_model"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    MICROSTRUCTURE = "microstructure"
    ALTERNATIVE_DATA = "alternative_data"
    OPTIONS_FLOW = "options_flow"
    FUNDAMENTAL = "fundamental"
    ICT_SMC = "ict_smc"
    PHYSICS_MODEL = "physics_model"
    ALPHA_DISCOVERY = "alpha_discovery"
    ENSEMBLE = "ensemble"


class SignalDirection(Enum):
    """Signal direction."""
    LONG = 1
    SHORT = -1
    NEUTRAL = 0


@dataclass
class TradingSignal:
    """Individual trading signal."""
    symbol: str
    source: SignalSource
    direction: SignalDirection
    strength: float  # -1 to 1
    confidence: float  # 0 to 1
    timestamp: datetime
    expiry: datetime = None  # When signal becomes stale
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.expiry is None:
            # Default expiry: 5 minutes
            self.expiry = self.timestamp + timedelta(minutes=5)

    def is_valid(self, current_time: datetime = None) -> bool:
        """Check if signal is still valid."""
        current_time = current_time or datetime.now(timezone.utc)
        return current_time < self.expiry

    def get_decay_factor(self, current_time: datetime = None) -> float:
        """Get signal decay factor (1.0 = fresh, 0.0 = expired)."""
        current_time = current_time or datetime.now(timezone.utc)
        total_life = (self.expiry - self.timestamp).total_seconds()
        elapsed = (current_time - self.timestamp).total_seconds()
        return max(0.0, 1.0 - elapsed / total_life)


@dataclass
class AggregatedSignal:
    """Combined signal from multiple sources."""
    symbol: str
    direction: SignalDirection
    strength: float
    confidence: float
    timestamp: datetime
    component_signals: Dict[SignalSource, TradingSignal]
    agreement_ratio: float  # % of sources agreeing
    source_weights: Dict[SignalSource, float]
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SIGNAL COMBINER STRATEGIES
# =============================================================================

class SignalCombiner:
    """Base class for signal combination strategies."""

    def combine(
        self,
        signals: List[TradingSignal],
        weights: Dict[SignalSource, float] = None,
    ) -> Tuple[float, float]:
        """
        Combine signals into final signal.

        Returns:
            Tuple of (strength, confidence)
        """
        raise NotImplementedError


class WeightedAverageCombiner(SignalCombiner):
    """Confidence-weighted average combination."""

    def combine(
        self,
        signals: List[TradingSignal],
        weights: Dict[SignalSource, float] = None,
    ) -> Tuple[float, float]:
        if not signals:
            return 0.0, 0.0

        weights = weights or {}

        total_weight = 0.0
        weighted_sum = 0.0
        confidence_sum = 0.0

        for signal in signals:
            source_weight = weights.get(signal.source, 1.0)
            decay = signal.get_decay_factor()
            effective_weight = source_weight * signal.confidence * decay

            weighted_sum += signal.strength * effective_weight
            total_weight += effective_weight
            confidence_sum += signal.confidence * decay

        if total_weight > 0:
            strength = weighted_sum / total_weight
            confidence = confidence_sum / len(signals)
        else:
            strength = 0.0
            confidence = 0.0

        return strength, confidence


class VotingCombiner(SignalCombiner):
    """Majority voting combination."""

    def __init__(self, threshold: float = 0.5):
        """
        Args:
            threshold: Minimum agreement ratio to generate signal
        """
        self.threshold = threshold

    def combine(
        self,
        signals: List[TradingSignal],
        weights: Dict[SignalSource, float] = None,
    ) -> Tuple[float, float]:
        if not signals:
            return 0.0, 0.0

        weights = weights or {}

        # Count votes
        long_votes = 0.0
        short_votes = 0.0
        total_weight = 0.0

        for signal in signals:
            source_weight = weights.get(signal.source, 1.0)
            decay = signal.get_decay_factor()
            vote_weight = source_weight * signal.confidence * decay

            if signal.direction == SignalDirection.LONG:
                long_votes += vote_weight
            elif signal.direction == SignalDirection.SHORT:
                short_votes += vote_weight

            total_weight += vote_weight

        if total_weight == 0:
            return 0.0, 0.0

        long_ratio = long_votes / total_weight
        short_ratio = short_votes / total_weight

        if long_ratio > self.threshold:
            strength = long_ratio
            confidence = long_ratio
        elif short_ratio > self.threshold:
            strength = -short_ratio
            confidence = short_ratio
        else:
            strength = 0.0
            confidence = max(long_ratio, short_ratio)

        return strength, confidence


class BayesianCombiner(SignalCombiner):
    """Bayesian signal combination."""

    def __init__(self, prior_strength: float = 0.0):
        self.prior_strength = prior_strength

    def combine(
        self,
        signals: List[TradingSignal],
        weights: Dict[SignalSource, float] = None,
    ) -> Tuple[float, float]:
        if not signals:
            return self.prior_strength, 0.0

        weights = weights or {}

        # Convert strengths to log-odds
        def strength_to_odds(s):
            # Map [-1, 1] to probability [0.01, 0.99]
            p = 0.5 + 0.49 * s
            return np.log(p / (1 - p))

        def odds_to_strength(log_odds):
            p = 1 / (1 + np.exp(-log_odds))
            return (p - 0.5) / 0.49

        # Combine in log-odds space
        prior_odds = strength_to_odds(self.prior_strength)
        combined_odds = prior_odds

        total_confidence = 0.0

        for signal in signals:
            source_weight = weights.get(signal.source, 1.0)
            decay = signal.get_decay_factor()

            signal_odds = strength_to_odds(signal.strength)
            effective_confidence = signal.confidence * source_weight * decay

            # Weight by confidence
            combined_odds += signal_odds * effective_confidence
            total_confidence += effective_confidence

        strength = odds_to_strength(combined_odds)
        confidence = min(1.0, total_confidence / len(signals)) if signals else 0.0

        return np.clip(strength, -1, 1), confidence


# =============================================================================
# SIGNAL AGGREGATOR
# =============================================================================

class SignalAggregator:
    """
    Real-time signal aggregation engine.

    Combines signals from multiple sources and produces
    unified trading signals.
    """

    def __init__(
        self,
        combiner: SignalCombiner = None,
        default_weights: Dict[SignalSource, float] = None,
        min_confidence: float = 0.3,
        min_sources: int = 2,
        signal_ttl_seconds: float = 300,  # 5 minutes
    ):
        self.combiner = combiner or WeightedAverageCombiner()
        self.default_weights = default_weights or self._default_source_weights()
        self.min_confidence = min_confidence
        self.min_sources = min_sources
        self.signal_ttl_seconds = signal_ttl_seconds

        # Signal storage
        self.signals: Dict[str, Dict[SignalSource, TradingSignal]] = defaultdict(dict)
        self.aggregated: Dict[str, AggregatedSignal] = {}
        self.signal_history: Dict[str, List[AggregatedSignal]] = defaultdict(list)

        # Real-time processing
        self.signal_queue: Queue = Queue()
        self.callbacks: List[Callable[[AggregatedSignal], None]] = []
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def _default_source_weights(self) -> Dict[SignalSource, float]:
        """Default weights for each signal source."""
        return {
            SignalSource.ML_MODEL: 1.0,
            SignalSource.TECHNICAL: 0.8,
            SignalSource.SENTIMENT: 0.6,
            SignalSource.MICROSTRUCTURE: 0.9,
            SignalSource.ALTERNATIVE_DATA: 0.7,
            SignalSource.OPTIONS_FLOW: 0.85,
            SignalSource.FUNDAMENTAL: 0.75,
            SignalSource.ICT_SMC: 0.8,
            SignalSource.PHYSICS_MODEL: 0.5,
            SignalSource.ALPHA_DISCOVERY: 0.9,
            SignalSource.ENSEMBLE: 1.0,
        }

    def add_signal(self, signal: TradingSignal) -> None:
        """Add a new signal."""
        with self._lock:
            self.signals[signal.symbol][signal.source] = signal

        # Queue for processing
        if self._running:
            self.signal_queue.put(signal)
        else:
            # Immediate aggregation if not running async
            self._aggregate_symbol(signal.symbol)

    def add_signals(self, signals: List[TradingSignal]) -> None:
        """Add multiple signals."""
        for signal in signals:
            self.add_signal(signal)

    def get_aggregated_signal(
        self,
        symbol: str,
        recalculate: bool = False,
    ) -> Optional[AggregatedSignal]:
        """Get aggregated signal for symbol."""
        if recalculate or symbol not in self.aggregated:
            self._aggregate_symbol(symbol)
        return self.aggregated.get(symbol)

    def _aggregate_symbol(self, symbol: str) -> Optional[AggregatedSignal]:
        """Aggregate signals for a symbol."""
        with self._lock:
            symbol_signals = self.signals.get(symbol, {})

        if not symbol_signals:
            return None

        current_time = datetime.now(timezone.utc)

        # Filter valid signals
        valid_signals = [
            s for s in symbol_signals.values()
            if s.is_valid(current_time)
        ]

        if len(valid_signals) < self.min_sources:
            return None

        # Combine signals
        strength, confidence = self.combiner.combine(
            valid_signals,
            self.default_weights
        )

        if confidence < self.min_confidence:
            return None

        # Determine direction
        if strength > 0.1:
            direction = SignalDirection.LONG
        elif strength < -0.1:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        # Calculate agreement
        directions = [s.direction for s in valid_signals]
        if direction != SignalDirection.NEUTRAL:
            agreement = sum(1 for d in directions if d == direction) / len(directions)
        else:
            agreement = sum(1 for d in directions if d == SignalDirection.NEUTRAL) / len(directions)

        aggregated = AggregatedSignal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=current_time,
            component_signals={s.source: s for s in valid_signals},
            agreement_ratio=agreement,
            source_weights={s.source: self.default_weights.get(s.source, 1.0) for s in valid_signals},
            metadata={
                'num_sources': len(valid_signals),
                'sources': [s.source.value for s in valid_signals],
            }
        )

        with self._lock:
            self.aggregated[symbol] = aggregated
            self.signal_history[symbol].append(aggregated)

            # Keep only last 100 signals per symbol
            if len(self.signal_history[symbol]) > 100:
                self.signal_history[symbol] = self.signal_history[symbol][-100:]

        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(aggregated)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return aggregated

    def register_callback(
        self,
        callback: Callable[[AggregatedSignal], None],
    ) -> None:
        """Register callback for new aggregated signals."""
        self.callbacks.append(callback)

    def start(self) -> None:
        """Start real-time processing."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        logger.info("Signal aggregator started")

    def stop(self) -> None:
        """Stop real-time processing."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Signal aggregator stopped")

    def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                signal = self.signal_queue.get(timeout=0.1)
                self._aggregate_symbol(signal.symbol)
            except Empty:
                # Clean up stale signals periodically
                self._cleanup_stale_signals()

    def _cleanup_stale_signals(self) -> None:
        """Remove expired signals."""
        current_time = datetime.now(timezone.utc)

        with self._lock:
            for symbol in list(self.signals.keys()):
                for source in list(self.signals[symbol].keys()):
                    if not self.signals[symbol][source].is_valid(current_time):
                        del self.signals[symbol][source]

                if not self.signals[symbol]:
                    del self.signals[symbol]

    def get_active_symbols(self) -> List[str]:
        """Get list of symbols with active signals."""
        with self._lock:
            return list(self.signals.keys())

    def get_signal_summary(self) -> Dict[str, Any]:
        """Get summary of current signal state."""
        with self._lock:
            active_symbols = list(self.aggregated.keys())

            summary = {
                'active_symbols': len(active_symbols),
                'total_signals': sum(len(s) for s in self.signals.values()),
                'long_signals': 0,
                'short_signals': 0,
                'neutral_signals': 0,
                'avg_confidence': 0.0,
                'top_opportunities': [],
            }

            confidences = []
            for symbol, agg in self.aggregated.items():
                if agg.direction == SignalDirection.LONG:
                    summary['long_signals'] += 1
                elif agg.direction == SignalDirection.SHORT:
                    summary['short_signals'] += 1
                else:
                    summary['neutral_signals'] += 1

                confidences.append(agg.confidence)

                summary['top_opportunities'].append({
                    'symbol': symbol,
                    'direction': agg.direction.name,
                    'strength': agg.strength,
                    'confidence': agg.confidence,
                    'sources': agg.metadata.get('num_sources', 0),
                })

            if confidences:
                summary['avg_confidence'] = np.mean(confidences)

            # Sort by absolute strength * confidence
            summary['top_opportunities'].sort(
                key=lambda x: abs(x['strength']) * x['confidence'],
                reverse=True
            )
            summary['top_opportunities'] = summary['top_opportunities'][:10]

            return summary


# =============================================================================
# CONFLICT RESOLVER
# =============================================================================

class SignalConflictResolver:
    """
    Resolves conflicting signals from different sources.
    """

    def __init__(
        self,
        hierarchy: List[SignalSource] = None,
        correlation_threshold: float = -0.5,
    ):
        """
        Args:
            hierarchy: Source priority order (higher = more trusted)
            correlation_threshold: Threshold for detecting conflicting sources
        """
        self.hierarchy = hierarchy or [
            SignalSource.ENSEMBLE,
            SignalSource.ML_MODEL,
            SignalSource.MICROSTRUCTURE,
            SignalSource.ALPHA_DISCOVERY,
            SignalSource.OPTIONS_FLOW,
            SignalSource.ICT_SMC,
            SignalSource.TECHNICAL,
            SignalSource.FUNDAMENTAL,
            SignalSource.ALTERNATIVE_DATA,
            SignalSource.SENTIMENT,
            SignalSource.PHYSICS_MODEL,
        ]
        self.correlation_threshold = correlation_threshold
        self.conflict_history: List[Dict[str, Any]] = []

    def resolve(
        self,
        signals: List[TradingSignal],
    ) -> List[TradingSignal]:
        """
        Resolve conflicts and return consistent signals.
        """
        if len(signals) <= 1:
            return signals

        # Detect conflicts
        conflicts = self._detect_conflicts(signals)

        if not conflicts:
            return signals

        # Log conflicts
        self.conflict_history.append({
            'timestamp': datetime.now(timezone.utc),
            'conflicts': conflicts,
            'signals': [(s.source.value, s.direction.name) for s in signals],
        })

        # Resolve using hierarchy
        resolved = []
        used_sources = set()

        for source in self.hierarchy:
            for signal in signals:
                if signal.source == source and signal.source not in used_sources:
                    # Check if conflicts with already selected
                    has_conflict = False
                    for selected in resolved:
                        if self._is_conflicting(signal, selected):
                            # Use hierarchy to decide
                            if self.hierarchy.index(signal.source) < self.hierarchy.index(selected.source):
                                resolved.remove(selected)
                                resolved.append(signal)
                            has_conflict = True
                            break

                    if not has_conflict:
                        resolved.append(signal)
                        used_sources.add(signal.source)

        return resolved

    def _detect_conflicts(
        self,
        signals: List[TradingSignal],
    ) -> List[Tuple[TradingSignal, TradingSignal]]:
        """Detect conflicting signal pairs."""
        conflicts = []

        for i, s1 in enumerate(signals):
            for s2 in signals[i+1:]:
                if self._is_conflicting(s1, s2):
                    conflicts.append((s1, s2))

        return conflicts

    def _is_conflicting(
        self,
        s1: TradingSignal,
        s2: TradingSignal,
    ) -> bool:
        """Check if two signals are conflicting."""
        # Opposite directions
        if s1.direction == SignalDirection.LONG and s2.direction == SignalDirection.SHORT:
            return True
        if s1.direction == SignalDirection.SHORT and s2.direction == SignalDirection.LONG:
            return True

        # Strong opposing strengths
        if s1.strength * s2.strength < self.correlation_threshold:
            return True

        return False


# =============================================================================
# SIGNAL STREAMER
# =============================================================================

class SignalStreamer:
    """
    Stream aggregated signals to consumers.
    """

    def __init__(self, aggregator: SignalAggregator):
        self.aggregator = aggregator
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._setup_callback()

    def _setup_callback(self) -> None:
        """Setup aggregator callback."""
        self.aggregator.register_callback(self._on_signal)

    def _on_signal(self, signal: AggregatedSignal) -> None:
        """Handle new aggregated signal."""
        # Notify all subscribers
        for callback in self.subscribers['all']:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")

        # Notify symbol-specific subscribers
        for callback in self.subscribers.get(signal.symbol, []):
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Symbol subscriber error: {e}")

    def subscribe(
        self,
        callback: Callable[[AggregatedSignal], None],
        symbol: str = 'all',
    ) -> None:
        """Subscribe to signals."""
        self.subscribers[symbol].append(callback)

    def unsubscribe(
        self,
        callback: Callable[[AggregatedSignal], None],
        symbol: str = 'all',
    ) -> None:
        """Unsubscribe from signals."""
        if callback in self.subscribers[symbol]:
            self.subscribers[symbol].remove(callback)


# =============================================================================
# ENSEMBLE SIGNAL GENERATOR
# =============================================================================

class EnsembleSignalGenerator:
    """
    Generate ensemble signals from multiple model predictions.
    """

    def __init__(
        self,
        aggregation_method: str = 'weighted_average',
        diversity_weight: float = 0.2,
    ):
        self.aggregation_method = aggregation_method
        self.diversity_weight = diversity_weight
        self.model_weights: Dict[str, float] = {}
        self.model_performance: Dict[str, Dict[str, float]] = {}

    def update_model_performance(
        self,
        model_id: str,
        accuracy: float,
        sharpe: float,
        max_drawdown: float,
    ) -> None:
        """Update model performance metrics."""
        self.model_performance[model_id] = {
            'accuracy': accuracy,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
        }

        # Update weights based on performance
        self._update_weights()

    def _update_weights(self) -> None:
        """Update model weights based on performance."""
        if not self.model_performance:
            return

        # Combine metrics into score
        scores = {}
        for model_id, perf in self.model_performance.items():
            # Higher accuracy, higher sharpe, lower drawdown = better
            score = (
                0.4 * perf['accuracy'] +
                0.4 * max(0, perf['sharpe']) / 3 +  # Normalize sharpe
                0.2 * (1 - min(1, perf['max_drawdown'] / 0.3))  # Normalize drawdown
            )
            scores[model_id] = max(0.01, score)

        # Normalize to weights
        total = sum(scores.values())
        self.model_weights = {k: v / total for k, v in scores.items()}

    def generate_ensemble_signal(
        self,
        symbol: str,
        model_predictions: Dict[str, Tuple[float, float]],  # model_id -> (strength, confidence)
    ) -> TradingSignal:
        """
        Generate ensemble signal from model predictions.

        Args:
            symbol: Trading symbol
            model_predictions: Dict of model_id -> (strength, confidence)
        """
        if not model_predictions:
            return TradingSignal(
                symbol=symbol,
                source=SignalSource.ENSEMBLE,
                direction=SignalDirection.NEUTRAL,
                strength=0.0,
                confidence=0.0,
                timestamp=datetime.now(timezone.utc),
            )

        # Get weights (default to equal if no performance data)
        if not self.model_weights:
            weights = {k: 1.0 / len(model_predictions) for k in model_predictions}
        else:
            weights = self.model_weights

        if self.aggregation_method == 'weighted_average':
            strength, confidence = self._weighted_average(model_predictions, weights)
        elif self.aggregation_method == 'stacking':
            strength, confidence = self._stacking(model_predictions, weights)
        else:
            strength, confidence = self._voting(model_predictions, weights)

        # Determine direction
        if strength > 0.1:
            direction = SignalDirection.LONG
        elif strength < -0.1:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        return TradingSignal(
            symbol=symbol,
            source=SignalSource.ENSEMBLE,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            metadata={
                'model_count': len(model_predictions),
                'weights': weights,
                'method': self.aggregation_method,
            }
        )

    def _weighted_average(
        self,
        predictions: Dict[str, Tuple[float, float]],
        weights: Dict[str, float],
    ) -> Tuple[float, float]:
        """Weighted average combination."""
        total_weight = 0.0
        weighted_sum = 0.0
        confidence_sum = 0.0

        for model_id, (strength, conf) in predictions.items():
            w = weights.get(model_id, 1.0 / len(predictions))
            effective_weight = w * conf

            weighted_sum += strength * effective_weight
            total_weight += effective_weight
            confidence_sum += conf * w

        if total_weight > 0:
            return weighted_sum / total_weight, confidence_sum
        return 0.0, 0.0

    def _voting(
        self,
        predictions: Dict[str, Tuple[float, float]],
        weights: Dict[str, float],
    ) -> Tuple[float, float]:
        """Voting combination."""
        long_votes = 0.0
        short_votes = 0.0
        total_weight = 0.0

        for model_id, (strength, conf) in predictions.items():
            w = weights.get(model_id, 1.0 / len(predictions))
            vote_weight = w * conf

            if strength > 0.1:
                long_votes += vote_weight
            elif strength < -0.1:
                short_votes += vote_weight

            total_weight += vote_weight

        if total_weight == 0:
            return 0.0, 0.0

        if long_votes > short_votes:
            return long_votes / total_weight, long_votes / total_weight
        elif short_votes > long_votes:
            return -short_votes / total_weight, short_votes / total_weight
        return 0.0, 0.5

    def _stacking(
        self,
        predictions: Dict[str, Tuple[float, float]],
        weights: Dict[str, float],
    ) -> Tuple[float, float]:
        """Stacking combination (meta-model approach)."""
        # Simplified: use diversity-weighted average
        strengths = [s for s, c in predictions.values()]
        confidences = [c for s, c in predictions.values()]

        # Calculate diversity (standard deviation of predictions)
        diversity = np.std(strengths) if len(strengths) > 1 else 0

        # Base average
        avg_strength = np.mean(strengths)
        avg_confidence = np.mean(confidences)

        # Adjust confidence by diversity
        # Lower diversity = higher confidence (agreement)
        diversity_factor = 1 - min(1, diversity * self.diversity_weight)
        final_confidence = avg_confidence * diversity_factor

        return avg_strength, final_confidence


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SignalSource',
    'SignalDirection',
    'TradingSignal',
    'AggregatedSignal',
    'SignalCombiner',
    'WeightedAverageCombiner',
    'VotingCombiner',
    'BayesianCombiner',
    'SignalAggregator',
    'SignalConflictResolver',
    'SignalStreamer',
    'EnsembleSignalGenerator',
]
