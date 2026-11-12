"""Message routes: send / batch / recall / history / latest / upload / scheduled / audit / export.

Phase 2 additions: batch broadcast, message recall (60s), image upload,
scheduled messages, audit filtering, CSV export.
"""

import csv
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models
from ..auth import Principal, authorize_class, get_principal
from ..config import BACKEND_ROOT
from ..database import get_db
from ..errors import ApiError, ErrorCode
from ..schemas import (
    BatchMessageCreate,
    BatchSendResponse,
    HistoryPage,
    ImageUploadResponse,
    MessageCreate,
    MessageOut,
    ScheduledMessageCreate,
    ScheduledMessageOut,
    SendResponse,
)
from ..ws.manager import manager, message_to_ws_event, _lookup_teacher_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _ensure_utc(dt: datetime) -> datetime:
    """Tag a naive datetime as UTC (SQLite strips timezone info)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

# Upload directory
UPLOAD_DIR = BACKEND_ROOT / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _client_ip(request: Request) -> str:
    if request.client:
        return f"{request.client.host}:{request.client.port}"
    return "unknown"


@router.post("", response_model=SendResponse)
async def send_message(
    payload: MessageCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> SendResponse:
    """Persist a message and broadcast it to the class WebSocket channel."""
    authorize_class(principal, payload.class_id, teacher_only=True, db=db)

    msg = models.Message(
        teacher_id=principal.teacher_id,
        class_id=payload.class_id,
        content=payload.content,
        display_mode=payload.display_mode,
        reminder_level=payload.reminder_level,
        duration=payload.duration,
        tts_enabled=payload.tts_enabled,
        tts_repeat=payload.tts_repeat,
        image_path=payload.image_path,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Look up teacher name for WS broadcast
    teacher_name = _lookup_teacher_name(principal.teacher_id)
    logger.info(
        "MSG_SEND_LOOKUP | teacher_id=%d | teacher_name=%s",
        principal.teacher_id, teacher_name,
    )
    await manager.broadcast(msg.class_id, message_to_ws_event(msg, teacher_name=teacher_name))

    logger.info(
        "MSG_CREATE | teacher_id=%d | IP=%s | 发送消息 msg_id=%d, class_id=%d",
        principal.teacher_id,
        _client_ip(request),
        msg.id,
        msg.class_id,
    )

    return SendResponse(id=msg.id, status="sent", sent_at=msg.sent_at)


@router.post("/batch", response_model=BatchSendResponse)
async def batch_send_message(
    payload: BatchMessageCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> BatchSendResponse:
    """Send the same message to multiple classes (≤6) simultaneously."""
    # Authorize all classes
    for cid in payload.class_ids:
        authorize_class(principal, cid, teacher_only=True, db=db)

    now = datetime.now(timezone.utc)
    ids: List[int] = []

    for cid in payload.class_ids:
        msg = models.Message(
            teacher_id=principal.teacher_id,
            class_id=cid,
            content=payload.content,
            display_mode=payload.display_mode,
            reminder_level=payload.reminder_level,
            duration=payload.duration,
            tts_enabled=payload.tts_enabled,
            tts_repeat=payload.tts_repeat,
            image_path=payload.image_path,
        )
        db.add(msg)
        db.flush()
        ids.append(msg.id)

    db.commit()

    # Build class_id -> message mapping from in-memory ORM objects (no re-query needed)
    msgs_by_class: dict[int, list] = {}
    for msg in db.query(models.Message).filter(models.Message.id.in_(ids)).all():
        msgs_by_class.setdefault(msg.class_id, []).append(msg)

    # Broadcast to all target channels
    teacher_name = _lookup_teacher_name(principal.teacher_id)
    for cid in payload.class_ids:
        for msg in msgs_by_class.get(cid, []):
            await manager.broadcast(cid, message_to_ws_event(msg, teacher_name=teacher_name))

    logger.info(
        "MSG_BATCH | teacher_id=%d | IP=%s | 批量发送 %d 条消息到班级 %s",
        principal.teacher_id,
        _client_ip(request),
        len(ids),
        payload.class_ids,
    )

    sent_at = now
    return BatchSendResponse(
        ids=ids,
        status="sent",
        sent_at=sent_at,
        class_count=len(payload.class_ids),
    )


@router.post("/{message_id}/recall")
async def recall_message(
    message_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Recall a message within 60 seconds of sending.

    Broadcasts a ``recall_message`` WS event to remove it from display.
    """
    msg = db.get(models.Message, message_id)
    if msg is None:
        raise ApiError(404, ErrorCode.MESSAGE_RECALL_NOT_FOUND, "消息不存在")

    # Only the sender can recall
    if msg.teacher_id != principal.teacher_id:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "只能撤回自己发送的消息")

    # Check 60-second window
    now = datetime.now(timezone.utc)
    sent_at = msg.sent_at
    # Handle naive datetime from SQLite
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    elapsed = (now - sent_at).total_seconds()
    if elapsed > 60:
        raise ApiError(400, ErrorCode.MESSAGE_RECALL_EXPIRED, "已超过 60 秒撤回时限")

    class_id = msg.class_id
    # Delete the message
    db.delete(msg)
    db.commit()

    # Broadcast recall event to the class channel
    await manager.broadcast(class_id, {
        "type": "recall_message",
        "message_id": message_id,
        "class_id": class_id,
    })

    logger.info(
        "MSG_RECALL | teacher_id=%d | IP=%s | 撤回消息 msg_id=%d, class_id=%d",
        principal.teacher_id,
        _client_ip(request),
        message_id,
        class_id,
    )

    return {"status": "recalled", "message_id": message_id}


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
) -> ImageUploadResponse:
    """Upload an image for display (≤5MB). Returns the relative URL path."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ApiError(400, ErrorCode.IMAGE_FORMAT_INVALID, "仅支持 JPEG/PNG/GIF/WebP 格式")

    # Read and check size
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise ApiError(400, ErrorCode.IMAGE_TOO_LARGE, "图片大小不能超过 5MB")

    # Save with unique name
    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    # Return relative URL path (consistent with what gets stored in DB and sent via WS)
    relative = f"/static/uploads/{filename}"
    return ImageUploadResponse(image_path=relative, url=relative)


@router.get("/history", response_model=HistoryPage)
def history(
    class_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> HistoryPage:
    query = db.query(models.Message)
    if class_id is not None:
        authorize_class(principal, class_id, db=db)
        query = query.filter(models.Message.class_id == class_id)
    else:
        # For teachers, use DB bindings; for display, use token class_id
        if principal.role == "teacher" and principal.teacher_id is not None:
            accessible = [
                row.class_id
                for row in db.query(models.TeacherClass)
                .filter_by(teacher_id=principal.teacher_id)
                .all()
            ]
        else:
            accessible = principal.accessible_class_ids
        query = query.filter(models.Message.class_id.in_(accessible or [-1]))

    total = query.count()
    rows = (
        query.order_by(models.Message.sent_at.desc(), models.Message.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    # Populate teacher_name for each message
    items = []
    if rows:
        tids = list({m.teacher_id for m in rows})
        teacher_names: dict[int, str] = {}
        for t in db.query(models.Teacher).filter(models.Teacher.id.in_(tids)).all():
            teacher_names[t.id] = t.name
        for m in rows:
            out = MessageOut.model_validate(m)
            out.teacher_name = teacher_names.get(m.teacher_id)
            out.sent_at = _ensure_utc(m.sent_at)
            items.append(out)
    return HistoryPage(
        total=total,
        page=page,
        limit=limit,
        items=items,
    )


@router.get("/latest", response_model=List[MessageOut])
def latest(
    class_id: int = Query(...),
    since: Optional[int] = Query(default=None, description="message id cursor"),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> List[MessageOut]:
    """Reconnect catch-up: messages for a class with id > since."""
    authorize_class(principal, class_id, db=db)
    query = db.query(models.Message).filter(models.Message.class_id == class_id)
    if since is not None:
        query = query.filter(models.Message.id > since)
    rows = query.order_by(models.Message.id.asc()).all()
    # Populate teacher_name for each message
    items = []
    if rows:
        tids = list({m.teacher_id for m in rows})
        teacher_names: dict[int, str] = {}
        for t in db.query(models.Teacher).filter(models.Teacher.id.in_(tids)).all():
            teacher_names[t.id] = t.name
        for m in rows:
            out = MessageOut.model_validate(m)
            out.teacher_name = teacher_names.get(m.teacher_id)
            out.sent_at = _ensure_utc(m.sent_at)
            items.append(out)
    return items


# ---- Scheduled Messages ----

@router.post("/scheduled", response_model=ScheduledMessageOut, status_code=201)
def create_scheduled_message(
    payload: ScheduledMessageCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> ScheduledMessageOut:
    """Create a scheduled/periodic broadcast task."""
    authorize_class(principal, payload.class_id, teacher_only=True, db=db)

    # Validate schedule parameters
    if payload.schedule_type == "once" and payload.schedule_at is None:
        raise ApiError(400, ErrorCode.SCHEDULE_INVALID, "单次定时需指定执行时间")
    if payload.schedule_type in ("daily", "weekly") and payload.cron_expression is None:
        # Auto-generate cron from schedule_type
        if payload.schedule_type == "daily":
            payload.cron_expression = "0 8 * * *"  # default 8:00
        else:
            payload.cron_expression = "0 8 * * 1"  # default Monday 8:00

    sm = models.ScheduledMessage(
        teacher_id=principal.teacher_id,
        class_id=payload.class_id,
        content=payload.content,
        display_mode=payload.display_mode,
        reminder_level=payload.reminder_level,
        duration=payload.duration,
        tts_enabled=payload.tts_enabled,
        image_path=payload.image_path,
        schedule_type=payload.schedule_type,
        schedule_at=payload.schedule_at,
        cron_expression=payload.cron_expression,
    )
    db.add(sm)
    db.commit()
    db.refresh(sm)

    # Register with scheduler
    from ..scheduler import register_scheduled_job
    register_scheduled_job(sm)

    logger.info(
        "SCHEDULE_CREATE | teacher_id=%d | IP=%s | 创建定时任务 id=%d, class_id=%d, type=%s",
        principal.teacher_id,
        _client_ip(request),
        sm.id,
        sm.class_id,
        sm.schedule_type,
    )

    return ScheduledMessageOut.model_validate(sm)


@router.get("/scheduled", response_model=List[ScheduledMessageOut])
def list_scheduled_messages(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> List[ScheduledMessageOut]:
    """List all scheduled messages for the current teacher."""
    query = db.query(models.ScheduledMessage).filter(
        models.ScheduledMessage.teacher_id == principal.teacher_id,
    )
    rows = query.order_by(models.ScheduledMessage.created_at.desc()).all()
    return [ScheduledMessageOut.model_validate(m) for m in rows]


@router.delete("/scheduled/{scheduled_id}", status_code=204)
def delete_scheduled_message(
    scheduled_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    """Cancel a scheduled message."""
    sm = db.get(models.ScheduledMessage, scheduled_id)
    if sm is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "定时任务不存在")
    if sm.teacher_id != principal.teacher_id:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "只能操作自己的定时任务")

    from ..scheduler import remove_scheduled_job
    remove_scheduled_job(scheduled_id)

    db.delete(sm)
    db.commit()


@router.put("/scheduled/{scheduled_id}/toggle", response_model=ScheduledMessageOut)
def toggle_scheduled_message(
    scheduled_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> ScheduledMessageOut:
    """Toggle a scheduled message active/inactive."""
    sm = db.get(models.ScheduledMessage, scheduled_id)
    if sm is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "定时任务不存在")
    if sm.teacher_id != principal.teacher_id:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "只能操作自己的定时任务")

    sm.is_active = not sm.is_active
    db.commit()
    db.refresh(sm)

    if sm.is_active:
        from ..scheduler import register_scheduled_job
        register_scheduled_job(sm)
    else:
        from ..scheduler import remove_scheduled_job
        remove_scheduled_job(scheduled_id)

    return ScheduledMessageOut.model_validate(sm)


# ---- Audit & Export ----

@router.get("/audit", response_model=HistoryPage)
def audit_messages(
    class_id: Optional[int] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> HistoryPage:
    """Filtered message list for auditing purposes (admin/teacher)."""
    query = db.query(models.Message)

    # Filter by accessible classes (use DB for teachers)
    if principal.role == "teacher" and principal.teacher_id is not None:
        accessible = [
            row.class_id
            for row in db.query(models.TeacherClass)
            .filter_by(teacher_id=principal.teacher_id)
            .all()
        ]
    else:
        accessible = principal.accessible_class_ids
    accessible = accessible or [-1]
    if class_id is not None:
        if class_id not in accessible:
            raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "无权查看该班级消息")
        query = query.filter(models.Message.class_id == class_id)
    else:
        query = query.filter(models.Message.class_id.in_(accessible))

    if teacher_id is not None:
        query = query.filter(models.Message.teacher_id == teacher_id)
    if start_time is not None:
        query = query.filter(models.Message.sent_at >= start_time)
    if end_time is not None:
        query = query.filter(models.Message.sent_at <= end_time)

    total = query.count()
    rows = (
        query.order_by(models.Message.sent_at.desc(), models.Message.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return HistoryPage(
        total=total,
        page=page,
        limit=limit,
        items=[MessageOut.model_validate(m) for m in rows],
    )


@router.get("/export")
def export_messages_csv(
    class_id: Optional[int] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export messages as CSV file."""
    query = db.query(models.Message)

    if principal.role == "teacher" and principal.teacher_id is not None:
        accessible = [
            row.class_id
            for row in db.query(models.TeacherClass)
            .filter_by(teacher_id=principal.teacher_id)
            .all()
        ]
    else:
        accessible = principal.accessible_class_ids
    accessible = accessible or [-1]
    if class_id is not None:
        if class_id not in accessible:
            raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "无权导出该班级消息")
        query = query.filter(models.Message.class_id == class_id)
    else:
        query = query.filter(models.Message.class_id.in_(accessible))

    if teacher_id is not None:
        query = query.filter(models.Message.teacher_id == teacher_id)
    if start_time is not None:
        query = query.filter(models.Message.sent_at >= start_time)
    if end_time is not None:
        query = query.filter(models.Message.sent_at <= end_time)

    rows = query.order_by(models.Message.sent_at.desc()).all()

    # Build class name lookup
    class_names: dict[int, str] = {}
    teacher_names: dict[int, str] = {}
    if rows:
        cids = list({m.class_id for m in rows})
        tids = list({m.teacher_id for m in rows})
        for c in db.query(models.Class).filter(models.Class.id.in_(cids)).all():
            class_names[c.id] = c.name
        for t in db.query(models.Teacher).filter(models.Teacher.id.in_(tids)).all():
            teacher_names[t.id] = t.name

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "班级", "教师", "内容", "展示方式", "强度", "时长(秒)", "语音", "发送时间"])
    for m in rows:
        writer.writerow([
            m.id,
            class_names.get(m.class_id, str(m.class_id)),
            teacher_names.get(m.teacher_id, str(m.teacher_id)),
            m.content,
            m.display_mode,
            m.reminder_level,
            m.duration,
            "是" if m.tts_enabled else "否",
            m.sent_at.strftime("%Y-%m-%d %H:%M:%S") if m.sent_at else "",
        ])

    output.seek(0)
    # Add BOM for Excel compatibility
    bom = "\ufeff"
    content = bom + output.getvalue()

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=messages_export.csv"},
    )


@router.delete("/{message_id}", status_code=204)
def delete_message(
    message_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    """Delete a message record. Only the sender can delete their own messages."""
    msg = db.get(models.Message, message_id)
    if msg is None:
        raise ApiError(404, ErrorCode.MESSAGE_RECALL_NOT_FOUND, "消息不存在")

    # Only the sender can delete
    if msg.teacher_id != principal.teacher_id:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "只能删除自己发送的消息")

    db.delete(msg)
    db.commit()

    logger.info(
        "MSG_DELETE | teacher_id=%d | IP=%s | 删除消息 msg_id=%d",
        principal.teacher_id,
        _client_ip(request),
        message_id,
    )
