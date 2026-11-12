# Classroom Horn Backend

FastAPI backend with native WebSocket real-time communication for the classroom
announcement system (喊话小喇叭). Sync SQLAlchemy 2.0 over SQLite (WAL), JWT
pairing-code auth, and Alembic migrations.

> The frozen interface contract lives in
> [`docs/02-后端API设计与实现.md`](../docs/02-后端API设计与实现.md). It is the
> single source of truth for REST paths, the message envelope and WS events.

## Quick Start

### 1. Setup development environment

```powershell
# From backend/ - extracts the local Python ZIP into .venv and installs deps.
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

> **Note on `.venv`**: `setup.ps1` extracts a *full portable Python* into
> `backend/.venv` (not `python -m venv`), so there is **no `Scripts\Activate.ps1`**.
> Always invoke the interpreter directly as `.venv\python.exe` - do not activate.

### 2. Initialize / migrate the database

```powershell
# Apply Alembic migrations (creates data/classroom_horn.db with the 5 tables).
.venv\python.exe -m alembic upgrade head
```

The app also auto-creates tables and seeds default classes on startup, so this
step is only required when you want Alembic to own the schema version.

### 3. Start the development server

```powershell
# Foreground; add --dev (or --reload) for auto-reload during development.
.venv\python.exe -m horn --dev
```

Server starts at http://localhost:18800 (configurable via `defaults/settings.json` or `SERVER_PORT` env var)

- API documentation: http://localhost:18800/docs
- H5 teacher client: served from `teacher-app/` dev server (port 5173) during development

CLI flags: `--host`, `--port`, `--reload`/`--dev`, `--log-level`. Auto-reload is
force-disabled in a frozen (PyInstaller) executable.

### 4. Run tests

```powershell
.venv\python.exe -m pytest
```

### 5. Build product package

```powershell
# pythonenv + .pyc compiled release ZIP.
.venv\python.exe scripts/build_runtime.py --package --force
```

## Project Structure

```
backend/
├── src/horn/                 # Backend source package
│   ├── __main__.py           # CLI entry (argparse; frozen-safe reload)
│   ├── api.py                # FastAPI app factory (horn.api:app)
│   ├── config.py             # pydantic-settings; frozen-aware paths; fail-fast secret
│   ├── database.py           # sync engine/session, SQLite WAL + FK pragmas
│   ├── models.py             # 5 ORM tables (classes/teachers/teacher_classes/messages/scheduled_messages)
│   ├── schemas.py            # Pydantic v2 request/response models
│   ├── auth.py               # JWT (HS256) + pairing-code login + principal
│   ├── errors.py             # unified {error:{code,message,status}} envelope
│   ├── logging_conf.py       # console + rotating file logging
│   ├── seed.py               # default classes seeding
│   ├── routes/               # auth, classes, messages routers
│   └── ws/manager.py         # WebSocket channel manager + /ws/class/{class_id}
├── migrations/               # Alembic env + versions
├── static/teacher/           # H5 teacher client (index.html)
├── defaults/                 # seed data (classes_seed.json) + settings.json
├── scripts/                  # setup.ps1, build_runtime.py
├── tests/                    # pytest suite (REST + WebSocket)
├── requirements-*.txt        # dependency files (mirror pyproject.toml)
├── pyproject.toml            # canonical package + dependency config
├── alembic.ini               # Alembic config (URL resolved by migrations/env.py)
├── pip.ini                   # public PyPI config (mounted via PIP_CONFIG_FILE)
└── VERSION_BACKEND           # backend version (SemVer)
```

## Technology Stack

- **Framework**: FastAPI + Uvicorn (Starlette WebSocket)
- **Database**: SQLite (WAL) + SQLAlchemy 2.0 (sync) + Alembic
- **Authentication**: JWT via python-jose; pairing-code login (no password hashing)
- **Config**: JSON settings (defaults/ + data/ + env overrides)
- **TTS**: pyttsx3 (optional, offline)
- **Build**: pythonenv + .pyc compilation

## API Endpoints (see docs/02 for the full contract)

### REST
- `GET  /health` - health check
- `GET  /` - service info
- `POST /api/auth/pairing-login` - pairing-code login, returns a JWT
- `GET  /api/classes` - list classes accessible to the token
- `POST /api/messages` - send an announcement (Bearer token required)
- `GET  /api/messages/history?class_id=&page=&limit=` - paged history
- `GET  /api/messages/latest?class_id=&since=` - reconnect catch-up

### WebSocket
- `WS /ws/class/{class_id}` - first frame must be `join_class{class_id, token}`;
  server replies `connection_ack`, then pushes `new_message` / `pong`.

All errors use the envelope `{"error": {"code", "message", "status"}}`.

## Development Workflow

1. Modify code under `src/horn/`.
2. Run with `--dev` for auto-reload.
3. After model changes: `.venv\python.exe -m alembic revision --autogenerate -m "..."`
   then `.venv\python.exe -m alembic upgrade head`.
4. Verify with `.venv\python.exe -m pytest`.

## Deployment

See [`docs/00-总体技术方案设计.md`](../docs/00-总体技术方案设计.md) for the Docker and
pythonenv private-deployment guides.
