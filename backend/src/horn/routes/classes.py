"""Class routes: CRUD for teacher-managed classes.

Endpoints:
- GET    /api/classes          — list teacher's bound classes
- POST   /api/classes          — create a new class (auto-generate pairing code)
- PUT    /api/classes/{id}     — rename a class
- DELETE /api/classes/{id}     — delete a class
- POST   /api/classes/{id}/regenerate-code — regenerate pairing code
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import models
from ..auth import Principal, get_principal
from ..database import get_db
from ..errors import ApiError, ErrorCode
from ..pairing_code import generate_unique_pairing_code
from ..schemas import ClassCreate, ClassCreateOut, ClassOut, ClassUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["classes"])


def _client_ip(request: Request) -> str:
    if request.client:
        return f"{request.client.host}:{request.client.port}"
    return "unknown"


@router.get("/classes", response_model=List[ClassOut])
def list_classes(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> List[ClassOut]:
    """Return all classes bound to the current teacher (queried from DB, not JWT)."""
    if principal.role == "display":
        # Display role: return the single class from the token
        cid = principal.class_id
        if cid is None:
            return []
        cls = db.get(models.Class, cid)
        return [ClassOut.model_validate(cls)] if cls else []

    # Teacher role: query actual bindings from DB (JWT class_ids may be stale)
    if principal.teacher_id is None:
        return []
    bound_ids = [
        row.class_id
        for row in db.query(models.TeacherClass)
        .filter_by(teacher_id=principal.teacher_id)
        .all()
    ]
    if not bound_ids:
        return []
    rows = db.query(models.Class).filter(models.Class.id.in_(bound_ids)).all()
    return [ClassOut.model_validate(c) for c in rows]


@router.post("/classes", response_model=ClassCreateOut, status_code=201)
def create_class(
    payload: ClassCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> ClassCreateOut:
    """Create a new class with an auto-generated pairing code.

    The class is automatically bound to the current teacher.
    """
    if principal.role != "teacher" or principal.teacher_id is None:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "仅教师可创建班级")

    # Check for duplicate class name under the same teacher
    existing = (
        db.query(models.Class)
        .join(models.TeacherClass, models.TeacherClass.class_id == models.Class.id)
        .filter(
            models.TeacherClass.teacher_id == principal.teacher_id,
            models.Class.name == payload.name,
        )
        .first()
    )
    if existing is not None:
        raise ApiError(400, ErrorCode.CLASS_FORBIDDEN, "班级名称已存在，请使用其他名称")

    # Generate a unique 6-digit pairing code
    pairing_code = generate_unique_pairing_code(db)

    # Create the class
    cls = models.Class(name=payload.name, pairing_code=pairing_code)
    db.add(cls)
    db.flush()  # populate cls.id

    # Bind to teacher
    binding = models.TeacherClass(teacher_id=principal.teacher_id, class_id=cls.id)
    db.add(binding)
    db.commit()
    db.refresh(cls)

    logger.info(
        "CLASS_CREATE | teacher_id=%d | IP=%s | 创建班级 class_id=%d, name=%s",
        principal.teacher_id,
        _client_ip(request),
        cls.id,
        cls.name,
    )

    return ClassCreateOut(
        id=cls.id,
        name=cls.name,
        pairing_code=cls.pairing_code,
        message="班级创建成功",
    )


@router.put("/classes/{class_id}", response_model=ClassOut)
def update_class(
    class_id: int,
    payload: ClassUpdate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> ClassOut:
    """Rename a class. Only the teacher bound to this class may rename it."""
    _ensure_teacher_class(principal, class_id, db)
    cls = db.query(models.Class).filter_by(id=class_id).first()
    if cls is None:
        raise ApiError(404, ErrorCode.CLASS_NOT_FOUND, "班级不存在")

    # Check for duplicate name (excluding self)
    duplicate = (
        db.query(models.Class)
        .join(models.TeacherClass, models.TeacherClass.class_id == models.Class.id)
        .filter(
            models.TeacherClass.teacher_id == principal.teacher_id,
            models.Class.name == payload.name,
            models.Class.id != class_id,
        )
        .first()
    )
    if duplicate is not None:
        raise ApiError(400, ErrorCode.CLASS_FORBIDDEN, "班级名称已存在，请使用其他名称")

    old_name = cls.name
    cls.name = payload.name
    db.commit()
    db.refresh(cls)

    logger.info(
        "CLASS_UPDATE | teacher_id=%d | IP=%s | 重命名班级 class_id=%d, '%s' -> '%s'",
        principal.teacher_id,
        _client_ip(request),
        class_id,
        old_name,
        cls.name,
    )

    return ClassOut.model_validate(cls)


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(
    class_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    """Delete a class and its teacher bindings. Only the owning teacher may delete."""
    cls = _ensure_teacher_class(principal, class_id, db)
    class_name = cls.name

    # Delete related messages (optional: could also keep them)
    db.query(models.Message).filter(models.Message.class_id == class_id).delete()
    # Delete teacher-class bindings
    db.query(models.TeacherClass).filter(models.TeacherClass.class_id == class_id).delete()
    # Delete the class itself
    db.delete(cls)
    db.commit()

    logger.info(
        "CLASS_DELETE | teacher_id=%d | IP=%s | 删除班级 class_id=%d, name=%s",
        principal.teacher_id,
        _client_ip(request),
        class_id,
        class_name,
    )


@router.post("/classes/{class_id}/regenerate-code", response_model=ClassOut)
def regenerate_pairing_code(
    class_id: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> ClassOut:
    """Regenerate the pairing code for a class. The old code becomes invalid immediately."""
    cls = _ensure_teacher_class(principal, class_id, db)
    new_code = generate_unique_pairing_code(db)
    cls.pairing_code = new_code
    db.commit()
    db.refresh(cls)
    return ClassOut.model_validate(cls)


def _ensure_teacher_class(
    principal: Principal, class_id: int, db: Session
) -> models.Class:
    """Verify the teacher is bound to this class and return the class object."""
    if principal.role != "teacher" or principal.teacher_id is None:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "仅教师可操作班级")
    # Check DB binding (JWT class_ids may be stale)
    if class_id not in principal.accessible_class_ids:
        binding = (
            db.query(models.TeacherClass)
            .filter_by(teacher_id=principal.teacher_id, class_id=class_id)
            .first()
        )
        if binding is None:
            raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "教师未绑定该班级")
    cls = db.query(models.Class).filter_by(id=class_id).first()
    if cls is None:
        raise ApiError(404, ErrorCode.CLASS_NOT_FOUND, "班级不存在")
    return cls
