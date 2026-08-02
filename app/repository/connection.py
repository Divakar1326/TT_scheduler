"""Database connection and transaction manager using SQLite."""
import sqlite3
import threading
from typing import Tuple
from config import DATABASE_PATH, logger

# Thread-local storage to track active transaction connections
_thread_local = threading.local()

class DatabaseConnectionManager:
    """Manages SQLite connection pooling/retrieval with transaction support."""
    
    @staticmethod
    def get_connection(db_path: str = DATABASE_PATH) -> Tuple[sqlite3.Connection, bool]:
        """
        Retrieves a database connection.
        
        If a transaction is active on the current thread, returns the shared connection
        and a boolean flag of False (indicating the caller should NOT close it).
        Otherwise, returns a new connection and True (caller must close it).
        """
        if hasattr(_thread_local, "active_connection") and _thread_local.active_connection is not None:
            return _thread_local.active_connection, False
        
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn, True


class TransactionContext:
    """Context manager for executing operations within a transaction block."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.conn = None
        self._is_outermost = False

    def __enter__(self):
        # Only create a new transaction connection if one does not already exist for this thread
        if not hasattr(_thread_local, "active_connection") or _thread_local.active_connection is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.row_factory = sqlite3.Row
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
        return False  # Bubble up any exceptions
