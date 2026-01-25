"""
Security Middleware for QUANT INDUSTRY API
Rate limiting, input validation, security headers
"""
import logging
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with per-endpoint and per-IP tracking
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_second: int = 10,
        burst_size: int = 20
    ):
        self.rpm = requests_per_minute
        self.rps = requests_per_second
        self.burst = burst_size
        self._requests: Dict[str, list] = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup_old_requests(self, key: str):
        """Remove requests older than 1 minute"""
        now = time.time()
        if now - self._last_cleanup > 60:
            # Full cleanup every minute
            for k in list(self._requests.keys()):
                self._requests[k] = [t for t in self._requests[k] if now - t < 60]
            self._last_cleanup = now
        else:
            # Just cleanup this key
            self._requests[key] = [t for t in self._requests[key] if now - t < 60]

    def is_allowed(self, client_id: str, endpoint: str = "") -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limits

        Returns:
            (allowed: bool, info: dict with remaining/retry_after)
        """
        key = f"{client_id}:{endpoint}" if endpoint else client_id
        now = time.time()

        self._cleanup_old_requests(key)
        requests = self._requests[key]

        # Check requests per second (last 1 second)
        recent_second = len([t for t in requests if now - t < 1])
        if recent_second >= self.rps:
            return False, {
                "remaining": 0,
                "retry_after": 1,
                "limit": self.rps,
                "window": "second"
            }

        # Check requests per minute
        if len(requests) >= self.rpm:
            oldest = min(requests) if requests else now
            retry_after = max(1, int(60 - (now - oldest)))
            return False, {
                "remaining": 0,
                "retry_after": retry_after,
                "limit": self.rpm,
                "window": "minute"
            }

        # Check burst
        recent_burst = len([t for t in requests if now - t < 5])
        if recent_burst >= self.burst:
            return False, {
                "remaining": 0,
                "retry_after": 5,
                "limit": self.burst,
                "window": "burst"
            }

        # Allowed - record this request
        self._requests[key].append(now)

        return True, {
            "remaining": self.rpm - len(requests) - 1,
            "limit": self.rpm,
            "window": "minute"
        }


# Global rate limiter instance - generous limits for development/testing
_rate_limiter = RateLimiter(
    requests_per_minute=600,  # 10 requests per second average
    requests_per_second=50,   # Allow bursts
    burst_size=100            # Large burst allowance
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on API requests
    """

    # Endpoints exempt from rate limiting
    EXEMPT_PATHS = {
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/health",
        "/api/system/health",
        "/favicon.ico"
    }

    # Stricter limits for certain endpoints
    STRICT_PATHS = {
        "/api/backtest/run": 5,  # 5 per minute
        "/api/brain-v6/train": 2,  # 2 per minute
        "/api/rl/train": 2,
        "/api/dl/train": 2,
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip rate limiting for exempt paths
        if path in self.EXEMPT_PATHS or path.startswith("/ws"):
            return await call_next(request)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for test clients (development/testing)
        if client_ip == "testclient" or client_ip.startswith("127.") or client_ip == "localhost":
            return await call_next(request)

        # Check for forwarded IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        # Check for strict path limits
        for strict_path, limit in self.STRICT_PATHS.items():
            if path.startswith(strict_path):
                strict_limiter = RateLimiter(requests_per_minute=limit, requests_per_second=1, burst_size=2)
                allowed, info = strict_limiter.is_allowed(client_ip, strict_path)
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "Rate limit exceeded for resource-intensive endpoint",
                            "retry_after": info["retry_after"],
                            "limit": info["limit"]
                        },
                        headers={
                            "Retry-After": str(info["retry_after"]),
                            "X-RateLimit-Limit": str(info["limit"]),
                            "X-RateLimit-Remaining": "0"
                        }
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
                    "retry_after": info["retry_after"]
                },
                headers={
                    "Retry-After": str(info["retry_after"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + info["retry_after"])
                }
            )

        # Process request and add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Cache control for API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response


class InputSanitizer:
    """
    Input validation and sanitization utilities
    """

    # Pattern for valid stock symbols
    SYMBOL_PATTERN = re.compile(r'^[A-Za-z]{1,5}$')

    # Pattern for valid dates
    DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    # Max lengths for various inputs
    MAX_SYMBOL_LENGTH = 10
    MAX_QUERY_LENGTH = 500
    MAX_BODY_SIZE = 1024 * 1024  # 1MB

    @classmethod
    def validate_symbol(cls, symbol: str) -> tuple[bool, str]:
        """Validate stock symbol"""
        if not symbol:
            return False, "Symbol is required"
        if len(symbol) > cls.MAX_SYMBOL_LENGTH:
            return False, f"Symbol too long (max {cls.MAX_SYMBOL_LENGTH})"
        # Allow alphanumeric and some special chars for futures/options
        if not re.match(r'^[A-Za-z0-9.\-/]{1,10}$', symbol):
            return False, "Invalid symbol format"
        return True, symbol.upper()

    @classmethod
    def validate_date(cls, date_str: str) -> tuple[bool, str]:
        """Validate date string"""
        if not cls.DATE_PATTERN.match(date_str):
            return False, "Invalid date format (use YYYY-MM-DD)"
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True, date_str
        except ValueError:
            return False, "Invalid date"

    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 500) -> str:
        """Sanitize string input"""
        if not value:
            return ""
        # Remove potential XSS
        value = re.sub(r'<[^>]*>', '', value)
        # Remove potential SQL injection characters
        value = re.sub(r'[;\'"\\]', '', value)
        # Truncate
        return value[:max_length]


def get_cors_origins(environment: str = "development") -> list:
    """
    Get CORS origins based on environment

    Args:
        environment: 'development', 'staging', or 'production'
    """
    if environment == "production":
        return [
            "https://quantindustry.com",
            "https://www.quantindustry.com",
            "https://app.quantindustry.com"
        ]
    elif environment == "staging":
        return [
            "https://staging.quantindustry.com",
            "http://localhost:3000",
            "http://localhost:5173"
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
