"""
Dedicated MiniMax H3 LongVideos GPU Worker.
Executes sliding-window multi-chunk long video workflows with telemetry,
checkpoint resumption, and normalized output.
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
from app.engines.minimax_h3_longvideos.diagnostics import check_h3_longvideo_environment
from app.engines.minimax_h3_longvideos.models import (
    H3LongVideoGenerationRequest,
    LongVideoCharacterCard,
)
from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner
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


class MiniMaxH3LongVideoGPUWorker(BaseGPUWorker):
    """
    Dedicated GPU worker specialized for MiniMax H3 LongVideos sliding-window workloads.
    Port: 8009 (when running as standalone server)
    """

    def __init__(
        self,
        worker_id: str = "h3-longvideo-gpu-worker-default",
        runner: Optional[MiniMaxH3LongVideoRunner] = None,
        checkpoints_dir: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
    ) -> None:
        self._worker_id = worker_id
        self._output_dir = Path(
            output_dir
            or os.environ.get("MINIMAX_H3_LONGVIDEO_OUTPUT_DIR", "./output/minimax_h3_longvideos")
        ).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._runner = runner or MiniMaxH3LongVideoRunner(
            checkpoints_dir=checkpoints_dir,
            output_dir=self._output_dir,
        )
        self._last_heartbeat = datetime.now(timezone.utc)
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_logs: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
        self._initialized = False

    # ------------------------------------------------------------------
    # BaseGPUWorker interface
    # ------------------------------------------------------------------

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.LOCAL

    @property
    def supported_engines(self) -> List[str]:
        return ["minimax-h3-longvideo"]

    def initialize(self) -> None:
        with self._lock:
            self._initialized = True
            self._last_heartbeat = datetime.now(timezone.utc)
            diag = check_h3_longvideo_environment()
            logger.info(
                f"[H3LVWorker '{self._worker_id}'] initialized. "
                f"Status: {diag.status_code.value} — {diag.diagnostic_message}"
            )

    def get_telemetry(self) -> WorkerTelemetry:
        with self._lock:
            try:
                import torch  # type: ignore
                if torch.cuda.is_available():
                    props = torch.cuda.get_device_properties(0)
                    gpu_name = torch.cuda.get_device_name(0)
                    vram_total_mb = int(props.total_memory / (1024 * 1024))
                    vram_used_mb = int(torch.cuda.memory_reserved(0) / (1024 * 1024))
                    health = WorkerHealthStatus.HEALTHY
                else:
                    gpu_name = "No CUDA GPU"
                    vram_total_mb = 0
                    vram_used_mb = 0
                    health = WorkerHealthStatus.UNAVAILABLE
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
                supported_engines=["minimax-h3-longvideo"],
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
                f"[{datetime.now(timezone.utc).isoformat()}] H3 LongVideos task submitted."
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

        # Run in background thread
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
            chars_raw = settings.get("characters", [])
            characters = [
                LongVideoCharacterCard(
                    character_id=c.get("character_id", c.get("id", f"char_{i}")),
                    name=c.get("name", "Unknown"),
                    description=c.get("description", ""),
                    reference_image_path=c.get("reference_image_path"),
                    reference_audio_path=c.get("reference_audio_path"),
                    voice_name=c.get("voice_name"),
                )
                for i, c in enumerate(chars_raw)
            ] if isinstance(chars_raw, list) else []

            request = H3LongVideoGenerationRequest(
                prompt=str(settings.get("prompt", "")),
                scene_description=str(settings.get("scene_description", "")),
                beats_text=settings.get("beats_text"),
                characters=characters,
                title=str(settings.get("title", "H3 Long Video")),
                total_duration_seconds=float(settings.get("total_duration_seconds", 15.0)),
                chunk_duration_seconds=float(settings.get("chunk_duration_seconds", 5.0)),
                overlap_frames=int(settings.get("overlap_frames", 0)),
                fps=int(settings.get("fps", 25)),
                resolution=str(settings.get("resolution", "1024*576")),
                num_inference_steps=int(settings.get("num_inference_steps", 35)),
                guidance_scale=float(settings.get("guidance_scale", 5.0)),
                seed=int(settings.get("seed", 42)),
                generate_audio=bool(settings.get("generate_audio", True)),
                enable_visual_continuity=bool(settings.get("enable_visual_continuity", True)),
                enable_audio_crossfade=bool(settings.get("enable_audio_crossfade", True)),
                plan_only=bool(settings.get("plan_only", False)),
                job_id=task_id,
            )

            def _progress(pct: float, msg: str) -> None:
                with self._lock:
                    self._task_logs.setdefault(task_id, []).append(
                        f"[{datetime.now(timezone.utc).isoformat()}] {pct:.1f}%: {msg}"
                    )
                if on_progress:
                    on_progress(WorkerProgress(task_id=task_id, percent=pct, status_text=msg))

            result = self._runner.execute_long_video(request, progress_callback=_progress)

            final_status = WorkerTaskStatus.COMPLETED if result.success else WorkerTaskStatus.FAILED
            with self._lock:
                if task_id in self._active_tasks:
                    self._active_tasks[task_id]["status"] = final_status
                    self._active_tasks[task_id]["result"] = result
            handle.status = final_status

        except Exception as exc:
            logger.error(f"[H3LVWorker] Task {task_id} exception: {exc}", exc_info=True)
            with self._lock:
                if task_id in self._active_tasks:
                    self._active_tasks[task_id]["status"] = WorkerTaskStatus.FAILED
                    self._active_tasks[task_id]["error"] = str(exc)
            handle.status = WorkerTaskStatus.FAILED
            handle.error_message = str(exc)

    def get_task_status(self, task_id: str) -> WorkerTaskStatus:
        with self._lock:
            task = self._active_tasks.get(task_id)
            if task is None:
                return WorkerTaskStatus.FAILED
            return task.get("status", WorkerTaskStatus.FAILED)

    def get_task_logs(self, task_id: str, tail_lines: int = 100) -> List[str]:
        with self._lock:
            logs = self._task_logs.get(task_id, [])
            return logs[-tail_lines:]

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._active_tasks.get(task_id)
            if task:
                task["status"] = WorkerTaskStatus.CANCELLED
        return self._runner.cancel(task_id)

    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        timeout = 3600  # 1 hour max for long video jobs
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_task_status(handle.task_id)
            if status in (WorkerTaskStatus.COMPLETED, WorkerTaskStatus.FAILED, WorkerTaskStatus.CANCELLED):
                break
            time.sleep(2.0)

        with self._lock:
            task = self._active_tasks.get(handle.task_id, {})
            result = task.get("result")
            error = task.get("error") or handle.error_message

        if result is not None:
            return WorkerResult(
                task_id=handle.task_id,
                success=result.success,
                output_paths=list(result.output_paths or []),
                error_message=result.error_message,
                logs=self.get_task_logs(handle.task_id),
                execution_time_seconds=result.execution_time_seconds,
            )

        return WorkerResult(
            task_id=handle.task_id,
            success=False,
            error_message=error or "H3 LongVideos task failed or timed out.",
            logs=self.get_task_logs(handle.task_id),
        )

    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        with self._lock:
            task = self._active_tasks.get(task_id, {})
            result = task.get("result")

        if result and result.video_path and Path(result.video_path).exists():
            dest = Path(destination_dir) / Path(result.video_path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result.video_path, dest)
            return dest

        raise FileNotFoundError(
            f"H3 LongVideos output not found for task {task_id}."
        )

    def retry_task(
        self,
        handle: WorkerTaskHandle,
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        if handle.retry_count >= handle.max_retries:
            logger.warning(f"[H3LVWorker] Task {handle.task_id} exceeded max retries ({handle.max_retries}).")
            return handle

        with self._lock:
            settings = self._active_tasks.get(handle.task_id, {}).get("settings", {})
            job_id = self._active_tasks.get(handle.task_id, {}).get("job_id", handle.job_id)

        handle.retry_count += 1
        new_task_id = str(uuid.uuid4())
        logger.info(f"[H3LVWorker] Retrying task {handle.task_id} as {new_task_id} (attempt {handle.retry_count}).")
        return self.submit_task(
            task_id=new_task_id,
            job_id=job_id,
            engine_id=handle.engine_id,
            model_type="minimax-h3-longvideo-v1",
            settings=settings,
            on_progress=on_progress,
        )

    def shutdown(self) -> None:
        with self._lock:
            self._initialized = False
        if self._runner:
            try:
                self._runner.shutdown()
            except Exception:
                pass
        logger.info(f"[H3LVWorker '{self._worker_id}'] shut down.")
