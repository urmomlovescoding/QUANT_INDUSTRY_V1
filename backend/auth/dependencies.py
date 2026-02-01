"""
Authentication Dependencies
===========================
FastAPI dependencies for database sessions and tenant context.
"""

import logging
from typing import Generator, Optional
from contextlib import contextmanager

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database.models.tenant import TenantAwareSession, get_current_tenant_id

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session.

    Usage:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            ...
    """
    from database.connection import get_session_factory

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_session(
    db: Session = Depends(get_db)
) -> TenantAwareSession:
    """
    FastAPI dependency for tenant-aware database session.

    Automatically filters queries by the current tenant.

    Usage:
        @router.get("/strategies")
        async def get_strategies(
            session: TenantAwareSession = Depends(get_tenant_session)
        ):
            # Automatically filtered by organization_id
            strategies = session.query(Strategy).all()
            ...
    """
    tenant_id = get_current_tenant_id()

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant context not set. Authentication required.",
        )

    return TenantAwareSession(db, tenant_id)


async def get_request_id(request: Request) -> Optional[str]:
    """Get or generate a request ID for tracing."""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
    return request_id


@contextmanager
def tenant_context(tenant_id: str):
    """
    Context manager for temporarily setting tenant context.

    Useful for background tasks or testing.

    Usage:
        with tenant_context("org-123"):
            # All queries in this block are scoped to org-123
            strategies = db.query(Strategy).all()
    """
    from database.models.tenant import set_current_tenant_id, get_current_tenant_id

    previous_tenant = get_current_tenant_id()
    set_current_tenant_id(tenant_id)
    try:
        yield
    finally:
        set_current_tenant_id(previous_tenant)
