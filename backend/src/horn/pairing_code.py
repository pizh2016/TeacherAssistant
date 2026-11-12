"""Pairing code generation utilities.

Generates unique 6-digit numeric codes for class pairing.
Ensures uniqueness via database lookup with retry.
"""

import random
import string

from sqlalchemy.orm import Session

from . import models

MAX_RETRIES = 100
CODE_LENGTH = 6


def generate_unique_pairing_code(db: Session) -> str:
    """Generate a unique 6-digit pairing code not yet in the database.

    Uses random digits and retries up to MAX_RETRIES times if a collision
    occurs. Raises RuntimeError if no unique code can be generated.
    """
    digits = string.digits  # "0123456789"
    for _ in range(MAX_RETRIES):
        code = "".join(random.choices(digits, k=CODE_LENGTH))
        exists = db.query(models.Class).filter_by(pairing_code=code).first()
        if exists is None:
            return code
    raise RuntimeError(
        f"Unable to generate a unique {CODE_LENGTH}-digit pairing code "
        f"after {MAX_RETRIES} retries. The pairing code space may be exhausted."
    )
