"""
QUANT_INDUSTRY_V1 Sentiment Analysis Engine

Multi-source sentiment analysis for trading signals.

Features:
- News sentiment extraction
- Social media analysis (Twitter/X, Reddit, StockTwits)
- Fear & Greed Index calculation
- Earnings call tone analysis
- Analyst sentiment tracking
- Retail vs institutional sentiment divergence
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
import re
import logging
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# SENTIMENT TYPES
# =============================================================================

class SentimentSource(Enum):
    """Sentiment data sources."""
    NEWS = "news"
    TWITTER = "twitter"
    REDDIT = "reddit"
    STOCKTWITS = "stocktwits"
    EARNINGS = "earnings"
    ANALYST = "analyst"
    OPTIONS = "options"  # Put/Call sentiment


class SentimentLevel(Enum):
    """Sentiment classification levels."""
    VERY_BEARISH = -2
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1
    VERY_BULLISH = 2


@dataclass
class SentimentData:
    """Single sentiment data point."""
    timestamp: datetime
    source: SentimentSource
    symbol: str
    score: float  # -1 to 1
    magnitude: float  # 0 to 1 (strength)
    volume: int = 1  # Number of mentions/posts
    raw_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        """Score weighted by magnitude."""
        return self.score * self.magnitude


# =============================================================================
# TEXT SENTIMENT ANALYZER
# =============================================================================

class TextSentimentAnalyzer:
    """
    Rule-based and lexicon sentiment analysis.

    Uses financial-specific lexicons for accuracy.
    """

    # Financial sentiment lexicons
    POSITIVE_WORDS = {
        # Strong positive
        'bullish', 'surge', 'soar', 'rally', 'boom', 'skyrocket', 'moonshot',
        'breakout', 'outperform', 'upgrade', 'beat', 'exceed', 'record',
        'all-time-high', 'ath', 'rocket', 'moon', 'parabolic', 'squeeze',
        'accumulate', 'strong', 'momentum', 'catalyst', 'growth',
        # Moderate positive
        'buy', 'long', 'calls', 'upside', 'gain', 'profit', 'recovery',
        'support', 'bounce', 'rebound', 'uptick', 'green', 'positive',
        'optimistic', 'opportunity', 'undervalued', 'bargain', 'cheap',
    }

    NEGATIVE_WORDS = {
        # Strong negative
        'bearish', 'crash', 'plunge', 'collapse', 'dump', 'tank', 'crater',
        'breakdown', 'underperform', 'downgrade', 'miss', 'fail', 'fraud',
        'bankruptcy', 'default', 'recession', 'capitulation', 'panic',
        # Moderate negative
        'sell', 'short', 'puts', 'downside', 'loss', 'risk', 'decline',
        'resistance', 'selloff', 'correction', 'red', 'negative',
        'pessimistic', 'overvalued', 'expensive', 'bubble', 'warning',
    }

    INTENSIFIERS = {
        'very', 'extremely', 'incredibly', 'absolutely', 'definitely',
        'strongly', 'highly', 'massively', 'huge', 'major', 'big',
    }

    NEGATIONS = {
        'not', 'no', 'never', 'neither', 'nobody', 'nothing',
        "n't", "dont", "doesnt", "isnt", "arent", "wont", "cant",
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.ticker_pattern = re.compile(r'\$([A-Z]{1,5})\b')
        self.cashtag_pattern = re.compile(r'#([A-Za-z]+)\b')
        self.url_pattern = re.compile(r'https?://\S+')
        self.emoji_pattern = re.compile(r'[[LAUNCH]🌙💎🙌[UP][DOWN]🐂🐻[$]🔥⬆️⬇️❤️👍👎]')

    def analyze(self, text: str) -> Tuple[float, float]:
        """
        Analyze text sentiment.

        Returns: (score, magnitude)
        - score: -1 to 1
        - magnitude: 0 to 1
        """
        if not text:
            return 0.0, 0.0

        # Preprocess
        text = text.lower()
        text = self.url_pattern.sub('', text)

        words = text.split()
        if not words:
            return 0.0, 0.0

        positive_count = 0
        negative_count = 0
        total_weight = 0

        prev_word = ""
        for word in words:
            # Clean word
            word = re.sub(r'[^\w]', '', word)
            if not word:
                continue

            # Check for intensifier
            intensity = 1.5 if prev_word in self.INTENSIFIERS else 1.0

            # Check for negation
            negated = prev_word in self.NEGATIONS

            if word in self.POSITIVE_WORDS:
                if negated:
                    negative_count += intensity
                else:
                    positive_count += intensity
                total_weight += intensity

            elif word in self.NEGATIVE_WORDS:
                if negated:
                    positive_count += intensity
                else:
                    negative_count += intensity
                total_weight += intensity

            prev_word = word

        # Emoji sentiment
        emojis = self.emoji_pattern.findall(text)
        for emoji in emojis:
            if emoji in ['[LAUNCH]', '🌙', '💎', '🙌', '[UP]', '🐂', '[$]', '🔥', '⬆️', '❤️', '👍']:
                positive_count += 0.5
                total_weight += 0.5
            elif emoji in ['[DOWN]', '🐻', '⬇️', '👎']:
                negative_count += 0.5
                total_weight += 0.5

        # Calculate score
        if positive_count + negative_count == 0:
            return 0.0, 0.0

        score = (positive_count - negative_count) / (positive_count + negative_count)

        # Magnitude based on word coverage
        magnitude = min(1.0, total_weight / max(len(words) * 0.2, 1))

        return score, magnitude

    def extract_tickers(self, text: str) -> List[str]:
        """Extract ticker symbols from text."""
        cashtags = self.ticker_pattern.findall(text)
        return list(set(cashtags))

    def classify_sentiment(self, score: float) -> SentimentLevel:
        """Classify sentiment score into levels."""
        if score >= 0.5:
            return SentimentLevel.VERY_BULLISH
        elif score >= 0.15:
            return SentimentLevel.BULLISH
        elif score <= -0.5:
            return SentimentLevel.VERY_BEARISH
        elif score <= -0.15:
            return SentimentLevel.BEARISH
        return SentimentLevel.NEUTRAL


# =============================================================================
# AGGREGATED SENTIMENT TRACKER
# =============================================================================

class SentimentAggregator:
    """
    Aggregate sentiment from multiple sources.

    Tracks sentiment over time with decay.
    """

    def __init__(
        self,
        decay_halflife_hours: float = 24.0,
        min_samples: int = 5,
    ):
        self.decay_halflife = timedelta(hours=decay_halflife_hours)
        self.min_samples = min_samples

        # Sentiment storage by symbol and source
        self.sentiment_data: Dict[str, Dict[SentimentSource, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=10000))
        )

        # Source weights
        self.source_weights = {
            SentimentSource.NEWS: 0.25,
            SentimentSource.TWITTER: 0.15,
            SentimentSource.REDDIT: 0.15,
            SentimentSource.STOCKTWITS: 0.10,
            SentimentSource.EARNINGS: 0.15,
            SentimentSource.ANALYST: 0.15,
            SentimentSource.OPTIONS: 0.05,
        }

    def add_sentiment(self, data: SentimentData) -> None:
        """Add new sentiment data point."""
        self.sentiment_data[data.symbol][data.source].append(data)

    def get_sentiment(
        self,
        symbol: str,
        lookback_hours: float = 24.0,
        source: SentimentSource = None,
    ) -> Dict[str, float]:
        """
        Get aggregated sentiment for a symbol.

        Returns dict with sentiment metrics.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=lookback_hours)

        all_scores = []
        all_magnitudes = []
        volume_total = 0

        sources_to_check = [source] if source else list(SentimentSource)

        for src in sources_to_check:
            if symbol not in self.sentiment_data:
                continue

            if src not in self.sentiment_data[symbol]:
                continue

            for data in self.sentiment_data[symbol][src]:
                if data.timestamp < cutoff:
                    continue

                # Apply time decay
                age = (now - data.timestamp).total_seconds() / 3600
                decay_factor = 0.5 ** (age / (self.decay_halflife.total_seconds() / 3600))

                # Weight by source and decay
                weight = self.source_weights.get(src, 0.1) * decay_factor * data.magnitude

                all_scores.append(data.score * weight)
                all_magnitudes.append(weight)
                volume_total += data.volume

        if len(all_scores) < self.min_samples:
            return {
                'sentiment_score': 0.0,
                'sentiment_magnitude': 0.0,
                'sentiment_volume': 0,
                'sentiment_level': SentimentLevel.NEUTRAL.name,
                'sample_count': len(all_scores),
            }

        # Weighted average
        total_weight = sum(all_magnitudes)
        if total_weight > 0:
            sentiment_score = sum(all_scores) / total_weight
        else:
            sentiment_score = 0.0

        sentiment_magnitude = np.mean(all_magnitudes)

        # Classify
        analyzer = TextSentimentAnalyzer()
        level = analyzer.classify_sentiment(sentiment_score)

        return {
            'sentiment_score': sentiment_score,
            'sentiment_magnitude': sentiment_magnitude,
            'sentiment_volume': volume_total,
            'sentiment_level': level.name,
            'sample_count': len(all_scores),
        }

    def get_sentiment_change(
        self,
        symbol: str,
        current_hours: float = 4.0,
        previous_hours: float = 24.0,
    ) -> float:
        """Get sentiment change between periods."""
        current = self.get_sentiment(symbol, current_hours)
        previous = self.get_sentiment(symbol, previous_hours)

        return current['sentiment_score'] - previous['sentiment_score']


# =============================================================================
# FEAR & GREED INDEX
# =============================================================================

class FearGreedIndex:
    """
    Market-wide Fear & Greed Index.

    Components:
    - Market momentum (S&P 500 vs 125-day MA)
    - Stock price breadth (52-week highs vs lows)
    - Put/Call ratio
    - Market volatility (VIX)
    - Safe haven demand (bond vs stock returns)
    - Junk bond demand (spread over investment grade)
    - Social sentiment
    """

    def __init__(self):
        self.components: Dict[str, float] = {}
        self.weights = {
            'momentum': 0.20,
            'breadth': 0.15,
            'put_call': 0.15,
            'volatility': 0.20,
            'safe_haven': 0.10,
            'junk_bond': 0.10,
            'social_sentiment': 0.10,
        }
        self.history: deque = deque(maxlen=252)

    def update_component(self, component: str, value: float) -> None:
        """Update a single component (0-100 scale)."""
        self.components[component] = np.clip(value, 0, 100)

    def calculate(self) -> float:
        """Calculate overall Fear & Greed Index."""
        if not self.components:
            return 50.0

        weighted_sum = 0.0
        total_weight = 0.0

        for component, weight in self.weights.items():
            if component in self.components:
                weighted_sum += self.components[component] * weight
                total_weight += weight

        if total_weight == 0:
            return 50.0

        index = weighted_sum / total_weight
        self.history.append(index)

        return index

    def get_signal(self) -> str:
        """Get trading signal from index."""
        index = self.calculate()

        if index <= 20:
            return "EXTREME_FEAR"
        elif index <= 40:
            return "FEAR"
        elif index <= 60:
            return "NEUTRAL"
        elif index <= 80:
            return "GREED"
        else:
            return "EXTREME_GREED"

    def get_contrarian_signal(self) -> Tuple[str, float]:
        """
        Get contrarian trading signal.

        Extreme fear = buying opportunity
        Extreme greed = selling opportunity
        """
        index = self.calculate()

        if index <= 20:
            return "STRONG_BUY", (25 - index) / 25
        elif index <= 35:
            return "BUY", (40 - index) / 20
        elif index >= 80:
            return "STRONG_SELL", (index - 75) / 25
        elif index >= 65:
            return "SELL", (index - 60) / 20
        else:
            return "HOLD", 0.0


# =============================================================================
# SENTIMENT ENGINE
# =============================================================================

class SentimentEngine:
    """
    Unified sentiment analysis engine.

    Combines all sentiment sources and provides trading signals.
    """

    def __init__(self):
        self.text_analyzer = TextSentimentAnalyzer()
        self.aggregator = SentimentAggregator()
        self.fear_greed = FearGreedIndex()

        # Signal thresholds
        self.extreme_bullish_threshold = 0.6
        self.bullish_threshold = 0.2
        self.bearish_threshold = -0.2
        self.extreme_bearish_threshold = -0.6

    def process_text(
        self,
        text: str,
        source: SentimentSource,
        timestamp: datetime = None,
    ) -> List[SentimentData]:
        """Process text and extract sentiment for all mentioned tickers."""
        timestamp = timestamp or datetime.now(timezone.utc)

        # Analyze sentiment
        score, magnitude = self.text_analyzer.analyze(text)

        # Extract tickers
        tickers = self.text_analyzer.extract_tickers(text)

        # If no tickers found, use generic market sentiment
        if not tickers:
            tickers = ['SPY']

        results = []
        for ticker in tickers:
            data = SentimentData(
                timestamp=timestamp,
                source=source,
                symbol=ticker,
                score=score,
                magnitude=magnitude,
                raw_text=text[:500],  # Truncate
            )
            self.aggregator.add_sentiment(data)
            results.append(data)

        return results

    def get_trading_signal(
        self,
        symbol: str,
        lookback_hours: float = 24.0,
    ) -> Dict[str, Any]:
        """
        Get trading signal based on sentiment.

        Returns dict with signal and confidence.
        """
        sentiment = self.aggregator.get_sentiment(symbol, lookback_hours)
        sentiment_change = self.aggregator.get_sentiment_change(symbol)

        score = sentiment['sentiment_score']

        # Determine signal
        if score >= self.extreme_bullish_threshold:
            signal = "STRONG_BUY"
            confidence = min(1.0, (score - self.extreme_bullish_threshold) / 0.4 + 0.6)
        elif score >= self.bullish_threshold:
            signal = "BUY"
            confidence = (score - self.bullish_threshold) / (self.extreme_bullish_threshold - self.bullish_threshold) * 0.4 + 0.2
        elif score <= self.extreme_bearish_threshold:
            signal = "STRONG_SELL"
            confidence = min(1.0, (self.extreme_bearish_threshold - score) / 0.4 + 0.6)
        elif score <= self.bearish_threshold:
            signal = "SELL"
            confidence = (self.bearish_threshold - score) / (self.bearish_threshold - self.extreme_bearish_threshold) * 0.4 + 0.2
        else:
            signal = "HOLD"
            confidence = 1.0 - abs(score) / self.bullish_threshold

        # Adjust confidence based on volume
        volume_factor = min(1.0, sentiment['sample_count'] / 100)
        confidence *= volume_factor

        return {
            'symbol': symbol,
            'signal': signal,
            'confidence': confidence,
            'sentiment_score': score,
            'sentiment_change': sentiment_change,
            'volume': sentiment['sentiment_volume'],
            'level': sentiment['sentiment_level'],
        }

    def get_market_sentiment(self) -> Dict[str, Any]:
        """Get overall market sentiment."""
        # Get SPY sentiment as market proxy
        spy_sentiment = self.aggregator.get_sentiment('SPY', lookback_hours=24.0)

        # Get Fear & Greed
        fg_index = self.fear_greed.calculate()
        fg_signal = self.fear_greed.get_signal()
        contrarian_signal, contrarian_strength = self.fear_greed.get_contrarian_signal()

        return {
            'market_sentiment': spy_sentiment['sentiment_score'],
            'market_level': spy_sentiment['sentiment_level'],
            'fear_greed_index': fg_index,
            'fear_greed_signal': fg_signal,
            'contrarian_signal': contrarian_signal,
            'contrarian_strength': contrarian_strength,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SentimentSource',
    'SentimentLevel',
    'SentimentData',
    'TextSentimentAnalyzer',
    'SentimentAggregator',
    'FearGreedIndex',
    'SentimentEngine',
]
