<#
.SYNOPSIS
    Execute full test suites on Windows PowerShell.
#>

param(
    [switch]$BackendOnly = $false,
    [switch]$FrontendOnly = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Running GenVid.AI Test Suites on Windows                 " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Backend pytest suite
if (-not $FrontendOnly) {
    Write-Host "`n[1/2] Running Backend Pytest Test Suite..." -ForegroundColor Yellow
    Push-Location $BackendDir
    try {
        python -m pytest tests -v
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Backend tests passed successfully!" -ForegroundColor Green
        } else {
            Write-Error "Backend tests failed."
        }
    } finally {
        Pop-Location
    }
}

# Frontend type-check / lint
if (-not $BackendOnly -and (Test-Path $FrontendDir)) {
    Write-Host "`n[2/2] Running Frontend TypeScript Check..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    try {
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            npm run type-check
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Frontend type check passed!" -ForegroundColor Green
            }
        }
    } finally {
        Pop-Location
    }
}

Write-Host "`nAll test validations completed!" -ForegroundColor Green
