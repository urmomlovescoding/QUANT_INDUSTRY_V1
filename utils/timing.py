"""
QUANT_INDUSTRY_V1 Timing Utilities

Provides timing decorators and utilities for performance monitoring.
"""

import time
import functools
from typing import Callable, Optional, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class Timer:
    """
    Context manager for timing code blocks.

    Usage:
        with Timer("operation_name") as t:
            # code to time
        print(f"Took {t.elapsed:.3f}s")
    """

    def __init__(
        self,
        name: str = "operation",
        log: bool = True,
        threshold_ms: Optional[float] = None
    ):
        self.name = name
        self.log = log
        self.threshold_ms = threshold_ms
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self._elapsed: Optional[float] = None

    def __enter__(self) -> 'Timer':
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self._elapsed = self.end_time - self.start_time

        if self.log:
            elapsed_ms = self._elapsed * 1000
            if self.threshold_ms is None or elapsed_ms >= self.threshold_ms:
                logger.debug(f"{self.name} completed in {elapsed_ms:.2f}ms")

        return False

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self._elapsed is not None:
            return self._elapsed
        if self.start_time is not None:
            return time.perf_counter() - self.start_time
        return 0.0

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed * 1000


def timed(
    name: Optional[str] = None,
    log: bool = True,
    threshold_ms: Optional[float] = None
):
    """
    Decorator for timing function execution.

    Usage:
        @timed("my_function")
        def my_function():
            pass

        @timed(threshold_ms=100)  # Only log if > 100ms
        def potentially_slow():
            pass
    """
    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            with Timer(func_name, log=log, threshold_ms=threshold_ms):
                return func(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def timer(name: str = "operation"):
    """
    Simple context manager for timing.

    Usage:
        with timer("data_fetch"):
            fetch_data()
    """
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logger.debug(f"{name}: {elapsed * 1000:.2f}ms")


class PerformanceMonitor:
    """
    Collects and aggregates timing metrics.

    Usage:
        monitor = PerformanceMonitor()
        with monitor.track("api_call"):
            call_api()

        print(monitor.summary())
    """

    def __init__(self):
        self._metrics: dict = {}

    @contextmanager
    def track(self, name: str):
        """Track timing for a named operation."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            if name not in self._metrics:
                self._metrics[name] = {
                    'count': 0,
                    'total_ms': 0,
                    'min_ms': float('inf'),
                    'max_ms': 0,
                }
            self._metrics[name]['count'] += 1
            self._metrics[name]['total_ms'] += elapsed * 1000
            self._metrics[name]['min_ms'] = min(self._metrics[name]['min_ms'], elapsed * 1000)
            self._metrics[name]['max_ms'] = max(self._metrics[name]['max_ms'], elapsed * 1000)

    def summary(self) -> dict:
        """Get summary of all tracked metrics."""
        result = {}
        for name, data in self._metrics.items():
            result[name] = {
                'count': data['count'],
                'total_ms': round(data['total_ms'], 2),
                'avg_ms': round(data['total_ms'] / data['count'], 2) if data['count'] > 0 else 0,
                'min_ms': round(data['min_ms'], 2) if data['min_ms'] != float('inf') else 0,
                'max_ms': round(data['max_ms'], 2),
            }
        return result

    def reset(self):
        """Reset all metrics."""
        self._metrics.clear()


# Global performance monitor
_global_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    return _global_monitor
