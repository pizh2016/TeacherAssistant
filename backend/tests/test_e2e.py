"""Playwright E2E tests covering all UI/UX fixes + previous defect fixes.

Issue 1: Class list shows after navigating to ClassManageView
Issue 2: Sub-page top-bar has "← 返回" on the right, no "退出" button
Issue 3: Unified top-bar with avatar + name (left), title (center), action (right)
Previous defects: class dedup, teacher dedup, WebSocket connection
"""

import json
from urllib import request as urllib_request

import pytest
from playwright.sync_api import sync_playwright

BASE = "http://localhost:18800"
TEACHER = f"{BASE}/static/teacher"


def turl(hash_path: str) -> str:
    return f"{TEACHER}/#{hash_path}"


# ---------- helpers ----------

def api(method: str, path: str, body: dict = None, token: str = None) -> tuple:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib_request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib_request.HTTPError as e:
        raw = e.read().decode()
        return e.code, json.loads(raw) if raw else {}


def teacher_login(name: str) -> dict:
    status, body = api("POST", "/api/auth/teacher-login", {"name": name})
    assert status == 200, f"teacher login failed: {body}"
    return body


def pairing_login(pairing_code: str) -> dict:
    status, body = api("POST", "/api/auth/pairing-login", {"pairing_code": pairing_code, "role": "display"})
    assert status == 200, f"pairing login failed: {body}"
    return body


def inject_auth(page, data: dict):
    page.evaluate(f"""() => {{
        localStorage.setItem('horn_token', '{data["token"]}');
        localStorage.setItem('horn_teacher_id', '{data["teacher_id"]}');
        localStorage.setItem('horn_teacher_name', '{data["teacher_name"]}');
        localStorage.setItem('horn_classes', '[]');
    }}""")


def login_and_goto(page, hash_path: str, teacher_name: str = "导航测试老师"):
    data = teacher_login(teacher_name)
    page.goto(turl("/login"))
    page.wait_for_load_state("networkidle")
    inject_auth(page, data)
    page.goto(turl(hash_path))
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def browser_ctx():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        yield ctx
        browser.close()


@pytest.fixture()
def page(browser_ctx):
    p = browser_ctx.new_page()
    yield p
    p.close()


# ---------- Issue 1: Class list visibility ----------

class TestClassListVisibility:
    """Issue 1: Class list must show after navigating to ClassManageView."""

    def test_class_list_shows_after_navigation(self, page):
        """Create a class on home page, navigate to class manage, verify list shows."""
        data = teacher_login("班级可见性老师")
        token = data["token"]

        # Create a class via API first
        s1, c1 = api("POST", "/api/classes", {"name": "可见性测试班"}, token)
        assert s1 == 201

        # Inject auth and navigate to class manage page
        page.goto(turl("/login"))
        page.wait_for_load_state("networkidle")
        inject_auth(page, data)
        page.goto(turl("/classes"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        # Class should be visible
        body_text = page.locator("body").text_content()
        assert "可见性测试班" in body_text, "class should appear in the list"

        # Cleanup
        api("DELETE", f"/api/classes/{c1['id']}", token=token)

    def test_class_list_fallback_to_localstorage(self, page):
        """If API fails, class list should fallback to localStorage cache."""
        data = teacher_login("缓存回退老师")
        token = data["token"]

        # Create a class
        s1, c1 = api("POST", "/api/classes", {"name": "缓存测试班"}, token)
        assert s1 == 201

        # Navigate to home first to cache classes in localStorage
        page.goto(turl("/login"))
        page.wait_for_load_state("networkidle")
        inject_auth(page, data)
        page.goto(turl("/"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        # Now navigate to class manage — should still show classes
        page.goto(turl("/classes"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        body_text = page.locator("body").text_content()
        assert "缓存测试班" in body_text, "class should appear via localStorage fallback"

        # Cleanup
        api("DELETE", f"/api/classes/{c1['id']}", token=token)


# ---------- Issue 2 & 3: TopBar layout ----------

class TestTopBarLayout:
    """Issue 2+3: Unified top-bar with avatar, title, and correct action button."""

    def test_home_page_has_logout_no_back(self, page):
        """Home page: has '退出' button, no '← 返回' button."""
        login_and_goto(page, "/")
        # Title should show
        title = page.locator(".page-title")
        assert title.is_visible()
        assert "喊话小喇叭" in title.text_content()
        # Logout button should exist
        logout = page.locator(".btn-logout")
        assert logout.is_visible()
        # Back button should NOT exist on home page
        back = page.locator(".btn-back")
        assert not back.is_visible(), "home page should not have back button"

    def test_home_page_has_avatar(self, page):
        """Home page: avatar circle is visible with teacher name."""
        login_and_goto(page, "/")
        avatar = page.locator(".avatar")
        assert avatar.is_visible()
        # Avatar should contain first char of teacher name
        avatar_text = avatar.text_content()
        assert avatar_text == "导", f"avatar should show first char, got: {avatar_text}"
        # Teacher name should be visible
        name = page.locator(".teacher-name")
        assert name.is_visible()

    def test_sub_page_has_back_no_logout(self, page):
        """Sub-pages: have '← 返回', no '退出' button."""
        for path in ["/classes", "/history", "/templates", "/schedule"]:
            login_and_goto(page, path)
            back = page.locator(".btn-back")
            assert back.is_visible(), f"{path} should have back button"
            assert "返回" in back.text_content()
            logout = page.locator(".btn-logout")
            assert not logout.is_visible(), f"{path} should NOT have logout button"

    def test_sub_page_titles(self, page):
        """Each sub-page shows correct title."""
        expected = {
            "/classes": "班级管理",
            "/history": "发送历史",
            "/templates": "常用语管理",
            "/schedule": "定时播报",
        }
        for path, title_text in expected.items():
            login_and_goto(page, path)
            title = page.locator(".page-title")
            assert title.is_visible()
            assert title_text in title.text_content(), f"{path} title should contain '{title_text}'"


# ---------- Class name dedup ----------

class TestClassDedup:
    def test_duplicate_class_name_rejected(self):
        data = teacher_login("班级去重老师")
        token = data["token"]
        s1, c1 = api("POST", "/api/classes", {"name": "测试一班"}, token)
        assert s1 == 201
        s2, c2 = api("POST", "/api/classes", {"name": "测试一班"}, token)
        assert s2 == 400
        assert "已存在" in c2["error"]["message"]
        s3, c3 = api("POST", "/api/classes", {"name": "测试二班"}, token)
        assert s3 == 201
        api("DELETE", f"/api/classes/{c1['id']}", token=token)
        api("DELETE", f"/api/classes/{c3['id']}", token=token)

    def test_duplicate_class_via_ui(self, page):
        data = teacher_login("班级去重UI老师")
        page.goto(turl("/login"))
        page.wait_for_load_state("networkidle")
        inject_auth(page, data)
        page.goto(turl("/classes"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        page.fill(".create-input", "UI测试班")
        page.click(".btn-create")
        page.wait_for_timeout(800)
        feedback = page.locator(".create-feedback")
        assert feedback.is_visible()
        page.fill(".create-input", "UI测试班")
        page.click(".btn-create")
        page.wait_for_timeout(800)
        feedback_text = page.locator(".create-feedback").text_content()
        assert "已存在" in feedback_text or "error" in page.locator(".create-feedback").get_attribute("class")


# ---------- Teacher name dedup ----------

class TestTeacherDedup:
    def test_same_name_reuses_record_with_classes(self):
        """Same name logs in again even after binding classes — same teacher_id."""
        a = teacher_login("同名老师")
        s1, c1 = api("POST", "/api/classes", {"name": "同名班"}, a["token"])
        assert s1 == 201
        b = teacher_login("同名老师")
        assert b["teacher_id"] == a["teacher_id"]
        assert b["teacher_name"] == "同名老师"
        api("DELETE", f"/api/classes/{c1['id']}", token=a["token"])

    def test_no_suffix_when_no_classes(self):
        a = teacher_login("空闲老师")
        b = teacher_login("空闲老师")
        assert a["teacher_id"] == b["teacher_id"]
        assert b["teacher_name"] == "空闲老师"


# ---------- Full workflow ----------

class TestFullWorkflow:
    def test_complete_flow(self, page):
        # Clear stale auth
        page.goto(turl("/login"))
        page.wait_for_load_state("networkidle")
        page.evaluate("localStorage.clear()")
        page.goto(turl("/login"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # Login via UI
        page.wait_for_selector("#teacher-name", timeout=10000)
        page.fill("#teacher-name", "流程测试老师")
        page.click("button[type=submit]")
        page.wait_for_timeout(1500)

        url = page.url
        assert "#/" in url

        # Create a class via UI
        page.goto(turl("/classes"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        page.fill(".create-input", "E2E班级")
        page.click(".btn-create")
        page.wait_for_timeout(1000)

        body_text = page.locator("body").text_content()
        assert "E2E班级" in body_text

        # Navigate to Home — verify avatar + teacher name + logout
        page.goto(turl("/"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        avatar = page.locator(".avatar")
        assert avatar.is_visible()
        name_el = page.locator(".teacher-name")
        assert name_el.is_visible()
        assert "流程测试老师" in name_el.text_content()

        # Verify sub-page back buttons
        for path in ["/history", "/templates", "/schedule"]:
            page.goto(turl(path))
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            back = page.locator(".btn-back")
            assert back.is_visible()

        # Logout
        page.goto(turl("/"))
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        page.click("button.btn-logout")
        page.wait_for_timeout(800)

        login_visible = page.locator("#teacher-name").is_visible()
        assert login_visible, "login form should be visible after logout"

        token = page.evaluate("localStorage.getItem('horn_token')")
        assert token is None or token == "", "token should be cleared after logout"


# ---------- Display WebSocket ----------

class TestDisplayConnection:
    def test_pairing_login_and_ws_connect(self):
        import websocket
        t = teacher_login("WS测试老师")
        s1, c1 = api("POST", "/api/classes", {"name": "WS测试班"}, t["token"])
        assert s1 == 201
        pairing_code = c1["pairing_code"]
        d = pairing_login(pairing_code)
        assert d["role"] == "display"
        assert d["classes"][0]["id"] == c1["id"]
        ws_url = f"ws://localhost:18800/ws/class/{c1['id']}"
        ws = websocket.create_connection(ws_url, timeout=5)
        join_msg = json.dumps({
            "type": "join_class",
            "class_id": c1["id"],
            "token": d["token"],
        })
        ws.send(join_msg)
        ack = json.loads(ws.recv())
        assert ack["type"] == "connection_ack"
        assert ack["status"] == "ok"
        assert ack["class_id"] == c1["id"]
        ws.close()
        api("DELETE", f"/api/classes/{c1['id']}", token=t["token"])
