<#
.SYNOPSIS
    Start the React/Vite Frontend development server on Windows.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting GenVid.AI Frontend (React + Vite)               " -ForegroundColor Cyan
Write-Host " URL: http://localhost:5173                               " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

Push-Location $FrontendDir
try {
    npm run dev
}
finally {
    Pop-Location
}
