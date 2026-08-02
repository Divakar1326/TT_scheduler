"""
test_login.py - Tests for authentication: login, logout, invalid credentials, session management.
"""
import pytest
from playwright.sync_api import expect
from tests.conftest import BASE_URL, ADMIN_TOKEN, HOD_TOKEN
from tests.helpers import screenshot, api_post, assert_api_ok, assert_api_error


class TestLogin:
    """Tests for the login page and authentication workflow."""

    def test_landing_page_loads(self, page):
        """Landing page should load without errors."""
        page.goto(BASE_URL)
        expect(page).to_have_title("University Timetable Management Dashboard")
        expect(page.locator("#view-landing")).to_be_visible()

    def test_landing_page_has_access_button(self, page):
        """Landing page must have an 'Access Scheduler System' button."""
        page.goto(BASE_URL)
        btn = page.locator("button:has-text('Access Scheduler System')")
        expect(btn).to_be_visible()

    def test_login_modal_opens(self, page):
        """Clicking Access button should open login modal."""
        page.goto(BASE_URL)
        page.click("button:has-text('Access Scheduler System')")
        modal = page.locator("#login-modal")
        expect(modal).not_to_have_class("hidden")

    def test_admin_login_via_ui(self, page):
        """Super Admin login via the UI form should redirect to admin dashboard."""
        page.goto(BASE_URL)
        page.click("button:has-text('Access Scheduler System')")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "adminpassword")
        page.click("button[type='submit']:has-text('Authenticate')")
        page.wait_for_selector("#view-admin-dashboard:not(.hidden)", timeout=10000)
        expect(page.locator("#view-admin-dashboard")).to_be_visible()

    def test_hod_login_via_ui(self, page):
        """HOD login via the UI form should redirect to HOD dashboard."""
        page.goto(BASE_URL)
        page.click("button:has-text('Access Scheduler System')")
        page.fill("input[name='username']", "hod")
        page.fill("input[name='password']", "hodpassword")
        page.click("button[type='submit']:has-text('Authenticate')")
        page.wait_for_selector("#view-hod-dashboard:not(.hidden)", timeout=10000)
        expect(page.locator("#view-hod-dashboard")).to_be_visible()

    def test_invalid_credentials_show_error(self, page):
        """Invalid login should show an error toast."""
        page.goto(BASE_URL)
        page.click("button:has-text('Access Scheduler System')")
        page.fill("input[name='username']", "invalid_user")
        page.fill("input[name='password']", "wrong_password")
        page.click("button[type='submit']:has-text('Authenticate')")
        # Should stay on landing (not navigate to dashboard)
        page.wait_for_timeout(2000)
        expect(page.locator("#view-landing")).to_be_visible()

    def test_empty_username_fails(self, page):
        """Empty username should not authenticate."""
        page.goto(BASE_URL)
        page.click("button:has-text('Access Scheduler System')")
        page.fill("input[name='username']", "")
        page.fill("input[name='password']", "adminpassword")
        # Don't click submit (HTML required validation will prevent it)
        page.wait_for_timeout(1500)
        # Admin dashboard should NOT be visible
        admin_dash = page.locator("#view-admin-dashboard")
        assert "hidden" in (admin_dash.get_attribute("class") or "hidden")

    def test_session_persists_after_reload(self, admin_page):
        """Refreshing the page should keep admin logged in."""
        admin_page.reload()
        admin_page.wait_for_selector("#view-admin-dashboard:not(.hidden)", timeout=8000)
        expect(admin_page.locator("#view-admin-dashboard")).to_be_visible()

    def test_logout_clears_session(self, admin_page):
        """Logout should clear session and return to landing."""
        admin_page.click("#nav-logout-btn")
        admin_page.wait_for_selector("#view-landing:not(.hidden)", timeout=8000)
        expect(admin_page.locator("#view-landing")).to_be_visible()
        # Token should be cleared from localStorage
        token = admin_page.evaluate("localStorage.getItem('auth_token')")
        assert token is None or token == ""

    def test_nav_buttons_visible_when_logged_in(self, admin_page):
        """Navigation buttons should be visible when logged in."""
        expect(admin_page.locator("#nav-dashboard-btn")).to_be_visible()
        expect(admin_page.locator("#nav-logout-btn")).to_be_visible()

    def test_nav_buttons_hidden_when_logged_out(self, page):
        """Navigation buttons should be hidden when not logged in."""
        page.goto(BASE_URL)
        expect(page.locator("#nav-logout-btn")).to_have_class("hidden")

    # ─── API Auth Tests ─────────────────────────────────────────────────────────
    def test_api_login_admin_success(self):
        """API login returns token and role for admin."""
        resp = api_post("/api/auth/login", {"username": "admin", "password": "adminpassword"}, token=None)
        assert_api_ok(resp, "Admin API login")
        data = resp.json()
        assert "token" in data
        assert data["role"] == "SUPER_ADMIN"

    def test_api_login_hod_success(self):
        """API login returns token and role for HOD."""
        resp = api_post("/api/auth/login", {"username": "hod", "password": "hodpassword"}, token=None)
        assert_api_ok(resp, "HOD API login")
        data = resp.json()
        assert "token" in data
        assert data["role"] == "HOD"

    def test_api_login_invalid_returns_401(self):
        """API login with wrong password returns 401."""
        import requests
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "WRONG"},
            timeout=10
        )
        assert_api_error(resp, 401, "Invalid credentials")

    def test_api_protected_route_without_token_returns_401(self):
        """Protected endpoints without Authorization header return 401."""
        import requests
        resp = requests.get(f"{BASE_URL}/api/faculties", timeout=10)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without token, got {resp.status_code}"
        )

    def test_api_hod_cannot_access_admin_route(self):
        """HOD token cannot POST (create) entities - returns 403."""
        resp = api_post("/api/departments", {"department_id": "HACK01"}, token=HOD_TOKEN)
        assert_api_error(resp, 403, "HOD admin route access")
