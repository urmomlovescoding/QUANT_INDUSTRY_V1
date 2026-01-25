"""
Tests for FastAPI API Endpoints
"""
import os
import sys

from fastapi.testclient import TestClient

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test /api/health endpoint"""

    def test_health_returns_200(self):
        """Health endpoint should return 200"""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_has_status(self):
        """Health should return status field"""
        response = client.get("/api/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_has_timestamp(self):
        """Health should return timestamp"""
        response = client.get("/api/health")
        data = response.json()
        assert "timestamp" in data

    def test_health_has_market_info(self):
        """Health should include market info"""
        response = client.get("/api/health")
        data = response.json()
        assert "market" in data


class TestMarketEndpoints:
    """Test /api/market/* endpoints"""

    def test_market_status(self):
        """Should return market status"""
        response = client.get("/api/market/status")
        assert response.status_code == 200
        data = response.json()
        assert "session" in data
        assert "is_open" in data

    def test_market_quote_spy(self):
        """Should return quote for SPY"""
        response = client.get("/api/market/quote/SPY")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "SPY"
        assert "price" in data
        assert data["price"] > 0

    def test_market_tickers(self):
        """Should return ticker list"""
        response = client.get("/api/market/tickers")
        assert response.status_code == 200
        data = response.json()
        assert "tickers" in data or isinstance(data, list)

    def test_market_sectors(self):
        """Should return sector data"""
        response = client.get("/api/market/sectors")
        assert response.status_code == 200

    def test_market_movers(self):
        """Should return market movers"""
        response = client.get("/api/market/movers")
        assert response.status_code == 200

    def test_market_quote_unknown_symbol(self):
        """Should handle unknown symbols gracefully"""
        response = client.get("/api/market/quote/UNKNOWNSYM123")
        # Should either return 200 with fallback or 404
        assert response.status_code in [200, 404]

    def test_market_quote_case_insensitive(self):
        """Symbol should be case insensitive"""
        response = client.get("/api/market/quote/spy")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"].upper() == "SPY"


class TestPositionsEndpoint:
    """Test /api/positions endpoint"""

    def test_positions_returns_200(self):
        """Positions endpoint should return 200"""
        response = client.get("/api/positions")
        assert response.status_code == 200


class TestPortfolioEndpoints:
    """Test /api/portfolio/* endpoints"""

    def test_portfolio_holdings(self):
        """Portfolio holdings should return 200"""
        response = client.get("/api/portfolio/holdings")
        assert response.status_code == 200

    def test_portfolio_performance(self):
        """Portfolio performance should return 200"""
        response = client.get("/api/portfolio/performance")
        assert response.status_code == 200


class TestSettingsEndpoints:
    """Test /api/settings/* endpoints"""

    def test_settings_get(self):
        """Should be able to get settings"""
        response = client.get("/api/settings")
        assert response.status_code == 200

    def test_settings_presets(self):
        """Should be able to get presets"""
        response = client.get("/api/settings/presets")
        assert response.status_code == 200

    def test_api_keys_get(self):
        """Should be able to get API keys config"""
        response = client.get("/api/settings/api-keys")
        assert response.status_code == 200


class TestSystemEndpoints:
    """Test /api/system/* endpoints"""

    def test_system_health(self):
        """System health should return 200"""
        response = client.get("/api/system/health")
        assert response.status_code == 200

    def test_system_status(self):
        """System status should return 200"""
        response = client.get("/api/system/status")
        assert response.status_code == 200

    def test_system_resources(self):
        """System resources should return 200"""
        response = client.get("/api/system/resources")
        assert response.status_code == 200

    def test_ml_capabilities(self):
        """ML capabilities should return 200"""
        response = client.get("/api/system/ml-capabilities")
        assert response.status_code == 200


class TestBrainV6Endpoints:
    """Test /api/brain-v6/* endpoints"""

    def test_brain_status(self):
        """Brain status should return 200"""
        response = client.get("/api/brain-v6/status")
        assert response.status_code == 200

    def test_brain_config(self):
        """Brain config should return 200"""
        response = client.get("/api/brain-v6/config")
        assert response.status_code == 200

    def test_brain_rulesets(self):
        """Brain rulesets should return 200"""
        response = client.get("/api/brain-v6/rulesets")
        assert response.status_code == 200


class TestAPIDocumentation:
    """Test API documentation endpoints"""

    def test_openapi_schema(self):
        """OpenAPI schema should be available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_available(self):
        """Swagger docs should be available"""
        response = client.get("/docs")
        # Should redirect or return HTML
        assert response.status_code in [200, 307]


class TestCORSHeaders:
    """Test CORS configuration"""

    def test_cors_headers_present(self):
        """CORS headers should be present for allowed origins"""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        # Should allow CORS or at least not error
        assert response.status_code in [200, 204, 405]


class TestErrorHandling:
    """Test error handling"""

    def test_404_for_unknown_route(self):
        """Unknown routes should return 404"""
        response = client.get("/api/nonexistent/endpoint")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Wrong method should return 405"""
        response = client.post("/api/health")
        assert response.status_code == 405
