"""
Feature Registry - Feature Metadata and Version Management

This module provides a centralized registry for tracking feature metadata,
versions, and lineage. Essential for ML model reproducibility.

Key Features:
- Feature versioning with semantic versioning
- Feature lineage tracking
- Feature deprecation management
- Feature statistics and monitoring
- Integration with ML model registry

Usage:
    from data.feature_store.registry import FeatureRegistry

    registry = FeatureRegistry()

    # Register a new feature
    registry.register_feature(
        name="sma_20",
        version="1.0.0",
        description="20-period SMA",
        compute_hash="abc123",
    )

    # Get feature metadata
    metadata = registry.get_feature("sma_20")
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class FeatureStatus(Enum):
    """Feature lifecycle status."""
    EXPERIMENTAL = "experimental"  # In development, not for production
    ACTIVE = "active"              # Production-ready
    DEPRECATED = "deprecated"      # Still available but will be removed
    ARCHIVED = "archived"          # No longer available


@dataclass
class FeatureVersion:
    """Version information for a feature."""
    version: str
    created_at: datetime
    compute_hash: str  # Hash of computation code
    description: str
    breaking_change: bool = False
    migration_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'compute_hash': self.compute_hash,
            'description': self.description,
            'breaking_change': self.breaking_change,
            'migration_notes': self.migration_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureVersion':
        return cls(
            version=data['version'],
            created_at=datetime.fromisoformat(data['created_at']),
            compute_hash=data['compute_hash'],
            description=data['description'],
            breaking_change=data.get('breaking_change', False),
            migration_notes=data.get('migration_notes'),
        )


@dataclass
class FeatureStatistics:
    """Runtime statistics for a feature."""
    compute_count: int = 0
    total_compute_time_ms: float = 0.0
    null_rate: float = 0.0
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_mean: Optional[float] = None
    value_std: Optional[float] = None
    last_computed: Optional[datetime] = None
    error_count: int = 0

    def update(self, value: Any, compute_time_ms: float) -> None:
        """Update statistics with a new computation."""
        self.compute_count += 1
        self.total_compute_time_ms += compute_time_ms
        self.last_computed = datetime.now(timezone.utc)

        if value is None:
            self.null_rate = (
                (self.null_rate * (self.compute_count - 1) + 1) / self.compute_count
            )
        elif isinstance(value, (int, float)):
            self.null_rate = (
                self.null_rate * (self.compute_count - 1) / self.compute_count
            )

            # Update value statistics
            if self.value_min is None or value < self.value_min:
                self.value_min = value
            if self.value_max is None or value > self.value_max:
                self.value_max = value

            # Running mean and std
            if self.value_mean is None:
                self.value_mean = value
                self.value_std = 0.0
            else:
                old_mean = self.value_mean
                self.value_mean = old_mean + (value - old_mean) / self.compute_count
                self.value_std = (
                    (self.value_std ** 2 * (self.compute_count - 1) +
                     (value - old_mean) * (value - self.value_mean)) / self.compute_count
                ) ** 0.5

    @property
    def avg_compute_time_ms(self) -> float:
        if self.compute_count == 0:
            return 0.0
        return self.total_compute_time_ms / self.compute_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            'compute_count': self.compute_count,
            'total_compute_time_ms': self.total_compute_time_ms,
            'avg_compute_time_ms': self.avg_compute_time_ms,
            'null_rate': self.null_rate,
            'value_min': self.value_min,
            'value_max': self.value_max,
            'value_mean': self.value_mean,
            'value_std': self.value_std,
            'last_computed': self.last_computed.isoformat() if self.last_computed else None,
            'error_count': self.error_count,
        }


@dataclass
class FeatureMetadata:
    """Complete metadata for a registered feature."""
    name: str
    description: str
    owner: str
    status: FeatureStatus
    current_version: str
    versions: List[FeatureVersion] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    consumers: List[str] = field(default_factory=list)  # Models using this feature
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deprecated_at: Optional[datetime] = None
    deprecation_message: Optional[str] = None
    statistics: FeatureStatistics = field(default_factory=FeatureStatistics)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_version(self, version: FeatureVersion) -> None:
        """Add a new version."""
        self.versions.append(version)
        self.current_version = version.version
        self.updated_at = datetime.now(timezone.utc)

    def deprecate(self, message: str) -> None:
        """Mark feature as deprecated."""
        self.status = FeatureStatus.DEPRECATED
        self.deprecated_at = datetime.now(timezone.utc)
        self.deprecation_message = message
        self.updated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        """Archive the feature."""
        self.status = FeatureStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'owner': self.owner,
            'status': self.status.value,
            'current_version': self.current_version,
            'versions': [v.to_dict() for v in self.versions],
            'dependencies': self.dependencies,
            'consumers': self.consumers,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'deprecated_at': self.deprecated_at.isoformat() if self.deprecated_at else None,
            'deprecation_message': self.deprecation_message,
            'statistics': self.statistics.to_dict(),
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureMetadata':
        return cls(
            name=data['name'],
            description=data['description'],
            owner=data['owner'],
            status=FeatureStatus(data['status']),
            current_version=data['current_version'],
            versions=[FeatureVersion.from_dict(v) for v in data.get('versions', [])],
            dependencies=data.get('dependencies', []),
            consumers=data.get('consumers', []),
            tags=data.get('tags', []),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            deprecated_at=datetime.fromisoformat(data['deprecated_at']) if data.get('deprecated_at') else None,
            deprecation_message=data.get('deprecation_message'),
            metadata=data.get('metadata', {}),
        )


class FeatureRegistry:
    """
    Central registry for feature metadata and versioning.

    Provides:
    - Feature registration and discovery
    - Version management with semantic versioning
    - Lineage tracking (dependencies and consumers)
    - Statistics collection
    - Deprecation management

    Example:
        registry = FeatureRegistry()

        # Register feature
        registry.register_feature(
            name="rsi_14",
            description="14-period RSI",
            owner="quant_team",
            version="1.0.0",
            compute_hash=hash_of_compute_function,
        )

        # Add consumer (model using this feature)
        registry.add_consumer("rsi_14", "momentum_model_v2")

        # Check for deprecated features in model
        deprecated = registry.check_deprecated_features(["rsi_14", "old_feature"])
    """

    def __init__(self, persist_path: Optional[str] = None):
        """
        Initialize the feature registry.

        Args:
            persist_path: Path to persist registry data (JSON file)
        """
        self._features: Dict[str, FeatureMetadata] = {}
        self._lock = threading.RLock()

        self._persist_path = Path(persist_path) if persist_path else (
            Path(__file__).parent / 'registry_data.json'
        )

        # Load existing data
        self._load()

        logger.info(f"FeatureRegistry initialized with {len(self._features)} features")

    def _load(self) -> None:
        """Load registry data from disk."""
        if self._persist_path.exists():
            try:
                with open(self._persist_path, 'r') as f:
                    data = json.load(f)

                for feature_data in data.get('features', []):
                    feature = FeatureMetadata.from_dict(feature_data)
                    self._features[feature.name] = feature

                logger.info(f"Loaded {len(self._features)} features from registry")

            except Exception as e:
                logger.warning(f"Failed to load registry: {e}")

    def _save(self) -> None:
        """Persist registry data to disk."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'features': [f.to_dict() for f in self._features.values()],
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }

            with open(self._persist_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def register_feature(
        self,
        name: str,
        description: str,
        owner: str = "quant_team",
        version: str = "1.0.0",
        compute_hash: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeatureMetadata:
        """
        Register a new feature or add a version to existing feature.

        Args:
            name: Unique feature name
            description: Human-readable description
            owner: Team or person responsible
            version: Semantic version string
            compute_hash: Hash of computation code for lineage
            dependencies: List of feature names this depends on
            tags: Tags for categorization
            metadata: Additional metadata

        Returns:
            FeatureMetadata for the registered feature
        """
        with self._lock:
            compute_hash = compute_hash or hashlib.md5(
                f"{name}:{version}".encode()
            ).hexdigest()

            version_info = FeatureVersion(
                version=version,
                created_at=datetime.now(timezone.utc),
                compute_hash=compute_hash,
                description=f"Version {version}",
            )

            if name in self._features:
                # Add new version to existing feature
                feature = self._features[name]
                feature.add_version(version_info)
                feature.description = description  # Update description

            else:
                # Create new feature
                feature = FeatureMetadata(
                    name=name,
                    description=description,
                    owner=owner,
                    status=FeatureStatus.ACTIVE,
                    current_version=version,
                    versions=[version_info],
                    dependencies=dependencies or [],
                    tags=tags or [],
                    metadata=metadata or {},
                )
                self._features[name] = feature

            self._save()
            logger.info(f"Registered feature: {name} v{version}")

            return feature

    def get_feature(self, name: str) -> Optional[FeatureMetadata]:
        """Get feature metadata by name."""
        return self._features.get(name)

    def list_features(
        self,
        status: Optional[FeatureStatus] = None,
        tag: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> List[FeatureMetadata]:
        """
        List features with optional filtering.

        Args:
            status: Filter by status
            tag: Filter by tag
            owner: Filter by owner

        Returns:
            List of matching features
        """
        features = list(self._features.values())

        if status:
            features = [f for f in features if f.status == status]
        if tag:
            features = [f for f in features if tag in f.tags]
        if owner:
            features = [f for f in features if f.owner == owner]

        return features

    def add_consumer(self, feature_name: str, consumer_name: str) -> bool:
        """
        Record that a model/system uses this feature.

        Args:
            feature_name: Name of the feature
            consumer_name: Name of the consuming model/system

        Returns:
            True if successful
        """
        with self._lock:
            feature = self._features.get(feature_name)
            if not feature:
                logger.warning(f"Feature not found: {feature_name}")
                return False

            if consumer_name not in feature.consumers:
                feature.consumers.append(consumer_name)
                feature.updated_at = datetime.now(timezone.utc)
                self._save()

            return True

    def remove_consumer(self, feature_name: str, consumer_name: str) -> bool:
        """Remove a consumer from feature."""
        with self._lock:
            feature = self._features.get(feature_name)
            if not feature:
                return False

            if consumer_name in feature.consumers:
                feature.consumers.remove(consumer_name)
                feature.updated_at = datetime.now(timezone.utc)
                self._save()

            return True

    def deprecate_feature(
        self,
        name: str,
        message: str,
        replacement: Optional[str] = None,
    ) -> bool:
        """
        Mark a feature as deprecated.

        Args:
            name: Feature name
            message: Deprecation message explaining why
            replacement: Suggested replacement feature

        Returns:
            True if successful
        """
        with self._lock:
            feature = self._features.get(name)
            if not feature:
                logger.warning(f"Feature not found: {name}")
                return False

            full_message = message
            if replacement:
                full_message += f" Use '{replacement}' instead."

            feature.deprecate(full_message)
            self._save()

            # Warn consumers
            if feature.consumers:
                logger.warning(
                    f"Deprecated feature '{name}' is used by: {feature.consumers}"
                )

            return True

    def check_deprecated_features(
        self,
        feature_names: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Check if any features in a list are deprecated.

        Args:
            feature_names: List of feature names to check

        Returns:
            List of deprecation warnings
        """
        warnings = []

        for name in feature_names:
            feature = self._features.get(name)
            if feature and feature.status == FeatureStatus.DEPRECATED:
                warnings.append({
                    'feature': name,
                    'message': feature.deprecation_message,
                    'deprecated_at': feature.deprecated_at.isoformat() if feature.deprecated_at else None,
                })

        return warnings

    def get_feature_lineage(self, name: str) -> Dict[str, Any]:
        """
        Get complete lineage for a feature.

        Returns:
            Dictionary with dependencies and consumers
        """
        feature = self._features.get(name)
        if not feature:
            return {'error': 'Feature not found'}

        # Get upstream (dependencies)
        upstream = []
        for dep_name in feature.dependencies:
            dep = self._features.get(dep_name)
            if dep:
                upstream.append({
                    'name': dep_name,
                    'version': dep.current_version,
                    'status': dep.status.value,
                })

        # Get downstream (consumers)
        downstream = feature.consumers.copy()

        return {
            'feature': name,
            'version': feature.current_version,
            'upstream': upstream,
            'downstream': downstream,
        }

    def update_statistics(
        self,
        name: str,
        value: Any,
        compute_time_ms: float,
    ) -> None:
        """Update feature statistics after computation."""
        with self._lock:
            feature = self._features.get(name)
            if feature:
                feature.statistics.update(value, compute_time_ms)

    def record_error(self, name: str) -> None:
        """Record a computation error for a feature."""
        with self._lock:
            feature = self._features.get(name)
            if feature:
                feature.statistics.error_count += 1

    def get_statistics(self, name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a feature."""
        feature = self._features.get(name)
        if feature:
            return feature.statistics.to_dict()
        return None

    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all features."""
        return {
            name: feature.statistics.to_dict()
            for name, feature in self._features.items()
        }

    def find_orphaned_features(self) -> List[str]:
        """Find features with no consumers."""
        return [
            name for name, feature in self._features.items()
            if not feature.consumers and feature.status == FeatureStatus.ACTIVE
        ]

    def find_broken_dependencies(self) -> List[Dict[str, Any]]:
        """Find features with missing dependencies."""
        broken = []

        for name, feature in self._features.items():
            for dep in feature.dependencies:
                if dep not in self._features:
                    broken.append({
                        'feature': name,
                        'missing_dependency': dep,
                    })
                elif self._features[dep].status == FeatureStatus.ARCHIVED:
                    broken.append({
                        'feature': name,
                        'archived_dependency': dep,
                    })

        return broken

    def export_catalog(self) -> Dict[str, Any]:
        """Export feature catalog for documentation."""
        catalog = {
            'total_features': len(self._features),
            'by_status': {},
            'features': [],
        }

        # Count by status
        for status in FeatureStatus:
            count = len([f for f in self._features.values() if f.status == status])
            catalog['by_status'][status.value] = count

        # Feature list
        for name, feature in sorted(self._features.items()):
            catalog['features'].append({
                'name': name,
                'description': feature.description,
                'status': feature.status.value,
                'version': feature.current_version,
                'owner': feature.owner,
                'tags': feature.tags,
                'consumers_count': len(feature.consumers),
            })

        return catalog
