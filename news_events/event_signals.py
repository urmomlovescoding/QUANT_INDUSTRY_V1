"""
Event-Based Trading Signal Generation
=====================================
Generates trading signals from news and economic events.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import logging

from .news_feed import NewsArticle, NewsCategory, Urgency
from .sentiment_analyzer import SentimentResult, SentimentLabel
from .event_calendar import EconomicEvent, EarningsEvent, EventType, EventImpact

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of event-driven signals."""
    NEWS_MOMENTUM = "news_momentum"  # Strong directional news
    EARNINGS_SURPRISE = "earnings_surprise"
    GUIDANCE_CHANGE = "guidance_change"
    MACRO_SHOCK = "macro_shock"
    BREAKING_NEWS = "breaking_news"
    SENTIMENT_SHIFT = "sentiment_shift"
    ANALYST_CHANGE = "analyst_change"
    REGULATORY = "regulatory"
    M_AND_A = "m_and_a"


class SignalDirection(Enum):
    """Signal direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class SignalUrgency(Enum):
    """How quickly to act."""
    IMMEDIATE = 1  # Trade now
    URGENT = 2  # Within minutes
    NORMAL = 3  # Can wait
    RESEARCH = 4  # Needs more analysis


@dataclass
class EventSignal:
    """Trading signal from event."""
    id: str
    signal_type: SignalType
    symbol: str
    direction: SignalDirection
    urgency: SignalUrgency
    
    # Strength and confidence
    strength: float  # 0-1
    confidence: float  # 0-1
    
    # Source
    source_type: str  # "news", "earnings", "economic"
    source_id: str
    headline: str = ""
    
    # Timing
    generated_at: datetime = field(default_factory=datetime.now)
    valid_until: Optional[datetime] = None
    
    # Suggested action
    suggested_action: str = ""
    risk_level: str = "medium"  # low, medium, high
    
    # Context
    sentiment_score: Optional[float] = None
    surprise_pct: Optional[float] = None
    related_symbols: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        if self.valid_until:
            return datetime.now() < self.valid_until
        return True
    
    @property
    def composite_score(self) -> float:
        """Combined score for ranking."""
        return self.strength * self.confidence
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "signal_type": self.signal_type.value,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "urgency": self.urgency.value,
            "strength": self.strength,
            "confidence": self.confidence,
            "headline": self.headline,
            "generated_at": self.generated_at.isoformat(),
            "suggested_action": self.suggested_action,
            "composite_score": self.composite_score,
        }


@dataclass
class SignalConfig:
    """Configuration for signal generation."""
    # Sentiment thresholds
    min_sentiment_magnitude: float = 0.3
    bullish_threshold: float = 0.3
    bearish_threshold: float = -0.3
    
    # Earnings thresholds
    earnings_surprise_threshold: float = 5.0  # 5% surprise
    revenue_surprise_threshold: float = 3.0
    
    # Economic thresholds
    economic_surprise_threshold: float = 10.0  # 10% vs forecast
    
    # Signal validity
    news_signal_validity_minutes: int = 60
    earnings_signal_validity_minutes: int = 120
    economic_signal_validity_minutes: int = 30
    
    # Minimum confidence
    min_confidence: float = 0.4


class EventSignalGenerator:
    """
    Generates trading signals from various event types.
    
    Signal sources:
    - Breaking news
    - Earnings surprises
    - Economic data releases
    - Analyst actions
    - M&A announcements
    """
    
    def __init__(self, config: Optional[SignalConfig] = None):
        self.config = config or SignalConfig()
        
        self._signals: Dict[str, EventSignal] = {}
        self._signal_counter = 0
        self._callbacks: List[Callable[[EventSignal], None]] = []
        
    def register_callback(self, callback: Callable[[EventSignal], None]):
        """Register callback for new signals."""
        self._callbacks.append(callback)
        
    def _notify(self, signal: EventSignal):
        """Notify callbacks of signal."""
        for cb in self._callbacks:
            try:
                cb(signal)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _generate_id(self) -> str:
        """Generate unique signal ID."""
        self._signal_counter += 1
        return f"SIG-{self._signal_counter:08d}"
    
    def process_news(
        self,
        article: NewsArticle,
        sentiment: Optional[SentimentResult] = None,
    ) -> Optional[EventSignal]:
        """
        Generate signal from news article.
        """
        # Skip if not urgent enough
        if article.urgency.value < Urgency.NORMAL.value:
            return None
            
        # Need symbols to trade
        if not article.symbols:
            return None
            
        # Get sentiment
        if sentiment is None and article.sentiment_score is not None:
            score = article.sentiment_score
            magnitude = article.sentiment_magnitude or 0.5
        elif sentiment:
            score = sentiment.overall_score
            magnitude = sentiment.magnitude
        else:
            return None
            
        # Check magnitude threshold
        if magnitude < self.config.min_sentiment_magnitude:
            return None
            
        # Determine direction
        if score >= self.config.bullish_threshold:
            direction = SignalDirection.LONG
        elif score <= self.config.bearish_threshold:
            direction = SignalDirection.SHORT
        else:
            return None
            
        # Determine signal type
        signal_type = self._categorize_news_signal(article)
        
        # Calculate strength and confidence
        strength = min(1.0, abs(score) + magnitude * 0.5)
        confidence = self._calculate_news_confidence(article, magnitude)
        
        if confidence < self.config.min_confidence:
            return None
            
        # Determine urgency
        if article.urgency == Urgency.FLASH:
            urgency = SignalUrgency.IMMEDIATE
        elif article.urgency == Urgency.URGENT:
            urgency = SignalUrgency.URGENT
        else:
            urgency = SignalUrgency.NORMAL
            
        # Primary symbol
        primary_symbol = article.symbols[0]
        
        signal = EventSignal(
            id=self._generate_id(),
            signal_type=signal_type,
            symbol=primary_symbol,
            direction=direction,
            urgency=urgency,
            strength=strength,
            confidence=confidence,
            source_type="news",
            source_id=article.id,
            headline=article.headline,
            valid_until=datetime.now() + timedelta(minutes=self.config.news_signal_validity_minutes),
            suggested_action=self._get_action_text(direction, signal_type),
            sentiment_score=score,
            related_symbols=article.symbols[1:5],
        )
        
        self._signals[signal.id] = signal
        self._notify(signal)
        
        return signal
    
    def process_earnings(
        self,
        event: EarningsEvent,
    ) -> Optional[EventSignal]:
        """
        Generate signal from earnings event.
        """
        if not event.is_reported:
            return None
            
        eps_surprise = event.eps_surprise_pct
        revenue_surprise = event.revenue_surprise_pct
        
        # Check if significant surprise
        has_eps_surprise = eps_surprise and abs(eps_surprise) >= self.config.earnings_surprise_threshold
        has_rev_surprise = revenue_surprise and abs(revenue_surprise) >= self.config.revenue_surprise_threshold
        
        if not has_eps_surprise and not has_rev_surprise:
            return None
            
        # Determine direction
        primary_surprise = eps_surprise if has_eps_surprise else revenue_surprise
        
        if primary_surprise > 0:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT
            
        # Strength based on surprise magnitude
        strength = min(1.0, abs(primary_surprise) / 20)  # 20% surprise = max strength
        
        # Confidence based on consistency
        confidence = 0.7
        if has_eps_surprise and has_rev_surprise:
            if (eps_surprise > 0) == (revenue_surprise > 0):
                confidence = 0.9  # Both in same direction
            else:
                confidence = 0.5  # Mixed signals
                
        signal = EventSignal(
            id=self._generate_id(),
            signal_type=SignalType.EARNINGS_SURPRISE,
            symbol=event.symbol,
            direction=direction,
            urgency=SignalUrgency.URGENT,
            strength=strength,
            confidence=confidence,
            source_type="earnings",
            source_id=f"{event.symbol}_{event.report_date}",
            headline=f"{event.company_name} {event.fiscal_quarter}: EPS {'+' if eps_surprise and eps_surprise > 0 else ''}{eps_surprise:.1f}% vs est",
            valid_until=datetime.now() + timedelta(minutes=self.config.earnings_signal_validity_minutes),
            suggested_action=self._get_action_text(direction, SignalType.EARNINGS_SURPRISE),
            surprise_pct=primary_surprise,
        )
        
        self._signals[signal.id] = signal
        self._notify(signal)
        
        return signal
    
    def process_economic(
        self,
        event: EconomicEvent,
    ) -> Optional[EventSignal]:
        """
        Generate signal from economic event.
        """
        if not event.is_released:
            return None
            
        surprise_pct = event.surprise_pct
        if surprise_pct is None:
            return None
            
        if abs(surprise_pct) < self.config.economic_surprise_threshold:
            return None
            
        # Economic interpretation depends on event type
        direction = self._interpret_economic_surprise(event.event_type, surprise_pct)
        
        if direction == SignalDirection.NEUTRAL:
            return None
            
        strength = min(1.0, abs(surprise_pct) / 30)
        
        # Higher confidence for high-impact events
        confidence = 0.6 if event.impact.value >= EventImpact.HIGH.value else 0.4
        
        # Affected symbols (index-level for macro)
        symbol = self._get_macro_symbol(event.event_type)
        
        signal = EventSignal(
            id=self._generate_id(),
            signal_type=SignalType.MACRO_SHOCK,
            symbol=symbol,
            direction=direction,
            urgency=SignalUrgency.IMMEDIATE,
            strength=strength,
            confidence=confidence,
            source_type="economic",
            source_id=event.id,
            headline=f"{event.name}: {event.actual} vs {event.forecast} forecast ({surprise_pct:+.1f}%)",
            valid_until=datetime.now() + timedelta(minutes=self.config.economic_signal_validity_minutes),
            suggested_action=self._get_action_text(direction, SignalType.MACRO_SHOCK),
            surprise_pct=surprise_pct,
        )
        
        self._signals[signal.id] = signal
        self._notify(signal)
        
        return signal
    
    def _categorize_news_signal(self, article: NewsArticle) -> SignalType:
        """Categorize news into signal type."""
        category_map = {
            NewsCategory.EARNINGS: SignalType.EARNINGS_SURPRISE,
            NewsCategory.GUIDANCE: SignalType.GUIDANCE_CHANGE,
            NewsCategory.M_AND_A: SignalType.M_AND_A,
            NewsCategory.REGULATORY: SignalType.REGULATORY,
            NewsCategory.UPGRADE: SignalType.ANALYST_CHANGE,
            NewsCategory.DOWNGRADE: SignalType.ANALYST_CHANGE,
            NewsCategory.MACRO: SignalType.MACRO_SHOCK,
            NewsCategory.FED: SignalType.MACRO_SHOCK,
        }
        
        signal_type = category_map.get(article.category, SignalType.NEWS_MOMENTUM)
        
        if article.urgency == Urgency.FLASH:
            return SignalType.BREAKING_NEWS
            
        return signal_type
    
    def _calculate_news_confidence(
        self,
        article: NewsArticle,
        magnitude: float,
    ) -> float:
        """Calculate confidence for news signal."""
        confidence = 0.5
        
        # Higher urgency = higher confidence
        confidence += article.urgency.value * 0.05
        
        # Higher magnitude = higher confidence
        confidence += magnitude * 0.2
        
        # Known reliable sources
        reliable_sources = {"bloomberg", "reuters", "wsj"}
        if article.source.value in reliable_sources:
            confidence += 0.1
            
        return min(1.0, confidence)
    
    def _interpret_economic_surprise(
        self,
        event_type: EventType,
        surprise_pct: float,
    ) -> SignalDirection:
        """Interpret economic surprise for market direction."""
        # Higher is bullish
        bullish_if_higher = {
            EventType.GDP,
            EventType.NFP,
            EventType.RETAIL_SALES,
            EventType.CONSUMER_CONFIDENCE,
            EventType.PMI,
            EventType.ISM,
            EventType.HOUSING,
        }
        
        # Higher is bearish (inflation)
        bearish_if_higher = {
            EventType.CPI,
            EventType.PPI,
            EventType.PCE,
        }
        
        if event_type in bullish_if_higher:
            return SignalDirection.LONG if surprise_pct > 0 else SignalDirection.SHORT
        elif event_type in bearish_if_higher:
            return SignalDirection.SHORT if surprise_pct > 0 else SignalDirection.LONG
        else:
            return SignalDirection.NEUTRAL
    
    def _get_macro_symbol(self, event_type: EventType) -> str:
        """Get symbol most affected by event type."""
        symbol_map = {
            EventType.FOMC: "SPY",
            EventType.GDP: "SPY",
            EventType.CPI: "TLT",
            EventType.NFP: "SPY",
            EventType.UNEMPLOYMENT: "SPY",
        }
        return symbol_map.get(event_type, "SPY")
    
    def _get_action_text(
        self,
        direction: SignalDirection,
        signal_type: SignalType,
    ) -> str:
        """Get suggested action text."""
        if direction == SignalDirection.LONG:
            return f"Consider LONG position based on {signal_type.value}"
        elif direction == SignalDirection.SHORT:
            return f"Consider SHORT position based on {signal_type.value}"
        return "Monitor for direction"
    
    def get_active_signals(
        self,
        symbol: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        min_strength: float = 0.0,
    ) -> List[EventSignal]:
        """Get active signals with filters."""
        signals = [
            s for s in self._signals.values()
            if s.is_valid
            and (symbol is None or s.symbol == symbol)
            and (signal_type is None or s.signal_type == signal_type)
            and s.strength >= min_strength
        ]
        
        # Sort by composite score
        signals.sort(key=lambda s: s.composite_score, reverse=True)
        return signals
    
    def cleanup_expired(self):
        """Remove expired signals."""
        expired = [
            sid for sid, signal in self._signals.items()
            if not signal.is_valid
        ]
        for sid in expired:
            del self._signals[sid]
