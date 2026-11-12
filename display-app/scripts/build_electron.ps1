# ==============================================================================
# Classroom Horn - Build Electron Installer (Display App)
# ==============================================================================
#
# 大屏端为纯客户端应用，后端独立部署在远程服务器。
# 构建流程：
#   1. Build the display-app frontend (npm run build)
#   2. Copy icons to dist/
#   3. Package with electron-builder (NSIS installer + portable)
#
# Usage:
#   .\scripts\build_electron.ps1
#   .\scripts\build_electron.ps1 -Clean
#   .\scripts\build_electron.ps1 -Clean -AllowNpmInstall
#
# Prerequisites:
#   - Node.js 18+ (npm install must have been run)
# ==============================================================================

param(
    # Remove dist/, release/, node_modules/.cache before building
    [switch]$Clean,

    # Allow npm install to run (requires network)
    [switch]$AllowNpmInstall
)

$ErrorActionPreference = "Stop"

$DisplayAppRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $DisplayAppRoot

# ==============================================================================
# Helper: Safe directory removal (handles Windows read-only & locked files)
# ==============================================================================
function Remove-DirSafe {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $true }

    # Clear read-only attributes first
    Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        try { $_.Attributes = 'Normal' } catch {}
    }

    try {
        Remove-Item -Recurse -Force $Path -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

# ==============================================================================
# Pre-build cleanup: remove stale win-unpacked to avoid EBUSY on app.asar
# ==============================================================================
$releaseDir = Join-Path $ProjectRoot "release"
$winUnpacked = Join-Path $releaseDir "win-unpacked"
if (Test-Path $winUnpacked) {
    Write-Host "[Pre-clean] Removing stale win-unpacked..." -ForegroundColor Yellow
    if (-not (Remove-DirSafe $winUnpacked)) {
        # Files locked by system process - rename old release dir with timestamp
        $ts = Get-Date -Format "yyyyMMdd_HHmmss"
        $oldName = "release_stale_$ts"
        $oldPath = Join-Path $ProjectRoot $oldName
        try {
            Rename-Item $releaseDir $oldPath -Force -ErrorAction Stop
            Write-Host "[Pre-clean] Old release renamed -> $oldName" -ForegroundColor Gray
        } catch {
            Write-Host "[WARN] Could not clear stale release dir. Close any file explorer or antivirus scan, then retry." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[Pre-clean] Done" -ForegroundColor Gray
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Classroom Horn Electron Build" -ForegroundColor Cyan
Write-Host "  (Display App - Pure Client)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# Clean if requested
# ==============================================================================
if ($Clean) {
    Write-Host "[Clean] Removing build artifacts..." -ForegroundColor Yellow
    $dirsToClean = @(
        (Join-Path $DisplayAppRoot "dist"),
        (Join-Path $ProjectRoot "release"),
        (Join-Path $DisplayAppRoot "node_modules\.cache")
    )
    foreach ($dir in $dirsToClean) {
        if (Remove-DirSafe $dir) {
            if (Test-Path $dir) {} else { Write-Host "  Removed: $dir" -ForegroundColor Gray }
        } else {
            Write-Host "  [SKIP] Locked: $dir" -ForegroundColor Yellow
        }
    }
}

# ==============================================================================
# Check node_modules
# ==============================================================================
$nodeModules = Join-Path $DisplayAppRoot "node_modules"
if (-not (Test-Path $nodeModules)) {
    if ($AllowNpmInstall) {
        Write-Host "[npm] Installing dependencies..." -ForegroundColor Yellow
        Push-Location $DisplayAppRoot
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: npm install failed" -ForegroundColor Red
            exit $LASTEXITCODE
        }
        Pop-Location
        Write-Host "[npm] Dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "ERROR: node_modules/ not found. Run 'npm install' first or use -AllowNpmInstall" -ForegroundColor Red
        exit 1
    }
}

# ==============================================================================
# Build frontend
# ==============================================================================
Write-Host "[1/2] Building frontend..." -ForegroundColor Cyan
Push-Location $DisplayAppRoot
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend build failed" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}
Pop-Location
Write-Host "[OK] Frontend built -> dist/" -ForegroundColor Green

# ==============================================================================
# Copy icons to dist/ (for runtime icon loading in production)
# ==============================================================================
$iconsSrc = Join-Path $DisplayAppRoot "assets\icons"
$iconsDst = Join-Path $DisplayAppRoot "dist\icons"
if (Test-Path $iconsSrc) {
    if (-not (Test-Path $iconsDst)) {
        New-Item -ItemType Directory -Path $iconsDst -Force | Out-Null
    }
    Copy-Item (Join-Path $iconsSrc "*") $iconsDst -Force
    Write-Host "[OK] Icons copied -> dist/icons/" -ForegroundColor Green
} else {
    Write-Host "[WARN] Icons source not found: $iconsSrc" -ForegroundColor Yellow
}

# ==============================================================================
# Package with electron-builder
# ==============================================================================
Write-Host "[2/2] Packaging with electron-builder..." -ForegroundColor Cyan
Push-Location $DisplayAppRoot

# Read version from package.json
$pkgJson = Get-Content (Join-Path $DisplayAppRoot "package.json") | ConvertFrom-Json
$version = $pkgJson.version

# Set environment variables for electron-builder (offline mode)
$env:ELECTRON_ARTIFACT_NAME = "Classroom-Horn-v$version-win-x64"

# Force electron-builder to use local cache (no network downloads)
$localCacheDir = Join-Path $env:LOCALAPPDATA "electron-builder\Cache"
$env:ELECTRON_BUILDER_CACHE = $localCacheDir
Write-Host "[Config] Cache: $localCacheDir" -ForegroundColor Gray
Write-Host "[Config] Electron: $(Join-Path $DisplayAppRoot 'node_modules\electron\dist')" -ForegroundColor Gray

npx electron-builder --config scripts/electron-builder.yml --win
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: electron-builder failed" -ForegroundColor Red
    Pop-Location
    exit $LASTEXITCODE
}
Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Version:   $version" -ForegroundColor Yellow
Write-Host "Output:    release\ (project root)" -ForegroundColor Yellow
Write-Host ""
