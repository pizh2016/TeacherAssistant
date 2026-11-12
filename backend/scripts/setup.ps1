# Classroom Horn - Development Environment Setup Script
# Uses local Python ZIP + public PyPI (no internal mirror)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$PythonZip = Join-Path (Split-Path -Parent $ProjectRoot) "python-3.10.11-amd64.zip"
$PythonExe = Join-Path $VenvPath "python.exe"
$PipIni = Join-Path $ProjectRoot "pip.ini"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Classroom Horn - Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if .venv already exists (idempotent execution)
# A valid .venv requires BOTH python.exe AND pip. An embedded Python ZIP
# extraction without ensurepip leaves a broken env that must be repaired.
$venvExists = $false
$needPip = $false
if (Test-Path $PythonExe) {
    # Verify pip is actually functional inside the .venv
    $pipCheck = & $PythonExe -m pip --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SKIP] .venv already exists and is valid at: $VenvPath" -ForegroundColor Yellow
        $venvExists = $true
    } else {
        Write-Host "[WARN] .venv exists but pip is missing/broken — will repair" -ForegroundColor Yellow
        $needPip = $true
    }
} else {
    Write-Host "[STEP 1] Setting up Python virtual environment..." -ForegroundColor Green
}

# Step 2: Extract Python from local ZIP if needed
if (-not $venvExists) {
    if (-not (Test-Path $PythonZip)) {
        Write-Host "[ERROR] Python ZIP not found: $PythonZip" -ForegroundColor Red
        Write-Host "Please download python-3.10.11-amd64.zip and place it in project parent directory" -ForegroundColor Red
        exit 1
    }

    Write-Host "[STEP 2] Extracting Python from local ZIP..." -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path $VenvPath | Out-Null
    Expand-Archive -Path $PythonZip -DestinationPath $VenvPath -Force

    # Verify extraction
    if (-not (Test-Path $PythonExe)) {
        Write-Host "[ERROR] Python extraction failed - python.exe not found" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Python extracted successfully" -ForegroundColor Green
}

# Step 3: Bootstrap pip using ensurepip
if (-not $venvExists -or $needPip) {
    Write-Host "[STEP 3] Bootstrapping pip..." -ForegroundColor Green
    & $PythonExe -m ensurepip --default-pip
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to bootstrap pip" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] pip bootstrapped successfully" -ForegroundColor Green
}

# Step 3.5: Generate venv activation scripts (Activate.ps1, activate.bat, etc.)
# The embedded Python ZIP is not a standard venv, so activation scripts are missing.
# NOTE: do NOT write a pyvenv.cfg here. This ".venv" is a full extracted
# interpreter, not a real venv; the mere presence of pyvenv.cfg makes CPython
# 3.10's getpath mis-resolve sys.prefix to the PARENT directory (backend\),
# which silently redirects all imports to backend\Lib\site-packages instead of
# .venv\Lib\site-packages. Activate.ps1 does not need pyvenv.cfg to work.
$activatePs1 = Join-Path $VenvPath "Scripts\Activate.ps1"
if ((-not $venvExists -or $needPip) -and -not (Test-Path $activatePs1)) {
    Write-Host "[STEP 3.5] Generating activation scripts..." -ForegroundColor Green
    $staleCfg = Join-Path $VenvPath "pyvenv.cfg"
    if (Test-Path $staleCfg) {
        Remove-Item $staleCfg -Force
        Write-Host "  Removed stale pyvenv.cfg (breaks prefix resolution on extracted interpreters)" -ForegroundColor Gray
    }
    # Copy Activate.ps1 from venv module template
    $venvTemplateDir = Join-Path $VenvPath "Lib\venv\scripts"
    $commonTemplate = Join-Path $venvTemplateDir "common\Activate.ps1"
    $ntTemplate = Join-Path $venvTemplateDir "nt\activate.bat"
    $scriptsDir = Join-Path $VenvPath "Scripts"

    if (Test-Path $commonTemplate) {
        Copy-Item $commonTemplate (Join-Path $scriptsDir "Activate.ps1") -Force
        Write-Host "  Created: Scripts\Activate.ps1" -ForegroundColor Gray
    }
    if (Test-Path $ntTemplate) {
        Copy-Item $ntTemplate (Join-Path $scriptsDir "activate.bat") -Force
        Write-Host "  Created: Scripts\activate.bat" -ForegroundColor Gray
    }
    # Create deactivate script
    $deactivateBat = Join-Path $venvTemplateDir "nt\deactivate.bat"
    if ((Test-Path $deactivateBat) -and -not (Test-Path (Join-Path $scriptsDir "deactivate.bat"))) {
        Copy-Item $deactivateBat (Join-Path $scriptsDir "deactivate.bat") -Force
    }
    Write-Host "[OK] Activation scripts generated" -ForegroundColor Green
}

# Step 4: Install dependencies from public PyPI
Write-Host "[STEP 4] Installing dependencies from public PyPI..." -ForegroundColor Green

# Set environment variables for pip configuration.
# Explicitly mount the repo pip.ini so it is actually honored (pip does NOT
# auto-read backend/pip.ini). PIP_INDEX_URL/TRUSTED_HOST are belt-and-suspenders.
if (Test-Path $PipIni) {
    $env:PIP_CONFIG_FILE = $PipIni
}
$env:PIP_INDEX_URL = "https://pypi.org/simple/"
$env:PIP_TRUSTED_HOST = "pypi.org"

$requirementsFiles = @(
    "requirements-core.txt",
    "requirements-db.txt",
    "requirements-auth.txt",
    "requirements-tts.txt",
    "requirements-dev.txt",
    "requirements-build.txt"
)

foreach ($reqFile in $requirementsFiles) {
    $reqPath = Join-Path $ProjectRoot $reqFile
    if (Test-Path $reqPath) {
        Write-Host "  Installing from $reqFile..." -ForegroundColor Gray
        & $PythonExe -m pip install -r $reqPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARNING] Failed to install from $reqFile" -ForegroundColor Yellow
        }
    }
}

# Install project itself in editable mode.
# --no-build-isolation uses local setuptools/wheel (offline-friendly, no network
# fetch); --no-deps because deps were just installed from requirements-*.txt.
Write-Host "  Installing project in editable mode..." -ForegroundColor Gray
& $PythonExe -m pip install -e $ProjectRoot --no-build-isolation --no-deps

Write-Host "[OK] Dependencies installed successfully" -ForegroundColor Green

# Step 5: Initialize data directories
Write-Host "[STEP 5] Initializing data directories..." -ForegroundColor Green
$dataDirs = @(
    (Join-Path $ProjectRoot "data"),
    (Join-Path $ProjectRoot "logs"),
    (Join-Path $ProjectRoot "static")
)

foreach ($dir in $dataDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Gray
    }
}

Write-Host "[OK] Data directories initialized" -ForegroundColor Green

# Step 6: Display environment summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Environment Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Python:   $PythonExe" -ForegroundColor White
Write-Host "Version:  $(& $PythonExe --version)" -ForegroundColor White
Write-Host "pip:      $(& $PythonExe -m pip --version)" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. cd backend" -ForegroundColor Gray
Write-Host "  2. .\.venv\Scripts\Activate.ps1       # Activate virtual environment" -ForegroundColor Gray
Write-Host "  3. python -m horn --dev                # Start dev server" -ForegroundColor Gray
Write-Host "  4. Visit http://localhost:18800/docs    # API documentation" -ForegroundColor Gray
Write-Host ""
