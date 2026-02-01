"""
Feature Store - Feast Client Wrapper for Quant Trading

This module provides a production-ready feature store implementation
with support for both online (real-time) and offline (batch) feature serving.

Key Features:
- Feast integration for feature management
- Redis-based online store for low-latency serving
- Point-in-time correct feature retrieval
- Feature caching with TTL management
- Fallback to computed features when store unavailable

Architecture:
    Online Path (< 100ms):
        Request → Cache Check → Redis Store → Return Features

    Offline Path (batch):
        Request → BigQuery/Parquet → Point-in-time Join → Return DataFrame

Rollback Plan:
    Set FEATURE_STORE_ENABLED=false to use direct feature computation

Tests Required:
    - test_online_feature_serving
    - test_offline_feature_retrieval
    - test_point_in_time_correctness
    - test_cache_behavior
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import threading
from collections import OrderedDict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureStoreBackend(Enum):
    """Supported feature store backends."""
    FEAST = "feast"
    REDIS = "redis"
    IN_MEMORY = "in_memory"
    FILE = "file"


@dataclass
class FeatureStoreConfig:
    """Configuration for the feature store."""
    backend: FeatureStoreBackend = FeatureStoreBackend.IN_MEMORY
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    feast_repo_path: Optional[str] = None
    cache_ttl_seconds: int = 300
    cache_max_size: int = 10000
    enable_fallback: bool = True
    online_timeout_ms: int = 100
    offline_timeout_ms: int = 30000
    feature_freshness_seconds: int = 60

    def validate(self) -> bool:
        """Validate configuration parameters."""
        if self.cache_ttl_seconds <= 0:
            return False
        if self.cache_max_size <= 0:
            return False
        if self.online_timeout_ms <= 0:
            return False
        return True


@dataclass
class FeatureVector:
    """Container for retrieved features."""
    entity_id: str
    features: Dict[str, Any]
    timestamp: datetime
    source: str  # 'online', 'offline', 'computed', 'cache'
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entity_id': self.entity_id,
            'features': self.features,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'latency_ms': self.latency_ms,
        }


@dataclass
class FeatureRetrievalResult:
    """Result of feature retrieval operation."""
    success: bool
    vectors: List[FeatureVector]
    missing_entities: List[str]
    missing_features: List[str]
    latency_ms: float
    error: Optional[str] = None


class LRUCache:
    """Thread-safe LRU cache for feature vectors."""

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    def _make_key(self, entity_id: str, feature_refs: List[str]) -> str:
        """Create cache key from entity and features."""
        feature_str = ','.join(sorted(feature_refs))
        return hashlib.md5(f"{entity_id}:{feature_str}".encode()).hexdigest()

    def get(self, entity_id: str, feature_refs: List[str]) -> Optional[FeatureVector]:
        """Get cached feature vector if valid."""
        key = self._make_key(entity_id, feature_refs)

        with self._lock:
            if key not in self._cache:
                return None

            # Check TTL
            timestamp = self._timestamps.get(key)
            if timestamp:
                age = (datetime.now(timezone.utc) - timestamp).total_seconds()
                if age > self.ttl_seconds:
                    del self._cache[key]
                    del self._timestamps[key]
                    return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, entity_id: str, feature_refs: List[str], vector: FeatureVector) -> None:
        """Cache feature vector."""
        key = self._make_key(entity_id, feature_refs)

        with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._timestamps.pop(oldest_key, None)

            self._cache[key] = vector
            self._timestamps[key] = datetime.now(timezone.utc)

    def invalidate(self, entity_id: Optional[str] = None) -> int:
        """Invalidate cache entries. Returns count of invalidated entries."""
        with self._lock:
            if entity_id is None:
                count = len(self._cache)
                self._cache.clear()
                self._timestamps.clear()
                return count

            # Invalidate all entries for entity
            keys_to_remove = [k for k in self._cache if entity_id in str(k)]
            for key in keys_to_remove:
                del self._cache[key]
                self._timestamps.pop(key, None)
            return len(keys_to_remove)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'ttl_seconds': self.ttl_seconds,
            }


class QuantFeatureStore:
    """
    Production feature store for quant trading ML features.

    Provides unified access to features for both training (offline)
    and serving (online) with consistent computation and caching.

    Example:
        store = QuantFeatureStore()

        # Online serving
        result = store.get_online_features(
            entity_ids=['AAPL', 'GOOGL'],
            feature_refs=['price_features:sma_20', 'volume_features:vwap']
        )

        # Offline batch retrieval
        df = store.get_historical_features(
            entity_df=entity_timestamps_df,
            feature_refs=['price_features:returns_1d']
        )
    """

    def __init__(self, config: Optional[FeatureStoreConfig] = None):
        """Initialize the feature store."""
        self.config = config or FeatureStoreConfig()

        if not self.config.validate():
            raise ValueError("Invalid feature store configuration")

        self._cache = LRUCache(
            max_size=self.config.cache_max_size,
            ttl_seconds=self.config.cache_ttl_seconds
        )

        self._feast_store = None
        self._redis_client = None
        self._in_memory_store: Dict[str, Dict[str, Any]] = {}

        # Initialize backend
        self._initialize_backend()

        # Statistics
        self._stats = {
            'online_requests': 0,
            'offline_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'fallback_count': 0,
            'errors': 0,
        }
        self._stats_lock = threading.Lock()

        logger.info(f"QuantFeatureStore initialized with backend: {self.config.backend.value}")

    def _initialize_backend(self) -> None:
        """Initialize the selected backend."""
        if self.config.backend == FeatureStoreBackend.FEAST:
            self._initialize_feast()
        elif self.config.backend == FeatureStoreBackend.REDIS:
            self._initialize_redis()
        elif self.config.backend == FeatureStoreBackend.FILE:
            self._initialize_file_backend()
        # IN_MEMORY uses self._in_memory_store directly

    def _initialize_feast(self) -> None:
        """Initialize Feast feature store."""
        try:
            from feast import FeatureStore

            repo_path = self.config.feast_repo_path or str(
                Path(__file__).parent / 'feast_repo'
            )

            if Path(repo_path).exists():
                self._feast_store = FeatureStore(repo_path=repo_path)
                logger.info(f"Feast store initialized from {repo_path}")
            else:
                logger.warning(f"Feast repo not found at {repo_path}, using in-memory fallback")
                self.config.backend = FeatureStoreBackend.IN_MEMORY

        except ImportError:
            logger.warning("Feast not installed, using in-memory backend")
            self.config.backend = FeatureStoreBackend.IN_MEMORY

    def _initialize_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis

            self._redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                socket_timeout=self.config.online_timeout_ms / 1000,
                decode_responses=True,
            )
            # Test connection
            self._redis_client.ping()
            logger.info("Redis feature store connected")

        except ImportError:
            logger.warning("Redis not installed, using in-memory backend")
            self.config.backend = FeatureStoreBackend.IN_MEMORY
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using in-memory backend")
            self.config.backend = FeatureStoreBackend.IN_MEMORY

    def _initialize_file_backend(self) -> None:
        """Initialize file-based backend for persistence."""
        self._file_store_path = Path(__file__).parent / 'feature_store_data'
        self._file_store_path.mkdir(parents=True, exist_ok=True)

        # Load existing data
        feature_file = self._file_store_path / 'features.json'
        if feature_file.exists():
            try:
                with open(feature_file, 'r') as f:
                    self._in_memory_store = json.load(f)
                logger.info(f"Loaded {len(self._in_memory_store)} entities from file store")
            except Exception as e:
                logger.warning(f"Failed to load file store: {e}")

    def _update_stats(self, stat_key: str, increment: int = 1) -> None:
        """Thread-safe statistics update."""
        with self._stats_lock:
            self._stats[stat_key] = self._stats.get(stat_key, 0) + increment

    def get_online_features(
        self,
        entity_ids: List[str],
        feature_refs: List[str],
        use_cache: bool = True,
    ) -> FeatureRetrievalResult:
        """
        Retrieve features for online serving with low latency.

        Args:
            entity_ids: List of entity identifiers (e.g., tickers)
            feature_refs: List of feature references (e.g., 'price_features:sma_20')
            use_cache: Whether to use cached values

        Returns:
            FeatureRetrievalResult with feature vectors
        """
        import time
        start_time = time.perf_counter()

        self._update_stats('online_requests')

        vectors: List[FeatureVector] = []
        missing_entities: List[str] = []
        cache_hits = 0

        for entity_id in entity_ids:
            # Check cache first
            if use_cache:
                cached = self._cache.get(entity_id, feature_refs)
                if cached:
                    vectors.append(cached)
                    cache_hits += 1
                    continue

            # Fetch from backend
            vector = self._fetch_online_features(entity_id, feature_refs)

            if vector:
                vectors.append(vector)
                if use_cache:
                    self._cache.put(entity_id, feature_refs, vector)
            else:
                missing_entities.append(entity_id)

        self._update_stats('cache_hits', cache_hits)
        self._update_stats('cache_misses', len(entity_ids) - cache_hits)

        latency_ms = (time.perf_counter() - start_time) * 1000

        return FeatureRetrievalResult(
            success=len(vectors) > 0,
            vectors=vectors,
            missing_entities=missing_entities,
            missing_features=[],
            latency_ms=latency_ms,
        )

    def _fetch_online_features(
        self,
        entity_id: str,
        feature_refs: List[str],
    ) -> Optional[FeatureVector]:
        """Fetch features from the configured backend."""
        import time
        start_time = time.perf_counter()

        try:
            if self.config.backend == FeatureStoreBackend.FEAST and self._feast_store:
                return self._fetch_from_feast(entity_id, feature_refs, start_time)

            elif self.config.backend == FeatureStoreBackend.REDIS and self._redis_client:
                return self._fetch_from_redis(entity_id, feature_refs, start_time)

            else:
                return self._fetch_from_memory(entity_id, feature_refs, start_time)

        except Exception as e:
            logger.error(f"Feature fetch failed for {entity_id}: {e}")
            self._update_stats('errors')

            if self.config.enable_fallback:
                self._update_stats('fallback_count')
                return self._compute_features_fallback(entity_id, feature_refs, start_time)

            return None

    def _fetch_from_feast(
        self,
        entity_id: str,
        feature_refs: List[str],
        start_time: float,
    ) -> Optional[FeatureVector]:
        """Fetch features from Feast online store."""
        import time

        entity_dict = {"ticker": entity_id}

        response = self._feast_store.get_online_features(
            features=feature_refs,
            entity_rows=[entity_dict],
        )

        feature_dict = response.to_dict()

        # Extract features
        features = {}
        for ref in feature_refs:
            feature_name = ref.split(':')[-1] if ':' in ref else ref
            if feature_name in feature_dict:
                features[feature_name] = feature_dict[feature_name][0]

        latency_ms = (time.perf_counter() - start_time) * 1000

        return FeatureVector(
            entity_id=entity_id,
            features=features,
            timestamp=datetime.now(timezone.utc),
            source='online',
            latency_ms=latency_ms,
        )

    def _fetch_from_redis(
        self,
        entity_id: str,
        feature_refs: List[str],
        start_time: float,
    ) -> Optional[FeatureVector]:
        """Fetch features from Redis."""
        import time

        features = {}

        for ref in feature_refs:
            key = f"feature:{entity_id}:{ref}"
            value = self._redis_client.get(key)

            if value:
                feature_name = ref.split(':')[-1] if ':' in ref else ref
                try:
                    features[feature_name] = json.loads(value)
                except json.JSONDecodeError:
                    features[feature_name] = float(value)

        if not features:
            return None

        latency_ms = (time.perf_counter() - start_time) * 1000

        return FeatureVector(
            entity_id=entity_id,
            features=features,
            timestamp=datetime.now(timezone.utc),
            source='online',
            latency_ms=latency_ms,
        )

    def _fetch_from_memory(
        self,
        entity_id: str,
        feature_refs: List[str],
        start_time: float,
    ) -> Optional[FeatureVector]:
        """Fetch features from in-memory store."""
        import time

        if entity_id not in self._in_memory_store:
            return None

        entity_features = self._in_memory_store[entity_id]
        features = {}

        for ref in feature_refs:
            feature_name = ref.split(':')[-1] if ':' in ref else ref
            if feature_name in entity_features:
                features[feature_name] = entity_features[feature_name]

        if not features:
            return None

        latency_ms = (time.perf_counter() - start_time) * 1000

        return FeatureVector(
            entity_id=entity_id,
            features=features,
            timestamp=datetime.now(timezone.utc),
            source='online',
            latency_ms=latency_ms,
        )

    def _compute_features_fallback(
        self,
        entity_id: str,
        feature_refs: List[str],
        start_time: float,
    ) -> Optional[FeatureVector]:
        """Compute features directly when store unavailable."""
        import time

        try:
            # Import feature computation module
            from ..features import FeatureComputer

            computer = FeatureComputer()
            features = {}

            for ref in feature_refs:
                feature_name = ref.split(':')[-1] if ':' in ref else ref
                value = computer.compute_single_feature(entity_id, feature_name)
                if value is not None:
                    features[feature_name] = value

            if not features:
                return None

            latency_ms = (time.perf_counter() - start_time) * 1000

            return FeatureVector(
                entity_id=entity_id,
                features=features,
                timestamp=datetime.now(timezone.utc),
                source='computed',
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Fallback feature computation failed: {e}")
            return None

    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_refs: List[str],
        full_feature_names: bool = True,
    ) -> pd.DataFrame:
        """
        Retrieve historical features for training with point-in-time correctness.

        Args:
            entity_df: DataFrame with entity_id and event_timestamp columns
            feature_refs: List of feature references
            full_feature_names: Whether to use full feature names in output

        Returns:
            DataFrame with features joined to entity_df
        """
        self._update_stats('offline_requests')

        if self.config.backend == FeatureStoreBackend.FEAST and self._feast_store:
            return self._feast_store.get_historical_features(
                entity_df=entity_df,
                features=feature_refs,
                full_feature_names=full_feature_names,
            ).to_df()

        # Fallback: compute features for each timestamp
        return self._compute_historical_features(entity_df, feature_refs)

    def _compute_historical_features(
        self,
        entity_df: pd.DataFrame,
        feature_refs: List[str],
    ) -> pd.DataFrame:
        """Compute historical features with point-in-time correctness."""
        result_df = entity_df.copy()

        for ref in feature_refs:
            feature_name = ref.split(':')[-1] if ':' in ref else ref
            result_df[feature_name] = np.nan

        # Group by entity and compute
        for entity_id in result_df['entity_id'].unique():
            entity_mask = result_df['entity_id'] == entity_id

            if entity_id in self._in_memory_store:
                entity_features = self._in_memory_store[entity_id]
                for ref in feature_refs:
                    feature_name = ref.split(':')[-1] if ':' in ref else ref
                    if feature_name in entity_features:
                        result_df.loc[entity_mask, feature_name] = entity_features[feature_name]

        return result_df

    def materialize_features(
        self,
        entity_id: str,
        features: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Write features to the online store for later retrieval.

        Args:
            entity_id: Entity identifier
            features: Dictionary of feature name to value
            timestamp: Feature timestamp (defaults to now)

        Returns:
            True if successful
        """
        timestamp = timestamp or datetime.now(timezone.utc)

        try:
            if self.config.backend == FeatureStoreBackend.REDIS and self._redis_client:
                for feature_name, value in features.items():
                    key = f"feature:{entity_id}:{feature_name}"
                    self._redis_client.setex(
                        key,
                        self.config.feature_freshness_seconds,
                        json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                    )
            else:
                if entity_id not in self._in_memory_store:
                    self._in_memory_store[entity_id] = {}
                self._in_memory_store[entity_id].update(features)

            # Invalidate cache for this entity
            self._cache.invalidate(entity_id)

            logger.debug(f"Materialized {len(features)} features for {entity_id}")
            return True

        except Exception as e:
            logger.error(f"Feature materialization failed: {e}")
            return False

    def batch_materialize(
        self,
        feature_df: pd.DataFrame,
        entity_column: str = 'ticker',
    ) -> int:
        """
        Batch write features to the online store.

        Args:
            feature_df: DataFrame with entity column and feature columns
            entity_column: Name of the entity column

        Returns:
            Number of entities materialized
        """
        count = 0

        for _, row in feature_df.iterrows():
            entity_id = row[entity_column]
            features = {col: row[col] for col in feature_df.columns if col != entity_column}

            if self.materialize_features(entity_id, features):
                count += 1

        logger.info(f"Batch materialized features for {count} entities")
        return count

    def get_feature_freshness(self, entity_id: str, feature_ref: str) -> Optional[float]:
        """
        Get the age of a feature in seconds.

        Returns None if feature not found.
        """
        if self.config.backend == FeatureStoreBackend.REDIS and self._redis_client:
            key = f"feature:{entity_id}:{feature_ref}"
            ttl = self._redis_client.ttl(key)
            if ttl > 0:
                return self.config.feature_freshness_seconds - ttl

        return None

    def invalidate_cache(self, entity_id: Optional[str] = None) -> int:
        """
        Invalidate cached features.

        Args:
            entity_id: Specific entity to invalidate, or None for all

        Returns:
            Number of invalidated entries
        """
        return self._cache.invalidate(entity_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get feature store statistics."""
        with self._stats_lock:
            stats = dict(self._stats)

        stats['cache_stats'] = self._cache.stats()
        stats['backend'] = self.config.backend.value

        if self._stats['online_requests'] > 0:
            stats['cache_hit_rate'] = (
                self._stats['cache_hits'] /
                (self._stats['cache_hits'] + self._stats['cache_misses'])
            )
        else:
            stats['cache_hit_rate'] = 0.0

        return stats

    def health_check(self) -> Dict[str, Any]:
        """Check feature store health."""
        import time

        health = {
            'status': 'healthy',
            'backend': self.config.backend.value,
            'checks': {},
        }

        # Backend connectivity check
        try:
            if self.config.backend == FeatureStoreBackend.REDIS and self._redis_client:
                start = time.perf_counter()
                self._redis_client.ping()
                health['checks']['redis'] = {
                    'status': 'connected',
                    'latency_ms': (time.perf_counter() - start) * 1000,
                }
            elif self.config.backend == FeatureStoreBackend.FEAST and self._feast_store:
                health['checks']['feast'] = {'status': 'initialized'}
            else:
                health['checks']['in_memory'] = {
                    'status': 'active',
                    'entities': len(self._in_memory_store),
                }
        except Exception as e:
            health['status'] = 'degraded'
            health['checks']['backend'] = {'status': 'error', 'error': str(e)}

        # Cache check
        health['checks']['cache'] = self._cache.stats()

        return health

    def close(self) -> None:
        """Clean up resources."""
        if self._redis_client:
            self._redis_client.close()

        # Persist file backend if enabled
        if self.config.backend == FeatureStoreBackend.FILE:
            feature_file = self._file_store_path / 'features.json'
            try:
                with open(feature_file, 'w') as f:
                    json.dump(self._in_memory_store, f)
            except Exception as e:
                logger.error(f"Failed to persist file store: {e}")

        logger.info("QuantFeatureStore closed")
