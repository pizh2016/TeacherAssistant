"""Step 3: Package release - assemble final installer ZIP.

Packages the built pythonenv + horn compiled code + defaults + teacher-app
build output into a distributable ZIP archive.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import stat
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from _build_shared import BuildContext

logger = logging.getLogger(__name__)


def _rmtree_safe(path: Path) -> None:
    """Remove directory tree, handling Windows read-only file permissions.

    On Windows, shutil.rmtree fails when encountering read-only files.
    This function first clears read-only attributes from all files,
    then safely removes the directory tree.

    Args:
        path: Directory path to remove
    """
    if not path.exists():
        return

    # First, clear read-only attributes from all files
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            filepath = os.path.join(root, name)
            try:
                os.chmod(filepath, stat.S_IWRITE | stat.S_IREAD)
            except (OSError, PermissionError):
                pass
        for name in dirs:
            dirpath = os.path.join(root, name)
            try:
                os.chmod(dirpath, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except (OSError, PermissionError):
                pass

    # Now safe to remove
    shutil.rmtree(path)


def package_release(ctx: BuildContext, backend_version: str) -> None:
    """Assemble final release package.

    Steps:
      1. Prepare package directory (copy pythonenv, defaults, teacher-app)
      2. Generate platform-specific startup script
      3. Copy version files
      4. Generate version.json and README.txt
      5. Create ZIP archive with progress logging
      6. Generate SHA256 checksum
    """
    logger.info("=" * 60)
    logger.info("Step 3/3: Package release (Backend v%s)", backend_version)
    logger.info("=" * 60)

    platform_tag = "win-x64" if sys.platform == "win32" else "linux-x64"
    logger.info("Build platform: %s", platform_tag)

    release_root = ctx.project_root / "release"
    package_name = "Classroom-Horn"
    zip_path = release_root / f"Classroom-Horn-v{backend_version}-{platform_tag}.zip"
    package_dir = release_root / package_name

    if package_dir.exists():
        _rmtree_safe(package_dir)
    if zip_path.exists():
        zip_path.unlink()

    package_dir.mkdir(parents=True, exist_ok=True)

    # Copy runtime/pythonenv/ (full Python environment)
    if ctx.pythonenv_dir.exists():
        pythonenv_target = package_dir / "runtime" / "pythonenv"
        logger.info("Copying runtime/pythonenv/ ...")
        shutil.copytree(ctx.pythonenv_dir, pythonenv_target)

    # Create data directories
    (package_dir / "data").mkdir(exist_ok=True)
    (package_dir / "logs").mkdir(exist_ok=True)

    # Copy defaults/ (factory config seeds)
    _copy_config_defaults(package_dir, ctx.backend_root)

    # Copy teacher-app build output (if exists)
    _copy_teacher_app(package_dir, ctx)

    # Copy admin-app build output (if exists)
    _copy_admin_app(package_dir, ctx)

    # Generate platform-specific startup script
    _generate_startup_scripts(package_dir, platform_tag)

    # Copy version files
    _copy_version_files(package_dir, ctx.backend_root)

    # Generate version.json
    version_info = {
        "product": "Classroom Horn",
        "backend_version": backend_version,
        "platform": platform_tag,
        "python_version": ctx.python_version,
        "runtime_layout": {
            "runtime/pythonenv": "runtime/pythonenv/ (standalone Python + Lib/site-packages/)",
            "defaults": "defaults/ (factory config seeds)",
            "teacher-app": "static/teacher/ (H5 teacher interface)",
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(package_dir / "version.json", "w", encoding="utf-8") as f:
        json.dump(version_info, f, indent=2, ensure_ascii=False)

    # Generate README.txt
    readme_lines = _build_readme_lines(backend_version, platform_tag)
    with open(package_dir / "README.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(readme_lines))

    # Create ZIP with progress logging
    _create_zip_with_progress(zip_path, release_root, package_name, package_dir)

    # Clean up temporary package directory
    if package_dir.exists():
        _rmtree_safe(package_dir)
        logger.info("Cleaned up temporary directory: %s", package_dir)

    # Generate SHA256
    with open(zip_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    with open(f"{zip_path}.sha256.txt", "w") as f:
        f.write(sha256)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    logger.info("Step 3 complete: %s (%.1f MB)", zip_path, zip_size_mb)
    logger.info("SHA256: %s", sha256)


def clean_build_dirs(ctx: BuildContext) -> None:
    """Clean all build artifacts (does NOT touch .venv dev environment)."""
    dirs_to_clean = [
        ctx.generated_dir,
        ctx.runtime_dir,
        ctx.backend_root / "build",
        ctx.backend_root / "dist",
    ]
    for d in dirs_to_clean:
        if d.exists():
            _rmtree_safe(d)
            logger.info("Removed: %s", d)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_startup_scripts(package_dir: Path, platform_tag: str) -> None:
    """Generate platform-specific startup script."""
    logger.info("Generating startup script for %s ...", platform_tag)

    if platform_tag == "win-x64":
        _generate_bat_launcher(package_dir)
    else:
        _generate_sh_launcher(package_dir)


def _generate_bat_launcher(package_dir: Path) -> None:
    """Generate start-backend.bat for Windows."""
    bat_content = r"""@echo off
REM ============================================================================
REM Classroom Horn Backend - Portable Launcher (Windows)
REM ============================================================================
REM Usage:
REM   start-backend.bat                    Start backend server (port from settings.json)
REM   start-backend.bat --port 9000        Start on port 9000 (override config)
REM   start-backend.bat --dev              Start with auto-reload
REM ============================================================================

setlocal enabledelayedexpansion

REM Get the directory of this script (installation root)
set "SCRIPT_DIR=%~dp0"

REM Locate embedded Python interpreter
set "PYTHON_EXE=%SCRIPT_DIR%runtime\pythonenv\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Embedded Python interpreter not found:
    echo   %PYTHON_EXE%
    echo.
    echo Please ensure the runtime/pythonenv/ directory is intact.
    exit /b 1
)

REM Launch backend via python -m horn (forward all arguments)
"%PYTHON_EXE%" -I -m horn %*
"""
    bat_path = package_dir / "start-backend.bat"
    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(bat_content)
    logger.info("Generated: %s", bat_path.name)


def _generate_sh_launcher(package_dir: Path) -> None:
    """Generate start-backend.sh for Linux."""
    import stat
    sh_content = r"""#!/usr/bin/env bash
# ============================================================================
# Classroom Horn Backend - Portable Launcher (Linux)
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXE="$SCRIPT_DIR/runtime/pythonenv/bin/python"

if [ ! -f "$PYTHON_EXE" ]; then
    echo "[ERROR] Embedded Python interpreter not found:"
    echo "  $PYTHON_EXE"
    exit 1
fi

exec "$PYTHON_EXE" -I -m horn "$@"
"""
    sh_path = package_dir / "start-backend.sh"
    with open(sh_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sh_content)
    sh_path.chmod(sh_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    logger.info("Generated: %s (executable)", sh_path.name)


def _copy_config_defaults(package_dir: Path, backend_root: Path) -> None:
    """Copy factory config seeds (defaults/) into the package."""
    src = backend_root / "defaults"
    dst = package_dir / "defaults"

    if src.exists():
        shutil.copytree(src, dst)
        logger.info("Copied: defaults/ -> %s/", dst.name)
    else:
        logger.warning("defaults/ not found at %s, skipping", src)


def _copy_teacher_app(package_dir: Path, ctx: BuildContext) -> None:
    """Copy teacher-app build output into the package.

    The runtime code (api.py) mounts static files from
    ``BACKEND_ROOT / "static" / "teacher"``, so the release package
    must place the built files at ``static/teacher/``.
    """
    dst = package_dir / "static" / "teacher"
    dst.mkdir(parents=True, exist_ok=True)

    # Try teacher-app/dist/ first (Vite build output)
    teacher_dist = ctx.project_root / "teacher-app" / "dist"
    if teacher_dist.exists():
        shutil.copytree(teacher_dist, dst, dirs_exist_ok=True)
        logger.info("Copied: teacher-app/dist/ -> static/teacher/")
        return

    # Fallback: backend/static/teacher/ (legacy location)
    legacy = ctx.backend_root / "static" / "teacher"
    if legacy.exists():
        shutil.copytree(legacy, dst, dirs_exist_ok=True)
        logger.info("Copied: static/teacher/ -> static/teacher/ (legacy)")
        return

    logger.warning("teacher-app build output not found, skipping")


def _copy_admin_app(package_dir: Path, ctx: BuildContext) -> None:
    """Copy admin-app build output into the package.

    The runtime code (api.py) mounts admin files from
    ``BACKEND_ROOT / "static" / "admin"``, so the release package
    must place the built files at ``static/admin/``.
    """
    dst = package_dir / "static" / "admin"
    dst.mkdir(parents=True, exist_ok=True)

    # Try admin-app/dist/ first (Vite build output)
    admin_dist = ctx.project_root / "admin-app" / "dist"
    if admin_dist.exists():
        shutil.copytree(admin_dist, dst, dirs_exist_ok=True)
        logger.info("Copied: admin-app/dist/ -> static/admin/")
        return

    # Fallback: backend/static/admin/ (legacy location)
    legacy = ctx.backend_root / "static" / "admin"
    if legacy.exists():
        shutil.copytree(legacy, dst, dirs_exist_ok=True)
        logger.info("Copied: static/admin/ -> static/admin/ (legacy)")
        return

    logger.warning("admin-app build output not found, skipping")


def _copy_version_files(package_dir: Path, backend_root: Path) -> None:
    """Copy backend version file into the package root."""
    src = backend_root / "VERSION_BACKEND"
    if src.exists():
        shutil.copy2(src, package_dir / "VERSION_BACKEND")
        logger.info("Copied: VERSION_BACKEND")
    else:
        logger.warning("VERSION_BACKEND not found, skipping")


def _build_readme_lines(backend_version: str, platform_tag: str) -> list[str]:
    """Build platform-specific README.txt content lines."""
    launcher = "start-backend.bat" if platform_tag == "win-x64" else "./start-backend.sh"

    return [
        f"Classroom Horn (Backend v{backend_version})",
        f"Platform: {platform_tag}",
        "",
        "Directory structure:",
        "  runtime/pythonenv/    - Standalone Python environment",
        "  defaults/             - Read-only factory config seeds (settings.json)",
        "  static/teacher/       - H5 teacher interface (static files)",
        "  data/                 - Runtime data directory (SQLite DB, settings.json)",
        "  logs/                 - Log files",
        "  VERSION_BACKEND       - Backend version",
        "  version.json          - Machine-readable version metadata",
        "",
        "Quick start:",
        f"  {launcher}                    (Start backend, port from settings.json)",
        f"  {launcher} --port 9000        (Override port to 9000)",
        f"  {launcher} --dev              (Start with auto-reload)",
        "",
        "Configuration:",
        "  Factory defaults: defaults/settings.json (read-only)",
        "  Runtime config:   data/settings.json (created on first launch)",
        "  Secrets:          Set JWT_SECRET_KEY environment variable",
        "",
        "This product includes an embedded Python runtime.",
        "No Python installation required.",
    ]


def _create_zip_with_progress(
    zip_path: Path,
    release_root: Path,
    package_name: str,
    package_dir: Path,
) -> None:
    """Create ZIP archive with progress logging."""
    logger.info("Preparing ZIP archive: %s", zip_path.name)
    all_files: list[tuple[Path, str]] = []
    total_size = 0

    for f in package_dir.rglob("*"):
        if f.is_file():
            arcname = f"{package_name}/{f.relative_to(package_dir).as_posix()}"
            all_files.append((f, arcname))
            total_size += f.stat().st_size

    file_count = len(all_files)
    total_mb = total_size / (1024 * 1024)
    logger.info("Compressing %d files (%.1f MB) ...", file_count, total_mb)

    t0 = time.monotonic()

    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for i, (abs_path, arcname) in enumerate(all_files, 1):
            zf.write(str(abs_path), arcname)

            if file_count > 100:
                pct = i / file_count * 100
                if abs(pct - round(pct / 25) * 25) < (100 / file_count):
                    if int(pct) in (25, 50, 75):
                        logger.info("  ... %d%% (%d/%d files)", int(pct), i, file_count)

    elapsed = time.monotonic() - t0
    zip_size = zip_path.stat().st_size
    zip_mb = zip_size / (1024 * 1024)
    ratio = (1 - zip_size / total_size) * 100 if total_size > 0 else 0

    logger.info(
        "ZIP created: %s (%.1f MB, %.1f%% compression, %.1fs)",
        zip_path.name, zip_mb, ratio, elapsed,
    )
