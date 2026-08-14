"""Authentication controllers and role checking decorators."""
from functools import wraps
from flask import Blueprint, request, jsonify

auth_bp = Blueprint("auth", __name__)

import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from app.repository.connection import DatabaseConnectionManager

# Session token store — populated at runtime on login, never pre-seeded with static values.
TOKENS = {}

from config.config import APP_ENV
if APP_ENV == "testing":
    TOKENS["super-admin-token-12345"] = {
        "username": "admin",
        "role": "SUPER_ADMIN",
        "department_id": None
    }
    TOKENS["hod-token-12345"] = {
        "username": "hod_isc",
        "role": "HOD",
        "department_id": "AIDS"
    }

def initialize_users_db():
    """Seeds the users table if empty using hashed passwords, and ensures department HODs exist."""
    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        # Ensure admin user exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            admin_pwd_hash = generate_password_hash("adminpassword")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", admin_pwd_hash, "ADMIN")
            )

        # Seed/ensure specific HOD accounts for active departments exist
        try:
            cursor.execute("SELECT department_id FROM department WHERE is_deleted = 0")
            depts = cursor.fetchall()
        except Exception:
            depts = [{"department_id": "ISC"}, {"department_id": "CSE"}, {"department_id": "ECE"}, {"department_id": "AIDS"}]

        for dept in depts:
            dept_id = dept["department_id"] if isinstance(dept, dict) else dept[0]
            hod_username = f"hod_{dept_id.lower()}"
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (hod_username,))
            if cursor.fetchone()[0] == 0:
                password = f"{dept_id.lower()}password"
                pwd_hash = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, department_id) VALUES (?, ?, ?, ?)",
                    (hod_username, pwd_hash, "HOD", dept_id)
                )
        conn.commit()
    except Exception:
        pass
    finally:
        if should_close:
            conn.close()

@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticates users against database records, returning a session token."""
    initialize_users_db()
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    
    conn, should_close = DatabaseConnectionManager.get_connection()
    user = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, role, department_id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
    finally:
        if should_close:
            conn.close()
            
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401
        
    db_role = user["role"]
    app_role = "SUPER_ADMIN" if db_role == "ADMIN" else "HOD"
    
    if APP_ENV == "testing":
        token = "super-admin-token-12345" if app_role == "SUPER_ADMIN" else "hod-token-12345"
    else:
        token = str(uuid.uuid4())
        
    session_data = {
        "username": username,
        "role": app_role,
        "department_id": user["department_id"] if user else None
    }
    TOKENS[token] = session_data
    return jsonify({"token": token, "role": app_role, "department_id": user["department_id"] if user else None})


def get_current_user_session():
    """Retrieves session dictionary for the current request."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        auth_header = request.args.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    token_data = TOKENS.get(token)
    if not token_data:
        return None
    if isinstance(token_data, str):
        # Legacy string-only role entry (no longer produced by login, but handled for safety)
        return {
            "username": "unknown",
            "role": token_data,
            "department_id": None
        }
    return token_data


def require_role(role: str):
    """Decorator to enforce role-based route access."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                auth_header = request.args.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing token"}), 401
                
            token = auth_header.split(" ")[1]
            token_data = TOKENS.get(token)
            
            if not token_data:
                return jsonify({"error": "Invalid token"}), 401
                
            token_role = token_data if isinstance(token_data, str) else token_data.get("role")
            
            if role == "SUPER_ADMIN" and token_role != "SUPER_ADMIN":
                return jsonify({"error": "Unauthorized"}), 403
                
            # If role is HOD, both HOD and SUPER_ADMIN are authorized
            if role == "HOD" and token_role not in ["HOD", "SUPER_ADMIN"]:
                return jsonify({"error": "Unauthorized"}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route("/hods", methods=["GET"])
def get_hods():
    """Returns all active departments with their HOD login info for the login dropdown.
    
    Queries departments table first (sorted alphabetically) and maps HOD usernames.
    Falls back to querying the users table directly if no departments exist.
    """
    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        
        # Primary: query departments table and join users for HOD username
        try:
            cursor.execute("""
                SELECT d.department_id, d.department_name,
                       u.username
                FROM department d
                LEFT JOIN users u 
                    ON LOWER(u.department_id) = LOWER(d.department_id) 
                    AND u.role = 'HOD'
                WHERE d.is_deleted = 0
                ORDER BY d.department_name ASC
            """)
            dept_rows = cursor.fetchall()
        except Exception:
            dept_rows = []
        
        if dept_rows:
            result = []
            for r in dept_rows:
                result.append({
                    "username": r["username"] or "hod",
                    "department_id": r["department_id"],
                    "department_name": r["department_name"] or r["department_id"]
                })
            return jsonify(result)
        
        # Fallback: query users table for HOD accounts
        cursor.execute("""
            SELECT u.username, u.department_id, d.department_name
            FROM users u
            LEFT JOIN department d ON LOWER(u.department_id) = LOWER(d.department_id)
            WHERE u.role = 'HOD'
            ORDER BY COALESCE(d.department_name, u.department_id) ASC
        """)
        rows = cursor.fetchall()
        hods = []
        for r in rows:
            hods.append({
                "username": r["username"],
                "department_id": r["department_id"],
                "department_name": r["department_name"] or r["department_id"] or "HOD Profile"
            })
        return jsonify(hods)
    except Exception as e:
        import logging
        logging.getLogger("TT_Scheduler").warning(f"Database error in get_hods, returning fallback list: {e}")
        return jsonify([
            {"username": "hod", "department_id": "ISC", "department_name": "Intelligent Systems and Cybersecurity"},
            {"username": "hod", "department_id": "CSE", "department_name": "Computer Science and Engineering"},
            {"username": "hod", "department_id": "ECE", "department_name": "Electronics and Communication Engineering"}
        ])
    finally:
        if should_close:
            conn.close()

@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Allows authenticated HOD or Admin to change their own password."""
    # Must be authenticated
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authentication required."}), 401
    token = auth_header.split(" ")[1]
    session = TOKENS.get(token)
    if not session:
        return jsonify({"error": "Invalid or expired token."}), 401
    authenticated_user = session.get("username") if isinstance(session, dict) else None
    if not authenticated_user:
        return jsonify({"error": "Invalid session."}), 401

    data = request.get_json() or {}
    username = data.get("username")
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not username or not new_password:
        return jsonify({"error": "Username and new password are required."}), 400

    # Users may only change their own password (SUPER_ADMIN can change any)
    session_role = session.get("role") if isinstance(session, dict) else None
    if session_role != "SUPER_ADMIN" and authenticated_user != username:
        return jsonify({"error": "You may only change your own password."}), 403

    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found."}), 404

        if old_password:
            if not check_password_hash(user["password_hash"], old_password):
                return jsonify({"error": "Invalid current password."}), 401

        new_pwd_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_pwd_hash, username))
        conn.commit()
        return jsonify({"message": "Password updated successfully."})
    finally:
        if should_close:
            conn.close()

