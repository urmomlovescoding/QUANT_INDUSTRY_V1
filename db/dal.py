"""
QUANT_INDUSTRY_V1 Database Access Layer (DAL)

This module provides the core database management functionality.
All SQLite operations MUST go through this layer.

Features:
- Connection pooling with WAL mode
- Transaction management
- Migration support
- Health checks
"""

import sqlite3
import threading
import hashlib
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Generator, Callable
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Thread-local storage for connections
_local = threading.local()

# Global database manager instance
_db_manager: Optional['DatabaseManager'] = None


class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


class ConnectionError(DatabaseError):
    """Database connection error."""
    pass


class MigrationError(DatabaseError):
    """Database migration error."""
    pass


class IntegrityError(DatabaseError):
    """Data integrity error."""
    pass


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    """Convert sqlite3 row to dictionary."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class DatabaseManager:
    """
    SQLite Database Manager with connection pooling and WAL mode.

    Usage:
        db = DatabaseManager('/path/to/db.sqlite')
        db.initialize()

        with db.transaction() as conn:
            conn.execute("INSERT INTO ...")
    """

    def __init__(
        self,
        db_path: str,
        wal_mode: bool = True,
        foreign_keys: bool = True,
        synchronous: str = 'NORMAL',
        cache_size: int = -64000,  # 64MB
    ):
        self.db_path = Path(db_path).resolve()
        self.wal_mode = wal_mode
        self.foreign_keys = foreign_keys
        self.synchronous = synchronous
        self.cache_size = cache_size
        self._lock = threading.RLock()
        self._initialized = False

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(_local, 'connection') or _local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
                isolation_level='DEFERRED',  # Use deferred transactions
            )
            conn.row_factory = dict_factory

            # Apply pragmas
            if self.wal_mode:
                conn.execute("PRAGMA journal_mode=WAL")
            if self.foreign_keys:
                conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(f"PRAGMA synchronous={self.synchronous}")
            conn.execute(f"PRAGMA cache_size={self.cache_size}")
            conn.execute("PRAGMA temp_store=MEMORY")

            _local.connection = conn
            logger.debug(f"Created new connection for thread {threading.current_thread().name}")

        return _local.connection

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection context."""
        yield self._get_connection()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Execute operations within a transaction.

        Usage:
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...")
                conn.execute("UPDATE ...")
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise

    def execute(
        self,
        sql: str,
        params: tuple = (),
        fetch: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement
            params: Parameters for the statement
            fetch: Whether to fetch results

        Returns:
            List of rows if fetch=True, None otherwise
        """
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            if fetch:
                return cursor.fetchall()
            return None

    def execute_many(
        self,
        sql: str,
        params_list: List[tuple]
    ) -> int:
        """
        Execute a SQL statement for multiple parameter sets.

        Returns:
            Number of rows affected
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            return cursor.rowcount

    def fetch_one(
        self,
        sql: str,
        params: tuple = ()
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()

    def fetch_all(
        self,
        sql: str,
        params: tuple = ()
    ) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def insert(
        self,
        table: str,
        data: Dict[str, Any],
        or_replace: bool = False
    ) -> int:
        """
        Insert a row into a table.

        Args:
            table: Table name
            data: Dictionary of column -> value
            or_replace: Use INSERT OR REPLACE

        Returns:
            Inserted row ID
        """
        columns = list(data.keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)

        verb = "INSERT OR REPLACE" if or_replace else "INSERT"
        sql = f"{verb} INTO {table} ({column_names}) VALUES ({placeholders})"

        with self.connection() as conn:
            cursor = conn.execute(sql, tuple(data.values()))
            return cursor.lastrowid

    def update(
        self,
        table: str,
        data: Dict[str, Any],
        where: str,
        where_params: tuple = ()
    ) -> int:
        """
        Update rows in a table.

        Args:
            table: Table name
            data: Dictionary of column -> value to update
            where: WHERE clause
            where_params: Parameters for WHERE clause

        Returns:
            Number of rows affected
        """
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        params = tuple(data.values()) + where_params

        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount

    def delete(
        self,
        table: str,
        where: str,
        where_params: tuple = ()
    ) -> int:
        """
        Delete rows from a table.

        Args:
            table: Table name
            where: WHERE clause
            where_params: Parameters for WHERE clause

        Returns:
            Number of rows affected
        """
        sql = f"DELETE FROM {table} WHERE {where}"

        with self.connection() as conn:
            cursor = conn.execute(sql, where_params)
            return cursor.rowcount

    def initialize(self, schema_path: Optional[str] = None) -> None:
        """
        Initialize the database with schema.

        Args:
            schema_path: Path to schema.sql file. If None, uses default.
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            if schema_path is None:
                schema_path = Path(__file__).parent / 'schema.sql'

            schema_path = Path(schema_path)
            if not schema_path.exists():
                raise MigrationError(f"Schema file not found: {schema_path}")

            schema_sql = schema_path.read_text()

            with self.transaction() as conn:
                conn.executescript(schema_sql)

            self._initialized = True
            logger.info(f"Database initialized at {self.db_path}")

    def run_migration(
        self,
        migration_sql: str,
        migration_name: str
    ) -> bool:
        """
        Run a database migration.

        Args:
            migration_sql: SQL to execute
            migration_name: Name/identifier for the migration

        Returns:
            True if migration was applied, False if already applied
        """
        # Check if migration was already applied
        check_sql = """
            SELECT 1 FROM audit_log
            WHERE action = 'execute'
            AND object_type = 'migration'
            AND object_id = ?
        """
        existing = self.fetch_one(check_sql, (migration_name,))
        if existing:
            logger.info(f"Migration {migration_name} already applied")
            return False

        try:
            with self.transaction() as conn:
                conn.executescript(migration_sql)

                # Record migration
                conn.execute("""
                    INSERT INTO audit_log (actor, action, object_type, object_id, details_json)
                    VALUES ('system', 'execute', 'migration', ?, ?)
                """, (migration_name, f'{{"applied_at": "{datetime.utcnow().isoformat()}"}}'))

            logger.info(f"Migration {migration_name} applied successfully")
            return True

        except Exception as e:
            logger.error(f"Migration {migration_name} failed: {e}")
            raise MigrationError(f"Migration failed: {e}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform database health check.

        Returns:
            Dictionary with health metrics
        """
        health = {
            'status': 'healthy',
            'db_path': str(self.db_path),
            'db_size_mb': 0,
            'wal_size_mb': 0,
            'table_counts': {},
            'index_count': 0,
            'integrity_check': 'unknown',
        }

        try:
            # Database file size
            if self.db_path.exists():
                health['db_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)

            wal_path = Path(str(self.db_path) + '-wal')
            if wal_path.exists():
                health['wal_size_mb'] = wal_path.stat().st_size / (1024 * 1024)

            # Table counts
            tables = self.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            for table in tables:
                count = self.fetch_one(f"SELECT COUNT(*) as cnt FROM {table['name']}")
                health['table_counts'][table['name']] = count['cnt'] if count else 0

            # Index count
            indexes = self.fetch_one(
                "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='index'"
            )
            health['index_count'] = indexes['cnt'] if indexes else 0

            # Quick integrity check
            integrity = self.fetch_one("PRAGMA quick_check")
            health['integrity_check'] = integrity['quick_check'] if integrity else 'failed'

            if health['integrity_check'] != 'ok':
                health['status'] = 'degraded'

        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            logger.error(f"Health check failed: {e}")

        return health

    def vacuum(self) -> None:
        """Optimize database by vacuuming."""
        with self.connection() as conn:
            conn.execute("VACUUM")
        logger.info("Database vacuumed")

    def checkpoint(self) -> None:
        """Force WAL checkpoint."""
        with self.connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        logger.info("WAL checkpoint completed")

    def close(self) -> None:
        """Close all connections."""
        if hasattr(_local, 'connection') and _local.connection:
            _local.connection.close()
            _local.connection = None
            logger.debug(f"Closed connection for thread {threading.current_thread().name}")

    def get_schema_hash(self) -> str:
        """Get hash of current schema for reproducibility."""
        tables = self.fetch_all(
            "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        schema_str = '\n'.join([t['sql'] or '' for t in tables])
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]


def get_db() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        raise DatabaseError("Database not initialized. Call init_db() first.")
    return _db_manager


def init_db(
    db_path: Optional[str] = None,
    **kwargs
) -> DatabaseManager:
    """
    Initialize the global database manager.

    Args:
        db_path: Path to SQLite database file
        **kwargs: Additional arguments for DatabaseManager

    Returns:
        Initialized DatabaseManager instance
    """
    global _db_manager

    if db_path is None:
        # Default path
        db_path = os.environ.get(
            'QUANT_DB_PATH',
            str(Path.home() / 'QUANT_INDUSTRY_V1' / 'data' / 'quant.db')
        )

    _db_manager = DatabaseManager(db_path, **kwargs)
    _db_manager.initialize()

    logger.info(f"Database initialized at {db_path}")
    return _db_manager
