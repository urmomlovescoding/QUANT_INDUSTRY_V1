"""
QUANT INDUSTRY - Feature Store
==============================
Production-grade feature engineering and storage:
- Centralized feature definitions
- Point-in-time correct features (no lookahead)
- Feature versioning
- Online (real-time) and offline (batch) serving
- Feature validation and monitoring

Feature stores prevent the #1 cause of ML failures in trading:
lookahead bias from incorrectly computed features.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import hashlib
import json
import logging
import pickle
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """Types of features"""
    PRICE = "price"           # Price-based (OHLCV)
    TECHNICAL = "technical"   # Technical indicators
    FUNDAMENTAL = "fundamental"  # Fundamental data
    ALTERNATIVE = "alternative"  # Alt data (sentiment, etc.)
    DERIVED = "derived"       # Computed from other features
    EXTERNAL = "external"     # External signals


class FeatureFrequency(Enum):
    """Feature update frequency"""
    TICK = "tick"
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class FeatureDefinition:
    """Definition of a single feature"""
    name: str
    feature_type: FeatureType
    frequency: FeatureFrequency
    description: str = ""
    
    # Computation
    compute_fn: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    
    # Validation
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allow_nan: bool = False
    
    # Lag to prevent lookahead
    lag_periods: int = 0
    
    # Versioning
    version: str = "1.0"
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.feature_type.value,
            "frequency": self.frequency.value,
            "description": self.description,
            "dependencies": self.dependencies,
            "lag_periods": self.lag_periods,
            "version": self.version,
        }
    
    @property
    def id(self) -> str:
        """Unique feature ID"""
        return f"{self.name}_v{self.version}"


@dataclass
class FeatureValue:
    """A single feature value with metadata"""
    feature_name: str
    value: float
    timestamp: datetime
    as_of_timestamp: datetime  # When this value was known (for point-in-time)
    
    def is_valid_at(self, query_time: datetime) -> bool:
        """Check if this value was known at query time"""
        return self.as_of_timestamp <= query_time


@dataclass
class FeatureVector:
    """Collection of features at a point in time"""
    timestamp: datetime
    features: Dict[str, float]
    
    def to_array(self, feature_names: List[str]) -> np.ndarray:
        """Convert to numpy array in specified order"""
        return np.array([self.features.get(name, np.nan) for name in feature_names])
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "features": self.features
        }


class FeatureStore:
    """
    Central feature store for ML models.
    
    Features:
    1. Point-in-time correct retrieval (no lookahead)
    2. Feature caching and persistence
    3. Online serving for real-time
    4. Batch retrieval for training
    5. Feature validation
    
    Usage:
    ------
    >>> store = FeatureStore()
    >>>
    >>> # Register feature definitions
    >>> store.register_feature(FeatureDefinition(
    ...     name="returns_20d",
    ...     feature_type=FeatureType.PRICE,
    ...     frequency=FeatureFrequency.DAILY,
    ...     compute_fn=lambda prices: (prices[-1]/prices[-21] - 1),
    ...     lag_periods=1  # Use yesterday's close
    ... ))
    >>>
    >>> # Compute and store features
    >>> store.compute_features(prices_df, symbols=['AAPL', 'GOOGL'])
    >>>
    >>> # Get features for training (point-in-time correct)
    >>> X = store.get_training_data(
    ...     symbols=['AAPL'],
    ...     start_date='2023-01-01',
    ...     end_date='2024-01-01'
    ... )
    >>>
    >>> # Get features for live trading
    >>> features = store.get_live_features('AAPL')
    """
    
    def __init__(
        self,
        storage_path: str = None,
        cache_size: int = 10000
    ):
        """
        Initialize feature store.
        
        Args:
            storage_path: Path for persistent storage
            cache_size: Max cached feature vectors
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.cache_size = cache_size
        
        # Feature definitions
        self.definitions: Dict[str, FeatureDefinition] = {}
        
        # Feature storage: {symbol: {timestamp: FeatureVector}}
        self.feature_data: Dict[str, Dict[datetime, FeatureVector]] = {}
        
        # Online cache for real-time serving
        self.online_cache: Dict[str, deque] = {}
        
        # Validation stats
        self.validation_errors: deque = deque(maxlen=1000)
        
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Register standard features
        self._register_standard_features()
        
        logger.info(f"FeatureStore initialized with {len(self.definitions)} features")
    
    def _register_standard_features(self):
        """Register common technical features"""
        # Returns
        for period in [1, 5, 10, 20, 60]:
            self.register_feature(FeatureDefinition(
                name=f"returns_{period}d",
                feature_type=FeatureType.PRICE,
                frequency=FeatureFrequency.DAILY,
                description=f"{period}-day returns",
                lag_periods=1
            ))
        
        # Volatility
        for period in [10, 20, 60]:
            self.register_feature(FeatureDefinition(
                name=f"volatility_{period}d",
                feature_type=FeatureType.TECHNICAL,
                frequency=FeatureFrequency.DAILY,
                description=f"{period}-day realized volatility",
                min_value=0,
                lag_periods=1
            ))
        
        # RSI
        self.register_feature(FeatureDefinition(
            name="rsi_14",
            feature_type=FeatureType.TECHNICAL,
            frequency=FeatureFrequency.DAILY,
            description="14-period RSI",
            min_value=0,
            max_value=100,
            lag_periods=1
        ))
        
        # MACD
        self.register_feature(FeatureDefinition(
            name="macd_signal",
            feature_type=FeatureType.TECHNICAL,
            frequency=FeatureFrequency.DAILY,
            description="MACD minus signal line",
            lag_periods=1
        ))
        
        # Bollinger Band position
        self.register_feature(FeatureDefinition(
            name="bb_position",
            feature_type=FeatureType.TECHNICAL,
            frequency=FeatureFrequency.DAILY,
            description="Position within Bollinger Bands (-1 to 1)",
            min_value=-2,
            max_value=2,
            lag_periods=1
        ))
        
        # Volume features
        self.register_feature(FeatureDefinition(
            name="volume_ratio_20d",
            feature_type=FeatureType.PRICE,
            frequency=FeatureFrequency.DAILY,
            description="Volume / 20-day average volume",
            min_value=0,
            lag_periods=1
        ))
        
        # Momentum
        self.register_feature(FeatureDefinition(
            name="momentum_12_1",
            feature_type=FeatureType.TECHNICAL,
            frequency=FeatureFrequency.DAILY,
            description="12-month return minus 1-month return",
            lag_periods=1
        ))
    
    def register_feature(self, definition: FeatureDefinition):
        """
        Register a feature definition.
        
        Args:
            definition: Feature definition to register
        """
        self.definitions[definition.name] = definition
        logger.debug(f"Registered feature: {definition.name}")
    
    def compute_feature(
        self,
        feature_name: str,
        data: np.ndarray,
        timestamps: List[datetime] = None
    ) -> np.ndarray:
        """
        Compute a single feature from raw data.
        
        Args:
            feature_name: Name of feature to compute
            data: Raw data (e.g., prices)
            timestamps: Corresponding timestamps
            
        Returns:
            Computed feature values
        """
        if feature_name not in self.definitions:
            raise ValueError(f"Unknown feature: {feature_name}")
        
        definition = self.definitions[feature_name]
        
        if definition.compute_fn is not None:
            values = definition.compute_fn(data)
        else:
            values = self._compute_standard_feature(feature_name, data)
        
        # Apply lag
        if definition.lag_periods > 0:
            values = np.roll(values, definition.lag_periods)
            values[:definition.lag_periods] = np.nan
        
        # Validate
        values = self._validate_feature(feature_name, values)
        
        return values
    
    def _compute_standard_feature(
        self,
        feature_name: str,
        data: np.ndarray
    ) -> np.ndarray:
        """Compute standard features"""
        n = len(data)
        result = np.full(n, np.nan)
        
        if feature_name.startswith("returns_"):
            period = int(feature_name.split("_")[1].replace("d", ""))
            for i in range(period, n):
                result[i] = (data[i] / data[i - period]) - 1
        
        elif feature_name.startswith("volatility_"):
            period = int(feature_name.split("_")[1].replace("d", ""))
            returns = np.diff(data) / data[:-1]
            for i in range(period, n):
                result[i] = np.std(returns[i-period:i]) * np.sqrt(252)
        
        elif feature_name == "rsi_14":
            returns = np.diff(data)
            gains = np.where(returns > 0, returns, 0)
            losses = np.where(returns < 0, -returns, 0)
            
            for i in range(14, n):
                avg_gain = np.mean(gains[i-14:i])
                avg_loss = np.mean(losses[i-14:i])
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    result[i] = 100 - (100 / (1 + rs))
                else:
                    result[i] = 100
        
        elif feature_name == "bb_position":
            for i in range(20, n):
                sma = np.mean(data[i-20:i])
                std = np.std(data[i-20:i])
                if std > 0:
                    result[i] = (data[i] - sma) / (2 * std)
                else:
                    result[i] = 0
        
        elif feature_name == "volume_ratio_20d":
            # Assumes data is volume
            for i in range(20, n):
                avg_vol = np.mean(data[i-20:i])
                if avg_vol > 0:
                    result[i] = data[i] / avg_vol
        
        elif feature_name == "momentum_12_1":
            for i in range(252, n):
                ret_12m = (data[i] / data[i-252]) - 1 if data[i-252] > 0 else 0
                ret_1m = (data[i] / data[i-21]) - 1 if data[i-21] > 0 else 0
                result[i] = ret_12m - ret_1m
        
        elif feature_name == "macd_signal":
            ema_12 = self._ema(data, 12)
            ema_26 = self._ema(data, 26)
            macd = ema_12 - ema_26
            signal = self._ema(macd, 9)
            result = macd - signal
        
        return result
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        result = np.full(len(data), np.nan)
        multiplier = 2 / (period + 1)
        
        # Start with SMA
        result[period-1] = np.mean(data[:period])
        
        for i in range(period, len(data)):
            result[i] = (data[i] * multiplier) + (result[i-1] * (1 - multiplier))
        
        return result
    
    def _validate_feature(
        self,
        feature_name: str,
        values: np.ndarray
    ) -> np.ndarray:
        """Validate feature values"""
        definition = self.definitions.get(feature_name)
        if definition is None:
            return values
        
        validated = values.copy()
        
        # Check bounds
        if definition.min_value is not None:
            below_min = validated < definition.min_value
            if below_min.any():
                self.validation_errors.append({
                    "feature": feature_name,
                    "error": "below_min",
                    "count": below_min.sum()
                })
                validated[below_min] = definition.min_value
        
        if definition.max_value is not None:
            above_max = validated > definition.max_value
            if above_max.any():
                self.validation_errors.append({
                    "feature": feature_name,
                    "error": "above_max",
                    "count": above_max.sum()
                })
                validated[above_max] = definition.max_value
        
        # Check NaN
        if not definition.allow_nan:
            nan_count = np.isnan(validated).sum()
            if nan_count > 0:
                self.validation_errors.append({
                    "feature": feature_name,
                    "error": "nan_values",
                    "count": nan_count
                })
        
        return validated
    
    def compute_all_features(
        self,
        prices: np.ndarray,
        volumes: np.ndarray = None,
        timestamps: List[datetime] = None,
        symbol: str = "UNKNOWN"
    ) -> Dict[str, np.ndarray]:
        """
        Compute all registered features from price/volume data.
        
        Args:
            prices: Price array
            volumes: Volume array (optional)
            timestamps: Timestamps
            symbol: Symbol name
            
        Returns:
            Dict of feature_name: values
        """
        features = {}
        
        for name, definition in self.definitions.items():
            try:
                if definition.feature_type == FeatureType.PRICE:
                    if "volume" in name.lower() and volumes is not None:
                        values = self.compute_feature(name, volumes, timestamps)
                    else:
                        values = self.compute_feature(name, prices, timestamps)
                else:
                    values = self.compute_feature(name, prices, timestamps)
                
                features[name] = values
            except Exception as e:
                logger.warning(f"Failed to compute {name}: {e}")
                features[name] = np.full(len(prices), np.nan)
        
        # Store
        if timestamps:
            self._store_features(symbol, features, timestamps)
        
        return features
    
    def _store_features(
        self,
        symbol: str,
        features: Dict[str, np.ndarray],
        timestamps: List[datetime]
    ):
        """Store computed features"""
        if symbol not in self.feature_data:
            self.feature_data[symbol] = {}
        
        for i, ts in enumerate(timestamps):
            vector = FeatureVector(
                timestamp=ts,
                features={name: float(values[i]) for name, values in features.items() if not np.isnan(values[i])}
            )
            self.feature_data[symbol][ts] = vector
    
    def get_features(
        self,
        symbol: str,
        timestamp: datetime,
        feature_names: List[str] = None
    ) -> FeatureVector:
        """
        Get features for a symbol at a specific time.
        
        Point-in-time correct: only returns features that were known at query time.
        """
        if symbol not in self.feature_data:
            return FeatureVector(timestamp=timestamp, features={})
        
        # Find the most recent features known at this time
        valid_times = [t for t in self.feature_data[symbol].keys() if t <= timestamp]
        
        if not valid_times:
            return FeatureVector(timestamp=timestamp, features={})
        
        latest_time = max(valid_times)
        vector = self.feature_data[symbol][latest_time]
        
        # Filter to requested features
        if feature_names:
            filtered = {k: v for k, v in vector.features.items() if k in feature_names}
            return FeatureVector(timestamp=timestamp, features=filtered)
        
        return vector
    
    def get_training_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        feature_names: List[str] = None
    ) -> Tuple[np.ndarray, List[datetime], List[str]]:
        """
        Get training data for multiple symbols.
        
        Returns:
            Tuple of (feature_matrix, timestamps, symbols_list)
        """
        if feature_names is None:
            feature_names = list(self.definitions.keys())
        
        all_features = []
        all_timestamps = []
        all_symbols = []
        
        for symbol in symbols:
            if symbol not in self.feature_data:
                continue
            
            for ts, vector in sorted(self.feature_data[symbol].items()):
                if start_date <= ts <= end_date:
                    features = vector.to_array(feature_names)
                    all_features.append(features)
                    all_timestamps.append(ts)
                    all_symbols.append(symbol)
        
        if not all_features:
            return np.array([]), [], []
        
        return np.array(all_features), all_timestamps, all_symbols
    
    def get_live_features(
        self,
        symbol: str,
        feature_names: List[str] = None
    ) -> FeatureVector:
        """
        Get most recent features for live trading.
        """
        return self.get_features(symbol, datetime.now(), feature_names)
    
    def save(self, path: str = None):
        """Save feature store to disk"""
        path = Path(path) if path else self.storage_path
        if path is None:
            raise ValueError("No storage path specified")
        
        path.mkdir(parents=True, exist_ok=True)
        
        # Save definitions
        definitions_dict = {name: defn.to_dict() for name, defn in self.definitions.items()}
        with open(path / "definitions.json", "w") as f:
            json.dump(definitions_dict, f, indent=2)
        
        # Save feature data
        for symbol, data in self.feature_data.items():
            symbol_data = {
                ts.isoformat(): vec.to_dict()
                for ts, vec in data.items()
            }
            with open(path / f"{symbol}_features.json", "w") as f:
                json.dump(symbol_data, f)
        
        logger.info(f"Feature store saved to {path}")
    
    def load(self, path: str = None):
        """Load feature store from disk"""
        path = Path(path) if path else self.storage_path
        if path is None or not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        
        # Load definitions
        with open(path / "definitions.json", "r") as f:
            definitions_dict = json.load(f)
        
        # Load feature data
        for file in path.glob("*_features.json"):
            symbol = file.stem.replace("_features", "")
            with open(file, "r") as f:
                symbol_data = json.load(f)
            
            self.feature_data[symbol] = {
                datetime.fromisoformat(ts): FeatureVector(
                    timestamp=datetime.fromisoformat(vec["timestamp"]),
                    features=vec["features"]
                )
                for ts, vec in symbol_data.items()
            }
        
        logger.info(f"Feature store loaded from {path}")
    
    def get_feature_stats(self) -> Dict[str, Dict]:
        """Get statistics about stored features"""
        stats = {
            "n_definitions": len(self.definitions),
            "n_symbols": len(self.feature_data),
            "validation_errors": len(self.validation_errors),
            "features": {}
        }
        
        for name in self.definitions:
            all_values = []
            for symbol_data in self.feature_data.values():
                for vector in symbol_data.values():
                    if name in vector.features:
                        all_values.append(vector.features[name])
            
            if all_values:
                stats["features"][name] = {
                    "count": len(all_values),
                    "mean": np.mean(all_values),
                    "std": np.std(all_values),
                    "min": np.min(all_values),
                    "max": np.max(all_values),
                }
        
        return stats


# ============== SINGLETON ==============

_feature_store: Optional[FeatureStore] = None


def get_feature_store(storage_path: str = None) -> FeatureStore:
    """Get or create global feature store"""
    global _feature_store
    
    if _feature_store is None:
        _feature_store = FeatureStore(storage_path)
    
    return _feature_store
