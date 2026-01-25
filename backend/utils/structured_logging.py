"""
Structured Logging for QUANT INDUSTRY
=====================================
Provides consistent, structured logging across all components.
Matches quant-platform pattern for production observability.

Features:
- Component-based logging with prefixes
- Structured log messages (JSON-compatible)
- Performance metrics logging
- Trade activity logging
- Error context tracking
"""
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional


class LogComponent(Enum):
    """Standard component names for logging."""
    API = "API"
    DATA = "DATA"
    TRADING = "TRADING"
    RISK = "RISK"
    BRAIN = "BRAIN"
    EXECUTION = "EXECUTION"
    WEBSOCKET = "WS"
    BACKTEST = "BACKTEST"
    HEALTH = "HEALTH"
    AUTH = "AUTH"
    CONFIG = "CONFIG"
    SCHEDULER = "SCHEDULER"


class LogLevel(Enum):
    """Log levels with numeric values."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogContext:
    """Context information for structured logs."""
    component: LogComponent
    operation: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    symbol: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "component": self.component.value,
            "operation": self.operation
        }
        if self.request_id:
            result["request_id"] = self.request_id
        if self.user_id:
            result["user_id"] = self.user_id
        if self.symbol:
            result["symbol"] = self.symbol
        if self.extra:
            result.update(self.extra)
        return result


@dataclass
class PerformanceMetric:
    """Performance metric for logging."""
    operation: str
    duration_ms: float
    success: bool
    component: LogComponent
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "component": self.component.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that produces structured log output.
    Includes component name, timestamp, and structured data.
    """

    def __init__(self, include_json: bool = False):
        super().__init__()
        self.include_json = include_json

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        name = record.name

        # Get component from record if available
        component = getattr(record, 'component', '')
        component_prefix = f"[{component}] " if component else ""

        # Get structured data if available
        structured = getattr(record, 'structured', None)

        # Base message
        base_msg = f"{timestamp} | {level:8s} | {component_prefix}{name} | {record.getMessage()}"

        # Add JSON data if available and requested
        if self.include_json and structured:
            base_msg += f" | {json.dumps(structured)}"

        # Add exception info if present
        if record.exc_info:
            base_msg += f"\n{self.formatException(record.exc_info)}"

        return base_msg


class ComponentLogger:
    """
    Logger wrapper that provides component-specific logging.
    Automatically prefixes logs with component name.
    """

    def __init__(self, component: LogComponent, name: str = None):
        self.component = component
        self._logger = logging.getLogger(name or f"quant.{component.value.lower()}")
        self._performance_history: List[PerformanceMetric] = []
        self._max_history = 1000

    def _log(
        self,
        level: int,
        msg: str,
        *args,
        context: Optional[LogContext] = None,
        structured: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
        **kwargs
    ):
        """Internal logging method with structured data support."""
        extra = {
            'component': self.component.value,
            'structured': structured or {}
        }

        if context:
            extra['structured'].update(context.to_dict())

        self._logger.log(level, f"[{self.component.value}] {msg}", *args, extra=extra, exc_info=exc_info, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, exc_info: bool = False, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, *args, exc_info: bool = False, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, msg, *args, exc_info=exc_info, **kwargs)

    def log_trade(
        self,
        action: str,
        symbol: str,
        quantity: int,
        price: float,
        order_id: str = None,
        **extra
    ):
        """Log a trade activity."""
        structured = {
            "trade": {
                "action": action,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "order_id": order_id,
                **extra
            }
        }
        self.info(f"TRADE: {action} {quantity} {symbol} @ ${price:.2f}", structured=structured)

    def log_signal(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        strategy: str = None,
        **extra
    ):
        """Log a trading signal."""
        structured = {
            "signal": {
                "symbol": symbol,
                "direction": direction,
                "confidence": confidence,
                "strategy": strategy,
                **extra
            }
        }
        self.info(f"SIGNAL: {direction} {symbol} (conf: {confidence:.2f})", structured=structured)

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool,
        **details
    ):
        """Log a performance metric."""
        metric = PerformanceMetric(
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            component=self.component,
            details=details
        )
        self._record_metric(metric)

        status = "OK" if success else "FAILED"
        self.debug(f"PERF: {operation} {status} ({duration_ms:.2f}ms)", structured=metric.to_dict())

    def _record_metric(self, metric: PerformanceMetric):
        """Record a performance metric in history."""
        self._performance_history.append(metric)
        if len(self._performance_history) > self._max_history:
            self._performance_history.pop(0)

    def get_performance_stats(self, operation: str = None) -> Dict[str, Any]:
        """Get performance statistics."""
        metrics = self._performance_history
        if operation:
            metrics = [m for m in metrics if m.operation == operation]

        if not metrics:
            return {"count": 0}

        durations = [m.duration_ms for m in metrics]
        successes = [m for m in metrics if m.success]

        return {
            "count": len(metrics),
            "success_rate": len(successes) / len(metrics) if metrics else 0,
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "recent_failures": len([m for m in metrics[-10:] if not m.success])
        }


def timed_operation(component: LogComponent, operation: str):
    """
    Decorator to time and log function execution.

    Usage:
        @timed_operation(LogComponent.DATA, "fetch_quotes")
        async def fetch_quotes(symbols):
            ...
    """
    def decorator(func: Callable):
        logger = get_component_logger(component)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            success = True
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start) * 1000
                logger.log_performance(operation, duration_ms, success)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            success = True
            try:
                return func(*args, **kwargs)
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start) * 1000
                logger.log_performance(operation, duration_ms, success)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Global logger instances (cached)
_component_loggers: Dict[LogComponent, ComponentLogger] = {}
_logger_lock = threading.Lock()


def get_component_logger(component: LogComponent) -> ComponentLogger:
    """Get or create a component-specific logger."""
    with _logger_lock:
        if component not in _component_loggers:
            _component_loggers[component] = ComponentLogger(component)
        return _component_loggers[component]


def configure_structured_logging(
    level: int = logging.INFO,
    include_json: bool = False,
    log_file: str = None
):
    """
    Configure structured logging for the application.

    Args:
        level: Minimum log level
        include_json: Include JSON structured data in output
        log_file: Optional file path for logging
    """
    # Create formatter
    formatter = StructuredFormatter(include_json=include_json)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)


# Convenience loggers for each component
api_logger = get_component_logger(LogComponent.API)
data_logger = get_component_logger(LogComponent.DATA)
trading_logger = get_component_logger(LogComponent.TRADING)
risk_logger = get_component_logger(LogComponent.RISK)
brain_logger = get_component_logger(LogComponent.BRAIN)
execution_logger = get_component_logger(LogComponent.EXECUTION)
ws_logger = get_component_logger(LogComponent.WEBSOCKET)
health_logger = get_component_logger(LogComponent.HEALTH)
