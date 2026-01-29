"""
QUANT INDUSTRY - Trading Brain
Multi-cycle intelligence system for coordinated trading decisions

Now integrated with mathematical foundations:
- HMM-based regime detection
- Kelly criterion position sizing
- Risk-adjusted parameters
"""

import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import sys

import numpy as np

# Add brain module to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from brain.math.integration import (
        IntegratedRegimeDetector,
        IntegratedPositionSizer,
        RiskManager,
        RegimeState,
        MarketRegime,
        create_regime_detector,
        create_position_sizer,
        create_risk_manager
    )
    MATH_AVAILABLE = True
except ImportError as e:
    MATH_AVAILABLE = False
    logging.warning(f"Math integration not available: {e}")

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
    
    Now with integrated math:
    - HMM regime detection for market state awareness
    - Kelly criterion for optimal position sizing
    - Risk manager for drawdown protection
    """

    def __init__(self, db_path: str = None, account_equity: float = 100000.0):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "brain.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        self.decisions: Dict[str, List[BrainDecision]] = {}  # symbol -> decisions
        self.state: Optional[BrainState] = None
        self.lock = threading.Lock()
        
        # Account tracking
        self.account_equity = account_equity

        # Cycle weights for final decision
        self.cycle_weights = {
            BrainCycle.MICRO: 0.1,
            BrainCycle.SHORT: 0.25,
            BrainCycle.MEDIUM: 0.35,
            BrainCycle.LONG: 0.2,
            BrainCycle.MACRO: 0.1,
        }
        
        # === MATH INTEGRATION ===
        if MATH_AVAILABLE:
            # HMM-based regime detector
            self.regime_detector = create_regime_detector(n_regimes=4)
            
            # Kelly-based position sizer
            self.position_sizer = create_position_sizer(
                max_position=0.10,      # Max 10% per position
                kelly_fraction=0.25     # Use quarter Kelly (safer)
            )
            
            # Risk manager with drawdown protection
            self.risk_manager = create_risk_manager(
                drawdown_threshold=0.10,   # Start reducing at 10% DD
                critical_drawdown=0.20     # Stop at 20% DD
            )
            self.risk_manager.update_equity(account_equity)
            
            # Track if regime detector is fitted
            self.regime_fitted = False
            
            logger.info("TradingBrain initialized WITH math integration")
        else:
            self.regime_detector = None
            self.position_sizer = None
            self.risk_manager = None
            self.regime_fitted = False
            logger.info("TradingBrain initialized WITHOUT math integration")

        # Initialize state
        self._init_state()

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
        
        # Get regime alignment AND regime state for position sizing
        regime_alignment, regime_state = self._get_regime_alignment(market_data)
        
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

        # Synthesize final decision (now with regime_state for Kelly sizing)
        final_decision = self._synthesize_decision(
            symbol, cycle_decisions,
            neural_score, regime_alignment, technical_score,
            sentiment_score, flow_score,
            market_data,
            regime_state=regime_state  # Pass for position sizing
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

    def _get_regime_alignment(self, market_data: Dict) -> Tuple[float, Optional['RegimeState']]:
        """
        Get regime alignment score using HMM-based detection.
        
        Returns:
            Tuple of (alignment_score, regime_state)
            - alignment_score: -1 to 1 indicating bearish to bullish
            - regime_state: Full RegimeState object for position sizing
        """
        regime_state = None
        
        # === USE HMM REGIME DETECTOR IF AVAILABLE ===
        if MATH_AVAILABLE and self.regime_detector is not None:
            try:
                # Extract prices from market data
                prices = self._extract_prices_for_regime(market_data)
                
                if prices is not None and len(prices) > 50:
                    # Fit regime detector if not yet fitted
                    if not self.regime_fitted:
                        self.regime_detector.fit(prices)
                        self.regime_fitted = True
                        logger.info("Regime detector fitted with HMM")
                    
                    # Detect current regime
                    regime_state = self.regime_detector.detect(prices)
                    
                    # Convert regime to alignment score
                    regime_scores = {
                        MarketRegime.CRISIS: -1.0,
                        MarketRegime.BEAR_STRONG: -0.8,
                        MarketRegime.BEAR_WEAK: -0.4,
                        MarketRegime.NEUTRAL: 0.0,
                        MarketRegime.BULL_WEAK: 0.4,
                        MarketRegime.BULL_STRONG: 0.8,
                        MarketRegime.EUPHORIA: 0.3,  # Cautious in euphoria
                    }
                    
                    alignment = regime_scores.get(regime_state.regime, 0.0)
                    
                    # Weight by confidence
                    alignment *= regime_state.confidence
                    
                    logger.debug(
                        f"HMM Regime: {regime_state.regime.value}, "
                        f"confidence={regime_state.confidence:.2f}, "
                        f"alignment={alignment:.2f}"
                    )
                    
                    return alignment, regime_state
                    
            except Exception as e:
                logger.error(f"HMM regime detection error: {e}")
        
        # === FALLBACK TO LEGACY DETECTOR ===
        try:
            from .regime_detector import get_regime_detector
            legacy_detector = get_regime_detector()

            regime_data = {}
            if "spy_ohlcv" in market_data:
                regime_data["SPY"] = market_data["spy_ohlcv"]
            if "qqq_ohlcv" in market_data:
                regime_data["QQQ"] = market_data["qqq_ohlcv"]

            if regime_data:
                analysis = legacy_detector.detect_regime(regime_data)
                regime = analysis.current_state.regime.value

                if regime in ["BULL_STRONG"]:
                    return 1.0, None
                elif regime in ["BULL_WEAK", "RECOVERY"]:
                    return 0.5, None
                elif regime in ["RANGING_LOW_VOL"]:
                    return 0.0, None
                elif regime in ["RANGING_HIGH_VOL", "BEAR_WEAK"]:
                    return -0.5, None
                elif regime in ["BEAR_STRONG", "CRISIS"]:
                    return -1.0, None

        except Exception as e:
            logger.error(f"Legacy regime detection error: {e}")

        return 0.0, None
    
    def _extract_prices_for_regime(self, market_data: Dict) -> Optional[np.ndarray]:
        """Extract price series for regime detection."""
        # Try SPY first (best for market regime)
        for key in ["spy_ohlcv", "qqq_ohlcv", "ohlcv"]:
            if key in market_data:
                ohlcv = market_data[key]
                if ohlcv and len(ohlcv) > 0:
                    try:
                        prices = np.array([
                            d.get("close", d.get("Close", 0)) for d in ohlcv
                        ])
                        if len(prices) > 50:
                            return prices
                    except Exception:
                        continue
        return None
    
    def _estimate_volatility(self, market_data: Dict, window: int = 20) -> float:
        """
        Estimate annualized volatility from OHLCV data.
        
        Returns annualized volatility (e.g., 0.20 = 20%).
        """
        ohlcv = market_data.get("ohlcv", [])
        if not ohlcv or len(ohlcv) < window:
            return 0.20  # Default 20% if not enough data
        
        try:
            closes = np.array([d.get("close", d.get("Close", 0)) for d in ohlcv])
            
            # Calculate log returns
            returns = np.diff(np.log(closes))
            
            # Recent volatility (annualized)
            recent_returns = returns[-window:]
            daily_vol = np.std(recent_returns)
            annualized_vol = daily_vol * np.sqrt(252)
            
            return max(annualized_vol, 0.05)  # Floor at 5%
            
        except Exception as e:
            logger.error(f"Volatility estimation error: {e}")
            return 0.20

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
        market_data: Dict,
        regime_state: Optional['RegimeState'] = None
    ) -> BrainDecision:
        """
        Synthesize final decision from all cycles.
        
        Now with:
        - Kelly criterion position sizing
        - Regime-adjusted risk parameters
        - Drawdown protection
        """
        import uuid

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

        # Calculate trade parameters with regime-adjusted stops/targets
        current_price = market_data.get("quote", {}).get("price", 0)
        
        # Get regime-based multipliers
        stop_mult = 1.0
        profit_mult = 1.0
        if regime_state is not None:
            stop_mult = regime_state.stop_multiplier
            profit_mult = regime_state.profit_multiplier
        
        if current_price > 0:
            # Base stop/target percentages
            base_stop_pct = 0.03  # 3% base stop
            base_target_pct = 0.05  # 5% base target
            
            # Adjust for regime
            adjusted_stop_pct = base_stop_pct * stop_mult
            adjusted_target_pct = base_target_pct * profit_mult
            
            if direction == "LONG":
                suggested_entry = current_price
                suggested_stop = current_price * (1 - adjusted_stop_pct)
                suggested_target = current_price * (1 + adjusted_target_pct)
            elif direction == "SHORT":
                suggested_entry = current_price
                suggested_stop = current_price * (1 + adjusted_stop_pct)
                suggested_target = current_price * (1 - adjusted_target_pct)
            else:
                suggested_entry = None
                suggested_stop = None
                suggested_target = None
        else:
            suggested_entry = None
            suggested_stop = None
            suggested_target = None

        # === KELLY CRITERION POSITION SIZING ===
        if MATH_AVAILABLE and self.position_sizer is not None and regime_state is not None:
            try:
                # Estimate current volatility from OHLCV
                current_vol = self._estimate_volatility(market_data)
                
                # Calculate Kelly-based position size
                size_result = self.position_sizer.calculate(
                    signal_confidence=confidence,
                    regime_state=regime_state,
                    current_volatility=current_vol,
                    account_equity=self.account_equity
                )
                
                # Apply risk manager check
                if self.risk_manager is not None:
                    risk_mult = self.risk_manager.get_risk_multiplier(regime_state)
                    position_size_pct = size_result.final_size * risk_mult * 100
                else:
                    position_size_pct = size_result.final_size * 100
                
                logger.debug(
                    f"Kelly sizing: base={size_result.base_kelly:.3f}, "
                    f"adjusted={size_result.adjusted_kelly:.3f}, "
                    f"final={position_size_pct:.2f}%"
                )
                
            except Exception as e:
                logger.error(f"Kelly position sizing error: {e}")
                position_size_pct = min(confidence * 10, 5.0)
        else:
            # Fallback: simple confidence-based sizing
            position_size_pct = min(confidence * 10, 5.0)

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
        
        # Add regime info to factors
        if regime_state is not None:
            factors.append(f"HMM Regime: {regime_state.regime.value} ({regime_state.confidence:.0%})")

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
        
        # Regime-specific warnings
        if regime_state is not None:
            if regime_state.regime == MarketRegime.CRISIS:
                warnings.append("⚠️ CRISIS regime - reduced positions")
            elif regime_state.regime == MarketRegime.EUPHORIA:
                warnings.append("⚠️ EUPHORIA regime - caution advised")
            if regime_state.volatility_regime == "extreme":
                warnings.append("⚠️ Extreme volatility - widened stops")

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
    
    # === TRADE FEEDBACK METHODS ===
    
    def record_trade_result(self, pnl: float, is_win: bool):
        """
        Record trade result for Kelly criterion learning.
        
        Call this when a trade closes to improve position sizing over time.
        
        Args:
            pnl: Profit/loss as a decimal (e.g., 0.02 = 2% gain)
            is_win: True if trade was profitable
        """
        if MATH_AVAILABLE and self.position_sizer is not None:
            self.position_sizer.add_trade(pnl, is_win)
            logger.info(f"Recorded trade: pnl={pnl:.2%}, win={is_win}")
    
    def update_equity(self, equity: float):
        """
        Update account equity for drawdown tracking.
        
        Args:
            equity: Current account value
        """
        self.account_equity = equity
        if MATH_AVAILABLE and self.risk_manager is not None:
            self.risk_manager.update_equity(equity)
            
            # Log if in drawdown
            dd = self.risk_manager.current_drawdown
            if dd > 0.05:
                logger.warning(f"Account in {dd:.1%} drawdown")
    
    def get_risk_status(self) -> Dict:
        """Get current risk status."""
        if not MATH_AVAILABLE or self.risk_manager is None:
            return {"status": "unavailable"}
        
        return {
            "current_drawdown": self.risk_manager.current_drawdown,
            "peak_equity": self.risk_manager.peak_equity,
            "current_equity": self.risk_manager.current_equity,
            "trading_allowed": self.risk_manager.current_drawdown < self.risk_manager.critical_drawdown,
            "risk_level": (
                "critical" if self.risk_manager.current_drawdown >= self.risk_manager.critical_drawdown
                else "elevated" if self.risk_manager.current_drawdown >= self.risk_manager.drawdown_threshold
                else "normal"
            )
        }
    
    def get_regime_status(self) -> Dict:
        """Get current regime detection status."""
        if not MATH_AVAILABLE or self.regime_detector is None:
            return {"status": "unavailable", "fitted": False}
        
        return {
            "status": "available",
            "fitted": self.regime_fitted,
            "n_regimes": self.regime_detector.n_regimes
        }


# Singleton instance
_trading_brain: Optional[TradingBrain] = None

def get_trading_brain() -> TradingBrain:
    global _trading_brain
    if _trading_brain is None:
        _trading_brain = TradingBrain()
    return _trading_brain
