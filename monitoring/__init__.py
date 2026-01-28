"""
Monitoring Module - Drift Detection and Smart Alerts
QUANT_INDUSTRY_V1
"""

from .drift_detector import (
    DriftDetector,
    DriftReport,
    DriftSeverity,
    DriftCause,
    DriftAlert,
    ExpectedPerformanceModel,
    AlphaDecayMonitor
)

from .smart_alerts import (
    SmartAlertSystem,
    SmartAlert,
    AlertPriority,
    AlertCategory,
    AnomalyDetector,
    AlertDeduplicator,
    AlertPrioritizer,
    AlertChannel,
    DiscordChannel,
    TelegramChannel
)

__all__ = [
    # Drift detection
    'DriftDetector',
    'DriftReport',
    'DriftSeverity',
    'DriftCause',
    'DriftAlert',
    'ExpectedPerformanceModel',
    'AlphaDecayMonitor',
    
    # Smart alerts
    'SmartAlertSystem',
    'SmartAlert',
    'AlertPriority',
    'AlertCategory',
    'AnomalyDetector',
    'AlertDeduplicator',
    'AlertPrioritizer',
    'AlertChannel',
    'DiscordChannel',
    'TelegramChannel',
]
