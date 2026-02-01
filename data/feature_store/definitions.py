"""
Feature Definitions - Standardized ML Feature Specifications

This module defines all features used in the quant trading system
with consistent naming, computation logic, and metadata.

Key Feature Groups:
- PriceFeatures: Price-based indicators (SMA, EMA, returns)
- VolumeFeatures: Volume analysis (VWAP, volume ratios)
- TechnicalFeatures: Technical indicators (RSI, MACD, Bollinger)
- SentimentFeatures: Market sentiment indicators
- RiskFeatures: Risk metrics (volatility, drawdown, VaR)

Each feature includes:
- Name and description
- Computation function
- Data requirements
- Expected value ranges
- Update frequency

Usage:
    from data.feature_store.definitions import get_feature_definitions

    definitions = get_feature_definitions()
    for feature in definitions['price_features']:
        print(f"{feature.name}: {feature.description}")
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureFrequency(Enum):
    """How often a feature should be updated."""
    TICK = "tick"           # Every price update
    SECOND = "second"       # Every second
    MINUTE = "minute"       # Every minute
    HOUR = "hour"           # Hourly
    DAILY = "daily"         # End of day
    WEEKLY = "weekly"       # End of week


class FeatureCategory(Enum):
    """Feature categorization for organization."""
    PRICE = "price"
    VOLUME = "volume"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    RISK = "risk"
    FUNDAMENTAL = "fundamental"
    ALTERNATIVE = "alternative"


@dataclass
class FeatureDefinition:
    """Complete specification of a feature."""
    name: str
    description: str
    category: FeatureCategory
    frequency: FeatureFrequency
    compute_func: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    lookback_periods: int = 1
    value_range: Tuple[Optional[float], Optional[float]] = (None, None)
    nullable: bool = False
    dtype: str = "float64"
    tags: List[str] = field(default_factory=list)

    def validate_value(self, value: Any) -> bool:
        """Check if a computed value is within expected range."""
        if value is None:
            return self.nullable

        min_val, max_val = self.value_range
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category.value,
            'frequency': self.frequency.value,
            'dependencies': self.dependencies,
            'lookback_periods': self.lookback_periods,
            'value_range': self.value_range,
            'nullable': self.nullable,
            'dtype': self.dtype,
            'tags': self.tags,
        }


# =============================================================================
# Price Features
# =============================================================================

class PriceFeatures:
    """Price-based feature definitions."""

    @staticmethod
    def sma(prices: pd.Series, period: int) -> float:
        """Simple Moving Average."""
        if len(prices) < period:
            return np.nan
        return prices.tail(period).mean()

    @staticmethod
    def ema(prices: pd.Series, period: int) -> float:
        """Exponential Moving Average."""
        if len(prices) < period:
            return np.nan
        return prices.ewm(span=period, adjust=False).mean().iloc[-1]

    @staticmethod
    def returns(prices: pd.Series, period: int = 1) -> float:
        """Log returns over period."""
        if len(prices) < period + 1:
            return np.nan
        return np.log(prices.iloc[-1] / prices.iloc[-period - 1])

    @staticmethod
    def momentum(prices: pd.Series, period: int) -> float:
        """Price momentum (rate of change)."""
        if len(prices) < period + 1:
            return np.nan
        return (prices.iloc[-1] - prices.iloc[-period - 1]) / prices.iloc[-period - 1]

    @staticmethod
    def price_position(prices: pd.Series, period: int) -> float:
        """Price position within recent range (0-1)."""
        if len(prices) < period:
            return np.nan
        recent = prices.tail(period)
        range_val = recent.max() - recent.min()
        if range_val == 0:
            return 0.5
        return (prices.iloc[-1] - recent.min()) / range_val

    @staticmethod
    def get_definitions() -> List[FeatureDefinition]:
        """Get all price feature definitions."""
        return [
            FeatureDefinition(
                name="sma_5",
                description="5-period Simple Moving Average",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: PriceFeatures.sma(p, 5),
                lookback_periods=5,
                tags=["trend", "short_term"],
            ),
            FeatureDefinition(
                name="sma_20",
                description="20-period Simple Moving Average",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: PriceFeatures.sma(p, 20),
                lookback_periods=20,
                tags=["trend", "medium_term"],
            ),
            FeatureDefinition(
                name="sma_50",
                description="50-period Simple Moving Average",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.HOUR,
                compute_func=lambda p: PriceFeatures.sma(p, 50),
                lookback_periods=50,
                tags=["trend", "long_term"],
            ),
            FeatureDefinition(
                name="ema_12",
                description="12-period Exponential Moving Average",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: PriceFeatures.ema(p, 12),
                lookback_periods=12,
                tags=["trend", "macd_component"],
            ),
            FeatureDefinition(
                name="ema_26",
                description="26-period Exponential Moving Average",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: PriceFeatures.ema(p, 26),
                lookback_periods=26,
                tags=["trend", "macd_component"],
            ),
            FeatureDefinition(
                name="returns_1d",
                description="1-day log returns",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.DAILY,
                compute_func=lambda p: PriceFeatures.returns(p, 1),
                lookback_periods=2,
                value_range=(-0.5, 0.5),
                tags=["returns"],
            ),
            FeatureDefinition(
                name="returns_5d",
                description="5-day log returns",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.DAILY,
                compute_func=lambda p: PriceFeatures.returns(p, 5),
                lookback_periods=6,
                value_range=(-1.0, 1.0),
                tags=["returns", "weekly"],
            ),
            FeatureDefinition(
                name="momentum_10",
                description="10-period price momentum",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: PriceFeatures.momentum(p, 10),
                lookback_periods=11,
                value_range=(-0.5, 0.5),
                tags=["momentum"],
            ),
            FeatureDefinition(
                name="price_position_20",
                description="Price position in 20-period range",
                category=FeatureCategory.PRICE,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: PriceFeatures.price_position(p, 20),
                lookback_periods=20,
                value_range=(0.0, 1.0),
                tags=["range", "mean_reversion"],
            ),
        ]


# =============================================================================
# Volume Features
# =============================================================================

class VolumeFeatures:
    """Volume-based feature definitions."""

    @staticmethod
    def vwap(prices: pd.Series, volumes: pd.Series) -> float:
        """Volume-Weighted Average Price."""
        if len(prices) == 0 or volumes.sum() == 0:
            return np.nan
        return (prices * volumes).sum() / volumes.sum()

    @staticmethod
    def volume_ratio(volumes: pd.Series, period: int) -> float:
        """Current volume vs average volume ratio."""
        if len(volumes) < period:
            return np.nan
        avg_volume = volumes.tail(period).mean()
        if avg_volume == 0:
            return 1.0
        return volumes.iloc[-1] / avg_volume

    @staticmethod
    def volume_trend(volumes: pd.Series, period: int) -> float:
        """Volume trend (slope of volume over period)."""
        if len(volumes) < period:
            return np.nan
        x = np.arange(period)
        y = volumes.tail(period).values
        slope, _ = np.polyfit(x, y, 1)
        return slope / np.mean(y) if np.mean(y) != 0 else 0

    @staticmethod
    def on_balance_volume(prices: pd.Series, volumes: pd.Series) -> float:
        """On-Balance Volume indicator."""
        if len(prices) < 2:
            return np.nan

        obv = 0
        for i in range(1, len(prices)):
            if prices.iloc[i] > prices.iloc[i-1]:
                obv += volumes.iloc[i]
            elif prices.iloc[i] < prices.iloc[i-1]:
                obv -= volumes.iloc[i]

        return obv

    @staticmethod
    def get_definitions() -> List[FeatureDefinition]:
        """Get all volume feature definitions."""
        return [
            FeatureDefinition(
                name="vwap",
                description="Volume-Weighted Average Price",
                category=FeatureCategory.VOLUME,
                frequency=FeatureFrequency.MINUTE,
                dependencies=["price", "volume"],
                tags=["execution", "benchmark"],
            ),
            FeatureDefinition(
                name="volume_ratio_20",
                description="Current volume vs 20-period average",
                category=FeatureCategory.VOLUME,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda v: VolumeFeatures.volume_ratio(v, 20),
                lookback_periods=20,
                value_range=(0.0, 10.0),
                tags=["relative_volume"],
            ),
            FeatureDefinition(
                name="volume_trend_10",
                description="10-period volume trend",
                category=FeatureCategory.VOLUME,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda v: VolumeFeatures.volume_trend(v, 10),
                lookback_periods=10,
                value_range=(-1.0, 1.0),
                tags=["trend"],
            ),
            FeatureDefinition(
                name="obv",
                description="On-Balance Volume",
                category=FeatureCategory.VOLUME,
                frequency=FeatureFrequency.MINUTE,
                dependencies=["price", "volume"],
                tags=["accumulation"],
            ),
        ]


# =============================================================================
# Technical Features
# =============================================================================

class TechnicalFeatures:
    """Technical indicator feature definitions."""

    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> float:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return np.nan

        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(prices: pd.Series) -> Tuple[float, float, float]:
        """MACD, Signal, and Histogram."""
        if len(prices) < 26:
            return np.nan, np.nan, np.nan

        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

    @staticmethod
    def bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[float, float, float]:
        """Bollinger Bands: middle, upper, lower."""
        if len(prices) < period:
            return np.nan, np.nan, np.nan

        middle = prices.rolling(period).mean().iloc[-1]
        std = prices.rolling(period).std().iloc[-1]
        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return middle, upper, lower

    @staticmethod
    def bollinger_position(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> float:
        """Price position within Bollinger Bands (0-1)."""
        middle, upper, lower = TechnicalFeatures.bollinger_bands(prices, period, std_dev)
        if np.isnan(upper):
            return np.nan

        band_width = upper - lower
        if band_width == 0:
            return 0.5

        return (prices.iloc[-1] - lower) / band_width

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Average True Range."""
        if len(high) < period + 1:
            return np.nan

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
        """Stochastic Oscillator %K and %D."""
        if len(close) < k_period:
            return np.nan, np.nan

        lowest_low = low.rolling(k_period).min()
        highest_high = high.rolling(k_period).max()

        denom = highest_high - lowest_low
        denom = denom.replace(0, np.nan)

        k = 100 * (close - lowest_low) / denom
        d = k.rolling(d_period).mean()

        return k.iloc[-1], d.iloc[-1]

    @staticmethod
    def get_definitions() -> List[FeatureDefinition]:
        """Get all technical feature definitions."""
        return [
            FeatureDefinition(
                name="rsi_14",
                description="14-period Relative Strength Index",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: TechnicalFeatures.rsi(p, 14),
                lookback_periods=15,
                value_range=(0.0, 100.0),
                tags=["momentum", "overbought_oversold"],
            ),
            FeatureDefinition(
                name="macd",
                description="MACD line value",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: TechnicalFeatures.macd(p)[0],
                lookback_periods=35,
                tags=["trend", "momentum"],
            ),
            FeatureDefinition(
                name="macd_signal",
                description="MACD signal line",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: TechnicalFeatures.macd(p)[1],
                lookback_periods=35,
                tags=["trend", "momentum"],
            ),
            FeatureDefinition(
                name="macd_histogram",
                description="MACD histogram (MACD - signal)",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: TechnicalFeatures.macd(p)[2],
                lookback_periods=35,
                tags=["trend", "momentum"],
            ),
            FeatureDefinition(
                name="bollinger_position",
                description="Price position in Bollinger Bands (0=lower, 1=upper)",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                compute_func=lambda p: TechnicalFeatures.bollinger_position(p, 20, 2.0),
                lookback_periods=20,
                value_range=(0.0, 1.0),
                tags=["volatility", "mean_reversion"],
            ),
            FeatureDefinition(
                name="atr_14",
                description="14-period Average True Range",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                dependencies=["high", "low", "close"],
                lookback_periods=15,
                value_range=(0.0, None),
                tags=["volatility"],
            ),
            FeatureDefinition(
                name="stochastic_k",
                description="Stochastic %K (14-period)",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                dependencies=["high", "low", "close"],
                lookback_periods=17,
                value_range=(0.0, 100.0),
                tags=["momentum", "overbought_oversold"],
            ),
            FeatureDefinition(
                name="stochastic_d",
                description="Stochastic %D (3-period smoothing)",
                category=FeatureCategory.TECHNICAL,
                frequency=FeatureFrequency.MINUTE,
                dependencies=["high", "low", "close"],
                lookback_periods=17,
                value_range=(0.0, 100.0),
                tags=["momentum", "overbought_oversold"],
            ),
        ]


# =============================================================================
# Sentiment Features
# =============================================================================

class SentimentFeatures:
    """Market sentiment feature definitions."""

    @staticmethod
    def fear_greed_index(vix: float, momentum: float, volume_ratio: float) -> float:
        """Composite fear/greed indicator (0-100)."""
        # VIX component (inverse - high VIX = fear)
        vix_score = max(0, min(100, 100 - vix * 2))

        # Momentum component
        momentum_score = max(0, min(100, 50 + momentum * 200))

        # Volume component
        volume_score = max(0, min(100, volume_ratio * 50))

        return (vix_score * 0.4 + momentum_score * 0.4 + volume_score * 0.2)

    @staticmethod
    def put_call_ratio(put_volume: float, call_volume: float) -> float:
        """Put/Call volume ratio."""
        if call_volume == 0:
            return np.nan
        return put_volume / call_volume

    @staticmethod
    def get_definitions() -> List[FeatureDefinition]:
        """Get all sentiment feature definitions."""
        return [
            FeatureDefinition(
                name="fear_greed",
                description="Fear/Greed index (0=extreme fear, 100=extreme greed)",
                category=FeatureCategory.SENTIMENT,
                frequency=FeatureFrequency.HOUR,
                dependencies=["vix", "momentum", "volume_ratio"],
                value_range=(0.0, 100.0),
                tags=["composite", "market_sentiment"],
            ),
            FeatureDefinition(
                name="put_call_ratio",
                description="Put/Call volume ratio",
                category=FeatureCategory.SENTIMENT,
                frequency=FeatureFrequency.DAILY,
                dependencies=["put_volume", "call_volume"],
                value_range=(0.0, 5.0),
                tags=["options", "contrarian"],
            ),
            FeatureDefinition(
                name="news_sentiment",
                description="Aggregated news sentiment score",
                category=FeatureCategory.SENTIMENT,
                frequency=FeatureFrequency.HOUR,
                value_range=(-1.0, 1.0),
                tags=["news", "nlp"],
            ),
            FeatureDefinition(
                name="social_sentiment",
                description="Social media sentiment score",
                category=FeatureCategory.SENTIMENT,
                frequency=FeatureFrequency.HOUR,
                value_range=(-1.0, 1.0),
                tags=["social", "nlp"],
            ),
        ]


# =============================================================================
# Risk Features
# =============================================================================

class RiskFeatures:
    """Risk metric feature definitions."""

    @staticmethod
    def realized_volatility(returns: pd.Series, period: int = 20, annualize: bool = True) -> float:
        """Realized volatility from returns."""
        if len(returns) < period:
            return np.nan

        vol = returns.tail(period).std()
        if annualize:
            vol *= np.sqrt(252)
        return vol

    @staticmethod
    def max_drawdown(prices: pd.Series, period: int = 20) -> float:
        """Maximum drawdown over period."""
        if len(prices) < period:
            return np.nan

        recent = prices.tail(period)
        peak = recent.expanding().max()
        drawdown = (recent - peak) / peak
        return drawdown.min()

    @staticmethod
    def var_historical(returns: pd.Series, confidence: float = 0.95, period: int = 252) -> float:
        """Historical Value at Risk."""
        if len(returns) < period:
            return np.nan

        return np.percentile(returns.tail(period), (1 - confidence) * 100)

    @staticmethod
    def expected_shortfall(returns: pd.Series, confidence: float = 0.95, period: int = 252) -> float:
        """Expected Shortfall (CVaR)."""
        if len(returns) < period:
            return np.nan

        var = RiskFeatures.var_historical(returns, confidence, period)
        return returns.tail(period)[returns.tail(period) <= var].mean()

    @staticmethod
    def get_definitions() -> List[FeatureDefinition]:
        """Get all risk feature definitions."""
        return [
            FeatureDefinition(
                name="volatility_20d",
                description="20-day annualized realized volatility",
                category=FeatureCategory.RISK,
                frequency=FeatureFrequency.DAILY,
                compute_func=lambda r: RiskFeatures.realized_volatility(r, 20, True),
                lookback_periods=20,
                value_range=(0.0, 2.0),
                tags=["volatility"],
            ),
            FeatureDefinition(
                name="max_drawdown_20d",
                description="20-day maximum drawdown",
                category=FeatureCategory.RISK,
                frequency=FeatureFrequency.DAILY,
                compute_func=lambda p: RiskFeatures.max_drawdown(p, 20),
                lookback_periods=20,
                value_range=(-1.0, 0.0),
                tags=["drawdown"],
            ),
            FeatureDefinition(
                name="var_95",
                description="95% 1-day Value at Risk",
                category=FeatureCategory.RISK,
                frequency=FeatureFrequency.DAILY,
                compute_func=lambda r: RiskFeatures.var_historical(r, 0.95),
                lookback_periods=252,
                value_range=(-0.5, 0.0),
                tags=["var"],
            ),
            FeatureDefinition(
                name="cvar_95",
                description="95% Expected Shortfall (CVaR)",
                category=FeatureCategory.RISK,
                frequency=FeatureFrequency.DAILY,
                compute_func=lambda r: RiskFeatures.expected_shortfall(r, 0.95),
                lookback_periods=252,
                value_range=(-1.0, 0.0),
                tags=["var", "tail_risk"],
            ),
            FeatureDefinition(
                name="beta",
                description="Market beta coefficient",
                category=FeatureCategory.RISK,
                frequency=FeatureFrequency.DAILY,
                dependencies=["returns", "market_returns"],
                value_range=(-3.0, 3.0),
                tags=["systematic_risk"],
            ),
            FeatureDefinition(
                name="sharpe_rolling_60d",
                description="60-day rolling Sharpe ratio",
                category=FeatureCategory.RISK,
                frequency=FeatureFrequency.DAILY,
                lookback_periods=60,
                value_range=(-5.0, 5.0),
                tags=["risk_adjusted_return"],
            ),
        ]


# =============================================================================
# Feature Registry Functions
# =============================================================================

def get_feature_definitions() -> Dict[str, List[FeatureDefinition]]:
    """
    Get all feature definitions organized by category.

    Returns:
        Dictionary mapping category name to list of feature definitions
    """
    return {
        'price_features': PriceFeatures.get_definitions(),
        'volume_features': VolumeFeatures.get_definitions(),
        'technical_features': TechnicalFeatures.get_definitions(),
        'sentiment_features': SentimentFeatures.get_definitions(),
        'risk_features': RiskFeatures.get_definitions(),
    }


def get_all_features() -> List[FeatureDefinition]:
    """Get flat list of all feature definitions."""
    all_features = []
    for features in get_feature_definitions().values():
        all_features.extend(features)
    return all_features


def get_features_by_tag(tag: str) -> List[FeatureDefinition]:
    """Get all features with a specific tag."""
    return [f for f in get_all_features() if tag in f.tags]


def get_features_by_frequency(frequency: FeatureFrequency) -> List[FeatureDefinition]:
    """Get all features with a specific update frequency."""
    return [f for f in get_all_features() if f.frequency == frequency]


def get_feature_by_name(name: str) -> Optional[FeatureDefinition]:
    """Get a specific feature by name."""
    for feature in get_all_features():
        if feature.name == name:
            return feature
    return None
