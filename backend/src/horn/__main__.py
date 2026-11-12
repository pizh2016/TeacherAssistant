"""CLI entry point: ``python -m horn`` or the ``classroom-horn`` console script.

Flags are actually parsed (the old skeleton silently ignored them). Auto-reload
is opt-in for development only and is force-disabled in a frozen (PyInstaller)
executable, where the reloader cannot work.
"""

import argparse
import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    """Allow running without an editable install (adds backend/src to sys.path)."""
    src_path = Path(__file__).resolve().parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="classroom-horn",
        description="Classroom Horn backend server (FastAPI + WebSocket)",
    )
    parser.add_argument("--host", default=None, help="bind host (default: from settings.json)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default: from settings.json)")
    parser.add_argument("--reload", action="store_true", help="dev auto-reload on code changes")
    parser.add_argument("--dev", action="store_true", help="alias for --reload")
    parser.add_argument(
        "--api",
        action="store_true",
        help="(compat, default) start the API server; accepted and ignored",
    )
    parser.add_argument("--log-level", default="info", help="uvicorn log level")
    return parser


def main(argv=None) -> None:
    _ensure_src_on_path()
    args = build_parser().parse_args(argv)

    import uvicorn
    from horn.config import get_settings

    settings = get_settings()

    # CLI args override config; fallback to settings.json values
    host = args.host or settings.server_host
    port = args.port or settings.server_port

    reload = args.reload or args.dev
    # A frozen exe (PyInstaller) cannot use the reloader; it spawns subprocesses
    # and watches source files that do not exist at runtime.
    if getattr(sys, "frozen", False):
        reload = False

    print("=" * 60)
    print("  Classroom Horn Backend Server")
    print("=" * 60)
    print(f"  Listening on http://{host}:{port}")
    print(f"  API docs:   http://{host}:{port}/docs")
    print(f"  Reload:     {reload}")
    print("=" * 60)

    if reload:
        # Import-string form is required for uvicorn's reloader.
        uvicorn.run(
            "horn.api:app",
            host=host,
            port=port,
            reload=True,
            log_level=args.log_level,
        )
    else:
        from horn.api import app

        uvicorn.run(app, host=host, port=port, log_level=args.log_level)


if __name__ == "__main__":
    main()
