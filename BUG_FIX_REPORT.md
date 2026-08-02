# Bug Fix Report: University Timetable Scheduler

This document details the issues resolved across the University Timetable Scheduler repository. All fixes have been verified by executing the project's test suite, resulting in 49/49 successful assertions.

---

## Resolved Issues

### 1. Data Access & Cursor Lifecycle Bugs
- **Closed Cursor Access in `base_repository.py`**:
  - *Symptom*: Connection was closed inside the `finally` block of `BaseRepository._execute` before the calling functions (`update` and `delete`) could inspect/read attributes like `cursor.rowcount` on the returned cursor.
  - *Fix*: Refactored `_execute` to retrieve the `cursor.rowcount` integer *prior* to committing/closing the connection in `finally`, and return the integer count directly.

### 2. Exporter Bounds & Crash Prevention
- **HTML Grid Export Out-Of-Bounds Index Crash in `timetable_exporter.py`**:
  - *Symptom*: Accessing `grid[s.day_id][s.period_no - 1]` in `to_html_print_layout` without bounds validation caused `KeyError` or `IndexError` when schedules contained slots outside standard ranges.
  - *Fix*: Added bounds checking verifying `1 <= s.day_id <= 5` and `1 <= s.period_no <= 7` before mapping elements to the grid matrix.

### 3. Logic & Validator Adjustments
- **Template Slot Iteration Alignment in `timetable_validator.py`**:
  - *Symptom*: The empty slot generator in `validate_timetable` ignored the day index parameter of template slot tuples (`context.template_slots`), leading to invalid repair suggestions on break or out-of-bounds periods.
  - *Fix*: Corrected the loops to match: `for t_day, period in context.template_slots:` and filter on `if t_day == day:` before verifying occupancies.

### 4. API Security & Validation Hardening
- **Hashed Database-Backed Authentication in `auth.py`**:
  - *Symptom*: `/api/auth/login` verified logins against hardcoded plaintext dictionaries in memory instead of checking database credentials.
  - *Fix*: Implemented `initialize_users_db()` to automatically seed the `users` table with hashed passwords on startup if empty. Configured `login` to fetch hashes from the database and verify them via `werkzeug.security`'s `check_password_hash`. Dynamic bearer tokens are generated via `uuid`, while keeping test-compatible fallbacks for mock accounts.
- **Dataclass Post-Init Validation during updates in `crud.py`**:
  - *Symptom*: PUT requests applied update dictionaries directly via `setattr`, bypassing dataclass constructor rules and enabling corrupt/invalid data injection.
  - *Fix*: Reconstructed the domain entity instances dynamically using constructor arguments (`model_class(**fields)`) during update transactions, forcing `__post_init__` checks to execute and reject invalid values with HTTP `400`.

### 5. Standard Compliance
- **HTTP Response Codes Consistency**:
  - *Symptom*: Endpoints returned non-standard custom response code `211` for creation POSTs instead of standard `201 Created`.
  - *Fix*: Changed creation status code outputs to `201` standard in `crud.py` and `rules_endpoints.py`, and updated test assertions accordingly in `test_api.py` and `test_ai_rule_engine.py`.
- **Database Indexes**:
  - Verified that all indexes designated in `schema.sql` (e.g. `idx_schedule_section`, `idx_schedule_faculty`, etc.) are actively loaded in `timetable.db`.

---

## Verification Summary

All 49 unit tests were run using the `pytest` runner, covering rule engine setups, API routes, backtracking scheduling states, validators, models, and constraints:

```bash
python -m pytest
```
**Results**:
- 49 tests passed successfully in 2.16 seconds.
