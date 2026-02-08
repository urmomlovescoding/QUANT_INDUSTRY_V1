"""
Create Admin/Dev Account
Run this script to create a developer admin account
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.connection import get_session_factory, init_database
from database.models import User, Organization, UserRole, OrgTier, OrgStatus
from auth.jwt_auth import hash_password

def create_admin():
    # Initialize database
    init_database()

    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.email == 'dev@stocksuite.io').first()
        if existing:
            print(f'Admin account already exists: {existing.email}')
            print(f'Role: {existing.role.value}')
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
            email='dev@stocksuite.io',
            password_hash=hash_password('DevAdmin123!'),
            full_name='Dev Admin',
            role=UserRole.OWNER,
            is_active=True,
            email_verified=True,
        )
        db.add(admin)
        db.commit()

        print('=' * 50)
        print('ADMIN ACCOUNT CREATED')
        print('=' * 50)
        print(f'Email:    dev@stocksuite.io')
        print(f'Password: DevAdmin123!')
        print(f'Role:     {admin.role.value}')
        print(f'Org:      {org.name} ({org.tier.value})')
        print('=' * 50)

    except Exception as e:
        db.rollback()
        print(f'Error: {e}')
    finally:
        db.close()

if __name__ == '__main__':
    create_admin()
