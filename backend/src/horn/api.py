"""FastAPI application factory (docs/02 is the接口 contract source of truth).

Exposes a module-level ``app`` so it can be referenced as ``horn.api:app`` by
uvicorn (dev reload) and PyInstaller (frozen).
"""

import logging
import mimetypes
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BACKEND_ROOT, DATA_ROOT, get_settings
from .database import SessionLocal, init_db
from .errors import register_exception_handlers
from .logging_conf import setup_logging
from .routes import auth as auth_routes
from .routes import classes as classes_routes
from .routes import messages as messages_routes
from .routes import templates as templates_routes
from .schemas import HealthOut
from .seed import seed_defaults
from .ws.manager import router as ws_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables, seed defaults, and start the scheduler."""
    init_db()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()

    # Ensure uploads directory exists (needed for StaticFiles mount)
    uploads_dir = BACKEND_ROOT / "static" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Start APScheduler and load existing jobs
    from .scheduler import start_scheduler, load_existing_jobs
    start_scheduler()
    load_existing_jobs()

    logger.info("Classroom Horn backend started")
    yield

    # Shutdown scheduler
    from .scheduler import shutdown_scheduler
    shutdown_scheduler()
    logger.info("Classroom Horn backend stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    # Fail fast if a placeholder secret would run outside debug mode.
    settings.validate_secrets()
    setup_logging(DATA_ROOT / "logs", settings.debug)

    app = FastAPI(
        title="Classroom Horn API",
        description="Real-time classroom announcement system (喊话小喇叭)",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS: never combine a wildcard origin with credentials (invalid per spec).
    # The H5 client is served same-origin, so CORS is mainly for dev tools.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Request logging middleware — filters health/static/root to reduce noise
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        path = request.url.path
        # Skip logging for health checks, static assets, and root probe
        if path == "/health" or path.startswith("/static/") or path == "/":
            return response
        logger.info(
            "%s %s -> %d (%.0fms)",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @app.get("/", tags=["system"])
    async def root():
        return {
            "status": "ok",
            "service": "Classroom Horn Backend",
            "version": settings.app_version,
        }

    @app.get("/health", response_model=HealthOut, tags=["system"])
    async def health() -> HealthOut:
        return HealthOut(
            status="healthy",
            timestamp=datetime.now(timezone.utc),
            version=settings.app_version,
        )

    app.include_router(auth_routes.router)
    app.include_router(classes_routes.router)
    app.include_router(messages_routes.router)
    app.include_router(templates_routes.router)
    app.include_router(ws_router)

    # Fix Windows MIME type for .js files (registry maps .js -> text/plain)
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("application/javascript", ".mjs")
    
    # Static file mounts
    static_teacher = BACKEND_ROOT / "static" / "teacher"
    if static_teacher.exists():
        app.mount(
            "/static/teacher",
            StaticFiles(directory=str(static_teacher), html=True),
            name="teacher",
        )

    static_uploads = BACKEND_ROOT / "static" / "uploads"
    if static_uploads.exists():
        app.mount(
            "/static/uploads",
            StaticFiles(directory=str(static_uploads)),
            name="uploads",
        )

    # Admin app static mount
    static_admin = BACKEND_ROOT / "static" / "admin"
    if static_admin.exists():
        app.mount(
            "/static/admin",
            StaticFiles(directory=str(static_admin), html=True),
            name="admin",
        )

    return app


app = create_app()
