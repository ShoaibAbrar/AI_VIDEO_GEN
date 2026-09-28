param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8007,
    [string]$ModelPath = "./models/minimax_h3"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  GenVid.AI - Dedicated MiniMax H3 GPU Worker Launcher     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$env:MINIMAX_H3_CHECKPOINTS_DIR = $ModelPath
$env:PYTHONPATH = "$PSScriptRoot\..\backend"

Write-Host "Binding Worker to http://${HostAddress}:${Port}" -ForegroundColor Green
Write-Host "Model Checkpoints Path: $ModelPath" -ForegroundColor Green

python "$PSScriptRoot\..\backend\app\workers\standalone_minimax_h3_server.py" --host $HostAddress --port $Port
