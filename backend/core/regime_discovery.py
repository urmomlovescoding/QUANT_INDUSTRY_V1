"""
Regime Discovery
================
P0 Critical Feature: Market regime detection and classification.

Implements parity with quant-platform/core/regime_discovery.py

Market Regimes:
1. TRENDING_UP - Strong upward trend
2. TRENDING_DOWN - Strong downward trend
3. RANGING - Sideways/consolidation
4. VOLATILE - High volatility without clear direction
5. BREAKOUT - Transitioning from range to trend
6. MEAN_REVERTING - Price oscillating around mean
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

logger = logging.getLogger("REGIME_DISCOVERY")


class MarketRegime(Enum):
    """Market regime classifications."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    BREAKOUT = "breakout"
    MEAN_REVERTING = "mean_reverting"
    UNKNOWN = "unknown"


@dataclass
class RegimeState:
    """Current regime state with confidence."""
    regime: MarketRegime
    confidence: float
    since: datetime
    duration_bars: int = 0

    # Supporting metrics
    trend_strength: float = 0.0
    volatility: float = 0.0
    atr_percentile: float = 0.0

    # Regime probabilities
    probabilities: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value,
            "confidence": self.confidence,
            "since": self.since.isoformat(),
            "duration_bars": self.duration_bars,
            "trend_strength": self.trend_strength,
            "volatility": self.volatility,
            "atr_percentile": self.atr_percentile,
            "probabilities": self.probabilities,
        }


@dataclass
class RegimeTransition:
    """Record of a regime change."""
    timestamp: datetime
    from_regime: MarketRegime
    to_regime: MarketRegime
    confidence: float
    trigger: str  # What caused the transition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "from_regime": self.from_regime.value,
            "to_regime": self.to_regime.value,
            "confidence": self.confidence,
            "trigger": self.trigger,
        }


class RegimeDiscovery:
    """
    Market regime detection and classification.

    Uses multiple indicators to determine current market regime:
    - ADX for trend strength
    - ATR for volatility
    - Bollinger Band width for ranging
    - Price position relative to moving averages
    - Volume patterns

    Matches quant-platform behavior exactly.
    """

    def __init__(self):
        # Current state
        self.current_state: Optional[RegimeState] = None
        self.transition_history: List[RegimeTransition] = []

        # Detection thresholds (match platform)
        self.thresholds = {
            "trend_adx_min": 25.0,          # ADX > 25 = trending
            "strong_trend_adx": 40.0,       # ADX > 40 = strong trend
            "ranging_adx_max": 20.0,        # ADX < 20 = ranging
            "volatility_atr_high": 75,      # ATR percentile for high vol
            "volatility_atr_low": 25,       # ATR percentile for low vol
            "bb_width_narrow": 0.02,        # 2% BB width = narrow
            "bb_width_wide": 0.08,          # 8% BB width = wide
            "trend_ma_diff": 0.02,          # 2% diff from MA = trending
        }

        # Lookback periods
        self.adx_period: int = 14
        self.atr_period: int = 14
        self.ma_period: int = 50
        self.bb_period: int = 20

        # Regime stability
        self.min_bars_for_transition: int = 3
        self.transition_cooldown: int = 5

        logger.info("RegimeDiscovery initialized")

    def detect_regime(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: Optional[List[float]] = None,
        timestamps: Optional[List[datetime]] = None,
    ) -> RegimeState:
        """
        Detect current market regime.

        Args:
            opens: Open prices
            highs: High prices
            lows: Low prices
            closes: Close prices
            volumes: Volume data (optional)
            timestamps: Candle timestamps (optional)

        Returns:
            Current regime state with confidence
        """
        if len(closes) < 50:
            return RegimeState(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                since=datetime.now(),
            )

        # Calculate indicators
        adx = self._calculate_adx(highs, lows, closes)
        atr = self._calculate_atr(highs, lows, closes)
        atr_percentile = self._calculate_percentile(atr, self._calculate_atr_history(highs, lows, closes))
        bb_width = self._calculate_bb_width(closes)
        ma = self._calculate_sma(closes, self.ma_period)
        trend_direction = self._determine_trend_direction(closes, ma)

        # Calculate regime probabilities
        probabilities = self._calculate_regime_probabilities(
            adx, atr_percentile, bb_width, trend_direction, closes
        )

        # Select regime with highest probability
        best_regime = max(probabilities, key=probabilities.get)
        confidence = probabilities[best_regime]

        regime = MarketRegime(best_regime)

        # Create state
        current_time = timestamps[-1] if timestamps else datetime.now()

        new_state = RegimeState(
            regime=regime,
            confidence=confidence,
            since=current_time,
            trend_strength=adx / 100.0,  # Normalize to 0-1
            volatility=atr_percentile / 100.0,
            atr_percentile=atr_percentile,
            probabilities=probabilities,
        )

        # Check for transition
        if self.current_state and self.current_state.regime != regime:
            if confidence >= 0.6:  # Only transition with confidence
                transition = RegimeTransition(
                    timestamp=current_time,
                    from_regime=self.current_state.regime,
                    to_regime=regime,
                    confidence=confidence,
                    trigger=self._determine_trigger(adx, atr_percentile, bb_width),
                )
                self.transition_history.append(transition)
                logger.info(
                    f"Regime transition: {transition.from_regime.value} -> "
                    f"{transition.to_regime.value} (confidence={confidence:.2f})"
                )
                self.current_state = new_state
        else:
            if self.current_state:
                self.current_state.duration_bars += 1
                self.current_state.confidence = confidence
                self.current_state.probabilities = probabilities
            else:
                self.current_state = new_state

        return self.current_state

    def _calculate_adx(self, highs: List[float], lows: List[float], closes: List[float]) -> float:
        """Calculate Average Directional Index."""
        if len(closes) < self.adx_period + 1:
            return 0.0

        highs = np.array(highs)
        lows = np.array(lows)
        closes = np.array(closes)

        # True Range
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                abs(highs[1:] - closes[:-1]),
                abs(lows[1:] - closes[:-1])
            )
        )

        # Directional Movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Smoothed values
        atr = self._smooth(tr, self.adx_period)
        plus_di = 100 * self._smooth(plus_dm, self.adx_period) / atr
        minus_di = 100 * self._smooth(minus_dm, self.adx_period) / atr

        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = self._smooth(dx, self.adx_period)

        return float(adx[-1]) if len(adx) > 0 else 0.0

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float]) -> float:
        """Calculate Average True Range."""
        if len(closes) < self.atr_period + 1:
            return 0.0

        highs = np.array(highs)
        lows = np.array(lows)
        closes = np.array(closes)

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                abs(highs[1:] - closes[:-1]),
                abs(lows[1:] - closes[:-1])
            )
        )

        atr = self._smooth(tr, self.atr_period)
        return float(atr[-1]) if len(atr) > 0 else 0.0

    def _calculate_atr_history(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        lookback: int = 100,
    ) -> List[float]:
        """Calculate ATR history for percentile calculation."""
        if len(closes) < self.atr_period + lookback:
            return [self._calculate_atr(highs, lows, closes)]

        history = []
        for i in range(lookback):
            end = len(closes) - i
            start = max(0, end - self.atr_period - 1)
            if end - start >= self.atr_period:
                atr = self._calculate_atr(
                    highs[start:end],
                    lows[start:end],
                    closes[start:end]
                )
                history.append(atr)
        return history

    def _calculate_percentile(self, value: float, history: List[float]) -> float:
        """Calculate percentile of value in history."""
        if not history:
            return 50.0
        return float(np.percentile(history, value / max(history) * 100))

    def _calculate_bb_width(self, closes: List[float]) -> float:
        """Calculate Bollinger Band width as percentage."""
        if len(closes) < self.bb_period:
            return 0.0

        closes = np.array(closes[-self.bb_period:])
        sma = np.mean(closes)
        std = np.std(closes)

        upper = sma + 2 * std
        lower = sma - 2 * std

        return (upper - lower) / sma

    def _calculate_sma(self, data: List[float], period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(data) < period:
            return np.mean(data)
        return np.mean(data[-period:])

    def _smooth(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential smoothing."""
        alpha = 1.0 / period
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
        return result

    def _determine_trend_direction(self, closes: List[float], ma: float) -> int:
        """Determine trend direction: 1=up, -1=down, 0=neutral."""
        if len(closes) < 2:
            return 0

        current = closes[-1]
        ma_diff = (current - ma) / ma

        if ma_diff > self.thresholds["trend_ma_diff"]:
            return 1
        elif ma_diff < -self.thresholds["trend_ma_diff"]:
            return -1
        return 0

    def _calculate_regime_probabilities(
        self,
        adx: float,
        atr_percentile: float,
        bb_width: float,
        trend_direction: int,
        closes: List[float],
    ) -> Dict[str, float]:
        """Calculate probability for each regime."""
        probs = {
            MarketRegime.TRENDING_UP.value: 0.0,
            MarketRegime.TRENDING_DOWN.value: 0.0,
            MarketRegime.RANGING.value: 0.0,
            MarketRegime.VOLATILE.value: 0.0,
            MarketRegime.BREAKOUT.value: 0.0,
            MarketRegime.MEAN_REVERTING.value: 0.0,
        }

        # Trending up
        if adx > self.thresholds["trend_adx_min"] and trend_direction > 0:
            probs[MarketRegime.TRENDING_UP.value] = min(1.0, adx / 60) * 0.9
            if adx > self.thresholds["strong_trend_adx"]:
                probs[MarketRegime.TRENDING_UP.value] = 0.95

        # Trending down
        if adx > self.thresholds["trend_adx_min"] and trend_direction < 0:
            probs[MarketRegime.TRENDING_DOWN.value] = min(1.0, adx / 60) * 0.9
            if adx > self.thresholds["strong_trend_adx"]:
                probs[MarketRegime.TRENDING_DOWN.value] = 0.95

        # Ranging
        if adx < self.thresholds["ranging_adx_max"] and bb_width < self.thresholds["bb_width_narrow"]:
            probs[MarketRegime.RANGING.value] = (self.thresholds["ranging_adx_max"] - adx) / self.thresholds["ranging_adx_max"]

        # Volatile
        if atr_percentile > self.thresholds["volatility_atr_high"] and adx < self.thresholds["trend_adx_min"]:
            probs[MarketRegime.VOLATILE.value] = atr_percentile / 100

        # Breakout - transitioning from low vol to high vol
        if bb_width > self.thresholds["bb_width_wide"] and adx > 20 and adx < 35:
            probs[MarketRegime.BREAKOUT.value] = 0.7

        # Mean reverting
        if adx < 25 and bb_width < self.thresholds["bb_width_wide"]:
            # Check if price is oscillating
            if len(closes) >= 20:
                recent = np.array(closes[-20:])
                mean = np.mean(recent)
                crosses = np.sum(np.diff(np.sign(recent - mean)) != 0)
                if crosses >= 4:
                    probs[MarketRegime.MEAN_REVERTING.value] = min(0.8, crosses / 10)

        # Normalize probabilities
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}

        return probs

    def _determine_trigger(self, adx: float, atr_percentile: float, bb_width: float) -> str:
        """Determine what triggered the regime change."""
        triggers = []
        if adx > self.thresholds["trend_adx_min"]:
            triggers.append(f"ADX={adx:.1f}")
        if atr_percentile > self.thresholds["volatility_atr_high"]:
            triggers.append(f"ATR_pct={atr_percentile:.0f}")
        if bb_width > self.thresholds["bb_width_wide"]:
            triggers.append(f"BB_wide={bb_width:.2%}")
        elif bb_width < self.thresholds["bb_width_narrow"]:
            triggers.append(f"BB_narrow={bb_width:.2%}")
        return ", ".join(triggers) if triggers else "conditions_changed"

    def get_transition_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent regime transitions."""
        return [t.to_dict() for t in self.transition_history[-limit:]]

    def get_regime_stats(self, lookback_days: int = 30) -> Dict[str, Any]:
        """Get regime statistics over lookback period."""
        if not self.transition_history:
            return {"message": "No transition history"}

        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent = [t for t in self.transition_history if t.timestamp >= cutoff]

        regime_counts = {}
        for t in recent:
            regime_counts[t.to_regime.value] = regime_counts.get(t.to_regime.value, 0) + 1

        return {
            "period_days": lookback_days,
            "total_transitions": len(recent),
            "regime_counts": regime_counts,
            "avg_transitions_per_day": len(recent) / lookback_days if lookback_days > 0 else 0,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get regime discovery status."""
        return {
            "current_state": self.current_state.to_dict() if self.current_state else None,
            "transition_count": len(self.transition_history),
            "recent_transitions": self.get_transition_history(5),
            "thresholds": self.thresholds,
        }


# Singleton instance
_regime_discovery: Optional[RegimeDiscovery] = None


def get_regime_discovery() -> RegimeDiscovery:
    """Get or create regime discovery singleton."""
    global _regime_discovery
    if _regime_discovery is None:
        _regime_discovery = RegimeDiscovery()
    return _regime_discovery
