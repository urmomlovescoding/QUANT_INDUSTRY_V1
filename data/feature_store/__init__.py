"""
Feature Store - Centralized Feature Management for Quant Trading

This module provides a Feast-compatible feature store implementation
for managing, versioning, and serving ML features in real-time.

Key Components:
- QuantFeatureStore: Main client wrapper for feature access
- FeatureDefinitions: Standardized feature definitions
- FeatureRegistry: Feature metadata and versioning

Industry Context:
Production ML systems require consistent feature computation between
training and serving. This feature store ensures:
- Point-in-time correctness (no data leakage)
- Feature versioning and lineage
- Low-latency online serving
- Batch materialization for training

Usage:
    from data.feature_store import QuantFeatureStore, get_feature_definitions

    store = QuantFeatureStore()
    features = store.get_online_features(
        entity_ids=['AAPL', 'GOOGL'],
        feature_refs=['price_features:sma_20', 'volume_features:vwap']
    )
"""

from .store import QuantFeatureStore, FeatureStoreConfig
from .definitions import (
    get_feature_definitions,
    PriceFeatures,
    VolumeFeatures,
    TechnicalFeatures,
    SentimentFeatures,
    RiskFeatures,
)
from .registry import (
    FeatureRegistry,
    FeatureMetadata,
    FeatureVersion,
    FeatureStatus,
)

__all__ = [
    # Main store
    'QuantFeatureStore',
    'FeatureStoreConfig',
    # Feature definitions
    'get_feature_definitions',
    'PriceFeatures',
    'VolumeFeatures',
    'TechnicalFeatures',
    'SentimentFeatures',
    'RiskFeatures',
    # Registry
    'FeatureRegistry',
    'FeatureMetadata',
    'FeatureVersion',
    'FeatureStatus',
]
