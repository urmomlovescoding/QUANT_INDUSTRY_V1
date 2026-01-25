"""
QUANT INDUSTRY - Neural Analysis Engine
Pattern recognition and AI-powered market analysis
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class PatternType(Enum):
    # Candlestick patterns
    DOJI = "DOJI"
    HAMMER = "HAMMER"
    INVERTED_HAMMER = "INVERTED_HAMMER"
    ENGULFING_BULLISH = "ENGULFING_BULLISH"
    ENGULFING_BEARISH = "ENGULFING_BEARISH"
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"
    THREE_WHITE_SOLDIERS = "THREE_WHITE_SOLDIERS"
    THREE_BLACK_CROWS = "THREE_BLACK_CROWS"
    PIERCING_LINE = "PIERCING_LINE"
    DARK_CLOUD_COVER = "DARK_CLOUD_COVER"
    HARAMI_BULLISH = "HARAMI_BULLISH"
    HARAMI_BEARISH = "HARAMI_BEARISH"

    # Chart patterns
    HEAD_AND_SHOULDERS = "HEAD_AND_SHOULDERS"
    INVERSE_HEAD_AND_SHOULDERS = "INVERSE_HEAD_AND_SHOULDERS"
    DOUBLE_TOP = "DOUBLE_TOP"
    DOUBLE_BOTTOM = "DOUBLE_BOTTOM"
    TRIPLE_TOP = "TRIPLE_TOP"
    TRIPLE_BOTTOM = "TRIPLE_BOTTOM"
    ASCENDING_TRIANGLE = "ASCENDING_TRIANGLE"
    DESCENDING_TRIANGLE = "DESCENDING_TRIANGLE"
    SYMMETRIC_TRIANGLE = "SYMMETRIC_TRIANGLE"
    FLAG_BULLISH = "FLAG_BULLISH"
    FLAG_BEARISH = "FLAG_BEARISH"
    WEDGE_RISING = "WEDGE_RISING"
    WEDGE_FALLING = "WEDGE_FALLING"
    CUP_AND_HANDLE = "CUP_AND_HANDLE"

    # Support/Resistance
    SUPPORT_LEVEL = "SUPPORT_LEVEL"
    RESISTANCE_LEVEL = "RESISTANCE_LEVEL"
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"

    # Trend patterns
    TREND_REVERSAL = "TREND_REVERSAL"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    CONSOLIDATION = "CONSOLIDATION"


class SignalStrength(Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


@dataclass
class NeuralSignal:
    symbol: str
    pattern: PatternType
    direction: str  # BULLISH, BEARISH, NEUTRAL
    strength: SignalStrength
    confidence: float  # 0-1
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    timeframe: str = "1D"
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "pattern": self.pattern.value,
            "direction": self.direction,
            "strength": self.strength.value,
            "confidence": round(self.confidence, 3),
            "price_target": self.price_target,
            "stop_loss": self.stop_loss,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
        }


@dataclass
class PatternMatch:
    pattern: PatternType
    start_index: int
    end_index: int
    confidence: float
    price_at_detection: float

    def to_dict(self) -> Dict:
        return {
            "pattern": self.pattern.value,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "confidence": round(self.confidence, 3),
            "price_at_detection": self.price_at_detection,
        }


@dataclass
class NeuralAnalysis:
    symbol: str
    timestamp: datetime
    current_price: float
    signals: List[NeuralSignal]
    patterns: List[PatternMatch]
    support_levels: List[float]
    resistance_levels: List[float]
    trend: str  # BULLISH, BEARISH, NEUTRAL
    trend_strength: float
    volatility_percentile: float
    neural_score: float  # -100 to 100
    recommendation: str  # BUY, SELL, HOLD

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "signals": [s.to_dict() for s in self.signals],
            "patterns": [p.to_dict() for p in self.patterns],
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels,
            "trend": self.trend,
            "trend_strength": round(self.trend_strength, 2),
            "volatility_percentile": round(self.volatility_percentile, 2),
            "neural_score": round(self.neural_score, 2),
            "recommendation": self.recommendation,
        }


class NeuralEngine:
    """
    Neural analysis engine for pattern recognition and market analysis
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "neural.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        # Pattern weights for scoring
        self.pattern_weights = {
            PatternType.DOJI: 0.3,
            PatternType.HAMMER: 0.6,
            PatternType.INVERTED_HAMMER: 0.5,
            PatternType.ENGULFING_BULLISH: 0.8,
            PatternType.ENGULFING_BEARISH: 0.8,
            PatternType.MORNING_STAR: 0.85,
            PatternType.EVENING_STAR: 0.85,
            PatternType.THREE_WHITE_SOLDIERS: 0.9,
            PatternType.THREE_BLACK_CROWS: 0.9,
            PatternType.HEAD_AND_SHOULDERS: 0.9,
            PatternType.INVERSE_HEAD_AND_SHOULDERS: 0.9,
            PatternType.DOUBLE_TOP: 0.75,
            PatternType.DOUBLE_BOTTOM: 0.75,
            PatternType.BREAKOUT: 0.7,
            PatternType.BREAKDOWN: 0.7,
        }

        logger.info("NeuralEngine initialized")

    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS neural_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                pattern TEXT NOT NULL,
                direction TEXT NOT NULL,
                strength TEXT NOT NULL,
                confidence REAL,
                price_target REAL,
                stop_loss REAL,
                timeframe TEXT,
                timestamp TEXT NOT NULL,
                description TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pattern_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                pattern TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                price_at_detection REAL,
                outcome TEXT,
                profit_loss_pct REAL
            )
        """)

        conn.commit()
        conn.close()

    def analyze(self, symbol: str, ohlcv_data: List[Dict]) -> NeuralAnalysis:
        """
        Perform comprehensive neural analysis on a symbol

        Args:
            symbol: Stock symbol
            ohlcv_data: List of OHLCV dictionaries with keys:
                        open, high, low, close, volume, timestamp
        """
        if not ohlcv_data or len(ohlcv_data) < 20:
            return self._empty_analysis(symbol)

        # Convert to numpy arrays for calculations
        opens = np.array([d["open"] for d in ohlcv_data])
        highs = np.array([d["high"] for d in ohlcv_data])
        lows = np.array([d["low"] for d in ohlcv_data])
        closes = np.array([d["close"] for d in ohlcv_data])
        volumes = np.array([d["volume"] for d in ohlcv_data])

        current_price = closes[-1]

        # Detect patterns
        patterns = self._detect_patterns(opens, highs, lows, closes, volumes)

        # Calculate support/resistance
        support_levels = self._find_support_levels(lows, current_price)
        resistance_levels = self._find_resistance_levels(highs, current_price)

        # Calculate trend
        trend, trend_strength = self._calculate_trend(closes)

        # Calculate volatility percentile
        volatility_percentile = self._calculate_volatility_percentile(closes)

        # Generate signals from patterns
        signals = self._generate_signals(symbol, patterns, current_price, trend)

        # Calculate neural score
        neural_score = self._calculate_neural_score(
            signals, trend, trend_strength, volatility_percentile
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(neural_score, trend)

        analysis = NeuralAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=current_price,
            signals=signals,
            patterns=patterns,
            support_levels=support_levels[:5],  # Top 5
            resistance_levels=resistance_levels[:5],  # Top 5
            trend=trend,
            trend_strength=trend_strength,
            volatility_percentile=volatility_percentile,
            neural_score=neural_score,
            recommendation=recommendation,
        )

        # Save signals to database
        for signal in signals:
            self._save_signal(signal)

        return analysis

    def _empty_analysis(self, symbol: str) -> NeuralAnalysis:
        """Return empty analysis when data is insufficient"""
        return NeuralAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=0,
            signals=[],
            patterns=[],
            support_levels=[],
            resistance_levels=[],
            trend="NEUTRAL",
            trend_strength=0,
            volatility_percentile=50,
            neural_score=0,
            recommendation="HOLD",
        )

    def _detect_patterns(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> List[PatternMatch]:
        """Detect candlestick and chart patterns"""
        patterns = []
        n = len(closes)

        if n < 3:
            return patterns

        # Calculate body and shadow metrics
        bodies = closes - opens
        upper_shadows = highs - np.maximum(opens, closes)
        lower_shadows = np.minimum(opens, closes) - lows
        ranges = highs - lows

        # Doji detection (small body relative to range)
        for i in range(n - 1, max(n - 10, 0), -1):
            if ranges[i] > 0 and abs(bodies[i]) / ranges[i] < 0.1:
                patterns.append(PatternMatch(
                    pattern=PatternType.DOJI,
                    start_index=i,
                    end_index=i,
                    confidence=0.7,
                    price_at_detection=closes[i]
                ))

        # Hammer detection (small body at top, long lower shadow)
        for i in range(n - 1, max(n - 10, 0), -1):
            if ranges[i] > 0:
                body_pct = abs(bodies[i]) / ranges[i]
                lower_shadow_pct = lower_shadows[i] / ranges[i]
                upper_shadow_pct = upper_shadows[i] / ranges[i]

                if body_pct < 0.3 and lower_shadow_pct > 0.6 and upper_shadow_pct < 0.1:
                    patterns.append(PatternMatch(
                        pattern=PatternType.HAMMER,
                        start_index=i,
                        end_index=i,
                        confidence=0.75,
                        price_at_detection=closes[i]
                    ))

        # Engulfing patterns
        for i in range(1, n):
            prev_body = bodies[i - 1]
            curr_body = bodies[i]

            # Bullish engulfing
            if prev_body < 0 and curr_body > 0:
                if closes[i] > opens[i - 1] and opens[i] < closes[i - 1]:
                    if abs(curr_body) > abs(prev_body):
                        patterns.append(PatternMatch(
                            pattern=PatternType.ENGULFING_BULLISH,
                            start_index=i - 1,
                            end_index=i,
                            confidence=0.8,
                            price_at_detection=closes[i]
                        ))

            # Bearish engulfing
            elif prev_body > 0 and curr_body < 0:
                if closes[i] < opens[i - 1] and opens[i] > closes[i - 1]:
                    if abs(curr_body) > abs(prev_body):
                        patterns.append(PatternMatch(
                            pattern=PatternType.ENGULFING_BEARISH,
                            start_index=i - 1,
                            end_index=i,
                            confidence=0.8,
                            price_at_detection=closes[i]
                        ))

        # Three white soldiers / Three black crows
        if n >= 3:
            for i in range(2, n):
                # Three white soldiers
                if (bodies[i] > 0 and bodies[i - 1] > 0 and bodies[i - 2] > 0 and
                    closes[i] > closes[i - 1] > closes[i - 2] and
                    opens[i] > opens[i - 1] > opens[i - 2]):
                    patterns.append(PatternMatch(
                        pattern=PatternType.THREE_WHITE_SOLDIERS,
                        start_index=i - 2,
                        end_index=i,
                        confidence=0.85,
                        price_at_detection=closes[i]
                    ))

                # Three black crows
                if (bodies[i] < 0 and bodies[i - 1] < 0 and bodies[i - 2] < 0 and
                    closes[i] < closes[i - 1] < closes[i - 2] and
                    opens[i] < opens[i - 1] < opens[i - 2]):
                    patterns.append(PatternMatch(
                        pattern=PatternType.THREE_BLACK_CROWS,
                        start_index=i - 2,
                        end_index=i,
                        confidence=0.85,
                        price_at_detection=closes[i]
                    ))

        # Double top/bottom detection (simplified)
        if n >= 20:
            window = 10
            for i in range(window, n - window):
                # Double top
                left_high = np.max(highs[i - window:i])
                right_high = np.max(highs[i:i + window])
                if abs(left_high - right_high) / left_high < 0.02:  # Within 2%
                    if highs[i] < left_high * 0.98:  # Valley in between
                        patterns.append(PatternMatch(
                            pattern=PatternType.DOUBLE_TOP,
                            start_index=i - window,
                            end_index=i + window,
                            confidence=0.7,
                            price_at_detection=closes[-1]
                        ))

                # Double bottom
                left_low = np.min(lows[i - window:i])
                right_low = np.min(lows[i:i + window])
                if abs(left_low - right_low) / left_low < 0.02:
                    if lows[i] > left_low * 1.02:
                        patterns.append(PatternMatch(
                            pattern=PatternType.DOUBLE_BOTTOM,
                            start_index=i - window,
                            end_index=i + window,
                            confidence=0.7,
                            price_at_detection=closes[-1]
                        ))

        # Breakout/Breakdown detection
        if n >= 20:
            recent_high = np.max(highs[-20:-1])
            recent_low = np.min(lows[-20:-1])

            if closes[-1] > recent_high:
                patterns.append(PatternMatch(
                    pattern=PatternType.BREAKOUT,
                    start_index=n - 20,
                    end_index=n - 1,
                    confidence=0.75,
                    price_at_detection=closes[-1]
                ))

            if closes[-1] < recent_low:
                patterns.append(PatternMatch(
                    pattern=PatternType.BREAKDOWN,
                    start_index=n - 20,
                    end_index=n - 1,
                    confidence=0.75,
                    price_at_detection=closes[-1]
                ))

        return patterns

    def _find_support_levels(self, lows: np.ndarray, current_price: float) -> List[float]:
        """Find support levels below current price"""
        # Use pivot points and local minima
        supports = []
        n = len(lows)

        # Find local minima
        for i in range(2, n - 2):
            if lows[i] < lows[i - 1] and lows[i] < lows[i - 2]:
                if lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
                    if lows[i] < current_price:
                        supports.append(lows[i])

        # Add recent low
        recent_low = np.min(lows[-20:])
        if recent_low < current_price and recent_low not in supports:
            supports.append(recent_low)

        # Sort by proximity to current price
        supports.sort(key=lambda x: current_price - x)

        return supports

    def _find_resistance_levels(self, highs: np.ndarray, current_price: float) -> List[float]:
        """Find resistance levels above current price"""
        resistances = []
        n = len(highs)

        # Find local maxima
        for i in range(2, n - 2):
            if highs[i] > highs[i - 1] and highs[i] > highs[i - 2]:
                if highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
                    if highs[i] > current_price:
                        resistances.append(highs[i])

        # Add recent high
        recent_high = np.max(highs[-20:])
        if recent_high > current_price and recent_high not in resistances:
            resistances.append(recent_high)

        # Sort by proximity to current price
        resistances.sort(key=lambda x: x - current_price)

        return resistances

    def _calculate_trend(self, closes: np.ndarray) -> Tuple[str, float]:
        """Calculate trend direction and strength"""
        if len(closes) < 20:
            return "NEUTRAL", 0.0

        # Use linear regression slope
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]

        # Normalize slope
        avg_price = np.mean(closes)
        normalized_slope = (slope / avg_price) * 100 * len(closes)

        # Also check moving averages
        sma_20 = np.mean(closes[-20:])
        sma_50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma_20

        # Combine signals
        ma_signal = (sma_20 - sma_50) / sma_50 * 100 if sma_50 > 0 else 0

        combined_signal = normalized_slope * 0.6 + ma_signal * 0.4

        strength = min(abs(combined_signal), 100)

        if combined_signal > 5:
            return "BULLISH", strength
        elif combined_signal < -5:
            return "BEARISH", strength
        else:
            return "NEUTRAL", strength

    def _calculate_volatility_percentile(self, closes: np.ndarray) -> float:
        """Calculate current volatility percentile"""
        if len(closes) < 20:
            return 50.0

        returns = np.diff(closes) / closes[:-1]

        # Rolling volatility
        current_vol = np.std(returns[-20:])

        # Historical volatility distribution
        vol_window = 20
        historical_vols = []
        for i in range(vol_window, len(returns)):
            historical_vols.append(np.std(returns[i - vol_window:i]))

        if not historical_vols:
            return 50.0

        # Calculate percentile
        percentile = sum(1 for v in historical_vols if v < current_vol) / len(historical_vols) * 100

        return percentile

    def _generate_signals(
        self,
        symbol: str,
        patterns: List[PatternMatch],
        current_price: float,
        trend: str
    ) -> List[NeuralSignal]:
        """Generate trading signals from detected patterns"""
        signals = []

        bullish_patterns = {
            PatternType.HAMMER, PatternType.ENGULFING_BULLISH,
            PatternType.MORNING_STAR, PatternType.THREE_WHITE_SOLDIERS,
            PatternType.DOUBLE_BOTTOM, PatternType.INVERSE_HEAD_AND_SHOULDERS,
            PatternType.BREAKOUT
        }

        bearish_patterns = {
            PatternType.INVERTED_HAMMER, PatternType.ENGULFING_BEARISH,
            PatternType.EVENING_STAR, PatternType.THREE_BLACK_CROWS,
            PatternType.DOUBLE_TOP, PatternType.HEAD_AND_SHOULDERS,
            PatternType.BREAKDOWN
        }

        for pattern in patterns:
            if pattern.pattern in bullish_patterns:
                direction = "BULLISH"
                price_target = current_price * 1.05  # 5% target
                stop_loss = current_price * 0.97  # 3% stop
            elif pattern.pattern in bearish_patterns:
                direction = "BEARISH"
                price_target = current_price * 0.95
                stop_loss = current_price * 1.03
            else:
                direction = "NEUTRAL"
                price_target = None
                stop_loss = None

            # Determine signal strength
            weight = self.pattern_weights.get(pattern.pattern, 0.5)
            combined_confidence = pattern.confidence * weight

            if combined_confidence >= 0.75:
                strength = SignalStrength.VERY_STRONG
            elif combined_confidence >= 0.6:
                strength = SignalStrength.STRONG
            elif combined_confidence >= 0.45:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Adjust for trend alignment
            if (direction == "BULLISH" and trend == "BULLISH") or \
               (direction == "BEARISH" and trend == "BEARISH"):
                combined_confidence = min(combined_confidence * 1.2, 1.0)
            elif (direction == "BULLISH" and trend == "BEARISH") or \
                 (direction == "BEARISH" and trend == "BULLISH"):
                combined_confidence *= 0.8

            signal = NeuralSignal(
                symbol=symbol,
                pattern=pattern.pattern,
                direction=direction,
                strength=strength,
                confidence=combined_confidence,
                price_target=price_target,
                stop_loss=stop_loss,
                timeframe="1D",
                description=f"{pattern.pattern.value} pattern detected with {combined_confidence:.0%} confidence"
            )

            signals.append(signal)

        return signals

    def _calculate_neural_score(
        self,
        signals: List[NeuralSignal],
        trend: str,
        trend_strength: float,
        volatility_percentile: float
    ) -> float:
        """Calculate overall neural score (-100 to 100)"""
        if not signals:
            # Base score on trend only
            if trend == "BULLISH":
                return trend_strength * 0.5
            elif trend == "BEARISH":
                return -trend_strength * 0.5
            return 0

        # Aggregate signal scores
        bullish_score = 0
        bearish_score = 0

        for signal in signals:
            weight = signal.confidence
            if signal.strength == SignalStrength.VERY_STRONG:
                weight *= 2.0
            elif signal.strength == SignalStrength.STRONG:
                weight *= 1.5
            elif signal.strength == SignalStrength.MODERATE:
                weight *= 1.0
            else:
                weight *= 0.5

            if signal.direction == "BULLISH":
                bullish_score += weight
            elif signal.direction == "BEARISH":
                bearish_score += weight

        # Net score
        net_score = (bullish_score - bearish_score) * 20  # Scale to ~100

        # Add trend component
        trend_component = trend_strength * 0.3
        if trend == "BULLISH":
            net_score += trend_component
        elif trend == "BEARISH":
            net_score -= trend_component

        # Volatility penalty for extreme values
        if volatility_percentile > 90:
            net_score *= 0.8
        elif volatility_percentile > 80:
            net_score *= 0.9

        return max(-100, min(100, net_score))

    def _generate_recommendation(self, neural_score: float, trend: str) -> str:
        """Generate trading recommendation"""
        if neural_score > 30:
            return "BUY"
        elif neural_score < -30:
            return "SELL"
        else:
            return "HOLD"

    def _save_signal(self, signal: NeuralSignal):
        """Save signal to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO neural_signals
                (symbol, pattern, direction, strength, confidence, price_target,
                 stop_loss, timeframe, timestamp, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.symbol,
                signal.pattern.value,
                signal.direction,
                signal.strength.value,
                signal.confidence,
                signal.price_target,
                signal.stop_loss,
                signal.timeframe,
                signal.timestamp.isoformat(),
                signal.description
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving neural signal: {e}")

    def get_signal_history(self, symbol: str, days: int = 30) -> List[Dict]:
        """Get signal history for a symbol"""
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, pattern, direction, strength, confidence,
                       price_target, stop_loss, timeframe, timestamp, description
                FROM neural_signals
                WHERE symbol = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (symbol, since))

            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "symbol": row[0],
                    "pattern": row[1],
                    "direction": row[2],
                    "strength": row[3],
                    "confidence": row[4],
                    "price_target": row[5],
                    "stop_loss": row[6],
                    "timeframe": row[7],
                    "timestamp": row[8],
                    "description": row[9],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting signal history: {e}")
            return []


# Singleton instance
_neural_engine: Optional[NeuralEngine] = None

def get_neural_engine() -> NeuralEngine:
    global _neural_engine
    if _neural_engine is None:
        _neural_engine = NeuralEngine()
    return _neural_engine
