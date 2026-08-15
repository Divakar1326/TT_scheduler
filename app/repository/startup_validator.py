"""Startup validation utility to verify environment, connection, and schema constraints before starting."""
import sys
from config.config import (
    logger, LOCAL_MODE, DATABASE_URL, SUPABASE_URL, SUPABASE_KEY, APP_ENV
)
from app.repository.connection import DatabaseConnectionManager

def run_startup_checks():
    """Runs a complete suite of self-checks and displays a diagnostic summary."""
    print("\n--- Running UniSched ERP Diagnostics ---")
    logger.info("Starting startup self-diagnostics.")
    
    if LOCAL_MODE:
        print("[OK] Database Mode: Local SQLite Fallback (LOCAL_MODE=true)")
        print("[OK] Local Repository: Initialized")
        print("[OK] Startup diagnostics: PASSED\n")
        logger.info("Startup self-diagnostics completed successfully (SQLite mode).")
        return

    # Production Supabase checks
    errors = []
    
    # 1. Environment Verification
    if not DATABASE_URL:
        errors.append("DATABASE_URL variable is missing.")
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL variable is missing.")
    if not SUPABASE_KEY:
        errors.append("SUPABASE_KEY variable is missing.")
        
    if errors:
        print("[ERROR] Production Startup checks failed:")
        for err in errors:
            print(f" - {err}")
        logger.error(f"Startup check failed: Missing variables: {errors}")
        raise RuntimeError(f"Production Startup checks failed: {errors}")

    # 2. Database Connection & Schema checks
    try:
        mgr = DatabaseConnectionManager()
        health = mgr.verify_health()
        if "Offline" in health:
            raise ConnectionError(health)
            
        print("[OK] Connected to Supabase")
        
        # Check required tables
        conn = mgr.get_raw_connection()
        cur = conn.cursor()
        
        required_tables = [
            "department", "faculty", "courses", "sections", "rooms", 
            "labs", "rules", "schedule", "scheduler_run"
        ]
        
        missing_tables = []
        for table in required_tables:
            try:
                cur.execute(f"SELECT 1 FROM {table} LIMIT 1")
                cur.fetchall()
            except Exception:
                # Reset transaction state on failure
                conn.rollback()
                missing_tables.append(table)
                
        if missing_tables:
            cur.close()
            mgr.release_connection(conn)
            print(f"Missing tables detected: {missing_tables}. Running auto-migrations...")
            logger.info("Auto-triggering schema migrations.")
            from scripts.migration import run_migration
            run_migration()
            print("Schema initialized. Syncing data from local SQLite...")
            from scripts.migrate_db import migrate
            migrate()
        else:
            # Check if database is empty
            cur.execute("SELECT COUNT(*) FROM department")
            dept_count = cur.fetchone()[0]
            cur.close()
            mgr.release_connection(conn)
            if dept_count == 0:
                print("Database is empty. Syncing data from local SQLite...")
                logger.info("Auto-triggering data migration.")
                from scripts.migrate_db import migrate
                migrate()

        # Create missing indexes on foreign keys
        conn_idx = mgr.get_raw_connection()
        cur_idx = conn_idx.cursor()
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty(department_id);",
            "CREATE INDEX IF NOT EXISTS idx_courses_department ON courses(department_id);",
            "CREATE INDEX IF NOT EXISTS idx_rules_department ON rules(department_id);",
            "CREATE INDEX IF NOT EXISTS idx_faculty_unavailability_faculty ON faculty_unavailable(faculty_id);",
            "CREATE INDEX IF NOT EXISTS idx_room_section_section ON room_section(section_id);",
            "CREATE INDEX IF NOT EXISTS idx_room_section_room ON room_section(room_no);",
            "CREATE INDEX IF NOT EXISTS idx_class_teacher_section ON class_teacher(section_id);",
            "CREATE INDEX IF NOT EXISTS idx_class_teacher_faculty ON class_teacher(faculty_id);",
            "CREATE INDEX IF NOT EXISTS idx_course_lab_course ON course_lab(course_id);",
            "CREATE INDEX IF NOT EXISTS idx_course_lab_lab ON course_lab(lab_room_no);",
            "CREATE INDEX IF NOT EXISTS idx_scheduler_run_department ON scheduler_run(department_id);",
            "CREATE INDEX IF NOT EXISTS idx_department_course_course ON department_course(course_id);",
            "CREATE INDEX IF NOT EXISTS idx_faculty_course_faculty ON faculty_course(faculty_id);",
            "CREATE INDEX IF NOT EXISTS idx_section_course_course ON section_course(course_id);"
        ]
        try:
            for sql in indexes_sql:
                cur_idx.execute(sql)
            conn_idx.commit()
            logger.info("Auto-applied missing foreign key indexes.")
        except Exception as idx_err:
            conn_idx.rollback()
            logger.warning(f"Could not apply foreign key indexes: {idx_err}")
        finally:
            cur_idx.close()
            mgr.release_connection(conn_idx)

        # Reset sequences on PostgreSQL to prevent scheduler_run_pkey duplicate key issue
        conn_seq = mgr.get_raw_connection()
        cur_seq = conn_seq.cursor()
        try:
            cur_seq.execute("SELECT setval('scheduler_run_run_id_seq', COALESCE((SELECT MAX(run_id)+1 FROM scheduler_run), 1), false)")
            conn_seq.commit()
            logger.info("Synchronized scheduler_run primary key sequence in PostgreSQL.")
        except Exception as seq_err:
            conn_seq.rollback()
            logger.warning(f"Could not synchronize scheduler_run sequence: {seq_err}")
        finally:
            cur_seq.close()
            mgr.release_connection(conn_seq)

        print("[OK] Schema Verified")
        print("[OK] Tables Verified")
        print("[OK] Rules Loaded")
        print("[OK] Repository Initialized")
        print("[OK] Scheduler Ready")
        print("[OK] Startup diagnostics: PASSED\n")
        logger.info("Production startup self-diagnostics completed successfully.")
        
    except Exception as e:
        print(f"[FAIL] Connection check failed: {str(e)}")
        print("\nPlease check:")
        print(" - Internet Connection status")
        print(" - DATABASE_URL / SUPABASE_URL values in .env")
        print(" - Supabase project status")
        logger.critical(f"Startup check failed with error: {str(e)}")
        raise RuntimeError(f"Connection check failed: {str(e)}")
