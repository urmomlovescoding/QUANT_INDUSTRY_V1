"""
QUANT_INDUSTRY_V1 Data Cache

In-memory and persistent cache for market data.

Rollback Plan: Delete this file
Tests Required: TTL expiration, memory limits, persistence
Failure Modes: Cache miss -> fetch fresh data
"""

import time
import threading
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import pickle

from .fetcher import MarketData, Bar, Timeframe, DataSource

logger = logging.getLogger(__name__)


# =============================================================================
# CACHE ENTRY
# =============================================================================

@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    key: str
    data: MarketData
    created_at: float  # Unix timestamp
    expires_at: float  # Unix timestamp
    hits: int = 0
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age in seconds."""
        return time.time() - self.created_at

    @property
    def ttl_remaining(self) -> float:
        """Get remaining TTL in seconds."""
        return max(0, self.expires_at - time.time())


# =============================================================================
# CACHE STATISTICS
# =============================================================================

@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    entries: int = 0
    size_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'expirations': self.expirations,
            'entries': self.entries,
            'size_bytes': self.size_bytes,
            'hit_rate': self.hit_rate,
        }


# =============================================================================
# IN-MEMORY CACHE
# =============================================================================

class MemoryCache:
    """
    Thread-safe in-memory cache with TTL and LRU eviction.

    Features:
    - Per-key TTL support
    - LRU eviction when max size exceeded
    - Memory size tracking
    - Statistics
    """

    def __init__(
        self,
        default_ttl: float = 300.0,  # 5 minutes
        max_entries: int = 1000,
        max_size_mb: float = 100.0,
    ):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)

        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = CacheStats()

        # Start cleanup thread
        self._cleanup_interval = 60.0  # seconds
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _make_key(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime
    ) -> str:
        """Generate cache key."""
        key_parts = [
            symbol,
            timeframe.value,
            start.isoformat(),
            end.isoformat(),
        ]
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime
    ) -> Optional[MarketData]:
        """
        Get data from cache.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime

        Returns:
            MarketData if found and not expired, None otherwise
        """
        key = self._make_key(symbol, timeframe, start, end)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                self._stats.expirations += 1
                self._update_stats()
                return None

            # Update hits
            entry.hits += 1
            self._stats.hits += 1

            logger.debug(f"Cache hit: {symbol}/{timeframe.value}")
            return entry.data

    def set(
        self,
        data: MarketData,
        ttl: float = None
    ) -> None:
        """
        Store data in cache.

        Args:
            data: MarketData to cache
            ttl: Time-to-live in seconds (default: class default)
        """
        if not data.bars:
            return

        ttl = ttl if ttl is not None else self.default_ttl

        # Calculate time range from bars
        start = data.bars[0].timestamp
        end = data.bars[-1].timestamp

        key = self._make_key(data.symbol, data.timeframe, start, end)

        # Estimate size
        size_bytes = len(data.bars) * 100  # Rough estimate

        entry = CacheEntry(
            key=key,
            data=data,
            created_at=time.time(),
            expires_at=time.time() + ttl,
            size_bytes=size_bytes,
        )

        with self._lock:
            # Evict if necessary
            self._ensure_capacity(size_bytes)

            self._cache[key] = entry
            self._update_stats()

        logger.debug(f"Cache set: {data.symbol}/{data.timeframe.value}, TTL={ttl}s")

    def invalidate(self, symbol: str = None, timeframe: Timeframe = None) -> int:
        """
        Invalidate cache entries.

        Args:
            symbol: Invalidate entries for this symbol (None = all)
            timeframe: Invalidate entries for this timeframe (None = all)

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            if symbol is None and timeframe is None:
                count = len(self._cache)
                self._cache.clear()
                self._update_stats()
                return count

            keys_to_remove = []
            for key, entry in self._cache.items():
                if symbol and entry.data.symbol != symbol:
                    continue
                if timeframe and entry.data.timeframe != timeframe:
                    continue
                keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._cache[key]

            self._update_stats()
            return len(keys_to_remove)

    def _ensure_capacity(self, needed_bytes: int) -> None:
        """Ensure cache has capacity for new entry."""
        # Check entry count
        while len(self._cache) >= self.max_entries:
            self._evict_lru()

        # Check size
        while self._stats.size_bytes + needed_bytes > self.max_size_bytes and self._cache:
            self._evict_lru()

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find LRU (oldest creation time with fewest hits)
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].hits, -self._cache[k].created_at)
        )

        del self._cache[lru_key]
        self._stats.evictions += 1
        self._update_stats()

    def _cleanup_loop(self) -> None:
        """Background cleanup of expired entries."""
        while self._running:
            time.sleep(self._cleanup_interval)
            self._cleanup_expired()

    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]

            for key in expired_keys:
                del self._cache[key]
                self._stats.expirations += 1

            if expired_keys:
                self._update_stats()
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _update_stats(self) -> None:
        """Update cache statistics."""
        self._stats.entries = len(self._cache)
        self._stats.size_bytes = sum(e.size_bytes for e in self._cache.values())

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expirations=self._stats.expirations,
                entries=self._stats.entries,
                size_bytes=self._stats.size_bytes,
            )

    def stop(self) -> None:
        """Stop background cleanup."""
        self._running = False


# =============================================================================
# DISK CACHE
# =============================================================================

class DiskCache:
    """
    Persistent disk-based cache.

    For longer-term caching of historical data.
    """

    def __init__(self, cache_dir: str = None):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / "QUANT_INDUSTRY_V1" / "cache"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _make_path(self, symbol: str, timeframe: Timeframe) -> Path:
        """Generate cache file path."""
        return self.cache_dir / f"{symbol}_{timeframe.value}.cache"

    def get(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime
    ) -> Optional[MarketData]:
        """Get data from disk cache."""
        path = self._make_path(symbol, timeframe)

        if not path.exists():
            return None

        try:
            with self._lock:
                with open(path, 'rb') as f:
                    cached_data: MarketData = pickle.load(f)

            # Check if cached data covers requested range
            if not cached_data.bars:
                return None

            cached_start = cached_data.bars[0].timestamp
            cached_end = cached_data.bars[-1].timestamp

            # Need to handle timezone-naive datetimes
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if cached_start <= start and cached_end >= end:
                # Filter to requested range
                filtered_bars = [
                    bar for bar in cached_data.bars
                    if start <= bar.timestamp <= end
                ]

                if filtered_bars:
                    return MarketData(
                        symbol=symbol,
                        timeframe=timeframe,
                        bars=filtered_bars,
                        source=DataSource.CACHE,
                        fetched_at=cached_data.fetched_at,
                        quality_score=cached_data.quality_score,
                    )

            return None

        except Exception as e:
            logger.warning(f"Disk cache read error: {e}")
            return None

    def set(self, data: MarketData) -> None:
        """Store data in disk cache."""
        if not data.bars:
            return

        path = self._make_path(data.symbol, data.timeframe)

        try:
            # Merge with existing data
            existing = self._read_raw(path)
            if existing:
                data = self._merge_data(existing, data)

            with self._lock:
                with open(path, 'wb') as f:
                    pickle.dump(data, f)

            logger.debug(f"Disk cache set: {data.symbol}/{data.timeframe.value}")

        except Exception as e:
            logger.warning(f"Disk cache write error: {e}")

    def _read_raw(self, path: Path) -> Optional[MarketData]:
        """Read raw data from disk."""
        if not path.exists():
            return None

        try:
            with open(path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return None

    def _merge_data(self, existing: MarketData, new: MarketData) -> MarketData:
        """Merge existing and new data."""
        # Create timestamp -> bar mapping
        bars_map = {bar.timestamp: bar for bar in existing.bars}

        # Add/update with new bars
        for bar in new.bars:
            bars_map[bar.timestamp] = bar

        # Sort by timestamp
        merged_bars = sorted(bars_map.values(), key=lambda b: b.timestamp)

        return MarketData(
            symbol=new.symbol,
            timeframe=new.timeframe,
            bars=merged_bars,
            source=new.source,
            fetched_at=new.fetched_at,
            quality_score=min(existing.quality_score, new.quality_score),
        )

    def invalidate(self, symbol: str = None) -> int:
        """Invalidate disk cache entries."""
        count = 0

        with self._lock:
            if symbol:
                for path in self.cache_dir.glob(f"{symbol}_*.cache"):
                    path.unlink()
                    count += 1
            else:
                for path in self.cache_dir.glob("*.cache"):
                    path.unlink()
                    count += 1

        return count


# =============================================================================
# COMBINED CACHE
# =============================================================================

class DataCache:
    """
    Combined memory and disk cache.

    - Memory cache for recent data (fast access)
    - Disk cache for historical data (persistence)
    """

    def __init__(
        self,
        memory_ttl: float = 300.0,
        memory_max_entries: int = 1000,
        memory_max_mb: float = 100.0,
        disk_enabled: bool = True,
        disk_dir: str = None,
    ):
        self.memory = MemoryCache(
            default_ttl=memory_ttl,
            max_entries=memory_max_entries,
            max_size_mb=memory_max_mb,
        )

        self.disk_enabled = disk_enabled
        if disk_enabled:
            self.disk = DiskCache(cache_dir=disk_dir)
        else:
            self.disk = None

    def get(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime
    ) -> Optional[MarketData]:
        """
        Get data from cache (memory first, then disk).

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime

        Returns:
            MarketData if found, None otherwise
        """
        # Try memory first
        data = self.memory.get(symbol, timeframe, start, end)
        if data is not None:
            return data

        # Try disk
        if self.disk_enabled and self.disk:
            data = self.disk.get(symbol, timeframe, start, end)
            if data is not None:
                # Promote to memory cache
                self.memory.set(data)
                return data

        return None

    def set(self, data: MarketData, persist: bool = True) -> None:
        """
        Store data in cache.

        Args:
            data: MarketData to cache
            persist: Whether to also store on disk
        """
        # Always store in memory
        self.memory.set(data)

        # Optionally persist
        if persist and self.disk_enabled and self.disk:
            self.disk.set(data)

    def invalidate(self, symbol: str = None, timeframe: Timeframe = None) -> int:
        """Invalidate cache entries."""
        memory_count = self.memory.invalidate(symbol, timeframe)
        disk_count = 0

        if self.disk_enabled and self.disk:
            disk_count = self.disk.invalidate(symbol)

        return memory_count + disk_count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'memory': self.memory.get_stats().to_dict(),
            'disk_enabled': self.disk_enabled,
        }

    def stop(self) -> None:
        """Stop cache (cleanup threads)."""
        self.memory.stop()
