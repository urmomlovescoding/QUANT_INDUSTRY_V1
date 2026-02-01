"""
Tenant Isolation Layer
======================
Core multi-tenancy implementation with row-level isolation.

All tenant-scoped models inherit from TenantMixin which:
1. Adds organization_id FK to every row
2. Creates proper indexes for query performance
3. Provides context-based auto-filtering

Usage:
    class Strategy(TenantMixin, Base):
        __tablename__ = "strategies"
        name = Column(String(255))
        # organization_id is automatically added by TenantMixin
"""

from contextvars import ContextVar
from typing import Optional
import uuid

from sqlalchemy import Column, String, ForeignKey, Index, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, declared_attr
from sqlalchemy.sql import func


# Context variable for current tenant - thread-safe and async-safe
_current_tenant_id: ContextVar[Optional[str]] = ContextVar(
    'current_tenant_id',
    default=None
)


def get_current_tenant_id() -> Optional[str]:
    """Get the current tenant ID from context."""
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: Optional[str]) -> None:
    """Set the current tenant ID in context."""
    _current_tenant_id.set(tenant_id)


class TenantMixin:
    """
    Mixin class for multi-tenant models.

    Automatically adds:
    - organization_id column with FK to organizations table
    - Index on organization_id for query performance
    - Auto-sets organization_id on insert from context

    Every model that contains tenant-specific data should inherit from this.
    """

    @declared_attr
    def organization_id(cls):
        return Column(
            String(36),  # UUID as string for SQLite compatibility
            ForeignKey('organizations.id', ondelete='CASCADE'),
            nullable=False,
            index=True
        )

    @declared_attr
    def __table_args__(cls):
        """Add composite indexes for tenant-scoped queries."""
        existing_args = getattr(super(), '__table_args__', ())
        if isinstance(existing_args, dict):
            existing_args = (existing_args,)
        elif not isinstance(existing_args, tuple):
            existing_args = ()

        # Add tenant index
        tenant_index = Index(
            f'ix_{cls.__tablename__}_org_id',
            'organization_id'
        )

        return existing_args + (tenant_index,)


class TenantAwareSession:
    """
    Session wrapper that automatically filters queries by tenant.

    Usage:
        session = TenantAwareSession(db_session, tenant_id)
        strategies = session.query(Strategy).all()  # Auto-filtered
    """

    def __init__(self, session: Session, tenant_id: str):
        self._session = session
        self._tenant_id = tenant_id

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    def query(self, model):
        """Create a query auto-filtered by tenant if applicable."""
        q = self._session.query(model)
        if hasattr(model, 'organization_id'):
            q = q.filter(model.organization_id == self._tenant_id)
        return q

    def add(self, obj):
        """Add object with auto-set tenant if applicable."""
        if hasattr(obj, 'organization_id') and obj.organization_id is None:
            obj.organization_id = self._tenant_id
        self._session.add(obj)

    def add_all(self, objects):
        """Add multiple objects with auto-set tenant."""
        for obj in objects:
            self.add(obj)

    def delete(self, obj):
        """Delete object (tenant-check recommended before calling)."""
        if hasattr(obj, 'organization_id'):
            if obj.organization_id != self._tenant_id:
                raise PermissionError(
                    f"Cannot delete object from different tenant"
                )
        self._session.delete(obj)

    def commit(self):
        self._session.commit()

    def rollback(self):
        self._session.rollback()

    def flush(self):
        self._session.flush()

    def refresh(self, obj):
        self._session.refresh(obj)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        return False


def auto_set_tenant_id(mapper, connection, target):
    """
    SQLAlchemy event listener to auto-set organization_id on insert.

    Called before INSERT for any model with TenantMixin.
    """
    if hasattr(target, 'organization_id') and target.organization_id is None:
        tenant_id = get_current_tenant_id()
        if tenant_id:
            target.organization_id = tenant_id
        else:
            raise ValueError(
                f"Cannot insert {target.__class__.__name__} without tenant context. "
                "Set tenant with set_current_tenant_id() before database operations."
            )


def validate_tenant_access(mapper, connection, target):
    """
    SQLAlchemy event listener to validate tenant access on update/delete.

    Prevents cross-tenant data modification.
    """
    if hasattr(target, 'organization_id'):
        current_tenant = get_current_tenant_id()
        if current_tenant and target.organization_id != current_tenant:
            raise PermissionError(
                f"Cannot modify {target.__class__.__name__} from different tenant. "
                f"Object tenant: {target.organization_id}, Current tenant: {current_tenant}"
            )


def register_tenant_events(model_class):
    """
    Register tenant isolation events for a model.

    Call this for each tenant-scoped model after definition:
        register_tenant_events(Strategy)
    """
    event.listen(model_class, 'before_insert', auto_set_tenant_id)
    event.listen(model_class, 'before_update', validate_tenant_access)
    event.listen(model_class, 'before_delete', validate_tenant_access)


__all__ = [
    'TenantMixin',
    'TenantAwareSession',
    'get_current_tenant_id',
    'set_current_tenant_id',
    'register_tenant_events',
]
