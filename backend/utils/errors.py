"""
Standardized Error Handling for QUANT INDUSTRY API
"""
import logging
import traceback
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors"""
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"ERR_{status_code}"
        self.details = details or {}
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found"""
    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND"
        )


class ValidationError(APIError):
    """Input validation failed"""
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details
        )


class ServiceUnavailableError(APIError):
    """External service unavailable"""
    def __init__(self, service: str, reason: Optional[str] = None):
        message = f"{service} service unavailable"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(
            message=message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            details={"service": service}
        )


class RateLimitError(APIError):
    """Rate limit exceeded"""
    def __init__(self, provider: str, retry_after: Optional[int] = None):
        super().__init__(
            message=f"Rate limit exceeded for {provider}",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"provider": provider, "retry_after": retry_after}
        )


class DataError(APIError):
    """Data fetch or processing error"""
    def __init__(self, message: str, symbol: Optional[str] = None):
        details = {"symbol": symbol} if symbol else {}
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATA_ERROR",
            details=details
        )


class AuthenticationError(APIError):
    """Authentication failed"""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTH_REQUIRED"
        )


class ConfigurationError(APIError):
    """Configuration error"""
    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {"config_key": config_key} if config_key else {}
        super().__init__(
            message=message,
            status_code=500,
            error_code="CONFIG_ERROR",
            details=details
        )


def error_response(
    message: str,
    status_code: int = 500,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary
    """
    return {
        "success": False,
        "error": {
            "message": message,
            "code": error_code or f"ERR_{status_code}",
            "status": status_code,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
    }


def success_response(
    data: Any,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response dictionary
    """
    response = {
        "success": True,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    if message:
        response["message"] = message
    return response


def handle_endpoint_errors(func):
    """
    Decorator to handle common endpoint errors consistently.
    Use this on async endpoint functions.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except APIError as e:
            logger.warning(f"API Error in {func.__name__}: {e.message}")
            raise HTTPException(
                status_code=e.status_code,
                detail=error_response(
                    message=e.message,
                    status_code=e.status_code,
                    error_code=e.error_code,
                    details=e.details
                )
            )
        except HTTPException:
            # Re-raise FastAPI HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=error_response(
                    message="Internal server error",
                    status_code=500,
                    error_code="INTERNAL_ERROR",
                    details={"original_error": str(e)}
                )
            )
    return wrapper


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Global exception handler for APIError exceptions.
    Register with: app.add_exception_handler(APIError, api_error_handler)
    """
    logger.warning(f"API Error: {exc.message} (code: {exc.error_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=exc.message,
            status_code=exc.status_code,
            error_code=exc.error_code,
            details=exc.details
        )
    )


def safe_get(
    func,
    default: Any = None,
    log_errors: bool = True,
    error_msg: Optional[str] = None
) -> Any:
    """
    Safely execute a function and return default on any exception.
    Useful for fallback patterns.

    Usage:
        value = safe_get(lambda: some_risky_call(), default=0)
    """
    try:
        return func()
    except Exception as e:
        if log_errors:
            msg = error_msg or f"safe_get error: {e}"
            logger.warning(msg)
        return default
