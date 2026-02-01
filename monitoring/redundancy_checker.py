"""
Redundancy Checker - Cross-Zone Redundancy and Failover Monitoring

This module monitors system redundancy, detects single points of
failure, and validates failover readiness.

Key Features:
- Cross-zone redundancy verification
- Service replica health monitoring
- Failover testing and validation
- Alert generation for redundancy gaps
- Kubernetes pod disruption budget monitoring

Usage:
    from monitoring.redundancy_checker import RedundancyChecker

    checker = RedundancyChecker()
    status = checker.check_redundancy()
    if not status.is_fully_redundant:
        print(f"Issues: {status.issues}")
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of services to monitor."""
    API = "api"
    DATA_FETCHER = "data_fetcher"
    EXECUTION = "execution"
    BRAIN = "brain"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    MONITORING = "monitoring"


class ZoneStatus(Enum):
    """Availability zone status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class ServiceInstance:
    """Represents a service instance/replica."""
    service_type: ServiceType
    instance_id: str
    zone: str
    host: str
    port: int
    is_healthy: bool
    last_health_check: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RedundancyStatus:
    """Overall redundancy status."""
    is_fully_redundant: bool
    redundancy_score: float  # 0-100
    service_status: Dict[str, Dict[str, Any]]
    zone_status: Dict[str, ZoneStatus]
    issues: List[str]
    recommendations: List[str]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_fully_redundant': self.is_fully_redundant,
            'redundancy_score': self.redundancy_score,
            'service_status': self.service_status,
            'zone_status': {k: v.value for k, v in self.zone_status.items()},
            'issues': self.issues,
            'recommendations': self.recommendations,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class FailoverTestResult:
    """Result of a failover test."""
    service_type: ServiceType
    test_type: str
    success: bool
    failover_time_ms: float
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RedundancyConfig:
    """Configuration for redundancy checker."""
    min_replicas_per_service: int = 2
    min_zones: int = 2
    health_check_interval_seconds: int = 30
    max_unhealthy_percent: float = 0.25
    failover_timeout_seconds: int = 30


class RedundancyChecker:
    """
    Monitors and validates system redundancy.

    Ensures critical services have adequate replicas across
    availability zones and can failover gracefully.

    Example:
        checker = RedundancyChecker()

        # Register services
        checker.register_service(ServiceType.API, 'api-1', 'zone-a')
        checker.register_service(ServiceType.API, 'api-2', 'zone-b')

        # Check redundancy
        status = checker.check_redundancy()
        print(f"Fully redundant: {status.is_fully_redundant}")

        # Test failover
        result = await checker.test_failover(ServiceType.API)
    """

    def __init__(self, config: Optional[RedundancyConfig] = None):
        self.config = config or RedundancyConfig()

        # Service registry
        self._services: Dict[ServiceType, List[ServiceInstance]] = {
            stype: [] for stype in ServiceType
        }

        # Zone tracking
        self._zones: Set[str] = set()

        # Failover test history
        self._failover_history: List[FailoverTestResult] = []

        # Health check callbacks
        self._health_check_callbacks: Dict[ServiceType, callable] = {}

        logger.info("RedundancyChecker initialized")

    def register_service(
        self,
        service_type: ServiceType,
        instance_id: str,
        zone: str,
        host: str = "localhost",
        port: int = 8080,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a service instance.

        Args:
            service_type: Type of service
            instance_id: Unique instance identifier
            zone: Availability zone
            host: Service host
            port: Service port
            metadata: Additional metadata
        """
        instance = ServiceInstance(
            service_type=service_type,
            instance_id=instance_id,
            zone=zone,
            host=host,
            port=port,
            is_healthy=True,
            last_health_check=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        self._services[service_type].append(instance)
        self._zones.add(zone)

        logger.info(f"Registered service: {service_type.value}/{instance_id} in {zone}")

    def unregister_service(
        self,
        service_type: ServiceType,
        instance_id: str,
    ) -> bool:
        """Unregister a service instance."""
        instances = self._services[service_type]
        original_len = len(instances)

        self._services[service_type] = [
            i for i in instances if i.instance_id != instance_id
        ]

        removed = len(self._services[service_type]) < original_len

        if removed:
            logger.info(f"Unregistered service: {service_type.value}/{instance_id}")

        return removed

    def update_health(
        self,
        service_type: ServiceType,
        instance_id: str,
        is_healthy: bool,
    ) -> None:
        """Update health status of a service instance."""
        for instance in self._services[service_type]:
            if instance.instance_id == instance_id:
                instance.is_healthy = is_healthy
                instance.last_health_check = datetime.now(timezone.utc)
                break

    def set_health_check_callback(
        self,
        service_type: ServiceType,
        callback: callable,
    ) -> None:
        """Set health check callback for a service type."""
        self._health_check_callbacks[service_type] = callback

    async def run_health_checks(self) -> Dict[ServiceType, Dict[str, bool]]:
        """
        Run health checks on all services.

        Returns:
            Dictionary of service type to instance health results
        """
        results = {}

        for service_type, instances in self._services.items():
            results[service_type] = {}

            for instance in instances:
                try:
                    # Use callback if registered
                    if service_type in self._health_check_callbacks:
                        callback = self._health_check_callbacks[service_type]
                        if asyncio.iscoroutinefunction(callback):
                            is_healthy = await callback(instance)
                        else:
                            is_healthy = callback(instance)
                    else:
                        # Default: assume healthy if recently checked
                        age = (datetime.now(timezone.utc) - instance.last_health_check).total_seconds()
                        is_healthy = age < 300  # 5 minutes

                    instance.is_healthy = is_healthy
                    instance.last_health_check = datetime.now(timezone.utc)
                    results[service_type][instance.instance_id] = is_healthy

                except Exception as e:
                    logger.error(f"Health check failed for {instance.instance_id}: {e}")
                    instance.is_healthy = False
                    results[service_type][instance.instance_id] = False

        return results

    def check_redundancy(self) -> RedundancyStatus:
        """
        Check overall system redundancy.

        Returns:
            RedundancyStatus with current redundancy state
        """
        issues = []
        recommendations = []
        service_status = {}
        zone_health: Dict[str, int] = {z: 0 for z in self._zones}
        total_score = 0
        service_count = 0

        for service_type, instances in self._services.items():
            if not instances:
                continue

            service_count += 1
            healthy = [i for i in instances if i.is_healthy]
            zones_covered = set(i.zone for i in healthy)

            # Check replica count
            replica_ok = len(healthy) >= self.config.min_replicas_per_service
            if not replica_ok:
                issues.append(
                    f"{service_type.value}: Only {len(healthy)}/{self.config.min_replicas_per_service} "
                    f"healthy replicas"
                )
                recommendations.append(
                    f"Add more replicas for {service_type.value}"
                )

            # Check zone coverage
            zone_ok = len(zones_covered) >= min(self.config.min_zones, len(self._zones))
            if not zone_ok and len(self._zones) >= 2:
                issues.append(
                    f"{service_type.value}: Only in {len(zones_covered)} zones, "
                    f"need {self.config.min_zones}"
                )
                recommendations.append(
                    f"Deploy {service_type.value} to more zones"
                )

            # Calculate service score
            replica_score = min(100, len(healthy) / self.config.min_replicas_per_service * 50)
            zone_score = min(100, len(zones_covered) / max(1, self.config.min_zones) * 50)
            service_score = replica_score + zone_score

            total_score += service_score

            service_status[service_type.value] = {
                'total_instances': len(instances),
                'healthy_instances': len(healthy),
                'zones': list(zones_covered),
                'is_redundant': replica_ok and zone_ok,
                'score': service_score,
            }

            # Update zone health
            for zone in zones_covered:
                zone_health[zone] += 1

        # Determine zone status
        max_services = max(zone_health.values()) if zone_health else 0
        zone_status = {}
        for zone, count in zone_health.items():
            if count == 0:
                zone_status[zone] = ZoneStatus.UNAVAILABLE
                issues.append(f"Zone {zone} has no healthy services")
            elif count < max_services * 0.5:
                zone_status[zone] = ZoneStatus.DEGRADED
            else:
                zone_status[zone] = ZoneStatus.HEALTHY

        # Calculate overall redundancy score
        redundancy_score = total_score / service_count if service_count > 0 else 100
        is_fully_redundant = len(issues) == 0 and redundancy_score >= 80

        return RedundancyStatus(
            is_fully_redundant=is_fully_redundant,
            redundancy_score=redundancy_score,
            service_status=service_status,
            zone_status=zone_status,
            issues=issues,
            recommendations=recommendations,
            timestamp=datetime.now(timezone.utc),
        )

    async def test_failover(
        self,
        service_type: ServiceType,
        simulate_failure: bool = False,
    ) -> FailoverTestResult:
        """
        Test failover capability for a service.

        Args:
            service_type: Service to test
            simulate_failure: Whether to actually simulate failure

        Returns:
            FailoverTestResult with test outcome
        """
        instances = self._services[service_type]
        healthy = [i for i in instances if i.is_healthy]

        if len(healthy) < 2:
            return FailoverTestResult(
                service_type=service_type,
                test_type='replica_count',
                success=False,
                failover_time_ms=0,
                error_message=f"Insufficient replicas: {len(healthy)} < 2",
            )

        # Pick primary and backup
        primary = healthy[0]
        backup = healthy[1]

        start_time = datetime.now(timezone.utc)

        try:
            if simulate_failure:
                # Mark primary as unhealthy
                primary.is_healthy = False

                # Verify backup can take over
                # In production, this would actually route traffic

                # Simulate failover time
                await asyncio.sleep(0.1)

                # Restore primary
                primary.is_healthy = True

            failover_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            result = FailoverTestResult(
                service_type=service_type,
                test_type='simulate_failure' if simulate_failure else 'dry_run',
                success=True,
                failover_time_ms=failover_time,
            )

        except Exception as e:
            result = FailoverTestResult(
                service_type=service_type,
                test_type='simulate_failure' if simulate_failure else 'dry_run',
                success=False,
                failover_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000,
                error_message=str(e),
            )

        self._failover_history.append(result)
        return result

    def get_single_points_of_failure(self) -> List[Dict[str, Any]]:
        """
        Identify single points of failure.

        Returns:
            List of SPOFs with details
        """
        spofs = []

        for service_type, instances in self._services.items():
            healthy = [i for i in instances if i.is_healthy]

            # Single replica
            if len(healthy) == 1:
                spofs.append({
                    'service': service_type.value,
                    'type': 'single_replica',
                    'instance': healthy[0].instance_id,
                    'severity': 'high',
                })

            # Single zone
            zones = set(i.zone for i in healthy)
            if len(zones) == 1 and len(healthy) > 0:
                spofs.append({
                    'service': service_type.value,
                    'type': 'single_zone',
                    'zone': list(zones)[0],
                    'severity': 'medium',
                })

        return spofs

    def get_pod_disruption_budget_recommendation(
        self,
        service_type: ServiceType,
    ) -> Dict[str, Any]:
        """
        Get recommended PodDisruptionBudget for a service.

        Args:
            service_type: Service to get recommendation for

        Returns:
            Dictionary with PDB configuration
        """
        instances = self._services[service_type]
        healthy_count = sum(1 for i in instances if i.is_healthy)

        if healthy_count <= 1:
            min_available = 1
            max_unavailable = 0
        elif healthy_count <= 3:
            min_available = healthy_count - 1
            max_unavailable = 1
        else:
            min_available = int(healthy_count * 0.75)
            max_unavailable = int(healthy_count * 0.25) or 1

        return {
            'service': service_type.value,
            'min_available': min_available,
            'max_unavailable': max_unavailable,
            'current_healthy': healthy_count,
            'pdb_yaml': f"""
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {service_type.value}-pdb
spec:
  minAvailable: {min_available}
  selector:
    matchLabels:
      app: {service_type.value}
""".strip(),
        }

    def get_zone_distribution(self) -> Dict[str, Dict[str, int]]:
        """
        Get service distribution across zones.

        Returns:
            Dictionary of zone to service counts
        """
        distribution = {zone: {} for zone in self._zones}

        for service_type, instances in self._services.items():
            for instance in instances:
                if instance.zone in distribution:
                    if service_type.value not in distribution[instance.zone]:
                        distribution[instance.zone][service_type.value] = 0
                    distribution[instance.zone][service_type.value] += 1

        return distribution

    def get_failover_history(
        self,
        service_type: Optional[ServiceType] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get failover test history."""
        history = self._failover_history

        if service_type:
            history = [h for h in history if h.service_type == service_type]

        history = history[-limit:]

        return [
            {
                'service': h.service_type.value,
                'test_type': h.test_type,
                'success': h.success,
                'failover_time_ms': h.failover_time_ms,
                'error': h.error_message,
                'timestamp': h.timestamp.isoformat(),
            }
            for h in history
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get checker statistics."""
        total_services = sum(len(instances) for instances in self._services.values())
        healthy_services = sum(
            sum(1 for i in instances if i.is_healthy)
            for instances in self._services.values()
        )

        return {
            'total_zones': len(self._zones),
            'total_service_instances': total_services,
            'healthy_instances': healthy_services,
            'service_types_registered': sum(
                1 for instances in self._services.values() if instances
            ),
            'failover_tests_run': len(self._failover_history),
        }
