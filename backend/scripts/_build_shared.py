"""Shared constants, BuildContext, and utility functions for build steps.

All build step modules import from this module to share path definitions
and common helpers. BuildContext carries all mutable state between steps.

Build workflow:
  Phase 1: Build runtime/pythonenv/ (smart skip if already valid + incremental deps)
  Phase 2 (optional): Compile .py -> .pyc and slim (smart skip if already compiled)
  --force: Disable all smart skip mechanisms for full rebuild
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path constants (relative to this script's location)
# ---------------------------------------------------------------------------

# scripts/ -> backend/ (project root for the backend)
BACKEND_ROOT = Path(__file__).resolve().parent.parent
# backend/ -> TeacherAssistant/ (workspace root)
PROJECT_ROOT = BACKEND_ROOT.parent

# .venv is inside backend/, created by setup.ps1
VENV_DIR = BACKEND_ROOT / ".venv"

# Project-level directories (inside backend/)
GENERATED_DIR = BACKEND_ROOT / "generated"
RUNTIME_DIR = BACKEND_ROOT / "runtime"
PYTHONENV_DIR = RUNTIME_DIR / "pythonenv"

# Cache directory for downloaded files
CACHE_DIR = GENERATED_DIR / "cache"

# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

PYTHON_VERSION = "3.10.11"
PYTHON_ZIP_NAME = f"python-{PYTHON_VERSION}-amd64.zip"

# Public python.org download URL (fallback)
PYTHON_ORG_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ZIP_NAME}"

# ---------------------------------------------------------------------------
# Runtime requirement files (installed into pythonenv in order)
# ---------------------------------------------------------------------------

RUNTIME_REQUIREMENTS = [
    "requirements-core.txt",
    "requirements-db.txt",
    "requirements-auth.txt",
    "requirements-tts.txt",
]

# Extra packages to install (not in any requirements file)
RUNTIME_EXTRA_PACKAGES: list[str] = []

# Packages to remove from pythonenv AFTER install (to save space)
STRIP_PACKAGES = [
    "tkinter", "_tkinter",
    "setuptools", "pkg_resources", "_distutils_hack",
    "pyreadline3",
]

# ---------------------------------------------------------------------------
# Standard library modules to EXCLUDE from the runtime pythonenv.
# ---------------------------------------------------------------------------

STDLIB_EXCLUDE_DIRS = [
    # GUI / desktop
    "tkinter", "turtle", "turtledemo", "idlelib",
    # Testing infrastructure
    "test", "unittest",
    # Development / documentation tools
    "pydoc", "pydoc_data", "venv", "lib2to3",
    # Multimedia
    "audiotools", "wave", "sunau", "aifc", "chunk", "sndhdr", "ossaudiodev",
    # Legacy network protocols
    "telnetlib", "nntplib", "ftplib", "imaplib", "poplib", "smtpd",
    # Platform-specific
    "curses", "readline", "termios", "pty", "crypt",
    "nis", "fcntl", "grp", "pwd", "resource", "posix",
    "_aix_support", "_osx_support", "antigravity",
    # Web frameworks / demos (stdlib side)
    "cgi", "cgitb",
    # Other unnecessary modules
    "xdrlib", "imghdr", "code", "codeop", "pdb", "profile", "pstats",
    "timeit", "tracemalloc", "wsgiref", "_wasm",
]

# Files / globs to remove from pythonenv root after extraction
STDLIB_EXCLUDE_ROOT_PATTERNS = [
    "tcl*", "tk*", "_tk*", "zlib1.dll",
]


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


def read_version() -> str:
    """Read backend version from VERSION_BACKEND file.

    Returns:
        Backend version string (e.g., "0.1.0").

    Raises:
        FileNotFoundError: If VERSION_BACKEND file does not exist.
        ValueError: If VERSION_BACKEND file is empty or malformed.
    """
    version_file = BACKEND_ROOT / "VERSION_BACKEND"
    if not version_file.exists():
        raise FileNotFoundError(
            f"VERSION_BACKEND file not found: {version_file}\n"
            "Please create a VERSION_BACKEND file in backend/ with a "
            "semantic version (e.g., 0.1.0)."
        )

    version = version_file.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError(f"VERSION_BACKEND file is empty: {version_file}")

    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(
            f"Invalid version format: '{version}'. "
            "Expected SemVer format: MAJOR.MINOR.PATCH (e.g., 0.1.0)"
        )

    return version


def read_gui_version() -> str:
    """Read display-app version from display-app/package.json.

    Returns:
        GUI version string (e.g., "0.1.0"), or "0.0.0" if not found.
    """
    import json
    pkg = PROJECT_ROOT / "display-app" / "package.json"
    if not pkg.exists():
        return "0.0.0"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except (json.JSONDecodeError, OSError):
        return "0.0.0"


def read_teacher_version() -> str:
    """Read teacher-app version from teacher-app/package.json.

    Returns:
        Teacher app version string, or "0.0.0" if not found.
    """
    import json
    pkg = PROJECT_ROOT / "teacher-app" / "package.json"
    if not pkg.exists():
        return "0.0.0"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except (json.JSONDecodeError, OSError):
        return "0.0.0"


# ---------------------------------------------------------------------------
# BuildContext: shared state passed to all step functions
# ---------------------------------------------------------------------------


@dataclass
class BuildContext:
    """Mutable state shared across build steps."""

    backend_root: Path = BACKEND_ROOT
    project_root: Path = PROJECT_ROOT
    venv_dir: Path = VENV_DIR
    runtime_dir: Path = RUNTIME_DIR
    pythonenv_dir: Path = PYTHONENV_DIR
    generated_dir: Path = GENERATED_DIR
    cache_dir: Path = CACHE_DIR

    python_version: str = PYTHON_VERSION

    # Derived helpers -------------------------------------------------------

    @property
    def venv_python(self) -> Path:
        """python.exe inside .venv/."""
        exe = self.venv_dir / "python.exe"
        if exe.exists():
            return exe
        exe_scripts = self.venv_dir / "Scripts" / "python.exe"
        if exe_scripts.exists():
            return exe_scripts
        raise FileNotFoundError(f"Python not found in .venv: {exe}")

    @property
    def pythonenv_python(self) -> Path:
        """python.exe inside runtime/pythonenv/."""
        return self.pythonenv_dir / "python.exe"

    @property
    def venv_site_packages(self) -> Path:
        """Locate site-packages directory inside .venv."""
        sp = self.venv_dir / "Lib" / "site-packages"
        if sp.exists():
            return sp
        raise FileNotFoundError(f"site-packages not found in .venv: {sp}")

    @property
    def pythonenv_site_packages(self) -> Path:
        """Locate site-packages directory inside pythonenv/."""
        return self.pythonenv_dir / "Lib" / "site-packages"

    @property
    def pip_mirror_args(self) -> list[str]:
        """Return empty list (no internal mirror for this project)."""
        return []


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """Run command with logging."""
    logger.info("Run: %s", " ".join(str(c) for c in cmd))
    kwargs: dict = {"cwd": cwd or BACKEND_ROOT, "check": check}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def _run_pip_stream(cmd: list[str], label: str) -> int:
    """Run pip command with real-time streaming of key output lines.

    Shows per-package progress while hiding noise.
    Returns process return code.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    pkg_count = 0
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        if not line:
            continue

        # Skip progress bars
        if line.startswith("  ") or line.startswith("\r"):
            continue

        # Skip already-installed noise
        if "Requirement already satisfied" in line:
            continue

        # Forward pip warnings to DEBUG
        if line.startswith("WARNING:"):
            logger.debug("[%s] %s", label, line)
            continue

        # Show: Collecting <package>
        if "Collecting " in line:
            pkg_name = line.split("Collecting ", 1)[-1].strip()
            pkg_count += 1
            logger.info("  [%s] Collecting %s", label, pkg_name)
            continue

        # Show: Successfully installed summary
        if line.startswith("Successfully installed"):
            logger.info("  [%s] %s", label, line)
            continue

    process.wait()
    if pkg_count == 0:
        logger.info("  [%s] All packages already up-to-date", label)
    return process.returncode
