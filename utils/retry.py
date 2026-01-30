"""
QUANT_INDUSTRY_V1 Retry Utilities

Provides retry logic with exponential backoff and configurable behavior.
"""

import time
import random
import functools
from typing import Callable, Any, Optional, Tuple, Type, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1

    # Exceptions to retry on (empty = retry all)
    retry_exceptions: Tuple[Type[Exception], ...] = ()

    # Exceptions to never retry on
    fatal_exceptions: Tuple[Type[Exception], ...] = ()

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        delay = min(
            self.initial_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay
        )
        if self.jitter:
            delay *= (1 + random.uniform(-self.jitter_factor, self.jitter_factor))
        return delay


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Tuple[Type[Exception], ...] = (),
    fatal_exceptions: Tuple[Type[Exception], ...] = (),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying function calls with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delays
        retry_exceptions: Tuple of exceptions to retry on (empty = all)
        fatal_exceptions: Tuple of exceptions to never retry on
        on_retry: Optional callback called on each retry (exception, attempt)

    Usage:
        @retry(max_attempts=3)
        def flaky_function():
            pass

        @retry(retry_exceptions=(ConnectionError, TimeoutError))
        def network_call():
            pass
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_exceptions=retry_exceptions,
        fatal_exceptions=fatal_exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except config.fatal_exceptions as e:
                    # Never retry fatal exceptions
                    logger.error(f"{func.__name__} failed with fatal exception: {e}")
                    raise

                except Exception as e:
                    last_exception = e

                    # Check if we should retry this exception
                    if config.retry_exceptions and not isinstance(e, config.retry_exceptions):
                        logger.error(f"{func.__name__} failed with non-retryable exception: {e}")
                        raise

                    if attempt < config.max_attempts:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"{func.__name__} attempt {attempt} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        if on_retry:
                            on_retry(e, attempt)

                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {config.max_attempts} attempts: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


class RetryContext:
    """
    Context manager for retry logic.

    Usage:
        with RetryContext(max_attempts=3) as ctx:
            while ctx.should_retry:
                try:
                    result = risky_operation()
                    break
                except Exception as e:
                    ctx.record_failure(e)
    """

    def __init__(self, config: Optional[RetryConfig] = None, **kwargs):
        self.config = config or RetryConfig(**kwargs)
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
        self._success = False

    def __enter__(self) -> 'RetryContext':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None and not self._success:
            logger.error(f"All {self.attempt} attempts failed. Last error: {exc_val}")
        return False

    @property
    def should_retry(self) -> bool:
        """Check if another attempt should be made."""
        return self.attempt < self.config.max_attempts and not self._success

    def record_failure(self, exception: Exception):
        """Record a failed attempt."""
        self.attempt += 1
        self.last_exception = exception

        # Check for fatal exceptions
        if isinstance(exception, self.config.fatal_exceptions):
            self._success = True  # Prevent further retries
            raise exception

        # Check if we should retry this exception
        if self.config.retry_exceptions:
            if not isinstance(exception, self.config.retry_exceptions):
                raise exception

        if self.should_retry:
            delay = self.config.get_delay(self.attempt)
            logger.warning(
                f"Attempt {self.attempt} failed: {exception}. "
                f"Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)

    def record_success(self):
        """Record a successful attempt."""
        self._success = True


async def async_retry(
    func: Callable,
    *args,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    **kwargs
) -> Any:
    """
    Async retry helper for coroutines.

    Usage:
        result = await async_retry(async_fetch, url, max_attempts=3)
    """
    import asyncio

    config = RetryConfig(max_attempts=max_attempts, initial_delay=initial_delay)
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < config.max_attempts:
                delay = config.get_delay(attempt)
                logger.warning(
                    f"{func.__name__} attempt {attempt} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

    raise last_exception


# =============================================================================
# Circuit Breaker Pattern
# =============================================================================

class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by temporarily blocking calls to failing services.
    
    States:
        - CLOSED: Normal operation, calls pass through
        - OPEN: Service is failing, calls blocked
        - HALF_OPEN: Testing if service recovered
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
        
        try:
            with breaker:
                result = risky_operation()
        except CircuitBreakerOpen:
            # Use fallback
            result = fallback_value
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        name: str = "circuit_breaker"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds before attempting recovery
            half_open_max_calls: Max calls in half-open state
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name
        
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = __import__('threading').Lock()
    
    @property
    def state(self) -> str:
        """Get current state, checking for recovery timeout."""
        with self._lock:
            if self._state == self.OPEN and self._last_failure_time:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"CircuitBreaker '{self.name}' entering HALF_OPEN state")
            return self._state
    
    def __enter__(self):
        """Enter context - check if call should be allowed."""
        state = self.state
        
        if state == self.OPEN:
            raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is OPEN")
        
        if state == self.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is HALF_OPEN (max calls reached)")
                self._half_open_calls += 1
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - record success or failure."""
        if exc_type is not None:
            self.record_failure()
        else:
            self.record_success()
        return False  # Don't suppress exceptions
    
    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = self.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"CircuitBreaker '{self.name}' recovered to CLOSED state")
            else:
                self._failure_count = max(0, self._failure_count - 1)
    
    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                logger.warning(f"CircuitBreaker '{self.name}' back to OPEN after HALF_OPEN failure")
            elif self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(f"CircuitBreaker '{self.name}' opened after {self._failure_count} failures")
    
    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            logger.info(f"CircuitBreaker '{self.name}' manually reset")
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure": self._last_failure_time
        }
