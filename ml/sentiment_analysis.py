"""
Integrated Sentiment Analysis Module
QUANT_INDUSTRY_V1 - P2 Task 19

Sentiment analysis for trading signals using HuggingFace Transformers patterns.

Features:
- Multi-source sentiment (news, social media, SEC filings)
- Financial domain-specific models (FinBERT)
- Real-time sentiment aggregation
- Historical sentiment trends
- Sentiment-to-signal conversion

Rollback Plan: Delete this file
Tests Required: Sentiment accuracy, signal correlation
Failure Modes: Graceful degradation to neutral sentiment
"""

import logging
import threading
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import numpy as np
import re

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES AND ENUMS
# =============================================================================

class SentimentSource(Enum):
    """Sources of sentiment data."""
    NEWS = "news"
    SOCIAL_MEDIA = "social_media"
    SEC_FILING = "sec_filing"
    EARNINGS_CALL = "earnings_call"
    ANALYST_REPORT = "analyst_report"
    GENERAL = "general"


class SentimentLabel(Enum):
    """Sentiment classification labels."""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


@dataclass
class SentimentScore:
    """Sentiment analysis result for a single text."""
    text: str
    text_hash: str
    label: SentimentLabel
    confidence: float  # 0-1
    positive_score: float
    negative_score: float
    neutral_score: float
    source: SentimentSource
    symbol: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def sentiment_value(self) -> float:
        """Convert to numeric sentiment (-1 to 1)."""
        label_values = {
            SentimentLabel.VERY_NEGATIVE: -1.0,
            SentimentLabel.NEGATIVE: -0.5,
            SentimentLabel.NEUTRAL: 0.0,
            SentimentLabel.POSITIVE: 0.5,
            SentimentLabel.VERY_POSITIVE: 1.0,
        }
        return label_values.get(self.label, 0.0) * self.confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text_preview': self.text[:100] + '...' if len(self.text) > 100 else self.text,
            'label': self.label.value,
            'confidence': self.confidence,
            'positive_score': self.positive_score,
            'negative_score': self.negative_score,
            'neutral_score': self.neutral_score,
            'sentiment_value': self.sentiment_value,
            'source': self.source.value,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment for a symbol over a time period."""
    symbol: str
    start_time: datetime
    end_time: datetime
    num_items: int
    mean_sentiment: float
    std_sentiment: float
    weighted_sentiment: float  # Confidence-weighted
    sentiment_momentum: float  # Change in sentiment
    dominant_label: SentimentLabel
    source_breakdown: Dict[str, float]
    confidence: float

    @property
    def signal_strength(self) -> float:
        """Convert to trading signal strength (-1 to 1)."""
        # Stronger signal when sentiment is extreme and consistent
        consistency_factor = 1 - self.std_sentiment
        return self.weighted_sentiment * consistency_factor * self.confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'period': f"{self.start_time.isoformat()} to {self.end_time.isoformat()}",
            'num_items': self.num_items,
            'mean_sentiment': self.mean_sentiment,
            'weighted_sentiment': self.weighted_sentiment,
            'sentiment_momentum': self.sentiment_momentum,
            'signal_strength': self.signal_strength,
            'dominant_label': self.dominant_label.value,
            'source_breakdown': self.source_breakdown,
        }


# =============================================================================
# SENTIMENT MODELS
# =============================================================================

class SentimentModel(ABC):
    """Abstract base class for sentiment models."""

    @abstractmethod
    def analyze(self, text: str) -> Tuple[SentimentLabel, float, Dict[str, float]]:
        """
        Analyze sentiment of text.
        
        Returns:
            Tuple of (label, confidence, {positive, negative, neutral scores})
        """
        pass


class FinancialSentimentModel(SentimentModel):
    """
    Financial domain sentiment model.
    
    Uses patterns similar to FinBERT for financial text.
    In production, this would use actual HuggingFace transformers.
    """

    def __init__(self, model_name: str = "ProsusAI/finbert"):
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
        
        # Financial sentiment lexicons
        self._positive_words = {
            'bullish', 'growth', 'profit', 'gain', 'surge', 'rally', 'outperform',
            'upgrade', 'beat', 'exceed', 'strong', 'positive', 'optimistic',
            'opportunity', 'momentum', 'breakthrough', 'record', 'innovation',
        }
        self._negative_words = {
            'bearish', 'loss', 'decline', 'drop', 'crash', 'fall', 'underperform',
            'downgrade', 'miss', 'weak', 'negative', 'pessimistic', 'risk',
            'concern', 'warning', 'recession', 'default', 'bankruptcy', 'fraud',
        }
        self._intensifiers = {'very', 'extremely', 'significantly', 'substantially'}
        self._negators = {'not', "n't", 'never', 'no', 'without'}

    def _load_model(self) -> None:
        """Load the transformer model (lazy loading)."""
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._model.eval()
            logger.info(f"Loaded sentiment model: {self.model_name}")
        except ImportError:
            logger.warning("Transformers not available, using rule-based fallback")
        except Exception as e:
            logger.warning(f"Could not load model {self.model_name}: {e}")

    def analyze(self, text: str) -> Tuple[SentimentLabel, float, Dict[str, float]]:
        """Analyze financial text sentiment."""
        # Try transformer model first
        if self._model is not None:
            return self._analyze_with_transformer(text)
        
        # Fall back to rule-based analysis
        return self._analyze_rule_based(text)

    def _analyze_with_transformer(self, text: str) -> Tuple[SentimentLabel, float, Dict[str, float]]:
        """Analyze using transformer model."""
        try:
            import torch
            
            inputs = self._tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                max_length=512
            )
            
            with torch.no_grad():
                outputs = self._model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)[0]
            
            # FinBERT output: [positive, negative, neutral]
            positive = probs[0].item()
            negative = probs[1].item()
            neutral = probs[2].item()
            
            scores = {
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
            }
            
            # Determine label
            max_score = max(positive, negative, neutral)
            confidence = max_score
            
            if positive == max_score:
                label = SentimentLabel.VERY_POSITIVE if positive > 0.7 else SentimentLabel.POSITIVE
            elif negative == max_score:
                label = SentimentLabel.VERY_NEGATIVE if negative > 0.7 else SentimentLabel.NEGATIVE
            else:
                label = SentimentLabel.NEUTRAL
            
            return label, confidence, scores
            
        except Exception as e:
            logger.warning(f"Transformer analysis failed: {e}")
            return self._analyze_rule_based(text)

    def _analyze_rule_based(self, text: str) -> Tuple[SentimentLabel, float, Dict[str, float]]:
        """Rule-based sentiment analysis fallback."""
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        positive_count = 0
        negative_count = 0
        negation_window = 0
        intensity = 1.0
        
        for i, word in enumerate(words):
            # Check for intensifiers
            if word in self._intensifiers:
                intensity = 1.5
                continue
            
            # Check for negators
            if word in self._negators:
                negation_window = 3
                continue
            
            # Apply sentiment with negation handling
            is_negated = negation_window > 0
            
            if word in self._positive_words:
                if is_negated:
                    negative_count += intensity
                else:
                    positive_count += intensity
            elif word in self._negative_words:
                if is_negated:
                    positive_count += intensity
                else:
                    negative_count += intensity
            
            if negation_window > 0:
                negation_window -= 1
            intensity = 1.0  # Reset intensity
        
        # Normalize scores
        total = positive_count + negative_count + 1  # +1 for neutral base
        positive_score = positive_count / total
        negative_score = negative_count / total
        neutral_score = 1 / total
        
        # Normalize to sum to 1
        score_sum = positive_score + negative_score + neutral_score
        positive_score /= score_sum
        negative_score /= score_sum
        neutral_score /= score_sum
        
        scores = {
            'positive': positive_score,
            'negative': negative_score,
            'neutral': neutral_score,
        }
        
        # Determine label
        if positive_score > negative_score and positive_score > neutral_score:
            label = SentimentLabel.VERY_POSITIVE if positive_score > 0.6 else SentimentLabel.POSITIVE
            confidence = positive_score
        elif negative_score > positive_score and negative_score > neutral_score:
            label = SentimentLabel.VERY_NEGATIVE if negative_score > 0.6 else SentimentLabel.NEGATIVE
            confidence = negative_score
        else:
            label = SentimentLabel.NEUTRAL
            confidence = neutral_score
        
        return label, confidence, scores


class NewsSentimentModel(FinancialSentimentModel):
    """Specialized model for news articles."""

    def __init__(self):
        super().__init__(model_name="mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis")
        
        # Add news-specific words
        self._positive_words.update({'announced', 'launches', 'partnership', 'acquisition'})
        self._negative_words.update({'investigation', 'lawsuit', 'recall', 'layoffs'})


class SocialMediaSentimentModel(FinancialSentimentModel):
    """Specialized model for social media content."""

    def __init__(self):
        super().__init__(model_name="cardiffnlp/twitter-roberta-base-sentiment")
        
        # Add social media specific patterns
        self._positive_words.update({'moon', 'rocket', 'diamond', 'hodl', 'tendies'})
        self._negative_words.update({'dump', 'bag', 'rug', 'scam', 'ponzi'})
        
        # Emojis (simplified)
        self._positive_emojis = {'[LAUNCH]', '[UP]', '💎', '🔥', '💪', '🌙'}
        self._negative_emojis = {'[DOWN]', '💀', '🔻', '😢', '😰'}

    def analyze(self, text: str) -> Tuple[SentimentLabel, float, Dict[str, float]]:
        # Count emojis
        positive_emoji_count = sum(1 for char in text if char in self._positive_emojis)
        negative_emoji_count = sum(1 for char in text if char in self._negative_emojis)
        
        # Get base analysis
        label, confidence, scores = super().analyze(text)
        
        # Adjust based on emojis
        emoji_impact = (positive_emoji_count - negative_emoji_count) * 0.1
        scores['positive'] = min(1.0, scores['positive'] + max(0, emoji_impact))
        scores['negative'] = min(1.0, scores['negative'] - min(0, emoji_impact))
        
        # Renormalize
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}
        
        # Recalculate label
        max_score = max(scores.values())
        max_key = max(scores, key=scores.get)
        
        if max_key == 'positive':
            label = SentimentLabel.VERY_POSITIVE if max_score > 0.7 else SentimentLabel.POSITIVE
        elif max_key == 'negative':
            label = SentimentLabel.VERY_NEGATIVE if max_score > 0.7 else SentimentLabel.NEGATIVE
        else:
            label = SentimentLabel.NEUTRAL
        
        return label, max_score, scores


# =============================================================================
# SENTIMENT ANALYZER
# =============================================================================

class SentimentAnalyzer:
    """
    Main sentiment analysis orchestrator.
    
    Coordinates multiple models and sources for comprehensive sentiment analysis.
    """

    def __init__(self, use_transformers: bool = True):
        self.use_transformers = use_transformers
        
        # Initialize models
        self._models: Dict[SentimentSource, SentimentModel] = {
            SentimentSource.NEWS: NewsSentimentModel(),
            SentimentSource.SOCIAL_MEDIA: SocialMediaSentimentModel(),
            SentimentSource.GENERAL: FinancialSentimentModel(),
            SentimentSource.SEC_FILING: FinancialSentimentModel(),
            SentimentSource.EARNINGS_CALL: FinancialSentimentModel(),
            SentimentSource.ANALYST_REPORT: FinancialSentimentModel(),
        }
        
        # Cache for deduplication
        self._cache: Dict[str, SentimentScore] = {}
        self._cache_ttl = timedelta(hours=24)
        
        # Historical storage
        self._history: Dict[str, List[SentimentScore]] = {}
        self._lock = threading.RLock()

    def _hash_text(self, text: str) -> str:
        """Generate hash for text deduplication."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def analyze_text(
        self,
        text: str,
        source: SentimentSource = SentimentSource.GENERAL,
        symbol: Optional[str] = None,
        use_cache: bool = True,
    ) -> SentimentScore:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Text to analyze
            source: Source of the text
            symbol: Associated stock symbol
            use_cache: Whether to use cached results
            
        Returns:
            SentimentScore object
        """
        text_hash = self._hash_text(text)
        
        # Check cache
        if use_cache and text_hash in self._cache:
            cached = self._cache[text_hash]
            if datetime.now(timezone.utc) - cached.timestamp < self._cache_ttl:
                return cached
        
        # Get appropriate model
        model = self._models.get(source, self._models[SentimentSource.GENERAL])
        
        # Analyze
        try:
            label, confidence, scores = model.analyze(text)
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            label = SentimentLabel.NEUTRAL
            confidence = 0.5
            scores = {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34}
        
        result = SentimentScore(
            text=text,
            text_hash=text_hash,
            label=label,
            confidence=confidence,
            positive_score=scores['positive'],
            negative_score=scores['negative'],
            neutral_score=scores['neutral'],
            source=source,
            symbol=symbol,
        )
        
        # Cache result
        with self._lock:
            self._cache[text_hash] = result
            
            # Store in history
            if symbol:
                if symbol not in self._history:
                    self._history[symbol] = []
                self._history[symbol].append(result)
        
        return result

    def analyze_batch(
        self,
        items: List[Dict[str, Any]],
        parallel: bool = False,
    ) -> List[SentimentScore]:
        """
        Analyze multiple texts.
        
        Args:
            items: List of dicts with 'text', 'source', 'symbol' keys
            parallel: Whether to use parallel processing
            
        Returns:
            List of SentimentScore objects
        """
        results = []
        
        for item in items:
            result = self.analyze_text(
                text=item.get('text', ''),
                source=SentimentSource(item.get('source', 'general')),
                symbol=item.get('symbol'),
            )
            results.append(result)
        
        return results

    def aggregate_sentiment(
        self,
        symbol: str,
        lookback_hours: int = 24,
        source_weights: Dict[SentimentSource, float] = None,
    ) -> Optional[AggregatedSentiment]:
        """
        Aggregate sentiment for a symbol over a time period.
        
        Args:
            symbol: Stock symbol
            lookback_hours: Hours to look back
            source_weights: Weights for different sources
            
        Returns:
            AggregatedSentiment or None if no data
        """
        with self._lock:
            if symbol not in self._history:
                return None
            
            cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
            recent = [s for s in self._history[symbol] if s.timestamp >= cutoff]
        
        if not recent:
            return None
        
        # Default source weights
        if source_weights is None:
            source_weights = {
                SentimentSource.NEWS: 1.0,
                SentimentSource.ANALYST_REPORT: 1.2,
                SentimentSource.SEC_FILING: 1.0,
                SentimentSource.EARNINGS_CALL: 1.1,
                SentimentSource.SOCIAL_MEDIA: 0.7,
                SentimentSource.GENERAL: 0.8,
            }
        
        # Calculate aggregated metrics
        sentiment_values = [s.sentiment_value for s in recent]
        confidences = [s.confidence for s in recent]
        
        # Source weights for weighted average
        weights = [
            source_weights.get(s.source, 1.0) * s.confidence
            for s in recent
        ]
        weight_sum = sum(weights)
        
        weighted_sentiment = (
            sum(sv * w for sv, w in zip(sentiment_values, weights)) / weight_sum
            if weight_sum > 0 else 0.0
        )
        
        # Calculate momentum (change in sentiment)
        if len(recent) >= 2:
            half_idx = len(recent) // 2
            early_sentiment = np.mean([s.sentiment_value for s in recent[:half_idx]])
            late_sentiment = np.mean([s.sentiment_value for s in recent[half_idx:]])
            momentum = late_sentiment - early_sentiment
        else:
            momentum = 0.0
        
        # Source breakdown
        source_breakdown = {}
        for source in SentimentSource:
            source_items = [s for s in recent if s.source == source]
            if source_items:
                source_breakdown[source.value] = np.mean(
                    [s.sentiment_value for s in source_items]
                )
        
        # Dominant label
        label_counts = {}
        for s in recent:
            label_counts[s.label] = label_counts.get(s.label, 0) + 1
        dominant_label = max(label_counts, key=label_counts.get)
        
        return AggregatedSentiment(
            symbol=symbol,
            start_time=min(s.timestamp for s in recent),
            end_time=max(s.timestamp for s in recent),
            num_items=len(recent),
            mean_sentiment=np.mean(sentiment_values),
            std_sentiment=np.std(sentiment_values),
            weighted_sentiment=weighted_sentiment,
            sentiment_momentum=momentum,
            dominant_label=dominant_label,
            source_breakdown=source_breakdown,
            confidence=np.mean(confidences),
        )

    def get_trading_signal(
        self,
        symbol: str,
        lookback_hours: int = 24,
        signal_threshold: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Convert sentiment to trading signal.
        
        Args:
            symbol: Stock symbol
            lookback_hours: Hours to look back
            signal_threshold: Minimum signal strength to generate trade
            
        Returns:
            Trading signal dictionary
        """
        agg = self.aggregate_sentiment(symbol, lookback_hours)
        
        if agg is None:
            return {
                'symbol': symbol,
                'signal': 'hold',
                'strength': 0.0,
                'confidence': 0.0,
                'reason': 'Insufficient sentiment data',
            }
        
        signal_strength = agg.signal_strength
        
        # Determine signal
        if signal_strength > signal_threshold:
            signal = 'buy'
        elif signal_strength < -signal_threshold:
            signal = 'sell'
        else:
            signal = 'hold'
        
        return {
            'symbol': symbol,
            'signal': signal,
            'strength': abs(signal_strength),
            'direction': 'bullish' if signal_strength > 0 else 'bearish',
            'confidence': agg.confidence,
            'sentiment_value': agg.weighted_sentiment,
            'momentum': agg.sentiment_momentum,
            'num_sources': agg.num_items,
            'reason': f"Weighted sentiment: {agg.weighted_sentiment:.2f}, Momentum: {agg.sentiment_momentum:.2f}",
        }

    def get_sentiment_history(
        self,
        symbol: str,
        hours: int = 168,  # 1 week
        resample_hours: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Get historical sentiment trend.
        
        Args:
            symbol: Stock symbol
            hours: Hours of history
            resample_hours: Resample interval
            
        Returns:
            List of sentiment data points
        """
        with self._lock:
            if symbol not in self._history:
                return []
            
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            data = [s for s in self._history[symbol] if s.timestamp >= cutoff]
        
        if not data:
            return []
        
        # Resample into buckets
        bucket_size = timedelta(hours=resample_hours)
        start = min(s.timestamp for s in data)
        end = max(s.timestamp for s in data)
        
        result = []
        current = start
        
        while current <= end:
            bucket_end = current + bucket_size
            bucket_data = [
                s for s in data 
                if current <= s.timestamp < bucket_end
            ]
            
            if bucket_data:
                result.append({
                    'timestamp': current.isoformat(),
                    'sentiment': np.mean([s.sentiment_value for s in bucket_data]),
                    'count': len(bucket_data),
                    'positive_ratio': np.mean([s.positive_score for s in bucket_data]),
                    'negative_ratio': np.mean([s.negative_score for s in bucket_data]),
                })
            
            current = bucket_end
        
        return result

    def clear_cache(self) -> None:
        """Clear the sentiment cache."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        with self._lock:
            return {
                'cache_size': len(self._cache),
                'symbols_tracked': len(self._history),
                'total_analyses': sum(len(v) for v in self._history.values()),
                'models_loaded': list(self._models.keys()),
            }


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_sentiment_analyzer: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create global sentiment analyzer."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SentimentSource',
    'SentimentLabel',
    'SentimentScore',
    'AggregatedSentiment',
    'SentimentModel',
    'FinancialSentimentModel',
    'NewsSentimentModel',
    'SocialMediaSentimentModel',
    'SentimentAnalyzer',
    'get_sentiment_analyzer',
]
