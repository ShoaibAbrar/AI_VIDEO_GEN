"""
Voice Cloning GPU Worker implementing BaseGPUWorker.
Provides queue-based and remote execution for Chatterbox zero-shot voice synthesis tasks.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from app.core.logging_config import logger
from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
from app.services.voice.cloning.engine import VoiceCloningEngine
from app.services.voice.cloning.models import (
    VoiceCloningRequest,
    VoiceCloningResult,
    VoiceCloningStatusCode,
    VoiceProfile,
)
from app.workers.base import (
    BaseGPUWorker,
    WorkerHealthStatus,
    WorkerProgress,
    WorkerResult,
    WorkerTaskHandle,
    WorkerTaskStatus,
    WorkerTelemetry,
    WorkerType,
)


class VoiceCloningGPUWorker(BaseGPUWorker):
    """
    Dedicated GPU worker specialized for Chatterbox zero-shot voice cloning.
    Port: 8010 (when deployed as standalone server)
    """

    def __init__(
        self,
        worker_id: str = "voice-cloning-gpu-worker-default",
        engine: Optional[VoiceCloningEngine] = None,
        output_dir: Optional[str | Path] = None,
    ):
        self._worker_id = worker_id
        self._output_dir = Path(
            output_dir
            or os.environ.get("VOICE_CLONING_OUTPUT_DIR")
            or "./output/voice_cloning"
        ).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._engine = engine or VoiceCloningEngine()
        self._last_heartbeat = datetime.now(timezone.utc)
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_logs: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
        self._initialized = False

    # ------------------------------------------------------------------
    # BaseGPUWorker Interface
    # ------------------------------------------------------------------

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.LOCAL

    @property
    def supported_engines(self) -> List[str]:
        return ["voice-cloning", "chatterbox"]

    def initialize(self) -> None:
        with self._lock:
            self._initialized = True
            self._last_heartbeat = datetime.now(timezone.utc)
            diag = check_voice_cloning_environment()
            logger.info(
                f"[VoiceCloningWorker '{self._worker_id}'] initialized. "
                f"Status: {diag.status_code.value} — {diag.diagnostic_message}"
            )

    def get_telemetry(self) -> WorkerTelemetry:
        with self._lock:
            try:
                import torch
                if torch.cuda.is_available():
                    props = torch.cuda.get_device_properties(0)
                    gpu_name = torch.cuda.get_device_name(0)
                    vram_total_mb = int(props.total_memory / (1024 * 1024))
                    vram_used_mb = int(torch.cuda.memory_allocated(0) / (1024 * 1024))
                    health = WorkerHealthStatus.HEALTHY
                else:
                    gpu_name = "CPU / No CUDA"
                    vram_total_mb = 0
                    vram_used_mb = 0
                    health = WorkerHealthStatus.HEALTHY
            except ImportError:
                gpu_name = "torch not installed"
                vram_total_mb = 0
                vram_used_mb = 0
                health = WorkerHealthStatus.UNAVAILABLE

            return WorkerTelemetry(
                worker_id=self._worker_id,
                worker_type=WorkerType.LOCAL,
                health_status=health,
                gpu_name=gpu_name,
                vram_total_mb=vram_total_mb,
                vram_used_mb=vram_used_mb,
                active_tasks=len(self._active_tasks),
                last_heartbeat=self._last_heartbeat,
                supported_engines=["voice-cloning"],
            )

    def send_heartbeat(self) -> bool:
        with self._lock:
            self._last_heartbeat = datetime.now(timezone.utc)
        return True

    def submit_task(
        self,
        task_id: str,
        job_id: str,
        engine_id: str,
        model_type: str,
        settings: Dict[str, Any],
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        with self._lock:
            self._task_logs[task_id] = [
                f"[{datetime.now(timezone.utc).isoformat()}] Voice cloning task submitted."
            ]
            self._active_tasks[task_id] = {
                "status": WorkerTaskStatus.QUEUED,
                "job_id": job_id,
                "settings": settings,
            }

        handle = WorkerTaskHandle(
            task_id=task_id,
            worker_id=self._worker_id,
            job_id=job_id,
            engine_id=engine_id,
            status=WorkerTaskStatus.QUEUED,
        )

        # Background thread execution
        thread = threading.Thread(
            target=self._execute_task,
            args=(task_id, job_id, settings, on_progress, handle),
            daemon=True,
        )
        thread.start()
        return handle

    def _execute_task(
        self,
        task_id: str,
        job_id: str,
        settings: Dict[str, Any],
        on_progress: Optional[Callable[[WorkerProgress], None]],
        handle: WorkerTaskHandle,
    ) -> None:
        with self._lock:
            if task_id in self._active_tasks:
                self._active_tasks[task_id]["status"] = WorkerTaskStatus.RUNNING
        handle.status = WorkerTaskStatus.RUNNING

        try:
            req = VoiceCloningRequest(
                text=str(settings.get("text", "")),
                voice_profile_id=settings.get("voice_profile_id"),
                reference_audio_path=settings.get("reference_audio_path"),
                language=str(settings.get("language", "en")),
                speed=float(settings.get("speed", 1.0)),
                pitch=float(settings.get("pitch", 0.0)),
                exaggeration=float(settings.get("exaggeration", 0.0)),
                cfg_weight=float(settings.get("cfg_weight", 0.5)),
                job_id=task_id,
                extra_options={"consent_confirmed": bool(settings.get("consent_confirmed", True))},
            )

            def _prog(pct: float, msg: str):
                with self._lock:
                    self._task_logs.setdefault(task_id, []).append(
                        f"[{datetime.now(timezone.utc).isoformat()}] {pct:.1f}%: {msg}"
                    )
                if on_progress:
                    on_progress(WorkerProgress(task_id=task_id, percent=pct, status_text=msg))

            result = self._engine.clone_voice(req)

            final_status = WorkerTaskStatus.COMPLETED if result.success else WorkerTaskStatus.FAILED
            with self._lock:
                if task_id in self._active_tasks:
                    self._active_tasks[task_id]["status"] = final_status
                    self._active_tasks[task_id]["result"] = result
            handle.status = final_status

        except Exception as exc:
            logger.error(f"[VoiceCloningWorker] Task {task_id} failed: {exc}", exc_info=True)
            with self._lock:
                if task_id in self._active_tasks:
                    self._active_tasks[task_id]["status"] = WorkerTaskStatus.FAILED
                    self._active_tasks[task_id]["error"] = str(exc)
            handle.status = WorkerTaskStatus.FAILED
            handle.error_message = str(exc)

    def get_task_status(self, task_id: str) -> WorkerTaskStatus:
        with self._lock:
            task = self._active_tasks.get(task_id)
            return task.get("status", WorkerTaskStatus.FAILED) if task else WorkerTaskStatus.FAILED

    def get_task_logs(self, task_id: str, tail_lines: int = 100) -> List[str]:
        with self._lock:
            logs = self._task_logs.get(task_id, [])
            return logs[-tail_lines:]

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._active_tasks.get(task_id)
            if task:
                task["status"] = WorkerTaskStatus.CANCELLED
        return self._engine.runner.cancel(task_id)

    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        timeout = 300
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_task_status(handle.task_id)
            if status in (WorkerTaskStatus.COMPLETED, WorkerTaskStatus.FAILED, WorkerTaskStatus.CANCELLED):
                break
            time.sleep(0.5)

        with self._lock:
            task = self._active_tasks.get(handle.task_id, {})
            result: Optional[VoiceCloningResult] = task.get("result")
            error = task.get("error") or handle.error_message

        if result is not None:
            return WorkerResult(
                task_id=handle.task_id,
                success=result.success,
                output_paths=[result.audio_path] if result.audio_path else [],
                error_message=result.error_message,
                logs=self.get_task_logs(handle.task_id),
                execution_time_seconds=result.execution_time_seconds,
            )

        return WorkerResult(
            task_id=handle.task_id,
            success=False,
            error_message=error or "Voice cloning task timed out.",
            logs=self.get_task_logs(handle.task_id),
        )

    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        with self._lock:
            task = self._active_tasks.get(task_id, {})
            result = task.get("result")

        if result and result.audio_path and Path(result.audio_path).exists():
            dest = Path(destination_dir) / Path(result.audio_path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result.audio_path, dest)
            return dest

        raise FileNotFoundError(f"Cloned audio output not found for task {task_id}.")

    def retry_task(
        self,
        handle: WorkerTaskHandle,
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        if handle.retry_count >= handle.max_retries:
            return handle

        with self._lock:
            settings = self._active_tasks.get(handle.task_id, {}).get("settings", {})
            job_id = self._active_tasks.get(handle.task_id, {}).get("job_id", handle.job_id)

        handle.retry_count += 1
        new_task_id = str(uuid.uuid4())
        return self.submit_task(
            task_id=new_task_id,
            job_id=job_id,
            engine_id=handle.engine_id,
            model_type="chatterbox-multilingual",
            settings=settings,
            on_progress=on_progress,
        )

    def shutdown(self) -> None:
        with self._lock:
            self._initialized = False
        logger.info(f"[VoiceCloningWorker '{self._worker_id}'] shut down.")
