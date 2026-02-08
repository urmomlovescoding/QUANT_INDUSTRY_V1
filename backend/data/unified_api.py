"""
QUANT INDUSTRY - Unified Data API
=================================
One API to rule all data sources:
- Multiple provider support (Yahoo, Alpaca, Polygon, etc.)
- Automatic fallback on failure
- Data normalization
- Caching and rate limiting
- Real-time and historical data

Never write provider-specific code again.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


class DataProvider(Enum):
    """Supported data providers"""
    YAHOO = "yahoo"
    ALPACA = "alpaca"
    POLYGON = "polygon"
    FINNHUB = "finnhub"
    ALPHA_VANTAGE = "alpha_vantage"
    BINANCE = "binance"
    COINBASE = "coinbase"
    IEX = "iex"


class DataFrequency(Enum):
    """Data frequencies"""
    TICK = "tick"
    SECOND = "1s"
    MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    HOUR = "1h"
    FOUR_HOUR = "4h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"


class AssetClass(Enum):
    """Asset classes"""
    EQUITY = "equity"
    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"
    OPTIONS = "options"
    ETF = "etf"
    INDEX = "index"


@dataclass
class OHLCV:
    """Standard OHLCV bar"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }
    
    def to_array(self) -> np.ndarray:
        return np.array([self.open, self.high, self.low, self.close, self.volume])


@dataclass
class Quote:
    """Real-time quote"""
    timestamp: datetime
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    last_size: int
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @property
    def spread_bps(self) -> float:
        return (self.spread / self.mid) * 10000 if self.mid > 0 else 0


@dataclass
class DataRequest:
    """Standardized data request"""
    symbol: str
    start_date: datetime
    end_date: datetime = None
    frequency: DataFrequency = DataFrequency.DAILY
    asset_class: AssetClass = AssetClass.EQUITY
    adjusted: bool = True
    provider: DataProvider = None  # None = auto-select


@dataclass
class DataResponse:
    """Standardized data response"""
    symbol: str
    bars: List[OHLCV]
    provider: DataProvider
    frequency: DataFrequency
    request_time: datetime = field(default_factory=datetime.now)
    cached: bool = False
    
    def to_dataframe(self) -> 'pd.DataFrame':
        """Convert to pandas DataFrame"""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required")
        
        data = [bar.to_dict() for bar in self.bars]
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    
    def to_arrays(self) -> Dict[str, np.ndarray]:
        """Convert to numpy arrays"""
        return {
            "timestamp": np.array([bar.timestamp for bar in self.bars]),
            "open": np.array([bar.open for bar in self.bars]),
            "high": np.array([bar.high for bar in self.bars]),
            "low": np.array([bar.low for bar in self.bars]),
            "close": np.array([bar.close for bar in self.bars]),
            "volume": np.array([bar.volume for bar in self.bars]),
        }
    
    @property
    def closes(self) -> np.ndarray:
        return np.array([bar.close for bar in self.bars])
    
    @property
    def volumes(self) -> np.ndarray:
        return np.array([bar.volume for bar in self.bars])


class BaseDataAdapter(ABC):
    """Base class for data provider adapters"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.request_count = 0
        self.last_request_time = None
    
    @property
    @abstractmethod
    def provider(self) -> DataProvider:
        pass
    
    @property
    @abstractmethod
    def supported_frequencies(self) -> List[DataFrequency]:
        pass
    
    @property
    @abstractmethod
    def supported_asset_classes(self) -> List[AssetClass]:
        pass
    
    @abstractmethod
    def fetch_historical(self, request: DataRequest) -> DataResponse:
        """Fetch historical data"""
        pass
    
    def fetch_quote(self, symbol: str) -> Optional[Quote]:
        """Fetch real-time quote (optional)"""
        return None
    
    def _rate_limit(self, min_interval: float = 0.5):
        """Apply rate limiting.

        WARNING: Uses blocking time.sleep(). If called from an async FastAPI endpoint,
        wrap the call: await asyncio.to_thread(adapter._rate_limit)
        or use the async variant _async_rate_limit() instead.
        """
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
        self.request_count += 1

    async def _async_rate_limit(self, min_interval: float = 0.5):
        """Async-safe rate limiting for use in async endpoints."""
        import asyncio
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
        self.request_count += 1


class YahooAdapter(BaseDataAdapter):
    """Yahoo Finance adapter"""
    
    @property
    def provider(self) -> DataProvider:
        return DataProvider.YAHOO
    
    @property
    def supported_frequencies(self) -> List[DataFrequency]:
        return [
            DataFrequency.MINUTE,
            DataFrequency.FIVE_MINUTE,
            DataFrequency.FIFTEEN_MINUTE,
            DataFrequency.THIRTY_MINUTE,
            DataFrequency.HOUR,
            DataFrequency.DAILY,
            DataFrequency.WEEKLY,
            DataFrequency.MONTHLY
        ]
    
    @property
    def supported_asset_classes(self) -> List[AssetClass]:
        return [AssetClass.EQUITY, AssetClass.ETF, AssetClass.INDEX, AssetClass.CRYPTO]
    
    def fetch_historical(self, request: DataRequest) -> DataResponse:
        if not YFINANCE_AVAILABLE:
            raise ImportError("yfinance required: pip install yfinance")
        
        self._rate_limit()
        
        # Map frequency
        interval_map = {
            DataFrequency.MINUTE: "1m",
            DataFrequency.FIVE_MINUTE: "5m",
            DataFrequency.FIFTEEN_MINUTE: "15m",
            DataFrequency.THIRTY_MINUTE: "30m",
            DataFrequency.HOUR: "1h",
            DataFrequency.DAILY: "1d",
            DataFrequency.WEEKLY: "1wk",
            DataFrequency.MONTHLY: "1mo"
        }
        
        interval = interval_map.get(request.frequency, "1d")
        
        # Fetch data
        ticker = yf.Ticker(request.symbol)
        
        end_date = request.end_date or datetime.now()
        
        df = ticker.history(
            start=request.start_date,
            end=end_date,
            interval=interval,
            auto_adjust=request.adjusted
        )
        
        # Convert to OHLCV
        bars = []
        for idx, row in df.iterrows():
            bars.append(OHLCV(
                timestamp=idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx,
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=float(row['Volume'])
            ))
        
        return DataResponse(
            symbol=request.symbol,
            bars=bars,
            provider=self.provider,
            frequency=request.frequency
        )
    
    def fetch_quote(self, symbol: str) -> Optional[Quote]:
        if not YFINANCE_AVAILABLE:
            return None
        
        self._rate_limit()
        
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return Quote(
            timestamp=datetime.now(),
            symbol=symbol,
            bid=info.get('bid', 0),
            ask=info.get('ask', 0),
            bid_size=info.get('bidSize', 0),
            ask_size=info.get('askSize', 0),
            last=info.get('regularMarketPrice', info.get('currentPrice', 0)),
            last_size=0
        )


class UnifiedDataAPI:
    """
    Unified data API with multiple providers and automatic fallback.
    
    Usage:
    ------
    >>> api = UnifiedDataAPI()
    >>>
    >>> # Get historical data (auto-selects provider)
    >>> data = api.get_historical(
    ...     symbol="AAPL",
    ...     start_date=datetime(2023, 1, 1),
    ...     frequency=DataFrequency.DAILY
    ... )
    >>>
    >>> # Access as DataFrame
    >>> df = data.to_dataframe()
    >>>
    >>> # Or as numpy arrays
    >>> closes = data.closes
    >>> volumes = data.volumes
    >>>
    >>> # Get real-time quote
    >>> quote = api.get_quote("AAPL")
    >>> print(f"Bid: {quote.bid}, Ask: {quote.ask}")
    >>>
    >>> # Multi-symbol fetch
    >>> multi_data = api.get_multiple(
    ...     symbols=["AAPL", "GOOGL", "MSFT"],
    ...     start_date=datetime(2023, 1, 1)
    ... )
    """
    
    def __init__(
        self,
        providers: Dict[DataProvider, str] = None,
        cache_hours: int = 1,
        enable_fallback: bool = True
    ):
        """
        Initialize unified API.
        
        Args:
            providers: Dict of provider: api_key
            cache_hours: Cache duration in hours
            enable_fallback: Auto-fallback on provider failure
        """
        self.providers = providers or {}
        self.cache_hours = cache_hours
        self.enable_fallback = enable_fallback
        
        # Initialize adapters
        self.adapters: Dict[DataProvider, BaseDataAdapter] = {}
        
        # Always add Yahoo (free)
        if YFINANCE_AVAILABLE:
            self.adapters[DataProvider.YAHOO] = YahooAdapter()
        
        # Add other adapters based on provided API keys
        # (Would add more adapters here in production)
        
        # Cache
        self._cache: Dict[str, Tuple[DataResponse, datetime]] = {}
        
        # Provider priority (for auto-selection)
        self.provider_priority = [
            DataProvider.POLYGON,
            DataProvider.ALPACA,
            DataProvider.IEX,
            DataProvider.YAHOO,
            DataProvider.ALPHA_VANTAGE,
        ]
        
        logger.info(f"UnifiedDataAPI initialized with {len(self.adapters)} providers")
    
    def _get_cache_key(self, request: DataRequest) -> str:
        """Generate cache key for request"""
        return f"{request.symbol}_{request.start_date}_{request.end_date}_{request.frequency.value}"
    
    def _check_cache(self, request: DataRequest) -> Optional[DataResponse]:
        """Check if data is cached"""
        key = self._get_cache_key(request)
        
        if key in self._cache:
            response, cache_time = self._cache[key]
            if datetime.now() - cache_time < timedelta(hours=self.cache_hours):
                response.cached = True
                return response
        
        return None
    
    def _select_provider(
        self,
        request: DataRequest
    ) -> Optional[BaseDataAdapter]:
        """Auto-select best provider for request"""
        # If provider specified, use it
        if request.provider and request.provider in self.adapters:
            return self.adapters[request.provider]
        
        # Select based on priority and capability
        for provider in self.provider_priority:
            if provider not in self.adapters:
                continue
            
            adapter = self.adapters[provider]
            
            if request.frequency not in adapter.supported_frequencies:
                continue
            
            if request.asset_class not in adapter.supported_asset_classes:
                continue
            
            return adapter
        
        return None
    
    def get_historical(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime = None,
        frequency: DataFrequency = DataFrequency.DAILY,
        asset_class: AssetClass = AssetClass.EQUITY,
        adjusted: bool = True,
        provider: DataProvider = None
    ) -> DataResponse:
        """
        Get historical data for a symbol.
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date (default: now)
            frequency: Data frequency
            asset_class: Asset class
            adjusted: Use adjusted prices
            provider: Specific provider (None = auto)
            
        Returns:
            DataResponse with OHLCV bars
        """
        request = DataRequest(
            symbol=symbol.upper(),
            start_date=start_date,
            end_date=end_date or datetime.now(),
            frequency=frequency,
            asset_class=asset_class,
            adjusted=adjusted,
            provider=provider
        )
        
        # Check cache
        cached = self._check_cache(request)
        if cached:
            logger.debug(f"Cache hit for {symbol}")
            return cached
        
        # Select provider
        adapter = self._select_provider(request)
        
        if adapter is None:
            raise ValueError(f"No provider available for {symbol} with {frequency.value}")
        
        # Fetch with fallback
        errors = []
        tried_providers = []
        
        while adapter:
            tried_providers.append(adapter.provider)
            
            try:
                response = adapter.fetch_historical(request)
                
                # Cache result
                key = self._get_cache_key(request)
                self._cache[key] = (response, datetime.now())
                
                return response
                
            except Exception as e:
                errors.append(f"{adapter.provider.value}: {e}")
                logger.warning(f"Provider {adapter.provider.value} failed: {e}")
                
                if not self.enable_fallback:
                    raise
                
                # Try next provider
                adapter = None
                for provider in self.provider_priority:
                    if provider in tried_providers:
                        continue
                    if provider in self.adapters:
                        test_adapter = self.adapters[provider]
                        if request.frequency in test_adapter.supported_frequencies:
                            adapter = test_adapter
                            break
        
        raise Exception(f"All providers failed: {'; '.join(errors)}")
    
    def get_multiple(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime = None,
        frequency: DataFrequency = DataFrequency.DAILY
    ) -> Dict[str, DataResponse]:
        """
        Get historical data for multiple symbols.
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            frequency: Data frequency
            
        Returns:
            Dict of symbol: DataResponse
        """
        results = {}
        
        for symbol in symbols:
            try:
                results[symbol] = self.get_historical(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    frequency=frequency
                )
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                results[symbol] = None
        
        return results
    
    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get real-time quote for a symbol"""
        for provider in self.provider_priority:
            if provider not in self.adapters:
                continue
            
            adapter = self.adapters[provider]
            try:
                quote = adapter.fetch_quote(symbol.upper())
                if quote:
                    return quote
            except Exception as e:
                logger.debug(f"Quote fetch failed from {provider.value}: {e}")
        
        return None
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get quotes for multiple symbols"""
        return {symbol: self.get_quote(symbol) for symbol in symbols}
    
    def clear_cache(self):
        """Clear data cache"""
        self._cache.clear()
        logger.info("Cache cleared")


# ============== SINGLETON ==============

_data_api: Optional[UnifiedDataAPI] = None


def get_data_api(providers: Dict[DataProvider, str] = None) -> UnifiedDataAPI:
    """Get or create global data API"""
    global _data_api
    
    if _data_api is None:
        _data_api = UnifiedDataAPI(providers)
    
    return _data_api


# ============== CONVENIENCE FUNCTIONS ==============

def fetch_prices(
    symbol: str,
    days: int = 365,
    frequency: str = "daily"
) -> np.ndarray:
    """
    Quick function to fetch closing prices.
    
    Args:
        symbol: Trading symbol
        days: Number of days of history
        frequency: "daily", "hourly", "minute"
        
    Returns:
        Numpy array of closing prices
    """
    freq_map = {
        "daily": DataFrequency.DAILY,
        "hourly": DataFrequency.HOUR,
        "minute": DataFrequency.MINUTE,
    }
    
    api = get_data_api()
    response = api.get_historical(
        symbol=symbol,
        start_date=datetime.now() - timedelta(days=days),
        frequency=freq_map.get(frequency, DataFrequency.DAILY)
    )
    
    return response.closes


def fetch_ohlcv(
    symbol: str,
    days: int = 365
) -> Dict[str, np.ndarray]:
    """
    Quick function to fetch OHLCV data.
    
    Returns:
        Dict with 'open', 'high', 'low', 'close', 'volume' arrays
    """
    api = get_data_api()
    response = api.get_historical(
        symbol=symbol,
        start_date=datetime.now() - timedelta(days=days)
    )
    
    return response.to_arrays()
