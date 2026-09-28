#!/usr/bin/env bash
# start-voice-cloning-worker.sh
# Launches the standalone Voice Cloning GPU Worker on port 8010.
#
# Requirements:
#   - Python 3.10+ with torch torchaudio transformers soundfile fastapi uvicorn
#   - NVIDIA CUDA GPU (optional; falls back to CPU mode if CUDA unavailable)
#
# Usage:
#   bash scripts/start-voice-cloning-worker.sh

set -e

HOST="${VOICE_CLONING_HOST:-0.0.0.0}"
PORT="${VOICE_CLONING_PORT:-8010}"
MODEL_PATH="${VOICE_CLONING_MODEL_PATH:-./models/chatterbox}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"

cd "${BACKEND_DIR}"

export VOICE_CLONING_MODEL_PATH="${MODEL_PATH}"

echo ""
echo "=========================================="
echo " Chatterbox Voice Cloning Server"
echo " Port     : ${PORT}"
echo " Host     : ${HOST}"
echo " Endpoint : http://${HOST}:${PORT}/health"
echo " Docs     : http://${HOST}:${PORT}/docs"
echo "=========================================="
echo ""

python app/workers/standalone_voice_cloning_server.py \
    --host "${HOST}" \
    --port "${PORT}"
