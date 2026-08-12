"""Database connection and transaction manager supporting both SQLite and PostgreSQL (Supabase) with retry logic."""
import sqlite3
import threading
import time
from typing import Tuple, Any
from config.config import DATABASE_PATH, DATABASE_URL, LOCAL_MODE, DB_TIMEOUT_SECONDS, logger

# Thread-local storage to track active transaction connections
_thread_local = threading.local()

class PostgresCursorWrapper:
    """Wraps a psycopg2 cursor to adjust SQLite '?' placeholders to PostgreSQL '%s'."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query: str, vars: Any = None):
        if query and isinstance(query, str):
            query = query.replace("?", "%s")
        return self._cursor.execute(query, vars)

    def executemany(self, query: str, vars_list: Any):
        if query and isinstance(query, str):
            query = query.replace("?", "%s")
        return self._cursor.executemany(query, vars_list)

    def __iter__(self):
        return iter(self._cursor)

    def __next__(self):
        return next(self._cursor)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class PostgresConnectionWrapper:
    """Wraps a psycopg2 connection to mimic SQLite behavior and support connection pooling."""
    def __init__(self, conn, manager):
        self._conn = conn
        self._manager = manager

    def cursor(self, *args, **kwargs):
        import psycopg2.extras
        kwargs.setdefault("cursor_factory", psycopg2.extras.DictCursor)
        raw_cursor = self._conn.cursor(*args, **kwargs)
        return PostgresCursorWrapper(raw_cursor)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._manager and self._conn:
            self._manager.release_connection(self._conn)
            self._conn = None
            self._manager = None

    def execute(self, sql: str, params: Any = None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executescript(self, script_sql: str):
        cur = self.cursor()
        cur.execute(script_sql)
        cur.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


class DatabaseConnectionManager:
    """Manages database connection pooling with retry loops and failover settings."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(DatabaseConnectionManager, cls).__new__(cls)
                cls._instance._pool = None
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._initialize_pool()

    def _initialize_pool(self):
        if LOCAL_MODE:
            logger.info("Local mode is active. Utilizing SQLite fallback.")
            return

        if not DATABASE_URL:
            err_msg = "[ERROR] Database URL is not set but LOCAL_MODE is false. Cannot connect to Supabase production layer."
            logger.error(err_msg)
            raise ValueError(err_msg)

        import psycopg2.pool
        retries = 3
        delay = 2
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Initializing ThreadedConnectionPool for Supabase PostgreSQL (Attempt {attempt}/{retries}).")
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=20,
                    dsn=DATABASE_URL,
                    connect_timeout=DB_TIMEOUT_SECONDS
                )
                logger.info("Supabase PostgreSQL connection pool initialized successfully.")
                return
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL pool on attempt {attempt}: {str(e)}")
                if attempt == retries:
                    raise ConnectionError(f"Unable to connect to Supabase database after {retries} retries: {str(e)}")
                time.sleep(delay)
                delay *= 2

    def get_raw_connection(self, db_path: str = DATABASE_PATH):
        if LOCAL_MODE:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = sqlite3.Row
            return conn
        
        if not self._pool:
            self._initialize_pool()
            
        try:
            conn = self._pool.getconn()
            # Verify active connection health
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
            except Exception:
                logger.warning("Pooled PostgreSQL connection health check failed. Recreating...")
                self._pool.putconn(conn, close=True)
                conn = self._pool.getconn()
            return conn
        except Exception as e:
            logger.error(f"Error fetching connection from pool: {str(e)}")
            # Try to reinitialize pool
            self._initialize_pool()
            return self._pool.getconn()

    def release_connection(self, conn):
        if not LOCAL_MODE and self._pool and conn:
            try:
                self._pool.putconn(conn)
            except Exception as e:
                logger.warning(f"Error returning connection to pool: {str(e)}")

    def verify_health(self) -> str:
        """Checks connection status and returns descriptive message."""
        if LOCAL_MODE:
            return "Connected (Local SQLite)"
        try:
            conn = self.get_raw_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            self.release_connection(conn)
            return "Connected"
        except Exception as e:
            return f"Offline (Failed: {str(e)})"

    @staticmethod
    def get_connection(db_path: str = DATABASE_PATH) -> Tuple[Any, bool]:
        """Retrieves active connection from thread-local storage or database pool."""
        if hasattr(_thread_local, "active_connection") and _thread_local.active_connection is not None:
            return _thread_local.active_connection, False

        mgr = DatabaseConnectionManager()
        conn = mgr.get_raw_connection(db_path)
        if LOCAL_MODE:
            return conn, True
        else:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.autocommit = True
            except Exception:
                pass
            return PostgresConnectionWrapper(conn, mgr), True


class TransactionContext:
    """Context manager for executing operations within a transaction block."""
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.conn = None
        self._is_outermost = False

    def __enter__(self):
        if not hasattr(_thread_local, "active_connection") or _thread_local.active_connection is None:
            mgr = DatabaseConnectionManager()
            raw_conn = mgr.get_raw_connection(self.db_path)
            if LOCAL_MODE:
                self.conn = raw_conn
            else:
                try:
                    raw_conn.rollback()
                except Exception:
                    pass
                raw_conn.autocommit = False
                self.conn = PostgresConnectionWrapper(raw_conn, mgr)
            _thread_local.active_connection = self.conn
            self._is_outermost = True
            logger.debug("Database transaction started.")
        else:
            self.conn = _thread_local.active_connection
            self._is_outermost = False
            logger.debug("Joining existing database transaction.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._is_outermost and self.conn:
            try:
                if exc_type is not None:
                    logger.error(f"Rolling back transaction due to exception: {exc_val}")
                    self.conn.rollback()
                else:
                    logger.debug("Committing transaction.")
                    self.conn.commit()
            except Exception as e:
                logger.error(f"Error finalising transaction: {e}")
                self.conn.rollback()
                raise e
            finally:
                self.conn.close()
                _thread_local.active_connection = None
                logger.debug("Transaction database connection closed.")
        return False
