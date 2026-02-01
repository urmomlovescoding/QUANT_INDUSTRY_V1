"""
Audit Log Model
===============
Comprehensive audit trail for compliance and security.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Index, JSON
)
from sqlalchemy.sql import func

from .base import Base


class AuditAction(str, Enum):
    """Categorized audit actions."""

    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_PASSWORD_CHANGE = "auth.password_change"
    AUTH_PASSWORD_RESET = "auth.password_reset"
    AUTH_MFA_ENABLED = "auth.mfa_enabled"
    AUTH_MFA_DISABLED = "auth.mfa_disabled"
    AUTH_SSO_LOGIN = "auth.sso_login"

    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_INVITED = "user.invited"
    USER_ROLE_CHANGED = "user.role_changed"
    USER_DEACTIVATED = "user.deactivated"
    USER_REACTIVATED = "user.reactivated"

    # Organization
    ORG_CREATED = "org.created"
    ORG_UPDATED = "org.updated"
    ORG_SETTINGS_CHANGED = "org.settings_changed"
    ORG_SSO_CONFIGURED = "org.sso_configured"

    # API Keys
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_USED = "api_key.used"

    # Billing
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPGRADED = "subscription.upgraded"
    SUBSCRIPTION_DOWNGRADED = "subscription.downgraded"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"

    # Trading Resources
    STRATEGY_CREATED = "strategy.created"
    STRATEGY_UPDATED = "strategy.updated"
    STRATEGY_DELETED = "strategy.deleted"
    STRATEGY_ACTIVATED = "strategy.activated"
    STRATEGY_DEACTIVATED = "strategy.deactivated"

    PORTFOLIO_CREATED = "portfolio.created"
    PORTFOLIO_UPDATED = "portfolio.updated"
    PORTFOLIO_DELETED = "portfolio.deleted"

    # Trading Actions
    SIGNAL_GENERATED = "trading.signal_generated"
    TRADE_EXECUTED = "trading.trade_executed"
    POSITION_OPENED = "trading.position_opened"
    POSITION_CLOSED = "trading.position_closed"
    ORDER_PLACED = "trading.order_placed"
    ORDER_CANCELLED = "trading.order_cancelled"

    # Safety
    KILL_SWITCH_ACTIVATED = "safety.kill_switch_activated"
    KILL_SWITCH_DEACTIVATED = "safety.kill_switch_deactivated"
    RISK_LIMIT_BREACHED = "safety.risk_limit_breached"

    # Data Access
    DATA_EXPORTED = "data.exported"
    DATA_DELETED = "data.deleted"

    # System
    SYSTEM_CONFIG_CHANGED = "system.config_changed"


class AuditLog(Base):
    """
    Immutable audit log for compliance.

    All sensitive operations are logged here for security and compliance.
    Logs are append-only and should never be modified or deleted.
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Tenant context
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='SET NULL'),
        nullable=True,  # System-level events may not have org
        index=True
    )

    # Actor
    user_id = Column(
        String(36),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True  # System/API key actions may not have user
    )
    actor_type = Column(String(50))  # user, api_key, system, webhook
    actor_email = Column(String(255))  # Denormalized for historical reference

    # Action
    action = Column(String(100), nullable=False, index=True)

    # Resource
    resource_type = Column(String(50), nullable=False)  # user, strategy, trade, etc.
    resource_id = Column(String(36))

    # Changes
    old_values = Column(JSON)  # Previous state
    new_values = Column(JSON)  # New state
    changes_summary = Column(Text)  # Human-readable summary

    # Context
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    request_id = Column(String(100))  # Correlation ID
    session_id = Column(String(100))

    # Extra context
    extra_data = Column(JSON)  # Additional context

    # Timestamp (immutable)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index('ix_audit_org_created', 'organization_id', 'created_at'),
        Index('ix_audit_user_created', 'user_id', 'created_at'),
        Index('ix_audit_action_created', 'action', 'created_at'),
        Index('ix_audit_resource', 'resource_type', 'resource_id'),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.actor_email or self.actor_type}>"

    @classmethod
    def log(
        cls,
        action: AuditAction,
        resource_type: str,
        resource_id: str = None,
        organization_id: str = None,
        user_id: str = None,
        actor_type: str = "user",
        actor_email: str = None,
        old_values: Dict = None,
        new_values: Dict = None,
        ip_address: str = None,
        user_agent: str = None,
        request_id: str = None,
        extra_data: Dict = None
    ) -> 'AuditLog':
        """
        Create an audit log entry.

        This is a factory method - caller must still add to session and commit.
        """
        # Generate changes summary
        changes_summary = None
        if old_values and new_values:
            changes = []
            all_keys = set(old_values.keys()) | set(new_values.keys())
            for key in all_keys:
                old_val = old_values.get(key)
                new_val = new_values.get(key)
                if old_val != new_val:
                    changes.append(f"{key}: {old_val} -> {new_val}")
            if changes:
                changes_summary = "; ".join(changes)

        return cls(
            organization_id=organization_id,
            user_id=user_id,
            actor_type=actor_type,
            actor_email=actor_email,
            action=action.value if isinstance(action, AuditAction) else action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            changes_summary=changes_summary,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            extra_data=extra_data,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "actor_type": self.actor_type,
            "actor_email": self.actor_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "changes_summary": self.changes_summary,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "extra_data": self.extra_data,
        }

    def to_compliance_dict(self) -> Dict[str, Any]:
        """Full details for compliance export."""
        return {
            **self.to_dict(),
            "old_values": self.old_values,
            "new_values": self.new_values,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
        }
