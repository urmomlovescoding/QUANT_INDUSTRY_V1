"""
QUANT INDUSTRY - Adaptive Market Intelligence & Flow Analysis Engine
====================================================================
Market microstructure awareness and adaptive signal generation.
Understands not just WHAT to trade, but WHEN conditions favor trading
and HOW the market is behaving.

Modules:
1. Order Flow Imbalance Detection
2. Volatility Regime Classifier
3. Liquidity Monitoring
4. Signal Confidence Decay
5. Adaptive Position Sizing
6. Market Hours Awareness
7. Cross-Asset Signal Validation

All modules are OPTIONAL enhancers with clear on/off toggles.
System works without them, but works BETTER with them.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============== ENUMS ==============

class VolatilityState(Enum):
    """Real-time volatility regime classification"""
    COMPRESSED = "COMPRESSED"
    NORMAL = "NORMAL"
    EXPANDING = "EXPANDING"
    CRISIS = "CRISIS"


class LiquidityState(Enum):
    """Liquidity condition classification"""
    DEEP = "DEEP"
    NORMAL = "NORMAL"
    THIN = "THIN"
    VACUUM = "VACUUM"


class MarketSession(Enum):
    """Market trading session"""
    PRE_MARKET = "PRE_MARKET"
    OPEN_AUCTION = "OPEN_AUCTION"
    MORNING = "MORNING"
    MIDDAY = "MIDDAY"
    AFTERNOON = "AFTERNOON"
    CLOSE_AUCTION = "CLOSE_AUCTION"
    AFTER_HOURS = "AFTER_HOURS"
    CLOSED = "CLOSED"


class FlowDirection(Enum):
    """Order flow direction"""
    BUYING = "BUYING"
    SELLING = "SELLING"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


# ============== DATA CLASSES ==============

@dataclass
class OrderFlowSnapshot:
    """Point-in-time order flow state"""
    symbol: str
    timestamp: datetime
    bid_volume: float
    ask_volume: float
    imbalance_ratio: float  # (bid - ask) / (bid + ask), range [-1, 1]
    flow_toxicity: float  # 0 (benign) to 1 (highly toxic)
    absorption_detected: bool
    iceberg_probability: float  # 0 to 1
    flow_direction: FlowDirection
    net_flow: float
    cumulative_delta: float
    unusual_flow: bool
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "bid_volume": round(self.bid_volume, 2),
            "ask_volume": round(self.ask_volume, 2),
            "imbalance_ratio": round(self.imbalance_ratio, 4),
            "flow_toxicity": round(self.flow_toxicity, 4),
            "absorption_detected": self.absorption_detected,
            "iceberg_probability": round(self.iceberg_probability, 4),
            "flow_direction": self.flow_direction.value,
            "net_flow": round(self.net_flow, 2),
            "cumulative_delta": round(self.cumulative_delta, 2),
            "unusual_flow": self.unusual_flow,
            "alerts": self.alerts,
        }


@dataclass
class VolatilityRegimeState:
    """Current volatility regime with metrics"""
    state: VolatilityState
    confidence: float
    timestamp: datetime
    atr_current: float
    atr_percentile: float  # Where current ATR sits vs history
    bollinger_width: float
    bollinger_width_percentile: float
    vix_level: float
    vix_term_structure: str  # contango / backwardation / flat
    regime_duration_bars: int
    transition_probability: float  # Prob of regime change
    position_size_multiplier: float  # Sizing adjustment
    history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "state": self.state.value,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp.isoformat(),
            "atr_current": round(self.atr_current, 4),
            "atr_percentile": round(self.atr_percentile, 4),
            "bollinger_width": round(self.bollinger_width, 4),
            "bollinger_width_percentile": round(self.bollinger_width_percentile, 4),
            "vix_level": round(self.vix_level, 2),
            "vix_term_structure": self.vix_term_structure,
            "regime_duration_bars": self.regime_duration_bars,
            "transition_probability": round(self.transition_probability, 4),
            "position_size_multiplier": round(self.position_size_multiplier, 4),
            "history": self.history[-20:],
        }


@dataclass
class LiquiditySnapshot:
    """Current liquidity conditions"""
    symbol: str
    timestamp: datetime
    state: LiquidityState
    spread_bps: float  # Spread in basis points
    spread_percentile: float  # Where current spread sits vs history
    relative_volume: float  # Current vol vs average
    depth_score: float  # 0 (no depth) to 1 (deep)
    fill_quality_estimate: float  # Expected slippage in bps
    deteriorating: bool
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "state": self.state.value,
            "spread_bps": round(self.spread_bps, 2),
            "spread_percentile": round(self.spread_percentile, 4),
            "relative_volume": round(self.relative_volume, 4),
            "depth_score": round(self.depth_score, 4),
            "fill_quality_estimate": round(self.fill_quality_estimate, 2),
            "deteriorating": self.deteriorating,
            "alerts": self.alerts,
        }


@dataclass
class SignalConfidenceState:
    """Signal with time-decaying confidence"""
    signal_id: str
    symbol: str
    direction: str  # BUY / SELL / HOLD
    initial_confidence: float
    current_confidence: float
    created_at: datetime
    last_updated: datetime
    decay_rate: float  # per-minute decay
    regime_modifier: float
    performance_modifier: float
    correlation_modifier: float
    is_actionable: bool
    time_alive_seconds: float
    factors: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "initial_confidence": round(self.initial_confidence, 4),
            "current_confidence": round(self.current_confidence, 4),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "decay_rate": round(self.decay_rate, 6),
            "regime_modifier": round(self.regime_modifier, 4),
            "performance_modifier": round(self.performance_modifier, 4),
            "correlation_modifier": round(self.correlation_modifier, 4),
            "is_actionable": self.is_actionable,
            "time_alive_seconds": round(self.time_alive_seconds, 1),
            "factors": {k: round(v, 4) for k, v in self.factors.items()},
        }


@dataclass
class PositionSizeResult:
    """Adaptive position sizing decision with reasoning"""
    symbol: str
    base_size: float  # Raw Kelly / model output
    adjusted_size: float  # After all adjustments
    max_size: float  # Hard cap
    final_size: float  # min(adjusted, max)
    adjustments: Dict[str, float] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "base_size": round(self.base_size, 4),
            "adjusted_size": round(self.adjusted_size, 4),
            "max_size": round(self.max_size, 4),
            "final_size": round(self.final_size, 4),
            "adjustments": {k: round(v, 4) for k, v in self.adjustments.items()},
            "reasoning": self.reasoning,
        }


@dataclass
class SessionProfile:
    """Market session behavior profile"""
    session: MarketSession
    avg_volatility: float
    avg_volume_ratio: float
    avg_spread_bps: float
    win_rate: float
    avg_pnl: float
    trade_count: int
    recommended_action: str  # "trade_normal", "reduce_size", "avoid", "aggressive"

    def to_dict(self) -> Dict:
        return {
            "session": self.session.value,
            "avg_volatility": round(self.avg_volatility, 4),
            "avg_volume_ratio": round(self.avg_volume_ratio, 4),
            "avg_spread_bps": round(self.avg_spread_bps, 2),
            "win_rate": round(self.win_rate, 4),
            "avg_pnl": round(self.avg_pnl, 2),
            "trade_count": self.trade_count,
            "recommended_action": self.recommended_action,
        }


@dataclass
class CrossAssetValidation:
    """Cross-asset signal confirmation result"""
    symbol: str
    signal_direction: str
    confirmation_score: float  # -1 (contradicts) to 1 (confirms)
    sector_alignment: float
    correlation_check: float
    options_flow_alignment: float
    is_confirmed: bool
    confirming_assets: List[Dict] = field(default_factory=list)
    diverging_assets: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "signal_direction": self.signal_direction,
            "confirmation_score": round(self.confirmation_score, 4),
            "confirming_assets": self.confirming_assets,
            "diverging_assets": self.diverging_assets,
            "sector_alignment": round(self.sector_alignment, 4),
            "correlation_check": round(self.correlation_check, 4),
            "options_flow_alignment": round(self.options_flow_alignment, 4),
            "is_confirmed": self.is_confirmed,
        }


@dataclass
class MicrostructureConfig:
    """Configuration for all microstructure modules"""
    # Module toggles
    order_flow_enabled: bool = True
    volatility_regime_enabled: bool = True
    liquidity_monitor_enabled: bool = True
    signal_decay_enabled: bool = True
    adaptive_sizing_enabled: bool = True
    market_hours_enabled: bool = True
    cross_asset_enabled: bool = True

    # Order flow params
    flow_toxicity_threshold: float = 0.7
    imbalance_alert_threshold: float = 0.6
    absorption_volume_ratio: float = 3.0

    # Volatility regime params
    atr_lookback: int = 14
    bollinger_lookback: int = 20
    volatility_history_bars: int = 252
    compression_percentile: float = 20.0
    expansion_percentile: float = 80.0
    crisis_percentile: float = 95.0

    # Liquidity params
    spread_history_size: int = 100
    thin_liquidity_percentile: float = 80.0
    vacuum_liquidity_percentile: float = 95.0

    # Signal decay params
    base_decay_rate: float = 0.002  # 0.2% per minute
    min_actionable_confidence: float = 0.3
    max_signal_age_minutes: float = 120.0

    # Position sizing params
    kelly_fraction: float = 0.25  # Quarter-Kelly
    max_position_pct: float = 0.05  # 5% of portfolio
    drawdown_reduction_threshold: float = 0.05  # Start reducing at 5% DD
    drawdown_max_reduction: float = 0.5  # Reduce to 50% at max DD

    # Market hours params
    avoid_first_minutes: int = 5  # Avoid first 5 min after open
    avoid_last_minutes: int = 5  # Avoid last 5 min before close
    low_liquidity_reduction: float = 0.5

    # Cross-asset params
    min_confirmation_score: float = 0.3
    sector_weight: float = 0.4
    correlation_weight: float = 0.3
    options_weight: float = 0.3

    def to_dict(self) -> Dict:
        return {
            "modules": {
                "order_flow": self.order_flow_enabled,
                "volatility_regime": self.volatility_regime_enabled,
                "liquidity_monitor": self.liquidity_monitor_enabled,
                "signal_decay": self.signal_decay_enabled,
                "adaptive_sizing": self.adaptive_sizing_enabled,
                "market_hours": self.market_hours_enabled,
                "cross_asset": self.cross_asset_enabled,
            },
            "order_flow": {
                "toxicity_threshold": self.flow_toxicity_threshold,
                "imbalance_alert_threshold": self.imbalance_alert_threshold,
                "absorption_volume_ratio": self.absorption_volume_ratio,
            },
            "volatility_regime": {
                "atr_lookback": self.atr_lookback,
                "bollinger_lookback": self.bollinger_lookback,
                "history_bars": self.volatility_history_bars,
                "compression_percentile": self.compression_percentile,
                "expansion_percentile": self.expansion_percentile,
                "crisis_percentile": self.crisis_percentile,
            },
            "liquidity": {
                "spread_history_size": self.spread_history_size,
                "thin_percentile": self.thin_liquidity_percentile,
                "vacuum_percentile": self.vacuum_liquidity_percentile,
            },
            "signal_decay": {
                "base_decay_rate": self.base_decay_rate,
                "min_actionable_confidence": self.min_actionable_confidence,
                "max_signal_age_minutes": self.max_signal_age_minutes,
            },
            "position_sizing": {
                "kelly_fraction": self.kelly_fraction,
                "max_position_pct": self.max_position_pct,
                "drawdown_reduction_threshold": self.drawdown_reduction_threshold,
                "drawdown_max_reduction": self.drawdown_max_reduction,
            },
            "market_hours": {
                "avoid_first_minutes": self.avoid_first_minutes,
                "avoid_last_minutes": self.avoid_last_minutes,
                "low_liquidity_reduction": self.low_liquidity_reduction,
            },
            "cross_asset": {
                "min_confirmation_score": self.min_confirmation_score,
                "sector_weight": self.sector_weight,
                "correlation_weight": self.correlation_weight,
                "options_weight": self.options_weight,
            },
        }


# ============== MODULE 1: ORDER FLOW IMBALANCE DETECTION ==============

class OrderFlowAnalyzer:
    """
    Tracks bid/ask imbalance ratios, detects absorption and iceberg orders,
    calculates flow toxicity scores, and alerts on unusual patterns.

    Works with available quote data (bid/ask/volume). When tick data is
    unavailable, infers flow characteristics from quote changes.
    """

    def __init__(self, config: MicrostructureConfig):
        self.config = config
        self._lock = threading.Lock()
        # Rolling history per symbol
        self._flow_history: Dict[str, List[Dict]] = {}
        self._cumulative_delta: Dict[str, float] = {}
        self._max_history = 500

    def analyze(
        self,
        symbol: str,
        bid: float,
        ask: float,
        price: float,
        volume: float,
        prev_price: float = None,
        prev_volume: float = None,
        prev_bid: float = None,
        prev_ask: float = None,
    ) -> OrderFlowSnapshot:
        """Analyze current order flow state from quote data."""
        now = datetime.now(timezone.utc)

        with self._lock:
            history = self._flow_history.setdefault(symbol, [])
            cum_delta = self._cumulative_delta.get(symbol, 0.0)

        spread = ask - bid if ask > bid else 0.001
        mid = (bid + ask) / 2.0

        # Estimate bid/ask volume split using trade classification
        # Lee-Ready algorithm approximation: if price > mid, classify as buy
        if prev_price is not None and volume > 0:
            if price > mid:
                bid_vol = volume * 0.3
                ask_vol = volume * 0.7
            elif price < mid:
                bid_vol = volume * 0.7
                ask_vol = volume * 0.3
            else:
                # Use tick rule: compare to previous price
                if price > prev_price:
                    bid_vol = volume * 0.35
                    ask_vol = volume * 0.65
                elif price < prev_price:
                    bid_vol = volume * 0.65
                    ask_vol = volume * 0.35
                else:
                    bid_vol = volume * 0.5
                    ask_vol = volume * 0.5
        else:
            bid_vol = volume * 0.5
            ask_vol = volume * 0.5

        # Imbalance ratio: positive = buying pressure, negative = selling
        total_vol = bid_vol + ask_vol
        if total_vol > 0:
            imbalance = (ask_vol - bid_vol) / total_vol  # buy-side imbalance
        else:
            imbalance = 0.0

        # Net flow
        net_flow = ask_vol - bid_vol
        cum_delta += net_flow

        # Flow toxicity (VPIN-inspired)
        # Higher when volume is one-sided and price doesn't move proportionally
        price_change = abs(price - prev_price) if prev_price else 0.0
        expected_move = spread * abs(imbalance) if spread > 0 else 0.0
        if expected_move > 0 and price_change > 0:
            toxicity = min(1.0, abs(imbalance) * (expected_move / max(price_change, 0.0001)))
        else:
            toxicity = abs(imbalance) * 0.5

        # Absorption detection: large volume with minimal price movement
        absorption = False
        if prev_price is not None and volume > 0 and prev_volume and prev_volume > 0:
            vol_ratio = volume / prev_volume
            price_move_pct = abs(price - prev_price) / prev_price if prev_price > 0 else 0
            if vol_ratio > self.config.absorption_volume_ratio and price_move_pct < 0.001:
                absorption = True

        # Iceberg detection: repeated fills at same price with consistent size
        iceberg_prob = 0.0
        if len(history) >= 3:
            recent = history[-3:]
            same_price = all(abs(h.get("price", 0) - price) < 0.01 for h in recent)
            consistent_vol = np.std([h.get("volume", 0) for h in recent]) < volume * 0.1 if volume > 0 else False
            if same_price and consistent_vol:
                iceberg_prob = 0.7
            elif same_price:
                iceberg_prob = 0.3

        # Flow direction
        if imbalance > 0.3:
            direction = FlowDirection.BUYING
        elif imbalance < -0.3:
            direction = FlowDirection.SELLING
        elif abs(imbalance) < 0.1:
            direction = FlowDirection.NEUTRAL
        else:
            direction = FlowDirection.MIXED

        # Unusual flow detection
        alerts = []
        unusual = False
        if abs(imbalance) > self.config.imbalance_alert_threshold:
            unusual = True
            side = "buy" if imbalance > 0 else "sell"
            alerts.append(f"High {side}-side imbalance: {imbalance:.2%}")
        if toxicity > self.config.flow_toxicity_threshold:
            unusual = True
            alerts.append(f"Elevated flow toxicity: {toxicity:.2%}")
        if absorption:
            unusual = True
            alerts.append("Absorption detected: large volume, minimal price movement")
        if iceberg_prob > 0.5:
            unusual = True
            alerts.append(f"Possible iceberg order (prob: {iceberg_prob:.0%})")

        # Store in history
        entry = {
            "timestamp": now.isoformat(),
            "price": price,
            "volume": volume,
            "bid": bid,
            "ask": ask,
            "imbalance": imbalance,
            "toxicity": toxicity,
            "net_flow": net_flow,
        }

        with self._lock:
            history.append(entry)
            if len(history) > self._max_history:
                history[:] = history[-self._max_history:]
            self._cumulative_delta[symbol] = cum_delta

        return OrderFlowSnapshot(
            symbol=symbol,
            timestamp=now,
            bid_volume=bid_vol,
            ask_volume=ask_vol,
            imbalance_ratio=imbalance,
            flow_toxicity=toxicity,
            absorption_detected=absorption,
            iceberg_probability=iceberg_prob,
            flow_direction=direction,
            net_flow=net_flow,
            cumulative_delta=cum_delta,
            unusual_flow=unusual,
            alerts=alerts,
        )

    def get_flow_history(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get recent flow history for a symbol."""
        with self._lock:
            history = self._flow_history.get(symbol, [])
            return history[-limit:]

    def reset(self, symbol: str = None):
        """Reset flow tracking."""
        with self._lock:
            if symbol:
                self._flow_history.pop(symbol, None)
                self._cumulative_delta.pop(symbol, None)
            else:
                self._flow_history.clear()
                self._cumulative_delta.clear()


# ============== MODULE 2: VOLATILITY REGIME CLASSIFIER ==============

class VolatilityRegimeClassifier:
    """
    Real-time volatility state classification using ATR, Bollinger Width,
    and VIX. Tracks regime transitions and adjusts position sizing.

    States: Compressed | Normal | Expanding | Crisis
    Key insight: Compression often precedes expansion.
    """

    def __init__(self, config: MicrostructureConfig):
        self.config = config
        self._lock = threading.Lock()
        self._regime_history: List[Dict] = []
        self._current_state: Optional[VolatilityState] = None
        self._state_start_bar: int = 0
        self._bar_count: int = 0

    def classify(
        self,
        prices: np.ndarray,
        highs: np.ndarray = None,
        lows: np.ndarray = None,
        vix: float = None,
    ) -> VolatilityRegimeState:
        """
        Classify the current volatility regime.

        Args:
            prices: Array of close prices (most recent last)
            highs: Array of high prices (optional, for ATR)
            lows: Array of low prices (optional, for ATR)
            vix: Current VIX level (optional)
        """
        now = datetime.now(timezone.utc)
        n = len(prices)

        if n < max(self.config.atr_lookback, self.config.bollinger_lookback) + 5:
            return VolatilityRegimeState(
                state=VolatilityState.NORMAL,
                confidence=0.3,
                timestamp=now,
                atr_current=0.0,
                atr_percentile=50.0,
                bollinger_width=0.0,
                bollinger_width_percentile=50.0,
                vix_level=vix or 0.0,
                vix_term_structure="unknown",
                regime_duration_bars=0,
                transition_probability=0.5,
                position_size_multiplier=1.0,
            )

        # Calculate ATR
        if highs is not None and lows is not None:
            tr = np.maximum(
                highs[1:] - lows[1:],
                np.maximum(
                    np.abs(highs[1:] - prices[:-1]),
                    np.abs(lows[1:] - prices[:-1])
                )
            )
            atr_series = self._ema(tr, self.config.atr_lookback)
            atr_current = atr_series[-1] if len(atr_series) > 0 else 0.0
        else:
            # Fallback: use returns-based volatility
            returns = np.diff(np.log(np.maximum(prices, 0.0001)))
            rolling_vol = self._rolling_std(returns, self.config.atr_lookback)
            atr_current = rolling_vol[-1] * prices[-1] if len(rolling_vol) > 0 else 0.0
            atr_series = rolling_vol * prices[self.config.atr_lookback:]

        # ATR percentile vs history
        if len(atr_series) > 10:
            atr_percentile = float(np.sum(atr_series < atr_current) / len(atr_series) * 100)
        else:
            atr_percentile = 50.0

        # Bollinger Band Width
        bb_lookback = self.config.bollinger_lookback
        if n >= bb_lookback:
            sma = np.mean(prices[-bb_lookback:])
            std = np.std(prices[-bb_lookback:])
            bb_width = (2 * std * 2) / sma if sma > 0 else 0.0  # Width as % of price

            # Historical BB widths
            bb_widths = []
            for i in range(bb_lookback, n):
                window = prices[i - bb_lookback:i]
                s = np.mean(window)
                d = np.std(window)
                if s > 0:
                    bb_widths.append((2 * d * 2) / s)
            if bb_widths:
                bb_percentile = float(np.sum(np.array(bb_widths) < bb_width) / len(bb_widths) * 100)
            else:
                bb_percentile = 50.0
        else:
            bb_width = 0.0
            bb_percentile = 50.0

        # VIX interpretation
        vix_level = vix or 20.0
        if vix_level < 12:
            vix_signal = "compressed"
        elif vix_level < 20:
            vix_signal = "normal"
        elif vix_level < 30:
            vix_signal = "elevated"
        else:
            vix_signal = "crisis"

        # Classify regime using combined metrics
        # Average the percentiles, weight VIX if available
        composite = atr_percentile * 0.4 + bb_percentile * 0.4
        if vix is not None:
            vix_percentile = min(100, max(0, (vix_level - 10) / 40 * 100))
            composite = atr_percentile * 0.3 + bb_percentile * 0.3 + vix_percentile * 0.4

        if composite < self.config.compression_percentile:
            state = VolatilityState.COMPRESSED
            confidence = 1.0 - composite / self.config.compression_percentile
            size_mult = 0.7  # Reduce size, breakout imminent
        elif composite < self.config.expansion_percentile:
            state = VolatilityState.NORMAL
            confidence = 0.8
            size_mult = 1.0
        elif composite < self.config.crisis_percentile:
            state = VolatilityState.EXPANDING
            confidence = (composite - self.config.expansion_percentile) / (
                self.config.crisis_percentile - self.config.expansion_percentile
            )
            size_mult = 0.6  # Reduce size in expanding vol
        else:
            state = VolatilityState.CRISIS
            confidence = min(1.0, (composite - self.config.crisis_percentile) / 5.0)
            size_mult = 0.3  # Heavily reduce in crisis

        # Track regime transitions
        self._bar_count += 1
        with self._lock:
            if self._current_state != state:
                # Regime change
                transition_prob = 0.8  # High if just changed
                if self._current_state is not None:
                    self._regime_history.append({
                        "from": self._current_state.value,
                        "to": state.value,
                        "bar": self._bar_count,
                        "timestamp": now.isoformat(),
                        "duration": self._bar_count - self._state_start_bar,
                    })
                    if len(self._regime_history) > 100:
                        self._regime_history = self._regime_history[-100:]
                self._current_state = state
                self._state_start_bar = self._bar_count
            else:
                # Same regime - decreasing transition probability over time
                duration = self._bar_count - self._state_start_bar
                transition_prob = max(0.05, 1.0 / (1 + duration * 0.1))

            regime_duration = self._bar_count - self._state_start_bar
            history_copy = list(self._regime_history[-20:])

        return VolatilityRegimeState(
            state=state,
            confidence=min(1.0, max(0.0, confidence)),
            timestamp=now,
            atr_current=float(atr_current),
            atr_percentile=atr_percentile,
            bollinger_width=float(bb_width),
            bollinger_width_percentile=bb_percentile,
            vix_level=vix_level,
            vix_term_structure=vix_signal,
            regime_duration_bars=regime_duration,
            transition_probability=transition_prob,
            position_size_multiplier=size_mult,
            history=history_copy,
        )

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average."""
        if len(data) == 0:
            return np.array([])
        alpha = 2.0 / (period + 1)
        result = np.zeros(len(data))
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    @staticmethod
    def _rolling_std(data: np.ndarray, window: int) -> np.ndarray:
        """Rolling standard deviation."""
        if len(data) < window:
            return np.array([np.std(data)] if len(data) > 0 else [])
        result = np.zeros(len(data) - window + 1)
        for i in range(len(result)):
            result[i] = np.std(data[i:i + window])
        return result


# ============== MODULE 3: LIQUIDITY MONITORING ==============

class LiquidityMonitor:
    """
    Tracks spread widening/tightening, monitors volume patterns,
    detects liquidity vacuums, and estimates realistic fill quality.
    """

    def __init__(self, config: MicrostructureConfig):
        self.config = config
        self._lock = threading.Lock()
        self._spread_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        self._prev_state: Dict[str, LiquidityState] = {}

    def analyze(
        self,
        symbol: str,
        bid: float,
        ask: float,
        price: float,
        volume: float,
        avg_volume: float = None,
    ) -> LiquiditySnapshot:
        """Analyze current liquidity conditions."""
        now = datetime.now(timezone.utc)

        spread = ask - bid if ask > bid else 0.0
        spread_bps = (spread / price * 10000) if price > 0 else 0.0

        with self._lock:
            spread_hist = self._spread_history.setdefault(symbol, [])
            vol_hist = self._volume_history.setdefault(symbol, [])

            spread_hist.append(spread_bps)
            if len(spread_hist) > self.config.spread_history_size:
                spread_hist[:] = spread_hist[-self.config.spread_history_size:]

            vol_hist.append(volume)
            if len(vol_hist) > self.config.spread_history_size:
                vol_hist[:] = vol_hist[-self.config.spread_history_size:]

            spread_arr = np.array(spread_hist)
            vol_arr = np.array(vol_hist)
            prev_state = self._prev_state.get(symbol)

        # Spread percentile
        if len(spread_arr) > 5:
            spread_percentile = float(np.sum(spread_arr < spread_bps) / len(spread_arr) * 100)
        else:
            spread_percentile = 50.0

        # Relative volume
        if avg_volume and avg_volume > 0:
            relative_volume = volume / avg_volume
        elif len(vol_arr) > 5:
            relative_volume = volume / np.mean(vol_arr) if np.mean(vol_arr) > 0 else 1.0
        else:
            relative_volume = 1.0

        # Depth score (derived from spread and volume)
        # Tighter spread + higher volume = deeper liquidity
        spread_score = max(0, 1.0 - spread_percentile / 100.0)
        volume_score = min(1.0, relative_volume)
        depth_score = spread_score * 0.6 + volume_score * 0.4

        # Classify liquidity state
        if spread_percentile >= self.config.vacuum_liquidity_percentile and relative_volume < 0.3:
            state = LiquidityState.VACUUM
        elif spread_percentile >= self.config.thin_liquidity_percentile or relative_volume < 0.5:
            state = LiquidityState.THIN
        elif spread_percentile <= 30 and relative_volume >= 1.0:
            state = LiquidityState.DEEP
        else:
            state = LiquidityState.NORMAL

        # Estimated fill quality (expected slippage in bps)
        base_slippage = spread_bps / 2.0  # Half-spread as baseline
        if state == LiquidityState.VACUUM:
            fill_quality = base_slippage * 3.0
        elif state == LiquidityState.THIN:
            fill_quality = base_slippage * 1.5
        elif state == LiquidityState.DEEP:
            fill_quality = base_slippage * 0.7
        else:
            fill_quality = base_slippage

        # Deterioration detection
        deteriorating = False
        alerts = []
        if len(spread_arr) >= 5:
            recent_avg = float(np.mean(spread_arr[-5:]))
            older_avg = float(np.mean(spread_arr[-20:-5])) if len(spread_arr) >= 20 else float(np.mean(spread_arr[:-5]))
            if recent_avg > older_avg * 1.5:
                deteriorating = True
                alerts.append(f"Spread widening: {recent_avg:.1f}bps vs {older_avg:.1f}bps avg")

        if state == LiquidityState.VACUUM:
            alerts.append("LIQUIDITY VACUUM: Extremely wide spreads, minimal volume")
        elif state == LiquidityState.THIN:
            alerts.append("Thin liquidity: Wide spreads or low volume")

        if prev_state and prev_state != state:
            if state.value in ("THIN", "VACUUM"):
                alerts.append(f"Liquidity deteriorated: {prev_state.value} -> {state.value}")

        with self._lock:
            self._prev_state[symbol] = state

        return LiquiditySnapshot(
            symbol=symbol,
            timestamp=now,
            state=state,
            spread_bps=spread_bps,
            spread_percentile=spread_percentile,
            relative_volume=float(relative_volume),
            depth_score=depth_score,
            fill_quality_estimate=fill_quality,
            deteriorating=deteriorating,
            alerts=alerts,
        )


# ============== MODULE 4: SIGNAL CONFIDENCE DECAY ==============

class SignalConfidenceManager:
    """
    Manages signal confidence with time-based decay and multi-factor adjustment.
    Every signal starts with initial confidence that decays over time.
    Stale signals are weak signals.
    """

    def __init__(self, config: MicrostructureConfig):
        self.config = config
        self._lock = threading.Lock()
        self._signals: Dict[str, Dict] = {}  # signal_id -> signal data
        self._signal_counter = 0

    def register_signal(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        regime_modifier: float = 1.0,
        performance_modifier: float = 1.0,
        correlation_modifier: float = 1.0,
    ) -> SignalConfidenceState:
        """Register a new signal with initial confidence."""
        now = datetime.now(timezone.utc)
        self._signal_counter += 1
        signal_id = f"SIG-{self._signal_counter:06d}"

        initial = min(1.0, max(0.0, confidence))

        signal_data = {
            "signal_id": signal_id,
            "symbol": symbol,
            "direction": direction,
            "initial_confidence": initial,
            "created_at": now,
            "regime_modifier": regime_modifier,
            "performance_modifier": performance_modifier,
            "correlation_modifier": correlation_modifier,
        }

        with self._lock:
            self._signals[signal_id] = signal_data

        return self._compute_state(signal_data)

    def get_signal(self, signal_id: str) -> Optional[SignalConfidenceState]:
        """Get current state of a signal with updated confidence."""
        with self._lock:
            data = self._signals.get(signal_id)
        if data is None:
            return None
        return self._compute_state(data)

    def get_active_signals(self) -> List[SignalConfidenceState]:
        """Get all active (non-expired) signals."""
        results = []
        expired = []
        with self._lock:
            signal_items = list(self._signals.items())

        for signal_id, data in signal_items:
            state = self._compute_state(data)
            if state.current_confidence <= 0 or state.time_alive_seconds > self.config.max_signal_age_minutes * 60:
                expired.append(signal_id)
            else:
                results.append(state)

        # Clean up expired
        if expired:
            with self._lock:
                for sid in expired:
                    self._signals.pop(sid, None)

        return sorted(results, key=lambda s: s.current_confidence, reverse=True)

    def update_modifiers(
        self,
        signal_id: str,
        regime_modifier: float = None,
        performance_modifier: float = None,
        correlation_modifier: float = None,
    ) -> Optional[SignalConfidenceState]:
        """Update confidence modifiers for a signal."""
        with self._lock:
            data = self._signals.get(signal_id)
            if data is None:
                return None
            if regime_modifier is not None:
                data["regime_modifier"] = regime_modifier
            if performance_modifier is not None:
                data["performance_modifier"] = performance_modifier
            if correlation_modifier is not None:
                data["correlation_modifier"] = correlation_modifier
        return self._compute_state(data)

    def _compute_state(self, data: Dict) -> SignalConfidenceState:
        """Compute current confidence with decay and modifiers."""
        now = datetime.now(timezone.utc)
        age_seconds = (now - data["created_at"]).total_seconds()
        age_minutes = age_seconds / 60.0

        # Exponential decay
        decay = math.exp(-self.config.base_decay_rate * age_minutes)
        base_decayed = data["initial_confidence"] * decay

        # Apply modifiers
        regime_mod = data.get("regime_modifier", 1.0)
        perf_mod = data.get("performance_modifier", 1.0)
        corr_mod = data.get("correlation_modifier", 1.0)

        combined_modifier = (regime_mod * 0.4 + perf_mod * 0.3 + corr_mod * 0.3)
        current = base_decayed * combined_modifier
        current = min(1.0, max(0.0, current))

        is_actionable = current >= self.config.min_actionable_confidence

        return SignalConfidenceState(
            signal_id=data["signal_id"],
            symbol=data["symbol"],
            direction=data["direction"],
            initial_confidence=data["initial_confidence"],
            current_confidence=current,
            created_at=data["created_at"],
            last_updated=now,
            decay_rate=self.config.base_decay_rate,
            regime_modifier=regime_mod,
            performance_modifier=perf_mod,
            correlation_modifier=corr_mod,
            is_actionable=is_actionable,
            time_alive_seconds=age_seconds,
            factors={
                "decay": decay,
                "regime": regime_mod,
                "performance": perf_mod,
                "correlation": corr_mod,
                "combined_modifier": combined_modifier,
            },
        )

    def clear(self):
        """Clear all signals."""
        with self._lock:
            self._signals.clear()


# ============== MODULE 5: ADAPTIVE POSITION SIZING ==============

class AdaptivePositionSizer:
    """
    Position sizing using Kelly criterion with fractional scaling,
    adjusted for volatility regime, signal confidence, correlation
    exposure, and recent drawdown.
    """

    def __init__(self, config: MicrostructureConfig):
        self.config = config

    def calculate(
        self,
        symbol: str,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        signal_confidence: float = 1.0,
        volatility_multiplier: float = 1.0,
        correlation_penalty: float = 0.0,
        current_drawdown: float = 0.0,
        portfolio_value: float = 100000.0,
    ) -> PositionSizeResult:
        """
        Calculate adaptive position size.

        Args:
            symbol: Symbol to size
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade size
            avg_loss: Average losing trade size (positive number)
            signal_confidence: Current signal confidence (0-1)
            volatility_multiplier: From volatility regime (0-1.2)
            correlation_penalty: Correlation-based reduction (0-1)
            current_drawdown: Current drawdown as fraction (0-1)
            portfolio_value: Total portfolio value
        """
        reasoning = []

        # Kelly criterion: f* = (b*p - q) / b
        # where b = avg_win/avg_loss, p = win_rate, q = 1-p
        if avg_loss > 0 and win_rate > 0:
            b = avg_win / avg_loss
            p = win_rate
            q = 1.0 - p
            kelly = (b * p - q) / b
            kelly = max(0.0, kelly)
            reasoning.append(f"Kelly criterion: {kelly:.4f} (b={b:.2f}, p={p:.2f})")
        else:
            kelly = 0.0
            reasoning.append("Insufficient data for Kelly: using 0")

        # Apply fractional Kelly
        base_size = kelly * self.config.kelly_fraction
        reasoning.append(f"Fractional Kelly ({self.config.kelly_fraction}x): {base_size:.4f}")

        # Adjustments
        adjustments = {}

        # 1. Signal confidence adjustment
        conf_adj = signal_confidence
        adjustments["signal_confidence"] = conf_adj
        reasoning.append(f"Signal confidence: {conf_adj:.2f}")

        # 2. Volatility regime adjustment
        vol_adj = volatility_multiplier
        adjustments["volatility_regime"] = vol_adj
        reasoning.append(f"Volatility multiplier: {vol_adj:.2f}")

        # 3. Correlation penalty
        corr_adj = max(0.0, 1.0 - correlation_penalty)
        adjustments["correlation"] = corr_adj
        reasoning.append(f"Correlation adjustment: {corr_adj:.2f} (penalty: {correlation_penalty:.2f})")

        # 4. Drawdown adjustment
        if current_drawdown > self.config.drawdown_reduction_threshold:
            dd_excess = current_drawdown - self.config.drawdown_reduction_threshold
            dd_max_excess = 0.20 - self.config.drawdown_reduction_threshold  # Max at 20% DD
            dd_factor = dd_excess / max(dd_max_excess, 0.01)
            dd_adj = max(
                self.config.drawdown_max_reduction,
                1.0 - dd_factor * (1.0 - self.config.drawdown_max_reduction)
            )
            adjustments["drawdown"] = dd_adj
            reasoning.append(f"Drawdown reduction: {dd_adj:.2f} (DD: {current_drawdown:.2%})")
        else:
            dd_adj = 1.0
            adjustments["drawdown"] = dd_adj

        # Combined adjustment
        total_adj = conf_adj * vol_adj * corr_adj * dd_adj
        adjusted_size = base_size * total_adj
        reasoning.append(f"Total adjustment: {total_adj:.4f}")
        reasoning.append(f"Adjusted size: {adjusted_size:.4f}")

        # Hard cap
        max_size = self.config.max_position_pct
        final_size = min(adjusted_size, max_size)
        if final_size < adjusted_size:
            reasoning.append(f"Capped at max position: {max_size:.2%}")

        # Convert to dollar amount
        dollar_size = final_size * portfolio_value
        reasoning.append(f"Dollar size: ${dollar_size:,.2f} of ${portfolio_value:,.2f}")

        return PositionSizeResult(
            symbol=symbol,
            base_size=base_size,
            adjusted_size=adjusted_size,
            max_size=max_size,
            final_size=final_size,
            adjustments=adjustments,
            reasoning=reasoning,
        )


# ============== MODULE 6: MARKET HOURS AWARENESS ==============

class MarketHoursAnalyzer:
    """
    Session-aware trading behavior. Different behavior for each market
    session with time-of-day performance attribution.
    """

    # Session definitions (ET)
    SESSION_TIMES = {
        MarketSession.PRE_MARKET: (4, 0, 9, 29),
        MarketSession.OPEN_AUCTION: (9, 30, 9, 34),
        MarketSession.MORNING: (9, 35, 11, 59),
        MarketSession.MIDDAY: (12, 0, 13, 59),
        MarketSession.AFTERNOON: (14, 0, 15, 44),
        MarketSession.CLOSE_AUCTION: (15, 45, 15, 59),
        MarketSession.AFTER_HOURS: (16, 0, 19, 59),
    }

    # Default session profiles
    DEFAULT_PROFILES = {
        MarketSession.PRE_MARKET: {
            "avg_volatility": 0.4, "avg_volume_ratio": 0.1, "avg_spread_bps": 15.0,
            "win_rate": 0.45, "avg_pnl": -5.0, "recommended_action": "avoid",
        },
        MarketSession.OPEN_AUCTION: {
            "avg_volatility": 1.8, "avg_volume_ratio": 2.5, "avg_spread_bps": 3.0,
            "win_rate": 0.48, "avg_pnl": 0.0, "recommended_action": "reduce_size",
        },
        MarketSession.MORNING: {
            "avg_volatility": 1.2, "avg_volume_ratio": 1.3, "avg_spread_bps": 2.0,
            "win_rate": 0.55, "avg_pnl": 15.0, "recommended_action": "trade_normal",
        },
        MarketSession.MIDDAY: {
            "avg_volatility": 0.6, "avg_volume_ratio": 0.7, "avg_spread_bps": 3.5,
            "win_rate": 0.50, "avg_pnl": 2.0, "recommended_action": "reduce_size",
        },
        MarketSession.AFTERNOON: {
            "avg_volatility": 1.0, "avg_volume_ratio": 1.1, "avg_spread_bps": 2.5,
            "win_rate": 0.53, "avg_pnl": 10.0, "recommended_action": "trade_normal",
        },
        MarketSession.CLOSE_AUCTION: {
            "avg_volatility": 1.5, "avg_volume_ratio": 2.0, "avg_spread_bps": 2.0,
            "win_rate": 0.52, "avg_pnl": 5.0, "recommended_action": "reduce_size",
        },
        MarketSession.AFTER_HOURS: {
            "avg_volatility": 0.5, "avg_volume_ratio": 0.05, "avg_spread_bps": 20.0,
            "win_rate": 0.42, "avg_pnl": -10.0, "recommended_action": "avoid",
        },
        MarketSession.CLOSED: {
            "avg_volatility": 0.0, "avg_volume_ratio": 0.0, "avg_spread_bps": 0.0,
            "win_rate": 0.0, "avg_pnl": 0.0, "recommended_action": "avoid",
        },
    }

    def __init__(self, config: MicrostructureConfig):
        self.config = config
        self._lock = threading.Lock()
        # Performance attribution by session
        self._session_trades: Dict[str, List[Dict]] = {s.value: [] for s in MarketSession}

    def get_current_session(self, now: datetime = None) -> MarketSession:
        """Determine current market session."""
        if now is None:
            now = datetime.now()

        # Convert to ET (approximate: UTC-5 for EST)
        # In production, use pytz or zoneinfo
        hour = now.hour
        minute = now.minute
        time_val = hour * 60 + minute

        # Weekend check
        if now.weekday() >= 5:
            return MarketSession.CLOSED

        for session, (sh, sm, eh, em) in self.SESSION_TIMES.items():
            start = sh * 60 + sm
            end = eh * 60 + em
            if start <= time_val <= end:
                return session

        return MarketSession.CLOSED

    def get_session_profile(self, session: MarketSession = None) -> SessionProfile:
        """Get behavior profile for a session."""
        if session is None:
            session = self.get_current_session()

        defaults = self.DEFAULT_PROFILES.get(session, self.DEFAULT_PROFILES[MarketSession.CLOSED])

        # Check if we have actual performance data
        with self._lock:
            trades = self._session_trades.get(session.value, [])

        if len(trades) >= 10:
            wins = [t for t in trades if t.get("pnl", 0) > 0]
            win_rate = len(wins) / len(trades)
            avg_pnl = np.mean([t.get("pnl", 0) for t in trades])
            trade_count = len(trades)
        else:
            win_rate = defaults["win_rate"]
            avg_pnl = defaults["avg_pnl"]
            trade_count = len(trades)

        return SessionProfile(
            session=session,
            avg_volatility=defaults["avg_volatility"],
            avg_volume_ratio=defaults["avg_volume_ratio"],
            avg_spread_bps=defaults["avg_spread_bps"],
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            trade_count=trade_count,
            recommended_action=defaults["recommended_action"],
        )

    def get_all_profiles(self) -> List[SessionProfile]:
        """Get profiles for all sessions."""
        return [self.get_session_profile(s) for s in MarketSession]

    def should_trade(self, now: datetime = None) -> Tuple[bool, str, float]:
        """
        Determine if current conditions favor trading.

        Returns:
            (should_trade, reason, size_multiplier)
        """
        session = self.get_current_session(now)
        profile = self.get_session_profile(session)

        if profile.recommended_action == "avoid":
            return False, f"Avoid trading during {session.value}", 0.0

        if profile.recommended_action == "reduce_size":
            return True, f"{session.value}: Reduced position sizing", self.config.low_liquidity_reduction

        if profile.recommended_action == "aggressive":
            return True, f"{session.value}: Favorable conditions", 1.2

        return True, f"{session.value}: Normal trading", 1.0

    def record_trade(self, session: MarketSession, pnl: float, symbol: str = ""):
        """Record a trade for session performance attribution."""
        with self._lock:
            trades = self._session_trades.setdefault(session.value, [])
            trades.append({
                "pnl": pnl,
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Keep last 200 trades per session
            if len(trades) > 200:
                trades[:] = trades[-200:]


# ============== MODULE 7: CROSS-ASSET SIGNAL VALIDATION ==============

class CrossAssetValidator:
    """
    Validates signals by checking if related assets confirm the direction.
    Detects divergences and calculates multi-asset confirmation scores.
    """

    # Sector ETF mappings
    SECTOR_ETFS = {
        "XLK": ["AAPL", "MSFT", "NVDA", "GOOG", "META", "AVGO", "ADBE", "CRM", "AMD", "INTC"],
        "XLF": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "USB"],
        "XLV": ["UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY"],
        "XLE": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL"],
        "XLY": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "CMG"],
        "XLP": ["PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "MDLZ", "KHC"],
        "XLI": ["CAT", "BA", "HON", "UPS", "RTX", "DE", "GE", "LMT", "MMM", "UNP"],
        "XLB": ["LIN", "APD", "SHW", "ECL", "FCX", "NEM", "DOW", "NUE", "VMC", "MLM"],
        "XLU": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC"],
        "XLRE": ["PLD", "AMT", "CCI", "EQIX", "PSA", "SPG", "O", "WELL", "DLR", "AVB"],
    }

    # Index ETF relationships
    INDEX_CORRELATION = {
        "SPY": ["QQQ", "DIA", "IWM"],
        "QQQ": ["SPY", "XLK", "ARKK"],
        "DIA": ["SPY", "XLI", "XLF"],
        "IWM": ["SPY", "XLF", "XLI"],
    }

    def __init__(self, config: MicrostructureConfig):
        self.config = config

    def validate(
        self,
        symbol: str,
        signal_direction: str,  # "BUY" or "SELL"
        asset_returns: Dict[str, float] = None,
        sector_return: float = None,
        options_flow_bullish: float = None,
    ) -> CrossAssetValidation:
        """
        Validate a signal against related assets.

        Args:
            symbol: Target symbol
            signal_direction: "BUY" or "SELL"
            asset_returns: Dict of symbol -> recent return for related assets
            sector_return: Sector ETF recent return (if known)
            options_flow_bullish: Fraction of bullish options flow (0-1)
        """
        asset_returns = asset_returns or {}
        confirming = []
        diverging = []

        is_bullish = signal_direction.upper() == "BUY"

        # 1. Sector alignment
        sector_etf = self._find_sector(symbol)
        if sector_return is not None:
            sector_aligned = (sector_return > 0) == is_bullish
            sector_score = min(1.0, abs(sector_return) * 100) * (1.0 if sector_aligned else -1.0)
            if sector_aligned:
                confirming.append({
                    "asset": sector_etf or "SECTOR",
                    "return": round(sector_return, 4),
                    "relationship": "sector",
                })
            else:
                diverging.append({
                    "asset": sector_etf or "SECTOR",
                    "return": round(sector_return, 4),
                    "relationship": "sector",
                    "warning": f"Signal {signal_direction} but sector {'down' if is_bullish else 'up'}",
                })
        else:
            sector_score = 0.0

        # 2. Correlated asset check
        correlation_scores = []
        for asset, ret in asset_returns.items():
            if asset == symbol:
                continue
            aligned = (ret > 0) == is_bullish
            score = min(1.0, abs(ret) * 50) * (1.0 if aligned else -1.0)
            correlation_scores.append(score)
            entry = {
                "asset": asset,
                "return": round(ret, 4),
                "relationship": "correlated",
            }
            if aligned:
                confirming.append(entry)
            else:
                entry["warning"] = f"Divergence: {asset} {'down' if is_bullish else 'up'}"
                diverging.append(entry)

        if correlation_scores:
            correlation_score = float(np.mean(correlation_scores))
        else:
            correlation_score = 0.0

        # 3. Options flow alignment
        if options_flow_bullish is not None:
            if is_bullish:
                options_score = options_flow_bullish * 2 - 1  # Map 0-1 to -1..1
            else:
                options_score = (1 - options_flow_bullish) * 2 - 1
            if (options_flow_bullish > 0.6 and is_bullish) or (options_flow_bullish < 0.4 and not is_bullish):
                confirming.append({
                    "asset": "OPTIONS_FLOW",
                    "return": round(options_flow_bullish, 4),
                    "relationship": "options",
                })
            elif (options_flow_bullish < 0.4 and is_bullish) or (options_flow_bullish > 0.6 and not is_bullish):
                diverging.append({
                    "asset": "OPTIONS_FLOW",
                    "return": round(options_flow_bullish, 4),
                    "relationship": "options",
                    "warning": "Options flow contradicts signal direction",
                })
        else:
            options_score = 0.0

        # Weighted confirmation score
        total_score = (
            sector_score * self.config.sector_weight
            + correlation_score * self.config.correlation_weight
            + options_score * self.config.options_weight
        )
        total_score = max(-1.0, min(1.0, total_score))

        is_confirmed = total_score >= self.config.min_confirmation_score

        return CrossAssetValidation(
            symbol=symbol,
            signal_direction=signal_direction,
            confirmation_score=total_score,
            confirming_assets=confirming,
            diverging_assets=diverging,
            sector_alignment=sector_score,
            correlation_check=correlation_score,
            options_flow_alignment=options_score,
            is_confirmed=is_confirmed,
        )

    def _find_sector(self, symbol: str) -> Optional[str]:
        """Find which sector ETF a symbol belongs to."""
        for etf, members in self.SECTOR_ETFS.items():
            if symbol.upper() in members:
                return etf
        return None

    def get_related_assets(self, symbol: str) -> Dict[str, List[str]]:
        """Get related assets for cross-validation."""
        result = {"sector_etf": None, "sector_peers": [], "index_etfs": [], "correlated": []}

        sector = self._find_sector(symbol)
        if sector:
            result["sector_etf"] = sector
            result["sector_peers"] = [s for s in self.SECTOR_ETFS[sector] if s != symbol.upper()][:5]

        for idx, corr in self.INDEX_CORRELATION.items():
            if symbol.upper() == idx or symbol.upper() in corr:
                result["index_etfs"].append(idx)
                result["correlated"].extend([c for c in corr if c != symbol.upper()])

        # Always include major indices for context
        if not result["index_etfs"]:
            result["index_etfs"] = ["SPY", "QQQ"]

        return result


# ============== UNIFIED ENGINE ==============

class MarketMicrostructureEngine:
    """
    Unified engine that orchestrates all 7 intelligence modules.
    Each module is independently toggleable and tracks its own performance.
    """

    def __init__(self, config: MicrostructureConfig = None):
        self.config = config or MicrostructureConfig()
        self._lock = threading.Lock()

        # Initialize modules
        self.order_flow = OrderFlowAnalyzer(self.config)
        self.volatility_regime = VolatilityRegimeClassifier(self.config)
        self.liquidity = LiquidityMonitor(self.config)
        self.signal_confidence = SignalConfidenceManager(self.config)
        self.position_sizer = AdaptivePositionSizer(self.config)
        self.market_hours = MarketHoursAnalyzer(self.config)
        self.cross_asset = CrossAssetValidator(self.config)

        # Module performance tracking
        self._module_stats: Dict[str, Dict] = {
            "order_flow": {"calls": 0, "alerts": 0, "value_added": 0.0},
            "volatility_regime": {"calls": 0, "regime_changes": 0, "value_added": 0.0},
            "liquidity": {"calls": 0, "warnings": 0, "value_added": 0.0},
            "signal_decay": {"signals_registered": 0, "signals_expired": 0, "value_added": 0.0},
            "adaptive_sizing": {"calls": 0, "avg_adjustment": 0.0, "value_added": 0.0},
            "market_hours": {"calls": 0, "trades_avoided": 0, "value_added": 0.0},
            "cross_asset": {"calls": 0, "confirmations": 0, "divergences": 0, "value_added": 0.0},
        }

        logger.info("MarketMicrostructureEngine initialized with config: %s",
                     {k: v for k, v in self.config.to_dict()["modules"].items()})

    def analyze_symbol(
        self,
        symbol: str,
        price: float,
        bid: float,
        ask: float,
        volume: float,
        prices: np.ndarray = None,
        highs: np.ndarray = None,
        lows: np.ndarray = None,
        vix: float = None,
        prev_price: float = None,
        prev_volume: float = None,
        avg_volume: float = None,
        signal_direction: str = None,
        signal_confidence_val: float = None,
        asset_returns: Dict[str, float] = None,
        sector_return: float = None,
        options_flow_bullish: float = None,
        win_rate: float = 0.55,
        avg_win: float = 100.0,
        avg_loss: float = 80.0,
        current_drawdown: float = 0.0,
        portfolio_value: float = 100000.0,
        correlation_penalty: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Run all enabled modules for a symbol and return comprehensive analysis.

        Returns dict with results from each enabled module.
        """
        result = {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modules": {},
            "alerts": [],
            "composite_score": 0.0,
            "recommendation": "HOLD",
        }

        scores = []

        # Module 1: Order Flow
        if self.config.order_flow_enabled:
            try:
                flow = self.order_flow.analyze(
                    symbol, bid, ask, price, volume,
                    prev_price=prev_price, prev_volume=prev_volume,
                    prev_bid=None, prev_ask=None,
                )
                result["modules"]["order_flow"] = flow.to_dict()
                result["alerts"].extend(flow.alerts)
                with self._lock:
                    self._module_stats["order_flow"]["calls"] += 1
                    self._module_stats["order_flow"]["alerts"] += len(flow.alerts)

                # Flow score: positive imbalance = buying, negative = selling
                flow_score = flow.imbalance_ratio * (1 - flow.flow_toxicity)
                scores.append(("order_flow", flow_score))
            except Exception as e:
                logger.error("Order flow analysis failed: %s", e)
                result["modules"]["order_flow"] = {"error": str(e)}

        # Module 2: Volatility Regime
        vol_multiplier = 1.0
        if self.config.volatility_regime_enabled and prices is not None and len(prices) > 20:
            try:
                vol_state = self.volatility_regime.classify(prices, highs, lows, vix)
                result["modules"]["volatility_regime"] = vol_state.to_dict()
                vol_multiplier = vol_state.position_size_multiplier
                with self._lock:
                    self._module_stats["volatility_regime"]["calls"] += 1

                # Vol score: normal is neutral, compressed/crisis are negative
                vol_scores = {
                    VolatilityState.COMPRESSED: -0.3,
                    VolatilityState.NORMAL: 0.0,
                    VolatilityState.EXPANDING: -0.5,
                    VolatilityState.CRISIS: -0.8,
                }
                scores.append(("volatility_regime", vol_scores.get(vol_state.state, 0.0)))
            except Exception as e:
                logger.error("Volatility regime classification failed: %s", e)
                result["modules"]["volatility_regime"] = {"error": str(e)}

        # Module 3: Liquidity
        if self.config.liquidity_monitor_enabled:
            try:
                liq = self.liquidity.analyze(symbol, bid, ask, price, volume, avg_volume)
                result["modules"]["liquidity"] = liq.to_dict()
                result["alerts"].extend(liq.alerts)
                with self._lock:
                    self._module_stats["liquidity"]["calls"] += 1
                    self._module_stats["liquidity"]["warnings"] += len(liq.alerts)

                liq_scores = {
                    LiquidityState.DEEP: 0.3,
                    LiquidityState.NORMAL: 0.0,
                    LiquidityState.THIN: -0.4,
                    LiquidityState.VACUUM: -0.8,
                }
                scores.append(("liquidity", liq_scores.get(liq.state, 0.0)))
            except Exception as e:
                logger.error("Liquidity analysis failed: %s", e)
                result["modules"]["liquidity"] = {"error": str(e)}

        # Module 4: Signal Confidence Decay
        if self.config.signal_decay_enabled and signal_direction and signal_confidence_val:
            try:
                regime_mod = vol_multiplier
                sig = self.signal_confidence.register_signal(
                    symbol, signal_direction, signal_confidence_val,
                    regime_modifier=regime_mod,
                )
                result["modules"]["signal_decay"] = sig.to_dict()
                with self._lock:
                    self._module_stats["signal_decay"]["signals_registered"] += 1
                scores.append(("signal_confidence", sig.current_confidence - 0.5))
            except Exception as e:
                logger.error("Signal confidence failed: %s", e)
                result["modules"]["signal_decay"] = {"error": str(e)}

        # Module 5: Adaptive Position Sizing
        if self.config.adaptive_sizing_enabled and signal_direction:
            try:
                size = self.position_sizer.calculate(
                    symbol, win_rate, avg_win, avg_loss,
                    signal_confidence=signal_confidence_val or 0.5,
                    volatility_multiplier=vol_multiplier,
                    correlation_penalty=correlation_penalty,
                    current_drawdown=current_drawdown,
                    portfolio_value=portfolio_value,
                )
                result["modules"]["position_sizing"] = size.to_dict()
                with self._lock:
                    self._module_stats["adaptive_sizing"]["calls"] += 1
            except Exception as e:
                logger.error("Position sizing failed: %s", e)
                result["modules"]["position_sizing"] = {"error": str(e)}

        # Module 6: Market Hours
        if self.config.market_hours_enabled:
            try:
                should_trade, reason, hours_mult = self.market_hours.should_trade()
                session = self.market_hours.get_current_session()
                profile = self.market_hours.get_session_profile(session)
                result["modules"]["market_hours"] = {
                    "session": session.value,
                    "should_trade": should_trade,
                    "reason": reason,
                    "size_multiplier": hours_mult,
                    "profile": profile.to_dict(),
                }
                with self._lock:
                    self._module_stats["market_hours"]["calls"] += 1
                    if not should_trade:
                        self._module_stats["market_hours"]["trades_avoided"] += 1

                if not should_trade:
                    result["alerts"].append(f"Market hours: {reason}")
                    scores.append(("market_hours", -0.5))
                else:
                    scores.append(("market_hours", (hours_mult - 1.0) * 0.5))
            except Exception as e:
                logger.error("Market hours analysis failed: %s", e)
                result["modules"]["market_hours"] = {"error": str(e)}

        # Module 7: Cross-Asset Validation
        if self.config.cross_asset_enabled and signal_direction:
            try:
                validation = self.cross_asset.validate(
                    symbol, signal_direction,
                    asset_returns=asset_returns,
                    sector_return=sector_return,
                    options_flow_bullish=options_flow_bullish,
                )
                result["modules"]["cross_asset"] = validation.to_dict()
                with self._lock:
                    self._module_stats["cross_asset"]["calls"] += 1
                    if validation.is_confirmed:
                        self._module_stats["cross_asset"]["confirmations"] += 1
                    if validation.diverging_assets:
                        self._module_stats["cross_asset"]["divergences"] += 1

                scores.append(("cross_asset", validation.confirmation_score))
                if validation.diverging_assets:
                    for d in validation.diverging_assets:
                        if "warning" in d:
                            result["alerts"].append(d["warning"])
            except Exception as e:
                logger.error("Cross-asset validation failed: %s", e)
                result["modules"]["cross_asset"] = {"error": str(e)}

        # Composite score
        if scores:
            composite = sum(s for _, s in scores) / len(scores)
            result["composite_score"] = round(composite, 4)

            if composite > 0.3:
                result["recommendation"] = "FAVORABLE"
            elif composite > 0.1:
                result["recommendation"] = "NEUTRAL_POSITIVE"
            elif composite > -0.1:
                result["recommendation"] = "NEUTRAL"
            elif composite > -0.3:
                result["recommendation"] = "NEUTRAL_NEGATIVE"
            else:
                result["recommendation"] = "UNFAVORABLE"

            result["score_breakdown"] = {name: round(score, 4) for name, score in scores}

        return result

    def get_status(self) -> Dict:
        """Get engine status and module statistics."""
        with self._lock:
            stats = {k: dict(v) for k, v in self._module_stats.items()}

        return {
            "engine": "MarketMicrostructureEngine",
            "version": "1.0.0",
            "config": self.config.to_dict(),
            "module_stats": stats,
            "active_signals": len(self.signal_confidence.get_active_signals()),
            "current_session": self.market_hours.get_current_session().value,
        }

    def get_config(self) -> Dict:
        """Get current configuration."""
        return self.config.to_dict()

    def update_config(self, updates: Dict) -> Dict:
        """Update configuration dynamically."""
        modules = updates.get("modules", {})
        for key, enabled in modules.items():
            attr = f"{key}_enabled"
            if hasattr(self.config, attr):
                setattr(self.config, attr, bool(enabled))

        # Update individual module params
        for section, params in updates.items():
            if section == "modules":
                continue
            if isinstance(params, dict):
                for key, value in params.items():
                    # Map section.key to config attribute
                    config_map = {
                        ("order_flow", "toxicity_threshold"): "flow_toxicity_threshold",
                        ("order_flow", "imbalance_alert_threshold"): "imbalance_alert_threshold",
                        ("volatility_regime", "atr_lookback"): "atr_lookback",
                        ("volatility_regime", "bollinger_lookback"): "bollinger_lookback",
                        ("signal_decay", "base_decay_rate"): "base_decay_rate",
                        ("signal_decay", "min_actionable_confidence"): "min_actionable_confidence",
                        ("position_sizing", "kelly_fraction"): "kelly_fraction",
                        ("position_sizing", "max_position_pct"): "max_position_pct",
                        ("cross_asset", "min_confirmation_score"): "min_confirmation_score",
                    }
                    attr = config_map.get((section, key))
                    if attr and hasattr(self.config, attr):
                        setattr(self.config, attr, type(getattr(self.config, attr))(value))

        logger.info("MicrostructureEngine config updated")
        return self.config.to_dict()

    def get_session_profiles(self) -> List[Dict]:
        """Get all market session profiles."""
        return [p.to_dict() for p in self.market_hours.get_all_profiles()]

    def get_active_signals(self) -> List[Dict]:
        """Get all active signals with current confidence."""
        return [s.to_dict() for s in self.signal_confidence.get_active_signals()]

    def get_flow_history(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get order flow history for a symbol."""
        return self.order_flow.get_flow_history(symbol, limit)

    def get_related_assets(self, symbol: str) -> Dict:
        """Get related assets for cross-validation."""
        return self.cross_asset.get_related_assets(symbol)


# ============== SINGLETON ==============

_engine_instance: Optional[MarketMicrostructureEngine] = None
_engine_lock = threading.Lock()


def get_microstructure_engine(config: MicrostructureConfig = None) -> MarketMicrostructureEngine:
    """Get or create the singleton MarketMicrostructureEngine."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = MarketMicrostructureEngine(config)
            logger.info("MarketMicrostructureEngine singleton created")
        return _engine_instance
