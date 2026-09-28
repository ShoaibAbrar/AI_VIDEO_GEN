param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8008,
    [string]$ModelPath = "./models/minimax_h3"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  GenVid.AI - MiniMax H3 Director GPU Worker Launcher     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$env:MINIMAX_H3_CHECKPOINTS_DIR = $ModelPath
$env:PYTHONPATH = "$PSScriptRoot\..\backend"

Write-Host "Binding Worker to http://${HostAddress}:${Port}" -ForegroundColor Green
Write-Host "Model Checkpoints Path: $ModelPath" -ForegroundColor Green

python "$PSScriptRoot\..\backend\app\workers\standalone_minimax_h3_director_server.py" --host $HostAddress --port $Port
