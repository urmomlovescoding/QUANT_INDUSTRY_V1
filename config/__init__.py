"""
QUANT_INDUSTRY_V1 Configuration Management

Provides environment-aware configuration with validation.
Supports .env files, environment variables, and programmatic configuration.
"""

from .settings import (
    Settings,
    get_settings,
    DataConfig,
    BrainConfig,
    ExecutionConfig,
    RiskConfig,
    UIConfig,
)

__all__ = [
    'Settings',
    'get_settings',
    'DataConfig',
    'BrainConfig',
    'ExecutionConfig',
    'RiskConfig',
    'UIConfig',
]
