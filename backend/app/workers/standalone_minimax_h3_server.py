"""
Standalone MiniMax H3 Omni-Modal GPU Server / Worker Endpoint.
Can be run on any NVIDIA CUDA machine (Linux, WSL2, RunPod, AWS EC2)
to provide a dedicated MiniMax H3 Omni-AV inference worker service for GenVid.AI.
"""

import argparse
import os
from pathlib import Path
import sys
from typing import Any, Dict

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import uvicorn

from app.engines.minimax_h3.diagnostics import check_minimax_h3_environment
from app.engines.minimax_h3.models import (
    MiniMaxH3GenerationRequest,
    MiniMaxH3GenerationResult,
    MiniMaxH3StatusCode,
    MiniMaxH3TaskType,
)
from app.engines.minimax_h3.runner import MiniMaxH3InferenceRunner

app = FastAPI(title="GenVid.AI - Dedicated MiniMax H3 Omni-AV GPU Worker", version="1.0.0")

_runner: MiniMaxH3InferenceRunner | None = None
_job_history: Dict[str, MiniMaxH3GenerationResult] = {}


def get_runner() -> MiniMaxH3InferenceRunner:
    global _runner
    if _runner is None:
        checkpoints_dir = os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR", "./models/minimax_h3")
        output_dir = os.environ.get("MINIMAX_H3_OUTPUT_DIR", "./output/minimax_h3")
        _runner = MiniMaxH3InferenceRunner(checkpoints_dir=checkpoints_dir, output_dir=output_dir)
    return _runner


@app.get("/health")
def health_check():
    """Health and telemetry endpoint."""
    runner = get_runner()
    diag = check_minimax_h3_environment(checkpoints_dir=runner.checkpoints_dir)
    return {
        "status": "HEALTHY" if diag.is_available else diag.status_code.value,
        "engine": "minimax-h3",
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "message": diag.diagnostic_message,
        "supports_audio": True,
    }


@app.get("/capabilities")
def get_capabilities():
    """Exposes MiniMax H3 engine capabilities."""
    return {
        "engine_id": "minimax-h3",
        "display_name": "MiniMax H3 Omni-AV Engine",
        "tasks_supported": ["T2VA", "FL2VA", "REF2VA"],
        "text_to_video": True,
        "image_to_video": True,
        "first_frame_conditioning": True,
        "last_frame_conditioning": True,
        "native_audio": True,
        "audio_sample_rate": 32000,
        "reference_conditioning": True,
        "native_long_video": False,
        "max_clip_duration_seconds": 15.0,
    }


@app.get("/diagnostics")
def get_diagnostics():
    """Returns granular diagnostic inspection."""
    runner = get_runner()
    diag = check_minimax_h3_environment(checkpoints_dir=runner.checkpoints_dir)
    return {
        "status_code": diag.status_code.value,
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "pytorch_version": diag.pytorch_version,
        "diffusers_version": diag.diffusers_version,
        "transformers_version": diag.transformers_version,
        "models_found": diag.models_found,
        "missing_dependencies": diag.missing_dependencies,
        "diagnostic_message": diag.diagnostic_message,
    }


@app.post("/generate")
def generate_omni_av(req: dict):
    """Executes real MiniMax H3 Omni-Modal Video and Audio generation."""
    runner = get_runner()
    diag = check_minimax_h3_environment(checkpoints_dir=runner.checkpoints_dir)
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

    task_type = MiniMaxH3TaskType.T2VA
    if req.get("image_start") or req.get("image_end"):
        task_type = MiniMaxH3TaskType.FL2VA
    if req.get("reference_images") or req.get("reference_audios"):
        task_type = MiniMaxH3TaskType.REF2VA

    h3_req = MiniMaxH3GenerationRequest(
        prompt=req.get("prompt", ""),
        negative_prompt=req.get("negative_prompt", ""),
        task_type=task_type,
        width=int(req.get("width", width)),
        height=int(req.get("height", height)),
        num_frames=int(req.get("num_frames", 125)),
        fps=int(req.get("fps", 25)),
        num_inference_steps=int(req.get("num_inference_steps", 35)),
        guidance_scale=float(req.get("guidance_scale", 5.0)),
        seed=int(req.get("seed", 42)),
        generate_audio=bool(req.get("generate_audio", True)),
        image_start=req.get("image_start"),
        image_end=req.get("image_end"),
        reference_images=req.get("reference_images", []),
        reference_audios=req.get("reference_audios", []),
        model_type=req.get("model_type", "minimax-h3-v1"),
        job_id=req.get("id"),
    )

    result: MiniMaxH3GenerationResult = runner.execute_generation(h3_req)
    _job_history[result.job_id] = result

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)

    return result.to_dict()


@app.get("/status/{job_id}")
def get_job_status(job_id: str):
    """Retrieves status of a generation job."""
    if job_id not in _job_history:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    res = _job_history[job_id]
    return res.to_dict()


@app.post("/cancel/{job_id}")
def cancel_job(job_id: str):
    """Signals cancellation for a running job."""
    runner = get_runner()
    cancelled = runner.cancel(job_id)
    return {"job_id": job_id, "cancelled": cancelled}


@app.get("/output/{job_id}")
def get_job_output(job_id: str):
    """Downloads the generated video file for a job."""
    if job_id not in _job_history:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    res = _job_history[job_id]
    if not res.video_path or not Path(res.video_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found on disk.")
    return FileResponse(res.video_path, media_type="video/mp4", filename=Path(res.video_path).name)


def main():
    parser = argparse.ArgumentParser(description="Start MiniMax H3 Standalone GPU Worker Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8007, help="Port (default: 8007)")
    args = parser.parse_args()

    print(f"Starting MiniMax H3 Omni-AV GPU Worker on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
