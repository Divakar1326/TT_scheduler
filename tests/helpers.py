"""
helpers.py - Reusable helper utilities for the QA test suite.
"""
import time
import json
from pathlib import Path
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:5000"
SCREENSHOT_DIR = Path("tests/screenshots")


# ─── Navigation Helpers ────────────────────────────────────────────────────────
def navigate_to_crud(page: Page, entity: str):
    """Navigate to CRUD page and select an entity from the dropdown."""
    page.click("#nav-crud-btn")
    page.wait_for_selector("#view-crud-manager:not(.hidden)", timeout=8000)
    sel = page.query_selector("#crud-entity-select")
    if sel:
        sel.select_option(entity)
    else:
        # Try button-based entity selector
        page.evaluate(f"changeCRUDEntity('{entity}')")
    page.wait_for_timeout(800)


def navigate_to_timetable(page: Page):
    """Navigate to timetable view."""
    page.click("#nav-timetable-btn")
    page.wait_for_selector("#view-timetable-planner:not(.hidden)", timeout=8000)
    page.wait_for_timeout(500)


def navigate_to_rules(page: Page):
    """Navigate to rule builder view."""
    page.click("#nav-rules-btn")
    page.wait_for_selector("#view-rule-builder:not(.hidden)", timeout=8000)
    page.wait_for_timeout(500)


def navigate_to_dashboard(page: Page):
    """Navigate to dashboard."""
    page.click("#nav-dashboard-btn")
    page.wait_for_timeout(1000)


# ─── Modal Helpers ─────────────────────────────────────────────────────────────
def open_modal(page: Page, modal_id: str):
    """Open a modal by ID via JS."""
    page.evaluate(f"openModal('{modal_id}')")
    page.wait_for_selector(f"#{modal_id}:not(.hidden)", timeout=5000)


def close_modal(page: Page, modal_id: str):
    """Close a modal by ID via JS."""
    page.evaluate(f"closeModal('{modal_id}')")


# ─── Form Fill Helpers ─────────────────────────────────────────────────────────
def fill_form_field(page: Page, selector: str, value: str):
    """Fill a form field, clearing existing value first."""
    el = page.query_selector(selector)
    if el:
        el.click()
        el.fill("")
        el.type(str(value), delay=20)
    else:
        raise AssertionError(f"Field not found: {selector}")


# ─── Screenshot Helper ──────────────────────────────────────────────────────────
def screenshot(page: Page, name: str) -> str:
    """Take a full-page screenshot."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    path = SCREENSHOT_DIR / f"{name}_{ts}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


# ─── API Request Helpers ────────────────────────────────────────────────────────
import requests

ADMIN_TOKEN = "super-admin-token-12345"
HOD_TOKEN = "hod-token-12345"


def api(method: str, path: str, body=None, token=ADMIN_TOKEN, timeout=15):
    """Generic API request helper."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{path}"
    resp = getattr(requests, method.lower())(
        url, json=body, headers=headers, timeout=timeout
    )
    return resp


def api_get(path, token=ADMIN_TOKEN):
    return api("GET", path, token=token)


def api_post(path, body=None, token=ADMIN_TOKEN):
    return api("POST", path, body=body, token=token)


def api_put(path, body=None, token=ADMIN_TOKEN):
    return api("PUT", path, body=body, token=token)


def api_delete(path, token=ADMIN_TOKEN):
    return api("DELETE", path, token=token)


# ─── Wait for toast ─────────────────────────────────────────────────────────────
def wait_for_toast(page: Page, text_fragment: str = None, timeout: int = 5000):
    """Wait for a toast notification to appear."""
    try:
        if text_fragment:
            page.wait_for_selector(
                f".toast:has-text('{text_fragment}')", timeout=timeout
            )
        else:
            page.wait_for_selector(".toast", timeout=timeout)
        return True
    except Exception:
        return False


# ─── Assertion helpers ──────────────────────────────────────────────────────────
def assert_api_ok(response, msg=""):
    assert response.status_code in (200, 201), (
        f"{msg} Expected 200/201, got {response.status_code}: {response.text[:300]}"
    )


def assert_api_error(response, expected_code: int, msg=""):
    assert response.status_code == expected_code, (
        f"{msg} Expected {expected_code}, got {response.status_code}: {response.text[:300]}"
    )


def assert_page_has_no_js_errors(page: Page):
    errors = getattr(page, "js_errors", [])
    # Filter out known acceptable warnings
    real_errors = [e for e in errors if "favicon" not in e.lower()]
    assert not real_errors, f"JavaScript errors on page: {real_errors}"


def assert_no_console_errors(page: Page):
    """Check page has no console errors (collected via page.on('pageerror'))."""
    assert_page_has_no_js_errors(page)


# ─── CRUD entity payloads ───────────────────────────────────────────────────────
QA_DEPT = {
    "department_id": "QAD",
    "department_name": "QA Test Department",
}

QA_FACULTY = {
    "faculty_id": "QAF01",
    "faculty_name": "QA Faculty Member",
    "max_hours_week": 20,
    "email": "qafac@test.edu",
    "status": "ACTIVE",
}

QA_COURSE = {
    "course_id": "QASC01",
    "course_name": "QA Test Course",
    "l": 2,
    "t": 0,
    "p": 0,
    "c": 2,
    "difficulty": 1,
    "semester": 7,
    "has_lab": False,
    "weekly_hours": 2,
}

QA_ROOM = {
    "room_no": "QAROOM01",
    "department_id": "ISC",
    "capacity": 60,
}

QA_LAB = {
    "lab_room_no": "QALAB01",
    "lab_name": "QA Test Lab",
    "capacity": 30,
    "department_id": "ISC",
}

QA_SECTION = {
    "section_id": "QAS01",
    "section_name": "QA Section A",
    "semester": 7,
    "department_id": "ISC",
    "capacity": 30,
}

QA_RULE = {
    "rule_id": "QA_RULE_01",
    "rule_name": "QA Test Rule - No Friday classes",
    "original_text": "No classes should be scheduled on Friday afternoons",
    "generated_json": json.dumps({"avoid_days": [5], "avoid_periods": [5, 6, 7]}),
    "priority": 5,
    "type": "SOFT",
    "parameter": json.dumps({"avoid_days": [5], "avoid_periods": [5, 6, 7]}),
    "enabled": True,
    "cost": 0,
}
