"""
RunPod GPU Worker implementation.
Communicates with RunPod Serverless / Pod API for on-demand cloud GPU generation.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import urllib.request
import urllib.error

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


class RunPodGPUWorker(BaseGPUWorker):
    """
    GPU Worker managing execution via RunPod Serverless / Pod API.
    """

    def __init__(
        self,
        worker_id: str = "runpod-serverless",
        api_key: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        supported_engines: Optional[List[str]] = None,
        gpu_name: str = "RunPod Cloud GPU (A100 / RTX 4090)",
        vram_total_mb: int = 24576,
        mock_handler: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self._worker_id = worker_id
        self._api_key = api_key or "mock-runpod-key"
        self._endpoint_id = endpoint_id or "ep-mock-wan2gp"
        self._supported_engines = supported_engines or ["wan2gp", "ltx-2", "ltx-video", "minimax-h3"]
        self._gpu_name = gpu_name
        self._vram_total_mb = vram_total_mb
        self._mock_handler = mock_handler
        self._last_heartbeat = datetime.utcnow()
        self._active_handles: Dict[str, WorkerTaskHandle] = {}
        self._runpod_job_ids: Dict[str, str] = {}  # task_id -> runpod_job_id
        self._task_logs: Dict[str, List[str]] = {}
        self._task_outputs: Dict[str, bytes] = {}
        self._lock = threading.RLock()

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.RUNPOD

    @property
    def supported_engines(self) -> List[str]:
        return list(self._supported_engines)

    def initialize(self) -> None:
        logger.info("Initializing RunPod worker %s (endpoint: %s)", self._worker_id, self._endpoint_id)
        self.send_heartbeat()

    def _api_call(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._mock_handler:
            return self._mock_handler(method, path, payload or {})

        url = f"https://api.runpod.ai/v2/{self._endpoint_id}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_telemetry(self) -> WorkerTelemetry:
        with self._lock:
            active_count = len(self._active_handles)
            return WorkerTelemetry(
                worker_id=self._worker_id,
                worker_type=self.worker_type,
                health_status=WorkerHealthStatus.HEALTHY if self.send_heartbeat() else WorkerHealthStatus.UNAVAILABLE,
                gpu_name=self._gpu_name,
                vram_total_mb=self._vram_total_mb,
                vram_used_mb=0,
                active_tasks=active_count,
                last_heartbeat=self._last_heartbeat,
                supported_engines=self._supported_engines,
            )

    def send_heartbeat(self) -> bool:
        try:
            if self._mock_handler:
                res = self._mock_handler("GET", "/health", {})
                alive = res.get("alive", True)
            else:
                res = self._api_call("GET", "/health")
                alive = res.get("status") in ("IDLE", "RUNNING", "HEALTHY")
            with self._lock:
                self._last_heartbeat = datetime.utcnow()
            return alive
        except Exception:
            return False

    def submit_task(
        self,
        task_id: str,
        job_id: str,
        engine_id: str,
        model_type: str,
        settings: Dict[str, Any],
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        handle = WorkerTaskHandle(
            task_id=task_id,
            worker_id=self._worker_id,
            job_id=job_id,
            engine_id=engine_id,
            status=WorkerTaskStatus.SUBMITTED,
        )
        with self._lock:
            self._active_handles[task_id] = handle
            self._task_logs[task_id] = [f"[{datetime.utcnow().isoformat()}] Submitting to RunPod endpoint {self._endpoint_id}"]

        runpod_input = {
            "input": {
                "task_id": task_id,
                "job_id": job_id,
                "engine_id": engine_id,
                "model_type": model_type,
                **settings,
            }
        }
        try:
            res = self._api_call("POST", "/run", runpod_input)
            runpod_id = res.get("id", f"rp-{task_id}")
            handle.raw_handle = runpod_id
            with self._lock:
                self._runpod_job_ids[task_id] = runpod_id
                handle.status = WorkerTaskStatus.RUNNING
                self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] RunPod job created: {runpod_id}")
        except Exception as exc:
            logger.exception("RunPod job submission error for task %s", task_id)
            handle.status = WorkerTaskStatus.FAILED
            handle.error_message = str(exc)
            with self._lock:
                self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] RunPod submission failed: {exc}")

        return handle

    def get_task_status(self, task_id: str) -> WorkerTaskStatus:
        with self._lock:
            runpod_id = self._runpod_job_ids.get(task_id)
            handle = self._active_handles.get(task_id)

        if not runpod_id:
            return WorkerTaskStatus.FAILED

        try:
            res = self._api_call("GET", f"/status/{runpod_id}")
            rp_status = res.get("status", "IN_PROGRESS").upper()
            status_map = {
                "IN_QUEUE": WorkerTaskStatus.QUEUED,
                "IN_PROGRESS": WorkerTaskStatus.RUNNING,
                "COMPLETED": WorkerTaskStatus.COMPLETED,
                "FAILED": WorkerTaskStatus.FAILED,
                "CANCELLED": WorkerTaskStatus.CANCELLED,
                "TIMED_OUT": WorkerTaskStatus.FAILED,
            }
            status = status_map.get(rp_status, WorkerTaskStatus.RUNNING)
            if handle:
                handle.status = status
            return status
        except Exception as e:
            logger.warning("Failed to fetch RunPod status for %s: %s", runpod_id, e)
            return WorkerTaskStatus.FAILED

    def get_task_logs(self, task_id: str, tail_lines: int = 100) -> List[str]:
        with self._lock:
            return self._task_logs.get(task_id, [])[-tail_lines:]

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            runpod_id = self._runpod_job_ids.get(task_id)
            handle = self._active_handles.get(task_id)

        if not runpod_id:
            return False

        try:
            res = self._api_call("POST", f"/cancel/{runpod_id}")
            with self._lock:
                if handle:
                    handle.status = WorkerTaskStatus.CANCELLED
                self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] RunPod job {runpod_id} cancelled")
            return res.get("status") in ("CANCELLED", "SUCCESS", True)
        except Exception as e:
            logger.warning("RunPod cancellation error for %s: %s", runpod_id, e)
            return False

    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        task_id = handle.task_id
        start_time = time.monotonic()
        runpod_id = handle.raw_handle or self._runpod_job_ids.get(task_id)

        if not runpod_id:
            return WorkerResult(task_id=task_id, success=False, error_message="No RunPod Job ID found")

        while True:
            try:
                res = self._api_call("GET", f"/status/{runpod_id}")
                rp_status = res.get("status", "IN_PROGRESS").upper()

                if rp_status == "COMPLETED":
                    handle.status = WorkerTaskStatus.COMPLETED
                    output_data = res.get("output", {})
                    output_files = output_data.get("output_files", [])
                    if "video_base64" in output_data:
                        import base64
                        with self._lock:
                            self._task_outputs[task_id] = base64.b64decode(output_data["video_base64"])

                    return WorkerResult(
                        task_id=task_id,
                        success=True,
                        output_paths=output_files,
                        logs=self.get_task_logs(task_id),
                        execution_time_seconds=time.monotonic() - start_time,
                    )
                elif rp_status in ("FAILED", "TIMED_OUT", "CANCELLED"):
                    handle.status = WorkerTaskStatus.FAILED if rp_status != "CANCELLED" else WorkerTaskStatus.CANCELLED
                    return WorkerResult(
                        task_id=task_id,
                        success=False,
                        logs=self.get_task_logs(task_id),
                        error_message=res.get("error", f"RunPod execution {rp_status}"),
                        execution_time_seconds=time.monotonic() - start_time,
                    )
            except Exception as exc:
                logger.warning("Polling error for RunPod task %s: %s", task_id, exc)

            time.sleep(0.5)

    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        dest_path = destination_dir / f"{task_id}_runpod_output.mp4"

        with self._lock:
            if task_id in self._task_outputs:
                dest_path.write_bytes(self._task_outputs[task_id])
                return dest_path

        # If mock handler provided
        if self._mock_handler:
            res = self._mock_handler("GET", f"/download/{task_id}", {})
            dest_path.write_bytes(res.get("data", b"mock runpod video"))
            return dest_path

        raise FileNotFoundError(f"No output payload available for RunPod task {task_id}")

    def retry_task(
        self,
        handle: WorkerTaskHandle,
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        if handle.retry_count >= handle.max_retries:
            raise RuntimeError(f"RunPod task {handle.task_id} exceeded maximum retries ({handle.max_retries})")

        handle.retry_count += 1
        handle.status = WorkerTaskStatus.RETRYING
        logger.info("Retrying RunPod task %s (attempt %s/%s)", handle.task_id, handle.retry_count, handle.max_retries)
        return self.submit_task(
            task_id=handle.task_id,
            job_id=handle.job_id,
            engine_id=handle.engine_id,
            model_type="",
            settings={},
            on_progress=on_progress,
        )

    def shutdown(self) -> None:
        with self._lock:
            self._active_handles.clear()
            logger.info("RunPod worker %s shut down", self._worker_id)
