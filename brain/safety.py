"""
QUANT_INDUSTRY_V1 Safety, Stability & Self-Diagnostics

System safety and monitoring:
- Model drift detection
- Anomaly detection
- Circuit breakers
- Health monitoring
- Self-diagnostic capabilities
- Graceful degradation

Rollback Plan: Delete this file
Tests Required: Drift detection accuracy, circuit breaker triggers
Failure Modes: Halt trading, alert operators
"""

import numpy as np
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# HEALTH STATUS
# =============================================================================

class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Result of a health check."""
    component: str
    status: HealthStatus
    message: str
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    components: Dict[str, HealthCheck]
    uptime_seconds: float
    last_check: datetime
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status.value,
            'components': {
                name: {
                    'status': check.status.value,
                    'message': check.message,
                    'metrics': check.metrics,
                    'timestamp': check.timestamp.isoformat(),
                    'latency_ms': check.latency_ms,
                }
                for name, check in self.components.items()
            },
            'uptime_seconds': self.uptime_seconds,
            'last_check': self.last_check.isoformat(),
            'alerts': self.alerts,
        }


# =============================================================================
# DRIFT DETECTION
# =============================================================================

class DriftType(Enum):
    """Types of drift."""
    DATA_DRIFT = "data_drift"  # Input distribution change
    CONCEPT_DRIFT = "concept_drift"  # Relationship change
    PREDICTION_DRIFT = "prediction_drift"  # Output distribution change
    PERFORMANCE_DRIFT = "performance_drift"  # Model degradation


@dataclass
class DriftResult:
    """Result of drift detection."""
    drift_type: DriftType
    is_drift_detected: bool
    drift_score: float  # 0-1, higher = more drift
    p_value: float
    threshold: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DriftDetector:
    """
    Detect various types of drift in data and model performance.
    """

    def __init__(
        self,
        reference_data: np.ndarray = None,
        window_size: int = 100,
        drift_threshold: float = 0.05
    ):
        self.reference_data = reference_data
        self.window_size = window_size
        self.drift_threshold = drift_threshold

        # Sliding windows
        self.feature_window: deque = deque(maxlen=window_size)
        self.prediction_window: deque = deque(maxlen=window_size)
        self.performance_window: deque = deque(maxlen=window_size)

        # Reference statistics
        if reference_data is not None:
            self._compute_reference_stats()
        else:
            self.reference_mean = None
            self.reference_std = None

    def _compute_reference_stats(self) -> None:
        """Compute reference statistics."""
        self.reference_mean = np.mean(self.reference_data, axis=0)
        self.reference_std = np.std(self.reference_data, axis=0) + 1e-8

    def update(
        self,
        features: np.ndarray = None,
        prediction: float = None,
        actual: float = None
    ) -> None:
        """Update windows with new observation."""
        if features is not None:
            self.feature_window.append(features)
        if prediction is not None:
            self.prediction_window.append(prediction)
        if actual is not None and prediction is not None:
            error = abs(prediction - actual)
            self.performance_window.append(error)

    def detect_data_drift(self) -> DriftResult:
        """
        Detect data drift using KS test.

        Compares current feature distribution to reference.
        """
        if self.reference_data is None or len(self.feature_window) < 30:
            return DriftResult(
                drift_type=DriftType.DATA_DRIFT,
                is_drift_detected=False,
                drift_score=0.0,
                p_value=1.0,
                threshold=self.drift_threshold,
                details={'reason': 'Insufficient data'},
            )

        current_data = np.array(list(self.feature_window))

        # KS test for each feature
        drift_scores = []
        p_values = []

        for i in range(current_data.shape[1]):
            # Simple KS statistic approximation
            ref_sorted = np.sort(self.reference_data[:, i])
            cur_sorted = np.sort(current_data[:, i])

            # Interpolate to same length
            n = min(len(ref_sorted), len(cur_sorted))
            ref_quantiles = np.interp(
                np.linspace(0, 1, n),
                np.linspace(0, 1, len(ref_sorted)),
                ref_sorted
            )
            cur_quantiles = np.interp(
                np.linspace(0, 1, n),
                np.linspace(0, 1, len(cur_sorted)),
                cur_sorted
            )

            # KS statistic
            ks_stat = np.max(np.abs(ref_quantiles - cur_quantiles)) / (np.std(ref_sorted) + 1e-8)
            drift_scores.append(ks_stat)

            # Approximate p-value
            p_value = np.exp(-2 * n * ks_stat ** 2) if ks_stat > 0 else 1.0
            p_values.append(p_value)

        overall_drift = float(np.mean(drift_scores))
        overall_p = float(np.min(p_values))  # Bonferroni-like correction

        return DriftResult(
            drift_type=DriftType.DATA_DRIFT,
            is_drift_detected=overall_p < self.drift_threshold,
            drift_score=overall_drift,
            p_value=overall_p,
            threshold=self.drift_threshold,
            details={
                'feature_drift_scores': drift_scores,
                'feature_p_values': p_values,
            },
        )

    def detect_prediction_drift(self) -> DriftResult:
        """
        Detect drift in model predictions.

        Uses Page-Hinkley test for change detection.
        """
        if len(self.prediction_window) < 30:
            return DriftResult(
                drift_type=DriftType.PREDICTION_DRIFT,
                is_drift_detected=False,
                drift_score=0.0,
                p_value=1.0,
                threshold=self.drift_threshold,
            )

        predictions = np.array(list(self.prediction_window))

        # Split into two halves
        mid = len(predictions) // 2
        first_half = predictions[:mid]
        second_half = predictions[mid:]

        # Compare distributions
        mean_diff = abs(np.mean(second_half) - np.mean(first_half))
        std_pooled = np.sqrt((np.var(first_half) + np.var(second_half)) / 2) + 1e-8

        # Effect size (Cohen's d)
        drift_score = mean_diff / std_pooled

        # Approximate p-value using t-test approximation
        n = len(first_half)
        t_stat = mean_diff / (std_pooled * np.sqrt(2 / n))
        p_value = 2 * (1 - self._norm_cdf(abs(t_stat)))

        return DriftResult(
            drift_type=DriftType.PREDICTION_DRIFT,
            is_drift_detected=p_value < self.drift_threshold,
            drift_score=float(drift_score),
            p_value=float(p_value),
            threshold=self.drift_threshold,
            details={
                'mean_first_half': float(np.mean(first_half)),
                'mean_second_half': float(np.mean(second_half)),
                'std_first_half': float(np.std(first_half)),
                'std_second_half': float(np.std(second_half)),
            },
        )

    def detect_performance_drift(
        self,
        reference_error: float = None
    ) -> DriftResult:
        """
        Detect degradation in model performance.
        """
        if len(self.performance_window) < 30:
            return DriftResult(
                drift_type=DriftType.PERFORMANCE_DRIFT,
                is_drift_detected=False,
                drift_score=0.0,
                p_value=1.0,
                threshold=self.drift_threshold,
            )

        errors = np.array(list(self.performance_window))
        current_error = np.mean(errors)

        if reference_error is None:
            reference_error = np.median(errors)

        # Check if error increased significantly
        drift_score = (current_error - reference_error) / (reference_error + 1e-8)

        # One-sided test (we care about degradation)
        std_error = np.std(errors) / np.sqrt(len(errors))
        z_stat = (current_error - reference_error) / (std_error + 1e-8)
        p_value = 1 - self._norm_cdf(z_stat)

        return DriftResult(
            drift_type=DriftType.PERFORMANCE_DRIFT,
            is_drift_detected=p_value < self.drift_threshold,
            drift_score=float(drift_score),
            p_value=float(p_value),
            threshold=self.drift_threshold,
            details={
                'current_error': float(current_error),
                'reference_error': float(reference_error),
                'error_std': float(np.std(errors)),
            },
        )

    def _norm_cdf(self, x: float) -> float:
        """Standard normal CDF approximation."""
        return 0.5 * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x ** 3)))


# =============================================================================
# ANOMALY DETECTION
# =============================================================================

class AnomalyDetector:
    """
    Detect anomalies in inputs and outputs.
    """

    def __init__(
        self,
        n_features: int,
        window_size: int = 100,
        z_threshold: float = 3.0
    ):
        self.n_features = n_features
        self.window_size = window_size
        self.z_threshold = z_threshold

        # Running statistics
        self.feature_windows: List[deque] = [
            deque(maxlen=window_size) for _ in range(n_features)
        ]

        self.anomaly_count = 0
        self.total_count = 0

    def check(self, features: np.ndarray) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if input is anomalous.

        Args:
            features: Input feature vector

        Returns:
            Tuple of (is_anomaly, details)
        """
        self.total_count += 1

        if features.ndim == 1:
            features = features.reshape(1, -1)

        anomalous_features = []
        z_scores = []

        for i in range(min(self.n_features, features.shape[1])):
            value = features[0, i]
            self.feature_windows[i].append(value)

            if len(self.feature_windows[i]) < 10:
                z_scores.append(0.0)
                continue

            window = np.array(self.feature_windows[i])
            mean = np.mean(window)
            std = np.std(window) + 1e-8

            z = abs(value - mean) / std
            z_scores.append(z)

            if z > self.z_threshold:
                anomalous_features.append(i)

        is_anomaly = len(anomalous_features) > 0

        if is_anomaly:
            self.anomaly_count += 1

        return is_anomaly, {
            'anomalous_features': anomalous_features,
            'z_scores': z_scores,
            'max_z_score': max(z_scores) if z_scores else 0.0,
            'anomaly_rate': self.anomaly_count / self.total_count if self.total_count > 0 else 0.0,
        }

    def isolation_forest_score(self, features: np.ndarray) -> float:
        """
        Simplified isolation forest-like anomaly score.

        Higher score = more anomalous.
        """
        if features.ndim == 1:
            features = features.reshape(1, -1)

        # Use average depth in random binary trees (approximation)
        scores = []

        for i in range(features.shape[1]):
            if len(self.feature_windows[i]) < 10:
                continue

            window = np.array(self.feature_windows[i])
            value = features[0, i]

            # How many standard deviations from median?
            median = np.median(window)
            mad = np.median(np.abs(window - median)) + 1e-8
            score = abs(value - median) / mad

            scores.append(score)

        return float(np.mean(scores)) if scores else 0.0


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 60.0
    half_open_max_calls: int = 3


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.

    Prevents cascading failures by stopping calls to failing services.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0

        self._lock = threading.Lock()
        self.state_history: List[Tuple[datetime, CircuitState]] = []

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self.last_failure_time:
                    elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        self._transition_to(CircuitState.HALF_OPEN)
                        return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return self.half_open_calls < self.config.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Record successful execution."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                self.half_open_calls += 1

                if self.success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)

            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state."""
        old_state = self.state
        self.state = new_state

        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0

        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0
            self.half_open_calls = 0

        elif new_state == CircuitState.OPEN:
            self.success_count = 0
            self.half_open_calls = 0

        self.state_history.append((datetime.now(timezone.utc), new_state))
        logger.info(f"Circuit breaker '{self.name}': {old_state.value} -> {new_state.value}")

    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


# =============================================================================
# SELF-DIAGNOSTICS
# =============================================================================

class SelfDiagnostics:
    """
    System self-diagnostic capabilities.
    """

    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.checks: Dict[str, Callable[[], HealthCheck]] = {}
        self.last_results: Dict[str, HealthCheck] = {}

        # Register default checks
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self.register_check('memory', self._check_memory)
        self.register_check('cpu', self._check_cpu)
        self.register_check('disk', self._check_disk)

    def register_check(
        self,
        name: str,
        check_func: Callable[[], HealthCheck]
    ) -> None:
        """Register a health check."""
        self.checks[name] = check_func

    def run_all_checks(self) -> SystemHealth:
        """Run all health checks."""
        results = {}
        alerts = []

        for name, check_func in self.checks.items():
            try:
                start = time.time()
                result = check_func()
                result.latency_ms = (time.time() - start) * 1000
                results[name] = result
                self.last_results[name] = result

                if result.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]:
                    alerts.append(f"{name}: {result.message}")

            except Exception as e:
                results[name] = HealthCheck(
                    component=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(e)}",
                )
                alerts.append(f"{name}: Check failed")

        # Determine overall status
        statuses = [r.status for r in results.values()]

        if HealthStatus.CRITICAL in statuses:
            overall = HealthStatus.CRITICAL
        elif HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        elif HealthStatus.UNKNOWN in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        return SystemHealth(
            status=overall,
            components=results,
            uptime_seconds=uptime,
            last_check=datetime.now(timezone.utc),
            alerts=alerts,
        )

    def _check_memory(self) -> HealthCheck:
        """Check memory usage."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            percent = memory.percent

            if percent > 95:
                status = HealthStatus.CRITICAL
                message = f"Memory critically high: {percent}%"
            elif percent > 85:
                status = HealthStatus.UNHEALTHY
                message = f"Memory high: {percent}%"
            elif percent > 70:
                status = HealthStatus.DEGRADED
                message = f"Memory elevated: {percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory OK: {percent}%"

            return HealthCheck(
                component='memory',
                status=status,
                message=message,
                metrics={
                    'percent': percent,
                    'available_gb': memory.available / (1024 ** 3),
                },
            )

        except ImportError:
            return HealthCheck(
                component='memory',
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
            )

    def _check_cpu(self) -> HealthCheck:
        """Check CPU usage."""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)

            if cpu_percent > 95:
                status = HealthStatus.CRITICAL
                message = f"CPU critically high: {cpu_percent}%"
            elif cpu_percent > 85:
                status = HealthStatus.UNHEALTHY
                message = f"CPU high: {cpu_percent}%"
            elif cpu_percent > 70:
                status = HealthStatus.DEGRADED
                message = f"CPU elevated: {cpu_percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU OK: {cpu_percent}%"

            return HealthCheck(
                component='cpu',
                status=status,
                message=message,
                metrics={'percent': cpu_percent},
            )

        except ImportError:
            return HealthCheck(
                component='cpu',
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
            )

    def _check_disk(self) -> HealthCheck:
        """Check disk usage."""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            percent = disk.percent

            if percent > 95:
                status = HealthStatus.CRITICAL
                message = f"Disk critically full: {percent}%"
            elif percent > 85:
                status = HealthStatus.UNHEALTHY
                message = f"Disk nearly full: {percent}%"
            elif percent > 70:
                status = HealthStatus.DEGRADED
                message = f"Disk usage elevated: {percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk OK: {percent}%"

            return HealthCheck(
                component='disk',
                status=status,
                message=message,
                metrics={
                    'percent': percent,
                    'free_gb': disk.free / (1024 ** 3),
                },
            )

        except ImportError:
            return HealthCheck(
                component='disk',
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
            )


# =============================================================================
# GRACEFUL DEGRADATION
# =============================================================================

class DegradationLevel(Enum):
    """Levels of system degradation."""
    FULL = "full"  # All features available
    REDUCED = "reduced"  # Some features disabled
    MINIMAL = "minimal"  # Essential features only
    EMERGENCY = "emergency"  # Emergency mode


class GracefulDegradation:
    """
    Manage graceful degradation of system capabilities.
    """

    def __init__(self):
        self.level = DegradationLevel.FULL
        self.disabled_features: set = set()
        self.degradation_history: List[Tuple[datetime, DegradationLevel, str]] = []

        # Feature priorities (lower = more essential)
        self.feature_priorities = {
            'advanced_ml': 4,
            'rl_agent': 4,
            'backtesting': 3,
            'analytics': 3,
            'real_time_signals': 2,
            'risk_management': 1,
            'order_execution': 1,
            'position_tracking': 1,
            'health_monitoring': 0,
        }

    def evaluate_degradation(self, health: SystemHealth) -> DegradationLevel:
        """
        Determine appropriate degradation level based on health.
        """
        if health.status == HealthStatus.CRITICAL:
            return DegradationLevel.EMERGENCY
        elif health.status == HealthStatus.UNHEALTHY:
            return DegradationLevel.MINIMAL
        elif health.status == HealthStatus.DEGRADED:
            return DegradationLevel.REDUCED
        else:
            return DegradationLevel.FULL

    def apply_degradation(self, level: DegradationLevel, reason: str = "") -> List[str]:
        """
        Apply degradation level.

        Returns:
            List of disabled features
        """
        old_level = self.level
        self.level = level

        # Determine which features to disable
        if level == DegradationLevel.FULL:
            self.disabled_features = set()
        elif level == DegradationLevel.REDUCED:
            self.disabled_features = {
                f for f, p in self.feature_priorities.items() if p >= 4
            }
        elif level == DegradationLevel.MINIMAL:
            self.disabled_features = {
                f for f, p in self.feature_priorities.items() if p >= 2
            }
        elif level == DegradationLevel.EMERGENCY:
            self.disabled_features = {
                f for f, p in self.feature_priorities.items() if p >= 1
            }

        self.degradation_history.append((datetime.now(timezone.utc), level, reason))

        if old_level != level:
            logger.warning(
                f"Degradation level changed: {old_level.value} -> {level.value}. "
                f"Reason: {reason}. Disabled: {self.disabled_features}"
            )

        return list(self.disabled_features)

    def is_feature_available(self, feature: str) -> bool:
        """Check if a feature is available."""
        return feature not in self.disabled_features

    def get_available_features(self) -> List[str]:
        """Get list of available features."""
        return [
            f for f in self.feature_priorities.keys()
            if f not in self.disabled_features
        ]


# =============================================================================
# SAFETY MONITOR
# =============================================================================

class SafetyMonitor:
    """
    Comprehensive safety monitoring for the trading system.
    """

    def __init__(self):
        self.diagnostics = SelfDiagnostics()
        self.degradation = GracefulDegradation()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.drift_detector: Optional[DriftDetector] = None
        self.anomaly_detector: Optional[AnomalyDetector] = None

        # Alert handlers
        self.alert_handlers: List[Callable[[str, str], None]] = []

        # Monitoring state
        self.is_running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def initialize(
        self,
        reference_data: np.ndarray = None,
        n_features: int = 10
    ) -> None:
        """Initialize detectors."""
        if reference_data is not None:
            self.drift_detector = DriftDetector(reference_data)
        else:
            self.drift_detector = DriftDetector()

        self.anomaly_detector = AnomalyDetector(n_features)

    def add_circuit_breaker(
        self,
        name: str,
        config: CircuitBreakerConfig = None
    ) -> CircuitBreaker:
        """Add a circuit breaker."""
        breaker = CircuitBreaker(name, config)
        self.circuit_breakers[name] = breaker
        return breaker

    def register_alert_handler(
        self,
        handler: Callable[[str, str], None]
    ) -> None:
        """Register alert handler."""
        self.alert_handlers.append(handler)

    def _send_alert(self, level: str, message: str) -> None:
        """Send alert to all handlers."""
        for handler in self.alert_handlers:
            try:
                handler(level, message)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def check_health(self) -> SystemHealth:
        """Run health check and apply degradation."""
        health = self.diagnostics.run_all_checks()

        # Apply degradation if needed
        new_level = self.degradation.evaluate_degradation(health)
        if new_level != self.degradation.level:
            disabled = self.degradation.apply_degradation(
                new_level,
                f"Health status: {health.status.value}"
            )
            if disabled:
                self._send_alert(
                    'warning',
                    f"Features disabled due to {health.status.value}: {disabled}"
                )

        return health

    def check_input(
        self,
        features: np.ndarray
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check input for anomalies and drift.

        Returns:
            Tuple of (is_safe, details)
        """
        issues = {}

        # Anomaly check
        if self.anomaly_detector:
            is_anomaly, anomaly_details = self.anomaly_detector.check(features)
            if is_anomaly:
                issues['anomaly'] = anomaly_details

        # Update drift detector
        if self.drift_detector:
            self.drift_detector.update(features=features)

        is_safe = len(issues) == 0

        if not is_safe:
            self._send_alert('warning', f"Input issues detected: {list(issues.keys())}")

        return is_safe, issues

    def check_drift(self) -> Dict[str, DriftResult]:
        """Run all drift checks."""
        results = {}

        if self.drift_detector:
            results['data'] = self.drift_detector.detect_data_drift()
            results['prediction'] = self.drift_detector.detect_prediction_drift()
            results['performance'] = self.drift_detector.detect_performance_drift()

            # Alert on significant drift
            for name, result in results.items():
                if result.is_drift_detected:
                    self._send_alert(
                        'warning',
                        f"{name.capitalize()} drift detected: score={result.drift_score:.3f}"
                    )

        return results

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive safety status."""
        health = self.check_health()
        drift = self.check_drift()

        return {
            'health': health.to_dict(),
            'degradation_level': self.degradation.level.value,
            'available_features': self.degradation.get_available_features(),
            'circuit_breakers': {
                name: breaker.get_status()
                for name, breaker in self.circuit_breakers.items()
            },
            'drift': {
                name: {
                    'detected': result.is_drift_detected,
                    'score': result.drift_score,
                }
                for name, result in drift.items()
            },
        }
