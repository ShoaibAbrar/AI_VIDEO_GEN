"""
Standalone MiniMax H3 Director GPU Server / Worker Endpoint.
Can be run on any NVIDIA CUDA machine (Linux, WSL2, RunPod, AWS EC2)
to provide a dedicated H3 Director multi-shot narrative worker service for GenVid.AI.
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

from app.engines.minimax_h3_director.diagnostics import check_minimax_h3_director_environment
from app.engines.minimax_h3_director.models import (
    DirectorCharacterCard,
    H3DirectorGenerationRequest,
    H3DirectorGenerationResult,
    H3DirectorStatusCode,
)
from app.engines.minimax_h3_director.runner import MiniMaxH3DirectorRunner

app = FastAPI(title="GenVid.AI - Dedicated MiniMax H3 Director GPU Worker", version="1.0.0")

_runner: MiniMaxH3DirectorRunner | None = None
_job_history: Dict[str, H3DirectorGenerationResult] = {}


def get_runner() -> MiniMaxH3DirectorRunner:
    global _runner
    if _runner is None:
        checkpoints_dir = os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR", "./models/minimax_h3")
        output_dir = os.environ.get("MINIMAX_H3_DIRECTOR_OUTPUT_DIR", "./output/minimax_h3_director")
        _runner = MiniMaxH3DirectorRunner(checkpoints_dir=checkpoints_dir, output_dir=output_dir)
    return _runner


@app.get("/health")
def health_check():
    """Health and telemetry endpoint."""
    runner = get_runner()
    diag = check_minimax_h3_director_environment(checkpoints_dir=runner.checkpoints_dir)
    return {
        "status": "HEALTHY" if diag.is_available else diag.status_code.value,
        "engine": "minimax-h3-director",
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "downstream_h3_available": diag.downstream_h3_available,
        "message": diag.diagnostic_message,
        "supports_directed_multi_cut": True,
    }


@app.get("/capabilities")
def get_capabilities():
    """Exposes MiniMax H3 Director engine capabilities."""
    return {
        "engine_id": "minimax-h3-director",
        "display_name": "MiniMax H3 Director Engine",
        "multiple_characters": True,
        "timeline_prompt_zones": True,
        "character_reference_cards": True,
        "visual_continuity": True,
        "native_long_video": True,
        "audio_generation": True,
        "reference_image": True,
        "reference_audio": True,
        "reference_video": True,
    }


@app.get("/diagnostics")
def get_diagnostics():
    """Returns granular diagnostic inspection."""
    runner = get_runner()
    diag = check_minimax_h3_director_environment(checkpoints_dir=runner.checkpoints_dir)
    return {
        "status_code": diag.status_code.value,
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "downstream_h3_available": diag.downstream_h3_available,
        "ffmpeg_available": diag.ffmpeg_available,
        "missing_dependencies": diag.missing_dependencies,
        "diagnostic_message": diag.diagnostic_message,
    }


@app.post("/generate")
def generate_directed_video(req: dict):
    """Executes real MiniMax H3 Director multi-cut generation."""
    runner = get_runner()
    diag = check_minimax_h3_director_environment(checkpoints_dir=runner.checkpoints_dir)
    if not diag.is_available and not diag.is_mock:
        raise HTTPException(
            status_code=503,
            detail=f"[{diag.status_code.value}] {diag.diagnostic_message}",
        )

    chars = []
    for c in req.get("characters", []):
        if isinstance(c, dict):
            chars.append(
                DirectorCharacterCard(
                    character_id=c.get("character_id") or c.get("id") or "char",
                    name=c.get("name", "Character"),
                    description=c.get("description", ""),
                    reference_image_path=c.get("reference_image_path") or c.get("reference_image_url"),
                    reference_audio_path=c.get("reference_audio_path") or c.get("reference_audio_url"),
                    voice_name=c.get("voice_name"),
                )
            )

    h3_req = H3DirectorGenerationRequest(
        prompt=req.get("prompt", ""),
        title=req.get("title", "Directed Sequence"),
        total_duration_seconds=float(req.get("duration", req.get("total_duration_seconds", 15.0))),
        fps=int(req.get("fps", 25)),
        resolution=str(req.get("resolution", "1024*576")),
        num_inference_steps=int(req.get("num_inference_steps", 35)),
        guidance_scale=float(req.get("guidance_scale", 5.0)),
        seed=int(req.get("seed", 42)),
        generate_audio=bool(req.get("generate_audio", True)),
        enable_visual_continuity=bool(req.get("enable_visual_continuity", True)),
        characters=chars,
        job_id=req.get("id"),
    )

    result: H3DirectorGenerationResult = runner.execute_generation(h3_req)
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
    parser = argparse.ArgumentParser(description="Start MiniMax H3 Director Standalone GPU Worker Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8008, help="Port (default: 8008)")
    args = parser.parse_args()

    print(f"Starting MiniMax H3 Director GPU Worker on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
