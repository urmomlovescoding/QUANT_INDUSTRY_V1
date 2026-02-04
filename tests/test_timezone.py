"""
Tests for timezone utilities.

These tests verify that the timezone utilities work correctly and provide
deterministic behavior for backtesting and consistent timestamps across systems.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch


class TestUtcNow:
    """Tests for utc_now() function."""

    def test_utc_now_returns_datetime(self):
        """utc_now() should return a datetime object."""
        from backend.utils.timezone import utc_now

        result = utc_now()
        assert isinstance(result, datetime)

    def test_utc_now_has_tzinfo(self):
        """utc_now() should return timezone-aware datetime."""
        from backend.utils.timezone import utc_now

        result = utc_now()
        assert result.tzinfo is not None

    def test_utc_now_is_utc(self):
        """utc_now() should return UTC time."""
        from backend.utils.timezone import utc_now, UTC

        result = utc_now()
        assert result.tzinfo == UTC

    def test_utc_now_is_current_time(self):
        """utc_now() should return approximately current time."""
        from backend.utils.timezone import utc_now

        before = datetime.now(timezone.utc)
        result = utc_now()
        after = datetime.now(timezone.utc)

        assert before <= result <= after


class TestToUtc:
    """Tests for to_utc() function."""

    def test_naive_datetime_assumed_utc(self):
        """Naive datetime should be assumed to be UTC."""
        from backend.utils.timezone import to_utc, UTC

        naive = datetime(2024, 1, 15, 12, 0, 0)
        result = to_utc(naive)

        assert result.tzinfo == UTC
        assert result.hour == 12

    def test_aware_datetime_converted(self):
        """Aware datetime should be converted to UTC."""
        from backend.utils.timezone import to_utc, UTC

        # Create datetime in a different timezone (UTC+5)
        tz_plus5 = timezone(timedelta(hours=5))
        aware = datetime(2024, 1, 15, 17, 0, 0, tzinfo=tz_plus5)  # 5pm UTC+5 = 12pm UTC

        result = to_utc(aware)

        assert result.tzinfo == UTC
        assert result.hour == 12


class TestToEastern:
    """Tests for to_eastern() function."""

    def test_utc_to_eastern_winter(self):
        """UTC should convert to Eastern correctly (winter = UTC-5)."""
        from backend.utils.timezone import to_eastern, UTC

        # January 15, 2024 12:00 UTC = 7:00 AM Eastern (EST, UTC-5)
        utc_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = to_eastern(utc_time)

        # During EST (winter), Eastern is UTC-5
        assert result.hour == 7

    def test_naive_datetime_assumed_utc(self):
        """Naive datetime should be assumed UTC before converting."""
        from backend.utils.timezone import to_eastern

        naive = datetime(2024, 1, 15, 12, 0, 0)
        result = to_eastern(naive)

        assert result.tzinfo is not None
        assert result.hour == 7  # UTC-5 in winter


class TestTimestampConversions:
    """Tests for timestamp conversion functions."""

    def test_from_timestamp(self):
        """from_timestamp() should convert Unix timestamp to UTC datetime."""
        from backend.utils.timezone import from_timestamp, UTC

        # 1705320000 = January 15, 2024 12:00:00 UTC
        ts = 1705320000
        result = from_timestamp(ts)

        assert result.tzinfo == UTC
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12

    def test_to_timestamp(self):
        """to_timestamp() should convert datetime to Unix timestamp."""
        from backend.utils.timezone import to_timestamp, UTC

        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = to_timestamp(dt)

        assert result == 1705320000

    def test_roundtrip_timestamp(self):
        """Converting to timestamp and back should preserve time."""
        from backend.utils.timezone import from_timestamp, to_timestamp, utc_now

        original = utc_now()
        ts = to_timestamp(original)
        result = from_timestamp(ts)

        # Allow 1 microsecond difference due to float precision
        assert abs((original - result).total_seconds()) < 0.001


class TestMarketHours:
    """Tests for market hours detection."""

    def test_market_open_during_trading_hours(self):
        """is_market_hours() should return True during trading hours."""
        from backend.utils.timezone import is_market_hours, UTC

        # Monday January 15, 2024 at 2:30 PM UTC = 9:30 AM Eastern (market open)
        dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=UTC)
        assert is_market_hours(dt) is True

    def test_market_closed_after_hours(self):
        """is_market_hours() should return False after market close."""
        from backend.utils.timezone import is_market_hours, UTC

        # Monday January 15, 2024 at 9:00 PM UTC = 4:00 PM Eastern (market closed)
        dt = datetime(2024, 1, 15, 21, 0, 0, tzinfo=UTC)
        assert is_market_hours(dt) is False

    def test_market_closed_on_weekend(self):
        """is_market_hours() should return False on weekends."""
        from backend.utils.timezone import is_market_hours, UTC

        # Saturday January 13, 2024 at 2:30 PM UTC
        dt = datetime(2024, 1, 13, 14, 30, 0, tzinfo=UTC)
        assert is_market_hours(dt) is False

    def test_premarket(self):
        """is_premarket() should detect pre-market hours."""
        from backend.utils.timezone import is_premarket, UTC

        # Monday January 15, 2024 at 1:00 PM UTC = 8:00 AM Eastern (pre-market)
        dt = datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC)
        assert is_premarket(dt) is True

    def test_afterhours(self):
        """is_afterhours() should detect after-hours trading."""
        from backend.utils.timezone import is_afterhours, UTC

        # Monday January 15, 2024 at 10:00 PM UTC = 5:00 PM Eastern (after-hours)
        dt = datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC)
        assert is_afterhours(dt) is True


class TestIsoFormatting:
    """Tests for ISO format functions."""

    def test_format_iso(self):
        """format_iso() should produce valid ISO 8601 string."""
        from backend.utils.timezone import format_iso, UTC

        dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=UTC)
        result = format_iso(dt)

        assert "2024-01-15" in result
        assert "12:30:45" in result
        assert "+00:00" in result

    def test_parse_iso(self):
        """parse_iso() should parse ISO 8601 strings."""
        from backend.utils.timezone import parse_iso, UTC

        result = parse_iso("2024-01-15T12:30:45+00:00")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.tzinfo is not None

    def test_parse_iso_with_z(self):
        """parse_iso() should handle 'Z' suffix for UTC."""
        from backend.utils.timezone import parse_iso

        result = parse_iso("2024-01-15T12:30:45Z")

        assert result.hour == 12
        assert result.tzinfo is not None

    def test_roundtrip_iso(self):
        """Formatting and parsing should be reversible."""
        from backend.utils.timezone import format_iso, parse_iso, utc_now

        original = utc_now().replace(microsecond=0)  # ISO doesn't always preserve microseconds
        formatted = format_iso(original)
        result = parse_iso(formatted)

        assert result == original


class TestMarketOpenCloseTimes:
    """Tests for market open/close time functions."""

    def test_get_market_open_time(self):
        """get_market_open_time() should return 9:30 AM Eastern in UTC."""
        from backend.utils.timezone import get_market_open_time, to_eastern, UTC

        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = get_market_open_time(dt)

        # Should be in UTC
        assert result.tzinfo == UTC

        # Convert to Eastern to verify it's 9:30 AM
        eastern = to_eastern(result)
        assert eastern.hour == 9
        assert eastern.minute == 30

    def test_get_market_close_time(self):
        """get_market_close_time() should return 4:00 PM Eastern in UTC."""
        from backend.utils.timezone import get_market_close_time, to_eastern, UTC

        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = get_market_close_time(dt)

        # Should be in UTC
        assert result.tzinfo == UTC

        # Convert to Eastern to verify it's 4:00 PM
        eastern = to_eastern(result)
        assert eastern.hour == 16
        assert eastern.minute == 0


class TestNowAlias:
    """Tests for now() alias function."""

    def test_now_is_utc_now(self):
        """now() should be equivalent to utc_now()."""
        from backend.utils.timezone import now, utc_now

        before = utc_now()
        result = now()
        after = utc_now()

        assert before <= result <= after
        assert result.tzinfo is not None
