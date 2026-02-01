"""
Audit Log - Immutable Security Audit Trail

This module provides an immutable audit logging system for
security compliance and forensic analysis.

Key Features:
- Immutable append-only log
- Cryptographic integrity verification
- Event categorization
- Query and search capabilities
- Export for compliance reporting

Usage:
    from security.audit_log import AuditLogger

    logger = AuditLogger()
    logger.log_event(AuditEventType.LOGIN, user_id="user123", details={"ip": "1.2.3.4"})
    events = logger.query_events(event_type=AuditEventType.LOGIN, limit=100)
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import threading
import uuid

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # Authorization
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ACCESS_DENIED = "access_denied"

    # Trading
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"

    # Configuration
    CONFIG_CHANGED = "config_changed"
    STRATEGY_ENABLED = "strategy_enabled"
    STRATEGY_DISABLED = "strategy_disabled"
    MODEL_DEPLOYED = "model_deployed"

    # System
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    ERROR = "error"
    ALERT_TRIGGERED = "alert_triggered"

    # Data
    DATA_EXPORT = "data_export"
    DATA_ACCESS = "data_access"
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"

    # API
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_CALL = "api_call"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Immutable audit event record."""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: Optional[str]
    ip_address: Optional[str]
    resource: Optional[str]
    action: str
    outcome: str  # 'success', 'failure', 'partial'
    details: Dict[str, Any]
    previous_hash: str
    event_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'severity': self.severity.value,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'resource': self.resource,
            'action': self.action,
            'outcome': self.outcome,
            'details': self.details,
            'previous_hash': self.previous_hash,
            'event_hash': self.event_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        return cls(
            event_id=data['event_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            event_type=AuditEventType(data['event_type']),
            severity=AuditSeverity(data['severity']),
            user_id=data.get('user_id'),
            ip_address=data.get('ip_address'),
            resource=data.get('resource'),
            action=data['action'],
            outcome=data['outcome'],
            details=data.get('details', {}),
            previous_hash=data['previous_hash'],
            event_hash=data['event_hash'],
        )


@dataclass
class AuditConfig:
    """Configuration for audit logger."""
    log_file_path: str = "audit_log.jsonl"
    max_file_size_mb: int = 100
    retention_days: int = 365
    enable_file_logging: bool = True
    hash_algorithm: str = "sha256"


class AuditLogger:
    """
    Immutable audit logging system.

    Provides cryptographically verifiable, append-only audit trail
    for security and compliance requirements.

    The log uses a hash chain where each event includes the hash
    of the previous event, making tampering detectable.

    Example:
        audit = AuditLogger()

        # Log a login event
        audit.log_event(
            event_type=AuditEventType.LOGIN,
            user_id="user123",
            ip_address="192.168.1.1",
            outcome="success"
        )

        # Query recent events
        events = audit.query_events(
            event_type=AuditEventType.LOGIN,
            start_time=datetime.now() - timedelta(hours=24)
        )

        # Verify log integrity
        is_valid = audit.verify_integrity()
    """

    def __init__(self, config: Optional[AuditConfig] = None):
        self.config = config or AuditConfig()

        self._events: List[AuditEvent] = []
        self._lock = threading.RLock()
        self._last_hash = "GENESIS"

        # Load existing log
        self._load_log()

        logger.info("AuditLogger initialized")

    def _load_log(self) -> None:
        """Load existing audit log from file."""
        log_path = Path(self.config.log_file_path)

        if not log_path.exists():
            return

        try:
            with open(log_path, 'r') as f:
                for line in f:
                    if line.strip():
                        event_data = json.loads(line)
                        event = AuditEvent.from_dict(event_data)
                        self._events.append(event)
                        self._last_hash = event.event_hash

            logger.info(f"Loaded {len(self._events)} audit events from log")

        except Exception as e:
            logger.error(f"Failed to load audit log: {e}")

    def _compute_hash(self, event_data: Dict[str, Any], previous_hash: str) -> str:
        """Compute hash for event chain."""
        data_str = json.dumps(event_data, sort_keys=True) + previous_hash
        return hashlib.new(
            self.config.hash_algorithm,
            data_str.encode()
        ).hexdigest()

    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        outcome: str = "success",
        severity: Optional[AuditSeverity] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            user_id: User identifier
            ip_address: Source IP address
            resource: Resource being accessed
            action: Action description
            outcome: 'success', 'failure', or 'partial'
            severity: Event severity
            details: Additional details

        Returns:
            Created AuditEvent
        """
        with self._lock:
            # Generate event ID
            event_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc)

            # Determine severity if not provided
            if severity is None:
                if outcome == "failure":
                    severity = AuditSeverity.WARNING
                elif event_type in (AuditEventType.ACCESS_DENIED, AuditEventType.LOGIN_FAILED):
                    severity = AuditSeverity.WARNING
                elif event_type == AuditEventType.ERROR:
                    severity = AuditSeverity.ERROR
                else:
                    severity = AuditSeverity.INFO

            # Build event data for hashing
            event_data = {
                'event_id': event_id,
                'timestamp': timestamp.isoformat(),
                'event_type': event_type.value,
                'severity': severity.value,
                'user_id': user_id,
                'ip_address': ip_address,
                'resource': resource,
                'action': action or event_type.value,
                'outcome': outcome,
                'details': details or {},
            }

            # Compute hash
            event_hash = self._compute_hash(event_data, self._last_hash)

            # Create event
            event = AuditEvent(
                event_id=event_id,
                timestamp=timestamp,
                event_type=event_type,
                severity=severity,
                user_id=user_id,
                ip_address=ip_address,
                resource=resource,
                action=action or event_type.value,
                outcome=outcome,
                details=details or {},
                previous_hash=self._last_hash,
                event_hash=event_hash,
            )

            self._events.append(event)
            self._last_hash = event_hash

            # Write to file
            if self.config.enable_file_logging:
                self._write_event(event)

            return event

    def _write_event(self, event: AuditEvent) -> None:
        """Write event to log file."""
        try:
            log_path = Path(self.config.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            with open(log_path, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')

            # Check file size and rotate if needed
            if log_path.stat().st_size > self.config.max_file_size_mb * 1024 * 1024:
                self._rotate_log()

        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")

    def _rotate_log(self) -> None:
        """Rotate log file."""
        log_path = Path(self.config.log_file_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_path = log_path.with_suffix(f'.{timestamp}.jsonl')

        try:
            log_path.rename(archive_path)
            logger.info(f"Rotated audit log to {archive_path}")
        except Exception as e:
            logger.error(f"Failed to rotate log: {e}")

    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        outcome: Optional[str] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """
        Query audit events.

        Args:
            event_type: Filter by event type
            user_id: Filter by user
            start_time: Start of time range
            end_time: End of time range
            severity: Filter by severity
            outcome: Filter by outcome
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        events = self._events.copy()

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if user_id:
            events = [e for e in events if e.user_id == user_id]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        if severity:
            events = [e for e in events if e.severity == severity]

        if outcome:
            events = [e for e in events if e.outcome == outcome]

        # Return most recent first
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log.

        Checks the hash chain to detect any tampering.

        Returns:
            Dictionary with verification results
        """
        if not self._events:
            return {
                'valid': True,
                'events_checked': 0,
                'message': 'No events to verify',
            }

        previous_hash = "GENESIS"
        invalid_events = []

        for event in self._events:
            # Rebuild event data
            event_data = {
                'event_id': event.event_id,
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type.value,
                'severity': event.severity.value,
                'user_id': event.user_id,
                'ip_address': event.ip_address,
                'resource': event.resource,
                'action': event.action,
                'outcome': event.outcome,
                'details': event.details,
            }

            # Verify hash
            expected_hash = self._compute_hash(event_data, previous_hash)

            if event.previous_hash != previous_hash:
                invalid_events.append({
                    'event_id': event.event_id,
                    'error': 'Previous hash mismatch',
                })
            elif event.event_hash != expected_hash:
                invalid_events.append({
                    'event_id': event.event_id,
                    'error': 'Event hash mismatch',
                })

            previous_hash = event.event_hash

        return {
            'valid': len(invalid_events) == 0,
            'events_checked': len(self._events),
            'invalid_events': invalid_events,
            'message': 'All events valid' if not invalid_events else f'{len(invalid_events)} invalid events found',
        }

    def get_security_summary(
        self,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get security summary for monitoring.

        Args:
            hours: Lookback period

        Returns:
            Security summary
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent = [e for e in self._events if e.timestamp >= cutoff]

        # Count by type
        type_counts = {}
        for e in recent:
            type_name = e.event_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        # Count failures
        failures = [e for e in recent if e.outcome == 'failure']
        access_denied = [e for e in recent if e.event_type == AuditEventType.ACCESS_DENIED]
        login_failures = [e for e in recent if e.event_type == AuditEventType.LOGIN_FAILED]

        # Unique users
        users = set(e.user_id for e in recent if e.user_id)
        ips = set(e.ip_address for e in recent if e.ip_address)

        return {
            'period_hours': hours,
            'total_events': len(recent),
            'event_types': type_counts,
            'failures': len(failures),
            'access_denied': len(access_denied),
            'login_failures': len(login_failures),
            'unique_users': len(users),
            'unique_ips': len(ips),
        }

    def export_report(
        self,
        start_time: datetime,
        end_time: datetime,
        include_details: bool = True,
    ) -> Dict[str, Any]:
        """
        Export compliance report.

        Args:
            start_time: Report start time
            end_time: Report end time
            include_details: Whether to include event details

        Returns:
            Compliance report
        """
        events = self.query_events(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        # Summary statistics
        type_counts = {}
        outcome_counts = {'success': 0, 'failure': 0, 'partial': 0}
        severity_counts = {}

        for e in events:
            type_name = e.event_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

            outcome_counts[e.outcome] = outcome_counts.get(e.outcome, 0) + 1

            sev_name = e.severity.value
            severity_counts[sev_name] = severity_counts.get(sev_name, 0) + 1

        report = {
            'report_generated': datetime.now(timezone.utc).isoformat(),
            'period_start': start_time.isoformat(),
            'period_end': end_time.isoformat(),
            'total_events': len(events),
            'event_types': type_counts,
            'outcomes': outcome_counts,
            'severities': severity_counts,
            'integrity_check': self.verify_integrity(),
        }

        if include_details:
            report['events'] = [e.to_dict() for e in events]

        return report

    def get_stats(self) -> Dict[str, Any]:
        """Get logger statistics."""
        return {
            'total_events': len(self._events),
            'last_event': self._events[-1].timestamp.isoformat() if self._events else None,
            'integrity_valid': self.verify_integrity()['valid'],
        }
