"""
DATA INTEGRITY LAYER
====================

This module provides the SINGLE SOURCE OF TRUTH for all market data.
All components MUST use this module to access prices, not direct API calls.

Key Features:
1. Single get_price_truth() function
2. Data mode enforcement (LIVE, PAPER, BACKTEST, SIMULATION)
3. Source provenance tracking
4. Staleness detection and warnings

Usage:
    from core.data_integrity import get_price_truth, DataMode, set_data_mode

    # Get authoritative price
    price_data = get_price_truth("SPY")

    # Check if data is live
    if price_data.is_live:
        execute_trade(...)
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DataMode(Enum):
    """
    System-wide data mode.

    LIVE: Real broker connection, real money at risk
    PAPER: Paper trading with real market prices
    BACKTEST: Historical simulation
    SIMULATION: Demo mode with synthetic data (clearly marked)
    """
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"
    SIMULATION = "simulation"


class DataQuality(Enum):
    """Data quality classification"""
    LIVE_VERIFIED = "live_verified"      # Real-time, validated
    LIVE_UNVERIFIED = "live_unverified"  # Real-time, quality uncertain
    CACHED = "cached"                     # Within TTL
    STALE = "stale"                       # Beyond TTL
    FALLBACK = "fallback"                 # Last known / synthetic
    UNAVAILABLE = "unavailable"           # No data


@dataclass
class PriceTruth:
    """
    Authoritative price data with full provenance.

    This is the ONLY structure that should be used for price data
    throughout the application.
    """
    symbol: str
    price: float
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    prev_close: float = 0.0

    # Provenance
    source: str = "unknown"
    quality: DataQuality = DataQuality.UNAVAILABLE
    timestamp: datetime = field(default_factory=datetime.now)
    fetch_latency_ms: float = 0.0

    # Flags
    is_live: bool = False
    is_market_open: bool = False
    is_stale: bool = False
    staleness_seconds: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "change": self.change,
            "change_pct": self.change_pct,
            "high": self.high,
            "low": self.low,
            "open": self.open,
            "prev_close": self.prev_close,
            "source": self.source,
            "quality": self.quality.value,
            "timestamp": self.timestamp.isoformat(),
            "fetch_latency_ms": round(self.fetch_latency_ms, 2),
            "is_live": self.is_live,
            "is_market_open": self.is_market_open,
            "is_stale": self.is_stale,
            "staleness_seconds": round(self.staleness_seconds, 1),
        }


# Global data mode (default to PAPER for safety)
_current_data_mode: DataMode = DataMode.PAPER
_mode_lock_reason: Optional[str] = None


def get_data_mode() -> DataMode:
    """Get current system data mode"""
    return _current_data_mode


def set_data_mode(mode: DataMode, reason: str = None) -> bool:
    """
    Set system data mode.

    Args:
        mode: New data mode
        reason: Reason for mode change (logged)

    Returns:
        True if mode changed, False if locked
    """
    global _current_data_mode, _mode_lock_reason

    if _mode_lock_reason and mode == DataMode.LIVE:
        logger.warning(f"Cannot switch to LIVE mode: {_mode_lock_reason}")
        return False

    old_mode = _current_data_mode
    _current_data_mode = mode

    logger.info(f"Data mode changed: {old_mode.value} -> {mode.value} (reason: {reason})")
    return True


def lock_mode(reason: str):
    """Lock the data mode to prevent accidental LIVE trading"""
    global _mode_lock_reason
    _mode_lock_reason = reason
    logger.warning(f"Data mode LOCKED: {reason}")


def unlock_mode():
    """Unlock data mode (requires explicit call)"""
    global _mode_lock_reason
    _mode_lock_reason = None
    logger.info("Data mode UNLOCKED")


def get_price_truth(symbol: str) -> PriceTruth:
    """
    Get the authoritative price for a symbol.

    This is the SINGLE SOURCE OF TRUTH for all price data.
    All components should use this function instead of direct API calls.

    Args:
        symbol: Stock symbol

    Returns:
        PriceTruth with full provenance information
    """
    start_time = time.perf_counter()

    try:
        # Import here to avoid circular imports
        from services.data_service import get_data_service
        from services.market_hours import is_market_open as check_market_open

        ds = get_data_service()
        quote = ds.get_quote(symbol.upper())

        latency = (time.perf_counter() - start_time) * 1000

        if quote is None:
            return PriceTruth(
                symbol=symbol.upper(),
                price=0.0,
                source="none",
                quality=DataQuality.UNAVAILABLE,
                fetch_latency_ms=latency,
            )

        # Determine quality
        source = getattr(quote, 'source', 'unknown')
        is_fallback = source in ['fallback', 'cache', 'last_known']

        if is_fallback:
            quality = DataQuality.FALLBACK
            is_live = False
        elif source in ['alpaca', 'tradier']:
            quality = DataQuality.LIVE_VERIFIED
            is_live = True
        elif source in ['yahoo', 'finnhub']:
            quality = DataQuality.LIVE_UNVERIFIED
            is_live = True
        else:
            quality = DataQuality.CACHED
            is_live = False

        # Check staleness
        quote_time = getattr(quote, 'timestamp', datetime.now())
        if isinstance(quote_time, str):
            try:
                quote_time = datetime.fromisoformat(quote_time)
            except (ValueError, TypeError):
                quote_time = datetime.now()

        staleness = (datetime.now() - quote_time).total_seconds()
        is_stale = staleness > 60  # More than 1 minute old

        if is_stale and quality != DataQuality.FALLBACK:
            quality = DataQuality.STALE

        # Check market status
        try:
            market_open = check_market_open()
        except Exception:
            market_open = False

        return PriceTruth(
            symbol=symbol.upper(),
            price=quote.price,
            bid=getattr(quote, 'bid', 0.0),
            ask=getattr(quote, 'ask', 0.0),
            volume=getattr(quote, 'volume', 0),
            change=getattr(quote, 'change', 0.0),
            change_pct=getattr(quote, 'change_pct', 0.0),
            high=getattr(quote, 'high', 0.0),
            low=getattr(quote, 'low', 0.0),
            open=getattr(quote, 'open', 0.0),
            prev_close=getattr(quote, 'prev_close', 0.0),
            source=source,
            quality=quality,
            timestamp=quote_time,
            fetch_latency_ms=latency,
            is_live=is_live,
            is_market_open=market_open,
            is_stale=is_stale,
            staleness_seconds=staleness,
        )

    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        logger.error(f"get_price_truth failed for {symbol}: {e}")

        return PriceTruth(
            symbol=symbol.upper(),
            price=0.0,
            source="error",
            quality=DataQuality.UNAVAILABLE,
            fetch_latency_ms=latency,
        )


def get_prices_truth(symbols: List[str]) -> Dict[str, PriceTruth]:
    """
    Get authoritative prices for multiple symbols.

    Args:
        symbols: List of stock symbols

    Returns:
        Dict mapping symbol to PriceTruth
    """
    return {symbol: get_price_truth(symbol) for symbol in symbols}


def validate_price(price: float, symbol: str = None) -> bool:
    """
    Validate that a price is reasonable.

    Args:
        price: Price to validate
        symbol: Optional symbol for context

    Returns:
        True if price is valid
    """
    if price <= 0:
        logger.warning(f"Invalid price {price} for {symbol}: must be > 0")
        return False

    if price > 100000:
        logger.warning(f"Suspicious price {price} for {symbol}: unusually high")
        return False

    return True


def assert_no_simulation(context: str = "operation"):
    """
    Assert that we're not in simulation mode.

    Use this before any real trading operation.

    Raises:
        RuntimeError if in SIMULATION mode
    """
    if _current_data_mode == DataMode.SIMULATION:
        raise RuntimeError(f"Cannot perform {context} in SIMULATION mode")


def assert_live_data(price_truth: PriceTruth, context: str = "operation"):
    """
    Assert that the data is live and verified.

    Raises:
        RuntimeError if data is not live
    """
    if not price_truth.is_live:
        raise RuntimeError(
            f"Cannot perform {context}: data is not live "
            f"(source={price_truth.source}, quality={price_truth.quality.value})"
        )


# ============================================================================
# ENHANCED VALIDATION (ported from quant-platform)
# ============================================================================

# Maximum age for price data (60 seconds for trading, 600 for display)
MAX_PRICE_AGE_TRADING_SECONDS = 60
MAX_PRICE_AGE_DISPLAY_SECONDS = 600


def validate_timestamp_freshness(
    timestamp: datetime,
    max_age_seconds: float = MAX_PRICE_AGE_TRADING_SECONDS,
    context: str = "price data"
) -> tuple:
    """
    Validate that a timestamp is fresh enough for trading.

    Args:
        timestamp: Data timestamp to validate
        max_age_seconds: Maximum allowed age
        context: Description for logging

    Returns:
        (is_valid, age_seconds, message)
    """
    import math

    if timestamp is None:
        return False, float('inf'), f"No timestamp for {context}"

    # Handle timezone-aware timestamps
    now = datetime.now()
    if timestamp.tzinfo is not None:
        try:
            from datetime import timezone
            now = datetime.now(timestamp.tzinfo)
        except Exception:
            # Strip timezone for comparison
            timestamp = timestamp.replace(tzinfo=None)

    age_seconds = (now - timestamp.replace(tzinfo=None)).total_seconds()

    if age_seconds > max_age_seconds:
        return False, age_seconds, f"{context} is stale: {age_seconds:.1f}s > {max_age_seconds}s"

    if age_seconds < -60:  # Allow 1 min clock skew
        return False, age_seconds, f"{context} timestamp is in the future by {-age_seconds:.1f}s"

    return True, age_seconds, "OK"


def validate_data_schema(data: dict, required_fields: list = None) -> tuple:
    """
    Validate data has required fields and no NaN values.

    Args:
        data: Dictionary to validate
        required_fields: List of required field names

    Returns:
        (is_valid, message)
    """
    import math

    if data is None:
        return False, "Data is None"

    required = required_fields or ['price', 'symbol']

    # Check required fields
    for field in required:
        if field not in data:
            return False, f"Missing required field: {field}"

    # Check for NaN/None values in numeric fields
    numeric_fields = ['price', 'bid', 'ask', 'volume', 'high', 'low', 'open', 'close']
    for field in numeric_fields:
        if field in data:
            val = data[field]
            if val is None:
                return False, f"Field {field} is None"
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return False, f"Field {field} has invalid value: {val}"

    return True, "OK"


def validate_price_reasonableness(
    price: float,
    symbol: str,
    prev_price: float = None,
    max_change_pct: float = 20.0
) -> tuple:
    """
    Validate that a price change is reasonable (not a bad tick).

    Args:
        price: Current price
        symbol: Symbol for logging
        prev_price: Previous known price
        max_change_pct: Maximum allowed percent change

    Returns:
        (is_valid, message)
    """
    if price <= 0:
        return False, f"Invalid price {price} for {symbol}: must be > 0"

    if prev_price is not None and prev_price > 0:
        change_pct = abs((price - prev_price) / prev_price) * 100
        if change_pct > max_change_pct:
            return False, f"Suspicious price change for {symbol}: {change_pct:.1f}% (max {max_change_pct}%)"

    return True, "OK"


def assert_data_integrity_for_trading(
    price_truth: PriceTruth,
    require_live: bool = True,
    max_age_seconds: float = MAX_PRICE_AGE_TRADING_SECONDS
):
    """
    Comprehensive data integrity check for trading operations.

    This is the FINAL gate before any trade execution.

    Args:
        price_truth: Price data to validate
        require_live: Whether to require live data
        max_age_seconds: Maximum data age

    Raises:
        RuntimeError: If any validation fails
    """
    # Check data mode
    if _current_data_mode == DataMode.SIMULATION:
        raise RuntimeError("Cannot trade with SIMULATION data")

    # Check live requirement
    if require_live and not price_truth.is_live:
        raise RuntimeError(
            f"Trading requires live data, got {price_truth.quality.value} "
            f"from {price_truth.source}"
        )

    # Check timestamp freshness
    is_fresh, age, msg = validate_timestamp_freshness(
        price_truth.timestamp,
        max_age_seconds,
        f"Price for {price_truth.symbol}"
    )
    if not is_fresh:
        raise RuntimeError(f"Data integrity check failed: {msg}")

    # Check price validity
    if not validate_price(price_truth.price, price_truth.symbol):
        raise RuntimeError(f"Invalid price for {price_truth.symbol}: {price_truth.price}")

    logger.debug(f"Data integrity OK for {price_truth.symbol}: age={age:.1f}s, source={price_truth.source}")


# Data quality tracking
_quality_stats: Dict[str, Dict] = {}


def record_data_quality(symbol: str, quality: DataQuality, source: str):
    """Record data quality for monitoring"""
    if symbol not in _quality_stats:
        _quality_stats[symbol] = {
            "live_count": 0,
            "fallback_count": 0,
            "unavailable_count": 0,
            "last_source": source,
            "last_quality": quality.value,
        }

    stats = _quality_stats[symbol]
    stats["last_source"] = source
    stats["last_quality"] = quality.value

    if quality in [DataQuality.LIVE_VERIFIED, DataQuality.LIVE_UNVERIFIED]:
        stats["live_count"] += 1
    elif quality == DataQuality.FALLBACK:
        stats["fallback_count"] += 1
    elif quality == DataQuality.UNAVAILABLE:
        stats["unavailable_count"] += 1


def get_quality_stats() -> Dict[str, Dict]:
    """Get data quality statistics"""
    return _quality_stats.copy()


# Initialization
def init_data_integrity(mode: DataMode = DataMode.PAPER):
    """
    Initialize the data integrity layer.

    Call this at application startup.
    """
    global _current_data_mode
    _current_data_mode = mode
    logger.info(f"Data integrity layer initialized in {mode.value} mode")
