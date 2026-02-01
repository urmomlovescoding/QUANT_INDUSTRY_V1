"""
Database Connection Management
==============================
Handles sync and async database connections with connection pooling.
"""

import os
from pathlib import Path
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional
import logging

logger = logging.getLogger(__name__)

# Import config first to ensure env is loaded
from config.env import config

# SQLAlchemy imports
try:
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import QueuePool, StaticPool
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.warning("SQLAlchemy not installed - database features disabled")

# Async support
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False

# Redis support
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.debug("aioredis not installed - Redis caching disabled")


# ============== DATABASE SETUP ==============

def get_database_url() -> str:
    """Get database URL from config or default to SQLite."""
    db_url = config.DATABASE_URL
    
    # Default to SQLite if not configured or if PostgreSQL isn't available
    if not db_url or db_url.startswith('postgresql://'):
        # Check if we can connect to PostgreSQL
        try:
            import psycopg2
            # Could test connection here
        except ImportError:
            # Fall back to SQLite
            data_dir = Path(__file__).parent.parent.parent / 'data'
            data_dir.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{data_dir / 'quant.db'}"
            logger.info(f"Using SQLite database: {db_url}")
    
    return db_url


def get_async_database_url() -> str:
    """Get async-compatible database URL."""
    url = get_database_url()
    
    # Convert sync URLs to async
    if url.startswith('sqlite://'):
        return url.replace('sqlite://', 'sqlite+aiosqlite://')
    elif url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+asyncpg://')
    
    return url


# Engine singletons
_engine = None
_async_engine = None
_SessionLocal = None
_AsyncSessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    
    if _engine is None:
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SQLAlchemy not installed")
        
        db_url = get_database_url()
        
        if db_url.startswith('sqlite://'):
            # SQLite-specific settings
            _engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=config.DEBUG
            )
            
            # Enable foreign keys for SQLite
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()
        else:
            # PostgreSQL/other settings
            _engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=config.DEBUG
            )
    
    return _engine


def get_async_engine():
    """Get or create the async database engine."""
    global _async_engine
    
    if _async_engine is None:
        if not ASYNC_AVAILABLE:
            raise RuntimeError("Async SQLAlchemy not available")
        
        db_url = get_async_database_url()
        
        if 'sqlite' in db_url:
            _async_engine = create_async_engine(
                db_url,
                echo=config.DEBUG
            )
        else:
            _async_engine = create_async_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=config.DEBUG
            )
    
    return _async_engine


def get_session_factory():
    """Get session factory."""
    global _SessionLocal
    
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    
    return _SessionLocal


def get_async_session_factory():
    """Get async session factory."""
    global _AsyncSessionLocal
    
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    return _AsyncSessionLocal


# ============== SESSION MANAGEMENT ==============

class DatabaseSession:
    """Context manager for database sessions."""
    
    def __init__(self, autocommit: bool = False):
        self.autocommit = autocommit
        self.session: Optional[Session] = None
    
    def __enter__(self) -> Session:
        SessionLocal = get_session_factory()
        self.session = SessionLocal()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type is not None:
                self.session.rollback()
            elif self.autocommit:
                self.session.commit()
            self.session.close()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session (sync)."""
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (async)."""
    AsyncSessionLocal = get_async_session_factory()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============== REDIS CACHE ==============

_redis_pool = None


async def get_redis():
    """Get Redis connection for caching."""
    global _redis_pool
    
    if not REDIS_AVAILABLE:
        return None
    
    if not config.redis_configured:
        return None
    
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    return _redis_pool


# ============== INITIALIZATION ==============

def init_database():
    """Initialize database - create all tables."""
    from .models import Base
    
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    
    logger.info("[OK] Database initialized")


async def init_async_database():
    """Initialize database asynchronously."""
    from .models import Base
    
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("[OK] Async database initialized")
