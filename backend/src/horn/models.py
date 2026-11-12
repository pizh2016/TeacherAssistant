"""SQLAlchemy ORM models aligned with docs/02 §2 (technical-design §5.5).

Six tables: classes, teachers, teacher_classes, messages, scheduled_messages,
teacher_templates.
``class_id`` / ``teacher_id`` / ``message_id`` are integer primary keys; the
6-digit ``pairing_code`` is the human-facing identifier for a class.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    pairing_code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    wechat_openid: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), primary_key=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    display_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="popup")
    reminder_level: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    duration: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    tts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tts_repeat: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    audio_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_messages_class_sent", "class_id", "sent_at"),
        Index("idx_messages_teacher", "teacher_id", "sent_at"),
    )


class ScheduledMessage(Base):
    """Scheduled broadcasts — APScheduler-driven periodic/one-time tasks."""

    __tablename__ = "scheduled_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    display_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="popup")
    reminder_level: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    duration: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    tts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tts_repeat: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    schedule_type: Mapped[str] = mapped_column(String(16), nullable=False, default="once")
    schedule_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TeacherTemplate(Base):
    """Teacher's custom message templates (persistent)."""

    __tablename__ = "teacher_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_template_teacher", "teacher_id", "sort_order"),
    )
