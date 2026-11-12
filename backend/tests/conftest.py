"""Pytest configuration.

Sets a throwaway DATABASE_URL and debug/test secrets BEFORE importing any horn
module (so the module-level engine binds to the temp DB), then provides a
``client`` fixture that rebuilds a fresh schema per test for determinism.
"""

import os
import tempfile
from pathlib import Path

# --- Must run before importing horn.* ---
_TMPDIR = Path(tempfile.mkdtemp(prefix="horn_test_"))
os.environ["DATABASE_URL"] = "sqlite:///" + (_TMPDIR / "test.db").as_posix()
os.environ["DEBUG"] = "True"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["CORS_ORIGINS"] = "*"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client():
    from horn.api import create_app
    from horn.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    app = create_app()
    # Entering the context runs the lifespan (init_db + seed defaults).
    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)


def login(client: TestClient, pairing_code: str = "123456", role: str = "display") -> dict:
    """Helper: perform a pairing-code login (display role) and return the JSON body."""
    resp = client.post(
        "/api/auth/pairing-login",
        json={"pairing_code": pairing_code, "role": role},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def teacher_login_by_name(client: TestClient, name: str = "张老师") -> dict:
    """Helper: perform a teacher name-based login and return the JSON body."""
    resp = client.post(
        "/api/auth/teacher-login",
        json={"name": name},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def refresh_teacher_token(teacher: dict, class_ids: list) -> dict:
    """Re-encode a teacher's JWT with updated class_ids (avoids re-login dedup)."""
    from horn.auth import create_token
    new_token = create_token(
        sub=f"teacher-{teacher['teacher_id']}",
        role="teacher",
        teacher_id=teacher["teacher_id"],
        class_ids=class_ids,
    )
    teacher = {**teacher, "token": new_token}
    return teacher


def setup_teacher_with_class(client: TestClient, teacher_name: str = "张老师") -> dict:
    """Create a teacher, create a class for them, and return teacher info with class.

    Returns: {"token": str, "teacher_id": int, "class_id": int, "classes": list}
    """
    teacher = teacher_login_by_name(client, teacher_name)
    # Create a class
    resp = client.post(
        "/api/classes",
        headers=auth_headers(teacher["token"]),
        json={"name": "测试班级"},
    )
    assert resp.status_code == 201, resp.text
    cls = resp.json()

    # Update token's class_ids claim by re-encoding (avoid re-login which triggers dedup)
    from horn.auth import create_token
    new_token = create_token(
        sub=f"teacher-{teacher['teacher_id']}",
        role="teacher",
        teacher_id=teacher["teacher_id"],
        class_ids=[cls["id"]],
    )
    teacher["token"] = new_token
    teacher["class_id"] = cls["id"]
    teacher["classes"] = [cls]
    return teacher
