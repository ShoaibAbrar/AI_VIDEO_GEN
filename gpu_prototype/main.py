"""Minimal real Wan2GP video-generation prototype."""

from __future__ import annotations

import shutil
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    import torch
except ImportError:
    torch = None

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs"
STATIC_ROOT = Path(__file__).resolve().parent / "static"

_session: Any = None
_session_lock = threading.Lock()
generation_lock = threading.Lock()
jobs: dict[str, dict[str, Any]] = {}


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    model: str | None = None
    steps: int = Field(default=20, ge=1, le=100)
    frames: int = Field(default=33, ge=1, le=9999)
    seed: int = Field(default=-1, ge=-1, le=2**63 - 1)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def gpu_info() -> dict[str, Any]:
    if torch is None:
        return {
            "cuda_available": False,
            "gpu_count": 0,
            "gpu_name": None,
            "pytorch_version": None,
            "cuda_version": None,
            "error": "PyTorch is not installed",
        }
    return {
        "cuda_available": bool(torch.cuda.is_available()),
        "gpu_count": int(torch.cuda.device_count()),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "pytorch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
    }


def get_session():
    global _session
    with _session_lock:
        if _session is None:
            from shared.api import init

            _session = init(
                root=ROOT,
                output_dir=OUTPUT_ROOT / "wan2gp-runtime",
                console_output=True,
                console_isatty=True,
            )
        return _session


def get_model_diagnostics() -> dict[str, Any]:
    if torch is None:
        return {
            "models": [],
            "unavailable": [
                {
                    "model_type": "t2v_1.3B",
                    "name": "Wan2.1 Text2video 1.3B",
                    "description": "PyTorch is not installed",
                    "availability": {"status": "missing", "status_code": 0, "available": False},
                }
            ],
            "setup_command": "python scripts/download_model.py t2v_1.3B",
            "error": "PyTorch is not installed",
        }
    try:
        session = get_session()
        records = session.list_model_metadata(include_availability=True, main_output="video")
        available_models = []
        unavailable_models = []
        
        for record in records:
            availability = record.get("availability", {})
            item = {
                "model_type": record.get("model_type"),
                "name": record.get("name", record.get("model_type")),
                "description": record.get("description", ""),
                "availability": availability,
            }
            if availability.get("available", False):
                available_models.append(item)
            else:
                unavailable_models.append(item)

        return {
            "models": available_models,
            "unavailable": unavailable_models,
            "setup_command": "python scripts/download_model.py t2v_1.3B",
        }
    except Exception as exc:
        return {
            "models": [],
            "unavailable": [
                {
                    "model_type": "t2v_1.3B",
                    "name": "Wan2.1 Text2video 1.3B",
                    "description": str(exc),
                    "availability": {"status": "missing", "status_code": 0, "available": False},
                }
            ],
            "setup_command": "python scripts/download_model.py t2v_1.3B",
            "error": str(exc),
        }



def model_records() -> list[dict[str, Any]]:
    return get_model_diagnostics()["models"]


def progress_callback(job_id: str):
    def on_progress(update: Any) -> None:
        job = jobs.get(job_id)
        if job is None:
            return
        job.update(
            {
                "progress": getattr(update, "progress", None),
                "phase": getattr(update, "phase", None),
                "status_text": getattr(update, "status", None),
                "current_step": getattr(update, "current_step", None),
                "total_steps": getattr(update, "total_steps", None),
            }
        )

    return on_progress


class ProgressCallbacks:
    def __init__(self, job_id: str):
        self._job_id = job_id

    def on_progress(self, update):
        progress_callback(self._job_id)(update)

    def on_status(self, status):
        job = jobs.get(self._job_id)
        if job is not None:
            job["status_text"] = str(status)


def run_generation(job_id: str, request: GenerationRequest) -> None:
    job = jobs[job_id]
    try:
        with generation_lock:
            job["status"] = "GENERATING"
            job["status_text"] = "Submitting to Wan2GP"
            session = get_session()
            model_type = request.model
            if not model_type:
                available = model_records()
                if not available:
                    raise RuntimeError("Model loading failed: no available video model was found")
                model_type = available[0]["model_type"]
            model_def = session.get_model_def(model_type)
            if model_def is None:
                raise ValueError(f"Unknown model: {model_type}")
            availability = session.get_model_availability(model_type)
            if not availability.get("available", False):
                raise RuntimeError(f"Model loading failed: model is unavailable: {model_type}")
            settings = session.get_default_settings(model_type)
            settings.update(
                {
                    "model_type": model_type,
                    "prompt": request.prompt,
                    "num_inference_steps": request.steps,
                    "video_length": request.frames,
                    "seed": request.seed,
                    "_api": {"return_media": False},
                }
            )
            job["model"] = model_type
            callbacks = ProgressCallbacks(job_id)
            wan_job = session.submit_task(settings, callbacks=callbacks)
            result = wan_job.result()
            if not result.success:
                message = str(result.errors[0]) if result.errors else "Wan2GP generation failed"
                raise RuntimeError(f"Generation failed: {message}")
            candidates = [*getattr(result, "generated_files", [])]
            candidates.extend(getattr(artifact, "path", None) for artifact in getattr(result, "artifacts", ()))
            source = next((Path(path).resolve() for path in candidates if path and Path(path).is_file()), None)
            if source is None:
                raise FileNotFoundError("Generation completed but Wan2GP returned no video file")
            if source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
                raise RuntimeError(f"Generation failed: unsupported output file {source.name}")
            destination = OUTPUT_ROOT / job_id / "generated.mp4"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            job.update({"status": "COMPLETED", "progress": 100, "output_file": str(destination), "completed_at": utc_now(), "status_text": "Completed"})
    except Exception as exc:
        message = str(exc)
        if "out of memory" in message.lower() or "cuda" in message.lower() or "gpu" in message.lower():
            message = f"CUDA/GPU unavailable: {message}"
        elif not message.lower().startswith(("model loading failed", "generation failed")):
            message = f"Generation failed: {message}"
        job.update({"status": "FAILED", "error": message, "completed_at": utc_now()})
        print(f"[{job_id}] {message}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"Wan2GP prototype GPU diagnostics: {gpu_info()}", flush=True)
    yield
    if _session is not None:
        _session.close()


app = FastAPI(title="Wan2GP GPU Prototype", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok", "gpu": gpu_info()}


@app.get("/api/models")
def models():
    try:
        diagnostics = get_model_diagnostics()
        return diagnostics
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Model loading failed: {exc}") from exc


@app.post("/api/generate", status_code=202)
def generate(request: GenerationRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=422, detail="Prompt cannot be blank")
    if generation_lock.locked():
        raise HTTPException(status_code=409, detail="A generation is already running")
    
    if torch is None:
        raise HTTPException(
            status_code=503,
            detail="CUDA/GPU unavailable: PyTorch is not installed in this Python environment",
        )

    requested_model = request.model or "t2v_1.3B"
    try:
        session = get_session()
        availability = session.get_model_availability(requested_model)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model loading failed: {exc}. Please run model setup: python scripts/download_model.py {requested_model}",
        ) from exc

    if not availability.get("available", False):
        status_text = availability.get("status", "unavailable")
        raise HTTPException(
            status_code=503,
            detail=(
                f"Model loading failed: Model '{requested_model}' is unavailable (status: {status_text}). "
                f"Please run model setup on your terminal: python scripts/download_model.py {requested_model}"
            ),
        )

    job_id = uuid.uuid4().hex

    jobs[job_id] = {
        "id": job_id,
        "status": "QUEUED",
        "progress": None,
        "phase": None,
        "status_text": "Queued",
        "current_step": None,
        "total_steps": None,
        "model": request.model,
        "prompt": request.prompt,
        "output_file": None,
        "error": None,
        "created_at": utc_now(),
        "completed_at": None,
    }
    threading.Thread(target=run_generation, args=(job_id, request), daemon=True, name=f"wan2gp-{job_id}").start()
    return jobs[job_id]


@app.get("/api/generate/{job_id}")
def generation_status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {key: value for key, value in job.items() if key != "output_file"}


@app.get("/api/video/{job_id}")
def video(job_id: str):
    job = jobs.get(job_id)
    if job is None or job["status"] != "COMPLETED" or not job.get("output_file"):
        raise HTTPException(status_code=404, detail="Completed video not found")
    output = Path(job["output_file"]).resolve()
    try:
        output.relative_to(OUTPUT_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Completed video not found") from exc
    if not output.is_file():
        raise HTTPException(status_code=404, detail="Completed video not found")
    return FileResponse(output, media_type="video/mp4", filename="generated.mp4")


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(STATIC_ROOT / "index.html")
