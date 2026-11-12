"""REST API contract tests (docs/02 §4) — Phase 2 updated.

Tests cover: teacher name login, pairing login (display-only), batch send,
message recall, image upload, scheduled messages, templates, audit/export.
"""

from conftest import auth_headers, login, teacher_login_by_name, setup_teacher_with_class, refresh_teacher_token


# ---- System ----

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "timestamp" in body
    assert "version" in body


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---- Auth ----

def test_teacher_name_login(client):
    """Teacher logs in by name, auto-registered on first use."""
    data = teacher_login_by_name(client, "王老师")
    assert data["role"] == "teacher"
    assert isinstance(data["teacher_id"], int)
    assert data["token"]
    assert isinstance(data["classes"], list)


def test_teacher_name_login_repeat(client):
    """Same name logs in again — returns the same teacher record."""
    d1 = teacher_login_by_name(client, "李老师")
    d2 = teacher_login_by_name(client, "李老师")
    assert d1["teacher_id"] == d2["teacher_id"]


def test_pairing_login_display(client):
    data = login(client, "123456", "display")
    assert data["role"] == "display"
    assert data["teacher_id"] is None
    assert len(data["classes"]) == 1


def test_pairing_login_teacher_rejected(client):
    """Phase 2: Teacher role via pairing code is rejected."""
    r = client.post(
        "/api/auth/pairing-login",
        json={"pairing_code": "123456", "role": "teacher"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CLASS_FORBIDDEN"


def test_pairing_login_invalid_code(client):
    r = client.post("/api/auth/pairing-login", json={"pairing_code": "000000", "role": "display"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "PAIRING_CODE_INVALID"


def test_pairing_login_bad_format(client):
    r = client.post("/api/auth/pairing-login", json={"pairing_code": "12ab", "role": "display"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- Classes ----

def test_classes_requires_auth(client):
    r = client.get("/api/classes")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "TOKEN_MISSING"


def test_classes_with_auth(client):
    t = setup_teacher_with_class(client)
    r = client.get("/api/classes", headers=auth_headers(t["token"]))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    assert data[0]["name"] == "测试班级"


# ---- Messages ----

def test_send_and_history_and_latest(client):
    t = setup_teacher_with_class(client)
    cid = t["class_id"]
    h = auth_headers(t["token"])

    r = client.post(
        "/api/messages",
        headers=h,
        json={
            "class_id": cid,
            "content": "上课了",
            "display_mode": "popup",
            "reminder_level": "normal",
            "duration": 60,
            "tts_enabled": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "sent"
    assert isinstance(body["id"], int)

    hist = client.get(f"/api/messages/history?class_id={cid}", headers=h)
    assert hist.status_code == 200
    page = hist.json()
    assert page["total"] >= 1
    assert page["items"][0]["content"] == "上课了"
    # Verify teacher_name is populated in history response
    assert page["items"][0].get("teacher_name") == "张老师"

    latest = client.get(f"/api/messages/latest?class_id={cid}", headers=h)
    assert latest.status_code == 200
    assert len(latest.json()) >= 1


def test_send_validation_error(client):
    t = setup_teacher_with_class(client)
    cid = t["class_id"]
    h = auth_headers(t["token"])

    empty = client.post("/api/messages", headers=h, json={"class_id": cid, "content": ""})
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "VALIDATION_ERROR"

    bad_enum = client.post(
        "/api/messages", headers=h, json={"class_id": cid, "content": "ok", "display_mode": "bad"}
    )
    assert bad_enum.status_code == 400

    bad_duration = client.post(
        "/api/messages", headers=h, json={"class_id": cid, "content": "ok", "duration": 5}
    )
    assert bad_duration.status_code == 400


def test_messages_requires_auth(client):
    r = client.post("/api/messages", json={"class_id": 1, "content": "x"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "TOKEN_MISSING"


# ---- Batch Send ----

def test_batch_send(client):
    """Send to 2 classes simultaneously."""
    t = teacher_login_by_name(client, "批量老师")
    h = auth_headers(t["token"])

    # Create 2 classes
    c1 = client.post("/api/classes", headers=h, json={"name": "一班"}).json()
    c2 = client.post("/api/classes", headers=h, json={"name": "二班"}).json()

    # Refresh token to include new class_ids (avoid re-login which triggers dedup)
    t = refresh_teacher_token(t, [c1["id"], c2["id"]])
    h = auth_headers(t["token"])

    r = client.post(
        "/api/messages/batch",
        headers=h,
        json={
            "class_ids": [c1["id"], c2["id"]],
            "content": "全体注意",
            "display_mode": "popup",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "sent"
    assert body["class_count"] == 2
    assert len(body["ids"]) == 2


def test_batch_send_limit(client):
    """Cannot send to more than 6 classes at once."""
    t = teacher_login_by_name(client, "多班老师")
    h = auth_headers(t["token"])

    # Create 7 classes
    cids = []
    for i in range(7):
        c = client.post("/api/classes", headers=h, json={"name": f"班{i}"}).json()
        cids.append(c["id"])

    # Refresh token to include new class_ids (ensure auth passes so Pydantic validates body)
    t = refresh_teacher_token(t, cids)
    h = auth_headers(t["token"])

    r = client.post(
        "/api/messages/batch",
        headers=h,
        json={"class_ids": cids, "content": "太多班级了"},
    )
    # Pydantic validation: max_length=6 on class_ids
    assert r.status_code in (400, 422)


# ---- Message Recall ----

def test_recall_message(client):
    """Recall a message within 60 seconds."""
    t = setup_teacher_with_class(client)
    cid = t["class_id"]
    h = auth_headers(t["token"])

    # Send a message
    r = client.post(
        "/api/messages",
        headers=h,
        json={"class_id": cid, "content": "可以撤回的消息"},
    )
    msg_id = r.json()["id"]

    # Recall it
    r2 = client.post(f"/api/messages/{msg_id}/recall", headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "recalled"

    # Verify it's gone from history
    hist = client.get(f"/api/messages/history?class_id={cid}", headers=h)
    ids = [item["id"] for item in hist.json()["items"]]
    assert msg_id not in ids


def test_recall_not_found(client):
    t = setup_teacher_with_class(client)
    h = auth_headers(t["token"])
    r = client.post("/api/messages/99999/recall", headers=h)
    assert r.status_code == 404


# ---- Message Delete ----

def test_delete_message(client):
    """Delete a message — only the sender can delete."""
    t = setup_teacher_with_class(client)
    cid = t["class_id"]
    h = auth_headers(t["token"])

    # Send a message
    r = client.post(
        "/api/messages",
        headers=h,
        json={"class_id": cid, "content": "待删除消息"},
    )
    msg_id = r.json()["id"]

    # Delete it
    r2 = client.delete(f"/api/messages/{msg_id}", headers=h)
    assert r2.status_code == 204

    # Verify it's gone from history
    hist = client.get(f"/api/messages/history?class_id={cid}", headers=h)
    ids = [item["id"] for item in hist.json()["items"]]
    assert msg_id not in ids


def test_delete_not_found(client):
    t = setup_teacher_with_class(client)
    h = auth_headers(t["token"])
    r = client.delete("/api/messages/99999", headers=h)
    assert r.status_code == 404


def test_delete_forbidden_for_other_teacher(client):
    """Teacher A cannot delete Teacher B's message."""
    t1 = setup_teacher_with_class(client, "老师甲")
    cid = t1["class_id"]
    h1 = auth_headers(t1["token"])

    # Teacher A sends a message
    r = client.post(
        "/api/messages",
        headers=h1,
        json={"class_id": cid, "content": "老师甲的消息"},
    )
    msg_id = r.json()["id"]

    # Teacher B tries to delete it
    t2 = setup_teacher_with_class(client, "老师乙")
    h2 = auth_headers(t2["token"])
    r2 = client.delete(f"/api/messages/{msg_id}", headers=h2)
    assert r2.status_code == 403


# ---- Templates ----

def test_template_crud(client):
    t = teacher_login_by_name(client, "模板老师")
    h = auth_headers(t["token"])

    # Create
    r = client.post("/api/templates", headers=h, json={"content": "请安静"})
    assert r.status_code == 201
    tpl_id = r.json()["id"]
    assert r.json()["content"] == "请安静"

    # List
    r = client.get("/api/templates", headers=h)
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Update
    r = client.put(f"/api/templates/{tpl_id}", headers=h, json={"content": "请保持安静"})
    assert r.status_code == 200
    assert r.json()["content"] == "请保持安静"

    # Delete
    r = client.delete(f"/api/templates/{tpl_id}", headers=h)
    assert r.status_code == 204


# ---- Scheduled Messages ----

def test_scheduled_message_create_and_list(client):
    from datetime import datetime, timedelta, timezone

    t = setup_teacher_with_class(client)
    cid = t["class_id"]
    h = auth_headers(t["token"])

    # Create a one-time scheduled message
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    r = client.post(
        "/api/messages/scheduled",
        headers=h,
        json={
            "class_id": cid,
            "content": "定时提醒",
            "schedule_type": "once",
            "schedule_at": future,
        },
    )
    assert r.status_code == 201, r.text
    sm_id = r.json()["id"]
    assert r.json()["is_active"] is True

    # List
    r = client.get("/api/messages/scheduled", headers=h)
    assert r.status_code == 200
    assert any(item["id"] == sm_id for item in r.json())

    # Delete
    r = client.delete(f"/api/messages/scheduled/{sm_id}", headers=h)
    assert r.status_code == 204


# ---- Audit & Export ----

def test_audit_messages(client):
    t = setup_teacher_with_class(client)
    cid = t["class_id"]
    h = auth_headers(t["token"])

    # Send a message
    client.post(
        "/api/messages",
        headers=h,
        json={"class_id": cid, "content": "审计测试消息"},
    )

    # Audit
    r = client.get(f"/api/messages/audit?class_id={cid}", headers=h)
    assert r.status_code == 200
    page = r.json()
    assert page["total"] >= 1
    assert any(item["content"] == "审计测试消息" for item in page["items"])


def test_export_csv(client):
    t = setup_teacher_with_class(client)
    cid = t["class_id"]
    h = auth_headers(t["token"])

    # Send a message
    client.post(
        "/api/messages",
        headers=h,
        json={"class_id": cid, "content": "导出测试"},
    )

    # Export
    r = client.get(f"/api/messages/export?class_id={cid}", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    content = r.text
    assert "导出测试" in content
    assert "班级" in content  # header row
