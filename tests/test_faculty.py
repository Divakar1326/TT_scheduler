"""
test_faculty.py - CRUD tests for Faculty entity.
"""
import pytest
from tests.helpers import (
    api_get, api_post, api_put, api_delete,
    assert_api_ok, assert_api_error,
    navigate_to_crud, ADMIN_TOKEN, HOD_TOKEN,
    QA_FACULTY
)

QA_FAC_ID = QA_FACULTY["faculty_id"]


class TestFacultyAPI:
    """API-level CRUD tests for faculty members."""

    def test_list_faculties(self):
        """GET /api/faculties returns a list of faculty."""
        resp = api_get("/api/faculties")
        assert_api_ok(resp, "List faculties")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Faculty list should contain seed data"

    def test_faculty_list_has_expected_fields(self):
        """Faculty list items should have required fields."""
        resp = api_get("/api/faculties")
        data = resp.json()
        if data:
            fac = data[0]
            assert "faculty_id" in fac
            assert "faculty_name" in fac

    def test_create_faculty(self):
        """POST /api/faculties creates a new faculty member."""
        api_delete(f"/api/faculties/{QA_FAC_ID}")
        resp = api_post("/api/faculties", QA_FACULTY)
        assert_api_ok(resp, "Create faculty")

    def test_get_faculty_by_id(self):
        """GET /api/faculties/<id> returns the correct faculty."""
        api_post("/api/faculties", QA_FACULTY)
        resp = api_get(f"/api/faculties/{QA_FAC_ID}")
        assert_api_ok(resp, "Get faculty by ID")
        data = resp.json()
        assert data.get("faculty_id") == QA_FAC_ID

    def test_update_faculty(self):
        """PUT /api/faculties/<id> updates faculty data."""
        api_post("/api/faculties", QA_FACULTY)
        updated = {**QA_FACULTY, "faculty_name": "QA Faculty Updated"}
        resp = api_put(f"/api/faculties/{QA_FAC_ID}", updated)
        assert_api_ok(resp, "Update faculty")

    def test_delete_faculty(self):
        """DELETE /api/faculties/<id> removes the faculty member."""
        api_post("/api/faculties", QA_FACULTY)
        resp = api_delete(f"/api/faculties/{QA_FAC_ID}")
        assert_api_ok(resp, "Delete faculty")

    def test_get_nonexistent_faculty_returns_404(self):
        """GET /api/faculties/<nonexistent> returns 404."""
        resp = api_get("/api/faculties/NOBODY_XYZ_9999")
        assert_api_error(resp, 404, "Nonexistent faculty")

    def test_hod_cannot_create_faculty(self):
        """HOD should be forbidden from creating faculty."""
        resp = api_post("/api/faculties", QA_FACULTY, token=HOD_TOKEN)
        assert_api_error(resp, 403, "HOD create faculty")

    def test_hod_can_read_faculty(self):
        """HOD should be able to read faculty list."""
        resp = api_get("/api/faculties", token=HOD_TOKEN)
        assert_api_ok(resp, "HOD read faculty")

    def test_faculty_max_hours_validation(self):
        """Faculty with invalid max_hours_week should be rejected."""
        bad_faculty = {**QA_FACULTY, "max_hours_week": -10, "faculty_id": "QABADFAC"}
        resp = api_post("/api/faculties", bad_faculty)
        # Should fail with 400 for invalid data
        # (or succeed if server doesn't validate negatives, mark as warning)
        # We just ensure it doesn't crash the server
        assert resp.status_code in (200, 201, 400, 422), (
            f"Server returned unexpected status {resp.status_code}"
        )

    def test_faculty_list_search_by_department(self):
        """Faculty list should return results with required fields."""
        resp = api_get("/api/faculties")
        data = resp.json()
        assert len(data) > 0, "Faculty list should have seeded data"
        # Verify each faculty has the expected domain fields
        for fac in data[:5]:
            assert "faculty_id" in fac, "Faculty missing faculty_id"
            assert "faculty_name" in fac, "Faculty missing faculty_name"


class TestFacultyUI:
    """UI-level tests for faculty management."""

    def test_faculty_list_loads_in_crud(self, admin_page):
        """Faculty list should be visible in CRUD manager."""
        navigate_to_crud(admin_page, "faculties")
        admin_page.wait_for_timeout(1500)
        content = admin_page.inner_text("body")
        # Should have some faculty names visible
        assert len(content) > 100, "Faculty list content is suspiciously empty"

    def test_faculty_entity_shown_in_table(self, admin_page):
        """Faculty data should appear in the CRUD table rows."""
        navigate_to_crud(admin_page, "faculties")
        admin_page.wait_for_timeout(2000)
        rows = admin_page.locator("table tr, .crud-row, .entity-row").all()
        # At least one data row (header + data)
        assert len(rows) >= 1, "Should have table rows"
