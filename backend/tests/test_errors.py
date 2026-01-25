"""
Tests for Error Handling Utilities
"""
import os
import sys

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from utils.errors import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    DataError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
    error_response,
    safe_get,
    success_response,
)


class TestAPIError:
    """Test base APIError class"""

    def test_api_error_creation(self):
        """APIError should be created with message and defaults"""
        error = APIError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.status_code == 500
        assert error.error_code == "ERR_500"

    def test_api_error_custom_status(self):
        """APIError should accept custom status code"""
        error = APIError("Bad request", status_code=400)
        assert error.status_code == 400
        assert error.error_code == "ERR_400"

    def test_api_error_custom_code(self):
        """APIError should accept custom error code"""
        error = APIError("Custom error", error_code="CUSTOM_CODE")
        assert error.error_code == "CUSTOM_CODE"

    def test_api_error_with_details(self):
        """APIError should store details"""
        error = APIError("Error", details={"field": "value"})
        assert error.details == {"field": "value"}


class TestSpecificErrors:
    """Test specific error types"""

    def test_not_found_error(self):
        """NotFoundError should have correct status and message"""
        error = NotFoundError("Symbol", "AAPL")
        assert error.status_code == 404
        assert error.error_code == "NOT_FOUND"
        assert "AAPL" in error.message
        assert "Symbol" in error.message

    def test_not_found_without_identifier(self):
        """NotFoundError should work without identifier"""
        error = NotFoundError("User")
        assert "User" in error.message
        assert error.status_code == 404

    def test_validation_error(self):
        """ValidationError should have correct status"""
        error = ValidationError("Invalid input", field="symbol")
        assert error.status_code == 400
        assert error.error_code == "VALIDATION_ERROR"
        assert error.details["field"] == "symbol"

    def test_service_unavailable_error(self):
        """ServiceUnavailableError should have correct status"""
        error = ServiceUnavailableError("Alpaca", "API rate limited")
        assert error.status_code == 503
        assert error.error_code == "SERVICE_UNAVAILABLE"
        assert "Alpaca" in error.message
        assert error.details["service"] == "Alpaca"

    def test_rate_limit_error(self):
        """RateLimitError should have correct status"""
        error = RateLimitError("Yahoo", retry_after=60)
        assert error.status_code == 429
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.details["retry_after"] == 60

    def test_data_error(self):
        """DataError should include symbol in details"""
        error = DataError("Failed to fetch", symbol="SPY")
        assert error.status_code == 500
        assert error.error_code == "DATA_ERROR"
        assert error.details["symbol"] == "SPY"

    def test_authentication_error(self):
        """AuthenticationError should have correct status"""
        error = AuthenticationError()
        assert error.status_code == 401
        assert error.error_code == "AUTH_REQUIRED"

    def test_configuration_error(self):
        """ConfigurationError should include config key"""
        error = ConfigurationError("Missing API key", config_key="ALPACA_API_KEY")
        assert error.status_code == 500
        assert error.error_code == "CONFIG_ERROR"
        assert error.details["config_key"] == "ALPACA_API_KEY"


class TestResponseHelpers:
    """Test response helper functions"""

    def test_error_response_structure(self):
        """error_response should return correct structure"""
        response = error_response("Something failed", status_code=400)

        assert response["success"] is False
        assert "error" in response
        assert response["error"]["message"] == "Something failed"
        assert response["error"]["status"] == 400
        assert "timestamp" in response["error"]

    def test_error_response_with_details(self):
        """error_response should include details"""
        response = error_response(
            "Validation failed",
            status_code=400,
            error_code="VALIDATION_ERROR",
            details={"field": "symbol", "reason": "required"}
        )

        assert response["error"]["code"] == "VALIDATION_ERROR"
        assert response["error"]["details"]["field"] == "symbol"

    def test_success_response_structure(self):
        """success_response should return correct structure"""
        response = success_response({"price": 100.0})

        assert response["success"] is True
        assert "data" in response
        assert response["data"]["price"] == 100.0
        assert "timestamp" in response

    def test_success_response_with_message(self):
        """success_response should include optional message"""
        response = success_response({"id": 1}, message="Created successfully")

        assert response["message"] == "Created successfully"


class TestSafeGet:
    """Test safe_get utility"""

    def test_safe_get_success(self):
        """safe_get should return function result on success"""
        result = safe_get(lambda: 42)
        assert result == 42

    def test_safe_get_with_exception(self):
        """safe_get should return default on exception"""
        result = safe_get(lambda: 1/0, default=-1, log_errors=False)
        assert result == -1

    def test_safe_get_with_none_default(self):
        """safe_get should return None as default"""
        result = safe_get(lambda: [][0], log_errors=False)
        assert result is None

    def test_safe_get_complex_call(self):
        """safe_get should work with complex operations"""
        data = {"key": "value"}
        result = safe_get(lambda: data.get("key"), default="default")
        assert result == "value"

        result = safe_get(lambda: data["missing"], default="default", log_errors=False)
        assert result == "default"
