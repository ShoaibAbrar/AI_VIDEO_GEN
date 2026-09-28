"""
Dedicated MiniMax H3 Director GPU Worker.
Executes multi-cut directed narrative workflows with telemetry, path safety, and normalized output.
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
from app.engines.minimax_h3_director.diagnostics import check_minimax_h3_director_environment
from app.engines.minimax_h3_director.models import (
    DirectorCharacterCard,
    DirectorShotCut,
    H3DirectorGenerationRequest,
    H3DirectorGenerationResult,
    H3DirectorStatusCode,
)
from app.engines.minimax_h3_director.runner import MiniMaxH3DirectorRunner
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


class MiniMaxH3DirectorGPUWorker(BaseGPUWorker):
    """
    Dedicated GPU worker specialized for MiniMax H3 Director multi-shot narrative workloads.
    """

    def __init__(
        self,
        worker_id: str = "h3-director-gpu-worker-default",
        runner: Optional[MiniMaxH3DirectorRunner] = None,
        checkpoints_dir: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
    ) -> None:
        self._worker_id = worker_id
        self._output_dir = Path(output_dir or "./output/minimax_h3_director").resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._runner = runner or MiniMaxH3DirectorRunner(
            checkpoints_dir=checkpoints_dir,
            output_dir=self._output_dir,
        )
        self._last_heartbeat = datetime.now(timezone.utc)
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_logs: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
        self._initialized = False

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.LOCAL

    @property
    def supported_engines(self) -> List[str]:
        return ["minimax-h3-director"]

    def initialize(self) -> None:
        with self._lock:
            self._initialized = True
            self._last_heartbeat = datetime.now(timezone.utc)
            logger.info(f"MiniMaxH3DirectorGPUWorker '{self._worker_id}' initialized.")

    def _validate_path_safety(self, path_str: Optional[str]) -> Optional[str]:
        if not path_str:
            return None
        p = Path(path_str).resolve()
        p_str = str(p).lower()
        if p_str in ["/", "\\", "c:\\", "c:\\windows", "c:\\windows\\system32"] or p == p.parent or "system32" in p_str:
            raise ValueError(f"Insecure path rejected: {path_str}")
        return str(p)

    def get_telemetry(self) -> WorkerTelemetry:
        vram_total = 0
        vram_used = 0
        gpu_name = "CPU / Unknown"

        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram_total = int(props.total_memory / (1024 * 1024))
                vram_used = int(torch.cuda.memory_allocated(0) / (1024 * 1024))
        except Exception:
            pass

        with self._lock:
            running_tasks = [
                t for t in self._active_tasks.values() if t.get("status") == WorkerTaskStatus.RUNNING
            ]
            health = WorkerHealthStatus.HEALTHY if len(running_tasks) < 2 else WorkerHealthStatus.BUSY

            return WorkerTelemetry(
                worker_id=self._worker_id,
                worker_type=self.worker_type,
                health_status=health,
                gpu_name=gpu_name,
                vram_total_mb=vram_total,
                vram_used_mb=vram_used,
                active_tasks=len(running_tasks),
                last_heartbeat=datetime.now(timezone.utc),
                supported_engines=self.supported_engines,
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
        if engine_id and engine_id != "minimax-h3-director":
            raise ValueError(f"MiniMaxH3DirectorGPUWorker only supports 'minimax-h3-director', received '{engine_id}'.")

        with self._lock:
            handle = WorkerTaskHandle(
                task_id=task_id,
                worker_id=self._worker_id,
                job_id=job_id,
                engine_id=engine_id or "minimax-h3-director",
                status=WorkerTaskStatus.RUNNING,
            )
            self._task_logs[task_id] = [
                f"[{datetime.now(timezone.utc).isoformat()}] Task {task_id} received by MiniMaxH3DirectorGPUWorker."
            ]
            task_entry = {
                "handle": handle,
                "task_id": task_id,
                "job_id": job_id,
                "engine_id": engine_id or "minimax-h3-director",
                "settings": settings,
                "status": WorkerTaskStatus.RUNNING,
                "progress": 0.0,
                "output_files": [],
                "error_message": None,
                "error_code": None,
                "started_at": datetime.now(timezone.utc),
                "completed_at": None,
                "on_progress": on_progress,
            }
            self._active_tasks[task_id] = task_entry

        # Character card normalization
        chars: List[DirectorCharacterCard] = []
        raw_chars = settings.get("characters", [])
        for c in raw_chars:
            if isinstance(c, dict):
                chars.append(
                    DirectorCharacterCard(
                        character_id=c.get("character_id") or c.get("id") or str(uuid.uuid4()),
                        name=c.get("name", "Character"),
                        description=c.get("description", ""),
                        reference_image_path=self._validate_path_safety(c.get("reference_image_path") or c.get("reference_image_url")),
                        reference_audio_path=self._validate_path_safety(c.get("reference_audio_path") or c.get("reference_audio_url")),
                        voice_name=c.get("voice_name"),
                    )
                )

        req = H3DirectorGenerationRequest(
            prompt=settings.get("prompt", ""),
            title=settings.get("title", "Directed Sequence"),
            total_duration_seconds=float(settings.get("duration", settings.get("total_duration_seconds", 15.0))),
            fps=int(settings.get("fps", 25)),
            resolution=str(settings.get("resolution", "1024*576")),
            num_inference_steps=int(settings.get("num_inference_steps", 35)),
            guidance_scale=float(settings.get("guidance_scale", 5.0)),
            seed=int(settings.get("seed", 42)),
            generate_audio=bool(settings.get("generate_audio", True)),
            enable_visual_continuity=bool(settings.get("enable_visual_continuity", True)),
            characters=chars,
            job_id=task_id,
        )

        def _execute_worker_thread():
            try:
                def _prog_bridge(pct: float, detail: str):
                    with self._lock:
                        if task_id in self._active_tasks:
                            self._active_tasks[task_id]["progress"] = pct
                            self._task_logs[task_id].append(
                                f"[{datetime.now(timezone.utc).isoformat()}] Progress {pct:.1f}%: {detail}"
                            )
                    if on_progress:
                        on_progress(
                            WorkerProgress(
                                task_id=task_id,
                                percent=pct,
                                status_text=detail,
                                phase="director_orchestration",
                            )
                        )

                gen_res: H3DirectorGenerationResult = self._runner.execute_generation(
                    request=req,
                    progress_callback=_prog_bridge,
                )

                with self._lock:
                    if gen_res.success:
                        files = [gen_res.combined_media_path or gen_res.video_path]
                        task_entry["status"] = WorkerTaskStatus.COMPLETED
                        task_entry["output_files"] = [f for f in files if f]
                        task_entry["progress"] = 100.0
                        task_entry["metadata"] = gen_res.metadata
                        handle.status = WorkerTaskStatus.COMPLETED
                    else:
                        task_entry["status"] = WorkerTaskStatus.FAILED
                        task_entry["error_message"] = gen_res.error_message
                        task_entry["error_code"] = gen_res.error_code
                        handle.status = WorkerTaskStatus.FAILED
                        handle.error_message = gen_res.error_message

                    task_entry["completed_at"] = datetime.now(timezone.utc)
                    self._task_logs[task_id].append(
                        f"[{datetime.now(timezone.utc).isoformat()}] Task finished (status={task_entry['status']})."
                    )

            except Exception as exc:
                with self._lock:
                    task_entry["status"] = WorkerTaskStatus.FAILED
                    task_entry["error_message"] = str(exc)
                    task_entry["completed_at"] = datetime.now(timezone.utc)
                    handle.status = WorkerTaskStatus.FAILED
                    handle.error_message = str(exc)
                    self._task_logs[task_id].append(
                        f"[{datetime.now(timezone.utc).isoformat()}] Exception in worker thread: {exc}"
                    )

        t = threading.Thread(target=_execute_worker_thread, daemon=True)
        t.start()

        return handle

    def get_task_status(self, task_id: str) -> WorkerTaskStatus:
        with self._lock:
            task = self._active_tasks.get(task_id)
            if not task:
                return WorkerTaskStatus.FAILED
            return task.get("status", WorkerTaskStatus.RUNNING)

    def get_task_logs(self, task_id: str, tail_lines: int = 100) -> List[str]:
        with self._lock:
            logs = self._task_logs.get(task_id, [])
            return logs[-tail_lines:]

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._active_tasks.get(task_id)
            if task:
                self._runner.cancel(task_id)
                task["status"] = WorkerTaskStatus.CANCELLED
                if task.get("handle"):
                    task["handle"].status = WorkerTaskStatus.CANCELLED
                self._task_logs[task_id].append(
                    f"[{datetime.now(timezone.utc).isoformat()}] Task {task_id} cancelled by user."
                )
                return True
            return False

    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        task_id = handle.task_id
        start_wait = time.time()

        while True:
            with self._lock:
                task = self._active_tasks.get(task_id)
                if not task:
                    return WorkerResult(
                        task_id=task_id,
                        success=False,
                        error_message="Task not found in active worker list.",
                    )

                status = task["status"]
                if status in [WorkerTaskStatus.COMPLETED, WorkerTaskStatus.FAILED, WorkerTaskStatus.CANCELLED]:
                    return WorkerResult(
                        task_id=task_id,
                        success=status == WorkerTaskStatus.COMPLETED,
                        output_paths=task.get("output_files", []),
                        error_message=task.get("error_message"),
                        logs=self._task_logs.get(task_id, []),
                    )

            if time.time() - start_wait > 300:
                return WorkerResult(
                    task_id=task_id,
                    success=False,
                    error_message="Worker timeout waiting for result.",
                )
            time.sleep(0.05)

    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        with self._lock:
            task = self._active_tasks.get(task_id)
            if not task or not task.get("output_files"):
                raise FileNotFoundError(f"No output file recorded for task {task_id}")
            src_file = Path(task["output_files"][0])

        if not src_file.exists():
            raise FileNotFoundError(f"Source output file missing: {src_file}")

        destination_dir.mkdir(parents=True, exist_ok=True)
        dest_file = destination_dir / src_file.name
        shutil.copy2(src_file, dest_file)
        return dest_file

    def retry_task(
        self,
        handle: WorkerTaskHandle,
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        with self._lock:
            task = self._active_tasks.get(handle.task_id)
            if not task:
                raise ValueError(f"Task {handle.task_id} not found for retry.")
            settings = task["settings"]
            job_id = task["job_id"]
            model_type = settings.get("model_type", "minimax-h3-director-hd")

        handle.retry_count += 1
        return self.submit_task(
            task_id=handle.task_id,
            job_id=job_id,
            engine_id="minimax-h3-director",
            model_type=model_type,
            settings=settings,
            on_progress=on_progress,
        )

    def health_check(self) -> WorkerHealthStatus:
        with self._lock:
            self._last_heartbeat = datetime.now(timezone.utc)
            return WorkerHealthStatus.HEALTHY

    def shutdown(self) -> None:
        with self._lock:
            self._active_tasks.clear()
            self._runner.unload()
            self._initialized = False
            logger.info(f"MiniMaxH3DirectorGPUWorker '{self._worker_id}' shut down.")
