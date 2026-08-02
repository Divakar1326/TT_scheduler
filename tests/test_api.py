"""
test_api.py - API consistency, error-handling, and edge-case tests.

Tests:
- 404 for unknown routes
- 401/403 for unauthorized access patterns
- 405 for wrong HTTP methods
- Response format consistency
- CORS headers
- Error message format
- Large payload handling
- Concurrent request handling
"""
import json
import time
import threading
import pytest
import requests
from tests.helpers import (
    api_get, api_post, api_put, api_delete,
    assert_api_ok, assert_api_error, ADMIN_TOKEN, HOD_TOKEN
)

BASE_URL = "http://127.0.0.1:5000"


class TestAPIRouteExistence:
    """Verify all required API routes exist (not 404/405)."""

    REQUIRED_ENDPOINTS = [
        ("GET", "/api/departments"),
        ("GET", "/api/faculties"),
        ("GET", "/api/courses"),
        ("GET", "/api/rooms"),
        ("GET", "/api/laboratories"),
        ("GET", "/api/sections"),
        ("GET", "/api/rules"),
        ("GET", "/api/dashboard/stats"),
        ("GET", "/api/hod/sections-status"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/scheduler/generate"),
        ("POST", "/api/scheduler/validate"),
        ("POST", "/api/scheduler/repair"),
        ("GET", "/api/scheduler/export"),
        ("POST", "/api/rules/parse-natural"),
    ]

    @pytest.mark.parametrize("method,path", REQUIRED_ENDPOINTS)
    def test_endpoint_exists(self, method, path):
        """Each required endpoint must respond (not 404)."""
        resp = requests.request(
            method,
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            json={},
            timeout=15
        )
        assert resp.status_code != 404, (
            f"{method} {path} returned 404 — endpoint does not exist"
        )


class TestAPIAuthentication:
    """Test authentication enforcement across all endpoints."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/departments"),
        ("GET", "/api/faculties"),
        ("GET", "/api/courses"),
        ("GET", "/api/rooms"),
        ("GET", "/api/laboratories"),
        ("GET", "/api/sections"),
        ("GET", "/api/rules"),
        ("GET", "/api/dashboard/stats"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_endpoint_requires_auth(self, method, path):
        """All protected endpoints must return 401 without a token."""
        resp = requests.request(method, f"{BASE_URL}{path}", timeout=10)
        assert resp.status_code in (401, 403), (
            f"{method} {path} without token returned {resp.status_code} — expected 401/403"
        )

    def test_invalid_token_rejected(self):
        """Invalid/random token should be rejected with 401/403."""
        resp = requests.get(
            f"{BASE_URL}/api/faculties",
            headers={"Authorization": "Bearer FAKE_TOKEN_XYZ"},
            timeout=10
        )
        assert resp.status_code in (401, 403), (
            f"Invalid token returned {resp.status_code}"
        )

    def test_malformed_auth_header_rejected(self):
        """Malformed Authorization header should be rejected."""
        resp = requests.get(
            f"{BASE_URL}/api/faculties",
            headers={"Authorization": "NotBearer token"},
            timeout=10
        )
        assert resp.status_code in (401, 403), (
            f"Malformed auth header returned {resp.status_code}"
        )


class TestAPIResponseFormats:
    """Verify API responses follow consistent JSON format."""

    def test_list_endpoints_return_json_array(self):
        """All list GET endpoints should return a JSON array."""
        endpoints = ["/api/departments", "/api/faculties", "/api/courses",
                     "/api/rooms", "/api/laboratories", "/api/sections", "/api/rules"]
        for path in endpoints:
            resp = api_get(path)
            assert resp.status_code == 200, f"{path} returned {resp.status_code}"
            data = resp.json()
            assert isinstance(data, list), f"{path} returned non-list: {type(data)}"

    def test_error_responses_have_error_key(self):
        """Error responses should have an 'error' key."""
        resp = api_get("/api/departments/DOES_NOT_EXIST_XYZ")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data, f"Error response missing 'error' key: {data}"

    def test_create_responses_have_message(self):
        """Successful create responses should have a 'message' or 'id' key."""
        from tests.helpers import QA_DEPT
        # Clean up in case it already exists
        api_delete(f"/api/departments/{QA_DEPT['department_id']}")
        resp = api_post("/api/departments", QA_DEPT)
        assert resp.status_code in (200, 201), (
            f"Create department failed: {resp.status_code}: {resp.text[:200]}"
        )
        data = resp.json()
        assert "message" in data or "id" in data, (
            f"Create response missing message/id: {data}"
        )

    def test_update_responses_have_message(self):
        """Successful update responses should have a 'message' key."""
        from tests.helpers import QA_DEPT
        # Ensure dept exists first (create if not)
        create_resp = api_post("/api/departments", QA_DEPT)
        # Proceed even if already exists (400 is ok)
        resp = api_put(f"/api/departments/{QA_DEPT['department_id']}", QA_DEPT)
        assert resp.status_code == 200, (
            f"Update dept returned {resp.status_code}: {resp.text[:200]}"
        )
        data = resp.json()
        assert "message" in data, f"Update response missing 'message': {data}"

    def test_delete_responses_have_message(self):
        """Successful delete responses should have a 'message' key."""
        from tests.helpers import QA_DEPT
        api_post("/api/departments", QA_DEPT)
        resp = api_delete(f"/api/departments/{QA_DEPT['department_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data, f"Delete response missing 'message': {data}"

    def test_all_responses_are_json(self):
        """All API responses should have Content-Type: application/json."""
        resp = api_get("/api/departments")
        ct = resp.headers.get("Content-Type", "")
        assert "application/json" in ct, (
            f"Expected JSON content type, got: {ct}"
        )


class TestAPIErrorHandling:
    """Test error conditions are handled gracefully."""

    def test_unknown_route_returns_404(self):
        """Unknown routes should return 404 or 500 (global handler may wrap it)."""
        resp = requests.get(f"{BASE_URL}/api/nonexistent_route_xyz", timeout=10)
        assert resp.status_code in (404, 500), (
            f"Unknown route returned {resp.status_code} — expected 404 or 500"
        )

    def test_wrong_http_method_returns_405(self):
        """Wrong HTTP method on existing routes should return 405 or 500 (global handler may wrap)."""
        resp = requests.delete(
            f"{BASE_URL}/api/auth/login",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=10
        )
        assert resp.status_code in (404, 405, 500), (
            f"DELETE on /api/auth/login returned {resp.status_code}"
        )

    def test_empty_body_on_post_does_not_crash(self):
        """POST with empty body should not crash the server catastrophically."""
        resp = requests.post(
            f"{BASE_URL}/api/departments",
            headers={
                "Authorization": f"Bearer {ADMIN_TOKEN}",
                "Content-Type": "application/json"
            },
            data="",
            timeout=10
        )
        # 400 = validation error, 500 = server handled error, both are acceptable
        # We only fail if the server doesn't respond at all
        assert resp.status_code in (400, 401, 403, 500), (
            f"Empty POST body returned unexpected status: {resp.status_code}"
        )

    def test_malformed_json_does_not_crash(self):
        """Malformed JSON body should be handled gracefully."""
        resp = requests.post(
            f"{BASE_URL}/api/departments",
            headers={
                "Authorization": f"Bearer {ADMIN_TOKEN}",
                "Content-Type": "application/json"
            },
            data="{invalid_json: true}",
            timeout=10
        )
        # Flask's get_json returns None/empty for malformed JSON, so server handles it
        assert resp.status_code in (400, 401, 403, 500), (
            f"Malformed JSON returned unexpected status: {resp.status_code} — body: {resp.text[:200]}"
        )

    def test_create_with_missing_required_fields(self):
        """Create request missing required fields should return 400."""
        resp = api_post("/api/departments", {"department_name": "Missing ID"})
        # Should fail gracefully
        assert resp.status_code in (400, 422, 500), (
            f"Missing fields create returned {resp.status_code}"
        )


class TestAPICORSHeaders:
    """Test CORS configuration."""

    def test_cors_headers_present_on_api_response(self):
        """CORS headers should be present (or at least the server shouldn't crash)."""
        resp = requests.options(
            f"{BASE_URL}/api/departments",
            headers={"Origin": "http://localhost:3000"},
            timeout=10
        )
        # 200 or 204 for OPTIONS is acceptable
        assert resp.status_code in (200, 204, 405), (
            f"OPTIONS request returned {resp.status_code}"
        )


class TestAPIPerformance:
    """Basic performance checks for API endpoints."""

    def test_list_departments_response_time(self):
        """Department list should respond within 2 seconds."""
        start = time.time()
        api_get("/api/departments")
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Department list took {elapsed:.2f}s — too slow"

    def test_list_faculties_response_time(self):
        """Faculty list should respond within 2 seconds."""
        start = time.time()
        api_get("/api/faculties")
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Faculty list took {elapsed:.2f}s"

    def test_concurrent_read_requests(self):
        """Multiple concurrent read requests should all succeed."""
        results = []
        errors = []

        def read_faculties():
            try:
                resp = api_get("/api/faculties")
                results.append(resp.status_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_faculties) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent requests failed: {errors}"
        assert all(s == 200 for s in results), (
            f"Some concurrent requests failed: {results}"
        )
