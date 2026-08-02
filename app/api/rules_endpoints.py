"""REST endpoints for managing version-controlled scheduling rules and AI translations."""
import os
import json
import sqlite3
from flask import Blueprint, request, jsonify
from app.constraints.prompt_manager import RulePromptManager
from app.constraints.rule_validator import RuleValidator
from app.repository.entity_repositories import RulesRepository
from app.repository.connection import DatabaseConnectionManager
from app.api.auth import require_role
from config import GEMINI_MODEL, GEMINI_API_KEY

from app.ai.gemini_client import GeminiAIClient

rules_bp = Blueprint("rules_bp", __name__)
prompt_manager = RulePromptManager()
validator = RuleValidator()
rules_repo = RulesRepository()
ai_client = GeminiAIClient()

# Helper to get active rules list for contradiction/duplication checking
def get_all_rules_raw() -> list:
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rules")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        if should_close:
            conn.close()

@rules_bp.route("/rules/parse-natural", methods=["POST"])
@require_role("HOD")
def parse_natural_rule():
    """Converts a natural language text rule into a structured JSON rule using Gemini 3.5 Flash."""
    data = request.get_json() or {}
    rule_text = data.get("rule_text", "").strip()
    
    if not rule_text:
        return jsonify({"error": "rule_text is required."}), 400
        
    prompt = prompt_manager.generate_prompt(rule_text)
    
    # Try calling actual Gemini if API key is present
    parsed_json = None
    if ai_client.client:
        try:
            resp_text = ai_client.translate_natural_rule(prompt)
            # Remove any possible formatting wrappers
            resp_text = resp_text.replace("```json", "").replace("```", "").strip()
            parsed_json = json.loads(resp_text)
        except Exception as e:
            return jsonify({"error": f"Gemini API failure: {str(e)}"}), 502
    else:
        # Fallback/Mock behavior for local testing if no API key is specified
        if "avoid Friday" in rule_text or "Friday" in rule_text:
            parsed_json = {
                "rule_id": "F01_avoid_friday",
                "rule_name": "F01 avoid Friday",
                "type": "HARD",
                "priority": 1,
                "parameter": {
                    "faculty_id": "F01",
                    "avoid_days": [5]
                }
            }
        elif "prefer" in rule_text or "Prefer" in rule_text:
            parsed_json = {
                "rule_id": "F01_prefer_friday",
                "rule_name": "F01 prefer Friday",
                "type": "SOFT",
                "priority": 1,
                "parameter": {
                    "faculty_id": "F01",
                    "preferred_days": [5]
                }
            }
        else:
            parsed_json = {
                "rule_id": "parsed_custom_rule",
                "rule_name": "Parsed Custom Rule",
                "type": "HARD",
                "priority": 1,
                "parameter": {}
            }
            
    return jsonify(parsed_json)


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
@require_role("SUPER_ADMIN")
def save_rule():
    """Saves a new rule or registers a new version under the same rule_id."""
    data = request.get_json() or {}
    rule_id = data.get("rule_id", "").strip()
    rule_name = data.get("rule_name", "").strip()
    original_text = data.get("original_text", "")
    parameter = data.get("parameter", {})
    rule_type = data.get("type", "HARD")
    priority = data.get("priority", 1)
    enabled = data.get("enabled", 1)
    created_by = data.get("created_by", "system")
    
    if not rule_id or not rule_name:
        return jsonify({"error": "rule_id and rule_name are required."}), 400

    # Entity validation
    entity_errors = validator.validate_entities(parameter)
    if entity_errors:
        return jsonify({"error": "Entity validation failed", "details": entity_errors}), 400

    existing = get_all_rules_raw()
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
            INSERT INTO rules (rule_id, version, rule_name, original_text, generated_json, priority, type, parameter, enabled, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rule_id, new_version, rule_name, original_text, param_str, priority, rule_type, param_str, enabled, created_by))
        
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
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rules WHERE rule_id = ? ORDER BY version DESC", (rule_id,))
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        if should_close:
            conn.close()


@rules_bp.route("/rules/toggle", methods=["POST"])
@require_role("SUPER_ADMIN")
def toggle_rule():
    """Enables or disables a specific version of a rule."""
    data = request.get_json() or {}
    rule_id = data.get("rule_id")
    version = data.get("version")
    enabled = data.get("enabled", 1)
    
    if not rule_id or version is None:
        return jsonify({"error": "rule_id and version are required."}), 400
        
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE rules SET enabled = ? WHERE rule_id = ? AND version = ?", (enabled, rule_id, version))
        conn.commit()
        return jsonify({"message": "Rule toggled successfully"})
    finally:
        if should_close:
            conn.close()


@rules_bp.route("/rules/delete", methods=["POST"])
@require_role("SUPER_ADMIN")
def delete_rule():
    """Soft deletes a specific version of a rule."""
    data = request.get_json() or {}
    rule_id = data.get("rule_id")
    version = data.get("version")
    
    if not rule_id or version is None:
        return jsonify({"error": "rule_id and version are required."}), 400
        
    conn, should_close = DatabaseConnectionManager.get_connection(rules_repo.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE rules SET is_deleted = 1 WHERE rule_id = ? AND version = ?", (rule_id, version))
        conn.commit()
        return jsonify({"message": "Rule deleted successfully"})
    finally:
        if should_close:
            conn.close()
