"""
QUANT_INDUSTRY_V1 Health Monitoring Service

Real-time system health monitoring:
- Component health checks
- Resource monitoring
- Alert generation
- Automated recovery

Rollback Plan: Delete this file
Tests Required: Health check accuracy, alert timing
Failure Modes: Graceful degradation, manual monitoring
"""

import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


# =============================================================================
# HEALTH TYPES
# =============================================================================

class HealthStatus(Enum):
    """Component health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """Result of a health check."""
    component: str
    status: HealthStatus
    message: str
    latency_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """System alert."""
    id: str
    severity: AlertSeverity
    component: str
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'severity': self.severity.value,
            'component': self.component,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged,
            'resolved': self.resolved,
            'metadata': self.metadata,
        }


@dataclass
class SystemMetrics:
    """Current system metrics."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    active_connections: int = 0
    requests_per_second: float = 0.0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    uptime_seconds: float = 0.0


# =============================================================================
# HEALTH CHECKS
# =============================================================================

class ComponentHealthChecker:
    """Base class for component health checkers."""

    def __init__(self, component_name: str):
        self.component_name = component_name

    def check(self) -> HealthCheck:
        """Perform health check. Override in subclasses."""
        return HealthCheck(
            component=self.component_name,
            status=HealthStatus.UNKNOWN,
            message="Not implemented",
            latency_ms=0
        )


class DatabaseHealthChecker(ComponentHealthChecker):
    """Check database health."""

    def __init__(self, db_path: str):
        super().__init__("database")
        self.db_path = db_path

    def check(self) -> HealthCheck:
        import sqlite3

        start = time.time()
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            latency = (time.time() - start) * 1000

            status = HealthStatus.HEALTHY
            if latency > 100:
                status = HealthStatus.DEGRADED

            return HealthCheck(
                component=self.component_name,
                status=status,
                message=f"Database responsive in {latency:.1f}ms",
                latency_ms=latency
            )

        except Exception as e:
            return HealthCheck(
                component=self.component_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                latency_ms=(time.time() - start) * 1000
            )


class BrokerHealthChecker(ComponentHealthChecker):
    """Check broker connectivity."""

    def __init__(self, broker):
        super().__init__("broker")
        self.broker = broker

    def check(self) -> HealthCheck:
        start = time.time()
        try:
            # Check if broker is connected
            if hasattr(self.broker, 'is_connected'):
                connected = self.broker.is_connected()
            else:
                connected = True  # Assume connected if no method

            latency = (time.time() - start) * 1000

            if connected:
                return HealthCheck(
                    component=self.component_name,
                    status=HealthStatus.HEALTHY,
                    message="Broker connected",
                    latency_ms=latency
                )
            else:
                return HealthCheck(
                    component=self.component_name,
                    status=HealthStatus.UNHEALTHY,
                    message="Broker disconnected",
                    latency_ms=latency
                )

        except Exception as e:
            return HealthCheck(
                component=self.component_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Broker error: {str(e)}",
                latency_ms=(time.time() - start) * 1000
            )


class ModelHealthChecker(ComponentHealthChecker):
    """Check ML model health."""

    def __init__(self, models: Dict[str, Any]):
        super().__init__("models")
        self.models = models

    def check(self) -> HealthCheck:
        start = time.time()
        try:
            healthy_models = 0
            total_models = len(self.models)

            for name, model in self.models.items():
                if hasattr(model, 'is_fitted') and model.is_fitted:
                    healthy_models += 1
                elif hasattr(model, 'predict'):
                    healthy_models += 1

            latency = (time.time() - start) * 1000

            if healthy_models == total_models:
                status = HealthStatus.HEALTHY
                message = f"All {total_models} models healthy"
            elif healthy_models > 0:
                status = HealthStatus.DEGRADED
                message = f"{healthy_models}/{total_models} models healthy"
            else:
                status = HealthStatus.UNHEALTHY
                message = "No models available"

            return HealthCheck(
                component=self.component_name,
                status=status,
                message=message,
                latency_ms=latency,
                metadata={'healthy': healthy_models, 'total': total_models}
            )

        except Exception as e:
            return HealthCheck(
                component=self.component_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Model check error: {str(e)}",
                latency_ms=(time.time() - start) * 1000
            )


# =============================================================================
# HEALTH MONITOR
# =============================================================================

class HealthMonitor:
    """
    Central health monitoring service.

    Continuously monitors system health and generates alerts.
    """

    def __init__(self, check_interval_seconds: int = 60):
        self.check_interval = check_interval_seconds
        self.checkers: List[ComponentHealthChecker] = []
        self.last_checks: Dict[str, HealthCheck] = {}
        self.alerts: List[Alert] = []
        self.alert_handlers: List[Callable[[Alert], None]] = []

        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._alert_count = 0

        # Start time for uptime calculation
        self._start_time = datetime.now(timezone.utc)

    def add_checker(self, checker: ComponentHealthChecker) -> None:
        """Add a health checker."""
        self.checkers.append(checker)

    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler callback."""
        self.alert_handlers.append(handler)

    def start(self) -> None:
        """Start the monitoring service."""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Health monitor started")

    def stop(self) -> None:
        """Stop the monitoring service."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Health monitor stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                self.run_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            time.sleep(self.check_interval)

    def run_checks(self) -> Dict[str, HealthCheck]:
        """Run all health checks."""
        results = {}

        for checker in self.checkers:
            try:
                result = checker.check()
                results[checker.component_name] = result
                self.last_checks[checker.component_name] = result

                # Check for alerts
                self._evaluate_for_alerts(result)

            except Exception as e:
                logger.error(f"Check failed for {checker.component_name}: {e}")
                results[checker.component_name] = HealthCheck(
                    component=checker.component_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(e)}",
                    latency_ms=0
                )

        return results

    def _evaluate_for_alerts(self, check: HealthCheck) -> None:
        """Evaluate health check for alert conditions."""
        # Alert on unhealthy status
        if check.status == HealthStatus.UNHEALTHY:
            self._create_alert(
                severity=AlertSeverity.ERROR,
                component=check.component,
                title=f"{check.component} Unhealthy",
                message=check.message
            )
        elif check.status == HealthStatus.DEGRADED:
            self._create_alert(
                severity=AlertSeverity.WARNING,
                component=check.component,
                title=f"{check.component} Degraded",
                message=check.message
            )

    def _create_alert(
        self,
        severity: AlertSeverity,
        component: str,
        title: str,
        message: str
    ) -> Alert:
        """Create and dispatch an alert."""
        self._alert_count += 1
        alert = Alert(
            id=f"ALERT-{self._alert_count:06d}",
            severity=severity,
            component=component,
            title=title,
            message=message
        )

        self.alerts.append(alert)

        # Dispatch to handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

        return alert

    def get_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        statuses = [c.status for c in self.last_checks.values()]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.UNKNOWN

        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return {
            'status': overall.value,
            'uptime_seconds': uptime,
            'components': {
                name: {
                    'status': check.status.value,
                    'message': check.message,
                    'latency_ms': check.latency_ms,
                    'last_check': check.timestamp.isoformat()
                }
                for name, check in self.last_checks.items()
            },
            'active_alerts': len([a for a in self.alerts if not a.resolved]),
            'total_alerts': len(self.alerts)
        }

    def get_active_alerts(self) -> List[Alert]:
        """Get unresolved alerts."""
        return [a for a in self.alerts if not a.resolved]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                return True
        return False


# =============================================================================
# DASHBOARD SERVICE
# =============================================================================

class DashboardService:
    """
    Dashboard data aggregation service.

    Aggregates data for display in UI/dashboard.
    """

    def __init__(
        self,
        health_monitor: HealthMonitor = None,
        grading_engine = None,
        risk_engine = None
    ):
        self.health_monitor = health_monitor
        self.grading_engine = grading_engine
        self.risk_engine = risk_engine

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all dashboard data."""
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'health': {},
            'performance': {},
            'risk': {},
            'alerts': [],
        }

        # Health data
        if self.health_monitor:
            data['health'] = self.health_monitor.get_status()
            data['alerts'] = [
                a.to_dict()
                for a in self.health_monitor.get_active_alerts()
            ]

        # Performance/grading data
        if self.grading_engine and self.grading_engine.grade_history:
            latest_report = self.grading_engine.grade_history[-1]
            data['performance'] = {
                'overall_score': latest_report.overall_score,
                'overall_grade': latest_report.overall_grade.value,
                'trend': latest_report.trend,
                'benchmark_comparison': latest_report.comparison_to_benchmark,
                'top_remediations': [
                    r.to_dict() for r in latest_report.remediations[:3]
                ],
            }

        # Risk data
        if self.risk_engine:
            data['risk'] = {
                'portfolio_value': getattr(self.risk_engine, 'portfolio_value', 0),
                'daily_pnl': getattr(self.risk_engine, 'daily_pnl', 0),
                'current_drawdown': getattr(self.risk_engine, 'current_drawdown', 0),
                'risk_utilization': getattr(self.risk_engine, 'risk_utilization', 0),
            }

        return data

    def get_historical_metrics(
        self,
        metric: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get historical metric values for charting."""
        # This would pull from database in production
        history = []

        if self.grading_engine:
            for report in self.grading_engine.grade_history[-days:]:
                if metric == 'overall_score':
                    history.append({
                        'timestamp': report.generated_at.isoformat(),
                        'value': report.overall_score
                    })
                elif metric in report.dimension_grades:
                    history.append({
                        'timestamp': report.generated_at.isoformat(),
                        'value': report.dimension_grades[metric].score
                    })

        return history
