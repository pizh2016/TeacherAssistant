"""Classroom Horn - product build script (pythonenv + .pyc compilation).

Packages the backend as a standalone runtime with embedded Python environment,
replacing the previous PyInstaller --onefile approach.

Architecture (from-scratch pythonenv):
    runtime/pythonenv/    - Standalone Python env built from Python ZIP + runtime deps
    defaults/             - Factory config seeds (settings.json)
    teacher-app/          - H5 teacher interface (from teacher-app/dist/)

Build workflow:
  Default: Build clean runtime/pythonenv/ (smart skip if already valid)
           + always reinstall & recompile project source (src/horn/ -> pythonenv)
  Optional: --phase2 to additionally compile .py -> .pyc and slim
  --force: Disable smart skip, force full rebuild from scratch

Note: project source recompilation is ALWAYS performed (never skipped),
so changes in src/horn/ are guaranteed to land in the runtime package.

Usage:
    python scripts/build_runtime.py                    # Build pythonenv (smart skip)
    python scripts/build_runtime.py --force            # Force full rebuild
    python scripts/build_runtime.py --phase2           # + compile .py -> .pyc
    python scripts/build_runtime.py --package          # Build + package as ZIP
    python scripts/build_runtime.py --clean            # Clean old artifacts first
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure sibling _build_*.py modules are importable when invoked as:
#   python scripts/build_runtime.py
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from _build_shared import BuildContext, read_version
from _build_pythonenv import build_pythonenv
from _build_compile import compile_horn_source, compile_and_strip
from _build_package import package_release, clean_build_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _verify_venv(ctx: BuildContext) -> None:
    """Verify that .venv exists with correct Python version."""
    if not ctx.venv_dir.exists():
        raise RuntimeError(
            f".venv not found at {ctx.venv_dir}. "
            "Please run scripts/setup.ps1 first to initialize the dev environment."
        )

    python = ctx.venv_python
    import subprocess
    result = subprocess.run(
        [str(python), "-I", "-c", "import platform; print(platform.python_version())"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Python interpreter in .venv failed to start")

    actual_version = (result.stdout or "").strip()
    if actual_version != ctx.python_version:
        raise RuntimeError(
            f"Python version mismatch in .venv: expected {ctx.python_version}, "
            f"got {actual_version}"
        )

    logger.info(".venv verified: Python %s", ctx.python_version)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classroom Horn product build script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Build modes:
  (default)                 : Build pythonenv/ (smart skip if already valid)
  --phase2                  : Additionally compile .py -> .pyc and slim

Other options:
  --force                   : Disable smart skip, force full rebuild
  --package                 : Auto-package as ZIP installer after build
  --clean                   : Clean old artifacts before build

Examples:
  python scripts/build_runtime.py
  python scripts/build_runtime.py --force
  python scripts/build_runtime.py --package
  python scripts/build_runtime.py --phase2 --package
        """,
    )
    parser.add_argument("--phase2", action="store_true",
                        help="Additionally compile .py -> .pyc and slim (optional)")
    parser.add_argument("--force", action="store_true",
                        help="Disable smart skip, force full rebuild from scratch")
    parser.add_argument("--package", action="store_true",
                        help="Auto-package as ZIP after build")
    parser.add_argument("--version", default=None,
                        help="Backend release version (default: read from VERSION_BACKEND)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean old artifacts before build")
    args = parser.parse_args()

    # Build context: shared state for all steps
    ctx = BuildContext()

    # Resolve backend version
    if args.version:
        backend_version = args.version
        logger.info("Using backend version from command-line: %s", backend_version)
    else:
        try:
            backend_version = read_version()
            logger.info("Using backend version from VERSION_BACKEND: %s", backend_version)
        except (FileNotFoundError, ValueError) as e:
            logger.error("Backend version error: %s", e)
            sys.exit(1)

    logger.info("=" * 60)
    logger.info("Classroom Horn Product Build")
    logger.info("Mode: from-scratch pythonenv")
    logger.info("Architecture: runtime/pythonenv/ + defaults/ + teacher-app/")
    logger.info("=" * 60)

    if args.clean:
        clean_build_dirs(ctx)

    # Common prerequisites
    _verify_venv(ctx)

    # Phase 1: Build clean runtime environment (smart skip if valid)
    logger.info("=" * 60)
    logger.info("Phase 1: Build clean runtime/pythonenv/")
    if args.force:
        logger.info("(--force: full rebuild, smart skip disabled)")
    logger.info("=" * 60)
    build_pythonenv(ctx, force=args.force)

    # Always reinstall + recompile project source (src/horn/ -> pythonenv).
    # Never skipped: ensures source changes are reflected even when the
    # environment-level smart skip reuses an existing pythonenv.
    compile_horn_source(ctx)

    # Phase 2: Compile and slim (optional)
    if args.phase2:
        logger.info("=" * 60)
        logger.info("Phase 2: Compile .py -> .pyc and slim")
        if args.force:
            logger.info("(--force: full compile, smart skip disabled)")
        logger.info("=" * 60)

        compile_ok = compile_and_strip(ctx, force=args.force)
        if not compile_ok:
            logger.error("Phase 2 failed. Fix errors and re-run with --phase2.")
            return

    # Package release (optional)
    if args.package:
        package_release(ctx, backend_version)

    logger.info("=" * 60)
    logger.info("Build complete!")
    logger.info("  Python env : %s", ctx.pythonenv_dir)
    if args.package:
        _plat = "win-x64" if sys.platform == "win32" else "linux-x64"
        logger.info("  Installer  : %s",
                     ctx.project_root / "release" / f"Classroom-Horn-v{backend_version}-{_plat}.zip")
        logger.info("  Backend    : v%s", backend_version)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
