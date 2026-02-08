"""
Market Data Service
===================
Unified service for fetching market data from configured providers.
Handles caching, fallback, and database persistence.

This is the SINGLE source of truth for market data in the application.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from zoneinfo import ZoneInfo

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

# yfinance availability check
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


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
    
    # In-memory cache for yfinance data: {cache_key: (timestamp, data)}
    _yf_cache: Dict[str, Tuple[float, Any]] = {}
    _YF_CACHE_TTL = 30  # seconds before cached yfinance data expires
    _YF_TIMEOUT = 10.0  # seconds before a yfinance request times out

    def __init__(self):
        self._alpaca = None
        self._use_yfinance = False
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 5  # seconds for quote cache

    @classmethod
    async def create(cls) -> "MarketDataService":
        """Factory method to create and initialize the service."""
        service = cls()
        await service._initialize()
        return service

    async def _initialize(self):
        """Initialize data providers.

        Priority:
        1. Alpaca (if API keys configured)
        2. yfinance (free, no API key required - default)
        3. Mock data (last resort if yfinance not installed)
        """
        data_mode = config.get_data_mode()

        if data_mode == "alpaca" and config.alpaca_configured:
            try:
                from data.providers.alpaca import AlpacaProvider, AlpacaConfig

                alpaca_config = AlpacaConfig(
                    api_key=config.ALPACA_API_KEY,
                    api_secret=config.ALPACA_API_SECRET
                )
                self._alpaca = AlpacaProvider(alpaca_config)
                await self._alpaca.connect()
                logger.info("[OK] Alpaca provider connected")
                return
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca: {e}")
                self._alpaca = None

        # Fall back to yfinance (free, no API key needed)
        if HAS_YFINANCE:
            self._use_yfinance = True
            logger.info("[OK] Using yfinance for market data (free, no API key required)")
        else:
            logger.warning(
                "[WARN] No API keys configured and yfinance not installed. "
                "Using mock data. Install yfinance with: pip install yfinance"
            )
    
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
        if self._use_yfinance:
            return "yfinance"
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

        # Try yfinance (free, no API key)
        if self._use_yfinance:
            try:
                quote = await self._yfinance_quote(symbol)
                if quote:
                    return quote
            except Exception as e:
                logger.warning(f"yfinance quote failed for {symbol}: {e}")

        # Last resort: mock data
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

        # Try yfinance for each symbol
        if self._use_yfinance:
            result = {}
            for symbol in symbols:
                try:
                    quote = await self._yfinance_quote(symbol)
                    result[symbol] = quote if quote else self._mock_quote(symbol)
                except Exception:
                    result[symbol] = self._mock_quote(symbol)
            return result

        return {s: self._mock_quote(s) for s in symbols}
    
    def _yf_cache_get(self, key: str) -> Optional[Any]:
        """Return cached yfinance data if still fresh, else None."""
        entry = self._yf_cache.get(key)
        if entry is None:
            return None
        cached_time, data = entry
        if time.monotonic() - cached_time > self._YF_CACHE_TTL:
            del self._yf_cache[key]
            return None
        return data

    def _yf_cache_set(self, key: str, data: Any) -> None:
        """Store data in the yfinance cache."""
        self._yf_cache[key] = (time.monotonic(), data)

    async def _yfinance_quote(self, symbol: str) -> Optional[Quote]:
        """Get quote from yfinance with timeout and caching."""
        if not HAS_YFINANCE:
            return None

        # Check cache first
        cache_key = f"quote:{symbol}"
        cached = self._yf_cache_get(cache_key)
        if cached is not None:
            logger.debug(f"yfinance cache hit for {symbol} quote")
            return cached

        # Normalize symbols for yfinance (VIX -> ^VIX, etc.)
        yf_symbol = symbol
        if symbol == "VIX":
            yf_symbol = "^VIX"

        try:
            loop = asyncio.get_event_loop()
            # Run yfinance in a thread with a timeout to prevent hangs
            info = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: yf.Ticker(yf_symbol).info),
                timeout=self._YF_TIMEOUT,
            )

            price = info.get('regularMarketPrice') or info.get('currentPrice', 0)
            if not price or price <= 0:
                return None

            bid = info.get('bid', price)
            ask = info.get('ask', price)
            volume = info.get('regularMarketVolume', 0)

            quote = Quote(
                symbol=symbol,
                bid=bid or price,
                ask=ask or price,
                last=price,
                volume=volume or 0,
                timestamp=datetime.now(),
                source="yfinance"
            )
            self._yf_cache_set(cache_key, quote)
            return quote
        except asyncio.TimeoutError:
            logger.warning(f"yfinance quote timed out for {symbol} after {self._YF_TIMEOUT}s")
            return None
        except Exception as e:
            logger.warning(f"yfinance quote failed for {symbol}: {e}")
            return None

    async def _yfinance_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1d"
    ) -> List['Bar']:
        """Get historical bars from yfinance with timeout and caching."""
        if not HAS_YFINANCE:
            return []

        # Check cache first
        cache_key = f"bars:{symbol}:{start.date()}:{end.date()}:{interval}"
        cached = self._yf_cache_get(cache_key)
        if cached is not None:
            logger.debug(f"yfinance cache hit for {symbol} bars")
            return cached

        # Normalize symbols for yfinance (VIX -> ^VIX, etc.)
        yf_symbol = symbol
        if symbol == "VIX":
            yf_symbol = "^VIX"

        try:
            loop = asyncio.get_event_loop()

            def _fetch():
                ticker = yf.Ticker(yf_symbol)
                df = ticker.history(
                    start=start.strftime('%Y-%m-%d'),
                    end=end.strftime('%Y-%m-%d'),
                    interval=interval,
                )
                return df

            # Run in executor with timeout to prevent hangs
            df = await asyncio.wait_for(
                loop.run_in_executor(None, _fetch),
                timeout=self._YF_TIMEOUT,
            )

            if df is None or df.empty:
                return []

            bars = []
            for idx, row in df.iterrows():
                bars.append(Bar(
                    timestamp=idx.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=float(row['Volume']),
                    source="yfinance"
                ))

            self._yf_cache_set(cache_key, bars)
            return bars
        except asyncio.TimeoutError:
            logger.warning(f"yfinance bars timed out for {symbol} after {self._YF_TIMEOUT}s")
            return []
        except Exception as e:
            logger.warning(f"yfinance bars failed for {symbol}: {e}")
            return []

    def _mock_quote(self, symbol: str) -> Quote:
        """Generate mock quote for testing."""
        import random
        
        base_prices = {
            "SPY": 585.42, "QQQ": 512.88, "DIA": 428.15, "IWM": 225.33,
            "AAPL": 242.50, "MSFT": 445.80, "NVDA": 142.30, "TSLA": 425.60,
            "GOOGL": 175.20, "AMZN": 225.40, "META": 620.30, "AMD": 125.40,
            "VIX": 18.50, "^VIX": 18.50,
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

        # Try yfinance before mock
        if self._use_yfinance:
            try:
                # Map timeframe to yfinance interval
                tf_map = {
                    "1Min": "1m", "5Min": "5m", "15Min": "15m",
                    "30Min": "30m", "1Hour": "1h", "1Day": "1d",
                    "1Week": "1wk", "1Month": "1mo",
                }
                yf_interval = tf_map.get(timeframe, "1d")
                bars = await self._yfinance_bars(symbol, start, end, interval=yf_interval)
                if bars:
                    return bars
            except Exception as e:
                logger.warning(f"yfinance bars failed for {symbol}: {e}")

        # Last resort: mock
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

        # Try yfinance for each symbol
        if self._use_yfinance:
            result = {}
            for symbol in symbols:
                try:
                    bars = await self._yfinance_bars(symbol, start, end)
                    result[symbol] = bars if bars else self._mock_bars(symbol, start, end)
                except Exception:
                    result[symbol] = self._mock_bars(symbol, start, end)
            return result

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
        
        # Try yfinance snapshot
        if self._use_yfinance:
            try:
                quote = await self._yfinance_quote(symbol)
                if quote:
                    return {
                        "symbol": symbol,
                        "latest_trade": {"price": quote.last, "size": 100},
                        "latest_quote": quote.to_dict(),
                        "daily_bar": {},
                        "source": "yfinance"
                    }
            except Exception as e:
                logger.warning(f"yfinance snapshot failed for {symbol}: {e}")

        # Last resort: mock snapshot
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
        """Get market open/close status using US/Eastern timezone."""
        eastern = ZoneInfo("America/New_York")
        now = datetime.now(eastern)
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()

        if weekday >= 5:  # Weekend
            return {
                "session": "closed",
                "is_open": False,
                "is_pre_market": False,
                "is_after_hours": False,
                "source": self.data_mode
            }

        # US market hours in Eastern time:
        # Pre-market:    04:00 - 09:30 ET
        # Regular:       09:30 - 16:00 ET
        # After-hours:   16:00 - 20:00 ET
        current_minutes = hour * 60 + minute

        if 570 <= current_minutes < 960:  # 09:30 - 16:00
            session, is_open = "regular", True
        elif 240 <= current_minutes < 570:  # 04:00 - 09:30
            session, is_open = "pre_market", True
        elif 960 <= current_minutes < 1200:  # 16:00 - 20:00
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
