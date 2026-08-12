"""CRUD REST APIs mapping endpoints to the Repository layer with full relationship mapping and enterprise validation."""
import json
from flask import Blueprint, request, jsonify, g
from app.repository.connection import DatabaseConnectionManager
from app.auth.auth import require_role, get_current_user_session
from config.config import LOCAL_MODE, DATABASE_PATH

crud_bp = Blueprint("crud", __name__)

def get_allowed_department_filter(session):
    """Returns (is_scoped, department_id) tuple based on session."""
    if not session:
        return False, None
    if session.get("role") == "SUPER_ADMIN":
        return False, None
    return True, session.get("department_id")

# ============================================================
# Request-scoped SQLite connection (open once per HTTP request,
# reuse across all query_db / execute_db calls, close at teardown)
# This eliminates the per-call sqlite3.connect() / close() overhead
# which was the primary cause of slow API response times.
# ============================================================

def _get_request_conn():
    """Returns the request-scoped DB connection, creating it if needed."""
    if LOCAL_MODE:
        import sqlite3
        if "db_conn" not in g:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            # Performance PRAGMAs — set once per connection
            conn.execute("PRAGMA journal_mode=WAL;")       # concurrent reads while writing
            conn.execute("PRAGMA synchronous=NORMAL;")     # safe but faster than FULL
            conn.execute("PRAGMA cache_size=-32000;")      # 32 MB page cache
            conn.execute("PRAGMA mmap_size=268435456;")    # 256 MB memory-mapped I/O
            conn.execute("PRAGMA temp_store=MEMORY;")      # keep temp tables in RAM
            conn.execute("PRAGMA foreign_keys=ON;")
            g.db_conn = conn
        return g.db_conn, False  # False = do NOT close after query
    else:
        # Postgres: use existing pool manager (no change needed)
        return DatabaseConnectionManager.get_connection()

@crud_bp.teardown_app_request
def _close_request_conn(exc):
    """Closes the request-scoped connection at the end of each request."""
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()

# Helper to run database queries directly
def query_db(query, args=(), one=False):
    conn, should_close = _get_request_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(query, args)
        rv = cursor.fetchall()
        return (dict(rv[0]) if rv else None) if one else [dict(r) for r in rv]
    finally:
        if should_close:
            conn.close()

def execute_db(query, args=()):
    conn, should_close = _get_request_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(query, args)
        conn.commit()
    finally:
        if should_close:
            conn.close()


# ============================================================
# Server-side In-Process TTL Cache
# Since the app talks to remote Supabase over the internet,
# network latency dominates. Caching GET-all responses in
# memory eliminates repeated round-trips for read-heavy pages.
# Cache is scoped by role/dept and invalidated on any write.
# TTL: 60 seconds (matches frontend 5-min cache, but server
# is the actual bottleneck for remote DB connections).
# ============================================================
import time as _time_mod

_SERVER_CACHE: dict = {}
_SERVER_CACHE_TTL = 60  # seconds

def _cache_key(entity: str, scope_dept: str = None) -> str:
    return f"{entity}::{scope_dept or 'ALL'}"

def _get_server_cache(entity: str, scope_dept: str = None):
    key = _cache_key(entity, scope_dept)
    entry = _SERVER_CACHE.get(key)
    if entry and (_time_mod.time() - entry["ts"]) < _SERVER_CACHE_TTL:
        return entry["data"]
    return None

def _set_server_cache(entity: str, data, scope_dept: str = None):
    key = _cache_key(entity, scope_dept)
    _SERVER_CACHE[key] = {"data": data, "ts": _time_mod.time()}

def _invalidate_server_cache(entity: str):
    """Removes all scope variants of an entity from the cache."""
    to_delete = [k for k in _SERVER_CACHE if k.startswith(f"{entity}::")]
    for k in to_delete:
        del _SERVER_CACHE[k]

# ==========================================
# DEPARTMENT ENDPOINTS
# ==========================================

@crud_bp.route("/departments", methods=["GET"])
@require_role("HOD")
def get_departments():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)

    # ── Server-side cache check ───────────────────────────────────────────────
    cached = _get_server_cache("departments", s_dept)
    if cached is not None:
        return jsonify(cached)

    if scoped:
        depts = query_db("SELECT * FROM department WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?)", (s_dept,))
    else:
        depts = query_db("SELECT * FROM department WHERE is_deleted = 0")

    if not depts:
        return jsonify([])

    # ── Bulk-aggregate all counts in 4 queries instead of 6N queries ──────────
    dept_ids = [d["department_id"] for d in depts]
    placeholders = ",".join("?" * len(dept_ids))

    fac_counts = {r["department_id"]: r["cnt"] for r in query_db(
        f"SELECT department_id, COUNT(*) as cnt FROM faculty WHERE is_deleted = 0 AND department_id IN ({placeholders}) GROUP BY department_id",
        dept_ids)}
    course_counts = {r["department_id"]: r["cnt"] for r in query_db(
        f"SELECT department_id, COUNT(*) as cnt FROM courses WHERE is_deleted = 0 AND department_id IN ({placeholders}) GROUP BY department_id",
        dept_ids)}
    section_counts = {r["department_id"]: r["cnt"] for r in query_db(
        f"SELECT department_id, COUNT(*) as cnt FROM sections WHERE is_deleted = 0 AND department_id IN ({placeholders}) GROUP BY department_id",
        dept_ids)}
    room_counts = {r["department_id"]: r["cnt"] for r in query_db(
        f"SELECT department_id, COUNT(*) as cnt FROM rooms WHERE is_deleted = 0 AND department_id IN ({placeholders}) GROUP BY department_id",
        dept_ids)}
    lab_counts = {r["department_id"]: r["cnt"] for r in query_db(
        f"SELECT department_id, COUNT(*) as cnt FROM labs WHERE is_deleted = 0 AND department_id IN ({placeholders}) GROUP BY department_id",
        dept_ids)}
    hod_users = {r["department_id"]: r["username"] for r in query_db(
        f"SELECT department_id, username FROM users WHERE role = 'HOD' AND department_id IN ({placeholders})",
        dept_ids)}

    for d in depts:
        dept_id = d["department_id"]
        d["faculty_count"] = fac_counts.get(dept_id, 0)
        d["course_count"] = course_counts.get(dept_id, 0)
        d["section_count"] = section_counts.get(dept_id, 0)
        d["room_count"] = room_counts.get(dept_id, 0)
        d["lab_count"] = lab_counts.get(dept_id, 0)
        d["hod_username"] = hod_users.get(dept_id, "")
        d["hod_password"] = ""

    _set_server_cache("departments", depts, s_dept)
    return jsonify(depts)


@crud_bp.route("/departments/<id_val>", methods=["GET"])
@require_role("HOD")
def get_department(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    if scoped and id_val.lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403
        
    d = query_db("SELECT * FROM department WHERE LOWER(department_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not d:
        return jsonify({"error": "Department not found"}), 404
        
    dept_id = d["department_id"]
    d["faculty_count"] = query_db("SELECT COUNT(*) as cnt FROM faculty WHERE department_id = ? AND is_deleted = 0", (dept_id,), one=True)["cnt"]
    d["course_count"] = query_db("SELECT COUNT(*) as cnt FROM courses WHERE department_id = ? AND is_deleted = 0", (dept_id,), one=True)["cnt"]
    d["section_count"] = query_db("SELECT COUNT(*) as cnt FROM sections WHERE department_id = ? AND is_deleted = 0", (dept_id,), one=True)["cnt"]
    d["room_count"] = query_db("SELECT COUNT(*) as cnt FROM rooms WHERE department_id = ? AND is_deleted = 0", (dept_id,), one=True)["cnt"]
    d["lab_count"] = query_db("SELECT COUNT(*) as cnt FROM labs WHERE department_id = ? AND is_deleted = 0", (dept_id,), one=True)["cnt"]
    
    # Populate HOD login username
    user_rec = query_db("SELECT username FROM users WHERE department_id = ? AND role = 'HOD' LIMIT 1", (dept_id,), one=True)
    d["hod_username"] = user_rec["username"] if user_rec else ""
    d["hod_password"] = ""
    
    # Related Lists
    d["faculty_members"] = query_db("SELECT faculty_id, faculty_name, designation FROM faculty WHERE department_id = ? AND is_deleted = 0", (dept_id,))
    d["courses"] = query_db("SELECT course_id, course_name, course_type FROM courses WHERE department_id = ? AND is_deleted = 0", (dept_id,))
    d["sections"] = query_db("SELECT section_id, section_name, semester FROM sections WHERE department_id = ? AND is_deleted = 0", (dept_id,))
    d["rooms"] = query_db("SELECT room_no, capacity, room_type FROM rooms WHERE department_id = ? AND is_deleted = 0", (dept_id,))
    d["laboratories"] = query_db("SELECT lab_room_no, lab_name, capacity FROM labs WHERE department_id = ? AND is_deleted = 0", (dept_id,))
    return jsonify(d)

@crud_bp.route("/departments", methods=["POST"])
@require_role("SUPER_ADMIN")
def create_department():
    from werkzeug.security import generate_password_hash
    import secrets
    import string
    data = request.get_json() or {}
    dept_id = data.get("department_id", "").strip()
    dept_name = data.get("department_name", "").strip()
    hod = data.get("hod", "").strip() or None

    if not dept_id or not dept_name:
        return jsonify({"error": "Department ID and Name are required."}), 400

    # Case-insensitive duplicate check for department
    existing = query_db("SELECT * FROM department WHERE LOWER(department_id) = LOWER(?) OR LOWER(department_name) = LOWER(?)", (dept_id, dept_name), one=True)
    if existing:
        return jsonify({"error": "This department already exists."}), 400

    # Automatically generate username and password
    hod_username = f"hod_{dept_id.lower()}"
    
    # Case-insensitive duplicate check for HOD user
    existing_user = query_db("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (hod_username,), one=True)
    if existing_user:
        return jsonify({"error": f"HOD login username '{hod_username}' is already taken."}), 400

    alphabet = string.ascii_letters + string.digits
    hod_password = ''.join(secrets.choice(alphabet) for _ in range(10))
    pwd_hash = generate_password_hash(hod_password)
    
    # Insert both in database
    execute_db("INSERT INTO department (department_id, department_name, hod) VALUES (?, ?, ?)", (dept_id, dept_name, hod_username))
    execute_db("INSERT INTO users (username, password_hash, role, department_id) VALUES (?, ?, 'HOD', ?)", (hod_username, pwd_hash, dept_id))
    
    return jsonify({"message": "Created successfully.", "id": dept_id, "hod_username": hod_username, "hod_password": hod_password}), 201


@crud_bp.route("/departments/<id_val>", methods=["PUT"])
@require_role("SUPER_ADMIN")
def update_department(id_val):
    data = request.get_json() or {}
    dept_name = data.get("department_name", "").strip()
    hod = data.get("hod", "").strip() or None

    if not dept_name:
        return jsonify({"error": "Department name is required."}), 400

    existing_name = query_db("SELECT * FROM department WHERE LOWER(department_name) = LOWER(?) AND LOWER(department_id) != LOWER(?)", (dept_name, id_val), one=True)
    if existing_name:
        return jsonify({"error": "This department name already exists."}), 400

    # Update department
    execute_db("UPDATE department SET department_name = ?, hod = ?, updated_at = CURRENT_TIMESTAMP WHERE LOWER(department_id) = LOWER(?)", (dept_name, hod or f"hod_{id_val.lower()}", id_val))
    
    # Ensure HOD user exists
    hod_username = f"hod_{id_val.lower()}"
    existing_user = query_db("SELECT * FROM users WHERE LOWER(department_id) = LOWER(?) AND role = 'HOD'", (id_val,), one=True)
    if not existing_user:
        from werkzeug.security import generate_password_hash
        pwd_hash = generate_password_hash("hodpassword")
        execute_db("INSERT INTO users (username, password_hash, role, department_id) VALUES (?, ?, 'HOD', ?)", (hod_username, pwd_hash, id_val))

    return jsonify({"message": "Updated successfully"})

@crud_bp.route("/departments/<id_val>", methods=["DELETE"])
@require_role("SUPER_ADMIN")
def delete_department(id_val):
    execute_db("UPDATE department SET is_deleted = 1 WHERE LOWER(department_id) = LOWER(?)", (id_val,))
    return jsonify({"message": "Deleted successfully"})


# ==========================================
# FACULTY ENDPOINTS
# ==========================================

@crud_bp.route("/faculties", methods=["GET"])
@require_role("HOD")
def get_faculties():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)

    cached = _get_server_cache("faculties", s_dept)
    if cached is not None:
        return jsonify(cached)

    if scoped:
        faculties = query_db("SELECT * FROM faculty WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?)", (s_dept,))
    else:
        faculties = query_db("SELECT * FROM faculty WHERE is_deleted = 0")
        
    all_courses = query_db("SELECT faculty_id, course_id FROM faculty_course")
    all_sections = query_db("SELECT DISTINCT faculty_id, section_id FROM faculty_assignment")
    
    from collections import defaultdict
    courses_by_fac = defaultdict(list)
    for row in all_courses:
        courses_by_fac[row["faculty_id"]].append(row["course_id"])
        
    sections_by_fac = defaultdict(list)
    for row in all_sections:
        sections_by_fac[row["faculty_id"]].append(row["section_id"])
        
    for f in faculties:
        fid = f["faculty_id"]
        f["assigned_courses"] = courses_by_fac[fid]
        f["assigned_sections"] = sections_by_fac[fid]

    _set_server_cache("faculties", faculties, s_dept)
    return jsonify(faculties)

@crud_bp.route("/faculties/<id_val>", methods=["GET"])
@require_role("HOD")
def get_faculty(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    f = query_db("SELECT * FROM faculty WHERE LOWER(faculty_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not f:
        return jsonify({"error": "Faculty not found"}), 404
        
    if scoped and f["department_id"] and f["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403
        
    fid = f["faculty_id"]
    assigned_courses = query_db("SELECT course_id FROM faculty_course WHERE faculty_id = ?", (fid,))
    f["assigned_courses"] = [c["course_id"] for c in assigned_courses]
    
    assigned_sections = query_db("SELECT DISTINCT section_id FROM faculty_assignment WHERE faculty_id = ?", (fid,))
    f["assigned_sections"] = [s["section_id"] for s in assigned_sections]
    
    # Lab access lists
    labs = query_db("SELECT DISTINCT l.lab_room_no, l.lab_name FROM labs l JOIN course_lab cl ON l.lab_room_no = cl.lab_room_no JOIN faculty_course fc ON cl.course_id = fc.course_id WHERE fc.faculty_id = ?", (fid,))
    f["lab_access"] = [l["lab_room_no"] for l in labs]
    
    return jsonify(f)

@crud_bp.route("/faculties", methods=["POST"])
@require_role("HOD")
def create_faculty():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    data = request.get_json() or {}
    fid = data.get("faculty_id", "").strip()
    name = data.get("faculty_name", "").strip()
    email = data.get("email", "").strip() or None
    phone = data.get("phone", "").strip() or None
    dept_id = data.get("department_id", "").strip() or None
    if scoped:
        if dept_id and dept_id.lower() != s_dept.lower():
            return jsonify({"error": "Access denied"}), 403
        dept_id = s_dept
    desig = data.get("designation", "").strip() or None
    prof_type = data.get("professor_type", "").strip() or None
    max_h_w = int(data.get("max_hours_week", 30))
    max_h_d = int(data.get("max_hours_daily", 8))
    status = data.get("status", "ACTIVE")
    avail = data.get("availability") or None
    spec = data.get("specialization") or None
    pref_days = data.get("preferred_days") or None
    pref_slots = data.get("preferred_time_slots") or None
    assigned_courses = data.get("assigned_courses", [])

    if not fid or not name:
        return jsonify({"error": "Faculty ID and Name are required."}), 400

    if max_h_w < 0 or max_h_d < 0:
        return jsonify({"error": "Workload hours cannot be negative."}), 400

    # Duplicate check
    existing = query_db("SELECT * FROM faculty WHERE LOWER(faculty_id) = LOWER(?)", (fid,), one=True)
    if existing:
        return jsonify({"error": "This Faculty ID is already registered."}), 400

    execute_db("""
        INSERT INTO faculty (
            faculty_id, faculty_name, max_hours_week, email, status, phone, designation, 
            max_hours_daily, department_id, professor_type, availability, specialization, 
            preferred_days, preferred_time_slots
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (fid, name, max_h_w, email, status, phone, desig, max_h_d, dept_id, prof_type, avail, spec, pref_days, pref_slots))

    # Link Department if set
    if dept_id:
        execute_db("DELETE FROM department_faculty WHERE faculty_id = ?", (fid,))
        execute_db("INSERT INTO department_faculty(department_id, faculty_id) VALUES (?, ?)", (dept_id, fid))

    # Save multi-select courses
    execute_db("DELETE FROM faculty_course WHERE faculty_id = ?", (fid,))
    for cid in assigned_courses:
        execute_db("INSERT INTO faculty_course (faculty_id, course_id) VALUES (?, ?)", (fid, cid))

    return jsonify({"message": "Created successfully", "id": fid}), 201

@crud_bp.route("/faculties/<id_val>", methods=["PUT"])
@require_role("HOD")
def update_faculty(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    f = query_db("SELECT * FROM faculty WHERE LOWER(faculty_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not f:
        return jsonify({"error": "Faculty not found"}), 404
        
    if scoped and f["department_id"] and f["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json() or {}
    name = data.get("faculty_name", "").strip()
    email = data.get("email", "").strip() or None
    phone = data.get("phone", "").strip() or None
    dept_id = data.get("department_id", "").strip() or None
    if scoped:
        dept_id = s_dept
    desig = data.get("designation", "").strip() or None
    prof_type = data.get("professor_type", "").strip() or None
    max_h_w = int(data.get("max_hours_week", 30))
    max_h_d = int(data.get("max_hours_daily", 8))
    status = data.get("status", "ACTIVE")
    avail = data.get("availability") or None
    spec = data.get("specialization") or None
    pref_days = data.get("preferred_days") or None
    pref_slots = data.get("preferred_time_slots") or None
    assigned_courses = data.get("assigned_courses", [])

    if not name:
        return jsonify({"error": "Faculty name is required."}), 400

    if max_h_w < 0 or max_h_d < 0:
        return jsonify({"error": "Workload hours cannot be negative."}), 400

    execute_db("""
        UPDATE faculty SET 
            faculty_name = ?, max_hours_week = ?, email = ?, status = ?, phone = ?, 
            designation = ?, max_hours_daily = ?, department_id = ?, professor_type = ?, 
            availability = ?, specialization = ?, preferred_days = ?, preferred_time_slots = ?, 
            updated_at = CURRENT_TIMESTAMP
        WHERE LOWER(faculty_id) = LOWER(?)
    """, (name, max_h_w, email, status, phone, desig, max_h_d, dept_id, prof_type, avail, spec, pref_days, pref_slots, id_val))

    # Sync Department
    if dept_id:
        execute_db("DELETE FROM department_faculty WHERE LOWER(faculty_id) = LOWER(?)", (id_val,))
        execute_db("INSERT INTO department_faculty(department_id, faculty_id) VALUES (?, ?)", (dept_id, id_val))

    # Sync courses
    execute_db("DELETE FROM faculty_course WHERE LOWER(faculty_id) = LOWER(?)", (id_val,))
    for cid in assigned_courses:
        execute_db("INSERT INTO faculty_course (faculty_id, course_id) VALUES (?, ?)", (id_val, cid))

    return jsonify({"message": "Updated successfully"})

@crud_bp.route("/faculties/<id_val>", methods=["DELETE"])
@require_role("HOD")
def delete_faculty(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    f = query_db("SELECT * FROM faculty WHERE LOWER(faculty_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not f:
        return jsonify({"error": "Faculty not found"}), 404
        
    if scoped and f["department_id"] and f["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    execute_db("UPDATE faculty SET is_deleted = 1 WHERE LOWER(faculty_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM department_faculty WHERE LOWER(faculty_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM faculty_course WHERE LOWER(faculty_id) = LOWER(?)", (id_val,))
    _invalidate_server_cache("faculties")
    _invalidate_server_cache("courses")  # faculty links courses
    return jsonify({"message": "Deleted successfully"})


# ==========================================
# COURSE ENDPOINTS
# ==========================================

@crud_bp.route("/courses", methods=["GET"])
@require_role("HOD")
def get_courses():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)

    cached = _get_server_cache("courses", s_dept)
    if cached is not None:
        return jsonify(cached)

    if scoped:
        courses = query_db("SELECT * FROM courses WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?)", (s_dept,))
    else:
        courses = query_db("SELECT * FROM courses WHERE is_deleted = 0")
        
    all_teachers = query_db("SELECT faculty_id, course_id FROM faculty_course")
    all_sections = query_db("SELECT section_id, course_id FROM section_course")
    
    from collections import defaultdict
    teachers_by_course = defaultdict(list)
    for row in all_teachers:
        teachers_by_course[row["course_id"]].append(row["faculty_id"])
        
    sections_by_course = defaultdict(list)
    for row in all_sections:
        sections_by_course[row["course_id"]].append(row["section_id"])
        
    for c in courses:
        cid = c["course_id"]
        c["assigned_faculty"] = teachers_by_course[cid]
        c["assigned_sections"] = sections_by_course[cid]

    _set_server_cache("courses", courses, s_dept)
    return jsonify(courses)

@crud_bp.route("/courses/<id_val>", methods=["GET"])
@require_role("HOD")
def get_course(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    c = query_db("SELECT * FROM courses WHERE LOWER(course_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not c:
        return jsonify({"error": "Course not found"}), 404
        
    if scoped and c["department_id"] and c["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403
        
    cid = c["course_id"]
    teachers = query_db("SELECT fc.faculty_id, f.faculty_name FROM faculty_course fc JOIN faculty f ON fc.faculty_id = f.faculty_id WHERE fc.course_id = ? AND f.is_deleted = 0", (cid,))
    c["assigned_faculty"] = [t["faculty_id"] for t in teachers]
    c["faculty_list"] = teachers
    
    sections = query_db("SELECT sc.section_id, s.section_name FROM section_course sc JOIN sections s ON sc.section_id = s.section_id WHERE sc.course_id = ? AND s.is_deleted = 0", (cid,))
    c["assigned_sections"] = [s["section_id"] for s in sections]
    c["sections_list"] = sections
    
    # Required Lab info
    lab = query_db("SELECT lab_room_no, lab_name FROM labs WHERE lab_room_no = (SELECT lab_room_no FROM course_lab WHERE course_id = ? LIMIT 1)", (cid,), one=True)
    c["required_lab"] = lab["lab_room_no"] if lab else None
    
    return jsonify(c)

@crud_bp.route("/courses", methods=["POST"])
@require_role("HOD")
def create_course():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    data = request.get_json() or {}
    cid = data.get("course_id", "").strip()
    name = data.get("course_name", "").strip()
    difficulty = int(data.get("difficulty", 1))
    semester = int(data.get("semester", 1))
    has_lab = int(data.get("has_lab", 0))
    weekly_hours = int(data.get("weekly_hours", 4))
    
    dept_id = data.get("department_id", "").strip() or None
    if scoped:
        if dept_id and dept_id.lower() != s_dept.lower():
            return jsonify({"error": "Access denied"}), 403
        dept_id = s_dept
    credits = int(data.get("credits", 3))
    theory_hours = int(data.get("theory_hours", 3))
    lab_hours = int(data.get("lab_hours", 0))
    course_type = data.get("course_type", "CORE")
    req_lab = data.get("required_laboratory", "").strip() or None
    color = data.get("course_color", "").strip() or None
    
    l = int(data.get("l", 0))
    t = int(data.get("t", 0))
    p = int(data.get("p", 0))
    if l == 0 and t == 0 and p == 0:
        l = theory_hours
        t = 0
        p = lab_hours
    
    assigned_faculty = data.get("assigned_faculty", [])
    assigned_sections = data.get("assigned_sections", [])

    if not cid or not name:
        return jsonify({"error": "Course Code and Name are required."}), 400

    if semester <= 0:
        return jsonify({"error": "This Semester value is invalid."}), 400

    if credits < 0 or weekly_hours < 0 or theory_hours < 0 or lab_hours < 0:
        return jsonify({"error": "Course credits and hours cannot be negative."}), 400

    # Duplicate check
    existing = query_db("SELECT * FROM courses WHERE LOWER(course_id) = LOWER(?)", (cid,), one=True)
    if existing:
        return jsonify({"error": "This Course Code is already registered."}), 400

    execute_db("""
        INSERT INTO courses (
            course_id, course_name, l, t, p, c, difficulty, semester, has_lab, weekly_hours,
            department_id, credits, theory_hours, lab_hours, course_type, required_laboratory, course_color
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cid, name, l, t, p, credits, difficulty, semester, has_lab, weekly_hours, dept_id, credits, theory_hours, lab_hours, course_type, req_lab, color))

    # Mappings
    if dept_id:
        execute_db("DELETE FROM department_course WHERE course_id = ?", (cid,))
        execute_db("INSERT INTO department_course(department_id, course_id) VALUES (?, ?)", (dept_id, cid))

    if req_lab:
        execute_db("DELETE FROM course_lab WHERE course_id = ?", (cid,))
        execute_db("INSERT INTO course_lab(course_id, lab_room_no) VALUES (?, ?)", (cid, req_lab))

    # Sync many-to-many
    execute_db("DELETE FROM faculty_course WHERE course_id = ?", (cid,))
    for fid in assigned_faculty:
        execute_db("INSERT INTO faculty_course (faculty_id, course_id) VALUES (?, ?)", (fid, cid))

    execute_db("DELETE FROM section_course WHERE course_id = ?", (cid,))
    for sid in assigned_sections:
        execute_db("INSERT INTO section_course (section_id, course_id) VALUES (?, ?)", (sid, cid))

    return jsonify({"message": "Created successfully", "id": cid}), 201

@crud_bp.route("/courses/<id_val>", methods=["PUT"])
@require_role("HOD")
def update_course(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    c = query_db("SELECT * FROM courses WHERE LOWER(course_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not c:
        return jsonify({"error": "Course not found"}), 404
        
    if scoped and c["department_id"] and c["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json() or {}
    name = data.get("course_name", "").strip()
    difficulty = int(data.get("difficulty", 1))
    semester = int(data.get("semester", 1))
    has_lab = int(data.get("has_lab", 0))
    weekly_hours = int(data.get("weekly_hours", 4))
    
    dept_id = data.get("department_id", "").strip() or None
    if scoped:
        dept_id = s_dept
    credits = int(data.get("credits", 3))
    theory_hours = int(data.get("theory_hours", 3))
    lab_hours = int(data.get("lab_hours", 0))
    course_type = data.get("course_type", "CORE")
    req_lab = data.get("required_laboratory", "").strip() or None
    color = data.get("course_color", "").strip() or None
    
    l = int(data.get("l", 0))
    t = int(data.get("t", 0))
    p = int(data.get("p", 0))
    if l == 0 and t == 0 and p == 0:
        l = theory_hours
        t = 0
        p = lab_hours
    
    assigned_faculty = data.get("assigned_faculty", [])
    assigned_sections = data.get("assigned_sections", [])

    if not name:
        return jsonify({"error": "Course name is required."}), 400

    if semester <= 0:
        return jsonify({"error": "This Semester value is invalid."}), 400

    if credits < 0 or weekly_hours < 0 or theory_hours < 0 or lab_hours < 0:
        return jsonify({"error": "Course credits and hours cannot be negative."}), 400

    execute_db("""
        UPDATE courses SET 
            course_name = ?, l = ?, t = ?, p = ?, c = ?, difficulty = ?, semester = ?, has_lab = ?, weekly_hours = ?,
            department_id = ?, credits = ?, theory_hours = ?, lab_hours = ?, course_type = ?, required_laboratory = ?, 
            course_color = ?, updated_at = CURRENT_TIMESTAMP
        WHERE LOWER(course_id) = LOWER(?)
    """, (name, l, t, p, credits, difficulty, semester, has_lab, weekly_hours, dept_id, credits, theory_hours, lab_hours, course_type, req_lab, color, id_val))

    # Sync
    if dept_id:
        execute_db("DELETE FROM department_course WHERE LOWER(course_id) = LOWER(?)", (id_val,))
        execute_db("INSERT INTO department_course(department_id, course_id) VALUES (?, ?)", (dept_id, id_val))

    if req_lab:
        execute_db("DELETE FROM course_lab WHERE LOWER(course_id) = LOWER(?)", (id_val,))
        execute_db("INSERT INTO course_lab(course_id, lab_room_no) VALUES (?, ?)", (id_val, req_lab))

    execute_db("DELETE FROM faculty_course WHERE LOWER(course_id) = LOWER(?)", (id_val,))
    for fid in assigned_faculty:
        execute_db("INSERT INTO faculty_course (faculty_id, course_id) VALUES (?, ?)", (fid, id_val))

    execute_db("DELETE FROM section_course WHERE LOWER(course_id) = LOWER(?)", (id_val,))
    for sid in assigned_sections:
        execute_db("INSERT INTO section_course (section_id, course_id) VALUES (?, ?)", (sid, id_val))

    _invalidate_server_cache("courses")
    _invalidate_server_cache("faculties")  # course-faculty links changed
    _invalidate_server_cache("sections")   # course-section links changed
    return jsonify({"message": "Updated successfully"})

@crud_bp.route("/courses/<id_val>", methods=["DELETE"])
@require_role("HOD")
def delete_course(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    c = query_db("SELECT * FROM courses WHERE LOWER(course_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not c:
        return jsonify({"error": "Course not found"}), 404
        
    if scoped and c["department_id"] and c["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    execute_db("UPDATE courses SET is_deleted = 1 WHERE LOWER(course_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM department_course WHERE LOWER(course_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM course_lab WHERE LOWER(course_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM faculty_course WHERE LOWER(course_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM section_course WHERE LOWER(course_id) = LOWER(?)", (id_val,))
    _invalidate_server_cache("courses")
    _invalidate_server_cache("faculties")
    _invalidate_server_cache("sections")
    return jsonify({"message": "Deleted successfully"})


# ==========================================
# SECTION ENDPOINTS
# ==========================================

@crud_bp.route("/sections", methods=["GET"])
@require_role("HOD")
def get_sections():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)

    cached = _get_server_cache("sections", s_dept)
    if cached is not None:
        return jsonify(cached)

    if scoped:
        sections = query_db("SELECT * FROM sections WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?)", (s_dept,))
    else:
        sections = query_db("SELECT * FROM sections WHERE is_deleted = 0")
        
    all_rooms = query_db("SELECT section_id, room_no FROM room_section")
    all_teachers = query_db("SELECT section_id, faculty_id FROM class_teacher")
    all_courses = query_db("SELECT section_id, course_id FROM section_course")
    
    rooms_by_sec = {row["section_id"]: row["room_no"] for row in all_rooms}
    teachers_by_sec = {row["section_id"]: row["faculty_id"] for row in all_teachers}
    
    from collections import defaultdict
    courses_by_sec = defaultdict(list)
    for row in all_courses:
        courses_by_sec[row["section_id"]].append(row["course_id"])
        
    for s in sections:
        sid = s["section_id"]
        s["classroom"] = rooms_by_sec.get(sid, "")
        s["classroom_id"] = s["classroom"]
        s["class_teacher"] = teachers_by_sec.get(sid, "")
        s["class_teacher_id"] = s["class_teacher"]
        s["assigned_courses"] = courses_by_sec[sid]

    _set_server_cache("sections", sections, s_dept)
    return jsonify(sections)

@crud_bp.route("/sections/<id_val>", methods=["GET"])
@require_role("HOD")
def get_section(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    s = query_db("SELECT * FROM sections WHERE LOWER(section_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not s:
        return jsonify({"error": "Section not found"}), 404
        
    if scoped and s["department_id"] and s["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403
        
    sid = s["section_id"]
    rs = query_db("SELECT room_no FROM room_section WHERE section_id = ?", (sid,), one=True)
    s["classroom"] = rs["room_no"] if rs else ""
    s["classroom_id"] = s["classroom"]
    
    ct = query_db("SELECT faculty_id FROM class_teacher WHERE section_id = ?", (sid,), one=True)
    s["class_teacher"] = ct["faculty_id"] if ct else ""
    s["class_teacher_id"] = s["class_teacher"]
    
    # List of Assigned courses with Faculty details
    courses = query_db("""
        SELECT sc.course_id, c.course_name, fa.faculty_id, f.faculty_name, c.has_lab 
        FROM section_course sc 
        JOIN courses c ON sc.course_id = c.course_id 
        LEFT JOIN faculty_assignment fa ON fa.section_id = sc.section_id AND fa.course_id = sc.course_id
        LEFT JOIN faculty f ON fa.faculty_id = f.faculty_id
        WHERE sc.section_id = ? AND c.is_deleted = 0
    """, (sid,))
    s["courses_list"] = courses
    s["assigned_courses"] = [c["course_id"] for c in courses]
    
    # Class teacher details
    if s["class_teacher"]:
        teacher_info = query_db("SELECT faculty_name, email FROM faculty WHERE faculty_id = ?", (s["class_teacher"],), one=True)
        s["class_teacher_details"] = teacher_info
        
    # Get associated laboratory rooms
    labs = query_db("SELECT DISTINCT cl.lab_room_no, l.lab_name FROM course_lab cl JOIN labs l ON cl.lab_room_no = l.lab_room_no JOIN section_course sc ON cl.course_id = sc.course_id WHERE sc.section_id = ?", (sid,))
    s["labs_list"] = labs
    
    # Get last generated timetable allocation for this section
    timetable = query_db("""
        SELECT s.day_id, s.period_no, s.course_id, c.course_name, s.faculty_id, f.faculty_name, s.room_no, s.lab_room_no 
        FROM schedule s 
        JOIN courses c ON s.course_id = c.course_id 
        JOIN faculty f ON s.faculty_id = f.faculty_id 
        WHERE s.section_id = ? AND s.run_id = (SELECT run_id FROM scheduler_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1)
    """, (sid,))
    s["timetable"] = timetable

    return jsonify(s)

@crud_bp.route("/sections", methods=["POST"])
@require_role("HOD")
def create_section():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    data = request.get_json() or {}
    sid = data.get("section_id", "").strip()
    name = data.get("section_name", "").strip()
    semester = int(data.get("semester", 1))
    dept_id = data.get("department_id", "").strip()
    if scoped:
        if dept_id and dept_id.lower() != s_dept.lower():
            return jsonify({"error": "Access denied"}), 403
        dept_id = s_dept
    capacity = int(data.get("capacity", 60))
    strength = int(data.get("strength", 60))
    classroom = data.get("classroom_id", "").strip() or None
    class_teacher = data.get("class_teacher_id", "").strip() or None
    assigned_courses = data.get("assigned_courses", [])

    if not sid or not name or not dept_id:
        return jsonify({"error": "Section ID, Name and Department are required."}), 400

    if semester <= 0:
        return jsonify({"error": "This Semester value is invalid."}), 400

    if capacity <= 0 or strength <= 0:
        return jsonify({"error": "Capacity and strength must be greater than zero."}), 400

    # Duplicate check
    existing = query_db("SELECT * FROM sections WHERE LOWER(section_id) = LOWER(?)", (sid,), one=True)
    if existing:
        return jsonify({"error": "This Section already exists."}), 400

    execute_db("""
        INSERT INTO sections (
            section_id, section_name, semester, department_id, capacity, strength, class_teacher_id, classroom_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (sid, name, semester, dept_id, capacity, strength, class_teacher, classroom))

    # Room section link
    if classroom:
        execute_db("DELETE FROM room_section WHERE section_id = ?", (sid,))
        execute_db("INSERT INTO room_section(room_no, section_id) VALUES (?, ?)", (classroom, sid))

    # Class teacher link
    if class_teacher:
        execute_db("DELETE FROM class_teacher WHERE section_id = ?", (sid,))
        execute_db("INSERT INTO class_teacher(section_id, faculty_id) VALUES (?, ?)", (sid, class_teacher))

    # Sync many-to-many courses
    execute_db("DELETE FROM section_course WHERE section_id = ?", (sid,))
    for cid in assigned_courses:
        execute_db("INSERT INTO section_course(section_id, course_id) VALUES (?, ?)", (sid, cid))

    return jsonify({"message": "Created successfully", "id": sid}), 201

@crud_bp.route("/sections/<id_val>", methods=["PUT"])
@require_role("HOD")
def update_section(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    s = query_db("SELECT * FROM sections WHERE LOWER(section_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not s:
        return jsonify({"error": "Section not found"}), 404
        
    if scoped and s["department_id"] and s["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json() or {}
    name = data.get("section_name", "").strip()
    semester = int(data.get("semester", 1))
    dept_id = data.get("department_id", "").strip()
    if scoped:
        dept_id = s_dept
    capacity = int(data.get("capacity", 60))
    strength = int(data.get("strength", 60))
    classroom = data.get("classroom_id", "").strip() or None
    class_teacher = data.get("class_teacher_id", "").strip() or None
    assigned_courses = data.get("assigned_courses", [])

    if not name or not dept_id:
        return jsonify({"error": "Section Name and Department are required."}), 400

    if semester <= 0:
        return jsonify({"error": "This Semester value is invalid."}), 400

    if capacity <= 0 or strength <= 0:
        return jsonify({"error": "Capacity and strength must be greater than zero."}), 400

    execute_db("""
        UPDATE sections SET 
            section_name = ?, semester = ?, department_id = ?, capacity = ?, strength = ?, 
            class_teacher_id = ?, classroom_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE LOWER(section_id) = LOWER(?)
    """, (name, semester, dept_id, capacity, strength, class_teacher, classroom, id_val))

    # Sync Room link
    execute_db("DELETE FROM room_section WHERE LOWER(section_id) = LOWER(?)", (id_val,))
    if classroom:
        execute_db("INSERT INTO room_section(room_no, section_id) VALUES (?, ?)", (classroom, id_val))

    # Sync Teacher link
    execute_db("DELETE FROM class_teacher WHERE LOWER(section_id) = LOWER(?)", (id_val,))
    if class_teacher:
        execute_db("INSERT INTO class_teacher(section_id, faculty_id) VALUES (?, ?)", (id_val, class_teacher))

    # Sync many-to-many courses
    execute_db("DELETE FROM section_course WHERE LOWER(section_id) = LOWER(?)", (id_val,))
    for cid in assigned_courses:
        execute_db("INSERT INTO section_course(section_id, course_id) VALUES (?, ?)", (id_val, cid))

    _invalidate_server_cache("sections")
    _invalidate_server_cache("courses")  # section-course links changed
    return jsonify({"message": "Updated successfully"})

@crud_bp.route("/sections/<id_val>", methods=["DELETE"])
@require_role("HOD")
def delete_section(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    s = query_db("SELECT * FROM sections WHERE LOWER(section_id) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not s:
        return jsonify({"error": "Section not found"}), 404
        
    if scoped and s["department_id"] and s["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    execute_db("UPDATE sections SET is_deleted = 1 WHERE LOWER(section_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM room_section WHERE LOWER(section_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM class_teacher WHERE LOWER(section_id) = LOWER(?)", (id_val,))
    execute_db("DELETE FROM section_course WHERE LOWER(section_id) = LOWER(?)", (id_val,))
    _invalidate_server_cache("sections")
    _invalidate_server_cache("courses")
    return jsonify({"message": "Deleted successfully"})


# ==========================================
# ROOMS ENDPOINTS
# ==========================================

@crud_bp.route("/rooms", methods=["GET"])
@require_role("HOD")
def get_rooms():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)

    cached = _get_server_cache("rooms", s_dept)
    if cached is not None:
        return jsonify(cached)

    if scoped:
        data = query_db("SELECT * FROM rooms WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?)", (s_dept,))
    else:
        data = query_db("SELECT * FROM rooms WHERE is_deleted = 0")
    _set_server_cache("rooms", data, s_dept)
    return jsonify(data)

@crud_bp.route("/rooms/<id_val>", methods=["GET"])
@require_role("HOD")
def get_room(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    r = query_db("SELECT * FROM rooms WHERE LOWER(room_no) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not r:
        return jsonify({"error": "Room not found"}), 404
        
    if scoped and r["department_id"] and r["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403
        
    # Get assigned sections
    r["assigned_sections"] = query_db("SELECT section_id FROM room_section WHERE room_no = ?", (r["room_no"],))
    return jsonify(r)

@crud_bp.route("/rooms", methods=["POST"])
@require_role("HOD")
def create_room():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    data = request.get_json() or {}
    room_no = data.get("room_no", "").strip()
    dept_id = data.get("department_id", "").strip()
    if scoped:
        if dept_id and dept_id.lower() != s_dept.lower():
            return jsonify({"error": "Access denied"}), 403
        dept_id = s_dept
    capacity = int(data.get("capacity", 0))
    room_type = data.get("room_type", "SMART")
    avail = data.get("availability") or None

    if not room_no or not dept_id:
        return jsonify({"error": "Room number and Department are required."}), 400

    if capacity <= 0:
        return jsonify({"error": "Capacity must be greater than zero."}), 400

    # Duplicate check
    existing = query_db("SELECT * FROM rooms WHERE LOWER(room_no) = LOWER(?)", (room_no,), one=True)
    if existing:
        return jsonify({"error": "This Room is already assigned."}), 400

    execute_db("INSERT INTO rooms (room_no, department_id, capacity, room_type, availability) VALUES (?, ?, ?, ?, ?)", (room_no, dept_id, capacity, room_type, avail))
    _invalidate_server_cache("rooms")
    _invalidate_server_cache("departments")  # dept room count changes
    return jsonify({"message": "Created successfully", "id": room_no}), 201

@crud_bp.route("/rooms/<id_val>", methods=["PUT"])
@require_role("HOD")
def update_room(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    r = query_db("SELECT * FROM rooms WHERE LOWER(room_no) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not r:
        return jsonify({"error": "Room not found"}), 404
        
    if scoped and r["department_id"] and r["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json() or {}
    dept_id = data.get("department_id", "").strip()
    if scoped:
        dept_id = s_dept
    capacity = int(data.get("capacity", 0))
    room_type = data.get("room_type", "SMART")
    avail = data.get("availability") or None

    if not dept_id:
        return jsonify({"error": "Department is required."}), 400

    if capacity <= 0:
        return jsonify({"error": "Capacity must be greater than zero."}), 400

    execute_db("UPDATE rooms SET department_id = ?, capacity = ?, room_type = ?, availability = ?, updated_at = CURRENT_TIMESTAMP WHERE LOWER(room_no) = LOWER(?)", (dept_id, capacity, room_type, avail, id_val))
    return jsonify({"message": "Updated successfully"})

@crud_bp.route("/rooms/<id_val>", methods=["DELETE"])
@require_role("HOD")
def delete_room(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    r = query_db("SELECT * FROM rooms WHERE LOWER(room_no) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not r:
        return jsonify({"error": "Room not found"}), 404
        
    if scoped and r["department_id"] and r["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    execute_db("UPDATE rooms SET is_deleted = 1 WHERE LOWER(room_no) = LOWER(?)", (id_val,))
    return jsonify({"message": "Deleted successfully"})


# ==========================================
# LABORATORIES ENDPOINTS
# ==========================================

@crud_bp.route("/laboratories", methods=["GET"])
@require_role("HOD")
def get_laboratories():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    if scoped:
        return jsonify(query_db("SELECT * FROM labs WHERE is_deleted = 0 AND LOWER(department_id) = LOWER(?)", (s_dept,)))
    else:
        return jsonify(query_db("SELECT * FROM labs WHERE is_deleted = 0"))

@crud_bp.route("/laboratories/<id_val>", methods=["GET"])
@require_role("HOD")
def get_laboratory(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    l = query_db("SELECT * FROM labs WHERE LOWER(lab_room_no) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not l:
        return jsonify({"error": "Laboratory not found"}), 404
        
    if scoped and l["department_id"] and l["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403
        
    lab_no = l["lab_room_no"]
    
    # Courses using this Lab
    courses = query_db("SELECT c.course_id, c.course_name FROM course_lab cl JOIN courses c ON cl.course_id = c.course_id WHERE cl.lab_room_no = ? AND c.is_deleted = 0", (lab_no,))
    l["courses_using"] = courses
    
    # Faculty using this Lab
    faculty = query_db("SELECT DISTINCT f.faculty_id, f.faculty_name FROM faculty_course fc JOIN faculty f ON fc.faculty_id = f.faculty_id JOIN course_lab cl ON fc.course_id = cl.course_id WHERE cl.lab_room_no = ? AND f.is_deleted = 0", (lab_no,))
    l["faculty_using"] = faculty
    
    # Allocated Timetable
    timetable = query_db("""
        SELECT s.day_id, s.period_no, s.section_id, s.course_id, c.course_name, s.faculty_id, f.faculty_name 
        FROM schedule s 
        JOIN courses c ON s.course_id = c.course_id 
        JOIN faculty f ON s.faculty_id = f.faculty_id 
        WHERE s.lab_room_no = ? AND s.run_id = (SELECT run_id FROM scheduler_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1)
    """, (lab_no,))
    l["timetable"] = timetable

    return jsonify(l)

@crud_bp.route("/laboratories", methods=["POST"])
@require_role("HOD")
def create_laboratory():
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    data = request.get_json() or {}
    lab_no = data.get("lab_room_no", "").strip()
    dept_id = data.get("department_id", "").strip()
    if scoped:
        if dept_id and dept_id.lower() != s_dept.lower():
            return jsonify({"error": "Access denied"}), 403
        dept_id = s_dept
    name = data.get("lab_name", "").strip()
    capacity = int(data.get("capacity", 0))
    incharge = data.get("lab_incharge_id", "").strip() or None
    equip = data.get("equipment", "").strip() or None
    avail = data.get("availability") or None

    if not lab_no or not dept_id or not name:
        return jsonify({"error": "Lab ID, Name and Department are required."}), 400

    if capacity <= 0:
        return jsonify({"error": "Capacity must be greater than zero."}), 400

    # Duplicate check
    existing = query_db("SELECT * FROM labs WHERE LOWER(lab_room_no) = LOWER(?)", (lab_no,), one=True)
    if existing:
        return jsonify({"error": "This Laboratory already exists."}), 400

    execute_db("""
        INSERT INTO labs (lab_room_no, department_id, lab_name, capacity, lab_incharge_id, equipment, availability) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (lab_no, dept_id, name, capacity, incharge, equip, avail))
    return jsonify({"message": "Created successfully", "id": lab_no}), 201

@crud_bp.route("/laboratories/<id_val>", methods=["PUT"])
@require_role("HOD")
def update_laboratory(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    l = query_db("SELECT * FROM labs WHERE LOWER(lab_room_no) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not l:
        return jsonify({"error": "Laboratory not found"}), 404
        
    if scoped and l["department_id"] and l["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json() or {}
    dept_id = data.get("department_id", "").strip()
    if scoped:
        dept_id = s_dept
    name = data.get("lab_name", "").strip()
    capacity = int(data.get("capacity", 0))
    incharge = data.get("lab_incharge_id", "").strip() or None
    equip = data.get("equipment", "").strip() or None
    avail = data.get("availability") or None

    if not dept_id or not name:
        return jsonify({"error": "Name and Department are required."}), 400

    if capacity <= 0:
        return jsonify({"error": "Capacity must be greater than zero."}), 400

    execute_db("""
        UPDATE labs SET department_id = ?, lab_name = ?, capacity = ?, lab_incharge_id = ?, equipment = ?, availability = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE LOWER(lab_room_no) = LOWER(?)
    """, (dept_id, name, capacity, incharge, equip, avail, id_val))
    return jsonify({"message": "Updated successfully"})

@crud_bp.route("/laboratories/<id_val>", methods=["DELETE"])
@require_role("HOD")
def delete_laboratory(id_val):
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    l = query_db("SELECT * FROM labs WHERE LOWER(lab_room_no) = LOWER(?) AND is_deleted = 0", (id_val,), one=True)
    if not l:
        return jsonify({"error": "Laboratory not found"}), 404
        
    if scoped and l["department_id"] and l["department_id"].lower() != s_dept.lower():
        return jsonify({"error": "Access denied"}), 403

    execute_db("UPDATE labs SET is_deleted = 1 WHERE LOWER(lab_room_no) = LOWER(?)", (id_val,))
    return jsonify({"message": "Deleted successfully"})

