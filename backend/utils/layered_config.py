"""
Layered Configuration System for QUANT INDUSTRY
================================================
Provides a hierarchical configuration system with multiple layers:
1. Defaults (code-level)
2. Config files (YAML/JSON)
3. Environment variables
4. Runtime overrides

Matches quant-platform pattern for production configuration management.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConfigLayer(Enum):
    """Configuration layer priority (higher = more priority)"""
    DEFAULTS = 0
    FILE = 1
    ENVIRONMENT = 2
    RUNTIME = 3


@dataclass
class ConfigValue:
    """Tracked configuration value with metadata"""
    key: str
    value: Any
    layer: ConfigLayer
    source: str  # e.g., "defaults", "config.yaml", "ENV:API_KEY"
    set_at: datetime = field(default_factory=datetime.now)
    validated: bool = True


@dataclass
class ConfigSchema:
    """Schema definition for a configuration key"""
    key: str
    type: type
    default: Any = None
    required: bool = False
    description: str = ""
    validator: Optional[Callable[[Any], bool]] = None
    env_var: Optional[str] = None
    secret: bool = False  # If True, value is masked in logs


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Configuration validation failed: {errors}")


class LayeredConfig:
    """
    Layered configuration manager with validation and change tracking.

    Example:
        config = LayeredConfig()
        config.register_schema(ConfigSchema(
            key="api.timeout",
            type=int,
            default=30,
            description="API request timeout in seconds"
        ))
        config.load_from_file("config.yaml")
        config.load_from_env()

        timeout = config.get("api.timeout")
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._schemas: Dict[str, ConfigSchema] = {}
        self._values: Dict[str, ConfigValue] = {}
        self._change_callbacks: List[Callable[[str, Any, Any], None]] = []
        self._frozen: bool = False

    def register_schema(self, schema: ConfigSchema) -> None:
        """Register a configuration schema"""
        self._schemas[schema.key] = schema

        # Set default value
        if schema.default is not None:
            self._set_value(
                schema.key,
                schema.default,
                ConfigLayer.DEFAULTS,
                "defaults"
            )

    def register_schemas(self, schemas: List[ConfigSchema]) -> None:
        """Register multiple schemas at once"""
        for schema in schemas:
            self.register_schema(schema)

    def _set_value(
        self,
        key: str,
        value: Any,
        layer: ConfigLayer,
        source: str
    ) -> None:
        """Internal method to set a value at a specific layer"""
        if self._frozen:
            raise RuntimeError("Configuration is frozen, cannot modify")

        # Check if this layer has priority
        if key in self._values:
            existing = self._values[key]
            if layer.value < existing.layer.value:
                logger.debug(
                    f"Ignoring {key} from {source}, "
                    f"higher priority value exists from {existing.source}"
                )
                return

        # Validate against schema
        validated = True
        if key in self._schemas:
            schema = self._schemas[key]
            value = self._coerce_type(value, schema.type)
            if schema.validator:
                validated = schema.validator(value)
                if not validated:
                    logger.warning(f"Validation failed for {key}={value}")

        old_value = self._values.get(key)
        self._values[key] = ConfigValue(
            key=key,
            value=value,
            layer=layer,
            source=source,
            validated=validated
        )

        # Notify callbacks
        if old_value is not None and old_value.value != value:
            for callback in self._change_callbacks:
                try:
                    callback(key, old_value.value, value)
                except Exception as e:
                    logger.error(f"Config change callback error: {e}")

    def _coerce_type(self, value: Any, target_type: type) -> Any:
        """Coerce a value to the target type"""
        if value is None:
            return None

        if isinstance(value, target_type):
            return value

        try:
            if target_type == bool:
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            elif target_type == int:
                return int(value)
            elif target_type == float:
                return float(value)
            elif target_type == str:
                return str(value)
            elif target_type == list:
                if isinstance(value, str):
                    return json.loads(value)
                return list(value)
            elif target_type == dict:
                if isinstance(value, str):
                    return json.loads(value)
                return dict(value)
            else:
                return target_type(value)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"Type coercion failed: {value} -> {target_type}: {e}")
            return value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        if key in self._values:
            return self._values[key].value

        if key in self._schemas:
            return self._schemas[key].default

        return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a float configuration value"""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)

    def get_list(self, key: str, default: List = None) -> List:
        """Get a list configuration value"""
        value = self.get(key, default or [])
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.split(',')
        return [value]

    def set(self, key: str, value: Any) -> None:
        """Set a runtime configuration value (highest priority)"""
        self._set_value(key, value, ConfigLayer.RUNTIME, "runtime")

    def load_from_dict(
        self,
        data: Dict[str, Any],
        layer: ConfigLayer = ConfigLayer.FILE,
        source: str = "dict"
    ) -> None:
        """Load configuration from a dictionary"""
        flat = self._flatten_dict(data)
        for key, value in flat.items():
            self._set_value(key, value, layer, source)

    def load_from_file(self, path: Union[str, Path]) -> bool:
        """Load configuration from a YAML or JSON file"""
        path = Path(path)

        if not path.exists():
            logger.warning(f"Config file not found: {path}")
            return False

        try:
            content = path.read_text()

            if path.suffix in ('.yaml', '.yml'):
                try:
                    import yaml
                    data = yaml.safe_load(content)
                except ImportError:
                    logger.warning("PyYAML not installed, skipping YAML file")
                    return False
            elif path.suffix == '.json':
                data = json.loads(content)
            else:
                logger.warning(f"Unknown config file format: {path.suffix}")
                return False

            self.load_from_dict(data, ConfigLayer.FILE, str(path))
            logger.info(f"Loaded config from {path}")
            return True

        except Exception as e:
            logger.error(f"Error loading config file {path}: {e}")
            return False

    def load_from_env(self, prefix: str = "QUANT_") -> int:
        """
        Load configuration from environment variables.

        Variables matching the prefix or registered env_var names are loaded.
        Returns the number of values loaded.
        """
        count = 0

        # Load registered env vars
        for key, schema in self._schemas.items():
            if schema.env_var and schema.env_var in os.environ:
                value = os.environ[schema.env_var]
                self._set_value(key, value, ConfigLayer.ENVIRONMENT, f"ENV:{schema.env_var}")
                count += 1

        # Load prefixed env vars
        for env_key, value in os.environ.items():
            if env_key.startswith(prefix):
                # Convert QUANT_API_TIMEOUT to api.timeout
                config_key = env_key[len(prefix):].lower().replace('_', '.')
                self._set_value(config_key, value, ConfigLayer.ENVIRONMENT, f"ENV:{env_key}")
                count += 1

        logger.info(f"Loaded {count} config values from environment")
        return count

    def _flatten_dict(
        self,
        data: Dict[str, Any],
        prefix: str = ""
    ) -> Dict[str, Any]:
        """Flatten a nested dictionary using dot notation"""
        result = {}

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                result.update(self._flatten_dict(value, full_key))
            else:
                result[full_key] = value

        return result

    def validate(self) -> List[str]:
        """
        Validate configuration against registered schemas.
        Returns list of error messages (empty if valid).
        """
        errors = []

        for key, schema in self._schemas.items():
            # Check required
            if schema.required and key not in self._values:
                errors.append(f"Required config missing: {key}")
                continue

            if key in self._values:
                config_value = self._values[key]
                value = config_value.value

                # Check type
                if not isinstance(value, schema.type) and value is not None:
                    errors.append(
                        f"Type mismatch for {key}: expected {schema.type.__name__}, "
                        f"got {type(value).__name__}"
                    )

                # Run custom validator
                if schema.validator and not schema.validator(value):
                    errors.append(f"Validation failed for {key}={value}")

        return errors

    def validate_or_raise(self) -> None:
        """Validate configuration, raising an exception on failure"""
        errors = self.validate()
        if errors:
            raise ConfigValidationError(errors)

    def freeze(self) -> None:
        """Freeze configuration, preventing further changes"""
        self._frozen = True
        logger.info(f"Configuration '{self.name}' frozen")

    def unfreeze(self) -> None:
        """Unfreeze configuration, allowing changes again"""
        self._frozen = False

    def on_change(self, callback: Callable[[str, Any, Any], None]) -> None:
        """Register a callback for configuration changes"""
        self._change_callbacks.append(callback)

    def get_all(self, include_defaults: bool = True) -> Dict[str, Any]:
        """Get all configuration values as a dictionary"""
        result = {}

        # Add defaults first
        if include_defaults:
            for key, schema in self._schemas.items():
                if schema.default is not None:
                    result[key] = schema.default

        # Override with actual values
        for key, config_value in self._values.items():
            schema = self._schemas.get(key)
            if schema and schema.secret:
                result[key] = "***REDACTED***"
            else:
                result[key] = config_value.value

        return result

    def get_sources(self) -> Dict[str, str]:
        """Get the source for each configuration value"""
        return {
            key: cv.source
            for key, cv in self._values.items()
        }

    def export(self, format: str = "dict") -> Union[Dict, str]:
        """Export configuration to various formats"""
        data = self.get_all()

        if format == "dict":
            return data
        elif format == "json":
            return json.dumps(data, indent=2, default=str)
        elif format == "env":
            lines = []
            for key, value in data.items():
                env_key = key.upper().replace('.', '_')
                lines.append(f"QUANT_{env_key}={value}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown export format: {format}")

    def diff(self, other: 'LayeredConfig') -> Dict[str, Dict[str, Any]]:
        """Compare this config with another, returning differences"""
        diffs = {}

        all_keys = set(self._values.keys()) | set(other._values.keys())

        for key in all_keys:
            self_value = self.get(key)
            other_value = other.get(key)

            if self_value != other_value:
                diffs[key] = {
                    "self": self_value,
                    "other": other_value
                }

        return diffs


# ============== PREDEFINED SCHEMAS ==============

def create_trading_config_schemas() -> List[ConfigSchema]:
    """Create standard trading configuration schemas"""
    return [
        # API Configuration
        ConfigSchema(
            key="api.timeout",
            type=int,
            default=30,
            description="API request timeout in seconds",
            env_var="API_TIMEOUT"
        ),
        ConfigSchema(
            key="api.retry_count",
            type=int,
            default=3,
            description="Number of API retry attempts"
        ),
        ConfigSchema(
            key="api.base_url",
            type=str,
            default="https://api.alpaca.markets",
            description="Base API URL",
            env_var="API_BASE_URL"
        ),

        # Trading Configuration
        ConfigSchema(
            key="trading.mode",
            type=str,
            default="paper",
            description="Trading mode: live, paper, or signal_only",
            validator=lambda x: x in ('live', 'paper', 'signal_only')
        ),
        ConfigSchema(
            key="trading.max_positions",
            type=int,
            default=10,
            description="Maximum number of concurrent positions"
        ),
        ConfigSchema(
            key="trading.max_position_size",
            type=float,
            default=0.1,
            description="Maximum position size as fraction of equity"
        ),
        ConfigSchema(
            key="trading.default_stop_loss",
            type=float,
            default=0.02,
            description="Default stop loss percentage"
        ),

        # Risk Configuration
        ConfigSchema(
            key="risk.max_daily_loss",
            type=float,
            default=0.02,
            description="Maximum daily loss as fraction of equity"
        ),
        ConfigSchema(
            key="risk.max_drawdown",
            type=float,
            default=0.05,
            description="Maximum drawdown limit"
        ),
        ConfigSchema(
            key="risk.position_limit",
            type=float,
            default=0.2,
            description="Maximum single position as fraction of equity"
        ),

        # Brain/ML Configuration
        ConfigSchema(
            key="brain.min_confidence",
            type=float,
            default=0.6,
            description="Minimum signal confidence for execution"
        ),
        ConfigSchema(
            key="brain.retraining_interval",
            type=int,
            default=86400,
            description="Model retraining interval in seconds"
        ),
        ConfigSchema(
            key="brain.device",
            type=str,
            default="auto",
            description="PyTorch device (auto, cpu, cuda)"
        ),

        # Data Configuration
        ConfigSchema(
            key="data.staleness_threshold",
            type=int,
            default=60,
            description="Data staleness threshold in seconds"
        ),
        ConfigSchema(
            key="data.cache_ttl",
            type=int,
            default=300,
            description="Data cache TTL in seconds"
        ),

        # WebSocket Configuration
        ConfigSchema(
            key="websocket.reconnect_attempts",
            type=int,
            default=10,
            description="WebSocket reconnection attempts"
        ),
        ConfigSchema(
            key="websocket.ping_interval",
            type=int,
            default=30,
            description="WebSocket ping interval in seconds"
        ),

        # Secrets (masked in logs)
        ConfigSchema(
            key="api.key",
            type=str,
            default="",
            description="API key",
            env_var="ALPACA_API_KEY",
            secret=True,
            required=False
        ),
        ConfigSchema(
            key="api.secret",
            type=str,
            default="",
            description="API secret",
            env_var="ALPACA_API_SECRET",
            secret=True,
            required=False
        ),
    ]


# ============== SINGLETON INSTANCE ==============

_global_config: Optional[LayeredConfig] = None


def get_config() -> LayeredConfig:
    """Get or create the global configuration instance"""
    global _global_config

    if _global_config is None:
        _global_config = LayeredConfig(name="global")
        _global_config.register_schemas(create_trading_config_schemas())

        # Try to load config files
        config_paths = [
            Path("config.yaml"),
            Path("config.json"),
            Path.home() / ".quant" / "config.yaml",
        ]

        for path in config_paths:
            if path.exists():
                _global_config.load_from_file(path)
                break

        # Load environment variables
        _global_config.load_from_env()

    return _global_config


def reset_config() -> None:
    """Reset the global configuration instance"""
    global _global_config
    _global_config = None
