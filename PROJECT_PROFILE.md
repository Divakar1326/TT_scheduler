# PROJECT PROFILE

## Project Name
AI-Powered University Timetable Generation System

## Version
1.0

## Objective
Build a production-ready, conflict-free university timetable generation system with a modular architecture. The system must automatically schedule theory classes and laboratory sessions while satisfying academic, institutional, and user-defined constraints.

## Architecture
```
SQLite Database 
      ↓
  Repository (Database Connection & CRUD Operations)
      ↓
  Domain Models (Core entities representation)
      ↓
  Constraint Engine (Validation of proposed allocations)
      ↓
  Scheduler (Candidate generation & scheduling workflow)
      ↓
  Backtracking Engine (Handling allocation failures/retries)
      ↓
  Validator (Final conflict & rule checks)
      ↓
  Repair Engine (Attempting legal repairs)
      ↓
  Exporter (Excel/CSV/PDF exports)
      ↓
  REST API (Flask endpoints for CRUD & generation)
      ↓
  Frontend UI (Responsive administration web dashboard)
```

## Technology Stack
- **Backend:** Python 3.12, Flask, SQLite (sqlite3)
- **AI Integration:** Gemini API (via Google GenAI SDK for NLP Rule Engine)
- **Frontend:** Vanilla HTML5, Javascript, and CSS (sleek, modern, and responsive UI)
- **Testing:** unittest / pytest
- **Documentation:** Markdown

## Folder Structure
```text
project/
  database/
    timetable.db            # SQLite database file
    schema.sql              # Database schema definition
  app/
    core/                   # Domain models and basic types
    repository/             # Connection manager & entity repositories
    services/               # Repair engine and core scheduling helpers
    validators/             # Hard/soft constraints and MasterValidator
    exporters/              # Exporter functions (Excel/PDF/CSV)
    auth/                   # Authentication logic and decorators
    ui/                     # HTML/CSS/JS frontend files
    api/                    # REST API endpoints and blueprint routes
    ai/                     # Gemini AI translation logic
  config/                   # Global configuration and path settings
  docs/                     # SRS, Specifications, and Blueprints
  tests/                    # Test directory
    unit/                   # Core unit & integration test suites
  scripts/                  # Setup and database seeding utilities
```

## Database Information
- **Source of Truth:** SQLite Database (`timetable.db`)
- **Key Tables:**
  - `department`, `academic_year`, `days`, `template`
  - `faculty`, `rooms`, `labs`, `courses`, `sections`
  - `department_faculty`, `department_course`, `section_course`, `faculty_course`
  - `faculty_assignment`, `faculty_unavailable`, `course_lab`, `room_section`, `class_teacher`
  - `rules`, `users`, `import_log`, `scheduler_run`, `validation_log`, `schedule`

## Development Rules
- Develop sequentially: Build one phase at a time.
- All tests for the current phase must pass before starting the next phase.
- Only one phase may be in progress. No parallel implementation.
- Never modify the SQL schema without approval.
- No placeholder/stub/TODO code.
- Log all actions and handle errors gracefully.

## UI Guidelines
- Modern responsive dashboard with sidebar, cards, and tables.
- Specific styles: White background, orange titles, green buttons, minimal UI with rich modern aesthetics (smooth animations, Google Fonts typography, sleek layout).
- Views needed: Dashboard, Faculty, Courses, Rooms, Labs, Departments, Semesters, Constraints, AI Rules, Timetable grid, Validation status, Settings.

## Coding Standards
- Python 3.12 compatibility
- Type hints on all function and method signatures
- Dataclasses for model representations
- Comprehensive logging and error handling
- 100% test coverage for key scheduler logic

## Current Phase
- Phase X: Production Cleanup & Refactor (Project Feature-Complete and Production Ready)

## Constraints
- **Hard Constraints:**
  - No faculty clashes (a teacher cannot teach two classes at the same time).
  - No room clashes (a room cannot host two classes at the same time).
  - No section clashes (a section cannot have two classes at the same time).
  - Respect faculty availability and daily session limits.
  - Complete all required weekly hours per course.
  - Consecutive laboratory periods (labs must be scheduled consecutively as 3-period blocks).
  - Maximum of two sessions of the same subject per day for any section.
- **Soft Constraints:**
  - Prefer scheduling laboratory sessions in the morning.
  - Maintain a balanced workload for faculty and sections.
  - Compact timetable layout (minimize idle gaps between classes).
  - Minimize room changes for a section.

## AI Model Used
- Gemini 3.5 Flash


Final Architecture Decisions
1. User Roles
Super Admin
Login as Super Admin.
Create/Edit/Delete departments.
Create HOD accounts.
View and manage all departments.
Uses the same dashboard as an HOD, but can switch between departments.
HOD
Login only to their department.
Manage only their department's data.
Cannot access other departments.
2. Timetable Template

Fixed configuration.

Monday–Friday
7 periods/day
Break after Period 2
Lunch after Period 4
55-minute periods

This is not configurable.

3. Classroom Rules

Each section has:

One permanent classroom
One permanent class teacher

These never change during timetable generation.

Only laboratory rooms change.

4. Faculty Workload

Each faculty has configurable limits.

Default:

Maximum 5 periods/day
Weekly limit stored in the database
5. Course Allocation

A course contains:

L
T
P
has_lab

Example:

AI

L = 2
T = 1
P = 2
has_lab = true

Scheduler creates:

2 independent theory sessions
1 tutorial session
1 practical block of 2 consecutive periods in a lab

Example 2

AI

L = 2
T = 1
P = 2
has_lab = false

Scheduler creates:

2 theory
1 tutorial
2 consecutive periods

No laboratory assignment.

This distinction is very important and should be documented clearly.

6. Timetable Generation

The HOD should be able to generate timetables for:

One section
All sections in the department

The scheduler always considers the entire department to avoid conflicts, even if only one timetable is being exported.

7. Export

Support:

Section timetable
Faculty timetable
Laboratory timetable

Formats:

PDF
Excel
8. Rule Engine

Support two ways of creating rules.

Structured Builder

Dropdowns:

Faculty
Course
Section
Day
Period
Action
Priority
Natural Language

Example:

AI should not be after lunch.

↓

Gemini

↓

JSON

↓

Validation

↓

Save

Each rule has:

Original text
JSON representation
Enabled/Disabled
Priority
Department
Created by
Created date
9. Dashboard

Summary cards:

Faculty
Courses
Sections
Rooms
Labs
Students

Table:

Section
Class Teacher
Classroom
Strength

Quick actions:

Faculty
Courses
Rooms
Labs
Sections
Rules
Generate
Export
10. Scheduler Rules

The scheduler must always satisfy:

No faculty clashes
No room clashes
No lab clashes
No section clashes
Practicals consecutive
Weekly hours complete
Permanent classroom maintained
Permanent class teacher maintained
Faculty daily limit
Theory/tutorial sessions distributed across the week
11. Error Handling

  