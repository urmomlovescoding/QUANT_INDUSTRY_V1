"""
QUANT_INDUSTRY_V1 Security Module Tests

Tests for encryption, API key management, and access control.
"""

import pytest
import tempfile
import os


class TestEncryptionEngine:
    """Test encryption engine."""

    def test_encrypt_decrypt(self):
        """Test basic encryption and decryption."""
        from security import EncryptionEngine

        engine = EncryptionEngine(master_key='test_key_12345')

        plaintext = "This is a secret API key"
        encrypted = engine.encrypt(plaintext)
        decrypted = engine.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext.encode()

    def test_different_keys_fail(self):
        """Test that different keys produce different results."""
        from security import EncryptionEngine

        engine1 = EncryptionEngine(master_key='key1')
        engine2 = EncryptionEngine(master_key='key2')

        plaintext = "secret"
        encrypted = engine1.encrypt(plaintext)

        # Should fail or produce garbage with different key
        try:
            decrypted = engine2.decrypt(encrypted)
            assert decrypted != plaintext
        except Exception:
            pass  # Expected

    def test_hash_value(self):
        """Test secure hashing."""
        from security import EncryptionEngine

        engine = EncryptionEngine(master_key='test_key')

        hash1 = engine.hash_value("password123")
        hash2 = engine.hash_value("password123")
        hash3 = engine.hash_value("password456")

        assert hash1 == hash2  # Deterministic
        assert hash1 != hash3  # Different inputs

    def test_generate_token(self):
        """Test token generation."""
        from security import EncryptionEngine

        engine = EncryptionEngine()

        token1 = engine.generate_token(32)
        token2 = engine.generate_token(32)

        assert len(token1) > 30  # Base64 encoded
        assert token1 != token2  # Random


class TestAPIKeyManager:
    """Test API key manager."""

    @pytest.fixture
    def key_manager(self):
        """Create temporary key manager."""
        from security import APIKeyManager, EncryptionEngine

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        engine = EncryptionEngine(master_key='test_master_key')
        manager = APIKeyManager(db_path, engine)

        yield manager

        os.unlink(db_path)

    def test_store_and_retrieve(self, key_manager):
        """Test storing and retrieving credentials."""
        key_manager.store_credential(
            name='alpaca_test',
            provider='alpaca',
            api_key='PKTEST123',
            api_secret='secret123456'
        )

        credentials = key_manager.get_credential('alpaca_test')

        assert credentials is not None
        key_hash, api_secret = credentials
        assert api_secret == 'secret123456'

    def test_revoke_credential(self, key_manager):
        """Test credential revocation."""
        key_manager.store_credential(
            name='to_revoke',
            provider='test',
            api_key='key',
            api_secret='secret'
        )

        result = key_manager.revoke_credential('to_revoke')
        assert result

        credentials = key_manager.get_credential('to_revoke')
        assert credentials is None

    def test_rotate_credential(self, key_manager):
        """Test credential rotation."""
        key_manager.store_credential(
            name='rotate_test',
            provider='test',
            api_key='old_key',
            api_secret='old_secret'
        )

        result = key_manager.rotate_credential(
            'rotate_test',
            new_api_key='new_key',
            new_api_secret='new_secret'
        )
        assert result

        _, api_secret = key_manager.get_credential('rotate_test')
        assert api_secret == 'new_secret'

    def test_list_credentials(self, key_manager):
        """Test listing credentials."""
        key_manager.store_credential(
            name='cred1',
            provider='provider1',
            api_key='key1',
            api_secret='secret1'
        )
        key_manager.store_credential(
            name='cred2',
            provider='provider2',
            api_key='key2',
            api_secret='secret2'
        )

        creds = key_manager.list_credentials()
        assert len(creds) == 2
        assert 'secret' not in str(creds)  # No secrets in list


class TestAuditLogger:
    """Test audit logger."""

    @pytest.fixture
    def audit_logger(self):
        """Create temporary audit logger."""
        from security import AuditLogger

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        logger = AuditLogger(db_path)

        yield logger

        os.unlink(db_path)

    def test_log_action(self, audit_logger):
        """Test logging an action."""
        from security import AuditAction

        entry_id = audit_logger.log(
            action=AuditAction.LOGIN,
            user_id='user123',
            resource='system',
            details={'ip': '192.168.1.1'}
        )

        assert entry_id is not None

    def test_query_by_user(self, audit_logger):
        """Test querying by user."""
        from security import AuditAction

        audit_logger.log(AuditAction.LOGIN, 'user1', 'system')
        audit_logger.log(AuditAction.API_CALL, 'user1', 'api')
        audit_logger.log(AuditAction.LOGIN, 'user2', 'system')

        entries = audit_logger.query(user_id='user1')
        assert len(entries) == 2

    def test_suspicious_activity(self, audit_logger):
        """Test suspicious activity detection."""
        from security import AuditAction

        # Log multiple failed logins
        for _ in range(5):
            audit_logger.log(
                AuditAction.LOGIN,
                'attacker',
                'system',
                success=False
            )

        suspicious = audit_logger.get_suspicious_activity(hours=1)
        assert len(suspicious) > 0
        assert suspicious[0]['type'] == 'multiple_failed_logins'


class TestRateLimiter:
    """Test rate limiter."""

    def test_within_limit(self):
        """Test requests within limit."""
        from security import RateLimiter

        limiter = RateLimiter()

        for i in range(5):
            allowed, remaining = limiter.check('test_key', limit=10)
            assert allowed
            assert remaining == 10 - i - 1

    def test_exceeds_limit(self):
        """Test requests exceeding limit."""
        from security import RateLimiter

        limiter = RateLimiter()

        # Exhaust limit
        for _ in range(10):
            limiter.check('test_key', limit=10)

        # Next request should fail
        allowed, remaining = limiter.check('test_key', limit=10)
        assert not allowed
        assert remaining == 0

    def test_reset(self):
        """Test limit reset."""
        from security import RateLimiter

        limiter = RateLimiter()

        # Use some quota
        for _ in range(5):
            limiter.check('test_key', limit=10)

        limiter.reset('test_key')

        allowed, remaining = limiter.check('test_key', limit=10)
        assert allowed
        assert remaining == 9


class TestAccessControl:
    """Test access control."""

    @pytest.fixture
    def access_control(self):
        """Create temporary access control."""
        from security import AccessControl

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        ac = AccessControl(db_path)

        yield ac

        os.unlink(db_path)

    def test_assign_role(self, access_control):
        """Test role assignment."""
        result = access_control.assign_role('user1', 'trader')
        assert result

    def test_check_permission(self, access_control):
        """Test permission check."""
        from security import PermissionLevel

        access_control.assign_role('user1', 'admin')
        access_control.assign_role('user2', 'viewer')

        # Admin should have all permissions
        assert access_control.check_permission(
            'user1', 'trades', PermissionLevel.ADMIN
        )

        # Viewer should only have read
        assert access_control.check_permission(
            'user2', 'data', PermissionLevel.READ
        )
        assert not access_control.check_permission(
            'user2', 'trades', PermissionLevel.EXECUTE
        )

    def test_get_user_permissions(self, access_control):
        """Test getting user permissions."""
        access_control.assign_role('user1', 'trader')

        perms = access_control.get_user_permissions('user1')
        assert len(perms) > 0


class TestSecurityManager:
    """Test security manager integration."""

    @pytest.fixture
    def security_manager(self):
        """Create temporary security manager."""
        from security import SecurityManager

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = SecurityManager(db_path, master_key='test_key')

        yield manager

        os.unlink(db_path)

    def test_secure_api_call(self, security_manager):
        """Test secure API call workflow."""
        # Setup
        security_manager.key_manager.store_credential(
            'alpaca_live', 'alpaca', 'key', 'secret'
        )
        security_manager.access_control.assign_role('user1', 'admin')

        # Should succeed
        credentials = security_manager.secure_api_call(
            user_id='user1',
            provider='alpaca',
            credential_name='alpaca_live'
        )

        assert credentials is not None

    def test_security_status(self, security_manager):
        """Test security status report."""
        status = security_manager.get_security_status()

        assert 'total_credentials' in status
        assert 'suspicious_activities' in status


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
