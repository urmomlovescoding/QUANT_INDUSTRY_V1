"""
QUANT INDUSTRY - Data Service
Multi-source market data provider with intelligent failover
Includes proper market hours detection and stable closed-market pricing
"""

import hashlib
import logging
import os
import random
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Import market hours service
try:
    from .market_hours import (
        MarketSession,
        can_trade,
        get_last_trading_day,
        get_market_session,
        get_market_status,
        is_market_open,
    )
    HAS_MARKET_HOURS = True
except ImportError:
    HAS_MARKET_HOURS = False

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

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

try:
    from utils.retry import CircuitBreaker
except ImportError:
    CircuitBreaker = None

logger = logging.getLogger(__name__)


# ============== DATA CLASSES ==============

@dataclass
class Quote:
    symbol: str
    price: float
    bid: float
    ask: float
    volume: int
    change: float
    change_pct: float
    high: float
    low: float
    open: float
    prev_close: float
    timestamp: datetime
    source: str = "unknown"
    market_session: str = "unknown"  # regular, pre_market, after_hours, closed
    is_market_open: bool = True


@dataclass
class OHLCV:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class OptionChain:
    symbol: str
    expiration: str
    calls: List[Dict]
    puts: List[Dict]
    underlying_price: float


@dataclass
class CacheEntry:
    data: Any
    timestamp: float
    ttl: float


# ============== DATA STALENESS DETECTION ==============

class StalenessLevel(Enum):
    """Data staleness severity levels."""
    FRESH = "fresh"           # Within expected TTL
    STALE = "stale"           # Slightly over TTL but usable
    VERY_STALE = "very_stale" # Significantly over TTL, use with caution
    EXPIRED = "expired"       # Data too old to be reliable


@dataclass
class DataStalenessAlert:
    """Alert for stale data."""
    symbol: str
    data_type: str  # quote, historical, options
    age_seconds: float
    staleness_level: StalenessLevel
    source: str
    last_update: datetime
    message: str
    threshold_seconds: float


class StalenessTracker:
    """
    Tracks data freshness and generates alerts for stale data.
    Matches quant-platform pattern for data quality monitoring.
    """

    def __init__(self):
        self.staleness_thresholds = {
            "quote": {
                "fresh": 15,        # 15s - within normal refresh
                "stale": 60,        # 1 min - slightly stale
                "very_stale": 300,  # 5 min - very stale
                "expired": 900      # 15 min - don't use
            },
            "historical": {
                "fresh": 120,       # 2 min
                "stale": 600,       # 10 min
                "very_stale": 3600, # 1 hour
                "expired": 86400    # 24 hours
            },
            "options": {
                "fresh": 30,        # 30s
                "stale": 120,       # 2 min
                "very_stale": 600,  # 10 min
                "expired": 1800     # 30 min
            }
        }
        self.alerts: List[DataStalenessAlert] = []
        self._max_alerts = 100
        self._lock = threading.Lock()

        # Track last update times
        self.last_updates: Dict[str, Dict[str, datetime]] = {}  # symbol -> {data_type: timestamp}

    def record_update(self, symbol: str, data_type: str, source: str = "unknown"):
        """Record that data was updated."""
        with self._lock:
            if symbol not in self.last_updates:
                self.last_updates[symbol] = {}
            self.last_updates[symbol][data_type] = datetime.now()

    def check_staleness(
        self,
        symbol: str,
        data_type: str,
        last_update: datetime = None,
        source: str = "unknown"
    ) -> Tuple[StalenessLevel, Optional[DataStalenessAlert]]:
        """
        Check if data is stale and return staleness level with optional alert.

        Args:
            symbol: The symbol to check
            data_type: Type of data (quote, historical, options)
            last_update: Optional override for last update time
            source: Data source name

        Returns:
            (StalenessLevel, optional alert if stale)
        """
        # Get last update time
        if last_update is None:
            with self._lock:
                updates = self.last_updates.get(symbol, {})
                last_update = updates.get(data_type)

        if last_update is None:
            # No record of update - consider expired
            return StalenessLevel.EXPIRED, DataStalenessAlert(
                symbol=symbol,
                data_type=data_type,
                age_seconds=float('inf'),
                staleness_level=StalenessLevel.EXPIRED,
                source=source,
                last_update=datetime.min,
                message=f"No data recorded for {symbol} {data_type}",
                threshold_seconds=0
            )

        # Calculate age
        age_seconds = (datetime.now() - last_update).total_seconds()
        thresholds = self.staleness_thresholds.get(data_type, self.staleness_thresholds["quote"])

        # Determine staleness level
        level = StalenessLevel.FRESH
        alert = None

        if age_seconds >= thresholds["expired"]:
            level = StalenessLevel.EXPIRED
        elif age_seconds >= thresholds["very_stale"]:
            level = StalenessLevel.VERY_STALE
        elif age_seconds >= thresholds["stale"]:
            level = StalenessLevel.STALE

        # Generate alert if not fresh
        if level != StalenessLevel.FRESH:
            alert = DataStalenessAlert(
                symbol=symbol,
                data_type=data_type,
                age_seconds=age_seconds,
                staleness_level=level,
                source=source,
                last_update=last_update,
                message=self._generate_message(symbol, data_type, age_seconds, level),
                threshold_seconds=thresholds[level.value]
            )
            self._record_alert(alert)

        return level, alert

    def _generate_message(
        self,
        symbol: str,
        data_type: str,
        age_seconds: float,
        level: StalenessLevel
    ) -> str:
        """Generate human-readable staleness message."""
        if age_seconds < 60:
            age_str = f"{age_seconds:.0f}s"
        elif age_seconds < 3600:
            age_str = f"{age_seconds / 60:.1f}min"
        else:
            age_str = f"{age_seconds / 3600:.1f}hr"

        level_text = {
            StalenessLevel.STALE: "slightly stale",
            StalenessLevel.VERY_STALE: "very stale - use with caution",
            StalenessLevel.EXPIRED: "EXPIRED - do not use for trading"
        }

        return f"{symbol} {data_type} data is {level_text.get(level, 'stale')} (age: {age_str})"

    def _record_alert(self, alert: DataStalenessAlert):
        """Record a staleness alert."""
        with self._lock:
            self.alerts.append(alert)
            if len(self.alerts) > self._max_alerts:
                self.alerts.pop(0)

    def get_alerts(
        self,
        symbol: str = None,
        data_type: str = None,
        min_level: StalenessLevel = StalenessLevel.STALE
    ) -> List[DataStalenessAlert]:
        """Get staleness alerts, optionally filtered."""
        level_order = [StalenessLevel.FRESH, StalenessLevel.STALE,
                       StalenessLevel.VERY_STALE, StalenessLevel.EXPIRED]
        min_idx = level_order.index(min_level)

        with self._lock:
            alerts = [a for a in self.alerts
                      if level_order.index(a.staleness_level) >= min_idx]

            if symbol:
                alerts = [a for a in alerts if a.symbol == symbol]
            if data_type:
                alerts = [a for a in alerts if a.data_type == data_type]

            return alerts

    def get_staleness_summary(self) -> Dict[str, Any]:
        """Get summary of data staleness status."""
        with self._lock:
            total_tracked = len(self.last_updates)
            stale_count = len([a for a in self.alerts[-50:]
                               if a.staleness_level in (StalenessLevel.STALE, StalenessLevel.VERY_STALE)])
            expired_count = len([a for a in self.alerts[-50:]
                                 if a.staleness_level == StalenessLevel.EXPIRED])

            return {
                "total_symbols_tracked": total_tracked,
                "recent_stale_alerts": stale_count,
                "recent_expired_alerts": expired_count,
                "last_50_alerts": [
                    {
                        "symbol": a.symbol,
                        "data_type": a.data_type,
                        "level": a.staleness_level.value,
                        "age_seconds": a.age_seconds,
                        "message": a.message
                    }
                    for a in self.alerts[-50:]
                ]
            }


# Global staleness tracker
_staleness_tracker: Optional[StalenessTracker] = None


def get_staleness_tracker() -> StalenessTracker:
    """Get global staleness tracker instance."""
    global _staleness_tracker
    if _staleness_tracker is None:
        _staleness_tracker = StalenessTracker()
    return _staleness_tracker


# ============== FALLBACK PRICE ESTIMATES (Feb 2026) ==============
# Updated 2026-02-06 with current market prices

FALLBACK_PRICES = {
    # Major Indices ETFs
    "SPY": 688.00, "QQQ": 606.00, "DIA": 499.00, "IWM": 264.00,
    # Mag 7
    "AAPL": 279.00, "MSFT": 396.00, "GOOGL": 321.00, "AMZN": 205.00,
    "NVDA": 183.00, "META": 655.00, "TSLA": 410.00,
    # Semiconductors
    "AMD": 207.00, "INTC": 51.00, "AVGO": 331.00, "QCOM": 138.00,
    "MU": 388.00, "AMAT": 193.00, "LRCX": 79.00, "KLAC": 720.00,
    # Tech
    "CRM": 190.00, "ORCL": 141.00, "ADBE": 267.00, "NOW": 102.00,
    "SHOP": 109.00, "SQ": 79.00, "PYPL": 69.00, "PLTR": 135.00,
    # Financials
    "JPM": 322.00, "BAC": 56.00, "WFC": 94.00, "GS": 921.00,
    "MS": 180.00, "BLK": 1026.00, "C": 69.00, "AXP": 298.00,
    # Healthcare
    "JNJ": 239.00, "UNH": 275.00, "PFE": 27.00, "MRK": 108.00,
    "ABBV": 186.00, "LLY": 1049.00, "BMY": 52.00, "AMGN": 298.00,
    # Consumer
    "WMT": 130.00, "COST": 996.00, "HD": 385.00, "MCD": 298.00,
    "NKE": 79.00, "SBUX": 98.00, "DIS": 113.00, "NFLX": 81.00,
    # Energy
    "XOM": 149.00, "CVX": 181.00, "COP": 112.00, "SLB": 49.00,
    "EOG": 133.00, "PXD": 246.00, "OXY": 52.00, "DVN": 43.00,
    # Futures (Micro)
    "MES": 5950.0, "MNQ": 21500.0, "MYM": 43500.0, "M2K": 2250.0,
    "MGC": 2350.0, "SIL": 28.50, "MCL": 72.50, "MBT": 98500.0,
    # VIX and Bonds
    "VIX": 18.00, "VXX": 42.00, "UVXY": 29.00,
    "TLT": 93.00, "IEF": 98.00, "SHY": 82.00, "HYG": 79.00,
    # Commodities ETFs
    "GLD": 219.00, "SLV": 25.00, "USO": 79.00, "UNG": 12.00,
    # International
    "EEM": 43.00, "FXI": 29.00, "EWJ": 69.00, "EFA": 82.00,
}


# ============== DATA QUALITY VALIDATION ==============

def validate_quote(quote: Quote, reference_prices: Dict[str, float] = None) -> Tuple[bool, str]:
    """
    Validate quote data quality to protect against bad data.
    Returns (is_valid, reason) tuple.
    """
    if quote is None:
        return False, "Quote is None"

    # Price must be positive
    if quote.price <= 0:
        return False, f"Invalid price: {quote.price}"

    # Validate change percentage - allow extreme but reject impossible
    if abs(quote.change_pct) > 100:  # >100% move in a day is suspicious
        return False, f"Suspicious change percentage: {quote.change_pct}%"

    # Cross-validate against reference prices if available
    ref_prices = reference_prices or FALLBACK_PRICES
    symbol = quote.symbol.upper().replace("^", "")  # Handle ^VIX -> VIX
    if symbol in ref_prices:
        ref_price = ref_prices[symbol]
        # Allow up to 50% deviation from reference (markets can move)
        if ref_price > 0:
            deviation = abs(quote.price - ref_price) / ref_price
            if deviation > 0.5:  # More than 50% off reference
                logger.warning(
                    f"[DATA QUALITY] {symbol} price ${quote.price:.2f} is {deviation*100:.0f}% "
                    f"from reference ${ref_price:.2f} - flagging as suspicious"
                )
                # Don't reject outright, just flag - markets can move significantly

    # Validate bid/ask spread is reasonable
    if quote.bid > 0 and quote.ask > 0:
        spread_pct = (quote.ask - quote.bid) / quote.price * 100
        if spread_pct > 10:  # >10% spread is very wide
            logger.debug(f"[DATA QUALITY] {quote.symbol} has wide spread: {spread_pct:.1f}%")

    return True, "Valid"


# ============== DATA PROVIDERS ==============

class DataSourceBase:
    """Base class for data sources"""

    def __init__(self, name: str, rate_limit: float = 1.0):
        self.name = name
        self.rate_limit = rate_limit
        self.last_request = 0
        self.backoff = 1.0
        self.max_backoff = 120.0
        self.lock = threading.Lock()

    def _wait_rate_limit(self):
        """Wait for rate limiting"""
        with self.lock:
            now = time.time()
            wait_time = (self.last_request + self.rate_limit * self.backoff) - now
            if wait_time > 0:
                time.sleep(wait_time)
            self.last_request = time.time()

    def _success(self):
        """Reduce backoff on success"""
        self.backoff = max(1.0, self.backoff * 0.8)

    def _failure(self):
        """Increase backoff on failure"""
        self.backoff = min(self.max_backoff, self.backoff * 2.0)

    def get_quote(self, symbol: str) -> Optional[Quote]:
        raise NotImplementedError

    def get_historical(self, symbol: str, period: str = "1y", interval: str = "1d") -> List[OHLCV]:
        raise NotImplementedError


class YahooDataSource(DataSourceBase):
    """Yahoo Finance data source"""

    def __init__(self):
        super().__init__("yahoo", rate_limit=0.5)

    def get_quote(self, symbol: str) -> Optional[Quote]:
        if not HAS_YFINANCE:
            return None

        self._wait_rate_limit()
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            price = info.get('regularMarketPrice') or info.get('currentPrice', 0)
            prev_close = info.get('previousClose', price)

            quote = Quote(
                symbol=symbol,
                price=price,
                bid=info.get('bid', price),
                ask=info.get('ask', price),
                volume=info.get('regularMarketVolume', 0),
                change=price - prev_close,
                change_pct=((price - prev_close) / prev_close * 100) if prev_close else 0,
                high=info.get('dayHigh', price),
                low=info.get('dayLow', price),
                open=info.get('regularMarketOpen', price),
                prev_close=prev_close,
                timestamp=datetime.now(),
                source="yahoo"
            )
            self._success()
            return quote
        except Exception as e:
            logger.warning(f"Yahoo quote failed for {symbol}: {e}")
            self._failure()
            return None

    def get_historical(self, symbol: str, period: str = "1y", interval: str = "1d") -> List[OHLCV]:
        if not HAS_YFINANCE:
            return []

        self._wait_rate_limit()
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)

            result = []
            for idx, row in df.iterrows():
                result.append(OHLCV(
                    timestamp=idx.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume'])
                ))
            self._success()
            return result
        except Exception as e:
            logger.warning(f"Yahoo historical failed for {symbol}: {e}")
            self._failure()
            return []


class AlpacaDataSource(DataSourceBase):
    """Alpaca Markets data source"""

    def __init__(self, api_key: str = None, secret_key: str = None):
        super().__init__("alpaca", rate_limit=0.2)

        # Try to load from config
        try:
            from ..config.api_keys import get_api_keys
            keys = get_api_keys()
            self.api_key = api_key or keys.alpaca.api_key or os.getenv("ALPACA_API_KEY", "")
            self.secret_key = secret_key or keys.alpaca.secret_key or os.getenv("ALPACA_SECRET_KEY", "")
        except Exception:
            self.api_key = api_key or os.getenv("ALPACA_API_KEY", "")
            self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY", "")

        self.base_url = "https://data.alpaca.markets/v2"

    def _get_headers(self):
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }

    def get_quote(self, symbol: str) -> Optional[Quote]:
        if not self.api_key or not HAS_REQUESTS:
            return None

        self._wait_rate_limit()
        try:
            url = f"{self.base_url}/stocks/{symbol}/quotes/latest"
            response = requests.get(url, headers=self._get_headers(), timeout=10)

            if response.status_code != 200:
                self._failure()
                return None

            data = response.json().get('quote', {})
            price = (data.get('bp', 0) + data.get('ap', 0)) / 2

            quote = Quote(
                symbol=symbol,
                price=price,
                bid=data.get('bp', price),
                ask=data.get('ap', price),
                volume=data.get('as', 0) + data.get('bs', 0),
                change=0,
                change_pct=0,
                high=price,
                low=price,
                open=price,
                prev_close=price,
                timestamp=datetime.now(),
                source="alpaca"
            )
            self._success()
            return quote
        except Exception as e:
            logger.warning(f"Alpaca quote failed for {symbol}: {e}")
            self._failure()
            return None


class FinnhubDataSource(DataSourceBase):
    """Finnhub data source"""

    def __init__(self, api_key: str = None):
        super().__init__("finnhub", rate_limit=1.0)  # 60/min limit

        # Try to load from config
        try:
            from ..config.api_keys import get_api_keys
            keys = get_api_keys()
            self.api_key = api_key or keys.finnhub.api_key or os.getenv("FINNHUB_API_KEY", "")
        except Exception:
            self.api_key = api_key or os.getenv("FINNHUB_API_KEY", "")

        self.base_url = "https://finnhub.io/api/v1"

    def get_quote(self, symbol: str) -> Optional[Quote]:
        if not self.api_key or not HAS_REQUESTS:
            return None

        self._wait_rate_limit()
        try:
            url = f"{self.base_url}/quote"
            params = {"symbol": symbol, "token": self.api_key}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                self._failure()
                return None

            data = response.json()
            if data.get('c', 0) == 0:
                return None

            quote = Quote(
                symbol=symbol,
                price=data.get('c', 0),
                bid=data.get('c', 0),
                ask=data.get('c', 0),
                volume=0,
                change=data.get('d', 0),
                change_pct=data.get('dp', 0),
                high=data.get('h', 0),
                low=data.get('l', 0),
                open=data.get('o', 0),
                prev_close=data.get('pc', 0),
                timestamp=datetime.now(),
                source="finnhub"
            )
            self._success()
            return quote
        except Exception as e:
            logger.warning(f"Finnhub quote failed for {symbol}: {e}")
            self._failure()
            return None


class TradierDataSource(DataSourceBase):
    """Tradier data source - excellent for options and stock quotes"""

    def __init__(self, api_key: str = None):
        super().__init__("tradier", rate_limit=0.2)  # 5 req/sec

        self.api_key = api_key or os.getenv("TRADIER_API_KEY", "")
        self.base_url = "https://api.tradier.com/v1"

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

    def get_quote(self, symbol: str) -> Optional[Quote]:
        if not self.api_key or not HAS_REQUESTS:
            return None

        self._wait_rate_limit()
        try:
            url = f"{self.base_url}/markets/quotes"
            params = {"symbols": symbol, "greeks": "false"}
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=3)

            if response.status_code != 200:
                self._failure()
                return None

            data = response.json()
            quote_data = data.get('quotes', {}).get('quote', {})

            if not quote_data or quote_data.get('last') is None:
                return None

            price = float(quote_data.get('last', 0))
            prev_close = float(quote_data.get('prevclose', price))

            quote = Quote(
                symbol=symbol.upper(),
                price=price,
                bid=float(quote_data.get('bid', price)),
                ask=float(quote_data.get('ask', price)),
                volume=int(quote_data.get('volume', 0)),
                change=float(quote_data.get('change', 0)),
                change_pct=float(quote_data.get('change_percentage', 0)),
                high=float(quote_data.get('high', price)),
                low=float(quote_data.get('low', price)),
                open=float(quote_data.get('open', price)),
                prev_close=prev_close,
                timestamp=datetime.now(),
                source="tradier"
            )
            self._success()
            logger.info(f"[TRADIER] {symbol}: ${price:.2f}")
            return quote
        except Exception as e:
            logger.warning(f"Tradier quote failed for {symbol}: {e}")
            self._failure()
            return None


class FallbackDataSource(DataSourceBase):
    """Fallback synthetic data source - respects market hours, persists prices"""

    # Cache for last known prices during closed hours
    _last_known_prices: Dict[str, Dict] = {}
    _db_path: str = None

    def __init__(self, db_path: str = None):
        super().__init__("fallback", rate_limit=0)
        self._db_path = db_path or os.path.join(os.path.dirname(__file__), "..", "cache", "last_prices.db")
        self._init_db()
        self._load_cached_prices()

    def _init_db(self):
        """Initialize SQLite database for price persistence"""
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_prices (
                    symbol TEXT PRIMARY KEY,
                    price REAL,
                    change REAL,
                    prev_close REAL,
                    high REAL,
                    low REAL,
                    open_price REAL,
                    volume INTEGER,
                    last_update TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to init price DB: {e}")

    def _load_cached_prices(self):
        """Load last known prices from database"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM last_prices")
            rows = cursor.fetchall()
            for row in rows:
                symbol, price, change, prev_close, high, low, open_price, volume, _ = row
                self._last_known_prices[symbol] = {
                    'price': price,
                    'change': change,
                    'prev_close': prev_close,
                    'high': high,
                    'low': low,
                    'open': open_price,
                    'volume': volume
                }
            conn.close()
            logger.info(f"Loaded {len(self._last_known_prices)} cached prices from DB")
        except Exception as e:
            logger.warning(f"Failed to load cached prices: {e}")

    def _save_price(self, symbol: str, data: Dict):
        """Save price to database"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO last_prices
                (symbol, price, change, prev_close, high, low, open_price, volume, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                data.get('price'),
                data.get('change'),
                data.get('prev_close'),
                data.get('high'),
                data.get('low'),
                data.get('open'),
                data.get('volume'),
                datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to save price for {symbol}: {e}")

    def get_quote(self, symbol: str) -> Optional[Quote]:
        symbol = symbol.upper()
        base_price = FALLBACK_PRICES.get(symbol)

        if base_price is None:
            # Use consistent price for unknown symbols (not random)
            base_price = 50 + (hash(symbol) % 450)

        # Check market hours
        market_open = True
        session = "regular"
        if HAS_MARKET_HOURS:
            market_session, status = get_market_session()
            session = market_session.value
            market_open = status.get("is_open", False) or status.get("is_pre_market", False) or status.get("is_after_hours", False)

        # If market is closed, return stable prices without fluctuation
        if not market_open:
            # Use cached price if available, otherwise use base price
            cached = self._last_known_prices.get(symbol, {})
            price = cached.get('price', base_price)
            change = cached.get('change', 0)
            prev_close = cached.get('prev_close', price)
            high = cached.get('high', price)
            low = cached.get('low', price)
            open_price = cached.get('open', price)
            volume = cached.get('volume', 0)  # No volume when closed

            return Quote(
                symbol=symbol,
                price=price,
                bid=price,
                ask=price,
                volume=volume,
                change=change,
                change_pct=(change / prev_close * 100) if prev_close else 0,
                high=high,
                low=low,
                open=open_price,
                prev_close=prev_close,
                timestamp=datetime.now(),
                source="fallback",
                market_session=session,
                is_market_open=False
            )

        # Market is open - add realistic fluctuations
        price = base_price * (1 + (random.random() - 0.5) * 0.02)
        change = (random.random() - 0.5) * 5
        prev_close = price - change
        high = price * 1.01
        low = price * 0.99
        open_price = price * (1 + (random.random() - 0.5) * 0.01)
        volume = int(10000000 + random.random() * 90000000)

        # Cache this price for closed hours (in memory and DB)
        price_data = {
            'price': price,
            'change': change,
            'prev_close': prev_close,
            'high': high,
            'low': low,
            'open': open_price,
            'volume': volume
        }
        self._last_known_prices[symbol] = price_data
        self._save_price(symbol, price_data)

        return Quote(
            symbol=symbol,
            price=price,
            bid=price - 0.01,
            ask=price + 0.01,
            volume=volume,
            change=change,
            change_pct=change / price * 100,
            high=high,
            low=low,
            open=open_price,
            prev_close=prev_close,
            timestamp=datetime.now(),
            source="fallback",
            market_session=session,
            is_market_open=True
        )

    def get_historical(self, symbol: str, period: str = "1y", interval: str = "1d") -> List[OHLCV]:
        symbol = symbol.upper()
        base_price = FALLBACK_PRICES.get(symbol, 100)

        # Determine number of bars
        period_days = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
            "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 2500
        }
        num_days = period_days.get(period, 365)

        result = []
        price = base_price * 0.7  # Start lower

        for i in range(num_days):
            timestamp = datetime.now() - timedelta(days=num_days - i)

            # Random walk
            change = (random.random() - 0.48) * price * 0.025
            price += change

            high = price * (1 + random.random() * 0.02)
            low = price * (1 - random.random() * 0.02)
            open_price = price + (random.random() - 0.5) * price * 0.01

            result.append(OHLCV(
                timestamp=timestamp,
                open=open_price,
                high=high,
                low=low,
                close=price,
                volume=int(10000000 + random.random() * 90000000)
            ))

        return result


# ============== MAIN DATA SERVICE ==============

class DataService:
    """
    Multi-source data service with intelligent failover and caching
    LIVE DATA MODE - Always tries real sources first, fallback disabled by default
    """

    def __init__(self, cache_dir: str = None, force_live: bool = True):
        self.sources: List[DataSourceBase] = []
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_lock = threading.Lock()
        self.force_live = force_live  # When True, don't use fallback for primary data
        self.cache_ttl = {
            "quote": 30,      # 30 seconds for quotes (balance freshness vs speed)
            "historical": 120, # 2 minutes for historical
            "options": 30,    # 30 seconds for options
        }

        # Initialize data sources in priority order
        self._init_sources()

        # SQLite cache for persistence
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), "..", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.db_path = os.path.join(self.cache_dir, "data_cache.db")
        self._init_db()

        # Thread pool for concurrent requests
        self.executor = ThreadPoolExecutor(max_workers=10)

        # Circuit breakers for each source (protect against hammering failing sources)
        self.circuit_breakers: Dict[str, Any] = {
            source.name: CircuitBreaker(
                failure_threshold=2,      # Open after 2 failures (fast fail)
                recovery_timeout=60.0,    # Try again after 60 seconds
                half_open_max_calls=1     # 1 successful call to close
            )
            for source in self.sources
        }

        # Reliability tracking for each source
        self.source_stats: Dict[str, Dict] = {
            source.name: {
                'success_count': 0,
                'failure_count': 0,
                'total_latency_ms': 0.0,
                'last_success': None,
                'last_failure': None,
            }
            for source in self.sources
        }

        # Log active sources
        live_sources = [s.name for s in self.sources if s.name != "fallback"]
        logger.info(f"DataService initialized with {len(self.sources)} sources")
        logger.info(f"LIVE DATA MODE: {'ENABLED' if force_live else 'DISABLED'}")
        logger.info(f"Active live sources: {live_sources if live_sources else 'None - will use fallback'}")

    def _init_sources(self):
        """Initialize data sources in priority order"""
        # 1. Try Alpaca first (no rate limit for paper)
        alpaca = AlpacaDataSource()
        if alpaca.api_key:
            self.sources.append(alpaca)
            logger.info("[DATA SOURCE] Alpaca: ENABLED")

        # 2. Tradier - disabled at startup, enable via API if DNS resolves
        # DNS for api.tradier.com is unreachable from some networks causing 30s+ timeouts
        tradier = TradierDataSource()
        if tradier.api_key:
            try:
                import socket
                socket.getaddrinfo("api.tradier.com", 443, socket.AF_INET, socket.SOCK_STREAM)
                self.sources.append(tradier)
                logger.info("[DATA SOURCE] Tradier: ENABLED")
            except (socket.gaierror, OSError):
                logger.warning("[DATA SOURCE] Tradier: DISABLED (DNS unreachable)")

        # 3. Yahoo Finance (widely available, no API key needed)
        if HAS_YFINANCE:
            self.sources.append(YahooDataSource())
            logger.info("[DATA SOURCE] Yahoo Finance: ENABLED")

        # 4. Finnhub (free tier)
        finnhub = FinnhubDataSource()
        if finnhub.api_key:
            self.sources.append(finnhub)
            logger.info("[DATA SOURCE] Finnhub: ENABLED")

        # 5. Always have fallback
        self.sources.append(FallbackDataSource())

    def _init_db(self):
        """Initialize SQLite cache database"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        timestamp REAL,
                        ttl REAL
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_timestamp ON cache(timestamp)
                """)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize cache database: {e}")

    def _get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key"""
        key_str = f"{prefix}:" + ":".join(str(a) for a in args)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        with self.cache_lock:
            entry = self.cache.get(key)
            if entry and time.time() - entry.timestamp < entry.ttl:
                return entry.data
        return None

    def _set_cache(self, key: str, data: Any, ttl: float):
        """Set item in cache"""
        with self.cache_lock:
            self.cache[key] = CacheEntry(data=data, timestamp=time.time(), ttl=ttl)

    def _record_source_success(self, source_name: str, latency_ms: float):
        """Record successful request to a data source."""
        if source_name in self.source_stats:
            stats = self.source_stats[source_name]
            stats['success_count'] += 1
            stats['total_latency_ms'] += latency_ms
            stats['last_success'] = datetime.now().isoformat()

    def _record_source_failure(self, source_name: str):
        """Record failed request to a data source."""
        if source_name in self.source_stats:
            stats = self.source_stats[source_name]
            stats['failure_count'] += 1
            stats['last_failure'] = datetime.now().isoformat()

    def get_source_reliability(self) -> Dict[str, Dict]:
        """
        Get reliability statistics for all data sources.
        Returns success rate, avg latency, and circuit breaker status.
        """
        result = {}
        for source_name, stats in self.source_stats.items():
            total = stats['success_count'] + stats['failure_count']
            reliability = stats['success_count'] / total if total > 0 else 1.0
            avg_latency = stats['total_latency_ms'] / stats['success_count'] if stats['success_count'] > 0 else 0

            cb = self.circuit_breakers.get(source_name)
            cb_state = cb.state if cb else "N/A"

            result[source_name] = {
                'reliability': round(reliability, 3),
                'success_count': stats['success_count'],
                'failure_count': stats['failure_count'],
                'avg_latency_ms': round(avg_latency, 1),
                'last_success': stats['last_success'],
                'last_failure': stats['last_failure'],
                'circuit_breaker': cb_state,
                'healthy': cb_state != "OPEN" if cb_state != "N/A" else True
            }
        return result

    # Map futures symbols to their liquid ETF proxies for faster data
    FUTURES_TO_ETF = {
        "NQ": "QQQ", "ES": "SPY", "YM": "DIA", "RTY": "IWM",
        "CL": "USO", "GC": "GLD", "SI": "SLV", "ZB": "TLT",
    }

    def get_quote(self, symbol: str, allow_fallback: bool = None) -> Quote:
        """Get quote with failover - LIVE DATA PREFERRED"""
        symbol = symbol.upper()
        cache_key = self._get_cache_key("quote", symbol)
        use_fallback = not self.force_live if allow_fallback is None else allow_fallback

        # Check cache FIRST (before any network calls)
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for {symbol}")
            return cached

        # For futures symbols, use ETF proxy (much faster, always available)
        etf_proxy = self.FUTURES_TO_ETF.get(symbol)
        if etf_proxy:
            proxy_quote = self.get_quote(etf_proxy, allow_fallback=allow_fallback)
            if proxy_quote:
                import copy
                result = copy.copy(proxy_quote)
                result.symbol = symbol
                self._set_cache(cache_key, result, self.cache_ttl["quote"])
                return result

        # Try sources in order
        live_quote = None
        for source in self.sources:
            # Skip fallback if force_live mode and we haven't tried all live sources
            if source.name == "fallback" and not use_fallback:
                continue

            # Check circuit breaker - skip sources that are failing repeatedly
            cb = self.circuit_breakers.get(source.name)
            if cb and not cb.allow_request():
                logger.debug(f"[CIRCUIT BREAKER] Skipping {source.name} - circuit is OPEN")
                continue

            start_time = time.time()
            try:
                quote = source.get_quote(symbol)
                latency_ms = (time.time() - start_time) * 1000

                if quote:
                    # Validate data quality before accepting
                    is_valid, reason = validate_quote(quote)
                    if not is_valid:
                        logger.warning(f"[DATA QUALITY] {symbol} from {source.name} rejected: {reason}")
                        if cb:
                            cb.record_failure()  # Bad data counts as failure
                        self._record_source_failure(source.name)
                        continue  # Try next source
                    # Success - record it
                    if cb:
                        cb.record_success()
                    self._record_source_success(source.name, latency_ms)
                    logger.info(f"[LIVE] {symbol} from {source.name}: ${quote.price:.2f}")
                    self._set_cache(cache_key, quote, self.cache_ttl["quote"])
                    return quote
            except Exception as e:
                if cb:
                    cb.record_failure()
                self._record_source_failure(source.name)
                logger.warning(f"Source {source.name} failed for {symbol}: {e}")
                continue

        # If all live sources failed and force_live is on, use fallback as last resort
        if self.force_live:
            logger.warning(f"All live sources failed for {symbol}, using fallback")
            fallback = FallbackDataSource()
            return fallback.get_quote(symbol)

        raise RuntimeError(f"All data sources failed for {symbol}")

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get multiple quotes concurrently"""
        results = {}
        futures = {
            self.executor.submit(self.get_quote, sym): sym
            for sym in symbols
        }

        for future in futures:
            symbol = futures[future]
            try:
                results[symbol] = future.result(timeout=30)
            except Exception as e:
                logger.error(f"Failed to get quote for {symbol}: {e}")

        return results

    def get_historical(self, symbol: str, period: str = "1y", interval: str = "1d") -> List[OHLCV]:
        """Get historical data with failover"""
        symbol = symbol.upper()
        cache_key = self._get_cache_key("historical", symbol, period, interval)

        # Check cache
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Try sources in order
        for source in self.sources:
            try:
                data = source.get_historical(symbol, period, interval)
                if data:
                    self._set_cache(cache_key, data, self.cache_ttl["historical"])
                    return data
            except Exception as e:
                logger.warning(f"Source {source.name} failed for historical: {e}")
                continue

        return []

    def get_sectors(self) -> List[Dict]:
        """Get sector performance"""
        sector_etfs = {
            "Technology": "XLK",
            "Healthcare": "XLV",
            "Financials": "XLF",
            "Consumer Disc.": "XLY",
            "Communication": "XLC",
            "Industrials": "XLI",
            "Consumer Staples": "XLP",
            "Energy": "XLE",
            "Utilities": "XLU",
            "Real Estate": "XLRE",
            "Materials": "XLB",
        }

        results = []
        quotes = self.get_quotes(list(sector_etfs.values()))

        for name, etf in sector_etfs.items():
            quote = quotes.get(etf)
            if quote:
                results.append({
                    "name": name,
                    "etf": etf,
                    "price": quote.price,
                    "change": quote.change,
                    "change_pct": quote.change_pct,
                })

        return results

    def get_movers(self, universe: List[str] = None) -> Dict[str, List[Dict]]:
        """Get top gainers and losers"""
        if universe is None:
            # Use a focused list of liquid stocks for faster response
            universe = [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD",
                "INTC", "AVGO", "CRM", "PLTR", "JPM", "GS", "JNJ", "LLY",
                "WMT", "NFLX", "XOM", "CVX",
            ]

        quotes = self.get_quotes(universe)

        sorted_quotes = sorted(
            quotes.values(),
            key=lambda q: q.change_pct,
            reverse=True
        )

        gainers = [
            {"symbol": q.symbol, "price": q.price, "change_pct": q.change_pct, "volume": q.volume}
            for q in sorted_quotes[:5]
        ]

        losers = [
            {"symbol": q.symbol, "price": q.price, "change_pct": q.change_pct, "volume": q.volume}
            for q in sorted_quotes[-5:][::-1]
        ]

        return {"gainers": gainers, "losers": losers}

    def cleanup_cache(self, max_age: float = 3600):
        """Clean up old cache entries"""
        now = time.time()
        with self.cache_lock:
            keys_to_remove = [
                k for k, v in self.cache.items()
                if now - v.timestamp > max_age
            ]
            for k in keys_to_remove:
                del self.cache[k]

        # Also clean SQLite cache
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM cache WHERE timestamp < ?",
                    (now - max_age,)
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.warning(f"Failed to clean SQLite cache: {e}")


# Singleton instance
_data_service: Optional[DataService] = None

def get_data_service() -> DataService:
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service
