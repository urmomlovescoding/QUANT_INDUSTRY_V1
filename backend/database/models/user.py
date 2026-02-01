"""
User and Organization Models
============================
Core identity models for multi-tenant authentication.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, Text, Index, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class UserRole(str, Enum):
    """User roles within an organization."""
    OWNER = "owner"          # Full control, billing access
    ADMIN = "admin"          # User management, settings
    MEMBER = "member"        # Trading, strategies
    VIEWER = "viewer"        # Read-only access


class OrgTier(str, Enum):
    """Organization subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class OrgStatus(str, Enum):
    """Organization account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TRIAL = "trial"


class Organization(Base):
    """
    Organization/Tenant - top-level entity for multi-tenancy.

    All user data is scoped to an organization.
    """
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Identity
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)

    # Subscription
    tier = Column(SQLEnum(OrgTier), default=OrgTier.FREE, nullable=False)
    status = Column(SQLEnum(OrgStatus), default=OrgStatus.ACTIVE, nullable=False)

    # Billing (Stripe)
    stripe_customer_id = Column(String(255), unique=True)
    stripe_subscription_id = Column(String(255))

    # Settings
    settings = Column(JSON, default=dict)

    # SSO Configuration
    sso_enabled = Column(Boolean, default=False)
    sso_provider = Column(String(50))  # saml, oidc
    sso_config = Column(JSON)  # IdP metadata, client credentials

    # Limits (overrides for enterprise)
    custom_limits = Column(JSON)  # Override default tier limits

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="organization")
    api_keys = relationship("APIKey", back_populates="organization")

    def __repr__(self):
        return f"<Organization {self.slug} ({self.tier.value})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "tier": self.tier.value,
            "status": self.status.value,
            "sso_enabled": self.sso_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(Base):
    """
    User account within an organization.

    Users belong to exactly one organization.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Authentication
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255))  # Null for SSO-only users

    # Profile
    full_name = Column(String(255))
    avatar_url = Column(String(500))

    # Role & Permissions
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False)

    # SSO
    sso_provider = Column(String(50))  # okta, azure, google
    sso_external_id = Column(String(255))  # IdP user ID

    # MFA
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))  # Encrypted TOTP secret

    # Status
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255))

    # Activity
    last_login_at = Column(DateTime(timezone=True))
    last_login_ip = Column(String(45))  # IPv6 compatible
    login_count = Column(Integer, default=0)

    # Metadata
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    organization = relationship("Organization", back_populates="users")
    api_keys = relationship("APIKey", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_users_org_email', 'organization_id', 'email', unique=True),
        Index('ix_users_sso', 'sso_provider', 'sso_external_id'),
    )

    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "organization_id": self.organization_id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role.value,
            "is_active": self.is_active,
            "mfa_enabled": self.mfa_enabled,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            data["email_verified"] = self.email_verified
            data["sso_provider"] = self.sso_provider
        return data

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        role_permissions = {
            UserRole.OWNER: ["*"],  # All permissions
            UserRole.ADMIN: [
                "users:read", "users:write", "users:invite",
                "strategies:*", "portfolios:*", "settings:read", "settings:write",
                "api_keys:*", "audit:read"
            ],
            UserRole.MEMBER: [
                "strategies:read", "strategies:write",
                "portfolios:read", "portfolios:write",
                "signals:read", "trades:read", "trades:write"
            ],
            UserRole.VIEWER: [
                "strategies:read", "portfolios:read",
                "signals:read", "trades:read"
            ]
        }

        user_perms = role_permissions.get(self.role, [])

        if "*" in user_perms:
            return True

        if permission in user_perms:
            return True

        # Check wildcard permissions (e.g., "strategies:*" matches "strategies:read")
        resource = permission.split(":")[0]
        if f"{resource}:*" in user_perms:
            return True

        return False


class RefreshToken(Base):
    """
    Refresh tokens for JWT authentication.

    Tracks active sessions and allows revocation.
    """
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Token
    token_hash = Column(String(255), nullable=False, unique=True)
    jti = Column(String(64), unique=True)  # JWT ID for the associated access token

    # Device/Session info
    device_name = Column(String(255))
    device_type = Column(String(50))  # web, mobile, api
    ip_address = Column(String(45))
    user_agent = Column(Text)

    # Lifecycle
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    revoked_reason = Column(String(100))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index('ix_refresh_tokens_expires', 'expires_at'),
    )

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid."""
        if self.revoked_at:
            return False
        if self.expires_at < datetime.utcnow():
            return False
        return True


