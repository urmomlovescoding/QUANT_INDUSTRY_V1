"""
Multi-Tenant Database Models
============================
SQLAlchemy models for the enterprise multi-tenant SaaS platform.

This module provides:
- TenantMixin for row-level tenant isolation
- User/Organization models for authentication
- Subscription models for billing
- APIKey for programmatic access
- AuditLog for compliance
"""

# Shared Base for all models
from .base import Base

# Export Base first so other modules can import it
from .tenant import (
    TenantMixin,
    TenantAwareSession,
    get_current_tenant_id,
    set_current_tenant_id,
    register_tenant_events,
)

from .user import (
    User,
    Organization,
    RefreshToken,
    UserRole,
    OrgTier,
    OrgStatus,
)

from .subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    UsageRecord,
    Invoice,
    PaymentMethod,
)

from .api_key import APIKey

from .audit import AuditLog, AuditAction

__all__ = [
    # Base
    "Base",
    # Tenant
    "TenantMixin",
    "TenantAwareSession",
    "get_current_tenant_id",
    "set_current_tenant_id",
    "register_tenant_events",
    # User/Org
    "User",
    "Organization",
    "RefreshToken",
    "UserRole",
    "OrgTier",
    "OrgStatus",
    # Billing
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "UsageRecord",
    "Invoice",
    "PaymentMethod",
    # Security
    "APIKey",
    # Audit
    "AuditLog",
    "AuditAction",
]
