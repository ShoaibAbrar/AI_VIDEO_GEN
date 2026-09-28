<#
.SYNOPSIS
    Initialize and seed SQLite/PostgreSQL database for the Wan2GP Platform.
.DESCRIPTION
    Creates database schema tables and seeds default admin and demo user accounts.
#>

param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $ProjectRoot "backend"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " GenVid.AI / Wan2GP - Database Initialization & Seeding   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Push-Location $BackendDir
try {
    Write-Host "Executing database schema setup and seed..." -ForegroundColor Yellow
    & $PythonExe -m app.db.init_db
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database initialization completed successfully!" -ForegroundColor Green
    } else {
        Write-Error "Database initialization failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
