"""
Unit and integration tests for the GPU Worker Abstraction Layer.
Validates LocalGPUWorker, RemoteHTTPGPUWorker, RunPodGPUWorker, and GPUWorkerPool.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.engines.base import BaseVideoEngine, EngineCapabilities, EngineProgress, EngineResult
from app.engines.registry import VideoEngineRegistry
from app.models.generation import GenerationJob, GenerationStatus
from app.models.user import User
from app.services.generation_worker import GenerationWorker
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
from app.workers.pool import GPUWorkerPool, get_default_worker_pool, reset_default_worker_pool
from app.workers.remote_worker import RemoteHTTPGPUWorker
from app.workers.runpod_worker import RunPodGPUWorker


class FakeVideoEngine(BaseVideoEngine):
    """Deterministic fake engine for worker testing."""

    def __init__(self, engine_id: str = "wan2gp") -> None:
        self._engine_id = engine_id
        self._capabilities = EngineCapabilities(
            text_to_video=True,
            image_to_video=True,
        )
        self.submitted_tasks: List[Dict[str, Any]] = []

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def display_name(self) -> str:
        return f"Fake {self._engine_id} Engine"

    @property
    def description(self) -> str:
        return "Fake video generation engine for testing"

    @property
    def capabilities(self) -> EngineCapabilities:
        return self._capabilities

    @property
    def is_available(self) -> bool:
        return True

    def initialize(self) -> None:
        pass

    def get_runtime_status(self) -> dict[str, Any]:
        return {
            "engine_id": self._engine_id,
            "available": True,
            "status": "ready",
            "models_available": 1,
            "models_total": 1,
        }

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "model_type": "fake-model",
                "name": "Fake Model",
                "availability": {"available": True},
            }
        ]

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        return dict(generation_settings)

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None] | None = None,
    ) -> Any:
        self.submitted_tasks.append(generation_settings)
        if on_progress:
            on_progress(EngineProgress(progress=50, phase="denoising", status="Processing"))
            on_progress(EngineProgress(progress=100, phase="completed", status="Done"))

        # Create dummy temp video file
        temp_dir = Path(tempfile.mkdtemp())
        dummy_video = temp_dir / "generated_fake.mp4"
        dummy_video.write_bytes(b"FAKE_VIDEO_STREAM")
        return {
            "success": True,
            "output_files": [dummy_video],
            "video_path": dummy_video,
        }

    def wait_for_result(self, handle: Any) -> EngineResult:
        if isinstance(handle, dict) and handle.get("success"):
            return EngineResult(
                success=True,
                output_files=handle.get("output_files", []),
            )
        return EngineResult(success=False, error_message="Engine execution failed")

    def cancel_generation(self, handle: Any) -> None:
        pass

    def shutdown(self) -> None:
        pass


@pytest.fixture(autouse=True)
def clean_pools():
    reset_default_worker_pool()
    yield
    reset_default_worker_pool()


# -------------------------------------------------------------------------
# LocalGPUWorker Tests
# -------------------------------------------------------------------------

def test_local_worker_lifecycle_and_telemetry():
    registry = VideoEngineRegistry()
    fake_engine = FakeVideoEngine("wan2gp")
    registry.register(fake_engine)

    worker = LocalGPUWorker(
        worker_id="local-test-01",
        engine_registry=registry,
        gpu_name="NVIDIA RTX 4090",
        vram_total_mb=24576,
    )
    worker.initialize()

    assert worker.worker_id == "local-test-01"
    assert worker.worker_type == WorkerType.LOCAL
    assert "wan2gp" in worker.supported_engines

    telemetry = worker.get_telemetry()
    assert telemetry.worker_id == "local-test-01"
    assert telemetry.gpu_name == "NVIDIA RTX 4090"
    assert telemetry.vram_total_mb == 24576
    assert telemetry.health_status == WorkerHealthStatus.HEALTHY
    assert worker.send_heartbeat() is True


def test_local_worker_task_submission_and_result():
    registry = VideoEngineRegistry()
    fake_engine = FakeVideoEngine("wan2gp")
    registry.register(fake_engine)

    worker = LocalGPUWorker(worker_id="local-01", engine_registry=registry)
    worker.initialize()

    progress_events = []
    def on_progress(p: WorkerProgress):
        progress_events.append(p)

    handle = worker.submit_task(
        task_id="task-123",
        job_id="job-abc",
        engine_id="wan2gp",
        model_type="fake-model",
        settings={"prompt": "test prompt"},
        on_progress=on_progress,
    )

    assert handle.task_id == "task-123"
    assert handle.status == WorkerTaskStatus.RUNNING
    assert len(progress_events) == 2
    assert progress_events[-1].percent == 100

    result = worker.wait_for_result(handle)
    assert result.success is True
    assert len(result.output_paths) == 1
    assert Path(result.output_paths[0]).is_file()

    logs = worker.get_task_logs("task-123")
    assert len(logs) >= 2

    # Test output retrieval
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = worker.retrieve_output("task-123", Path(tmp_dir))
        assert out_file.is_file()
        assert out_file.read_bytes() == b"FAKE_VIDEO_STREAM"

    worker.shutdown()


def test_local_worker_cancellation_and_retry():
    registry = VideoEngineRegistry()
    fake_engine = FakeVideoEngine("wan2gp")
    registry.register(fake_engine)

    worker = LocalGPUWorker(worker_id="local-02", engine_registry=registry)
    worker.initialize()

    handle = worker.submit_task(
        task_id="task-cancel-01",
        job_id="job-c1",
        engine_id="wan2gp",
        model_type="fake-model",
        settings={"prompt": "cancelled prompt"},
    )

    cancelled = worker.cancel_task("task-cancel-01")
    assert cancelled is True
    assert worker.get_task_status("task-cancel-01") == WorkerTaskStatus.CANCELLED

    # Retry
    retry_handle = worker.retry_task(handle)
    assert retry_handle.task_id == "task-cancel-01"
    assert handle.retry_count == 1


# -------------------------------------------------------------------------
# RemoteHTTPGPUWorker Tests
# -------------------------------------------------------------------------

def test_remote_worker_with_mock_handler():
    temp_dir = tempfile.mkdtemp()
    remote_video_file = Path(temp_dir) / "remote_output.mp4"
    remote_video_file.write_bytes(b"REMOTE_VIDEO_BINARY_DATA")

    def mock_server(method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if path == "/health":
            return {"status": "HEALTHY", "gpu_name": "NVIDIA H100", "vram_total_mb": 81920, "active_tasks": 0}
        elif path == "/heartbeat":
            return {"alive": True}
        elif path == "/tasks" and method == "POST":
            return {"status": "RUNNING", "task_id": payload.get("task_id")}
        elif path == "/tasks/rtask-1":
            return {"status": "COMPLETED", "output_paths": [str(remote_video_file)]}
        elif path.startswith("/tasks/rtask-1/logs"):
            return {"logs": ["Remote denoising step 10/10", "Encoding completed"]}
        elif path == "/tasks/rtask-1/cancel":
            return {"cancelled": True}
        elif path == "/tasks/rtask-1/download":
            return {"data": b"REMOTE_VIDEO_BINARY_DATA"}
        return {}

    worker = RemoteHTTPGPUWorker(
        worker_id="remote-h100-01",
        endpoint_url="http://remote-gpu.internal:8080",
        supported_engines=["wan2gp", "ltx-2"],
        mock_handler=mock_server,
    )
    worker.initialize()

    telemetry = worker.get_telemetry()
    assert telemetry.gpu_name == "NVIDIA H100"
    assert telemetry.vram_total_mb == 81920
    assert telemetry.health_status == WorkerHealthStatus.HEALTHY
    assert worker.send_heartbeat() is True

    handle = worker.submit_task(
        task_id="rtask-1",
        job_id="rjob-1",
        engine_id="ltx-2",
        model_type="",
        settings={"prompt": "remote scene"},
    )
    assert handle.task_id == "rtask-1"

    result = worker.wait_for_result(handle)
    assert result.success is True
    assert result.output_paths == [str(remote_video_file)]

    logs = worker.get_task_logs("rtask-1")
    assert any("Encoding completed" in log for log in logs)

    with tempfile.TemporaryDirectory() as dl_dir:
        downloaded = worker.retrieve_output("rtask-1", Path(dl_dir))
        assert downloaded.is_file()
        assert downloaded.read_bytes() == b"REMOTE_VIDEO_BINARY_DATA"

    worker.shutdown()


# -------------------------------------------------------------------------
# RunPodGPUWorker Tests
# -------------------------------------------------------------------------

def test_runpod_worker_execution():
    def mock_runpod_api(method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if path == "/health":
            return {"alive": True, "status": "HEALTHY"}
        elif path == "/run":
            return {"id": "rp-job-9999"}
        elif path == "/status/rp-job-9999":
            return {
                "status": "COMPLETED",
                "output": {
                    "output_files": ["https://s3.amazonaws.com/bucket/video.mp4"],
                },
            }
        elif path == "/download/rp-task-1":
            return {"data": b"RUNPOD_CLOUD_VIDEO"}
        elif path == "/cancel/rp-job-9999":
            return {"status": "CANCELLED"}
        return {}

    worker = RunPodGPUWorker(
        worker_id="runpod-serverless-01",
        endpoint_id="wan2gp-endpoint",
        mock_handler=mock_runpod_api,
    )
    worker.initialize()

    telemetry = worker.get_telemetry()
    assert telemetry.worker_type == WorkerType.RUNPOD
    assert telemetry.health_status == WorkerHealthStatus.HEALTHY

    handle = worker.submit_task(
        task_id="rp-task-1",
        job_id="job-rp-1",
        engine_id="wan2gp",
        model_type="wan2gp-t2v",
        settings={"prompt": "cloud render"},
    )
    assert handle.task_id == "rp-task-1"
    assert handle.raw_handle == "rp-job-9999"

    result = worker.wait_for_result(handle)
    assert result.success is True
    assert result.output_paths == ["https://s3.amazonaws.com/bucket/video.mp4"]

    with tempfile.TemporaryDirectory() as dl_dir:
        out = worker.retrieve_output("rp-task-1", Path(dl_dir))
        assert out.is_file()
        assert out.read_bytes() == b"RUNPOD_CLOUD_VIDEO"

    worker.shutdown()


# -------------------------------------------------------------------------
# GPUWorkerPool Multi-Worker Routing & Failover Tests
# -------------------------------------------------------------------------

def test_worker_pool_routing_and_failover():
    pool = GPUWorkerPool()

    # Worker 1: Local worker (supports wan2gp)
    reg_local = VideoEngineRegistry()
    reg_local.register(FakeVideoEngine("wan2gp"))
    local_worker = LocalGPUWorker("local-worker-1", engine_registry=reg_local)
    local_worker.initialize()
    pool.register_worker(local_worker)

    # Worker 2: RunPod worker (supports ltx-2 and minimax-h3)
    def mock_rp(method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if path == "/run":
            return {"id": "rp-123"}
        elif path.startswith("/status/"):
            return {"status": "COMPLETED", "output": {"output_files": ["video.mp4"]}}
        elif path.startswith("/download/"):
            return {"data": b"CLOUD_VIDEO"}
        return {"alive": True, "status": "HEALTHY"}

    rp_worker = RunPodGPUWorker(
        worker_id="runpod-worker-1",
        supported_engines=["ltx-2", "minimax-h3"],
        mock_handler=mock_rp,
    )
    pool.register_worker(rp_worker)

    assert len(pool.list_workers()) == 2
    telemetries = pool.get_all_telemetry()
    assert len(telemetries) == 2

    # Route wan2gp -> selects local_worker
    selected_wan = pool.select_worker("wan2gp")
    assert selected_wan.worker_id == "local-worker-1"

    # Route ltx-2 -> selects rp_worker
    selected_ltx = pool.select_worker("ltx-2")
    assert selected_ltx.worker_id == "runpod-worker-1"

    # Dispatch via pool
    handle = pool.dispatch_job(
        task_id="pool-task-1",
        job_id="job-p1",
        engine_id="wan2gp",
        model_type="fake-model",
        settings={"prompt": "pool dispatched"},
    )
    assert handle.worker_id == "local-worker-1"
    res = pool.wait_for_result(handle)
    assert res.success is True

    # Test unknown engine raises error
    with pytest.raises(RuntimeError, match="No GPU workers registered"):
        pool.select_worker("unregistered-engine")

    pool.shutdown_all()


# -------------------------------------------------------------------------
# GenerationWorker Database Queue with GPU Worker Pool
# -------------------------------------------------------------------------

def test_generation_worker_integration_with_gpu_worker_pool():
    temp_dir = tempfile.mkdtemp()
    db_engine = create_engine(f"sqlite:///{Path(temp_dir) / 'test.db'}")
    Base.metadata.create_all(db_engine)
    session_factory = sessionmaker(bind=db_engine)

    # Set up worker pool with fake engine
    pool = GPUWorkerPool()
    reg = VideoEngineRegistry()
    fake_engine = FakeVideoEngine("wan2gp")
    reg.register(fake_engine)
    local_worker = LocalGPUWorker("local-test", engine_registry=reg)
    local_worker.initialize()
    pool.register_worker(local_worker)

    storage_root = Path(temp_dir) / "storage"
    worker = GenerationWorker(
        session_factory=session_factory,
        storage_root=storage_root,
        worker_pool=pool,
        poll_seconds=0.1,
    )

    # Insert a job
    db = session_factory()
    job = GenerationJob(
        id="job-worker-pool-test",
        user_id="user-123",
        status=GenerationStatus.QUEUED,
        prompt="A robotic future",
        model_type="fake-model",
        generation_settings={"engine_id": "wan2gp", "prompt": "A robotic future"},
    )
    db.add(job)
    db.commit()
    db.close()

    # Process job once
    processed = worker.run_once()
    assert processed is True

    # Verify job status in DB
    db = session_factory()
    refreshed_job = db.get(GenerationJob, "job-worker-pool-test")
    assert refreshed_job.status == GenerationStatus.COMPLETED
    assert refreshed_job.progress == 100
    assert refreshed_job.output_path is not None
    assert (storage_root / refreshed_job.output_path).is_file()
    db.close()

    worker.stop()
    shutil.rmtree(temp_dir, ignore_errors=True)
