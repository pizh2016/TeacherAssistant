"""WebSocket protocol tests (docs/02 §5) — Phase 2 updated.

Covers the first-frame ``join_class{class_id, token}`` authorization, the
``connection_ack`` handshake, ``heartbeat``/``pong`` keepalive, REST-triggered
``new_message`` broadcast, recall_message event, and the application close
codes 4401/4403.
"""

import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import auth_headers, login, teacher_login_by_name, setup_teacher_with_class, refresh_teacher_token


def _next_event(ws, skip=None):
    """Receive JSON frames, transparently skipping transient ``skip`` types."""
    skip = skip or set()
    while True:
        evt = ws.receive_json()
        if isinstance(evt, dict) and evt.get("type") in skip:
            continue
        return evt


def test_ws_join_ack_and_broadcast(client):
    """Display joins its class channel and receives a teacher's broadcast."""
    disp = login(client, "123456", "display")
    teach = setup_teacher_with_class(client, "广播老师")
    # Get the pairing code for the teacher's class
    cid = teach["class_id"]

    # We need a display token for this specific class.
    # The teacher created a class, so we need to find its pairing code.
    pairing_code = teach["classes"][0]["pairing_code"]
    disp = login(client, pairing_code, "display")

    with client.websocket_connect(f"/ws/class/{cid}") as ws:
        ws.send_json({"type": "join_class", "class_id": cid, "token": disp["token"]})
        ack = _next_event(ws, skip={"reconnect_hint"})
        assert ack["type"] == "connection_ack"
        assert ack["status"] == "ok"
        assert ack["class_id"] == cid

        # Teacher sends via REST; the endpoint awaits broadcast to this channel.
        r = client.post(
            "/api/messages",
            headers=auth_headers(teach["token"]),
            json={"class_id": cid, "content": "上课了", "display_mode": "popup"},
        )
        assert r.status_code == 200, r.text

        evt = _next_event(ws, skip={"reconnect_hint"})
        assert evt["type"] == "new_message"
        assert evt["content"] == "上课了"
        assert evt["class_id"] == cid
        assert evt["id"] == r.json()["id"]
        # Verify teacher_name is included in the broadcast
        assert evt.get("teacher_name") == "广播老师"


def test_ws_recall_message(client):
    """Display receives a recall_message event when teacher recalls."""
    teach = setup_teacher_with_class(client, "撤回老师")
    cid = teach["class_id"]
    pairing_code = teach["classes"][0]["pairing_code"]
    disp = login(client, pairing_code, "display")

    with client.websocket_connect(f"/ws/class/{cid}") as ws:
        ws.send_json({"type": "join_class", "class_id": cid, "token": disp["token"]})
        ack = _next_event(ws, skip={"reconnect_hint"})
        assert ack["type"] == "connection_ack"

        # Send a message
        r = client.post(
            "/api/messages",
            headers=auth_headers(teach["token"]),
            json={"class_id": cid, "content": "待撤回消息"},
        )
        msg_id = r.json()["id"]

        # Receive new_message
        evt = _next_event(ws, skip={"reconnect_hint"})
        assert evt["type"] == "new_message"
        assert evt["content"] == "待撤回消息"

        # Recall the message
        r2 = client.post(f"/api/messages/{msg_id}/recall", headers=auth_headers(teach["token"]))
        assert r2.status_code == 200

        # Receive recall_message event
        evt2 = _next_event(ws, skip={"reconnect_hint"})
        assert evt2["type"] == "recall_message"
        assert evt2["message_id"] == msg_id


def test_ws_batch_broadcast(client):
    """Multiple display channels receive the batch broadcast."""
    teach = teacher_login_by_name(client, "批量广播老师")
    h = auth_headers(teach["token"])

    # Create 2 classes
    c1 = client.post("/api/classes", headers=h, json={"name": "一班"}).json()
    c2 = client.post("/api/classes", headers=h, json={"name": "二班"}).json()

    # Refresh token to include new class_ids (avoid re-login which triggers dedup)
    teach = refresh_teacher_token(teach, [c1["id"], c2["id"]])
    h = auth_headers(teach["token"])

    # Connect displays to both classes
    disp1 = login(client, c1["pairing_code"], "display")
    disp2 = login(client, c2["pairing_code"], "display")

    with client.websocket_connect(f"/ws/class/{c1['id']}") as ws1:
        ws1.send_json({"type": "join_class", "class_id": c1["id"], "token": disp1["token"]})
        ack1 = _next_event(ws1, skip={"reconnect_hint"})
        assert ack1["type"] == "connection_ack"

        with client.websocket_connect(f"/ws/class/{c2['id']}") as ws2:
            ws2.send_json({"type": "join_class", "class_id": c2["id"], "token": disp2["token"]})
            ack2 = _next_event(ws2, skip={"reconnect_hint"})
            assert ack2["type"] == "connection_ack"

            # Batch send
            r = client.post(
                "/api/messages/batch",
                headers=h,
                json={
                    "class_ids": [c1["id"], c2["id"]],
                    "content": "全体注意",
                },
            )
            assert r.status_code == 200

            # Both displays should receive the message
            evt1 = _next_event(ws1, skip={"reconnect_hint"})
            assert evt1["type"] == "new_message"
            assert evt1["content"] == "全体注意"
            # Verify teacher_name is included
            assert evt1.get("teacher_name") == "批量广播老师"

            evt2 = _next_event(ws2, skip={"reconnect_hint"})
            assert evt2["type"] == "new_message"
            assert evt2["content"] == "全体注意"
            assert evt2.get("teacher_name") == "批量广播老师"


def test_ws_heartbeat_pong(client):
    disp = login(client, "123456", "display")
    cid = disp["classes"][0]["id"]

    with client.websocket_connect(f"/ws/class/{cid}") as ws:
        ws.send_json({"type": "join_class", "class_id": cid, "token": disp["token"]})
        ack = _next_event(ws, skip={"reconnect_hint"})
        assert ack["type"] == "connection_ack"

        ws.send_json({"type": "heartbeat"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert isinstance(pong["timestamp_ms"], int)


def test_ws_invalid_token_closed(client):
    """A bad/absent JWT on the join frame closes the socket with 4401."""
    with client.websocket_connect("/ws/class/1") as ws:
        ws.send_json({"type": "join_class", "class_id": 1, "token": "not-a-jwt"})
        with pytest.raises(WebSocketDisconnect) as ei:
            ws.receive_json()
        assert ei.value.code == 4401


def test_ws_wrong_class_forbidden(client):
    """A token scoped to class A cannot join class B's channel (4403)."""
    disp_a = login(client, "123456", "display")
    disp_b = login(client, "654321", "display")
    cid_a = disp_a["classes"][0]["id"]
    cid_b = disp_b["classes"][0]["id"]
    assert cid_a != cid_b

    with client.websocket_connect(f"/ws/class/{cid_b}") as ws:
        ws.send_json({"type": "join_class", "class_id": cid_b, "token": disp_a["token"]})
        with pytest.raises(WebSocketDisconnect) as ei:
            ws.receive_json()
        assert ei.value.code == 4403
