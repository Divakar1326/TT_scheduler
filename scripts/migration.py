"""Migration script to initialize Supabase PostgreSQL or SQLite schema."""
import os
import sys
from config.config import DATABASE_PATH, DATABASE_URL, logger
from app.repository.connection import DatabaseConnectionManager

def run_migration():
    if not DATABASE_URL:
        logger.info("DATABASE_URL not set. Running migration locally on SQLite.")
    else:
        logger.info("DATABASE_URL detected. Running migration on Supabase PostgreSQL.")
        
    schema_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "schema.sql")
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found at: {schema_path}")
        sys.exit(1)
        
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Split script into individual statements
    statements = []
    current_statement = []
    for line in schema_sql.split("\n"):
        # Ignore comments and SQLite PRAGMAs
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("--") or trimmed.upper().startswith("PRAGMA "):
            continue
        current_statement.append(line)
        if trimmed.endswith(";"):
            statements.append("\n".join(current_statement))
            current_statement = []

    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        for stmt in statements:
            # PostgreSQL dialect translations
            if DATABASE_URL:
                stmt_upper = stmt.upper()
                # Translate SQLite AUTOINCREMENT
                if "INTEGER PRIMARY KEY AUTOINCREMENT" in stmt_upper:
                    stmt = stmt.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                    stmt = stmt.replace("integer primary key autoincrement", "serial primary key")
                    stmt = stmt.replace("Integer Primary Key Autoincrement", "Serial Primary Key")
                # Translate SQLite DATETIME to TIMESTAMP
                stmt = stmt.replace("DATETIME", "TIMESTAMP")
                stmt = stmt.replace("datetime", "timestamp")
                
            logger.debug(f"Executing statement: {stmt[:60]}...")
            cursor.execute(stmt)
            
        if DATABASE_URL:
            conn.commit()
            
        logger.info("Migration completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if DATABASE_URL and conn:
            conn.rollback()
        raise e
    finally:
        if should_close:
            conn.close()

if __name__ == "__main__":
    logging_config = {
        "level": 10,
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
    import logging
    logging.basicConfig(**logging_config)
    run_migration()
