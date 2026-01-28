"""
QUANT_INDUSTRY_V1 Security Module

Security infrastructure for institutional-grade trading:
- API key encryption and management
- Audit logging
- Rate limiting
- Access control

Usage:
    from security import SecurityManager

    security = SecurityManager('security.db')
    credentials = security.secure_api_call(
        user_id='user123',
        provider='alpaca',
        credential_name='alpaca_live'
    )
"""

from .encryption import (
    # Types
    PermissionLevel,
    AuditAction,
    APICredential,
    AuditEntry,
    RateLimitState,
    # Components
    EncryptionEngine,
    APIKeyManager,
    AuditLogger,
    RateLimiter,
    AccessControl,
    # Main
    SecurityManager,
)

__all__ = [
    # Types
    'PermissionLevel',
    'AuditAction',
    'APICredential',
    'AuditEntry',
    'RateLimitState',
    # Components
    'EncryptionEngine',
    'APIKeyManager',
    'AuditLogger',
    'RateLimiter',
    'AccessControl',
    # Main
    'SecurityManager',
]
