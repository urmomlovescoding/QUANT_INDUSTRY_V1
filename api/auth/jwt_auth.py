"""
JWT Authentication Module
Secure token-based authentication for the API.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from functools import wraps
import os
import logging

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    is_admin: bool = False
    token_type: str = "access"
    exp: Optional[datetime] = None


class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class JWTAuth:
    """
    JWT Authentication handler.
    
    Usage:
        auth = JWTAuth()
        
        # Create tokens
        tokens = auth.create_tokens(user_id=1, username="trader")
        
        # Verify token
        payload = auth.verify_token(token)
    """
    
    def __init__(
        self,
        secret_key: str = SECRET_KEY,
        algorithm: str = ALGORITHM,
        access_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_expire_days: int = REFRESH_TOKEN_EXPIRE_DAYS
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_days = refresh_expire_days
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create an access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a refresh token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_tokens(
        self,
        user_id: int,
        username: str,
        email: str = None,
        is_admin: bool = False
    ) -> Token:
        """Create both access and refresh tokens."""
        data = {
            "sub": str(user_id),
            "username": username,
            "email": email,
            "is_admin": is_admin
        }
        
        access_token = self.create_access_token(data)
        refresh_token = self.create_refresh_token(data)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_expire_minutes * 60
        )
    
    def verify_token(self, token: str, token_type: str = "access") -> TokenData:
        """Verify and decode a token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != token_type:
                raise JWTError(f"Invalid token type. Expected {token_type}")
            
            user_id = payload.get("sub")
            if user_id is None:
                raise JWTError("Token missing subject")
            
            return TokenData(
                user_id=int(user_id),
                username=payload.get("username"),
                email=payload.get("email"),
                is_admin=payload.get("is_admin", False),
                token_type=payload.get("type", "access"),
                exp=datetime.fromtimestamp(payload.get("exp", 0))
            )
            
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            raise
    
    def refresh_access_token(self, refresh_token: str) -> Token:
        """Create new tokens using a refresh token."""
        token_data = self.verify_token(refresh_token, token_type="refresh")
        
        return self.create_tokens(
            user_id=token_data.user_id,
            username=token_data.username,
            email=token_data.email,
            is_admin=token_data.is_admin
        )


# Global auth instance
_auth = JWTAuth()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create an access token."""
    return _auth.create_access_token(data, expires_delta)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a refresh token."""
    return _auth.create_refresh_token(data, expires_delta)


def decode_token(token: str) -> TokenData:
    """Decode and verify a token."""
    return _auth.verify_token(token)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    FastAPI dependency to get current authenticated user.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: TokenData = Depends(get_current_user)):
            return {"user_id": user.user_id}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        token_data = _auth.verify_token(token, token_type="access")
        return token_data
    except JWTError:
        raise credentials_exception


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    FastAPI dependency to get current active (non-disabled) user.
    
    In production, this would check if user is disabled/banned.
    """
    # Add additional checks here (e.g., user not banned)
    return current_user


async def get_current_admin(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    FastAPI dependency to require admin privileges.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def require_auth(func):
    """
    Decorator to require authentication on a route.
    
    Usage:
        @app.get("/protected")
        @require_auth
        async def protected_route(request: Request):
            user = request.state.user
            return {"user_id": user.user_id}
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = auth_header.split(" ")[1]
        try:
            token_data = _auth.verify_token(token, token_type="access")
            request.state.user = token_data
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return await func(request, *args, **kwargs)
    
    return wrapper


def require_admin(func):
    """
    Decorator to require admin privileges on a route.
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # First check auth
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        try:
            token_data = _auth.verify_token(token, token_type="access")
            if not token_data.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin privileges required"
                )
            request.state.user = token_data
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        return await func(request, *args, **kwargs)
    
    return wrapper


# Password utilities
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)
