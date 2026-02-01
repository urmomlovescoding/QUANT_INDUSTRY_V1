"""
Predictive Maintenance - System Health Prediction and Monitoring

This module provides predictive maintenance capabilities for the
trading system, detecting issues before they cause problems.

Key Features:
- Model drift detection
- Latency trend prediction
- Data quality monitoring
- Memory pressure prediction
- Component health scoring

Usage:
    from monitoring.maintenance_predictor import MaintenancePredictor

    predictor = MaintenancePredictor()
    predictor.record_metrics(latency=50, memory=70, model_accuracy=0.95)
    alerts = predictor.get_maintenance_alerts()
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Types of system components."""
    MODEL = "model"
    DATA_PIPELINE = "data_pipeline"
    EXECUTION = "execution"
    DATABASE = "database"
    NETWORK = "network"
    MEMORY = "memory"


class AlertPriority(Enum):
    """Maintenance alert priority."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MaintenanceAlert:
    """Maintenance alert."""
    timestamp: datetime
    component: ComponentType
    priority: AlertPriority
    message: str
    metric_name: str
    current_value: float
    threshold: float
    predicted_issue_time: Optional[datetime] = None
    recommended_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'component': self.component.value,
            'priority': self.priority.value,
            'message': self.message,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'predicted_issue_time': self.predicted_issue_time.isoformat() if self.predicted_issue_time else None,
            'recommended_action': self.recommended_action,
        }


@dataclass
class ComponentHealth:
    """Health status of a component."""
    component: ComponentType
    health_score: float  # 0-100
    status: str  # 'healthy', 'degraded', 'unhealthy'
    metrics: Dict[str, float]
    trend: str  # 'improving', 'stable', 'degrading'
    last_updated: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'component': self.component.value,
            'health_score': self.health_score,
            'status': self.status,
            'metrics': self.metrics,
            'trend': self.trend,
            'last_updated': self.last_updated.isoformat(),
        }


@dataclass
class MaintenanceConfig:
    """Configuration for maintenance predictor."""
    history_window: int = 1000
    prediction_horizon_minutes: int = 60
    latency_warning_ms: float = 100
    latency_critical_ms: float = 500
    memory_warning_percent: float = 75
    memory_critical_percent: float = 90
    drift_warning_threshold: float = 0.05
    drift_critical_threshold: float = 0.10
    data_quality_threshold: float = 0.95
    alert_cooldown_seconds: int = 300


class MaintenancePredictor:
    """
    Predictive maintenance system for trading infrastructure.

    Monitors system health, predicts issues, and generates
    maintenance alerts before problems occur.

    Example:
        predictor = MaintenancePredictor()

        # Record metrics
        predictor.record_latency('execution', 45.0)
        predictor.record_memory_usage(68.5)
        predictor.record_model_accuracy('momentum_model', 0.92)

        # Check for alerts
        alerts = predictor.get_maintenance_alerts()
        for alert in alerts:
            print(f"{alert.priority}: {alert.message}")
    """

    def __init__(self, config: Optional[MaintenanceConfig] = None):
        self.config = config or MaintenanceConfig()

        # Metric history
        self._latency_history: Dict[str, deque] = {}
        self._memory_history: deque = deque(maxlen=self.config.history_window)
        self._model_accuracy_history: Dict[str, deque] = {}
        self._data_quality_history: deque = deque(maxlen=self.config.history_window)
        self._error_history: deque = deque(maxlen=self.config.history_window)

        # Alert tracking
        self._active_alerts: List[MaintenanceAlert] = []
        self._alert_cooldowns: Dict[str, datetime] = {}

        # Component health
        self._component_health: Dict[ComponentType, ComponentHealth] = {}

        logger.info("MaintenancePredictor initialized")

    def record_latency(
        self,
        component: str,
        latency_ms: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record latency measurement."""
        timestamp = timestamp or datetime.now(timezone.utc)

        if component not in self._latency_history:
            self._latency_history[component] = deque(maxlen=self.config.history_window)

        self._latency_history[component].append({
            'timestamp': timestamp,
            'value': latency_ms,
        })

    def record_memory_usage(
        self,
        usage_percent: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record memory usage."""
        timestamp = timestamp or datetime.now(timezone.utc)

        self._memory_history.append({
            'timestamp': timestamp,
            'value': usage_percent,
        })

    def record_model_accuracy(
        self,
        model_name: str,
        accuracy: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record model accuracy for drift detection."""
        timestamp = timestamp or datetime.now(timezone.utc)

        if model_name not in self._model_accuracy_history:
            self._model_accuracy_history[model_name] = deque(maxlen=self.config.history_window)

        self._model_accuracy_history[model_name].append({
            'timestamp': timestamp,
            'value': accuracy,
        })

    def record_data_quality(
        self,
        quality_score: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record data quality score."""
        timestamp = timestamp or datetime.now(timezone.utc)

        self._data_quality_history.append({
            'timestamp': timestamp,
            'value': quality_score,
        })

    def record_error(
        self,
        component: str,
        error_type: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record an error occurrence."""
        timestamp = timestamp or datetime.now(timezone.utc)

        self._error_history.append({
            'timestamp': timestamp,
            'component': component,
            'error_type': error_type,
        })

    def get_maintenance_alerts(self) -> List[MaintenanceAlert]:
        """
        Get current maintenance alerts.

        Returns:
            List of active maintenance alerts
        """
        alerts = []

        # Check latency
        alerts.extend(self._check_latency_alerts())

        # Check memory
        alerts.extend(self._check_memory_alerts())

        # Check model drift
        alerts.extend(self._check_model_drift_alerts())

        # Check data quality
        alerts.extend(self._check_data_quality_alerts())

        # Check error rate
        alerts.extend(self._check_error_rate_alerts())

        # Filter by cooldown
        alerts = self._filter_by_cooldown(alerts)

        self._active_alerts = alerts
        return alerts

    def _check_latency_alerts(self) -> List[MaintenanceAlert]:
        """Check for latency-related alerts."""
        alerts = []

        for component, history in self._latency_history.items():
            if len(history) < 10:
                continue

            recent = [h['value'] for h in list(history)[-50:]]
            current = recent[-1]
            avg = np.mean(recent)
            trend = self._compute_trend(recent)

            # Current threshold breach
            if current >= self.config.latency_critical_ms:
                alerts.append(MaintenanceAlert(
                    timestamp=datetime.now(timezone.utc),
                    component=ComponentType.EXECUTION,
                    priority=AlertPriority.CRITICAL,
                    message=f"{component} latency critical: {current:.1f}ms",
                    metric_name=f"latency_{component}",
                    current_value=current,
                    threshold=self.config.latency_critical_ms,
                    recommended_action="Check connection pool and network",
                ))
            elif current >= self.config.latency_warning_ms:
                alerts.append(MaintenanceAlert(
                    timestamp=datetime.now(timezone.utc),
                    component=ComponentType.EXECUTION,
                    priority=AlertPriority.MEDIUM,
                    message=f"{component} latency elevated: {current:.1f}ms",
                    metric_name=f"latency_{component}",
                    current_value=current,
                    threshold=self.config.latency_warning_ms,
                ))

            # Predict future breach
            if trend > 0:
                predicted_time = self._predict_threshold_breach(
                    recent,
                    self.config.latency_warning_ms,
                )
                if predicted_time:
                    alerts.append(MaintenanceAlert(
                        timestamp=datetime.now(timezone.utc),
                        component=ComponentType.EXECUTION,
                        priority=AlertPriority.LOW,
                        message=f"{component} latency trending up",
                        metric_name=f"latency_{component}",
                        current_value=current,
                        threshold=self.config.latency_warning_ms,
                        predicted_issue_time=predicted_time,
                        recommended_action="Monitor and prepare for scaling",
                    ))

        return alerts

    def _check_memory_alerts(self) -> List[MaintenanceAlert]:
        """Check for memory-related alerts."""
        alerts = []

        if len(self._memory_history) < 10:
            return alerts

        recent = [h['value'] for h in list(self._memory_history)[-50:]]
        current = recent[-1]
        trend = self._compute_trend(recent)

        if current >= self.config.memory_critical_percent:
            alerts.append(MaintenanceAlert(
                timestamp=datetime.now(timezone.utc),
                component=ComponentType.MEMORY,
                priority=AlertPriority.CRITICAL,
                message=f"Memory critical: {current:.1f}%",
                metric_name="memory_usage",
                current_value=current,
                threshold=self.config.memory_critical_percent,
                recommended_action="Restart service or increase memory",
            ))
        elif current >= self.config.memory_warning_percent:
            alerts.append(MaintenanceAlert(
                timestamp=datetime.now(timezone.utc),
                component=ComponentType.MEMORY,
                priority=AlertPriority.HIGH,
                message=f"Memory elevated: {current:.1f}%",
                metric_name="memory_usage",
                current_value=current,
                threshold=self.config.memory_warning_percent,
            ))

        # Predict memory exhaustion
        if trend > 0 and current > 50:
            predicted_time = self._predict_threshold_breach(
                recent,
                self.config.memory_critical_percent,
            )
            if predicted_time:
                alerts.append(MaintenanceAlert(
                    timestamp=datetime.now(timezone.utc),
                    component=ComponentType.MEMORY,
                    priority=AlertPriority.MEDIUM,
                    message="Memory pressure increasing",
                    metric_name="memory_usage",
                    current_value=current,
                    threshold=self.config.memory_critical_percent,
                    predicted_issue_time=predicted_time,
                    recommended_action="Clear caches or prepare for restart",
                ))

        return alerts

    def _check_model_drift_alerts(self) -> List[MaintenanceAlert]:
        """Check for model drift."""
        alerts = []

        for model_name, history in self._model_accuracy_history.items():
            if len(history) < 20:
                continue

            values = [h['value'] for h in history]
            recent = values[-20:]
            baseline = values[:min(100, len(values) - 20)]

            if not baseline:
                continue

            # Compute drift
            baseline_mean = np.mean(baseline)
            recent_mean = np.mean(recent)
            drift = baseline_mean - recent_mean

            if drift >= self.config.drift_critical_threshold:
                alerts.append(MaintenanceAlert(
                    timestamp=datetime.now(timezone.utc),
                    component=ComponentType.MODEL,
                    priority=AlertPriority.CRITICAL,
                    message=f"Model {model_name} critical drift: {drift:.2%}",
                    metric_name=f"drift_{model_name}",
                    current_value=drift,
                    threshold=self.config.drift_critical_threshold,
                    recommended_action="Retrain model immediately",
                ))
            elif drift >= self.config.drift_warning_threshold:
                alerts.append(MaintenanceAlert(
                    timestamp=datetime.now(timezone.utc),
                    component=ComponentType.MODEL,
                    priority=AlertPriority.MEDIUM,
                    message=f"Model {model_name} drifting: {drift:.2%}",
                    metric_name=f"drift_{model_name}",
                    current_value=drift,
                    threshold=self.config.drift_warning_threshold,
                    recommended_action="Schedule model retraining",
                ))

        return alerts

    def _check_data_quality_alerts(self) -> List[MaintenanceAlert]:
        """Check data quality issues."""
        alerts = []

        if len(self._data_quality_history) < 5:
            return alerts

        recent = [h['value'] for h in list(self._data_quality_history)[-20:]]
        current = recent[-1]
        avg = np.mean(recent)

        if current < self.config.data_quality_threshold:
            alerts.append(MaintenanceAlert(
                timestamp=datetime.now(timezone.utc),
                component=ComponentType.DATA_PIPELINE,
                priority=AlertPriority.HIGH,
                message=f"Data quality degraded: {current:.2%}",
                metric_name="data_quality",
                current_value=current,
                threshold=self.config.data_quality_threshold,
                recommended_action="Check data sources and validation rules",
            ))

        if avg < self.config.data_quality_threshold:
            alerts.append(MaintenanceAlert(
                timestamp=datetime.now(timezone.utc),
                component=ComponentType.DATA_PIPELINE,
                priority=AlertPriority.MEDIUM,
                message=f"Persistent data quality issues: avg {avg:.2%}",
                metric_name="data_quality_avg",
                current_value=avg,
                threshold=self.config.data_quality_threshold,
            ))

        return alerts

    def _check_error_rate_alerts(self) -> List[MaintenanceAlert]:
        """Check error rate trends."""
        alerts = []

        if len(self._error_history) < 5:
            return alerts

        # Count errors in last hour
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        recent_errors = [
            e for e in self._error_history
            if e['timestamp'] > hour_ago
        ]

        if len(recent_errors) >= 10:
            # Group by component
            error_counts = {}
            for e in recent_errors:
                comp = e['component']
                error_counts[comp] = error_counts.get(comp, 0) + 1

            for comp, count in error_counts.items():
                if count >= 5:
                    alerts.append(MaintenanceAlert(
                        timestamp=now,
                        component=ComponentType.DATA_PIPELINE,
                        priority=AlertPriority.HIGH,
                        message=f"High error rate in {comp}: {count} errors/hour",
                        metric_name=f"error_rate_{comp}",
                        current_value=count,
                        threshold=5,
                        recommended_action=f"Investigate {comp} errors",
                    ))

        return alerts

    def _compute_trend(self, values: List[float]) -> float:
        """Compute trend (positive = increasing, negative = decreasing)."""
        if len(values) < 3:
            return 0.0

        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)
        return slope

    def _predict_threshold_breach(
        self,
        values: List[float],
        threshold: float,
    ) -> Optional[datetime]:
        """
        Predict when a metric will breach a threshold.

        Returns None if not predicted within horizon.
        """
        if len(values) < 10:
            return None

        current = values[-1]
        if current >= threshold:
            return None  # Already breached

        trend = self._compute_trend(values)
        if trend <= 0:
            return None  # Not increasing

        # Simple linear extrapolation
        time_to_breach = (threshold - current) / trend

        if time_to_breach > self.config.prediction_horizon_minutes:
            return None

        return datetime.now(timezone.utc) + timedelta(minutes=time_to_breach)

    def _filter_by_cooldown(
        self,
        alerts: List[MaintenanceAlert],
    ) -> List[MaintenanceAlert]:
        """Filter alerts by cooldown period."""
        filtered = []
        now = datetime.now(timezone.utc)

        for alert in alerts:
            alert_key = f"{alert.component.value}:{alert.metric_name}"

            last_alert = self._alert_cooldowns.get(alert_key)
            if last_alert:
                elapsed = (now - last_alert).total_seconds()
                if elapsed < self.config.alert_cooldown_seconds:
                    continue

            filtered.append(alert)
            self._alert_cooldowns[alert_key] = now

        return filtered

    def get_component_health(self) -> Dict[str, ComponentHealth]:
        """
        Get health status of all components.

        Returns:
            Dictionary of component name to health status
        """
        health = {}

        # Execution health
        exec_health = self._compute_execution_health()
        health['execution'] = exec_health

        # Memory health
        mem_health = self._compute_memory_health()
        health['memory'] = mem_health

        # Model health
        model_health = self._compute_model_health()
        health['model'] = model_health

        # Data pipeline health
        data_health = self._compute_data_health()
        health['data_pipeline'] = data_health

        return health

    def _compute_execution_health(self) -> ComponentHealth:
        """Compute execution component health."""
        metrics = {}
        scores = []

        for component, history in self._latency_history.items():
            if len(history) >= 5:
                recent = [h['value'] for h in list(history)[-20:]]
                avg = np.mean(recent)
                metrics[f'{component}_latency'] = avg

                # Score: 100 if < warning, 0 if > critical
                score = max(0, min(100, 100 * (
                    self.config.latency_critical_ms - avg
                ) / (
                    self.config.latency_critical_ms - self.config.latency_warning_ms
                )))
                scores.append(score)

        health_score = np.mean(scores) if scores else 100
        trend = 'stable'

        return ComponentHealth(
            component=ComponentType.EXECUTION,
            health_score=health_score,
            status='healthy' if health_score >= 70 else 'degraded' if health_score >= 40 else 'unhealthy',
            metrics=metrics,
            trend=trend,
            last_updated=datetime.now(timezone.utc),
        )

    def _compute_memory_health(self) -> ComponentHealth:
        """Compute memory health."""
        if len(self._memory_history) < 5:
            return ComponentHealth(
                component=ComponentType.MEMORY,
                health_score=100,
                status='healthy',
                metrics={},
                trend='stable',
                last_updated=datetime.now(timezone.utc),
            )

        recent = [h['value'] for h in list(self._memory_history)[-20:]]
        current = recent[-1]
        trend_value = self._compute_trend(recent)

        health_score = max(0, min(100, 100 - current))

        return ComponentHealth(
            component=ComponentType.MEMORY,
            health_score=health_score,
            status='healthy' if current < 70 else 'degraded' if current < 85 else 'unhealthy',
            metrics={'usage_percent': current},
            trend='degrading' if trend_value > 0.5 else 'improving' if trend_value < -0.5 else 'stable',
            last_updated=datetime.now(timezone.utc),
        )

    def _compute_model_health(self) -> ComponentHealth:
        """Compute model health."""
        metrics = {}
        scores = []

        for model, history in self._model_accuracy_history.items():
            if len(history) >= 10:
                recent = [h['value'] for h in list(history)[-20:]]
                avg = np.mean(recent)
                metrics[f'{model}_accuracy'] = avg
                scores.append(avg * 100)

        health_score = np.mean(scores) if scores else 100

        return ComponentHealth(
            component=ComponentType.MODEL,
            health_score=health_score,
            status='healthy' if health_score >= 80 else 'degraded' if health_score >= 60 else 'unhealthy',
            metrics=metrics,
            trend='stable',
            last_updated=datetime.now(timezone.utc),
        )

    def _compute_data_health(self) -> ComponentHealth:
        """Compute data pipeline health."""
        if len(self._data_quality_history) < 5:
            return ComponentHealth(
                component=ComponentType.DATA_PIPELINE,
                health_score=100,
                status='healthy',
                metrics={},
                trend='stable',
                last_updated=datetime.now(timezone.utc),
            )

        recent = [h['value'] for h in list(self._data_quality_history)[-20:]]
        avg = np.mean(recent)

        return ComponentHealth(
            component=ComponentType.DATA_PIPELINE,
            health_score=avg * 100,
            status='healthy' if avg >= 0.95 else 'degraded' if avg >= 0.85 else 'unhealthy',
            metrics={'quality_score': avg},
            trend='stable',
            last_updated=datetime.now(timezone.utc),
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get predictor statistics."""
        return {
            'latency_components_tracked': len(self._latency_history),
            'memory_samples': len(self._memory_history),
            'models_tracked': len(self._model_accuracy_history),
            'data_quality_samples': len(self._data_quality_history),
            'active_alerts': len(self._active_alerts),
            'total_errors_recorded': len(self._error_history),
        }
