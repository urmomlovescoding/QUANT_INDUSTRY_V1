"""
Market Data Contract
====================
Canonical interface for all market data operations.

ALL market data access MUST go through implementations of this contract.
Direct API calls to Alpaca/Yahoo/etc are FORBIDDEN outside adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class DataSource(Enum):
    """Data source identifiers."""
    ALPACA = "alpaca"
    TRADIER = "tradier"
    YAHOO = "yahoo"
    POLYGON = "polygon"
    IBKR = "ibkr"
    CACHE = "cache"
    FALLBACK = "fallback"
    SIMULATION = "simulation"


class DataQuality(Enum):
    """Data quality levels."""
    LIVE = "live"           # Real-time, verified
    DELAYED = "delayed"     # 15-min delayed
    CACHED = "cached"       # From cache, within TTL
    STALE = "stale"         # Beyond TTL
    SIMULATED = "simulated" # Synthetic/generated


@dataclass
class Quote:
    """
    Canonical quote structure.

    This is the ONLY quote format used throughout the application.
    """
    symbol: str
    price: float
    bid: float
    ask: float
    bid_size: int = 0
    ask_size: int = 0
    volume: int = 0

    # Change tracking
    change: float = 0.0
    change_pct: float = 0.0

    # Provenance (MANDATORY)
    source: DataSource = DataSource.FALLBACK
    quality: DataQuality = DataQuality.STALE
    timestamp: datetime = field(default_factory=datetime.now)
    received_at: datetime = field(default_factory=datetime.now)

    # Staleness
    @property
    def age_seconds(self) -> float:
        return (datetime.now() - self.timestamp).total_seconds()

    @property
    def is_stale(self) -> bool:
        return self.age_seconds > 60  # 60 seconds = stale

    @property
    def is_live(self) -> bool:
        return self.quality == DataQuality.LIVE and not self.is_stale

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "volume": self.volume,
            "change": self.change,
            "change_pct": self.change_pct,
            "source": self.source.value,
            "quality": self.quality.value,
            "timestamp": self.timestamp.isoformat(),
            "age_seconds": self.age_seconds,
            "is_stale": self.is_stale,
            "is_live": self.is_live,
        }


@dataclass
class Bar:
    """OHLCV bar data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    # Provenance
    source: DataSource = DataSource.FALLBACK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "source": self.source.value,
        }


@dataclass
class MarketStatus:
    """Market session status."""
    is_open: bool
    session: str  # "pre", "regular", "post", "closed"
    next_open: Optional[datetime] = None
    next_close: Optional[datetime] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_open": self.is_open,
            "session": self.session,
            "next_open": self.next_open.isoformat() if self.next_open else None,
            "next_close": self.next_close.isoformat() if self.next_close else None,
            "reason": self.reason,
        }


class MarketDataContract(ABC):
    """
    Market Data Service Contract.

    All implementations MUST:
    1. Return Quote/Bar objects with full provenance
    2. Never return data without source/quality fields
    3. Mark simulated data clearly
    4. Respect staleness thresholds
    """

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """
        Get current quote for symbol.

        MUST return Quote with:
        - source: Where data came from
        - quality: Live/delayed/cached/stale
        - timestamp: When data was generated at source
        """
        pass

    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get quotes for multiple symbols."""
        pass

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        timeframe: str,  # "1m", "5m", "1h", "1d"
        limit: int = 100
    ) -> List[Bar]:
        """Get historical bars."""
        pass

    @abstractmethod
    def get_market_status(self) -> MarketStatus:
        """Get current market session status."""
        pass

    @abstractmethod
    def subscribe(self, symbols: List[str], callback) -> str:
        """
        Subscribe to real-time updates.

        Returns subscription ID for unsubscribe.
        """
        pass

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from updates."""
        pass

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """
        Get data service health.

        MUST return:
        - active_sources: List of working data sources
        - failed_sources: List of failed sources
        - cache_stats: Cache hit/miss rates
        - latency_ms: Average latency per source
        """
        pass
