"""
Health Monitoring Service for QUANT INDUSTRY
Provides comprehensive health checks, auto-recovery, and graceful degradation
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component"""
    name: str
    status: HealthStatus
    message: str = ""
    last_check: datetime = field(default_factory=datetime.now)
    response_time_ms: float = 0
    error_count: int = 0
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health"""
    status: HealthStatus
    components: Dict[str, ComponentHealth]
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    uptime_seconds: float
    timestamp: datetime
    warnings: List[str] = field(default_factory=list)


class HealthMonitor:
    """
    Monitors system health and provides auto-recovery capabilities
    """

    # Thresholds for health status
    CPU_WARNING_THRESHOLD = 80
    CPU_CRITICAL_THRESHOLD = 95
    MEMORY_WARNING_THRESHOLD = 80
    MEMORY_CRITICAL_THRESHOLD = 95
    DISK_WARNING_THRESHOLD = 85
    DISK_CRITICAL_THRESHOLD = 95
    MAX_CONSECUTIVE_FAILURES = 3

    def __init__(self):
        self._components: Dict[str, ComponentHealth] = {}
        self._health_checks: Dict[str, Callable] = {}
        self._recovery_handlers: Dict[str, Callable] = {}
        self._start_time = time.time()
        self._check_interval = 30  # seconds
        self._running = False
        self._last_full_check: Optional[datetime] = None

    def register_component(
        self,
        name: str,
        health_check: Callable,
        recovery_handler: Optional[Callable] = None
    ):
        """
        Register a component for health monitoring

        Args:
            name: Component name
            health_check: Async function that returns (status, message)
            recovery_handler: Optional async function to attempt recovery
        """
        self._components[name] = ComponentHealth(
            name=name,
            status=HealthStatus.UNKNOWN
        )
        self._health_checks[name] = health_check
        if recovery_handler:
            self._recovery_handlers[name] = recovery_handler
        logger.info(f"Registered health check for component: {name}")

    async def check_component(self, name: str) -> ComponentHealth:
        """Check health of a single component"""
        if name not in self._health_checks:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="Component not registered"
            )

        check_func = self._health_checks[name]
        component = self._components[name]

        start_time = time.time()
        try:
            status, message = await check_func()
            response_time = (time.time() - start_time) * 1000

            if status == HealthStatus.HEALTHY:
                component.consecutive_failures = 0
            else:
                component.consecutive_failures += 1
                component.error_count += 1

            component.status = status
            component.message = message
            component.response_time_ms = response_time
            component.last_check = datetime.now()

            # Attempt recovery if needed
            if (component.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES
                    and name in self._recovery_handlers):
                logger.warning(f"Attempting recovery for {name}")
                await self._attempt_recovery(name)

        except Exception as e:
            component.status = HealthStatus.UNHEALTHY
            component.message = f"Health check failed: {e!s}"
            component.consecutive_failures += 1
            component.error_count += 1
            component.last_check = datetime.now()
            logger.error(f"Health check error for {name}: {e}")

        return component

    async def _attempt_recovery(self, name: str):
        """Attempt to recover a failed component"""
        if name not in self._recovery_handlers:
            return

        try:
            recovery_func = self._recovery_handlers[name]
            success = await recovery_func()
            if success:
                logger.info(f"Recovery successful for {name}")
                self._components[name].consecutive_failures = 0
            else:
                logger.warning(f"Recovery failed for {name}")
        except Exception as e:
            logger.error(f"Recovery error for {name}: {e}")

    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system resource metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3)
            }
        except Exception as e:
            logger.warning(f"Failed to get system metrics: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "memory_available_gb": 0,
                "disk_percent": 0,
                "disk_free_gb": 0
            }

    async def get_full_health(self) -> SystemHealth:
        """Get comprehensive system health status"""
        # Check all components
        for name in self._health_checks:
            await self.check_component(name)

        # Get system metrics
        metrics = self.get_system_metrics()

        # Determine warnings
        warnings = []
        if metrics["cpu_percent"] > self.CPU_WARNING_THRESHOLD:
            warnings.append(f"High CPU usage: {metrics['cpu_percent']:.1f}%")
        if metrics["memory_percent"] > self.MEMORY_WARNING_THRESHOLD:
            warnings.append(f"High memory usage: {metrics['memory_percent']:.1f}%")
        if metrics["disk_percent"] > self.DISK_WARNING_THRESHOLD:
            warnings.append(f"High disk usage: {metrics['disk_percent']:.1f}%")

        # Determine overall status
        component_statuses = [c.status for c in self._components.values()]

        if any(s == HealthStatus.UNHEALTHY for s in component_statuses):
            overall_status = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in component_statuses) or (metrics["cpu_percent"] > self.CPU_CRITICAL_THRESHOLD or
              metrics["memory_percent"] > self.MEMORY_CRITICAL_THRESHOLD):
            overall_status = HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in component_statuses):
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.DEGRADED

        self._last_full_check = datetime.now()

        return SystemHealth(
            status=overall_status,
            components=dict(self._components),
            cpu_percent=metrics["cpu_percent"],
            memory_percent=metrics["memory_percent"],
            disk_percent=metrics["disk_percent"],
            uptime_seconds=time.time() - self._start_time,
            timestamp=datetime.now(),
            warnings=warnings
        )

    def get_quick_status(self) -> Dict[str, Any]:
        """Get quick health status without running checks"""
        metrics = self.get_system_metrics()
        unhealthy = sum(1 for c in self._components.values()
                       if c.status == HealthStatus.UNHEALTHY)
        degraded = sum(1 for c in self._components.values()
                      if c.status == HealthStatus.DEGRADED)

        if unhealthy > 0:
            status = "unhealthy"
        elif degraded > 0:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "uptime_seconds": time.time() - self._start_time,
            "cpu_percent": metrics["cpu_percent"],
            "memory_percent": metrics["memory_percent"],
            "components_total": len(self._components),
            "components_unhealthy": unhealthy,
            "components_degraded": degraded,
            "last_check": self._last_full_check.isoformat() if self._last_full_check else None
        }

    async def start_monitoring(self):
        """Start background health monitoring"""
        if self._running:
            return

        self._running = True
        logger.info("Starting health monitoring")

        while self._running:
            try:
                await self.get_full_health()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(5)

    def stop_monitoring(self):
        """Stop background health monitoring"""
        self._running = False
        logger.info("Stopped health monitoring")


# Global health monitor instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get or create the global health monitor"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor


# Pre-built health checks for common components

async def check_data_service() -> tuple[HealthStatus, str]:
    """Health check for data service"""
    try:
        from services.data_service import get_data_service
        service = get_data_service()
        quote = service.get_quote("SPY", allow_fallback=True)
        if quote and quote.price > 0:
            return HealthStatus.HEALTHY, f"Data service OK (SPY: ${quote.price:.2f})"
        return HealthStatus.DEGRADED, "Data service returned invalid data"
    except Exception as e:
        return HealthStatus.UNHEALTHY, f"Data service error: {e!s}"


async def check_market_hours() -> tuple[HealthStatus, str]:
    """Health check for market hours service"""
    try:
        from services.market_hours import get_market_status
        status = get_market_status()
        if "session" in status:
            return HealthStatus.HEALTHY, f"Market hours OK (session: {status['session']})"
        return HealthStatus.DEGRADED, "Market hours returned incomplete data"
    except Exception as e:
        return HealthStatus.UNHEALTHY, f"Market hours error: {e!s}"


async def check_database() -> tuple[HealthStatus, str]:
    """Health check for database"""
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "..", "cache", "last_prices.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return HealthStatus.HEALTHY, "Database OK"
    except Exception as e:
        return HealthStatus.DEGRADED, f"Database warning: {e!s}"


async def check_brain_v6() -> tuple[HealthStatus, str]:
    """Health check for PropFirm Brain V6"""
    try:
        from brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()
        if brain:
            return HealthStatus.HEALTHY, "Brain V6 loaded"
        return HealthStatus.DEGRADED, "Brain V6 not initialized"
    except ImportError:
        return HealthStatus.DEGRADED, "Brain V6 not available"
    except Exception as e:
        return HealthStatus.UNHEALTHY, f"Brain V6 error: {e!s}"


def register_default_health_checks(monitor: HealthMonitor):
    """Register default health checks"""
    monitor.register_component("data_service", check_data_service)
    monitor.register_component("market_hours", check_market_hours)
    monitor.register_component("database", check_database)
    monitor.register_component("brain_v6", check_brain_v6)
