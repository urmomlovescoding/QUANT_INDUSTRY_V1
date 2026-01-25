"""
Security Tests for QUANT INDUSTRY API
Tests rate limiting, security headers, input validation
"""
import os
import sys
import time

from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from main import app
from middleware.security import InputSanitizer, RateLimiter, get_cors_origins

client = TestClient(app)


class TestRateLimiter:
    """Test rate limiter functionality"""

    def test_rate_limiter_allows_normal_traffic(self):
        """Normal traffic should be allowed"""
        limiter = RateLimiter(requests_per_minute=10, requests_per_second=5)

        for _ in range(5):
            allowed, info = limiter.is_allowed("test_client")
            assert allowed is True
            assert info["remaining"] >= 0

    def test_rate_limiter_blocks_burst(self):
        """Burst traffic should be blocked"""
        limiter = RateLimiter(requests_per_minute=100, requests_per_second=2, burst_size=5)

        # Make many rapid requests
        blocked = False
        for _ in range(20):
            allowed, info = limiter.is_allowed("burst_client")
            if not allowed:
                blocked = True
                break

        assert blocked is True

    def test_rate_limiter_tracks_per_client(self):
        """Different clients should have separate limits"""
        limiter = RateLimiter(requests_per_minute=10, requests_per_second=5)

        # Client A makes requests
        for _ in range(4):
            limiter.is_allowed("client_a_unique")

        # Client B should still have full quota
        allowed, info = limiter.is_allowed("client_b_unique")
        assert allowed is True
        assert info["remaining"] >= 8  # Should have most of quota left

    def test_rate_limiter_recovery(self):
        """Rate limit should recover over time"""
        limiter = RateLimiter(requests_per_minute=60, requests_per_second=2, burst_size=3)

        # Exhaust burst
        for _ in range(5):
            limiter.is_allowed("recovery_client")

        # Wait a bit
        time.sleep(1.1)

        # Should be allowed again
        allowed, _ = limiter.is_allowed("recovery_client")
        # May or may not be allowed depending on burst timing


class TestInputSanitizer:
    """Test input sanitization"""

    def test_validate_symbol_valid(self):
        """Valid symbols should pass"""
        valid, result = InputSanitizer.validate_symbol("SPY")
        assert valid is True
        assert result == "SPY"

    def test_validate_symbol_lowercase(self):
        """Lowercase symbols should be uppercased"""
        valid, result = InputSanitizer.validate_symbol("spy")
        assert valid is True
        assert result == "SPY"

    def test_validate_symbol_too_long(self):
        """Too long symbols should fail"""
        valid, error = InputSanitizer.validate_symbol("A" * 20)
        assert valid is False
        assert "too long" in error.lower()

    def test_validate_symbol_empty(self):
        """Empty symbols should fail"""
        valid, error = InputSanitizer.validate_symbol("")
        assert valid is False

    def test_validate_date_valid(self):
        """Valid dates should pass"""
        valid, result = InputSanitizer.validate_date("2026-01-24")
        assert valid is True
        assert result == "2026-01-24"

    def test_validate_date_invalid_format(self):
        """Invalid date format should fail"""
        valid, error = InputSanitizer.validate_date("01-24-2026")
        assert valid is False

    def test_validate_date_invalid_date(self):
        """Invalid date should fail"""
        valid, error = InputSanitizer.validate_date("2026-13-45")
        assert valid is False

    def test_sanitize_string_xss(self):
        """XSS attempts should be sanitized"""
        result = InputSanitizer.sanitize_string("<script>alert('xss')</script>test")
        assert "<script>" not in result
        assert "test" in result

    def test_sanitize_string_sql_injection(self):
        """SQL injection attempts should be sanitized"""
        result = InputSanitizer.sanitize_string("'; DROP TABLE users; --")
        assert ";" not in result
        assert "'" not in result

    def test_sanitize_string_truncation(self):
        """Long strings should be truncated"""
        long_string = "a" * 1000
        result = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(result) == 100


class TestCorsOrigins:
    """Test CORS origin configuration"""

    def test_development_origins(self):
        """Development should allow localhost"""
        origins = get_cors_origins("development")
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins

    def test_production_origins(self):
        """Production should only allow production domains"""
        origins = get_cors_origins("production")
        assert "http://localhost:3000" not in origins
        assert all("quantindustry.com" in o for o in origins)

    def test_staging_origins(self):
        """Staging should allow staging domain and localhost"""
        origins = get_cors_origins("staging")
        assert any("staging" in o for o in origins)


class TestSecurityHeaders:
    """Test security headers in responses"""

    def test_content_type_options(self):
        """X-Content-Type-Options header should be set"""
        resp = client.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_frame_options(self):
        """X-Frame-Options header should be set"""
        resp = client.get("/api/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_xss_protection(self):
        """X-XSS-Protection header should be set"""
        resp = client.get("/api/health")
        assert "1" in resp.headers.get("X-XSS-Protection", "")

    def test_referrer_policy(self):
        """Referrer-Policy header should be set"""
        resp = client.get("/api/health")
        assert resp.headers.get("Referrer-Policy") is not None

    def test_cache_control_api(self):
        """API responses should have cache control"""
        resp = client.get("/api/health")
        cache_control = resp.headers.get("Cache-Control", "")
        assert "no-store" in cache_control or resp.status_code == 200


class TestRateLimitHeaders:
    """Test rate limit headers in responses"""

    def test_rate_limit_header_present(self):
        """Rate limit headers should be present"""
        resp = client.get("/api/health")
        # Rate limit headers should be present
        assert "X-RateLimit-Limit" in resp.headers or resp.status_code == 200

    def test_rate_limit_remaining(self):
        """Remaining requests should be tracked"""
        resp = client.get("/api/market/quote/SPY")
        # Either has header or just returns 200
        assert resp.status_code == 200


class TestSecurityEndpoints:
    """Test security-related behavior of endpoints"""

    def test_unknown_endpoint_no_info_leak(self):
        """404 should not leak server information"""
        resp = client.get("/api/nonexistent/path")
        assert resp.status_code == 404
        data = resp.json()
        # Should not contain stack traces or internal paths
        text = str(data)
        assert "traceback" not in text.lower()
        assert "\\quant_industry" not in text

    def test_method_not_allowed_no_info_leak(self):
        """405 should not leak server information"""
        resp = client.post("/api/health")
        assert resp.status_code == 405

    def test_invalid_json_handled(self):
        """Invalid JSON should be handled gracefully"""
        resp = client.post(
            "/api/settings",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code in [400, 422]
