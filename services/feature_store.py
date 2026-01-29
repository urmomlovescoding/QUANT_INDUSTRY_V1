"""
QUANT_INDUSTRY_V1 Feature Store

Feast-inspired feature management for ML trading systems:
- Feature registration and versioning
- Point-in-time correct feature retrieval
- Online/offline feature serving
- Feature freshness tracking
- Feature lineage and metadata

Rollback Plan: Delete this file
Tests Required: Feature retrieval, TTL, point-in-time correctness
Failure Modes: Return stale features with warning, fallback to computed
"""

import time
import logging
import threading
import hashlib
import pickle
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE TYPES
# =============================================================================

class FeatureValueType(Enum):
    """Supported feature value types."""
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    ARRAY = "array"
    EMBEDDING = "embedding"


class FeatureStatus(Enum):
    """Feature availability status."""
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    COMPUTED = "computed"


@dataclass
class FeatureDefinition:
    """Feature metadata and computation spec."""
    name: str
    value_type: FeatureValueType
    description: str = ""
    entity: str = "symbol"  # Entity this feature belongs to (symbol, portfolio, etc.)
    ttl_seconds: int = 300  # Time-to-live for online features
    tags: List[str] = field(default_factory=list)
    owner: str = ""
    compute_fn: Optional[Callable] = None  # Function to compute feature on-demand
    dependencies: List[str] = field(default_factory=list)  # Other features this depends on
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __hash__(self):
        return hash(self.name)


@dataclass
class FeatureValue:
    """Single feature value with metadata."""
    name: str
    value: Any
    timestamp: datetime
    entity_key: str  # e.g., "AAPL" for symbol entity
    status: FeatureStatus = FeatureStatus.FRESH
    source: str = "online"
    latency_ms: float = 0.0

    @property
    def age_seconds(self) -> float:
        """Get age of feature value in seconds."""
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()


@dataclass 
class FeatureVector:
    """Collection of features for an entity at a point in time."""
    entity_key: str
    timestamp: datetime
    features: Dict[str, FeatureValue]
    request_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary of feature name -> value."""
        return {name: fv.value for name, fv in self.features.items()}

    def to_array(self, feature_names: List[str]) -> np.ndarray:
        """Convert to numpy array in specified feature order."""
        return np.array([self.features[name].value for name in feature_names])

    @property
    def freshness_ratio(self) -> float:
        """Ratio of fresh features."""
        if not self.features:
            return 0.0
        fresh = sum(1 for fv in self.features.values() if fv.status == FeatureStatus.FRESH)
        return fresh / len(self.features)


# =============================================================================
# ONLINE FEATURE STORE
# =============================================================================

class OnlineStore(ABC):
    """Abstract base for online feature stores."""

    @abstractmethod
    def get(self, entity_key: str, feature_names: List[str]) -> Dict[str, FeatureValue]:
        """Get features for entity."""
        pass

    @abstractmethod
    def put(self, entity_key: str, features: Dict[str, Any], timestamp: datetime = None) -> None:
        """Store features for entity."""
        pass

    @abstractmethod
    def delete(self, entity_key: str, feature_names: List[str] = None) -> None:
        """Delete features for entity."""
        pass


class InMemoryOnlineStore(OnlineStore):
    """In-memory online store for low-latency feature serving."""

    def __init__(self, max_entities: int = 10000):
        self.max_entities = max_entities
        self._store: Dict[str, Dict[str, FeatureValue]] = defaultdict(dict)
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    def get(self, entity_key: str, feature_names: List[str]) -> Dict[str, FeatureValue]:
        """Get features with sub-millisecond latency."""
        start = time.perf_counter()
        result = {}
        
        with self._lock:
            entity_features = self._store.get(entity_key, {})
            self._access_times[entity_key] = datetime.now(timezone.utc)
            
            for name in feature_names:
                if name in entity_features:
                    fv = entity_features[name]
                    fv.latency_ms = (time.perf_counter() - start) * 1000
                    result[name] = fv

        return result

    def put(self, entity_key: str, features: Dict[str, Any], timestamp: datetime = None) -> None:
        """Store features for entity."""
        timestamp = timestamp or datetime.now(timezone.utc)
        
        with self._lock:
            # Evict if at capacity
            if len(self._store) >= self.max_entities and entity_key not in self._store:
                self._evict_lru()

            for name, value in features.items():
                self._store[entity_key][name] = FeatureValue(
                    name=name,
                    value=value,
                    timestamp=timestamp,
                    entity_key=entity_key,
                    source="online"
                )
            self._access_times[entity_key] = datetime.now(timezone.utc)

    def delete(self, entity_key: str, feature_names: List[str] = None) -> None:
        """Delete features for entity."""
        with self._lock:
            if entity_key in self._store:
                if feature_names:
                    for name in feature_names:
                        self._store[entity_key].pop(name, None)
                else:
                    del self._store[entity_key]
                    self._access_times.pop(entity_key, None)

    def _evict_lru(self) -> None:
        """Evict least recently used entity."""
        if not self._access_times:
            return
        oldest = min(self._access_times, key=self._access_times.get)
        del self._store[oldest]
        del self._access_times[oldest]
        logger.debug(f"Evicted entity {oldest} from online store")


# =============================================================================
# OFFLINE FEATURE STORE
# =============================================================================

class OfflineStore(ABC):
    """Abstract base for offline/historical feature stores."""

    @abstractmethod
    def get_historical(
        self,
        entity_keys: List[str],
        feature_names: List[str],
        start: datetime,
        end: datetime,
    ) -> Dict[str, List[FeatureValue]]:
        """Get historical features for training."""
        pass

    @abstractmethod
    def write_batch(self, features: List[FeatureValue]) -> int:
        """Write batch of features. Returns count written."""
        pass


class InMemoryOfflineStore(OfflineStore):
    """In-memory offline store for historical features."""

    def __init__(self, max_history_days: int = 30):
        self.max_history_days = max_history_days
        self._store: Dict[str, Dict[str, List[FeatureValue]]] = defaultdict(lambda: defaultdict(list))
        self._lock = threading.RLock()

    def get_historical(
        self,
        entity_keys: List[str],
        feature_names: List[str],
        start: datetime,
        end: datetime,
    ) -> Dict[str, List[FeatureValue]]:
        """Get historical features within time range."""
        result = {}
        
        with self._lock:
            for entity_key in entity_keys:
                entity_features = self._store.get(entity_key, {})
                key = f"{entity_key}"
                result[key] = []
                
                for name in feature_names:
                    if name in entity_features:
                        for fv in entity_features[name]:
                            if start <= fv.timestamp <= end:
                                result[key].append(fv)

        return result

    def write_batch(self, features: List[FeatureValue]) -> int:
        """Write batch of features."""
        count = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_history_days)
        
        with self._lock:
            for fv in features:
                if fv.timestamp >= cutoff:
                    self._store[fv.entity_key][fv.name].append(fv)
                    count += 1
                    
            # Cleanup old entries
            self._cleanup_old_entries(cutoff)
                
        return count

    def _cleanup_old_entries(self, cutoff: datetime) -> None:
        """Remove entries older than cutoff."""
        for entity_key in list(self._store.keys()):
            for feature_name in list(self._store[entity_key].keys()):
                self._store[entity_key][feature_name] = [
                    fv for fv in self._store[entity_key][feature_name]
                    if fv.timestamp >= cutoff
                ]


# =============================================================================
# FEATURE STORE
# =============================================================================

class FeatureStore:
    """
    Feast-inspired feature store for ML trading systems.
    
    Provides:
    - Feature registration with metadata
    - Online serving (<10ms latency)
    - Offline historical retrieval
    - Point-in-time correct joins
    - Feature freshness tracking
    - On-demand feature computation
    """

    def __init__(
        self,
        online_store: OnlineStore = None,
        offline_store: OfflineStore = None,
        default_ttl_seconds: int = 300,
    ):
        self.online_store = online_store or InMemoryOnlineStore()
        self.offline_store = offline_store or InMemoryOfflineStore()
        self.default_ttl_seconds = default_ttl_seconds
        
        self._definitions: Dict[str, FeatureDefinition] = {}
        self._compute_fns: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        
        # Metrics
        self._stats = {
            'online_hits': 0,
            'online_misses': 0,
            'computations': 0,
            'stale_served': 0,
        }

        logger.info("FeatureStore initialized")

    def register_feature(self, definition: FeatureDefinition) -> None:
        """Register a feature definition."""
        with self._lock:
            self._definitions[definition.name] = definition
            if definition.compute_fn:
                self._compute_fns[definition.name] = definition.compute_fn
                
        logger.info(f"Registered feature: {definition.name} v{definition.version}")

    def register_features(self, definitions: List[FeatureDefinition]) -> None:
        """Register multiple feature definitions."""
        for defn in definitions:
            self.register_feature(defn)

    def get_online_features(
        self,
        entity_keys: Union[str, List[str]],
        feature_names: List[str],
        allow_stale: bool = True,
        compute_missing: bool = True,
    ) -> Dict[str, FeatureVector]:
        """
        Get features for online serving.
        
        Args:
            entity_keys: Entity key(s) to fetch features for
            feature_names: List of feature names to retrieve
            allow_stale: Whether to return stale features
            compute_missing: Whether to compute missing features on-demand
            
        Returns:
            Dictionary mapping entity_key -> FeatureVector
        """
        start = time.perf_counter()
        
        if isinstance(entity_keys, str):
            entity_keys = [entity_keys]
            
        results = {}
        
        for entity_key in entity_keys:
            features = self._get_entity_features(
                entity_key, 
                feature_names, 
                allow_stale, 
                compute_missing
            )
            
            results[entity_key] = FeatureVector(
                entity_key=entity_key,
                timestamp=datetime.now(timezone.utc),
                features=features,
                request_latency_ms=(time.perf_counter() - start) * 1000,
            )
            
        return results

    def _get_entity_features(
        self,
        entity_key: str,
        feature_names: List[str],
        allow_stale: bool,
        compute_missing: bool,
    ) -> Dict[str, FeatureValue]:
        """Get features for a single entity."""
        features = {}
        now = datetime.now(timezone.utc)
        
        # Try online store first
        online_features = self.online_store.get(entity_key, feature_names)
        
        for name in feature_names:
            definition = self._definitions.get(name)
            ttl = definition.ttl_seconds if definition else self.default_ttl_seconds
            
            if name in online_features:
                fv = online_features[name]
                
                # Check freshness
                if fv.age_seconds <= ttl:
                    fv.status = FeatureStatus.FRESH
                    self._stats['online_hits'] += 1
                elif allow_stale:
                    fv.status = FeatureStatus.STALE
                    self._stats['stale_served'] += 1
                    logger.warning(f"Serving stale feature {name} for {entity_key}")
                else:
                    fv = None
                    self._stats['online_misses'] += 1
                    
                if fv:
                    features[name] = fv
                    continue
            else:
                self._stats['online_misses'] += 1
                    
            # Try to compute missing
            if compute_missing and name in self._compute_fns:
                try:
                    value = self._compute_fns[name](entity_key)
                    fv = FeatureValue(
                        name=name,
                        value=value,
                        timestamp=now,
                        entity_key=entity_key,
                        status=FeatureStatus.COMPUTED,
                        source="computed"
                    )
                    features[name] = fv
                    
                    # Cache computed value
                    self.online_store.put(entity_key, {name: value}, now)
                    self._stats['computations'] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to compute feature {name}: {e}")
                    features[name] = FeatureValue(
                        name=name,
                        value=None,
                        timestamp=now,
                        entity_key=entity_key,
                        status=FeatureStatus.MISSING,
                    )
            else:
                features[name] = FeatureValue(
                    name=name,
                    value=None,
                    timestamp=now,
                    entity_key=entity_key,
                    status=FeatureStatus.MISSING,
                )
                
        return features

    def materialize_features(
        self,
        entity_keys: List[str],
        feature_names: List[str],
        values: Dict[str, Dict[str, Any]],
        timestamp: datetime = None,
    ) -> int:
        """
        Materialize (write) features to online store.
        
        Args:
            entity_keys: List of entity keys
            feature_names: List of feature names being written
            values: Dict of entity_key -> {feature_name: value}
            timestamp: Optional timestamp for values
            
        Returns:
            Count of features written
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        count = 0
        
        for entity_key in entity_keys:
            if entity_key in values:
                self.online_store.put(entity_key, values[entity_key], timestamp)
                count += len(values[entity_key])
                
        logger.debug(f"Materialized {count} features for {len(entity_keys)} entities")
        return count

    def get_historical_features(
        self,
        entity_df: List[Dict[str, Any]],
        feature_names: List[str],
        timestamp_col: str = "timestamp",
        entity_col: str = "symbol",
    ) -> List[Dict[str, Any]]:
        """
        Get point-in-time correct historical features for training.
        
        Args:
            entity_df: List of dicts with entity keys and timestamps
            feature_names: Features to retrieve
            timestamp_col: Column name for timestamps
            entity_col: Column name for entity keys
            
        Returns:
            entity_df enriched with feature columns
        """
        if not entity_df:
            return []
            
        # Get time range
        timestamps = [row[timestamp_col] for row in entity_df]
        start = min(timestamps)
        end = max(timestamps)
        
        # Get all entity keys
        entity_keys = list(set(row[entity_col] for row in entity_df))
        
        # Fetch historical features
        historical = self.offline_store.get_historical(
            entity_keys, feature_names, start, end
        )
        
        # Point-in-time join
        result = []
        for row in entity_df:
            entity_key = row[entity_col]
            row_ts = row[timestamp_col]
            
            enriched = dict(row)
            
            for name in feature_names:
                # Find most recent feature value before timestamp
                key = f"{entity_key}"
                if key in historical:
                    candidates = [
                        fv for fv in historical[key]
                        if fv.name == name and fv.timestamp <= row_ts
                    ]
                    if candidates:
                        latest = max(candidates, key=lambda x: x.timestamp)
                        enriched[name] = latest.value
                    else:
                        enriched[name] = None
                else:
                    enriched[name] = None
                    
            result.append(enriched)
            
        return result

    def write_to_offline_store(self, features: List[FeatureValue]) -> int:
        """Write features to offline store for historical retrieval."""
        return self.offline_store.write_batch(features)

    def get_feature_definition(self, name: str) -> Optional[FeatureDefinition]:
        """Get feature definition by name."""
        return self._definitions.get(name)

    def list_features(self, tags: List[str] = None) -> List[FeatureDefinition]:
        """List all registered features, optionally filtered by tags."""
        features = list(self._definitions.values())
        
        if tags:
            features = [f for f in features if any(t in f.tags for t in tags)]
            
        return features

    def get_statistics(self) -> Dict[str, Any]:
        """Get feature store statistics."""
        total = self._stats['online_hits'] + self._stats['online_misses']
        hit_rate = self._stats['online_hits'] / total if total > 0 else 0
        
        return {
            **self._stats,
            'registered_features': len(self._definitions),
            'compute_functions': len(self._compute_fns),
            'hit_rate': hit_rate,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_trading_feature_store() -> FeatureStore:
    """Create feature store with common trading features pre-registered."""
    store = FeatureStore()
    
    # Register common trading features
    common_features = [
        FeatureDefinition(
            name="price",
            value_type=FeatureValueType.FLOAT,
            description="Latest price",
            ttl_seconds=60,
            tags=["price", "realtime"]
        ),
        FeatureDefinition(
            name="volume_24h",
            value_type=FeatureValueType.FLOAT,
            description="24-hour trading volume",
            ttl_seconds=300,
            tags=["volume"]
        ),
        FeatureDefinition(
            name="volatility_20d",
            value_type=FeatureValueType.FLOAT,
            description="20-day realized volatility",
            ttl_seconds=3600,
            tags=["volatility", "risk"]
        ),
        FeatureDefinition(
            name="rsi_14",
            value_type=FeatureValueType.FLOAT,
            description="14-period RSI",
            ttl_seconds=300,
            tags=["momentum", "technical"]
        ),
        FeatureDefinition(
            name="sma_50",
            value_type=FeatureValueType.FLOAT,
            description="50-day simple moving average",
            ttl_seconds=3600,
            tags=["trend", "technical"]
        ),
        FeatureDefinition(
            name="atr_14",
            value_type=FeatureValueType.FLOAT,
            description="14-period Average True Range",
            ttl_seconds=300,
            tags=["volatility", "technical"]
        ),
    ]
    
    store.register_features(common_features)
    
    return store
