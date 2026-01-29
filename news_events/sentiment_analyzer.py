"""
NLP Sentiment Analysis for News
===============================
Extracts sentiment and entities from news text.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


class SentimentLabel(Enum):
    """Sentiment classification."""
    VERY_BEARISH = -2
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1
    VERY_BULLISH = 2


@dataclass
class EntitySentiment:
    """Sentiment for a specific entity (company/symbol)."""
    entity: str
    entity_type: str  # "company", "symbol", "person", "product"
    sentiment_score: float  # -1 to 1
    sentiment_label: SentimentLabel
    confidence: float  # 0 to 1
    mentions: int = 1
    context_snippets: List[str] = field(default_factory=list)


@dataclass
class SentimentResult:
    """Complete sentiment analysis result."""
    text_id: str
    timestamp: datetime
    
    # Overall sentiment
    overall_score: float  # -1 to 1
    overall_label: SentimentLabel
    overall_confidence: float
    
    # Magnitude (strength of sentiment)
    magnitude: float  # 0 to 1
    
    # Entity-level sentiment
    entities: List[EntitySentiment] = field(default_factory=list)
    
    # Key phrases
    positive_phrases: List[str] = field(default_factory=list)
    negative_phrases: List[str] = field(default_factory=list)
    
    # Topics detected
    topics: List[str] = field(default_factory=list)
    
    # Processing info
    model_used: str = "rule_based"
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_id": self.text_id,
            "timestamp": self.timestamp.isoformat(),
            "overall_score": self.overall_score,
            "overall_label": self.overall_label.name,
            "confidence": self.overall_confidence,
            "magnitude": self.magnitude,
            "entities": [
                {
                    "entity": e.entity,
                    "type": e.entity_type,
                    "score": e.sentiment_score,
                    "label": e.sentiment_label.name,
                }
                for e in self.entities
            ],
            "positive_phrases": self.positive_phrases[:5],
            "negative_phrases": self.negative_phrases[:5],
            "topics": self.topics,
        }


@dataclass
class AnalyzerConfig:
    """Configuration for sentiment analyzer."""
    # Model selection
    use_ml_model: bool = False  # Use rule-based by default
    ml_model_name: str = "finbert"
    
    # Thresholds
    neutral_threshold: float = 0.15
    confidence_threshold: float = 0.5
    
    # Processing
    max_text_length: int = 5000
    extract_entities: bool = True
    extract_topics: bool = True


class SentimentAnalyzer:
    """
    Analyzes sentiment in financial news text.
    
    Features:
    - Overall sentiment scoring
    - Entity-level sentiment
    - Financial domain-specific lexicon
    - Key phrase extraction
    """
    
    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or AnalyzerConfig()
        
        # Financial sentiment lexicons
        self._positive_words = self._load_positive_lexicon()
        self._negative_words = self._load_negative_lexicon()
        self._intensifiers = {"very", "extremely", "significantly", "substantially", "highly"}
        self._negations = {"not", "no", "never", "neither", "nobody", "nothing", "nowhere"}
        
        # Domain-specific patterns
        self._bullish_patterns = [
            r"beat\s+(?:expectations?|estimates?)",
            r"raise[ds]?\s+(?:guidance|outlook|forecast)",
            r"(?:record|strong|solid)\s+(?:earnings|revenue|growth)",
            r"upgrade[ds]?",
            r"buy\s+rating",
            r"price\s+target\s+(?:raised|increased)",
            r"outperform",
            r"positive\s+(?:surprise|momentum)",
        ]
        
        self._bearish_patterns = [
            r"miss(?:ed|es)?\s+(?:expectations?|estimates?)",
            r"(?:cut|lower)[s]?\s+(?:guidance|outlook|forecast)",
            r"(?:weak|disappointing|poor)\s+(?:earnings|revenue|results)",
            r"downgrade[ds]?",
            r"sell\s+rating",
            r"price\s+target\s+(?:cut|lowered|reduced)",
            r"underperform",
            r"(?:negative|warning|concern)",
        ]
        
    def _load_positive_lexicon(self) -> set:
        """Load positive sentiment words."""
        return {
            # General positive
            "good", "great", "excellent", "positive", "strong", "better",
            "best", "high", "higher", "increase", "increased", "increasing",
            "growth", "growing", "gain", "gains", "profit", "profitable",
            "success", "successful", "improve", "improved", "improvement",
            "up", "upward", "rise", "rising", "rose", "surge", "surged",
            "rally", "rallied", "boom", "booming", "bull", "bullish",
            
            # Financial positive
            "beat", "beats", "exceeded", "exceeds", "outperform", "outperformed",
            "upgrade", "upgraded", "buy", "accumulate", "overweight",
            "record", "breakthrough", "innovation", "expansion", "expand",
            "dividend", "buyback", "repurchase", "acquisition",
            
            # Earnings positive
            "surprise", "surprised", "top-line", "bottom-line", "margin",
            "margins", "eps", "revenue", "sales", "income",
        }
        
    def _load_negative_lexicon(self) -> set:
        """Load negative sentiment words."""
        return {
            # General negative
            "bad", "poor", "weak", "negative", "worse", "worst",
            "low", "lower", "decrease", "decreased", "decreasing",
            "decline", "declining", "declined", "loss", "losses",
            "fail", "failed", "failure", "down", "downward",
            "fall", "falling", "fell", "drop", "dropped", "dropping",
            "crash", "crashed", "bear", "bearish", "sell-off",
            
            # Financial negative
            "miss", "missed", "misses", "below", "underperform",
            "downgrade", "downgraded", "sell", "reduce", "underweight",
            "warning", "warned", "concern", "concerns", "risk", "risks",
            "cut", "cuts", "layoff", "layoffs", "restructure",
            
            # Negative events
            "lawsuit", "investigation", "fraud", "scandal", "bankruptcy",
            "default", "debt", "liability", "fine", "penalty",
        }
    
    def analyze(
        self,
        text: str,
        text_id: str = "",
        context_symbols: Optional[List[str]] = None,
    ) -> SentimentResult:
        """
        Analyze sentiment of text.
        
        Args:
            text: Text to analyze
            text_id: Identifier for the text
            context_symbols: Symbols mentioned (for entity sentiment)
            
        Returns:
            SentimentResult with scores and analysis
        """
        start_time = datetime.now()
        
        # Preprocess
        text = text[:self.config.max_text_length]
        text_lower = text.lower()
        words = text_lower.split()
        
        # Calculate overall sentiment
        pos_score, neg_score, pos_phrases, neg_phrases = self._score_text(text_lower, words)
        
        # Check patterns
        pattern_score = self._check_patterns(text_lower)
        
        # Combine scores
        raw_score = (pos_score - neg_score) + pattern_score
        
        # Normalize to -1 to 1
        overall_score = max(-1, min(1, raw_score / 5))
        
        # Magnitude (absolute strength)
        magnitude = (pos_score + neg_score) / max(1, len(words)) * 10
        magnitude = min(1, magnitude)
        
        # Label
        overall_label = self._score_to_label(overall_score)
        
        # Confidence based on word coverage and magnitude
        confidence = min(1, (pos_score + neg_score) / 10 + magnitude)
        
        # Entity sentiment
        entities = []
        if self.config.extract_entities and context_symbols:
            entities = self._analyze_entity_sentiment(text, context_symbols)
            
        # Topics
        topics = []
        if self.config.extract_topics:
            topics = self._extract_topics(text_lower)
            
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SentimentResult(
            text_id=text_id,
            timestamp=datetime.now(),
            overall_score=overall_score,
            overall_label=overall_label,
            overall_confidence=confidence,
            magnitude=magnitude,
            entities=entities,
            positive_phrases=pos_phrases,
            negative_phrases=neg_phrases,
            topics=topics,
            processing_time_ms=processing_time,
        )
    
    def _score_text(
        self,
        text_lower: str,
        words: List[str],
    ) -> Tuple[float, float, List[str], List[str]]:
        """Score text using lexicon."""
        pos_score = 0.0
        neg_score = 0.0
        pos_phrases = []
        neg_phrases = []
        
        # Track negation window
        negation_active = False
        negation_countdown = 0
        
        for i, word in enumerate(words):
            # Check negation
            if word in self._negations:
                negation_active = True
                negation_countdown = 3  # Affect next 3 words
                continue
                
            if negation_countdown > 0:
                negation_countdown -= 1
            else:
                negation_active = False
                
            # Check intensifier
            intensifier = 1.0
            if i > 0 and words[i-1] in self._intensifiers:
                intensifier = 1.5
                
            # Score word
            if word in self._positive_words:
                if negation_active:
                    neg_score += 1 * intensifier
                    neg_phrases.append(f"not {word}" if negation_active else word)
                else:
                    pos_score += 1 * intensifier
                    pos_phrases.append(word)
                    
            elif word in self._negative_words:
                if negation_active:
                    pos_score += 1 * intensifier
                    pos_phrases.append(f"not {word}")
                else:
                    neg_score += 1 * intensifier
                    neg_phrases.append(word)
                    
        return pos_score, neg_score, pos_phrases[:10], neg_phrases[:10]
    
    def _check_patterns(self, text_lower: str) -> float:
        """Check for domain-specific patterns."""
        score = 0.0
        
        for pattern in self._bullish_patterns:
            if re.search(pattern, text_lower):
                score += 1.0
                
        for pattern in self._bearish_patterns:
            if re.search(pattern, text_lower):
                score -= 1.0
                
        return score
    
    def _score_to_label(self, score: float) -> SentimentLabel:
        """Convert score to label."""
        if score >= 0.5:
            return SentimentLabel.VERY_BULLISH
        elif score >= self.config.neutral_threshold:
            return SentimentLabel.BULLISH
        elif score <= -0.5:
            return SentimentLabel.VERY_BEARISH
        elif score <= -self.config.neutral_threshold:
            return SentimentLabel.BEARISH
        else:
            return SentimentLabel.NEUTRAL
    
    def _analyze_entity_sentiment(
        self,
        text: str,
        symbols: List[str],
    ) -> List[EntitySentiment]:
        """Analyze sentiment for specific entities."""
        entities = []
        
        for symbol in symbols:
            # Find sentences mentioning the symbol
            sentences = self._find_entity_sentences(text, symbol)
            
            if not sentences:
                continue
                
            # Analyze each sentence
            scores = []
            snippets = []
            
            for sentence in sentences[:5]:
                result = self.analyze(sentence, f"entity_{symbol}")
                scores.append(result.overall_score)
                snippets.append(sentence[:100])
                
            avg_score = sum(scores) / len(scores)
            
            entities.append(EntitySentiment(
                entity=symbol,
                entity_type="symbol",
                sentiment_score=avg_score,
                sentiment_label=self._score_to_label(avg_score),
                confidence=min(1, len(sentences) / 3),
                mentions=len(sentences),
                context_snippets=snippets,
            ))
            
        return entities
    
    def _find_entity_sentences(
        self,
        text: str,
        entity: str,
    ) -> List[str]:
        """Find sentences mentioning entity."""
        sentences = re.split(r'[.!?]+', text)
        entity_lower = entity.lower()
        
        return [
            s.strip()
            for s in sentences
            if entity_lower in s.lower() or f"${entity}" in s
        ]
    
    def _extract_topics(self, text_lower: str) -> List[str]:
        """Extract topics from text."""
        topics = []
        
        topic_patterns = {
            "earnings": r"(?:earnings|quarterly results|q[1-4]|fiscal)",
            "guidance": r"(?:guidance|outlook|forecast)",
            "merger": r"(?:merger|acquisition|m&a|takeover)",
            "regulatory": r"(?:sec|fda|regulation|compliance)",
            "rates": r"(?:interest rate|fed|fomc|monetary)",
            "layoffs": r"(?:layoff|job cut|restructur)",
            "product": r"(?:launch|release|new product|announcement)",
        }
        
        for topic, pattern in topic_patterns.items():
            if re.search(pattern, text_lower):
                topics.append(topic)
                
        return topics


class BatchSentimentAnalyzer:
    """
    Batch processing for sentiment analysis.
    """
    
    def __init__(self, analyzer: Optional[SentimentAnalyzer] = None):
        self.analyzer = analyzer or SentimentAnalyzer()
        
    def analyze_batch(
        self,
        texts: List[Tuple[str, str]],  # (text_id, text)
    ) -> List[SentimentResult]:
        """Analyze batch of texts."""
        return [
            self.analyzer.analyze(text, text_id)
            for text_id, text in texts
        ]
    
    def get_aggregate_sentiment(
        self,
        results: List[SentimentResult],
    ) -> Dict[str, Any]:
        """Aggregate sentiment across multiple results."""
        if not results:
            return {"count": 0}
            
        scores = [r.overall_score for r in results]
        
        return {
            "count": len(results),
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "bullish_count": len([r for r in results if r.overall_label in (SentimentLabel.BULLISH, SentimentLabel.VERY_BULLISH)]),
            "bearish_count": len([r for r in results if r.overall_label in (SentimentLabel.BEARISH, SentimentLabel.VERY_BEARISH)]),
            "neutral_count": len([r for r in results if r.overall_label == SentimentLabel.NEUTRAL]),
        }
