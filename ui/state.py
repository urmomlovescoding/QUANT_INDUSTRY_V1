"""
QUANT_INDUSTRY_V1 UI State Management

Centralized state store with event-based updates.
Follows unidirectional data flow pattern.

Rollback Plan: Delete this file, revert dependent modules
Tests Required: Unit tests for state transitions, event dispatch
Failure Modes: Invalid state -> validation errors, logged and ignored
"""

import threading
import queue
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable, Set, TypeVar, Generic
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from copy import deepcopy
import json

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# EVENT SYSTEM
# =============================================================================

class EventType(Enum):
    """UI event types."""

    # Data events
    DATA_UPDATED = auto()
    DATA_ERROR = auto()
    DATA_LOADING = auto()

    # Signal events
    SIGNALS_UPDATED = auto()
    SIGNAL_EXECUTED = auto()

    # Portfolio events
    POSITIONS_UPDATED = auto()
    PORTFOLIO_UPDATED = auto()
    TRADE_EXECUTED = auto()

    # Regime events
    REGIME_CHANGED = auto()

    # Risk events
    RISK_ALERT = auto()
    RISK_BREACH = auto()
    KILL_SWITCH = auto()

    # System events
    HEALTH_UPDATED = auto()
    ERROR_OCCURRED = auto()
    NOTIFICATION = auto()

    # UI events
    VIEW_CHANGED = auto()
    THEME_CHANGED = auto()
    LAYOUT_CHANGED = auto()
    REFRESH_REQUESTED = auto()

    # Trading control events
    EMERGENCY_STOP = auto()
    CLOSE_ALL_POSITIONS = auto()


@dataclass
class Event:
    """Event object for state changes."""

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'type': self.type.name,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
        }


EventHandler = Callable[[Event], None]


class EventBus:
    """
    Thread-safe event bus for UI updates.

    Implements publish-subscribe pattern for loose coupling.
    """

    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._lock = threading.RLock()
        self._event_queue: queue.Queue = queue.Queue()
        self._processing = False

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type."""
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logger.debug(f"Subscribed handler to {event_type.name}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type."""
        with self._lock:
            if event_type in self._handlers:
                try:
                    self._handlers[event_type].remove(handler)
                except ValueError:
                    pass

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        self._event_queue.put(event)

        # Process immediately if not in batch
        if not self._processing:
            self._process_events()

    def _process_events(self) -> None:
        """Process queued events."""
        self._processing = True
        try:
            while not self._event_queue.empty():
                event = self._event_queue.get_nowait()
                self._dispatch(event)
        finally:
            self._processing = False

    def _dispatch(self, event: Event) -> None:
        """Dispatch event to handlers."""
        with self._lock:
            handlers = self._handlers.get(event.type, []).copy()

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.type.name}: {e}")

    def clear(self) -> None:
        """Clear all subscriptions."""
        with self._lock:
            self._handlers.clear()


# Global event bus
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# =============================================================================
# STATE MODELS
# =============================================================================

@dataclass
class SignalState:
    """State for a single trading signal."""

    symbol: str
    direction: str = "NEUTRAL"  # LONG, SHORT, NEUTRAL
    strength: float = 0.0       # -1.0 to 1.0
    confidence: float = 0.0     # 0.0 to 1.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    expected_return: float = 0.0
    regime: str = "UNKNOWN"
    model_id: str = ""
    explanation: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PositionState:
    """State for a trading position."""

    symbol: str
    side: str = "long"  # long, short
    qty: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    entry_time: Optional[datetime] = None


@dataclass
class PortfolioState:
    """Portfolio summary state."""

    cash: float = 0.0
    equity: float = 0.0
    buying_power: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    day_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0


@dataclass
class MarketState:
    """Market data state."""

    regime: str = "UNKNOWN"
    regime_confidence: float = 0.5
    spy_price: float = 0.0
    spy_change_pct: float = 0.0
    vix: float = 0.0
    market_open: bool = False
    last_update: Optional[datetime] = None


@dataclass
class SystemHealthState:
    """System health state."""

    status: str = "healthy"  # healthy, degraded, unhealthy
    db_status: str = "ok"
    api_status: str = "ok"
    model_status: str = "ok"
    data_freshness: float = 0.0  # seconds since last update
    error_count: int = 0
    warning_count: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    last_check: Optional[datetime] = None


@dataclass
class NotificationState:
    """Notification/alert state."""

    id: str
    level: str = "info"  # info, warning, error, success
    title: str = ""
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read: bool = False
    dismissible: bool = True


@dataclass
class UIState:
    """UI-specific state."""

    current_view: str = "dashboard"
    selected_symbol: Optional[str] = None
    sidebar_collapsed: bool = False
    theme: str = "dark"
    layout: str = "default"
    loading: bool = False
    error: Optional[str] = None


# =============================================================================
# APPLICATION STATE
# =============================================================================

@dataclass
class AppState:
    """
    Complete application state.

    Single source of truth for all UI state.
    """

    # Trading state
    signals: Dict[str, SignalState] = field(default_factory=dict)
    positions: Dict[str, PositionState] = field(default_factory=dict)
    portfolio: PortfolioState = field(default_factory=PortfolioState)

    # Market state
    market: MarketState = field(default_factory=MarketState)

    # System state
    health: SystemHealthState = field(default_factory=SystemHealthState)
    notifications: List[NotificationState] = field(default_factory=list)

    # UI state
    ui: UIState = field(default_factory=UIState)

    # Metadata
    run_id: Optional[str] = None
    mode: str = "paper"  # paper, live, backtest
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# STATE STORE
# =============================================================================

class StateStore:
    """
    Thread-safe state store with change detection.

    Implements observer pattern for reactive updates.
    """

    def __init__(self):
        self._state: AppState = AppState()
        self._lock = threading.RLock()
        self._event_bus = get_event_bus()
        self._watchers: Dict[str, Set[Callable]] = {}

    @property
    def state(self) -> AppState:
        """Get current state (read-only snapshot)."""
        with self._lock:
            return deepcopy(self._state)

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get state value by dot-notation path.

        Example: store.get('portfolio.cash')
        """
        with self._lock:
            parts = path.split('.')
            value = self._state
            try:
                for part in parts:
                    if hasattr(value, part):
                        value = getattr(value, part)
                    elif isinstance(value, dict):
                        value = value[part]
                    else:
                        return default
                return deepcopy(value)
            except (KeyError, AttributeError):
                return default

    def update(self, path: str, value: Any) -> None:
        """
        Update state value by dot-notation path.

        Example: store.update('portfolio.cash', 100000)
        """
        with self._lock:
            parts = path.split('.')
            target = self._state

            # Navigate to parent
            for part in parts[:-1]:
                if hasattr(target, part):
                    target = getattr(target, part)
                elif isinstance(target, dict):
                    target = target[part]

            # Set value
            final_key = parts[-1]
            if hasattr(target, final_key):
                setattr(target, final_key, value)
            elif isinstance(target, dict):
                target[final_key] = value

        # Notify watchers
        self._notify_watchers(path)

    def update_signals(self, signals: Dict[str, SignalState]) -> None:
        """Update all signals."""
        with self._lock:
            self._state.signals = signals

        self._event_bus.publish(Event(
            type=EventType.SIGNALS_UPDATED,
            data={'count': len(signals)},
        ))
        self._notify_watchers('signals')

    def update_signal(self, symbol: str, signal: SignalState) -> None:
        """Update a single signal."""
        with self._lock:
            self._state.signals[symbol] = signal

        self._event_bus.publish(Event(
            type=EventType.SIGNALS_UPDATED,
            data={'symbol': symbol},
        ))
        self._notify_watchers(f'signals.{symbol}')

    def update_positions(self, positions: Dict[str, PositionState]) -> None:
        """Update all positions."""
        with self._lock:
            self._state.positions = positions

        self._event_bus.publish(Event(
            type=EventType.POSITIONS_UPDATED,
            data={'count': len(positions)},
        ))
        self._notify_watchers('positions')

    def update_portfolio(self, portfolio: PortfolioState) -> None:
        """Update portfolio state."""
        with self._lock:
            self._state.portfolio = portfolio

        self._event_bus.publish(Event(
            type=EventType.PORTFOLIO_UPDATED,
            data={'equity': portfolio.equity, 'pnl': portfolio.total_pnl},
        ))
        self._notify_watchers('portfolio')

    def update_market(self, market: MarketState) -> None:
        """Update market state."""
        old_regime = self._state.market.regime
        with self._lock:
            self._state.market = market

        if market.regime != old_regime:
            self._event_bus.publish(Event(
                type=EventType.REGIME_CHANGED,
                data={'old': old_regime, 'new': market.regime},
            ))
        self._notify_watchers('market')

    def update_health(self, health: SystemHealthState) -> None:
        """Update system health state."""
        with self._lock:
            self._state.health = health

        self._event_bus.publish(Event(
            type=EventType.HEALTH_UPDATED,
            data={'status': health.status},
        ))
        self._notify_watchers('health')

    def add_notification(self, notification: NotificationState) -> None:
        """Add a notification."""
        with self._lock:
            self._state.notifications.insert(0, notification)
            # Keep last 100 notifications
            self._state.notifications = self._state.notifications[:100]

        self._event_bus.publish(Event(
            type=EventType.NOTIFICATION,
            data={'level': notification.level, 'message': notification.message},
        ))

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        with self._lock:
            self._state.ui.loading = loading
        self._notify_watchers('ui.loading')

    def set_error(self, error: Optional[str]) -> None:
        """Set error state."""
        with self._lock:
            self._state.ui.error = error
        if error:
            self._event_bus.publish(Event(
                type=EventType.ERROR_OCCURRED,
                data={'error': error},
            ))
        self._notify_watchers('ui.error')

    def set_view(self, view: str) -> None:
        """Set current view."""
        old_view = self._state.ui.current_view
        with self._lock:
            self._state.ui.current_view = view

        self._event_bus.publish(Event(
            type=EventType.VIEW_CHANGED,
            data={'old': old_view, 'new': view},
        ))
        self._notify_watchers('ui.current_view')

    def watch(self, path: str, callback: Callable) -> None:
        """Watch a state path for changes."""
        with self._lock:
            if path not in self._watchers:
                self._watchers[path] = set()
            self._watchers[path].add(callback)

    def unwatch(self, path: str, callback: Callable) -> None:
        """Stop watching a state path."""
        with self._lock:
            if path in self._watchers:
                self._watchers[path].discard(callback)

    def _notify_watchers(self, path: str) -> None:
        """Notify watchers of a path change."""
        with self._lock:
            watchers = self._watchers.get(path, set()).copy()
            # Also notify parent path watchers
            parts = path.split('.')
            for i in range(len(parts)):
                parent_path = '.'.join(parts[:i+1])
                watchers.update(self._watchers.get(parent_path, set()))

        for watcher in watchers:
            try:
                watcher()
            except Exception as e:
                logger.error(f"State watcher error for {path}: {e}")

    def reset(self) -> None:
        """Reset state to initial values."""
        with self._lock:
            self._state = AppState()
        self._event_bus.publish(Event(type=EventType.VIEW_CHANGED, data={'view': 'dashboard'}))


# Global store instance
_store: Optional[StateStore] = None


def get_store() -> StateStore:
    """Get global state store instance."""
    global _store
    if _store is None:
        _store = StateStore()
    return _store


def init_store(run_id: str = None, mode: str = "paper") -> StateStore:
    """Initialize state store with run context."""
    store = get_store()
    store.update('run_id', run_id)
    store.update('mode', mode)
    return store


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def dispatch(event_type: EventType, data: Dict[str, Any] = None, source: str = "system") -> None:
    """Convenience function to dispatch events."""
    event = Event(
        type=event_type,
        data=data or {},
        source=source,
    )
    get_event_bus().publish(event)


def notify(
    message: str,
    level: str = "info",
    title: str = "",
    dismissible: bool = True
) -> None:
    """Convenience function to add notification."""
    import uuid
    notification = NotificationState(
        id=str(uuid.uuid4()),
        level=level,
        title=title,
        message=message,
        dismissible=dismissible,
    )
    get_store().add_notification(notification)
