"""Authentication controllers and role checking decorators."""
from functools import wraps
from flask import Blueprint, request, jsonify

auth_bp = Blueprint("auth", __name__)

import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from app.repository.connection import DatabaseConnectionManager

# Hardcoded demo credentials fallback/cache structure for quick token mapping
TOKENS = {
    "super-admin-token-12345": "SUPER_ADMIN",
    "hod-token-12345": "HOD"
}

def initialize_users_db():
    """Seeds the users table if empty using hashed passwords."""
    conn, should_close = DatabaseConnectionManager.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            admin_pwd_hash = generate_password_hash("adminpassword")
            hod_pwd_hash = generate_password_hash("hodpassword")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", admin_pwd_hash, "ADMIN")
            )
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("hod", hod_pwd_hash, "HOD")
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
        cursor.execute("SELECT password_hash, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
    finally:
        if should_close:
            conn.close()
            
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401
        
    db_role = user["role"]
    app_role = "SUPER_ADMIN" if db_role == "ADMIN" else "HOD"
    
    if username == "admin":
        token = "super-admin-token-12345"
    elif username == "hod":
        token = "hod-token-12345"
    else:
        token = str(uuid.uuid4())
        
    TOKENS[token] = app_role
    return jsonify({"token": token, "role": app_role})


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
            token_role = TOKENS.get(token)
            
            if not token_role:
                return jsonify({"error": "Invalid token"}), 401
                
            if role == "SUPER_ADMIN" and token_role != "SUPER_ADMIN":
                return jsonify({"error": "Unauthorized"}), 403
                
            # If role is HOD, both HOD and SUPER_ADMIN are authorized
            if role == "HOD" and token_role not in ["HOD", "SUPER_ADMIN"]:
                return jsonify({"error": "Unauthorized"}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
