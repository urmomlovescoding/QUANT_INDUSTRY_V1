"""
Unusual Options Activity Detector
=================================
Identifies abnormal options volume, sweeps, and unusual positioning.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import logging
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class OptionsActivityType(Enum):
    """Classification of unusual options activity."""
    SWEEP = "sweep"  # Aggressive multi-exchange sweep
    BLOCK = "block"  # Large single block trade
    UNUSUAL_VOLUME = "unusual_volume"  # Volume >> average
    REPEAT_BUYER = "repeat_buyer"  # Same strike hit multiple times
    OPENING_POSITION = "opening_position"  # New large position
    GOLDEN_SWEEP = "golden_sweep"  # Large OTM sweep with short expiry
    WHALE_ALERT = "whale_alert"  # Massive single order
    SPLIT_STRIKE = "split_strike"  # Spread or combo detected


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


class TradeSide(Enum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


@dataclass
class OptionsContract:
    """Represents an options contract."""
    symbol: str
    underlying: str
    strike: float
    expiry: datetime
    option_type: OptionType
    
    @property
    def dte(self) -> int:
        """Days to expiration."""
        return max(0, (self.expiry - datetime.now()).days)
    
    @property
    def is_weekly(self) -> bool:
        """Check if this is a weekly option."""
        return self.dte <= 7
    
    def moneyness(self, spot_price: float) -> float:
        """Calculate moneyness (strike / spot)."""
        return self.strike / spot_price if spot_price > 0 else 0
    
    def is_otm(self, spot_price: float, threshold: float = 0.02) -> bool:
        """Check if option is out of the money."""
        if self.option_type == OptionType.CALL:
            return self.strike > spot_price * (1 + threshold)
        else:
            return self.strike < spot_price * (1 - threshold)


@dataclass
class OptionsTrade:
    """Single options trade record."""
    contract: OptionsContract
    timestamp: datetime
    price: float
    size: int
    premium: float  # price * size * 100
    side: TradeSide
    exchange: str
    condition: str = ""  # Trade condition codes
    spot_price: float = 0.0
    iv: float = 0.0  # Implied volatility
    delta: float = 0.0
    open_interest: int = 0
    volume_prior: int = 0  # Volume before this trade
    
    @property
    def notional(self) -> float:
        """Notional value of underlying controlled."""
        return self.size * 100 * self.spot_price
    
    @property
    def is_above_ask(self) -> bool:
        """Trade executed at or above ask (aggressive buy)."""
        return "AA" in self.condition or "A" in self.condition
    
    @property
    def is_below_bid(self) -> bool:
        """Trade executed at or below bid (aggressive sell)."""
        return "BB" in self.condition or "B" in self.condition


@dataclass
class UnusualActivity:
    """Detected unusual options activity."""
    activity_type: OptionsActivityType
    trade: OptionsTrade
    score: float  # 0-100 significance score
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    related_trades: List[OptionsTrade] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def is_bullish(self) -> bool:
        """Determine if activity is bullish."""
        if self.trade.contract.option_type == OptionType.CALL:
            return self.trade.side == TradeSide.BUY
        else:
            return self.trade.side == TradeSide.SELL
    
    @property
    def is_bearish(self) -> bool:
        """Determine if activity is bearish."""
        return not self.is_bullish
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "activity_type": self.activity_type.value,
            "symbol": self.trade.contract.underlying,
            "strike": self.trade.contract.strike,
            "expiry": self.trade.contract.expiry.isoformat(),
            "option_type": self.trade.contract.option_type.value,
            "premium": self.trade.premium,
            "size": self.trade.size,
            "score": self.score,
            "description": self.description,
            "is_bullish": self.is_bullish,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DetectorConfig:
    """Configuration for unusual activity detection."""
    # Volume thresholds
    min_premium: float = 25_000  # Minimum premium to consider
    unusual_volume_multiplier: float = 3.0  # Volume vs avg OI
    whale_premium_threshold: float = 1_000_000  # $1M+ premium
    
    # Sweep detection
    sweep_time_window_seconds: int = 60  # Time window for sweep detection
    sweep_min_exchanges: int = 2  # Minimum exchanges for sweep
    sweep_min_contracts: int = 100
    
    # Golden sweep (OTM + short expiry + large)
    golden_sweep_max_dte: int = 14
    golden_sweep_min_otm_pct: float = 0.05  # 5% OTM
    golden_sweep_min_premium: float = 100_000
    
    # Repeat buyer detection
    repeat_buyer_time_window_minutes: int = 30
    repeat_buyer_min_hits: int = 3
    
    # Score weights
    weight_premium: float = 0.3
    weight_volume_ratio: float = 0.25
    weight_dte: float = 0.15
    weight_otm: float = 0.15
    weight_side_confidence: float = 0.15


class UnusualActivityDetector:
    """
    Detects unusual options activity patterns.
    
    Monitors options flow for:
    - Sweeps (aggressive multi-exchange orders)
    - Unusual volume spikes
    - Large block trades
    - Repeat buying patterns
    - Golden sweeps (OTM + short expiry)
    - Whale alerts
    """
    
    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()
        self._trade_buffer: Dict[str, List[OptionsTrade]] = defaultdict(list)
        self._volume_history: Dict[str, List[int]] = defaultdict(list)
        self._callbacks: List[Callable[[UnusualActivity], None]] = []
        self._running = False
        
    def register_callback(self, callback: Callable[[UnusualActivity], None]):
        """Register callback for unusual activity alerts."""
        self._callbacks.append(callback)
        
    def _notify(self, activity: UnusualActivity):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(activity)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    async def process_trade(self, trade: OptionsTrade) -> List[UnusualActivity]:
        """
        Process a single trade and detect unusual activity.
        
        Args:
            trade: The options trade to analyze
            
        Returns:
            List of detected unusual activities
        """
        if trade.premium < self.config.min_premium:
            return []
            
        activities = []
        
        # Buffer trade for pattern detection
        key = f"{trade.contract.underlying}:{trade.contract.strike}:{trade.contract.expiry.date()}"
        self._trade_buffer[key].append(trade)
        self._cleanup_buffer()
        
        # Run all detectors
        if whale := self._detect_whale(trade):
            activities.append(whale)
            
        if sweep := self._detect_sweep(trade, key):
            activities.append(sweep)
            
        if golden := self._detect_golden_sweep(trade):
            activities.append(golden)
            
        if unusual_vol := self._detect_unusual_volume(trade):
            activities.append(unusual_vol)
            
        if repeat := self._detect_repeat_buyer(key):
            activities.append(repeat)
        
        # Notify callbacks
        for activity in activities:
            self._notify(activity)
            
        return activities
    
    def _detect_whale(self, trade: OptionsTrade) -> Optional[UnusualActivity]:
        """Detect whale-sized trades."""
        if trade.premium < self.config.whale_premium_threshold:
            return None
            
        score = min(100, 50 + (trade.premium / self.config.whale_premium_threshold) * 25)
        
        return UnusualActivity(
            activity_type=OptionsActivityType.WHALE_ALERT,
            trade=trade,
            score=score,
            description=f"🐋 WHALE: ${trade.premium:,.0f} premium on {trade.contract.underlying} "
                       f"${trade.contract.strike} {trade.contract.option_type.value.upper()} "
                       f"exp {trade.contract.expiry.strftime('%m/%d')}",
            metadata={
                "premium_millions": trade.premium / 1_000_000,
                "contracts": trade.size,
                "notional": trade.notional,
            }
        )
    
    def _detect_sweep(self, trade: OptionsTrade, key: str) -> Optional[UnusualActivity]:
        """Detect multi-exchange sweeps."""
        recent_trades = self._get_recent_trades(
            key, 
            seconds=self.config.sweep_time_window_seconds
        )
        
        if len(recent_trades) < 2:
            return None
            
        exchanges = set(t.exchange for t in recent_trades)
        if len(exchanges) < self.config.sweep_min_exchanges:
            return None
            
        total_contracts = sum(t.size for t in recent_trades)
        if total_contracts < self.config.sweep_min_contracts:
            return None
            
        total_premium = sum(t.premium for t in recent_trades)
        
        # Check if mostly aggressive buys (above ask)
        aggressive_buys = sum(1 for t in recent_trades if t.is_above_ask)
        is_aggressive = aggressive_buys > len(recent_trades) / 2
        
        if not is_aggressive:
            return None
            
        score = self._calculate_score(trade, volume_ratio=total_contracts / 100)
        
        return UnusualActivity(
            activity_type=OptionsActivityType.SWEEP,
            trade=trade,
            score=score,
            description=f"🧹 SWEEP: {total_contracts} contracts across {len(exchanges)} exchanges, "
                       f"${total_premium:,.0f} premium on {trade.contract.underlying} "
                       f"${trade.contract.strike} {trade.contract.option_type.value.upper()}",
            metadata={
                "exchanges": list(exchanges),
                "total_contracts": total_contracts,
                "total_premium": total_premium,
                "num_trades": len(recent_trades),
            },
            related_trades=recent_trades,
        )
    
    def _detect_golden_sweep(self, trade: OptionsTrade) -> Optional[UnusualActivity]:
        """Detect golden sweeps (OTM + short expiry + large)."""
        if trade.premium < self.config.golden_sweep_min_premium:
            return None
            
        if trade.contract.dte > self.config.golden_sweep_max_dte:
            return None
            
        if not trade.contract.is_otm(trade.spot_price, self.config.golden_sweep_min_otm_pct):
            return None
            
        if not trade.is_above_ask:
            return None
            
        otm_pct = abs(1 - trade.contract.moneyness(trade.spot_price)) * 100
        score = min(100, 70 + (trade.premium / self.config.golden_sweep_min_premium) * 15)
        
        return UnusualActivity(
            activity_type=OptionsActivityType.GOLDEN_SWEEP,
            trade=trade,
            score=score,
            description=f"🌟 GOLDEN SWEEP: ${trade.premium:,.0f} on {trade.contract.underlying} "
                       f"${trade.contract.strike} {trade.contract.option_type.value.upper()} "
                       f"({otm_pct:.1f}% OTM, {trade.contract.dte} DTE)",
            metadata={
                "dte": trade.contract.dte,
                "otm_percent": otm_pct,
                "is_weekly": trade.contract.is_weekly,
            }
        )
    
    def _detect_unusual_volume(self, trade: OptionsTrade) -> Optional[UnusualActivity]:
        """Detect unusual volume relative to open interest."""
        if trade.open_interest <= 0:
            return None
            
        volume_ratio = (trade.volume_prior + trade.size) / trade.open_interest
        
        if volume_ratio < self.config.unusual_volume_multiplier:
            return None
            
        score = self._calculate_score(trade, volume_ratio=volume_ratio)
        
        return UnusualActivity(
            activity_type=OptionsActivityType.UNUSUAL_VOLUME,
            trade=trade,
            score=score,
            description=f"📊 UNUSUAL VOLUME: {volume_ratio:.1f}x OI on {trade.contract.underlying} "
                       f"${trade.contract.strike} {trade.contract.option_type.value.upper()} "
                       f"(Vol: {trade.volume_prior + trade.size}, OI: {trade.open_interest})",
            metadata={
                "volume_ratio": volume_ratio,
                "volume": trade.volume_prior + trade.size,
                "open_interest": trade.open_interest,
            }
        )
    
    def _detect_repeat_buyer(self, key: str) -> Optional[UnusualActivity]:
        """Detect repeat buying at same strike."""
        recent_trades = self._get_recent_trades(
            key,
            seconds=self.config.repeat_buyer_time_window_minutes * 60
        )
        
        # Filter for buys only
        buys = [t for t in recent_trades if t.side == TradeSide.BUY or t.is_above_ask]
        
        if len(buys) < self.config.repeat_buyer_min_hits:
            return None
            
        total_premium = sum(t.premium for t in buys)
        total_contracts = sum(t.size for t in buys)
        
        latest = buys[-1]
        score = min(100, 50 + len(buys) * 10)
        
        return UnusualActivity(
            activity_type=OptionsActivityType.REPEAT_BUYER,
            trade=latest,
            score=score,
            description=f"🔄 REPEAT BUYER: {len(buys)} hits on {latest.contract.underlying} "
                       f"${latest.contract.strike} {latest.contract.option_type.value.upper()}, "
                       f"${total_premium:,.0f} total premium",
            metadata={
                "num_trades": len(buys),
                "total_premium": total_premium,
                "total_contracts": total_contracts,
                "time_span_minutes": self.config.repeat_buyer_time_window_minutes,
            },
            related_trades=buys,
        )
    
    def _get_recent_trades(self, key: str, seconds: int) -> List[OptionsTrade]:
        """Get trades within time window."""
        cutoff = datetime.now() - timedelta(seconds=seconds)
        return [t for t in self._trade_buffer[key] if t.timestamp > cutoff]
    
    def _cleanup_buffer(self):
        """Remove old trades from buffer."""
        cutoff = datetime.now() - timedelta(hours=1)
        for key in list(self._trade_buffer.keys()):
            self._trade_buffer[key] = [
                t for t in self._trade_buffer[key] if t.timestamp > cutoff
            ]
            if not self._trade_buffer[key]:
                del self._trade_buffer[key]
    
    def _calculate_score(
        self, 
        trade: OptionsTrade, 
        volume_ratio: float = 1.0
    ) -> float:
        """Calculate significance score for unusual activity."""
        score = 0.0
        
        # Premium contribution (log scale)
        premium_score = min(100, np.log10(max(1, trade.premium / 10000)) * 30)
        score += premium_score * self.config.weight_premium
        
        # Volume ratio contribution
        vol_score = min(100, volume_ratio * 20)
        score += vol_score * self.config.weight_volume_ratio
        
        # DTE contribution (shorter = more significant)
        if trade.contract.dte <= 7:
            dte_score = 100
        elif trade.contract.dte <= 14:
            dte_score = 75
        elif trade.contract.dte <= 30:
            dte_score = 50
        else:
            dte_score = 25
        score += dte_score * self.config.weight_dte
        
        # OTM contribution
        if trade.spot_price > 0:
            otm_pct = abs(1 - trade.contract.moneyness(trade.spot_price))
            otm_score = min(100, otm_pct * 500)  # 20% OTM = 100 score
            score += otm_score * self.config.weight_otm
        
        # Side confidence
        if trade.is_above_ask or trade.is_below_bid:
            score += 100 * self.config.weight_side_confidence
        elif trade.side != TradeSide.UNKNOWN:
            score += 50 * self.config.weight_side_confidence
            
        return min(100, score)
    
    async def scan_symbol(
        self, 
        symbol: str,
        trades: List[OptionsTrade]
    ) -> List[UnusualActivity]:
        """
        Scan all trades for a symbol and return unusual activity.
        
        Args:
            symbol: Underlying symbol
            trades: List of trades to analyze
            
        Returns:
            List of all detected unusual activities
        """
        all_activities = []
        
        # Sort by timestamp
        sorted_trades = sorted(trades, key=lambda t: t.timestamp)
        
        for trade in sorted_trades:
            activities = await self.process_trade(trade)
            all_activities.extend(activities)
            
        return all_activities
    
    def get_summary(self, activities: List[UnusualActivity]) -> Dict[str, Any]:
        """Generate summary of unusual activities."""
        if not activities:
            return {"total": 0, "bullish": 0, "bearish": 0}
            
        bullish = [a for a in activities if a.is_bullish]
        bearish = [a for a in activities if a.is_bearish]
        
        by_type = defaultdict(list)
        for a in activities:
            by_type[a.activity_type.value].append(a)
            
        total_premium_bullish = sum(a.trade.premium for a in bullish)
        total_premium_bearish = sum(a.trade.premium for a in bearish)
        
        return {
            "total": len(activities),
            "bullish": len(bullish),
            "bearish": len(bearish),
            "bullish_premium": total_premium_bullish,
            "bearish_premium": total_premium_bearish,
            "sentiment": "bullish" if total_premium_bullish > total_premium_bearish else "bearish",
            "sentiment_ratio": total_premium_bullish / max(1, total_premium_bearish),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "top_score": max(a.score for a in activities),
            "avg_score": sum(a.score for a in activities) / len(activities),
        }


class RealTimeFlowMonitor:
    """
    Real-time options flow monitoring with aggregation.
    """
    
    def __init__(
        self,
        detector: Optional[UnusualActivityDetector] = None,
        aggregation_window_seconds: int = 300,
    ):
        self.detector = detector or UnusualActivityDetector()
        self.aggregation_window = aggregation_window_seconds
        self._activities: List[UnusualActivity] = []
        self._running = False
        
    async def start(self, trade_source: Callable):
        """Start monitoring trades from source."""
        self._running = True
        logger.info("Starting real-time flow monitor")
        
        async for trade in trade_source():
            if not self._running:
                break
                
            activities = await self.detector.process_trade(trade)
            self._activities.extend(activities)
            self._cleanup_activities()
            
    def stop(self):
        """Stop monitoring."""
        self._running = False
        
    def _cleanup_activities(self):
        """Remove old activities."""
        cutoff = datetime.now() - timedelta(seconds=self.aggregation_window * 2)
        self._activities = [a for a in self._activities if a.timestamp > cutoff]
        
    def get_recent_activities(
        self, 
        symbol: Optional[str] = None,
        activity_type: Optional[OptionsActivityType] = None,
        min_score: float = 0,
    ) -> List[UnusualActivity]:
        """Get recent unusual activities with filters."""
        cutoff = datetime.now() - timedelta(seconds=self.aggregation_window)
        
        activities = [a for a in self._activities if a.timestamp > cutoff]
        
        if symbol:
            activities = [a for a in activities if a.trade.contract.underlying == symbol]
            
        if activity_type:
            activities = [a for a in activities if a.activity_type == activity_type]
            
        if min_score > 0:
            activities = [a for a in activities if a.score >= min_score]
            
        return sorted(activities, key=lambda a: a.score, reverse=True)
    
    def get_flow_summary(self) -> Dict[str, Any]:
        """Get aggregated flow summary."""
        return self.detector.get_summary(self._activities)
