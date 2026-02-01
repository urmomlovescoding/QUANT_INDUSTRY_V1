"""
Authentication Routes
=====================
API endpoints for user authentication and session management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth.jwt_auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    JWTAuth,
)
from auth.dependencies import get_db
from database.models import (
    User, Organization, RefreshToken, UserRole, OrgTier, OrgStatus,
    AuditLog, AuditAction,
)
from database.models.tenant import set_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# ============== Request/Response Models ==============

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    organization_name: str = Field(..., min_length=2)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User information response."""
    id: str
    email: str
    full_name: Optional[str]
    role: str
    organization_id: str
    organization_name: str
    is_active: bool


class AuthResponse(BaseModel):
    """Full authentication response."""
    tokens: TokenResponse
    user: UserResponse


# ============== Helper Functions ==============

def generate_org_slug(name: str, db: Session) -> str:
    """Generate a unique organization slug from name."""
    import re
    import uuid

    # Convert to lowercase, replace spaces with hyphens, remove special chars
    base_slug = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-'))
    base_slug = base_slug[:50]  # Limit length

    # Check uniqueness
    slug = base_slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def create_audit_log(
    db: Session,
    action: AuditAction,
    user: Optional[User] = None,
    org_id: Optional[str] = None,
    resource_type: str = "user",
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra_data: dict = None
):
    """Create an audit log entry."""
    log = AuditLog.log(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=org_id or (user.organization_id if user else None),
        user_id=user.id if user else None,
        actor_type="user",
        actor_email=user.email if user else None,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=extra_data,
    )
    db.add(log)


# ============== Routes ==============

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user and organization.

    Creates a new organization and user account.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create organization
    org = Organization(
        name=data.organization_name,
        slug=generate_org_slug(data.organization_name, db),
        tier=OrgTier.FREE,
        status=OrgStatus.ACTIVE,
    )
    db.add(org)
    db.flush()  # Get org.id

    # Create user
    user = User(
        organization_id=org.id,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole.OWNER,  # First user is owner
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.flush()  # Get user.id

    # Create tokens
    access_token = create_access_token(user)
    refresh_token, jti = create_refresh_token(user)

    # Store refresh token
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_password(refresh_token),
        jti=jti,
        expires_at=datetime.utcnow() + timedelta(days=JWTAuth().refresh_token_expire_days),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(refresh_token_record)

    # Audit log
    create_audit_log(
        db,
        AuditAction.USER_CREATED,
        user=user,
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_data={"registration": True}
    )

    db.commit()

    logger.info(f"New user registered: {user.email} (org: {org.slug})")

    return AuthResponse(
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=JWTAuth().access_token_expire_minutes * 60
        ),
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            organization_id=org.id,
            organization_name=org.name,
            is_active=user.is_active,
        )
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return tokens.
    """
    # Find user by email
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not user.password_hash:
        # Log failed attempt
        logger.warning(f"Login failed: user not found - {data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(data.password, user.password_hash):
        # Log failed attempt
        create_audit_log(
            db,
            AuditAction.AUTH_LOGIN_FAILED,
            user=user,
            resource_id=user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()

        logger.warning(f"Login failed: wrong password - {data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Get organization
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org or org.status != OrgStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is suspended or cancelled"
        )

    # Create tokens
    access_token = create_access_token(user)
    refresh_token, jti = create_refresh_token(user)

    # Store refresh token
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_password(refresh_token),
        jti=jti,
        expires_at=datetime.utcnow() + timedelta(days=JWTAuth().refresh_token_expire_days),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(refresh_token_record)

    # Update user login info
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host if request.client else None
    user.login_count = (user.login_count or 0) + 1

    # Audit log
    create_audit_log(
        db,
        AuditAction.AUTH_LOGIN,
        user=user,
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    db.commit()

    logger.info(f"User logged in: {user.email}")

    return AuthResponse(
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=JWTAuth().access_token_expire_minutes * 60
        ),
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            organization_id=org.id,
            organization_name=org.name,
            is_active=user.is_active,
        )
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    data: RefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    """
    # Verify refresh token
    token_data = verify_token(data.refresh_token, "refresh")

    # Find user
    user = db.query(User).filter(
        User.id == token_data.sub,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Check if refresh token is revoked
    refresh_record = db.query(RefreshToken).filter(
        RefreshToken.jti == token_data.jti,
        RefreshToken.revoked_at == None
    ).first()

    if not refresh_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked"
        )

    # Create new access token
    access_token = create_access_token(user)

    # Optionally rotate refresh token
    new_refresh_token, new_jti = create_refresh_token(user)

    # Revoke old refresh token
    refresh_record.revoked_at = datetime.utcnow()
    refresh_record.revoked_reason = "rotated"

    # Store new refresh token
    new_refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_password(new_refresh_token),
        jti=new_jti,
        expires_at=datetime.utcnow() + timedelta(days=JWTAuth().refresh_token_expire_days),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(new_refresh_record)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=JWTAuth().access_token_expire_minutes * 60
    )


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user and revoke all refresh tokens.
    """
    # Revoke all user's refresh tokens
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at == None
    ).update({
        RefreshToken.revoked_at: datetime.utcnow(),
        RefreshToken.revoked_reason: "logout"
    })

    # Audit log
    create_audit_log(
        db,
        AuditAction.AUTH_LOGOUT,
        user=user,
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    db.commit()

    logger.info(f"User logged out: {user.email}")

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user's information.
    """
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        organization_id=org.id if org else user.organization_id,
        organization_name=org.name if org else "Unknown",
        is_active=user.is_active,
    )


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/change-password")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change the current user's password.
    """
    # Re-query user in current session to enable modifications
    db_user = db.query(User).filter(User.id == user.id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not verify_password(data.current_password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    db_user.password_hash = hash_password(data.new_password)

    # Revoke all refresh tokens (force re-login)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == db_user.id,
        RefreshToken.revoked_at == None
    ).update({
        RefreshToken.revoked_at: datetime.utcnow(),
        RefreshToken.revoked_reason: "password_change"
    })

    # Audit log
    create_audit_log(
        db,
        AuditAction.AUTH_PASSWORD_CHANGE,
        user=db_user,
        resource_id=db_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    db.commit()

    logger.info(f"Password changed for user: {db_user.email}")

    return {"message": "Password changed successfully. Please login again."}
