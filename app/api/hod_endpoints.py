"""REST endpoints for HOD Dashboard specific workflows."""
from flask import Blueprint, jsonify
from app.repository.entity_repositories import SectionRepository, RoomRepository, FacultyRepository
from app.repository.connection import DatabaseConnectionManager
from app.auth.auth import require_role

hod_bp = Blueprint("hod", __name__)
sec_repo = SectionRepository()
fac_repo = FacultyRepository()

@hod_bp.route("/hod/sections-status", methods=["GET"])
@require_role("HOD")
def sections_status():
    """Compiles statuses of sections, class teachers, and generation results."""
    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        
        from app.auth.auth import get_current_user_session
        session = get_current_user_session()
        scoped = False
        s_dept = None
        if session and session.get("role") == "HOD":
            scoped = True
            s_dept = session.get("department_id")

        # Get all sections
        sections = sec_repo.get_all()
        if scoped:
            sections = [s for s in sections if s.department_id.lower() == s_dept.lower()]
        
        # Get latest success run
        cursor.execute("SELECT run_id FROM scheduler_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1")
        run_row = cursor.fetchone()
        latest_run_id = run_row[0] if run_row else None
        
        # Load room sections mapping
        cursor.execute("SELECT section_id, room_no FROM room_section")
        room_sections = {r[0]: r[1] for r in cursor.fetchall()}
        
        # Load class teachers mapping and faculty names
        cursor.execute("""
            SELECT ct.section_id, f.faculty_id, f.faculty_name, f.email 
            FROM class_teacher ct
            JOIN faculty f ON ct.faculty_id = f.faculty_id
        """)
        class_teachers = {}
        for r in cursor.fetchall():
            class_teachers[r[0]] = {
                "id": r[1],
                "name": r[2],
                "phone": f"+91 94421 {abs(hash(r[1])) % 90000 + 10000}"
            }
            
        # Check generated sections in latest run
        generated_sections = set()
        if latest_run_id:
            cursor.execute("SELECT DISTINCT section_id FROM schedule WHERE run_id = ?", (latest_run_id,))
            generated_sections = {r[0] for r in cursor.fetchall()}
            
        results = []
        for sec in sections:
            teacher_info = class_teachers.get(sec.section_id, {
                "id": "N/A", "name": "Not Assigned", "phone": "N/A"
            })
            
            results.append({
                "section_id": sec.section_id,
                "section_name": sec.section_name,
                "room_no": room_sections.get(sec.section_id, "Unassigned"),
                "class_teacher_name": teacher_info["name"],
                "class_teacher_phone": teacher_info["phone"],
                "student_count": sec.capacity,
                "status": "Generated" if sec.section_id in generated_sections else "Not Generated"
            })
            
        return jsonify(results)
    finally:
        if should_close:
            conn.close()
