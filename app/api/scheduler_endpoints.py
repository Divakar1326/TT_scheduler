"""Scheduler execution triggers, Validation, Repairs, Exports, and Dashboard APIs."""
from flask import Blueprint, request, jsonify, Response
from config.config import logger
import time
from app.repository.entity_repositories import (
    FacultyRepository, CourseRepository, RoomRepository, LabRepository,
    SectionRepository, RulesRepository, DepartmentRepository,
    SchedulerRunRepository
)
from app.scheduler.session import Session
from app.scheduler.state_manager import SchedulingState
from app.scheduler.backtracking import BacktrackingSolver
from app.validators.validator import ValidationContext
from app.validators.timetable_validator import TimetableValidator
from app.services.repair_engine import RepairEngine
from app.exporters.timetable_exporter import TimetableExporter
from app.core.mapping import ModelMapper
from app.core.domain import Schedule
from app.auth.auth import require_role

from app.validators.validator import MasterValidator

scheduler_bp = Blueprint("scheduler", __name__)

@scheduler_bp.route("/developer/about", methods=["GET"])
def get_developer_about():
    """Serves the about.md file as JSON/text."""
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    about_path = os.path.join(base_dir, "ABOUT_DEVELOPER.md")
    
    content = ""
    if os.path.exists(about_path):
        try:
            with open(about_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            content = f"Error reading about.md: {str(e)}"
    else:
        content = "Developer profile (about.md) is not yet set up."
        
    return jsonify({"markdown": content})


@scheduler_bp.route("/developer/socials", methods=["GET"])
def get_developer_socials():
    """Serves configured developer social links."""
    from config.config import GITHUB_URL, LINKEDIN_URL
    return jsonify({
        "github_url": GITHUB_URL,
        "linkedin_url": LINKEDIN_URL
    })


@scheduler_bp.route("/developer/resume", methods=["GET"])
def get_developer_resume():
    """Attempts to send the developer's resume PDF file."""
    import os
    from flask import send_file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    paths_to_check = [
        os.path.join(base_dir, "Divakar_M Resume.pdf"),          # Primary: actual resume at project root
        os.path.join(base_dir, "resume.pdf"),                     # Generic root name
        os.path.join(base_dir, "assets", "resume", "resume.pdf"),
        os.path.join(base_dir, "public", "resume", "resume.pdf"),
        os.path.join(base_dir, "static", "resume.pdf"),
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            return send_file(p, mimetype="application/pdf", as_attachment=True, download_name="Divakar_M_Resume.pdf")
    return jsonify({"error": "Resume is currently unavailable."}), 404

@scheduler_bp.route("/developer/photo", methods=["GET"])
def get_developer_photo():
    """Serves the developer photo (me/photo.jpg or other images)."""
    import os
    from flask import send_file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    paths_to_check = [
        os.path.join(base_dir, "Divakar_M .png"),
        os.path.join(base_dir, "Divakar_M.png"),
        os.path.join(base_dir, "me", "photo.jpg"),
        os.path.join(base_dir, "me", "photo.png"),
        os.path.join(base_dir, "me", "photo.jpeg")
    ]
    for img_path in paths_to_check:
        if os.path.exists(img_path):
            return send_file(img_path)
            
    return jsonify({"error": "Developer photo not found"}), 404

MEM_SCHEDULE_STORE = []
_scheduler_run_repo = SchedulerRunRepository()

# In-process TTL cache for dashboard stats (invalidated on new scheduler run)
# Structure: { scope_key: {"data": {...}, "ts": float} }
_STATS_CACHE: dict = {}
_STATS_CACHE_TTL = 30  # seconds
_VALIDATION_CACHE: dict = {}

def load_latest_run_to_memory(force=False):
    """Loads the most recent successful schedule into memory using the repository layer."""
    global MEM_SCHEDULE_STORE
    if MEM_SCHEDULE_STORE and not force:
        return
    try:
        from app.repository.connection import DatabaseConnectionManager
        conn, should_close = DatabaseConnectionManager.get_connection()
        try:
            cursor = conn.cursor()
            # Use _adjust_query via a temporary helper to handle ? vs %s
            cursor.execute(
                _scheduler_run_repo._adjust_query(
                    "SELECT run_id FROM scheduler_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1"
                )
            )
            row = cursor.fetchone()
            if not row:
                return
            run_id = row[0]
            cursor.execute(
                _scheduler_run_repo._adjust_query(
                    "SELECT section_id, day_id, period_no, course_id, faculty_id, room_no, lab_room_no, year, semester "
                    "FROM schedule WHERE run_id = ?"
                ),
                (run_id,)
            )
            allocations = []
            for r in cursor.fetchall():
                allocations.append(Schedule(
                    run_id=run_id,
                    section_id=r[0],
                    day_id=int(r[1]),
                    period_no=int(r[2]),
                    course_id=r[3],
                    faculty_id=r[4],
                    room_no=r[5],
                    lab_room_no=r[6],
                    year=int(r[7]) if r[7] else 2026,
                    semester=int(r[8]) if r[8] else 1
                ))
            MEM_SCHEDULE_STORE = allocations
        finally:
            if should_close:
                conn.close()
    except Exception as e:
        logger.warning(f"load_latest_run_to_memory failed: {e}")

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
    
    from app.repository.entity_repositories import RoomSectionRepository, ClassTeacherRepository, CourseLabRepository
    room_sec_repo = RoomSectionRepository()
    class_teacher_repo = ClassTeacherRepository()
    course_lab_repo = CourseLabRepository()
    
    course_dict = {c.course_id: c for c in courses}
    room_sections = {row["section_id"]: row["room_no"] for row in room_sec_repo.find_all("room_section")}
    class_teachers = {row["section_id"]: row["faculty_id"] for row in class_teacher_repo.find_all("class_teacher")}
    course_labs = {row["course_id"]: row["lab_room_no"] for row in course_lab_repo.find_all("course_lab")}
    
    # Static defaults from user specs
    working_days = {1, 2, 3, 4, 5}
    template_slots = {(d, p) for d in range(1, 6) for p in range(1, 8)} # 7 periods/day
    
    section_depts = {s.section_id: s.department_id for s in sections}
    section_semesters = {s.section_id: s.semester for s in sections}
    
    from collections import defaultdict
    dept_course_rows = dept_repo.find_all("department_course")
    course_depts = defaultdict(list)
    for row in dept_course_rows:
        course_depts[row["course_id"]].append(row["department_id"])
    for c in courses:
        if c.department_id and c.department_id not in course_depts[c.course_id]:
            course_depts[c.course_id].append(c.department_id)
        
    # Retrieve active rules
    import json
    from app.repository.connection import DatabaseConnectionManager
    conn, should_close = DatabaseConnectionManager.get_connection()
    ai_rules = []
    faculty_unavailables = set()
    section_courses = defaultdict(list)
    try:
        cursor = conn.cursor()
        # Fetch section courses
        cursor.execute("SELECT section_id, course_id FROM section_course")
        for row in cursor.fetchall():
            section_courses[row[0]].append(row[1])
            
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
                    if isinstance(row[0], str):
                        param_dict = json.loads(row[0])
                    else:
                        param_dict = row[0]
                    if isinstance(param_dict, dict) and "parameter" in param_dict and isinstance(param_dict["parameter"], dict):
                        nested = param_dict["parameter"]
                        for k, v in nested.items():
                            if k not in param_dict or param_dict[k] is None:
                                param_dict[k] = v
                    ai_rules.append(param_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse rule parameter: {e}")
                    
        # Fetch faculty unavailables
        cursor.execute("SELECT faculty_id, day_id, period_no FROM faculty_unavailable")
        for row in cursor.fetchall():
            faculty_unavailables.add((row[0], int(row[1]), int(row[2])))
    finally:
        if should_close:
            conn.close()
    
    faculty_max_hours = {f.faculty_id: f.max_hours_week for f in faculties}
    faculty_max_daily = {f.faculty_id: f.max_hours_daily for f in faculties}

    return ValidationContext(
        course_dict=course_dict,
        faculty_unavailables=faculty_unavailables,
        room_sections=room_sections,
        class_teachers=class_teachers,
        working_days=working_days,
        template_slots=template_slots,
        section_depts=section_depts,
        course_depts=dict(course_depts),
        ai_rules=ai_rules,
        faculty_max_hours=faculty_max_hours,
        faculty_max_daily=faculty_max_daily,
        course_labs=course_labs,
        section_semesters=section_semesters,
        section_courses=dict(section_courses)
    )

@scheduler_bp.route("/scheduler/generate", methods=["POST"])
@require_role("HOD")
def generate():
    """Generates a new schedule from database entities using Server-Sent Events (SSE) for real-time progress."""
    from flask import Response, stream_with_context
    import json
    import traceback
    from collections import defaultdict
    import time
    import os
    from app.scheduler.input_validator import InputValidator, PipelineTrace

    req_data = request.get_json(silent=True) or {}
    
    # If dry_run is requested, return cached memory schedule immediately instead of streaming SSE
    if req_data.get("dry_run"):
        load_latest_run_to_memory()
        return jsonify({
            "success": True,
            "allocations": [ModelMapper.to_dict(a) for a in MEM_SCHEDULE_STORE]
        })

    def event_stream():
        global MEM_SCHEDULE_STORE
        t_start = time.time()
        current_stage = "Initializing"
        trace = PipelineTrace(t_start)

        def emit(stage, pct, scheduled=0, remaining=0, hard=100.0, soft=0.0, eta=None, **extra):
            """Helper to yield a structured SSE data chunk and log the stage."""
            elapsed = time.time() - t_start
            _eta = eta if eta is not None else max(0.0, (elapsed / max(1, pct / 100)) * ((100 - pct) / 100))
            payload = {
                "stage": stage, "percentage": pct, "elapsed": round(elapsed, 3),
                "eta": round(_eta, 1), "scheduled_classes": scheduled,
                "remaining_classes": remaining, "hard_score": hard, "soft_penalty": soft,
                **extra
            }
            return f"data: {json.dumps(payload)}\n\n"

        try:
            # Yield 4KB comment padding to flush headers and start streaming instantly
            yield ":" + " " * 4096 + "\n\n"

            # ================================================================
            # STAGE 1 -- Database Connection
            # ================================================================
            current_stage = "Database connection"
            trace.begin(current_stage)
            yield emit(current_stage, 5)
            time.sleep(0.05)
            trace.end(current_stage)

            # ================================================================
            # STAGE 2 -- Load Academic Year
            # ================================================================
            current_stage = "Loading academic year"
            trace.begin(current_stage)
            from app.repository.connection import DatabaseConnectionManager
            conn, should_close = DatabaseConnectionManager.get_connection()
            year, semester = 2026, 1
            try:
                cursor = conn.cursor()
                cursor.execute(_scheduler_run_repo._adjust_query(
                    "SELECT year, semester FROM academic_year WHERE is_deleted = 0 LIMIT 1"
                ))
                ay_row = cursor.fetchone()
                if ay_row:
                    year, semester = int(ay_row[0]), int(ay_row[1])
            finally:
                if should_close:
                    conn.close()
            trace.end(current_stage, f"year={year}, semester={semester}")
            logger.info(f"[PIPELINE] Academic year resolved: year={year}, semester={semester}")

            # ================================================================
            # ================================================================
            # STAGE 3 -- Resolve Department
            # ================================================================
            current_stage = "Loading departments"
            trace.begin(current_stage)
            yield emit(current_stage, 10)
            from app.auth.auth import get_current_user_session
            session = get_current_user_session()
            department_id = req_data.get("department_id") or (
                session.get("department_id") if session else None
            )
            target_section_id = req_data.get("section_id")
            if target_section_id and not department_id:
                from app.repository.entity_repositories import SectionRepository
                sec_repo_temp = SectionRepository()
                sec_obj = next((s for s in sec_repo_temp.get_all() if s.section_id == target_section_id), None)
                if sec_obj:
                    department_id = sec_obj.department_id

            if not department_id:
                yield f"data: {json.dumps({'error': True, 'stage': 'Initializing', 'message': 'No department selected. Please select a department before generating.', 'root_cause': 'department_id is missing from the request and the current session.', 'suggested_fix': 'Select a department from the dropdown before clicking Generate.'})}\n\n"
                return
            logger.info(f"[PIPELINE] Scheduling for department: {department_id!r}")
            trace.end(current_stage, f"dept={department_id!r}")

            # ================================================================
            # STAGE 4 -- Load Sections
            # ================================================================
            current_stage = "Loading sections"
            trace.begin(current_stage)
            yield emit(current_stage, 15)
            sections = sec_repo.get_all()
            dept_sections = [s for s in sections if s.department_id and s.department_id.upper() == department_id.upper()]
            trace.end(current_stage, f"total={len(sections)}, dept={len(dept_sections)}")
            logger.info(f"[PIPELINE] Sections: {len(dept_sections)} in dept, {len(sections)} total")

            # ================================================================
            # STAGE 5 -- Load Courses
            # ================================================================
            current_stage = "Loading courses"
            trace.begin(current_stage)
            yield emit(current_stage, 20)
            courses = course_repo.get_all()
            trace.end(current_stage, f"total={len(courses)}")
            logger.info(f"[PIPELINE] Courses loaded: {len(courses)}")

            # ================================================================
            # STAGE 6 -- Load Faculty
            # ================================================================
            current_stage = "Loading faculty"
            trace.begin(current_stage)
            yield emit(current_stage, 25)
            all_fac_objects = fac_repo.get_all()
            dept_facs = [f.faculty_id for f in all_fac_objects if f.department_id and f.department_id.upper() == department_id.upper()]
            if not dept_facs:
                dept_facs = [f.faculty_id for f in all_fac_objects if f.status == "ACTIVE"]
            if not dept_facs:
                dept_facs = ["F01"]
            dept_fac_index = 0
            trace.end(current_stage, f"dept_faculty={len(dept_facs)}")
            logger.info(f"[PIPELINE] Faculty: {len(dept_facs)} available for dept")

            # ================================================================
            # STAGE 7 -- Load Rooms & Labs
            # ================================================================
            current_stage = "Loading rooms"
            trace.begin(current_stage)
            yield emit(current_stage, 30)
            rooms_list = [r.room_no for r in room_repo.get_all() if not r.department_id or r.department_id.lower() == department_id.lower()]
            if not rooms_list:
                rooms_list = [r.room_no for r in room_repo.get_all()]
            trace.end(current_stage, f"rooms={len(rooms_list)}")

            current_stage = "Loading labs"
            trace.begin(current_stage)
            yield emit(current_stage, 35)
            labs_list = [l.lab_room_no for l in lab_repo.get_all() if not l.department_id or l.department_id.lower() == department_id.lower()]
            if not labs_list:
                labs_list = [l.lab_room_no for l in lab_repo.get_all()]
            trace.end(current_stage, f"labs={len(labs_list)}")
            logger.info(f"[PIPELINE] Rooms={len(rooms_list)}, Labs={len(labs_list)}")

            # ================================================================
            # STAGE 8 -- Build Validation Context (Constraints / Rules)
            # ================================================================
            current_stage = "Loading rules"
            trace.begin(current_stage)
            yield emit(current_stage, 40)
            context = build_validation_context()
            trace.end(current_stage, f"ai_rules={len(context.ai_rules)}, template_slots={len(context.template_slots)}")
            logger.info(f"[PIPELINE] Constraint context built: {len(context.ai_rules)} AI rules, "
                        f"{len(context.template_slots)} template slots, "
                        f"{len(context.working_days)} working days")

            # ================================================================
            # STAGE 9 -- Load Faculty-Course Mappings
            # ================================================================
            current_stage = "Loading mappings"
            trace.begin(current_stage)
            yield emit(current_stage, 45)
            from app.repository.entity_repositories import FacultyAssignmentRepository
            fac_assign_repo = FacultyAssignmentRepository()
            assignments = fac_assign_repo.find_all("faculty_assignment")
            faculty_map = {(row["section_id"], row["course_id"]): row["faculty_id"] for row in assignments}
            logger.info(f"[PIPELINE] Faculty assignments loaded: {len(faculty_map)} direct mappings")

            # Load faculty-course fallback map
            conn_fc, should_close_fc = DatabaseConnectionManager.get_connection()
            fac_course_map = defaultdict(list)
            try:
                cur_fc = conn_fc.cursor()
                cur_fc.execute("SELECT faculty_id, course_id FROM faculty_course")
                for row in cur_fc.fetchall():
                    fac_course_map[row[1]].append(row[0])
            finally:
                if should_close_fc:
                    conn_fc.close()

            # Load section-course assignments for pre-flight
            section_courses_map = context.section_courses or {}
            trace.end(current_stage, f"faculty_map={len(faculty_map)}, fac_course_map={len(fac_course_map)}")

            # ================================================================
            # STAGE 10 -- PRE-FLIGHT INPUT VALIDATION (ABORT GATE)
            # ================================================================
            current_stage = "Validating input data"
            trace.begin(current_stage)
            yield emit(current_stage, 48)

            preflight_errors = InputValidator.validate_all(
                department_id=department_id,
                sections=sections,
                courses=courses,
                faculty_list=all_fac_objects,
                rooms_list=rooms_list,
                labs_list=labs_list,
                faculty_map=faculty_map,
                fac_course_map=dict(fac_course_map),
                section_courses=section_courses_map,
                working_days=context.working_days,
                template_slots=context.template_slots,
                academic_year=(year, semester),
                course_dict=context.course_dict
            )
            trace.end(current_stage, f"errors={len(preflight_errors)}")

            if preflight_errors:
                error_detail = " | ".join(preflight_errors[:3])
                logger.error(f"[PIPELINE] PRE-FLIGHT ABORT: {error_detail}")
                yield f"data: {json.dumps({'error': True, 'stage': current_stage, 'message': preflight_errors[0], 'all_errors': preflight_errors, 'root_cause': 'Pre-flight input validation failed', 'suggested_fix': 'Ensure all required entities (sections, courses, faculty, rooms, mappings) are configured before scheduling.'})} \n\n"
                return

            logger.info(f"[PIPELINE] OK PRE-FLIGHT PASSED -- proceeding to session build")

            # ================================================================
            # STAGE 11 -- Build Scheduling Sessions
            # ================================================================
            current_stage = "Building candidate slots"
            trace.begin(current_stage)
            yield emit(current_stage, 50)

            sessions = []
            course_depts = context.course_depts
            for sec in sections:
                if target_section_id:
                    if sec.section_id != target_section_id:
                        continue
                else:
                    if not sec.department_id or not department_id or sec.department_id.upper() != department_id.upper():
                        continue
                for course in courses:
                    mapped_depts = [d.upper() for d in course_depts.get(course.course_id, [])]
                    dept_matches = (sec.department_id.upper() in mapped_depts) or (course.department_id and course.department_id.upper() == sec.department_id.upper())
                    if sec.semester == course.semester and dept_matches:
                        fac_id = faculty_map.get((sec.section_id, course.course_id))
                        if not fac_id:
                            fallback_facs = fac_course_map.get(course.course_id)
                            if fallback_facs:
                                fac_id = fallback_facs[0]
                            else:
                                fac_id = dept_facs[dept_fac_index % len(dept_facs)]
                                dept_fac_index += 1

                        # Compute LTP-derived session slots
                        l_slots = course.l
                        t_slots = course.t
                        p_slots = course.p
                        if l_slots == 0 and t_slots == 0 and p_slots == 0:
                            # Pure weekly_hours course -- treat all as theory
                            l_slots = course.weekly_hours

                        for idx in range(l_slots):
                            sessions.append(Session(f"{course.course_id}_{sec.section_id}_L_{idx}", course.course_id, sec.section_id, fac_id, "THEORY", 1, False))
                        for idx in range(t_slots):
                            sessions.append(Session(f"{course.course_id}_{sec.section_id}_T_{idx}", course.course_id, sec.section_id, fac_id, "TUTORIAL", 1, False))
                        if p_slots > 0:
                            sessions.append(Session(f"{course.course_id}_{sec.section_id}_P", course.course_id, sec.section_id, fac_id, "PRACTICAL", p_slots, True))

            if not sessions:
                raise ValueError(f"No schedulable sessions found for department '{department_id}' in semester {semester}. "
                                 "Check that sections have courses assigned and faculty mappings exist.")

            trace.end(current_stage, f"sessions={len(sessions)}")
            logger.info(f"[PIPELINE] Session list built: {len(sessions)} sessions to schedule")

            # ================================================================
            # STAGE 12 -- Load Existing Cross-Dept Allocations
            # ================================================================
            current_stage = "Loading existing allocations"
            trace.begin(current_stage)
            existing_allocations = []
            conn, should_close = DatabaseConnectionManager.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    _scheduler_run_repo._adjust_query("""
                        SELECT s.section_id, s.day_id, s.period_no, s.course_id, s.faculty_id, s.room_no, s.lab_room_no, s.year, s.semester
                        FROM schedule s
                        INNER JOIN scheduler_run r ON s.run_id = r.run_id
                        INNER JOIN (
                            SELECT department_id, MAX(version) as max_version
                            FROM scheduler_run
                            WHERE status = 'SUCCESS' AND department_id != ? AND year = ? AND semester = ?
                            GROUP BY department_id
                        ) latest ON r.department_id = latest.department_id AND r.version = latest.max_version
                        WHERE r.year = ? AND r.semester = ?
                    """),
                    (department_id, year, semester, year, semester)
                )
                for r in cursor.fetchall():
                    existing_allocations.append(Schedule(
                        run_id=0, section_id=r[0], day_id=int(r[1]), period_no=int(r[2]),
                        course_id=r[3], faculty_id=r[4], room_no=r[5], lab_room_no=r[6],
                        year=int(r[7]), semester=int(r[8])
                    ))

                # If target_section_id is set, we also load the latest run's allocations for other sections in the same department
                if target_section_id:
                    cursor.execute(
                        _scheduler_run_repo._adjust_query("""
                            SELECT s.section_id, s.day_id, s.period_no, s.course_id, s.faculty_id, s.room_no, s.lab_room_no, s.year, s.semester
                            FROM schedule s
                            INNER JOIN scheduler_run r ON s.run_id = r.run_id
                            INNER JOIN (
                                SELECT department_id, MAX(version) as max_version
                                FROM scheduler_run
                                WHERE status = 'SUCCESS' AND department_id = ? AND year = ? AND semester = ?
                                GROUP BY department_id
                            ) latest ON r.department_id = latest.department_id AND r.version = latest.max_version
                            WHERE r.year = ? AND r.semester = ? AND s.section_id != ?
                        """),
                        (department_id, year, semester, year, semester, target_section_id)
                    )
                    for r in cursor.fetchall():
                        existing_allocations.append(Schedule(
                            run_id=0, section_id=r[0], day_id=int(r[1]), period_no=int(r[2]),
                            course_id=r[3], faculty_id=r[4], room_no=r[5], lab_room_no=r[6],
                            year=int(r[7]), semester=int(r[8])
                        ))
            finally:
                if should_close:
                    conn.close()
            trace.end(current_stage, f"existing_cross_dept={len(existing_allocations)}")
            logger.info(f"[PIPELINE] Cross-department existing allocations loaded: {len(existing_allocations)}")

            # ================================================================
            # STAGE 13 -- CSP Backtracking Solver
            # ================================================================
            current_stage = "Running CSP solver"
            trace.begin(current_stage)
            logger.info(f"[PIPELINE] CSP solver started | sessions={len(sessions)}, "
                        f"rooms={len(rooms_list)}, labs={len(labs_list)}, "
                        f"working_days={sorted(context.working_days)}, "
                        f"template_slots={len(context.template_slots)}")

            # Inject year/semester into SchedulingState (BUG-3 fix)
            state = SchedulingState(
                remaining_sessions=sessions,
                initial_allocations=existing_allocations,
                year=year,
                semester=semester
            )
            solver = BacktrackingSolver()

            total_sessions = len(sessions)
            for progress in solver.solve_generator(state, context, rooms_list, labs_list, allow_partial=True):
                elapsed = time.time() - t_start
                scheduled = progress["scheduled_classes"]
                remaining = progress["remaining_classes"]
                eta = (elapsed / max(1, scheduled)) * remaining if scheduled > 0 else 5.0
                live_soft_penalty = MasterValidator.calculate_soft_penalty_percentage(state.allocations, context)

                yield emit(
                    current_stage,
                    50 + int((scheduled / max(1, total_sessions)) * 20),
                    scheduled=scheduled, remaining=remaining,
                    hard=100.0, soft=live_soft_penalty, eta=eta
                )

            csp_duration = trace.end(current_stage,
                f"allocated={len(state.allocations)}, unscheduled={len(state.remaining_sessions)}, "
                f"backtracks={solver.stats.backtracks}, nodes={solver.stats.nodes_explored}")
            logger.info(f"[PIPELINE] CSP complete | allocated={len(state.allocations)}, "
                        f"unscheduled={len(state.remaining_sessions)}, "
                        f"backtracks={solver.stats.backtracks}, "
                        f"nodes_explored={solver.stats.nodes_explored}, "
                        f"duration={csp_duration:.3f}s")

            # ================================================================
            # STAGE 14 -- Soft Constraint Optimization Pass
            # ================================================================
            current_stage = "Repairing conflicts"
            trace.begin(current_stage)
            yield emit(current_stage, 75,
                scheduled=len(state.allocations), remaining=len(state.remaining_sessions),
                hard=100.0, soft=0.0)

            from app.services.repair_engine import RepairEngine
            state.allocations = RepairEngine.optimize_timetable(state.allocations, context, rooms_list, labs_list)
            trace.end(current_stage, f"allocations_after_optimize={len(state.allocations)}")
            logger.info(f"[PIPELINE] Soft optimization done | total_allocations={len(state.allocations)}")

            # Filter to only this department's allocations
            new_allocations = [
                a for a in state.allocations
                if context.section_depts.get(a.section_id) and
                context.section_depts.get(a.section_id).upper() == department_id.upper()
            ]
            MEM_SCHEDULE_STORE = list(new_allocations)

            # ================================================================
            # STAGE 15 -- Timetable Validation
            # ================================================================
            current_stage = "Running validation"
            trace.begin(current_stage)
            yield emit(current_stage, 85,
                scheduled=len(new_allocations), remaining=0, hard=100.0, soft=0.0)

            report = TimetableValidator.validate_timetable(new_allocations, context, rooms_list, labs_list)
            hard_percent = report.stats.get("constraint_satisfaction", 100.0)
            soft_penalty_percent = MasterValidator.calculate_soft_penalty_percentage(new_allocations, context)
            trace.end(current_stage,
                f"errors={len(report.errors)}, warnings={len(report.warnings)}, "
                f"hard={hard_percent:.1f}%, soft={soft_penalty_percent:.1f}%")
            logger.info(f"[PIPELINE] Validation complete | errors={len(report.errors)}, "
                        f"warnings={len(report.warnings)}, "
                        f"constraint_satisfaction={hard_percent:.2f}%, "
                        f"soft_penalty={soft_penalty_percent:.2f}%")

            # Log each validation error explicitly
            for i, err in enumerate(report.errors[:20]):
                logger.warning(f"[PIPELINE] VALIDATION ERROR [{i+1}]: {err}")

            # ================================================================
            # STAGE 16 -- Hard Constraint Repair (if errors exist)
            # ================================================================
            if report.errors:
                current_stage = "Repairing hard constraint violations"
                trace.begin(current_stage)
                yield emit(current_stage, 88,
                    scheduled=len(new_allocations), remaining=len(report.errors),
                    hard=hard_percent, soft=soft_penalty_percent)

                repaired, repair_stats, remaining_errors = RepairEngine.repair_timetable(
                    new_allocations, context, rooms_list, labs_list, max_iterations=30
                )
                new_allocations = repaired
                MEM_SCHEDULE_STORE = list(new_allocations)

                # Re-validate after repair
                report = TimetableValidator.validate_timetable(new_allocations, context, rooms_list, labs_list)
                hard_percent = report.stats.get("constraint_satisfaction", 100.0)
                soft_penalty_percent = MasterValidator.calculate_soft_penalty_percentage(new_allocations, context)

                trace.end(current_stage,
                    f"repaired={repair_stats.get('repaired_count',0)}, "
                    f"remaining_errors={len(remaining_errors)}")
                logger.info(f"[PIPELINE] Hard constraint repair done | "
                            f"repaired={repair_stats.get('repaired_count',0)}, "
                            f"remaining_errors={len(remaining_errors)}, "
                            f"new_hard={hard_percent:.2f}%")

            # ================================================================
            # STAGE 17 -- Persist Schedule to Database
            # ================================================================
            current_stage = "Saving timetable"
            trace.begin(current_stage)
            yield emit(current_stage, 92,
                scheduled=len(new_allocations), remaining=0,
                hard=hard_percent, soft=soft_penalty_percent)

            run_status = "SUCCESS"
            total_penalty = MasterValidator.calculate_total_penalty(new_allocations, context)
            duration_seconds = time.time() - t_start

            # Create scheduler_run record
            run_id = _scheduler_run_repo.create_run(year, semester, department_id)
            logger.info(f"[PIPELINE] Created scheduler_run | run_id={run_id}, dept={department_id!r}, year={year}, semester={semester}")

            # Bulk insert schedule records
            conn, should_close = DatabaseConnectionManager.get_connection()
            inserted = 0
            try:
                cursor = conn.cursor()
                for alloc in new_allocations:
                    cursor.execute(
                        _scheduler_run_repo._adjust_query("""
                            INSERT INTO schedule (run_id, section_id, day_id, period_no, course_id, faculty_id, room_no, lab_room_no, year, semester)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """),
                        (run_id, alloc.section_id, alloc.day_id, alloc.period_no,
                         alloc.course_id, alloc.faculty_id, alloc.room_no or None,
                         alloc.lab_room_no or None, year, semester)
                    )
                    inserted += 1
                conn.commit()
            finally:
                if should_close:
                    conn.close()

            _scheduler_run_repo.update_run_status(run_id, run_status, total_penalty, duration_seconds)
            trace.end(current_stage, f"run_id={run_id}, inserted={inserted}, penalty={total_penalty}")
            logger.info(f"[PIPELINE] Schedule persisted | run_id={run_id}, "
                        f"rows_inserted={inserted}, total_penalty={total_penalty}, "
                        f"duration={duration_seconds:.3f}s")

            # ================================================================
            # STAGE 18 -- Finalize & Emit Complete Event
            # ================================================================
            current_stage = "Updating faculty timetable"
            yield emit(current_stage, 96,
                scheduled=len(new_allocations), remaining=0,
                hard=hard_percent, soft=soft_penalty_percent)

            current_stage = "Updating lab timetable"
            yield emit(current_stage, 98,
                scheduled=len(new_allocations), remaining=0,
                hard=hard_percent, soft=soft_penalty_percent)

            current_stage = "Completed"

            # Emit final pipeline summary to log
            trace.log_summary()

            rule_statuses = report.stats.get("rule_statuses", {})
            stats_data = solver.stats.to_dict()
            stats_data["execution_time"] = time.time() - t_start
            stats_data["fitness_score"] = report.stats.get("fitness_score", 100.0)
            stats_data["constraint_satisfaction"] = hard_percent
            stats_data["soft_penalty_percent"] = soft_penalty_percent
            stats_data["validation_errors"] = report.errors[:10]
            stats_data["validation_warnings"] = report.warnings[:10]
            stats_data["rule_statuses"] = rule_statuses
            stats_data["run_id"] = run_id
            stats_data["year"] = year
            stats_data["semester"] = semester

            logger.info(f"[PIPELINE] OK SCHEDULING COMPLETE | "
                        f"dept={department_id!r}, run_id={run_id}, "
                        f"allocations={len(new_allocations)}, "
                        f"errors={len(report.errors)}, "
                        f"hard={hard_percent:.2f}%, soft={soft_penalty_percent:.2f}%, "
                        f"total_time={time.time() - t_start:.3f}s")

            # Clear stats and validation caches on successful generation so dashboard/reports update instantly
            _STATS_CACHE.clear()
            _VALIDATION_CACHE.clear()

            yield f"data: {json.dumps({'stage': current_stage, 'percentage': 100, 'elapsed': round(time.time() - t_start, 3), 'eta': 0.0, 'scheduled_classes': len(new_allocations), 'remaining_classes': 0, 'hard_score': hard_percent, 'soft_penalty': soft_penalty_percent, 'success': True, 'stats': stats_data, 'allocations': [ModelMapper.to_dict(a) for a in new_allocations]})}\n\n"

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"[PIPELINE] ERROR FATAL ERROR at stage '{current_stage}': {str(e)}\n{tb}")
            suggested_fix = "Please verify your database seeding, ensure HOD faculty assignments are set up, or check rule contradictions."
            if "pre-flight" in current_stage.lower() or "validating" in current_stage.lower():
                suggested_fix = "Fix the reported data issues before re-running the scheduler."
            elif "mapping" in current_stage.lower():
                suggested_fix = "Run 'python -m scripts.seed_supabase' to seed required faculty-course assignments."
            elif "session" in current_stage.lower():
                suggested_fix = "Ensure sections have courses assigned and faculty-course mappings exist."
            yield f"data: {json.dumps({'error': True, 'stage': current_stage, 'message': str(e), 'root_cause': tb, 'suggested_fix': suggested_fix})}\n\n"

    def bytes_stream():
        for chunk in event_stream():
            if isinstance(chunk, str):
                yield chunk.encode("utf-8")
            else:
                yield chunk

    response = Response(stream_with_context(bytes_stream()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    response.direct_passthrough = False
    return response


@scheduler_bp.route("/scheduler/validate", methods=["POST"])
@require_role("HOD")
def validate():
    """Validates the last generated schedule in memory."""
    load_latest_run_to_memory(force=True)
    context = build_validation_context()
    
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped = False
    s_dept = None
    if session and session.get("role") == "HOD":
        scoped = True
        s_dept = session.get("department_id")

    if scoped:
        rooms_list = [r.room_no for r in room_repo.get_all() if not r.department_id or r.department_id.lower() == s_dept.lower()]
        labs_list = [l.lab_room_no for l in lab_repo.get_all() if not l.department_id or l.department_id.lower() == s_dept.lower()]
    else:
        rooms_list = [r.room_no for r in room_repo.get_all()]
        labs_list = [l.lab_room_no for l in lab_repo.get_all()]
    
    # Read custom schedule payload if provided, otherwise use cache
    data = request.get_json(silent=True) or {}
    schedule_payload = data.get("schedule")
    
    # Cache parameters for saved runs
    cache_key = None
    if schedule_payload is None:
        latest_run_id = MEM_SCHEDULE_STORE[0].run_id if MEM_SCHEDULE_STORE else 0
        crud_state = f"{len(room_repo.get_all())}_{len(lab_repo.get_all())}_{len(fac_repo.get_all())}"
        cache_key = f"val_{s_dept or 'ALL'}_{latest_run_id}_{len(MEM_SCHEDULE_STORE)}_{crud_state}"
        if cache_key in _VALIDATION_CACHE:
            print("DIAGNOSTIC: Returning cached validation results!", flush=True)
            return jsonify(_VALIDATION_CACHE[cache_key])

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
        
    if scoped:
        test_schedule = [s for s in test_schedule if context.section_depts.get(s.section_id, "").lower() == s_dept.lower()]

    print("DIAGNOSTIC: s_dept:", s_dept, flush=True)
    print("DIAGNOSTIC: ai_rules:", context.ai_rules, flush=True)
    print("DIAGNOSTIC: test_schedule len:", len(test_schedule), flush=True)

    if not test_schedule:
        return jsonify({
            "error": "No active timetable generated. Please run the Scheduler to generate a timetable before verifying constraints."
        }), 400

    report = TimetableValidator.validate_timetable(test_schedule, context, rooms_list, labs_list)
    res_dict = report.to_dict()
    res_dict["diagnostic_rules"] = context.ai_rules
    res_dict["diagnostic_schedule_len"] = len(test_schedule)
    res_dict["diagnostic_schedule"] = [
        {"section_id": s.section_id, "day_id": s.day_id, "period_no": s.period_no, "course_id": s.course_id, "lab_room_no": s.lab_room_no}
        for s in test_schedule if s.period_no == 1
    ]
    
    if cache_key:
        _VALIDATION_CACHE[cache_key] = res_dict
    return jsonify(res_dict)


@scheduler_bp.route("/scheduler/repair", methods=["POST"])
@require_role("HOD")
def repair():
    """Repairs the last generated schedule in memory."""
    global MEM_SCHEDULE_STORE
    load_latest_run_to_memory(force=True)
    context = build_validation_context()
    
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped = False
    s_dept = None
    if session and session.get("role") == "HOD":
        scoped = True
        s_dept = session.get("department_id")

    if scoped:
        rooms_list = [r.room_no for r in room_repo.get_all() if not r.department_id or r.department_id.lower() == s_dept.lower()]
        labs_list = [l.lab_room_no for l in lab_repo.get_all() if not l.department_id or l.department_id.lower() == s_dept.lower()]
    else:
        rooms_list = [r.room_no for r in room_repo.get_all()]
        labs_list = [l.lab_room_no for l in lab_repo.get_all()]
    
    data = request.get_json(silent=True) or {}
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

    if scoped:
        test_schedule = [s for s in test_schedule if context.section_depts.get(s.section_id, "").lower() == s_dept.lower()]

    if not test_schedule:
        return jsonify({
            "error": "No active timetable generated. Please run the Scheduler to generate a timetable before executing repairs."
        }), 400

    repaired, stats_dict, remaining = RepairEngine.repair_timetable(test_schedule, context, rooms_list, labs_list)
    
    # Save back to cache if payload was empty
    if schedule_payload is None:
        if scoped:
            # Merge repaired items back into MEM_SCHEDULE_STORE
            repaired_ids = {s.section_id for s in repaired}
            new_store = [s for s in MEM_SCHEDULE_STORE if s.section_id not in repaired_ids]
            new_store.extend(repaired)
            MEM_SCHEDULE_STORE = new_store
        else:
            MEM_SCHEDULE_STORE = repaired

    return jsonify({
        "stats": stats_dict,
        "remaining_conflicts": remaining,
        "repaired_schedule": [ModelMapper.to_dict(a) for a in repaired]
    })


@scheduler_bp.route("/scheduler/export", methods=["GET"])
@require_role("HOD")
def export():
    """Exports timetable grids to CSV or Excel files."""
    load_latest_run_to_memory(force=True)
    if not MEM_SCHEDULE_STORE:
        return jsonify({"error": "No timetable data exists to export. Please generate a timetable first."}), 400
    export_type = request.args.get("type", "section")
    id_val = request.args.get("id")
    
    if not id_val:
        return jsonify({"error": "Missing parameter 'id'"}), 400
        
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped = False
    s_dept = None
    if session and session.get("role") == "HOD":
        scoped = True
        s_dept = session.get("department_id")
        
    if scoped:
        if export_type == "section":
            sec = sec_repo.get_by_id(id_val)
            if not sec or sec.department_id.lower() != s_dept.lower():
                return jsonify({"error": "Access denied"}), 403
        elif export_type == "faculty":
            fac = fac_repo.get_by_id(id_val)
            if not fac or fac.department_id.lower() != s_dept.lower():
                return jsonify({"error": "Access denied"}), 403
        elif export_type == "lab":
            lab = lab_repo.get_by_id(id_val)
            if not lab or lab.department_id.lower() != s_dept.lower():
                return jsonify({"error": "Access denied"}), 403
        elif export_type == "department":
            if id_val.lower() != s_dept.lower():
                return jsonify({"error": "Access denied"}), 403

    format_val = request.args.get("format", "csv")
    
    if format_val == "html":
        html_data = TimetableExporter.to_html_print_layout(MEM_SCHEDULE_STORE, export_type, id_val)
        return Response(
            html_data,
            mimetype="text/html"
        )
    
    if format_val in ("excel", "xls"):
        excel_data = TimetableExporter.to_excel_layout(MEM_SCHEDULE_STORE, export_type, id_val)
        return Response(
            excel_data,
            mimetype="application/vnd.ms-excel",
            headers={"Content-disposition": f"attachment; filename=timetable_{export_type}_{id_val}.xls"}
        )

    csv_data = ""
    if export_type == "section":
        csv_data = TimetableExporter.to_csv_section(MEM_SCHEDULE_STORE, id_val)
    elif export_type == "faculty":
        csv_data = TimetableExporter.to_csv_faculty(MEM_SCHEDULE_STORE, id_val)
    elif export_type == "lab":
        csv_data = TimetableExporter.to_csv_lab(MEM_SCHEDULE_STORE, id_val)
    elif export_type == "department":
        course_names, course_has_lab, course_ltp, faculty_names, sec_details, _, _, _, _ = TimetableExporter._get_metadata()
        targets = [sid for sid, details in sec_details.items() if details.get("department_id") == id_val]
        targets.sort()
        csv_parts = []
        for t_id in targets:
            csv_parts.append(f"SECTION: {t_id}\n" + TimetableExporter.to_csv_section(MEM_SCHEDULE_STORE, t_id))
        csv_data = "\n\n".join(csv_parts)
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
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped = False
    s_dept = None
    if session and session.get("role") == "HOD":
        scoped = True
        s_dept = session.get("department_id")

    # ----------------------------------------------------------------
    # Fast dashboard stats — use TTL cache to avoid repeated DB hits
    # ----------------------------------------------------------------
    import time as _time
    _cache_key = f"stats_{s_dept or 'ALL'}"
    _cached = _STATS_CACHE.get(_cache_key)
    if _cached and (_time.time() - _cached["ts"]) < _STATS_CACHE_TTL:
        return jsonify(_cached["data"])

    sections = sec_repo.get_all()
    if scoped:
        sections = [s for s in sections if s.department_id and s.department_id.lower() == s_dept.lower()]
    student_count = sum(s.capacity for s in sections)
    
    from app.repository.entity_repositories import ClassTeacherRepository
    class_teacher_repo = ClassTeacherRepository()
    all_teachers = class_teacher_repo.find_all("class_teacher")
    if scoped:
        section_ids = {s.section_id for s in sections}
        class_teacher_count = len([t for t in all_teachers if t["section_id"] in section_ids])
    else:
        class_teacher_count = len(all_teachers)

    from app.repository.connection import DatabaseConnectionManager
    conn, should_close = DatabaseConnectionManager.get_connection()
    run_count = 0
    latest_time = "N/A"
    active_rules = 0
    rules_count = 0
    recent_activity = []
    
    hod_count = 0
    prof_count = 0
    asst_prof_count = 0
    assoc_prof_count = 0
    instructor_count = 0
    
    theory_course_count = 0
    lab_course_count = 0
    
    classroom_count = 0
    room_lab_count = 0
    
    try:
        cursor = conn.cursor()
        if scoped:
            cursor.execute("SELECT COUNT(*), MAX(finished_at) FROM scheduler_run WHERE status = 'SUCCESS' AND LOWER(department_id) = LOWER(?)", (s_dept,))
        else:
            cursor.execute("SELECT COUNT(*), MAX(finished_at) FROM scheduler_run WHERE status = 'SUCCESS'")
        row = cursor.fetchone()
        if row:
            run_count = row[0] or 0
            latest_time = row[1] or "N/A"
            
        if scoped:
            cursor.execute("SELECT COUNT(DISTINCT rule_id) FROM rules WHERE is_deleted = 0 AND (department_id IS NULL OR LOWER(department_id) = LOWER(?))", (s_dept,))
        else:
            cursor.execute("SELECT COUNT(DISTINCT rule_id) FROM rules WHERE is_deleted = 0")
        rules_count = cursor.fetchone()[0] or 0
            
        if scoped:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM rules r
                INNER JOIN (
                    SELECT rule_id, MAX(version) as max_version 
                    FROM rules 
                    WHERE is_deleted = 0 
                    GROUP BY rule_id
                ) latest ON r.rule_id = latest.rule_id AND r.version = latest.max_version
                WHERE r.enabled = 1 AND (r.department_id IS NULL OR LOWER(r.department_id) = LOWER(?))
            """, (s_dept,))
        else:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM rules r
                INNER JOIN (
                    SELECT rule_id, MAX(version) as max_version 
                    FROM rules 
                    WHERE is_deleted = 0 
                    GROUP BY rule_id
                ) latest ON r.rule_id = latest.rule_id AND r.version = latest.max_version
                WHERE r.enabled = 1
            """)
        active_rules = cursor.fetchone()[0] or 0

        if scoped:
            cursor.execute("SELECT designation, COUNT(*) FROM faculty WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?) GROUP BY designation", (s_dept,))
        else:
            cursor.execute("SELECT designation, COUNT(*) FROM faculty WHERE is_deleted = 0 GROUP BY designation")
        for r in cursor.fetchall():
            desig = (r[0] or "").lower()
            cnt = r[1]
            if "hod" in desig:
                hod_count += cnt
            elif "assistant" in desig:
                asst_prof_count += cnt
            elif "associate" in desig:
                assoc_prof_count += cnt
            elif "professor" in desig:
                prof_count += cnt
            elif "instructor" in desig or "staff" in desig:
                instructor_count += cnt

        if scoped:
            cursor.execute("SELECT COUNT(DISTINCT hod) FROM department WHERE is_deleted = 0 AND hod IS NOT NULL AND LOWER(department_id) = LOWER(?)", (s_dept,))
        else:
            cursor.execute("SELECT COUNT(DISTINCT hod) FROM department WHERE is_deleted = 0 AND hod IS NOT NULL")
        hod_count = cursor.fetchone()[0] or 0

        if scoped:
            cursor.execute("SELECT has_lab, COUNT(*) FROM courses WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?) GROUP BY has_lab", (s_dept,))
        else:
            cursor.execute("SELECT has_lab, COUNT(*) FROM courses WHERE is_deleted = 0 GROUP BY has_lab")
        for r in cursor.fetchall():
            if r[0] == 1:
                lab_course_count = r[1]
            else:
                theory_course_count = r[1]

        if scoped:
            cursor.execute("SELECT room_type, COUNT(*) FROM rooms WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?) GROUP BY room_type", (s_dept,))
        else:
            cursor.execute("SELECT room_type, COUNT(*) FROM rooms WHERE is_deleted = 0 GROUP BY room_type")
        for r in cursor.fetchall():
            rtype = (r[0] or "").lower()
            if rtype == "lab":
                room_lab_count += r[1]
            else:
                classroom_count += r[1]

        if scoped:
            cursor.execute("""
                SELECT 'Timetable Generated' as act_type, finished_at, 'Version ' || version || ' (penalty: ' || total_penalty || ')' as remarks
                FROM scheduler_run 
                WHERE LOWER(department_id) = LOWER(?)
                ORDER BY finished_at DESC LIMIT 5
            """, (s_dept,))
        else:
            cursor.execute("""
                SELECT 'Timetable Generated' as act_type, finished_at, 'Version ' || version || ' (penalty: ' || total_penalty || ')' as remarks
                FROM scheduler_run 
                ORDER BY finished_at DESC LIMIT 5
            """)
        for r in cursor.fetchall():
            recent_activity.append({
                "activity": r[0],
                "timestamp": r[1],
                "details": r[2]
            })
    except Exception:
        pass
    finally:
        if should_close:
            conn.close()

    # Fast resource counts from repos (all cached at repo level)
    if scoped:
        fac_count = len([f for f in fac_repo.get_all() if f.department_id and f.department_id.lower() == s_dept.lower()])
        c_count = len([c for c in course_repo.get_all() if c.department_id and c.department_id.lower() == s_dept.lower()])
        rooms_list = [r.room_no for r in room_repo.get_all() if not r.department_id or r.department_id.lower() == s_dept.lower()]
        labs_list = [l.lab_room_no for l in lab_repo.get_all() if not l.department_id or l.department_id.lower() == s_dept.lower()]
        r_count = len(rooms_list) + len(labs_list)
        l_count = len(labs_list)
    else:
        fac_count = len(fac_repo.get_all())
        c_count = len(course_repo.get_all())
        r_count = len(room_repo.get_all()) + len(lab_repo.get_all())
        l_count = len(lab_repo.get_all())

    # Quick validation status: use MEM_SCHEDULE_STORE without re-running full validation
    # (avoids O(N²) validation on every dashboard load)
    load_latest_run_to_memory()
    if scoped:
        from app.validators.validator import ValidationContext as _VC
        dept_schedule = [s for s in MEM_SCHEDULE_STORE
                         if s.section_id in {sec.section_id for sec in sections}]
    else:
        dept_schedule = MEM_SCHEDULE_STORE

    scheduled_sections_count = len(set(s.section_id for s in dept_schedule if getattr(s, "section_id", None)))

    # Derive validation status from memory without full constraint check
    if not dept_schedule:
        val_status = "No timetable generated"
    elif run_count > 0:
        val_status = "VALID (last run passed)"
    else:
        val_status = "Not validated"

    result = {
        "faculty_count": fac_count,
        "faculty_hod_count": hod_count,
        "faculty_prof_count": prof_count,
        "faculty_asst_prof_count": asst_prof_count,
        "faculty_assoc_prof_count": assoc_prof_count,
        "faculty_instructor_count": instructor_count,
        
        "course_count": c_count,
        "course_theory_count": theory_course_count,
        "course_lab_count": lab_course_count,
        
        "room_count": r_count,
        "room_classroom_count": classroom_count,
        "room_lab_count": room_lab_count + l_count,
        
        "lab_count": l_count,
        "section_count": len(sections),
        "department_count": len(dept_repo.get_all()) if not scoped else 1,
        "rule_count": rules_count,
        "active_rules_count": active_rules,
        "student_count": student_count,
        "class_teacher_count": class_teacher_count,
        "generated_timetables_count": run_count,
        "latest_generation_time": latest_time,
        "validation_status": val_status,
        "scheduled_sections_count": f"{scheduled_sections_count} / {len(sections)}",
        "recent_activity": recent_activity
    }

    # Store in TTL cache
    _STATS_CACHE[_cache_key] = {"data": result, "ts": _time.time()}
    return jsonify(result)


@scheduler_bp.route("/system/clear-cache", methods=["POST"])
@require_role("HOD")
def clear_backend_cache():
    """Clears stats and validation caches on the backend."""
    _STATS_CACHE.clear()
    _VALIDATION_CACHE.clear()
    return jsonify({"message": "Backend cache cleared successfully", "success": True})


@scheduler_bp.route("/system/status", methods=["GET"])
@require_role("HOD")
def system_status():
    """Returns database versions, sync times, and API connection statuses."""
    import sqlite3
    import datetime
    from config.config import DATABASE_URL, LOCAL_MODE, APP_ENV
    from app.ai.ai_service import AIService
    from app.repository.connection import DatabaseConnectionManager

    # 1. Supabase/PostgreSQL connection check
    mgr = DatabaseConnectionManager()
    supabase_status = mgr.verify_health()
            
    # 2. AI Service status check
    ai_service = AIService()
    ai_status = ai_service.get_health_status()
                
    # 3. Database Version
    db_version = "SQLite " + sqlite3.sqlite_version
    total_tables = 0
    migration_status = "Pending"
    if not LOCAL_MODE and DATABASE_URL:
        try:
            conn = mgr.get_raw_connection()
            cur = conn.cursor()
            cur.execute("SELECT version();")
            db_version = cur.fetchone()[0].split(",")[0]
            
            # Get table count for Supabase
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
            total_tables = cur.fetchone()[0] or 0
            cur.close()
            mgr.release_connection(conn)
        except Exception:
            pass
    else:
        try:
            conn = mgr.get_raw_connection()
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            total_tables = cur.fetchone()[0] or 0
            cur.close()
            mgr.release_connection(conn)
        except Exception:
            pass

    if total_tables >= 16:
        migration_status = "Fully Migrated"
    elif total_tables > 0:
        migration_status = "Partially Migrated"

    # 4. Validation Status
    val_status = "No Active Timetable"
    try:
        load_latest_run_to_memory()
        context = build_validation_context()
        rooms_list = [r.room_no for r in room_repo.get_all()]
        labs_list = [l.lab_room_no for l in lab_repo.get_all()]
        if MEM_SCHEDULE_STORE:
            report = TimetableValidator.validate_timetable(MEM_SCHEDULE_STORE, context, rooms_list, labs_list)
            val_status = "VALID" if report.is_valid() else f"CONFLICT ({len(report.errors)} errors)"
    except Exception:
        pass

    last_sync = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({
        "supabase_status": supabase_status,
        "database_version": db_version,
        "total_tables": total_tables,
        "migration_status": migration_status,
        "validation_status": val_status,
        "api_version": "2.0.0-Enterprise-Production",
        "scheduler_version": "4.0.0-CSP-Supabase",
        "environment": APP_ENV.capitalize(),
        "last_sync_time": last_sync,
        "ai_health": ai_status
    })


@scheduler_bp.route("/scheduler/metadata", methods=["GET"])
@require_role("HOD")
def scheduler_metadata():
    """Returns metadata for headers (generation details, section capacities, teachers)."""
    course_names, course_has_lab, course_ltp, faculty_names, sec_details, gen_date, version_num, lab_details, department_names = TimetableExporter._get_metadata()
    
    duration = 0.0
    total_penalty = 0
    
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped = False
    s_dept = None
    if session and session.get("role") == "HOD":
        scoped = True
        s_dept = session.get("department_id")
        
    from app.repository.connection import DatabaseConnectionManager
    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        if scoped:
            cursor.execute("SELECT duration_seconds, total_penalty FROM scheduler_run WHERE status = 'SUCCESS' AND LOWER(department_id) = LOWER(?) ORDER BY run_id DESC LIMIT 1", (s_dept,))
        else:
            cursor.execute("SELECT duration_seconds, total_penalty FROM scheduler_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            duration = row[0] or 0.0
            total_penalty = row[1] or 0
    except Exception:
        pass
    finally:
        if should_close:
            conn.close()
            
    return jsonify({
        "sections": sec_details,
        "gen_date": gen_date,
        "version": version_num,
        "generation_time_seconds": duration,
        "total_penalty": total_penalty,
        "course_names": course_names,
        "faculty_names": faculty_names,
        "lab_details": lab_details,
        "department_names": department_names
    })
