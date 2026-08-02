"""Generic base repository for SQL operations on SQLite."""
import sqlite3
from typing import Any, Dict, List, Optional
from config import DATABASE_PATH, logger
from app.repository.connection import DatabaseConnectionManager

class BaseRepository:
    """Provides generic abstract CRUD interfaces for any database table."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path

    def _execute(self, query: str, params: tuple = ()) -> int:
        """Helper to execute query with proper connection management. Returns rowcount."""
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            logger.debug(f"Executing: {query} with params {params}")
            cursor.execute(query, params)
            rowcount = cursor.rowcount
            return rowcount
        except sqlite3.Error as e:
            logger.error(f"SQLite error executing {query}: {e}")
            raise e
        finally:
            # Note: Do not close connection here if it's managed by transaction context
            # We commit on success if should_close is True (standalone auto-commit behavior)
            if should_close:
                conn.commit()
                conn.close()

    def insert(self, table_name: str, data: Dict[str, Any]) -> None:
        """Inserts a record into the table."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        self._execute(query, tuple(data.values()))

    def update(self, table_name: str, key_dict: Dict[str, Any], data: Dict[str, Any]) -> int:
        """Updates records in the table matching the keys."""
        set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
        where_clause = " AND ".join([f"{col} = ?" for col in key_dict.keys()])
        query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        params = tuple(data.values()) + tuple(key_dict.values())
        return self._execute(query, params)

    def delete(self, table_name: str, key_dict: Dict[str, Any]) -> int:
        """Deletes records from the table matching the keys."""
        where_clause = " AND ".join([f"{col} = ?" for col in key_dict.keys()])
        query = f"DELETE FROM {table_name} WHERE {where_clause}"
        return self._execute(query, tuple(key_dict.values()))

    def find_one(self, table_name: str, key_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Finds a single record matching the keys."""
        where_clause = " AND ".join([f"{col} = ?" for col in key_dict.keys()])
        query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT 1"
        
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(query, tuple(key_dict.values()))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Error finding one from {table_name}: {e}")
            raise e
        finally:
            if should_close:
                conn.close()

    def find_all(self, table_name: str, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Finds all records, optionally filtered."""
        if filter_dict:
            where_clause = " AND ".join([f"{col} = ?" for col in filter_dict.keys()])
            query = f"SELECT * FROM {table_name} WHERE {where_clause}"
            params = tuple(filter_dict.values())
        else:
            query = f"SELECT * FROM {table_name}"
            params = ()
            
        conn, should_close = DatabaseConnectionManager.get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error finding all from {table_name}: {e}")
            raise e
        finally:
            if should_close:
                conn.close()
