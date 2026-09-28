#!/usr/bin/env bash
# start-ltx-video-worker.sh - Launch dedicated LTX-Video GPU worker on Linux / WSL2 / Cloud GPU

HOST=${1:-"0.0.0.0"}
PORT=${2:-8005}
CHECKPOINTS_DIR=${3:-"./models/ltx_video"}

echo "=================================================="
echo "   GenVid.AI - Dedicated LTX-Video GPU Worker     "
echo "=================================================="

export LTX_VIDEO_CHECKPOINTS_DIR="$CHECKPOINTS_DIR"
export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../backend" && pwd):$PYTHONPATH"

# Detect CUDA
python3 -c "import torch; print('CUDA Available:', torch.cuda.is_available())" 2>/dev/null || true

echo "Starting LTX-Video worker service on http://${HOST}:${PORT}..."
python3 backend/app/workers/standalone_ltx_server.py --host "$HOST" --port "$PORT"
