"""
conftest.py - Shared Playwright fixtures, constants, and helpers for the QA test suite.
"""
import os
import json
import time
import pytest
import subprocess
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

# ─── Constants ────────────────────────────────────────────────────────────────
BASE_URL = "http://127.0.0.1:5000"
ADMIN_USER = "admin"
ADMIN_PASS = "adminpassword"
HOD_USER = "hod"
HOD_PASS = "hodpassword"
SCREENSHOT_DIR = Path("tests/screenshots")
REPORTS_DIR = Path("tests/reports")

ADMIN_TOKEN = "super-admin-token-12345"
HOD_TOKEN = "hod-token-12345"

# ─── Setup directories ─────────────────────────────────────────────────────────
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Global failure registry (for FAILED_TESTS.md) ────────────────────────────
FAILED_TESTS = []
ALL_TEST_RESULTS = []


def pytest_configure(config):
    """Ensure screenshot/reports dirs exist at configure time."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def pytest_runtest_makereport(item, call):
    """Hook to capture failures and record results."""
    if call.when == "call":
        result = {
            "name": item.name,
            "nodeid": item.nodeid,
            "outcome": call.excinfo is None and "PASSED" or "FAILED",
            "duration": call.duration,
        }
        if call.excinfo:
            result["error"] = str(call.excinfo.value)
            result["traceback"] = str(call.excinfo.traceback)
            FAILED_TESTS.append(result)
        ALL_TEST_RESULTS.append(result)


def pytest_sessionfinish(session, exitstatus):
    """Write all reports after test session ends."""
    _write_test_report()
    _write_failed_tests()


def _write_test_report():
    passed = sum(1 for r in ALL_TEST_RESULTS if r["outcome"] == "PASSED")
    failed = sum(1 for r in ALL_TEST_RESULTS if r["outcome"] == "FAILED")
    total = len(ALL_TEST_RESULTS)
    
    lines = [
        "# E2E QA Test Report\n",
        f"**Total:** {total} | **Passed:** {passed} | **Failed:** {failed}\n\n",
        "| Test | Status | Duration |\n",
        "|------|--------|----------|\n",
    ]
    for r in ALL_TEST_RESULTS:
        emoji = "✅" if r["outcome"] == "PASSED" else "❌"
        lines.append(f"| `{r['nodeid']}` | {emoji} {r['outcome']} | {r.get('duration', 0):.2f}s |\n")
    
    (REPORTS_DIR / "TEST_REPORT.md").write_text("".join(lines), encoding="utf-8")


def _write_failed_tests():
    lines = ["# Failed Tests Detail\n\n"]
    if not FAILED_TESTS:
        lines.append("🎉 **All tests passed!**\n")
    else:
        for r in FAILED_TESTS:
            lines.append(f"## ❌ {r['name']}\n")
            lines.append(f"- **Node:** `{r['nodeid']}`\n")
            lines.append(f"- **Error:** `{r.get('error', 'N/A')}`\n\n")
    (REPORTS_DIR / "FAILED_TESTS.md").write_text("".join(lines), encoding="utf-8")


# ─── Flask Server Fixture ──────────────────────────────────────────────────────
_server_process = None

@pytest.fixture(scope="session", autouse=True)
def flask_server():
    """Start Flask server for the entire test session."""
    global _server_process
    env = os.environ.copy()
    env["FLASK_ENV"] = "testing"
    
    _server_process = subprocess.Popen(
        ["python", "-c",
         "import sys; sys.path.insert(0, '.'); "
         "from app.api.app import create_app; "
         "app = create_app(); "
         "app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)"
         ],
        cwd=str(Path(__file__).parent.parent),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # Wait for server to be ready
    import requests
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/", timeout=2)
            if r.status_code < 500:
                break
        except Exception:
            pass
        time.sleep(1)
    
    yield
    
    if _server_process:
        _server_process.terminate()
        _server_process.wait(timeout=10)


# ─── Playwright Fixtures ───────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def browser_instance():
    """Single browser instance for entire session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
        browser.close()


@pytest.fixture
def page(browser_instance):
    """Fresh page (context) per test."""
    context = browser_instance.new_context(
        viewport={"width": 1280, "height": 900},
        record_video_dir=None,
    )
    context.set_default_timeout(15000)
    pg = context.new_page()
    
    # Collect JS errors
    js_errors = []
    pg.on("pageerror", lambda err: js_errors.append(str(err)))
    pg.js_errors = js_errors
    
    yield pg
    
    pg.close()
    context.close()


@pytest.fixture
def admin_page(page):
    """Page pre-logged-in as Super Admin."""
    page.goto(BASE_URL)
    page.evaluate(f"""
        localStorage.setItem('auth_token', '{ADMIN_TOKEN}');
        localStorage.setItem('auth_role', 'SUPER_ADMIN');
    """)
    page.reload()
    page.wait_for_selector("#view-admin-dashboard:not(.hidden)", timeout=10000)
    return page


@pytest.fixture
def hod_page(page):
    """Page pre-logged-in as HOD."""
    page.goto(BASE_URL)
    page.evaluate(f"""
        localStorage.setItem('auth_token', '{HOD_TOKEN}');
        localStorage.setItem('auth_role', 'HOD');
    """)
    page.reload()
    page.wait_for_selector("#view-hod-dashboard:not(.hidden)", timeout=10000)
    return page


# ─── API Helper ─────────────────────────────────────────────────────────────────
import requests as req_lib

def api_get(path, token=ADMIN_TOKEN):
    """Raw API GET helper."""
    return req_lib.get(f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=10)

def api_post(path, body, token=ADMIN_TOKEN):
    """Raw API POST helper."""
    return req_lib.post(f"{BASE_URL}{path}", json=body, headers={"Authorization": f"Bearer {token}"}, timeout=10)

def api_put(path, body, token=ADMIN_TOKEN):
    """Raw API PUT helper."""
    return req_lib.put(f"{BASE_URL}{path}", json=body, headers={"Authorization": f"Bearer {token}"}, timeout=10)

def api_delete(path, token=ADMIN_TOKEN):
    """Raw API DELETE helper."""
    return req_lib.delete(f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=10)


# ─── Screenshot Helper ──────────────────────────────────────────────────────────
def screenshot_on_failure(page: Page, test_name: str):
    """Save screenshot with timestamped filename."""
    ts = int(time.time())
    path = SCREENSHOT_DIR / f"{test_name}_{ts}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return str(path)
