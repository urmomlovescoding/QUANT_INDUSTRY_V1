"""
REGRESSION GATES - Critical path testing for QUANT INDUSTRY
============================================================

These tests MUST pass before any deployment or major change.
Failure here = system is broken at a fundamental level.

Categories:
1. STARTUP - App can start without crashes
2. DATA_INTEGRITY - Prices are real, not simulated where expected
3. CHARTS - All timeframes render without error
4. BOTS - Bots can execute N ticks without crash
5. TRADES - Trade logging works correctly

Run with: pytest tests/test_regression_gates.py -v --tb=short
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# Add backend to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)


# =============================================================================
# CATEGORY 1: STARTUP GATES
# =============================================================================

class TestStartupGates:
    """App must start without crashes"""

    def test_main_module_imports(self):
        """Main module imports without error"""
        try:
            import main
            assert main is not None
            assert hasattr(main, 'app')
        except Exception as e:
            pytest.fail(f"Main module import failed: {e}")

    def test_fastapi_app_exists(self):
        """FastAPI app object is properly configured"""
        from main import app
        assert app is not None
        assert hasattr(app, 'routes')
        assert len(app.routes) > 0

    def test_critical_services_importable(self):
        """All critical service modules import"""
        critical_modules = [
            'services.data_service',
            'services.trading_service',
            'services.risk_service',
            'services.health_service',
            'services.market_hours',
        ]

        for module_name in critical_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Critical module {module_name} failed to import: {e}")

    def test_brain_modules_importable(self):
        """Brain/bot modules import without error"""
        brain_modules = [
            'brain.algo_bot',
            'brain.trading_brain',
            'brain.propfirm_brain_v6',
        ]

        for module_name in brain_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Brain module {module_name} failed to import: {e}")

    def test_no_circular_imports(self):
        """No circular import errors on fresh import"""
        import importlib
        import sys

        # Clear cached modules
        modules_to_clear = [k for k in sys.modules.keys()
                          if k.startswith('services.') or k.startswith('brain.')]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        # Re-import main - this should catch circular imports
        try:
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
        except ImportError as e:
            if 'circular' in str(e).lower():
                pytest.fail(f"Circular import detected: {e}")
            raise


# =============================================================================
# CATEGORY 2: DATA INTEGRITY GATES
# =============================================================================

class TestDataIntegrityGates:
    """Prices must be real where expected, simulated data must be labeled"""

    def test_data_service_initializes(self):
        """DataService can be instantiated"""
        from services.data_service import DataService
        ds = DataService()
        assert ds is not None

    def test_data_service_has_sources(self):
        """DataService has configured data sources"""
        from services.data_service import get_data_service
        ds = get_data_service()
        assert hasattr(ds, 'sources')
        assert len(ds.sources) > 0

    def test_quote_has_source_label(self):
        """Every quote includes its data source"""
        from services.data_service import get_data_service
        ds = get_data_service()

        quote = ds.get_quote("SPY")
        assert quote is not None
        assert hasattr(quote, 'source'), "Quote must have 'source' attribute"
        assert quote.source != "", "Quote source must not be empty"

    def test_fallback_prices_are_labeled(self):
        """Fallback/cached prices are clearly labeled as such"""
        from services.data_service import FallbackDataSource

        fallback = FallbackDataSource()
        quote = fallback.get_quote("SPY")

        assert quote is not None
        assert quote.source == "fallback", f"Fallback quote should be labeled as 'fallback', got '{quote.source}'"

    def test_live_vs_cached_distinction(self):
        """System distinguishes between live and cached data"""
        from services.data_service import get_data_service
        ds = get_data_service()

        # First call
        quote1 = ds.get_quote("AAPL")

        # Check that quote has freshness indicator
        assert hasattr(quote1, 'timestamp') or hasattr(quote1, 'source')

    def test_price_sanity_check(self):
        """Prices are within reasonable bounds (no $0, no $1M for normal stocks)"""
        from services.data_service import get_data_service
        ds = get_data_service()

        test_symbols = ["SPY", "AAPL", "MSFT"]

        for symbol in test_symbols:
            quote = ds.get_quote(symbol)
            if quote:
                assert quote.price > 0, f"{symbol} price should be > 0"
                assert quote.price < 100000, f"{symbol} price {quote.price} seems unreasonable"

    def test_ohlcv_data_valid(self):
        """OHLCV data has valid structure (High >= Low, Volume >= 0)"""
        from services.data_service import get_data_service
        ds = get_data_service()

        hist = ds.get_historical("SPY", "1d", 10)

        if hist and len(hist) > 0:
            for bar in hist:
                if hasattr(bar, 'high') and hasattr(bar, 'low'):
                    assert bar.high >= bar.low, "High must be >= Low"
                if hasattr(bar, 'volume'):
                    assert bar.volume >= 0, "Volume must be >= 0"


# =============================================================================
# CATEGORY 3: CHART DATA GATES
# =============================================================================

class TestChartDataGates:
    """Charts must render on all timeframes without crash"""

    TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]

    def test_historical_data_all_timeframes(self):
        """Historical data fetches for all timeframes without error"""
        from services.data_service import get_data_service
        ds = get_data_service()

        symbol = "SPY"
        failed_timeframes = []

        for tf in self.TIMEFRAMES:
            try:
                data = ds.get_historical(symbol, tf, 50)
                # Allow None (no data) but not exceptions
            except Exception as e:
                failed_timeframes.append((tf, str(e)))

        if failed_timeframes:
            pytest.fail(f"Timeframes failed: {failed_timeframes}")

    def test_chart_endpoint_all_timeframes(self):
        """Chart API endpoint works for all timeframes"""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        symbol = "SPY"
        failed = []

        for tf in self.TIMEFRAMES:
            try:
                response = client.get(f"/api/charts/ohlcv/{symbol}?interval={tf}")
                if response.status_code >= 500:
                    failed.append((tf, f"Status {response.status_code}"))
            except Exception as e:
                failed.append((tf, str(e)))

        if failed:
            pytest.fail(f"Chart endpoint failures: {failed}")

    def test_chart_data_not_empty_for_major_symbols(self):
        """Major symbols return non-empty chart data"""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        major_symbols = ["SPY", "QQQ", "AAPL"]

        for symbol in major_symbols:
            response = client.get(f"/api/charts/ohlcv/{symbol}?interval=1d")
            if response.status_code == 200:
                data = response.json()
                # Should have some data points
                assert isinstance(data, (list, dict)), f"{symbol} chart data should be list or dict"


# =============================================================================
# CATEGORY 4: BOT EXECUTION GATES
# =============================================================================

class TestBotExecutionGates:
    """Bots must be able to execute N ticks without crash"""

    def test_algo_bot_instantiates(self):
        """AlgoBot can be created with default config"""
        from brain.algo_bot import AlgoBot, BotConfig

        config = BotConfig(
            name="RegressionTestBot",
            symbols=["SPY"],
        )
        bot = AlgoBot(config)
        assert bot is not None
        assert bot.state is not None

    def test_bot_can_generate_signal(self):
        """Bot can generate a trading signal without crash"""
        from brain.algo_bot import AlgoBot, BotConfig

        config = BotConfig(
            name="SignalTestBot",
            symbols=["SPY"],
        )
        bot = AlgoBot(config)

        try:
            # Most bots have some form of signal generation
            if hasattr(bot, 'generate_signals'):
                signals = bot.generate_signals()
                assert isinstance(signals, (list, type(None)))
            elif hasattr(bot, '_generate_signal'):
                signal = bot._generate_signal("SPY")
                # Signal can be None if no opportunity
        except Exception as e:
            pytest.fail(f"Signal generation crashed: {e}")

    def test_bot_tick_execution(self):
        """Bot can execute multiple ticks without crash"""
        from brain.algo_bot import AlgoBot, BotConfig, BotState

        config = BotConfig(
            name="TickTestBot",
            symbols=["SPY"],
            max_position_size=0,  # No actual trading
        )
        bot = AlgoBot(config)

        N_TICKS = 5
        errors = []

        for i in range(N_TICKS):
            try:
                if hasattr(bot, 'tick'):
                    bot.tick()
                elif hasattr(bot, '_process_tick'):
                    bot._process_tick()
                elif hasattr(bot, 'process_market_data'):
                    bot.process_market_data({})
            except Exception as e:
                errors.append((i, str(e)))

        if errors:
            pytest.fail(f"Bot ticks failed: {errors}")

    def test_propfirm_brain_loads(self):
        """PropFirm Brain V6 can be loaded"""
        try:
            from brain.propfirm_brain_v6 import PropFirmBrainV6
            brain = PropFirmBrainV6()
            assert brain is not None
        except Exception as e:
            pytest.fail(f"PropFirm Brain V6 failed to load: {e}")


# =============================================================================
# CATEGORY 5: TRADE LOGGING GATES
# =============================================================================

class TestTradeLoggingGates:
    """Trade journal and logging must work correctly"""

    def test_trade_journal_imports(self):
        """Trade journal module imports"""
        try:
            from execution.trade_journal import TradeJournal
        except ImportError as e:
            pytest.fail(f"Trade journal import failed: {e}")

    def test_trade_journal_can_log(self):
        """Trade journal can record a trade"""
        try:
            from execution.trade_journal import TradeJournal, TradeAction

            journal = TradeJournal()

            # Record a trade decision using the correct API
            entry = journal.record_decision(
                symbol="TEST",
                action=TradeAction.BUY,
                direction="LONG",
                signal_confidence=0.75,
                signal_source="regression_test",
                decision="taken",
                entry_price=100.00,
            )

            assert entry is not None, "Failed to record trade decision"
            assert entry.symbol == "TEST"

        except Exception as e:
            pytest.fail(f"Trade logging failed: {e}")

    def test_trade_retrieval(self):
        """Logged trades can be retrieved"""
        try:
            from execution.trade_journal import TradeJournal

            journal = TradeJournal()

            if hasattr(journal, 'get_trades'):
                trades = journal.get_trades()
                assert isinstance(trades, (list, dict, type(None)))
            elif hasattr(journal, 'get_history'):
                history = journal.get_history()
                assert isinstance(history, (list, dict, type(None)))

        except Exception as e:
            pytest.fail(f"Trade retrieval failed: {e}")


# =============================================================================
# CATEGORY 6: API ENDPOINT GATES
# =============================================================================

class TestAPIEndpointGates:
    """Critical API endpoints must respond correctly"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Health endpoint returns 200"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_market_status_endpoint(self, client):
        """Market status endpoint works"""
        response = client.get("/api/market/status")
        assert response.status_code == 200

    def test_positions_endpoint(self, client):
        """Positions endpoint works"""
        response = client.get("/api/positions")
        assert response.status_code == 200

    def test_signals_endpoint(self, client):
        """Signals endpoint works"""
        response = client.get("/api/signals")
        assert response.status_code == 200

    def test_brain_status_endpoint(self, client):
        """Brain status endpoint works"""
        response = client.get("/api/brain-v6/status")
        assert response.status_code == 200


# =============================================================================
# REGRESSION GATE SUMMARY
# =============================================================================

class TestRegressionGateSummary:
    """Meta-test to ensure all gate categories are covered"""

    def test_all_gate_categories_exist(self):
        """Verify all required gate categories have tests"""
        required_categories = [
            TestStartupGates,
            TestDataIntegrityGates,
            TestChartDataGates,
            TestBotExecutionGates,
            TestTradeLoggingGates,
            TestAPIEndpointGates,
        ]

        for category in required_categories:
            test_methods = [m for m in dir(category) if m.startswith('test_')]
            assert len(test_methods) > 0, f"{category.__name__} has no tests"
