"""
Standalone LTX-Video GPU Server / Worker Endpoint.
Can be run on any NVIDIA CUDA machine (Windows, Linux, WSL2, RunPod, AWS EC2)
to provide a dedicated LTX-Video inference worker service for the GenVid.AI platform.
"""

import argparse
import os
from pathlib import Path
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

from app.engines.ltx_video.diagnostics import check_ltx_environment
from app.engines.ltx_video.models import LTXGenerationRequest, LTXGenerationResult
from app.engines.ltx_video.runner import LTXVideoInferenceRunner

app = FastAPI(title="GenVid.AI - Dedicated LTX-Video GPU Worker", version="1.0.0")

_runner: LTXVideoInferenceRunner | None = None


def get_runner() -> LTXVideoInferenceRunner:
    global _runner
    if _runner is None:
        checkpoints_dir = os.environ.get("LTX_VIDEO_CHECKPOINTS_DIR", "./models/ltx_video")
        output_dir = os.environ.get("LTX_VIDEO_OUTPUT_DIR", "./output/ltx_video")
        _runner = LTXVideoInferenceRunner(checkpoints_dir=checkpoints_dir, output_dir=output_dir)
    return _runner


@app.get("/health")
def health_check():
    """Health and telemetry endpoint."""
    runner = get_runner()
    diag = check_ltx_environment(checkpoints_dir=runner.checkpoints_dir)
    return {
        "status": "HEALTHY" if diag.is_available else diag.status_code.value,
        "engine": "ltx-video",
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "message": diag.diagnostic_message,
    }


@app.post("/generate")
def generate_video(req: dict):
    """Executes real LTX-Video generation."""
    runner = get_runner()
    diag = check_ltx_environment(checkpoints_dir=runner.checkpoints_dir)
    if not diag.is_available and not diag.is_mock:
        raise HTTPException(
            status_code=503,
            detail=f"[{diag.status_code.value}] {diag.diagnostic_message}",
        )

    res_str = str(req.get("resolution", "768*512"))
    width, height = 768, 512
    if "*" in res_str:
        parts = res_str.split("*")
        width, height = int(parts[0]), int(parts[1])
    elif "x" in res_str:
        parts = res_str.split("x")
        width, height = int(parts[0]), int(parts[1])

    ltx_req = LTXGenerationRequest(
        prompt=req.get("prompt", ""),
        negative_prompt=req.get("negative_prompt", ""),
        width=int(req.get("width", width)),
        height=int(req.get("height", height)),
        num_frames=int(req.get("num_frames", 121)),
        fps=int(req.get("fps", 24)),
        num_inference_steps=int(req.get("num_inference_steps", 30)),
        guidance_scale=float(req.get("guidance_scale", 3.0)),
        seed=int(req.get("seed", 42)),
        image_start=req.get("image_start"),
        model_type=req.get("model_type", "ltx-video-0.9.5"),
        job_id=req.get("id"),
    )

    result: LTXGenerationResult = runner.execute_generation(ltx_req)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return {
        "job_id": result.job_id,
        "status": result.status,
        "success": result.success,
        "output_path": result.output_path,
        "duration": result.duration,
        "width": result.width,
        "height": result.height,
        "fps": result.fps,
        "num_frames": result.num_frames,
        "metadata": result.metadata,
    }


def main():
    parser = argparse.ArgumentParser(description="Start LTX-Video Standalone GPU Worker Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8005, help="Port (default: 8005)")
    args = parser.parse_args()

    print(f"Starting LTX-Video GPU Worker on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
