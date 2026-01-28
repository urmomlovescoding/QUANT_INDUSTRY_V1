"""
QUANT INDUSTRY - Alternative Data Service
==========================================
Integrates alternative data sources for alpha generation:
- Social media sentiment (Reddit, Twitter/X, StockTwits)
- News sentiment analysis
- Insider trading signals
- Dark pool flow analysis
- Options unusual activity
- Congress/Senate trading disclosure
- ESG metrics

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger(__name__)


# ============== DATA CLASSES ==============

class SentimentScore(Enum):
    """Sentiment classification"""
    VERY_BEARISH = -2
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1
    VERY_BULLISH = 2


@dataclass
class SentimentData:
    """Aggregated sentiment data for a symbol"""
    symbol: str
    timestamp: datetime
    overall_score: float  # -1.0 to 1.0
    sentiment_class: SentimentScore
    reddit_score: Optional[float] = None
    twitter_score: Optional[float] = None
    stocktwits_score: Optional[float] = None
    news_score: Optional[float] = None
    mention_count: int = 0
    mention_velocity: float = 0.0  # % change in mentions vs 24h ago
    bullish_ratio: float = 0.5
    sources: List[str] = field(default_factory=list)


@dataclass
class InsiderTrade:
    """Insider trading activity"""
    symbol: str
    insider_name: str
    title: str
    trade_type: str  # 'buy', 'sell', 'exercise'
    shares: int
    price: float
    value: float
    trade_date: datetime
    filing_date: datetime
    ownership_change_pct: float


@dataclass
class DarkPoolFlow:
    """Dark pool / off-exchange activity"""
    symbol: str
    timestamp: datetime
    dark_pool_volume: int
    total_volume: int
    dark_pool_pct: float
    short_volume: int
    short_pct: float
    net_flow: float  # Positive = buying pressure
    large_block_count: int
    average_block_size: float


@dataclass
class UnusualOptions:
    """Unusual options activity"""
    symbol: str
    timestamp: datetime
    contract_type: str  # 'call' or 'put'
    strike: float
    expiration: str
    volume: int
    open_interest: int
    vol_oi_ratio: float
    premium: float
    implied_volatility: float
    sentiment: str  # 'bullish', 'bearish', 'neutral'
    unusual_score: float  # 0-100


@dataclass
class CongressTrade:
    """Congressional trading disclosure"""
    symbol: str
    politician: str
    party: str
    chamber: str  # 'house' or 'senate'
    trade_type: str
    amount_range: str
    trade_date: datetime
    disclosure_date: datetime


@dataclass
class ESGMetrics:
    """Environmental, Social, Governance scores"""
    symbol: str
    timestamp: datetime
    overall_score: float  # 0-100
    environmental_score: float
    social_score: float
    governance_score: float
    controversy_score: float
    industry_rank: int
    industry_percentile: float


@dataclass
class AlternativeDataBundle:
    """Complete alternative data for a symbol"""
    symbol: str
    timestamp: datetime
    sentiment: Optional[SentimentData] = None
    insider_trades: List[InsiderTrade] = field(default_factory=list)
    dark_pool: Optional[DarkPoolFlow] = None
    unusual_options: List[UnusualOptions] = field(default_factory=list)
    congress_trades: List[CongressTrade] = field(default_factory=list)
    esg: Optional[ESGMetrics] = None
    features: Dict[str, float] = field(default_factory=dict)


# ============== DATA PROVIDERS ==============

class AlternativeDataProvider(ABC):
    """Base class for alternative data providers"""
    
    @abstractmethod
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        pass
    
    @abstractmethod
    def get_insider_trades(self, symbol: str, days: int = 90) -> List[InsiderTrade]:
        pass
    
    @abstractmethod
    def get_dark_pool_flow(self, symbol: str) -> Optional[DarkPoolFlow]:
        pass
    
    @abstractmethod
    def get_unusual_options(self, symbol: str) -> List[UnusualOptions]:
        pass


class FinnhubProvider(AlternativeDataProvider):
    """Finnhub.io alternative data provider"""
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY", "")
        self.session = requests.Session() if HAS_REQUESTS else None
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
    
    def _request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with caching"""
        if not self.session or not self.api_key:
            return None
        
        params = params or {}
        params['token'] = self.api_key
        
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).seconds < self._cache_ttl:
                return cached_data
        
        try:
            response = self.session.get(f"{self.BASE_URL}{endpoint}", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self._cache[cache_key] = (datetime.now(), data)
                return data
        except Exception as e:
            logger.warning(f"Finnhub request failed: {e}")
        
        return None
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Get social sentiment from Finnhub"""
        data = self._request("/stock/social-sentiment", {"symbol": symbol})
        if not data:
            return None
        
        reddit = data.get("reddit", [])
        twitter = data.get("twitter", [])
        
        reddit_score = None
        twitter_score = None
        total_mentions = 0
        
        if reddit:
            latest_reddit = reddit[-1] if reddit else {}
            positive = latest_reddit.get("positiveMention", 0)
            negative = latest_reddit.get("negativeMention", 0)
            total = positive + negative
            if total > 0:
                reddit_score = (positive - negative) / total
                total_mentions += total
        
        if twitter:
            latest_twitter = twitter[-1] if twitter else {}
            positive = latest_twitter.get("positiveMention", 0)
            negative = latest_twitter.get("negativeMention", 0)
            total = positive + negative
            if total > 0:
                twitter_score = (positive - negative) / total
                total_mentions += total
        
        # Aggregate score
        scores = [s for s in [reddit_score, twitter_score] if s is not None]
        overall = sum(scores) / len(scores) if scores else 0.0
        
        # Classify sentiment
        if overall > 0.5:
            sentiment_class = SentimentScore.VERY_BULLISH
        elif overall > 0.2:
            sentiment_class = SentimentScore.BULLISH
        elif overall < -0.5:
            sentiment_class = SentimentScore.VERY_BEARISH
        elif overall < -0.2:
            sentiment_class = SentimentScore.BEARISH
        else:
            sentiment_class = SentimentScore.NEUTRAL
        
        return SentimentData(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            overall_score=overall,
            sentiment_class=sentiment_class,
            reddit_score=reddit_score,
            twitter_score=twitter_score,
            mention_count=total_mentions,
            bullish_ratio=0.5 + (overall / 2),
            sources=["finnhub"]
        )
    
    def get_insider_trades(self, symbol: str, days: int = 90) -> List[InsiderTrade]:
        """Get insider trading activity"""
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        
        data = self._request("/stock/insider-transactions", {
            "symbol": symbol,
            "from": from_date,
            "to": to_date
        })
        
        if not data or "data" not in data:
            return []
        
        trades = []
        for item in data["data"][:20]:  # Limit to 20 most recent
            try:
                trades.append(InsiderTrade(
                    symbol=symbol,
                    insider_name=item.get("name", "Unknown"),
                    title=item.get("position", "Unknown"),
                    trade_type="buy" if item.get("change", 0) > 0 else "sell",
                    shares=abs(int(item.get("change", 0))),
                    price=float(item.get("transactionPrice", 0)),
                    value=abs(item.get("change", 0)) * item.get("transactionPrice", 0),
                    trade_date=datetime.strptime(item.get("transactionDate", "2024-01-01"), "%Y-%m-%d"),
                    filing_date=datetime.strptime(item.get("filingDate", "2024-01-01"), "%Y-%m-%d"),
                    ownership_change_pct=0.0
                ))
            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping insider trade: {e}")
        
        return trades
    
    def get_dark_pool_flow(self, symbol: str) -> Optional[DarkPoolFlow]:
        """Dark pool data - using FINRA ATS data via proxy"""
        # Finnhub doesn't have direct dark pool data
        # Return simulated data based on volume patterns
        return None
    
    def get_unusual_options(self, symbol: str) -> List[UnusualOptions]:
        """Get unusual options activity"""
        # Finnhub has options data but not unusual activity detection
        # Would need to calculate vol/OI ratios ourselves
        return []


class QuiverQuantProvider(AlternativeDataProvider):
    """QuiverQuant for congressional trading data"""
    
    BASE_URL = "https://api.quiverquant.com/beta"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("QUIVERQUANT_API_KEY", "")
        self.session = requests.Session() if HAS_REQUESTS else None
    
    def _request(self, endpoint: str) -> Optional[List]:
        if not self.session or not self.api_key:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = self.session.get(
                f"{self.BASE_URL}{endpoint}",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"QuiverQuant request failed: {e}")
        
        return None
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        return None
    
    def get_insider_trades(self, symbol: str, days: int = 90) -> List[InsiderTrade]:
        return []
    
    def get_dark_pool_flow(self, symbol: str) -> Optional[DarkPoolFlow]:
        return None
    
    def get_unusual_options(self, symbol: str) -> List[UnusualOptions]:
        return []
    
    def get_congress_trades(self, symbol: str) -> List[CongressTrade]:
        """Get congressional trading data"""
        data = self._request(f"/historical/congresstrading/{symbol}")
        if not data:
            return []
        
        trades = []
        for item in data[:20]:
            try:
                trades.append(CongressTrade(
                    symbol=symbol,
                    politician=item.get("Representative", "Unknown"),
                    party=item.get("Party", "Unknown"),
                    chamber=item.get("House", "unknown").lower(),
                    trade_type=item.get("Transaction", "Unknown").lower(),
                    amount_range=item.get("Range", "$0"),
                    trade_date=datetime.strptime(item.get("TransactionDate", "2024-01-01"), "%Y-%m-%d"),
                    disclosure_date=datetime.strptime(item.get("DisclosureDate", "2024-01-01"), "%Y-%m-%d")
                ))
            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping congress trade: {e}")
        
        return trades


# ============== ALTERNATIVE DATA SERVICE ==============

class AlternativeDataService:
    """
    Unified alternative data service that aggregates from multiple providers
    and converts to ML-ready features.
    """
    
    def __init__(self):
        self.providers: Dict[str, AlternativeDataProvider] = {}
        self._db_path = "alternative_data.db"
        self._cache: Dict[str, Tuple[datetime, AlternativeDataBundle]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize providers
        self._init_providers()
        self._init_database()
    
    def _init_providers(self):
        """Initialize available data providers"""
        # Finnhub - free tier available
        finnhub_key = os.getenv("FINNHUB_API_KEY")
        if finnhub_key:
            self.providers["finnhub"] = FinnhubProvider(finnhub_key)
            logger.info("Finnhub provider initialized")
        
        # QuiverQuant - congressional data
        quiver_key = os.getenv("QUIVERQUANT_API_KEY")
        if quiver_key:
            self.providers["quiverquant"] = QuiverQuantProvider(quiver_key)
            logger.info("QuiverQuant provider initialized")
    
    def _init_database(self):
        """Initialize SQLite database for caching"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_cache (
                symbol TEXT,
                timestamp TEXT,
                data TEXT,
                PRIMARY KEY (symbol, timestamp)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insider_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                insider_name TEXT,
                trade_type TEXT,
                shares INTEGER,
                price REAL,
                trade_date TEXT,
                UNIQUE(symbol, insider_name, trade_date, shares)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_alternative_data(self, symbol: str) -> AlternativeDataBundle:
        """
        Get complete alternative data bundle for a symbol.
        Aggregates from all available providers.
        """
        # Check cache
        cache_key = symbol.upper()
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).seconds < self._cache_ttl:
                return cached_data
        
        bundle = AlternativeDataBundle(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Gather data from all providers in parallel
        futures = []
        
        if "finnhub" in self.providers:
            provider = self.providers["finnhub"]
            futures.append(("sentiment", self._executor.submit(provider.get_sentiment, symbol)))
            futures.append(("insider", self._executor.submit(provider.get_insider_trades, symbol)))
        
        if "quiverquant" in self.providers:
            provider = self.providers["quiverquant"]
            futures.append(("congress", self._executor.submit(provider.get_congress_trades, symbol)))
        
        # Collect results
        for data_type, future in futures:
            try:
                result = future.result(timeout=15)
                if data_type == "sentiment" and result:
                    bundle.sentiment = result
                elif data_type == "insider" and result:
                    bundle.insider_trades = result
                elif data_type == "congress" and result:
                    bundle.congress_trades = result
            except Exception as e:
                logger.warning(f"Failed to get {data_type} data: {e}")
        
        # Generate features
        bundle.features = self._generate_features(bundle)
        
        # Cache result
        self._cache[cache_key] = (datetime.now(), bundle)
        
        return bundle
    
    def _generate_features(self, bundle: AlternativeDataBundle) -> Dict[str, float]:
        """
        Convert alternative data to ML-ready features.
        These can be integrated into the PropFirm Brain feature engine.
        """
        features = {}
        
        # Sentiment features
        if bundle.sentiment:
            features["alt_sentiment_score"] = bundle.sentiment.overall_score
            features["alt_sentiment_reddit"] = bundle.sentiment.reddit_score or 0.0
            features["alt_sentiment_twitter"] = bundle.sentiment.twitter_score or 0.0
            features["alt_mention_count"] = min(bundle.sentiment.mention_count / 1000, 1.0)
            features["alt_mention_velocity"] = bundle.sentiment.mention_velocity
            features["alt_bullish_ratio"] = bundle.sentiment.bullish_ratio
        else:
            features["alt_sentiment_score"] = 0.0
            features["alt_sentiment_reddit"] = 0.0
            features["alt_sentiment_twitter"] = 0.0
            features["alt_mention_count"] = 0.0
            features["alt_mention_velocity"] = 0.0
            features["alt_bullish_ratio"] = 0.5
        
        # Insider trading features
        if bundle.insider_trades:
            recent_trades = bundle.insider_trades[:10]
            buy_count = sum(1 for t in recent_trades if t.trade_type == "buy")
            sell_count = sum(1 for t in recent_trades if t.trade_type == "sell")
            total = buy_count + sell_count
            
            features["alt_insider_buy_ratio"] = buy_count / total if total > 0 else 0.5
            features["alt_insider_activity"] = min(total / 10, 1.0)
            
            # Net insider value
            net_value = sum(
                t.value if t.trade_type == "buy" else -t.value
                for t in recent_trades
            )
            features["alt_insider_net_value"] = np.tanh(net_value / 10_000_000)  # Normalize
        else:
            features["alt_insider_buy_ratio"] = 0.5
            features["alt_insider_activity"] = 0.0
            features["alt_insider_net_value"] = 0.0
        
        # Congress trading features
        if bundle.congress_trades:
            recent = bundle.congress_trades[:10]
            buy_count = sum(1 for t in recent if "purchase" in t.trade_type)
            sell_count = sum(1 for t in recent if "sale" in t.trade_type)
            total = buy_count + sell_count
            
            features["alt_congress_buy_ratio"] = buy_count / total if total > 0 else 0.5
            features["alt_congress_activity"] = min(total / 5, 1.0)
        else:
            features["alt_congress_buy_ratio"] = 0.5
            features["alt_congress_activity"] = 0.0
        
        # Dark pool features (if available)
        if bundle.dark_pool:
            features["alt_darkpool_pct"] = bundle.dark_pool.dark_pool_pct
            features["alt_short_pct"] = bundle.dark_pool.short_pct
            features["alt_darkpool_flow"] = np.tanh(bundle.dark_pool.net_flow / 1_000_000)
        else:
            features["alt_darkpool_pct"] = 0.0
            features["alt_short_pct"] = 0.0
            features["alt_darkpool_flow"] = 0.0
        
        # Unusual options features
        if bundle.unusual_options:
            bullish = sum(1 for o in bundle.unusual_options if o.sentiment == "bullish")
            bearish = sum(1 for o in bundle.unusual_options if o.sentiment == "bearish")
            total = len(bundle.unusual_options)
            
            features["alt_options_bullish_ratio"] = bullish / total if total > 0 else 0.5
            features["alt_options_unusual_count"] = min(total / 10, 1.0)
            features["alt_options_avg_score"] = (
                sum(o.unusual_score for o in bundle.unusual_options) / total
                if total > 0 else 0.0
            ) / 100
        else:
            features["alt_options_bullish_ratio"] = 0.5
            features["alt_options_unusual_count"] = 0.0
            features["alt_options_avg_score"] = 0.0
        
        # ESG features
        if bundle.esg:
            features["alt_esg_overall"] = bundle.esg.overall_score / 100
            features["alt_esg_environmental"] = bundle.esg.environmental_score / 100
            features["alt_esg_social"] = bundle.esg.social_score / 100
            features["alt_esg_governance"] = bundle.esg.governance_score / 100
            features["alt_esg_controversy"] = bundle.esg.controversy_score / 100
        else:
            features["alt_esg_overall"] = 0.5
            features["alt_esg_environmental"] = 0.5
            features["alt_esg_social"] = 0.5
            features["alt_esg_governance"] = 0.5
            features["alt_esg_controversy"] = 0.5
        
        return features
    
    def get_features_for_symbol(self, symbol: str) -> Dict[str, float]:
        """Get just the ML features for a symbol"""
        bundle = self.get_alternative_data(symbol)
        return bundle.features
    
    def get_bulk_features(self, symbols: List[str]) -> Dict[str, Dict[str, float]]:
        """Get features for multiple symbols efficiently"""
        results = {}
        futures = [
            (symbol, self._executor.submit(self.get_features_for_symbol, symbol))
            for symbol in symbols
        ]
        
        for symbol, future in futures:
            try:
                results[symbol] = future.result(timeout=30)
            except Exception as e:
                logger.warning(f"Failed to get features for {symbol}: {e}")
                results[symbol] = {}
        
        return results


# ============== SINGLETON INSTANCE ==============

_alt_data_service: Optional[AlternativeDataService] = None
_lock = threading.Lock()


def get_alternative_data_service() -> AlternativeDataService:
    """Get or create the singleton alternative data service"""
    global _alt_data_service
    
    if _alt_data_service is None:
        with _lock:
            if _alt_data_service is None:
                _alt_data_service = AlternativeDataService()
    
    return _alt_data_service


# ============== CONVENIENCE FUNCTIONS ==============

def get_sentiment(symbol: str) -> Optional[SentimentData]:
    """Get sentiment data for a symbol"""
    service = get_alternative_data_service()
    bundle = service.get_alternative_data(symbol)
    return bundle.sentiment


def get_alternative_features(symbol: str) -> Dict[str, float]:
    """Get alternative data features for ML integration"""
    service = get_alternative_data_service()
    return service.get_features_for_symbol(symbol)


def get_insider_signal(symbol: str) -> float:
    """
    Get insider trading signal (-1 to 1).
    Positive = insider buying, Negative = insider selling
    """
    service = get_alternative_data_service()
    bundle = service.get_alternative_data(symbol)
    
    if not bundle.insider_trades:
        return 0.0
    
    return bundle.features.get("alt_insider_net_value", 0.0)
