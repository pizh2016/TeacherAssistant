"""Authentication: JWT (HS256) + pairing-code login + teacher name login.

Phase 2: Teachers log in by name (auto-register on first use); pairing codes
are restricted to display-only. The WebSocket channel is authorized with the
same JWT, delivered via the first ``join_class`` frame.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Header
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import models
from .config import get_settings
from .errors import ApiError, ErrorCode
from .schemas import ClassOut, LoginResponse

_settings = get_settings()


class Principal:
    """Authenticated caller identity extracted from a JWT."""

    def __init__(
        self,
        sub: str,
        role: str,
        teacher_id: Optional[int] = None,
        class_ids: Optional[List[int]] = None,
        class_id: Optional[int] = None,
    ):
        self.sub = sub
        self.role = role
        self.teacher_id = teacher_id
        self.class_ids = class_ids or []
        self.class_id = class_id

    @property
    def accessible_class_ids(self) -> List[int]:
        if self.role == "display":
            return [self.class_id] if self.class_id is not None else []
        return self.class_ids


def create_token(
    sub: str,
    role: str,
    teacher_id: Optional[int] = None,
    class_ids: Optional[List[int]] = None,
    class_id: Optional[int] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=_settings.access_token_expire_minutes),
    }
    if teacher_id is not None:
        payload["teacher_id"] = teacher_id
    if class_ids is not None:
        payload["class_ids"] = class_ids
    if class_id is not None:
        payload["class_id"] = class_id
    return jwt.encode(payload, _settings.jwt_secret_key, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode/verify a JWT, raising ApiError(401) on failure."""
    if not token:
        raise ApiError(401, ErrorCode.TOKEN_INVALID, "令牌无效或已过期")
    try:
        return jwt.decode(
            token,
            _settings.jwt_secret_key,
            algorithms=[_settings.jwt_algorithm],
        )
    except JWTError:
        raise ApiError(401, ErrorCode.TOKEN_INVALID, "令牌无效或已过期")


def principal_from_token(token: str) -> Principal:
    data = decode_token(token)
    return Principal(
        sub=data.get("sub", ""),
        role=data.get("role", "teacher"),
        teacher_id=data.get("teacher_id"),
        class_ids=data.get("class_ids") or [],
        class_id=data.get("class_id"),
    )


def get_principal(authorization: Optional[str] = Header(default=None)) -> Principal:
    """FastAPI dependency: require a valid ``Authorization: Bearer <token>``."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, ErrorCode.TOKEN_MISSING, "缺少 Authorization 头")
    token = authorization.split(" ", 1)[1].strip()
    return principal_from_token(token)


def authorize_class(
    principal: Principal,
    class_id: int,
    *,
    teacher_only: bool = False,
    db: Optional[Session] = None,
) -> None:
    """Ensure the principal may act on ``class_id``.

    For teachers, if the JWT's class_ids doesn't contain ``class_id`` but a
    ``db`` session is provided, fall back to querying the DB (handles the case
    where the JWT is stale after creating a new class).
    """
    if teacher_only and principal.role != "teacher":
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "仅教师可执行该操作")

    if class_id in principal.accessible_class_ids:
        return

    # Fallback: query DB for teacher-class binding (JWT may be stale)
    if db is not None and principal.role == "teacher" and principal.teacher_id is not None:
        binding = (
            db.query(models.TeacherClass)
            .filter_by(teacher_id=principal.teacher_id, class_id=class_id)
            .first()
        )
        if binding is not None:
            return

    raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "教师未绑定该班级")


def _find_or_create_teacher(db: Session, cls: models.Class) -> models.Teacher:
    binding = db.query(models.TeacherClass).filter_by(class_id=cls.id).first()
    if binding is not None:
        teacher = db.get(models.Teacher, binding.teacher_id)
        if teacher is not None:
            return teacher
    teacher = models.Teacher(name=f"教师·{cls.name}")
    db.add(teacher)
    db.flush()  # populate teacher.id
    db.add(models.TeacherClass(teacher_id=teacher.id, class_id=cls.id))
    db.commit()
    return teacher


def pairing_login(db: Session, pairing_code: str, role: str) -> LoginResponse:
    """Resolve a pairing code to a class and issue a JWT.

    Phase 2: Only ``role=display`` is allowed. Teacher login should use
    ``teacher_login()`` instead.
    """
    cls = db.query(models.Class).filter_by(pairing_code=pairing_code).first()
    if cls is None:
        raise ApiError(401, ErrorCode.PAIRING_CODE_INVALID, "配对码无效")

    if role != "display":
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "教师请使用姓名登录")

    token = create_token(sub=f"display-{cls.id}", role="display", class_id=cls.id)
    return LoginResponse(
        token=token,
        role="display",
        teacher_id=None,
        teacher_name="",
        classes=[ClassOut.model_validate(cls)],
    )


def teacher_login(db: Session, name: str) -> LoginResponse:
    """Find or create a teacher by name and issue a JWT.

    Design: name is the unique identity. Same name always maps to the same
    teacher record, regardless of whether classes are bound. A new record is
    created only when the name does not exist yet.
    """
    teacher = db.query(models.Teacher).filter_by(name=name).first()
    if teacher is None:
        teacher = models.Teacher(name=name)
        db.add(teacher)
        db.flush()

    # Update last login timestamp
    teacher.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(teacher)

    # Find bound classes
    bound_ids = [
        row.class_id
        for row in db.query(models.TeacherClass).filter_by(teacher_id=teacher.id).all()
    ]
    classes = db.query(models.Class).filter(models.Class.id.in_(bound_ids or [-1])).all()

    token = create_token(
        sub=f"teacher-{teacher.id}",
        role="teacher",
        teacher_id=teacher.id,
        class_ids=bound_ids,
    )
    return LoginResponse(
        token=token,
        role="teacher",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[ClassOut.model_validate(c) for c in classes],
    )
