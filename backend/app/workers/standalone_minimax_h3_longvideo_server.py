"""
Standalone MiniMax H3 LongVideos GPU Server / Worker Endpoint.
Can be run on any NVIDIA CUDA machine (Linux, WSL2, RunPod, AWS EC2)
to provide a dedicated H3 LongVideos sliding-window worker service for GenVid.AI.

Port: 8009
"""

import argparse
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from app.engines.minimax_h3_longvideos.diagnostics import check_h3_longvideo_environment
from app.engines.minimax_h3_longvideos.models import (
    H3LongVideoGenerationRequest,
    H3LongVideoGenerationResult,
    LongVideoCharacterCard,
)
from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner

app = FastAPI(
    title="GenVid.AI — Dedicated MiniMax H3 LongVideos GPU Worker",
    version="1.0.0",
    description=(
        "Standalone FastAPI server that exposes the MiniMax H3 LongVideos sliding-window "
        "multi-chunk generation engine on port 8009."
    ),
)

_runner: Optional[MiniMaxH3LongVideoRunner] = None
_job_history: Dict[str, H3LongVideoGenerationResult] = {}


def get_runner() -> MiniMaxH3LongVideoRunner:
    global _runner
    if _runner is None:
        checkpoints_dir = os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR", "./models/minimax_h3")
        output_dir = os.environ.get("MINIMAX_H3_LONGVIDEO_OUTPUT_DIR", "./output/minimax_h3_longvideos")
        _runner = MiniMaxH3LongVideoRunner(
            checkpoints_dir=checkpoints_dir,
            output_dir=output_dir,
        )
    return _runner


# ---------------------------------------------------------------------------
# Health & Diagnostics
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Health and telemetry endpoint for H3 LongVideos worker."""
    runner = get_runner()
    diag = check_h3_longvideo_environment(checkpoints_dir=runner.checkpoints_dir)
    return {
        "status": "HEALTHY" if diag.is_available else diag.status_code.value,
        "engine": "minimax-h3-longvideo",
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "pytorch_version": diag.pytorch_version,
        "downstream_h3_available": diag.downstream_h3_available,
        "chunk_vram_budget_gb": diag.chunk_vram_budget_gb,
        "max_feasible_chunks": diag.max_feasible_chunks,
        "message": diag.diagnostic_message,
        "supports_sliding_window": True,
        "supports_beat_planning": True,
        "supports_fl2va_continuity": True,
        "supports_audio_crossfade": True,
        "max_duration_seconds": 300,
        "port": 8009,
    }


@app.get("/diagnostics")
def diagnostics():
    """Full diagnostic report for H3 LongVideos environment."""
    runner = get_runner()
    diag = check_h3_longvideo_environment(checkpoints_dir=runner.checkpoints_dir)
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
        "model_weights_path": diag.model_weights_path,
        "models_found": diag.models_found,
        "missing_dependencies": diag.missing_dependencies,
        "downstream_h3_available": diag.downstream_h3_available,
        "chunk_vram_budget_gb": diag.chunk_vram_budget_gb,
        "max_feasible_chunks": diag.max_feasible_chunks,
        "message": diag.diagnostic_message,
    }


@app.get("/models")
def list_models():
    """List supported models for H3 LongVideos engine."""
    return {
        "engine_id": "minimax-h3-longvideo",
        "models": [
            {
                "model_id": "minimax-h3-longvideo-v1",
                "name": "MiniMax H3 Long Video (Sliding Window)",
                "description": (
                    "Sliding-window multi-chunk long video generation using MiniMax H3 Omni-AV. "
                    "Beat-based scene planning, FL2VA visual continuity, 32kHz stereo audio crossfade."
                ),
                "native_long_video": True,
                "max_duration_seconds": 300,
                "default_chunk_duration_seconds": 5.0,
                "audio_sample_rate": 32000,
                "min_vram_gb": 24.0,
                "recommended_vram_gb": 48.0,
                "upstream": "https://github.com/MiniMax-AI/MiniMax-H3",
                "community_longvideo_reference": "https://huggingface.co/Smite79/MiniMax-H3-Longvideos",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class GenerationPayload:
    pass


from pydantic import BaseModel


class CharacterCardPayload(BaseModel):
    character_id: str
    name: str = "Character"
    description: str = ""
    reference_image_path: Optional[str] = None
    reference_audio_path: Optional[str] = None
    voice_name: Optional[str] = None


class GenerationRequest(BaseModel):
    job_id: Optional[str] = None
    prompt: str
    scene_description: str = ""
    beats_text: Optional[str] = None
    characters: List[CharacterCardPayload] = []
    title: str = "H3 Long Video"
    total_duration_seconds: float = 15.0
    chunk_duration_seconds: float = 5.0
    overlap_frames: int = 0
    fps: int = 25
    resolution: str = "1024*576"
    num_inference_steps: int = 35
    guidance_scale: float = 5.0
    seed: int = 42
    generate_audio: bool = True
    enable_visual_continuity: bool = True
    enable_audio_crossfade: bool = True
    audio_crossfade_duration_seconds: float = 0.2
    plan_only: bool = False


@app.post("/generate", response_model=None)
def generate(payload: GenerationRequest):
    """
    Submit a sliding-window long video generation job.
    Returns plan in plan_only mode, otherwise executes full generation.
    """
    runner = get_runner()
    diag = check_h3_longvideo_environment(checkpoints_dir=runner.checkpoints_dir)
    if not diag.is_available:
        raise HTTPException(
            status_code=503,
            detail=f"H3 LongVideos unavailable: {diag.diagnostic_message}",
        )

    chars = [
        LongVideoCharacterCard(
            character_id=c.character_id,
            name=c.name,
            description=c.description,
            reference_image_path=c.reference_image_path,
            reference_audio_path=c.reference_audio_path,
            voice_name=c.voice_name,
        )
        for c in payload.characters
    ]

    import uuid
    request = H3LongVideoGenerationRequest(
        prompt=payload.prompt,
        scene_description=payload.scene_description,
        beats_text=payload.beats_text,
        characters=chars,
        title=payload.title,
        total_duration_seconds=payload.total_duration_seconds,
        chunk_duration_seconds=payload.chunk_duration_seconds,
        overlap_frames=payload.overlap_frames,
        fps=payload.fps,
        resolution=payload.resolution,
        num_inference_steps=payload.num_inference_steps,
        guidance_scale=payload.guidance_scale,
        seed=payload.seed,
        generate_audio=payload.generate_audio,
        enable_visual_continuity=payload.enable_visual_continuity,
        enable_audio_crossfade=payload.enable_audio_crossfade,
        audio_crossfade_duration_seconds=payload.audio_crossfade_duration_seconds,
        plan_only=payload.plan_only,
        job_id=payload.job_id or str(uuid.uuid4()),
    )

    result = runner.execute_long_video(request)
    _job_history[result.job_id] = result

    return {
        "job_id": result.job_id,
        "status": result.status,
        "success": result.success,
        "plan_only": result.plan_only,
        "video_path": result.video_path,
        "audio_path": result.audio_path,
        "combined_media_path": result.combined_media_path,
        "output_paths": result.output_paths,
        "chunks": result.chunks,
        "plan": result.plan,
        "error_message": result.error_message,
        "execution_time_seconds": result.execution_time_seconds,
        "telemetry": result.telemetry,
    }


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Retrieve status and result for a completed job."""
    result = _job_history.get(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {
        "job_id": result.job_id,
        "status": result.status,
        "success": result.success,
        "video_path": result.video_path,
        "audio_path": result.audio_path,
        "error_message": result.error_message,
        "execution_time_seconds": result.execution_time_seconds,
    }


@app.get("/jobs/{job_id}/download")
def download_video(job_id: str):
    """Download the generated video for a completed job."""
    result = _job_history.get(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    if not result.video_path or not Path(result.video_path).exists():
        raise HTTPException(status_code=404, detail="Output video not found.")
    return FileResponse(
        result.video_path,
        media_type="video/mp4",
        filename=f"minimax_h3_longvideo_{job_id}.mp4",
    )


@app.get("/plan")
def plan_only(
    prompt: str,
    total_duration_seconds: float = 15.0,
    chunk_duration_seconds: float = 5.0,
    fps: int = 25,
    resolution: str = "1024*576",
):
    """
    Dry-run: return the sliding-window chunk plan without generating video.
    Equivalent to setting plan_only=True in /generate.
    """
    runner = get_runner()
    from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
    planner = H3LongVideoPlanner(fps=fps)
    req = H3LongVideoGenerationRequest(
        prompt=prompt,
        total_duration_seconds=total_duration_seconds,
        chunk_duration_seconds=chunk_duration_seconds,
        fps=fps,
        resolution=resolution,
        plan_only=True,
    )
    plan = planner.plan(req)
    return {
        "title": plan.title,
        "total_duration_seconds": plan.total_duration_seconds,
        "fps": plan.fps,
        "resolution": plan.resolution,
        "num_chunks": len(plan.chunks),
        "estimated_vram_gb": plan.estimated_vram_gb,
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "start_second": c.start_second,
                "end_second": c.end_second,
                "duration_seconds": c.duration_seconds,
                "num_frames": c.num_frames,
                "prompt": c.prompt[:80],
            }
            for c in plan.chunks
        ],
        "report": planner.plan_report(plan),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MiniMax H3 LongVideos GPU Worker Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8009, help="Bind port (default: 8009)")
    parser.add_argument("--checkpoints-dir", default=None, help="Path to MiniMax H3 model checkpoints")
    parser.add_argument("--output-dir", default=None, help="Output directory for generated videos")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload (dev only)")
    args = parser.parse_args()

    if args.checkpoints_dir:
        os.environ["MINIMAX_H3_CHECKPOINTS_DIR"] = args.checkpoints_dir
    if args.output_dir:
        os.environ["MINIMAX_H3_LONGVIDEO_OUTPUT_DIR"] = args.output_dir

    print(f"[H3LongVideo Worker] Starting on http://{args.host}:{args.port}")
    print(f"[H3LongVideo Worker] Health: http://{args.host}:{args.port}/health")
    print(f"[H3LongVideo Worker] Docs:   http://{args.host}:{args.port}/docs")
    uvicorn.run(
        "standalone_minimax_h3_longvideo_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
