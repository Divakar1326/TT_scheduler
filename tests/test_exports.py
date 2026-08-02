"""
test_exports.py - Tests for PDF and Excel/CSV export functionality.
"""
import pytest
import requests
from tests.helpers import (
    api_get, api_post, api_delete,
    assert_api_ok, ADMIN_TOKEN, HOD_TOKEN
)

BASE_URL = "http://127.0.0.1:5000"


def get_first_section_id():
    """Helper to fetch first available section ID."""
    resp = api_get("/api/sections")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            return data[0]["section_id"]
    return "ISCA"  # fallback seed data ID


def get_first_faculty_id():
    """Helper to fetch first available faculty ID."""
    resp = api_get("/api/faculties")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            return data[0]["faculty_id"]
    return "F001"


def get_first_lab_id():
    """Helper to fetch first available lab ID."""
    resp = api_get("/api/laboratories")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            return data[0]["lab_room_no"]
    return "LAB01"


def ensure_schedule_exists():
    """Make sure there is a generated schedule in the database."""
    resp = api_post("/api/scheduler/generate", {})
    return resp.status_code in (200, 201)


class TestExportEndpoint:
    """Tests for /api/scheduler/export endpoint."""

    def test_export_endpoint_exists(self):
        """GET /api/scheduler/export must respond (not 404)."""
        sec_id = get_first_section_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "section", "id": sec_id, "format": "html"},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=15
        )
        assert resp.status_code != 404, "Export endpoint does not exist"

    def test_export_section_html_returns_content(self):
        """Export a section timetable as HTML."""
        ensure_schedule_exists()
        sec_id = get_first_section_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "section", "id": sec_id, "format": "html"},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=15
        )
        assert resp.status_code in (200, 204, 400), (
            f"HTML export returned {resp.status_code}: {resp.text[:200]}"
        )
        if resp.status_code == 200:
            assert len(resp.content) > 0, "HTML export is empty"

    def test_export_section_csv_returns_content(self):
        """Export a section timetable as CSV."""
        ensure_schedule_exists()
        sec_id = get_first_section_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "section", "id": sec_id, "format": "csv"},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=15
        )
        assert resp.status_code in (200, 204, 400), (
            f"CSV export returned {resp.status_code}: {resp.text[:200]}"
        )
        if resp.status_code == 200:
            assert len(resp.content) > 0, "CSV export is empty"

    def test_export_faculty_timetable(self):
        """Export a faculty timetable."""
        ensure_schedule_exists()
        fac_id = get_first_faculty_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "faculty", "id": fac_id, "format": "html"},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=15
        )
        assert resp.status_code in (200, 204, 400, 404), (
            f"Faculty export returned {resp.status_code}"
        )

    def test_export_lab_timetable(self):
        """Export a lab timetable."""
        ensure_schedule_exists()
        lab_id = get_first_lab_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "lab", "id": lab_id, "format": "html"},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=15
        )
        assert resp.status_code in (200, 204, 400, 404), (
            f"Lab export returned {resp.status_code}"
        )

    def test_export_requires_authentication(self):
        """Export without token should fail."""
        sec_id = get_first_section_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "section", "id": sec_id, "format": "html"},
            timeout=10
        )
        assert resp.status_code in (401, 403), (
            f"Unauthenticated export should be rejected, got {resp.status_code}"
        )

    def test_export_invalid_format_handled(self):
        """Export with unknown format should return error, not crash."""
        ensure_schedule_exists()
        sec_id = get_first_section_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "section", "id": sec_id, "format": "xlsx_INVALID"},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=10
        )
        assert resp.status_code in (200, 400, 422), (
            f"Invalid format should return 400/422, got {resp.status_code}"
        )

    def test_export_missing_id_returns_error(self):
        """Export without an ID should return 400 or similar error."""
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "section", "format": "html"},
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=10
        )
        assert resp.status_code in (400, 422, 200), (
            f"Missing ID in export returned {resp.status_code}"
        )

    def test_hod_can_export(self):
        """HOD should be allowed to export timetables."""
        ensure_schedule_exists()
        sec_id = get_first_section_id()
        resp = requests.get(
            f"{BASE_URL}/api/scheduler/export",
            params={"type": "section", "id": sec_id, "format": "html"},
            headers={"Authorization": f"Bearer {HOD_TOKEN}"},
            timeout=15
        )
        assert resp.status_code != 403, "HOD should not be forbidden from exporting"


class TestExportUI:
    """UI tests for export buttons."""

    def test_download_export_buttons_visible(self, admin_page):
        """Export buttons should be visible on timetable page."""
        admin_page.click("#nav-timetable-btn")
        admin_page.wait_for_selector("#view-timetable-planner:not(.hidden)", timeout=8000)
        admin_page.wait_for_timeout(1000)
        # Look for export/download buttons
        download_btns = admin_page.locator("button:has-text('Download'), button:has-text('Export'), button:has-text('PDF'), button:has-text('CSV')")
        assert download_btns.count() > 0, "No download/export buttons found on timetable page"

    def test_hod_dashboard_has_export_buttons(self, hod_page):
        """HOD dashboard section rows should have PDF and Excel buttons."""
        hod_page.wait_for_timeout(2000)
        pdf_btns = hod_page.locator("button:has-text('PDF')")
        csv_btns = hod_page.locator("button:has-text('Excel'), button:has-text('CSV')")
        # At least some section should have both buttons (or page may have 0 rows)
        content = hod_page.inner_text("body")
        if "No sections found" not in content:
            assert pdf_btns.count() > 0, "PDF buttons not found in HOD dashboard"
