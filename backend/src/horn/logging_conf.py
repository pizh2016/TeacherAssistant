"""Logging configuration: console + rotating file under backend/logs/.

Filters:
- Suppress uvicorn access logs (custom middleware handles request logging)
- Suppress /health and /static/* paths from custom middleware
"""

import logging
import logging.handlers
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
_configured = False


class PathFilter(logging.Filter):
    """Filter out log records whose message starts with a suppressed path."""

    SUPPRESSED_PREFIXES = ("/health", "/static/", "/ ")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(msg.startswith(p) for p in self.SUPPRESSED_PREFIXES)


def setup_logging(log_dir: Path, debug: bool = False) -> None:
    """Configure root logging once (idempotent)."""
    global _configured
    if _configured:
        return

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter(_LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers on repeated calls / reload
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "backend.log",
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(PathFilter())
        root.addHandler(file_handler)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
               for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.addFilter(PathFilter())
        root.addHandler(console)

    # Silence uvicorn access logs entirely — custom middleware handles request logging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").addFilter(PathFilter())
    logging.getLogger("uvicorn.error").setLevel(logging.DEBUG if debug else logging.INFO)

    _configured = True
