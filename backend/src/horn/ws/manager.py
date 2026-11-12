"""WebSocket connection manager and the /ws/class/{class_id} endpoint.

Protocol (docs/02 §5):
  - Client connects, then MUST send ``join_class{class_id, token}`` within
    ``ws_join_timeout`` seconds. The JWT authorizes the channel.
  - Server replies ``connection_ack`` (+ ``reconnect_hint`` if history exists).
  - Client ``heartbeat`` -> server ``pong``.
  - REST ``POST /api/messages`` triggers ``broadcast()`` -> ``new_message``.

Concurrency note: asyncio is single-threaded and channel mutations below contain
no ``await``, so they are atomic with respect to other coroutines. ``broadcast``
snapshots the connection list before awaiting sends, avoiding mutation-during-
iteration issues. Application close codes: 4401 unauthorized, 4403 forbidden,
4408 join timeout.
"""

import asyncio
import json
import logging
import time
from datetime import timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import models
from ..auth import principal_from_token
from ..config import get_settings
from ..database import SessionLocal
from ..errors import ApiError

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_JOIN_TIMEOUT = 4408


class ConnectionManager:
    """Groups live WebSocket connections by integer class_id."""

    def __init__(self) -> None:
        self._channels: Dict[int, List[WebSocket]] = {}

    def add(self, websocket: WebSocket, class_id: int) -> None:
        self._channels.setdefault(class_id, []).append(websocket)

    def remove(self, websocket: WebSocket, class_id: int) -> None:
        conns = self._channels.get(class_id)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._channels.pop(class_id, None)

    def channel_size(self, class_id: int) -> int:
        return len(self._channels.get(class_id, []))

    async def broadcast(self, class_id: int, message: dict) -> int:
        """Send ``message`` to every connection in ``class_id``; return delivered count."""
        connections = list(self._channels.get(class_id, []))
        delivered = 0
        dead: List[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
                delivered += 1
            except Exception:  # noqa: BLE001 - a dead socket must not break others
                dead.append(ws)
        for ws in dead:
            self.remove(ws, class_id)
        return delivered


manager = ConnectionManager()


def message_to_ws_event(msg: models.Message, teacher_name: Optional[str] = None) -> dict:
    """Convert a persisted Message ORM row into a ``new_message`` WS event."""
    logger.debug(
        "WS_EVENT | msg_id=%d | teacher_name=%s | sent_at=%s",
        msg.id, teacher_name, msg.sent_at,
    )
    # Ensure UTC timezone info for correct ISO serialization.
    # SQLite returns naive datetimes; tag them as UTC so the frontend
    # can convert to local time properly.
    sent_at = msg.sent_at
    if sent_at is not None and sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    return {
        "type": "new_message",
        "id": msg.id,
        "class_id": msg.class_id,
        "content": msg.content,
        "display_mode": msg.display_mode,
        "reminder_level": msg.reminder_level,
        "duration": msg.duration,
        "tts_enabled": bool(msg.tts_enabled),
        "tts_repeat": int(msg.tts_repeat) if hasattr(msg, "tts_repeat") else 1,
        "audio_path": msg.audio_path,
        "image_path": msg.image_path,
        "sent_at": sent_at.isoformat() if sent_at else None,
        "teacher_name": teacher_name,
    }


router = APIRouter()


async def _safe_close(websocket: WebSocket, code: int) -> None:
    try:
        await websocket.close(code=code)
    except Exception:  # noqa: BLE001 - already-closed socket
        pass


def _lookup_teacher_name(teacher_id: int) -> Optional[str]:
    """Look up teacher name by ID."""
    db = SessionLocal()
    try:
        teacher = db.get(models.Teacher, teacher_id)
        name = teacher.name if teacher else None
        logger.debug(
            "LOOKUP_TEACHER | teacher_id=%d | name=%s | found=%s",
            teacher_id, name, teacher is not None,
        )
        return name
    finally:
        db.close()


def _lookup_class_name(class_id: int) -> Optional[str]:
    db = SessionLocal()
    try:
        cls = db.get(models.Class, class_id)
        return cls.name if cls else None
    finally:
        db.close()


def _lookup_last_message_id(class_id: int) -> Optional[int]:
    db = SessionLocal()
    try:
        row = (
            db.query(models.Message.id)
            .filter(models.Message.class_id == class_id)
            .order_by(models.Message.id.desc())
            .first()
        )
        return row[0] if row else None
    finally:
        db.close()


@router.websocket("/ws/class/{class_id}")
async def ws_class_endpoint(websocket: WebSocket, class_id: int) -> None:
    settings = get_settings()
    await websocket.accept()

    # 1) Expect join_class within the timeout window.
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=settings.ws_join_timeout)
    except asyncio.TimeoutError:
        await _safe_close(websocket, CLOSE_JOIN_TIMEOUT)
        return
    except WebSocketDisconnect:
        return

    try:
        first = json.loads(raw)
    except json.JSONDecodeError:
        await _safe_close(websocket, CLOSE_UNAUTHORIZED)
        return

    if not isinstance(first, dict) or first.get("type") != "join_class":
        await _safe_close(websocket, CLOSE_UNAUTHORIZED)
        return

    # 2) Verify the JWT carried in the join frame.
    try:
        principal = principal_from_token(str(first.get("token", "")))
    except ApiError:
        await _safe_close(websocket, CLOSE_UNAUTHORIZED)
        return

    # 3) The token must be scoped to this class_id.
    if class_id not in principal.accessible_class_ids:
        await _safe_close(websocket, CLOSE_FORBIDDEN)
        return

    # 4) Register and acknowledge.
    manager.add(websocket, class_id)
    user_id = principal.teacher_id if principal.role == "teacher" else principal.class_id
    user_label = "teacher_id" if principal.role == "teacher" else "class_id"
    client_ip = websocket.client
    ip_str = f"{client_ip.host}:{client_ip.port}" if client_ip else "unknown"
    logger.info(
        "WS_JOIN | %s=%s, role=%s | IP=%s | 连接班级 class_id=%s",
        user_label,
        user_id,
        principal.role,
        ip_str,
        class_id,
    )
    try:
        await websocket.send_json(
            {
                "type": "connection_ack",
                "status": "ok",
                "class_id": class_id,
                "class_name": _lookup_class_name(class_id),
            }
        )
        last_id = _lookup_last_message_id(class_id)
        if last_id is not None:
            await websocket.send_json({"type": "reconnect_hint", "last_message_id": last_id})

        # 5) Steady-state event loop.
        while True:
            data = await websocket.receive_text()
            try:
                evt = json.loads(data)
            except json.JSONDecodeError:
                continue
            etype = evt.get("type") if isinstance(evt, dict) else None
            if etype == "heartbeat":
                await websocket.send_json({"type": "pong", "timestamp_ms": int(time.time() * 1000)})
            elif etype == "ack_message":
                logger.debug("ack_message class_id=%s id=%s", class_id, evt.get("message_id"))
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - ensure we always deregister
        logger.exception("WS error on class_id=%s", class_id)
    finally:
        manager.remove(websocket, class_id)
        logger.info(
            "WS_LEAVE | %s=%s | IP=%s | 断开班级 class_id=%s",
            user_label,
            user_id,
            ip_str,
            class_id,
        )
