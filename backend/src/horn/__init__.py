"""Classroom Horn Backend - FastAPI server with WebSocket real-time communication.

Package layout (Phase 1):
    horn.config        -- pydantic-settings configuration + secret validation
    horn.logging_conf  -- structured logging to backend/logs/
    horn.errors        -- unified error codes + exception handlers
    horn.database      -- sync SQLAlchemy engine/session (SQLite + WAL)
    horn.models        -- ORM models (classes/teachers/messages/...)
    horn.schemas       -- Pydantic request/response schemas
    horn.auth          -- JWT + pairing-code login + principal dependency
    horn.seed          -- default class seeding
    horn.ws.manager    -- WebSocket connection manager + /ws/class/{id}
    horn.routes        -- REST routers (auth/classes/messages)
    horn.api           -- FastAPI application factory
    horn.__main__      -- CLI entry point (argparse)
"""

__version__ = "0.1.0"
