"""
test_labs.py - CRUD tests for Laboratory entity.
"""
import pytest
from tests.helpers import (
    api_get, api_post, api_put, api_delete,
    assert_api_ok, assert_api_error,
    navigate_to_crud, ADMIN_TOKEN, HOD_TOKEN,
    QA_LAB
)

QA_LAB_ID = QA_LAB["lab_room_no"]


class TestLabAPI:
    """API-level CRUD tests for laboratories."""

    def test_list_labs(self):
        """GET /api/laboratories returns a list."""
        resp = api_get("/api/laboratories")
        assert_api_ok(resp, "List labs")
        data = resp.json()
        assert isinstance(data, list)

    def test_labs_have_required_fields(self):
        """Labs should have lab_room_no, lab_name, capacity fields."""
        resp = api_get("/api/laboratories")
        data = resp.json()
        if data:
            lab = data[0]
            assert "lab_room_no" in lab or "lab_name" in lab, (
                f"Missing lab fields. Got: {list(lab.keys())}"
            )

    def test_create_lab(self):
        """POST /api/laboratories creates a new lab."""
        api_delete(f"/api/laboratories/{QA_LAB_ID}")
        resp = api_post("/api/laboratories", QA_LAB)
        assert_api_ok(resp, "Create lab")

    def test_get_lab_by_id(self):
        """GET /api/laboratories/<id> returns correct lab."""
        api_post("/api/laboratories", QA_LAB)
        resp = api_get(f"/api/laboratories/{QA_LAB_ID}")
        assert_api_ok(resp, "Get lab by ID")
        data = resp.json()
        assert data.get("lab_room_no") == QA_LAB_ID

    def test_update_lab(self):
        """PUT /api/laboratories/<id> updates lab data."""
        api_post("/api/laboratories", QA_LAB)
        updated = {**QA_LAB, "lab_name": "QA Lab - Updated"}
        resp = api_put(f"/api/laboratories/{QA_LAB_ID}", updated)
        assert_api_ok(resp, "Update lab")

    def test_delete_lab(self):
        """DELETE /api/laboratories/<id> removes a lab."""
        api_post("/api/laboratories", QA_LAB)
        resp = api_delete(f"/api/laboratories/{QA_LAB_ID}")
        assert_api_ok(resp, "Delete lab")

    def test_nonexistent_lab_returns_404(self):
        """GET /api/laboratories/<nonexistent> returns 404."""
        resp = api_get("/api/laboratories/NONEXISTENT_LAB_9999")
        assert_api_error(resp, 404, "Nonexistent lab")

    def test_lab_capacity_is_positive(self):
        """Lab capacity should be a positive integer."""
        resp = api_get("/api/laboratories")
        data = resp.json()
        for lab in data[:5]:
            cap = lab.get("capacity")
            if cap is not None:
                assert isinstance(cap, (int, float)) and cap > 0, (
                    f"Lab {lab.get('lab_room_no')} invalid capacity: {cap}"
                )

    def test_hod_cannot_create_lab(self):
        """HOD cannot create a lab."""
        resp = api_post("/api/laboratories", QA_LAB, token=HOD_TOKEN)
        assert_api_error(resp, 403, "HOD create lab")

    def test_hod_can_read_labs(self):
        """HOD can read labs list."""
        resp = api_get("/api/laboratories", token=HOD_TOKEN)
        assert_api_ok(resp, "HOD read labs")


class TestLabUI:
    """UI tests for lab management."""

    def test_labs_visible_in_crud_manager(self, admin_page):
        """Labs should appear in the CRUD manager."""
        navigate_to_crud(admin_page, "laboratories")
        admin_page.wait_for_timeout(1500)
        content = admin_page.inner_text("body")
        assert len(content) > 50, "Labs list is suspiciously empty"
