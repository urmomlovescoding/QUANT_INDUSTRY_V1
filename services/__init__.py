"""
QUANT_INDUSTRY_V1 Services Module

Background services for platform operation:
- Autonomous self-grading and improvement
- Health monitoring and alerting
- System orchestration
- Dashboard aggregation

Usage:
    from services import TradingPlatform

    platform = TradingPlatform()
    platform.initialize('trading.db')
    platform.run()
"""

from .self_grade import (
    # Types
    GradeLevel,
    GradingDimension,
    RemediationPriority,
    DimensionGrade,
    Remediation,
    GradeReport,
    # Graders
    DimensionGrader,
    ReturnsGrader,
    RiskAdjustedGrader,
    DrawdownGrader,
    ConsistencyGrader,
    ModelPerformanceGrader,
    SystemHealthGrader,
    # Engine
    RemediationGenerator,
    SelfGradingEngine,
)

from .health_monitor import (
    # Types
    HealthStatus,
    AlertSeverity,
    HealthCheck,
    Alert,
    SystemMetrics,
    # Checkers
    ComponentHealthChecker,
    DatabaseHealthChecker,
    BrokerHealthChecker,
    ModelHealthChecker,
    # Services
    HealthMonitor,
    DashboardService,
)

from .orchestrator import (
    # Types
    ComponentState,
    EventType,
    Event,
    ComponentInfo,
    # Core
    EventBus,
    SystemOrchestrator,
    TradingPlatform,
)

__all__ = [
    # Self-grading types
    'GradeLevel',
    'GradingDimension',
    'RemediationPriority',
    'DimensionGrade',
    'Remediation',
    'GradeReport',
    # Graders
    'DimensionGrader',
    'ReturnsGrader',
    'RiskAdjustedGrader',
    'DrawdownGrader',
    'ConsistencyGrader',
    'ModelPerformanceGrader',
    'SystemHealthGrader',
    # Self-grade engine
    'RemediationGenerator',
    'SelfGradingEngine',
    # Health types
    'HealthStatus',
    'AlertSeverity',
    'HealthCheck',
    'Alert',
    'SystemMetrics',
    # Health checkers
    'ComponentHealthChecker',
    'DatabaseHealthChecker',
    'BrokerHealthChecker',
    'ModelHealthChecker',
    # Health services
    'HealthMonitor',
    'DashboardService',
    # Orchestrator types
    'ComponentState',
    'EventType',
    'Event',
    'ComponentInfo',
    # Orchestrator core
    'EventBus',
    'SystemOrchestrator',
    'TradingPlatform',
]
