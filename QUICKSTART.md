# Classroom Horn - Quick Start Guide

## Current Status

✅ **Phase 1 backend core**: FastAPI + WebSocket + SQLite (SQLAlchemy 2.0) +
JWT pairing-code auth + Alembic migrations, covered by a pytest suite.

- Backend server: http://localhost:18800
- API documentation: http://localhost:18800/docs
- H5 teacher client: http://localhost:18800/static/teacher/index.html
- Interface contract: [`docs/02-后端API设计与实现.md`](docs/02-后端API设计与实现.md)

> All commands below run from `backend/` and call the portable interpreter
> directly (`.venv\python.exe`). The `.venv` is a full Python extract, so there
> is **no `Activate.ps1`** - do not try to activate it.

## Daily Development Workflow

### Start Backend Server

```powershell
cd backend
.venv\python.exe -m horn            # production-style (no reload)
.venv\python.exe -m horn --dev      # development (auto-reload)
```

### Initialize / Migrate the Database

```powershell
cd backend
.venv\python.exe -m alembic upgrade head
```

Startup also auto-creates tables and seeds the default classes
(`一年级A班` / code `123456`, `一年级B班` / code `654321`).

### Test API Endpoints

```bash
# Health check
curl http://localhost:18800/health

# 1) Pairing-code login -> returns { token, role, teacher_id, classes[] }
curl -X POST http://localhost:18800/api/auth/pairing-login \
  -H "Content-Type: application/json" \
  -d '{"pairing_code": "123456", "role": "teacher"}'

# 2) Send a message (integer class_id + Bearer token from step 1)
curl -X POST http://localhost:18800/api/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"class_id": 1, "content": "上课了", "display_mode": "popup", "reminder_level": "normal", "duration": 120, "tts_enabled": true}'

# 3) History
curl http://localhost:18800/api/messages/history?class_id=1 \
  -H "Authorization: Bearer <TOKEN>"
```

### Access H5 Teacher Client

Open http://localhost:18800/static/teacher/index.html, log in with a class
pairing code (e.g. `123456`), pick a class, compose a message and click
"发送喊话".

### Run Tests

```powershell
cd backend
.venv\python.exe -m pytest
```

## Project Structure

```
backend/
├── src/horn/           # Backend source package (api/config/models/auth/routes/ws)
├── migrations/         # Alembic env.py + versions/
├── static/teacher/     # H5 teacher client
├── defaults/           # Seed data (classes_seed.json)
├── scripts/            # setup.ps1, build_runtime.py
├── tests/              # pytest suite (REST + WebSocket)
├── data/               # SQLite database (runtime, gitignored)
├── logs/               # Log files (runtime, gitignored)
└── .venv/              # Portable Python environment
```

## Troubleshooting

### Server won't start
- Check whether port 18800 is already in use.
- Verify `.venv\python.exe` exists; re-run `scripts/setup.ps1` if not.
- `JWT_SECRET_KEY` fail-fast: with `DEBUG=False` you must set a non-default
  secret in `backend/.env`.

### Dependencies not installed
```powershell
cd backend
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

### Reset environment
```powershell
cd backend
Remove-Item -Recurse -Force .venv
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

## Key Files to Modify

| Task | File to Edit |
|------|-------------|
| Add a REST endpoint | `src/horn/routes/*.py` |
| Change the WS protocol | `src/horn/ws/manager.py` |
| Add/adjust a DB model | `src/horn/models.py` + a new Alembic migration |
| Update request/response shapes | `src/horn/schemas.py` |
| Update H5 UI | `static/teacher/index.html` |
| Change configuration | `.env` (see `.env.example`) |
| Add a dependency | `pyproject.toml` **and** the matching `requirements-*.txt` |
| Modify the build | `scripts/build_runtime.py` |

## Useful Commands

```powershell
# View installed packages
.venv\python.exe -m pip list

# Autogenerate a migration after model changes
.venv\python.exe -m alembic revision --autogenerate -m "describe change"
.venv\python.exe -m alembic upgrade head

# Run tests
.venv\python.exe -m pytest

# Build product package (exe + ZIP + version.json)
.venv\python.exe scripts/build_runtime.py --package --force
```

---

**Backend Version**: 0.2.0
