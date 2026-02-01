"""
QUANT_INDUSTRY_V1 Real-Time Data Normalization

Streaming normalization system with <50ms latency for production trading:
- Z-score, Min-Max, and Robust scaling methods
- Rolling statistics for online normalization
- Async processing support
- Integration with data pipeline

Rollback Plan: Delete this file
Tests Required: Unit tests for normalization accuracy, latency tests
Failure Modes: Return unnormalized data with warning, log errors
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
)
import math
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# NORMALIZATION TYPES
# =============================================================================

class NormalizationMethod(Enum):
    """Available normalization methods."""
    ZSCORE = "zscore"          # (x - mean) / std
    MINMAX = "minmax"          # (x - min) / (max - min)
    ROBUST = "robust"          # (x - median) / IQR
    DECIMAL = "decimal"        # x / 10^n where n = ceil(log10(max(|x|)))
    NONE = "none"              # No normalization


class WindowType(Enum):
    """Types of rolling windows."""
    FIXED = "fixed"            # Fixed-size sliding window
    EXPONENTIAL = "exponential"  # Exponentially weighted
    EXPANDING = "expanding"    # Growing window (all history)


@dataclass
class NormalizationConfig:
    """Configuration for data normalization."""
    # Method settings
    method: NormalizationMethod = NormalizationMethod.ZSCORE
    window_type: WindowType = WindowType.FIXED
    window_size: int = 100

    # Exponential weighting (for EXPONENTIAL window)
    alpha: float = 0.1  # Smoothing factor (higher = more recent weight)

    # Bounds for clipping
    clip_min: Optional[float] = -5.0  # Clip normalized values below this
    clip_max: Optional[float] = 5.0   # Clip normalized values above this

    # Min-max specific
    minmax_min: float = 0.0  # Target min for minmax scaling
    minmax_max: float = 1.0  # Target max for minmax scaling

    # Robust scaling specific
    quantile_low: float = 0.25   # Lower quantile for IQR
    quantile_high: float = 0.75  # Upper quantile for IQR

    # Performance settings
    target_latency_ms: float = 50.0  # Target normalization latency
    warmup_samples: int = 20  # Min samples before normalization

    # Error handling
    fallback_on_error: bool = True  # Return unnormalized on error
    epsilon: float = 1e-8  # Small value to prevent division by zero

    def validate(self) -> List[str]:
        """Validate configuration, return list of errors."""
        errors = []
        if self.window_size < 2:
            errors.append("window_size must be >= 2")
        if not 0 < self.alpha <= 1:
            errors.append("alpha must be in (0, 1]")
        if self.quantile_low >= self.quantile_high:
            errors.append("quantile_low must be < quantile_high")
        if self.warmup_samples < 1:
            errors.append("warmup_samples must be >= 1")
        return errors


@dataclass
class NormalizationStats:
    """Statistics computed for normalization."""
    count: int = 0
    mean: float = 0.0
    variance: float = 0.0
    std: float = 0.0
    min_val: float = float('inf')
    max_val: float = float('-inf')
    median: float = 0.0
    q1: float = 0.0  # 25th percentile
    q3: float = 0.0  # 75th percentile
    iqr: float = 0.0  # Interquartile range

    # Exponential weighted stats
    ewm_mean: float = 0.0
    ewm_variance: float = 0.0
    ewm_std: float = 0.0

    # Metadata
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_warm: bool = False  # Has enough samples for reliable normalization

    @property
    def is_valid(self) -> bool:
        """Check if statistics are valid for normalization."""
        return (
            self.count > 0 and
            not math.isnan(self.mean) and
            not math.isinf(self.mean) and
            self.std > 0
        )


@dataclass
class NormalizationResult:
    """Result of a normalization operation."""
    original_value: float
    normalized_value: float
    method: NormalizationMethod
    stats_used: NormalizationStats
    processing_time_ms: float
    was_clipped: bool = False
    was_fallback: bool = False  # True if returned unnormalized due to error
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'original_value': self.original_value,
            'normalized_value': self.normalized_value,
            'method': self.method.value,
            'processing_time_ms': self.processing_time_ms,
            'was_clipped': self.was_clipped,
            'was_fallback': self.was_fallback,
            'timestamp': self.timestamp.isoformat(),
        }


# =============================================================================
# ROLLING STATISTICS
# =============================================================================

class RollingStatistics:
    """
    Maintains rolling statistics for real-time normalization.

    Uses Welford's online algorithm for numerically stable computation
    of mean and variance in a single pass.

    Features:
    - O(1) updates for fixed window
    - O(1) memory for exponential weighting
    - Thread-safe operations
    """

    def __init__(
        self,
        window_size: int = 100,
        window_type: WindowType = WindowType.FIXED,
        alpha: float = 0.1,
    ):
        self.window_size = window_size
        self.window_type = window_type
        self.alpha = alpha

        # Fixed window storage
        self._window: Deque[float] = deque(maxlen=window_size)

        # Welford's algorithm state
        self._count = 0
        self._mean = 0.0
        self._m2 = 0.0  # Sum of squared differences from mean

        # Exponential weighted state
        self._ewm_mean = 0.0
        self._ewm_variance = 0.0
        self._ewm_initialized = False

        # Min/max tracking
        self._min = float('inf')
        self._max = float('-inf')

        # Thread safety
        self._lock = threading.Lock()

    def update(self, value: float) -> NormalizationStats:
        """
        Update statistics with a new value.

        Args:
            value: New data point

        Returns:
            Updated NormalizationStats
        """
        with self._lock:
            return self._update_internal(value)

    def _update_internal(self, value: float) -> NormalizationStats:
        """Internal update without lock (caller must hold lock)."""
        if math.isnan(value) or math.isinf(value):
            logger.warning(f"Skipping invalid value: {value}")
            return self.get_stats()

        # Update exponential weighted stats first (independent of window)
        self._update_ewm(value)

        if self.window_type == WindowType.EXPANDING:
            self._update_expanding(value)
        elif self.window_type == WindowType.FIXED:
            self._update_fixed_window(value)
        elif self.window_type == WindowType.EXPONENTIAL:
            # For exponential, we don't need the fixed window stats
            pass

        # Update global min/max
        self._min = min(self._min, value)
        self._max = max(self._max, value)

        return self.get_stats()

    def _update_expanding(self, value: float) -> None:
        """Update using expanding window (all history)."""
        self._count += 1
        delta = value - self._mean
        self._mean += delta / self._count
        delta2 = value - self._mean
        self._m2 += delta * delta2

    def _update_fixed_window(self, value: float) -> None:
        """Update using fixed sliding window."""
        old_value = None
        if len(self._window) == self.window_size:
            old_value = self._window[0]

        self._window.append(value)

        if old_value is not None:
            # Remove old value's contribution and add new value's
            # Using corrected two-pass approach for stability
            n = len(self._window)
            old_mean = self._mean

            # Update mean
            self._mean = old_mean + (value - old_value) / n

            # Update M2 (sum of squared deviations)
            self._m2 = self._m2 + (value - old_value) * (
                (value - self._mean) + (old_value - old_mean)
            )
            self._count = n
        else:
            # Growing phase - use Welford's
            self._count += 1
            delta = value - self._mean
            self._mean += delta / self._count
            delta2 = value - self._mean
            self._m2 += delta * delta2

    def _update_ewm(self, value: float) -> None:
        """Update exponentially weighted moving statistics."""
        if not self._ewm_initialized:
            self._ewm_mean = value
            self._ewm_variance = 0.0
            self._ewm_initialized = True
        else:
            # EWM mean
            delta = value - self._ewm_mean
            self._ewm_mean += self.alpha * delta

            # EWM variance using online algorithm
            # Var_new = (1-alpha) * (Var_old + alpha * delta^2)
            self._ewm_variance = (1 - self.alpha) * (
                self._ewm_variance + self.alpha * delta * delta
            )

    def get_stats(self) -> NormalizationStats:
        """Get current statistics."""
        with self._lock:
            # Calculate variance and std
            variance = self._m2 / max(self._count - 1, 1) if self._count > 1 else 0.0
            std = math.sqrt(variance) if variance > 0 else 0.0

            # Calculate quantiles from window (for robust scaling)
            q1, median, q3 = 0.0, 0.0, 0.0
            if len(self._window) >= 3:
                sorted_window = sorted(self._window)
                n = len(sorted_window)
                q1 = sorted_window[int(n * 0.25)]
                median = sorted_window[n // 2]
                q3 = sorted_window[int(n * 0.75)]

            return NormalizationStats(
                count=self._count,
                mean=self._mean,
                variance=variance,
                std=std,
                min_val=self._min if self._min != float('inf') else 0.0,
                max_val=self._max if self._max != float('-inf') else 0.0,
                median=median,
                q1=q1,
                q3=q3,
                iqr=q3 - q1,
                ewm_mean=self._ewm_mean,
                ewm_variance=self._ewm_variance,
                ewm_std=math.sqrt(self._ewm_variance) if self._ewm_variance > 0 else 0.0,
                last_updated=datetime.now(timezone.utc),
                is_warm=self._count >= self.window_size // 2,
            )

    def reset(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self._window.clear()
            self._count = 0
            self._mean = 0.0
            self._m2 = 0.0
            self._ewm_mean = 0.0
            self._ewm_variance = 0.0
            self._ewm_initialized = False
            self._min = float('inf')
            self._max = float('-inf')


# =============================================================================
# DATA NORMALIZER
# =============================================================================

class DataNormalizer:
    """
    Real-time data normalizer with streaming support.

    Provides:
    - Z-score normalization (standard scaling)
    - Min-Max normalization (range scaling)
    - Robust normalization (median/IQR based)
    - Async processing for non-blocking operations
    - Performance monitoring and latency tracking

    Usage:
        normalizer = DataNormalizer(NormalizationConfig(
            method=NormalizationMethod.ZSCORE,
            window_size=100,
        ))

        # Single value
        result = normalizer.normalize(42.5)

        # Batch
        results = normalizer.normalize_batch([1.0, 2.0, 3.0])

        # Async
        result = await normalizer.normalize_async(42.5)
    """

    def __init__(self, config: NormalizationConfig = None):
        self.config = config or NormalizationConfig()

        # Validate config
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid config: {errors}")

        # Per-feature statistics
        self._stats: Dict[str, RollingStatistics] = {}
        self._default_stats = RollingStatistics(
            window_size=self.config.window_size,
            window_type=self.config.window_type,
            alpha=self.config.alpha,
        )

        # Performance tracking
        self._total_normalizations = 0
        self._total_latency_ms = 0.0
        self._max_latency_ms = 0.0
        self._latency_breaches = 0

        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=4)

        # Lock for thread-safe counter updates
        self._perf_lock = threading.Lock()

        logger.info(f"DataNormalizer initialized: method={self.config.method.value}")

    def get_or_create_stats(self, feature_name: str = "default") -> RollingStatistics:
        """Get or create rolling statistics for a feature."""
        if feature_name not in self._stats:
            self._stats[feature_name] = RollingStatistics(
                window_size=self.config.window_size,
                window_type=self.config.window_type,
                alpha=self.config.alpha,
            )
        return self._stats[feature_name]

    def normalize(
        self,
        value: float,
        feature_name: str = "default",
        update_stats: bool = True,
    ) -> NormalizationResult:
        """
        Normalize a single value.

        Args:
            value: Value to normalize
            feature_name: Name of the feature (for per-feature stats)
            update_stats: Whether to update rolling statistics

        Returns:
            NormalizationResult with normalized value and metadata
        """
        start_time = time.perf_counter()

        try:
            stats_tracker = self.get_or_create_stats(feature_name)

            # Update statistics if requested
            if update_stats:
                stats = stats_tracker.update(value)
            else:
                stats = stats_tracker.get_stats()

            # Check warmup
            if stats.count < self.config.warmup_samples:
                # Not enough data - return original or simple normalization
                if self.config.fallback_on_error:
                    return self._create_fallback_result(value, start_time, stats)

            # Perform normalization
            normalized, was_clipped = self._normalize_value(value, stats)

            # Track performance
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            self._track_performance(processing_time_ms)

            return NormalizationResult(
                original_value=value,
                normalized_value=normalized,
                method=self.config.method,
                stats_used=stats,
                processing_time_ms=processing_time_ms,
                was_clipped=was_clipped,
                was_fallback=False,
            )

        except Exception as e:
            logger.error(f"Normalization error: {e}")
            if self.config.fallback_on_error:
                return self._create_fallback_result(
                    value, start_time, self._default_stats.get_stats()
                )
            raise

    def _normalize_value(
        self,
        value: float,
        stats: NormalizationStats,
    ) -> Tuple[float, bool]:
        """
        Apply normalization method to value.

        Returns:
            Tuple of (normalized_value, was_clipped)
        """
        eps = self.config.epsilon
        was_clipped = False

        if self.config.method == NormalizationMethod.NONE:
            return value, False

        elif self.config.method == NormalizationMethod.ZSCORE:
            if self.config.window_type == WindowType.EXPONENTIAL:
                # Use exponentially weighted stats
                std = stats.ewm_std if stats.ewm_std > eps else eps
                normalized = (value - stats.ewm_mean) / std
            else:
                std = stats.std if stats.std > eps else eps
                normalized = (value - stats.mean) / std

        elif self.config.method == NormalizationMethod.MINMAX:
            range_val = stats.max_val - stats.min_val
            if range_val < eps:
                range_val = eps
            normalized = (value - stats.min_val) / range_val
            # Scale to target range
            target_range = self.config.minmax_max - self.config.minmax_min
            normalized = normalized * target_range + self.config.minmax_min

        elif self.config.method == NormalizationMethod.ROBUST:
            iqr = stats.iqr if stats.iqr > eps else eps
            normalized = (value - stats.median) / iqr

        elif self.config.method == NormalizationMethod.DECIMAL:
            max_abs = max(abs(stats.min_val), abs(stats.max_val))
            if max_abs < eps:
                normalized = value
            else:
                scale = 10 ** math.ceil(math.log10(max_abs + eps))
                normalized = value / scale

        else:
            normalized = value

        # Apply clipping if configured
        if self.config.clip_min is not None or self.config.clip_max is not None:
            original_normalized = normalized
            if self.config.clip_min is not None:
                normalized = max(normalized, self.config.clip_min)
            if self.config.clip_max is not None:
                normalized = min(normalized, self.config.clip_max)
            was_clipped = normalized != original_normalized

        return normalized, was_clipped

    def _create_fallback_result(
        self,
        value: float,
        start_time: float,
        stats: NormalizationStats,
    ) -> NormalizationResult:
        """Create a fallback result when normalization cannot be performed."""
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        self._track_performance(processing_time_ms)

        return NormalizationResult(
            original_value=value,
            normalized_value=value,  # Return original
            method=NormalizationMethod.NONE,
            stats_used=stats,
            processing_time_ms=processing_time_ms,
            was_clipped=False,
            was_fallback=True,
        )

    def _track_performance(self, latency_ms: float) -> None:
        """Track normalization performance."""
        with self._perf_lock:
            self._total_normalizations += 1
            self._total_latency_ms += latency_ms
            self._max_latency_ms = max(self._max_latency_ms, latency_ms)

            if latency_ms > self.config.target_latency_ms:
                self._latency_breaches += 1
                logger.warning(
                    f"Normalization latency breach: {latency_ms:.2f}ms > "
                    f"{self.config.target_latency_ms}ms target"
                )

    def normalize_batch(
        self,
        values: List[float],
        feature_name: str = "default",
        update_stats: bool = True,
    ) -> List[NormalizationResult]:
        """
        Normalize a batch of values.

        Args:
            values: Values to normalize
            feature_name: Feature name for statistics
            update_stats: Whether to update rolling statistics

        Returns:
            List of NormalizationResult
        """
        return [
            self.normalize(v, feature_name, update_stats)
            for v in values
        ]

    def normalize_array(
        self,
        values: np.ndarray,
        feature_name: str = "default",
        update_stats: bool = True,
    ) -> np.ndarray:
        """
        Normalize a numpy array efficiently.

        For large arrays, uses vectorized operations after computing stats.

        Args:
            values: 1D numpy array
            feature_name: Feature name for statistics
            update_stats: Whether to update rolling statistics

        Returns:
            Normalized numpy array
        """
        start_time = time.perf_counter()

        stats_tracker = self.get_or_create_stats(feature_name)

        # Update stats with all values if requested
        if update_stats:
            for v in values:
                stats_tracker.update(float(v))

        stats = stats_tracker.get_stats()
        eps = self.config.epsilon

        # Vectorized normalization
        if self.config.method == NormalizationMethod.ZSCORE:
            if self.config.window_type == WindowType.EXPONENTIAL:
                std = stats.ewm_std if stats.ewm_std > eps else eps
                normalized = (values - stats.ewm_mean) / std
            else:
                std = stats.std if stats.std > eps else eps
                normalized = (values - stats.mean) / std

        elif self.config.method == NormalizationMethod.MINMAX:
            range_val = stats.max_val - stats.min_val
            if range_val < eps:
                range_val = eps
            normalized = (values - stats.min_val) / range_val
            target_range = self.config.minmax_max - self.config.minmax_min
            normalized = normalized * target_range + self.config.minmax_min

        elif self.config.method == NormalizationMethod.ROBUST:
            iqr = stats.iqr if stats.iqr > eps else eps
            normalized = (values - stats.median) / iqr

        elif self.config.method == NormalizationMethod.DECIMAL:
            max_abs = max(abs(stats.min_val), abs(stats.max_val))
            if max_abs < eps:
                normalized = values.copy()
            else:
                scale = 10 ** math.ceil(math.log10(max_abs + eps))
                normalized = values / scale

        else:
            normalized = values.copy()

        # Apply clipping
        if self.config.clip_min is not None:
            normalized = np.maximum(normalized, self.config.clip_min)
        if self.config.clip_max is not None:
            normalized = np.minimum(normalized, self.config.clip_max)

        # Track performance
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        self._track_performance(processing_time_ms)

        return normalized

    async def normalize_async(
        self,
        value: float,
        feature_name: str = "default",
        update_stats: bool = True,
    ) -> NormalizationResult:
        """
        Async normalization for non-blocking operations.

        Runs normalization in a thread pool to avoid blocking
        the event loop.

        Args:
            value: Value to normalize
            feature_name: Feature name for statistics
            update_stats: Whether to update rolling statistics

        Returns:
            NormalizationResult
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.normalize,
            value,
            feature_name,
            update_stats,
        )

    async def normalize_batch_async(
        self,
        values: List[float],
        feature_name: str = "default",
        update_stats: bool = True,
    ) -> List[NormalizationResult]:
        """
        Async batch normalization.

        Args:
            values: Values to normalize
            feature_name: Feature name for statistics
            update_stats: Whether to update rolling statistics

        Returns:
            List of NormalizationResult
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.normalize_batch,
            values,
            feature_name,
            update_stats,
        )

    def get_stats(self, feature_name: str = "default") -> NormalizationStats:
        """Get current statistics for a feature."""
        return self.get_or_create_stats(feature_name).get_stats()

    def reset_stats(self, feature_name: str = None) -> None:
        """Reset statistics for a feature or all features."""
        if feature_name:
            if feature_name in self._stats:
                self._stats[feature_name].reset()
        else:
            for stats in self._stats.values():
                stats.reset()
            self._default_stats.reset()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        with self._perf_lock:
            avg_latency = (
                self._total_latency_ms / self._total_normalizations
                if self._total_normalizations > 0
                else 0.0
            )
            breach_rate = (
                self._latency_breaches / self._total_normalizations * 100
                if self._total_normalizations > 0
                else 0.0
            )

            return {
                'total_normalizations': self._total_normalizations,
                'avg_latency_ms': round(avg_latency, 3),
                'max_latency_ms': round(self._max_latency_ms, 3),
                'target_latency_ms': self.config.target_latency_ms,
                'latency_breaches': self._latency_breaches,
                'breach_rate_pct': round(breach_rate, 2),
                'features_tracked': len(self._stats),
            }

    def __del__(self):
        """Cleanup thread pool on destruction."""
        self._executor.shutdown(wait=False)


# =============================================================================
# MULTI-FEATURE NORMALIZER
# =============================================================================

class MultiFeatureNormalizer:
    """
    Normalizer for handling multiple features with different configurations.

    Usage:
        normalizer = MultiFeatureNormalizer()
        normalizer.configure_feature('price', NormalizationConfig(
            method=NormalizationMethod.ROBUST,
            window_size=200,
        ))
        normalizer.configure_feature('volume', NormalizationConfig(
            method=NormalizationMethod.ZSCORE,
            window_size=50,
        ))

        results = normalizer.normalize_features({
            'price': 100.5,
            'volume': 1000000,
        })
    """

    def __init__(self, default_config: NormalizationConfig = None):
        self.default_config = default_config or NormalizationConfig()
        self._normalizers: Dict[str, DataNormalizer] = {}
        self._lock = threading.Lock()

    def configure_feature(
        self,
        feature_name: str,
        config: NormalizationConfig,
    ) -> None:
        """Configure normalization for a specific feature."""
        with self._lock:
            self._normalizers[feature_name] = DataNormalizer(config)
            logger.debug(f"Configured feature '{feature_name}' with {config.method.value}")

    def get_normalizer(self, feature_name: str) -> DataNormalizer:
        """Get or create normalizer for a feature."""
        with self._lock:
            if feature_name not in self._normalizers:
                self._normalizers[feature_name] = DataNormalizer(self.default_config)
            return self._normalizers[feature_name]

    def normalize_features(
        self,
        features: Dict[str, float],
        update_stats: bool = True,
    ) -> Dict[str, NormalizationResult]:
        """
        Normalize multiple features at once.

        Args:
            features: Dict of feature_name -> value
            update_stats: Whether to update rolling statistics

        Returns:
            Dict of feature_name -> NormalizationResult
        """
        results = {}
        for name, value in features.items():
            normalizer = self.get_normalizer(name)
            results[name] = normalizer.normalize(value, name, update_stats)
        return results

    async def normalize_features_async(
        self,
        features: Dict[str, float],
        update_stats: bool = True,
    ) -> Dict[str, NormalizationResult]:
        """
        Async normalization of multiple features.

        Args:
            features: Dict of feature_name -> value
            update_stats: Whether to update rolling statistics

        Returns:
            Dict of feature_name -> NormalizationResult
        """
        tasks = []
        names = []

        for name, value in features.items():
            normalizer = self.get_normalizer(name)
            tasks.append(normalizer.normalize_async(value, name, update_stats))
            names.append(name)

        results = await asyncio.gather(*tasks)
        return dict(zip(names, results))

    def get_all_stats(self) -> Dict[str, NormalizationStats]:
        """Get statistics for all features."""
        return {
            name: normalizer.get_stats(name)
            for name, normalizer in self._normalizers.items()
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get combined performance metrics."""
        summary = {
            'features': {},
            'total_normalizations': 0,
            'total_latency_breaches': 0,
        }

        for name, normalizer in self._normalizers.items():
            metrics = normalizer.get_performance_metrics()
            summary['features'][name] = metrics
            summary['total_normalizations'] += metrics['total_normalizations']
            summary['total_latency_breaches'] += metrics['latency_breaches']

        return summary


# =============================================================================
# STREAMING NORMALIZER (PIPELINE INTEGRATION)
# =============================================================================

T = TypeVar('T')


class StreamingNormalizer(Generic[T]):
    """
    Streaming normalizer for integration with data pipelines.

    Provides a callback-based interface for processing data streams
    with configurable buffering and batching.

    Usage:
        async def process_normalized(result: NormalizationResult):
            # Handle normalized data
            pass

        stream = StreamingNormalizer(
            on_normalized=process_normalized,
            buffer_size=10,
        )

        # In your data pipeline:
        await stream.push(42.5, 'price')
    """

    def __init__(
        self,
        config: NormalizationConfig = None,
        on_normalized: Optional[Callable[[NormalizationResult], Coroutine]] = None,
        buffer_size: int = 1,
        flush_interval_ms: float = 50.0,
    ):
        self.config = config or NormalizationConfig()
        self.on_normalized = on_normalized
        self.buffer_size = buffer_size
        self.flush_interval_ms = flush_interval_ms

        self._normalizer = DataNormalizer(self.config)
        self._buffer: List[Tuple[float, str]] = []
        self._buffer_lock = asyncio.Lock()
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the streaming normalizer."""
        self._running = True
        if self.flush_interval_ms > 0 and self.buffer_size > 1:
            self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("StreamingNormalizer started")

    async def stop(self) -> None:
        """Stop the streaming normalizer and flush remaining data."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.flush()
        logger.info("StreamingNormalizer stopped")

    async def push(
        self,
        value: float,
        feature_name: str = "default",
    ) -> Optional[NormalizationResult]:
        """
        Push a value to the normalizer.

        If buffer_size is 1, normalizes immediately and returns result.
        Otherwise, buffers and returns None (results delivered via callback).

        Args:
            value: Value to normalize
            feature_name: Feature name

        Returns:
            NormalizationResult if immediate mode, None if buffered
        """
        if self.buffer_size <= 1:
            # Immediate mode
            result = await self._normalizer.normalize_async(
                value, feature_name, update_stats=True
            )
            if self.on_normalized:
                await self.on_normalized(result)
            return result

        # Buffered mode
        async with self._buffer_lock:
            self._buffer.append((value, feature_name))

            if len(self._buffer) >= self.buffer_size:
                await self._flush_internal()

        return None

    async def flush(self) -> List[NormalizationResult]:
        """Flush the buffer and return all results."""
        async with self._buffer_lock:
            return await self._flush_internal()

    async def _flush_internal(self) -> List[NormalizationResult]:
        """Internal flush without lock."""
        if not self._buffer:
            return []

        results = []
        for value, feature_name in self._buffer:
            result = await self._normalizer.normalize_async(
                value, feature_name, update_stats=True
            )
            results.append(result)

            if self.on_normalized:
                await self.on_normalized(result)

        self._buffer.clear()
        return results

    async def _periodic_flush(self) -> None:
        """Periodically flush the buffer."""
        while self._running:
            await asyncio.sleep(self.flush_interval_ms / 1000)
            await self.flush()

    def get_stats(self, feature_name: str = "default") -> NormalizationStats:
        """Get statistics for a feature."""
        return self._normalizer.get_stats(feature_name)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return self._normalizer.get_performance_metrics()


# =============================================================================
# PIPELINE INTEGRATION ADAPTER
# =============================================================================

class NormalizationPipelineAdapter:
    """
    Adapter for integrating normalization into the data pipeline.

    Provides a standardized interface for normalizing market data
    before feature computation or model inference.

    Usage:
        adapter = NormalizationPipelineAdapter(
            fields=['close', 'volume', 'high', 'low'],
            config=NormalizationConfig(method=NormalizationMethod.ROBUST),
        )

        # Process market data
        normalized_data = adapter.process_bar(bar_data)
    """

    def __init__(
        self,
        fields: List[str] = None,
        config: NormalizationConfig = None,
        field_configs: Dict[str, NormalizationConfig] = None,
    ):
        """
        Initialize the adapter.

        Args:
            fields: List of field names to normalize
            config: Default configuration for all fields
            field_configs: Per-field configurations (overrides default)
        """
        self.fields = fields or ['close', 'high', 'low', 'open', 'volume']
        self.config = config or NormalizationConfig()
        self.field_configs = field_configs or {}

        # Create multi-feature normalizer
        self._normalizer = MultiFeatureNormalizer(self.config)

        # Configure per-field
        for field, cfg in self.field_configs.items():
            self._normalizer.configure_feature(field, cfg)

        logger.info(f"NormalizationPipelineAdapter initialized for fields: {self.fields}")

    def process_bar(
        self,
        bar: Dict[str, float],
        update_stats: bool = True,
    ) -> Dict[str, float]:
        """
        Normalize a single bar of market data.

        Args:
            bar: Dict with OHLCV data
            update_stats: Whether to update rolling statistics

        Returns:
            Dict with normalized values
        """
        # Extract fields to normalize
        to_normalize = {
            field: bar[field]
            for field in self.fields
            if field in bar
        }

        # Normalize
        results = self._normalizer.normalize_features(to_normalize, update_stats)

        # Build output
        normalized_bar = bar.copy()
        for field, result in results.items():
            normalized_bar[f'{field}_normalized'] = result.normalized_value

        return normalized_bar

    async def process_bar_async(
        self,
        bar: Dict[str, float],
        update_stats: bool = True,
    ) -> Dict[str, float]:
        """
        Async version of process_bar.

        Args:
            bar: Dict with OHLCV data
            update_stats: Whether to update rolling statistics

        Returns:
            Dict with normalized values
        """
        to_normalize = {
            field: bar[field]
            for field in self.fields
            if field in bar
        }

        results = await self._normalizer.normalize_features_async(
            to_normalize, update_stats
        )

        normalized_bar = bar.copy()
        for field, result in results.items():
            normalized_bar[f'{field}_normalized'] = result.normalized_value

        return normalized_bar

    def process_dataframe(
        self,
        df: "pd.DataFrame",
        update_stats: bool = True,
    ) -> "pd.DataFrame":
        """
        Normalize a pandas DataFrame.

        Args:
            df: DataFrame with market data
            update_stats: Whether to update rolling statistics

        Returns:
            DataFrame with additional normalized columns
        """
        import pandas as pd

        result_df = df.copy()

        for field in self.fields:
            if field not in df.columns:
                continue

            values = df[field].values
            normalizer = self._normalizer.get_normalizer(field)

            # Use vectorized normalization
            normalized = normalizer.normalize_array(
                values.astype(np.float64),
                field,
                update_stats,
            )

            result_df[f'{field}_normalized'] = normalized

        return result_df

    def get_stats(self) -> Dict[str, NormalizationStats]:
        """Get statistics for all fields."""
        return self._normalizer.get_all_stats()

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        return self._normalizer.get_performance_summary()


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_price_normalizer(
    window_size: int = 100,
    method: NormalizationMethod = NormalizationMethod.ROBUST,
) -> DataNormalizer:
    """
    Create a normalizer optimized for price data.

    Uses robust scaling (median/IQR) by default as it's less
    sensitive to outliers common in price data.

    Args:
        window_size: Rolling window size
        method: Normalization method

    Returns:
        Configured DataNormalizer
    """
    return DataNormalizer(NormalizationConfig(
        method=method,
        window_type=WindowType.FIXED,
        window_size=window_size,
        clip_min=-10.0,
        clip_max=10.0,
    ))


def create_volume_normalizer(
    window_size: int = 50,
    method: NormalizationMethod = NormalizationMethod.ZSCORE,
) -> DataNormalizer:
    """
    Create a normalizer optimized for volume data.

    Uses z-score by default with shorter window as volume
    tends to be more variable.

    Args:
        window_size: Rolling window size
        method: Normalization method

    Returns:
        Configured DataNormalizer
    """
    return DataNormalizer(NormalizationConfig(
        method=method,
        window_type=WindowType.EXPONENTIAL,
        window_size=window_size,
        alpha=0.2,  # Higher alpha for faster adaptation
        clip_min=-5.0,
        clip_max=10.0,  # Allow larger positive spikes
    ))


def create_returns_normalizer(
    window_size: int = 100,
) -> DataNormalizer:
    """
    Create a normalizer optimized for return data.

    Uses z-score with expanding window for returns which
    are typically stationary.

    Args:
        window_size: Rolling window size

    Returns:
        Configured DataNormalizer
    """
    return DataNormalizer(NormalizationConfig(
        method=NormalizationMethod.ZSCORE,
        window_type=WindowType.FIXED,
        window_size=window_size,
        clip_min=-4.0,
        clip_max=4.0,
    ))


def create_pipeline_adapter(
    price_window: int = 100,
    volume_window: int = 50,
) -> NormalizationPipelineAdapter:
    """
    Create a pre-configured pipeline adapter for market data.

    Args:
        price_window: Window size for price fields
        volume_window: Window size for volume field

    Returns:
        Configured NormalizationPipelineAdapter
    """
    return NormalizationPipelineAdapter(
        fields=['close', 'high', 'low', 'open', 'volume'],
        field_configs={
            'close': NormalizationConfig(
                method=NormalizationMethod.ROBUST,
                window_size=price_window,
            ),
            'high': NormalizationConfig(
                method=NormalizationMethod.ROBUST,
                window_size=price_window,
            ),
            'low': NormalizationConfig(
                method=NormalizationMethod.ROBUST,
                window_size=price_window,
            ),
            'open': NormalizationConfig(
                method=NormalizationMethod.ROBUST,
                window_size=price_window,
            ),
            'volume': NormalizationConfig(
                method=NormalizationMethod.ZSCORE,
                window_type=WindowType.EXPONENTIAL,
                window_size=volume_window,
                alpha=0.2,
            ),
        },
    )
