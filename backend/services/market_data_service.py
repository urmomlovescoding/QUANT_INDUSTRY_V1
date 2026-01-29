"""
Market Data Service
===================
Unified service for fetching market data from configured providers.
Handles caching, fallback, and database persistence.

This is the SINGLE source of truth for market data in the application.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Import config - uses relative import for flexibility
try:
    from backend.config.env import config
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from backend.config.env import config

# Provider imports
_alpaca_provider = None
_initialized = False


@dataclass
class Quote:
    """Standardized quote format."""
    symbol: str
    bid: float
    ask: float
    last: float
    bid_size: int = 0
    ask_size: int = 0
    volume: int = 0
    timestamp: Optional[datetime] = None
    source: str = "unknown"
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2 if self.bid and self.ask else self.last
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid if self.bid and self.ask else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.last or self.mid,
            "bid": self.bid,
            "ask": self.ask,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source": self.source,
        }


@dataclass
class Bar:
    """Standardized OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None
    trade_count: Optional[int] = None
    source: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": self.vwap,
            "trade_count": self.trade_count,
            "source": self.source,
        }


class MarketDataService:
    """
    Unified market data service.
    
    Usage:
        service = await MarketDataService.create()
        quote = await service.get_quote("AAPL")
        bars = await service.get_bars("AAPL", timeframe="1Day", days=30)
    """
    
    def __init__(self):
        self._alpaca = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 5  # seconds for quote cache
    
    @classmethod
    async def create(cls) -> "MarketDataService":
        """Factory method to create and initialize the service."""
        service = cls()
        await service._initialize()
        return service
    
    async def _initialize(self):
        """Initialize data providers."""
        if config.alpaca_configured:
            try:
                from data.providers.alpaca import AlpacaProvider, AlpacaConfig
                
                alpaca_config = AlpacaConfig(
                    api_key=config.ALPACA_API_KEY,
                    api_secret=config.ALPACA_API_SECRET
                )
                self._alpaca = AlpacaProvider(alpaca_config)
                await self._alpaca.connect()
                logger.info("[OK] Alpaca provider connected")
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca: {e}")
                self._alpaca = None
        else:
            logger.warning("[WARN] Alpaca not configured - using mock data")
    
    async def close(self):
        """Clean up resources."""
        if self._alpaca:
            try:
                await self._alpaca.disconnect()
            except Exception:
                pass
            self._alpaca = None
    
    @property
    def data_mode(self) -> str:
        """Get current data mode."""
        if self._alpaca:
            return "alpaca"
        return "mock"
    
    # =========================================================================
    # QUOTES
    # =========================================================================
    
    async def get_quote(self, symbol: str) -> Quote:
        """Get real-time quote for a symbol."""
        symbol = symbol.upper()
        
        # Try Alpaca first
        if self._alpaca:
            try:
                data = await self._alpaca.get_quote(symbol)
                return Quote(
                    symbol=symbol,
                    bid=data.get('bid', 0),
                    ask=data.get('ask', 0),
                    last=data.get('ask', 0),  # Use ask as last if no trade
                    bid_size=data.get('bid_size', 0),
                    ask_size=data.get('ask_size', 0),
                    timestamp=datetime.now(),
                    source="alpaca"
                )
            except Exception as e:
                logger.warning(f"Alpaca quote failed for {symbol}: {e}")
        
        # Fallback to mock
        return self._mock_quote(symbol)
    
    async def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get quotes for multiple symbols."""
        symbols = [s.upper() for s in symbols]
        
        if self._alpaca:
            try:
                data = await self._alpaca.get_quotes(symbols)
                result = {}
                for symbol in symbols:
                    q = data.get(symbol, {})
                    if q:
                        result[symbol] = Quote(
                            symbol=symbol,
                            bid=q.get('bid', 0),
                            ask=q.get('ask', 0),
                            last=q.get('ask', 0),
                            bid_size=q.get('bid_size', 0),
                            ask_size=q.get('ask_size', 0),
                            timestamp=datetime.now(),
                            source="alpaca"
                        )
                    else:
                        result[symbol] = self._mock_quote(symbol)
                return result
            except Exception as e:
                logger.warning(f"Alpaca quotes failed: {e}")
        
        return {s: self._mock_quote(s) for s in symbols}
    
    def _mock_quote(self, symbol: str) -> Quote:
        """Generate mock quote for testing."""
        import random
        
        base_prices = {
            "SPY": 585.42, "QQQ": 512.88, "DIA": 428.15, "IWM": 225.33,
            "AAPL": 242.50, "MSFT": 445.80, "NVDA": 142.30, "TSLA": 425.60,
            "GOOGL": 175.20, "AMZN": 225.40, "META": 620.30, "AMD": 125.40,
        }
        
        base = base_prices.get(symbol, 100 + hash(symbol) % 400)
        price = base * (1 + random.uniform(-0.001, 0.001))
        spread = price * 0.0005
        
        return Quote(
            symbol=symbol,
            bid=price - spread/2,
            ask=price + spread/2,
            last=price,
            volume=random.randint(1000000, 50000000),
            timestamp=datetime.now(),
            source="mock"
        )
    
    # =========================================================================
    # BARS / HISTORICAL DATA
    # =========================================================================
    
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        days: int = 365,
        limit: int = 10000
    ) -> List[Bar]:
        """Get historical OHLCV bars."""
        symbol = symbol.upper()
        
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=days)
        
        if self._alpaca:
            try:
                data = await self._alpaca.get_bars(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=start,
                    end=end,
                    limit=limit
                )
                
                return [
                    Bar(
                        timestamp=datetime.fromisoformat(b['timestamp'].replace('Z', '+00:00')) 
                            if isinstance(b['timestamp'], str) else b['timestamp'],
                        open=b['open'],
                        high=b['high'],
                        low=b['low'],
                        close=b['close'],
                        volume=b['volume'],
                        vwap=b.get('vwap'),
                        trade_count=b.get('trade_count'),
                        source="alpaca"
                    )
                    for b in data
                ]
            except Exception as e:
                logger.warning(f"Alpaca bars failed for {symbol}: {e}")
        
        # Fallback to mock
        return self._mock_bars(symbol, start, end)
    
    async def get_multi_bars(
        self,
        symbols: List[str],
        timeframe: str = "1Day",
        days: int = 365
    ) -> Dict[str, List[Bar]]:
        """Get bars for multiple symbols."""
        symbols = [s.upper() for s in symbols]
        end = datetime.now()
        start = end - timedelta(days=days)
        
        if self._alpaca:
            try:
                data = await self._alpaca.get_multi_bars(
                    symbols=symbols,
                    timeframe=timeframe,
                    start=start,
                    end=end
                )
                
                result = {}
                for symbol, bars in data.items():
                    result[symbol] = [
                        Bar(
                            timestamp=datetime.fromisoformat(b['timestamp'].replace('Z', '+00:00'))
                                if isinstance(b['timestamp'], str) else b['timestamp'],
                            open=b['open'],
                            high=b['high'],
                            low=b['low'],
                            close=b['close'],
                            volume=b['volume'],
                            vwap=b.get('vwap'),
                            source="alpaca"
                        )
                        for b in bars
                    ]
                return result
            except Exception as e:
                logger.warning(f"Alpaca multi-bars failed: {e}")
        
        return {s: self._mock_bars(s, start, end) for s in symbols}
    
    def _mock_bars(self, symbol: str, start: datetime, end: datetime) -> List[Bar]:
        """Generate mock bars for testing."""
        import random
        
        base_prices = {
            "SPY": 500, "QQQ": 450, "AAPL": 200, "MSFT": 400, 
            "NVDA": 120, "TSLA": 350, "GOOGL": 150, "AMZN": 180
        }
        
        price = base_prices.get(symbol, 100 + hash(symbol) % 300)
        bars = []
        
        current = start
        while current <= end:
            if current.weekday() < 5:  # Skip weekends
                change = random.uniform(-0.025, 0.03)
                open_price = price
                close_price = price * (1 + change)
                high = max(open_price, close_price) * (1 + random.uniform(0, 0.01))
                low = min(open_price, close_price) * (1 - random.uniform(0, 0.01))
                
                bars.append(Bar(
                    timestamp=current,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close_price,
                    volume=random.randint(10000000, 100000000),
                    source="mock"
                ))
                
                price = close_price
            
            current += timedelta(days=1)
        
        return bars
    
    # =========================================================================
    # SNAPSHOTS
    # =========================================================================
    
    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get complete snapshot for a symbol."""
        symbol = symbol.upper()
        
        if self._alpaca:
            try:
                data = await self._alpaca.get_snapshot(symbol)
                return {
                    "symbol": symbol,
                    "latest_trade": data.get('latest_trade', {}),
                    "latest_quote": data.get('latest_quote', {}),
                    "minute_bar": data.get('minute_bar', {}),
                    "daily_bar": data.get('daily_bar', {}),
                    "prev_daily_bar": data.get('prev_daily_bar', {}),
                    "source": "alpaca"
                }
            except Exception as e:
                logger.warning(f"Alpaca snapshot failed for {symbol}: {e}")
        
        # Mock snapshot
        quote = self._mock_quote(symbol)
        return {
            "symbol": symbol,
            "latest_trade": {"price": quote.last, "size": 100},
            "latest_quote": quote.to_dict(),
            "daily_bar": {},
            "source": "mock"
        }
    
    # =========================================================================
    # NEWS
    # =========================================================================
    
    async def get_news(
        self,
        symbols: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get news articles."""
        if self._alpaca:
            try:
                data = await self._alpaca.get_news(symbols=symbols, limit=limit)
                return data
            except Exception as e:
                logger.warning(f"Alpaca news failed: {e}")
        
        # Mock news
        return self._mock_news(symbols)
    
    def _mock_news(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Generate mock news."""
        news_items = [
            {"title": "Fed Signals Rate Cuts Ahead", "source": "Bloomberg", "sentiment": "positive"},
            {"title": "Tech Earnings Beat Expectations", "source": "Reuters", "sentiment": "positive"},
            {"title": "Oil Prices Surge on Supply Concerns", "source": "CNBC", "sentiment": "neutral"},
            {"title": "AI Stocks Rally on Strong Demand", "source": "WSJ", "sentiment": "positive"},
        ]
        
        return [
            {
                "id": f"news-{i}",
                "headline": item["title"],
                "summary": f"Breaking: {item['title']}. Market analysts weigh in...",
                "source": item["source"],
                "url": f"https://example.com/news/{i}",
                "symbols": symbols or ["SPY", "QQQ"],
                "sentiment": item["sentiment"],
                "created_at": (datetime.now() - timedelta(hours=i)).isoformat()
            }
            for i, item in enumerate(news_items)
        ]
    
    # =========================================================================
    # MARKET STATUS
    # =========================================================================
    
    async def get_market_status(self) -> Dict[str, Any]:
        """Get market open/close status."""
        # For now, simple time-based check
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()
        
        if weekday >= 5:  # Weekend
            return {
                "session": "closed",
                "is_open": False,
                "is_pre_market": False,
                "is_after_hours": False,
                "source": self.data_mode
            }
        
        if 9 <= hour < 16:
            session, is_open = "regular", True
        elif 4 <= hour < 9:
            session, is_open = "pre_market", True
        elif 16 <= hour < 20:
            session, is_open = "after_hours", True
        else:
            session, is_open = "closed", False
        
        return {
            "session": session,
            "is_open": is_open,
            "is_pre_market": session == "pre_market",
            "is_after_hours": session == "after_hours",
            "source": self.data_mode
        }


# ============== SINGLETON ==============

_service_instance: Optional[MarketDataService] = None


async def get_market_data_service() -> MarketDataService:
    """Get or create the market data service singleton."""
    global _service_instance
    
    if _service_instance is None:
        _service_instance = await MarketDataService.create()
    
    return _service_instance
