"""Application configuration via JSON settings files + environment overrides.

Configuration loading order (later overrides earlier):
  1. defaults/settings.json  — factory defaults (read-only, shipped with product)
  2. data/settings.json      — user overrides (created on first launch, persistent)
  3. Environment variables   — JWT_SECRET_KEY, DEBUG, etc. (highest priority)

This replaces the previous .env-based configuration (plan §4).

Frozen (pythonenv) builds separate two roots:
  BACKEND_ROOT -> read-only bundled resources (defaults/, teacher-app/).
                  Under pythonenv this is the directory containing runtime/.
  DATA_ROOT    -> stable, writable base for runtime data (data/, logs/).
                  Under pythonenv this is the directory holding runtime/.
  In a normal source checkout both point at backend/.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Root directory resolution
# ---------------------------------------------------------------------------

# Detect frozen mode: pythonenv builds place horn inside
#   <root>/runtime/pythonenv/Lib/site-packages/horn/
# In a source checkout the package lives under
#   <backend>/src/horn/
# We distinguish the two by checking whether the path contains
# "site-packages" (frozen) vs "src" (editable / source checkout).
_resolved = Path(__file__).resolve()
IS_PYTHONENV = any(p.name == "site-packages" for p in _resolved.parents)

if IS_PYTHONENV:
    # Installed layout: <root>/runtime/pythonenv/Lib/site-packages/horn/config.py
    # -> backend/ is <root>/
    _horn_pkg = _resolved.parent                                   # horn/
    _sp = _horn_pkg.parent                                         # site-packages/
    _pythonenv = _sp.parent.parent                                 # pythonenv/
    _root = _pythonenv.parent.parent                               # <root>/
    BACKEND_ROOT = _root
    DATA_ROOT = _root
else:
    # Source checkout: backend/src/horn/config.py -> backend/
    BACKEND_ROOT = _resolved.parent.parent.parent
    DATA_ROOT = BACKEND_ROOT

# ---------------------------------------------------------------------------
# Settings file paths
# ---------------------------------------------------------------------------

DEFAULTS_DIR = BACKEND_ROOT / "defaults"
DEFAULTS_SETTINGS = DEFAULTS_DIR / "settings.json"
USER_SETTINGS = DATA_ROOT / "data" / "settings.json"

# Placeholder for JWT secret; must be replaced in production.
DEFAULT_JWT_SECRET = "your-secret-key-change-in-production"

_SQLITE_PREFIX = "sqlite:///"


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file, returning empty dict if not found or invalid."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge *override* into *base* (non-destructive). Returns new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_json(data: dict, prefix: str = "") -> dict[str, Any]:
    """Flatten nested JSON to UPPER_SNAKE env-var-style keys.

    Example: {"app": {"name": "X"}} -> {"APP_NAME": "X"}
    """
    items: dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}_{key.upper()}" if prefix else key.upper()
        if isinstance(value, dict):
            items.update(_flatten_json(value, full_key))
        else:
            items[full_key] = value
    return items


# ---------------------------------------------------------------------------
# Settings class (lightweight, no pydantic dependency for JSON loading)
# ---------------------------------------------------------------------------


class Settings:
    """Runtime settings loaded from JSON files + env overrides.

    Field names match the flattened JSON keys (lowercase, underscored).
    """

    def __init__(self) -> None:
        # Load and merge settings
        defaults = _read_json(DEFAULTS_SETTINGS)
        user = _read_json(USER_SETTINGS)
        merged = _deep_merge(defaults, user)

        # Apply environment variable overrides
        self._apply_env_overrides(merged)

        # Extract fields from nested structure
        self.app_name: str = merged.get("app", {}).get("name", "Classroom Horn")
        self.app_version: str = merged.get("app", {}).get("version", "0.1.0")
        self.debug: bool = merged.get("app", {}).get("debug", True)

        self.server_host: str = merged.get("server", {}).get("host", "0.0.0.0")
        self.server_port: int = merged.get("server", {}).get("port", 18800)

        self.database_url: str = merged.get("database", {}).get(
            "url", "sqlite:///./data/classroom_horn.db"
        )

        self.jwt_secret_key: str = merged.get("auth", {}).get(
            "jwt_secret_key", DEFAULT_JWT_SECRET
        )
        self.jwt_algorithm: str = merged.get("auth", {}).get("jwt_algorithm", "HS256")
        self.access_token_expire_minutes: int = merged.get("auth", {}).get(
            "access_token_expire_minutes", 30
        )

        self.ws_heartbeat_interval: int = merged.get("ws", {}).get(
            "heartbeat_interval", 30
        )
        self.ws_max_reconnect_attempts: int = merged.get("ws", {}).get(
            "max_reconnect_attempts", 5
        )
        self.ws_join_timeout: int = merged.get("ws", {}).get("join_timeout", 10)

        self.cors_origins: str = merged.get("cors", {}).get("origins", "*")

    def _apply_env_overrides(self, merged: dict) -> None:
        """Apply environment variable overrides to merged settings.

        Supports both flat env vars (JWT_SECRET_KEY) and nested JSON-style
        env vars (APP_NAME -> app.name).
        """
        # Direct env var overrides (highest priority)
        env_map = {
            "APP_NAME": ("app", "name"),
            "APP_VERSION": ("app", "version"),
            "DEBUG": ("app", "debug"),
            "SERVER_HOST": ("server", "host"),
            "SERVER_PORT": ("server", "port"),
            "DATABASE_URL": ("database", "url"),
            "JWT_SECRET_KEY": ("auth", "jwt_secret_key"),
            "JWT_ALGORITHM": ("auth", "jwt_algorithm"),
            "ACCESS_TOKEN_EXPIRE_MINUTES": ("auth", "access_token_expire_minutes"),
            "WS_HEARTBEAT_INTERVAL": ("ws", "heartbeat_interval"),
            "WS_MAX_RECONNECT_ATTEMPTS": ("ws", "max_reconnect_attempts"),
            "WS_JOIN_TIMEOUT": ("ws", "join_timeout"),
            "CORS_ORIGINS": ("cors", "origins"),
        }

        for env_key, path in env_map.items():
            value = os.environ.get(env_key)
            if value is not None:
                # Navigate to the correct nested level
                node = merged
                for part in path[:-1]:
                    if part not in node:
                        node[part] = {}
                    node = node[part]
                # Type conversion
                leaf = path[-1]
                if leaf in ("debug",):
                    node[leaf] = value.strip().lower() in ("true", "1", "yes")
                elif leaf in ("access_token_expire_minutes", "ws_heartbeat_interval",
                              "ws_max_reconnect_attempts", "ws_join_timeout",
                              "server_port", "port"):
                    node[leaf] = int(value)
                else:
                    node[leaf] = value

    @property
    def sqlalchemy_url(self) -> str:
        """Return an absolute SQLAlchemy URL, creating the parent dir for sqlite."""
        url = self.database_url
        if url.startswith(_SQLITE_PREFIX):
            raw = url[len(_SQLITE_PREFIX):]
            path = Path(raw)
            if not path.is_absolute():
                path = (DATA_ROOT / path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return _SQLITE_PREFIX + path.as_posix()
        return url

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_secrets(self) -> None:
        """Fail fast if a placeholder secret is used outside debug mode."""
        if not self.debug and self.jwt_secret_key == DEFAULT_JWT_SECRET:
            raise RuntimeError(
                "JWT_SECRET_KEY is still the default placeholder. Set a strong "
                "secret via environment variable or data/settings.json before "
                "running with debug=false."
            )


# ---------------------------------------------------------------------------
# Runtime config modification API (whitelist-based)
# ---------------------------------------------------------------------------

# Keys that can be modified at runtime via the settings API.
# Maps dotted key -> (json_path, type, description)
RUNTIME_CONFIG_KEYS: dict[str, tuple[list[str], type, str]] = {
    "ws.heartbeat_interval": (["ws", "heartbeat_interval"], int, "WS 心跳间隔(秒)"),
    "ws.max_reconnect_attempts": (["ws", "max_reconnect_attempts"], int, "WS 最大重连次数"),
    "ws.join_timeout": (["ws", "join_timeout"], int, "WS 加入超时(秒)"),
    "cors.origins": (["cors", "origins"], str, "CORS 允许的来源"),
    "app.debug": (["app", "debug"], bool, "调试模式"),
}


def update_runtime_setting(key: str, value: Any) -> None:
    """Update a runtime-modifiable setting and persist to data/settings.json.

    Only keys in RUNTIME_CONFIG_KEYS can be modified. Raises ValueError for
    unknown keys or invalid values.
    """
    if key not in RUNTIME_CONFIG_KEYS:
        raise ValueError(f"不支持运行时修改的配置项: {key}")

    json_path, expected_type, _desc = RUNTIME_CONFIG_KEYS[key]

    # Type coercion
    if expected_type is bool:
        if isinstance(value, str):
            value = value.strip().lower() in ("true", "1", "yes")
        value = bool(value)
    elif expected_type is int:
        value = int(value)

    # Read current user settings
    user_settings = _read_json(USER_SETTINGS)

    # Navigate and set
    node = user_settings
    for part in json_path[:-1]:
        if part not in node:
            node[part] = {}
        node = node[part]
    node[json_path[-1]] = value

    # Persist
    USER_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    USER_SETTINGS.write_text(
        json.dumps(user_settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Updated runtime setting: %s = %s", key, value)

    # Invalidate cached settings
    get_settings.cache_clear()


def list_runtime_settings() -> dict[str, Any]:
    """List all runtime-modifiable settings with their current values."""
    settings = get_settings()
    result = {}
    for key, (json_path, _type, desc) in RUNTIME_CONFIG_KEYS.items():
        # Navigate the settings object
        value = settings
        for part in json_path:
            value = getattr(value, "_".join(json_path), None)
            break
        result[key] = {"description": desc, "value": value}
    return result


# ---------------------------------------------------------------------------
# Cached singleton
# ---------------------------------------------------------------------------


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
