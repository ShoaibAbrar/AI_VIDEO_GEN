"""Authenticated generation job and model endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.db.database import SessionLocal, get_db
from app.engines.base import BaseVideoEngine
from app.engines.registry import VideoEngineRegistry, get_engine_registry
from app.models.generation import GenerationJob, GenerationStatus
from app.schemas.generation import GenerationCancelResponse, GenerationCreate, GenerationRead, ModelMetadata
from app.schemas.requirements import GenerationPlanRead, UserRequirements
from app.services.capability_resolver import CapabilityResolver
from app.services.generation_worker import GenerationWorker
from app.services.wan2gp_service import Wan2GPService

router = APIRouter(prefix="/generations", tags=["generations"])

engine_registry = get_engine_registry()
generation_worker = GenerationWorker(SessionLocal, engine_registry=engine_registry)


def get_engine_registry_dep() -> VideoEngineRegistry:
    return engine_registry


def get_wan2gp_service() -> Any:
    wan_engine = engine_registry.get_engine("wan2gp")
    if hasattr(wan_engine, "raw_service"):
        return wan_engine.raw_service
    return wan_engine


def get_generation_worker() -> GenerationWorker:
    return generation_worker


def _is_admin(user: User) -> bool:
    return user.has_role("admin")


def _to_read(job: GenerationJob, storage_root: Path) -> GenerationRead:
    output_available = False
    if job.output_path:
        try:
            output = (storage_root / job.output_path).resolve()
            output.relative_to(storage_root)
            output_available = output.is_file()
        except (OSError, ValueError):
            output_available = False
    return GenerationRead(
        id=job.id,
        status=job.status,
        prompt=job.prompt,
        model_type=job.model_type,
        generation_settings=job.generation_settings,
        progress=job.progress,
        current_step=job.current_step,
        total_steps=job.total_steps,
        phase=job.phase,
        status_text=job.status_text,
        output_available=output_available,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _get_visible_job(job_id: str, user: User, db: Session) -> GenerationJob:
    query = select(GenerationJob).where(GenerationJob.id == job_id)
    if not _is_admin(user):
        query = query.where(GenerationJob.user_id == user.id)
    job = db.execute(query).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found")
    return job


@router.get("/engines")
async def list_engines(
    current_user: User = Depends(get_current_user),
    registry: VideoEngineRegistry = Depends(get_engine_registry_dep),
):
    """Discover all registered video generation engines and their capabilities."""
    del current_user
    return registry.list_engines()


@router.post("/plan", response_model=GenerationPlanRead)
async def generate_plan(
    requirements: UserRequirements,
    current_user: User = Depends(get_current_user),
    registry: VideoEngineRegistry = Depends(get_engine_registry_dep),
):
    """
    Resolve user-level requirements against available video engines to produce
    a deterministic, explainable generation plan with capabilities, selection reasons, and fallbacks.
    """
    del current_user
    try:
        return CapabilityResolver.resolve_plan(requirements, registry, preferred_engine_id=requirements.preferred_engine_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not resolve capability plan: {exc}",
        ) from exc


@router.post("/by-requirements", response_model=GenerationRead, status_code=status.HTTP_202_ACCEPTED)
async def create_generation_by_requirements(
    requirements: UserRequirements,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    registry: VideoEngineRegistry = Depends(get_engine_registry_dep),
    worker: GenerationWorker = Depends(get_generation_worker),
):
    """
    Submit a generation request driven by high-level user requirements.
    The backend capability resolver evaluates engines, creates the plan, and queues the job.
    """
    plan = CapabilityResolver.resolve_plan(requirements, registry, preferred_engine_id=requirements.preferred_engine_id)
    if not plan.selected_engine_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No video engine is available to handle this request.",
        )

    try:
        engine = registry.get_engine(plan.selected_engine_id)
        validated_settings = engine.validate_generation(plan.normalized_settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Engine '{plan.selected_engine_id}' is unavailable: {exc}",
        ) from exc

    # Store plan metadata in generation_settings for auditability and UI feedback
    validated_settings["generation_plan"] = plan.model_dump()

    job = GenerationJob(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        status=GenerationStatus.QUEUED,
        prompt=requirements.prompt,
        model_type=plan.selected_model_type or "default",
        generation_settings=validated_settings,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    worker.wake()
    return _to_read(job, Path(settings.STORAGE_PATH).resolve())


@router.get("/models", response_model=List[ModelMetadata])
async def list_models(
    current_user: User = Depends(get_current_user),
    service: Any = Depends(get_wan2gp_service),
):
    del current_user
    try:
        return service.list_models()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Models are unavailable") from exc


@router.post("", response_model=GenerationRead, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    payload: GenerationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: Any = Depends(get_wan2gp_service),
    worker: GenerationWorker = Depends(get_generation_worker),
):
    try:
        validated_settings = service.validate_generation(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Generation engine is unavailable") from exc

    job = GenerationJob(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        status=GenerationStatus.QUEUED,
        prompt=payload.prompt,
        model_type=payload.model_type,
        generation_settings=validated_settings,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    worker.wake()
    return _to_read(job, Path(settings.STORAGE_PATH).resolve())


@router.get("", response_model=List[GenerationRead])
async def list_generations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(GenerationJob).order_by(GenerationJob.created_at.desc())
    if not _is_admin(current_user):
        query = query.where(GenerationJob.user_id == current_user.id)
    jobs = db.execute(query).scalars().all()
    storage_root = Path(settings.STORAGE_PATH).resolve()
    return [_to_read(job, storage_root) for job in jobs]


@router.get("/{job_id}", response_model=GenerationRead)
async def get_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_visible_job(job_id, current_user, db)
    return _to_read(job, Path(settings.STORAGE_PATH).resolve())


@router.get("/{job_id}/video")
@router.get("/{job_id}/output")
async def get_generation_video(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_visible_job(job_id, current_user, db)
    if job.status != GenerationStatus.COMPLETED or not job.output_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated video not found")
    storage_root = Path(settings.STORAGE_PATH).resolve()
    try:
        video_path = (storage_root / job.output_path).resolve()
        video_path.relative_to(storage_root)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated video not found") from exc
    if not video_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated video not found")
    return FileResponse(video_path, media_type="video/mp4", filename=video_path.name)


@router.get("/{job_id}/download")
async def download_generation_video(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = _get_visible_job(job_id, current_user, db)
    if job.status != GenerationStatus.COMPLETED or not job.output_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated video not found")
    storage_root = Path(settings.STORAGE_PATH).resolve()
    try:
        video_path = (storage_root / job.output_path).resolve()
        video_path.relative_to(storage_root)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated video not found") from exc
    if not video_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated video not found")
    return FileResponse(
        video_path,
        media_type="application/octet-stream",
        filename=f"generation_{job_id}.mp4",
        headers={"Content-Disposition": f'attachment; filename="generation_{job_id}.mp4"'},
    )


@router.post("/{job_id}/cancel", response_model=GenerationCancelResponse)
async def cancel_generation(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    worker: GenerationWorker = Depends(get_generation_worker),
):
    job = _get_visible_job(job_id, current_user, db)
    if job.status != GenerationStatus.QUEUED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only queued jobs can be cancelled")
    job.status = GenerationStatus.CANCELLED
    db.commit()
    worker.wake()
    return GenerationCancelResponse(id=job.id, status=job.status)
