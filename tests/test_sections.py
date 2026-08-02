"""
test_sections.py - CRUD tests for Section entity.
"""
import pytest
from tests.helpers import (
    api_get, api_post, api_put, api_delete,
    assert_api_ok, assert_api_error,
    navigate_to_crud, ADMIN_TOKEN, HOD_TOKEN,
    QA_SECTION
)

QA_SEC_ID = QA_SECTION["section_id"]


class TestSectionAPI:
    """API-level CRUD tests for sections."""

    def test_list_sections(self):
        """GET /api/sections returns a list."""
        resp = api_get("/api/sections")
        assert_api_ok(resp, "List sections")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Sections list should contain seed data"

    def test_section_has_required_fields(self):
        """Sections should have section_id, section_name, department_id."""
        resp = api_get("/api/sections")
        data = resp.json()
        if data:
            sec = data[0]
            assert "section_id" in sec, "Missing section_id"
            assert "section_name" in sec, "Missing section_name"

    def test_create_section(self):
        """POST /api/sections creates a new section."""
        api_delete(f"/api/sections/{QA_SEC_ID}")
        resp = api_post("/api/sections", QA_SECTION)
        assert_api_ok(resp, "Create section")

    def test_get_section_by_id(self):
        """GET /api/sections/<id> returns correct section."""
        api_post("/api/sections", QA_SECTION)
        resp = api_get(f"/api/sections/{QA_SEC_ID}")
        assert_api_ok(resp, "Get section by ID")
        data = resp.json()
        assert data.get("section_id") == QA_SEC_ID

    def test_update_section(self):
        """PUT /api/sections/<id> updates section data."""
        api_post("/api/sections", QA_SECTION)
        updated = {**QA_SECTION, "section_name": "QA Section - Updated"}
        resp = api_put(f"/api/sections/{QA_SEC_ID}", updated)
        assert_api_ok(resp, "Update section")

    def test_delete_section(self):
        """DELETE /api/sections/<id> removes a section."""
        api_post("/api/sections", QA_SECTION)
        resp = api_delete(f"/api/sections/{QA_SEC_ID}")
        assert_api_ok(resp, "Delete section")

    def test_nonexistent_section_returns_404(self):
        """GET /api/sections/<nonexistent> returns 404."""
        resp = api_get("/api/sections/XYZXYZ_9999")
        assert_api_error(resp, 404, "Nonexistent section")

    def test_hod_cannot_create_section(self):
        """HOD token rejected for section creation."""
        resp = api_post("/api/sections", QA_SECTION, token=HOD_TOKEN)
        assert_api_error(resp, 403, "HOD create section")

    def test_hod_can_read_sections(self):
        """HOD can read the sections list."""
        resp = api_get("/api/sections", token=HOD_TOKEN)
        assert_api_ok(resp, "HOD read sections")

    def test_sections_belong_to_department(self):
        """All sections should have a valid department_id."""
        resp = api_get("/api/sections")
        data = resp.json()
        for sec in data:
            assert sec.get("department_id"), (
                f"Section {sec.get('section_id')} missing department_id"
            )

    def test_section_student_count_non_negative(self):
        """Student count should not be negative."""
        resp = api_get("/api/sections")
        data = resp.json()
        for sec in data:
            count = sec.get("student_count")
            if count is not None:
                assert count >= 0, (
                    f"Section {sec.get('section_id')} has negative student_count: {count}"
                )


class TestSectionUI:
    """UI-level tests for section management."""

    def test_sections_visible_in_crud(self, admin_page):
        """Sections should be visible in the CRUD manager."""
        navigate_to_crud(admin_page, "sections")
        admin_page.wait_for_timeout(1500)
        content = admin_page.inner_text("body")
        assert len(content) > 50, "Sections list is empty"
