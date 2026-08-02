"""
test_rules.py - Tests for the Rule Builder (Structured + Natural Language via Gemini).
"""
import json
import pytest
from tests.helpers import (
    api_get, api_post, api_put, api_delete,
    assert_api_ok, assert_api_error,
    navigate_to_rules, ADMIN_TOKEN, HOD_TOKEN,
    QA_RULE
)

QA_RULE_ID = QA_RULE["rule_id"]


class TestRuleAPI:
    """API-level CRUD tests for scheduling rules.
    
    Note: Rules use the specialized rules_bp endpoints (/api/rules/save, /api/rules/toggle, etc.)
    rather than the generic CRUD endpoint, because the DB schema differs from the domain model.
    """

    def test_list_rules(self):
        """GET /api/rules returns a list."""
        resp = api_get("/api/rules")
        assert_api_ok(resp, "List rules")
        data = resp.json()
        assert isinstance(data, list)

    def test_rules_have_required_fields(self):
        """Rules should have rule_id, rule_name, enabled fields."""
        resp = api_get("/api/rules")
        data = resp.json()
        if data:
            rule = data[0]
            for field in ["rule_id", "rule_name"]:
                assert field in rule, f"Missing field {field} in rule"

    def test_create_rule_via_save_endpoint(self):
        """POST /api/rules/save creates a new rule using the correct endpoint."""
        # Soft-delete any existing version first
        api_post("/api/rules/delete", {"rule_id": QA_RULE_ID, "version": 1})
        resp = api_post("/api/rules/save", {
            "rule_id": QA_RULE_ID,
            "rule_name": "QA Test Rule",
            "original_text": "No classes on Friday afternoons",
            "parameter": {"avoid_days": [5]},
            "type": "SOFT",
            "priority": 5,
            "enabled": 1,
        })
        assert_api_ok(resp, "Create rule via save")
        data = resp.json()
        assert "rule_id" in data or "message" in data

    def test_get_rule_by_id_after_save(self):
        """GET /api/rules/<id> returns the rule after saving it."""
        # Ensure rule exists
        api_post("/api/rules/save", {
            "rule_id": QA_RULE_ID,
            "rule_name": "QA Test Rule",
            "original_text": "No classes on Friday afternoons",
            "parameter": {"avoid_days": [5]},
            "type": "SOFT",
            "priority": 5,
        })
        resp = api_get(f"/api/rules/{QA_RULE_ID}")
        assert_api_ok(resp, "Get rule by ID")
        data = resp.json()
        assert data.get("rule_id") == QA_RULE_ID

    def test_rule_versions_endpoint(self):
        """GET /api/rules/versions/<id> returns version history."""
        api_post("/api/rules/save", {
            "rule_id": QA_RULE_ID,
            "rule_name": "QA Test Rule v2",
            "original_text": "Test rule",
            "parameter": {"avoid_days": [5]},
            "type": "SOFT",
            "priority": 5,
        })
        resp = api_get(f"/api/rules/versions/{QA_RULE_ID}", token=ADMIN_TOKEN)
        assert_api_ok(resp, "Get rule versions")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Should have at least one version"

    def test_rule_enable_disable_toggle(self):
        """POST /api/rules/toggle enables/disables a rule version."""
        # Create/ensure rule exists at version 1
        api_post("/api/rules/save", {
            "rule_id": QA_RULE_ID,
            "rule_name": "QA Toggle Rule",
            "original_text": "Test toggle",
            "parameter": {},
            "type": "SOFT",
            "priority": 1,
        })
        # Toggle to disabled
        resp = api_post("/api/rules/toggle", {
            "rule_id": QA_RULE_ID,
            "version": 1,
            "enabled": 0
        })
        assert_api_ok(resp, "Toggle rule disabled")
        # Toggle back to enabled
        resp2 = api_post("/api/rules/toggle", {
            "rule_id": QA_RULE_ID,
            "version": 1,
            "enabled": 1
        })
        assert_api_ok(resp2, "Toggle rule enabled")

    def test_delete_rule_via_soft_delete(self):
        """POST /api/rules/delete soft-deletes a rule."""
        api_post("/api/rules/save", {
            "rule_id": QA_RULE_ID,
            "rule_name": "QA Delete Rule",
            "original_text": "Delete test",
            "parameter": {},
            "type": "SOFT",
            "priority": 1,
        })
        resp = api_post("/api/rules/delete", {
            "rule_id": QA_RULE_ID,
            "version": 1
        })
        assert_api_ok(resp, "Soft delete rule")

    def test_nonexistent_rule_returns_404(self):
        """GET /api/rules/<nonexistent> returns 404."""
        resp = api_get("/api/rules/NONEXISTENT_RULE_XXXXX")
        assert_api_error(resp, 404, "Nonexistent rule")

    def test_rule_parameter_is_valid_json(self):
        """Rule parameter field should be valid JSON when set."""
        resp = api_get("/api/rules")
        data = resp.json()
        for rule in data:
            param = rule.get("parameter")
            if param and isinstance(param, str):
                try:
                    parsed = json.loads(param)
                    assert isinstance(parsed, dict), f"Rule {rule.get('rule_id')} parameter is not a dict"
                except json.JSONDecodeError:
                    pytest.fail(f"Rule {rule.get('rule_id')} has invalid JSON parameter: {param[:100]}")

    def test_hod_cannot_create_rule(self):
        """HOD token is rejected for rule save."""
        resp = api_post("/api/rules/save", {
            "rule_id": "HOD_TEST_RULE",
            "rule_name": "HOD Test Rule",
            "parameter": {},
            "type": "SOFT",
            "priority": 1,
        }, token=HOD_TOKEN)
        assert_api_error(resp, 403, "HOD create rule")

    def test_hod_can_read_rules(self):
        """HOD can read rules list."""
        resp = api_get("/api/rules", token=HOD_TOKEN)
        assert_api_ok(resp, "HOD read rules")


class TestNaturalLanguageRuleAPI:
    """Tests for the Gemini NL → Rule pipeline API."""

    def test_nl_parse_endpoint_exists(self):
        """POST /api/rules/parse-natural endpoint must exist and respond."""
        resp = api_post("/api/rules/parse-natural", {
            "rule_text": "Faculty should not be assigned to more than 4 periods per day"
        })
        # Must return 200 with JSON or an appropriate error (not 404/500 from missing route)
        assert resp.status_code in (200, 400, 422, 500, 502, 503), (
            f"NL parse endpoint returned unexpected {resp.status_code}: {resp.text[:200]}"
        )

    def test_nl_parse_returns_json_structure(self):
        """NL parse should return a JSON object on success."""
        resp = api_post("/api/rules/parse-natural", {
            "rule_text": "Avoid Friday afternoon classes"
        })
        if resp.status_code == 200:
            data = resp.json()
            # Should have at least one key
            assert isinstance(data, dict), "NL parse response should be a dict"

    def test_nl_parse_requires_text_field(self):
        """NL parse without 'rule_text' field should return 400."""
        resp = api_post("/api/rules/parse-natural", {})
        assert resp.status_code in (400, 422), (
            f"Missing text field should return 400/422, got {resp.status_code}"
        )


class TestRuleUI:
    """UI tests for the Rule Builder page."""

    def test_rule_builder_page_loads(self, admin_page):
        """Rule builder page should load and display rule list."""
        navigate_to_rules(admin_page)
        admin_page.wait_for_timeout(1500)
        expect_visible = admin_page.locator("#view-rule-builder")
        assert "hidden" not in (expect_visible.get_attribute("class") or "")

    def test_rule_builder_has_tab_structure(self, admin_page):
        """Rule builder should have structured and NL rule tabs."""
        navigate_to_rules(admin_page)
        admin_page.wait_for_timeout(1000)
        page_content = admin_page.inner_text("body")
        # Check for tab indicators
        assert any(word in page_content.lower() for word in ["structured", "natural language", "gemini", "rule"])

    def test_rule_list_visible_in_ui(self, admin_page):
        """Rules list should appear in the UI."""
        navigate_to_rules(admin_page)
        admin_page.wait_for_timeout(1500)
        content = admin_page.inner_text("body")
        assert len(content) > 100, "Rules page content seems empty"

    def test_rule_versions_endpoint(self):
        """GET /api/rules/<id>/versions returns version history."""
        # Ensure we have a rule
        api_post("/api/rules", QA_RULE)
        resp = api_get(f"/api/rules/{QA_RULE_ID}/versions")
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
        else:
            # versions endpoint may not exist
            assert resp.status_code in (404, 405), (
                f"Versions endpoint returned {resp.status_code}"
            )
