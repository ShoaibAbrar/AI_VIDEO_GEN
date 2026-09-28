"""
GPU Worker Pool Manager.
Orchestrates worker registration, health checks, heartbeats, routing, and automatic failover/retry.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.core.logging_config import logger
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
from app.workers.local_worker import LocalGPUWorker


class GPUWorkerPool:
    """
    Central dispatch and lifecycle management for GPU workers.
    Provides load distribution, health check monitoring, and automatic failover.
    """

    def __init__(self, heartbeat_timeout_seconds: float = 60.0) -> None:
        self._workers: Dict[str, BaseGPUWorker] = {}
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._lock = threading.RLock()
        self._active_tasks: Dict[str, Dict[str, Any]] = {}

    def register_worker(self, worker: BaseGPUWorker) -> None:
        """Register a GPU worker in the pool."""
        with self._lock:
            self._workers[worker.worker_id] = worker
            logger.info(
                "Registered GPU worker '%s' (type=%s, engines=%s)",
                worker.worker_id,
                worker.worker_type.value,
                worker.supported_engines,
            )

    def unregister_worker(self, worker_id: str) -> Optional[BaseGPUWorker]:
        """Remove a worker from the pool."""
        with self._lock:
            return self._workers.pop(worker_id, None)

    def get_worker(self, worker_id: str) -> Optional[BaseGPUWorker]:
        """Look up worker by ID."""
        with self._lock:
            return self._workers.get(worker_id)

    def list_workers(self) -> List[BaseGPUWorker]:
        """List all registered workers."""
        with self._lock:
            return list(self._workers.values())

    def get_all_telemetry(self) -> List[WorkerTelemetry]:
        """Collect telemetry from all registered workers."""
        with self._lock:
            workers = list(self._workers.values())

        telemetries: List[WorkerTelemetry] = []
        for worker in workers:
            try:
                telemetries.append(worker.get_telemetry())
            except Exception as e:
                logger.warning("Failed to get telemetry from worker %s: %s", worker.worker_id, e)
                telemetries.append(
                    WorkerTelemetry(
                        worker_id=worker.worker_id,
                        worker_type=worker.worker_type,
                        health_status=WorkerHealthStatus.UNAVAILABLE,
                        supported_engines=worker.supported_engines,
                    )
                )
        return telemetries

    def select_worker(self, engine_id: str, preferred_type: Optional[WorkerType] = None) -> BaseGPUWorker:
        """
        Select the best available healthy worker capable of executing the specified engine.
        Prioritizes:
        1. Preferred WorkerType (if specified and healthy)
        2. Healthy workers supporting engine_id with the lowest active task load
        3. Degraded workers supporting engine_id
        """
        with self._lock:
            candidates = [w for w in self._workers.values() if engine_id in w.supported_engines]

        if not candidates:
            raise RuntimeError(f"No GPU workers registered that support engine '{engine_id}'")

        # Evaluate candidate health & load
        ranked: List[tuple[int, int, BaseGPUWorker]] = []
        for worker in candidates:
            try:
                telemetry = worker.get_telemetry()
                health_score = 0
                if telemetry.health_status == WorkerHealthStatus.HEALTHY:
                    health_score = 0
                elif telemetry.health_status == WorkerHealthStatus.BUSY:
                    health_score = 1
                elif telemetry.health_status == WorkerHealthStatus.DEGRADED:
                    health_score = 2
                else:
                    health_score = 99  # UNAVAILABLE

                # Preferred type bonus
                if preferred_type and worker.worker_type == preferred_type:
                    health_score -= 1

                ranked.append((health_score, telemetry.active_tasks, worker))
            except Exception:
                ranked.append((99, 999, worker))

        ranked.sort(key=lambda x: (x[0], x[1]))
        best_score, _, best_worker = ranked[0]

        if best_score >= 99:
            logger.warning("All workers supporting '%s' appear degraded or unavailable. Attempting best candidate: %s", engine_id, best_worker.worker_id)

        return best_worker

    def dispatch_job(
        self,
        task_id: str,
        job_id: str,
        engine_id: str,
        model_type: str,
        settings: Dict[str, Any],
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
        preferred_worker_type: Optional[WorkerType] = None,
    ) -> WorkerTaskHandle:
        """
        Select a worker, submit task, and track task state.
        If initial submission fails, attempts failover to secondary worker.
        """
        worker = self.select_worker(engine_id, preferred_worker_type)
        logger.info("Dispatching task %s (engine=%s) to worker %s (%s)", task_id, engine_id, worker.worker_id, worker.worker_type)

        try:
            handle = worker.submit_task(
                task_id=task_id,
                job_id=job_id,
                engine_id=engine_id,
                model_type=model_type,
                settings=settings,
                on_progress=on_progress,
            )
            with self._lock:
                self._active_tasks[task_id] = {
                    "worker_id": worker.worker_id,
                    "handle": handle,
                    "engine_id": engine_id,
                    "settings": settings,
                    "model_type": model_type,
                    "job_id": job_id,
                    "on_progress": on_progress,
                }
            return handle
        except Exception as exc:
            logger.warning("Worker %s failed to accept task %s: %s. Attempting failover.", worker.worker_id, task_id, exc)
            # Find alternative worker
            with self._lock:
                alternatives = [
                    w for w in self._workers.values()
                    if engine_id in w.supported_engines and w.worker_id != worker.worker_id
                ]
            if not alternatives:
                raise RuntimeError(f"Task submission failed on {worker.worker_id} and no fallback workers available: {exc}")

            fallback_worker = alternatives[0]
            logger.info("Failover: Dispatching task %s to %s", task_id, fallback_worker.worker_id)
            handle = fallback_worker.submit_task(
                task_id=task_id,
                job_id=job_id,
                engine_id=engine_id,
                model_type=model_type,
                settings=settings,
                on_progress=on_progress,
            )
            with self._lock:
                self._active_tasks[task_id] = {
                    "worker_id": fallback_worker.worker_id,
                    "handle": handle,
                    "engine_id": engine_id,
                    "settings": settings,
                    "model_type": model_type,
                    "job_id": job_id,
                    "on_progress": on_progress,
                }
            return handle

    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        """Wait for worker result and handle retry if necessary."""
        worker = self.get_worker(handle.worker_id)
        if not worker:
            return WorkerResult(
                task_id=handle.task_id,
                success=False,
                error_message=f"Worker '{handle.worker_id}' is no longer registered",
            )

        result = worker.wait_for_result(handle)
        return result

    def get_task_logs(self, task_id: str, tail_lines: int = 100) -> List[str]:
        """Fetch logs from the worker executing the task."""
        with self._lock:
            task_info = self._active_tasks.get(task_id)
        if task_info:
            worker = self.get_worker(task_info["worker_id"])
            if worker:
                return worker.get_task_logs(task_id, tail_lines)
        return []

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task on its assigned worker."""
        with self._lock:
            task_info = self._active_tasks.get(task_id)
        if task_info:
            worker = self.get_worker(task_info["worker_id"])
            if worker:
                return worker.cancel_task(task_id)
        return False

    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        """Retrieve output video from the assigned worker."""
        with self._lock:
            task_info = self._active_tasks.get(task_id)
        if not task_info:
            raise FileNotFoundError(f"Task {task_id} not registered in pool")

        worker = self.get_worker(task_info["worker_id"])
        if not worker:
            raise RuntimeError(f"Assigned worker '{task_info['worker_id']}' is not available")

        return worker.retrieve_output(task_id, destination_dir)

    def shutdown_all(self) -> None:
        """Shut down all registered workers."""
        with self._lock:
            workers = list(self._workers.values())
        for worker in workers:
            try:
                worker.shutdown()
            except Exception as e:
                logger.warning("Error shutting down worker %s: %s", worker.worker_id, e)
        with self._lock:
            self._workers.clear()
            self._active_tasks.clear()
            logger.info("GPUWorkerPool shut down completely")


_DEFAULT_WORKER_POOL: Optional[GPUWorkerPool] = None


def get_default_worker_pool() -> GPUWorkerPool:
    """Return singleton default worker pool initialized with LocalGPUWorker."""
    global _DEFAULT_WORKER_POOL
    if _DEFAULT_WORKER_POOL is None:
        pool = GPUWorkerPool()
        local_worker = LocalGPUWorker()
        local_worker.initialize()
        pool.register_worker(local_worker)
        _DEFAULT_WORKER_POOL = pool
    return _DEFAULT_WORKER_POOL


def reset_default_worker_pool() -> None:
    """Reset the singleton worker pool (useful for tests)."""
    global _DEFAULT_WORKER_POOL
    if _DEFAULT_WORKER_POOL is not None:
        _DEFAULT_WORKER_POOL.shutdown_all()
        _DEFAULT_WORKER_POOL = None
