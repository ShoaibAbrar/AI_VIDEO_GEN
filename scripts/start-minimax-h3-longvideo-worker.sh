#!/usr/bin/env bash
# start-minimax-h3-longvideo-worker.sh
# Launches the MiniMax H3 LongVideos standalone GPU worker on port 8009.
#
# Requirements:
#   - NVIDIA CUDA GPU with >= 24 GB VRAM
#   - MiniMax H3 model weights in $MINIMAX_H3_CHECKPOINTS_DIR (or ./models/minimax_h3)
#   - Python environment with: torch diffusers transformers pillow soundfile uvicorn fastapi
#
# Usage:
#   bash scripts/start-minimax-h3-longvideo-worker.sh
#   MINIMAX_H3_CHECKPOINTS_DIR=/data/models/minimax_h3 bash scripts/start-minimax-h3-longvideo-worker.sh

set -e

HOST="${H3_LONGVIDEO_HOST:-0.0.0.0}"
PORT="${H3_LONGVIDEO_PORT:-8009}"
CHECKPOINTS_DIR="${MINIMAX_H3_CHECKPOINTS_DIR:-./models/minimax_h3}"
OUTPUT_DIR="${MINIMAX_H3_LONGVIDEO_OUTPUT_DIR:-./output/minimax_h3_longvideos}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"

cd "${BACKEND_DIR}"

export MINIMAX_H3_CHECKPOINTS_DIR="${CHECKPOINTS_DIR}"
export MINIMAX_H3_LONGVIDEO_OUTPUT_DIR="${OUTPUT_DIR}"

echo ""
echo "=========================================="
echo " MiniMax H3 LongVideos GPU Worker"
echo " Port     : ${PORT}"
echo " Host     : ${HOST}"
echo " Endpoint : http://${HOST}:${PORT}/health"
echo "=========================================="
echo ""

python app/workers/standalone_minimax_h3_longvideo_server.py \
    --host "${HOST}" \
    --port "${PORT}"
