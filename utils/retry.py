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
