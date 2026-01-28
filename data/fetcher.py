"""
QUANT_INDUSTRY_V1 Data Fetcher

Multi-source data fetcher with fallbacks, retry logic, and rate limiting.

Rollback Plan: Delete this file
Tests Required: API mocking, fallback chain, rate limit handling
Failure Modes: All sources fail -> return cached data or raise
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# DATA TYPES
# =============================================================================

class DataSource(Enum):
    """Available data sources."""
    ALPACA = "alpaca"
    YAHOO = "yahoo"
    POLYGON = "polygon"
    CACHE = "cache"
    MANUAL = "manual"


class Timeframe(Enum):
    """Supported timeframes."""
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


@dataclass
class Bar:
    """Single OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None
    trade_count: Optional[int] = None


@dataclass
class MarketData:
    """
    Market data container.

    Stores OHLCV data with metadata.
    """
    symbol: str
    timeframe: Timeframe
    bars: List[Bar]
    source: DataSource
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    quality_score: float = 1.0

    def __len__(self) -> int:
        return len(self.bars)

    def __bool__(self) -> bool:
        return len(self.bars) > 0

    @property
    def latest_bar(self) -> Optional[Bar]:
        """Get most recent bar."""
        return self.bars[-1] if self.bars else None

    @property
    def latest_price(self) -> Optional[float]:
        """Get most recent close price."""
        bar = self.latest_bar
        return bar.close if bar else None

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert to list of dictionaries."""
        return [
            {
                'timestamp': bar.timestamp.isoformat(),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'vwap': bar.vwap,
                'trade_count': bar.trade_count,
            }
            for bar in self.bars
        ]


@dataclass
class FetchResult:
    """Result of a data fetch operation."""
    success: bool
    data: Optional[MarketData] = None
    source: Optional[DataSource] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    cached: bool = False
    fallback_used: bool = False


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter.

    Ensures API rate limits are respected.
    """

    def __init__(self, rate: int, per_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            rate: Number of requests allowed
            per_seconds: Time window in seconds
        """
        self.rate = rate
        self.per_seconds = per_seconds
        self.tokens = float(rate)
        self.last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1, block: bool = True, timeout: float = 30.0) -> bool:
        """
        Acquire tokens (make a request).

        Args:
            tokens: Number of tokens to acquire
            block: Whether to block waiting for tokens
            timeout: Max time to wait

        Returns:
            True if tokens acquired, False otherwise
        """
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.per_seconds))
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            if not block:
                return False

        # Block waiting for tokens
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.1)
            with self._lock:
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.per_seconds))
                self.last_update = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

        logger.warning("Rate limiter timeout")
        return False

    def wait_time(self) -> float:
        """Get estimated wait time for next token."""
        with self._lock:
            if self.tokens >= 1:
                return 0.0
            return (1 - self.tokens) * (self.per_seconds / self.rate)


# =============================================================================
# BASE DATA PROVIDER
# =============================================================================

class BaseDataProvider(ABC):
    """Abstract base class for data providers."""

    def __init__(self, name: str, rate_limit: int = 200, timeout: float = 30.0):
        self.name = name
        self.rate_limiter = RateLimiter(rate_limit, 60)
        self.timeout = timeout
        self._available = True
        self._last_error: Optional[str] = None
        self._error_count = 0
        self._success_count = 0

    @property
    def source(self) -> DataSource:
        """Get data source enum."""
        return DataSource(self.name.lower())

    @property
    def is_available(self) -> bool:
        """Check if provider is available."""
        return self._available

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> FetchResult:
        """
        Fetch market data.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime (default: now)
            limit: Max bars to fetch

        Returns:
            FetchResult with data or error
        """
        pass

    def _record_success(self) -> None:
        """Record successful fetch."""
        self._success_count += 1
        self._error_count = max(0, self._error_count - 1)
        if not self._available and self._error_count == 0:
            self._available = True
            logger.info(f"Provider {self.name} restored")

    def _record_error(self, error: str) -> None:
        """Record fetch error."""
        self._error_count += 1
        self._last_error = error
        if self._error_count >= 5:
            self._available = False
            logger.warning(f"Provider {self.name} marked unavailable after {self._error_count} errors")


# =============================================================================
# ALPACA DATA PROVIDER
# =============================================================================

class AlpacaDataProvider(BaseDataProvider):
    """
    Alpaca Markets data provider.

    Primary data source for US equities.
    """

    TIMEFRAME_MAP = {
        Timeframe.MIN_1: "1Min",
        Timeframe.MIN_5: "5Min",
        Timeframe.MIN_15: "15Min",
        Timeframe.MIN_30: "30Min",
        Timeframe.HOUR_1: "1Hour",
        Timeframe.HOUR_4: "4Hour",
        Timeframe.DAY_1: "1Day",
        Timeframe.WEEK_1: "1Week",
        Timeframe.MONTH_1: "1Month",
    }

    def __init__(self, api_key: str = None, api_secret: str = None):
        super().__init__("alpaca", rate_limit=200)
        self.api_key = api_key
        self.api_secret = api_secret
        self._client = None

    def _get_client(self):
        """Get or create Alpaca client."""
        if self._client is None:
            try:
                from alpaca.data import StockHistoricalDataClient
                self._client = StockHistoricalDataClient(
                    api_key=self.api_key,
                    secret_key=self.api_secret,
                )
            except ImportError:
                logger.warning("alpaca-py not installed")
                self._available = False
            except Exception as e:
                logger.error(f"Failed to create Alpaca client: {e}")
                self._available = False
        return self._client

    def fetch(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> FetchResult:
        """Fetch data from Alpaca."""
        start_time = time.time()

        if not self.is_available:
            return FetchResult(
                success=False,
                error="Provider not available",
                source=self.source,
            )

        if not self.rate_limiter.acquire():
            return FetchResult(
                success=False,
                error="Rate limit exceeded",
                source=self.source,
            )

        try:
            client = self._get_client()
            if client is None:
                return FetchResult(
                    success=False,
                    error="Client not available",
                    source=self.source,
                )

            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

            # Map timeframe
            tf_map = {
                Timeframe.MIN_1: TimeFrame(1, TimeFrameUnit.Minute),
                Timeframe.MIN_5: TimeFrame(5, TimeFrameUnit.Minute),
                Timeframe.MIN_15: TimeFrame(15, TimeFrameUnit.Minute),
                Timeframe.MIN_30: TimeFrame(30, TimeFrameUnit.Minute),
                Timeframe.HOUR_1: TimeFrame(1, TimeFrameUnit.Hour),
                Timeframe.DAY_1: TimeFrame(1, TimeFrameUnit.Day),
                Timeframe.WEEK_1: TimeFrame(1, TimeFrameUnit.Week),
                Timeframe.MONTH_1: TimeFrame(1, TimeFrameUnit.Month),
            }

            alpaca_tf = tf_map.get(timeframe)
            if alpaca_tf is None:
                return FetchResult(
                    success=False,
                    error=f"Unsupported timeframe: {timeframe}",
                    source=self.source,
                )

            end = end or datetime.now(timezone.utc)

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=alpaca_tf,
                start=start,
                end=end,
                limit=limit,
            )

            bars_response = client.get_stock_bars(request)
            bars_data = bars_response[symbol] if symbol in bars_response else []

            bars = [
                Bar(
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                    vwap=float(bar.vwap) if bar.vwap else None,
                    trade_count=bar.trade_count,
                )
                for bar in bars_data
            ]

            market_data = MarketData(
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
                source=self.source,
            )

            self._record_success()

            return FetchResult(
                success=True,
                data=market_data,
                source=self.source,
                latency_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            self._record_error(str(e))
            return FetchResult(
                success=False,
                error=str(e),
                source=self.source,
                latency_ms=(time.time() - start_time) * 1000,
            )


# =============================================================================
# YAHOO FINANCE DATA PROVIDER
# =============================================================================

class YahooDataProvider(BaseDataProvider):
    """
    Yahoo Finance data provider.

    Fallback data source with broad coverage.
    """

    TIMEFRAME_MAP = {
        Timeframe.MIN_1: "1m",
        Timeframe.MIN_5: "5m",
        Timeframe.MIN_15: "15m",
        Timeframe.MIN_30: "30m",
        Timeframe.HOUR_1: "1h",
        Timeframe.DAY_1: "1d",
        Timeframe.WEEK_1: "1wk",
        Timeframe.MONTH_1: "1mo",
    }

    def __init__(self):
        super().__init__("yahoo", rate_limit=100)

    def fetch(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> FetchResult:
        """Fetch data from Yahoo Finance."""
        start_time = time.time()

        if not self.is_available:
            return FetchResult(
                success=False,
                error="Provider not available",
                source=self.source,
            )

        if not self.rate_limiter.acquire():
            return FetchResult(
                success=False,
                error="Rate limit exceeded",
                source=self.source,
            )

        try:
            import yfinance as yf

            yahoo_tf = self.TIMEFRAME_MAP.get(timeframe)
            if yahoo_tf is None:
                return FetchResult(
                    success=False,
                    error=f"Unsupported timeframe: {timeframe}",
                    source=self.source,
                )

            end = end or datetime.now(timezone.utc)

            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start,
                end=end,
                interval=yahoo_tf,
            )

            if df.empty:
                return FetchResult(
                    success=False,
                    error="No data returned",
                    source=self.source,
                )

            bars = [
                Bar(
                    timestamp=idx.to_pydatetime().replace(tzinfo=timezone.utc),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=float(row['Volume']),
                )
                for idx, row in df.iterrows()
            ]

            # Limit results
            if len(bars) > limit:
                bars = bars[-limit:]

            market_data = MarketData(
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
                source=self.source,
            )

            self._record_success()

            return FetchResult(
                success=True,
                data=market_data,
                source=self.source,
                latency_ms=(time.time() - start_time) * 1000,
            )

        except ImportError:
            self._available = False
            return FetchResult(
                success=False,
                error="yfinance not installed",
                source=self.source,
            )
        except Exception as e:
            self._record_error(str(e))
            return FetchResult(
                success=False,
                error=str(e),
                source=self.source,
                latency_ms=(time.time() - start_time) * 1000,
            )


# =============================================================================
# UNIFIED DATA FETCHER
# =============================================================================

class UnifiedDataFetcher:
    """
    Multi-source data fetcher with fallback chain.

    Features:
    - Multiple data sources (Alpaca -> Yahoo fallback)
    - Rate limiting per source
    - Automatic failover
    - Caching integration
    - Quality scoring
    """

    def __init__(
        self,
        alpaca_key: str = None,
        alpaca_secret: str = None,
        cache_enabled: bool = True,
        fallback_enabled: bool = True,
    ):
        self.fallback_enabled = fallback_enabled
        self.cache_enabled = cache_enabled

        # Initialize providers
        self._providers: List[BaseDataProvider] = []

        # Primary: Alpaca
        alpaca = AlpacaDataProvider(api_key=alpaca_key, api_secret=alpaca_secret)
        self._providers.append(alpaca)

        # Fallback: Yahoo
        yahoo = YahooDataProvider()
        self._providers.append(yahoo)

        # Cache reference (set externally)
        self._cache = None

        logger.info(f"UnifiedDataFetcher initialized with {len(self._providers)} providers")

    def set_cache(self, cache) -> None:
        """Set cache instance."""
        self._cache = cache

    def fetch(
        self,
        symbol: str,
        timeframe: Timeframe = Timeframe.DAY_1,
        start: datetime = None,
        end: datetime = None,
        limit: int = 100,
        use_cache: bool = True,
    ) -> FetchResult:
        """
        Fetch market data with fallback.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime (default: limit bars back)
            end: End datetime (default: now)
            limit: Max bars
            use_cache: Whether to check cache first

        Returns:
            FetchResult with data or error
        """
        end = end or datetime.now(timezone.utc)

        # Calculate default start
        if start is None:
            tf_deltas = {
                Timeframe.MIN_1: timedelta(minutes=limit),
                Timeframe.MIN_5: timedelta(minutes=limit * 5),
                Timeframe.MIN_15: timedelta(minutes=limit * 15),
                Timeframe.MIN_30: timedelta(minutes=limit * 30),
                Timeframe.HOUR_1: timedelta(hours=limit),
                Timeframe.HOUR_4: timedelta(hours=limit * 4),
                Timeframe.DAY_1: timedelta(days=limit),
                Timeframe.WEEK_1: timedelta(weeks=limit),
                Timeframe.MONTH_1: timedelta(days=limit * 30),
            }
            start = end - tf_deltas.get(timeframe, timedelta(days=limit))

        # Check cache
        if use_cache and self.cache_enabled and self._cache is not None:
            cached = self._cache.get(symbol, timeframe, start, end)
            if cached is not None:
                return FetchResult(
                    success=True,
                    data=cached,
                    source=DataSource.CACHE,
                    cached=True,
                )

        # Try providers in order
        last_error = None
        fallback_used = False

        for i, provider in enumerate(self._providers):
            if not provider.is_available:
                continue

            result = provider.fetch(symbol, timeframe, start, end, limit)

            if result.success and result.data:
                # Cache the result
                if self.cache_enabled and self._cache is not None:
                    self._cache.set(result.data)

                result.fallback_used = fallback_used

                logger.debug(
                    f"Fetched {symbol} from {provider.name}: "
                    f"{len(result.data)} bars, {result.latency_ms:.0f}ms"
                )
                return result

            last_error = result.error
            fallback_used = True

            if not self.fallback_enabled:
                break

            logger.warning(f"Provider {provider.name} failed for {symbol}: {result.error}")

        # All providers failed
        return FetchResult(
            success=False,
            error=last_error or "All providers failed",
            fallback_used=fallback_used,
        )

    def fetch_batch(
        self,
        symbols: List[str],
        timeframe: Timeframe = Timeframe.DAY_1,
        limit: int = 100,
    ) -> Dict[str, FetchResult]:
        """
        Fetch data for multiple symbols.

        Args:
            symbols: List of symbols
            timeframe: Data timeframe
            limit: Max bars per symbol

        Returns:
            Dictionary of symbol -> FetchResult
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.fetch(symbol, timeframe, limit=limit)
        return results

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol."""
        result = self.fetch(symbol, Timeframe.MIN_1, limit=1)
        if result.success and result.data:
            return result.data.latest_price
        return None

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers."""
        return {
            provider.name: {
                'available': provider.is_available,
                'error_count': provider._error_count,
                'success_count': provider._success_count,
                'last_error': provider._last_error,
            }
            for provider in self._providers
        }
