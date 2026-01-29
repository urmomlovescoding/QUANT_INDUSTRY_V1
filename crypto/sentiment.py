"""
Crypto Sentiment Engine
Social media and news sentiment analysis for crypto.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


class SentimentSource(Enum):
    """Sentiment data sources."""
    TWITTER = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    NEWS = "news"
    FEAR_GREED = "fear_greed"


class SentimentLevel(Enum):
    """Sentiment classification levels."""
    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"


@dataclass
class SentimentScore:
    """Sentiment score for a token or market."""
    token: str
    score: float  # -1 to 1
    level: SentimentLevel
    sources: Dict[SentimentSource, float] = field(default_factory=dict)
    volume: int = 0  # Number of data points
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_bullish(self) -> bool:
        return self.score > 0.2
    
    @property
    def is_bearish(self) -> bool:
        return self.score < -0.2


@dataclass
class SocialMention:
    """Social media mention."""
    source: SentimentSource
    text: str
    sentiment: float
    token: str
    author: Optional[str] = None
    engagement: int = 0  # Likes, retweets, etc.
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CryptoSentimentEngine:
    """
    Crypto-specific sentiment analysis engine.
    
    Features:
    - Twitter/X sentiment (Crypto Twitter)
    - Reddit sentiment (r/cryptocurrency, r/bitcoin, etc.)
    - News sentiment
    - Fear & Greed Index tracking
    - Influencer impact weighting
    - Token-specific sentiment scoring
    
    Signal Generation:
    - Extreme fear = potential buy signal
    - Extreme greed = potential sell signal
    - Sentiment divergence from price = opportunity
    """
    
    # API endpoints
    APIS = {
        "fear_greed": "https://api.alternative.me/fng/",
        "lunarcrush": "https://api.lunarcrush.com/v2",
        "santiment": "https://api.santiment.net/graphql",
    }
    
    # Sentiment keywords for basic analysis
    BULLISH_KEYWORDS = [
        "moon", "bullish", "buy", "long", "pump", "breakout", "ath",
        "accumulate", "hodl", "rocket", "gains", "parabolic", "green"
    ]
    
    BEARISH_KEYWORDS = [
        "dump", "bearish", "sell", "short", "crash", "collapse", "rekt",
        "capitulation", "dead", "scam", "rug", "fear", "panic", "red"
    ]
    
    # Major crypto influencers (simplified list)
    INFLUENCERS = {
        "elonmusk": 3.0,
        "michael_saylor": 2.5,
        "caborat": 2.0,
        "vikibi": 2.0,
        "inversebrah": 1.8,
    }
    
    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None
    ):
        self.api_keys = api_keys or {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._scores: Dict[str, SentimentScore] = {}
        self._mentions: List[SocialMention] = []
        self._fear_greed_history: List[Dict[str, Any]] = []
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _classify_sentiment(self, score: float) -> SentimentLevel:
        """Classify sentiment score to level."""
        if score <= -0.6:
            return SentimentLevel.EXTREME_FEAR
        elif score <= -0.2:
            return SentimentLevel.FEAR
        elif score <= 0.2:
            return SentimentLevel.NEUTRAL
        elif score <= 0.6:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED
    
    def _analyze_text_sentiment(self, text: str) -> float:
        """
        Simple keyword-based sentiment analysis.
        
        For production, use VADER, FinBERT, or similar.
        
        Returns:
            Sentiment score from -1 (bearish) to 1 (bullish)
        """
        text_lower = text.lower()
        
        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text_lower)
        
        total = bullish_count + bearish_count
        if total == 0:
            return 0.0
        
        return (bullish_count - bearish_count) / total
    
    async def fetch_fear_greed_index(self) -> Dict[str, Any]:
        """
        Fetch Bitcoin Fear & Greed Index.
        
        Returns:
            Current fear & greed data
        """
        session = await self._get_session()
        
        try:
            url = f"{self.APIS['fear_greed']}?limit=30"
            async with session.get(url) as response:
                data = await response.json()
            
            if data.get("data"):
                current = data["data"][0]
                
                # Store history
                self._fear_greed_history = data["data"]
                
                value = int(current["value"])
                
                if value <= 25:
                    level = SentimentLevel.EXTREME_FEAR
                elif value <= 45:
                    level = SentimentLevel.FEAR
                elif value <= 55:
                    level = SentimentLevel.NEUTRAL
                elif value <= 75:
                    level = SentimentLevel.GREED
                else:
                    level = SentimentLevel.EXTREME_GREED
                
                return {
                    "value": value,
                    "level": level.value,
                    "classification": current["value_classification"],
                    "timestamp": datetime.fromtimestamp(int(current["timestamp"])).isoformat(),
                    "history_avg_7d": sum(int(d["value"]) for d in data["data"][:7]) / 7,
                    "history_avg_30d": sum(int(d["value"]) for d in data["data"]) / len(data["data"])
                }
            
            return {"error": "No data available"}
            
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
            return {"error": str(e)}
    
    def analyze_social_mentions(
        self,
        mentions: List[Dict[str, Any]],
        token: str
    ) -> SentimentScore:
        """
        Analyze a batch of social media mentions.
        
        Args:
            mentions: List of mention data
            token: Token symbol
        
        Returns:
            Aggregated sentiment score
        """
        if not mentions:
            return SentimentScore(
                token=token,
                score=0.0,
                level=SentimentLevel.NEUTRAL,
                volume=0
            )
        
        total_score = 0.0
        total_weight = 0.0
        source_scores: Dict[SentimentSource, List[float]] = defaultdict(list)
        
        for mention in mentions:
            text = mention.get("text", "")
            source = mention.get("source", SentimentSource.TWITTER)
            author = mention.get("author", "").lower()
            engagement = mention.get("engagement", 1)
            
            # Calculate sentiment
            sentiment = self._analyze_text_sentiment(text)
            
            # Weight by engagement
            weight = max(1, min(100, engagement / 100))
            
            # Boost by influencer
            if author in self.INFLUENCERS:
                weight *= self.INFLUENCERS[author]
            
            total_score += sentiment * weight
            total_weight += weight
            
            # Track by source
            if isinstance(source, str):
                try:
                    source = SentimentSource(source)
                except ValueError:
                    source = SentimentSource.TWITTER
            
            source_scores[source].append(sentiment)
            
            # Store mention
            self._mentions.append(SocialMention(
                source=source,
                text=text[:500],
                sentiment=sentiment,
                token=token,
                author=author,
                engagement=engagement
            ))
        
        # Calculate final score
        final_score = total_score / total_weight if total_weight > 0 else 0.0
        
        # Calculate per-source averages
        sources = {
            source: sum(scores) / len(scores)
            for source, scores in source_scores.items()
        }
        
        score = SentimentScore(
            token=token,
            score=final_score,
            level=self._classify_sentiment(final_score),
            sources=sources,
            volume=len(mentions)
        )
        
        self._scores[token] = score
        return score
    
    def generate_trading_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals from sentiment data.
        
        Returns:
            List of trading signals
        """
        signals = []
        
        for token, score in self._scores.items():
            # Extreme fear = potential buy
            if score.level == SentimentLevel.EXTREME_FEAR:
                signals.append({
                    "token": token,
                    "signal": "BUY",
                    "strength": abs(score.score),
                    "reasoning": "Extreme fear - contrarian buy signal",
                    "sentiment_score": score.score,
                    "sentiment_level": score.level.value,
                    "confidence": min(0.8, score.volume / 100),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Extreme greed = potential sell
            elif score.level == SentimentLevel.EXTREME_GREED:
                signals.append({
                    "token": token,
                    "signal": "SELL",
                    "strength": abs(score.score),
                    "reasoning": "Extreme greed - contrarian sell signal",
                    "sentiment_score": score.score,
                    "sentiment_level": score.level.value,
                    "confidence": min(0.8, score.volume / 100),
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        return signals
    
    def get_sentiment_summary(self) -> Dict[str, Any]:
        """Get summary of current sentiment data."""
        if not self._scores:
            return {"message": "No sentiment data. Analyze some mentions first."}
        
        bullish_tokens = [t for t, s in self._scores.items() if s.is_bullish]
        bearish_tokens = [t for t, s in self._scores.items() if s.is_bearish]
        
        avg_sentiment = sum(s.score for s in self._scores.values()) / len(self._scores)
        
        return {
            "total_tokens_tracked": len(self._scores),
            "bullish_count": len(bullish_tokens),
            "bearish_count": len(bearish_tokens),
            "bullish_tokens": bullish_tokens,
            "bearish_tokens": bearish_tokens,
            "average_sentiment": avg_sentiment,
            "market_mood": self._classify_sentiment(avg_sentiment).value,
            "total_mentions_analyzed": len(self._mentions),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_token_sentiment(self, token: str) -> Optional[Dict[str, Any]]:
        """Get detailed sentiment for a specific token."""
        score = self._scores.get(token.upper())
        
        if not score:
            return None
        
        recent_mentions = [
            {
                "text": m.text[:200],
                "sentiment": m.sentiment,
                "source": m.source.value,
                "engagement": m.engagement
            }
            for m in self._mentions[-100:]
            if m.token == token.upper()
        ]
        
        return {
            "token": token.upper(),
            "score": score.score,
            "level": score.level.value,
            "is_bullish": score.is_bullish,
            "is_bearish": score.is_bearish,
            "sources": {k.value: v for k, v in score.sources.items()},
            "volume": score.volume,
            "recent_mentions": recent_mentions[:10],
            "timestamp": score.timestamp.isoformat()
        }
    
    async def get_market_sentiment(self) -> Dict[str, Any]:
        """
        Get overall crypto market sentiment.
        
        Combines Fear & Greed with social sentiment.
        """
        fear_greed = await self.fetch_fear_greed_index()
        social_summary = self.get_sentiment_summary()
        
        # Combine indicators
        fg_score = fear_greed.get("value", 50) / 50 - 1  # Normalize to -1 to 1
        social_score = social_summary.get("average_sentiment", 0)
        
        combined_score = (fg_score * 0.6 + social_score * 0.4)  # Weight FG more
        
        return {
            "combined_score": combined_score,
            "combined_level": self._classify_sentiment(combined_score).value,
            "fear_greed": fear_greed,
            "social_sentiment": social_summary,
            "recommendation": self._get_recommendation(combined_score),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _get_recommendation(self, score: float) -> str:
        """Get trading recommendation based on sentiment."""
        if score <= -0.6:
            return "Strong contrarian BUY - Extreme fear often marks bottoms"
        elif score <= -0.2:
            return "Mild BUY bias - Market fearful but not extreme"
        elif score <= 0.2:
            return "NEUTRAL - No strong sentiment signal"
        elif score <= 0.6:
            return "Mild SELL bias - Market greedy but not extreme"
        else:
            return "Strong contrarian SELL - Extreme greed often marks tops"
