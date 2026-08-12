# SOFTWARE REQUIREMENTS SPECIFICATION (SRS)

## AI-Powered University Timetable Generation System

Version: 1.0

## 1. Vision

Build a production-grade University Timetable Generation System from scratch.

Existing assets: - SQL Schema - SQLite Database - Seed Data

Everything else must be designed and implemented from scratch.

The objective is to automatically generate conflict-free timetables while satisfying academic, institutional, and user-defined constraints.

## 2. Goals

- Modular architecture
- Scalable design
- SQLite as source of truth
- Automatic scheduling
- AI-assisted rule creation (via Gemini 3.5 Flash)
- Interactive web dashboard (Vanilla HTML/CSS/JS with minimal premium aesthetics)
- Export to Excel/PDF (Section, Faculty, and Laboratory views)
- Comprehensive validation

## 3. Architecture

Database ↓ Repository ↓ Domain Models ↓ Constraint Engine ↓ Candidate Generator ↓ Scheduler ↓ Backtracking Engine ↓ Validator ↓ Repair Engine ↓ Exporter ↓ REST API (Flask) ↓ Frontend UI (Dashboard)

Each layer has one responsibility and cannot bypass lower layers.

## 4. Folder Structure

```text
project/
  database/
    timetable.db            # SQLite database file
    schema.sql              # Database schema definition
  app/
    repository/             # Database connection, CRUD operations, transactions
    models/                 # Dataclasses representing domain models
    constraints/            # Core scheduling constraints & AI Rule Engine
    scheduler/              # Candidate generation & backtracking scheduler
    validator/              # Verification engine for completed timetables
    repair/                 # Timetable repair and heuristics engine
    exporter/               # PDF, CSV, Excel exporters
    ai/                     # Gemini integration for natural language rules
    api/                    # Flask REST API endpoints
    ui/                     # HTML/CSS/JS frontend files
    tests/                  # Unit and integration tests
  docs/                     # SRS, Specifications, and Blueprints
```

## 5. Module Specifications & Frozen Architecture Decisions

### User Authentication & Roles
- **Super Admin:** Manage departments, HOD accounts, global settings. Shared dashboard with drop-down context switching.
- **HOD:** Restricted to their department's data and timetable generation.

### Timetable Template (Fixed Configuration)
- Grid: Monday to Friday.
- Slots: 7 periods per day (55-minute periods).
- Breaks: Short break after Period 2, Lunch break after Period 4. Static and non-configurable.

### Classroom & Class Teacher Binding
- Permanent mapping: Each section has one permanent classroom and one permanent class teacher.
- Stays constant during schedule generation (only lab room mapping varies for practical sessions).

### Faculty Workload
- Default limit of maximum 5 periods per day.
- Configurable limits per faculty with weekly totals stored in the database.

### Course Allocation & Creation Logic
- **`has_lab = true`** (e.g. `L=2, T=1, P=2`): Creates 2 independent theory sessions (classroom), 1 tutorial (classroom), and 1 practical block of 2 consecutive periods (laboratory room).
- **`has_lab = false`** (e.g. `L=2, T=1, P=2`): Creates 2 independent theory sessions (classroom), 1 tutorial (classroom), and 2 consecutive periods (classroom). No lab assignment.

### Timetable Generation Flow
- Supports generating for one section or all sections of the department.
- Scheduler always checks conflicts across the entire department to ensure global consistency.

### Rule Engine
- **Structured Builder:** Dropdowns for Faculty, Course, Section, Day, Period, Action, Priority.
- **Natural Language Parsing:** AI translates prompt string (e.g. *"AI should not be after lunch"*) using Gemini 3.5 Flash to validated JSON which is then saved.
- Saved fields: original text, JSON representation, enabled status, priority, department, created by, and created date.

### Dashboard UI
- **Summary Cards:** Faculty, Courses, Sections, Rooms, Labs, Students.
- **Summary Table:** Section | Class Teacher | Classroom | Strength.
- **Quick Actions:** Navigation to CRUD forms, Rules configuration, Generator, and Export triggers.

## 6. Scheduling Workflow

1. Load SQLite database.
2. Build domain models.
3. Load constraints.
4. Generate required sessions based on L-T-P parameters and `has_lab` flag.
5. Sort session candidates by difficulty.
6. Allocate laboratories first.
7. Allocate theory classes in permanent classrooms.
8. Backtrack when needed (undo allocations, try alternate paths).
9. Validate complete timetable.
10. Repair if required.
11. Export (Section, Faculty, Lab timetables to PDF/Excel).

## 7. Constraints

### Hard (Must pass)
- No faculty clash
- No room clash
- No section clash
- No lab clash
- Faculty availability respected
- Permanent classroom binding maintained
- Permanent class teacher binding maintained
- Faculty daily workload limit respected
- Weekly hours fully satisfied
- Consecutive lab periods scheduled in designated rooms

### Soft (Weighted optimization)
- Morning labs preferred
- Balanced workload
- Compact schedules (minimize idle gaps)
- Minimize room changes (maintenance of permanent classroom)
- Theory/tutorial sessions distributed evenly across the week

## 8. Exporter Specifications
- Section timetable, Faculty timetable, Laboratory timetable.
- Output formats: PDF and Excel.

## 9. Coding Standards

- Python 3.12 compatibility
- Type hints on all definitions
- Domain models as dataclasses
- Proper logging and nested error handling
- Zero placeholder code
- Unit tests and Integration tests

## 10. Development Phases

1. Repository
2. Models
3. Constraint Engine
4. Scheduler
5. Backtracking
6. Validator
7. Repair
8. Export
9. API
10. UI
11. Integration
12. Performance Optimization

## 11. Instructions for Antigravity

You are the lead software engineer.
Rules:
- Treat this as a brand-new project.
- Ignore any previous implementation.
- Never modify SQL schema without approval.
- Build exactly one phase at a time.
- Run tests before finishing a phase.
- Stop after every phase and summarize completed work.
- Do not create TODO stubs.
- Produce production-quality code.

## 12. Definition of Done

A phase is complete only when:
- Code compiles
- Tests pass
- Integrated successfully
- Logging exists
- Error handling exists
- Documentation updated
- No placeholders remain
