"""
QUANT_INDUSTRY_V1 Real-Time Data Normalization

Streaming normalization pipeline for market data:
- Online statistics (running mean/std)
- Z-score normalization with decay
- Min-max scaling with adaptive bounds
- Outlier clipping
- Feature-specific normalization

Target: All input data normalized within 50ms of streaming.

Rollback Plan: Delete this file
Tests Required: Online stats accuracy, latency benchmarks
Failure Modes: Return raw data with warning, alert operators
"""

import time
import logging
import threading
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# NORMALIZATION TYPES
# =============================================================================

class NormalizationMethod(Enum):
    """Supported normalization methods."""
    ZSCORE = "zscore"           # (x - mean) / std
    MINMAX = "minmax"           # (x - min) / (max - min)
    ROBUST = "robust"           # (x - median) / IQR
    LOG = "log"                 # log(1 + x) for positive values
    RANK = "rank"               # Percentile rank
    NONE = "none"               # Passthrough


@dataclass
class NormalizationConfig:
    """Configuration for a feature's normalization."""
    method: NormalizationMethod = NormalizationMethod.ZSCORE
    clip_outliers: bool = True
    clip_sigma: float = 3.0           # Clip at N standard deviations
    decay_factor: float = 0.99        # Exponential decay for online stats
    warmup_samples: int = 100         # Minimum samples before normalizing
    adaptive_bounds: bool = True      # Update min/max dynamically
    log_transform_first: bool = False # Apply log before normalization


@dataclass
class OnlineStats:
    """
    Online/streaming statistics using Welford's algorithm.
    
    Maintains running mean, variance, min, max with exponential decay.
    """
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0  # Sum of squared differences
    min_val: float = float('inf')
    max_val: float = float('-inf')
    decay_factor: float = 0.99
    
    # For robust statistics
    recent_values: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    @property
    def variance(self) -> float:
        """Get current variance estimate."""
        if self.count < 2:
            return 1.0
        return self.m2 / (self.count - 1)
    
    @property
    def std(self) -> float:
        """Get current standard deviation estimate."""
        return math.sqrt(max(self.variance, 1e-10))
    
    @property
    def median(self) -> float:
        """Get approximate median from recent values."""
        if not self.recent_values:
            return self.mean
        sorted_vals = sorted(self.recent_values)
        n = len(sorted_vals)
        return sorted_vals[n // 2]
    
    @property
    def iqr(self) -> float:
        """Get interquartile range from recent values."""
        if len(self.recent_values) < 4:
            return self.std * 1.35  # Approximate
        sorted_vals = sorted(self.recent_values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        return max(q3 - q1, 1e-10)
    
    def update(self, value: float) -> None:
        """Update statistics with new value using Welford's algorithm with decay."""
        self.count += 1
        self.recent_values.append(value)
        
        # Apply decay to existing stats
        if self.count > 1:
            self.m2 *= self.decay_factor
            
        # Welford's online algorithm
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2
        
        # Update bounds
        self.min_val = min(self.min_val, value)
        self.max_val = max(self.max_val, value)
    
    def update_batch(self, values: np.ndarray) -> None:
        """Update statistics with batch of values."""
        for v in values:
            self.update(float(v))


# =============================================================================
# NORMALIZERS
# =============================================================================

class StreamingNormalizer(ABC):
    """Base class for streaming normalizers."""
    
    @abstractmethod
    def normalize(self, value: float) -> float:
        """Normalize a single value."""
        pass
    
    @abstractmethod
    def normalize_batch(self, values: np.ndarray) -> np.ndarray:
        """Normalize a batch of values."""
        pass
    
    @abstractmethod
    def update(self, value: float) -> None:
        """Update normalizer state with new value."""
        pass
    
    @abstractmethod
    def inverse_normalize(self, value: float) -> float:
        """Convert normalized value back to original scale."""
        pass


class ZScoreNormalizer(StreamingNormalizer):
    """Online Z-score normalization with exponential decay."""
    
    def __init__(self, config: NormalizationConfig = None):
        self.config = config or NormalizationConfig()
        self.stats = OnlineStats(decay_factor=self.config.decay_factor)
        self._lock = threading.Lock()
    
    def normalize(self, value: float) -> float:
        """Normalize single value to Z-score."""
        with self._lock:
            self.stats.update(value)
            
            if self.stats.count < self.config.warmup_samples:
                return 0.0  # Return neutral during warmup
                
            z = (value - self.stats.mean) / self.stats.std
            
            if self.config.clip_outliers:
                z = np.clip(z, -self.config.clip_sigma, self.config.clip_sigma)
                
            return float(z)
    
    def normalize_batch(self, values: np.ndarray) -> np.ndarray:
        """Normalize batch of values."""
        return np.array([self.normalize(v) for v in values])
    
    def update(self, value: float) -> None:
        """Update statistics without normalizing."""
        with self._lock:
            self.stats.update(value)
    
    def inverse_normalize(self, value: float) -> float:
        """Convert Z-score back to original scale."""
        with self._lock:
            return value * self.stats.std + self.stats.mean


class MinMaxNormalizer(StreamingNormalizer):
    """Online min-max normalization with adaptive bounds."""
    
    def __init__(self, config: NormalizationConfig = None, target_min: float = 0.0, target_max: float = 1.0):
        self.config = config or NormalizationConfig()
        self.stats = OnlineStats(decay_factor=self.config.decay_factor)
        self.target_min = target_min
        self.target_max = target_max
        self._lock = threading.Lock()
        
        # Adaptive bounds with decay
        self._running_min = float('inf')
        self._running_max = float('-inf')
    
    def normalize(self, value: float) -> float:
        """Normalize value to [target_min, target_max] range."""
        with self._lock:
            self.stats.update(value)
            
            if self.config.adaptive_bounds:
                # Decay bounds slowly toward current value
                alpha = 0.001
                self._running_min = min(self._running_min, value)
                self._running_max = max(self._running_max, value)
                # Gentle decay to prevent bounds from getting stuck
                self._running_min += alpha * (value - self._running_min)
                self._running_max += alpha * (value - self._running_max)
                min_val = self._running_min
                max_val = self._running_max
            else:
                min_val = self.stats.min_val
                max_val = self.stats.max_val
                
            if self.stats.count < self.config.warmup_samples:
                return (self.target_min + self.target_max) / 2
                
            range_val = max_val - min_val
            if range_val < 1e-10:
                return (self.target_min + self.target_max) / 2
                
            normalized = (value - min_val) / range_val
            scaled = normalized * (self.target_max - self.target_min) + self.target_min
            
            return float(np.clip(scaled, self.target_min, self.target_max))
    
    def normalize_batch(self, values: np.ndarray) -> np.ndarray:
        """Normalize batch of values."""
        return np.array([self.normalize(v) for v in values])
    
    def update(self, value: float) -> None:
        """Update statistics without normalizing."""
        with self._lock:
            self.stats.update(value)
            if self.config.adaptive_bounds:
                self._running_min = min(self._running_min, value)
                self._running_max = max(self._running_max, value)
    
    def inverse_normalize(self, value: float) -> float:
        """Convert normalized value back to original scale."""
        with self._lock:
            min_val = self._running_min if self.config.adaptive_bounds else self.stats.min_val
            max_val = self._running_max if self.config.adaptive_bounds else self.stats.max_val
            range_val = max_val - min_val
            
            descaled = (value - self.target_min) / (self.target_max - self.target_min)
            return descaled * range_val + min_val


class RobustNormalizer(StreamingNormalizer):
    """Robust normalization using median and IQR (outlier resistant)."""
    
    def __init__(self, config: NormalizationConfig = None):
        self.config = config or NormalizationConfig()
        self.stats = OnlineStats(decay_factor=self.config.decay_factor)
        self._lock = threading.Lock()
    
    def normalize(self, value: float) -> float:
        """Normalize using robust statistics (median, IQR)."""
        with self._lock:
            self.stats.update(value)
            
            if self.stats.count < self.config.warmup_samples:
                return 0.0
                
            normalized = (value - self.stats.median) / self.stats.iqr
            
            if self.config.clip_outliers:
                normalized = np.clip(normalized, -self.config.clip_sigma, self.config.clip_sigma)
                
            return float(normalized)
    
    def normalize_batch(self, values: np.ndarray) -> np.ndarray:
        """Normalize batch of values."""
        return np.array([self.normalize(v) for v in values])
    
    def update(self, value: float) -> None:
        """Update statistics without normalizing."""
        with self._lock:
            self.stats.update(value)
    
    def inverse_normalize(self, value: float) -> float:
        """Convert normalized value back to original scale."""
        with self._lock:
            return value * self.stats.iqr + self.stats.median


# =============================================================================
# STREAMING NORMALIZATION PIPELINE
# =============================================================================

class StreamingNormalizationPipeline:
    """
    Real-time data normalization pipeline.
    
    Features:
    - Per-feature normalization configuration
    - Online statistics with exponential decay
    - Latency monitoring (<50ms target)
    - Batch and streaming support
    - Thread-safe operations
    """
    
    def __init__(self, default_method: NormalizationMethod = NormalizationMethod.ZSCORE):
        self.default_method = default_method
        self._normalizers: Dict[str, StreamingNormalizer] = {}
        self._configs: Dict[str, NormalizationConfig] = {}
        self._lock = threading.RLock()
        
        # Latency tracking
        self._latencies: deque = deque(maxlen=1000)
        self._latency_violations = 0
        self._total_processed = 0
        
        logger.info(f"StreamingNormalizationPipeline initialized with default method: {default_method}")
    
    def configure_feature(self, feature_name: str, config: NormalizationConfig) -> None:
        """Configure normalization for a specific feature."""
        with self._lock:
            self._configs[feature_name] = config
            self._normalizers[feature_name] = self._create_normalizer(config)
            
        logger.debug(f"Configured normalization for {feature_name}: {config.method}")
    
    def _create_normalizer(self, config: NormalizationConfig) -> StreamingNormalizer:
        """Create normalizer based on config."""
        if config.method == NormalizationMethod.ZSCORE:
            return ZScoreNormalizer(config)
        elif config.method == NormalizationMethod.MINMAX:
            return MinMaxNormalizer(config)
        elif config.method == NormalizationMethod.ROBUST:
            return RobustNormalizer(config)
        else:
            # Passthrough normalizer
            return ZScoreNormalizer(NormalizationConfig(method=NormalizationMethod.NONE))
    
    def _get_normalizer(self, feature_name: str) -> StreamingNormalizer:
        """Get or create normalizer for feature."""
        if feature_name not in self._normalizers:
            config = self._configs.get(feature_name, NormalizationConfig(method=self.default_method))
            self._normalizers[feature_name] = self._create_normalizer(config)
        return self._normalizers[feature_name]
    
    def normalize(self, data: Dict[str, float]) -> Tuple[Dict[str, float], float]:
        """
        Normalize a single data point (streaming).
        
        Args:
            data: Dictionary of feature_name -> raw value
            
        Returns:
            Tuple of (normalized_data, latency_ms)
        """
        start = time.perf_counter()
        
        normalized = {}
        with self._lock:
            for feature_name, value in data.items():
                if value is None:
                    normalized[feature_name] = None
                    continue
                    
                normalizer = self._get_normalizer(feature_name)
                config = self._configs.get(feature_name, NormalizationConfig())
                
                # Optional log transform first
                if config.log_transform_first and value > 0:
                    value = math.log1p(value)
                    
                normalized[feature_name] = normalizer.normalize(value)
                
        latency_ms = (time.perf_counter() - start) * 1000
        
        # Track latency
        self._latencies.append(latency_ms)
        self._total_processed += 1
        if latency_ms > 50:
            self._latency_violations += 1
            logger.warning(f"Normalization latency exceeded 50ms: {latency_ms:.2f}ms")
            
        return normalized, latency_ms
    
    def normalize_batch(
        self, 
        data: Dict[str, np.ndarray],
        update_stats: bool = True
    ) -> Tuple[Dict[str, np.ndarray], float]:
        """
        Normalize a batch of data.
        
        Args:
            data: Dictionary of feature_name -> array of values
            update_stats: Whether to update running statistics
            
        Returns:
            Tuple of (normalized_data, latency_ms)
        """
        start = time.perf_counter()
        
        normalized = {}
        with self._lock:
            for feature_name, values in data.items():
                if values is None or len(values) == 0:
                    normalized[feature_name] = values
                    continue
                    
                normalizer = self._get_normalizer(feature_name)
                config = self._configs.get(feature_name, NormalizationConfig())
                
                # Optional log transform
                if config.log_transform_first:
                    values = np.log1p(np.maximum(values, 0))
                    
                normalized[feature_name] = normalizer.normalize_batch(values)
                
        latency_ms = (time.perf_counter() - start) * 1000
        self._latencies.append(latency_ms)
        
        return normalized, latency_ms
    
    def inverse_normalize(self, data: Dict[str, float]) -> Dict[str, float]:
        """Convert normalized values back to original scale."""
        original = {}
        with self._lock:
            for feature_name, value in data.items():
                if value is None:
                    original[feature_name] = None
                    continue
                    
                if feature_name in self._normalizers:
                    original[feature_name] = self._normalizers[feature_name].inverse_normalize(value)
                else:
                    original[feature_name] = value
                    
        return original
    
    def update_statistics(self, data: Dict[str, float]) -> None:
        """Update running statistics without normalizing."""
        with self._lock:
            for feature_name, value in data.items():
                if value is not None:
                    normalizer = self._get_normalizer(feature_name)
                    normalizer.update(value)
    
    def get_statistics(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get current statistics for a feature."""
        with self._lock:
            if feature_name not in self._normalizers:
                return None
                
            normalizer = self._normalizers[feature_name]
            stats = normalizer.stats
            
            return {
                'count': stats.count,
                'mean': stats.mean,
                'std': stats.std,
                'min': stats.min_val,
                'max': stats.max_val,
                'median': stats.median,
                'iqr': stats.iqr,
            }
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline performance statistics."""
        latencies = list(self._latencies)
        
        return {
            'total_processed': self._total_processed,
            'latency_violations': self._latency_violations,
            'violation_rate': self._latency_violations / max(1, self._total_processed),
            'avg_latency_ms': np.mean(latencies) if latencies else 0,
            'p50_latency_ms': np.percentile(latencies, 50) if latencies else 0,
            'p99_latency_ms': np.percentile(latencies, 99) if latencies else 0,
            'max_latency_ms': max(latencies) if latencies else 0,
            'configured_features': len(self._configs),
            'active_normalizers': len(self._normalizers),
        }
    
    def reset(self, feature_name: str = None) -> None:
        """Reset normalizer state."""
        with self._lock:
            if feature_name:
                if feature_name in self._normalizers:
                    config = self._configs.get(feature_name, NormalizationConfig())
                    self._normalizers[feature_name] = self._create_normalizer(config)
            else:
                for name in list(self._normalizers.keys()):
                    config = self._configs.get(name, NormalizationConfig())
                    self._normalizers[name] = self._create_normalizer(config)


# =============================================================================
# CONVENIENCE FUNCTIONS  
# =============================================================================

def create_market_data_normalizer() -> StreamingNormalizationPipeline:
    """Create normalizer pre-configured for common market data features."""
    pipeline = StreamingNormalizationPipeline()
    
    # Price features - use robust normalization
    price_config = NormalizationConfig(
        method=NormalizationMethod.ROBUST,
        clip_outliers=True,
        clip_sigma=4.0,
        warmup_samples=50
    )
    for feature in ['price', 'open', 'high', 'low', 'close', 'vwap']:
        pipeline.configure_feature(feature, price_config)
    
    # Volume features - log transform + z-score
    volume_config = NormalizationConfig(
        method=NormalizationMethod.ZSCORE,
        log_transform_first=True,
        clip_outliers=True,
        clip_sigma=3.0
    )
    for feature in ['volume', 'dollar_volume', 'trade_count']:
        pipeline.configure_feature(feature, volume_config)
    
    # Returns - z-score with tight clipping
    returns_config = NormalizationConfig(
        method=NormalizationMethod.ZSCORE,
        clip_outliers=True,
        clip_sigma=3.0,
        decay_factor=0.995
    )
    for feature in ['return', 'return_1m', 'return_5m', 'return_1h', 'return_1d']:
        pipeline.configure_feature(feature, returns_config)
    
    # Volatility - minmax to [0, 1]
    vol_config = NormalizationConfig(
        method=NormalizationMethod.MINMAX,
        adaptive_bounds=True
    )
    for feature in ['volatility', 'atr', 'realized_vol']:
        pipeline.configure_feature(feature, vol_config)
    
    # Indicators - z-score 
    indicator_config = NormalizationConfig(
        method=NormalizationMethod.ZSCORE,
        clip_outliers=True,
        clip_sigma=3.0
    )
    for feature in ['rsi', 'macd', 'momentum', 'mfi']:
        pipeline.configure_feature(feature, indicator_config)
    
    return pipeline
