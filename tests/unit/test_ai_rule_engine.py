"""Unit tests for the AI Rule Engine, including prompt, validator, conflict, and route tests."""
import os
os.environ["APP_ENV"] = "testing"
os.environ["FLASK_ENV"] = "testing"
import json
import unittest
from app.api.app import create_app
from app.ai.prompt_manager import RulePromptManager
from app.validators.rule_validator import RuleValidator
from app.repository.connection import DatabaseConnectionManager

class TestAIRuleEngine(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.headers_admin = {"Authorization": "Bearer super-admin-token-12345"}
        self.headers_hod = {"Authorization": "Bearer hod-token-12345"}
        self.prompt_mgr = RulePromptManager()
        self.validator = RuleValidator()
        # Clean up test rules
        conn, should_close = DatabaseConnectionManager.get_connection()
        try:
            conn.execute("DELETE FROM rules WHERE rule_id LIKE 'test_%'")
            conn.commit()
        finally:
            if should_close:
                conn.close()

    def test_prompt_generation(self):
        prompt = self.prompt_mgr.generate_prompt("Dr. Rekha (F01) avoids Friday.")
        self.assertIn("Dr. Rekha (F01) avoids Friday.", prompt)
        self.assertIn("JSON", prompt)

    def test_entity_existence_validation(self):
        # 1. Valid parameters
        param_valid = {
            "faculty_id": "F01",
            "avoid_days": [5],
            "avoid_periods": [5]
        }
        errors = self.validator.validate_entities(param_valid)
        self.assertEqual(len(errors), 0)

        # 2. Invalid entities
        param_invalid = {
            "faculty_id": "NON_EXISTENT_FACULTY",
            "course_id": "NON_EXISTENT_COURSE",
            "avoid_days": [99] # Invalid day id
        }
        errors = self.validator.validate_entities(param_invalid)
        self.assertTrue(len(errors) >= 3)

    def test_duplication_and_contradiction(self):
        existing_rules = [
            {
                "rule_id": "r1",
                "rule_name": "R1",
                "parameter": json.dumps({"faculty_id": "F01", "avoid_days": [5]}),
                "enabled": 1,
                "is_deleted": 0
            }
        ]

        # 1. Duplication
        new_param_dup = {"faculty_id": "F01", "avoid_days": [5]}
        self.assertTrue(self.validator.check_duplication(new_param_dup, existing_rules))

        # 2. Self contradiction (prefer vs avoid same day)
        new_param_contra_self = {
            "faculty_id": "F01",
            "avoid_days": [5],
            "preferred_days": [5]
        }
        contra_self_errors = self.validator.check_contradictions(new_param_contra_self, [])
        self.assertEqual(len(contra_self_errors), 1)

        # 3. Contradiction with existing rules (prefer Friday when already avoiding Friday)
        new_param_contra_ext = {
            "faculty_id": "F01",
            "preferred_days": [5]
        }
        contra_ext_errors = self.validator.check_contradictions(new_param_contra_ext, existing_rules)
        self.assertEqual(len(contra_ext_errors), 1)

    def test_rules_api_endpoints(self):
        # 1. Natural Language Parser Mock
        from unittest.mock import patch
        with patch('app.ai.ai_service.AIService.translate_natural_rule') as mock_generate:
            mock_generate.return_value = json.dumps({
                "rule_id": "F01_avoid_friday",
                "rule_name": "Dr. Rekha avoids Friday",
                "original_text": "Dr. Rekha (F01) avoids Friday",
                "type": "HARD",
                "priority": 1,
                "parameter": {
                    "faculty_id": "F01",
                    "avoid_days": [5]
                }
            })
            res_parse = self.client.post("/api/rules/parse-natural", json={"rule_text": "Dr. Rekha (F01) avoids Friday"}, headers=self.headers_hod)
            self.assertEqual(res_parse.status_code, 200)
            data_parse = res_parse.get_json()
            self.assertEqual(data_parse["rule_id"], "F01_avoid_friday")
        
        # 2. Save Rule Version 1
        rule_payload = {
            "rule_id": "test_fac_rule_1",
            "rule_name": "Test Faculty Rule",
            "original_text": "F01 avoids Friday period 7",
            "type": "HARD",
            "priority": 1,
            "parameter": {
                "faculty_id": "F01",
                "avoid_days": [5],
                "avoid_periods": [7]
            }
        }
        res_save1 = self.client.post("/api/rules/save", json=rule_payload, headers=self.headers_admin)
        self.assertEqual(res_save1.status_code, 201)
        self.assertEqual(res_save1.get_json()["version"], 1)

        # 3. Save Rule Version 2 (Same rule_id, different details)
        rule_payload["original_text"] = "F01 avoids Friday period 6 and 7"
        rule_payload["parameter"]["avoid_periods"] = [6, 7]
        res_save2 = self.client.post("/api/rules/save", json=rule_payload, headers=self.headers_admin)
        self.assertEqual(res_save2.status_code, 201)
        self.assertEqual(res_save2.get_json()["version"], 2)

        # 4. Fetch versions
        res_ver = self.client.get("/api/rules/versions/test_fac_rule_1", headers=self.headers_hod)
        self.assertEqual(res_ver.status_code, 200)
        versions = res_ver.get_json()
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["version"], 2)
        self.assertEqual(versions[1]["version"], 1)

        # 5. Toggle Rule
        res_toggle = self.client.post("/api/rules/toggle", json={"rule_id": "test_fac_rule_1", "version": 1, "enabled": 0}, headers=self.headers_admin)
        self.assertEqual(res_toggle.status_code, 200)

        # 6. Delete Rule Version
        res_del = self.client.post("/api/rules/delete", json={"rule_id": "test_fac_rule_1", "version": 2}, headers=self.headers_admin)
        self.assertEqual(res_del.status_code, 200)


if __name__ == "__main__":
    unittest.main()
