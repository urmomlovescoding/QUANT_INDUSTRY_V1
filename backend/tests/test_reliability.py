"""
Reliability Tests for QUANT INDUSTRY
Tests health monitoring, retry logic, and circuit breaker
"""
import asyncio
import os
import sys
import time

import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from services.health_monitor import HealthMonitor, HealthStatus, get_health_monitor
from utils.retry import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    RetryableOperation,
    async_retry,
    calculate_delay,
    retry,
)


class TestRetryDecorator:
    """Test retry decorator functionality"""

    def test_retry_succeeds_first_try(self):
        """Function that succeeds shouldn't retry"""
        call_count = 0

        @retry(max_retries=3)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()
        assert result == "success"
        assert call_count == 1

    def test_retry_succeeds_after_failures(self):
        """Function should retry and eventually succeed"""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = fails_twice()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self):
        """Should raise after max retries"""
        call_count = 0

        @retry(max_retries=2, base_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError):
            always_fails()

        assert call_count == 3  # Initial + 2 retries

    def test_retry_specific_exceptions(self):
        """Should only retry specified exceptions"""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01, retry_exceptions=(ValueError,))
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            raises_type_error()

        assert call_count == 1  # No retries for TypeError


class TestAsyncRetryDecorator:
    """Test async retry decorator"""

    def test_async_retry_succeeds(self):
        """Async function should retry and succeed"""
        call_count = 0

        @async_retry(max_retries=3, base_delay=0.01)
        async def async_fails_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary")
            return "success"

        result = asyncio.run(async_fails_once())
        assert result == "success"
        assert call_count == 2


class TestCalculateDelay:
    """Test delay calculation"""

    def test_exponential_backoff(self):
        """Delay should increase exponentially"""
        delay0 = calculate_delay(0, 1.0, 60.0, 2.0, jitter=False)
        delay1 = calculate_delay(1, 1.0, 60.0, 2.0, jitter=False)
        delay2 = calculate_delay(2, 1.0, 60.0, 2.0, jitter=False)

        assert delay0 == 1.0
        assert delay1 == 2.0
        assert delay2 == 4.0

    def test_max_delay_cap(self):
        """Delay should be capped at max"""
        delay = calculate_delay(10, 1.0, 5.0, 2.0, jitter=False)
        assert delay == 5.0

    def test_jitter_adds_randomness(self):
        """Jitter should vary the delay"""
        delays = [calculate_delay(0, 1.0, 60.0, 2.0, jitter=True) for _ in range(10)]
        # With jitter, delays should vary
        assert len(set(delays)) > 1


class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def test_circuit_starts_closed(self):
        """Circuit should start in closed state"""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "CLOSED"
        assert cb.allow_request() is True

    def test_circuit_opens_after_failures(self):
        """Circuit should open after threshold failures"""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == "OPEN"
        assert cb.allow_request() is False

    def test_circuit_closes_after_success(self):
        """Circuit should close after successful calls in half-open"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, half_open_max_calls=2)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"

        # Wait for recovery timeout
        time.sleep(0.02)

        # Should transition to half-open
        assert cb.state == "HALF_OPEN"

        # Record successes
        cb.record_success()
        cb.record_success()

        assert cb.state == "CLOSED"

    def test_circuit_breaker_decorator(self):
        """Circuit breaker should work as decorator"""
        cb = CircuitBreaker(failure_threshold=2)
        call_count = 0

        @cb
        def unreliable_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        # First two calls should go through (and fail)
        for _ in range(2):
            with pytest.raises(ValueError):
                unreliable_function()

        # Third call should be blocked by circuit breaker
        with pytest.raises(CircuitBreakerOpenError):
            unreliable_function()

        assert call_count == 2  # Only 2 calls went through


class TestHealthMonitor:
    """Test health monitoring functionality"""

    def test_health_monitor_creation(self):
        """Health monitor should be created"""
        monitor = HealthMonitor()
        assert monitor is not None

    def test_register_component(self):
        """Should be able to register components"""
        monitor = HealthMonitor()

        async def check_func():
            return HealthStatus.HEALTHY, "OK"

        monitor.register_component("test_component", check_func)
        assert "test_component" in monitor._components

    def test_check_component_healthy(self):
        """Should check component health"""
        monitor = HealthMonitor()

        async def healthy_check():
            return HealthStatus.HEALTHY, "All good"

        monitor.register_component("healthy", healthy_check)
        health = asyncio.run(monitor.check_component("healthy"))

        assert health.status == HealthStatus.HEALTHY
        assert health.message == "All good"

    def test_check_component_unhealthy(self):
        """Should track unhealthy components"""
        monitor = HealthMonitor()

        async def unhealthy_check():
            return HealthStatus.UNHEALTHY, "Service down"

        monitor.register_component("unhealthy", unhealthy_check)
        health = asyncio.run(monitor.check_component("unhealthy"))

        assert health.status == HealthStatus.UNHEALTHY
        assert health.consecutive_failures == 1

    def test_get_system_metrics(self):
        """Should get system metrics"""
        monitor = HealthMonitor()
        metrics = monitor.get_system_metrics()

        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "disk_percent" in metrics
        assert metrics["cpu_percent"] >= 0
        assert metrics["memory_percent"] >= 0

    def test_quick_status(self):
        """Should get quick status"""
        monitor = HealthMonitor()
        status = monitor.get_quick_status()

        assert "status" in status
        assert "uptime_seconds" in status
        assert "cpu_percent" in status


class TestRetryableOperation:
    """Test RetryableOperation context manager"""

    def test_retryable_operation_success(self):
        """Should execute operation successfully"""
        async def run_test():
            async with RetryableOperation(max_retries=3) as op:
                result = await op.execute(lambda: "success")
                return result, op.attempt_count

        result, attempts = asyncio.run(run_test())
        assert result == "success"
        assert attempts == 1

    def test_retryable_operation_with_retries(self):
        """Should retry failing operation"""
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary")
            return "success"

        async def run_test():
            async with RetryableOperation(max_retries=3, base_delay=0.01) as op:
                result = await op.execute(flaky_func)
                return result

        result = asyncio.run(run_test())
        assert result == "success"


class TestGlobalHealthMonitor:
    """Test global health monitor singleton"""

    def test_get_health_monitor_singleton(self):
        """Should return same instance"""
        monitor1 = get_health_monitor()
        monitor2 = get_health_monitor()
        assert monitor1 is monitor2
