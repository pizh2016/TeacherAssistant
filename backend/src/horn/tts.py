"""Optional pyttsx3-based TTS backend for higher-quality audio generation.

Phase 2 P2: Generates audio files server-side using pyttsx3 (offline, no
network needed). The generated audio file path is stored in the message's
``audio_path`` field and served via the static file mount.

Usage: call ``generate_tts_audio(text, output_dir)`` from the send endpoint
when TTS is enabled. The display app can then play the audio file instead
of using Web Speech API.
"""

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    """Lazy-initialize the pyttsx3 engine (thread-safe singleton)."""
    global _engine
    if _engine is None:
        try:
            import pyttsx3
            _engine = pyttsx3.init()
            # Set default rate
            _engine.setProperty("rate", 160)
            logger.info("pyttsx3 TTS engine initialized")
        except Exception:
            logger.warning("pyttsx3 not available; TTS will fall back to browser Web Speech API")
            return None
    return _engine


def generate_tts_audio(text: str, output_dir: Path) -> str | None:
    """Generate an audio file for the given text.

    Returns the relative URL path (e.g. ``/static/uploads/tts_xxx.mp3``) or
    None if pyttsx3 is unavailable.
    """
    engine = _get_engine()
    if engine is None:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"tts_{uuid.uuid4().hex[:12]}.wav"
    filepath = output_dir / filename

    try:
        engine.save_to_file(text, str(filepath))
        engine.runAndWait()

        if filepath.exists() and filepath.stat().st_size > 0:
            relative = f"/static/uploads/{filename}"
            logger.debug("Generated TTS audio: %s", relative)
            return relative
        else:
            logger.warning("TTS file empty for text: %s", text[:50])
            return None
    except Exception:
        logger.exception("Failed to generate TTS audio")
        return None
