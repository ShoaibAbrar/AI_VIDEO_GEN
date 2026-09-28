<#
.SYNOPSIS
    Launch both Backend and Frontend development servers in Windows PowerShell.
#>

param(
    [switch]$SeparateWindows = $true
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendScript = Join-Path $ScriptDir "start-backend.ps1"
$FrontendScript = Join-Path $ScriptDir "start-frontend.ps1"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " GenVid.AI / Wan2GP - Launching Full Development Stack    " -ForegroundColor Cyan
Write-Host " Backend:  http://127.0.0.1:8000 (API: /api/v1)           " -ForegroundColor Green
Write-Host " Frontend: http://localhost:5173                          " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

if ($SeparateWindows) {
    Write-Host "Opening Backend and Frontend in dedicated PowerShell windows..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$BackendScript`""
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$FrontendScript`""
    Write-Host "Servers launched! Press Ctrl+C in their respective windows to stop." -ForegroundColor Green
} else {
    Write-Host "Starting backend in foreground..." -ForegroundColor Yellow
    & $BackendScript
}
