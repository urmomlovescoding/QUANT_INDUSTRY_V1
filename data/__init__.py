"""
QUANT_INDUSTRY_V1 Data Module

Market data fetching, validation, and caching with:
- Multi-source fetching (Alpaca -> Yahoo fallback)
- Rate limiting per source
- Data quality validation
- Quality firewall
- Memory + disk caching

Usage:
    from data.fetcher import UnifiedDataFetcher, Timeframe
    from data.validator import DataQualityFirewall
    from data.cache import DataCache

    cache = DataCache()
    fetcher = UnifiedDataFetcher()
    fetcher.set_cache(cache)

    result = fetcher.fetch("AAPL", Timeframe.DAY_1, limit=100)
"""

from .fetcher import (
    # Types
    DataSource,
    Timeframe,
    Bar,
    MarketData,
    FetchResult,
    # Rate limiter
    RateLimiter,
    # Providers
    BaseDataProvider,
    AlpacaDataProvider,
    YahooDataProvider,
    # Main fetcher
    UnifiedDataFetcher,
)

from .validator import (
    # Types
    ValidationSeverity,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
    ValidationConfig,
    # Validator
    DataValidator,
    DataQualityFirewall,
)

from .cache import (
    # Types
    CacheEntry,
    CacheStats,
    # Caches
    MemoryCache,
    DiskCache,
    DataCache,
)

from .features import (
    # Types
    FeatureCategory,
    FeatureConfig,
    FeatureSet,
    # Computers
    FeatureComputer,
    MovingAverages,
    MomentumIndicators,
    VolatilityIndicators,
    VolumeIndicators,
    StatisticalFeatures,
    # Engine
    FeatureEngine,
)

__all__ = [
    # Fetcher types
    'DataSource',
    'Timeframe',
    'Bar',
    'MarketData',
    'FetchResult',
    'RateLimiter',
    # Providers
    'BaseDataProvider',
    'AlpacaDataProvider',
    'YahooDataProvider',
    'UnifiedDataFetcher',
    # Validator types
    'ValidationSeverity',
    'ValidationCategory',
    'ValidationIssue',
    'ValidationResult',
    'ValidationConfig',
    'DataValidator',
    'DataQualityFirewall',
    # Cache
    'CacheEntry',
    'CacheStats',
    'MemoryCache',
    'DiskCache',
    'DataCache',
    # Features
    'FeatureCategory',
    'FeatureConfig',
    'FeatureSet',
    'FeatureComputer',
    'MovingAverages',
    'MomentumIndicators',
    'VolatilityIndicators',
    'VolumeIndicators',
    'StatisticalFeatures',
    'FeatureEngine',
]
