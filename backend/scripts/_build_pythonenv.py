"""Phase 1: Build the runtime Python environment with smart skip.

Downloads Python ZIP, extracts to runtime/pythonenv/, bootstraps pip via
ensurepip, installs all runtime dependencies, then performs comprehensive
cleanup to produce a clean, ready-to-use Python environment.

Smart skip (when environment already valid):
  - Skips download / extract / ensurepip if python.exe + pip exist
  - Incremental requirements install (mtime-based: only re-install when
    requirements file is newer than site-packages)
  - Cleanup always runs (idempotent) to keep environment clean

Phase 1 cleanup (after dependency installation):
  - Delete .dist-info / .egg-info metadata from site-packages (preserving pip)
  - Delete test folders from all packages
  - Delete all __pycache__ directories
  - Remove STDLIB_EXCLUDE_DIRS modules (unnecessary stdlib)
  - Clean .pth files from site-packages
  - Remove STRIP_PACKAGES (tkinter, setuptools, etc.)
  - Clean Scripts/ directory but preserve pip executables
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from _build_shared import (
    BuildContext,
    RUNTIME_EXTRA_PACKAGES,
    RUNTIME_REQUIREMENTS,
    STDLIB_EXCLUDE_DIRS,
    STDLIB_EXCLUDE_ROOT_PATTERNS,
    STRIP_PACKAGES,
    PYTHON_ORG_URL,
    _run_pip_stream,
)

logger = logging.getLogger(__name__)


def _is_pythonenv_valid(ctx: BuildContext) -> bool:
    """Check if existing pythonenv is valid and can be reused."""
    pythonenv = ctx.pythonenv_dir
    if not pythonenv.exists():
        return False

    python_exe = ctx.pythonenv_python
    if not python_exe.exists():
        logger.info("Skip check: python.exe not found")
        return False

    # Check pip availability via site-packages/pip directory
    sp = ctx.pythonenv_site_packages
    pip_dir = sp / "pip" if sp.exists() else None
    if not pip_dir or not pip_dir.exists():
        logger.info("Skip check: pip not found in site-packages")
        return False

    logger.info("Existing pythonenv is valid (python.exe + pip OK)")
    return True


def run_phase1_cleanup(ctx: BuildContext) -> None:
    """Run all Phase 1 post-install cleanup steps (idempotent)."""
    pythonenv = ctx.pythonenv_dir
    _remove_bloat_packages(ctx)
    _trim_stdlib(ctx)
    _trim_metadata(ctx)
    _remove_test_dirs(ctx)
    _cleanup_pycache(pythonenv)
    _clean_pth_files(ctx)
    _clean_scripts_dir(ctx)
    _verify_python_works(ctx)


def build_pythonenv(ctx: BuildContext, *, force: bool = False) -> None:
    """Phase 1: Build clean runtime/pythonenv/ (with smart skip).

    When *force* is False (default) and the environment already exists with
    python.exe and pip intact, the heavy download / extract / ensurepip steps
    are skipped. Cleanup and incremental dependency installation still run.

    Steps (full build):
      1. Download / locate Python ZIP
      2. Extract to runtime/pythonenv/
      3. Bootstrap pip via ensurepip
      4. Clean up ensurepip after bootstrap
      5. Install runtime dependencies (incremental by mtime)
      6. Post-install cleanup (metadata, tests, stdlib trim, bloat removal)
    """
    logger.info("=" * 60)
    logger.info("Phase 1: Build clean runtime/pythonenv/")
    logger.info("=" * 60)

    pythonenv = ctx.pythonenv_dir

    # Ensure cache dir exists
    ctx.cache_dir.mkdir(parents=True, exist_ok=True)

    # Smart skip: check if environment is already valid
    env_valid = _is_pythonenv_valid(ctx)
    if env_valid and not force:
        logger.info("pythonenv already valid, skipping download/extract/ensurepip")

        # Incremental dependency installation
        _install_runtime_deps(ctx)

        # Always run cleanup (idempotent)
        run_phase1_cleanup(ctx)

        logger.info("Phase 1 complete (skipped heavy steps, cleanup done)")
        return

    if force and pythonenv.exists():
        logger.info("--force specified, rebuilding pythonenv from scratch")

    # --- Full build from scratch ---

    # Clean existing pythonenv
    if pythonenv.exists():
        shutil.rmtree(pythonenv)
    pythonenv.mkdir(parents=True, exist_ok=True)

    # Step 1: Get Python ZIP
    python_zip = _ensure_python_zip(ctx)

    # Step 2: Extract to pythonenv
    _extract_python_zip(python_zip, pythonenv)

    # Step 3: Bootstrap pip
    _bootstrap_pip(ctx)

    # Step 4: Clean up ensurepip
    _cleanup_ensurepip(ctx)

    # Step 5: Install runtime deps
    _install_runtime_deps(ctx, force)

    # Step 6: Post-install cleanup (always runs)
    run_phase1_cleanup(ctx)

    logger.info("Phase 1 complete: clean pythonenv ready")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_python_zip(ctx: BuildContext) -> Path:
    """Locate or download the Python embeddable ZIP.

    Priority:
      1. Local cache (generated/cache/)
      2. Project root (python-3.10.11-amd64.zip)
      3. Public python.org via urllib
    """
    zip_filename = f"python-{ctx.python_version}-amd64.zip"
    local_zip = ctx.cache_dir / zip_filename

    if local_zip.exists():
        logger.info("Using cached Python ZIP: %s", local_zip)
        return local_zip

    # Try project root (where the user typically places the ZIP)
    project_root_zip = ctx.project_root / zip_filename
    if project_root_zip.exists():
        logger.info("Using Python ZIP from project root: %s", project_root_zip)
        # Copy to cache for future use
        shutil.copy2(project_root_zip, local_zip)
        return local_zip

    # Fallback: public python.org
    logger.info("Downloading from python.org: %s", PYTHON_ORG_URL)
    try:
        import urllib.request
        urllib.request.urlretrieve(PYTHON_ORG_URL, str(local_zip))
        if local_zip.exists() and local_zip.stat().st_size > 0:
            logger.info("Downloaded from python.org")
            return local_zip
    except Exception as e:
        raise RuntimeError(
            f"Failed to download Python ZIP. Place {zip_filename} in "
            f"{ctx.cache_dir} or {ctx.project_root}"
        ) from e

    raise RuntimeError(f"Python ZIP not available: {zip_filename}")


def _extract_python_zip(zip_path: Path, dest: Path) -> None:
    """Extract Python ZIP into runtime/pythonenv/."""
    import zipfile
    logger.info("Extracting %s -> %s", zip_path.name, dest)
    t0 = time.monotonic()
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        zf.extractall(str(dest))
    elapsed = time.monotonic() - t0

    # Verify python.exe exists
    python_exe = dest / "python.exe"
    if not python_exe.exists():
        raise RuntimeError(f"python.exe not found after extraction: {python_exe}")

    # Remove ._pth file if present (embeddable package restricts imports)
    for pth in dest.glob("python*._pth"):
        pth.unlink()
        logger.info("Removed %s (enables standard import paths)", pth.name)

    logger.info("Python extracted (%.1fs)", elapsed)


def _cleanup_ensurepip(ctx: BuildContext) -> None:
    """Remove ensurepip bundled wheels and module after pip bootstrap."""
    pythonenv = ctx.pythonenv_dir
    removed = 0

    # Remove ensurepip module from Lib/
    ensurepip_dir = pythonenv / "Lib" / "ensurepip"
    if ensurepip_dir.exists():
        shutil.rmtree(ensurepip_dir)
        removed += 1

    if removed:
        logger.info("Cleaned up ensurepip (%d items)", removed)


def _bootstrap_pip(ctx: BuildContext) -> None:
    """Bootstrap pip inside pythonenv using ensurepip."""
    python_exe = ctx.pythonenv_python
    logger.info("Bootstrapping pip via ensurepip in pythonenv...")

    result = subprocess.run(
        [str(python_exe), "-I", "-m", "ensurepip", "--upgrade"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ensurepip failed: {result.stderr.strip()}")

    logger.info("pip bootstrapped in pythonenv")


def _get_mtime(path: Path) -> float:
    """Return file modification time, or 0.0 if file doesn't exist."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _install_runtime_deps(ctx: BuildContext, force: bool = False) -> None:
    """Install runtime dependencies with incremental (mtime-based) skip."""
    python_exe = ctx.pythonenv_python
    sp = ctx.pythonenv_site_packages
    sp_mtime = _get_mtime(sp)

    for req_file in RUNTIME_REQUIREMENTS:
        req_path = ctx.backend_root / req_file
        if not req_path.exists():
            logger.info("Skipping %s (not found)", req_file)
            continue

        req_mtime = _get_mtime(req_path)

        if not force:
            # Incremental skip: requirements file older than site-packages
            if sp_mtime > 0 and req_mtime <= sp_mtime:
                logger.info(
                    "Skipping %s (unchanged, site-packages newer)", req_file
                )
                continue

        label = req_file
        logger.info("Installing %s ...", req_file)
        cmd = [
            str(python_exe), "-I", "-m", "pip", "install",
            "--no-cache-dir", "--progress-bar=off",
        ] + ctx.pip_mirror_args + ["-r", str(req_path)]
        rc = _run_pip_stream(cmd, label)
        if rc != 0:
            logger.warning("%s install failed (exit code %d)", req_file, rc)
        else:
            logger.info("%s installed", req_file)

    # Install extra runtime packages
    if RUNTIME_EXTRA_PACKAGES:
        label = "extra-packages"
        logger.info("Installing extra packages: %s", list(RUNTIME_EXTRA_PACKAGES))
        cmd = [
            str(python_exe), "-I", "-m", "pip", "install",
            "--no-cache-dir", "--progress-bar=off",
        ] + ctx.pip_mirror_args + list(RUNTIME_EXTRA_PACKAGES)
        rc = _run_pip_stream(cmd, label)
        if rc != 0:
            logger.warning("Extra packages install failed (exit code %d)", rc)


# ---------------------------------------------------------------------------
# Phase 1 post-install cleanup functions
# ---------------------------------------------------------------------------


def _remove_bloat_packages(ctx: BuildContext) -> None:
    """Remove tkinter, setuptools, and other bloat packages from pythonenv/."""
    sp = ctx.pythonenv_site_packages
    if not sp.exists():
        return

    removed = 0
    for pkg_name in STRIP_PACKAGES:
        # Remove from site-packages/
        pkg_dir = sp / pkg_name
        if pkg_dir.exists():
            if pkg_dir.is_dir():
                shutil.rmtree(pkg_dir)
            else:
                pkg_dir.unlink()
            removed += 1
        # Remove from Lib/ root (stdlib-level packages)
        lib_dir = ctx.pythonenv_dir / "Lib"
        lib_pkg = lib_dir / pkg_name
        if lib_pkg.exists():
            if lib_pkg.is_dir():
                shutil.rmtree(lib_pkg)
            else:
                lib_pkg.unlink()
            removed += 1

    # Remove tkinter-related DLLs
    for dll_name in ("tcl*.dll", "tk*.dll", "zlib1.dll", "_tkinter*.pyd"):
        for dll in ctx.pythonenv_dir.glob(dll_name):
            dll.unlink()
            removed += 1
        dlls = ctx.pythonenv_dir / "DLLs"
        if dlls.exists():
            for dll in dlls.glob(dll_name):
                dll.unlink()
                removed += 1

    logger.info("Removed %d bloat packages/files", removed)


def _trim_stdlib(ctx: BuildContext) -> None:
    """Remove unnecessary stdlib modules from pythonenv/ to minimize size."""
    pythonenv = ctx.pythonenv_dir
    lib_dir = pythonenv / "Lib"

    removed_count = 0
    removed_size = 0

    if lib_dir.exists():
        for mod_name in STDLIB_EXCLUDE_DIRS:
            mod_dir = lib_dir / mod_name
            if mod_dir.exists() and mod_dir.is_dir():
                size = _dir_size(mod_dir)
                shutil.rmtree(mod_dir)
                removed_count += 1
                removed_size += size

            mod_py = lib_dir / f"{mod_name}.py"
            if mod_py.exists():
                size = mod_py.stat().st_size
                mod_py.unlink()
                removed_count += 1
                removed_size += size

    # Remove tkinter-related DLLs from pythonenv root
    for pattern in STDLIB_EXCLUDE_ROOT_PATTERNS:
        for f in pythonenv.glob(pattern):
            if f.is_file():
                removed_size += f.stat().st_size
                f.unlink()
                removed_count += 1
            elif f.is_dir():
                size = _dir_size(f)
                shutil.rmtree(f)
                removed_count += 1
                removed_size += size

    # Remove DLLs/ directory tkinter-related files
    dlls_dir = pythonenv / "DLLs"
    if dlls_dir.exists():
        for tk_dll in list(dlls_dir.glob("tcl*.dll")) + list(dlls_dir.glob("tk*.dll")):
            removed_size += tk_dll.stat().st_size
            tk_dll.unlink()
            removed_count += 1

    # Remove docs/ and Tools/ if present
    for extra_dir in ("docs", "Tools", "tools"):
        d = pythonenv / extra_dir
        if d.exists():
            size = _dir_size(d)
            shutil.rmtree(d)
            removed_count += 1
            removed_size += size

    logger.info(
        "Stdlib trimmed: removed %d items (%.1f MB saved)",
        removed_count,
        removed_size / (1024 * 1024),
    )


def _trim_metadata(ctx: BuildContext) -> None:
    """Trim .dist-info and .egg-info metadata to reduce size.

    Preserves pip/setuptools/wheel dist-info so ``python -m pip`` keeps
    working in the deployed pythonenv.
    """
    sp = ctx.pythonenv_site_packages
    if not sp.exists():
        return

    # Packages whose metadata must be kept for pip to function
    _KEEP_METADATA = {"pip", "setuptools", "wheel", "pkg_resources"}

    def _is_keepable(dist_info_name: str) -> bool:
        # dist-info dirs look like: pip-23.0.1.dist-info
        pkg_name = dist_info_name.split("-")[0].lower().replace("_", "-")
        return pkg_name in _KEEP_METADATA

    removed = 0
    for dist_info in sp.glob("*.dist-info"):
        if _is_keepable(dist_info.name):
            continue
        shutil.rmtree(dist_info)
        removed += 1

    # Also clean egg-info (none of these are pip-critical)
    for egg_info in sp.glob("*.egg-info"):
        if _is_keepable(egg_info.name):
            continue
        shutil.rmtree(egg_info)
        removed += 1

    logger.info("Trimmed %d metadata entries (preserved pip/setuptools)", removed)


def _remove_test_dirs(ctx: BuildContext) -> None:
    """Remove test folders from all packages in site-packages."""
    sp = ctx.pythonenv_site_packages
    if not sp.exists():
        return

    test_names = {"test", "tests", "testing", "_tests", "_testing"}
    removed = 0
    for d in sp.rglob("*"):
        if d.is_dir() and d.name in test_names:
            shutil.rmtree(d)
            removed += 1

    logger.info("Removed %d test directories", removed)


def _cleanup_pycache(pythonenv: Path) -> None:
    """Remove all __pycache__ directories from pythonenv/."""
    removed = 0
    for pycache in pythonenv.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)
            removed += 1
    logger.info("Removed %d __pycache__ directories", removed)


def _clean_scripts_dir(ctx: BuildContext) -> None:
    """Clean Scripts/ but preserve pip executables for post-deploy use.

    Remove console-script wrappers (which have hardcoded paths) while
    keeping pip.exe / pip3.exe / pip3.x.exe so the deployed pythonenv
    can still install packages if needed.
    """
    scripts_dir = ctx.pythonenv_dir / "Scripts"
    if not scripts_dir.exists():
        return

    # Patterns to keep (pip family)
    _KEEP_PATTERNS = {"pip.exe", "pip3.exe", "pip3.10.exe"}

    removed = 0
    kept = 0
    for item in list(scripts_dir.iterdir()):
        if item.name.lower() in _KEEP_PATTERNS:
            kept += 1
            continue
        if item.is_file():
            item.unlink()
            removed += 1
        elif item.is_dir():
            shutil.rmtree(item)
            removed += 1

    logger.info(
        "Cleaned Scripts/: removed %d items, kept %d pip executables",
        removed, kept,
    )


def _clean_pth_files(ctx: BuildContext) -> None:
    """Remove orphaned .pth files from site-packages."""
    sp = ctx.pythonenv_site_packages
    if not sp.exists():
        return
    removed = 0
    for pth in sp.glob("*.pth"):
        pth.unlink()
        removed += 1
    logger.info("Removed %d .pth files", removed)


def _verify_python_works(ctx: BuildContext) -> None:
    """Verify pythonenv/python.exe still runs after cleanup."""
    python_exe = ctx.pythonenv_python
    result = subprocess.run(
        [str(python_exe), "-I", "-c", "import sys; print(sys.version)"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"python.exe broken after phase 1 cleanup: {result.stderr.strip()}"
        )
    logger.info("Post-cleanup verification OK: %s", result.stdout.strip())


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory tree in bytes."""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total
