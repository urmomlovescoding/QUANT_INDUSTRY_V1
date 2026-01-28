"""
QUANT_INDUSTRY_V1 Exception Hierarchy

Defines all custom exceptions used throughout the system.
Use specific exceptions to enable proper error handling.
"""

from typing import Optional, Dict, Any


class QuantError(Exception):
    """
    Base exception for all Quant Platform errors.

    All custom exceptions should inherit from this class.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context or {}
        self.recoverable = recoverable

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            'type': self.__class__.__name__,
            'message': self.message,
            'code': self.code,
            'context': self.context,
            'recoverable': self.recoverable,
        }


class ConfigError(QuantError):
    """Configuration-related errors."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(message, code='CONFIG_ERROR', **kwargs)
        self.config_key = config_key
        if config_key:
            self.context['config_key'] = config_key


class ValidationError(QuantError):
    """Data or input validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(message, code='VALIDATION_ERROR', **kwargs)
        self.field = field
        self.value = value
        if field:
            self.context['field'] = field
        if value is not None:
            self.context['value'] = str(value)[:100]  # Truncate for safety


class DataError(QuantError):
    """Data fetching and processing errors."""

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        source: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='DATA_ERROR', **kwargs)
        self.symbol = symbol
        self.source = source
        if symbol:
            self.context['symbol'] = symbol
        if source:
            self.context['source'] = source


class DataFetchError(DataError):
    """Failed to fetch data from source."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code='DATA_FETCH_ERROR', **kwargs)


class DataQualityError(DataError):
    """Data quality validation failed."""

    def __init__(
        self,
        message: str,
        quality_issues: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, code='DATA_QUALITY_ERROR', **kwargs)
        self.quality_issues = quality_issues or []
        self.context['quality_issues'] = self.quality_issues


class DataStaleError(DataError):
    """Data is too stale to use."""

    def __init__(
        self,
        message: str,
        staleness_seconds: Optional[float] = None,
        max_staleness: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, code='DATA_STALE_ERROR', **kwargs)
        self.staleness_seconds = staleness_seconds
        self.max_staleness = max_staleness
        if staleness_seconds:
            self.context['staleness_seconds'] = staleness_seconds
        if max_staleness:
            self.context['max_staleness'] = max_staleness


class ModelError(QuantError):
    """Model-related errors."""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        model_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='MODEL_ERROR', **kwargs)
        self.model_id = model_id
        self.model_type = model_type
        if model_id:
            self.context['model_id'] = model_id
        if model_type:
            self.context['model_type'] = model_type


class ModelNotFoundError(ModelError):
    """Model not found in registry."""

    def __init__(self, model_id: str, **kwargs):
        super().__init__(
            f"Model not found: {model_id}",
            model_id=model_id,
            code='MODEL_NOT_FOUND',
            **kwargs
        )


class ModelTrainingError(ModelError):
    """Error during model training."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code='MODEL_TRAINING_ERROR', **kwargs)


class ModelInferenceError(ModelError):
    """Error during model inference."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code='MODEL_INFERENCE_ERROR', **kwargs)


class ModelDriftError(ModelError):
    """Model drift detected."""

    def __init__(
        self,
        message: str,
        drift_score: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, code='MODEL_DRIFT_ERROR', **kwargs)
        self.drift_score = drift_score
        if drift_score:
            self.context['drift_score'] = drift_score


class ExecutionError(QuantError):
    """Trade execution errors."""

    def __init__(
        self,
        message: str,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='EXECUTION_ERROR', **kwargs)
        self.order_id = order_id
        self.symbol = symbol
        if order_id:
            self.context['order_id'] = order_id
        if symbol:
            self.context['symbol'] = symbol


class OrderRejectedError(ExecutionError):
    """Order was rejected by broker."""

    def __init__(
        self,
        message: str,
        rejection_reason: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='ORDER_REJECTED', **kwargs)
        self.rejection_reason = rejection_reason
        if rejection_reason:
            self.context['rejection_reason'] = rejection_reason


class InsufficientFundsError(ExecutionError):
    """Insufficient buying power for order."""

    def __init__(
        self,
        message: str,
        required: Optional[float] = None,
        available: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, code='INSUFFICIENT_FUNDS', **kwargs)
        self.required = required
        self.available = available
        if required:
            self.context['required'] = required
        if available:
            self.context['available'] = available


class RiskError(QuantError):
    """Risk management errors."""

    def __init__(
        self,
        message: str,
        limit_type: Optional[str] = None,
        limit_value: Optional[float] = None,
        actual_value: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, code='RISK_ERROR', **kwargs)
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.actual_value = actual_value
        if limit_type:
            self.context['limit_type'] = limit_type
        if limit_value:
            self.context['limit_value'] = limit_value
        if actual_value:
            self.context['actual_value'] = actual_value


class RiskLimitBreachedError(RiskError):
    """Risk limit has been breached."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code='RISK_LIMIT_BREACHED', recoverable=False, **kwargs)


class KillSwitchTriggeredError(RiskError):
    """Kill switch has been triggered."""

    def __init__(
        self,
        message: str,
        trigger_reason: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='KILL_SWITCH_TRIGGERED', recoverable=False, **kwargs)
        self.trigger_reason = trigger_reason
        if trigger_reason:
            self.context['trigger_reason'] = trigger_reason


class DrawdownLimitError(RiskError):
    """Maximum drawdown limit exceeded."""

    def __init__(
        self,
        message: str,
        current_drawdown: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, code='DRAWDOWN_LIMIT', **kwargs)
        self.current_drawdown = current_drawdown
        self.max_drawdown = max_drawdown
        if current_drawdown:
            self.context['current_drawdown'] = current_drawdown
        if max_drawdown:
            self.context['max_drawdown'] = max_drawdown


class StrategyError(QuantError):
    """Strategy-related errors."""

    def __init__(
        self,
        message: str,
        strategy_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='STRATEGY_ERROR', **kwargs)
        self.strategy_id = strategy_id
        if strategy_id:
            self.context['strategy_id'] = strategy_id


class StrategyNotFoundError(StrategyError):
    """Strategy not found in registry."""

    def __init__(self, strategy_id: str, **kwargs):
        super().__init__(
            f"Strategy not found: {strategy_id}",
            strategy_id=strategy_id,
            code='STRATEGY_NOT_FOUND',
            **kwargs
        )


class StrategyDisabledError(StrategyError):
    """Strategy is disabled."""

    def __init__(self, strategy_id: str, **kwargs):
        super().__init__(
            f"Strategy is disabled: {strategy_id}",
            strategy_id=strategy_id,
            code='STRATEGY_DISABLED',
            **kwargs
        )


class FeatureError(QuantError):
    """Feature computation errors."""

    def __init__(
        self,
        message: str,
        feature_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='FEATURE_ERROR', **kwargs)
        self.feature_name = feature_name
        if feature_name:
            self.context['feature_name'] = feature_name


class FeatureComputationError(FeatureError):
    """Error computing feature value."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code='FEATURE_COMPUTATION_ERROR', **kwargs)


class FeatureNotFoundError(FeatureError):
    """Feature definition not found."""

    def __init__(self, feature_name: str, **kwargs):
        super().__init__(
            f"Feature not found: {feature_name}",
            feature_name=feature_name,
            code='FEATURE_NOT_FOUND',
            **kwargs
        )


class DatabaseError(QuantError):
    """Database operation errors."""

    def __init__(
        self,
        message: str,
        table: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code='DATABASE_ERROR', **kwargs)
        self.table = table
        self.operation = operation
        if table:
            self.context['table'] = table
        if operation:
            self.context['operation'] = operation


class ConnectionError(DatabaseError):
    """Database connection failed."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code='CONNECTION_ERROR', **kwargs)


class IntegrityError(DatabaseError):
    """Database integrity constraint violated."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code='INTEGRITY_ERROR', **kwargs)
