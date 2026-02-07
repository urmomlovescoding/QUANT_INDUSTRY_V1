"""
Create Admin/Dev Account
Run this script to create a developer admin account.

Usage:
    python create_admin.py
    python create_admin.py --email admin@example.com --password MySecurePass!
"""
import getpass
import logging
import os
import secrets
import sys

sys.path.insert(0, '..')

from database.connection import get_session_factory, init_database
from database.models import User, Organization, UserRole, OrgTier, OrgStatus
from auth.jwt_auth import hash_password

logger = logging.getLogger(__name__)


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_admin(email: str = None, password: str = None):
    """Create an admin account with provided or prompted credentials."""
    # Initialize database
    init_database()

    # Get credentials from args, env, or prompt
    email = email or os.environ.get('ADMIN_EMAIL')
    password = password or os.environ.get('ADMIN_PASSWORD')

    if not email:
        email = input('Enter admin email: ').strip()
        if not email:
            logger.error("Email is required")
            return

    if not password:
        password = getpass.getpass('Enter admin password (leave blank to auto-generate): ').strip()
        if not password:
            password = generate_secure_password()
            print(f'Generated password: {password}')
            print('IMPORTANT: Save this password now. It will not be shown again.')

    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            logger.info(f'Admin account already exists: {existing.email}')
            return

        # Create organization
        org = Organization(
            name='Stock Suite Development',
            slug='stocksuite-dev',
            tier=OrgTier.ENTERPRISE,
            status=OrgStatus.ACTIVE,
        )
        db.add(org)
        db.flush()

        # Create admin user
        admin = User(
            organization_id=org.id,
            email=email,
            password_hash=hash_password(password),
            full_name='Admin',
            role=UserRole.OWNER,
            is_active=True,
            email_verified=True,
        )
        db.add(admin)
        db.commit()

        logger.info(f'Admin account created: {email} (role: {admin.role.value})')

    except Exception as e:
        db.rollback()
        logger.error(f'Error creating admin: {e}')
    finally:
        db.close()


if __name__ == '__main__':
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Create admin account')
    parser.add_argument('--email', help='Admin email address')
    parser.add_argument('--password', help='Admin password (will prompt if not provided)')
    args = parser.parse_args()
    create_admin(email=args.email, password=args.password)
