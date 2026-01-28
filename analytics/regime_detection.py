"""
QUANT_INDUSTRY_V1 Market Regime Detection

Sophisticated regime identification for adaptive strategy selection.

Features:
- Hidden Markov Models (HMM)
- Gaussian Mixture Models
- Volatility Regime Classification
- Trend/Mean-Reversion Detection
- Risk-On/Risk-Off Classification
- Correlation Regime Analysis
- Multi-timeframe Regime Fusion
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict
import logging
from scipy import stats
from scipy.ndimage import gaussian_filter1d

logger = logging.getLogger(__name__)


# =============================================================================
# REGIME TYPES
# =============================================================================

class MarketRegime(Enum):
    """Market regime types."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    CRISIS = "crisis"
    RECOVERY = "recovery"
    UNKNOWN = "unknown"


class VolatilityRegime(Enum):
    """Volatility regime classification."""
    EXTREMELY_LOW = "extremely_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREMELY_HIGH = "extremely_high"


class TrendRegime(Enum):
    """Trend regime classification."""
    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    NEUTRAL = "neutral"
    WEAK_DOWNTREND = "weak_downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


@dataclass
class RegimeState:
    """Current regime state."""
    primary_regime: MarketRegime
    volatility_regime: VolatilityRegime
    trend_regime: TrendRegime
    confidence: float
    timestamp: datetime
    probabilities: Dict[MarketRegime, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# HIDDEN MARKOV MODEL REGIME DETECTOR
# =============================================================================

class HMMRegimeDetector:
    """
    Hidden Markov Model for regime detection.

    Learns latent market states from price/return dynamics.
    """

    def __init__(
        self,
        n_regimes: int = 3,
        n_iterations: int = 100,
        convergence_threshold: float = 1e-6,
    ):
        self.n_regimes = n_regimes
        self.n_iterations = n_iterations
        self.convergence_threshold = convergence_threshold

        # Model parameters
        self.transition_matrix: Optional[np.ndarray] = None
        self.emission_means: Optional[np.ndarray] = None
        self.emission_stds: Optional[np.ndarray] = None
        self.initial_probs: Optional[np.ndarray] = None

        self._fitted = False

    def fit(self, returns: np.ndarray) -> 'HMMRegimeDetector':
        """
        Fit HMM using Baum-Welch algorithm (simplified EM).

        Args:
            returns: Array of returns
        """
        n = len(returns)
        k = self.n_regimes

        # Initialize parameters using K-means style clustering
        sorted_returns = np.sort(returns)
        quantiles = np.linspace(0, 1, k + 1)
        self.emission_means = np.array([
            np.mean(sorted_returns[int(quantiles[i] * n):int(quantiles[i + 1] * n)])
            for i in range(k)
        ])
        self.emission_stds = np.std(returns) * np.ones(k)
        self.transition_matrix = np.ones((k, k)) / k + 0.5 * np.eye(k)
        self.transition_matrix /= self.transition_matrix.sum(axis=1, keepdims=True)
        self.initial_probs = np.ones(k) / k

        # EM iterations
        for iteration in range(self.n_iterations):
            # E-step: Forward-Backward algorithm
            alpha, beta, gamma, xi = self._forward_backward(returns)

            # M-step: Update parameters
            new_initial = gamma[0] / gamma[0].sum()

            new_transition = np.zeros((k, k))
            for t in range(n - 1):
                new_transition += xi[t]
            new_transition /= new_transition.sum(axis=1, keepdims=True)

            new_means = np.zeros(k)
            new_stds = np.zeros(k)
            for j in range(k):
                weights = gamma[:, j]
                new_means[j] = np.sum(weights * returns) / np.sum(weights)
                new_stds[j] = np.sqrt(
                    np.sum(weights * (returns - new_means[j]) ** 2) / np.sum(weights)
                )

            # Check convergence
            mean_diff = np.abs(new_means - self.emission_means).max()
            if mean_diff < self.convergence_threshold:
                break

            self.initial_probs = new_initial
            self.transition_matrix = new_transition
            self.emission_means = new_means
            self.emission_stds = np.maximum(new_stds, 1e-6)

        self._fitted = True
        return self

    def _forward_backward(
        self,
        returns: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Forward-backward algorithm."""
        n = len(returns)
        k = self.n_regimes

        # Emission probabilities
        B = np.zeros((n, k))
        for j in range(k):
            B[:, j] = stats.norm.pdf(returns, self.emission_means[j], self.emission_stds[j])

        # Forward pass
        alpha = np.zeros((n, k))
        alpha[0] = self.initial_probs * B[0]
        alpha[0] /= alpha[0].sum()

        for t in range(1, n):
            alpha[t] = B[t] * (alpha[t - 1] @ self.transition_matrix)
            alpha[t] /= alpha[t].sum() + 1e-10

        # Backward pass
        beta = np.zeros((n, k))
        beta[-1] = 1

        for t in range(n - 2, -1, -1):
            beta[t] = self.transition_matrix @ (B[t + 1] * beta[t + 1])
            beta[t] /= beta[t].sum() + 1e-10

        # Gamma (state probabilities)
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True)

        # Xi (transition probabilities)
        xi = np.zeros((n - 1, k, k))
        for t in range(n - 1):
            xi[t] = np.outer(alpha[t], B[t + 1] * beta[t + 1]) * self.transition_matrix
            xi[t] /= xi[t].sum() + 1e-10

        return alpha, beta, gamma, xi

    def predict(self, returns: np.ndarray) -> np.ndarray:
        """
        Predict most likely regime sequence (Viterbi algorithm).
        """
        if not self._fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        n = len(returns)
        k = self.n_regimes

        # Emission log-probabilities
        log_B = np.zeros((n, k))
        for j in range(k):
            log_B[:, j] = stats.norm.logpdf(returns, self.emission_means[j], self.emission_stds[j])

        # Viterbi
        log_delta = np.zeros((n, k))
        psi = np.zeros((n, k), dtype=int)

        log_delta[0] = np.log(self.initial_probs + 1e-10) + log_B[0]

        for t in range(1, n):
            for j in range(k):
                candidates = log_delta[t - 1] + np.log(self.transition_matrix[:, j] + 1e-10)
                psi[t, j] = np.argmax(candidates)
                log_delta[t, j] = candidates[psi[t, j]] + log_B[t, j]

        # Backtrack
        states = np.zeros(n, dtype=int)
        states[-1] = np.argmax(log_delta[-1])

        for t in range(n - 2, -1, -1):
            states[t] = psi[t + 1, states[t + 1]]

        return states

    def get_regime_probabilities(self, returns: np.ndarray) -> np.ndarray:
        """Get probability of each regime at each time step."""
        if not self._fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        alpha, beta, gamma, _ = self._forward_backward(returns)
        return gamma


# =============================================================================
# VOLATILITY REGIME CLASSIFIER
# =============================================================================

class VolatilityRegimeClassifier:
    """
    Classify volatility regimes using rolling statistics.
    """

    def __init__(
        self,
        lookback: int = 20,
        long_lookback: int = 252,
        extremely_low_percentile: float = 10,
        low_percentile: float = 30,
        high_percentile: float = 70,
        extremely_high_percentile: float = 90,
    ):
        self.lookback = lookback
        self.long_lookback = long_lookback
        self.extremely_low_pct = extremely_low_percentile
        self.low_pct = low_percentile
        self.high_pct = high_percentile
        self.extremely_high_pct = extremely_high_percentile

    def classify(self, returns: np.ndarray) -> Tuple[VolatilityRegime, Dict[str, float]]:
        """
        Classify current volatility regime.

        Returns:
            Tuple of (regime, metrics dict)
        """
        if len(returns) < self.lookback:
            return VolatilityRegime.NORMAL, {}

        # Current volatility
        current_vol = np.std(returns[-self.lookback:]) * np.sqrt(252)

        # Historical distribution
        n = min(len(returns), self.long_lookback)
        rolling_vols = []
        for i in range(self.lookback, n):
            rv = np.std(returns[i - self.lookback:i]) * np.sqrt(252)
            rolling_vols.append(rv)

        if not rolling_vols:
            return VolatilityRegime.NORMAL, {'current_vol': current_vol}

        # Percentile rank
        percentile = stats.percentileofscore(rolling_vols, current_vol)

        # Classify
        if percentile <= self.extremely_low_pct:
            regime = VolatilityRegime.EXTREMELY_LOW
        elif percentile <= self.low_pct:
            regime = VolatilityRegime.LOW
        elif percentile >= self.extremely_high_pct:
            regime = VolatilityRegime.EXTREMELY_HIGH
        elif percentile >= self.high_pct:
            regime = VolatilityRegime.HIGH
        else:
            regime = VolatilityRegime.NORMAL

        return regime, {
            'current_vol': current_vol,
            'percentile': percentile,
            'median_vol': np.median(rolling_vols),
            'vol_of_vol': np.std(rolling_vols),
        }


# =============================================================================
# TREND REGIME CLASSIFIER
# =============================================================================

class TrendRegimeClassifier:
    """
    Classify trend regimes using multiple indicators.
    """

    def __init__(
        self,
        short_lookback: int = 10,
        medium_lookback: int = 20,
        long_lookback: int = 50,
        adx_threshold: float = 25,
    ):
        self.short_lookback = short_lookback
        self.medium_lookback = medium_lookback
        self.long_lookback = long_lookback
        self.adx_threshold = adx_threshold

    def classify(
        self,
        prices: np.ndarray,
        highs: np.ndarray = None,
        lows: np.ndarray = None,
    ) -> Tuple[TrendRegime, Dict[str, float]]:
        """
        Classify current trend regime.
        """
        if len(prices) < self.long_lookback:
            return TrendRegime.NEUTRAL, {}

        # Calculate moving averages
        sma_short = np.mean(prices[-self.short_lookback:])
        sma_medium = np.mean(prices[-self.medium_lookback:])
        sma_long = np.mean(prices[-self.long_lookback:])

        current_price = prices[-1]

        # Calculate momentum
        momentum = (current_price - prices[-self.medium_lookback]) / prices[-self.medium_lookback]

        # Calculate ADX if high/low available
        adx = None
        if highs is not None and lows is not None:
            adx = self._calculate_adx(highs, lows, prices)

        # Determine trend
        ma_alignment = 0
        if current_price > sma_short > sma_medium > sma_long:
            ma_alignment = 2  # Perfect bullish alignment
        elif current_price > sma_short > sma_medium:
            ma_alignment = 1
        elif current_price < sma_short < sma_medium < sma_long:
            ma_alignment = -2  # Perfect bearish alignment
        elif current_price < sma_short < sma_medium:
            ma_alignment = -1

        # Classify regime
        if ma_alignment >= 2 and momentum > 0.05:
            regime = TrendRegime.STRONG_UPTREND
        elif ma_alignment >= 1 and momentum > 0.02:
            regime = TrendRegime.WEAK_UPTREND
        elif ma_alignment <= -2 and momentum < -0.05:
            regime = TrendRegime.STRONG_DOWNTREND
        elif ma_alignment <= -1 and momentum < -0.02:
            regime = TrendRegime.WEAK_DOWNTREND
        else:
            regime = TrendRegime.NEUTRAL

        # Adjust for ADX if available
        if adx is not None and adx < self.adx_threshold:
            # Low ADX suggests ranging market
            if regime in (TrendRegime.STRONG_UPTREND, TrendRegime.STRONG_DOWNTREND):
                regime = TrendRegime.WEAK_UPTREND if regime == TrendRegime.STRONG_UPTREND else TrendRegime.WEAK_DOWNTREND

        return regime, {
            'momentum': momentum,
            'ma_alignment': ma_alignment,
            'adx': adx,
            'sma_short': sma_short,
            'sma_medium': sma_medium,
            'sma_long': sma_long,
        }

    def _calculate_adx(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        period: int = 14,
    ) -> Optional[float]:
        """Calculate ADX indicator."""
        if len(highs) < period + 1:
            return None

        n = len(highs)

        # True Range
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )

        # Directional Movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Smoothed averages
        atr = self._wilder_smooth(tr, period)
        plus_di = 100 * self._wilder_smooth(plus_dm, period) / atr
        minus_di = 100 * self._wilder_smooth(minus_dm, period) / atr

        # DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = self._wilder_smooth(dx, period)

        return adx[-1] if len(adx) > 0 else None

    def _wilder_smooth(self, data: np.ndarray, period: int) -> np.ndarray:
        """Wilder's smoothing."""
        smoothed = np.zeros_like(data)
        smoothed[period - 1] = np.mean(data[:period])
        for i in range(period, len(data)):
            smoothed[i] = (smoothed[i - 1] * (period - 1) + data[i]) / period
        return smoothed[period - 1:]


# =============================================================================
# RISK ON/OFF DETECTOR
# =============================================================================

class RiskOnOffDetector:
    """
    Detect Risk-On vs Risk-Off market conditions.
    """

    def __init__(
        self,
        lookback: int = 20,
        correlation_threshold: float = 0.5,
    ):
        self.lookback = lookback
        self.correlation_threshold = correlation_threshold

    def detect(
        self,
        equity_returns: np.ndarray,
        bond_returns: np.ndarray = None,
        vix_level: float = None,
        gold_returns: np.ndarray = None,
    ) -> Tuple[MarketRegime, Dict[str, float]]:
        """
        Detect risk-on/risk-off regime.

        Uses cross-asset correlations and flight-to-safety indicators.
        """
        metrics = {}

        # Equity momentum
        equity_momentum = np.mean(equity_returns[-self.lookback:]) if len(equity_returns) >= self.lookback else 0
        metrics['equity_momentum'] = equity_momentum

        # VIX level check
        if vix_level is not None:
            metrics['vix'] = vix_level
            if vix_level > 30:
                return MarketRegime.RISK_OFF, metrics
            elif vix_level > 25:
                metrics['vix_signal'] = 'elevated'
            elif vix_level < 15:
                metrics['vix_signal'] = 'complacent'

        # Equity-Bond correlation
        if bond_returns is not None and len(bond_returns) >= self.lookback:
            if len(equity_returns) >= self.lookback:
                eq_bond_corr = np.corrcoef(
                    equity_returns[-self.lookback:],
                    bond_returns[-self.lookback:]
                )[0, 1]
                metrics['equity_bond_correlation'] = eq_bond_corr

                # Negative correlation = risk-off (flight to safety)
                if eq_bond_corr < -self.correlation_threshold:
                    metrics['flight_to_safety'] = True

        # Gold as safe haven
        if gold_returns is not None and len(gold_returns) >= self.lookback:
            gold_momentum = np.mean(gold_returns[-self.lookback:])
            metrics['gold_momentum'] = gold_momentum

            # Gold rising + equity falling = risk-off
            if gold_momentum > 0 and equity_momentum < 0:
                metrics['gold_safe_haven'] = True

        # Determine regime
        risk_off_signals = 0
        risk_on_signals = 0

        if equity_momentum > 0.001:
            risk_on_signals += 1
        elif equity_momentum < -0.001:
            risk_off_signals += 1

        if vix_level is not None:
            if vix_level > 25:
                risk_off_signals += 1
            elif vix_level < 18:
                risk_on_signals += 1

        if metrics.get('flight_to_safety'):
            risk_off_signals += 1
        if metrics.get('gold_safe_haven'):
            risk_off_signals += 1

        if risk_off_signals > risk_on_signals:
            return MarketRegime.RISK_OFF, metrics
        elif risk_on_signals > risk_off_signals:
            return MarketRegime.RISK_ON, metrics
        else:
            return MarketRegime.UNKNOWN, metrics


# =============================================================================
# UNIFIED REGIME DETECTOR
# =============================================================================

class MarketRegimeDetector:
    """
    Unified market regime detection combining multiple approaches.
    """

    def __init__(
        self,
        n_hmm_regimes: int = 3,
        vol_lookback: int = 20,
        trend_lookback: int = 50,
    ):
        self.hmm = HMMRegimeDetector(n_regimes=n_hmm_regimes)
        self.vol_classifier = VolatilityRegimeClassifier(lookback=vol_lookback)
        self.trend_classifier = TrendRegimeClassifier(long_lookback=trend_lookback)
        self.risk_detector = RiskOnOffDetector()

        self.regime_history: List[RegimeState] = []
        self._hmm_fitted = False

    def fit(self, returns: np.ndarray) -> 'MarketRegimeDetector':
        """Fit the regime detector on historical data."""
        self.hmm.fit(returns)
        self._hmm_fitted = True
        return self

    def detect(
        self,
        prices: np.ndarray,
        returns: np.ndarray = None,
        highs: np.ndarray = None,
        lows: np.ndarray = None,
        vix: float = None,
        bond_returns: np.ndarray = None,
    ) -> RegimeState:
        """
        Detect current market regime.

        Returns comprehensive regime state.
        """
        timestamp = datetime.now(timezone.utc)

        if returns is None:
            returns = np.diff(prices) / prices[:-1]

        # Volatility regime
        vol_regime, vol_metrics = self.vol_classifier.classify(returns)

        # Trend regime
        trend_regime, trend_metrics = self.trend_classifier.classify(prices, highs, lows)

        # Risk on/off
        risk_regime, risk_metrics = self.risk_detector.detect(
            returns,
            bond_returns=bond_returns,
            vix_level=vix,
        )

        # HMM regime (if fitted)
        hmm_state = None
        hmm_probs = {}
        if self._hmm_fitted:
            hmm_states = self.hmm.predict(returns)
            hmm_state = hmm_states[-1]
            probs = self.hmm.get_regime_probabilities(returns)
            hmm_probs = {f"hmm_state_{i}": probs[-1, i] for i in range(probs.shape[1])}

        # Determine primary regime
        primary_regime = self._synthesize_regime(
            vol_regime, trend_regime, risk_regime, hmm_state
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            vol_regime, trend_regime, risk_regime, vol_metrics, trend_metrics
        )

        # Build probabilities
        probabilities = {
            MarketRegime.TRENDING_UP: 0.0,
            MarketRegime.TRENDING_DOWN: 0.0,
            MarketRegime.RANGING: 0.0,
            MarketRegime.HIGH_VOLATILITY: 0.0,
            MarketRegime.LOW_VOLATILITY: 0.0,
            MarketRegime.RISK_ON: 0.0,
            MarketRegime.RISK_OFF: 0.0,
        }

        # Assign probabilities based on classifiers
        if trend_regime == TrendRegime.STRONG_UPTREND:
            probabilities[MarketRegime.TRENDING_UP] = 0.9
        elif trend_regime == TrendRegime.WEAK_UPTREND:
            probabilities[MarketRegime.TRENDING_UP] = 0.6
        elif trend_regime == TrendRegime.STRONG_DOWNTREND:
            probabilities[MarketRegime.TRENDING_DOWN] = 0.9
        elif trend_regime == TrendRegime.WEAK_DOWNTREND:
            probabilities[MarketRegime.TRENDING_DOWN] = 0.6
        else:
            probabilities[MarketRegime.RANGING] = 0.7

        if vol_regime in (VolatilityRegime.HIGH, VolatilityRegime.EXTREMELY_HIGH):
            probabilities[MarketRegime.HIGH_VOLATILITY] = 0.8
        elif vol_regime in (VolatilityRegime.LOW, VolatilityRegime.EXTREMELY_LOW):
            probabilities[MarketRegime.LOW_VOLATILITY] = 0.8

        if risk_regime == MarketRegime.RISK_ON:
            probabilities[MarketRegime.RISK_ON] = 0.7
        elif risk_regime == MarketRegime.RISK_OFF:
            probabilities[MarketRegime.RISK_OFF] = 0.7

        state = RegimeState(
            primary_regime=primary_regime,
            volatility_regime=vol_regime,
            trend_regime=trend_regime,
            confidence=confidence,
            timestamp=timestamp,
            probabilities=probabilities,
            metadata={
                'volatility': vol_metrics,
                'trend': trend_metrics,
                'risk': risk_metrics,
                'hmm_state': hmm_state,
                'hmm_probs': hmm_probs,
            }
        )

        self.regime_history.append(state)
        return state

    def _synthesize_regime(
        self,
        vol_regime: VolatilityRegime,
        trend_regime: TrendRegime,
        risk_regime: MarketRegime,
        hmm_state: Optional[int],
    ) -> MarketRegime:
        """Synthesize primary regime from multiple classifiers."""
        # Priority: Crisis > Risk-Off > Trend > Volatility > Ranging

        # Check for crisis conditions
        if vol_regime == VolatilityRegime.EXTREMELY_HIGH and risk_regime == MarketRegime.RISK_OFF:
            return MarketRegime.CRISIS

        # Check for risk regimes
        if risk_regime == MarketRegime.RISK_OFF:
            return MarketRegime.RISK_OFF
        elif risk_regime == MarketRegime.RISK_ON:
            # Continue to check trend
            pass

        # Trend-based classification
        if trend_regime in (TrendRegime.STRONG_UPTREND, TrendRegime.WEAK_UPTREND):
            return MarketRegime.TRENDING_UP
        elif trend_regime in (TrendRegime.STRONG_DOWNTREND, TrendRegime.WEAK_DOWNTREND):
            return MarketRegime.TRENDING_DOWN

        # Volatility-based when neutral trend
        if vol_regime in (VolatilityRegime.HIGH, VolatilityRegime.EXTREMELY_HIGH):
            return MarketRegime.HIGH_VOLATILITY
        elif vol_regime in (VolatilityRegime.LOW, VolatilityRegime.EXTREMELY_LOW):
            return MarketRegime.LOW_VOLATILITY

        return MarketRegime.RANGING

    def _calculate_confidence(
        self,
        vol_regime: VolatilityRegime,
        trend_regime: TrendRegime,
        risk_regime: MarketRegime,
        vol_metrics: Dict,
        trend_metrics: Dict,
    ) -> float:
        """Calculate confidence in regime classification."""
        confidence = 0.5  # Base confidence

        # Trend strength
        momentum = abs(trend_metrics.get('momentum', 0))
        if momentum > 0.05:
            confidence += 0.2
        elif momentum > 0.02:
            confidence += 0.1

        # MA alignment
        ma_alignment = abs(trend_metrics.get('ma_alignment', 0))
        confidence += ma_alignment * 0.1

        # ADX strength
        adx = trend_metrics.get('adx')
        if adx is not None:
            if adx > 40:
                confidence += 0.15
            elif adx > 25:
                confidence += 0.1

        # Volatility percentile extremes
        percentile = vol_metrics.get('percentile', 50)
        if percentile > 90 or percentile < 10:
            confidence += 0.1

        return min(1.0, confidence)

    def get_regime_duration(self, regime: MarketRegime = None) -> int:
        """Get duration of current or specified regime."""
        if not self.regime_history:
            return 0

        if regime is None:
            regime = self.regime_history[-1].primary_regime

        count = 0
        for state in reversed(self.regime_history):
            if state.primary_regime == regime:
                count += 1
            else:
                break

        return count

    def get_transition_probability(
        self,
        from_regime: MarketRegime,
        to_regime: MarketRegime,
    ) -> float:
        """Get historical transition probability."""
        if len(self.regime_history) < 2:
            return 0.0

        transitions = 0
        from_count = 0

        for i in range(len(self.regime_history) - 1):
            if self.regime_history[i].primary_regime == from_regime:
                from_count += 1
                if self.regime_history[i + 1].primary_regime == to_regime:
                    transitions += 1

        return transitions / from_count if from_count > 0 else 0.0


# =============================================================================
# MULTI-TIMEFRAME REGIME FUSION
# =============================================================================

class MultiTimeframeRegimeFusion:
    """
    Combine regime signals from multiple timeframes.
    """

    def __init__(
        self,
        timeframe_weights: Dict[str, float] = None,
    ):
        self.timeframe_weights = timeframe_weights or {
            '1min': 0.1,
            '5min': 0.15,
            '15min': 0.2,
            '1hour': 0.25,
            '4hour': 0.15,
            'daily': 0.15,
        }
        self.detectors: Dict[str, MarketRegimeDetector] = {}

    def add_detector(self, timeframe: str, detector: MarketRegimeDetector) -> None:
        """Add detector for a timeframe."""
        self.detectors[timeframe] = detector

    def fuse(
        self,
        regime_states: Dict[str, RegimeState],
    ) -> RegimeState:
        """
        Fuse regime states from multiple timeframes.

        Args:
            regime_states: Dict of timeframe -> RegimeState
        """
        if not regime_states:
            return RegimeState(
                primary_regime=MarketRegime.UNKNOWN,
                volatility_regime=VolatilityRegime.NORMAL,
                trend_regime=TrendRegime.NEUTRAL,
                confidence=0.0,
                timestamp=datetime.now(timezone.utc),
            )

        # Weighted voting for primary regime
        regime_votes: Dict[MarketRegime, float] = defaultdict(float)
        vol_votes: Dict[VolatilityRegime, float] = defaultdict(float)
        trend_votes: Dict[TrendRegime, float] = defaultdict(float)

        total_weight = 0.0
        weighted_confidence = 0.0

        for tf, state in regime_states.items():
            weight = self.timeframe_weights.get(tf, 0.1)
            total_weight += weight

            regime_votes[state.primary_regime] += weight * state.confidence
            vol_votes[state.volatility_regime] += weight * state.confidence
            trend_votes[state.trend_regime] += weight * state.confidence
            weighted_confidence += weight * state.confidence

        # Select winners
        primary = max(regime_votes.keys(), key=lambda k: regime_votes[k])
        vol = max(vol_votes.keys(), key=lambda k: vol_votes[k])
        trend = max(trend_votes.keys(), key=lambda k: trend_votes[k])

        # Normalize confidence
        if total_weight > 0:
            confidence = weighted_confidence / total_weight
        else:
            confidence = 0.0

        return RegimeState(
            primary_regime=primary,
            volatility_regime=vol,
            trend_regime=trend,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            metadata={
                'timeframes': list(regime_states.keys()),
                'regime_votes': dict(regime_votes),
            }
        )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
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
]
