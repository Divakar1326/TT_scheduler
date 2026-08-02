# MASTER PROJECT BLUEPRINT

## Project Vision

Build a University Timetable Management System from scratch.

Existing assets: - SQL Schema - SQLite Database - Seed Data

Everything else must be implemented.

## Roles

### Super Admin

* Create/Edit/Delete departments
* Create department HOD accounts
* Global settings
* View and manage all departments (switches between department dashboards)

### Department (HOD)

* Faculty CRUD
* Course CRUD
* Room CRUD
* Lab CRUD
* Section CRUD
* Rules configuration
* Generate Timetable
* Reports / Exports
* Only access their designated department data

## Landing Page

* Project title
* Developer details
* HITS branding
* Project summary
* Login button
* White background
* Orange title
* Green buttons
* Minimal UI

## Dashboard

* Summary cards: Faculty, Courses, Sections, Rooms, Labs, Students.
* Table: Section | Class Teacher | Classroom | Strength.
* Actions: Faculty, Courses, Rooms, Labs, Sections, Rules, Generate Timetable, Validation, Export.

## Scheduling Rules & Constraints

### Hard Constraints (Must satisfy)
* No faculty clash
* No room clash
* No lab clash
* No section clash
* Practicals/Labs are consecutive blocks
* Weekly hours satisfied
* Complete timetable generated
* Max two sessions of the same subject/day for any section
* Faculty daily hour limit (default max 5 periods/day, weekly hours configurable in DB)
* Permanent classroom maintained for each section
* Permanent class teacher maintained for each section
* Theory/tutorial sessions distributed evenly across the week

### Soft Constraints (Optimizations)
* Morning labs preferred
* Balanced workload
* Compact timetable (minimize gaps)
* Minimize room changes

## Course Allocation Logic
* **`has_lab = true`** (e.g. `L=2, T=1, P=2`)
  - Generates: 2 theory sessions (classroom), 1 tutorial session (classroom), and 1 practical block of 2 consecutive periods (laboratory room).
* **`has_lab = false`** (e.g. `L=2, T=1, P=2`)
  - Generates: 2 theory sessions (classroom), 1 tutorial session (classroom), and 1 block of 2 consecutive periods (classroom). No lab assignment.

## AI Rule Engine

* Support structured rule builder (Dropdowns for Faculty, Course, Section, Day, Period, Action, Priority).
* Support natural language rules parsed via Gemini 3.5 Flash into validated JSON representation.
* Saved rules metadata: original text, JSON representation, enabled status, priority, department ID, created by, and created date.

## Workflow

Database -> Repository -> Models -> CRUD -> Constraint Engine -> Scheduler -> Backtracking -> Validator -> Repair -> Export -> UI

## Development Order

1. Repository
2. Models
3. CRUD API (Flask)
4. UI Dashboard
5. Constraints Engine
6. Scheduler & Candidate Generator
7. Backtracking Engine
8. Validator
9. Repair Engine
10. AI Rules Integration
11. Export Functionality (PDF / Excel)
12. Integration & End-to-End Testing

## PROJECT_LOG

Every completed phase updates `PROJECT_LOG.md` with: Completed tasks, Files changed, Tests, Pending work, Known issues, Next task.
Always read `PROJECT_LOG.md` before continuing.

## Definition of Done

* Code compiles
* Tests pass
* UI works
* CRUD works
* Logging added
* Documentation updated
* PROJECT_LOG updated

---

# PROJECT MANAGEMENT PROTOCOL

This project is developed incrementally.

Before writing any code:
1. Check whether `PROJECT_PROFILE.md` exists.
2. Check whether `PROJECT_LOG.md` exists.
3. Check whether `TASK_QUEUE.md` exists.

If they do not exist, create them automatically.
Only one phase may be in progress. No parallel implementation.
All tests for the current phase must pass before starting the next phase.
