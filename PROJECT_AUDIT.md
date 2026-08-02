# Project Audit Report: University Timetable Scheduler

This document provides a comprehensive review of the University Timetable Scheduler codebase, assessing the system's architecture, security, database usage, APIs, UI/UX, module quality, and listing specific bugs and improvement areas.

---

## Module Ratings (1–10)

| Module Path | Rating | Key Rationale |
| :--- | :---: | :--- |
| **`app.models`** (`domain.py`, `mapping.py`) | **8/10** | Clear dataclass structures and validation constraints in `__post_init__`. Mapping layer is simple and effective. Needs typing/validation refinement during updates. |
| **`app.repository`** (`connection.py`, `base_repository.py`, `entity_repositories.py`) | **6/10** | Database connection pooling is cleanly implemented, but returning cursors on closed connections (`BaseRepository._execute`) is a major flaw. Several repository files are empty stubs. |
| **`app.constraints`** (`hard_constraints.py`, `soft_constraints.py`, `validator.py`, `rule_validator.py`, `prompt_manager.py`) | **8/10** | Excellent separation of concerns. Robust validation of rules, logic checks, and constraint scoring. `validator.py` has minor logic slip-ups in repair generation. |
| **`app.scheduler`** (`session.py`, `candidate_generator.py`, `backtracking.py`, `scheduler.py`, `state_manager.py`) | **9/10** | Very strong implementation of backtracking search using CSP heuristics (MCV/LCV). Highly deterministic and performant. |
| **`app.repair`** (`repair_engine.py`) | **7/10** | Good local search (Move & Swap) heuristics. However, it relies heavily on in-memory mutation of lists, and performance could be optimized. |
| **`app.validator`** (`timetable_validator.py`) | **7/10** | Solid full-schedule validation, but contains a minor bug in the template slots iteration logic when suggesting repairs. |
| **`app.exporter`** (`timetable_exporter.py`) | **6/10** | Exporter outputs readable CSV/HTML, but lacks bounds checking on day and period keys, posing a high risk of runtime index crashes. |
| **`app.api`** (`app.py`, `auth.py`, `crud.py`, `rules_endpoints.py`, `scheduler_endpoints.py`) | **4/10** | **Critical Security Flaws**: Authentication is mock/hardcoded, completely bypassing database tables and password hashing. Uses non-standard HTTP response codes (e.g., 211). |
| **`app.static`** (`app.js`, `index.html`, `style.css`) | **7/10** | Functional single-page web app layout. Clean CSS styling but lacks full responsive adaptability and is tightly coupled to the ISC department. |

---

## Architectural Review

### 1. Structure & Boundaries
- The codebase follows a standard **layered architecture** (Presentation, Controller, Domain, Repository).
- High cohesion is maintained across core processing logic, with dependencies flowing inward towards domain models.
- **Violation of Layering**: Controllers (`app/api`) contain direct SQLite connections and queries bypassing the repository classes, particularly in `auth.py` (which ignores database users) and `rules_endpoints.py` (which implements manual sql execution).

### 2. Circular Imports
- The codebase runs successfully without circular imports, using local imports inside controllers (e.g., in `scheduler_endpoints.py` to import repositories dynamically). However, this can be refactored to standard modular imports by decoupling configuration.

### 3. Dead Code
- Empty repositories (`ImportLogRepository`, `SchedulerRunRepository`, `ValidationLogRepository`) are declared but never utilized.
- Tables `import_log`, `scheduler_run`, and `validation_log` exist in `schema.sql` but have no read/write interactions in the backend app logic.
- Scheduler runs are cached in-memory (`MEM_SCHEDULE_STORE`) rather than persisted in the database.

### 4. Code Duplication
- SQLite connection properties (`PRAGMA foreign_keys = ON;` and `conn.row_factory = sqlite3.Row`) are configured in duplicate inside both `DatabaseConnectionManager.get_connection` and `TransactionContext.__enter__`.

---

## Bug List

### 1. Critical Bugs & Crashes
- **`timetable_exporter.py` Index Crash**: `to_html_print_layout` does not validate if `s.day_id` is within `[1..5]` or `s.period_no` within `[1..7]` before accessing `grid[s.day_id][s.period_no - 1]`. Any out-of-bounds slot (e.g., weekend or late periods) will cause a runtime crash (`KeyError` / `IndexError`).
- **`base_repository.py` Closed Cursor Bug**: In `BaseRepository._execute`, if `should_close` is `True`, `conn.close()` is executed in the `finally` block before returning the `cursor`. Attempting to read from or inspect the cursor (e.g., calling `cursor.rowcount` in `update` or `delete`) operates on a closed connection, leading to undefined or crashing behavior in SQLite/Python.

### 2. Security Vulnerabilities
- **Bypassed Auth Database**: The `/api/auth/login` endpoint authenticates against a hardcoded dictionary (`USERS`) instead of verifying credentials against the SQLite `users` table.
- **No Password Hashing**: The `users` database table contains a column for `password_hash`, but no hashing logic is applied. Passwords in configuration are handled in plaintext.
- **Static Access Tokens**: Bearer tokens (`super-admin-token-12345` and `hod-token-12345`) are completely static, hardcoded, and permanent.
- **Arbitrary Mass Parameter Injection**: `crud.py` PUT endpoints loop over request parameters (`data.items()`) and apply `setattr` directly to domain models. This bypasses the dataclass constructor validations (`__post_init__`), allowing invalid data (e.g., negative capacity, empty strings) to pass validation and be saved to the database.

### 3. Logic Errors
- **`timetable_validator.py` Incorrect Suggestion Loop**: In `validate_timetable`, the loops for locating empty slots check:
  ```python
  for day in context.working_days:
      for _, period in context.template_slots:
          if (day, period, room) not in occupied_slots:
  ```
  Since `context.template_slots` is a set of `(day_id, period_no)`, iterating over it returns all day/period pairs. Under `_`, the code discards the template day. It then checks `(day, period, room)`, which means it might check and suggest a period that is not in the active template for the selected `day` (such as a lunch/break hour or weekend), because the check `if (day, period) in context.template_slots` is missing.

---

## Improvement Areas

### 1. Naming & Consistency
- **Role Inconsistencies**: The database schema enforces `role CHECK(role IN ('ADMIN','HOD'))`, whereas python controllers check for `SUPER_ADMIN` or `HOD`.
- **Non-Standard HTTP Status Codes**: The server returns custom code `211` instead of standard `201 Created` for POST create endpoints (`create_{prefix}`, `save_rule`).
- **Endpoint vs. DB Naming**: The API uses `/api/laboratories` but maps to the database table `labs`.

### 2. Database & Performance
- **Missing Database Indexes**: The `schedule` table is queried frequently for clashes, but lacks indexes on primary search columns (`run_id`, `day_id`, `period_no`, `faculty_id`, `room_no`, `lab_room_no`). Adding indexes will improve database search speeds.
- **Persistence of runs**: Save the generated scheduler results in the database `schedule` and `scheduler_run` tables instead of maintaining `MEM_SCHEDULE_STORE` in-memory.

### 3. General Architecture & Design
- Add schema validation (e.g. Marshmallow or Pydantic) to the REST API layers to validate incoming payloads before instantiating domain models.
- Centralize SQLite configuration initialization to remove duplicate connections setup.
