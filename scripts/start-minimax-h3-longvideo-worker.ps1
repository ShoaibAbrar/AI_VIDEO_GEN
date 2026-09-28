# Start-MiniMax-H3-LongVideo-Worker.ps1
# Launches the MiniMax H3 LongVideos standalone GPU worker on port 8009.
#
# Requirements:
#   - NVIDIA CUDA GPU with >= 24 GB VRAM
#   - MiniMax H3 model weights in $MINIMAX_H3_CHECKPOINTS_DIR (or ./models/minimax_h3)
#   - Python environment with: torch diffusers transformers pillow soundfile uvicorn fastapi
#
# Usage:
#   .\scripts\start-minimax-h3-longvideo-worker.ps1
#   .\scripts\start-minimax-h3-longvideo-worker.ps1 -Port 8009 -CheckpointsDir "D:\models\minimax_h3"

param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 8009,
    [string]$CheckpointsDir = "",
    [string]$OutputDir = "",
    [switch]$Reload
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir "..\backend"

Set-Location $BackendDir

if ($CheckpointsDir -ne "") {
    $env:MINIMAX_H3_CHECKPOINTS_DIR = $CheckpointsDir
    Write-Host "[H3LongVideo] Using checkpoints: $CheckpointsDir"
}

if ($OutputDir -ne "") {
    $env:MINIMAX_H3_LONGVIDEO_OUTPUT_DIR = $OutputDir
    Write-Host "[H3LongVideo] Using output dir: $OutputDir"
}

Write-Host ""
Write-Host "=========================================="
Write-Host " MiniMax H3 LongVideos GPU Worker"
Write-Host " Port     : $Port"
Write-Host " Host     : $Host"
Write-Host " Endpoint : http://${Host}:${Port}/health"
Write-Host "=========================================="
Write-Host ""

$Args = @(
    "app/workers/standalone_minimax_h3_longvideo_server.py",
    "--host", $Host,
    "--port", $Port
)

if ($Reload) {
    $Args += "--reload"
}

python @Args
