"""
Retry Utilities for QUANT INDUSTRY
Provides retry logic with exponential backoff for unreliable operations
"""
import asyncio
import functools
import logging
import random
from datetime import datetime
from typing import Callable, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        on_retry: Optional[Callable[[int, Exception], None]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_exceptions = retry_exceptions
        self.on_retry = on_retry


def calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool
) -> float:
    """Calculate delay for next retry with exponential backoff"""
    delay = base_delay * (exponential_base ** attempt)
    delay = min(delay, max_delay)

    if jitter:
        # Add random jitter (0.5x to 1.5x)
        delay = delay * (0.5 + random.random())

    return delay


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Decorator for retrying synchronous functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
        retry_exceptions: Exception types to retry on
        on_retry: Callback function called on each retry

    Example:
        @retry(max_retries=3, base_delay=1.0)
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    delay = calculate_delay(
                        attempt, base_delay, max_delay, exponential_base, jitter
                    )

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    import time
                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Decorator for retrying async functions with exponential backoff

    Example:
        @async_retry(max_retries=3, base_delay=1.0)
        async def fetch_data():
            return await client.get(url)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    delay = calculate_delay(
                        attempt, base_delay, max_delay, exponential_base, jitter
                    )

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    await asyncio.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


class RetryableOperation:
    """
    Context manager for retryable operations

    Example:
        async with RetryableOperation(max_retries=3) as op:
            result = await op.execute(fetch_data, url)
    """

    def __init__(self, config: Optional[RetryConfig] = None, **kwargs):
        self.config = config or RetryConfig(**kwargs)
        self._attempt = 0
        self._start_time: Optional[datetime] = None

    async def __aenter__(self):
        self._start_time = datetime.now()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function with retry logic"""
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            self._attempt = attempt
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except self.config.retry_exceptions as e:
                last_exception = e

                if attempt == self.config.max_retries:
                    raise

                delay = calculate_delay(
                    attempt,
                    self.config.base_delay,
                    self.config.max_delay,
                    self.config.exponential_base,
                    self.config.jitter
                )

                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s..."
                )

                if self.config.on_retry:
                    self.config.on_retry(attempt, e)

                await asyncio.sleep(delay)

        raise last_exception

    @property
    def attempt_count(self) -> int:
        """Get current attempt count"""
        return self._attempt + 1


class CircuitBreaker:
    """
    Circuit breaker pattern implementation

    Prevents repeated calls to a failing service by "opening" the circuit
    after a threshold of failures.

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Failing, requests are blocked
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        """Get current circuit state"""
        if self._state == "OPEN":
            if self._should_try_reset():
                self._state = "HALF_OPEN"
                self._half_open_calls = 0
        return self._state

    def _should_try_reset(self) -> bool:
        """Check if enough time has passed to try resetting"""
        if self._last_failure_time is None:
            return True
        import time
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def record_success(self):
        """Record a successful call"""
        if self._state == "HALF_OPEN":
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                logger.info("Circuit breaker closed - service recovered")
                self._state = "CLOSED"
                self._failure_count = 0
        elif self._state == "CLOSED":
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call"""
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == "HALF_OPEN":
            logger.warning("Circuit breaker opened - service still failing")
            self._state = "OPEN"
        elif self._failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )
            self._state = "OPEN"

    def allow_request(self) -> bool:
        """Check if a request should be allowed"""
        state = self.state  # This may transition OPEN -> HALF_OPEN
        if state == "CLOSED" or state == "HALF_OPEN":
            return True
        else:  # OPEN
            return False

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Use as a decorator"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not self.allow_request():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open for {func.__name__}"
                )
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception:
                self.record_failure()
                raise

        return wrapper


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """
    Token bucket rate limiter with exponential backoff.
    Matches quant-platform pattern for API rate limiting.

    Supports:
    - Token bucket algorithm for smooth rate limiting
    - Parsing rate limit headers from API responses
    - Exponential backoff when rate limited
    - Per-endpoint rate limit tracking

    Example:
        limiter = RateLimiter(requests_per_second=10)

        async def fetch_data(symbol):
            await limiter.acquire()
            return await api.get_quote(symbol)
    """

    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: Optional[int] = None,
        max_wait_time: float = 30.0,
        backoff_base: float = 2.0,
        max_backoff: float = 60.0
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Target request rate
            burst_size: Max tokens in bucket (default: 2x requests_per_second)
            max_wait_time: Max time to wait for a token
            backoff_base: Base for exponential backoff
            max_backoff: Maximum backoff delay
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size or int(requests_per_second * 2)
        self.max_wait_time = max_wait_time
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff

        # Token bucket state
        self._tokens = float(self.burst_size)
        self._last_update: Optional[float] = None
        self._lock = asyncio.Lock()

        # Backoff state
        self._consecutive_limits = 0
        self._backoff_until: Optional[float] = None

        # Statistics
        self._total_requests = 0
        self._total_waits = 0
        self._total_rate_limits = 0

    def _refill_tokens(self):
        """Refill tokens based on time elapsed"""
        import time
        now = time.time()

        if self._last_update is None:
            self._last_update = now
            return

        elapsed = now - self._last_update
        self._last_update = now

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.requests_per_second
        self._tokens = min(self._tokens + new_tokens, float(self.burst_size))

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from the bucket, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Wait time in seconds (0 if no wait needed)

        Raises:
            RateLimitExceededError: If max wait time exceeded
        """
        import time

        async with self._lock:
            # Check if we're in backoff period
            if self._backoff_until is not None:
                now = time.time()
                if now < self._backoff_until:
                    wait_time = self._backoff_until - now
                    if wait_time > self.max_wait_time:
                        raise RateLimitExceededError(
                            f"Rate limit backoff: {wait_time:.1f}s remaining",
                            retry_after=wait_time
                        )
                    logger.debug(f"Waiting {wait_time:.2f}s for backoff")
                    await asyncio.sleep(wait_time)
                self._backoff_until = None

            self._refill_tokens()

            total_wait = 0.0

            while self._tokens < tokens:
                # Calculate wait time for tokens to refill
                needed = tokens - self._tokens
                wait_time = needed / self.requests_per_second

                if total_wait + wait_time > self.max_wait_time:
                    raise RateLimitExceededError(
                        f"Rate limit exceeded, would wait {total_wait + wait_time:.1f}s",
                        retry_after=wait_time
                    )

                logger.debug(f"Rate limit: waiting {wait_time:.2f}s for tokens")
                await asyncio.sleep(wait_time)
                total_wait += wait_time
                self._total_waits += 1
                self._refill_tokens()

            self._tokens -= tokens
            self._total_requests += 1

            return total_wait

    def acquire_sync(self, tokens: int = 1) -> float:
        """Synchronous version of acquire"""
        import time

        # Check backoff
        if self._backoff_until is not None:
            now = time.time()
            if now < self._backoff_until:
                wait_time = self._backoff_until - now
                if wait_time > self.max_wait_time:
                    raise RateLimitExceededError(
                        f"Rate limit backoff: {wait_time:.1f}s remaining",
                        retry_after=wait_time
                    )
                time.sleep(wait_time)
            self._backoff_until = None

        self._refill_tokens()

        total_wait = 0.0

        while self._tokens < tokens:
            needed = tokens - self._tokens
            wait_time = needed / self.requests_per_second

            if total_wait + wait_time > self.max_wait_time:
                raise RateLimitExceededError(
                    f"Rate limit exceeded, would wait {total_wait + wait_time:.1f}s",
                    retry_after=wait_time
                )

            time.sleep(wait_time)
            total_wait += wait_time
            self._total_waits += 1
            self._refill_tokens()

        self._tokens -= tokens
        self._total_requests += 1

        return total_wait

    def record_rate_limit(self, retry_after: Optional[float] = None):
        """
        Record that we hit a rate limit, triggering backoff.

        Args:
            retry_after: Optional retry-after value from API response
        """
        import time

        self._total_rate_limits += 1
        self._consecutive_limits += 1

        # Calculate backoff delay
        if retry_after is not None:
            delay = retry_after
        else:
            # Exponential backoff
            delay = min(
                self.backoff_base ** self._consecutive_limits,
                self.max_backoff
            )
            # Add jitter
            delay = delay * (0.5 + random.random())

        self._backoff_until = time.time() + delay
        logger.warning(
            f"Rate limit hit (#{self._consecutive_limits}), backing off {delay:.1f}s"
        )

    def record_success(self):
        """Record a successful request, resetting backoff"""
        self._consecutive_limits = 0

    def parse_rate_limit_headers(self, headers: dict) -> dict:
        """
        Parse rate limit headers from API response.

        Common headers:
        - X-RateLimit-Limit: Total allowed requests
        - X-RateLimit-Remaining: Requests remaining
        - X-RateLimit-Reset: Unix timestamp when limit resets
        - Retry-After: Seconds to wait before retrying

        Returns:
            Dict with parsed rate limit info
        """
        info = {}

        # Standard headers
        if 'X-RateLimit-Limit' in headers:
            info['limit'] = int(headers['X-RateLimit-Limit'])
        if 'X-RateLimit-Remaining' in headers:
            info['remaining'] = int(headers['X-RateLimit-Remaining'])
        if 'X-RateLimit-Reset' in headers:
            info['reset'] = float(headers['X-RateLimit-Reset'])
        if 'Retry-After' in headers:
            info['retry_after'] = float(headers['Retry-After'])

        # Alpaca-style headers
        if 'X-Ratelimit-Limit' in headers:
            info['limit'] = int(headers['X-Ratelimit-Limit'])
        if 'X-Ratelimit-Remaining' in headers:
            info['remaining'] = int(headers['X-Ratelimit-Remaining'])

        return info

    def update_from_headers(self, headers: dict):
        """Update rate limiter state from API response headers"""
        info = self.parse_rate_limit_headers(headers)

        if 'retry_after' in info:
            self.record_rate_limit(info['retry_after'])
        elif 'remaining' in info and info['remaining'] == 0:
            # No remaining requests, calculate wait from reset time
            import time
            if 'reset' in info:
                retry_after = max(0, info['reset'] - time.time())
                self.record_rate_limit(retry_after)

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            'total_requests': self._total_requests,
            'total_waits': self._total_waits,
            'total_rate_limits': self._total_rate_limits,
            'current_tokens': self._tokens,
            'requests_per_second': self.requests_per_second,
            'backoff_active': self._backoff_until is not None
        }


class MultiEndpointRateLimiter:
    """
    Rate limiter that manages separate limits per endpoint.
    Useful when different API endpoints have different rate limits.

    Example:
        limiter = MultiEndpointRateLimiter({
            'quotes': RateLimiter(requests_per_second=100),
            'orders': RateLimiter(requests_per_second=10),
            'account': RateLimiter(requests_per_second=5)
        })

        await limiter.acquire('quotes')
        data = await api.get_quote(symbol)
    """

    def __init__(
        self,
        limiters: Optional[dict] = None,
        default_rps: float = 10.0
    ):
        """
        Initialize multi-endpoint rate limiter.

        Args:
            limiters: Dict of endpoint name -> RateLimiter
            default_rps: Default requests per second for new endpoints
        """
        self._limiters: dict = limiters or {}
        self._default_rps = default_rps
        self._lock = asyncio.Lock()

    def get_limiter(self, endpoint: str) -> RateLimiter:
        """Get or create rate limiter for endpoint"""
        if endpoint not in self._limiters:
            self._limiters[endpoint] = RateLimiter(
                requests_per_second=self._default_rps
            )
        return self._limiters[endpoint]

    async def acquire(self, endpoint: str, tokens: int = 1) -> float:
        """Acquire tokens for an endpoint"""
        limiter = self.get_limiter(endpoint)
        return await limiter.acquire(tokens)

    def acquire_sync(self, endpoint: str, tokens: int = 1) -> float:
        """Synchronous acquire for an endpoint"""
        limiter = self.get_limiter(endpoint)
        return limiter.acquire_sync(tokens)

    def record_rate_limit(self, endpoint: str, retry_after: Optional[float] = None):
        """Record rate limit hit for endpoint"""
        limiter = self.get_limiter(endpoint)
        limiter.record_rate_limit(retry_after)

    def record_success(self, endpoint: str):
        """Record success for endpoint"""
        limiter = self.get_limiter(endpoint)
        limiter.record_success()

    def update_from_headers(self, endpoint: str, headers: dict):
        """Update endpoint limiter from response headers"""
        limiter = self.get_limiter(endpoint)
        limiter.update_from_headers(headers)

    def get_stats(self) -> dict:
        """Get stats for all endpoints"""
        return {
            endpoint: limiter.get_stats()
            for endpoint, limiter in self._limiters.items()
        }


def rate_limited(
    limiter: RateLimiter,
    tokens: int = 1,
    handle_429: bool = True
):
    """
    Decorator for rate-limiting function calls.

    Args:
        limiter: RateLimiter instance to use
        tokens: Number of tokens per call
        handle_429: Whether to handle 429 responses automatically

    Example:
        api_limiter = RateLimiter(requests_per_second=10)

        @rate_limited(api_limiter)
        async def fetch_quote(symbol):
            return await client.get(f'/quote/{symbol}')
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            await limiter.acquire(tokens)
            try:
                result = await func(*args, **kwargs)
                limiter.record_success()
                return result
            except Exception as e:
                # Check for rate limit errors (429)
                if handle_429 and _is_rate_limit_error(e):
                    retry_after = _extract_retry_after(e)
                    limiter.record_rate_limit(retry_after)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            limiter.acquire_sync(tokens)
            try:
                result = func(*args, **kwargs)
                limiter.record_success()
                return result
            except Exception as e:
                if handle_429 and _is_rate_limit_error(e):
                    retry_after = _extract_retry_after(e)
                    limiter.record_rate_limit(retry_after)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception indicates a rate limit error"""
    error_str = str(error).lower()
    if '429' in error_str or 'rate limit' in error_str:
        return True
    if hasattr(error, 'status') and error.status == 429:
        return True
    if hasattr(error, 'status_code') and error.status_code == 429:
        return True
    return False


def _extract_retry_after(error: Exception) -> Optional[float]:
    """Extract retry-after value from an exception"""
    if hasattr(error, 'headers'):
        headers = error.headers
        if 'Retry-After' in headers:
            try:
                return float(headers['Retry-After'])
            except (ValueError, TypeError):
                pass
    return None
