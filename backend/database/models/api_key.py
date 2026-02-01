"""
API Key Model
=============
Customer API key management for programmatic access.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid
import secrets
import hashlib

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, Text, Index, JSON, ARRAY
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class APIKey(Base):
    """
    API Key for programmatic access.

    Keys are hashed - the plaintext is only shown once on creation.
    """
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    user_id = Column(
        String(36),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Key identification
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification
    key_hash = Column(String(255), nullable=False, unique=True)

    # Permissions (scopes)
    scopes = Column(JSON, default=list)  # ["read:signals", "write:trades", ...]

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_day = Column(Integer, default=10000)

    # Usage tracking
    last_used_at = Column(DateTime(timezone=True))
    last_used_ip = Column(String(45))
    usage_count = Column(Integer, default=0)

    # Lifecycle
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
    revoked_reason = Column(String(255))

    # Metadata
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="api_keys")
    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index('ix_api_keys_prefix', 'key_prefix'),
        Index('ix_api_keys_org_active', 'organization_id', 'is_active'),
    )

    # Available scopes
    AVAILABLE_SCOPES = [
        "read:signals",
        "write:signals",
        "read:strategies",
        "write:strategies",
        "read:portfolios",
        "write:portfolios",
        "read:trades",
        "write:trades",
        "read:positions",
        "read:market_data",
        "read:analytics",
        "admin:users",
        "admin:billing",
    ]

    def __repr__(self):
        return f"<APIKey {self.name} ({self.key_prefix}...)>"

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            (full_key, prefix, hash) - Only show full_key once!
        """
        # Generate 32-byte random key, encode as hex (64 chars)
        key_bytes = secrets.token_bytes(32)
        full_key = f"qi_{key_bytes.hex()}"  # qi_ prefix for identification
        prefix = full_key[:10]  # qi_XXXXXX

        # Hash for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        return full_key, prefix, key_hash

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for comparison."""
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def create(
        cls,
        organization_id: str,
        name: str,
        scopes: List[str] = None,
        user_id: str = None,
        expires_at: datetime = None,
        rate_limit_per_minute: int = 60,
        description: str = None
    ) -> tuple['APIKey', str]:
        """
        Create a new API key.

        Returns:
            (api_key_model, plaintext_key) - plaintext_key only shown once!
        """
        full_key, prefix, key_hash = cls.generate_key()

        api_key = cls(
            organization_id=organization_id,
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=scopes or ["read:signals", "read:market_data"],
            rate_limit_per_minute=rate_limit_per_minute,
            expires_at=expires_at,
            description=description,
        )

        return api_key, full_key

    def verify(self, key: str) -> bool:
        """Verify an API key matches this record."""
        if not self.is_valid:
            return False
        return self.key_hash == self.hash_key(key)

    @property
    def is_valid(self) -> bool:
        """Check if key is still valid."""
        if not self.is_active:
            return False
        if self.revoked_at:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        """Check if key has a specific scope."""
        if not self.scopes:
            return False

        # Check exact match
        if scope in self.scopes:
            return True

        # Check wildcard (e.g., "read:*" matches "read:signals")
        scope_parts = scope.split(":")
        if len(scope_parts) == 2:
            wildcard = f"{scope_parts[0]}:*"
            if wildcard in self.scopes:
                return True

        # Check admin override
        if "admin:*" in self.scopes:
            return True

        return False

    def record_usage(self, ip_address: str = None):
        """Record that this key was used."""
        self.last_used_at = datetime.utcnow()
        self.usage_count = (self.usage_count or 0) + 1
        if ip_address:
            self.last_used_ip = ip_address

    def revoke(self, reason: str = None):
        """Revoke this API key."""
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason

    def to_dict(self, include_prefix: bool = True) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "name": self.name,
            "scopes": self.scopes,
            "is_active": self.is_active,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "usage_count": self.usage_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_prefix:
            data["key_prefix"] = self.key_prefix
        return data
