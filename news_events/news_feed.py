"""
Multi-Source News Feed Aggregation
==================================
Aggregates news from multiple sources for trading signals.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Set
from enum import Enum
from collections import defaultdict
import logging
import hashlib
import re

logger = logging.getLogger(__name__)


class NewsSource(Enum):
    """News sources."""
    # Financial News
    BLOOMBERG = "bloomberg"
    REUTERS = "reuters"
    CNBC = "cnbc"
    WSJ = "wsj"
    FT = "ft"
    MARKETWATCH = "marketwatch"
    BENZINGA = "benzinga"
    
    # Crypto
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    THE_BLOCK = "the_block"
    DECRYPT = "decrypt"
    
    # Social
    TWITTER = "twitter"
    REDDIT = "reddit"
    STOCKTWITS = "stocktwits"
    
    # Regulatory
    SEC = "sec"
    FED = "fed"
    
    # General
    AP = "ap"
    UNKNOWN = "unknown"


class NewsCategory(Enum):
    """News categories."""
    EARNINGS = "earnings"
    M_AND_A = "m_and_a"
    IPO = "ipo"
    GUIDANCE = "guidance"
    DIVIDEND = "dividend"
    BUYBACK = "buyback"
    INSIDER = "insider"
    
    MACRO = "macro"
    FED = "fed"
    RATES = "rates"
    INFLATION = "inflation"
    GDP = "gdp"
    EMPLOYMENT = "employment"
    
    REGULATORY = "regulatory"
    LAWSUIT = "lawsuit"
    INVESTIGATION = "investigation"
    
    PRODUCT = "product"
    PARTNERSHIP = "partnership"
    MANAGEMENT = "management"
    
    CRYPTO = "crypto"
    DEFI = "defi"
    NFT = "nft"
    
    GEOPOLITICAL = "geopolitical"
    WEATHER = "weather"
    COMMODITY = "commodity"
    
    ANALYST = "analyst"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    
    GENERAL = "general"


class Urgency(Enum):
    """News urgency level."""
    FLASH = 5  # Breaking, immediate action
    URGENT = 4  # Important, act soon
    NORMAL = 3  # Standard news
    LOW = 2  # Background info
    ARCHIVE = 1  # Old news


@dataclass
class NewsArticle:
    """Single news article."""
    id: str
    source: NewsSource
    headline: str
    timestamp: datetime
    
    # Content
    summary: str = ""
    body: str = ""
    url: str = ""
    
    # Classification
    category: NewsCategory = NewsCategory.GENERAL
    urgency: Urgency = Urgency.NORMAL
    
    # Entities
    symbols: List[str] = field(default_factory=list)
    companies: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    
    # Sentiment (pre-computed if available)
    sentiment_score: Optional[float] = None  # -1 to 1
    sentiment_magnitude: Optional[float] = None
    
    # Metadata
    author: str = ""
    tags: List[str] = field(default_factory=list)
    language: str = "en"
    
    # Processing
    processed_at: Optional[datetime] = None
    is_duplicate: bool = False
    
    @property
    def age_seconds(self) -> float:
        return (datetime.now() - self.timestamp).total_seconds()
    
    @property
    def is_stale(self) -> bool:
        return self.age_seconds > 3600  # 1 hour
    
    @property
    def is_breaking(self) -> bool:
        return self.urgency == Urgency.FLASH and self.age_seconds < 300
    
    def content_hash(self) -> str:
        """Hash for deduplication."""
        content = f"{self.headline}{self.source.value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.value,
            "headline": self.headline,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "category": self.category.value,
            "urgency": self.urgency.value,
            "symbols": self.symbols,
            "sentiment_score": self.sentiment_score,
            "age_seconds": self.age_seconds,
        }


@dataclass
class FeedConfig:
    """Configuration for news feed."""
    # Sources to include
    enabled_sources: Set[NewsSource] = field(default_factory=lambda: {
        NewsSource.BLOOMBERG,
        NewsSource.REUTERS,
        NewsSource.BENZINGA,
    })
    
    # Filtering
    min_urgency: Urgency = Urgency.LOW
    categories: Optional[Set[NewsCategory]] = None  # None = all
    symbols_filter: Optional[Set[str]] = None  # None = all
    
    # Deduplication
    dedup_window_hours: float = 24.0
    similarity_threshold: float = 0.8
    
    # History
    max_articles: int = 10000
    
    # Processing
    auto_categorize: bool = True
    auto_extract_symbols: bool = True


class NewsFeed:
    """
    Aggregates news from multiple sources.
    
    Features:
    - Multi-source aggregation
    - Deduplication
    - Category classification
    - Symbol extraction
    - Real-time streaming
    """
    
    def __init__(self, config: Optional[FeedConfig] = None):
        self.config = config or FeedConfig()
        
        # Article storage
        self._articles: Dict[str, NewsArticle] = {}
        self._article_order: List[str] = []  # Ordered by time
        
        # Deduplication
        self._seen_hashes: Dict[str, datetime] = {}
        
        # Indices for fast lookup
        self._by_symbol: Dict[str, List[str]] = defaultdict(list)
        self._by_category: Dict[NewsCategory, List[str]] = defaultdict(list)
        self._by_source: Dict[NewsSource, List[str]] = defaultdict(list)
        
        # Callbacks
        self._callbacks: List[Callable[[NewsArticle], None]] = []
        
        # Symbol patterns
        self._symbol_patterns = [
            r'\$([A-Z]{1,5})\b',  # $AAPL
            r'\b([A-Z]{2,5})(?:\s+(?:shares|stock|Inc|Corp|Ltd))',  # AAPL shares
        ]
        
    def register_callback(self, callback: Callable[[NewsArticle], None]):
        """Register callback for new articles."""
        self._callbacks.append(callback)
        
    def _notify(self, article: NewsArticle):
        """Notify callbacks of new article."""
        for cb in self._callbacks:
            try:
                cb(article)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def add_article(self, article: NewsArticle) -> bool:
        """
        Add article to feed.
        
        Returns True if article was added (not duplicate).
        """
        # Check source filter
        if article.source not in self.config.enabled_sources:
            return False
            
        # Check urgency filter
        if article.urgency.value < self.config.min_urgency.value:
            return False
            
        # Check deduplication
        content_hash = article.content_hash()
        if self._is_duplicate(content_hash, article.headline):
            article.is_duplicate = True
            return False
            
        self._seen_hashes[content_hash] = datetime.now()
        
        # Process article
        if self.config.auto_extract_symbols and not article.symbols:
            article.symbols = self._extract_symbols(article.headline + " " + article.summary)
            
        if self.config.auto_categorize and article.category == NewsCategory.GENERAL:
            article.category = self._categorize(article.headline + " " + article.summary)
            
        # Check category filter
        if self.config.categories and article.category not in self.config.categories:
            return False
            
        # Check symbol filter
        if self.config.symbols_filter:
            if not any(s in self.config.symbols_filter for s in article.symbols):
                return False
                
        # Store article
        article.processed_at = datetime.now()
        self._articles[article.id] = article
        self._article_order.append(article.id)
        
        # Update indices
        for symbol in article.symbols:
            self._by_symbol[symbol].append(article.id)
        self._by_category[article.category].append(article.id)
        self._by_source[article.source].append(article.id)
        
        # Cleanup if needed
        self._cleanup()
        
        # Notify
        self._notify(article)
        
        return True
    
    def _is_duplicate(self, content_hash: str, headline: str) -> bool:
        """Check if article is duplicate."""
        # Exact hash match
        if content_hash in self._seen_hashes:
            hash_time = self._seen_hashes[content_hash]
            if (datetime.now() - hash_time).total_seconds() < self.config.dedup_window_hours * 3600:
                return True
                
        # TODO: Fuzzy matching for similar headlines
        
        return False
    
    def _extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text."""
        symbols = set()
        
        for pattern in self._symbol_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                symbol = match.upper()
                if len(symbol) >= 1 and len(symbol) <= 5:
                    # Filter out common words
                    if symbol not in {"A", "I", "AT", "BY", "FOR", "TO", "IS", "IT", "ON", "IN"}:
                        symbols.add(symbol)
                        
        return list(symbols)
    
    def _categorize(self, text: str) -> NewsCategory:
        """Categorize article based on text."""
        text_lower = text.lower()
        
        # Check keywords for each category
        category_keywords = {
            NewsCategory.EARNINGS: ["earnings", "eps", "revenue", "quarterly", "beat", "miss", "guidance"],
            NewsCategory.M_AND_A: ["acquisition", "merger", "acquire", "takeover", "deal", "buyout"],
            NewsCategory.IPO: ["ipo", "initial public offering", "public debut", "going public"],
            NewsCategory.FED: ["federal reserve", "fomc", "powell", "interest rate", "fed "],
            NewsCategory.MACRO: ["gdp", "inflation", "employment", "jobs report", "cpi", "pce"],
            NewsCategory.REGULATORY: ["sec", "regulation", "compliance", "investigation", "fine"],
            NewsCategory.CRYPTO: ["bitcoin", "crypto", "blockchain", "ethereum", "defi"],
            NewsCategory.ANALYST: ["upgrade", "downgrade", "price target", "rating", "analyst"],
            NewsCategory.INSIDER: ["insider", "director bought", "ceo sold", "form 4"],
            NewsCategory.DIVIDEND: ["dividend", "distribution", "yield"],
            NewsCategory.BUYBACK: ["buyback", "repurchase", "share repurchase"],
        }
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
                    
        return NewsCategory.GENERAL
    
    def _cleanup(self):
        """Remove old articles."""
        if len(self._articles) <= self.config.max_articles:
            return
            
        # Remove oldest articles
        while len(self._article_order) > self.config.max_articles:
            old_id = self._article_order.pop(0)
            if old_id in self._articles:
                del self._articles[old_id]
                
        # Clean hash cache
        cutoff = datetime.now() - timedelta(hours=self.config.dedup_window_hours)
        self._seen_hashes = {
            h: t for h, t in self._seen_hashes.items()
            if t > cutoff
        }
    
    def get_article(self, article_id: str) -> Optional[NewsArticle]:
        """Get article by ID."""
        return self._articles.get(article_id)
    
    def get_recent(
        self,
        limit: int = 50,
        symbol: Optional[str] = None,
        category: Optional[NewsCategory] = None,
        source: Optional[NewsSource] = None,
        max_age_hours: Optional[float] = None,
    ) -> List[NewsArticle]:
        """Get recent articles with filters."""
        # Start with all articles or filtered subset
        if symbol:
            article_ids = self._by_symbol.get(symbol, [])
        elif category:
            article_ids = self._by_category.get(category, [])
        elif source:
            article_ids = self._by_source.get(source, [])
        else:
            article_ids = self._article_order
            
        # Filter and collect
        articles = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours) if max_age_hours else None
        
        for aid in reversed(article_ids):  # Most recent first
            if len(articles) >= limit:
                break
                
            article = self._articles.get(aid)
            if not article:
                continue
                
            if cutoff and article.timestamp < cutoff:
                continue
                
            articles.append(article)
            
        return articles
    
    def get_breaking_news(self, max_age_seconds: int = 300) -> List[NewsArticle]:
        """Get breaking/flash news."""
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        
        return [
            a for a in self._articles.values()
            if a.urgency == Urgency.FLASH and a.timestamp > cutoff
        ]
    
    def get_symbol_news_count(
        self,
        symbol: str,
        hours: float = 24,
    ) -> Dict[str, int]:
        """Get news count breakdown for symbol."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        articles = [
            self._articles[aid]
            for aid in self._by_symbol.get(symbol, [])
            if aid in self._articles and self._articles[aid].timestamp > cutoff
        ]
        
        return {
            "total": len(articles),
            "breaking": len([a for a in articles if a.urgency == Urgency.FLASH]),
            "urgent": len([a for a in articles if a.urgency == Urgency.URGENT]),
            "by_category": {
                cat.value: len([a for a in articles if a.category == cat])
                for cat in NewsCategory
                if any(a.category == cat for a in articles)
            },
        }
    
    def get_trending_symbols(
        self,
        hours: float = 1,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get symbols with most news activity."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        symbol_counts: Dict[str, int] = defaultdict(int)
        
        for article in self._articles.values():
            if article.timestamp > cutoff:
                for symbol in article.symbols:
                    symbol_counts[symbol] += 1
                    
        # Sort by count
        sorted_symbols = sorted(
            symbol_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]
        
        return [
            {"symbol": s, "news_count": c, "period_hours": hours}
            for s, c in sorted_symbols
        ]
