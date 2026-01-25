"""
QUANT INDUSTRY - Market Hours Service
Accurate US stock market hours detection with pre-market, after-hours, and holiday support
"""

from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Dict, Tuple

import pytz

# Eastern timezone for US markets
ET = pytz.timezone('US/Eastern')


class MarketSession(Enum):
    """Market session types"""
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"


# US Stock Market Holidays 2024-2026
# Markets closed entirely on these dates
US_MARKET_HOLIDAYS = {
    # 2024
    date(2024, 1, 1),   # New Year's Day
    date(2024, 1, 15),  # MLK Day
    date(2024, 2, 19),  # Presidents Day
    date(2024, 3, 29),  # Good Friday
    date(2024, 5, 27),  # Memorial Day
    date(2024, 6, 19),  # Juneteenth
    date(2024, 7, 4),   # Independence Day
    date(2024, 9, 2),   # Labor Day
    date(2024, 11, 28), # Thanksgiving
    date(2024, 12, 25), # Christmas
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # MLK Day
    date(2025, 2, 17),  # Presidents Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}

# Early close days (1:00 PM ET)
US_EARLY_CLOSE_DAYS = {
    # 2024
    date(2024, 7, 3),   # Day before Independence Day
    date(2024, 11, 29), # Day after Thanksgiving
    date(2024, 12, 24), # Christmas Eve
    # 2025
    date(2025, 7, 3),   # Day before Independence Day
    date(2025, 11, 28), # Day after Thanksgiving
    date(2025, 12, 24), # Christmas Eve
    # 2026
    date(2026, 11, 27), # Day after Thanksgiving
    date(2026, 12, 24), # Christmas Eve
}

# Market session times (Eastern Time)
PRE_MARKET_START = time(4, 0)    # 4:00 AM ET
REGULAR_OPEN = time(9, 30)       # 9:30 AM ET
REGULAR_CLOSE = time(16, 0)      # 4:00 PM ET
EARLY_CLOSE = time(13, 0)        # 1:00 PM ET (early close days)
AFTER_HOURS_END = time(20, 0)    # 8:00 PM ET


def get_eastern_now() -> datetime:
    """Get current time in Eastern timezone"""
    return datetime.now(ET)


def is_weekend(dt: datetime = None) -> bool:
    """Check if it's a weekend (Saturday=5, Sunday=6)"""
    if dt is None:
        dt = get_eastern_now()
    return dt.weekday() >= 5


def is_holiday(dt: datetime = None) -> bool:
    """Check if it's a market holiday"""
    if dt is None:
        dt = get_eastern_now()
    return dt.date() in US_MARKET_HOLIDAYS


def is_early_close_day(dt: datetime = None) -> bool:
    """Check if it's an early close day"""
    if dt is None:
        dt = get_eastern_now()
    return dt.date() in US_EARLY_CLOSE_DAYS


def get_market_session(dt: datetime = None) -> Tuple[MarketSession, Dict]:
    """
    Determine current market session and return status info

    Returns:
        Tuple of (MarketSession, status_dict) with session info
    """
    if dt is None:
        dt = get_eastern_now()

    current_time = dt.time()
    current_date = dt.date()
    weekday = dt.weekday()

    # Build status dict
    status = {
        "session": MarketSession.CLOSED.value,
        "is_open": False,
        "is_pre_market": False,
        "is_after_hours": False,
        "is_weekend": weekday >= 5,
        "is_holiday": current_date in US_MARKET_HOLIDAYS,
        "is_early_close": current_date in US_EARLY_CLOSE_DAYS,
        "current_time_et": dt.strftime("%Y-%m-%d %H:%M:%S ET"),
        "next_open": None,
        "next_close": None,
        "reason": None
    }

    # Weekend check
    if weekday >= 5:
        days_until_monday = (7 - weekday) % 7
        if days_until_monday == 0:
            days_until_monday = 1 if weekday == 6 else 2
        next_monday = current_date + timedelta(days=days_until_monday)
        status["reason"] = "Weekend - Markets Closed"
        status["next_open"] = f"{next_monday} 09:30 ET"
        return MarketSession.CLOSED, status

    # Holiday check
    if current_date in US_MARKET_HOLIDAYS:
        next_trading = current_date + timedelta(days=1)
        while next_trading.weekday() >= 5 or next_trading in US_MARKET_HOLIDAYS:
            next_trading += timedelta(days=1)
        status["reason"] = "Holiday - Markets Closed"
        status["next_open"] = f"{next_trading} 09:30 ET"
        return MarketSession.CLOSED, status

    # Determine close time for today
    close_time = EARLY_CLOSE if current_date in US_EARLY_CLOSE_DAYS else REGULAR_CLOSE

    # Pre-market: 4:00 AM - 9:30 AM
    if PRE_MARKET_START <= current_time < REGULAR_OPEN:
        status["session"] = MarketSession.PRE_MARKET.value
        status["is_pre_market"] = True
        status["reason"] = "Pre-Market Trading"
        status["next_open"] = f"{current_date} 09:30 ET"
        return MarketSession.PRE_MARKET, status

    # Regular hours: 9:30 AM - 4:00 PM (or 1:00 PM on early close)
    if REGULAR_OPEN <= current_time < close_time:
        status["session"] = MarketSession.REGULAR.value
        status["is_open"] = True
        status["reason"] = "Regular Market Hours"
        if status["is_early_close"]:
            status["reason"] += " (Early Close Today)"
        status["next_close"] = f"{current_date} {close_time.strftime('%H:%M')} ET"
        return MarketSession.REGULAR, status

    # After hours: 4:00 PM - 8:00 PM (not available on early close days after 1 PM close)
    if close_time <= current_time < AFTER_HOURS_END:
        # On early close days, after-hours still runs 1 PM - 8 PM
        status["session"] = MarketSession.AFTER_HOURS.value
        status["is_after_hours"] = True
        status["reason"] = "After-Hours Trading"
        status["next_close"] = f"{current_date} 20:00 ET"
        return MarketSession.AFTER_HOURS, status

    # Closed: Before 4 AM or After 8 PM
    next_trading = current_date
    if current_time >= AFTER_HOURS_END:
        next_trading = current_date + timedelta(days=1)

    while next_trading.weekday() >= 5 or next_trading in US_MARKET_HOLIDAYS:
        next_trading += timedelta(days=1)

    status["reason"] = "Markets Closed"
    status["next_open"] = f"{next_trading} 04:00 ET (Pre-Market) / 09:30 ET (Regular)"
    return MarketSession.CLOSED, status


def is_market_open() -> bool:
    """Simple check if regular market is open"""
    session, _ = get_market_session()
    return session == MarketSession.REGULAR


def is_extended_hours() -> bool:
    """Check if in pre-market or after-hours"""
    session, _ = get_market_session()
    return session in (MarketSession.PRE_MARKET, MarketSession.AFTER_HOURS)


def can_trade() -> bool:
    """Check if any trading is possible (regular, pre, or after hours)"""
    session, _ = get_market_session()
    return session != MarketSession.CLOSED


def get_market_status() -> Dict:
    """Get comprehensive market status for API response"""
    session, status = get_market_session()

    # Calculate time until next event
    now = get_eastern_now()
    current_date = now.date()

    if status["is_open"]:
        close_time = EARLY_CLOSE if status["is_early_close"] else REGULAR_CLOSE
        close_dt = ET.localize(datetime.combine(current_date, close_time))
        time_until_close = close_dt - now
        status["time_until_close"] = str(time_until_close).split('.')[0]

    if status["is_pre_market"]:
        open_dt = ET.localize(datetime.combine(current_date, REGULAR_OPEN))
        time_until_open = open_dt - now
        status["time_until_open"] = str(time_until_open).split('.')[0]

    return status


def get_last_trading_day() -> date:
    """Get the most recent trading day"""
    now = get_eastern_now()
    current_date = now.date()

    # If before 4 AM, use yesterday
    if now.time() < PRE_MARKET_START:
        current_date = current_date - timedelta(days=1)

    # Walk back to find a trading day
    while current_date.weekday() >= 5 or current_date in US_MARKET_HOLIDAYS:
        current_date = current_date - timedelta(days=1)

    return current_date


def get_next_trading_day() -> date:
    """Get the next trading day"""
    now = get_eastern_now()
    next_date = now.date()

    # If after hours ended, start from tomorrow
    if now.time() >= AFTER_HOURS_END:
        next_date = next_date + timedelta(days=1)

    # Walk forward to find a trading day
    while next_date.weekday() >= 5 or next_date in US_MARKET_HOLIDAYS:
        next_date = next_date + timedelta(days=1)

    return next_date


# Convenience exports
__all__ = [
    'MarketSession',
    'can_trade',
    'get_eastern_now',
    'get_last_trading_day',
    'get_market_session',
    'get_market_status',
    'get_next_trading_day',
    'is_extended_hours',
    'is_holiday',
    'is_market_open',
    'is_weekend',
]
