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
from app.models.generation import GenerationJob, GenerationStatus
from app.models.user import User
from app.schemas.generation import GenerationCancelResponse, GenerationCreate, GenerationRead, ModelMetadata
from app.services.generation_worker import GenerationWorker
from app.services.wan2gp_service import Wan2GPService

router = APIRouter(prefix="/generations", tags=["generations"])

wan2gp_service = Wan2GPService()
generation_worker = GenerationWorker(SessionLocal, wan2gp_service)


def get_wan2gp_service() -> Wan2GPService:
    return wan2gp_service


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


@router.get("/models", response_model=List[ModelMetadata])
async def list_models(
    current_user: User = Depends(get_current_user),
    service: Wan2GPService = Depends(get_wan2gp_service),
):
    del current_user
    try:
        return service.list_models()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Wan2GP models are unavailable") from exc


@router.post("", response_model=GenerationRead, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    payload: GenerationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: Wan2GPService = Depends(get_wan2gp_service),
    worker: GenerationWorker = Depends(get_generation_worker),
):
    try:
        validated_settings = service.validate_generation(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Wan2GP is unavailable") from exc

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
