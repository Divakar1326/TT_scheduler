"""REST endpoints for managing version-controlled scheduling rules and AI translations."""
import os
import json
import sqlite3
from flask import Blueprint, request, jsonify
from app.ai.prompt_manager import RulePromptManager
from app.validators.rule_validator import RuleValidator
from app.repository.entity_repositories import RulesRepository
from app.repository.connection import DatabaseConnectionManager
from app.auth.auth import require_role
from app.ai.ai_service import AIService

rules_bp = Blueprint("rules_bp", __name__)
prompt_manager = RulePromptManager()
validator = RuleValidator()
rules_repo = RulesRepository()
ai_service = AIService()
def get_allowed_department_filter(session):
    """Returns (is_scoped, department_id) tuple based on session."""
    if not session:
        return False, None
    if session.get("role") == "SUPER_ADMIN":
        return False, None
    return True, session.get("department_id")

# Helper to get active rules list for contradiction/duplication checking
def get_all_rules_raw() -> list:
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        if scoped:
            cursor.execute("SELECT * FROM rules WHERE department_id IS NULL OR LOWER(department_id) = LOWER(?)", (s_dept,))
        else:
            cursor.execute("SELECT * FROM rules")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if should_close:
            conn.close()

@rules_bp.route("/rules", methods=["GET"])
@require_role("HOD")
def get_rules():
    """Retrieves all active rules (latest version for each rule_id)."""
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        if scoped:
            cursor.execute("""
                SELECT r.* 
                FROM rules r
                INNER JOIN (
                    SELECT rule_id, MAX(version) as max_version 
                    FROM rules 
                    WHERE is_deleted = 0 
                    GROUP BY rule_id
                ) latest ON r.rule_id = latest.rule_id AND r.version = latest.max_version
                WHERE r.is_deleted = 0 AND (r.department_id IS NULL OR LOWER(r.department_id) = LOWER(?))
            """, (s_dept,))
        else:
            cursor.execute("""
                SELECT r.* 
                FROM rules r
                INNER JOIN (
                    SELECT rule_id, MAX(version) as max_version 
                    FROM rules 
                    WHERE is_deleted = 0 
                    GROUP BY rule_id
                ) latest ON r.rule_id = latest.rule_id AND r.version = latest.max_version
                WHERE r.is_deleted = 0
            """)
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        if should_close:
            conn.close()


@rules_bp.route("/rules/parse-natural", methods=["POST"])
@require_role("HOD")
def parse_natural_rule():
    """Converts a natural language text rule into a structured JSON rule using OpenRouter."""
    data = request.get_json() or {}
    rule_text = data.get("rule_text", "").strip()
    
    if not rule_text:
        return jsonify({"error": "rule_text is required."}), 400
        
    prompt = prompt_manager.generate_prompt(rule_text)
    
    try:
        resp_text = ai_service.translate_natural_rule(prompt)
        # Remove any possible formatting wrappers
        resp_text = resp_text.replace("```json", "").replace("```", "").strip()
        parsed_json = json.loads(resp_text)
        
        # Check for fallback warning
        warning_msg = None
        if "switch" in getattr(ai_service, "fallback_status", "").lower():
            warning_msg = ai_service.fallback_status
        
        if warning_msg:
            parsed_json["warning"] = warning_msg
        return jsonify(parsed_json)
    except json.JSONDecodeError:
        from config.config import logger
        logger.error("Rule parsing failed: AI returned invalid JSON structure.")
        return jsonify({"error": "The AI returned an invalid response. Please rephrase the rule and try again."}), 502
    except Exception as e:
        import uuid
        from config.config import logger
        req_id = str(uuid.uuid4())
        logger.error(f"[{req_id}] Rule parsing failed: {e}")
        return jsonify({"error": "AI rule translation failed. Please try again later.", "request_id": req_id}), 502


@rules_bp.route("/rules/validate-structure", methods=["POST"])
@require_role("HOD")
def validate_structure():
    """Validates the structure, entity existence, and logical contradictions of a rule."""
    data = request.get_json() or {}
    parameter = data.get("parameter", {})
    
    entity_errors = validator.validate_entities(parameter)
    if entity_errors:
        return jsonify({"valid": False, "errors": entity_errors}), 200
        
    existing = get_all_rules_raw()
    
    if validator.check_duplication(parameter, existing):
        return jsonify({"valid": False, "errors": ["Duplicate rule detected."]}), 200
        
    contradictions = validator.check_contradictions(parameter, existing)
    if contradictions:
        return jsonify({"valid": False, "errors": contradictions}), 200
        
    return jsonify({"valid": True, "errors": []})


@rules_bp.route("/rules/save", methods=["POST"])
@require_role("HOD")
def save_rule():
    """Saves a new rule or registers a new version under the same rule_id."""
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    
    data = request.get_json() or {}
    rule_id = data.get("rule_id", "").strip()
    rule_name = data.get("rule_name", "").strip()
    original_text = data.get("original_text", "")
    parameter = data.get("parameter", {})
    rule_type = data.get("type", "HARD")
    priority = data.get("priority", 1)
    enabled = data.get("enabled", 1)
    created_by = data.get("created_by", "system")
    dept_id = data.get("department_id", "").strip() or None
    if scoped:
        dept_id = s_dept
    
    if not rule_id or not rule_name:
        return jsonify({"error": "rule_id and rule_name are required."}), 400

    # Entity validation
    entity_errors = validator.validate_entities(parameter)
    if entity_errors:
        return jsonify({"error": "Entity validation failed", "details": entity_errors}), 400

    existing = get_all_rules_raw()
    
    # If scoped, verify ownership of existing rule_id
    if scoped:
        existing_owner = [r for r in existing if r.get("rule_id") == rule_id]
        if existing_owner:
            owner_dept = existing_owner[0].get("department_id")
            if owner_dept and owner_dept.lower() != s_dept.lower():
                return jsonify({"error": "Access denied"}), 403

    # Check duplicates before saving (exclude same rule ID to allow version updates)
    other_rules = [r for r in existing if r.get("rule_id") != rule_id]
    if validator.check_duplication(parameter, other_rules):
        return jsonify({"error": "Duplicate rule", "details": ["An identical rule already exists in the system under a different ID."]}), 400

    # Check contradictions before saving
    contradictions = validator.check_contradictions(parameter, existing)
    if contradictions:
        return jsonify({"error": "Contradictory rule", "details": contradictions}), 400

    # Determine version number
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) FROM rules WHERE rule_id = ?", (rule_id,))
        row = cursor.fetchone()
        max_version = row[0] if row and row[0] is not None else 0
        new_version = max_version + 1
        
        # Save parameter as JSON string
        param_str = json.dumps(parameter)
        
        cursor.execute("""
            INSERT INTO rules (rule_id, version, rule_name, original_text, generated_json, priority, type, parameter, enabled, created_by, department_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rule_id, new_version, rule_name, original_text, param_str, priority, rule_type, param_str, enabled, created_by, dept_id))
        
        conn.commit()
        return jsonify({"message": "Rule saved successfully", "rule_id": rule_id, "version": new_version}), 201
    finally:
        if should_close:
            conn.close()


@rules_bp.route("/rules/versions/<rule_id>", methods=["GET"])
@rules_bp.route("/rules/<rule_id>/versions", methods=["GET"])
@require_role("HOD")
def get_rule_versions(rule_id):
    """Retrieves all version history of a specific rule."""
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        if scoped:
            cursor.execute("SELECT * FROM rules WHERE rule_id = ? AND (department_id IS NULL OR LOWER(department_id) = LOWER(?)) ORDER BY version DESC", (rule_id, s_dept))
        else:
            cursor.execute("SELECT * FROM rules WHERE rule_id = ? ORDER BY version DESC", (rule_id,))
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        if should_close:
            conn.close()


@rules_bp.route("/rules/toggle", methods=["POST"])
@require_role("HOD")
def toggle_rule():
    """Enables or disables a specific version of a rule."""
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    data = request.get_json() or {}
    rule_id = data.get("rule_id")
    version = data.get("version")
    enabled = data.get("enabled", 1)
    
    if not rule_id or version is None:
        return jsonify({"error": "rule_id and version are required."}), 400
        
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        if scoped:
            cursor.execute("SELECT department_id FROM rules WHERE rule_id = ? AND version = ? LIMIT 1", (rule_id, version))
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Rule not found"}), 404
            dept = row["department_id"]
            if dept and dept.lower() != s_dept.lower():
                return jsonify({"error": "Access denied"}), 403

        cursor.execute("UPDATE rules SET enabled = ? WHERE rule_id = ? AND version = ?", (enabled, rule_id, version))
        conn.commit()
        return jsonify({"message": "Rule toggled successfully"})
    finally:
        if should_close:
            conn.close()


@rules_bp.route("/rules/delete", methods=["POST"])
@require_role("HOD")
def delete_rule():
    """Soft deletes a specific version of a rule."""
    from app.auth.auth import get_current_user_session
    session = get_current_user_session()
    scoped, s_dept = get_allowed_department_filter(session)
    data = request.get_json() or {}
    rule_id = data.get("rule_id")
    version = data.get("version")
    
    if not rule_id or version is None:
        return jsonify({"error": "rule_id and version are required."}), 400
        
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        if scoped:
            cursor.execute("SELECT department_id FROM rules WHERE rule_id = ? AND version = ? LIMIT 1", (rule_id, version))
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Rule not found"}), 404
            dept = row["department_id"]
            if dept and dept.lower() != s_dept.lower():
                return jsonify({"error": "Access denied"}), 403

        cursor.execute("UPDATE rules SET is_deleted = 1 WHERE rule_id = ? AND version = ?", (rule_id, version))
        conn.commit()
        return jsonify({"message": "Rule deleted successfully"})
    finally:
        if should_close:
            conn.close()
