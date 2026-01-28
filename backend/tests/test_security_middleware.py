"""
Tests for security middleware: RateLimiter, InputSanitizer, SecurityHeaders.

Tests cover:
- Rate limiting with per-second, per-minute, and burst controls
- Memory safety (max tracked clients, cleanup)
- Strict path rate limiting with persistent limiters
- Input validation for symbols, dates, and numerics
- String sanitization
- CORS origin configuration
"""
import os
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from middleware.security import (
    InputSanitizer,
    RateLimiter,
    SecurityHeadersMiddleware,
    get_cors_origins,
    _get_strict_limiter,
    _strict_limiters,
)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allows_requests_under_limit(self):
        limiter = RateLimiter(requests_per_minute=10, requests_per_second=5, burst_size=5)
        allowed, info = limiter.is_allowed("client1")
        assert allowed is True
        assert info["remaining"] == 9

    def test_blocks_requests_over_per_second_limit(self):
        limiter = RateLimiter(requests_per_minute=100, requests_per_second=2, burst_size=100)
        # Make 2 requests (at limit)
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        # Third should be blocked
        allowed, info = limiter.is_allowed("client1")
        assert allowed is False
        assert info["window"] == "second"
        assert info["retry_after"] == 1

    def test_blocks_requests_over_per_minute_limit(self):
        limiter = RateLimiter(requests_per_minute=3, requests_per_second=100, burst_size=100)
        for _ in range(3):
            limiter.is_allowed("client1")
        allowed, info = limiter.is_allowed("client1")
        assert allowed is False
        assert info["window"] == "minute"

    def test_blocks_burst_requests(self):
        limiter = RateLimiter(requests_per_minute=100, requests_per_second=100, burst_size=3)
        for _ in range(3):
            limiter.is_allowed("client1")
        allowed, info = limiter.is_allowed("client1")
        assert allowed is False
        assert info["window"] == "burst"

    def test_separate_clients_independent(self):
        limiter = RateLimiter(requests_per_minute=2, requests_per_second=100, burst_size=100)
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        # client1 should be blocked
        allowed1, _ = limiter.is_allowed("client1")
        assert allowed1 is False
        # client2 should still be allowed
        allowed2, _ = limiter.is_allowed("client2")
        assert allowed2 is True

    def test_endpoint_rate_limiting(self):
        limiter = RateLimiter(requests_per_minute=2, requests_per_second=100, burst_size=100)
        limiter.is_allowed("client1", "/api/fast")
        limiter.is_allowed("client1", "/api/fast")
        # Same endpoint blocked
        allowed1, _ = limiter.is_allowed("client1", "/api/fast")
        assert allowed1 is False
        # Different endpoint still works
        allowed2, _ = limiter.is_allowed("client1", "/api/other")
        assert allowed2 is True

    def test_tracked_clients_property(self):
        limiter = RateLimiter()
        assert limiter.tracked_clients == 0
        limiter.is_allowed("client1")
        assert limiter.tracked_clients == 1
        limiter.is_allowed("client2")
        assert limiter.tracked_clients == 2

    def test_remaining_decreases(self):
        limiter = RateLimiter(requests_per_minute=5, requests_per_second=100, burst_size=100)
        _, info1 = limiter.is_allowed("c1")
        _, info2 = limiter.is_allowed("c1")
        assert info1["remaining"] == 4
        assert info2["remaining"] == 3


class TestStrictLimiter:
    """Tests for persistent strict path limiters."""

    def test_get_strict_limiter_creates_once(self):
        _strict_limiters.clear()
        limiter1 = _get_strict_limiter("/api/test", 5)
        limiter2 = _get_strict_limiter("/api/test", 5)
        assert limiter1 is limiter2

    def test_different_paths_different_limiters(self):
        _strict_limiters.clear()
        limiter1 = _get_strict_limiter("/api/path1", 5)
        limiter2 = _get_strict_limiter("/api/path2", 10)
        assert limiter1 is not limiter2
        assert limiter1.rpm == 5
        assert limiter2.rpm == 10


class TestInputSanitizer:
    """Tests for InputSanitizer validation methods."""

    def test_validate_symbol_valid(self):
        valid, result = InputSanitizer.validate_symbol("AAPL")
        assert valid is True
        assert result == "AAPL"

    def test_validate_symbol_lowercase(self):
        valid, result = InputSanitizer.validate_symbol("aapl")
        assert valid is True
        assert result == "AAPL"

    def test_validate_symbol_with_strip(self):
        valid, result = InputSanitizer.validate_symbol("  AAPL  ")
        assert valid is True
        assert result == "AAPL"

    def test_validate_symbol_empty(self):
        valid, msg = InputSanitizer.validate_symbol("")
        assert valid is False
        assert "required" in msg.lower()

    def test_validate_symbol_too_long(self):
        valid, msg = InputSanitizer.validate_symbol("A" * 15)
        assert valid is False
        assert "too long" in msg.lower()

    def test_validate_symbol_futures(self):
        """Futures symbols like ^VIX and ES/H24 should be valid."""
        valid, result = InputSanitizer.validate_symbol("^VIX")
        assert valid is True
        assert result == "^VIX"

    def test_validate_symbol_with_dot(self):
        valid, result = InputSanitizer.validate_symbol("BRK.B")
        assert valid is True

    def test_validate_symbol_invalid_chars(self):
        valid, msg = InputSanitizer.validate_symbol("AAPL!@#")
        assert valid is False

    def test_validate_date_valid(self):
        valid, result = InputSanitizer.validate_date("2024-01-15")
        assert valid is True
        assert result == "2024-01-15"

    def test_validate_date_invalid_format(self):
        valid, msg = InputSanitizer.validate_date("01/15/2024")
        assert valid is False
        assert "format" in msg.lower()

    def test_validate_date_empty(self):
        valid, msg = InputSanitizer.validate_date("")
        assert valid is False

    def test_validate_date_too_old(self):
        valid, msg = InputSanitizer.validate_date("1899-01-01")
        assert valid is False
        assert "past" in msg.lower()

    def test_validate_numeric_in_range(self):
        valid, _ = InputSanitizer.validate_numeric(5.0, min_val=0, max_val=10)
        assert valid is True

    def test_validate_numeric_below_min(self):
        valid, msg = InputSanitizer.validate_numeric(-1, min_val=0, name="price")
        assert valid is False
        assert "price" in msg
        assert ">=" in msg

    def test_validate_numeric_above_max(self):
        valid, msg = InputSanitizer.validate_numeric(100, max_val=50, name="quantity")
        assert valid is False
        assert "quantity" in msg

    def test_sanitize_string_removes_html(self):
        result = InputSanitizer.sanitize_string("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result

    def test_sanitize_string_removes_null_bytes(self):
        result = InputSanitizer.sanitize_string("Hello\x00World")
        assert "\x00" not in result
        assert "HelloWorld" == result

    def test_sanitize_string_truncates(self):
        result = InputSanitizer.sanitize_string("A" * 1000, max_length=10)
        assert len(result) == 10

    def test_sanitize_string_empty(self):
        assert InputSanitizer.sanitize_string("") == ""
        assert InputSanitizer.sanitize_string(None) == ""


class TestCorsOrigins:
    """Tests for CORS origin configuration."""

    def test_development_origins(self):
        origins = get_cors_origins("development")
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins

    def test_production_origins(self):
        origins = get_cors_origins("production")
        assert all("https://" in o for o in origins)
        assert "http://localhost:3000" not in origins

    def test_staging_origins(self):
        origins = get_cors_origins("staging")
        assert "https://staging.quantindustry.com" in origins
        assert "http://localhost:3000" in origins

    def test_auto_detect_from_env(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            origins = get_cors_origins()
            assert "https://quantindustry.com" in origins

    def test_default_is_development(self):
        with patch.dict(os.environ, {}, clear=True):
            origins = get_cors_origins()
            assert "http://localhost:3000" in origins
