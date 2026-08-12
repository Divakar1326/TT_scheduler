# Supabase PostgreSQL Migration & Connection Guide

This guide documents the database structure migration from SQLite to Supabase PostgreSQL for the University Timetable Generation System.

## 1. Prerequisites & Dependencies
To connect to the Supabase PostgreSQL database, we use connection pooling and the standard Python PostgreSQL driver `psycopg2-binary`:
```bash
pip install psycopg2-binary
```

## 2. Configuration Setup
Configure the environment variables (e.g., in your local `.env` file or environment variables settings):
```env
# Supabase PostgreSQL Connection String (Transaction Pool or Direct Connection)
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF_ID].supabase.co:5432/postgres
```
* **Fallback Behavior**: If `DATABASE_URL` is not defined or empty, the application automatically falls back to the local SQLite database at `database/timetable.db` or memory.

## 3. SQL Dialect Translation Heuristics
The migration script automatically translates the following SQLite-specific features into standard PostgreSQL compatibility markers:
* **Autoincrement**: Translates `INTEGER PRIMARY KEY AUTOINCREMENT` to `SERIAL PRIMARY KEY`.
* **DateTime**: Translates SQLite `DATETIME` columns to PostgreSQL `TIMESTAMP` columns.
* **Pragmas**: Ignores SQLite `PRAGMA` lines which are unsupported or unnecessary in PostgreSQL.
* **Placeholder Normalization**: Replaces parameter placeholders (`?`) with standard PostgreSQL type placeholders (`%s`) dynamically on execution using our cursor wrapper.

## 4. Running Migrations & Seeding
To initialize the Supabase tables and seed the database with initial ISC department metadata:
```bash
# 1. Run migrations to create tables and indexes
python scripts/migration.py

# 2. Seed database with default ISC department schedules/parameters
python scripts/seed_supabase.py
```
Both scripts run seamlessly against whichever database engine is selected by your active environment variables.
