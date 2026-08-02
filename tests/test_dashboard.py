"""
test_dashboard.py - Tests for Admin and HOD dashboards.
"""
import pytest
from playwright.sync_api import expect
from tests.helpers import (
    navigate_to_dashboard, screenshot, api_get,
    assert_api_ok, ADMIN_TOKEN, HOD_TOKEN
)


class TestAdminDashboard:
    """Tests for the Super Admin dashboard view."""

    def test_admin_dashboard_visible(self, admin_page):
        """Admin dashboard section must be visible after login."""
        expect(admin_page.locator("#view-admin-dashboard")).to_be_visible()

    def test_admin_dashboard_stat_cards_present(self, admin_page):
        """All stat cards should be present on admin dashboard."""
        stat_ids = [
            "stat-admin-depts", "stat-admin-faculty", "stat-admin-courses",
            "stat-admin-rooms", "stat-admin-rules", "stat-admin-students",
            "stat-admin-teachers"
        ]
        for stat_id in stat_ids:
            el = admin_page.locator(f"#{stat_id}")
            expect(el).to_be_visible()

    def test_admin_dashboard_stats_load_non_zero(self, admin_page):
        """At least some stats should be non-zero (database has seed data)."""
        admin_page.wait_for_timeout(2000)
        faculty_count = admin_page.locator("#stat-admin-faculty").inner_text()
        assert faculty_count.strip() != "0", "Faculty count should be non-zero"

    def test_admin_dashboard_quick_actions_visible(self, admin_page):
        """Quick Action buttons should be visible."""
        expect(admin_page.locator("button:has-text('Manage Database Entities')")).to_be_visible()
        expect(admin_page.locator("button:has-text('Define Scheduling Constraints')")).to_be_visible()

    def test_admin_quick_action_to_crud(self, admin_page):
        """Clicking 'Manage Database Entities' navigates to CRUD."""
        admin_page.click("button:has-text('Manage Database Entities')")
        admin_page.wait_for_selector("#view-crud-manager:not(.hidden)", timeout=8000)
        expect(admin_page.locator("#view-crud-manager")).to_be_visible()

    def test_admin_quick_action_to_rules(self, admin_page):
        """Clicking 'Define Scheduling Constraints' navigates to Rules."""
        admin_page.click("button:has-text('Define Scheduling Constraints')")
        admin_page.wait_for_selector("#view-rule-builder:not(.hidden)", timeout=8000)
        expect(admin_page.locator("#view-rule-builder")).to_be_visible()

    def test_api_dashboard_stats_endpoint(self):
        """Dashboard stats API returns valid data structure."""
        resp = api_get("/api/dashboard/stats")
        assert_api_ok(resp, "Dashboard stats")
        data = resp.json()
        assert "faculty_count" in data
        assert "course_count" in data
        assert "department_count" in data
        assert "room_count" in data
        assert "section_count" in data
        assert isinstance(data["faculty_count"], int)

    def test_api_dashboard_stats_counts_positive(self):
        """Dashboard stats should return non-negative counts."""
        resp = api_get("/api/dashboard/stats")
        data = resp.json()
        for key in ["faculty_count", "course_count", "room_count"]:
            assert data.get(key, -1) >= 0, f"{key} should be non-negative"


class TestHODDashboard:
    """Tests for the HOD dashboard view."""

    def test_hod_dashboard_visible(self, hod_page):
        """HOD dashboard section must be visible after login."""
        expect(hod_page.locator("#view-hod-dashboard")).to_be_visible()

    def test_hod_dashboard_stat_cards_present(self, hod_page):
        """All HOD stat cards should be present."""
        stat_ids = [
            "stat-hod-faculty", "stat-hod-courses", "stat-hod-rooms",
            "stat-hod-sections", "stat-hod-students", "stat-hod-teachers"
        ]
        for stat_id in stat_ids:
            el = hod_page.locator(f"#{stat_id}")
            expect(el).to_be_visible()

    def test_hod_dashboard_sections_table_loads(self, hod_page):
        """HOD dashboard should show sections status table."""
        hod_page.wait_for_timeout(2000)
        tbody = hod_page.locator("#hod-sections-tbody")
        expect(tbody).to_be_visible()
        # Should have at least one row
        rows = tbody.locator("tr").all()
        assert len(rows) >= 1, "HOD dashboard should have at least 1 section row"

    def test_hod_sections_status_api(self):
        """HOD sections status API returns list of section data."""
        resp = api_get("/api/hod/sections-status", token=HOD_TOKEN)
        assert_api_ok(resp, "HOD sections status")
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            sec = data[0]
            assert "section_id" in sec
            assert "section_name" in sec
            assert "status" in sec

    def test_hod_dashboard_has_navigation_buttons(self, hod_page):
        """HOD dashboard navigation buttons should be accessible."""
        nav_btns = ["nav-dashboard-btn", "nav-crud-btn", "nav-timetable-btn", "nav-rules-btn"]
        for btn_id in nav_btns:
            btn = hod_page.locator(f"#{btn_id}")
            expect(btn).to_be_visible()

    def test_hod_can_navigate_to_timetable(self, hod_page):
        """HOD can navigate to the timetable planner."""
        hod_page.click("#nav-timetable-btn")
        hod_page.wait_for_selector("#view-timetable-planner:not(.hidden)", timeout=8000)
        expect(hod_page.locator("#view-timetable-planner")).to_be_visible()

    def test_hod_cannot_create_entities_via_api(self):
        """HOD token should be rejected for admin-only create operations."""
        import requests
        resp = requests.post(
            f"http://127.0.0.1:5000/api/departments",
            json={"department_id": "XYZ99", "department_name": "Hack Dept"},
            headers={"Authorization": f"Bearer {HOD_TOKEN}"},
            timeout=10
        )
        assert resp.status_code == 403, f"HOD should be forbidden from admin routes, got {resp.status_code}"
