"""
Remote HTTP GPU Worker implementation.
Communicates with dedicated private GPU servers or remote clusters via REST API.
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


class RemoteHTTPGPUWorker(BaseGPUWorker):
    """
    GPU Worker that communicates with an external or private GPU server over HTTP/REST.
    """

    def __init__(
        self,
        worker_id: str,
        endpoint_url: str,
        api_key: Optional[str] = None,
        supported_engines: Optional[List[str]] = None,
        timeout_seconds: float = 30.0,
        mock_handler: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self._worker_id = worker_id
        self._endpoint_url = endpoint_url.rstrip("/")
        self._api_key = api_key
        self._supported_engines = supported_engines or ["wan2gp", "ltx-2", "ltx-video", "minimax-h3"]
        self._timeout_seconds = timeout_seconds
        self._mock_handler = mock_handler
        self._last_heartbeat = datetime.utcnow()
        self._cached_telemetry: Optional[WorkerTelemetry] = None
        self._active_handles: Dict[str, WorkerTaskHandle] = {}
        self._task_logs: Dict[str, List[str]] = {}
        self._lock = threading.RLock()

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.REMOTE_HTTP

    @property
    def supported_engines(self) -> List[str]:
        return list(self._supported_engines)

    def initialize(self) -> None:
        """Ping remote worker and load telemetry."""
        logger.info("Initializing RemoteHTTPGPUWorker %s at %s", self._worker_id, self._endpoint_url)
        self.send_heartbeat()

    def _http_request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send HTTP request or execute mock handler if provided."""
        if self._mock_handler:
            return self._mock_handler(method, path, payload or {})

        url = f"{self._endpoint_url}{path}"
        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self._timeout_seconds) as response:
            res_data = response.read().decode("utf-8")
            return json.loads(res_data) if res_data else {}

    def get_telemetry(self) -> WorkerTelemetry:
        try:
            res = self._http_request("GET", "/health")
            health_str = res.get("status", "HEALTHY").upper()
            health = WorkerHealthStatus(health_str) if health_str in WorkerHealthStatus._value2member_map_ else WorkerHealthStatus.HEALTHY
            telemetry = WorkerTelemetry(
                worker_id=self._worker_id,
                worker_type=self.worker_type,
                health_status=health,
                gpu_name=res.get("gpu_name", "Remote GPU Device"),
                vram_total_mb=res.get("vram_total_mb", 24576),
                vram_used_mb=res.get("vram_used_mb", 0),
                active_tasks=res.get("active_tasks", 0),
                last_heartbeat=datetime.utcnow(),
                supported_engines=res.get("supported_engines", self._supported_engines),
            )
            self._cached_telemetry = telemetry
            self._last_heartbeat = datetime.utcnow()
            return telemetry
        except Exception as e:
            logger.warning("Remote worker %s telemetry check failed: %s", self._worker_id, e)
            return WorkerTelemetry(
                worker_id=self._worker_id,
                worker_type=self.worker_type,
                health_status=WorkerHealthStatus.UNAVAILABLE,
                last_heartbeat=self._last_heartbeat,
                supported_engines=self._supported_engines,
            )

    def send_heartbeat(self) -> bool:
        try:
            res = self._http_request("GET", "/heartbeat")
            with self._lock:
                self._last_heartbeat = datetime.utcnow()
            return res.get("alive", True)
        except Exception as exc:
            logger.warning("Worker %s heartbeat failure: %s", self._worker_id, exc)
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
            self._task_logs[task_id] = [f"[{datetime.utcnow().isoformat()}] Task submitted to {self._endpoint_url}"]

        payload = {
            "task_id": task_id,
            "job_id": job_id,
            "engine_id": engine_id,
            "model_type": model_type,
            "settings": settings,
        }
        try:
            res = self._http_request("POST", "/tasks", payload)
            handle.status = WorkerTaskStatus(res.get("status", "RUNNING"))
            with self._lock:
                self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] Remote worker accepted task (status={handle.status})")
        except Exception as exc:
            logger.exception("Remote worker submission error for task %s", task_id)
            handle.status = WorkerTaskStatus.FAILED
            handle.error_message = str(exc)
            with self._lock:
                self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] Submission failed: {exc}")

        return handle

    def get_task_status(self, task_id: str) -> WorkerTaskStatus:
        try:
            res = self._http_request("GET", f"/tasks/{task_id}/status")
            status_str = res.get("status", "FAILED")
            status = WorkerTaskStatus(status_str) if status_str in WorkerTaskStatus._value2member_map_ else WorkerTaskStatus.FAILED
            with self._lock:
                if task_id in self._active_handles:
                    self._active_handles[task_id].status = status
            return status
        except Exception as exc:
            logger.warning("Error fetching task status %s: %s", task_id, exc)
            return WorkerTaskStatus.FAILED

    def get_task_logs(self, task_id: str, tail_lines: int = 100) -> List[str]:
        try:
            res = self._http_request("GET", f"/tasks/{task_id}/logs?tail={tail_lines}")
            remote_logs = res.get("logs", [])
            with self._lock:
                local_logs = self._task_logs.get(task_id, [])
                all_logs = local_logs + remote_logs
                return all_logs[-tail_lines:]
        except Exception:
            with self._lock:
                return self._task_logs.get(task_id, [])[-tail_lines:]

    def cancel_task(self, task_id: str) -> bool:
        try:
            res = self._http_request("POST", f"/tasks/{task_id}/cancel")
            with self._lock:
                if task_id in self._active_handles:
                    self._active_handles[task_id].status = WorkerTaskStatus.CANCELLED
                if task_id in self._task_logs:
                    self._task_logs[task_id].append(f"[{datetime.utcnow().isoformat()}] Task cancelled on remote worker")
            return res.get("cancelled", True)
        except Exception as e:
            logger.warning("Failed to cancel task %s on remote worker: %s", task_id, e)
            return False

    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        task_id = handle.task_id
        start_time = time.monotonic()
        poll_interval = 0.5

        while True:
            try:
                res = self._http_request("GET", f"/tasks/{task_id}")
                status = res.get("status", "RUNNING")
                if status == WorkerTaskStatus.COMPLETED.value:
                    handle.status = WorkerTaskStatus.COMPLETED
                    return WorkerResult(
                        task_id=task_id,
                        success=True,
                        output_paths=res.get("output_paths", []),
                        logs=res.get("logs", self.get_task_logs(task_id)),
                        execution_time_seconds=time.monotonic() - start_time,
                    )
                elif status in (WorkerTaskStatus.FAILED.value, WorkerTaskStatus.CANCELLED.value):
                    handle.status = WorkerTaskStatus(status)
                    return WorkerResult(
                        task_id=task_id,
                        success=False,
                        logs=res.get("logs", self.get_task_logs(task_id)),
                        error_message=res.get("error_message", "Remote generation failed"),
                        execution_time_seconds=time.monotonic() - start_time,
                    )
            except Exception as exc:
                logger.warning("Polling error for remote task %s: %s", task_id, exc)

            time.sleep(poll_interval)

    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        dest_path = destination_dir / f"{task_id}_output.mp4"

        if self._mock_handler:
            res = self._http_request("GET", f"/tasks/{task_id}/download")
            data = res.get("data", b"dummy video content")
            if isinstance(data, str):
                dest_path.write_text(data, encoding="utf-8")
            else:
                dest_path.write_bytes(data)
            return dest_path

        url = f"{self._endpoint_url}/tasks/{task_id}/download"
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60.0) as resp, open(dest_path, "wb") as f:
            f.write(resp.read())
        return dest_path

    def retry_task(
        self,
        handle: WorkerTaskHandle,
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        if handle.retry_count >= handle.max_retries:
            raise RuntimeError(f"Task {handle.task_id} exceeded maximum retries ({handle.max_retries})")

        handle.retry_count += 1
        handle.status = WorkerTaskStatus.RETRYING
        logger.info("Retrying remote task %s on %s (attempt %s/%s)", handle.task_id, self._worker_id, handle.retry_count, handle.max_retries)
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
            logger.info("RemoteHTTPGPUWorker %s shut down", self._worker_id)
