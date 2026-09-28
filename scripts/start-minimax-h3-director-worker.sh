#!/usr/bin/env bash
set -e

HOST=${1:-"0.0.0.0"}
PORT=${2:-8008}
MODEL_PATH=${3:-"./models/minimax_h3"}

echo "=========================================================="
echo "  GenVid.AI - MiniMax H3 Director GPU Worker Launcher     "
echo "=========================================================="

export MINIMAX_H3_CHECKPOINTS_DIR="$MODEL_PATH"
export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../backend" && pwd):$PYTHONPATH"

echo "Binding Worker to http://${HOST}:${PORT}"
echo "Model Checkpoints Path: ${MODEL_PATH}"

python "$(cd "$(dirname "${BASH_SOURCE[0]}")/../backend/app/workers" && pwd)/standalone_minimax_h3_director_server.py" --host "$HOST" --port "$PORT"
