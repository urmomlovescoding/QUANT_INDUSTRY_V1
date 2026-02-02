"""
JWT Authentication Service
==========================
Handles token generation, validation, and user authentication.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
import uuid

from fastapi import Depends, HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from database.models import User, Organization, RefreshToken
from database.models.tenant import set_current_tenant_id, get_current_tenant_id

logger = logging.getLogger(__name__)

# Configuration - SECURITY: JWT_SECRET_KEY must be set in environment
_jwt_secret = os.getenv("JWT_SECRET_KEY")
if not _jwt_secret:
    logger.warning(
        "JWT_SECRET_KEY not set! Using development-only fallback. "
        "Set JWT_SECRET_KEY environment variable for production."
    )
    _jwt_secret = "dev-only-insecure-key-not-for-production"
SECRET_KEY = _jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing - using argon2 as primary (more secure and no bcrypt compatibility issues)
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # user_id
    org: str  # organization_id
    role: str
    email: str
    jti: str  # JWT ID for revocation
    type: str  # access or refresh
    exp: datetime
    iat: datetime


class TokenResponse(BaseModel):
    """Token response structure."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user: User,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user: User model instance
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = TokenPayload(
        sub=user.id,
        org=user.organization_id,
        role=user.role.value,
        email=user.email,
        jti=str(uuid.uuid4()),
        type="access",
        exp=expire,
        iat=datetime.utcnow(),
    )

    return jwt.encode(payload.model_dump(), SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    user: User,
    expires_delta: Optional[timedelta] = None
) -> tuple[str, str]:
    """
    Create a JWT refresh token for a user.

    Args:
        user: User model instance
        expires_delta: Optional custom expiration time

    Returns:
        (token, jti) - jti is stored in DB for revocation
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    jti = str(uuid.uuid4())

    payload = TokenPayload(
        sub=user.id,
        org=user.organization_id,
        role=user.role.value,
        email=user.email,
        jti=jti,
        type="refresh",
        exp=expire,
        iat=datetime.utcnow(),
    )

    token = jwt.encode(payload.model_dump(), SECRET_KEY, algorithm=ALGORITHM)
    return token, jti


def verify_token(token: str, token_type: str = "access") -> TokenPayload:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenPayload with decoded data

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)

        if token_data.type != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return token_data

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.warning(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class JWTAuth:
    """
    JWT Authentication handler class.

    Provides methods for user authentication and token management.
    """

    def __init__(
        self,
        secret_key: str = SECRET_KEY,
        algorithm: str = ALGORITHM,
        access_token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days: int = REFRESH_TOKEN_EXPIRE_DAYS
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    def create_tokens(self, user: User) -> TokenResponse:
        """Create both access and refresh tokens for a user."""
        access_token = create_access_token(user)
        refresh_token, jti = create_refresh_token(user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60,
            user=user.to_dict()
        )

    def verify_access_token(self, token: str) -> TokenPayload:
        """Verify an access token."""
        return verify_token(token, "access")

    def verify_refresh_token(self, token: str) -> TokenPayload:
        """Verify a refresh token."""
        return verify_token(token, "refresh")


# FastAPI Dependencies

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    Also sets the tenant context for the request.

    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    token_data = verify_token(token, "access")

    # Import here to avoid circular imports
    from database.connection import get_session_factory

    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        user = session.query(User).filter(
            User.id == token_data.sub,
            User.is_active == True
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Set tenant context for this request
        set_current_tenant_id(user.organization_id)

        # Store user in request state for later access
        request.state.user = user
        request.state.token_data = token_data

        return user
    finally:
        session.close()


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[User]:
    """
    FastAPI dependency to optionally get the current user.

    Returns None if not authenticated instead of raising an exception.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


async def get_current_admin(
    user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency to require an admin user.

    Usage:
        @router.post("/admin-only")
        async def admin_route(user: User = Depends(get_current_admin)):
            ...
    """
    from database.models import UserRole

    if user.role not in [UserRole.OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_permission(permission: str) -> Callable:
    """
    Factory for creating permission-checking dependencies.

    Usage:
        @router.post("/strategies")
        async def create_strategy(
            user: User = Depends(require_permission("strategies:write"))
        ):
            ...
    """
    async def permission_checker(
        user: User = Depends(get_current_user)
    ) -> User:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return user

    return permission_checker


# Global auth instance
_auth = JWTAuth()


def get_auth() -> JWTAuth:
    """Get the global JWTAuth instance."""
    return _auth
