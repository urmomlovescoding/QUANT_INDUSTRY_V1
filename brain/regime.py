"""
QUANT_INDUSTRY_V1 Regime Detection

Market regime detection using:
- Hidden Markov Models (HMM)
- K-Means clustering
- Volatility-based regimes
- Trend strength analysis

Rollback Plan: Delete this file
Tests Required: Regime detection accuracy, state transitions
Failure Modes: Default to 'unknown' regime
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# REGIME TYPES
# =============================================================================

class MarketRegime(Enum):
    """Market regime classification."""
    BULL_TRENDING = "bull_trending"
    BEAR_TRENDING = "bear_trending"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    MEAN_REVERTING = "mean_reverting"
    BREAKOUT = "breakout"
    CONSOLIDATION = "consolidation"
    UNKNOWN = "unknown"


@dataclass
class RegimeState:
    """Current regime state with metadata."""
    regime: MarketRegime
    confidence: float  # 0.0 - 1.0
    detected_at: datetime
    duration_bars: int = 0
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'regime': self.regime.value,
            'confidence': self.confidence,
            'detected_at': self.detected_at.isoformat(),
            'duration_bars': self.duration_bars,
            'metrics': self.metrics,
        }


@dataclass
class RegimeTransition:
    """Regime transition event."""
    from_regime: MarketRegime
    to_regime: MarketRegime
    timestamp: datetime
    confidence: float
    trigger_metrics: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# BASE REGIME DETECTOR
# =============================================================================

class BaseRegimeDetector(ABC):
    """Abstract base class for regime detection."""

    @abstractmethod
    def detect(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> RegimeState:
        """Detect current market regime."""
        pass

    @abstractmethod
    def fit(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> None:
        """Fit the detector to historical data."""
        pass


# =============================================================================
# HIDDEN MARKOV MODEL REGIME DETECTOR
# =============================================================================

class HMMRegimeDetector(BaseRegimeDetector):
    """
    Hidden Markov Model regime detector.

    Uses a simple implementation without heavy dependencies.
    For production, consider hmmlearn library.
    """

    def __init__(
        self,
        n_states: int = 3,
        n_iterations: int = 100,
        convergence_threshold: float = 1e-6,
    ):
        self.n_states = n_states
        self.n_iterations = n_iterations
        self.convergence_threshold = convergence_threshold

        # Model parameters (initialized during fit)
        self.transition_matrix: Optional[np.ndarray] = None
        self.emission_means: Optional[np.ndarray] = None
        self.emission_vars: Optional[np.ndarray] = None
        self.initial_probs: Optional[np.ndarray] = None

        # State to regime mapping
        self.state_regime_map: Dict[int, MarketRegime] = {}

        self._is_fitted = False

    def fit(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> None:
        """
        Fit HMM using Baum-Welch algorithm (simplified).

        Args:
            returns: Array of returns
            volatility: Array of volatility values
            volume: Array of volume values (normalized)
        """
        if len(returns) < 50:
            logger.warning("Insufficient data for HMM fitting")
            return

        # Use returns as primary observation
        observations = returns.reshape(-1, 1)
        n_obs = len(observations)

        # Initialize parameters
        self._initialize_parameters(observations)

        # Baum-Welch iterations
        prev_log_likelihood = float('-inf')

        for iteration in range(self.n_iterations):
            # E-step: Forward-backward algorithm
            alpha, beta, log_likelihood = self._forward_backward(observations)

            # Check convergence
            if abs(log_likelihood - prev_log_likelihood) < self.convergence_threshold:
                logger.info(f"HMM converged at iteration {iteration}")
                break

            prev_log_likelihood = log_likelihood

            # M-step: Update parameters
            self._update_parameters(observations, alpha, beta)

        # Map states to regimes based on emission means
        self._map_states_to_regimes(volatility)

        self._is_fitted = True
        logger.info(f"HMM fitted with {self.n_states} states")

    def _initialize_parameters(self, observations: np.ndarray) -> None:
        """Initialize HMM parameters."""
        n_states = self.n_states

        # Random initialization
        self.transition_matrix = np.random.dirichlet(
            np.ones(n_states), size=n_states
        )

        self.initial_probs = np.ones(n_states) / n_states

        # Initialize emission parameters using k-means-like approach
        obs_sorted = np.sort(observations.flatten())
        n_obs = len(obs_sorted)

        self.emission_means = np.array([
            obs_sorted[int(i * n_obs / n_states)]
            for i in range(n_states)
        ])

        self.emission_vars = np.full(n_states, np.var(observations))

    def _gaussian_pdf(self, x: float, mean: float, var: float) -> float:
        """Compute Gaussian PDF."""
        if var <= 0:
            var = 1e-6
        return np.exp(-0.5 * (x - mean) ** 2 / var) / np.sqrt(2 * np.pi * var)

    def _forward_backward(
        self,
        observations: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """Forward-backward algorithm."""
        n_obs = len(observations)
        n_states = self.n_states

        # Forward pass
        alpha = np.zeros((n_obs, n_states))

        # Initialize
        for s in range(n_states):
            alpha[0, s] = self.initial_probs[s] * self._gaussian_pdf(
                observations[0, 0], self.emission_means[s], self.emission_vars[s]
            )

        # Normalize
        alpha[0] /= (alpha[0].sum() + 1e-10)

        # Forward
        for t in range(1, n_obs):
            for s in range(n_states):
                alpha[t, s] = sum(
                    alpha[t-1, s_prev] * self.transition_matrix[s_prev, s]
                    for s_prev in range(n_states)
                ) * self._gaussian_pdf(
                    observations[t, 0], self.emission_means[s], self.emission_vars[s]
                )
            alpha[t] /= (alpha[t].sum() + 1e-10)

        # Backward pass
        beta = np.zeros((n_obs, n_states))
        beta[-1] = 1.0

        for t in range(n_obs - 2, -1, -1):
            for s in range(n_states):
                beta[t, s] = sum(
                    self.transition_matrix[s, s_next] *
                    self._gaussian_pdf(
                        observations[t+1, 0],
                        self.emission_means[s_next],
                        self.emission_vars[s_next]
                    ) * beta[t+1, s_next]
                    for s_next in range(n_states)
                )
            beta[t] /= (beta[t].sum() + 1e-10)

        # Log-likelihood
        log_likelihood = np.sum(np.log(alpha.sum(axis=1) + 1e-10))

        return alpha, beta, log_likelihood

    def _update_parameters(
        self,
        observations: np.ndarray,
        alpha: np.ndarray,
        beta: np.ndarray
    ) -> None:
        """Update HMM parameters (M-step)."""
        n_obs = len(observations)
        n_states = self.n_states

        # Compute gamma (state probabilities)
        gamma = alpha * beta
        gamma /= (gamma.sum(axis=1, keepdims=True) + 1e-10)

        # Update initial probabilities
        self.initial_probs = gamma[0]

        # Update transition matrix
        for i in range(n_states):
            for j in range(n_states):
                numerator = 0.0
                denominator = 0.0

                for t in range(n_obs - 1):
                    xi = (
                        alpha[t, i] *
                        self.transition_matrix[i, j] *
                        self._gaussian_pdf(
                            observations[t+1, 0],
                            self.emission_means[j],
                            self.emission_vars[j]
                        ) *
                        beta[t+1, j]
                    )
                    numerator += xi
                    denominator += gamma[t, i]

                self.transition_matrix[i, j] = numerator / (denominator + 1e-10)

            # Normalize
            self.transition_matrix[i] /= (self.transition_matrix[i].sum() + 1e-10)

        # Update emission parameters
        for s in range(n_states):
            gamma_sum = gamma[:, s].sum() + 1e-10

            self.emission_means[s] = (
                (gamma[:, s] * observations[:, 0]).sum() / gamma_sum
            )

            self.emission_vars[s] = (
                (gamma[:, s] * (observations[:, 0] - self.emission_means[s]) ** 2).sum()
                / gamma_sum
            )

    def _map_states_to_regimes(self, volatility: np.ndarray) -> None:
        """Map HMM states to market regimes."""
        # Sort states by emission mean
        sorted_indices = np.argsort(self.emission_means)

        # Map based on return characteristics
        if self.n_states == 3:
            self.state_regime_map = {
                sorted_indices[0]: MarketRegime.BEAR_TRENDING,
                sorted_indices[1]: MarketRegime.CONSOLIDATION,
                sorted_indices[2]: MarketRegime.BULL_TRENDING,
            }
        elif self.n_states == 4:
            self.state_regime_map = {
                sorted_indices[0]: MarketRegime.BEAR_TRENDING,
                sorted_indices[1]: MarketRegime.LOW_VOLATILITY,
                sorted_indices[2]: MarketRegime.HIGH_VOLATILITY,
                sorted_indices[3]: MarketRegime.BULL_TRENDING,
            }
        else:
            # Generic mapping
            for i, idx in enumerate(sorted_indices):
                if i < self.n_states // 3:
                    self.state_regime_map[idx] = MarketRegime.BEAR_TRENDING
                elif i < 2 * self.n_states // 3:
                    self.state_regime_map[idx] = MarketRegime.CONSOLIDATION
                else:
                    self.state_regime_map[idx] = MarketRegime.BULL_TRENDING

    def detect(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> RegimeState:
        """Detect current regime using Viterbi-like approach."""
        if not self._is_fitted:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                detected_at=datetime.now(timezone.utc),
            )

        if len(returns) == 0:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                detected_at=datetime.now(timezone.utc),
            )

        # Get most recent observation
        obs = returns[-1] if len(returns) > 0 else 0.0

        # Compute state probabilities
        state_probs = np.array([
            self._gaussian_pdf(obs, self.emission_means[s], self.emission_vars[s])
            for s in range(self.n_states)
        ])
        state_probs /= (state_probs.sum() + 1e-10)

        # Get most likely state
        most_likely_state = np.argmax(state_probs)
        confidence = state_probs[most_likely_state]

        regime = self.state_regime_map.get(most_likely_state, MarketRegime.UNKNOWN)

        return RegimeState(
            regime=regime,
            confidence=float(confidence),
            detected_at=datetime.now(timezone.utc),
            metrics={
                'state_probs': state_probs.tolist(),
                'emission_means': self.emission_means.tolist(),
                'last_return': float(obs),
            }
        )


# =============================================================================
# VOLATILITY-BASED REGIME DETECTOR
# =============================================================================

class VolatilityRegimeDetector(BaseRegimeDetector):
    """
    Simple volatility-based regime detection.

    Uses rolling volatility percentiles to classify regimes.
    """

    def __init__(
        self,
        lookback: int = 252,
        low_vol_percentile: float = 25.0,
        high_vol_percentile: float = 75.0,
    ):
        self.lookback = lookback
        self.low_vol_percentile = low_vol_percentile
        self.high_vol_percentile = high_vol_percentile

        self.vol_thresholds: Dict[str, float] = {}
        self._is_fitted = False

    def fit(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> None:
        """Fit volatility thresholds."""
        if len(volatility) < self.lookback:
            logger.warning("Insufficient data for volatility regime fitting")
            return

        self.vol_thresholds = {
            'low': np.percentile(volatility, self.low_vol_percentile),
            'high': np.percentile(volatility, self.high_vol_percentile),
            'median': np.median(volatility),
        }

        self._is_fitted = True
        logger.info(f"Volatility regime thresholds: {self.vol_thresholds}")

    def detect(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> RegimeState:
        """Detect regime based on current volatility."""
        if not self._is_fitted or len(volatility) == 0:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                detected_at=datetime.now(timezone.utc),
            )

        current_vol = volatility[-1]

        # Determine regime
        if current_vol <= self.vol_thresholds['low']:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = min(1.0, (self.vol_thresholds['low'] - current_vol) /
                           (self.vol_thresholds['low'] + 1e-10) + 0.5)
        elif current_vol >= self.vol_thresholds['high']:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(1.0, (current_vol - self.vol_thresholds['high']) /
                           (self.vol_thresholds['high'] + 1e-10) + 0.5)
        else:
            regime = MarketRegime.CONSOLIDATION
            # Confidence based on distance from thresholds
            mid_range = (self.vol_thresholds['high'] - self.vol_thresholds['low']) / 2
            dist_from_mid = abs(current_vol - self.vol_thresholds['median'])
            confidence = max(0.5, 1.0 - dist_from_mid / (mid_range + 1e-10))

        return RegimeState(
            regime=regime,
            confidence=float(confidence),
            detected_at=datetime.now(timezone.utc),
            metrics={
                'current_vol': float(current_vol),
                'low_threshold': self.vol_thresholds['low'],
                'high_threshold': self.vol_thresholds['high'],
            }
        )


# =============================================================================
# TREND-BASED REGIME DETECTOR
# =============================================================================

class TrendRegimeDetector(BaseRegimeDetector):
    """
    Trend-based regime detection.

    Uses moving average crossovers and momentum indicators.
    """

    def __init__(
        self,
        short_window: int = 20,
        long_window: int = 50,
        momentum_window: int = 14,
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.momentum_window = momentum_window

        self._is_fitted = False

    def fit(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> None:
        """Trend detector doesn't require fitting."""
        self._is_fitted = True

    def detect(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> RegimeState:
        """Detect trend regime."""
        if len(returns) < self.long_window:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                detected_at=datetime.now(timezone.utc),
            )

        # Compute cumulative returns (proxy for price)
        cum_returns = np.cumprod(1 + returns) - 1

        # Moving averages
        short_ma = np.mean(cum_returns[-self.short_window:])
        long_ma = np.mean(cum_returns[-self.long_window:])

        # Momentum (rate of change)
        if len(cum_returns) >= self.momentum_window:
            momentum = cum_returns[-1] - cum_returns[-self.momentum_window]
        else:
            momentum = 0.0

        # Recent volatility
        recent_vol = np.std(returns[-self.short_window:]) if len(returns) >= self.short_window else 0.0

        # Determine regime
        ma_diff = short_ma - long_ma

        if ma_diff > 0 and momentum > 0:
            if recent_vol > np.std(returns[-self.long_window:]) * 1.5:
                regime = MarketRegime.BREAKOUT
            else:
                regime = MarketRegime.BULL_TRENDING
            confidence = min(1.0, abs(ma_diff) * 10 + 0.5)
        elif ma_diff < 0 and momentum < 0:
            if recent_vol > np.std(returns[-self.long_window:]) * 1.5:
                regime = MarketRegime.HIGH_VOLATILITY
            else:
                regime = MarketRegime.BEAR_TRENDING
            confidence = min(1.0, abs(ma_diff) * 10 + 0.5)
        else:
            # Mixed signals - mean reverting or consolidation
            if abs(momentum) < 0.02:
                regime = MarketRegime.CONSOLIDATION
            else:
                regime = MarketRegime.MEAN_REVERTING
            confidence = 0.5

        return RegimeState(
            regime=regime,
            confidence=float(confidence),
            detected_at=datetime.now(timezone.utc),
            metrics={
                'short_ma': float(short_ma),
                'long_ma': float(long_ma),
                'momentum': float(momentum),
                'recent_vol': float(recent_vol),
            }
        )


# =============================================================================
# ENSEMBLE REGIME DETECTOR
# =============================================================================

class EnsembleRegimeDetector:
    """
    Ensemble of multiple regime detectors.

    Combines signals from HMM, volatility, and trend detectors.
    """

    def __init__(
        self,
        use_hmm: bool = True,
        use_volatility: bool = True,
        use_trend: bool = True,
        hmm_weight: float = 0.4,
        volatility_weight: float = 0.3,
        trend_weight: float = 0.3,
    ):
        self.detectors: Dict[str, Tuple[BaseRegimeDetector, float]] = {}

        if use_hmm:
            self.detectors['hmm'] = (HMMRegimeDetector(), hmm_weight)
        if use_volatility:
            self.detectors['volatility'] = (VolatilityRegimeDetector(), volatility_weight)
        if use_trend:
            self.detectors['trend'] = (TrendRegimeDetector(), trend_weight)

        # Normalize weights
        total_weight = sum(w for _, w in self.detectors.values())
        for name in self.detectors:
            detector, weight = self.detectors[name]
            self.detectors[name] = (detector, weight / total_weight)

        self.current_regime: Optional[RegimeState] = None
        self.regime_history: List[RegimeTransition] = []

    def fit(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> None:
        """Fit all detectors."""
        for name, (detector, _) in self.detectors.items():
            try:
                detector.fit(returns, volatility, volume)
                logger.info(f"Fitted {name} regime detector")
            except Exception as e:
                logger.error(f"Failed to fit {name} detector: {e}")

    def detect(
        self,
        returns: np.ndarray,
        volatility: np.ndarray,
        volume: np.ndarray,
    ) -> RegimeState:
        """
        Detect regime using ensemble voting.

        Args:
            returns: Array of returns
            volatility: Array of volatility values
            volume: Array of volume values

        Returns:
            RegimeState with consensus regime
        """
        regime_votes: Dict[MarketRegime, float] = {}
        all_states: Dict[str, RegimeState] = {}

        for name, (detector, weight) in self.detectors.items():
            try:
                state = detector.detect(returns, volatility, volume)
                all_states[name] = state

                if state.regime != MarketRegime.UNKNOWN:
                    current_vote = regime_votes.get(state.regime, 0.0)
                    regime_votes[state.regime] = current_vote + weight * state.confidence

            except Exception as e:
                logger.error(f"Error in {name} detector: {e}")

        if not regime_votes:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                detected_at=datetime.now(timezone.utc),
            )

        # Get regime with highest weighted vote
        best_regime = max(regime_votes, key=regime_votes.get)
        total_confidence = sum(regime_votes.values())
        confidence = regime_votes[best_regime] / (total_confidence + 1e-10)

        # Track transitions
        new_state = RegimeState(
            regime=best_regime,
            confidence=float(confidence),
            detected_at=datetime.now(timezone.utc),
            metrics={
                'regime_votes': {r.value: v for r, v in regime_votes.items()},
                'detector_states': {n: s.to_dict() for n, s in all_states.items()},
            }
        )

        if self.current_regime and self.current_regime.regime != best_regime:
            transition = RegimeTransition(
                from_regime=self.current_regime.regime,
                to_regime=best_regime,
                timestamp=datetime.now(timezone.utc),
                confidence=confidence,
                trigger_metrics={
                    'old_confidence': self.current_regime.confidence,
                    'new_confidence': confidence,
                }
            )
            self.regime_history.append(transition)

            # Keep only recent transitions
            if len(self.regime_history) > 100:
                self.regime_history = self.regime_history[-100:]

        self.current_regime = new_state
        return new_state

    def get_regime_stats(self) -> Dict[str, Any]:
        """Get regime detection statistics."""
        if not self.regime_history:
            return {
                'total_transitions': 0,
                'regime_counts': {},
                'avg_regime_duration': 0,
            }

        regime_counts: Dict[str, int] = {}
        for transition in self.regime_history:
            regime = transition.from_regime.value
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        return {
            'total_transitions': len(self.regime_history),
            'regime_counts': regime_counts,
            'current_regime': self.current_regime.to_dict() if self.current_regime else None,
        }


# =============================================================================
# REGIME FILTER
# =============================================================================

class RegimeFilter:
    """
    Filter trading signals based on regime.

    Allows/blocks signals based on current market regime.
    """

    def __init__(self):
        # Default regime rules
        self.allowed_regimes: Dict[str, List[MarketRegime]] = {
            'long': [
                MarketRegime.BULL_TRENDING,
                MarketRegime.BREAKOUT,
                MarketRegime.LOW_VOLATILITY,
            ],
            'short': [
                MarketRegime.BEAR_TRENDING,
                MarketRegime.HIGH_VOLATILITY,
            ],
            'both': [
                MarketRegime.MEAN_REVERTING,
                MarketRegime.CONSOLIDATION,
            ],
        }

        # Regime-specific position sizing multipliers
        self.regime_sizing: Dict[MarketRegime, float] = {
            MarketRegime.BULL_TRENDING: 1.0,
            MarketRegime.BEAR_TRENDING: 0.8,
            MarketRegime.HIGH_VOLATILITY: 0.5,
            MarketRegime.LOW_VOLATILITY: 1.2,
            MarketRegime.MEAN_REVERTING: 0.7,
            MarketRegime.BREAKOUT: 0.9,
            MarketRegime.CONSOLIDATION: 0.6,
            MarketRegime.UNKNOWN: 0.3,
        }

    def is_signal_allowed(
        self,
        direction: str,  # 'long' or 'short'
        regime: RegimeState,
        min_confidence: float = 0.5,
    ) -> Tuple[bool, str]:
        """
        Check if signal is allowed in current regime.

        Args:
            direction: Signal direction ('long' or 'short')
            regime: Current regime state
            min_confidence: Minimum confidence threshold

        Returns:
            Tuple of (allowed, reason)
        """
        if regime.regime == MarketRegime.UNKNOWN:
            return False, "Unknown regime"

        if regime.confidence < min_confidence:
            return False, f"Low regime confidence: {regime.confidence:.2f}"

        direction = direction.lower()

        if regime.regime in self.allowed_regimes.get(direction, []):
            return True, f"Regime {regime.regime.value} allows {direction}"

        if regime.regime in self.allowed_regimes.get('both', []):
            return True, f"Regime {regime.regime.value} allows both directions"

        return False, f"Regime {regime.regime.value} does not allow {direction}"

    def get_position_multiplier(self, regime: RegimeState) -> float:
        """Get position sizing multiplier for regime."""
        base_mult = self.regime_sizing.get(regime.regime, 0.5)

        # Adjust by confidence
        confidence_adj = 0.5 + 0.5 * regime.confidence

        return base_mult * confidence_adj

    def set_regime_rules(
        self,
        direction: str,
        regimes: List[MarketRegime]
    ) -> None:
        """Update allowed regimes for a direction."""
        self.allowed_regimes[direction.lower()] = regimes

    def set_regime_sizing(
        self,
        regime: MarketRegime,
        multiplier: float
    ) -> None:
        """Update position sizing for a regime."""
        self.regime_sizing[regime] = max(0.0, min(2.0, multiplier))
