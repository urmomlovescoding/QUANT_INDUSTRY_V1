"""
Security Middleware for QUANT INDUSTRY API
Rate limiting, input validation, security headers
"""
import logging
import os
import re
import time
import threading
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with per-endpoint and per-IP tracking.

    Features:
    - Per-second, per-minute, and burst rate limiting
    - Automatic cleanup of expired entries to prevent memory leaks
    - Thread-safe operations
    - Bounded memory usage with max tracked clients limit
    """

    # Maximum number of unique client keys to track (prevents memory exhaustion)
    MAX_TRACKED_CLIENTS = 10000

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_second: int = 10,
        burst_size: int = 20,
    ):
        self.rpm = requests_per_minute
        self.rps = requests_per_second
        self.burst = burst_size
        self._requests: Dict[str, list] = defaultdict(list)
        self._last_cleanup = time.time()
        self._lock = threading.Lock()

    def _cleanup(self):
        """Remove expired entries and evict oldest clients if over limit."""
        now = time.time()

        # Only run full cleanup periodically (every 30 seconds)
        if now - self._last_cleanup < 30:
            return

        with self._lock:
            # Remove expired timestamps from all keys
            keys_to_delete = []
            for key in list(self._requests.keys()):
                self._requests[key] = [t for t in self._requests[key] if now - t < 60]
                if not self._requests[key]:
                    keys_to_delete.append(key)

            # Remove empty keys
            for key in keys_to_delete:
                del self._requests[key]

            # Evict oldest entries if over limit
            if len(self._requests) > self.MAX_TRACKED_CLIENTS:
                # Find keys with oldest last request and remove them
                sorted_keys = sorted(
                    self._requests.keys(),
                    key=lambda k: max(self._requests[k]) if self._requests[k] else 0,
                )
                excess = len(self._requests) - self.MAX_TRACKED_CLIENTS
                for key in sorted_keys[:excess]:
                    del self._requests[key]

            self._last_cleanup = now

    def _cleanup_key(self, key: str):
        """Remove expired entries for a specific key."""
        now = time.time()
        self._requests[key] = [t for t in self._requests[key] if now - t < 60]

    def is_allowed(self, client_id: str, endpoint: str = "") -> Tuple[bool, dict]:
        """
        Check if request is allowed under rate limits.

        Args:
            client_id: Client identifier (usually IP address)
            endpoint: Optional endpoint path for per-endpoint limiting

        Returns:
            Tuple of (allowed, info_dict) where info_dict contains
            remaining requests, retry_after, limit, and window.
        """
        key = f"{client_id}:{endpoint}" if endpoint else client_id
        now = time.time()

        # Run periodic cleanup
        self._cleanup()

        # Clean up this specific key
        self._cleanup_key(key)
        requests = self._requests[key]

        # Check requests per second (last 1 second)
        recent_second = sum(1 for t in requests if now - t < 1)
        if recent_second >= self.rps:
            return False, {
                "remaining": 0,
                "retry_after": 1,
                "limit": self.rps,
                "window": "second",
            }

        # Check requests per minute
        if len(requests) >= self.rpm:
            oldest = min(requests) if requests else now
            retry_after = max(1, int(60 - (now - oldest)))
            return False, {
                "remaining": 0,
                "retry_after": retry_after,
                "limit": self.rpm,
                "window": "minute",
            }

        # Check burst (5-second window)
        recent_burst = sum(1 for t in requests if now - t < 5)
        if recent_burst >= self.burst:
            return False, {
                "remaining": 0,
                "retry_after": 5,
                "limit": self.burst,
                "window": "burst",
            }

        # Allowed - record this request
        self._requests[key].append(now)

        return True, {
            "remaining": self.rpm - len(requests) - 1,
            "limit": self.rpm,
            "window": "minute",
        }

    @property
    def tracked_clients(self) -> int:
        """Number of currently tracked client keys."""
        return len(self._requests)


# Global rate limiter instance - generous limits for development/testing
_rate_limiter = RateLimiter(
    requests_per_minute=600,  # 10 requests per second average
    requests_per_second=50,  # Allow bursts
    burst_size=100,  # Large burst allowance
)

# Persistent strict limiters (one per strict path, not per request)
_strict_limiters: Dict[str, RateLimiter] = {}


def _get_strict_limiter(path: str, limit: int) -> RateLimiter:
    """Get or create a persistent rate limiter for a strict path."""
    if path not in _strict_limiters:
        _strict_limiters[path] = RateLimiter(
            requests_per_minute=limit,
            requests_per_second=1,
            burst_size=2,
        )
    return _strict_limiters[path]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on API requests.

    Features:
    - Exempts health check and documentation endpoints
    - Stricter limits for resource-intensive endpoints (training, backtesting)
    - Skips rate limiting for local development clients
    - Adds standard rate limit headers to responses
    """

    # Endpoints exempt from rate limiting
    EXEMPT_PATHS = frozenset({
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/health",
        "/api/system/health",
        "/favicon.ico",
    })

    # Stricter limits for resource-intensive endpoints (requests per minute)
    STRICT_PATHS = {
        "/api/backtest/run": 5,
        "/api/brain-v6/train": 2,
        "/api/rl/train": 2,
        "/api/dl/train": 2,
        "/api/monte-carlo/run": 5,
        "/api/evolution/evolve": 3,
        "/api/kill-switch/activate": 3,
        "/api/kill-switch/deactivate": 3,
        "/api/orders": 30,
        "/api/broker/order": 30,
        "/api/settings/api-keys": 5,
        "/api/ai/confirm-trade": 20,
        # Auth endpoints — strict rate limits to prevent brute force
        "/api/auth/login": 10,
        "/api/auth/register": 5,
        "/api/auth/refresh": 30,
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip rate limiting for exempt paths and WebSocket connections
        if path in self.EXEMPT_PATHS or path.startswith("/ws"):
            return await call_next(request)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for local development clients
        if client_ip in ("testclient", "localhost") or client_ip.startswith("127."):
            return await call_next(request)

        # Check for forwarded IP (behind a reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take only the first IP (client IP), ignore proxy chain
            client_ip = forwarded.split(",")[0].strip()

        # Check strict path limits using persistent limiters
        for strict_path, limit in self.STRICT_PATHS.items():
            if path.startswith(strict_path):
                strict_limiter = _get_strict_limiter(strict_path, limit)
                allowed, info = strict_limiter.is_allowed(client_ip, strict_path)
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "Rate limit exceeded for resource-intensive endpoint",
                            "retry_after": info["retry_after"],
                            "limit": info["limit"],
                        },
                        headers={
                            "Retry-After": str(info["retry_after"]),
                            "X-RateLimit-Limit": str(info["limit"]),
                            "X-RateLimit-Remaining": "0",
                        },
                    )

        # Standard rate limiting
        allowed, info = _rate_limiter.is_allowed(client_ip)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip} on {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please retry after {info['retry_after']} seconds.",
                    "retry_after": info["retry_after"],
                },
                headers={
                    "Retry-After": str(info["retry_after"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + info["retry_after"]),
                },
            )

        # Process request and add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Adds standard security headers including:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    - Content-Security-Policy: Basic CSP for API responses
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # Disabled per modern best practice
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:"

        # Cache control for API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response


class InputSanitizer:
    """
    Input validation and sanitization utilities.

    Provides methods for validating common input types used in
    trading platform operations: symbols, dates, numeric ranges.
    """

    # Pattern for valid stock symbols (1-5 uppercase letters)
    SYMBOL_PATTERN = re.compile(r"^[A-Za-z]{1,5}$")

    # Extended pattern for futures/options symbols (includes digits, dots, dashes, carets)
    EXTENDED_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9.\-/^]{1,10}$")

    # Pattern for valid dates
    DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    # Max lengths for various inputs
    MAX_SYMBOL_LENGTH = 10
    MAX_QUERY_LENGTH = 500
    MAX_BODY_SIZE = 1024 * 1024  # 1MB

    @classmethod
    def validate_symbol(cls, symbol: str) -> Tuple[bool, str]:
        """
        Validate a stock/futures/options symbol.

        Args:
            symbol: The symbol string to validate

        Returns:
            Tuple of (is_valid, result_or_error_message)
        """
        if not symbol:
            return False, "Symbol is required"

        symbol = symbol.strip()

        if len(symbol) > cls.MAX_SYMBOL_LENGTH:
            return False, f"Symbol too long (max {cls.MAX_SYMBOL_LENGTH})"

        # Allow alphanumeric and special chars for futures/options (^VIX, ES/H24, etc.)
        if not cls.EXTENDED_SYMBOL_PATTERN.match(symbol):
            return False, "Invalid symbol format"

        return True, symbol.upper()

    @classmethod
    def validate_date(cls, date_str: str) -> Tuple[bool, str]:
        """
        Validate a date string in YYYY-MM-DD format.

        Args:
            date_str: Date string to validate

        Returns:
            Tuple of (is_valid, result_or_error_message)
        """
        if not date_str:
            return False, "Date is required"

        if not cls.DATE_PATTERN.match(date_str):
            return False, "Invalid date format (use YYYY-MM-DD)"

        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d")
            # Reject dates too far in the past or future
            now = datetime.now()
            if parsed.year < 1990:
                return False, "Date too far in the past (minimum 1990)"
            if parsed > now.replace(year=now.year + 2):
                return False, "Date too far in the future"
            return True, date_str
        except ValueError:
            return False, "Invalid date"

    @classmethod
    def validate_numeric(
        cls,
        value: float,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        name: str = "value",
    ) -> Tuple[bool, str]:
        """
        Validate a numeric value within optional bounds.

        Args:
            value: The numeric value to validate
            min_val: Optional minimum value (inclusive)
            max_val: Optional maximum value (inclusive)
            name: Name of the field for error messages

        Returns:
            Tuple of (is_valid, error_message_if_invalid)
        """
        if not isinstance(value, (int, float)):
            return False, f"{name} must be a number"

        if min_val is not None and value < min_val:
            return False, f"{name} must be >= {min_val}"

        if max_val is not None and value > max_val:
            return False, f"{name} must be <= {max_val}"

        return True, ""

    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 500) -> str:
        """
        Sanitize string input by removing potentially dangerous characters.

        Args:
            value: The string to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not value:
            return ""

        # Remove potential XSS - strip HTML tags
        value = re.sub(r"<[^>]*>", "", value)

        # Remove null bytes
        value = value.replace("\x00", "")

        # Truncate to max length
        return value[:max_length]


def get_cors_origins(environment: Optional[str] = None) -> list:
    """
    Get CORS origins based on environment.

    If environment is not specified, reads from the ENVIRONMENT
    environment variable (defaults to 'development').

    Args:
        environment: 'development', 'staging', or 'production'

    Returns:
        List of allowed CORS origin URLs
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment == "production":
        return [
            "https://quantindustry.com",
            "https://www.quantindustry.com",
            "https://app.quantindustry.com",
        ]
    elif environment == "staging":
        return [
            "https://staging.quantindustry.com",
            "http://localhost:3000",
            "http://localhost:5173",
        ]
    else:  # development
        return [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://localhost:3003",
            "http://localhost:3004",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce authentication on state-changing API endpoints.

    Protects POST/PUT/DELETE endpoints while allowing GET (read-only) access.
    Uses JWT Bearer tokens from the auth.jwt_auth module when AUTH_REQUIRED=true.
    Localhost requests bypass auth in development mode for backward compatibility.

    Enable by setting environment variable: AUTH_REQUIRED=true

    Critical endpoints (kill switch, orders, API key changes) are ALWAYS protected
    regardless of AUTH_REQUIRED setting.
    """

    # Endpoints that are ALWAYS exempt from auth (public)
    PUBLIC_PATHS = frozenset({
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/health",
        "/api/system/health",
        "/api/system/status",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/favicon.ico",
    })

    # Critical endpoints that ALWAYS require auth, even in dev mode
    CRITICAL_PATHS = frozenset({
        "/api/kill-switch/activate",
        "/api/kill-switch/deactivate",
        "/api/orders",
        "/api/broker/order",
        "/api/settings/api-keys",
        "/api/ai/confirm-trade",
    })

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        # Always allow public paths
        if path in self.PUBLIC_PATHS or path.startswith("/ws"):
            return await call_next(request)

        # Allow all GET/HEAD/OPTIONS requests (read-only)
        if method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Check if auth is required
        auth_required = os.getenv("AUTH_REQUIRED", "false").lower() == "true"
        is_critical = any(path.startswith(cp) for cp in self.CRITICAL_PATHS)

        # In dev mode, only protect critical endpoints
        if not auth_required and not is_critical:
            return await call_next(request)

        # For critical or auth-required endpoints, validate Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required",
                    "detail": f"Bearer token required for {method} {path}",
                    "code": "AUTH_REQUIRED",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]  # Strip "Bearer "

        try:
            from auth.jwt_auth import verify_token
            token_data = verify_token(token, "access")

            # Store user info in request state for downstream use
            request.state.user_id = token_data.sub
            request.state.org_id = token_data.org
            request.state.user_role = token_data.role

        except Exception:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid or expired token",
                    "detail": "Please re-authenticate",
                    "code": "TOKEN_INVALID",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


def get_security_middleware_stack() -> list:
    """
    Return the recommended middleware stack in order.

    Usage in main.py:
        from middleware.security import get_security_middleware_stack
        for middleware_cls in get_security_middleware_stack():
            app.add_middleware(middleware_cls)
    """
    return [
        SecurityHeadersMiddleware,
        RateLimitMiddleware,
        AuthenticationMiddleware,
    ]
