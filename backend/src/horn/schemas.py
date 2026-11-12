"""Pydantic v2 request/response schemas aligned with docs/02 §4-§5.

Phase 2 additions: batch send, recall, scheduled messages, image upload,
teacher login, templates, audit/export.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DisplayMode = Literal["popup", "marquee"]
ReminderLevel = Literal["normal", "strong"]
Role = Literal["teacher", "display"]
ScheduleType = Literal["once", "daily", "weekly", "cron"]


# ---- Auth ----
class PairingLoginRequest(BaseModel):
    pairing_code: str = Field(..., pattern=r"^\d{6}$", description="6 位数字配对码")
    role: Role = "display"


class TeacherLoginRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="教师姓名")


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pairing_code: str


class ClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="班级名称")


class ClassUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="班级名称")


class ClassCreateOut(BaseModel):
    """Response after creating a class — includes the auto-generated pairing code."""
    id: int
    name: str
    pairing_code: str
    message: str = "班级创建成功"


class LoginResponse(BaseModel):
    token: str
    role: str
    teacher_id: Optional[int] = None
    teacher_name: str = ""
    classes: List[ClassOut] = Field(default_factory=list)


# ---- Messages ----
class MessageCreate(BaseModel):
    class_id: int
    content: str = Field(..., min_length=1, max_length=500)
    display_mode: DisplayMode = "popup"
    reminder_level: ReminderLevel = "normal"
    duration: int = Field(120, ge=30, le=300)
    tts_enabled: bool = True
    tts_repeat: int = Field(1, ge=1, le=3)
    image_path: Optional[str] = None


class BatchMessageCreate(BaseModel):
    """Send the same message to multiple classes (≤6)."""
    class_ids: List[int] = Field(..., min_length=1, max_length=6)
    content: str = Field(..., min_length=1, max_length=500)
    display_mode: DisplayMode = "popup"
    reminder_level: ReminderLevel = "normal"
    duration: int = Field(120, ge=30, le=300)
    tts_enabled: bool = True
    tts_repeat: int = Field(1, ge=1, le=3)
    image_path: Optional[str] = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: int
    class_id: int
    content: str
    display_mode: str
    reminder_level: str
    duration: int
    tts_enabled: bool
    tts_repeat: int = 1
    audio_path: Optional[str] = None
    image_path: Optional[str] = None
    sent_at: datetime
    teacher_name: Optional[str] = None


class SendResponse(BaseModel):
    id: int
    status: str
    sent_at: datetime


class BatchSendResponse(BaseModel):
    ids: List[int]
    status: str
    sent_at: datetime
    class_count: int


class HistoryPage(BaseModel):
    total: int
    page: int
    limit: int
    items: List[MessageOut] = Field(default_factory=list)


# ---- Scheduled Messages ----
class ScheduledMessageCreate(BaseModel):
    class_id: int
    content: str = Field(..., min_length=1, max_length=500)
    display_mode: DisplayMode = "popup"
    reminder_level: ReminderLevel = "normal"
    duration: int = Field(120, ge=30, le=300)
    tts_enabled: bool = True
    image_path: Optional[str] = None
    schedule_type: ScheduleType = "once"
    schedule_at: Optional[datetime] = None
    cron_expression: Optional[str] = None


class ScheduledMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: int
    class_id: int
    content: str
    display_mode: str
    reminder_level: str
    duration: int
    tts_enabled: bool
    image_path: Optional[str] = None
    schedule_type: str
    schedule_at: Optional[datetime] = None
    cron_expression: Optional[str] = None
    is_active: bool
    created_at: datetime


# ---- Templates ----
class TemplateCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class TemplateUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    sort_order: int
    created_at: datetime


# ---- Audit / Export ----
class AuditFilter(BaseModel):
    class_id: Optional[int] = None
    teacher_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=500)


# ---- Image Upload ----
class ImageUploadResponse(BaseModel):
    image_path: str
    url: str


# ---- System ----
class HealthOut(BaseModel):
    status: str
    timestamp: datetime
    version: str
