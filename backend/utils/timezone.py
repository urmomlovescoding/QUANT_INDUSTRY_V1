"""
Timezone Utilities
==================
Centralized timezone handling to prevent off-by-one errors and ensure
deterministic backtests.

CRITICAL: Always use utc_now() instead of datetime.now() throughout the codebase.
This ensures:
1. Consistent timestamps across all systems
2. No ambiguity during daylight saving transitions
3. Deterministic backtesting results
4. Proper handling of market hours across timezones

Usage:
    from backend.utils.timezone import utc_now, to_eastern, is_market_hours

    # Get current time in UTC
    now = utc_now()

    # Convert to Eastern for market hours check
    eastern_time = to_eastern(now)
"""

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Timezone constants
UTC = timezone.utc

# Eastern timezone (US markets) - handles DST automatically
try:
    import zoneinfo
    EASTERN = zoneinfo.ZoneInfo("America/New_York")
except ImportError:
    # Fallback for Python < 3.9 or missing tzdata
    try:
        import pytz
        EASTERN = pytz.timezone("America/New_York")
    except ImportError:
        # Last resort: fixed offset (doesn't handle DST)
        logger.warning(
            "Neither zoneinfo nor pytz available. "
            "Eastern timezone will use fixed UTC-5 offset (no DST handling)."
        )
        EASTERN = timezone(timedelta(hours=-5))


def utc_now() -> datetime:
    """
    Get current UTC time with timezone info.

    ALWAYS use this instead of datetime.now() to ensure:
    - Consistent timestamps across all systems
    - No timezone ambiguity
    - Deterministic behavior in backtests

    Returns:
        datetime: Current UTC time with tzinfo set
    """
    return datetime.now(UTC)


def to_utc(dt: datetime) -> datetime:
    """
    Convert a datetime to UTC.

    Args:
        dt: Datetime to convert. If naive (no tzinfo), assumes UTC.

    Returns:
        datetime: UTC datetime with tzinfo set
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's already UTC
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_eastern(dt: datetime) -> datetime:
    """
    Convert a datetime to US Eastern time.

    Args:
        dt: Datetime to convert. If naive, assumes UTC.

    Returns:
        datetime: Eastern time with tzinfo set
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(EASTERN)


def from_timestamp(ts: float) -> datetime:
    """
    Convert Unix timestamp to UTC datetime.

    Args:
        ts: Unix timestamp (seconds since epoch)

    Returns:
        datetime: UTC datetime with tzinfo set
    """
    return datetime.fromtimestamp(ts, tz=UTC)


def to_timestamp(dt: datetime) -> float:
    """
    Convert datetime to Unix timestamp.

    Args:
        dt: Datetime to convert. If naive, assumes UTC.

    Returns:
        float: Unix timestamp (seconds since epoch)
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def is_market_hours(
    dt: Optional[datetime] = None,
    market_open: time = time(9, 30),
    market_close: time = time(16, 0),
) -> bool:
    """
    Check if given time is during regular market hours (US Eastern).

    Args:
        dt: Datetime to check (default: current time)
        market_open: Market open time (default: 9:30 AM ET)
        market_close: Market close time (default: 4:00 PM ET)

    Returns:
        bool: True if during market hours, False otherwise
    """
    if dt is None:
        dt = utc_now()

    eastern = to_eastern(dt)

    # Check weekday (0=Monday, 4=Friday)
    if eastern.weekday() > 4:
        return False

    current_time = eastern.time()
    return market_open <= current_time < market_close


def is_premarket(dt: Optional[datetime] = None) -> bool:
    """
    Check if given time is during pre-market hours (4:00 AM - 9:30 AM ET).

    Args:
        dt: Datetime to check (default: current time)

    Returns:
        bool: True if during pre-market
    """
    if dt is None:
        dt = utc_now()

    eastern = to_eastern(dt)

    if eastern.weekday() > 4:
        return False

    current_time = eastern.time()
    return time(4, 0) <= current_time < time(9, 30)


def is_afterhours(dt: Optional[datetime] = None) -> bool:
    """
    Check if given time is during after-hours trading (4:00 PM - 8:00 PM ET).

    Args:
        dt: Datetime to check (default: current time)

    Returns:
        bool: True if during after-hours
    """
    if dt is None:
        dt = utc_now()

    eastern = to_eastern(dt)

    if eastern.weekday() > 4:
        return False

    current_time = eastern.time()
    return time(16, 0) <= current_time < time(20, 0)


def get_market_open_time(date: Optional[datetime] = None) -> datetime:
    """
    Get market open time (9:30 AM ET) for a given date.

    Args:
        date: Date to get market open for (default: today)

    Returns:
        datetime: Market open time in UTC
    """
    if date is None:
        date = utc_now()

    eastern = to_eastern(date)
    market_open = eastern.replace(hour=9, minute=30, second=0, microsecond=0)
    return to_utc(market_open)


def get_market_close_time(date: Optional[datetime] = None) -> datetime:
    """
    Get market close time (4:00 PM ET) for a given date.

    Args:
        date: Date to get market close for (default: today)

    Returns:
        datetime: Market close time in UTC
    """
    if date is None:
        date = utc_now()

    eastern = to_eastern(date)
    market_close = eastern.replace(hour=16, minute=0, second=0, microsecond=0)
    return to_utc(market_close)


def format_iso(dt: datetime) -> str:
    """
    Format datetime as ISO 8601 string.

    Args:
        dt: Datetime to format

    Returns:
        str: ISO 8601 formatted string (e.g., "2024-01-15T14:30:00+00:00")
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def parse_iso(s: str) -> datetime:
    """
    Parse ISO 8601 datetime string.

    Args:
        s: ISO 8601 string to parse

    Returns:
        datetime: Parsed datetime with tzinfo (defaults to UTC if not specified)
    """
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


# Compatibility alias for gradual migration
def now() -> datetime:
    """
    Alias for utc_now(). Prefer utc_now() for clarity.

    Returns:
        datetime: Current UTC time
    """
    return utc_now()
