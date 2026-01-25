"""
Tests for Data Service
"""
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

from services.data_service import FALLBACK_PRICES, OHLCV, DataService, FallbackDataSource, Quote


class TestQuote:
    """Test Quote dataclass"""

    def test_quote_creation(self):
        """Test creating a Quote"""
        quote = Quote(
            symbol="SPY",
            price=688.44,
            bid=688.40,
            ask=688.48,
            volume=1000000,
            change=2.50,
            change_pct=0.36,
            high=690.00,
            low=686.00,
            open=687.00,
            prev_close=685.94,
            timestamp=datetime.now(),
            source="test"
        )

        assert quote.symbol == "SPY"
        assert quote.price == 688.44
        assert quote.source == "test"

    def test_quote_market_session_default(self):
        """Quote should have market_session field"""
        quote = Quote(
            symbol="SPY",
            price=100.0,
            bid=99.9,
            ask=100.1,
            volume=1000,
            change=1.0,
            change_pct=1.0,
            high=101.0,
            low=99.0,
            open=100.0,
            prev_close=99.0,
            timestamp=datetime.now()
        )

        assert hasattr(quote, 'market_session')
        assert hasattr(quote, 'is_market_open')


class TestFallbackPrices:
    """Test fallback price data"""

    def test_fallback_prices_exist(self):
        """Fallback prices should have common symbols"""
        common_symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA']
        for symbol in common_symbols:
            assert symbol in FALLBACK_PRICES, f"Missing fallback price for {symbol}"

    def test_fallback_prices_reasonable(self):
        """Fallback prices should be positive and reasonable"""
        # Futures contracts can be >10000, Bitcoin futures >100000
        futures_symbols = {'ES', 'NQ', 'MNQ', 'MES', 'RTY', 'YM', 'MYM', 'CL', 'GC'}
        crypto_futures = {'BTC', 'MBT', 'ETH'}  # Bitcoin/Crypto futures
        for symbol, price in FALLBACK_PRICES.items():
            assert price > 0, f"Price for {symbol} should be positive"
            if symbol in crypto_futures:
                max_price = 200000  # Bitcoin can be >100k
            elif symbol in futures_symbols:
                max_price = 50000
            else:
                max_price = 10000
            assert price < max_price, f"Price for {symbol} seems too high"


class TestFallbackDataSource:
    """Test FallbackDataSource"""

    def test_fallback_returns_quote(self):
        """Fallback should return a Quote object"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            source = FallbackDataSource(db_path=db_path)
            quote = source.get_quote("SPY")

            assert quote is not None
            assert isinstance(quote, Quote)
            assert quote.symbol == "SPY"
            assert quote.source == "fallback"

    def test_fallback_unknown_symbol(self):
        """Fallback should handle unknown symbols"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            source = FallbackDataSource(db_path=db_path)
            quote = source.get_quote("UNKNOWNSYMBOL123")

            assert quote is not None
            assert quote.price > 0

    def test_fallback_symbol_case_insensitive(self):
        """Fallback should handle different cases"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            source = FallbackDataSource(db_path=db_path)

            quote_upper = source.get_quote("SPY")
            quote_lower = source.get_quote("spy")

            assert quote_upper.symbol == quote_lower.symbol == "SPY"

    @patch('services.data_service.HAS_MARKET_HOURS', True)
    @patch('services.data_service.get_market_session')
    def test_fallback_stable_when_closed(self, mock_session):
        """Prices should be stable when market is closed"""
        from services.data_service import MarketSession

        # Mock market as closed
        mock_session.return_value = (
            MarketSession.CLOSED,
            {'is_open': False, 'is_pre_market': False, 'is_after_hours': False}
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            source = FallbackDataSource(db_path=db_path)

            # Get two quotes
            quote1 = source.get_quote("SPY")
            quote2 = source.get_quote("SPY")

            # Should be same price when closed
            assert quote1.price == quote2.price
            assert quote1.is_market_open is False


class TestDataService:
    """Test DataService"""

    def test_data_service_initialization(self):
        """DataService should initialize without errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DataService(cache_dir=tmpdir)
            assert service is not None
            assert len(service.sources) > 0

    def test_data_service_has_fallback(self):
        """DataService should always have fallback source"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DataService(cache_dir=tmpdir)
            source_names = [s.name for s in service.sources]
            assert "fallback" in source_names

    def test_get_quote_returns_data(self):
        """get_quote should return data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DataService(cache_dir=tmpdir, force_live=False)
            quote = service.get_quote("SPY", allow_fallback=True)

            assert quote is not None
            assert quote.symbol == "SPY"
            assert quote.price > 0

    def test_get_multiple_quotes(self):
        """get_quotes should return multiple quotes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DataService(cache_dir=tmpdir, force_live=False)
            quotes = service.get_quotes(["SPY", "QQQ"])

            assert len(quotes) >= 1
            for symbol, quote in quotes.items():
                assert quote.price > 0


class TestOHLCV:
    """Test OHLCV dataclass"""

    def test_ohlcv_creation(self):
        """Test creating an OHLCV object"""
        ohlcv = OHLCV(
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000000
        )

        assert ohlcv.open == 100.0
        assert ohlcv.high == 105.0
        assert ohlcv.close == 103.0


class TestCaching:
    """Test caching functionality"""

    def test_cache_stores_quote(self):
        """Cache should store and return quotes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DataService(cache_dir=tmpdir, force_live=False)

            # First call - should fetch
            quote1 = service.get_quote("SPY", allow_fallback=True)

            # Second call - should be cached
            quote2 = service.get_quote("SPY", allow_fallback=True)

            # Both should return data
            assert quote1 is not None
            assert quote2 is not None

    def test_cache_cleanup(self):
        """Cache cleanup should work without errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DataService(cache_dir=tmpdir)
            service.cleanup_cache(max_age=0)  # Should cleanup everything
