# Start-Voice-Cloning-Worker.ps1
# Launches the standalone Voice Cloning GPU Worker on port 8010.
#
# Requirements:
#   - Python 3.10+ with torch torchaudio transformers soundfile fastapi uvicorn
#   - NVIDIA CUDA GPU (optional; falls back to CPU mode if CUDA unavailable)
#
# Usage:
#   .\scripts\start-voice-cloning-worker.ps1
#   .\scripts\start-voice-cloning-worker.ps1 -Port 8010

param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 8010,
    [string]$ModelPath = "",
    [switch]$Reload
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir "..\backend"

Set-Location $BackendDir

if ($ModelPath -ne "") {
    $env:VOICE_CLONING_MODEL_PATH = $ModelPath
    Write-Host "[VoiceCloning] Model path: $ModelPath"
}

Write-Host ""
Write-Host "=========================================="
Write-Host " Chatterbox Voice Cloning Server"
Write-Host " Port     : $Port"
Write-Host " Host     : $Host"
Write-Host " Endpoint : http://${Host}:${Port}/health"
Write-Host " Docs     : http://${Host}:${Port}/docs"
Write-Host "=========================================="
Write-Host ""

$Args = @(
    "app/workers/standalone_voice_cloning_server.py",
    "--host", $Host,
    "--port", $Port
)

if ($Reload) {
    $Args += "--reload"
}

python @Args
