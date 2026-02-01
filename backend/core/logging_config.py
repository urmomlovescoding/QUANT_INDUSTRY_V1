"""
Logging Configuration
=====================
Centralized logging setup for QUANT_INDUSTRY_V1.

Provides:
- Structured logging with JSON support
- Log rotation
- Separate files for trades, errors, and system
- Color console output
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Log levels with colors for console
LOG_COLORS = {
    'DEBUG': '\033[36m',    # Cyan
    'INFO': '\033[32m',     # Green
    'WARNING': '\033[33m',  # Yellow
    'ERROR': '\033[31m',    # Red
    'CRITICAL': '\033[35m', # Magenta
    'RESET': '\033[0m'
}


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output."""

    def format(self, record):
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = LOG_COLORS.get(record.levelname, LOG_COLORS['RESET'])
            reset = LOG_COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """Formatter that outputs JSON for structured logging."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


class TradeLogFilter(logging.Filter):
    """Filter that only allows trade-related logs."""

    def filter(self, record):
        return any(keyword in record.getMessage().lower()
                  for keyword in ['trade', 'order', 'position', 'fill', 'pnl'])


class ErrorLogFilter(logging.Filter):
    """Filter for ERROR and above."""

    def filter(self, record):
        return record.levelno >= logging.ERROR


def setup_logging(
    log_dir: str = "logs",
    level: int = logging.INFO,
    json_logs: bool = False,
    console_output: bool = True
) -> None:
    """
    Setup logging configuration.

    Args:
        log_dir: Directory for log files
        level: Logging level
        json_logs: Use JSON format for files
        console_output: Enable console logging
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Main log file (rotating)
    main_handler = logging.handlers.RotatingFileHandler(
        log_path / "quant_industry.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    main_handler.setLevel(level)
    if json_logs:
        main_handler.setFormatter(JSONFormatter())
    else:
        main_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s'
        ))
    root_logger.addHandler(main_handler)

    # Trade-specific log file
    trade_handler = logging.handlers.RotatingFileHandler(
        log_path / "trades.log",
        maxBytes=5_000_000,
        backupCount=10
    )
    trade_handler.setLevel(logging.INFO)
    trade_handler.addFilter(TradeLogFilter())
    trade_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(message)s'
    ))
    root_logger.addHandler(trade_handler)

    # Error-only log file
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log",
        maxBytes=5_000_000,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s\n%(exc_info)s'
    ))
    root_logger.addHandler(error_handler)

    logging.info("Logging configured")


def get_trade_logger() -> logging.Logger:
    """Get logger specifically for trade events."""
    return logging.getLogger("TRADES")


def get_safety_logger() -> logging.Logger:
    """Get logger for safety/risk events."""
    return logging.getLogger("SAFETY")


def get_ml_logger() -> logging.Logger:
    """Get logger for ML/brain events."""
    return logging.getLogger("ML")


def log_trade(
    symbol: str,
    action: str,
    price: float,
    quantity: int,
    pnl: Optional[float] = None,
    strategy: Optional[str] = None,
    **kwargs
) -> None:
    """
    Convenience function to log trade events.

    Args:
        symbol: Trading symbol
        action: Action type (OPEN, CLOSE, etc.)
        price: Trade price
        quantity: Trade quantity
        pnl: Profit/loss (for closes)
        strategy: Strategy name
        **kwargs: Additional fields
    """
    logger = get_trade_logger()

    msg_parts = [f"{action} {symbol} {quantity}@{price:.2f}"]
    if pnl is not None:
        msg_parts.append(f"PnL=${pnl:.2f}")
    if strategy:
        msg_parts.append(f"strategy={strategy}")

    for key, value in kwargs.items():
        msg_parts.append(f"{key}={value}")

    logger.info(" | ".join(msg_parts))


def log_safety_event(event: str, details: dict) -> None:
    """Log a safety/risk event."""
    logger = get_safety_logger()
    logger.warning(f"SAFETY: {event} | {json.dumps(details)}")


__all__ = [
    'setup_logging',
    'get_trade_logger',
    'get_safety_logger',
    'get_ml_logger',
    'log_trade',
    'log_safety_event',
]
