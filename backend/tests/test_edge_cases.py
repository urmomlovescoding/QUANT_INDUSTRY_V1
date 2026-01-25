"""
Edge Case Tests for QUANT INDUSTRY API
Tests boundary conditions and unusual inputs
"""
import os
import sys

from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from main import app

client = TestClient(app)


class TestSymbolEdgeCases:
    """Test edge cases for symbol handling"""

    def test_empty_symbol(self):
        """Empty symbol should be handled"""
        resp = client.get("/api/market/quote/")
        # Should return 404 or 307 (redirect)
        assert resp.status_code in [307, 404, 405]

    def test_very_long_symbol(self):
        """Very long symbol should be handled"""
        long_symbol = "A" * 100
        resp = client.get(f"/api/market/quote/{long_symbol}")
        assert resp.status_code in [200, 400, 404]

    def test_special_characters_in_symbol(self):
        """Special characters in symbol should be handled"""
        resp = client.get("/api/market/quote/SPY%20TEST")
        assert resp.status_code in [200, 400, 404]

    def test_numeric_symbol(self):
        """Numeric symbol should be handled"""
        resp = client.get("/api/market/quote/12345")
        assert resp.status_code in [200, 404]

    def test_lowercase_symbol(self):
        """Lowercase symbol should work"""
        resp = client.get("/api/market/quote/spy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "SPY"  # Should be uppercased

    def test_mixed_case_symbol(self):
        """Mixed case symbol should work"""
        resp = client.get("/api/market/quote/SpY")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "SPY"


class TestQueryParameterEdgeCases:
    """Test edge cases for query parameters"""

    def test_negative_values(self):
        """Negative values in parameters"""
        resp = client.get("/api/charts/ohlcv/SPY?days=-1")
        # Should handle gracefully
        assert resp.status_code in [200, 400, 422]

    def test_zero_values(self):
        """Zero values in parameters"""
        resp = client.get("/api/charts/ohlcv/SPY?days=0")
        assert resp.status_code in [200, 400, 422]

    def test_very_large_values(self):
        """Very large values in parameters"""
        resp = client.get("/api/charts/ohlcv/SPY?days=999999")
        assert resp.status_code in [200, 400, 422]

    def test_float_where_int_expected(self):
        """Float where integer expected"""
        resp = client.get("/api/charts/ohlcv/SPY?days=5.5")
        assert resp.status_code in [200, 400, 422]

    def test_string_where_number_expected(self):
        """String where number expected"""
        resp = client.get("/api/charts/ohlcv/SPY?days=abc")
        assert resp.status_code in [200, 400, 422]


class TestRequestBodyEdgeCases:
    """Test edge cases for request bodies"""

    def test_empty_body(self):
        """Empty body for POST endpoints"""
        resp = client.post("/api/settings", json={})
        assert resp.status_code in [200, 400, 422]

    def test_null_values(self):
        """Null values in body"""
        resp = client.post("/api/settings", json={"theme": None})
        assert resp.status_code in [200, 400, 422]

    def test_extra_fields(self):
        """Extra unknown fields in body"""
        resp = client.post("/api/settings", json={
            "unknown_field": "value",
            "another_unknown": 123
        })
        assert resp.status_code in [200, 400, 422]

    def test_deeply_nested_json(self):
        """Deeply nested JSON"""
        nested = {"level": 1}
        current = nested
        for i in range(10):
            current["nested"] = {"level": i + 2}
            current = current["nested"]

        resp = client.post("/api/settings", json=nested)
        assert resp.status_code in [200, 400, 422]

    def test_large_array(self):
        """Large array in body"""
        large_list = list(range(1000))
        resp = client.post("/api/settings", json={"items": large_list})
        assert resp.status_code in [200, 400, 422]


class TestHeaderEdgeCases:
    """Test edge cases for HTTP headers"""

    def test_missing_content_type(self):
        """Missing content-type header"""
        resp = client.post("/api/settings", content='{"key": "value"}')
        assert resp.status_code in [200, 400, 415, 422]

    def test_wrong_content_type(self):
        """Wrong content-type header"""
        resp = client.post(
            "/api/settings",
            content='{"key": "value"}',
            headers={"Content-Type": "text/plain"}
        )
        assert resp.status_code in [200, 400, 415, 422]

    def test_accept_header(self):
        """Accept header should be respected"""
        resp = client.get("/api/health", headers={"Accept": "application/json"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")


class TestConcurrencyEdgeCases:
    """Test edge cases for concurrent access"""

    def test_rapid_sequential_requests(self):
        """Rapid sequential requests to same endpoint"""
        for _ in range(10):
            resp = client.get("/api/market/quote/SPY")
            assert resp.status_code == 200

    def test_alternating_endpoints(self):
        """Alternating between different endpoints"""
        endpoints = [
            "/api/health",
            "/api/market/quote/SPY",
            "/api/market/status",
            "/api/positions"
        ]
        for _ in range(3):
            for endpoint in endpoints:
                resp = client.get(endpoint)
                assert resp.status_code == 200


class TestResponseFormat:
    """Test response format consistency"""

    def test_json_response_format(self):
        """All API responses should be valid JSON"""
        endpoints = [
            "/api/health",
            "/api/market/status",
            "/api/market/quote/SPY",
            "/api/positions",
            "/api/settings"
        ]
        for endpoint in endpoints:
            resp = client.get(endpoint)
            assert resp.status_code == 200
            # Should be valid JSON
            data = resp.json()
            assert data is not None

    def test_error_response_format(self):
        """Error responses should have consistent format"""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data or "error" in data or "message" in data


class TestTimeBasedEdgeCases:
    """Test time-based edge cases"""

    def test_market_status_always_available(self):
        """Market status should always return valid data"""
        resp = client.get("/api/market/status")
        assert resp.status_code == 200
        data = resp.json()

        # Should always have session info
        assert "session" in data
        assert data["session"] in ["closed", "pre_market", "regular", "after_hours"]

    def test_quote_timestamp_present(self):
        """Quotes should include timestamp info"""
        resp = client.get("/api/market/quote/SPY")
        assert resp.status_code == 200
        data = resp.json()

        # Should have market session info
        assert "market_session" in data
        assert "is_market_open" in data
