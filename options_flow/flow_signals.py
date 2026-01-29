"""
Options Flow Trading Signals
============================
Aggregates options flow data into actionable trading signals.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import logging
from collections import defaultdict
import statistics

from .unusual_activity import (
    UnusualActivityDetector, UnusualActivity, OptionsActivityType,
    OptionsTrade, TradeSide
)
from .dark_pool import DarkPoolMonitor, BlockTrade, PrintSentiment
from .gamma_exposure import GammaExposureCalculator, GEXProfile

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of flow-based signals."""
    BULLISH_FLOW = "bullish_flow"
    BEARISH_FLOW = "bearish_flow"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    GAMMA_SQUEEZE = "gamma_squeeze"
    PUT_WALL = "put_wall"
    CALL_WALL = "call_wall"
    SMART_MONEY = "smart_money"
    UNUSUAL_SWEEP = "unusual_sweep"
    DARK_POOL_DIVERGENCE = "dark_pool_divergence"


class SignalStrength(Enum):
    """Signal strength levels."""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    EXTREME = 4


class SignalTimeframe(Enum):
    """Expected signal duration."""
    INTRADAY = "intraday"
    SWING = "swing"  # 2-5 days
    POSITION = "position"  # 1-4 weeks


@dataclass
class FlowSignal:
    """Trading signal derived from options flow."""
    symbol: str
    signal_type: SignalType
    direction: str  # "bullish" or "bearish"
    strength: SignalStrength
    timeframe: SignalTimeframe
    confidence: float  # 0-100
    
    # Price levels
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    
    # Context
    reasoning: str = ""
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    related_activities: List[UnusualActivity] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    @property
    def risk_reward(self) -> Optional[float]:
        """Calculate risk/reward ratio."""
        if not all([self.entry_price, self.target_price, self.stop_price]):
            return None
        risk = abs(self.entry_price - self.stop_price)
        reward = abs(self.target_price - self.entry_price)
        return reward / risk if risk > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "direction": self.direction,
            "strength": self.strength.value,
            "timeframe": self.timeframe.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_price": self.stop_price,
            "risk_reward": self.risk_reward,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class SignalConfig:
    """Configuration for signal generation."""
    # Flow thresholds
    min_premium_for_signal: float = 100_000
    bullish_call_ratio_threshold: float = 1.5
    bearish_put_ratio_threshold: float = 1.5
    
    # Confidence requirements
    min_confidence_weak: float = 30
    min_confidence_moderate: float = 50
    min_confidence_strong: float = 70
    min_confidence_extreme: float = 85
    
    # Aggregation
    flow_aggregation_minutes: int = 60
    signal_cooldown_minutes: int = 15
    
    # Risk parameters
    default_stop_pct: float = 0.02  # 2%
    default_target_multiplier: float = 2.0  # 2:1 R:R


class OptionsFlowSignals:
    """
    Generates trading signals from aggregated options flow data.
    
    Combines:
    - Unusual activity detection
    - Dark pool analysis
    - Gamma exposure positioning
    - Put/call ratios
    - Smart money indicators
    """
    
    def __init__(
        self,
        unusual_detector: Optional[UnusualActivityDetector] = None,
        dark_pool_monitor: Optional[DarkPoolMonitor] = None,
        gex_calculator: Optional[GammaExposureCalculator] = None,
        config: Optional[SignalConfig] = None,
    ):
        self.unusual_detector = unusual_detector or UnusualActivityDetector()
        self.dark_pool_monitor = dark_pool_monitor or DarkPoolMonitor()
        self.gex_calculator = gex_calculator or GammaExposureCalculator()
        self.config = config or SignalConfig()
        
        self._flow_buffer: Dict[str, List[UnusualActivity]] = defaultdict(list)
        self._signal_history: Dict[str, List[FlowSignal]] = defaultdict(list)
        self._callbacks: List[Callable[[FlowSignal], None]] = []
        
    def register_callback(self, callback: Callable[[FlowSignal], None]):
        """Register callback for new signals."""
        self._callbacks.append(callback)
        
    def _notify(self, signal: FlowSignal):
        """Notify callbacks of new signal."""
        for cb in self._callbacks:
            try:
                cb(signal)
            except Exception as e:
                logger.error(f"Signal callback error: {e}")
    
    async def process_unusual_activity(
        self,
        activity: UnusualActivity,
        spot_price: float,
    ) -> Optional[FlowSignal]:
        """
        Process unusual activity and potentially generate signal.
        """
        symbol = activity.trade.contract.underlying
        
        # Buffer activity
        self._flow_buffer[symbol].append(activity)
        self._cleanup_buffer()
        
        # Check cooldown
        if self._in_cooldown(symbol, activity.activity_type):
            return None
            
        # Analyze aggregated flow
        signal = await self._analyze_flow(symbol, spot_price)
        
        if signal:
            self._signal_history[symbol].append(signal)
            self._notify(signal)
            
        return signal
    
    async def _analyze_flow(
        self,
        symbol: str,
        spot_price: float,
    ) -> Optional[FlowSignal]:
        """Analyze buffered flow for signal generation."""
        activities = self._get_recent_activities(symbol)
        
        if not activities:
            return None
        
        # Yield to event loop for cooperative multitasking
        await asyncio.sleep(0)
            
        # Calculate flow metrics
        metrics = self._calculate_flow_metrics(activities)
        
        # Check for various signal types
        signal = None
        
        # Bullish/Bearish flow
        if flow_signal := self._check_directional_flow(symbol, spot_price, metrics, activities):
            signal = flow_signal
            
        # Unusual sweep cluster
        elif sweep_signal := self._check_sweep_cluster(symbol, spot_price, activities):
            signal = sweep_signal
            
        # Smart money detection
        elif smart_signal := self._check_smart_money(symbol, spot_price, activities):
            signal = smart_signal
            
        return signal
    
    def _calculate_flow_metrics(
        self,
        activities: List[UnusualActivity],
    ) -> Dict[str, Any]:
        """Calculate aggregate flow metrics."""
        total_premium = sum(a.trade.premium for a in activities)
        
        bullish = [a for a in activities if a.is_bullish]
        bearish = [a for a in activities if a.is_bearish]
        
        bullish_premium = sum(a.trade.premium for a in bullish)
        bearish_premium = sum(a.trade.premium for a in bearish)
        
        # By activity type
        by_type = defaultdict(list)
        for a in activities:
            by_type[a.activity_type].append(a)
            
        # Score distribution
        scores = [a.score for a in activities]
        
        return {
            "total_count": len(activities),
            "total_premium": total_premium,
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "bullish_premium": bullish_premium,
            "bearish_premium": bearish_premium,
            "premium_ratio": bullish_premium / max(1, bearish_premium),
            "by_type": {k.value: len(v) for k, v in by_type.items()},
            "avg_score": statistics.mean(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "sweeps": len(by_type.get(OptionsActivityType.SWEEP, [])),
            "golden_sweeps": len(by_type.get(OptionsActivityType.GOLDEN_SWEEP, [])),
            "whales": len(by_type.get(OptionsActivityType.WHALE_ALERT, [])),
        }
    
    def _check_directional_flow(
        self,
        symbol: str,
        spot_price: float,
        metrics: Dict[str, Any],
        activities: List[UnusualActivity],
    ) -> Optional[FlowSignal]:
        """Check for directional (bullish/bearish) flow signal."""
        total_premium = metrics["total_premium"]
        
        if total_premium < self.config.min_premium_for_signal:
            return None
            
        ratio = metrics["premium_ratio"]
        
        # Strong bullish flow
        if ratio >= self.config.bullish_call_ratio_threshold:
            direction = "bullish"
            confidence = min(100, 50 + (ratio - 1) * 20 + metrics["avg_score"] * 0.3)
            
        # Strong bearish flow  
        elif ratio <= 1 / self.config.bearish_put_ratio_threshold:
            direction = "bearish"
            confidence = min(100, 50 + (1/ratio - 1) * 20 + metrics["avg_score"] * 0.3)
            
        else:
            return None
            
        # Determine strength
        strength = self._confidence_to_strength(confidence)
        
        # Calculate price targets
        move_pct = 0.01 * strength.value  # 1-4% based on strength
        stop_pct = self.config.default_stop_pct
        
        if direction == "bullish":
            target = spot_price * (1 + move_pct * self.config.default_target_multiplier)
            stop = spot_price * (1 - stop_pct)
        else:
            target = spot_price * (1 - move_pct * self.config.default_target_multiplier)
            stop = spot_price * (1 + stop_pct)
            
        # Timeframe based on DTE of underlying flow
        avg_dte = statistics.mean([
            a.trade.contract.dte for a in activities if a.trade.contract.dte > 0
        ]) if activities else 7
        
        if avg_dte <= 7:
            timeframe = SignalTimeframe.INTRADAY
        elif avg_dte <= 21:
            timeframe = SignalTimeframe.SWING
        else:
            timeframe = SignalTimeframe.POSITION
            
        return FlowSignal(
            symbol=symbol,
            signal_type=SignalType.BULLISH_FLOW if direction == "bullish" else SignalType.BEARISH_FLOW,
            direction=direction,
            strength=strength,
            timeframe=timeframe,
            confidence=confidence,
            entry_price=spot_price,
            target_price=round(target, 2),
            stop_price=round(stop, 2),
            reasoning=f"Strong {direction} flow: ${metrics['bullish_premium']:,.0f} bullish vs "
                     f"${metrics['bearish_premium']:,.0f} bearish ({ratio:.1f}:1 ratio). "
                     f"{metrics['total_count']} unusual activities, avg score {metrics['avg_score']:.0f}.",
            supporting_data=metrics,
            related_activities=activities[:5],  # Top 5
            expires_at=datetime.now() + timedelta(days=avg_dte),
        )
    
    def _check_sweep_cluster(
        self,
        symbol: str,
        spot_price: float,
        activities: List[UnusualActivity],
    ) -> Optional[FlowSignal]:
        """Check for clustered sweep activity."""
        sweeps = [
            a for a in activities 
            if a.activity_type in (OptionsActivityType.SWEEP, OptionsActivityType.GOLDEN_SWEEP)
        ]
        
        if len(sweeps) < 3:
            return None
            
        # Check if sweeps are same direction
        bullish_sweeps = [s for s in sweeps if s.is_bullish]
        bearish_sweeps = [s for s in sweeps if s.is_bearish]
        
        if len(bullish_sweeps) >= 3 and len(bullish_sweeps) > len(bearish_sweeps) * 2:
            direction = "bullish"
            target_sweeps = bullish_sweeps
        elif len(bearish_sweeps) >= 3 and len(bearish_sweeps) > len(bullish_sweeps) * 2:
            direction = "bearish"
            target_sweeps = bearish_sweeps
        else:
            return None
            
        total_premium = sum(s.trade.premium for s in target_sweeps)
        avg_score = statistics.mean(s.score for s in target_sweeps)
        
        # Golden sweeps are extra significant
        golden_count = len([
            s for s in target_sweeps 
            if s.activity_type == OptionsActivityType.GOLDEN_SWEEP
        ])
        
        confidence = min(100, 60 + len(target_sweeps) * 5 + golden_count * 10 + avg_score * 0.2)
        strength = self._confidence_to_strength(confidence)
        
        return FlowSignal(
            symbol=symbol,
            signal_type=SignalType.UNUSUAL_SWEEP,
            direction=direction,
            strength=strength,
            timeframe=SignalTimeframe.SWING,
            confidence=confidence,
            entry_price=spot_price,
            reasoning=f"Sweep cluster: {len(target_sweeps)} {direction} sweeps "
                     f"(${total_premium:,.0f} premium, {golden_count} golden sweeps). "
                     f"Aggressive institutional positioning detected.",
            supporting_data={
                "sweep_count": len(target_sweeps),
                "golden_sweeps": golden_count,
                "total_premium": total_premium,
            },
            related_activities=target_sweeps[:5],
        )
    
    def _check_smart_money(
        self,
        symbol: str,
        spot_price: float,
        activities: List[UnusualActivity],
    ) -> Optional[FlowSignal]:
        """Detect smart money patterns."""
        # Smart money indicators:
        # 1. Large premium + short DTE + OTM (conviction bet)
        # 2. Repeat buying at same strike (accumulation)
        # 3. Opening positions in illiquid strikes
        
        smart_activities = []
        
        for a in activities:
            is_smart = False
            
            # Large OTM short-dated (high conviction)
            if (a.activity_type == OptionsActivityType.GOLDEN_SWEEP and 
                a.trade.premium >= 250_000):
                is_smart = True
                
            # Repeat buyer (accumulation)
            elif (a.activity_type == OptionsActivityType.REPEAT_BUYER and
                  a.metadata.get("num_trades", 0) >= 4):
                is_smart = True
                
            # Whale in unusual strike
            elif (a.activity_type == OptionsActivityType.WHALE_ALERT and
                  a.trade.open_interest < 1000):  # Low OI = unusual strike
                is_smart = True
                
            if is_smart:
                smart_activities.append(a)
                
        if len(smart_activities) < 2:
            return None
            
        # Determine direction
        bullish = [a for a in smart_activities if a.is_bullish]
        bearish = [a for a in smart_activities if a.is_bearish]
        
        if len(bullish) > len(bearish):
            direction = "bullish"
            primary = bullish
        else:
            direction = "bearish"
            primary = bearish
            
        total_premium = sum(a.trade.premium for a in primary)
        confidence = min(100, 70 + len(primary) * 10)
        
        return FlowSignal(
            symbol=symbol,
            signal_type=SignalType.SMART_MONEY,
            direction=direction,
            strength=SignalStrength.STRONG,
            timeframe=SignalTimeframe.SWING,
            confidence=confidence,
            entry_price=spot_price,
            reasoning=f"Smart money detected: {len(primary)} high-conviction {direction} trades "
                     f"totaling ${total_premium:,.0f}. Unusual positioning suggests informed flow.",
            supporting_data={
                "smart_activity_count": len(smart_activities),
                "total_premium": total_premium,
            },
            related_activities=primary[:5],
        )
    
    def generate_gamma_signal(
        self,
        symbol: str,
        spot_price: float,
        gex_profile: GEXProfile,
    ) -> Optional[FlowSignal]:
        """Generate signal from gamma exposure analysis."""
        # Gamma squeeze potential
        if not gex_profile.is_positive_gamma and gex_profile.gamma_flip_price:
            # Negative gamma + approaching flip = potential squeeze
            distance_to_flip = abs(spot_price - gex_profile.gamma_flip_price) / spot_price
            
            if distance_to_flip < 0.03:  # Within 3% of flip
                direction = "bullish" if spot_price < gex_profile.gamma_flip_price else "bearish"
                
                return FlowSignal(
                    symbol=symbol,
                    signal_type=SignalType.GAMMA_SQUEEZE,
                    direction=direction,
                    strength=SignalStrength.STRONG,
                    timeframe=SignalTimeframe.INTRADAY,
                    confidence=75,
                    entry_price=spot_price,
                    target_price=gex_profile.gamma_flip_price,
                    reasoning=f"Gamma squeeze setup: Price near flip level (${gex_profile.gamma_flip_price:.2f}). "
                             f"Negative gamma regime will amplify moves through the flip point.",
                    supporting_data=gex_profile.to_dict(),
                )
                
        # Put wall (support)
        if gex_profile.total_put_gex > gex_profile.total_call_gex * 2:
            key_strike = min(gex_profile.key_strikes) if gex_profile.key_strikes else None
            
            if key_strike and key_strike < spot_price:
                return FlowSignal(
                    symbol=symbol,
                    signal_type=SignalType.PUT_WALL,
                    direction="bullish",
                    strength=SignalStrength.MODERATE,
                    timeframe=SignalTimeframe.SWING,
                    confidence=60,
                    entry_price=spot_price,
                    stop_price=key_strike * 0.98,
                    reasoning=f"Put wall support at ${key_strike:.2f}. "
                             f"High put gamma creates dealer buying on dips.",
                    supporting_data=gex_profile.to_dict(),
                )
                
        # Call wall (resistance)
        if gex_profile.total_call_gex > gex_profile.total_put_gex * 2:
            key_strike = max(gex_profile.key_strikes) if gex_profile.key_strikes else None
            
            if key_strike and key_strike > spot_price:
                return FlowSignal(
                    symbol=symbol,
                    signal_type=SignalType.CALL_WALL,
                    direction="bearish",
                    strength=SignalStrength.MODERATE,
                    timeframe=SignalTimeframe.SWING,
                    confidence=60,
                    entry_price=spot_price,
                    stop_price=key_strike * 1.02,
                    reasoning=f"Call wall resistance at ${key_strike:.2f}. "
                             f"High call gamma creates dealer selling on rips.",
                    supporting_data=gex_profile.to_dict(),
                )
                
        return None
    
    def generate_dark_pool_signal(
        self,
        symbol: str,
        spot_price: float,
        accumulation_data: Dict[str, Any],
    ) -> Optional[FlowSignal]:
        """Generate signal from dark pool analysis."""
        signal_type = accumulation_data.get("signal")
        
        if signal_type == "accumulation":
            return FlowSignal(
                symbol=symbol,
                signal_type=SignalType.ACCUMULATION,
                direction="bullish",
                strength=self._strength_from_pct(accumulation_data.get("strength", 0)),
                timeframe=SignalTimeframe.POSITION,
                confidence=min(100, 50 + accumulation_data.get("strength", 0)),
                entry_price=spot_price,
                reasoning=f"Dark pool accumulation: {accumulation_data.get('bullish_pct', 0):.0f}% bullish flow, "
                         f"${accumulation_data.get('total_value', 0)/1e6:.1f}M total volume. "
                         f"Institutional buying above VWAP.",
                supporting_data=accumulation_data,
            )
            
        elif signal_type == "distribution":
            return FlowSignal(
                symbol=symbol,
                signal_type=SignalType.DISTRIBUTION,
                direction="bearish",
                strength=self._strength_from_pct(accumulation_data.get("strength", 0)),
                timeframe=SignalTimeframe.POSITION,
                confidence=min(100, 50 + accumulation_data.get("strength", 0)),
                entry_price=spot_price,
                reasoning=f"Dark pool distribution: {100 - accumulation_data.get('bullish_pct', 100):.0f}% bearish flow, "
                         f"${accumulation_data.get('total_value', 0)/1e6:.1f}M total volume. "
                         f"Institutional selling below VWAP.",
                supporting_data=accumulation_data,
            )
            
        return None
    
    def _confidence_to_strength(self, confidence: float) -> SignalStrength:
        """Convert confidence score to strength level."""
        if confidence >= self.config.min_confidence_extreme:
            return SignalStrength.EXTREME
        elif confidence >= self.config.min_confidence_strong:
            return SignalStrength.STRONG
        elif confidence >= self.config.min_confidence_moderate:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
            
    def _strength_from_pct(self, pct: float) -> SignalStrength:
        """Convert percentage to strength."""
        if pct >= 100:
            return SignalStrength.EXTREME
        elif pct >= 50:
            return SignalStrength.STRONG
        elif pct >= 25:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
    
    def _get_recent_activities(self, symbol: str) -> List[UnusualActivity]:
        """Get activities within aggregation window."""
        cutoff = datetime.now() - timedelta(minutes=self.config.flow_aggregation_minutes)
        return [
            a for a in self._flow_buffer.get(symbol, [])
            if a.timestamp > cutoff
        ]
    
    def _in_cooldown(self, symbol: str, activity_type: OptionsActivityType) -> bool:
        """Check if we're in cooldown for this symbol/type."""
        cutoff = datetime.now() - timedelta(minutes=self.config.signal_cooldown_minutes)
        
        recent_signals = [
            s for s in self._signal_history.get(symbol, [])
            if s.created_at > cutoff
        ]
        
        return len(recent_signals) > 0
    
    def _cleanup_buffer(self):
        """Remove old activities from buffer."""
        cutoff = datetime.now() - timedelta(hours=4)
        
        for symbol in list(self._flow_buffer.keys()):
            self._flow_buffer[symbol] = [
                a for a in self._flow_buffer[symbol]
                if a.timestamp > cutoff
            ]
            if not self._flow_buffer[symbol]:
                del self._flow_buffer[symbol]
    
    def get_active_signals(
        self,
        symbol: Optional[str] = None,
        min_confidence: float = 0,
    ) -> List[FlowSignal]:
        """Get currently active (non-expired) signals."""
        now = datetime.now()
        signals = []
        
        for sym, sym_signals in self._signal_history.items():
            if symbol and sym != symbol:
                continue
                
            for s in sym_signals:
                if s.expires_at and s.expires_at < now:
                    continue
                if s.confidence < min_confidence:
                    continue
                signals.append(s)
                
        return sorted(signals, key=lambda s: s.confidence, reverse=True)
    
    def get_signal_summary(self) -> Dict[str, Any]:
        """Get summary of recent signals."""
        active = self.get_active_signals()
        
        bullish = [s for s in active if s.direction == "bullish"]
        bearish = [s for s in active if s.direction == "bearish"]
        
        by_type = defaultdict(int)
        for s in active:
            by_type[s.signal_type.value] += 1
            
        return {
            "total_active": len(active),
            "bullish": len(bullish),
            "bearish": len(bearish),
            "by_type": dict(by_type),
            "avg_confidence": statistics.mean(s.confidence for s in active) if active else 0,
            "strongest": active[0].to_dict() if active else None,
        }
