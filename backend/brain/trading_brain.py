"""
QUANT INDUSTRY - Trading Brain
Multi-cycle intelligence system for coordinated trading decisions
"""

import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class BrainCycle(Enum):
    MICRO = "MICRO"      # Sub-minute decisions (scalping)
    SHORT = "SHORT"      # Intraday decisions (day trading)
    MEDIUM = "MEDIUM"    # Multi-day decisions (swing)
    LONG = "LONG"        # Multi-week decisions (position)
    MACRO = "MACRO"      # Multi-month decisions (investing)


class DecisionType(Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    SCALE_IN = "SCALE_IN"
    SCALE_OUT = "SCALE_OUT"
    HEDGE = "HEDGE"
    HOLD = "HOLD"
    AVOID = "AVOID"


class ConfidenceLevel(Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


@dataclass
class BrainDecision:
    decision_id: str
    symbol: str
    cycle: BrainCycle
    decision_type: DecisionType
    direction: str  # LONG, SHORT, NEUTRAL
    confidence: float
    confidence_level: ConfidenceLevel
    timestamp: datetime = field(default_factory=datetime.now)

    # Supporting data
    neural_score: float = 0.0
    regime_alignment: float = 0.0
    technical_score: float = 0.0
    sentiment_score: float = 0.0
    flow_score: float = 0.0

    # Trade parameters
    suggested_entry: Optional[float] = None
    suggested_stop: Optional[float] = None
    suggested_target: Optional[float] = None
    position_size_pct: float = 0.0

    # Reasoning
    factors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "cycle": self.cycle.value,
            "decision_type": self.decision_type.value,
            "direction": self.direction,
            "confidence": round(self.confidence, 3),
            "confidence_level": self.confidence_level.value,
            "timestamp": self.timestamp.isoformat(),
            "neural_score": round(self.neural_score, 2),
            "regime_alignment": round(self.regime_alignment, 2),
            "technical_score": round(self.technical_score, 2),
            "sentiment_score": round(self.sentiment_score, 2),
            "flow_score": round(self.flow_score, 2),
            "suggested_entry": self.suggested_entry,
            "suggested_stop": self.suggested_stop,
            "suggested_target": self.suggested_target,
            "position_size_pct": round(self.position_size_pct, 2),
            "factors": self.factors,
            "warnings": self.warnings,
        }


@dataclass
class BrainState:
    overall_bias: str  # BULLISH, BEARISH, NEUTRAL
    bias_strength: float
    active_cycles: List[BrainCycle]
    decisions_pending: int
    last_update: datetime

    # Cycle-specific states
    micro_state: Dict = field(default_factory=dict)
    short_state: Dict = field(default_factory=dict)
    medium_state: Dict = field(default_factory=dict)
    long_state: Dict = field(default_factory=dict)
    macro_state: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "overall_bias": self.overall_bias,
            "bias_strength": round(self.bias_strength, 2),
            "active_cycles": [c.value for c in self.active_cycles],
            "decisions_pending": self.decisions_pending,
            "last_update": self.last_update.isoformat(),
            "micro_state": self.micro_state,
            "short_state": self.short_state,
            "medium_state": self.medium_state,
            "long_state": self.long_state,
            "macro_state": self.macro_state,
        }


class TradingBrain:
    """
    Multi-cycle trading intelligence system
    Coordinates signals from neural engine, regime detector, and algo bot
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "brain.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        self.decisions: Dict[str, List[BrainDecision]] = {}  # symbol -> decisions
        self.state: Optional[BrainState] = None
        self.lock = threading.Lock()

        # Cycle weights for final decision
        self.cycle_weights = {
            BrainCycle.MICRO: 0.1,
            BrainCycle.SHORT: 0.25,
            BrainCycle.MEDIUM: 0.35,
            BrainCycle.LONG: 0.2,
            BrainCycle.MACRO: 0.1,
        }

        # Initialize state
        self._init_state()

        logger.info("TradingBrain initialized")

    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brain_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                cycle TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                confidence REAL,
                timestamp TEXT NOT NULL,
                neural_score REAL,
                regime_alignment REAL,
                technical_score REAL,
                factors TEXT,
                warnings TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brain_state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                overall_bias TEXT NOT NULL,
                bias_strength REAL,
                active_cycles TEXT,
                state_json TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _init_state(self):
        """Initialize brain state"""
        self.state = BrainState(
            overall_bias="NEUTRAL",
            bias_strength=0.0,
            active_cycles=[BrainCycle.SHORT, BrainCycle.MEDIUM],
            decisions_pending=0,
            last_update=datetime.now(),
        )

    def think(self, symbol: str, market_data: Dict) -> BrainDecision:
        """
        Main thinking process - analyze symbol across all cycles

        Args:
            symbol: Stock symbol
            market_data: Dictionary containing:
                - ohlcv: OHLCV data
                - quote: Current quote
                - news: Recent news (optional)
                - options_flow: Options flow data (optional)
        """

        # Gather intelligence from all sources
        neural_score = self._get_neural_intelligence(symbol, market_data)
        regime_alignment = self._get_regime_alignment(market_data)
        technical_score = self._get_technical_score(symbol, market_data)
        sentiment_score = self._get_sentiment_score(symbol, market_data)
        flow_score = self._get_flow_score(symbol, market_data)

        # Analyze each cycle
        cycle_decisions = {}
        for cycle in BrainCycle:
            cycle_decision = self._analyze_cycle(
                symbol, cycle, market_data,
                neural_score, regime_alignment, technical_score,
                sentiment_score, flow_score
            )
            cycle_decisions[cycle] = cycle_decision

        # Synthesize final decision
        final_decision = self._synthesize_decision(
            symbol, cycle_decisions,
            neural_score, regime_alignment, technical_score,
            sentiment_score, flow_score,
            market_data
        )

        # Store decision
        with self.lock:
            if symbol not in self.decisions:
                self.decisions[symbol] = []
            self.decisions[symbol].append(final_decision)
            if len(self.decisions[symbol]) > 100:
                self.decisions[symbol] = self.decisions[symbol][-100:]

        # Save to database
        self._save_decision(final_decision)

        # Update state
        self._update_state()

        return final_decision

    def _get_neural_intelligence(self, symbol: str, market_data: Dict) -> float:
        """Get neural analysis score"""
        try:
            from .neural_engine import get_neural_engine
            neural_engine = get_neural_engine()

            ohlcv = market_data.get("ohlcv", [])
            if ohlcv:
                analysis = neural_engine.analyze(symbol, ohlcv)
                return analysis.neural_score
        except Exception as e:
            logger.error(f"Error getting neural intelligence: {e}")

        return 0.0

    def _get_regime_alignment(self, market_data: Dict) -> float:
        """Get regime alignment score"""
        try:
            from .regime_detector import get_regime_detector
            regime_detector = get_regime_detector()

            # Prepare market data for regime detection
            regime_data = {}
            if "spy_ohlcv" in market_data:
                regime_data["SPY"] = market_data["spy_ohlcv"]
            if "qqq_ohlcv" in market_data:
                regime_data["QQQ"] = market_data["qqq_ohlcv"]

            if regime_data:
                analysis = regime_detector.detect_regime(regime_data)
                regime = analysis.current_state.regime.value

                # Score based on regime favorability
                if regime in ["BULL_STRONG"]:
                    return 1.0
                elif regime in ["BULL_WEAK", "RECOVERY"]:
                    return 0.5
                elif regime in ["RANGING_LOW_VOL"]:
                    return 0.0
                elif regime in ["RANGING_HIGH_VOL", "BEAR_WEAK"]:
                    return -0.5
                elif regime in ["BEAR_STRONG", "CRISIS"]:
                    return -1.0

        except Exception as e:
            logger.error(f"Error getting regime alignment: {e}")

        return 0.0

    def _get_technical_score(self, symbol: str, market_data: Dict) -> float:
        """Calculate technical analysis score"""
        ohlcv = market_data.get("ohlcv", [])
        if not ohlcv or len(ohlcv) < 50:
            return 0.0

        try:
            closes = np.array([d.get("close", d.get("Close", 0)) for d in ohlcv])
            highs = np.array([d.get("high", d.get("High", 0)) for d in ohlcv])
            lows = np.array([d.get("low", d.get("Low", 0)) for d in ohlcv])

            score = 0.0

            # SMA crossover
            sma_20 = np.mean(closes[-20:])
            sma_50 = np.mean(closes[-50:])
            current = closes[-1]

            if current > sma_20 > sma_50:
                score += 30
            elif current < sma_20 < sma_50:
                score -= 30

            # RSI
            returns = np.diff(closes) / closes[:-1]
            gains = np.where(returns > 0, returns, 0)
            losses = np.where(returns < 0, -returns, 0)
            avg_gain = np.mean(gains[-14:])
            avg_loss = np.mean(losses[-14:])
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))

            if rsi > 70:
                score -= 20  # Overbought
            elif rsi < 30:
                score += 20  # Oversold
            elif 40 < rsi < 60:
                score += 5  # Neutral

            # MACD (simplified)
            ema_12 = self._ema(closes, 12)
            ema_26 = self._ema(closes, 26)
            macd = ema_12 - ema_26
            signal = self._ema(np.array([macd]), 9)

            if macd > signal:
                score += 20
            else:
                score -= 20

            # Trend strength
            x = np.arange(20)
            slope = np.polyfit(x, closes[-20:], 1)[0]
            trend_pct = (slope / np.mean(closes[-20:])) * 100 * 20

            if trend_pct > 5:
                score += 30
            elif trend_pct > 2:
                score += 15
            elif trend_pct < -5:
                score -= 30
            elif trend_pct < -2:
                score -= 15

            return max(-100, min(100, score))

        except Exception as e:
            logger.error(f"Error calculating technical score: {e}")
            return 0.0

    def _ema(self, data: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return np.mean(data)

        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])

        for i in range(period, len(data)):
            ema = (data[i] * multiplier) + (ema * (1 - multiplier))

        return ema

    def _get_sentiment_score(self, symbol: str, market_data: Dict) -> float:
        """Calculate sentiment score from news"""
        news = market_data.get("news", [])
        if not news:
            return 0.0

        # Simple sentiment analysis based on news headlines
        positive_words = ["surge", "rally", "gain", "beat", "strong", "upgrade", "bullish", "buy"]
        negative_words = ["fall", "drop", "miss", "weak", "downgrade", "bearish", "sell", "crash"]

        score = 0
        for article in news[:10]:  # Last 10 articles
            headline = article.get("headline", "").lower()
            for word in positive_words:
                if word in headline:
                    score += 10
            for word in negative_words:
                if word in headline:
                    score -= 10

        return max(-100, min(100, score))

    def _get_flow_score(self, symbol: str, market_data: Dict) -> float:
        """Calculate options flow score"""
        flow = market_data.get("options_flow", [])
        if not flow:
            return 0.0

        call_premium = 0
        put_premium = 0

        for trade in flow:
            premium = trade.get("premium", 0)
            if trade.get("option_type") == "call":
                call_premium += premium
            else:
                put_premium += premium

        if call_premium + put_premium == 0:
            return 0.0

        # Call/Put ratio
        ratio = call_premium / max(put_premium, 1)

        if ratio > 2:
            return 50  # Bullish flow
        elif ratio > 1.2:
            return 25
        elif ratio < 0.5:
            return -50  # Bearish flow
        elif ratio < 0.8:
            return -25

        return 0.0

    def _analyze_cycle(
        self,
        symbol: str,
        cycle: BrainCycle,
        market_data: Dict,
        neural_score: float,
        regime_alignment: float,
        technical_score: float,
        sentiment_score: float,
        flow_score: float
    ) -> Dict:
        """Analyze a specific trading cycle"""
        # Adjust weights based on cycle
        if cycle == BrainCycle.MICRO:
            weights = {"neural": 0.1, "regime": 0.05, "technical": 0.6, "sentiment": 0.05, "flow": 0.2}
        elif cycle == BrainCycle.SHORT:
            weights = {"neural": 0.2, "regime": 0.1, "technical": 0.4, "sentiment": 0.1, "flow": 0.2}
        elif cycle == BrainCycle.MEDIUM:
            weights = {"neural": 0.3, "regime": 0.2, "technical": 0.25, "sentiment": 0.15, "flow": 0.1}
        elif cycle == BrainCycle.LONG:
            weights = {"neural": 0.25, "regime": 0.3, "technical": 0.15, "sentiment": 0.2, "flow": 0.1}
        else:  # MACRO
            weights = {"neural": 0.15, "regime": 0.4, "technical": 0.1, "sentiment": 0.3, "flow": 0.05}

        # Calculate weighted score
        weighted_score = (
            neural_score * weights["neural"] +
            regime_alignment * 100 * weights["regime"] +
            technical_score * weights["technical"] +
            sentiment_score * weights["sentiment"] +
            flow_score * weights["flow"]
        )

        # Determine direction
        if weighted_score > 20:
            direction = "LONG"
        elif weighted_score < -20:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        return {
            "cycle": cycle,
            "score": weighted_score,
            "direction": direction,
            "weights": weights,
        }

    def _synthesize_decision(
        self,
        symbol: str,
        cycle_decisions: Dict[BrainCycle, Dict],
        neural_score: float,
        regime_alignment: float,
        technical_score: float,
        sentiment_score: float,
        flow_score: float,
        market_data: Dict
    ) -> BrainDecision:
        """Synthesize final decision from all cycles"""
        # Weight cycle decisions
        total_score = 0
        for cycle, weight in self.cycle_weights.items():
            total_score += cycle_decisions[cycle]["score"] * weight

        # Determine confidence
        confidence = min(abs(total_score) / 100, 1.0)

        if confidence >= 0.8:
            confidence_level = ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.6:
            confidence_level = ConfidenceLevel.HIGH
        elif confidence >= 0.4:
            confidence_level = ConfidenceLevel.MEDIUM
        elif confidence >= 0.2:
            confidence_level = ConfidenceLevel.LOW
        else:
            confidence_level = ConfidenceLevel.VERY_LOW

        # Determine direction
        if total_score > 15:
            direction = "LONG"
        elif total_score < -15:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        # Determine decision type
        if direction == "NEUTRAL" or confidence < 0.3:
            decision_type = DecisionType.HOLD
        elif direction == "LONG":
            if confidence > 0.6:
                decision_type = DecisionType.ENTRY
            else:
                decision_type = DecisionType.SCALE_IN
        elif confidence > 0.6:
            decision_type = DecisionType.ENTRY
        else:
            decision_type = DecisionType.SCALE_IN

        # Calculate trade parameters
        current_price = market_data.get("quote", {}).get("price", 0)
        if current_price > 0:
            if direction == "LONG":
                suggested_entry = current_price
                suggested_stop = current_price * 0.97
                suggested_target = current_price * 1.05
            elif direction == "SHORT":
                suggested_entry = current_price
                suggested_stop = current_price * 1.03
                suggested_target = current_price * 0.95
            else:
                suggested_entry = None
                suggested_stop = None
                suggested_target = None
        else:
            suggested_entry = None
            suggested_stop = None
            suggested_target = None

        # Position sizing based on confidence
        position_size_pct = min(confidence * 10, 5.0)  # Max 5% of portfolio

        # Compile factors
        factors = []
        if neural_score > 20:
            factors.append(f"Strong neural signal ({neural_score:.0f})")
        elif neural_score < -20:
            factors.append(f"Bearish neural signal ({neural_score:.0f})")

        if regime_alignment > 0.5:
            factors.append("Favorable market regime")
        elif regime_alignment < -0.5:
            factors.append("Unfavorable market regime")

        if technical_score > 30:
            factors.append(f"Bullish technicals ({technical_score:.0f})")
        elif technical_score < -30:
            factors.append(f"Bearish technicals ({technical_score:.0f})")

        # Compile warnings
        warnings = []
        if regime_alignment < -0.5 and direction == "LONG":
            warnings.append("Going long against bearish regime")
        if confidence < 0.4:
            warnings.append("Low confidence signal")

        return BrainDecision(
            decision_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            cycle=BrainCycle.MEDIUM,  # Primary cycle
            decision_type=decision_type,
            direction=direction,
            confidence=confidence,
            confidence_level=confidence_level,
            neural_score=neural_score,
            regime_alignment=regime_alignment * 100,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            flow_score=flow_score,
            suggested_entry=suggested_entry,
            suggested_stop=suggested_stop,
            suggested_target=suggested_target,
            position_size_pct=position_size_pct,
            factors=factors,
            warnings=warnings,
        )

    def _update_state(self):
        """Update brain state"""
        with self.lock:
            # Aggregate recent decisions
            all_decisions = []
            for symbol_decisions in self.decisions.values():
                all_decisions.extend(symbol_decisions[-10:])

            if all_decisions:
                # Calculate overall bias
                long_count = sum(1 for d in all_decisions if d.direction == "LONG")
                short_count = sum(1 for d in all_decisions if d.direction == "SHORT")
                total = long_count + short_count

                if total > 0:
                    bias_ratio = (long_count - short_count) / total
                    if bias_ratio > 0.3:
                        self.state.overall_bias = "BULLISH"
                    elif bias_ratio < -0.3:
                        self.state.overall_bias = "BEARISH"
                    else:
                        self.state.overall_bias = "NEUTRAL"

                    self.state.bias_strength = abs(bias_ratio)

            self.state.decisions_pending = len([
                d for d in all_decisions
                if d.decision_type == DecisionType.ENTRY
            ])
            self.state.last_update = datetime.now()

    def get_state(self) -> BrainState:
        """Get current brain state"""
        return self.state

    def get_decisions(self, symbol: str = None, limit: int = 10) -> List[BrainDecision]:
        """Get recent decisions"""
        with self.lock:
            if symbol:
                return self.decisions.get(symbol, [])[-limit:]
            else:
                all_decisions = []
                for symbol_decisions in self.decisions.values():
                    all_decisions.extend(symbol_decisions)
                all_decisions.sort(key=lambda d: d.timestamp, reverse=True)
                return all_decisions[:limit]

    def _save_decision(self, decision: BrainDecision):
        """Save decision to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO brain_decisions
                (decision_id, symbol, cycle, decision_type, direction, confidence,
                 timestamp, neural_score, regime_alignment, technical_score, factors, warnings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.decision_id,
                decision.symbol,
                decision.cycle.value,
                decision.decision_type.value,
                decision.direction,
                decision.confidence,
                decision.timestamp.isoformat(),
                decision.neural_score,
                decision.regime_alignment,
                decision.technical_score,
                ",".join(decision.factors),
                ",".join(decision.warnings)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving decision: {e}")


# Singleton instance
_trading_brain: Optional[TradingBrain] = None

def get_trading_brain() -> TradingBrain:
    global _trading_brain
    if _trading_brain is None:
        _trading_brain = TradingBrain()
    return _trading_brain
