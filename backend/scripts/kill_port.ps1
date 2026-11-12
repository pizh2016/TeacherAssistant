# Classroom Horn - Kill process occupying port 18800
# Usage: .\scripts\kill_port.ps1

param(
    [int]$Port = 18800
)

Write-Host "Checking port $Port..." -ForegroundColor Cyan

# Find process using the port
$connections = netstat -ano | Select-String ":${Port}\s" | Where-Object { $_ -match "LISTENING" }

if (-not $connections) {
    Write-Host "Port $Port is free." -ForegroundColor Green
    exit 0
}

Write-Host "Found processes on port ${Port}:" -ForegroundColor Yellow
$connections | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

# Extract PIDs and kill them
$procIds = $connections | ForEach-Object {
    if ($_ -match "\s+(\d+)\s*$") { $Matches[1] }
} | Select-Object -Unique | Where-Object { $_ -ne "0" }

foreach ($procId in $procIds) {
    try {
        $proc = Get-Process -Id $procId -ErrorAction Stop
        Write-Host "Killing process: $($proc.ProcessName) (PID: $procId)" -ForegroundColor Yellow
        Stop-Process -Id $procId -Force
        Write-Host "  Killed successfully." -ForegroundColor Green
    } catch {
        Write-Host "  Failed to kill PID $procId : $_" -ForegroundColor Red
    }
}

# Verify port is free now
Start-Sleep -Seconds 2
$remaining = netstat -ano | Select-String ":${Port}\s" | Where-Object { $_ -match "LISTENING" }
if ($remaining) {
    Write-Host "WARNING: Port $Port is still occupied!" -ForegroundColor Red
    exit 1
} else {
    Write-Host "Port $Port is now free." -ForegroundColor Green
}
