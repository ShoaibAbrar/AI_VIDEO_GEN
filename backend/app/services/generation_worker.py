"""Database queue worker for video generation engines."""

from __future__ import annotations

import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core.logging_config import logger
from app.engines.base import BaseVideoEngine, EngineProgress
from app.engines.registry import VideoEngineRegistry, get_engine_registry
from app.models.generation import GenerationJob, GenerationStatus
from app.workers.base import BaseGPUWorker, WorkerProgress, WorkerResult
from app.workers.local_worker import LocalGPUWorker
from app.workers.pool import GPUWorkerPool, get_default_worker_pool


class GenerationWorker:
    """Process one database job at a time using registered GPU worker(s) & video engines."""

    def __init__(
        self,
        session_factory: sessionmaker,
        wan2gp_service: Any = None,
        storage_root: str | Path | None = None,
        poll_seconds: float | None = None,
        *,
        engine_registry: VideoEngineRegistry | None = None,
        worker_pool: GPUWorkerPool | None = None,
    ) -> None:
        self._session_factory = session_factory

        # Resolve Worker Pool / Engine Registry / Direct Engine
        if isinstance(wan2gp_service, GPUWorkerPool):
            self._worker_pool = wan2gp_service
            self._registry = None
            self._engine = None
        elif worker_pool is not None:
            self._worker_pool = worker_pool
            self._registry = engine_registry
            self._engine = None
        elif isinstance(wan2gp_service, VideoEngineRegistry):
            self._registry = wan2gp_service
            self._engine = None
            self._worker_pool = GPUWorkerPool()
            self._worker_pool.register_worker(LocalGPUWorker(engine_registry=self._registry))
        elif engine_registry is not None:
            self._registry = engine_registry
            self._engine = None
            self._worker_pool = GPUWorkerPool()
            self._worker_pool.register_worker(LocalGPUWorker(engine_registry=self._registry))
        elif isinstance(wan2gp_service, BaseGPUWorker):
            self._registry = None
            self._engine = None
            self._worker_pool = GPUWorkerPool()
            self._worker_pool.register_worker(wan2gp_service)
        elif wan2gp_service is not None:
            self._engine = wan2gp_service
            self._registry = None
            self._worker_pool = None
        else:
            self._registry = get_engine_registry()
            self._engine = None
            self._worker_pool = get_default_worker_pool()

        self._storage_root = Path(storage_root or settings.STORAGE_PATH).resolve()
        self._poll_seconds = poll_seconds if poll_seconds is not None else settings.GENERATION_WORKER_POLL_SECONDS
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_handle = None
        self._active_job_id: str | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="generation-worker")
        self._thread.start()
        logger.info("Generation worker started")

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
        if self._worker_pool is not None:
            self._worker_pool.shutdown_all()
        if self._registry is not None:
            self._registry.shutdown_all()
        elif self._engine is not None and hasattr(self._engine, "shutdown"):
            self._engine.shutdown()
        logger.info("Generation worker stopped")

    def wake(self) -> None:
        self._wake_event.set()

    def run_once(self) -> bool:
        job = self._claim_next_job()
        if job is None:
            return False
        try:
            self._process_job(job)
        except Exception:
            logger.exception("Unexpected generation worker failure for job %s", job.id)
            self._mark_failed(job.id, "Generation worker failed")
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = self.run_once()
            except Exception:
                logger.exception("Generation worker loop failure")
                processed = False
            if processed:
                continue
            self._wake_event.wait(timeout=max(0.1, self._poll_seconds))
            self._wake_event.clear()

    def _claim_next_job(self) -> GenerationJob | None:
        db: Session = self._session_factory()
        try:
            query = (
                select(GenerationJob)
                .where(GenerationJob.status == GenerationStatus.QUEUED)
                .order_by(GenerationJob.created_at, GenerationJob.id)
                .with_for_update(skip_locked=True)
            )
            job = db.execute(query).scalars().first()
            if job is None:
                db.rollback()
                return None
            if not job.can_transition_to(GenerationStatus.PROCESSING):
                db.rollback()
                return None
            job.status = GenerationStatus.PROCESSING
            job.started_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
            return job
        finally:
            db.close()

    def _resolve_engine(self, job: GenerationJob) -> Any:
        if self._registry is not None:
            settings_dict = job.generation_settings or {}
            engine_id = settings_dict.get("engine_id")
            if engine_id:
                return self._registry.get_engine(engine_id)
            if job.model_type:
                return self._registry.resolve_engine_for_model(job.model_type)
            return self._registry.get_engine()
        return self._engine

    def _process_job(self, job: GenerationJob) -> None:
        self._active_job_id = job.id
        progress_callback = self._progress_callback(job.id)
        try:
            settings_payload = dict(job.generation_settings or {})
            if self._worker_pool is not None:
                engine_id = settings_payload.get("engine_id")
                if not engine_id:
                    if job.model_type:
                        try:
                            reg = self._registry or get_engine_registry()
                            engine_inst = reg.resolve_engine_for_model(job.model_type)
                            engine_id = engine_inst.engine_id
                        except Exception:
                            engine_id = "wan2gp"
                    else:
                        engine_id = "wan2gp"

                handle = self._worker_pool.dispatch_job(
                    task_id=f"task_{job.id}",
                    job_id=job.id,
                    engine_id=engine_id,
                    model_type=job.model_type or "",
                    settings=settings_payload,
                    on_progress=progress_callback,
                )
                self._active_handle = handle
                result = self._worker_pool.wait_for_result(handle)
                if not getattr(result, "success", False):
                    message = self._safe_result_error(result)
                    self._mark_failed(job.id, message)
                    return

                output_path = self._store_first_video(job, result)
                self._mark_completed(job.id, output_path)
            else:
                engine = self._resolve_engine(job)
                handle = engine.submit_generation(settings_payload, progress_callback)
                self._active_handle = handle
                result = engine.wait_for_result(handle)
                if not getattr(result, "success", False):
                    message = self._safe_result_error(result)
                    self._mark_failed(job.id, message)
                    return

                output_path = self._store_first_video(job, result)
                self._mark_completed(job.id, output_path)
        except Exception as exc:
            logger.exception("Generation failed for job %s", job.id)
            self._mark_failed(job.id, self._safe_error(exc))
        finally:
            self._active_handle = None
            self._active_job_id = None

    def _progress_callback(self, job_id: str) -> Callable[[Any], None]:
        last_persisted = {"time": 0.0, "value": None}

        def update(progress: Any) -> None:
            now = time.monotonic()
            prog_val = getattr(progress, "progress", None)
            if prog_val is None:
                prog_val = getattr(progress, "percent", None)

            value = (
                prog_val,
                getattr(progress, "current_step", None),
                getattr(progress, "total_steps", None),
                getattr(progress, "phase", None),
                getattr(progress, "status", None) or getattr(progress, "status_text", None),
            )
            if now - last_persisted["time"] < 0.5 and value == last_persisted["value"]:
                return
            last_persisted["time"] = now
            last_persisted["value"] = value
            db: Session = self._session_factory()
            try:
                job = db.get(GenerationJob, job_id)
                if job is None or job.status != GenerationStatus.PROCESSING:
                    return
                job.progress = prog_val
                job.current_step = getattr(progress, "current_step", None)
                job.total_steps = getattr(progress, "total_steps", None)
                job.phase = getattr(progress, "phase", None)
                job.status_text = getattr(progress, "status", None) or getattr(progress, "status_text", None)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Could not persist generation progress for job %s", job_id)
            finally:
                db.close()

        return update

    def _store_first_video(self, job: GenerationJob, result: object) -> str:
        output_files = list(getattr(result, "output_files", []) or [])
        output_paths = list(getattr(result, "output_paths", []) or [])
        generated_files = list(getattr(result, "generated_files", []) or [])
        artifact_paths = [getattr(artifact, "path", None) for artifact in getattr(result, "artifacts", ())]
        candidates = [str(path) for path in [*output_files, *output_paths, *artifact_paths, *generated_files] if path]
        source = next((Path(path).resolve() for path in candidates if Path(path).is_file()), None)
        if source is None:
            raise FileNotFoundError("Video engine completed without a generated video artifact")
        if source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
            raise ValueError("Video engine returned an unsupported output file")

        destination = self._storage_root / "videos" / str(job.user_id) / job.id / f"output{source.suffix.lower()}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination.relative_to(self._storage_root).as_posix()

    def _mark_completed(self, job_id: str, output_path: str) -> None:
        db: Session = self._session_factory()
        try:
            job = db.get(GenerationJob, job_id)
            if job is None or not job.can_transition_to(GenerationStatus.COMPLETED):
                return
            job.status = GenerationStatus.COMPLETED
            job.output_path = output_path
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

    def _mark_failed(self, job_id: str, message: str) -> None:
        db: Session = self._session_factory()
        try:
            job = db.get(GenerationJob, job_id)
            if job is None:
                return
            if job.status == GenerationStatus.QUEUED:
                job.status = GenerationStatus.FAILED
            elif job.can_transition_to(GenerationStatus.FAILED):
                job.status = GenerationStatus.FAILED
            else:
                return
            job.error_message = message[:1000]
            job.completed_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _safe_error(error: Exception) -> str:
        text = str(error).strip()
        if "out of memory" in text.lower() or "cuda" in text.lower():
            return "Video engine could not complete generation on the configured GPU."
        return text[:1000] or "Generation failed"

    @staticmethod
    def _safe_result_error(result: object) -> str:
        if getattr(result, "error_message", None):
            return GenerationWorker._safe_error(Exception(str(result.error_message)))
        errors = list(getattr(result, "errors", ()) or ())
        if not errors:
            return "Video engine generation failed"
        return GenerationWorker._safe_error(Exception(str(errors[0])))
