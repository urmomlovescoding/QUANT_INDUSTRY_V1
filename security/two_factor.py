"""
Two-Factor Authentication (2FA) Module
QUANT_INDUSTRY_V1 - P2 Enhancement

Provides:
- TOTP (Time-based One-Time Password) support
- Backup codes generation
- Rate-limited verification
- Session management with 2FA enforcement

Rollback Plan: Delete this file, disable 2FA in settings
Tests Required: TOTP generation/validation, rate limiting, backup codes
Failure Modes: Fall back to password-only auth, alert security team
"""

import os
import hmac
import hashlib
import base64
import secrets
import struct
import time
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

TOTP_INTERVAL = 30  # Seconds
TOTP_DIGITS = 6
TOTP_ALGORITHM = 'sha1'
BACKUP_CODE_LENGTH = 8
BACKUP_CODE_COUNT = 10
MAX_VERIFICATION_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


# =============================================================================
# TYPES
# =============================================================================

class TwoFactorStatus(Enum):
    """2FA status for a user."""
    DISABLED = "disabled"
    PENDING = "pending"  # Setup started but not verified
    ENABLED = "enabled"
    LOCKED = "locked"  # Too many failed attempts


@dataclass
class TwoFactorSetup:
    """2FA setup data for a user."""
    user_id: str
    secret_key: str
    status: TwoFactorStatus
    created_at: datetime
    verified_at: Optional[datetime] = None
    backup_codes: List[str] = field(default_factory=list)
    used_backup_codes: List[str] = field(default_factory=list)
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'backup_codes_remaining': len(self.backup_codes) - len(self.used_backup_codes),
            'failed_attempts': self.failed_attempts,
            'locked_until': self.locked_until.isoformat() if self.locked_until else None,
        }


@dataclass 
class TwoFactorSession:
    """Session with 2FA verification state."""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    two_factor_verified: bool = False
    two_factor_verified_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# =============================================================================
# TOTP IMPLEMENTATION
# =============================================================================

class TOTPGenerator:
    """
    Time-based One-Time Password generator.
    
    Implements RFC 6238 TOTP algorithm compatible with:
    - Google Authenticator
    - Authy
    - Microsoft Authenticator
    - Any TOTP-compatible app
    """
    
    @staticmethod
    def generate_secret(length: int = 32) -> str:
        """
        Generate a random secret key for TOTP.
        
        Returns base32-encoded secret suitable for QR codes.
        """
        # Generate random bytes
        random_bytes = secrets.token_bytes(length)
        # Encode as base32 (standard for TOTP secrets)
        return base64.b32encode(random_bytes).decode('utf-8').rstrip('=')
    
    @staticmethod
    def get_totp_token(secret: str, time_step: int = None) -> str:
        """
        Generate TOTP token for given secret.
        
        Args:
            secret: Base32-encoded secret
            time_step: Optional time step (defaults to current)
            
        Returns:
            6-digit TOTP code as string
        """
        if time_step is None:
            time_step = int(time.time()) // TOTP_INTERVAL
        
        # Decode secret
        # Pad to multiple of 8 for base32
        secret_padded = secret + '=' * ((8 - len(secret) % 8) % 8)
        try:
            key = base64.b32decode(secret_padded.upper())
        except Exception as e:
            logger.error(f"Failed to decode secret: {e}")
            raise ValueError("Invalid secret key")
        
        # Pack time as big-endian 8-byte integer
        msg = struct.pack('>Q', time_step)
        
        # HMAC-SHA1
        h = hmac.new(key, msg, hashlib.sha1).digest()
        
        # Dynamic truncation
        offset = h[-1] & 0x0F
        code = struct.unpack('>I', h[offset:offset + 4])[0]
        code = (code & 0x7FFFFFFF) % (10 ** TOTP_DIGITS)
        
        return str(code).zfill(TOTP_DIGITS)
    
    @staticmethod
    def verify_totp(secret: str, token: str, window: int = 1) -> bool:
        """
        Verify TOTP token with time window.
        
        Args:
            secret: Base32-encoded secret
            token: Token to verify
            window: Number of time steps to check before/after current
            
        Returns:
            True if token is valid
        """
        if not token or len(token) != TOTP_DIGITS:
            return False
        
        current_step = int(time.time()) // TOTP_INTERVAL
        
        # Check current and adjacent time steps
        for offset in range(-window, window + 1):
            expected = TOTPGenerator.get_totp_token(secret, current_step + offset)
            if hmac.compare_digest(token, expected):
                return True
        
        return False
    
    @staticmethod
    def get_provisioning_uri(
        secret: str,
        user_email: str,
        issuer: str = "QUANT_INDUSTRY"
    ) -> str:
        """
        Generate provisioning URI for QR code.
        
        Compatible with Google Authenticator and similar apps.
        """
        import urllib.parse
        
        params = {
            'secret': secret,
            'issuer': issuer,
            'algorithm': TOTP_ALGORITHM.upper(),
            'digits': TOTP_DIGITS,
            'period': TOTP_INTERVAL,
        }
        
        label = urllib.parse.quote(f"{issuer}:{user_email}")
        query = urllib.parse.urlencode(params)
        
        return f"otpauth://totp/{label}?{query}"


# =============================================================================
# BACKUP CODES
# =============================================================================

class BackupCodeManager:
    """
    Manages backup/recovery codes for 2FA.
    
    Backup codes are single-use codes that can be used when
    the user doesn't have access to their authenticator app.
    """
    
    @staticmethod
    def generate_codes(count: int = BACKUP_CODE_COUNT) -> List[str]:
        """
        Generate backup codes.
        
        Returns list of codes in format: XXXX-XXXX
        """
        codes = []
        for _ in range(count):
            # Generate random hex
            code_raw = secrets.token_hex(BACKUP_CODE_LENGTH // 2)
            # Format as XXXX-XXXX
            code = f"{code_raw[:4]}-{code_raw[4:]}"
            codes.append(code.upper())
        
        return codes
    
    @staticmethod
    def hash_code(code: str) -> str:
        """Hash a backup code for storage."""
        # Normalize code
        normalized = code.replace('-', '').upper()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    @staticmethod
    def verify_code(code: str, hashed_codes: List[str]) -> Optional[str]:
        """
        Verify a backup code.
        
        Returns the matched hash if valid, None otherwise.
        """
        code_hash = BackupCodeManager.hash_code(code)
        
        for stored_hash in hashed_codes:
            if hmac.compare_digest(code_hash, stored_hash):
                return stored_hash
        
        return None


# =============================================================================
# 2FA MANAGER
# =============================================================================

class TwoFactorManager:
    """
    Central manager for two-factor authentication.
    
    Handles:
    - Setup and enrollment
    - Verification
    - Backup codes
    - Rate limiting
    - Session management
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
        
        logger.info("TwoFactorManager initialized")
    
    def _init_database(self) -> None:
        """Initialize 2FA database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS two_factor_setup (
                    user_id TEXT PRIMARY KEY,
                    secret_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'disabled',
                    created_at TEXT NOT NULL,
                    verified_at TEXT,
                    backup_codes_json TEXT,
                    used_codes_json TEXT DEFAULT '[]',
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until TEXT
                );
                
                CREATE TABLE IF NOT EXISTS two_factor_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    two_factor_verified INTEGER DEFAULT 0,
                    verified_at TEXT,
                    ip_address TEXT,
                    user_agent TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_2fa_user ON two_factor_setup(user_id);
                CREATE INDEX IF NOT EXISTS idx_2fa_sessions_user ON two_factor_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_2fa_sessions_expires ON two_factor_sessions(expires_at);
            """)
            conn.commit()
    
    # =========================================================================
    # SETUP & ENROLLMENT
    # =========================================================================
    
    def initiate_setup(self, user_id: str) -> Dict[str, Any]:
        """
        Start 2FA setup for a user.
        
        Returns:
            Dictionary with secret, provisioning URI, and backup codes
        """
        # Generate new secret
        secret = TOTPGenerator.generate_secret()
        
        # Generate backup codes
        backup_codes = BackupCodeManager.generate_codes()
        backup_hashes = [BackupCodeManager.hash_code(c) for c in backup_codes]
        
        now = datetime.now(timezone.utc)
        
        # Store setup (pending verification)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO two_factor_setup
                (user_id, secret_key, status, created_at, backup_codes_json, used_codes_json)
                VALUES (?, ?, 'pending', ?, ?, '[]')
            """, (
                user_id,
                secret,
                now.isoformat(),
                json.dumps(backup_hashes),
            ))
            conn.commit()
        
        logger.info(f"2FA setup initiated for user {user_id}")
        
        return {
            'secret': secret,
            'provisioning_uri': TOTPGenerator.get_provisioning_uri(
                secret,
                f"user_{user_id}@quant.industry"
            ),
            'backup_codes': backup_codes,  # Only shown once!
            'status': 'pending',
        }
    
    def confirm_setup(self, user_id: str, token: str) -> bool:
        """
        Confirm 2FA setup by verifying initial token.
        
        User must verify they can generate valid tokens before
        2FA is fully enabled.
        """
        setup = self._get_setup(user_id)
        if not setup:
            logger.warning(f"No pending 2FA setup for user {user_id}")
            return False
        
        if setup.status != TwoFactorStatus.PENDING:
            logger.warning(f"2FA not in pending state for user {user_id}")
            return False
        
        # Verify token
        if not TOTPGenerator.verify_totp(setup.secret_key, token):
            self._record_failed_attempt(user_id)
            return False
        
        # Enable 2FA
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE two_factor_setup
                SET status = 'enabled', verified_at = ?, failed_attempts = 0
                WHERE user_id = ?
            """, (now.isoformat(), user_id))
            conn.commit()
        
        logger.info(f"2FA enabled for user {user_id}")
        return True
    
    def disable(self, user_id: str, token: str) -> bool:
        """
        Disable 2FA for a user (requires valid token).
        """
        # Verify current token first
        if not self.verify(user_id, token):
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE two_factor_setup
                SET status = 'disabled', secret_key = '', backup_codes_json = '[]'
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
        
        logger.info(f"2FA disabled for user {user_id}")
        return True
    
    # =========================================================================
    # VERIFICATION
    # =========================================================================
    
    def verify(self, user_id: str, token: str) -> bool:
        """
        Verify a 2FA token.
        
        Handles:
        - TOTP verification
        - Backup code verification
        - Rate limiting
        - Account lockout
        """
        setup = self._get_setup(user_id)
        if not setup:
            return False
        
        if setup.status != TwoFactorStatus.ENABLED:
            return False
        
        # Check lockout
        if setup.locked_until and datetime.now(timezone.utc) < setup.locked_until:
            logger.warning(f"User {user_id} is locked out until {setup.locked_until}")
            return False
        
        # Try TOTP first
        if TOTPGenerator.verify_totp(setup.secret_key, token):
            self._reset_failed_attempts(user_id)
            return True
        
        # Try backup code
        if self._verify_backup_code(user_id, token, setup):
            self._reset_failed_attempts(user_id)
            return True
        
        # Failed verification
        self._record_failed_attempt(user_id)
        return False
    
    def _verify_backup_code(
        self,
        user_id: str,
        code: str,
        setup: TwoFactorSetup
    ) -> bool:
        """Verify and consume a backup code."""
        # Get unused codes
        unused = [c for c in setup.backup_codes if c not in setup.used_backup_codes]
        
        matched = BackupCodeManager.verify_code(code, unused)
        if not matched:
            return False
        
        # Mark code as used
        with sqlite3.connect(self.db_path) as conn:
            used = setup.used_backup_codes + [matched]
            conn.execute("""
                UPDATE two_factor_setup
                SET used_codes_json = ?
                WHERE user_id = ?
            """, (json.dumps(used), user_id))
            conn.commit()
        
        remaining = len(setup.backup_codes) - len(used)
        logger.info(f"Backup code used for user {user_id}. {remaining} remaining.")
        
        return True
    
    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    
    def _record_failed_attempt(self, user_id: str) -> None:
        """Record a failed verification attempt."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT failed_attempts FROM two_factor_setup WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            attempts = (row[0] if row else 0) + 1
            
            locked_until = None
            status = 'enabled'
            
            if attempts >= MAX_VERIFICATION_ATTEMPTS:
                locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                status = 'locked'
                logger.warning(
                    f"User {user_id} locked out until {locked_until} "
                    f"after {attempts} failed attempts"
                )
            
            conn.execute("""
                UPDATE two_factor_setup
                SET failed_attempts = ?, locked_until = ?, status = ?
                WHERE user_id = ?
            """, (
                attempts,
                locked_until.isoformat() if locked_until else None,
                status,
                user_id,
            ))
            conn.commit()
    
    def _reset_failed_attempts(self, user_id: str) -> None:
        """Reset failed attempts after successful verification."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE two_factor_setup
                SET failed_attempts = 0, locked_until = NULL, status = 'enabled'
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def create_session(
        self,
        user_id: str,
        ip_address: str = None,
        user_agent: str = None,
        duration_hours: int = 24
    ) -> TwoFactorSession:
        """Create a new session requiring 2FA verification."""
        session_id = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=duration_hours)
        
        session = TwoFactorSession(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            expires_at=expires,
            two_factor_verified=False,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO two_factor_sessions
                (session_id, user_id, created_at, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.user_id,
                session.created_at.isoformat(),
                session.expires_at.isoformat(),
                session.ip_address,
                session.user_agent,
            ))
            conn.commit()
        
        return session
    
    def verify_session(self, session_id: str, token: str) -> bool:
        """
        Verify 2FA for a session.
        
        After verification, session is marked as 2FA verified.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, expires_at, two_factor_verified
                FROM two_factor_sessions
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            user_id, expires_at, already_verified = row
            
            # Check expiry
            if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
                return False
            
            # Already verified?
            if already_verified:
                return True
            
            # Verify token
            if not self.verify(user_id, token):
                return False
            
            # Mark session as verified
            now = datetime.now(timezone.utc)
            conn.execute("""
                UPDATE two_factor_sessions
                SET two_factor_verified = 1, verified_at = ?
                WHERE session_id = ?
            """, (now.isoformat(), session_id))
            conn.commit()
        
        return True
    
    def is_session_verified(self, session_id: str) -> bool:
        """Check if a session has completed 2FA verification."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT two_factor_verified, expires_at
                FROM two_factor_sessions
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            verified, expires_at = row
            
            # Check expiry
            if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
                return False
            
            return bool(verified)
    
    def invalidate_session(self, session_id: str) -> None:
        """Invalidate a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM two_factor_sessions WHERE session_id = ?
            """, (session_id,))
            conn.commit()
    
    def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM two_factor_sessions WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            return cursor.rowcount
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_setup(self, user_id: str) -> Optional[TwoFactorSetup]:
        """Get 2FA setup for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT secret_key, status, created_at, verified_at,
                       backup_codes_json, used_codes_json, failed_attempts, locked_until
                FROM two_factor_setup
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return TwoFactorSetup(
                user_id=user_id,
                secret_key=row[0],
                status=TwoFactorStatus(row[1]),
                created_at=datetime.fromisoformat(row[2]),
                verified_at=datetime.fromisoformat(row[3]) if row[3] else None,
                backup_codes=json.loads(row[4]) if row[4] else [],
                used_backup_codes=json.loads(row[5]) if row[5] else [],
                failed_attempts=row[6] or 0,
                locked_until=datetime.fromisoformat(row[7]) if row[7] else None,
            )
    
    def is_enabled(self, user_id: str) -> bool:
        """Check if 2FA is enabled for a user."""
        setup = self._get_setup(user_id)
        return setup is not None and setup.status == TwoFactorStatus.ENABLED
    
    def get_status(self, user_id: str) -> Dict[str, Any]:
        """Get 2FA status for a user."""
        setup = self._get_setup(user_id)
        if not setup:
            return {
                'enabled': False,
                'status': 'disabled',
            }
        return setup.to_dict()
    
    def regenerate_backup_codes(self, user_id: str, token: str) -> Optional[List[str]]:
        """
        Regenerate backup codes (requires valid token).
        
        Returns new codes if successful, None otherwise.
        """
        if not self.verify(user_id, token):
            return None
        
        # Generate new codes
        backup_codes = BackupCodeManager.generate_codes()
        backup_hashes = [BackupCodeManager.hash_code(c) for c in backup_codes]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE two_factor_setup
                SET backup_codes_json = ?, used_codes_json = '[]'
                WHERE user_id = ?
            """, (json.dumps(backup_hashes), user_id))
            conn.commit()
        
        logger.info(f"Backup codes regenerated for user {user_id}")
        return backup_codes


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    'TwoFactorStatus',
    'TwoFactorSetup',
    'TwoFactorSession',
    'TOTPGenerator',
    'BackupCodeManager',
    'TwoFactorManager',
]
