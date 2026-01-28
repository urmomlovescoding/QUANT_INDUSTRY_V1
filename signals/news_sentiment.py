"""
News Sentiment Analysis
QUANT_INDUSTRY_V1

Industry Problem: News moves markets. By the time you read it, it's too late.
Manual news reading doesn't scale. Missing important news = missed opportunities.

Our Solution:
- Real-time news ingestion from multiple sources
- NLP-based sentiment analysis
- Entity extraction (companies, people, events)
- Event detection (earnings, M&A, lawsuits)
- Relevance scoring per symbol
- Sentiment time-series for trading signals
- Unusual news volume detection
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import re
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)

# Optional NLP imports
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not installed. Using rule-based sentiment.")


class SentimentLabel(Enum):
    """Sentiment labels."""
    VERY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    VERY_POSITIVE = 2


class EventType(Enum):
    """News event types."""
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    MERGER_ACQUISITION = "merger_acquisition"
    PRODUCT_LAUNCH = "product_launch"
    EXECUTIVE_CHANGE = "executive_change"
    LAWSUIT = "lawsuit"
    REGULATORY = "regulatory"
    ANALYST_RATING = "analyst_rating"
    DIVIDEND = "dividend"
    BUYBACK = "buyback"
    PARTNERSHIP = "partnership"
    LAYOFFS = "layoffs"
    BANKRUPTCY = "bankruptcy"
    IPO = "ipo"
    OTHER = "other"


@dataclass
class NewsArticle:
    """A news article."""
    article_id: str
    title: str
    content: str
    source: str
    published_at: datetime
    url: str
    
    # Extracted data
    symbols: List[str] = field(default_factory=list)
    sentiment: Optional[SentimentLabel] = None
    sentiment_score: float = 0.0  # -1 to 1
    relevance_scores: Dict[str, float] = field(default_factory=dict)  # Per symbol
    
    # Event detection
    event_type: Optional[EventType] = None
    event_confidence: float = 0.0
    
    # Entities
    entities: Dict[str, List[str]] = field(default_factory=dict)  # {type: [entities]}
    
    # Metadata
    word_count: int = 0
    processed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'article_id': self.article_id,
            'title': self.title,
            'source': self.source,
            'published_at': self.published_at.isoformat(),
            'url': self.url,
            'symbols': self.symbols,
            'sentiment': self.sentiment.name if self.sentiment else None,
            'sentiment_score': self.sentiment_score,
            'event_type': self.event_type.value if self.event_type else None,
            'relevance_scores': self.relevance_scores
        }


@dataclass
class SentimentSignal:
    """Sentiment signal for trading."""
    symbol: str
    timestamp: datetime
    
    # Sentiment
    sentiment_score: float  # -1 to 1
    sentiment_momentum: float  # Change vs previous period
    
    # Volume
    news_count: int
    news_count_zscore: float  # vs historical average
    
    # Event flags
    has_material_event: bool
    event_types: List[EventType] = field(default_factory=list)
    
    # Signal strength
    signal_strength: float = 0.0  # Combined metric
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'sentiment_score': self.sentiment_score,
            'sentiment_momentum': self.sentiment_momentum,
            'news_count': self.news_count,
            'news_count_zscore': self.news_count_zscore,
            'has_material_event': self.has_material_event,
            'event_types': [e.value for e in self.event_types],
            'signal_strength': self.signal_strength
        }


class RuleBasedSentimentAnalyzer:
    """
    Simple rule-based sentiment analyzer.
    Used when transformers not available.
    """
    
    def __init__(self):
        # Sentiment word lists
        self.positive_words = {
            'beat', 'beats', 'exceeds', 'exceeded', 'surpass', 'strong', 'growth',
            'profit', 'gain', 'gains', 'surge', 'surges', 'soar', 'soars', 'jump',
            'jumps', 'rally', 'rallies', 'boom', 'record', 'high', 'upgrade',
            'upgraded', 'buy', 'outperform', 'bullish', 'optimistic', 'positive',
            'success', 'successful', 'win', 'wins', 'winner', 'breakthrough',
            'innovative', 'innovation', 'expand', 'expansion', 'increase', 'increased'
        }
        
        self.negative_words = {
            'miss', 'misses', 'missed', 'fall', 'falls', 'drop', 'drops', 'plunge',
            'plunges', 'crash', 'crashes', 'decline', 'declines', 'loss', 'losses',
            'weak', 'weakness', 'downgrade', 'downgraded', 'sell', 'underperform',
            'bearish', 'pessimistic', 'negative', 'fail', 'fails', 'failure',
            'lawsuit', 'sue', 'sued', 'fraud', 'scandal', 'investigation', 'probe',
            'layoff', 'layoffs', 'cut', 'cuts', 'warning', 'concern', 'risk', 'risks',
            'bankruptcy', 'default', 'recall', 'trouble', 'crisis'
        }
        
        self.very_positive_words = {'surge', 'soar', 'record', 'breakthrough', 'boom'}
        self.very_negative_words = {'crash', 'plunge', 'bankruptcy', 'fraud', 'crisis'}
        
    def analyze(self, text: str) -> Tuple[SentimentLabel, float]:
        """
        Analyze sentiment of text.
        
        Returns: (label, score)
        """
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        pos_count = len(words & self.positive_words)
        neg_count = len(words & self.negative_words)
        very_pos = len(words & self.very_positive_words)
        very_neg = len(words & self.very_negative_words)
        
        # Calculate score
        total = pos_count + neg_count
        if total == 0:
            return SentimentLabel.NEUTRAL, 0.0
            
        score = (pos_count - neg_count) / total
        
        # Boost for very positive/negative
        score += very_pos * 0.2
        score -= very_neg * 0.2
        
        # Clamp
        score = max(-1, min(1, score))
        
        # Label
        if score > 0.5:
            label = SentimentLabel.VERY_POSITIVE
        elif score > 0.1:
            label = SentimentLabel.POSITIVE
        elif score < -0.5:
            label = SentimentLabel.VERY_NEGATIVE
        elif score < -0.1:
            label = SentimentLabel.NEGATIVE
        else:
            label = SentimentLabel.NEUTRAL
            
        return label, score


class TransformerSentimentAnalyzer:
    """
    Transformer-based sentiment analyzer using FinBERT.
    """
    
    def __init__(self, model_name: str = "ProsusAI/finbert"):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers not installed")
            
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.pipeline = None
        
    def load(self):
        """Load the model."""
        logger.info(f"Loading sentiment model: {self.model_name}")
        self.pipeline = pipeline(
            "sentiment-analysis",
            model=self.model_name,
            tokenizer=self.model_name
        )
        logger.info("Sentiment model loaded")
        
    def analyze(self, text: str) -> Tuple[SentimentLabel, float]:
        """Analyze sentiment."""
        if self.pipeline is None:
            self.load()
            
        # Truncate long text
        if len(text) > 512:
            text = text[:512]
            
        result = self.pipeline(text)[0]
        
        label_map = {
            'positive': SentimentLabel.POSITIVE,
            'negative': SentimentLabel.NEGATIVE,
            'neutral': SentimentLabel.NEUTRAL
        }
        
        label = label_map.get(result['label'].lower(), SentimentLabel.NEUTRAL)
        
        # Convert score
        score = result['score']
        if label == SentimentLabel.NEGATIVE:
            score = -score
        elif label == SentimentLabel.NEUTRAL:
            score = 0
            
        return label, score


class EventDetector:
    """Detect material events in news."""
    
    def __init__(self):
        # Event patterns
        self.patterns = {
            EventType.EARNINGS: [
                r'\bearnings\b', r'\bquarter(?:ly)?\s+results?\b', r'\beps\b',
                r'\brevenue\b', r'\bbeat\s+estimates?\b', r'\bmiss(?:ed)?\s+estimates?\b'
            ],
            EventType.GUIDANCE: [
                r'\bguidance\b', r'\boutlook\b', r'\bforecast\b', r'\bexpects?\b'
            ],
            EventType.MERGER_ACQUISITION: [
                r'\bacquire[sd]?\b', r'\bacquisition\b', r'\bmerger?\b', r'\btakeover\b',
                r'\bbuyout\b', r'\bdeal\b'
            ],
            EventType.PRODUCT_LAUNCH: [
                r'\blaunch(?:ed|es|ing)?\b', r'\breleased?\b', r'\bunveiled?\b',
                r'\bannounced?\s+(?:new|product)\b'
            ],
            EventType.EXECUTIVE_CHANGE: [
                r'\bceo\b', r'\bcfo\b', r'\bchief\b', r'\bappointed?\b', r'\bresigned?\b',
                r'\bstepped?\s+down\b'
            ],
            EventType.LAWSUIT: [
                r'\blawsuit\b', r'\bsued?\b', r'\blitigation\b', r'\bsettlement\b',
                r'\bcomplaint\b', r'\ballegation\b'
            ],
            EventType.REGULATORY: [
                r'\bfda\b', r'\bsec\b', r'\bapproval\b', r'\bregulator[sy]?\b',
                r'\bcompliance\b', r'\binvestigation\b'
            ],
            EventType.ANALYST_RATING: [
                r'\bupgrade[sd]?\b', r'\bdowngrade[sd]?\b', r'\btarget\s+price\b',
                r'\brating\b', r'\banalyst\b'
            ],
            EventType.DIVIDEND: [
                r'\bdividend\b', r'\bpayout\b', r'\byield\b'
            ],
            EventType.BUYBACK: [
                r'\bbuyback\b', r'\brepurchase\b', r'\bshare\s+repurchase\b'
            ],
            EventType.LAYOFFS: [
                r'\blayoff[s]?\b', r'\bjob\s+cut[s]?\b', r'\bworkforce\s+reduction\b',
                r'\bdownsiz(?:e|ing)\b'
            ],
            EventType.BANKRUPTCY: [
                r'\bbankrupt(?:cy)?\b', r'\bchapter\s+11\b', r'\bdefault\b',
                r'\binsolvenc[ey]\b'
            ]
        }
        
        # Compile patterns
        self.compiled = {
            event: [re.compile(p, re.IGNORECASE) for p in patterns]
            for event, patterns in self.patterns.items()
        }
        
    def detect(self, text: str) -> Tuple[Optional[EventType], float]:
        """
        Detect event type in text.
        
        Returns: (event_type, confidence)
        """
        scores = {}
        
        for event, patterns in self.compiled.items():
            matches = sum(1 for p in patterns if p.search(text))
            if matches > 0:
                scores[event] = matches / len(patterns)
                
        if not scores:
            return None, 0.0
            
        # Return highest confidence event
        best_event = max(scores, key=scores.get)
        return best_event, scores[best_event]


class SymbolExtractor:
    """Extract stock symbols from text."""
    
    def __init__(self, known_symbols: Optional[List[str]] = None):
        self.known_symbols = set(known_symbols) if known_symbols else set()
        
        # Common company name to symbol mappings
        self.company_map = {
            'apple': 'AAPL', 'microsoft': 'MSFT', 'google': 'GOOGL', 'alphabet': 'GOOGL',
            'amazon': 'AMZN', 'meta': 'META', 'facebook': 'META', 'tesla': 'TSLA',
            'nvidia': 'NVDA', 'netflix': 'NFLX', 'intel': 'INTC', 'amd': 'AMD',
            'jpmorgan': 'JPM', 'goldman': 'GS', 'berkshire': 'BRK.B'
        }
        
    def extract(self, text: str) -> List[str]:
        """Extract symbols from text."""
        symbols = set()
        
        # Look for ticker patterns ($AAPL or AAPL:)
        ticker_patterns = re.findall(r'\$([A-Z]{1,5})\b', text)
        symbols.update(ticker_patterns)
        
        ticker_patterns = re.findall(r'\b([A-Z]{1,5}):\s', text)
        symbols.update(ticker_patterns)
        
        # Look for known symbols mentioned
        text_upper = text.upper()
        for symbol in self.known_symbols:
            if re.search(rf'\b{symbol}\b', text_upper):
                symbols.add(symbol)
                
        # Look for company names
        text_lower = text.lower()
        for company, symbol in self.company_map.items():
            if company in text_lower:
                symbols.add(symbol)
                
        return list(symbols)


class NewsSentimentEngine:
    """
    Complete news sentiment analysis engine.
    """
    
    def __init__(
        self,
        known_symbols: Optional[List[str]] = None,
        use_transformer: bool = True,
        lookback_hours: int = 24
    ):
        # Analyzers
        if use_transformer and TRANSFORMERS_AVAILABLE:
            self.sentiment_analyzer = TransformerSentimentAnalyzer()
        else:
            self.sentiment_analyzer = RuleBasedSentimentAnalyzer()
            
        self.event_detector = EventDetector()
        self.symbol_extractor = SymbolExtractor(known_symbols)
        
        # History
        self.lookback_hours = lookback_hours
        self.articles: Dict[str, NewsArticle] = {}
        self.symbol_sentiment_history: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)
        
        # Cache
        self.daily_sentiment: Dict[str, Dict[str, float]] = {}  # {date: {symbol: score}}
        
    def process_article(self, article: NewsArticle) -> NewsArticle:
        """Process a news article."""
        # Extract symbols
        full_text = f"{article.title} {article.content}"
        article.symbols = self.symbol_extractor.extract(full_text)
        
        # Analyze sentiment
        article.sentiment, article.sentiment_score = self.sentiment_analyzer.analyze(full_text)
        
        # Detect events
        article.event_type, article.event_confidence = self.event_detector.detect(full_text)
        
        # Calculate relevance per symbol
        for symbol in article.symbols:
            article.relevance_scores[symbol] = self._calculate_relevance(article, symbol)
            
        article.word_count = len(full_text.split())
        article.processed = True
        
        # Store
        self.articles[article.article_id] = article
        
        # Update history
        for symbol in article.symbols:
            self.symbol_sentiment_history[symbol].append(
                (article.published_at, article.sentiment_score)
            )
            
        return article
        
    def _calculate_relevance(self, article: NewsArticle, symbol: str) -> float:
        """Calculate how relevant article is to symbol."""
        relevance = 0.5  # Base relevance
        
        # Title mention is more relevant
        if symbol in article.title.upper():
            relevance += 0.3
            
        # Company name mention
        for company, sym in self.symbol_extractor.company_map.items():
            if sym == symbol and company in article.title.lower():
                relevance += 0.2
                
        # Event relevance
        if article.event_type in [EventType.EARNINGS, EventType.MERGER_ACQUISITION]:
            relevance += 0.2
            
        return min(relevance, 1.0)
        
    def get_sentiment_signal(self, symbol: str) -> SentimentSignal:
        """Get sentiment signal for a symbol."""
        now = datetime.now()
        cutoff = now - timedelta(hours=self.lookback_hours)
        
        # Get recent articles for this symbol
        recent_articles = [
            a for a in self.articles.values()
            if symbol in a.symbols and a.published_at > cutoff
        ]
        
        if not recent_articles:
            return SentimentSignal(
                symbol=symbol,
                timestamp=now,
                sentiment_score=0.0,
                sentiment_momentum=0.0,
                news_count=0,
                news_count_zscore=0.0,
                has_material_event=False
            )
            
        # Calculate average sentiment (weighted by relevance)
        total_weight = sum(a.relevance_scores.get(symbol, 0.5) for a in recent_articles)
        if total_weight > 0:
            sentiment_score = sum(
                a.sentiment_score * a.relevance_scores.get(symbol, 0.5)
                for a in recent_articles
            ) / total_weight
        else:
            sentiment_score = 0.0
            
        # Calculate momentum (compare to previous period)
        prev_cutoff = cutoff - timedelta(hours=self.lookback_hours)
        prev_articles = [
            a for a in self.articles.values()
            if symbol in a.symbols and prev_cutoff < a.published_at <= cutoff
        ]
        
        if prev_articles:
            prev_sentiment = np.mean([a.sentiment_score for a in prev_articles])
            momentum = sentiment_score - prev_sentiment
        else:
            momentum = 0.0
            
        # News volume analysis
        news_count = len(recent_articles)
        history = self.symbol_sentiment_history[symbol]
        if len(history) > 20:
            historical_counts = []
            for i in range(0, len(history) - 10, 10):
                period_count = sum(1 for _, _ in history[i:i+10])
                historical_counts.append(period_count)
            
            if historical_counts:
                mean_count = np.mean(historical_counts)
                std_count = np.std(historical_counts)
                news_count_zscore = (news_count - mean_count) / std_count if std_count > 0 else 0
            else:
                news_count_zscore = 0.0
        else:
            news_count_zscore = 0.0
            
        # Check for material events
        event_types = [
            a.event_type for a in recent_articles
            if a.event_type and a.event_confidence > 0.5
        ]
        has_material_event = len(event_types) > 0
        
        # Calculate signal strength
        signal_strength = self._calculate_signal_strength(
            sentiment_score, momentum, news_count_zscore, has_material_event
        )
        
        return SentimentSignal(
            symbol=symbol,
            timestamp=now,
            sentiment_score=sentiment_score,
            sentiment_momentum=momentum,
            news_count=news_count,
            news_count_zscore=news_count_zscore,
            has_material_event=has_material_event,
            event_types=list(set(event_types)),
            signal_strength=signal_strength
        )
        
    def _calculate_signal_strength(
        self,
        sentiment: float,
        momentum: float,
        volume_zscore: float,
        has_event: bool
    ) -> float:
        """Calculate combined signal strength."""
        # Sentiment contribution
        strength = abs(sentiment) * 0.4
        
        # Momentum contribution
        strength += abs(momentum) * 0.2
        
        # Volume contribution (unusual volume amplifies signal)
        if volume_zscore > 2:
            strength *= 1.5
        elif volume_zscore > 1:
            strength *= 1.2
            
        # Event contribution
        if has_event:
            strength *= 1.3
            
        # Apply direction
        direction = 1 if sentiment > 0 else -1
        
        return strength * direction
        
    def get_market_sentiment(self) -> Dict[str, Any]:
        """Get overall market sentiment."""
        now = datetime.now()
        cutoff = now - timedelta(hours=self.lookback_hours)
        
        recent = [a for a in self.articles.values() if a.published_at > cutoff]
        
        if not recent:
            return {'overall_sentiment': 0.0, 'article_count': 0}
            
        # Overall sentiment
        overall = np.mean([a.sentiment_score for a in recent])
        
        # Sentiment distribution
        positive = len([a for a in recent if a.sentiment_score > 0.1])
        negative = len([a for a in recent if a.sentiment_score < -0.1])
        neutral = len(recent) - positive - negative
        
        # Top events
        events = [a.event_type for a in recent if a.event_type]
        event_counts = defaultdict(int)
        for e in events:
            event_counts[e.value] += 1
            
        return {
            'overall_sentiment': overall,
            'article_count': len(recent),
            'positive_count': positive,
            'negative_count': negative,
            'neutral_count': neutral,
            'sentiment_ratio': positive / negative if negative > 0 else positive,
            'top_events': dict(event_counts),
            'timestamp': now.isoformat()
        }
        
    def get_top_movers(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get symbols with biggest sentiment moves."""
        signals = {}
        
        for symbol in set(
            sym for a in self.articles.values() for sym in a.symbols
        ):
            signal = self.get_sentiment_signal(symbol)
            if signal.news_count > 0:
                signals[symbol] = signal
                
        # Sort by absolute signal strength
        sorted_signals = sorted(
            signals.values(),
            key=lambda s: abs(s.signal_strength),
            reverse=True
        )
        
        return [s.to_dict() for s in sorted_signals[:n]]
