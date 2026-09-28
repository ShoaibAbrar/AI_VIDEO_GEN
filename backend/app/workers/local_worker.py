"""
Local GPU Worker implementation.
Executes generation workloads locally using the VideoEngineRegistry.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.core.logging_config import logger
from app.engines.base import EngineProgress, EngineResult
from app.engines.registry import VideoEngineRegistry, get_engine_registry
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


class LocalGPUWorker(BaseGPUWorker):
    """
    Worker executing generation tasks on the local machine/GPU
    via the VideoEngineRegistry.
    """

    def __init__(
        self,
        worker_id: str = "local-gpu-default",
        engine_registry: Optional[VideoEngineRegistry] = None,
        gpu_name: Optional[str] = None,
        vram_total_mb: Optional[int] = None,
    ) -> None:
        self._worker_id = worker_id
        self._registry = engine_registry or get_engine_registry()
        self._gpu_name = gpu_name
        self._vram_total_mb = vram_total_mb
        self._last_heartbeat = datetime.utcnow()
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
        return self._registry.list_engine_ids()

    def initialize(self) -> None:
        """Query local hardware status and initialize registry."""
        with self._lock:
            if not self._gpu_name or not self._vram_total_mb:
                self._detect_hardware()
            self._initialized = True
            self._last_heartbeat = datetime.utcnow()
            logger.info("LocalGPUWorker %s initialized with engines: %s", self._worker_id, self.supported_engines)

    def _detect_hardware(self) -> None:
        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                self._gpu_name = self._gpu_name or torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                self._vram_total_mb = self._vram_total_mb or int(props.total_memory / (1024 * 1024))
            else:
                self._gpu_name = self._gpu_name or "CPU Fallback"
                self._vram_total_mb = self._vram_total_mb or 0
        except Exception:
            self._gpu_name = self._gpu_name or "Standard Local System"
            self._vram_total_mb = self._vram_total_mb or 0

    def get_telemetry(self) -> WorkerTelemetry:
        vram_used = 0
        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                vram_used = int(torch.cuda.memory_allocated(0) / (1024 * 1024))
        except Exception:
            pass

        with self._lock:
            active_count = len([t for t in self._active_tasks.values() if t.get("status") == WorkerTaskStatus.RUNNING])
            health = WorkerHealthStatus.HEALTHY if active_count < 2 else WorkerHealthStatus.BUSY
            return WorkerTelemetry(
                worker_id=self._worker_id,
                worker_type=self.worker_type,
                health_status=health,
                gpu_name=self._gpu_name or "Local Hardware",
                vram_total_mb=self._vram_total_mb or 0,
                vram_used_mb=vram_used,
                active_tasks=active_count,
                last_heartbeat=self._last_heartbeat,
                supported_engines=self.supported_engines,
            )

    def send_heartbeat(self) -> bool:
        with self._lock:
            self._last_heartbeat = datetime.utcnow()
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
            if not self._initialized:
                self.initialize()

            handle = WorkerTaskHandle(
                task_id=task_id,
                worker_id=self._worker_id,
                job_id=job_id,
                engine_id=engine_id,
                status=WorkerTaskStatus.RUNNING,
            )
            self._task_logs[task_id] = [f"[{datetime.utcnow().isoformat()}] Task {task_id} received on local worker"]
            self._active_tasks[task_id] = {
                "handle": handle,
                "engine_id": engine_id,
                "settings": settings,
                "status": WorkerTaskStatus.RUNNING,
                "progress_callback": on_progress,
                "result": None,
                "engine_handle": None,
            }

        # Resolve engine
        engine = self._registry.get_engine(engine_id) if engine_id else self._registry.resolve_engine_for_model(model_type)

        def bridge_progress(prog: EngineProgress) -> None:
            pct = getattr(prog, "progress", 0.0) or 0.0
            cur_step = getattr(prog, "current_step", None)
            tot_step = getattr(prog, "total_steps", None)
            phase = getattr(prog, "phase", None)
            status_text = getattr(prog, "status", None)

            w_prog = WorkerProgress(
                task_id=task_id,
                percent=pct,
                current_step=cur_step,
                total_steps=tot_step,
                phase=phase,
                status_text=status_text,
                heartbeat_timestamp=datetime.utcnow(),
            )
            with self._lock:
                if task_id in self._task_logs:
                    self._task_logs[task_id].append(
                        f"[{datetime.utcnow().isoformat()}] Progress: {pct}% ({status_text or phase})"
                    )
            if on_progress:
                on_progress(w_prog)

        try:
            engine_handle = engine.submit_generation(settings, bridge_progress)
            with self._lock:
                self._active_tasks[task_id]["engine_handle"] = engine_handle
                handle.raw_handle = engine_handle
        except Exception as exc:
            logger.exception("Failed to submit task %s to engine %s", task_id, engine_id)
            with self._lock:
                handle.status = WorkerTaskStatus.FAILED
                handle.error_message = str(exc)
                self._active_tasks[task_id]["status"] = WorkerTaskStatus.FAILED
                self._active_tasks[task_id]["error_message"] = str(exc)
                self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] Execution error: {exc}")

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
            if not task:
                return False
            engine_id = task.get("engine_id")
            engine_handle = task.get("engine_handle")
            task["status"] = WorkerTaskStatus.CANCELLED
            if task.get("handle"):
                task["handle"].status = WorkerTaskStatus.CANCELLED
            self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] Task {task_id} cancelled")

        if engine_id and engine_handle:
            try:
                engine = self._registry.get_engine(engine_id)
                if hasattr(engine, "cancel_generation"):
                    engine.cancel_generation(engine_handle)
            except Exception as e:
                logger.warning("Error cancelling local engine execution: %s", e)
        return True

    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        task_id = handle.task_id
        with self._lock:
            task = self._active_tasks.get(task_id)
            if not task:
                return WorkerResult(
                    task_id=task_id,
                    success=False,
                    error_message=f"Task {task_id} not found on worker {self._worker_id}",
                )
            engine_id = task.get("engine_id")
            engine_handle = task.get("engine_handle")

        if not engine_handle:
            return WorkerResult(
                task_id=task_id,
                success=False,
                error_message=handle.error_message or "Task has no engine handle",
            )

        start_time = time.monotonic()
        try:
            engine = self._registry.get_engine(engine_id)
            gen_result = engine.wait_for_result(engine_handle)
            exec_time = time.monotonic() - start_time

            output_files: List[str] = []
            if hasattr(gen_result, "output_files") and gen_result.output_files:
                output_files = [str(p) for p in gen_result.output_files]
            elif hasattr(gen_result, "generated_files") and gen_result.generated_files:
                output_files = [str(p) for p in gen_result.generated_files]

            success = bool(getattr(gen_result, "success", False))
            err_msg = getattr(gen_result, "error_message", None)
            if not err_msg and getattr(gen_result, "errors", None):
                err_msg = str(gen_result.errors[0])

            with self._lock:
                self._task_logs[task_id].append(
                    f"[{datetime.utcnow().isoformat()}] Execution finished (success={success})"
                )
                task["status"] = WorkerTaskStatus.COMPLETED if success else WorkerTaskStatus.FAILED
                handle.status = task["status"]

            return WorkerResult(
                task_id=task_id,
                success=success,
                output_paths=output_files,
                logs=self.get_task_logs(task_id),
                error_message=err_msg,
                execution_time_seconds=exec_time,
            )
        except Exception as exc:
            logger.exception("wait_for_result failed for task %s", task_id)
            with self._lock:
                task["status"] = WorkerTaskStatus.FAILED
                handle.status = WorkerTaskStatus.FAILED
            return WorkerResult(
                task_id=task_id,
                success=False,
                logs=self.get_task_logs(task_id),
                error_message=str(exc),
                execution_time_seconds=time.monotonic() - start_time,
            )

    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        with self._lock:
            task = self._active_tasks.get(task_id)
            if not task:
                raise FileNotFoundError(f"Task {task_id} not found on worker {self._worker_id}")

        destination_dir.mkdir(parents=True, exist_ok=True)
        logs = self.get_task_logs(task_id)
        # Search output files registered
        engine_handle = task.get("engine_handle")
        if engine_handle:
            try:
                engine = self._registry.get_engine(task["engine_id"])
                res = engine.wait_for_result(engine_handle)
                files = getattr(res, "output_files", []) or getattr(res, "generated_files", [])
                if files and Path(files[0]).is_file():
                    src = Path(files[0])
                    dest = destination_dir / src.name
                    shutil.copy2(src, dest)
                    return dest
            except Exception:
                pass
        raise FileNotFoundError(f"No generated output file found for task {task_id}")

    def retry_task(
        self,
        handle: WorkerTaskHandle,
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        if handle.retry_count >= handle.max_retries:
            raise RuntimeError(f"Task {handle.task_id} exceeded maximum retries ({handle.max_retries})")

        handle.retry_count += 1
        handle.status = WorkerTaskStatus.RETRYING
        with self._lock:
            task = self._active_tasks.get(handle.task_id, {})
            settings = task.get("settings", {})
            engine_id = task.get("engine_id", handle.engine_id)

        logger.info("Retrying task %s on worker %s (attempt %s/%s)", handle.task_id, self._worker_id, handle.retry_count, handle.max_retries)
        return self.submit_task(
            task_id=handle.task_id,
            job_id=handle.job_id,
            engine_id=engine_id,
            model_type="",
            settings=settings,
            on_progress=on_progress,
        )

    def shutdown(self) -> None:
        with self._lock:
            self._active_tasks.clear()
            self._initialized = False
            logger.info("LocalGPUWorker %s shut down", self._worker_id)
