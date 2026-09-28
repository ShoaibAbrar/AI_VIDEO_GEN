"""
Standalone LTX-2 Audio-Video GPU Server / Worker Endpoint.
Can be run on any NVIDIA CUDA machine (Windows, Linux, WSL2, RunPod, AWS EC2)
to provide a dedicated LTX-2 joint Audio-Video inference worker service for the GenVid.AI platform.
"""

import argparse
import os
from pathlib import Path
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException
import uvicorn

from app.engines.ltx2.diagnostics import check_ltx2_environment
from app.engines.ltx2.models import LTX2GenerationRequest, LTX2GenerationResult
from app.engines.ltx2.runner import LTX2InferenceRunner

app = FastAPI(title="GenVid.AI - Dedicated LTX-2 Audio-Video GPU Worker", version="1.0.0")

_runner: LTX2InferenceRunner | None = None


def get_runner() -> LTX2InferenceRunner:
    global _runner
    if _runner is None:
        checkpoints_dir = os.environ.get("LTX2_CHECKPOINTS_DIR", "./models/ltx2")
        output_dir = os.environ.get("LTX2_OUTPUT_DIR", "./output/ltx2")
        _runner = LTX2InferenceRunner(checkpoints_dir=checkpoints_dir, output_dir=output_dir)
    return _runner


@app.get("/health")
def health_check():
    """Health and telemetry endpoint."""
    runner = get_runner()
    diag = check_ltx2_environment(checkpoints_dir=runner.checkpoints_dir)
    return {
        "status": "HEALTHY" if diag.is_available else diag.status_code.value,
        "engine": "ltx-2",
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "message": diag.diagnostic_message,
        "supports_audio": True,
    }


@app.post("/generate")
def generate_video_and_audio(req: dict):
    """Executes real LTX-2 Audio-Video generation."""
    runner = get_runner()
    diag = check_ltx2_environment(checkpoints_dir=runner.checkpoints_dir)
    if not diag.is_available and not diag.is_mock:
        raise HTTPException(
            status_code=503,
            detail=f"[{diag.status_code.value}] {diag.diagnostic_message}",
        )

    res_str = str(req.get("resolution", "1024*576"))
    width, height = 1024, 576
    if "*" in res_str:
        parts = res_str.split("*")
        width, height = int(parts[0]), int(parts[1])
    elif "x" in res_str:
        parts = res_str.split("x")
        width, height = int(parts[0]), int(parts[1])

    ltx2_req = LTX2GenerationRequest(
        prompt=req.get("prompt", ""),
        negative_prompt=req.get("negative_prompt", ""),
        width=int(req.get("width", width)),
        height=int(req.get("height", height)),
        num_frames=int(req.get("num_frames", 125)),
        fps=int(req.get("fps", 25)),
        num_inference_steps=int(req.get("num_inference_steps", 40)),
        guidance_scale=float(req.get("guidance_scale", 4.5)),
        seed=int(req.get("seed", 42)),
        generate_audio=bool(req.get("generate_audio", True)),
        image_start=req.get("image_start"),
        model_type=req.get("model_type", "ltx-2-19b-av"),
        job_id=req.get("id"),
    )

    result: LTX2GenerationResult = runner.execute_generation(ltx2_req)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return {
        "job_id": result.job_id,
        "status": result.status,
        "success": result.success,
        "video_path": result.video_path,
        "audio_path": result.audio_path,
        "combined_media_path": result.combined_media_path,
        "duration": result.duration,
        "width": result.width,
        "height": result.height,
        "fps": result.fps,
        "num_frames": result.num_frames,
        "has_audio": result.has_audio,
        "metadata": result.metadata,
    }


def main():
    parser = argparse.ArgumentParser(description="Start LTX-2 Standalone GPU Worker Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8006, help="Port (default: 8006)")
    args = parser.parse_args()

    print(f"Starting LTX-2 Audio-Video GPU Worker on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
