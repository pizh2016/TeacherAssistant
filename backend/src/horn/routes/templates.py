"""Template routes: CRUD for teacher's custom message templates.

Phase 2: Teachers can create, read, update, and delete their own
persistent message templates.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import models
from ..auth import Principal, get_principal
from ..database import get_db
from ..errors import ApiError, ErrorCode
from ..schemas import TemplateCreate, TemplateOut, TemplateUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/templates", tags=["templates"])


def _client_ip(request: Request) -> str:
    if request.client:
        return f"{request.client.host}:{request.client.port}"
    return "unknown"


@router.get("", response_model=List[TemplateOut])
def list_templates(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> List[TemplateOut]:
    """Return all templates for the current teacher."""
    if principal.role != "teacher" or principal.teacher_id is None:
        return []
    rows = (
        db.query(models.TeacherTemplate)
        .filter(models.TeacherTemplate.teacher_id == principal.teacher_id)
        .order_by(models.TeacherTemplate.sort_order.asc(), models.TeacherTemplate.id.asc())
        .all()
    )
    return [TemplateOut.model_validate(t) for t in rows]


@router.post("", response_model=TemplateOut, status_code=201)
def create_template(
    payload: TemplateCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> TemplateOut:
    """Create a new template for the current teacher."""
    if principal.role != "teacher" or principal.teacher_id is None:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "仅教师可管理模板")

    # Get max sort_order
    max_order = db.query(models.TeacherTemplate).filter_by(
        teacher_id=principal.teacher_id
    ).count()

    tpl = models.TeacherTemplate(
        teacher_id=principal.teacher_id,
        content=payload.content,
        sort_order=max_order,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)

    logger.info(
        "TPL_CREATE | teacher_id=%d | IP=%s | 创建模板 tpl_id=%d",
        principal.teacher_id,
        _client_ip(request),
        tpl.id,
    )

    return TemplateOut.model_validate(tpl)


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int,
    payload: TemplateUpdate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> TemplateOut:
    """Update a template's content."""
    tpl = db.get(models.TeacherTemplate, template_id)
    if tpl is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.teacher_id != principal.teacher_id:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "只能编辑自己的模板")

    tpl.content = payload.content
    db.commit()
    db.refresh(tpl)

    logger.info(
        "TPL_UPDATE | teacher_id=%d | IP=%s | 更新模板 tpl_id=%d",
        principal.teacher_id,
        _client_ip(request),
        template_id,
    )

    return TemplateOut.model_validate(tpl)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> None:
    """Delete a template."""
    tpl = db.get(models.TeacherTemplate, template_id)
    if tpl is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "模板不存在")
    if tpl.teacher_id != principal.teacher_id:
        raise ApiError(403, ErrorCode.CLASS_FORBIDDEN, "只能删除自己的模板")

    db.delete(tpl)
    db.commit()

    logger.info(
        "TPL_DELETE | teacher_id=%d | IP=%s | 删除模板 tpl_id=%d",
        principal.teacher_id,
        _client_ip(request),
        template_id,
    )
