# start-ltx2-worker.ps1 - Launch dedicated LTX-2 Audio-Video GPU worker on Windows

[CmdletBinding()]
param (
    [string]$Host = "0.0.0.0",
    [int]$Port = 8006,
    [string]$CheckpointsDir = "./models/ltx2"
)

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   GenVid.AI - Dedicated LTX-2 Audio-Video Worker " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$env:LTX2_CHECKPOINTS_DIR = $CheckpointsDir
$env:PYTHONPATH = "$PSScriptRoot/../backend"

# Detect CUDA
try {
    $cudaCheck = python -c "import torch; print(torch.cuda.is_available())" 2>$null
    if ($cudaCheck -eq "True") {
        $gpuName = python -c "import torch; print(torch.cuda.get_device_name(0))"
        Write-Host "[OK] Detected NVIDIA CUDA GPU: $gpuName" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] No NVIDIA CUDA device detected on this host." -ForegroundColor Yellow
        Write-Host "Real LTX-2 inference requires an NVIDIA GPU with at least 16 GB VRAM (24 GB recommended)." -ForegroundColor Yellow
    }
} catch {
    Write-Host "[INFO] Checking Python environment..." -ForegroundColor Gray
}

Write-Host "`nStarting LTX-2 worker service on http://$Host`:$Port..." -ForegroundColor Cyan
python backend/app/workers/standalone_ltx2_server.py --host $Host --port $Port
