"""
Database Abstraction Layer for QUANT INDUSTRY
==============================================
Provides a unified interface for database operations with:
- Connection pooling
- Transaction management
- Query building
- Migration support

Matches quant-platform pattern for data persistence.
"""

import logging
import os
import re
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue, Empty
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, TypeVar, Union

logger = logging.getLogger(__name__)

# SECURITY: Pattern for valid SQL identifiers (table names, column names)
# Only allows alphanumeric characters and underscores, must start with letter/underscore
_VALID_SQL_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_sql_identifier(name: str, context: str = "identifier") -> str:
    """
    Validate a SQL identifier (table name, column name) to prevent SQL injection.

    Args:
        name: The identifier to validate
        context: Description for error messages (e.g., "column name", "table name")

    Returns:
        The validated identifier

    Raises:
        ValueError: If the identifier is invalid
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"Invalid {context}: must be a non-empty string")

    # Remove any whitespace
    name = name.strip()

    if not _VALID_SQL_IDENTIFIER.match(name):
        raise ValueError(
            f"Invalid {context} '{name}': must contain only alphanumeric characters "
            "and underscores, and must start with a letter or underscore"
        )

    # Additional check: prevent SQL keywords from being used as identifiers
    sql_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
                    'ALTER', 'TRUNCATE', 'EXEC', 'EXECUTE', 'UNION', 'WHERE'}
    if name.upper() in sql_keywords:
        raise ValueError(f"Invalid {context} '{name}': SQL keywords are not allowed")

    return name


def _validate_order_by(order_by: str) -> str:
    """
    Validate ORDER BY clause to prevent SQL injection.

    Accepts formats like:
        - "column_name"
        - "column_name ASC"
        - "column_name DESC"
        - "col1 ASC, col2 DESC"

    Returns:
        Validated ORDER BY string
    """
    if not order_by or not isinstance(order_by, str):
        raise ValueError("ORDER BY must be a non-empty string")

    parts = []
    for part in order_by.split(','):
        part = part.strip()
        tokens = part.split()

        if len(tokens) == 0:
            continue
        elif len(tokens) == 1:
            # Just column name
            parts.append(_validate_sql_identifier(tokens[0], "column name"))
        elif len(tokens) == 2:
            # Column name + direction
            col = _validate_sql_identifier(tokens[0], "column name")
            direction = tokens[1].upper()
            if direction not in ('ASC', 'DESC'):
                raise ValueError(f"Invalid sort direction: {tokens[1]}")
            parts.append(f"{col} {direction}")
        else:
            raise ValueError(f"Invalid ORDER BY format: {part}")

    if not parts:
        raise ValueError("ORDER BY clause is empty")

    return ", ".join(parts)

T = TypeVar('T')


class DatabaseType(Enum):
    """Supported database types"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


@dataclass
class ConnectionConfig:
    """Database connection configuration"""
    db_type: DatabaseType = DatabaseType.SQLITE
    database: str = "quant_industry.db"
    host: str = "localhost"
    port: int = 5432
    username: str = ""
    password: str = ""
    pool_size: int = 5
    max_overflow: int = 10
    timeout: float = 30.0
    echo: bool = False

    @classmethod
    def from_env(cls) -> 'ConnectionConfig':
        """Create config from environment variables"""
        db_type_str = os.getenv("DB_TYPE", "sqlite").lower()
        db_type = DatabaseType(db_type_str) if db_type_str in [t.value for t in DatabaseType] else DatabaseType.SQLITE

        return cls(
            db_type=db_type,
            database=os.getenv("DB_NAME", "quant_industry.db"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            username=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        )


@dataclass
class QueryResult:
    """Result of a database query"""
    rows: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time_ms: float
    affected_rows: int = 0


class ConnectionPool:
    """
    Simple connection pool for SQLite.
    For production, use SQLAlchemy or similar for advanced pooling.
    """

    def __init__(
        self,
        database: str,
        pool_size: int = 5,
        timeout: float = 30.0
    ):
        self.database = database
        self.pool_size = pool_size
        self.timeout = timeout

        self._pool: Queue = Queue(maxsize=pool_size)
        self._size = 0
        self._lock = threading.Lock()

        # Pre-create connections
        for _ in range(pool_size):
            self._add_connection()

    def _add_connection(self) -> None:
        """Add a new connection to the pool"""
        conn = sqlite3.connect(
            self.database,
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        self._pool.put(conn)
        self._size += 1

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool"""
        try:
            conn = self._pool.get(timeout=self.timeout)
            # Verify connection is valid
            try:
                conn.execute("SELECT 1")
            except sqlite3.Error:
                # Connection is stale, create new one
                conn = sqlite3.connect(
                    self.database,
                    timeout=self.timeout,
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except Empty:
            raise TimeoutError("Timeout waiting for database connection")

    def return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool"""
        try:
            self._pool.put_nowait(conn)
        except Exception:
            # Pool is full, close connection
            try:
                conn.close()
            except Exception:
                pass

    def close_all(self) -> None:
        """Close all connections in the pool"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters"""

    @abstractmethod
    def execute(
        self,
        query: str,
        params: Tuple = None
    ) -> QueryResult:
        """Execute a query"""
        pass

    @abstractmethod
    def execute_many(
        self,
        query: str,
        params_list: List[Tuple]
    ) -> int:
        """Execute a query with multiple parameter sets"""
        pass

    @abstractmethod
    def fetch_one(
        self,
        query: str,
        params: Tuple = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        pass

    @abstractmethod
    def fetch_all(
        self,
        query: str,
        params: Tuple = None
    ) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        pass

    @abstractmethod
    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for transactions"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the database connection"""
        pass


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter"""

    def __init__(self, config: ConnectionConfig):
        self.config = config

        # Ensure directory exists
        db_dir = os.path.dirname(config.database)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._pool = ConnectionPool(
            database=config.database,
            pool_size=config.pool_size,
            timeout=config.timeout
        )
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get connection for current thread"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._pool.get_connection()
        return self._local.conn

    def _return_connection(self) -> None:
        """Return connection for current thread"""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._pool.return_connection(self._local.conn)
            self._local.conn = None

    def execute(
        self,
        query: str,
        params: Tuple = None
    ) -> QueryResult:
        """Execute a query"""
        start_time = time.time()
        conn = self._get_connection()

        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Commit for non-SELECT queries
            if not query.strip().upper().startswith("SELECT"):
                conn.commit()
                affected = cursor.rowcount
                return QueryResult(
                    rows=[],
                    row_count=0,
                    columns=[],
                    execution_time_ms=(time.time() - start_time) * 1000,
                    affected_rows=affected
                )

            # Fetch results for SELECT
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            return QueryResult(
                rows=[dict(row) for row in rows],
                row_count=len(rows),
                columns=columns,
                execution_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            conn.rollback()
            raise

    def execute_many(
        self,
        query: str,
        params_list: List[Tuple]
    ) -> int:
        """Execute a query with multiple parameter sets"""
        conn = self._get_connection()

        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise

    def fetch_one(
        self,
        query: str,
        params: Tuple = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        result = self.execute(query, params)
        return result.rows[0] if result.rows else None

    def fetch_all(
        self,
        query: str,
        params: Tuple = None
    ) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        result = self.execute(query, params)
        return result.rows

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for transactions"""
        conn = self._get_connection()
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        """Close all connections"""
        self._return_connection()
        self._pool.close_all()


class Database:
    """
    High-level database interface with query building.

    Example:
        db = Database()
        db.create_table("signals", {
            "id": "INTEGER PRIMARY KEY",
            "symbol": "TEXT NOT NULL",
            "direction": "TEXT",
            "confidence": "REAL",
            "timestamp": "TEXT"
        })

        db.insert("signals", {
            "symbol": "AAPL",
            "direction": "LONG",
            "confidence": 0.85
        })

        signals = db.select("signals", where={"symbol": "AAPL"})
    """

    def __init__(self, config: ConnectionConfig = None):
        self.config = config or ConnectionConfig.from_env()

        if self.config.db_type == DatabaseType.SQLITE:
            self._adapter = SQLiteAdapter(self.config)
        else:
            raise NotImplementedError(f"Database type {self.config.db_type} not implemented")

        self._migrations: List[Tuple[int, str, Callable]] = []

    # ============== QUERY EXECUTION ==============

    def execute(
        self,
        query: str,
        params: Tuple = None
    ) -> QueryResult:
        """Execute a raw SQL query"""
        if self.config.echo:
            logger.debug(f"SQL: {query} | Params: {params}")
        return self._adapter.execute(query, params)

    def execute_many(
        self,
        query: str,
        params_list: List[Tuple]
    ) -> int:
        """Execute a query with multiple parameter sets"""
        return self._adapter.execute_many(query, params_list)

    def fetch_one(
        self,
        query: str,
        params: Tuple = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        return self._adapter.fetch_one(query, params)

    def fetch_all(
        self,
        query: str,
        params: Tuple = None
    ) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        return self._adapter.fetch_all(query, params)

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Transaction context manager"""
        with self._adapter.transaction():
            yield

    # ============== QUERY BUILDING ==============

    def create_table(
        self,
        table: str,
        columns: Dict[str, str],
        if_not_exists: bool = True
    ) -> None:
        """Create a table"""
        exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        cols = ", ".join(f"{name} {definition}" for name, definition in columns.items())
        query = f"CREATE TABLE {exists_clause}{table} ({cols})"
        self.execute(query)

    def insert(
        self,
        table: str,
        data: Dict[str, Any],
        or_replace: bool = False
    ) -> int:
        """Insert a row and return lastrowid"""
        action = "INSERT OR REPLACE" if or_replace else "INSERT"
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        query = f"{action} INTO {table} ({columns}) VALUES ({placeholders})"
        result = self.execute(query, tuple(data.values()))
        return result.affected_rows

    def insert_many(
        self,
        table: str,
        data_list: List[Dict[str, Any]]
    ) -> int:
        """Insert multiple rows"""
        if not data_list:
            return 0

        columns = ", ".join(data_list[0].keys())
        placeholders = ", ".join("?" * len(data_list[0]))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        params_list = [tuple(d.values()) for d in data_list]
        return self.execute_many(query, params_list)

    def select(
        self,
        table: str,
        columns: List[str] = None,
        where: Dict[str, Any] = None,
        order_by: str = None,
        limit: int = None,
        offset: int = None
    ) -> List[Dict[str, Any]]:
        """Select rows from a table with SQL injection protection."""
        # SECURITY: Validate table name
        table = _validate_sql_identifier(table, "table name")

        # SECURITY: Validate column names
        if columns:
            validated_cols = [_validate_sql_identifier(c, "column name") for c in columns]
            cols = ", ".join(validated_cols)
        else:
            cols = "*"

        query = f"SELECT {cols} FROM {table}"
        params = []

        if where:
            # SECURITY: Validate WHERE column names
            validated_where = {_validate_sql_identifier(k, "column name"): v for k, v in where.items()}
            conditions = " AND ".join(f"{k} = ?" for k in validated_where.keys())
            query += f" WHERE {conditions}"
            params.extend(validated_where.values())

        if order_by:
            # SECURITY: Validate ORDER BY clause
            validated_order = _validate_order_by(order_by)
            query += f" ORDER BY {validated_order}"

        if limit is not None:
            # SECURITY: Ensure limit is an integer
            if not isinstance(limit, int) or limit < 0:
                raise ValueError("LIMIT must be a non-negative integer")
            query += f" LIMIT {limit}"

        if offset is not None:
            # SECURITY: Ensure offset is an integer
            if not isinstance(offset, int) or offset < 0:
                raise ValueError("OFFSET must be a non-negative integer")
            query += f" OFFSET {offset}"

        return self.fetch_all(query, tuple(params) if params else None)

    def update(
        self,
        table: str,
        data: Dict[str, Any],
        where: Dict[str, Any]
    ) -> int:
        """Update rows in a table with SQL injection protection."""
        # SECURITY: Validate table name
        table = _validate_sql_identifier(table, "table name")

        # SECURITY: Validate column names in SET clause
        validated_data = {_validate_sql_identifier(k, "column name"): v for k, v in data.items()}
        set_clause = ", ".join(f"{k} = ?" for k in validated_data.keys())

        # SECURITY: Validate column names in WHERE clause
        validated_where = {_validate_sql_identifier(k, "column name"): v for k, v in where.items()}
        where_clause = " AND ".join(f"{k} = ?" for k in validated_where.keys())

        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = list(validated_data.values()) + list(validated_where.values())

        result = self.execute(query, tuple(params))
        return result.affected_rows

    def delete(
        self,
        table: str,
        where: Dict[str, Any]
    ) -> int:
        """Delete rows from a table with SQL injection protection."""
        # SECURITY: Validate table name
        table = _validate_sql_identifier(table, "table name")

        # SECURITY: Validate column names in WHERE clause
        validated_where = {_validate_sql_identifier(k, "column name"): v for k, v in where.items()}
        where_clause = " AND ".join(f"{k} = ?" for k in validated_where.keys())
        query = f"DELETE FROM {table} WHERE {where_clause}"

        result = self.execute(query, tuple(validated_where.values()))
        return result.affected_rows

    def count(
        self,
        table: str,
        where: Dict[str, Any] = None
    ) -> int:
        """Count rows in a table"""
        query = f"SELECT COUNT(*) as count FROM {table}"
        params = []

        if where:
            conditions = " AND ".join(f"{k} = ?" for k in where.keys())
            query += f" WHERE {conditions}"
            params.extend(where.values())

        result = self.fetch_one(query, tuple(params) if params else None)
        return result['count'] if result else 0

    def exists(
        self,
        table: str,
        where: Dict[str, Any]
    ) -> bool:
        """Check if a row exists"""
        return self.count(table, where) > 0

    # ============== MIGRATIONS ==============

    def register_migration(
        self,
        version: int,
        name: str,
        migrate_fn: Callable[['Database'], None]
    ) -> None:
        """Register a migration"""
        self._migrations.append((version, name, migrate_fn))

    def run_migrations(self) -> List[str]:
        """Run pending migrations"""
        # Create migrations table
        self.create_table("_migrations", {
            "version": "INTEGER PRIMARY KEY",
            "name": "TEXT NOT NULL",
            "applied_at": "TEXT NOT NULL"
        })

        # Get applied migrations
        applied = {m['version'] for m in self.select("_migrations")}

        # Run pending migrations
        applied_names = []
        for version, name, migrate_fn in sorted(self._migrations):
            if version not in applied:
                logger.info(f"Running migration {version}: {name}")
                try:
                    with self.transaction():
                        migrate_fn(self)
                        self.insert("_migrations", {
                            "version": version,
                            "name": name,
                            "applied_at": datetime.now().isoformat()
                        })
                    applied_names.append(f"{version}: {name}")
                except Exception as e:
                    logger.error(f"Migration {version} failed: {e}")
                    raise

        return applied_names

    # ============== UTILITIES ==============

    def table_exists(self, table: str) -> bool:
        """Check if a table exists"""
        result = self.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return result is not None

    def get_tables(self) -> List[str]:
        """Get list of all tables"""
        rows = self.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r['name'] for r in rows if not r['name'].startswith('_')]

    def get_columns(self, table: str) -> List[Dict[str, Any]]:
        """Get column info for a table"""
        rows = self.fetch_all(f"PRAGMA table_info({table})")
        return rows

    def close(self) -> None:
        """Close database connection"""
        self._adapter.close()


# ============== REPOSITORY PATTERN ==============

class Repository(ABC):
    """
    Abstract repository for entity persistence.

    Example:
        class SignalRepository(Repository[Signal]):
            def __init__(self, db: Database):
                super().__init__(db, "signals")

            def to_entity(self, row: Dict) -> Signal:
                return Signal(**row)

            def to_row(self, entity: Signal) -> Dict:
                return entity.__dict__
    """

    def __init__(self, db: Database, table: str):
        self.db = db
        self.table = table

    @abstractmethod
    def to_entity(self, row: Dict[str, Any]) -> T:
        """Convert a database row to an entity"""
        pass

    @abstractmethod
    def to_row(self, entity: T) -> Dict[str, Any]:
        """Convert an entity to a database row"""
        pass

    def find_by_id(self, id: Any) -> Optional[T]:
        """Find entity by ID"""
        row = self.db.fetch_one(
            f"SELECT * FROM {self.table} WHERE id = ?",
            (id,)
        )
        return self.to_entity(row) if row else None

    def find_all(
        self,
        limit: int = None,
        offset: int = None
    ) -> List[T]:
        """Find all entities"""
        rows = self.db.select(self.table, limit=limit, offset=offset)
        return [self.to_entity(row) for row in rows]

    def find_by(
        self,
        where: Dict[str, Any],
        order_by: str = None,
        limit: int = None
    ) -> List[T]:
        """Find entities matching criteria"""
        rows = self.db.select(
            self.table,
            where=where,
            order_by=order_by,
            limit=limit
        )
        return [self.to_entity(row) for row in rows]

    def save(self, entity: T) -> T:
        """Save an entity (insert or update)"""
        row = self.to_row(entity)
        self.db.insert(self.table, row, or_replace=True)
        return entity

    def save_many(self, entities: List[T]) -> int:
        """Save multiple entities"""
        rows = [self.to_row(e) for e in entities]
        return self.db.insert_many(self.table, rows)

    def delete(self, entity: T) -> bool:
        """Delete an entity"""
        row = self.to_row(entity)
        if 'id' in row:
            affected = self.db.delete(self.table, {"id": row['id']})
            return affected > 0
        return False

    def count(self, where: Dict[str, Any] = None) -> int:
        """Count entities"""
        return self.db.count(self.table, where)


# ============== SINGLETON ==============

_database: Optional[Database] = None


def get_database(config: ConnectionConfig = None) -> Database:
    """Get or create the global database instance"""
    global _database

    if _database is None:
        _database = Database(config)

    return _database


def reset_database() -> None:
    """Reset the global database instance"""
    global _database
    if _database:
        _database.close()
    _database = None
