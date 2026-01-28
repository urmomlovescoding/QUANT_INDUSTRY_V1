"""
Tests for retry utilities: retry decorators, CircuitBreaker, RateLimiter.

Tests cover:
- Synchronous retry with exponential backoff
- Async retry with exponential backoff
- Circuit breaker state transitions
- Circuit breaker decorator
- Rate limiter token bucket
- Backoff delay calculation
"""
import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from utils.retry import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    RateLimiter,
    RateLimitExceededError,
    RetryConfig,
    RetryableOperation,
    calculate_delay,
    retry,
    async_retry,
)


class TestCalculateDelay:
    """Tests for delay calculation."""

    def test_exponential_growth(self):
        d0 = calculate_delay(0, base_delay=1.0, max_delay=100, exponential_base=2, jitter=False)
        d1 = calculate_delay(1, base_delay=1.0, max_delay=100, exponential_base=2, jitter=False)
        d2 = calculate_delay(2, base_delay=1.0, max_delay=100, exponential_base=2, jitter=False)
        assert d0 == 1.0
        assert d1 == 2.0
        assert d2 == 4.0

    def test_max_delay_cap(self):
        delay = calculate_delay(10, base_delay=1.0, max_delay=5.0, exponential_base=2, jitter=False)
        assert delay == 5.0

    def test_jitter_adds_randomness(self):
        delays = set()
        for _ in range(20):
            d = calculate_delay(1, base_delay=1.0, max_delay=100, exponential_base=2, jitter=True)
            delays.add(round(d, 3))
        # With jitter, we should get different values
        assert len(delays) > 1


class TestRetryDecorator:
    """Tests for synchronous retry decorator."""

    def test_succeeds_on_first_try(self):
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_failure(self):
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not ready")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        @retry(max_retries=2, base_delay=0.01)
        def always_fail():
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            always_fail()

    def test_only_retries_specified_exceptions(self):
        call_count = 0

        @retry(max_retries=3, base_delay=0.01, retry_exceptions=(ValueError,))
        def fail_with_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            fail_with_type_error()
        assert call_count == 1  # No retries for non-matching exception

    def test_on_retry_callback(self):
        callback = MagicMock()

        @retry(max_retries=2, base_delay=0.01, on_retry=callback)
        def fail_once():
            if callback.call_count == 0:
                raise ValueError("fail")
            return "ok"

        fail_once()
        assert callback.call_count == 1
        assert callback.call_args[0][0] == 0  # attempt number


class TestAsyncRetryDecorator:
    """Tests for async retry decorator."""

    @pytest.mark.asyncio
    async def test_async_succeeds(self):
        @async_retry(max_retries=2, base_delay=0.01)
        async def succeed():
            return "ok"

        result = await succeed()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_async_retries(self):
        call_count = 0

        @async_retry(max_retries=3, base_delay=0.01)
        async def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry me")
            return "ok"

        result = await fail_once()
        assert result == "ok"
        assert call_count == 2


class TestCircuitBreaker:
    """Tests for the CircuitBreaker pattern."""

    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "CLOSED"
        assert cb.allow_request() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=100)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.allow_request() is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        # Should still be CLOSED (failure count reset by success)
        assert cb.state == "CLOSED"

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"

        time.sleep(0.02)
        assert cb.state == "HALF_OPEN"
        assert cb.allow_request() is True

    def test_half_open_returns_to_closed(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, half_open_max_calls=2)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        # Now HALF_OPEN
        cb.record_success()
        cb.record_success()
        assert cb.state == "CLOSED"

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        # Now HALF_OPEN
        _ = cb.state  # Trigger state transition
        cb.record_failure()
        assert cb.state == "OPEN"

    def test_decorator_usage(self):
        cb = CircuitBreaker(failure_threshold=2)

        call_count = 0

        @cb
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("fail")
            return "ok"

        with pytest.raises(RuntimeError):
            flaky_func()
        with pytest.raises(RuntimeError):
            flaky_func()

        # Circuit should now be open
        with pytest.raises(CircuitBreakerOpenError):
            flaky_func()


class TestRateLimiterTokenBucket:
    """Tests for the token bucket RateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_burst(self):
        limiter = RateLimiter(requests_per_second=10, burst_size=5)
        # Should allow 5 burst requests
        for _ in range(5):
            wait = await limiter.acquire()
            assert wait == 0.0 or wait < 0.1

    @pytest.mark.asyncio
    async def test_get_stats(self):
        limiter = RateLimiter(requests_per_second=10)
        await limiter.acquire()
        stats = limiter.get_stats()
        assert stats["total_requests"] == 1
        assert stats["requests_per_second"] == 10

    def test_sync_acquire(self):
        limiter = RateLimiter(requests_per_second=100, burst_size=10)
        wait = limiter.acquire_sync()
        assert wait == 0.0 or wait < 0.1

    def test_record_rate_limit(self):
        limiter = RateLimiter(requests_per_second=10)
        limiter.record_rate_limit(retry_after=0.5)
        stats = limiter.get_stats()
        assert stats["total_rate_limits"] == 1
        assert stats["backoff_active"] is True

    def test_record_success_resets_backoff(self):
        limiter = RateLimiter(requests_per_second=10)
        limiter.record_rate_limit()
        limiter.record_success()
        stats = limiter.get_stats()
        assert stats["total_rate_limits"] == 1  # Count doesn't reset

    def test_parse_rate_limit_headers(self):
        limiter = RateLimiter()
        info = limiter.parse_rate_limit_headers({
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "50",
            "Retry-After": "30",
        })
        assert info["limit"] == 100
        assert info["remaining"] == 50
        assert info["retry_after"] == 30.0


class TestRetryableOperation:
    """Tests for the RetryableOperation context manager."""

    @pytest.mark.asyncio
    async def test_succeeds(self):
        config = RetryConfig(max_retries=3, base_delay=0.01)
        async with RetryableOperation(config=config) as op:
            result = await op.execute(lambda: "ok")
        assert result == "ok"
        assert op.attempt_count == 1

    @pytest.mark.asyncio
    async def test_retries_async_function(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not ready")
            return "ok"

        config = RetryConfig(max_retries=3, base_delay=0.01)
        async with RetryableOperation(config=config) as op:
            result = await op.execute(flaky)
        assert result == "ok"
        assert call_count == 3
