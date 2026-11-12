"""Seed default classes from backend/defaults/classes_seed.json.

Runs on startup only when the classes table is empty, so an existing deployment
is never overwritten. Provides an out-of-the-box usable system for development.
"""

import json
import logging

from sqlalchemy.orm import Session

from . import models
from .config import BACKEND_ROOT

logger = logging.getLogger(__name__)

SEED_FILE = BACKEND_ROOT / "defaults" / "classes_seed.json"


def seed_defaults(db: Session) -> int:
    """Seed classes if none exist. Returns the number of classes inserted."""
    if db.query(models.Class).count() > 0:
        return 0
    if not SEED_FILE.exists():
        logger.info("No seed file at %s; skipping seeding", SEED_FILE)
        return 0

    try:
        data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read seed file %s: %s", SEED_FILE, exc)
        return 0

    inserted = 0
    for item in data.get("classes", []):
        name = item.get("name")
        code = item.get("pairing_code")
        if not name or not code:
            continue
        exists = db.query(models.Class).filter_by(pairing_code=str(code)).first()
        if exists is None:
            db.add(models.Class(name=str(name), pairing_code=str(code)))
            inserted += 1
    db.commit()
    if inserted:
        logger.info("Seeded %d default class(es)", inserted)
    return inserted
