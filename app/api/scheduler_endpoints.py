"""Scheduler execution triggers, Validation, Repairs, Exports, and Dashboard APIs."""
from flask import Blueprint, request, jsonify, Response
from app.repository.entity_repositories import (
    FacultyRepository, CourseRepository, RoomRepository, LabRepository,
    SectionRepository, RulesRepository, DepartmentRepository
)
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState
from app.scheduler.backtracking import BacktrackingSolver
from app.constraints.validator import ValidationContext
from app.validator.timetable_validator import TimetableValidator
from app.repair.repair_engine import RepairEngine
from app.exporter.timetable_exporter import TimetableExporter
from app.models.mapping import ModelMapper
from app.models.domain import Schedule
from app.api.auth import require_role

from app.constraints.validator import MasterValidator

scheduler_bp = Blueprint("scheduler", __name__)

MEM_SCHEDULE_STORE = []

def load_latest_run_to_memory():
    global MEM_SCHEDULE_STORE
    if MEM_SCHEDULE_STORE:
        return
    from app.repository.connection import DatabaseConnectionManager
    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT run_id FROM scheduler_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return
        run_id = row[0]
        cursor.execute("""
            SELECT section_id, day_id, period_no, course_id, faculty_id, room_no, lab_room_no 
            FROM schedule WHERE run_id = ?
        """, (run_id,))
        allocations = []
        for r in cursor.fetchall():
            allocations.append(Schedule(
                section_id=r[0],
                day_id=int(r[1]),
                period_no=int(r[2]),
                course_id=r[3],
                faculty_id=r[4],
                room_no=r[5],
                lab_room_no=r[6]
            ))
        MEM_SCHEDULE_STORE = allocations
    except Exception:
        pass
    finally:
        if should_close:
            conn.close()

# Repositories
fac_repo = FacultyRepository()
course_repo = CourseRepository()
room_repo = RoomRepository()
lab_repo = LabRepository()
sec_repo = SectionRepository()
rules_repo = RulesRepository()
dept_repo = DepartmentRepository()

def build_validation_context() -> ValidationContext:
    """Builds a ValidationContext from repository database mappings."""
    courses = course_repo.get_all()
    rooms_list = room_repo.get_all()
    labs_list = lab_repo.get_all()
    sections = sec_repo.get_all()
    faculties = fac_repo.get_all()
    
    from app.repository.entity_repositories import RoomSectionRepository, ClassTeacherRepository
    room_sec_repo = RoomSectionRepository()
    class_teacher_repo = ClassTeacherRepository()
    
    course_dict = {c.course_id: c for c in courses}
    room_sections = {row["section_id"]: row["room_no"] for row in room_sec_repo.find_all("room_section")}
    class_teachers = {row["section_id"]: row["faculty_id"] for row in class_teacher_repo.find_all("class_teacher")}
    
    # Static defaults from user specs
    working_days = {1, 2, 3, 4, 5}
    template_slots = {(d, p) for d in range(1, 6) for p in range(1, 8)} # 7 periods/day
    
    section_depts = {s.section_id: s.department_id for s in sections}
    
    from collections import defaultdict
    dept_course_rows = dept_repo.find_all("department_course")
    course_depts = defaultdict(list)
    for row in dept_course_rows:
        course_depts[row["course_id"]].append(row["department_id"])
        
    # Retrieve active rules
    import json
    from app.repository.connection import DatabaseConnectionManager
    conn, should_close = DatabaseConnectionManager.get_connection()
    ai_rules = []
    faculty_unavailables = set()
    try:
        cursor = conn.cursor()
        # Fetch the parameters of active, non-deleted rule versions
        cursor.execute("""
            SELECT r.parameter 
            FROM rules r
            INNER JOIN (
                SELECT rule_id, MAX(version) as max_version 
                FROM rules 
                WHERE is_deleted = 0 
                GROUP BY rule_id
            ) latest ON r.rule_id = latest.rule_id AND r.version = latest.max_version
            WHERE r.enabled = 1
        """)
        rows = cursor.fetchall()
        for row in rows:
            if row[0]:
                try:
                    param_dict = json.loads(row[0])
                    ai_rules.append(param_dict)
                except Exception:
                    pass
                    
        # Fetch faculty unavailables
        cursor.execute("SELECT faculty_id, day_id, period_no FROM faculty_unavailable")
        for row in cursor.fetchall():
            faculty_unavailables.add((row[0], int(row[1]), int(row[2])))
    finally:
        if should_close:
            conn.close()
    
    return ValidationContext(
        course_dict=course_dict,
        faculty_unavailables=faculty_unavailables,
        room_sections=room_sections,
        class_teachers=class_teachers,
        working_days=working_days,
        template_slots=template_slots,
        section_depts=section_depts,
        course_depts=dict(course_depts),
        ai_rules=ai_rules
    )

@scheduler_bp.route("/scheduler/generate", methods=["POST"])
@require_role("HOD")
def generate():
    """Generates a new schedule from database entities."""
    global MEM_SCHEDULE_STORE
    context = build_validation_context()
    sections = sec_repo.get_all()
    courses = course_repo.get_all()
    rooms_list = [r.room_no for r in room_repo.get_all()]
    labs_list = [l.lab_room_no for l in lab_repo.get_all()]
    
    # Load faculty assignments mapping from database
    from app.repository.entity_repositories import FacultyAssignmentRepository
    fac_assign_repo = FacultyAssignmentRepository()
    assignments = fac_assign_repo.find_all("faculty_assignment")
    faculty_map = {(row["section_id"], row["course_id"]): row["faculty_id"] for row in assignments}
    
    # Formulate backtracking sessions list
    sessions = []
    course_depts = context.course_depts
    for sec in sections:
        for course in courses:
            if sec.semester == course.semester and sec.department_id in course_depts.get(course.course_id, []):
                fac_id = faculty_map.get((sec.section_id, course.course_id), "F01")
                # Add theory slots
                for idx in range(course.l):
                    sessions.append(Session(f"{course.course_id}_{sec.section_id}_L_{idx}", course.course_id, sec.section_id, fac_id, "THEORY", 1, False))
                # Add tutorial slots
                for idx in range(course.t):
                    sessions.append(Session(f"{course.course_id}_{sec.section_id}_T_{idx}", course.course_id, sec.section_id, fac_id, "TUTORIAL", 1, False))
                # Add practical slots
                if course.p > 0:
                    sessions.append(Session(f"{course.course_id}_{sec.section_id}_P", course.course_id, sec.section_id, fac_id, "PRACTICAL", course.p, True))
                    
    state = SchedulingState(remaining_sessions=sessions)
    solver = BacktrackingSolver()
    
    success = solver.solve(state, context, rooms_list, labs_list)
    
    if not success:
        return jsonify({"error": "No valid schedule could be generated", "stats": solver.stats.to_dict()}), 422
        
    MEM_SCHEDULE_STORE = list(state.allocations)
    
    # Save schedule run & schedule rows to database
    from app.constraints.validator import MasterValidator
    total_penalty = MasterValidator.calculate_total_penalty(state.allocations, context)
    
    from app.repository.connection import DatabaseConnectionManager
    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT year, semester FROM academic_year WHERE is_deleted = 0 LIMIT 1")
        ay_row = cursor.fetchone()
        year, semester = (ay_row[0], ay_row[1]) if ay_row else (2026, 1)
        
        department_id = "ISC"  # HOD department
        
        # Get next version
        cursor.execute("""
            SELECT COALESCE(MAX(version), 0) + 1 
            FROM scheduler_run 
            WHERE year = ? AND semester = ? AND department_id = ?
        """, (year, semester, department_id))
        version = cursor.fetchone()[0]
        
        # Insert run
        cursor.execute("""
            INSERT INTO scheduler_run (year, semester, department_id, version, started_at, finished_at, duration_seconds, status, total_penalty)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'), ?, 'SUCCESS', ?)
        """, (year, semester, department_id, version, solver.stats.execution_time, total_penalty))
        run_id = cursor.lastrowid
        
        # Insert allocations
        for alloc in state.allocations:
            cursor.execute("""
                INSERT INTO schedule (run_id, section_id, day_id, period_no, course_id, faculty_id, room_no, lab_room_no, year, semester)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, alloc.section_id, alloc.day_id, alloc.period_no, alloc.course_id, alloc.faculty_id, alloc.room_no or None, alloc.lab_room_no or None, year, semester))
            
        conn.commit()
    except Exception as e:
        import traceback
        traceback.print_exc()
        conn.rollback()
        return jsonify({"error": f"Failed to persist schedule to database: {str(e)}"}), 500
    finally:
        if should_close:
            conn.close()
    
    return jsonify({
        "message": "Schedule generated successfully",
        "stats": solver.stats.to_dict(),
        "allocations": [ModelMapper.to_dict(a) for a in state.allocations]
    })


@scheduler_bp.route("/scheduler/validate", methods=["POST"])
@require_role("HOD")
def validate():
    """Validates the last generated schedule in memory."""
    load_latest_run_to_memory()
    context = build_validation_context()
    rooms_list = [r.room_no for r in room_repo.get_all()]
    labs_list = [l.lab_room_no for l in lab_repo.get_all()]
    
    # Read custom schedule payload if provided, otherwise use cache
    data = request.get_json() or {}
    schedule_payload = data.get("schedule")
    if schedule_payload is not None:
        test_schedule = [
            Schedule(
                run_id=s.get("run_id", 1), section_id=s["section_id"], day_id=s["day_id"], period_no=s["period_no"],
                course_id=s["course_id"], faculty_id=s["faculty_id"], room_no=s.get("room_no"), lab_room_no=s.get("lab_room_no"),
                year=s.get("year", 2026), semester=s.get("semester", 1), schedule_id=s.get("schedule_id")
            )
            for s in schedule_payload
        ]
    else:
        test_schedule = MEM_SCHEDULE_STORE

    report = TimetableValidator.validate_timetable(test_schedule, context, rooms_list, labs_list)
    return jsonify(report.to_dict())


@scheduler_bp.route("/scheduler/repair", methods=["POST"])
@require_role("HOD")
def repair():
    """Repairs the last generated schedule in memory."""
    global MEM_SCHEDULE_STORE
    load_latest_run_to_memory()
    context = build_validation_context()
    rooms_list = [r.room_no for r in room_repo.get_all()]
    labs_list = [l.lab_room_no for l in lab_repo.get_all()]
    
    data = request.get_json() or {}
    schedule_payload = data.get("schedule")
    if schedule_payload is not None:
        test_schedule = [
            Schedule(
                run_id=s.get("run_id", 1), section_id=s["section_id"], day_id=s["day_id"], period_no=s["period_no"],
                course_id=s["course_id"], faculty_id=s["faculty_id"], room_no=s.get("room_no"), lab_room_no=s.get("lab_room_no"),
                year=s.get("year", 2026), semester=s.get("semester", 1), schedule_id=s.get("schedule_id")
            )
            for s in schedule_payload
        ]
    else:
        test_schedule = MEM_SCHEDULE_STORE

    repaired, stats_dict, remaining = RepairEngine.repair_timetable(test_schedule, context, rooms_list, labs_list)
    
    # Save back to cache if payload was empty
    if schedule_payload is None:
        MEM_SCHEDULE_STORE = repaired

    return jsonify({
        "stats": stats_dict,
        "remaining_conflicts": remaining,
        "repaired_schedule": [ModelMapper.to_dict(a) for a in repaired]
    })


@scheduler_bp.route("/scheduler/export", methods=["GET"])
@require_role("HOD")
def export():
    """Exports timetable grids to CSV files."""
    load_latest_run_to_memory()
    export_type = request.args.get("type", "section")
    id_val = request.args.get("id")
    
    if not id_val:
        return jsonify({"error": "Missing parameter 'id'"}), 400
        
    format_val = request.args.get("format", "csv")
    
    if format_val == "html":
        html_data = TimetableExporter.to_html_print_layout(MEM_SCHEDULE_STORE, export_type, id_val)
        return Response(
            html_data,
            mimetype="text/html"
        )

    csv_data = ""
    if export_type == "section":
        csv_data = TimetableExporter.to_csv_section(MEM_SCHEDULE_STORE, id_val)
    elif export_type == "faculty":
        csv_data = TimetableExporter.to_csv_faculty(MEM_SCHEDULE_STORE, id_val)
    elif export_type == "lab":
        csv_data = TimetableExporter.to_csv_lab(MEM_SCHEDULE_STORE, id_val)
    else:
        return jsonify({"error": "Invalid export type"}), 400
        
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=timetable_{export_type}_{id_val}.csv"}
    )


@scheduler_bp.route("/dashboard/stats", methods=["GET"])
@require_role("HOD")
def dashboard_stats():
    """Aggregates quick dashboard counts and database statistics summaries."""
    sections = sec_repo.get_all()
    student_count = sum(s.capacity for s in sections)
    
    from app.repository.entity_repositories import ClassTeacherRepository
    class_teacher_repo = ClassTeacherRepository()
    class_teacher_count = len(class_teacher_repo.find_all("class_teacher"))

    # Fetch scheduler run stats
    from app.repository.connection import DatabaseConnectionManager
    conn, should_close = DatabaseConnectionManager.get_connection()
    run_count = 0
    latest_time = "N/A"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), MAX(finished_at) FROM scheduler_run WHERE status = 'SUCCESS'")
        row = cursor.fetchone()
        if row:
            run_count = row[0] or 0
            latest_time = row[1] or "N/A"
    except Exception:
        pass
    finally:
        if should_close:
            conn.close()
    
    return jsonify({
        "faculty_count": len(fac_repo.get_all()),
        "course_count": len(course_repo.get_all()),
        "room_count": len(room_repo.get_all()),
        "lab_count": len(lab_repo.get_all()),
        "section_count": len(sections),
        "department_count": len(dept_repo.get_all()),
        "rule_count": len(rules_repo.get_all()),
        "student_count": student_count,
        "class_teacher_count": class_teacher_count,
        "generated_timetables_count": run_count,
        "latest_generation_time": latest_time
    })
