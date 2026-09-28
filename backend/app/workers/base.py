"""
Base GPU Worker Abstraction & Interface Contracts.
Enables transparent job execution across Local GPUs, Remote Private Servers, RunPod, and Cloud GPUs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class WorkerType(str, Enum):
    """Execution environment for the GPU worker."""
    LOCAL = "LOCAL"
    REMOTE_HTTP = "REMOTE_HTTP"
    RUNPOD = "RUNPOD"
    CLOUD_GPU = "CLOUD_GPU"
    PRIVATE_CLUSTER = "PRIVATE_CLUSTER"


class WorkerHealthStatus(str, Enum):
    """Health state of a GPU worker."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    BUSY = "BUSY"


class WorkerTaskStatus(str, Enum):
    """Lifecycle state of a task assigned to a GPU worker."""
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"


@dataclass
class WorkerProgress:
    """Normalized progress telemetry emitted by a GPU worker."""
    task_id: str
    percent: float = 0.0
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    phase: Optional[str] = None
    status_text: Optional[str] = None
    heartbeat_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkerResult:
    """Execution output delivered by a GPU worker upon task completion."""
    task_id: str
    success: bool
    output_paths: List[str] = field(default_factory=list)
    output_bytes: Optional[bytes] = None
    logs: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0


@dataclass
class WorkerTelemetry:
    """Hardware and operational metrics reported by a GPU worker."""
    worker_id: str
    worker_type: WorkerType
    health_status: WorkerHealthStatus
    gpu_name: str = "Unknown GPU"
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    active_tasks: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    supported_engines: List[str] = field(default_factory=list)


@dataclass
class WorkerTaskHandle:
    """Opaque handle tracking an in-flight execution on a GPU worker."""
    task_id: str
    worker_id: str
    job_id: str
    engine_id: str
    status: WorkerTaskStatus = WorkerTaskStatus.SUBMITTED
    logs: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    raw_handle: Any = None


class BaseGPUWorker(ABC):
    """
    Abstract contract for GPU execution workers.
    Provides uniform interface for job dispatch, heartbeat monitoring,
    log collection, output retrieval, and retry handling.
    """

    @property
    @abstractmethod
    def worker_id(self) -> str:
        """Unique identifier for this worker instance."""
        raise NotImplementedError

    @property
    @abstractmethod
    def worker_type(self) -> WorkerType:
        """Provider/Deployment type of this worker."""
        raise NotImplementedError

    @property
    @abstractmethod
    def supported_engines(self) -> List[str]:
        """List of engine IDs supported by this worker (e.g. ['wan2gp', 'ltx-2', 'ltx-video'])."""
        raise NotImplementedError

    @abstractmethod
    def initialize(self) -> None:
        """Initialize worker session, connection pools, or local device resources."""
        raise NotImplementedError

    @abstractmethod
    def get_telemetry(self) -> WorkerTelemetry:
        """Report worker operational health, VRAM utilization, and heartbeat."""
        raise NotImplementedError

    @abstractmethod
    def send_heartbeat(self) -> bool:
        """Verify worker connectivity and record heartbeat timestamp."""
        raise NotImplementedError

    @abstractmethod
    def submit_task(
        self,
        task_id: str,
        job_id: str,
        engine_id: str,
        model_type: str,
        settings: Dict[str, Any],
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        """Submit a generation task to the GPU worker for execution."""
        raise NotImplementedError

    @abstractmethod
    def get_task_status(self, task_id: str) -> WorkerTaskStatus:
        """Query current execution state for an assigned task."""
        raise NotImplementedError

    @abstractmethod
    def get_task_logs(self, task_id: str, tail_lines: int = 100) -> List[str]:
        """Retrieve execution logs for diagnostics and debugging."""
        raise NotImplementedError

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """Request cancellation of an active task on this worker."""
        raise NotImplementedError

    @abstractmethod
    def wait_for_result(self, handle: WorkerTaskHandle) -> WorkerResult:
        """Block or poll until the worker completes the task and delivers results."""
        raise NotImplementedError

    @abstractmethod
    def retrieve_output(self, task_id: str, destination_dir: Path) -> Path:
        """Fetch output video file from the worker to the platform local storage."""
        raise NotImplementedError

    @abstractmethod
    def retry_task(
        self,
        handle: WorkerTaskHandle,
        on_progress: Optional[Callable[[WorkerProgress], None]] = None,
    ) -> WorkerTaskHandle:
        """Retry a failed task if retry limit has not been exceeded."""
        raise NotImplementedError

    @abstractmethod
    def shutdown(self) -> None:
        """Gracefully terminate worker connections and clean up resources."""
        raise NotImplementedError
