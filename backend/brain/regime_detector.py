"""
QUANT INDUSTRY - Market Regime Detection
Classifies market conditions into Bull/Bear/Ranging/Crisis regimes
Enhanced with SVM-based regime classification for learned decision boundaries
"""

import logging
import math
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

# SVM for enhanced regime classification
try:
    from sklearn.svm import SVC
    from sklearn.preprocessing import RobustScaler
    import joblib
    SVM_AVAILABLE = True
except ImportError:
    SVM_AVAILABLE = False

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    BULL_STRONG = "BULL_STRONG"
    BULL_WEAK = "BULL_WEAK"
    BEAR_STRONG = "BEAR_STRONG"
    BEAR_WEAK = "BEAR_WEAK"
    RANGING_HIGH_VOL = "RANGING_HIGH_VOL"
    RANGING_LOW_VOL = "RANGING_LOW_VOL"
    CRISIS = "CRISIS"
    RECOVERY = "RECOVERY"


class VolatilityRegime(Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    EXTREME = "EXTREME"


class TrendRegime(Enum):
    STRONG_UPTREND = "STRONG_UPTREND"
    UPTREND = "UPTREND"
    WEAK_UPTREND = "WEAK_UPTREND"
    SIDEWAYS = "SIDEWAYS"
    WEAK_DOWNTREND = "WEAK_DOWNTREND"
    DOWNTREND = "DOWNTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"


@dataclass
class RegimeState:
    regime: MarketRegime
    volatility_regime: VolatilityRegime
    trend_regime: TrendRegime
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)

    # Regime metrics
    trend_strength: float = 0.0
    volatility_percentile: float = 0.0
    momentum_score: float = 0.0
    breadth_score: float = 0.0

    # Transition probabilities
    transition_probs: Dict[str, float] = field(default_factory=dict)

    # Recommendations
    recommended_strategies: List[str] = field(default_factory=list)
    risk_adjustment: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "regime": self.regime.value,
            "volatility_regime": self.volatility_regime.value,
            "trend_regime": self.trend_regime.value,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat(),
            "trend_strength": round(self.trend_strength, 2),
            "volatility_percentile": round(self.volatility_percentile, 2),
            "momentum_score": round(self.momentum_score, 2),
            "breadth_score": round(self.breadth_score, 2),
            "transition_probs": self.transition_probs,
            "recommended_strategies": self.recommended_strategies,
            "risk_adjustment": round(self.risk_adjustment, 2),
        }


@dataclass
class RegimeAnalysis:
    current_state: RegimeState
    history: List[RegimeState]
    regime_duration_days: int
    avg_regime_duration: float
    regime_change_probability: float
    indicators: Dict[str, float]

    def to_dict(self) -> Dict:
        return {
            "current_state": self.current_state.to_dict(),
            "history": [h.to_dict() for h in self.history[-10:]],  # Last 10
            "regime_duration_days": self.regime_duration_days,
            "avg_regime_duration": round(self.avg_regime_duration, 1),
            "regime_change_probability": round(self.regime_change_probability, 3),
            "indicators": self.indicators,
        }


class RegimeDetector:
    """
    Market regime detection using multiple indicators and classification.
    Enhanced with SVM classifier for learned regime boundaries.

    The SVM learns from historical indicator-to-regime mappings and provides
    a more nuanced, data-driven classification that can capture non-linear
    relationships between market indicators and regime states.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "regime.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        self.regime_history: List[RegimeState] = []
        self.last_regime_change: datetime = datetime.now()

        # SVM regime classifier
        self.svm_classifier: Optional[SVC] = None if SVM_AVAILABLE else None
        self.svm_scaler: Optional[RobustScaler] = None if SVM_AVAILABLE else None
        self.svm_trained: bool = False
        self._indicator_buffer: List[Dict[str, float]] = []
        self._regime_label_buffer: List[str] = []
        self._svm_model_path = os.path.join(
            os.path.dirname(self.db_path), "regime_svm.joblib"
        )

        # Try to load existing SVM model
        self._try_load_svm()

        # Strategy recommendations by regime
        self.regime_strategies = {
            MarketRegime.BULL_STRONG: ["trend_following", "momentum", "buy_dips"],
            MarketRegime.BULL_WEAK: ["selective_longs", "covered_calls"],
            MarketRegime.BEAR_STRONG: ["short_selling", "puts", "inverse_etfs"],
            MarketRegime.BEAR_WEAK: ["hedged_longs", "cash", "defensive"],
            MarketRegime.RANGING_HIGH_VOL: ["straddles", "strangles", "iron_condors"],
            MarketRegime.RANGING_LOW_VOL: ["iron_condors", "butterflies", "calendars"],
            MarketRegime.CRISIS: ["cash", "puts", "safe_havens", "vix_calls"],
            MarketRegime.RECOVERY: ["value_investing", "sector_rotation", "calls"],
        }

        # Risk adjustments by regime
        self.risk_adjustments = {
            MarketRegime.BULL_STRONG: 1.2,
            MarketRegime.BULL_WEAK: 1.0,
            MarketRegime.BEAR_STRONG: 0.5,
            MarketRegime.BEAR_WEAK: 0.7,
            MarketRegime.RANGING_HIGH_VOL: 0.8,
            MarketRegime.RANGING_LOW_VOL: 1.1,
            MarketRegime.CRISIS: 0.3,
            MarketRegime.RECOVERY: 0.9,
        }

        logger.info(f"RegimeDetector initialized | SVM available: {SVM_AVAILABLE}")

    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regime_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                regime TEXT NOT NULL,
                volatility_regime TEXT NOT NULL,
                trend_regime TEXT NOT NULL,
                confidence REAL,
                trend_strength REAL,
                volatility_percentile REAL,
                momentum_score REAL,
                breadth_score REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regime_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                from_regime TEXT NOT NULL,
                to_regime TEXT NOT NULL,
                duration_days INTEGER
            )
        """)

        conn.commit()
        conn.close()

    def detect_regime(
        self,
        market_data: Dict[str, List[Dict]],
        vix_data: Optional[List[float]] = None
    ) -> RegimeAnalysis:
        """
        Detect current market regime

        Args:
            market_data: Dictionary of symbol -> OHLCV data for major indices
                        Should include SPY, QQQ, IWM, etc.
            vix_data: Optional VIX price history
        """
        # Calculate key indicators
        indicators = self._calculate_indicators(market_data, vix_data)

        # Determine volatility regime
        volatility_regime = self._classify_volatility(
            indicators.get("volatility_percentile", 50),
            indicators.get("vix_level", 20)
        )

        # Determine trend regime
        trend_regime = self._classify_trend(
            indicators.get("trend_strength", 0),
            indicators.get("sma_position", 0)
        )

        # Determine overall market regime (rule-based)
        regime, confidence = self._classify_regime(
            trend_regime, volatility_regime, indicators
        )

        # Try SVM-based regime prediction (overrides rule-based when confident)
        svm_result = self._svm_predict_regime(indicators)
        if svm_result is not None:
            svm_regime_val, svm_confidence = svm_result
            # Use SVM prediction if it's confident enough (>0.5)
            if svm_confidence > 0.5:
                try:
                    svm_regime = MarketRegime(svm_regime_val)
                    # Blend: use SVM when confident, otherwise keep rule-based
                    if svm_confidence > 0.7:
                        regime = svm_regime
                        confidence = svm_confidence
                    else:
                        # Average confidence if they agree, reduce if they disagree
                        if svm_regime == regime:
                            confidence = (confidence + svm_confidence) / 2
                        else:
                            confidence = min(confidence, svm_confidence) * 0.8
                except ValueError:
                    pass  # Invalid regime string, keep rule-based

        # Accumulate training data for SVM (using rule-based regime as label)
        self._indicator_buffer.append(indicators.copy())
        self._regime_label_buffer.append(regime.value)
        # Keep buffer bounded
        if len(self._indicator_buffer) > 5000:
            self._indicator_buffer = self._indicator_buffer[-5000:]
            self._regime_label_buffer = self._regime_label_buffer[-5000:]
        # Auto-train SVM periodically
        if (SVM_AVAILABLE and len(self._indicator_buffer) >= 100 and
                len(self._indicator_buffer) % 100 == 0):
            self.train_svm_classifier()

        # Calculate momentum and breadth
        momentum_score = indicators.get("momentum_score", 0)
        breadth_score = indicators.get("breadth_score", 50)

        # Calculate transition probabilities
        transition_probs = self._calculate_transition_probs(regime)

        # Create regime state
        state = RegimeState(
            regime=regime,
            volatility_regime=volatility_regime,
            trend_regime=trend_regime,
            confidence=confidence,
            trend_strength=indicators.get("trend_strength", 0),
            volatility_percentile=indicators.get("volatility_percentile", 50),
            momentum_score=momentum_score,
            breadth_score=breadth_score,
            transition_probs=transition_probs,
            recommended_strategies=self.regime_strategies.get(regime, []),
            risk_adjustment=self.risk_adjustments.get(regime, 1.0),
        )

        # Check for regime change
        self._check_regime_change(state)

        # Save to history
        self.regime_history.append(state)
        if len(self.regime_history) > 1000:
            self.regime_history = self.regime_history[-1000:]

        self._save_regime_state(state)

        # Calculate analysis metrics
        regime_duration = (datetime.now() - self.last_regime_change).days
        avg_duration = self._calculate_avg_regime_duration()
        change_prob = self._calculate_change_probability(regime_duration, avg_duration)

        analysis = RegimeAnalysis(
            current_state=state,
            history=self.regime_history[-30:],
            regime_duration_days=regime_duration,
            avg_regime_duration=avg_duration,
            regime_change_probability=change_prob,
            indicators=indicators,
        )

        return analysis

    def _calculate_indicators(
        self,
        market_data: Dict[str, List[Dict]],
        vix_data: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """Calculate regime detection indicators"""
        indicators = {}

        # Get SPY data for primary analysis
        spy_data = market_data.get("SPY", [])
        if not spy_data:
            spy_data = market_data.get("spy", [])
        if not spy_data and market_data:
            spy_data = list(market_data.values())[0]

        if spy_data and len(spy_data) >= 50:
            closes = np.array([d.get("close", d.get("Close", 0)) for d in spy_data])

            # Trend strength (slope of 50-day regression)
            if len(closes) >= 50:
                x = np.arange(50)
                slope = np.polyfit(x, closes[-50:], 1)[0]
                avg_price = np.mean(closes[-50:])
                indicators["trend_strength"] = (slope / avg_price) * 100 * 50

            # SMA position
            sma_20 = np.mean(closes[-20:])
            sma_50 = np.mean(closes[-50:])
            sma_200 = np.mean(closes[-200:]) if len(closes) >= 200 else sma_50

            current_price = closes[-1]
            indicators["sma_position"] = (
                (1 if current_price > sma_20 else 0) +
                (1 if current_price > sma_50 else 0) +
                (1 if current_price > sma_200 else 0) +
                (1 if sma_20 > sma_50 else 0) +
                (1 if sma_50 > sma_200 else 0)
            ) / 5 * 100

            # Volatility percentile
            returns = np.diff(closes) / closes[:-1]
            current_vol = np.std(returns[-20:])

            vol_window = 20
            historical_vols = []
            for i in range(vol_window, len(returns)):
                historical_vols.append(np.std(returns[i - vol_window:i]))

            if historical_vols:
                percentile = sum(1 for v in historical_vols if v < current_vol) / len(historical_vols) * 100
                indicators["volatility_percentile"] = percentile
            else:
                indicators["volatility_percentile"] = 50

            # Momentum score (ROC)
            if len(closes) >= 20:
                roc_5 = (closes[-1] / closes[-5] - 1) * 100 if closes[-5] > 0 else 0
                roc_10 = (closes[-1] / closes[-10] - 1) * 100 if closes[-10] > 0 else 0
                roc_20 = (closes[-1] / closes[-20] - 1) * 100 if closes[-20] > 0 else 0
                indicators["momentum_score"] = (roc_5 * 0.5 + roc_10 * 0.3 + roc_20 * 0.2)

            # RSI
            if len(returns) >= 14:
                gains = np.where(returns > 0, returns, 0)
                losses = np.where(returns < 0, -returns, 0)
                avg_gain = np.mean(gains[-14:])
                avg_loss = np.mean(losses[-14:])
                rs = avg_gain / avg_loss if avg_loss > 0 else 100
                indicators["rsi"] = 100 - (100 / (1 + rs))

        # VIX level
        if vix_data and len(vix_data) > 0:
            indicators["vix_level"] = vix_data[-1]
            indicators["vix_sma"] = np.mean(vix_data[-20:]) if len(vix_data) >= 20 else vix_data[-1]
        else:
            indicators["vix_level"] = 20
            indicators["vix_sma"] = 20

        # Market breadth (simplified - based on multiple indices)
        advancing = 0
        total = 0
        for symbol, data in market_data.items():
            if data and len(data) >= 2:
                prev_close = data[-2].get("close", data[-2].get("Close", 0))
                curr_close = data[-1].get("close", data[-1].get("Close", 0))
                if curr_close > prev_close:
                    advancing += 1
                total += 1

        if total > 0:
            indicators["breadth_score"] = (advancing / total) * 100
        else:
            indicators["breadth_score"] = 50

        return indicators

    def _classify_volatility(self, vol_percentile: float, vix_level: float) -> VolatilityRegime:
        """Classify volatility regime"""
        # Combine percentile and VIX
        if vix_level > 40 or vol_percentile > 95:
            return VolatilityRegime.EXTREME
        elif vix_level > 30 or vol_percentile > 85:
            return VolatilityRegime.VERY_HIGH
        elif vix_level > 22 or vol_percentile > 70:
            return VolatilityRegime.HIGH
        elif vix_level > 15 or vol_percentile > 40:
            return VolatilityRegime.NORMAL
        elif vix_level > 12 or vol_percentile > 20:
            return VolatilityRegime.LOW
        else:
            return VolatilityRegime.VERY_LOW

    def _classify_trend(self, trend_strength: float, sma_position: float) -> TrendRegime:
        """Classify trend regime"""
        combined = trend_strength * 0.6 + (sma_position - 50) * 0.4

        if combined > 20:
            return TrendRegime.STRONG_UPTREND
        elif combined > 10:
            return TrendRegime.UPTREND
        elif combined > 3:
            return TrendRegime.WEAK_UPTREND
        elif combined > -3:
            return TrendRegime.SIDEWAYS
        elif combined > -10:
            return TrendRegime.WEAK_DOWNTREND
        elif combined > -20:
            return TrendRegime.DOWNTREND
        else:
            return TrendRegime.STRONG_DOWNTREND

    def _classify_regime(
        self,
        trend: TrendRegime,
        volatility: VolatilityRegime,
        indicators: Dict[str, float]
    ) -> Tuple[MarketRegime, float]:
        """Classify overall market regime"""
        confidence = 0.7  # Base confidence

        vix = indicators.get("vix_level", 20)
        momentum = indicators.get("momentum_score", 0)

        # Crisis detection
        if volatility == VolatilityRegime.EXTREME and vix > 35:
            return MarketRegime.CRISIS, 0.9

        # Recovery detection
        if volatility in [VolatilityRegime.HIGH, VolatilityRegime.VERY_HIGH]:
            if momentum > 5 and trend in [TrendRegime.WEAK_UPTREND, TrendRegime.UPTREND]:
                return MarketRegime.RECOVERY, 0.75

        # Bull markets
        if trend in [TrendRegime.STRONG_UPTREND, TrendRegime.UPTREND]:
            if volatility in [VolatilityRegime.LOW, VolatilityRegime.VERY_LOW, VolatilityRegime.NORMAL]:
                return MarketRegime.BULL_STRONG, 0.85
            else:
                return MarketRegime.BULL_WEAK, 0.7

        if trend == TrendRegime.WEAK_UPTREND:
            return MarketRegime.BULL_WEAK, 0.65

        # Bear markets
        if trend in [TrendRegime.STRONG_DOWNTREND, TrendRegime.DOWNTREND]:
            if volatility in [VolatilityRegime.HIGH, VolatilityRegime.VERY_HIGH]:
                return MarketRegime.BEAR_STRONG, 0.85
            else:
                return MarketRegime.BEAR_WEAK, 0.7

        if trend == TrendRegime.WEAK_DOWNTREND:
            return MarketRegime.BEAR_WEAK, 0.65

        # Ranging markets
        if volatility in [VolatilityRegime.HIGH, VolatilityRegime.VERY_HIGH]:
            return MarketRegime.RANGING_HIGH_VOL, 0.7
        else:
            return MarketRegime.RANGING_LOW_VOL, 0.7

    def _check_regime_change(self, new_state: RegimeState):
        """Check if regime has changed"""
        if not self.regime_history:
            self.last_regime_change = datetime.now()
            return

        last_regime = self.regime_history[-1].regime
        if new_state.regime != last_regime:
            duration = (datetime.now() - self.last_regime_change).days
            self._save_transition(last_regime, new_state.regime, duration)
            self.last_regime_change = datetime.now()
            logger.info(f"Regime change: {last_regime.value} -> {new_state.regime.value}")

    def _calculate_transition_probs(self, current_regime: MarketRegime) -> Dict[str, float]:
        """Calculate transition probabilities based on historical data"""
        # Simplified transition matrix (based on historical research)
        transition_matrix = {
            MarketRegime.BULL_STRONG: {
                "BULL_STRONG": 0.70, "BULL_WEAK": 0.15, "RANGING_LOW_VOL": 0.10,
                "BEAR_WEAK": 0.03, "BEAR_STRONG": 0.01, "CRISIS": 0.01
            },
            MarketRegime.BULL_WEAK: {
                "BULL_STRONG": 0.25, "BULL_WEAK": 0.40, "RANGING_LOW_VOL": 0.15,
                "RANGING_HIGH_VOL": 0.10, "BEAR_WEAK": 0.08, "BEAR_STRONG": 0.02
            },
            MarketRegime.BEAR_STRONG: {
                "BEAR_STRONG": 0.50, "BEAR_WEAK": 0.20, "CRISIS": 0.10,
                "RECOVERY": 0.10, "RANGING_HIGH_VOL": 0.08, "BULL_WEAK": 0.02
            },
            MarketRegime.BEAR_WEAK: {
                "BEAR_WEAK": 0.35, "BEAR_STRONG": 0.15, "RANGING_HIGH_VOL": 0.20,
                "RECOVERY": 0.15, "BULL_WEAK": 0.10, "BULL_STRONG": 0.05
            },
            MarketRegime.RANGING_HIGH_VOL: {
                "RANGING_HIGH_VOL": 0.40, "BEAR_WEAK": 0.20, "BEAR_STRONG": 0.15,
                "BULL_WEAK": 0.15, "CRISIS": 0.05, "RECOVERY": 0.05
            },
            MarketRegime.RANGING_LOW_VOL: {
                "RANGING_LOW_VOL": 0.50, "BULL_WEAK": 0.20, "BULL_STRONG": 0.15,
                "RANGING_HIGH_VOL": 0.10, "BEAR_WEAK": 0.05
            },
            MarketRegime.CRISIS: {
                "CRISIS": 0.40, "BEAR_STRONG": 0.25, "RECOVERY": 0.20,
                "RANGING_HIGH_VOL": 0.10, "BEAR_WEAK": 0.05
            },
            MarketRegime.RECOVERY: {
                "RECOVERY": 0.30, "BULL_WEAK": 0.35, "BULL_STRONG": 0.15,
                "RANGING_HIGH_VOL": 0.10, "BEAR_WEAK": 0.10
            },
        }

        return transition_matrix.get(current_regime, {})

    def _calculate_avg_regime_duration(self) -> float:
        """Calculate average regime duration from history"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT AVG(duration_days) FROM regime_transitions
                WHERE duration_days > 0
            """)
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                return float(result[0])
            return 30.0  # Default
        except Exception:
            return 30.0

    def _calculate_change_probability(self, current_duration: int, avg_duration: float) -> float:
        """Calculate probability of regime change"""
        if avg_duration <= 0:
            return 0.1

        # Exponential distribution assumption
        rate = 1 / avg_duration
        survival_prob = math.exp(-rate * current_duration)

        # Hazard rate increases with duration
        return 1 - survival_prob

    def _save_regime_state(self, state: RegimeState):
        """Save regime state to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO regime_history
                (timestamp, regime, volatility_regime, trend_regime, confidence,
                 trend_strength, volatility_percentile, momentum_score, breadth_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state.timestamp.isoformat(),
                state.regime.value,
                state.volatility_regime.value,
                state.trend_regime.value,
                state.confidence,
                state.trend_strength,
                state.volatility_percentile,
                state.momentum_score,
                state.breadth_score
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving regime state: {e}")

    def _save_transition(self, from_regime: MarketRegime, to_regime: MarketRegime, duration: int):
        """Save regime transition"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO regime_transitions
                (timestamp, from_regime, to_regime, duration_days)
                VALUES (?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                from_regime.value,
                to_regime.value,
                duration
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving regime transition: {e}")

    def _try_load_svm(self):
        """Try to load a previously saved SVM regime model."""
        if not SVM_AVAILABLE:
            return
        try:
            if os.path.exists(self._svm_model_path):
                model_data = joblib.load(self._svm_model_path)
                self.svm_classifier = model_data['classifier']
                self.svm_scaler = model_data['scaler']
                self.svm_trained = True
                logger.info(f"SVM regime model loaded from {self._svm_model_path}")
        except Exception as e:
            logger.debug(f"Could not load SVM regime model: {e}")

    def _indicators_to_feature_vector(self, indicators: Dict[str, float]) -> np.ndarray:
        """Convert indicator dict to a fixed-size feature vector for SVM."""
        keys = [
            'trend_strength', 'sma_position', 'volatility_percentile',
            'momentum_score', 'rsi', 'vix_level', 'vix_sma', 'breadth_score'
        ]
        vector = []
        for key in keys:
            val = indicators.get(key, 0.0)
            if val is None or np.isnan(val) or np.isinf(val):
                val = 0.0
            vector.append(float(val))
        return np.array(vector).reshape(1, -1)

    def train_svm_classifier(self) -> Dict:
        """
        Train SVM regime classifier from accumulated indicator data.
        The SVM learns the mapping from market indicators to regime labels,
        finding optimal decision boundaries between regime states.

        Returns:
            Training metrics
        """
        if not SVM_AVAILABLE:
            return {'error': 'scikit-learn not available'}

        if len(self._indicator_buffer) < 50:
            return {'error': f'Need at least 50 samples, have {len(self._indicator_buffer)}'}

        try:
            # Convert buffers to arrays
            X_list = [self._indicators_to_feature_vector(ind).flatten()
                      for ind in self._indicator_buffer]
            X = np.vstack(X_list)
            y = np.array(self._regime_label_buffer)

            # Scale features
            self.svm_scaler = RobustScaler()
            X_scaled = self.svm_scaler.fit_transform(X)
            X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)

            # Train SVM
            self.svm_classifier = SVC(
                kernel='rbf',
                C=10.0,
                gamma='scale',
                probability=True,
                class_weight='balanced',
                cache_size=500,
                max_iter=5000,
                random_state=42
            )
            self.svm_classifier.fit(X_scaled, y)
            self.svm_trained = True

            # Evaluate
            from sklearn.metrics import accuracy_score
            y_pred = self.svm_classifier.predict(X_scaled)
            accuracy = accuracy_score(y, y_pred)

            # Save model
            self._save_svm_model()

            logger.info(f"SVM regime classifier trained - Accuracy: {accuracy:.4f} | Samples: {len(y)}")
            return {
                'trained': True,
                'accuracy': accuracy,
                'samples': len(y),
                'support_vectors': int(sum(self.svm_classifier.n_support_))
            }

        except Exception as e:
            logger.error(f"SVM regime training failed: {e}")
            return {'error': str(e)}

    def _save_svm_model(self):
        """Save SVM regime model to disk."""
        if not SVM_AVAILABLE or not self.svm_trained:
            return
        try:
            model_data = {
                'classifier': self.svm_classifier,
                'scaler': self.svm_scaler,
            }
            joblib.dump(model_data, self._svm_model_path)
            logger.info(f"SVM regime model saved to {self._svm_model_path}")
        except Exception as e:
            logger.error(f"Failed to save SVM regime model: {e}")

    def _svm_predict_regime(self, indicators: Dict[str, float]) -> Optional[Tuple[str, float]]:
        """
        Use SVM to predict market regime from indicators.

        Returns:
            Tuple of (regime_value_string, confidence) or None
        """
        if not self.svm_trained or self.svm_classifier is None:
            return None

        try:
            X = self._indicators_to_feature_vector(indicators)
            X_scaled = self.svm_scaler.transform(X)
            X_scaled = np.nan_to_num(X_scaled, nan=0.0, posinf=0.0, neginf=0.0)

            proba = self.svm_classifier.predict_proba(X_scaled)[0]
            predicted_class = self.svm_classifier.predict(X_scaled)[0]
            confidence = float(max(proba))

            return predicted_class, confidence
        except Exception as e:
            logger.debug(f"SVM regime prediction error: {e}")
            return None

    def get_regime_history(self, days: int = 90) -> List[Dict]:
        """Get regime history"""
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, regime, volatility_regime, trend_regime,
                       confidence, trend_strength, volatility_percentile
                FROM regime_history
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            """, (since,))

            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "timestamp": row[0],
                    "regime": row[1],
                    "volatility_regime": row[2],
                    "trend_regime": row[3],
                    "confidence": row[4],
                    "trend_strength": row[5],
                    "volatility_percentile": row[6],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting regime history: {e}")
            return []


# Singleton instance
_regime_detector: Optional[RegimeDetector] = None

def get_regime_detector() -> RegimeDetector:
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RegimeDetector()
    return _regime_detector
