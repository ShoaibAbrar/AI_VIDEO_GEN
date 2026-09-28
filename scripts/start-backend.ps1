<#
.SYNOPSIS
    Start the FastAPI Backend server on Windows.
#>

param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload = $true
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $ProjectRoot "backend"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting GenVid.AI Backend (FastAPI + Uvicorn)           " -ForegroundColor Cyan
Write-Host " Endpoint: http://${Host}:${Port}/api/v1                 " -ForegroundColor Green
Write-Host " Docs:     http://${Host}:${Port}/docs                   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

Push-Location $BackendDir
try {
    $reloadFlag = if ($Reload) { "--reload" } else { "" }
    python -m uvicorn app.main:app --host $Host --port $Port $reloadFlag
}
finally {
    Pop-Location
}
