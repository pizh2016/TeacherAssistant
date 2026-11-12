"""Auth routes: POST /api/auth/pairing-login + POST /api/auth/teacher-login."""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import auth as auth_service
from ..database import get_db
from ..schemas import LoginResponse, PairingLoginRequest, TeacherLoginRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    """Extract client IP from request."""
    if request.client:
        return f"{request.client.host}:{request.client.port}"
    return "unknown"


@router.post("/pairing-login", response_model=LoginResponse)
def pairing_login(
    payload: PairingLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Pairing-code login — display-only in Phase 2."""
    result = auth_service.pairing_login(db, payload.pairing_code, payload.role)
    ip = _client_ip(request)
    logger.info(
        "DISPLAY_LOGIN | display_id=%s, class_id=%s | IP=%s | 配对登录成功",
        result.teacher_id,
        result.classes[0].id if result.classes else None,
        ip,
    )
    return result


@router.post("/teacher-login", response_model=LoginResponse)
def teacher_login(
    payload: TeacherLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Teacher name-based login — auto-register on first use."""
    result = auth_service.teacher_login(db, payload.name)
    ip = _client_ip(request)
    logger.info(
        "TEACHER_LOGIN | teacher_id=%d, name=%s | IP=%s | 登录成功",
        result.teacher_id,
        result.teacher_name,
        ip,
    )
    return result
