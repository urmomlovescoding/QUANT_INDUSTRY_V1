"""
Tests for Market Hours Service
"""
from datetime import date, datetime
from unittest.mock import patch

from services.market_hours import (
    ET,
    US_MARKET_HOLIDAYS,
    MarketSession,
    can_trade,
    get_last_trading_day,
    get_market_session,
    get_market_status,
    get_next_trading_day,
    is_holiday,
    is_weekend,
)


class TestMarketSession:
    """Test market session detection"""

    def test_weekend_saturday(self):
        """Saturday should be closed"""
        saturday = ET.localize(datetime(2026, 1, 24, 12, 0, 0))  # Saturday
        session, status = get_market_session(saturday)

        assert session == MarketSession.CLOSED
        assert status["is_weekend"] is True
        assert status["is_open"] is False
        assert "Weekend" in status["reason"]

    def test_weekend_sunday(self):
        """Sunday should be closed"""
        sunday = ET.localize(datetime(2026, 1, 25, 12, 0, 0))  # Sunday
        session, status = get_market_session(sunday)

        assert session == MarketSession.CLOSED
        assert status["is_weekend"] is True

    def test_pre_market(self):
        """4:00 AM - 9:30 AM should be pre-market"""
        pre_market = ET.localize(datetime(2026, 1, 26, 7, 0, 0))  # Monday 7 AM
        session, status = get_market_session(pre_market)

        assert session == MarketSession.PRE_MARKET
        assert status["is_pre_market"] is True
        assert status["is_open"] is False

    def test_regular_hours_open(self):
        """9:30 AM - 4:00 PM should be regular hours"""
        regular = ET.localize(datetime(2026, 1, 26, 12, 0, 0))  # Monday noon
        session, status = get_market_session(regular)

        assert session == MarketSession.REGULAR
        assert status["is_open"] is True
        assert status["is_pre_market"] is False
        assert status["is_after_hours"] is False

    def test_regular_hours_start(self):
        """Exactly 9:30 AM should be regular hours"""
        open_time = ET.localize(datetime(2026, 1, 26, 9, 30, 0))
        session, status = get_market_session(open_time)

        assert session == MarketSession.REGULAR
        assert status["is_open"] is True

    def test_after_hours(self):
        """4:00 PM - 8:00 PM should be after hours"""
        after_hours = ET.localize(datetime(2026, 1, 26, 18, 0, 0))  # Monday 6 PM
        session, status = get_market_session(after_hours)

        assert session == MarketSession.AFTER_HOURS
        assert status["is_after_hours"] is True
        assert status["is_open"] is False

    def test_closed_late_night(self):
        """After 8 PM should be closed"""
        late = ET.localize(datetime(2026, 1, 26, 21, 0, 0))  # Monday 9 PM
        session, status = get_market_session(late)

        assert session == MarketSession.CLOSED
        assert status["is_open"] is False

    def test_closed_early_morning(self):
        """Before 4 AM should be closed"""
        early = ET.localize(datetime(2026, 1, 26, 3, 0, 0))  # Monday 3 AM
        session, status = get_market_session(early)

        assert session == MarketSession.CLOSED


class TestHolidays:
    """Test holiday detection"""

    def test_christmas_closed(self):
        """Christmas should be closed"""
        christmas = ET.localize(datetime(2025, 12, 25, 12, 0, 0))
        session, status = get_market_session(christmas)

        assert session == MarketSession.CLOSED
        assert status["is_holiday"] is True

    def test_mlk_day_closed(self):
        """MLK Day should be closed"""
        mlk = ET.localize(datetime(2026, 1, 19, 12, 0, 0))
        session, status = get_market_session(mlk)

        assert session == MarketSession.CLOSED
        assert status["is_holiday"] is True

    def test_holiday_list_populated(self):
        """Holiday list should have entries"""
        assert len(US_MARKET_HOLIDAYS) > 20  # Multiple years of holidays


class TestHelperFunctions:
    """Test helper functions"""

    def test_is_weekend_saturday(self):
        saturday = ET.localize(datetime(2026, 1, 24, 12, 0, 0))
        assert is_weekend(saturday) is True

    def test_is_weekend_monday(self):
        monday = ET.localize(datetime(2026, 1, 26, 12, 0, 0))
        assert is_weekend(monday) is False

    def test_is_holiday(self):
        christmas = ET.localize(datetime(2025, 12, 25, 12, 0, 0))
        assert is_holiday(christmas) is True

    def test_is_not_holiday(self):
        regular_day = ET.localize(datetime(2026, 1, 26, 12, 0, 0))
        assert is_holiday(regular_day) is False

    def test_can_trade_regular_hours(self):
        """Should be able to trade during regular hours"""
        regular = ET.localize(datetime(2026, 1, 26, 12, 0, 0))
        with patch('services.market_hours.get_eastern_now', return_value=regular):
            assert can_trade() is True

    def test_cannot_trade_weekend(self):
        """Should not be able to trade on weekends"""
        saturday = ET.localize(datetime(2026, 1, 24, 12, 0, 0))
        with patch('services.market_hours.get_eastern_now', return_value=saturday):
            assert can_trade() is False


class TestTradingDays:
    """Test trading day calculations"""

    def test_last_trading_day_from_weekend(self):
        """Last trading day from Saturday should be Friday"""
        saturday = ET.localize(datetime(2026, 1, 24, 12, 0, 0))
        with patch('services.market_hours.get_eastern_now', return_value=saturday):
            last_day = get_last_trading_day()
            assert last_day == date(2026, 1, 23)  # Friday

    def test_next_trading_day_from_weekend(self):
        """Next trading day from Saturday should be Monday"""
        saturday = ET.localize(datetime(2026, 1, 24, 12, 0, 0))
        with patch('services.market_hours.get_eastern_now', return_value=saturday):
            next_day = get_next_trading_day()
            assert next_day == date(2026, 1, 26)  # Monday


class TestMarketStatus:
    """Test market status endpoint data"""

    def test_status_has_required_fields(self):
        """Status should have all required fields"""
        status = get_market_status()

        required_fields = [
            'session', 'is_open', 'is_pre_market',
            'is_after_hours', 'is_weekend', 'is_holiday',
            'current_time_et', 'reason'
        ]

        for field in required_fields:
            assert field in status, f"Missing field: {field}"

    def test_status_session_valid(self):
        """Session should be a valid value"""
        status = get_market_status()
        valid_sessions = ['closed', 'pre_market', 'regular', 'after_hours']
        assert status['session'] in valid_sessions
