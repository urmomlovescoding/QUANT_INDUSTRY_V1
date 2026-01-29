"""
Automated Feature Engineering
QUANT_INDUSTRY_V1 - P2 Enhancement

Implements automated feature generation patterns inspired by Featuretools:
- Time-based aggregations
- Rolling statistics
- Lag features
- Cross-feature interactions
- Technical indicators as features

Reduces manual feature engineering time and discovers important features.

Rollback Plan: Delete this file, use manual feature engineering
Tests Required: Feature generation, transformation consistency
Failure Modes: Fall back to manual features, log warnings
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE TYPES
# =============================================================================

class FeatureType(Enum):
    """Types of features that can be generated."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    DERIVED = "derived"


class AggregationType(Enum):
    """Aggregation primitives for feature generation."""
    MEAN = "mean"
    STD = "std"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    COUNT = "count"
    MEDIAN = "median"
    SKEW = "skew"
    KURTOSIS = "kurtosis"
    FIRST = "first"
    LAST = "last"
    TREND = "trend"  # Linear regression slope
    PERCENTILE_25 = "percentile_25"
    PERCENTILE_75 = "percentile_75"


@dataclass
class FeatureDefinition:
    """Definition of a generated feature."""
    name: str
    feature_type: FeatureType
    source_columns: List[str]
    aggregation: Optional[AggregationType] = None
    window: Optional[int] = None
    lag: Optional[int] = None
    transform: Optional[str] = None
    description: str = ""
    importance: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'feature_type': self.feature_type.value,
            'source_columns': self.source_columns,
            'aggregation': self.aggregation.value if self.aggregation else None,
            'window': self.window,
            'lag': self.lag,
            'transform': self.transform,
            'description': self.description,
            'importance': self.importance,
        }


@dataclass
class FeatureSet:
    """Collection of features for a dataset."""
    features: List[FeatureDefinition] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_data_hash: str = ""
    
    def add(self, feature: FeatureDefinition) -> None:
        self.features.append(feature)
    
    def get_feature_names(self) -> List[str]:
        return [f.name for f in self.features]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'features': [f.to_dict() for f in self.features],
            'created_at': self.created_at.isoformat(),
            'num_features': len(self.features),
        }


# =============================================================================
# AGGREGATION FUNCTIONS
# =============================================================================

class AggregationFunctions:
    """Collection of aggregation primitives."""
    
    @staticmethod
    def mean(arr: np.ndarray) -> float:
        return float(np.nanmean(arr)) if len(arr) > 0 else np.nan
    
    @staticmethod
    def std(arr: np.ndarray) -> float:
        return float(np.nanstd(arr)) if len(arr) > 1 else np.nan
    
    @staticmethod
    def min(arr: np.ndarray) -> float:
        return float(np.nanmin(arr)) if len(arr) > 0 else np.nan
    
    @staticmethod
    def max(arr: np.ndarray) -> float:
        return float(np.nanmax(arr)) if len(arr) > 0 else np.nan
    
    @staticmethod
    def sum(arr: np.ndarray) -> float:
        return float(np.nansum(arr)) if len(arr) > 0 else np.nan
    
    @staticmethod
    def count(arr: np.ndarray) -> float:
        return float(np.count_nonzero(~np.isnan(arr)))
    
    @staticmethod
    def median(arr: np.ndarray) -> float:
        return float(np.nanmedian(arr)) if len(arr) > 0 else np.nan
    
    @staticmethod
    def skew(arr: np.ndarray) -> float:
        if len(arr) < 3:
            return np.nan
        mean = np.nanmean(arr)
        std = np.nanstd(arr)
        if std < 1e-8:
            return 0.0
        return float(np.nanmean(((arr - mean) / std) ** 3))
    
    @staticmethod
    def kurtosis(arr: np.ndarray) -> float:
        if len(arr) < 4:
            return np.nan
        mean = np.nanmean(arr)
        std = np.nanstd(arr)
        if std < 1e-8:
            return 0.0
        return float(np.nanmean(((arr - mean) / std) ** 4) - 3)
    
    @staticmethod
    def first(arr: np.ndarray) -> float:
        if len(arr) == 0:
            return np.nan
        for v in arr:
            if not np.isnan(v):
                return float(v)
        return np.nan
    
    @staticmethod
    def last(arr: np.ndarray) -> float:
        if len(arr) == 0:
            return np.nan
        for v in reversed(arr):
            if not np.isnan(v):
                return float(v)
        return np.nan
    
    @staticmethod
    def trend(arr: np.ndarray) -> float:
        """Linear regression slope."""
        if len(arr) < 2:
            return np.nan
        valid = ~np.isnan(arr)
        if np.sum(valid) < 2:
            return np.nan
        x = np.arange(len(arr))[valid]
        y = arr[valid]
        # Simple linear regression slope
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)
        if denominator < 1e-8:
            return 0.0
        return float(numerator / denominator)
    
    @staticmethod
    def percentile_25(arr: np.ndarray) -> float:
        return float(np.nanpercentile(arr, 25)) if len(arr) > 0 else np.nan
    
    @staticmethod
    def percentile_75(arr: np.ndarray) -> float:
        return float(np.nanpercentile(arr, 75)) if len(arr) > 0 else np.nan
    
    @classmethod
    def get_function(cls, agg_type: AggregationType) -> Callable:
        """Get aggregation function by type."""
        mapping = {
            AggregationType.MEAN: cls.mean,
            AggregationType.STD: cls.std,
            AggregationType.MIN: cls.min,
            AggregationType.MAX: cls.max,
            AggregationType.SUM: cls.sum,
            AggregationType.COUNT: cls.count,
            AggregationType.MEDIAN: cls.median,
            AggregationType.SKEW: cls.skew,
            AggregationType.KURTOSIS: cls.kurtosis,
            AggregationType.FIRST: cls.first,
            AggregationType.LAST: cls.last,
            AggregationType.TREND: cls.trend,
            AggregationType.PERCENTILE_25: cls.percentile_25,
            AggregationType.PERCENTILE_75: cls.percentile_75,
        }
        return mapping.get(agg_type, cls.mean)


# =============================================================================
# AUTOMATED FEATURE ENGINEER
# =============================================================================

class AutoFeatureEngineer:
    """
    Automated feature engineering for financial time series.
    
    Generates features using Featuretools-inspired patterns:
    - Rolling window aggregations
    - Lag features
    - Cross-feature interactions
    - Technical indicator features
    """
    
    # Default windows for rolling features
    DEFAULT_WINDOWS = [5, 10, 20, 50]
    
    # Default lags
    DEFAULT_LAGS = [1, 2, 5, 10, 20]
    
    # Default aggregations
    DEFAULT_AGGREGATIONS = [
        AggregationType.MEAN,
        AggregationType.STD,
        AggregationType.MIN,
        AggregationType.MAX,
        AggregationType.TREND,
    ]
    
    def __init__(
        self,
        windows: List[int] = None,
        lags: List[int] = None,
        aggregations: List[AggregationType] = None,
        include_interactions: bool = True,
        include_technical: bool = True,
        max_features: int = 500,
    ):
        self.windows = windows or self.DEFAULT_WINDOWS
        self.lags = lags or self.DEFAULT_LAGS
        self.aggregations = aggregations or self.DEFAULT_AGGREGATIONS
        self.include_interactions = include_interactions
        self.include_technical = include_technical
        self.max_features = max_features
        
        self.feature_set = FeatureSet()
        self._feature_cache: Dict[str, np.ndarray] = {}
        
        logger.info("AutoFeatureEngineer initialized")
    
    def fit_transform(
        self,
        data: Dict[str, np.ndarray],
        target: Optional[np.ndarray] = None,
    ) -> Tuple[Dict[str, np.ndarray], FeatureSet]:
        """
        Generate features from input data.
        
        Args:
            data: Dictionary of column_name -> numpy array
            target: Optional target variable for feature importance
            
        Returns:
            Tuple of (feature_dict, feature_set)
        """
        features = {}
        self.feature_set = FeatureSet()
        
        # 1. Generate lag features
        lag_features = self._generate_lag_features(data)
        features.update(lag_features)
        
        # 2. Generate rolling window features
        rolling_features = self._generate_rolling_features(data)
        features.update(rolling_features)
        
        # 3. Generate interaction features
        if self.include_interactions:
            interaction_features = self._generate_interaction_features(data)
            features.update(interaction_features)
        
        # 4. Generate technical indicator features
        if self.include_technical:
            technical_features = self._generate_technical_features(data)
            features.update(technical_features)
        
        # 5. Calculate feature importance if target provided
        if target is not None:
            self._calculate_importance(features, target)
        
        # 6. Limit features if needed
        if len(features) > self.max_features:
            features = self._select_top_features(features, self.max_features)
        
        logger.info(f"Generated {len(features)} features")
        
        return features, self.feature_set
    
    def _generate_lag_features(
        self,
        data: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Generate lag features for all columns."""
        features = {}
        
        for col_name, col_data in data.items():
            for lag in self.lags:
                feature_name = f"{col_name}_lag_{lag}"
                
                # Create lagged array
                lagged = np.full_like(col_data, np.nan, dtype=float)
                if lag < len(col_data):
                    lagged[lag:] = col_data[:-lag]
                
                features[feature_name] = lagged
                
                # Add feature definition
                self.feature_set.add(FeatureDefinition(
                    name=feature_name,
                    feature_type=FeatureType.TEMPORAL,
                    source_columns=[col_name],
                    lag=lag,
                    description=f"Lag {lag} of {col_name}",
                ))
        
        return features
    
    def _generate_rolling_features(
        self,
        data: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Generate rolling window aggregation features."""
        features = {}
        
        for col_name, col_data in data.items():
            col_data = np.asarray(col_data, dtype=float)
            n = len(col_data)
            
            for window in self.windows:
                if window >= n:
                    continue
                    
                for agg in self.aggregations:
                    feature_name = f"{col_name}_roll{window}_{agg.value}"
                    agg_func = AggregationFunctions.get_function(agg)
                    
                    # Apply rolling aggregation
                    result = np.full(n, np.nan)
                    for i in range(window - 1, n):
                        window_data = col_data[i - window + 1:i + 1]
                        result[i] = agg_func(window_data)
                    
                    features[feature_name] = result
                    
                    self.feature_set.add(FeatureDefinition(
                        name=feature_name,
                        feature_type=FeatureType.DERIVED,
                        source_columns=[col_name],
                        aggregation=agg,
                        window=window,
                        description=f"Rolling {agg.value} (window={window}) of {col_name}",
                    ))
        
        return features
    
    def _generate_interaction_features(
        self,
        data: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Generate cross-feature interaction features."""
        features = {}
        columns = list(data.keys())
        
        # Limit to avoid combinatorial explosion
        max_interactions = min(len(columns), 5)
        
        for i, col1 in enumerate(columns[:max_interactions]):
            for col2 in columns[i + 1:max_interactions]:
                data1 = np.asarray(data[col1], dtype=float)
                data2 = np.asarray(data[col2], dtype=float)
                
                # Ratio feature
                ratio_name = f"{col1}_div_{col2}"
                with np.errstate(divide='ignore', invalid='ignore'):
                    ratio = np.where(np.abs(data2) > 1e-8, data1 / data2, np.nan)
                features[ratio_name] = ratio
                
                self.feature_set.add(FeatureDefinition(
                    name=ratio_name,
                    feature_type=FeatureType.DERIVED,
                    source_columns=[col1, col2],
                    transform="divide",
                    description=f"Ratio of {col1} to {col2}",
                ))
                
                # Difference feature
                diff_name = f"{col1}_minus_{col2}"
                features[diff_name] = data1 - data2
                
                self.feature_set.add(FeatureDefinition(
                    name=diff_name,
                    feature_type=FeatureType.DERIVED,
                    source_columns=[col1, col2],
                    transform="subtract",
                    description=f"Difference of {col1} and {col2}",
                ))
                
                # Product feature (for momentum interactions)
                if 'volume' in col1.lower() or 'volume' in col2.lower():
                    prod_name = f"{col1}_times_{col2}"
                    features[prod_name] = data1 * data2
                    
                    self.feature_set.add(FeatureDefinition(
                        name=prod_name,
                        feature_type=FeatureType.DERIVED,
                        source_columns=[col1, col2],
                        transform="multiply",
                        description=f"Product of {col1} and {col2}",
                    ))
        
        return features
    
    def _generate_technical_features(
        self,
        data: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Generate technical indicator features."""
        features = {}
        
        # Need OHLCV data for technical indicators
        close = data.get('close', data.get('Close', None))
        high = data.get('high', data.get('High', None))
        low = data.get('low', data.get('Low', None))
        volume = data.get('volume', data.get('Volume', None))
        
        if close is None:
            return features
        
        close = np.asarray(close, dtype=float)
        n = len(close)
        
        # Returns
        returns = np.full(n, np.nan)
        returns[1:] = (close[1:] - close[:-1]) / close[:-1]
        features['returns'] = returns
        self.feature_set.add(FeatureDefinition(
            name='returns',
            feature_type=FeatureType.DERIVED,
            source_columns=['close'],
            transform='pct_change',
            description='Simple returns',
        ))
        
        # Log returns
        log_returns = np.full(n, np.nan)
        with np.errstate(divide='ignore', invalid='ignore'):
            log_returns[1:] = np.log(close[1:] / close[:-1])
        features['log_returns'] = log_returns
        self.feature_set.add(FeatureDefinition(
            name='log_returns',
            feature_type=FeatureType.DERIVED,
            source_columns=['close'],
            transform='log_pct_change',
            description='Log returns',
        ))
        
        # Volatility (rolling std of returns)
        for window in [5, 10, 20]:
            if window >= n:
                continue
            vol_name = f'volatility_{window}'
            vol = np.full(n, np.nan)
            for i in range(window, n):
                vol[i] = np.nanstd(returns[i - window + 1:i + 1]) * np.sqrt(252)
            features[vol_name] = vol
            self.feature_set.add(FeatureDefinition(
                name=vol_name,
                feature_type=FeatureType.DERIVED,
                source_columns=['close'],
                aggregation=AggregationType.STD,
                window=window,
                description=f'Annualized volatility (window={window})',
            ))
        
        # RSI
        for period in [7, 14, 21]:
            if period >= n:
                continue
            rsi_name = f'rsi_{period}'
            rsi = self._calculate_rsi(close, period)
            features[rsi_name] = rsi
            self.feature_set.add(FeatureDefinition(
                name=rsi_name,
                feature_type=FeatureType.DERIVED,
                source_columns=['close'],
                window=period,
                transform='rsi',
                description=f'RSI (period={period})',
            ))
        
        # MACD features
        macd, signal, hist = self._calculate_macd(close)
        features['macd'] = macd
        features['macd_signal'] = signal
        features['macd_histogram'] = hist
        for fname in ['macd', 'macd_signal', 'macd_histogram']:
            self.feature_set.add(FeatureDefinition(
                name=fname,
                feature_type=FeatureType.DERIVED,
                source_columns=['close'],
                transform='macd',
                description=f'MACD {fname}',
            ))
        
        # Bollinger Band features
        if high is not None and low is not None:
            high = np.asarray(high, dtype=float)
            low = np.asarray(low, dtype=float)
            
            # ATR
            for period in [14, 20]:
                if period >= n:
                    continue
                atr_name = f'atr_{period}'
                atr = self._calculate_atr(high, low, close, period)
                features[atr_name] = atr
                self.feature_set.add(FeatureDefinition(
                    name=atr_name,
                    feature_type=FeatureType.DERIVED,
                    source_columns=['high', 'low', 'close'],
                    window=period,
                    transform='atr',
                    description=f'ATR (period={period})',
                ))
        
        # Volume-based features
        if volume is not None:
            volume = np.asarray(volume, dtype=float)
            
            # Volume ratio
            for window in [5, 20]:
                if window >= n:
                    continue
                vol_ratio_name = f'volume_ratio_{window}'
                vol_ma = np.full(n, np.nan)
                for i in range(window - 1, n):
                    vol_ma[i] = np.nanmean(volume[i - window + 1:i + 1])
                vol_ratio = np.where(vol_ma > 0, volume / vol_ma, np.nan)
                features[vol_ratio_name] = vol_ratio
                self.feature_set.add(FeatureDefinition(
                    name=vol_ratio_name,
                    feature_type=FeatureType.DERIVED,
                    source_columns=['volume'],
                    window=window,
                    transform='volume_ratio',
                    description=f'Volume ratio to {window}-day average',
                ))
        
        return features
    
    def _calculate_rsi(self, close: np.ndarray, period: int) -> np.ndarray:
        """Calculate RSI."""
        n = len(close)
        rsi = np.full(n, np.nan)
        
        if n < period + 1:
            return rsi
        
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        if avg_loss == 0:
            rsi[period] = 100
        else:
            rsi[period] = 100 - (100 / (1 + avg_gain / avg_loss))
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi[i + 1] = 100
            else:
                rsi[i + 1] = 100 - (100 / (1 + avg_gain / avg_loss))
        
        return rsi
    
    def _calculate_macd(
        self,
        close: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate MACD."""
        n = len(close)
        
        def ema(data, period):
            result = np.full(n, np.nan)
            if n < period:
                return result
            multiplier = 2 / (period + 1)
            result[period - 1] = np.mean(data[:period])
            for i in range(period, n):
                result[i] = data[i] * multiplier + result[i - 1] * (1 - multiplier)
            return result
        
        ema_fast = ema(close, fast)
        ema_slow = ema(close, slow)
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = np.full(n, np.nan)
        valid_macd = macd_line[~np.isnan(macd_line)]
        if len(valid_macd) >= signal:
            sig_ema = ema(valid_macd, signal)
            start_idx = n - len(sig_ema)
            signal_line[start_idx:] = sig_ema
        
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int
    ) -> np.ndarray:
        """Calculate Average True Range."""
        n = len(close)
        atr = np.full(n, np.nan)
        
        if n < period + 1:
            return atr
        
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1])
            )
        
        for i in range(period - 1, n):
            atr[i] = np.mean(tr[i - period + 1:i + 1])
        
        return atr
    
    def _calculate_importance(
        self,
        features: Dict[str, np.ndarray],
        target: np.ndarray
    ) -> None:
        """Calculate feature importance using correlation with target."""
        target = np.asarray(target, dtype=float)
        
        for feature in self.feature_set.features:
            if feature.name not in features:
                continue
            
            feat_data = features[feature.name]
            
            # Use correlation as simple importance measure
            valid = ~(np.isnan(feat_data) | np.isnan(target))
            if np.sum(valid) < 10:
                continue
            
            corr = np.corrcoef(feat_data[valid], target[valid])[0, 1]
            feature.importance = abs(corr) if not np.isnan(corr) else 0.0
    
    def _select_top_features(
        self,
        features: Dict[str, np.ndarray],
        max_features: int
    ) -> Dict[str, np.ndarray]:
        """Select top features by importance."""
        # Sort by importance
        sorted_features = sorted(
            self.feature_set.features,
            key=lambda f: f.importance,
            reverse=True
        )
        
        # Keep top N
        top_names = set(f.name for f in sorted_features[:max_features])
        
        # Filter
        filtered = {k: v for k, v in features.items() if k in top_names}
        self.feature_set.features = [f for f in self.feature_set.features if f.name in top_names]
        
        return filtered
    
    def transform(
        self,
        data: Dict[str, np.ndarray],
    ) -> Dict[str, np.ndarray]:
        """
        Transform new data using the same feature definitions.
        
        Use after fit_transform to generate same features on new data.
        """
        if not self.feature_set.features:
            raise ValueError("Must call fit_transform first")
        
        features = {}
        
        for feat_def in self.feature_set.features:
            # Regenerate feature based on definition
            if feat_def.lag is not None:
                # Lag feature
                col = feat_def.source_columns[0]
                if col in data:
                    col_data = np.asarray(data[col], dtype=float)
                    lagged = np.full_like(col_data, np.nan)
                    if feat_def.lag < len(col_data):
                        lagged[feat_def.lag:] = col_data[:-feat_def.lag]
                    features[feat_def.name] = lagged
            
            elif feat_def.aggregation is not None and feat_def.window is not None:
                # Rolling aggregation
                col = feat_def.source_columns[0]
                if col in data:
                    col_data = np.asarray(data[col], dtype=float)
                    n = len(col_data)
                    agg_func = AggregationFunctions.get_function(feat_def.aggregation)
                    result = np.full(n, np.nan)
                    for i in range(feat_def.window - 1, n):
                        window_data = col_data[i - feat_def.window + 1:i + 1]
                        result[i] = agg_func(window_data)
                    features[feat_def.name] = result
        
        return features
    
    def get_feature_summary(self) -> Dict[str, Any]:
        """Get summary of generated features."""
        by_type = defaultdict(int)
        for f in self.feature_set.features:
            by_type[f.feature_type.value] += 1
        
        top_important = sorted(
            self.feature_set.features,
            key=lambda f: f.importance,
            reverse=True
        )[:10]
        
        return {
            'total_features': len(self.feature_set.features),
            'by_type': dict(by_type),
            'windows_used': self.windows,
            'lags_used': self.lags,
            'top_important': [
                {'name': f.name, 'importance': f.importance}
                for f in top_important
            ],
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def auto_generate_features(
    ohlcv: Dict[str, np.ndarray],
    target: np.ndarray = None,
    max_features: int = 200,
) -> Tuple[Dict[str, np.ndarray], FeatureSet]:
    """
    Convenience function to generate features from OHLCV data.
    
    Args:
        ohlcv: Dictionary with 'open', 'high', 'low', 'close', 'volume'
        target: Optional target for importance calculation
        max_features: Maximum number of features to generate
        
    Returns:
        Tuple of (features_dict, feature_set)
    """
    engineer = AutoFeatureEngineer(max_features=max_features)
    return engineer.fit_transform(ohlcv, target)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'FeatureType',
    'AggregationType',
    'FeatureDefinition',
    'FeatureSet',
    'AggregationFunctions',
    'AutoFeatureEngineer',
    'auto_generate_features',
]
