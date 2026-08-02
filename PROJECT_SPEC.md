# AI-Powered University Timetable Generation System

This project starts from scratch.

Existing assets: - SQL Schema - SQLite Database - Seed Data

Everything else must be created from scratch.

## Objective

Build a production-ready university timetable generation system with a modular architecture.

## Architecture

Database -> Repository -> Models -> Constraint Engine -> Scheduler -> Backtracking -> Validator -> Repair -> Export -> Flask API -> UI

## Rules

- Never modify SQL schema unless approved.
- Build one phase at a time.
- Test each phase before continuing.
- No placeholder code.
- Use Python 3.12, modular design, logging, type hints.

## Core Specifications & Architecture Decisions (Frozen)

### 1. User Roles
- **Super Admin:** Can manage departments, create HOD accounts, and switch dashboard views between departments.
- **HOD:** Designated to a specific department. Can manage only their department's data and generate timetables.

### 2. Timetable Template (Fixed Configuration)
- Monday–Friday, 7 periods per day (55-minute periods).
- Short break after Period 2.
- Lunch break after Period 4.
- This grid layout is static and non-configurable.

### 3. Classroom & Teacher Binding Rules
- Each section is assigned one permanent classroom and one permanent class teacher.
- These bounds remain fixed during scheduling; only laboratory rooms vary during practicals.

### 4. Faculty Workload Limits
- Default limit of maximum 5 periods per day.
- Weekly hour limit stored directly in the database.

### 5. Course Session Allocation Logic
- Courses contain `L` (Lecture), `T` (Tutorial), `P` (Practical), and `has_lab` attributes.
- **Case 1: `has_lab = true`** (e.g. `L=2, T=1, P=2`)
  - Generates: 2 theory sessions (classroom), 1 tutorial session (classroom), and 1 practical block of 2 consecutive periods (laboratory room).
- **Case 2: `has_lab = false`** (e.g. `L=2, T=1, P=2`)
  - Generates: 2 theory sessions (classroom), 1 tutorial session (classroom), and 1 block of 2 consecutive periods (classroom). No lab assignment.

### 6. Timetable Generation
- Timetables can be triggered for one section or all sections.
- The scheduler always processes conflict checks department-wide to maintain overall integrity.

### 7. Export Types
- **Views:** Section, Faculty, and Laboratory timetables.
- **Formats:** PDF, Excel.

### 8. Rule Engine
- **Structured Builder:** Form-based rule builder using dropdowns (Faculty, Course, Section, Day, Period, Action, Priority).
- **Natural Language:** Gemini converts natural language (e.g., *"AI should not be after lunch"*) into structured JSON, which is validated and saved.
- **Rules schema:** Original text, JSON representation, Enabled/Disabled, Priority, Department, Created by, Created date.

### 9. Dashboard Layout
- **Summary Cards:** Faculty, Courses, Sections, Rooms, Labs, Students.
- **Summary Table:** Section | Class Teacher | Classroom | Strength.
- **Quick Actions:** CRUD pages, Rules configuration, Generation panel, Export triggers.

### 10. Scheduler Rules
The scheduler must satisfy:
- No faculty clashes
- No room clashes
- No lab clashes
- No section clashes
- Practicals scheduled consecutively
- Weekly hours fully satisfied
- Permanent classroom maintained for each section
- Permanent class teacher maintained for each section
- Faculty daily workload limits respected
- Theory/tutorial sessions distributed evenly across the week

---

## Phases

1. Repository
2. Models
3. Constraint Engine
4. Scheduler
5. Backtracking
6. Validator
7. Repair
8. Export
9. Backend API (Flask)
10. Modern UI (HTML/CSS/JS)
11. Integration
12. Performance Optimization

## Scheduler Workflow

Load DB -> Build Models -> Load Constraints -> Generate Candidates -> Allocate Labs -> Allocate Theory -> Backtrack if needed -> Validate -> Repair -> Export

## Final Instruction

Treat this as a completely new software project. Ignore any previous implementation. Use only the SQL schema, SQLite database and seed data as the source of truth. Implement one phase at a time and stop after each phase for testing.
