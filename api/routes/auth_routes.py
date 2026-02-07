"""
Authentication Routes (Lightweight)
====================================
Simple JWT auth for the local trading platform.
No database dependency — uses in-memory user store.
"""

import os
import logging
import uuid
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Secret key for token signing
_secret = os.getenv("JWT_SECRET_KEY", "quant-industry-local-dev-secret-key")

# In-memory user store (persists for server lifetime)
_users: dict[str, dict] = {}


# ============== Models ==============

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    organization_name: str = Field(..., min_length=2)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    organization_id: str
    organization_name: str
    is_active: bool


class AuthResponse(BaseModel):
    tokens: TokenResponse
    user: UserResponse


# ============== Helpers ==============

def _hash_password(password: str) -> str:
    """Simple password hashing."""
    return hashlib.sha256(f"{_secret}:{password}".encode()).hexdigest()


def _create_token(user_id: str, email: str, expires_minutes: int = 1440) -> str:
    """Create a simple signed token (base64-encoded JSON with HMAC)."""
    import base64
    import json

    payload = {
        "sub": user_id,
        "email": email,
        "exp": int(time.time()) + (expires_minutes * 60),
        "iat": int(time.time()),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(_secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def _make_auth_response(user: dict) -> AuthResponse:
    """Build auth response from user dict."""
    access_token = _create_token(user["id"], user["email"], expires_minutes=1440)
    refresh_token = _create_token(user["id"], user["email"], expires_minutes=10080)

    return AuthResponse(
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=86400,
        ),
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            role="owner",
            organization_id=user["org_id"],
            organization_name=user.get("org_name", "Trading Desk"),
            is_active=True,
        ),
    )


# ============== Endpoints ==============

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Authenticate user and return tokens."""
    email = request.email.lower()
    password_hash = _hash_password(request.password)

    # Check existing user
    if email in _users:
        user = _users[email]
        if user["password_hash"] != password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        logger.info(f"User logged in: {email}")
        return _make_auth_response(user)

    # Auto-register on first login (local dev convenience)
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "full_name": email.split("@")[0].replace(".", " ").title(),
        "password_hash": password_hash,
        "org_id": str(uuid.uuid4()),
        "org_name": "Trading Desk",
        "created_at": datetime.utcnow().isoformat(),
    }
    _users[email] = user
    logger.info(f"Auto-registered new user: {email}")
    return _make_auth_response(user)


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register a new user."""
    email = request.email.lower()

    if email in _users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "full_name": request.full_name,
        "password_hash": _hash_password(request.password),
        "org_id": str(uuid.uuid4()),
        "org_name": request.organization_name,
        "created_at": datetime.utcnow().isoformat(),
    }
    _users[email] = user
    logger.info(f"Registered new user: {email}")
    return _make_auth_response(user)


@router.post("/logout")
async def logout():
    """Logout (token invalidation is client-side for local dev)."""
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user():
    """Get current user info (simplified — returns first registered user)."""
    if not _users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = next(iter(_users.values()))
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        role="owner",
        organization_id=user["org_id"],
        organization_name=user.get("org_name", "Trading Desk"),
        is_active=True,
    )


@router.post("/refresh")
async def refresh_token(request: dict):
    """Refresh access token."""
    # For local dev, just issue a new token for the first user
    if not _users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = next(iter(_users.values()))
    access_token = _create_token(user["id"], user["email"], expires_minutes=1440)
    return TokenResponse(
        access_token=access_token,
        refresh_token=request.get("refresh_token", ""),
        token_type="bearer",
        expires_in=86400,
    )


@router.post("/change-password")
async def change_password():
    """Change password (stub for local dev)."""
    return {"message": "Password changed successfully"}


@router.get("/ping")
async def auth_ping():
    """Fast auth health check."""
    return {"status": "ok", "auth": "available"}
