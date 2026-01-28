"""
QUANT_INDUSTRY_V1 Security Module

Security features for institutional-grade trading:
- API key management and encryption
- Credential storage
- Access control
- Audit logging
- Rate limiting

Rollback Plan: Delete this file
Tests Required: Encryption/decryption, key rotation
Failure Modes: Deny access, alert security
"""

import os
import hashlib
import hmac
import secrets
import base64
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


# =============================================================================
# SECURITY TYPES
# =============================================================================

class PermissionLevel(Enum):
    """Access permission levels."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class AuditAction(Enum):
    """Auditable actions."""
    LOGIN = "login"
    LOGOUT = "logout"
    API_CALL = "api_call"
    CONFIG_CHANGE = "config_change"
    KEY_ACCESS = "key_access"
    TRADE_SUBMIT = "trade_submit"
    TRADE_CANCEL = "trade_cancel"
    DATA_EXPORT = "data_export"
    PERMISSION_CHANGE = "permission_change"


@dataclass
class APICredential:
    """Stored API credential."""
    name: str
    provider: str
    key_hash: str
    encrypted_secret: bytes
    permissions: List[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class AuditEntry:
    """Audit log entry."""
    id: str
    timestamp: datetime
    action: AuditAction
    user_id: str
    resource: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    success: bool = True


@dataclass
class RateLimitState:
    """Rate limit tracking state."""
    key: str
    count: int
    window_start: datetime
    limit: int
    window_seconds: int


# =============================================================================
# ENCRYPTION ENGINE
# =============================================================================

class EncryptionEngine:
    """
    Simple encryption engine using PBKDF2 and XOR-based encryption.

    For production, replace with proper AES encryption via cryptography library.
    """

    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption engine.

        Args:
            master_key: Master encryption key (from environment or secure storage)
        """
        self._master_key = master_key or os.environ.get('QUANT_MASTER_KEY', '')
        if not self._master_key:
            # Generate a random key for this session (not persistent)
            self._master_key = secrets.token_hex(32)
            logger.warning("No master key provided. Using session-only key.")

        self._derived_key = self._derive_key(self._master_key)

    def _derive_key(self, password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2."""
        if salt is None:
            salt = secrets.token_bytes(16)

        # PBKDF2 with SHA256
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            iterations=100000,
            dklen=32
        )
        return key, salt

    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt plaintext string.

        Returns: salt (16) + encrypted data
        """
        key, salt = self._derive_key(self._master_key)
        data = plaintext.encode('utf-8')

        # Simple XOR encryption (for production, use AES)
        encrypted = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])

        return salt + encrypted

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt ciphertext bytes."""
        salt = ciphertext[:16]
        encrypted = ciphertext[16:]

        key, _ = self._derive_key(self._master_key, salt)

        # XOR decrypt
        decrypted = bytes([encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted))])

        return decrypted.decode('utf-8')

    def hash_value(self, value: str) -> str:
        """Create secure hash of value."""
        return hashlib.sha256(
            (value + self._master_key).encode('utf-8')
        ).hexdigest()

    def generate_token(self, length: int = 32) -> str:
        """Generate secure random token."""
        return secrets.token_urlsafe(length)


# =============================================================================
# API KEY MANAGER
# =============================================================================

class APIKeyManager:
    """
    Secure API key storage and management.

    Keys are encrypted at rest and accessed only when needed.
    """

    def __init__(self, db_path: str, encryption_engine: EncryptionEngine = None):
        self.db_path = db_path
        self.encryption = encryption_engine or EncryptionEngine()
        self._credentials: Dict[str, APICredential] = {}
        self._init_database()

    def _init_database(self) -> None:
        """Initialize credentials database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_credentials (
                    name TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    encrypted_secret BLOB NOT NULL,
                    permissions TEXT,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.commit()

    def store_credential(
        self,
        name: str,
        provider: str,
        api_key: str,
        api_secret: str,
        permissions: List[str] = None,
        expires_in_days: int = None
    ) -> bool:
        """
        Store API credentials securely.

        Args:
            name: Credential identifier
            provider: Provider name (e.g., "alpaca", "polygon")
            api_key: API key
            api_secret: API secret
            permissions: List of permitted actions
            expires_in_days: Auto-expire after N days
        """
        try:
            key_hash = self.encryption.hash_value(api_key)
            encrypted_secret = self.encryption.encrypt(api_secret)

            expires_at = None
            if expires_in_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

            credential = APICredential(
                name=name,
                provider=provider,
                key_hash=key_hash,
                encrypted_secret=encrypted_secret,
                permissions=permissions or [],
                expires_at=expires_at,
            )

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO api_credentials
                    (name, provider, key_hash, encrypted_secret, permissions,
                     created_at, expires_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    credential.name,
                    credential.provider,
                    credential.key_hash,
                    credential.encrypted_secret,
                    json.dumps(credential.permissions),
                    credential.created_at.isoformat(),
                    credential.expires_at.isoformat() if credential.expires_at else None,
                    1 if credential.is_active else 0,
                ))
                conn.commit()

            self._credentials[name] = credential
            logger.info(f"Stored credential: {name} for {provider}")
            return True

        except Exception as e:
            logger.error(f"Failed to store credential {name}: {e}")
            return False

    def get_credential(self, name: str) -> Optional[Tuple[str, str]]:
        """
        Retrieve decrypted API credentials.

        Returns: (api_key_hash, api_secret) or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT key_hash, encrypted_secret, expires_at, is_active
                    FROM api_credentials
                    WHERE name = ?
                """, (name,))
                row = cursor.fetchone()

            if not row:
                return None

            key_hash, encrypted_secret, expires_at_str, is_active = row

            if not is_active:
                logger.warning(f"Credential {name} is inactive")
                return None

            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now(timezone.utc) > expires_at:
                    logger.warning(f"Credential {name} has expired")
                    return None

            api_secret = self.encryption.decrypt(encrypted_secret)

            # Update last used
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE api_credentials
                    SET last_used = ?
                    WHERE name = ?
                """, (datetime.now(timezone.utc).isoformat(), name))
                conn.commit()

            return (key_hash, api_secret)

        except Exception as e:
            logger.error(f"Failed to retrieve credential {name}: {e}")
            return None

    def revoke_credential(self, name: str) -> bool:
        """Revoke/disable a credential."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE api_credentials
                    SET is_active = 0
                    WHERE name = ?
                """, (name,))
                conn.commit()

            if name in self._credentials:
                self._credentials[name].is_active = False

            logger.info(f"Revoked credential: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke credential {name}: {e}")
            return False

    def rotate_credential(
        self,
        name: str,
        new_api_key: str,
        new_api_secret: str
    ) -> bool:
        """Rotate API credentials."""
        try:
            # Get existing credential
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT provider, permissions, expires_at
                    FROM api_credentials
                    WHERE name = ?
                """, (name,))
                row = cursor.fetchone()

            if not row:
                logger.error(f"Credential {name} not found for rotation")
                return False

            provider, permissions_json, expires_at_str = row
            permissions = json.loads(permissions_json) if permissions_json else []

            # Store new credential
            new_key_hash = self.encryption.hash_value(new_api_key)
            new_encrypted_secret = self.encryption.encrypt(new_api_secret)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE api_credentials
                    SET key_hash = ?, encrypted_secret = ?
                    WHERE name = ?
                """, (new_key_hash, new_encrypted_secret, name))
                conn.commit()

            logger.info(f"Rotated credential: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to rotate credential {name}: {e}")
            return False

    def list_credentials(self) -> List[Dict[str, Any]]:
        """List all credentials (without secrets)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name, provider, created_at, last_used, expires_at, is_active
                FROM api_credentials
            """)
            rows = cursor.fetchall()

        return [
            {
                'name': row[0],
                'provider': row[1],
                'created_at': row[2],
                'last_used': row[3],
                'expires_at': row[4],
                'is_active': bool(row[5]),
            }
            for row in rows
        ]


# =============================================================================
# AUDIT LOGGER
# =============================================================================

class AuditLogger:
    """
    Security audit logging.

    Records all security-relevant actions for compliance.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize audit database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    resource TEXT,
                    details TEXT,
                    ip_address TEXT,
                    success INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user
                ON audit_log(user_id)
            """)
            conn.commit()

    def log(
        self,
        action: AuditAction,
        user_id: str,
        resource: str = "",
        details: Dict[str, Any] = None,
        ip_address: str = None,
        success: bool = True
    ) -> str:
        """Log an audit entry."""
        entry_id = secrets.token_hex(8)
        timestamp = datetime.now(timezone.utc)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO audit_log
                    (id, timestamp, action, user_id, resource, details, ip_address, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry_id,
                    timestamp.isoformat(),
                    action.value,
                    user_id,
                    resource,
                    json.dumps(details or {}),
                    ip_address,
                    1 if success else 0,
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")

        return entry_id

    def query(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        user_id: str = None,
        action: AuditAction = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Query audit log."""
        conditions = []
        params = []

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if action:
            conditions.append("action = ?")
            params.append(action.value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"""
                SELECT id, timestamp, action, user_id, resource, details, ip_address, success
                FROM audit_log
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [limit])
            rows = cursor.fetchall()

        return [
            AuditEntry(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                action=AuditAction(row[2]),
                user_id=row[3],
                resource=row[4],
                details=json.loads(row[5]) if row[5] else {},
                ip_address=row[6],
                success=bool(row[7]),
            )
            for row in rows
        ]

    def get_suspicious_activity(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Detect suspicious activity patterns."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        suspicious = []

        with sqlite3.connect(self.db_path) as conn:
            # Failed logins
            cursor = conn.execute("""
                SELECT user_id, COUNT(*) as count
                FROM audit_log
                WHERE action = 'login' AND success = 0 AND timestamp >= ?
                GROUP BY user_id
                HAVING count >= 3
            """, (cutoff.isoformat(),))

            for row in cursor.fetchall():
                suspicious.append({
                    'type': 'multiple_failed_logins',
                    'user_id': row[0],
                    'count': row[1],
                    'severity': 'high',
                })

            # Unusual API access patterns
            cursor = conn.execute("""
                SELECT user_id, COUNT(*) as count
                FROM audit_log
                WHERE action = 'api_call' AND timestamp >= ?
                GROUP BY user_id
                HAVING count >= 1000
            """, (cutoff.isoformat(),))

            for row in cursor.fetchall():
                suspicious.append({
                    'type': 'high_api_volume',
                    'user_id': row[0],
                    'count': row[1],
                    'severity': 'medium',
                })

        return suspicious


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Rate limiting for API calls and sensitive operations.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self._memory_state: Dict[str, RateLimitState] = {}

        if db_path:
            self._init_database()

    def _init_database(self) -> None:
        """Initialize rate limit database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    window_start TEXT,
                    limit_value INTEGER,
                    window_seconds INTEGER
                )
            """)
            conn.commit()

    def check(
        self,
        key: str,
        limit: int = 100,
        window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if action is within rate limit.

        Args:
            key: Rate limit key (e.g., "user:123:api_calls")
            limit: Maximum actions per window
            window_seconds: Window size in seconds

        Returns:
            (allowed, remaining)
        """
        now = datetime.now(timezone.utc)

        if key in self._memory_state:
            state = self._memory_state[key]
            window_elapsed = (now - state.window_start).total_seconds()

            if window_elapsed >= state.window_seconds:
                # Reset window
                state.count = 1
                state.window_start = now
            else:
                state.count += 1

            remaining = max(0, state.limit - state.count)
            allowed = state.count <= state.limit

        else:
            # New rate limit key
            state = RateLimitState(
                key=key,
                count=1,
                window_start=now,
                limit=limit,
                window_seconds=window_seconds,
            )
            self._memory_state[key] = state
            remaining = limit - 1
            allowed = True

        return (allowed, remaining)

    def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        if key in self._memory_state:
            del self._memory_state[key]

    def get_status(self, key: str) -> Optional[Dict[str, Any]]:
        """Get current rate limit status."""
        if key not in self._memory_state:
            return None

        state = self._memory_state[key]
        now = datetime.now(timezone.utc)
        elapsed = (now - state.window_start).total_seconds()
        reset_in = max(0, state.window_seconds - elapsed)

        return {
            'key': key,
            'count': state.count,
            'limit': state.limit,
            'remaining': max(0, state.limit - state.count),
            'reset_in_seconds': reset_in,
        }


# =============================================================================
# ACCESS CONTROL
# =============================================================================

class AccessControl:
    """
    Role-based access control.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize access control database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role TEXT,
                    resource TEXT,
                    permission TEXT,
                    PRIMARY KEY (role, resource)
                )
            """)
            conn.commit()

            # Default roles
            default_permissions = [
                ('admin', '*', 'admin'),
                ('trader', 'trades', 'execute'),
                ('trader', 'positions', 'read'),
                ('trader', 'orders', 'write'),
                ('analyst', 'data', 'read'),
                ('analyst', 'reports', 'read'),
                ('analyst', 'models', 'read'),
                ('viewer', '*', 'read'),
            ]

            for role, resource, permission in default_permissions:
                conn.execute("""
                    INSERT OR IGNORE INTO role_permissions
                    (role, resource, permission)
                    VALUES (?, ?, ?)
                """, (role, resource, permission))

            conn.commit()

    def assign_role(self, user_id: str, role: str) -> bool:
        """Assign role to user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO user_roles
                    (user_id, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    user_id,
                    role,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ))
                conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to assign role: {e}")
            return False

    def check_permission(
        self,
        user_id: str,
        resource: str,
        required_permission: PermissionLevel
    ) -> bool:
        """Check if user has permission for resource."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get user's role
                cursor = conn.execute("""
                    SELECT role FROM user_roles WHERE user_id = ?
                """, (user_id,))
                row = cursor.fetchone()

                if not row:
                    return False

                role = row[0]

                # Check permission
                cursor = conn.execute("""
                    SELECT permission FROM role_permissions
                    WHERE role = ? AND (resource = ? OR resource = '*')
                """, (role, resource))
                rows = cursor.fetchall()

                if not rows:
                    return False

                # Check if any permission is sufficient
                permission_hierarchy = {
                    PermissionLevel.NONE: 0,
                    PermissionLevel.READ: 1,
                    PermissionLevel.WRITE: 2,
                    PermissionLevel.EXECUTE: 3,
                    PermissionLevel.ADMIN: 4,
                }

                for (perm,) in rows:
                    try:
                        level = PermissionLevel(perm)
                        if permission_hierarchy.get(level, 0) >= permission_hierarchy.get(required_permission, 0):
                            return True
                    except ValueError:
                        continue

                return False

        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False

    def get_user_permissions(self, user_id: str) -> Dict[str, str]:
        """Get all permissions for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT rp.resource, rp.permission
                FROM user_roles ur
                JOIN role_permissions rp ON ur.role = rp.role
                WHERE ur.user_id = ?
            """, (user_id,))
            rows = cursor.fetchall()

        return {row[0]: row[1] for row in rows}


# =============================================================================
# SECURITY MANAGER
# =============================================================================

class SecurityManager:
    """
    Central security management.

    Coordinates all security components.
    """

    def __init__(self, db_path: str, master_key: str = None):
        self.db_path = db_path

        self.encryption = EncryptionEngine(master_key)
        self.key_manager = APIKeyManager(db_path, self.encryption)
        self.audit_logger = AuditLogger(db_path)
        self.rate_limiter = RateLimiter()
        self.access_control = AccessControl(db_path)

    def secure_api_call(
        self,
        user_id: str,
        provider: str,
        credential_name: str,
        rate_limit_key: str = None
    ) -> Optional[Tuple[str, str]]:
        """
        Securely retrieve API credentials with all checks.

        Returns credentials only if all security checks pass.
        """
        # Check rate limit
        if rate_limit_key:
            allowed, remaining = self.rate_limiter.check(rate_limit_key)
            if not allowed:
                self.audit_logger.log(
                    AuditAction.API_CALL,
                    user_id,
                    provider,
                    {'reason': 'rate_limited'},
                    success=False
                )
                return None

        # Check permission
        if not self.access_control.check_permission(
            user_id, provider, PermissionLevel.EXECUTE
        ):
            self.audit_logger.log(
                AuditAction.API_CALL,
                user_id,
                provider,
                {'reason': 'permission_denied'},
                success=False
            )
            return None

        # Get credentials
        credentials = self.key_manager.get_credential(credential_name)
        if not credentials:
            self.audit_logger.log(
                AuditAction.KEY_ACCESS,
                user_id,
                credential_name,
                {'reason': 'not_found'},
                success=False
            )
            return None

        # Log successful access
        self.audit_logger.log(
            AuditAction.KEY_ACCESS,
            user_id,
            credential_name,
            {'provider': provider}
        )

        return credentials

    def get_security_status(self) -> Dict[str, Any]:
        """Get overall security status."""
        suspicious = self.audit_logger.get_suspicious_activity(24)
        credentials = self.key_manager.list_credentials()

        expired_creds = [
            c for c in credentials
            if c.get('expires_at') and
            datetime.fromisoformat(c['expires_at']) < datetime.now(timezone.utc)
        ]

        return {
            'total_credentials': len(credentials),
            'active_credentials': sum(1 for c in credentials if c['is_active']),
            'expired_credentials': len(expired_creds),
            'suspicious_activities': len(suspicious),
            'suspicious_details': suspicious,
        }
