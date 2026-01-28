"""
QUANT_INDUSTRY_V1 Run Context

Provides thread-safe context management for tracking run state,
correlation IDs, and other contextual information.
"""

import threading
import uuid
import hashlib
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Thread-local storage for context
_context_local = threading.local()


@dataclass
class RunContext:
    """
    Execution context for a single run.

    Provides:
    - Run identification and tracking
    - Correlation ID propagation
    - Git hash for reproducibility
    - Timing information
    """
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    mode: str = 'paper'
    config_hash: str = ''
    git_hash: Optional[str] = None

    start_time: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Parent context (for nested runs)
    parent: Optional['RunContext'] = None

    def __post_init__(self):
        """Initialize derived fields."""
        if self.git_hash is None:
            self.git_hash = self._get_git_hash()

        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())[:12]

    @staticmethod
    def _get_git_hash() -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=None
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def new_correlation_id(self) -> str:
        """Generate a new correlation ID for a sub-operation."""
        return f"{self.correlation_id}-{str(uuid.uuid4())[:4]}"

    def child_context(self, **kwargs) -> 'RunContext':
        """Create a child context with inherited properties."""
        return RunContext(
            run_id=self.run_id,
            mode=kwargs.get('mode', self.mode),
            config_hash=kwargs.get('config_hash', self.config_hash),
            git_hash=self.git_hash,
            correlation_id=self.new_correlation_id(),
            parent=self,
            metadata={**self.metadata, **kwargs.get('metadata', {})},
        )

    @property
    def elapsed_seconds(self) -> float:
        """Get seconds since run started."""
        return (datetime.utcnow() - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'run_id': self.run_id,
            'mode': self.mode,
            'config_hash': self.config_hash,
            'git_hash': self.git_hash,
            'start_time': self.start_time.isoformat(),
            'correlation_id': self.correlation_id,
            'metadata': self.metadata,
        }

    def log_dict(self) -> Dict[str, str]:
        """Get dictionary suitable for logging context."""
        return {
            'run_id': self.run_id,
            'correlation_id': self.correlation_id,
        }


def get_current_context() -> Optional[RunContext]:
    """Get the current thread's run context."""
    return getattr(_context_local, 'context', None)


def set_current_context(context: Optional[RunContext]) -> None:
    """Set the current thread's run context."""
    _context_local.context = context


def get_or_create_context(**kwargs) -> RunContext:
    """Get current context or create a new one."""
    ctx = get_current_context()
    if ctx is None:
        ctx = RunContext(**kwargs)
        set_current_context(ctx)
    return ctx


@contextmanager
def run_context(**kwargs):
    """
    Context manager for running with a specific context.

    Usage:
        with run_context(mode='backtest') as ctx:
            # code runs with this context
            pass
    """
    previous_context = get_current_context()
    new_context = RunContext(**kwargs)
    set_current_context(new_context)

    try:
        yield new_context
    finally:
        set_current_context(previous_context)


@contextmanager
def child_context(**kwargs):
    """
    Context manager for creating a child context.

    Usage:
        with child_context(metadata={'operation': 'training'}) as ctx:
            # code runs with child context
            pass
    """
    current = get_current_context()
    if current is None:
        raise RuntimeError("No current context to create child from")

    child = current.child_context(**kwargs)
    set_current_context(child)

    try:
        yield child
    finally:
        set_current_context(current)


class ContextLogger:
    """
    Logger wrapper that automatically includes context information.

    Usage:
        log = ContextLogger('my_module')
        log.info("Something happened")  # Includes run_id, correlation_id
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _add_context(self, extra: Optional[Dict] = None) -> Dict[str, Any]:
        """Add context information to log extras."""
        result = extra.copy() if extra else {}

        ctx = get_current_context()
        if ctx:
            result.update(ctx.log_dict())

        return result

    def debug(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        self._logger.debug(msg, *args, extra=self._add_context(extra), **kwargs)

    def info(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        self._logger.info(msg, *args, extra=self._add_context(extra), **kwargs)

    def warning(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        self._logger.warning(msg, *args, extra=self._add_context(extra), **kwargs)

    def error(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        self._logger.error(msg, *args, extra=self._add_context(extra), **kwargs)

    def critical(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        self._logger.critical(msg, *args, extra=self._add_context(extra), **kwargs)

    def exception(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        self._logger.exception(msg, *args, extra=self._add_context(extra), **kwargs)
