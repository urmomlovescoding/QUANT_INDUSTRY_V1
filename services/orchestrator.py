"""
QUANT_INDUSTRY_V1 System Orchestrator

Central orchestration for the trading platform:
- Component lifecycle management
- Event routing
- State coordination
- Graceful shutdown

Rollback Plan: Delete this file
Tests Required: Startup/shutdown, event flow
Failure Modes: Safe shutdown, preserve state
"""

import logging
import threading
import signal
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
import json

logger = logging.getLogger(__name__)


# =============================================================================
# ORCHESTRATION TYPES
# =============================================================================

class ComponentState(Enum):
    """Component lifecycle state."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class EventType(Enum):
    """System event types."""
    # Data events
    MARKET_DATA = "market_data"
    FEATURE_UPDATE = "feature_update"

    # Trading events
    SIGNAL_GENERATED = "signal_generated"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"

    # Risk events
    RISK_BREACH = "risk_breach"
    POSITION_UPDATE = "position_update"

    # System events
    COMPONENT_STARTED = "component_started"
    COMPONENT_STOPPED = "component_stopped"
    ERROR_OCCURRED = "error_occurred"
    ALERT_RAISED = "alert_raised"

    # Grading events
    GRADE_UPDATED = "grade_updated"
    REMEDIATION_SUGGESTED = "remediation_suggested"


@dataclass
class Event:
    """System event."""
    event_type: EventType
    source: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': self.event_type.value,
            'source': self.source,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'correlation_id': self.correlation_id,
        }


@dataclass
class ComponentInfo:
    """Information about a managed component."""
    name: str
    state: ComponentState
    instance: Any
    start_callback: Optional[Callable] = None
    stop_callback: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    error_message: Optional[str] = None


# =============================================================================
# EVENT BUS
# =============================================================================

class EventBus:
    """
    Central event bus for component communication.

    Implements publish-subscribe pattern.
    """

    def __init__(self, max_queue_size: int = 10000):
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._queue: Queue = Queue(maxsize=max_queue_size)
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None

        # Event history for debugging
        self._history: List[Event] = []
        self._max_history = 1000

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None]
    ) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None]
    ) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: Event) -> None:
        """Publish an event."""
        try:
            self._queue.put_nowait(event)
        except Exception:
            logger.warning(f"Event queue full, dropping event: {event.event_type}")

    def start(self) -> None:
        """Start the event processor."""
        if self._running:
            return

        self._running = True
        self._processor_thread = threading.Thread(
            target=self._process_events,
            daemon=True
        )
        self._processor_thread.start()
        logger.info("Event bus started")

    def stop(self) -> None:
        """Stop the event processor."""
        self._running = False
        if self._processor_thread:
            self._processor_thread.join(timeout=5)
        logger.info("Event bus stopped")

    def _process_events(self) -> None:
        """Process events from queue."""
        while self._running:
            try:
                event = self._queue.get(timeout=0.1)
                self._dispatch_event(event)

                # Store in history
                self._history.append(event)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")

    def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to subscribers."""
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def get_recent_events(
        self,
        event_type: EventType = None,
        limit: int = 100
    ) -> List[Event]:
        """Get recent events from history."""
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]


# =============================================================================
# SYSTEM ORCHESTRATOR
# =============================================================================

class SystemOrchestrator:
    """
    Central system orchestrator.

    Manages component lifecycle and coordinates the platform.
    """

    def __init__(self):
        self.components: Dict[str, ComponentInfo] = {}
        self.event_bus = EventBus()

        self._running = False
        self._shutdown_event = threading.Event()

        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def register_component(
        self,
        name: str,
        instance: Any,
        start_callback: Callable = None,
        stop_callback: Callable = None,
        dependencies: List[str] = None
    ) -> None:
        """Register a component with the orchestrator."""
        self.components[name] = ComponentInfo(
            name=name,
            state=ComponentState.STOPPED,
            instance=instance,
            start_callback=start_callback,
            stop_callback=stop_callback,
            dependencies=dependencies or []
        )
        logger.info(f"Registered component: {name}")

    def start(self) -> bool:
        """Start all components in dependency order."""
        try:
            logger.info("Starting system orchestrator...")

            # Start event bus first
            self.event_bus.start()

            # Determine start order based on dependencies
            start_order = self._resolve_dependencies()

            # Start components
            for name in start_order:
                if not self._start_component(name):
                    logger.error(f"Failed to start {name}, aborting startup")
                    self.stop()
                    return False

            self._running = True
            logger.info("System orchestrator started successfully")

            # Publish startup event
            self.event_bus.publish(Event(
                event_type=EventType.COMPONENT_STARTED,
                source="orchestrator",
                data={'component': 'system', 'status': 'running'}
            ))

            return True

        except Exception as e:
            logger.error(f"Startup error: {e}")
            return False

    def stop(self) -> None:
        """Stop all components gracefully."""
        logger.info("Stopping system orchestrator...")

        # Stop in reverse order
        start_order = self._resolve_dependencies()
        stop_order = list(reversed(start_order))

        for name in stop_order:
            self._stop_component(name)

        # Stop event bus last
        self.event_bus.stop()

        self._running = False
        self._shutdown_event.set()
        logger.info("System orchestrator stopped")

    def _start_component(self, name: str) -> bool:
        """Start a single component."""
        if name not in self.components:
            return False

        info = self.components[name]
        if info.state == ComponentState.RUNNING:
            return True

        logger.info(f"Starting component: {name}")
        info.state = ComponentState.STARTING

        try:
            # Call start callback if provided
            if info.start_callback:
                info.start_callback()
            elif hasattr(info.instance, 'start'):
                info.instance.start()

            info.state = ComponentState.RUNNING
            info.started_at = datetime.now(timezone.utc)

            self.event_bus.publish(Event(
                event_type=EventType.COMPONENT_STARTED,
                source="orchestrator",
                data={'component': name}
            ))

            return True

        except Exception as e:
            info.state = ComponentState.ERROR
            info.error_message = str(e)
            logger.error(f"Failed to start {name}: {e}")
            return False

    def _stop_component(self, name: str) -> None:
        """Stop a single component."""
        if name not in self.components:
            return

        info = self.components[name]
        if info.state != ComponentState.RUNNING:
            return

        logger.info(f"Stopping component: {name}")
        info.state = ComponentState.STOPPING

        try:
            if info.stop_callback:
                info.stop_callback()
            elif hasattr(info.instance, 'stop'):
                info.instance.stop()

            info.state = ComponentState.STOPPED

            self.event_bus.publish(Event(
                event_type=EventType.COMPONENT_STOPPED,
                source="orchestrator",
                data={'component': name}
            ))

        except Exception as e:
            logger.error(f"Error stopping {name}: {e}")
            info.state = ComponentState.ERROR

    def _resolve_dependencies(self) -> List[str]:
        """Resolve component dependencies and return start order."""
        resolved = []
        unresolved = set(self.components.keys())

        while unresolved:
            # Find components with all dependencies resolved
            ready = []
            for name in unresolved:
                deps = self.components[name].dependencies
                if all(d in resolved for d in deps):
                    ready.append(name)

            if not ready:
                # Circular dependency or missing dependency
                logger.warning(f"Could not resolve dependencies for: {unresolved}")
                # Add remaining in arbitrary order
                resolved.extend(unresolved)
                break

            resolved.extend(ready)
            unresolved -= set(ready)

        return resolved

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.stop()

    def wait_for_shutdown(self) -> None:
        """Block until shutdown is requested."""
        self._shutdown_event.wait()

    def get_status(self) -> Dict[str, Any]:
        """Get system status."""
        return {
            'running': self._running,
            'components': {
                name: {
                    'state': info.state.value,
                    'started_at': info.started_at.isoformat() if info.started_at else None,
                    'error': info.error_message,
                }
                for name, info in self.components.items()
            },
            'event_bus': {
                'running': self.event_bus._running,
                'queue_size': self.event_bus._queue.qsize(),
                'history_size': len(self.event_bus._history),
            }
        }


# =============================================================================
# PLATFORM BOOTSTRAP
# =============================================================================

class TradingPlatform:
    """
    Main trading platform class.

    Bootstraps and coordinates all system components.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.orchestrator = SystemOrchestrator()

        # Core components (initialized later)
        self.health_monitor = None
        self.grading_engine = None
        self.risk_engine = None
        self.security_manager = None
        self.strategy_registry = None

    def initialize(self, db_path: str) -> None:
        """Initialize all platform components."""
        from .health_monitor import HealthMonitor, DashboardService
        from .self_grade import SelfGradingEngine

        # Initialize core services
        self.health_monitor = HealthMonitor(check_interval_seconds=60)
        self.grading_engine = SelfGradingEngine(db_path)

        # Register with orchestrator
        self.orchestrator.register_component(
            'health_monitor',
            self.health_monitor,
            start_callback=self.health_monitor.start,
            stop_callback=self.health_monitor.stop
        )

        self.orchestrator.register_component(
            'grading_engine',
            self.grading_engine
        )

        # Create dashboard service
        self.dashboard = DashboardService(
            health_monitor=self.health_monitor,
            grading_engine=self.grading_engine
        )

        logger.info("Platform initialized")

    def start(self) -> bool:
        """Start the trading platform."""
        return self.orchestrator.start()

    def stop(self) -> None:
        """Stop the trading platform."""
        self.orchestrator.stop()

    def run(self) -> None:
        """Run the platform until shutdown."""
        if self.start():
            self.orchestrator.wait_for_shutdown()

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data."""
        if self.dashboard:
            return self.dashboard.get_dashboard_data()
        return {}

    def get_status(self) -> Dict[str, Any]:
        """Get platform status."""
        return {
            'platform': self.orchestrator.get_status(),
            'health': self.health_monitor.get_status() if self.health_monitor else {},
        }
