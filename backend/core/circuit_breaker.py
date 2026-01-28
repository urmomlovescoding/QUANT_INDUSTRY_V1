"""
QUANT INDUSTRY - Circuit Breaker & Error Recovery
=================================================
Production-grade error handling:
- Circuit breaker pattern for failing services
- Exponential backoff retry logic
- Graceful degradation
- Automatic recovery

This prevents cascading failures in live trading.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import asyncio
import functools
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from collections import deque

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 3      # Successes to close from half-open
    timeout_seconds: float = 30.0   # Time before trying half-open
    
    # Retry settings
    max_retries: int = 3
    base_delay: float = 1.0         # Base delay for exponential backoff
    max_delay: float = 60.0         # Maximum delay between retries
    exponential_base: float = 2.0   # Backoff multiplier


@dataclass
class CircuitStats:
    """Statistics for circuit breaker"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls
    
    def to_dict(self) -> Dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "success_rate": f"{self.success_rate:.1%}",
            "consecutive_failures": self.consecutive_failures,
            "state": "healthy" if self.consecutive_failures < 3 else "degraded"
        }


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    Usage:
    ------
    >>> breaker = CircuitBreaker("data_api")
    >>> 
    >>> @breaker
    >>> def fetch_data():
    ...     return api.get_data()
    >>>
    >>> # Or manually:
    >>> with breaker:
    ...     result = risky_operation()
    >>>
    >>> # Check state:
    >>> if breaker.is_available:
    ...     do_something()
    """
    
    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig = None,
        fallback: Callable[[], T] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Identifier for this breaker
            config: Configuration settings
            fallback: Function to call when circuit is open
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback
        
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._last_state_change = datetime.now()
        self._lock = asyncio.Lock() if asyncio.iscoroutinefunction(fallback) else None
        
        logger.info(f"CircuitBreaker '{name}' initialized")
    
    @property
    def is_available(self) -> bool:
        """Check if circuit allows calls"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            elapsed = (datetime.now() - self._last_state_change).total_seconds()
            if elapsed >= self.config.timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        
        # Half-open: allow limited calls
        return True
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state"""
        if self.state != new_state:
            logger.info(f"CircuitBreaker '{self.name}': {self.state.value} -> {new_state.value}")
            self.state = new_state
            self._last_state_change = datetime.now()
    
    def _record_success(self):
        """Record a successful call"""
        self.stats.total_calls += 1
        self.stats.successful_calls += 1
        self.stats.last_success_time = datetime.now()
        self.stats.consecutive_successes += 1
        self.stats.consecutive_failures = 0
        
        if self.state == CircuitState.HALF_OPEN:
            if self.stats.consecutive_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
    
    def _record_failure(self, error: Exception = None):
        """Record a failed call"""
        self.stats.total_calls += 1
        self.stats.failed_calls += 1
        self.stats.last_failure_time = datetime.now()
        self.stats.consecutive_failures += 1
        self.stats.consecutive_successes = 0
        
        if error:
            logger.warning(f"CircuitBreaker '{self.name}' failure: {error}")
        
        if self.state == CircuitState.CLOSED:
            if self.stats.consecutive_failures >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
        
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
    
    def _record_rejection(self):
        """Record a rejected call (circuit open)"""
        self.stats.total_calls += 1
        self.stats.rejected_calls += 1
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for protecting functions"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.call(func, *args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await self.call_async(func, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    
    def __enter__(self):
        """Context manager entry"""
        if not self.is_available:
            self._record_rejection()
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is None:
            self._record_success()
        else:
            self._record_failure(exc_val)
        return False  # Don't suppress exceptions
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments for function
            
        Returns:
            Function result or fallback value
        """
        if not self.is_available:
            self._record_rejection()
            if self.fallback:
                logger.info(f"CircuitBreaker '{self.name}': using fallback")
                return self.fallback()
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            if self.fallback:
                return self.fallback()
            raise
    
    async def call_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Async version of call"""
        if not self.is_available:
            self._record_rejection()
            if self.fallback:
                if asyncio.iscoroutinefunction(self.fallback):
                    return await self.fallback()
                return self.fallback()
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            if self.fallback:
                if asyncio.iscoroutinefunction(self.fallback):
                    return await self.fallback()
                return self.fallback()
            raise
    
    def reset(self):
        """Manually reset circuit to closed state"""
        self._transition_to(CircuitState.CLOSED)
        self.stats = CircuitStats()
        logger.info(f"CircuitBreaker '{self.name}' manually reset")
    
    def get_status(self) -> Dict:
        """Get current circuit status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "is_available": self.is_available,
            "stats": self.stats.to_dict(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            }
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retry with exponential backoff.
    
    Usage:
    ------
    >>> @retry_with_backoff(max_retries=3, base_delay=1.0)
    >>> def flaky_api_call():
    ...     return requests.get(url)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"All {max_retries} retries failed for {func.__name__}")
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            
            raise last_exception
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__} in {delay:.1f}s")
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    
    return decorator


class CircuitBreakerRegistry:
    """
    Global registry for circuit breakers.
    
    Allows monitoring all breakers in the system.
    """
    
    _breakers: Dict[str, CircuitBreaker] = {}
    
    @classmethod
    def register(cls, breaker: CircuitBreaker):
        """Register a circuit breaker"""
        cls._breakers[breaker.name] = breaker
    
    @classmethod
    def get(cls, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name"""
        return cls._breakers.get(name)
    
    @classmethod
    def get_or_create(
        cls,
        name: str,
        config: CircuitBreakerConfig = None,
        fallback: Callable = None
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker"""
        if name not in cls._breakers:
            breaker = CircuitBreaker(name, config, fallback)
            cls._breakers[name] = breaker
        return cls._breakers[name]
    
    @classmethod
    def get_all_status(cls) -> Dict[str, Dict]:
        """Get status of all circuit breakers"""
        return {name: breaker.get_status() for name, breaker in cls._breakers.items()}
    
    @classmethod
    def reset_all(cls):
        """Reset all circuit breakers"""
        for breaker in cls._breakers.values():
            breaker.reset()


# ============== CONVENIENCE FUNCTIONS ==============

def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout_seconds: float = 30.0
) -> CircuitBreaker:
    """Get or create a circuit breaker"""
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        timeout_seconds=timeout_seconds
    )
    return CircuitBreakerRegistry.get_or_create(name, config)


def protected_call(
    name: str,
    func: Callable[..., T],
    *args,
    fallback: T = None,
    **kwargs
) -> T:
    """
    Execute a function with circuit breaker protection.
    
    Args:
        name: Circuit breaker name
        func: Function to execute
        fallback: Value to return if circuit is open
        
    Returns:
        Function result or fallback
    """
    breaker = get_circuit_breaker(name)
    breaker.fallback = lambda: fallback
    return breaker.call(func, *args, **kwargs)
