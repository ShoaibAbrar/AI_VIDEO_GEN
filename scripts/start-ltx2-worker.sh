#!/usr/bin/env bash
# start-ltx2-worker.sh - Launch dedicated LTX-2 Audio-Video GPU worker on Linux / WSL2 / Cloud GPU

HOST=${1:-"0.0.0.0"}
PORT=${2:-8006}
CHECKPOINTS_DIR=${3:-"./models/ltx2"}

echo "=================================================="
echo "   GenVid.AI - Dedicated LTX-2 Audio-Video Worker "
echo "=================================================="

export LTX2_CHECKPOINTS_DIR="$CHECKPOINTS_DIR"
export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../backend" && pwd):$PYTHONPATH"

# Detect CUDA
python3 -c "import torch; print('CUDA Available:', torch.cuda.is_available())" 2>/dev/null || true

echo "Starting LTX-2 worker service on http://${HOST}:${PORT}..."
python3 backend/app/workers/standalone_ltx2_server.py --host "$HOST" --port "$PORT"
