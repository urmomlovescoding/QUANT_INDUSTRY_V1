"""
Authentication Module
=====================
JWT-based authentication for the SaaS platform.
"""

from .jwt_auth import (
    JWTAuth,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    verify_token,
    hash_password,
    verify_password,
    get_current_user,
    get_current_admin,
    require_permission,
)

from .dependencies import (
    get_db,
    get_tenant_session,
)

__all__ = [
    "JWTAuth",
    "TokenPayload",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "hash_password",
    "verify_password",
    "get_current_user",
    "get_current_admin",
    "get_current_user_optional",
    "require_permission",
    "get_db",
    "get_tenant_session",
]
