"""Single-worker database queue for Wan2GP generation jobs."""

from __future__ import annotations

import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core.logging_config import logger
from app.models.generation import GenerationJob, GenerationStatus
from app.services.wan2gp_service import Wan2GPProgress, Wan2GPService


class GenerationWorker:
    """Process one database job at a time using one reusable Wan2GP session."""

    def __init__(
        self,
        session_factory: sessionmaker,
        wan2gp_service: Wan2GPService,
        storage_root: str | Path | None = None,
        poll_seconds: float | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._wan2gp = wan2gp_service
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
        self._wan2gp.shutdown()
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

    def _process_job(self, job: GenerationJob) -> None:
        self._active_job_id = job.id
        progress_callback = self._progress_callback(job.id)
        try:
            settings_payload = dict(job.generation_settings)
            handle = self._wan2gp.submit_generation(settings_payload, progress_callback)
            self._active_handle = handle
            result = self._wan2gp.wait_for_result(handle)
            if not getattr(result, "success", False):
                message = self._safe_result_error(result)
                self._mark_failed(job.id, message)
                return

            output_path = self._store_first_video(job, result)
            self._mark_completed(job.id, output_path)
        except Exception as exc:
            logger.exception("Wan2GP generation failed for job %s", job.id)
            self._mark_failed(job.id, self._safe_error(exc))
        finally:
            self._active_handle = None
            self._active_job_id = None

    def _progress_callback(self, job_id: str) -> Callable[[Wan2GPProgress], None]:
        last_persisted = {"time": 0.0, "value": None}

        def update(progress: Wan2GPProgress) -> None:
            now = time.monotonic()
            value = (progress.progress, progress.current_step, progress.total_steps, progress.phase, progress.status)
            if now - last_persisted["time"] < 0.5 and value == last_persisted["value"]:
                return
            last_persisted["time"] = now
            last_persisted["value"] = value
            db: Session = self._session_factory()
            try:
                job = db.get(GenerationJob, job_id)
                if job is None or job.status != GenerationStatus.PROCESSING:
                    return
                job.progress = progress.progress
                job.current_step = progress.current_step
                job.total_steps = progress.total_steps
                job.phase = progress.phase
                job.status_text = progress.status
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Could not persist generation progress for job %s", job_id)
            finally:
                db.close()

        return update

    def _store_first_video(self, job: GenerationJob, result: object) -> str:
        generated_files = list(getattr(result, "generated_files", []) or [])
        artifact_paths = [getattr(artifact, "path", None) for artifact in getattr(result, "artifacts", ())]
        candidates = [str(path) for path in [*artifact_paths, *generated_files] if path]
        source = next((Path(path).resolve() for path in candidates if Path(path).is_file()), None)
        if source is None:
            raise FileNotFoundError("Wan2GP completed without a generated video artifact")
        if source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
            raise ValueError("Wan2GP returned an unsupported output file")

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
            return "Wan2GP could not complete the generation on the configured GPU."
        return text[:1000] or "Generation failed"

    @staticmethod
    def _safe_result_error(result: object) -> str:
        errors = list(getattr(result, "errors", ()) or ())
        if not errors:
            return "Wan2GP generation failed"
        return GenerationWorker._safe_error(Exception(str(errors[0])))
