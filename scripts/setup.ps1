<#
.SYNOPSIS
    Automated environment setup script for Windows 10/11 PowerShell.
.DESCRIPTION
    Verifies prerequisites (Python, Node.js, npm), sets up .env configuration,
    installs backend and frontend dependencies, initializes database, and reports GPU status.
#>

param(
    [switch]$SkipFrontend = $false,
    [switch]$SkipBackend = $false,
    [switch]$SkipDb = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " GenVid.AI / Wan2GP - Windows Developer Environment Setup" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python
Write-Host "`n[1/6] Checking Python installation..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Error "Python is not found in PATH. Please install Python 3.10+ from https://www.python.org/"
}

# 2. Check Node.js and npm
Write-Host "`n[2/6] Checking Node.js and npm..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    $npmVersion = npm --version 2>&1
    Write-Host "  Found Node.js: $nodeVersion, npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "  Warning: Node.js/npm not found or not in PATH." -ForegroundColor DarkYellow
    Write-Host "  Frontend builds will require Node.js 18+ from https://nodejs.org/" -ForegroundColor DarkYellow
}

# 3. Setup Environment Files (.env)
Write-Host "`n[3/6] Setting up environment configuration files..." -ForegroundColor Yellow
$rootEnv = Join-Path $ProjectRoot ".env"
$rootEnvEx = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path $rootEnv) -and (Test-Path $rootEnvEx)) {
    Copy-Item $rootEnvEx $rootEnv
    Write-Host "  Created root .env from .env.example" -ForegroundColor Green
} else {
    Write-Host "  Root .env already present." -ForegroundColor Gray
}

$backendEnv = Join-Path $BackendDir ".env"
$backendEnvEx = Join-Path $BackendDir ".env.example"
if (-not (Test-Path $backendEnv) -and (Test-Path $backendEnvEx)) {
    Copy-Item $backendEnvEx $backendEnv
    Write-Host "  Created backend/.env from backend/.env.example" -ForegroundColor Green
} else {
    Write-Host "  backend/.env already present." -ForegroundColor Gray
}

# 4. Install Backend Dependencies
if (-not $SkipBackend) {
    Write-Host "`n[4/6] Installing backend dependencies..." -ForegroundColor Yellow
    $reqFile = Join-Path $BackendDir "requirements.txt"
    if (Test-Path $reqFile) {
        python -m pip install --upgrade pip -q
        python -m pip install -r $reqFile -q
        Write-Host "  Backend dependencies installed successfully." -ForegroundColor Green
    }
}

# 5. Install Frontend Dependencies
if (-not $SkipFrontend -and (Test-Path $FrontendDir)) {
    Write-Host "`n[5/6] Installing frontend npm packages..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    try {
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            npm install --silent
            Write-Host "  Frontend npm dependencies installed." -ForegroundColor Green
        }
    } finally {
        Pop-Location
    }
}

# 6. Initialize Database
if (-not $SkipDb) {
    Write-Host "`n[6/6] Initializing and seeding local database..." -ForegroundColor Yellow
    Push-Location $BackendDir
    try {
        python -m app.db.init_db
        Write-Host "  Database initialized with default admin & demo users." -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# 7. Hardware & GPU Diagnostics
Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " Hardware & Engine Diagnostics                           " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
python -c "import torch; cuda=torch.cuda.is_available(); name=torch.cuda.get_device_name(0) if cuda else 'None'; print(f'CUDA Available: {cuda} | Device: {name}')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  PyTorch CUDA not installed or CPU only." -ForegroundColor Gray
}

Write-Host "`n[✓] Setup completed successfully!" -ForegroundColor Green
Write-Host "To start the development servers on Windows:" -ForegroundColor Cyan
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start-dev.ps1" -ForegroundColor White
Write-Host "  Or individually:" -ForegroundColor Gray
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start-backend.ps1" -ForegroundColor Gray
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start-frontend.ps1" -ForegroundColor Gray
