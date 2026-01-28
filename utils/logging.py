"""
QUANT_INDUSTRY_V1 Logging Utilities

Provides structured logging with JSON output and context propagation.
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from core.context import get_current_context


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Output format:
    {
        "timestamp": "2026-01-22T10:30:00.000Z",
        "level": "INFO",
        "logger": "module.name",
        "message": "Log message",
        "run_id": "abc123",
        "correlation_id": "xyz789",
        "extra": {...}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add context if available
        ctx = get_current_context()
        if ctx:
            log_entry['run_id'] = ctx.run_id
            log_entry['correlation_id'] = ctx.correlation_id

        # Add record extras
        if hasattr(record, 'run_id'):
            log_entry['run_id'] = record.run_id
        if hasattr(record, 'correlation_id'):
            log_entry['correlation_id'] = record.correlation_id

        # Add any extra data
        extra_keys = set(record.__dict__.keys()) - {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'message', 'thread',
            'threadName', 'run_id', 'correlation_id'
        }
        if extra_keys:
            log_entry['extra'] = {k: record.__dict__[k] for k in extra_keys}

        # Add exception info
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for development.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"

        # Add context
        ctx = get_current_context()
        if ctx:
            record.msg = f"[{ctx.run_id}] {record.msg}"

        return super().format(record)


class StructuredLogger:
    """
    Logger wrapper with structured data support.

    Usage:
        log = StructuredLogger('my_module')
        log.info("Processing", symbol='AAPL', action='buy')
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(
        self,
        level: int,
        msg: str,
        **kwargs
    ):
        """Internal log method with extra data support."""
        extra = {'extra_data': kwargs} if kwargs else {}
        self._logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._log(logging.CRITICAL, msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        self._logger.exception(msg, extra={'extra_data': kwargs} if kwargs else {})


def setup_logging(
    level: str = 'INFO',
    log_dir: Optional[Path] = None,
    json_output: bool = False,
    console: bool = True,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (None = no file logging)
        json_output: Use JSON format for file output
        console: Enable console output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        # Use colored output for console in development
        if not json_output:
            formatter = ColoredFormatter(
                '%(asctime)s %(levelname)s %(name)s: %(message)s',
                datefmt='%H:%M:%S'
            )
        else:
            formatter = JSONFormatter()

        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main log file with rotation
        log_file = log_dir / 'quant.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

        # Error log file
        error_file = log_dir / 'error.log'
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(error_handler)

    # Reduce noise from third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('alpaca').setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger for a module."""
    return StructuredLogger(name)
