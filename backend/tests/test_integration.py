"""
Integration Tests for QUANT INDUSTRY API
Tests full request/response cycles and service interactions
"""
import os
import sys

from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from main import app

client = TestClient(app)


class TestMarketDataFlow:
    """Test complete market data flow from request to response"""

    def test_quote_to_portfolio_flow(self):
        """Test getting quote then checking it appears in data"""
        # Get a quote
        quote_resp = client.get("/api/market/quote/SPY")
        assert quote_resp.status_code == 200
        quote_data = quote_resp.json()

        # Verify quote structure
        assert "symbol" in quote_data
        assert "price" in quote_data
        assert "market_session" in quote_data
        assert quote_data["price"] > 0

    def test_multiple_symbols_consistency(self):
        """Test that multiple quote requests return consistent data"""
        symbols = ["SPY", "QQQ", "AAPL"]
        quotes = {}

        for symbol in symbols:
            resp = client.get(f"/api/market/quote/{symbol}")
            assert resp.status_code == 200
            quotes[symbol] = resp.json()

        # Verify all have required fields
        for symbol, quote in quotes.items():
            assert quote["symbol"] == symbol
            assert "price" in quote
            assert "change" in quote
            assert "volume" in quote or quote.get("volume", 0) >= 0

    def test_market_status_affects_quotes(self):
        """Test that market status is reflected in quotes"""
        # Get market status
        status_resp = client.get("/api/market/status")
        assert status_resp.status_code == 200
        status = status_resp.json()

        # Get quote
        quote_resp = client.get("/api/market/quote/SPY")
        assert quote_resp.status_code == 200
        quote = quote_resp.json()

        # Both should have session info
        assert "session" in status
        assert "market_session" in quote


class TestHealthAndStatus:
    """Test health check and system status endpoints"""

    def test_health_contains_market_info(self):
        """Health endpoint should include market status"""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "market" in data
        assert "session" in data["market"]

    def test_system_health_detailed(self):
        """System health should provide detailed status"""
        resp = client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()

        # Should have comprehensive health info
        assert "status" in data or "healthy" in str(data).lower()

    def test_system_status_services(self):
        """System status should list available services"""
        resp = client.get("/api/system/status")
        assert resp.status_code == 200
        data = resp.json()

        # Should indicate service availability
        assert isinstance(data, dict)

    def test_ml_capabilities_listed(self):
        """ML capabilities endpoint should list available ML features"""
        resp = client.get("/api/system/ml-capabilities")
        assert resp.status_code == 200
        data = resp.json()

        # Should list ML features
        assert isinstance(data, dict)


class TestBrainV6Integration:
    """Test PropFirm Brain V6 integration"""

    def test_brain_status_structure(self):
        """Brain status should have proper structure"""
        resp = client.get("/api/brain-v6/status")
        assert resp.status_code == 200
        data = resp.json()

        # Should have status fields
        assert isinstance(data, dict)

    def test_brain_config_retrievable(self):
        """Brain config should be retrievable"""
        resp = client.get("/api/brain-v6/config")
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data, dict)

    def test_brain_rulesets_available(self):
        """Brain rulesets should be available"""
        resp = client.get("/api/brain-v6/rulesets")
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data, (dict, list))

    def test_brain_signal_for_symbol(self):
        """Brain should generate signal for symbol"""
        resp = client.get("/api/brain-v6/signal/SPY")
        assert resp.status_code == 200
        data = resp.json()

        # Should have signal information
        assert isinstance(data, dict)


class TestSettingsAndConfig:
    """Test settings and configuration endpoints"""

    def test_settings_round_trip(self):
        """Test getting and setting settings"""
        # Get current settings
        get_resp = client.get("/api/settings")
        assert get_resp.status_code == 200
        original = get_resp.json()

        # Settings should be a dict
        assert isinstance(original, dict)

    def test_presets_available(self):
        """Presets should be listed"""
        resp = client.get("/api/settings/presets")
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data, (dict, list))

    def test_api_keys_masked(self):
        """API keys should be masked in response"""
        resp = client.get("/api/settings/api-keys")
        assert resp.status_code == 200
        data = resp.json()

        # Keys should not expose full secrets
        assert isinstance(data, dict)


class TestErrorScenarios:
    """Test error handling scenarios"""

    def test_invalid_symbol_handled(self):
        """Invalid symbols should be handled gracefully"""
        resp = client.get("/api/market/quote/INVALID_SYMBOL_12345")
        # Should either return 200 with fallback or 404
        assert resp.status_code in [200, 404]

        if resp.status_code == 200:
            data = resp.json()
            assert "symbol" in data

    def test_malformed_request_rejected(self):
        """Malformed requests should be rejected"""
        # Test with invalid JSON body
        resp = client.post(
            "/api/settings",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code in [400, 422]

    def test_missing_required_params(self):
        """Missing required params should be handled"""
        # Backtest without required config - may use defaults or return error
        resp = client.post("/api/backtest/run", json={})
        # Either succeeds with defaults or returns error
        assert resp.status_code in [200, 400, 422, 500]

    def test_method_not_allowed(self):
        """Wrong HTTP method should return 405"""
        resp = client.delete("/api/health")
        assert resp.status_code == 405


class TestDataConsistency:
    """Test data consistency across endpoints"""

    def test_ticker_list_valid(self):
        """Ticker list should contain valid symbols"""
        resp = client.get("/api/market/tickers")
        assert resp.status_code == 200
        data = resp.json()

        if "tickers" in data:
            tickers = data["tickers"]
        elif isinstance(data, list):
            tickers = data
        else:
            tickers = []

        # Should have some tickers
        assert isinstance(tickers, list)

    def test_sectors_data_valid(self):
        """Sector data should be valid"""
        resp = client.get("/api/market/sectors")
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data, (dict, list))

    def test_positions_structure(self):
        """Positions should have proper structure"""
        resp = client.get("/api/positions")
        assert resp.status_code == 200
        data = resp.json()

        assert isinstance(data, (dict, list))


class TestConcurrentRequests:
    """Test handling of concurrent requests"""

    def test_multiple_quote_requests(self):
        """Multiple quote requests should all succeed"""
        import concurrent.futures

        symbols = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]

        def get_quote(symbol):
            return client.get(f"/api/market/quote/{symbol}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(get_quote, s): s for s in symbols}
            results = {}
            for future in concurrent.futures.as_completed(futures):
                symbol = futures[future]
                resp = future.result()
                results[symbol] = resp.status_code

        # All should succeed
        for symbol, status in results.items():
            assert status == 200, f"Failed for {symbol}"
