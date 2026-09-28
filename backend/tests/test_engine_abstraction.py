"""Comprehensive unit and integration tests for the Video Engine Abstraction layer."""

from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy.orm import sessionmaker

from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)
from app.engines.registry import VideoEngineRegistry, get_engine_registry
from app.engines.stubs import (
    LTX2Adapter,
    LTXVideoAdapter,
    MiniMaxH3DirectorAdapter,
    MiniMaxH3LongVideoAdapter,
)
from app.engines.wan2gp_adapter import Wan2GPAdapter
from app.models.generation import GenerationJob, GenerationStatus
from app.models.user import User
from app.services.generation_worker import GenerationWorker
from app.services.wan2gp_service import Wan2GPProgress


class MockWan2GPService:
    """Mock Wan2GPService simulating runtime behaviors."""

    def __init__(self, output_path=None, available=True):
        self.output_path = Path(output_path) if output_path else None
        self.available = available
        self.submitted_settings = []
        self.initialized = False
        self.shutdown_called = False

    def initialize(self):
        self.initialized = True

    def get_runtime_status(self):
        return {
            "available": self.available,
            "initialized": self.initialized,
            "status": "ready" if self.available else "unavailable",
            "models_available": 1 if self.available else 0,
            "models_total": 2,
        }

    def list_models(self):
        return [
            {
                "model_type": "wan-t2v-1.3b",
                "name": "Wan2.1 1.3B",
                "availability": {"available": self.available},
            }
        ]

    def validate_generation(self, settings):
        if settings.get("model_type") != "wan-t2v-1.3b":
            raise ValueError("Unsupported model")
        return {**settings, "validated": True}

    def submit_generation(self, settings, on_progress):
        self.submitted_settings.append(settings)
        on_progress(Wan2GPProgress(progress=50, current_step=5, total_steps=10, phase="diffusion", status="Generating"))
        return SimpleNamespace(task_id="raw-task-123")

    def wait_for_result(self, raw_handle):
        if self.output_path:
            return SimpleNamespace(success=True, generated_files=[str(self.output_path)], artifacts=(), errors=())
        return SimpleNamespace(success=False, generated_files=[], artifacts=(), errors=("Mock engine failure",))

    def cancel_generation(self, raw_handle):
        pass

    def shutdown(self):
        self.shutdown_called = True


def test_engine_capabilities_serialization():
    caps = EngineCapabilities(
        text_to_video=True,
        image_to_video=True,
        native_long_video=False,
    )
    d = caps.to_dict()
    assert d["text_to_video"] is True
    assert d["image_to_video"] is True
    assert d["native_long_video"] is False
    assert isinstance(d, dict)


def test_video_engine_registry_lifecycle():
    registry = VideoEngineRegistry()
    mock_wan = MockWan2GPService()
    wan_adapter = Wan2GPAdapter(mock_wan)
    ltx_stub = LTXVideoAdapter()

    # Registration
    registry.register(wan_adapter, default=True)
    registry.register(ltx_stub)

    assert registry.get_engine().engine_id == "wan2gp"
    assert registry.get_engine("wan2gp").engine_id == "wan2gp"
    assert registry.get_engine("LTX-VIDEO").engine_id == "ltx-video"

    # Engine list
    engines = registry.list_engines()
    assert len(engines) == 2
    ids = [e["engine_id"] for e in engines]
    assert "wan2gp" in ids
    assert "ltx-video" in ids

    # Model resolution
    resolved = registry.resolve_engine_for_model("wan-t2v-1.3b")
    assert resolved.engine_id == "wan2gp"

    # Unknown engine lookup
    with pytest.raises(ValueError, match="Unknown video engine"):
        registry.get_engine("non-existent-engine")

    # Unregister
    registry.unregister("wan2gp")
    assert registry.get_engine().engine_id == "ltx-video"


def test_wan2gp_adapter_delegation(tmp_path):
    video_file = tmp_path / "result.mp4"
    video_file.write_bytes(b"fake video stream")
    mock_service = MockWan2GPService(output_path=video_file)
    adapter = Wan2GPAdapter(mock_service)

    assert adapter.engine_id == "wan2gp"
    assert adapter.is_available is True
    assert adapter.capabilities.text_to_video is True
    assert adapter.capabilities.image_to_video is True

    # Models list tagging
    models = adapter.list_models()
    assert len(models) == 1
    assert models[0]["engine_id"] == "wan2gp"

    # Validation
    valid = adapter.validate_generation({"model_type": "wan-t2v-1.3b", "prompt": "hello"})
    assert valid["validated"] is True
    assert valid["engine_id"] == "wan2gp"

    # Progress and Result translation
    received_progress = []
    handle = adapter.submit_generation(valid, on_progress=lambda p: received_progress.append(p))
    assert handle.engine_id == "wan2gp"
    assert len(received_progress) == 1
    assert isinstance(received_progress[0], EngineProgress)
    assert received_progress[0].progress == 50
    assert received_progress[0].current_step == 5

    result = adapter.wait_for_result(handle)
    assert isinstance(result, EngineResult)
    assert result.success is True
    assert len(result.output_files) == 1
    assert result.output_files[0] == str(video_file)


def test_stub_adapters_declare_capabilities_and_reject_execution():
    from app.engines.stubs import _StubEngine

    class FutureExperimentalEngine(_StubEngine):
        _engine_id = "future-engine"
        _display_name = "Future Experimental Engine"
        _description = "Placeholder for upcoming experimental video models."
        _capabilities = EngineCapabilities(text_to_video=True)

    stub = FutureExperimentalEngine()
    assert stub.is_available is False
    status = stub.get_runtime_status()
    assert status["available"] is False
    assert status["engine_id"] == "future-engine"
    assert stub.list_models() == []

    with pytest.raises(NotImplementedError, match="not yet installed"):
        stub.validate_generation({"model_type": "test"})

    with pytest.raises(NotImplementedError, match="not yet installed"):
        stub.submit_generation({}, lambda p: None)


def test_global_engine_registry_initialization():
    registry = get_engine_registry()
    registered = registry.list_engines()
    engine_ids = [e["engine_id"] for e in registered]

    assert "wan2gp" in engine_ids
    assert "ltx-video" in engine_ids
    assert "ltx-2" in engine_ids
    assert "minimax-h3-longvideo" in engine_ids
    assert "minimax-h3-director" in engine_ids

    runtime_status = registry.get_runtime_status()
    assert "engines" in runtime_status
    assert "wan2gp" in runtime_status["engines"]


def test_generation_worker_with_engine_registry(db, tmp_path):
    user = User(username="engineuser", email="engine@example.com", hashed_password="hash")
    db.add(user)
    db.commit()
    db.refresh(user)

    video_file = tmp_path / "generated_test.mp4"
    video_file.write_bytes(b"engine video bytes")

    mock_service = MockWan2GPService(output_path=video_file)
    registry = VideoEngineRegistry()
    registry.register(Wan2GPAdapter(mock_service), default=True)

    job = GenerationJob(
        id="engine-job-1",
        user_id=user.id,
        status=GenerationStatus.QUEUED,
        prompt="A serene mountain lake",
        model_type="wan-t2v-1.3b",
        generation_settings={"model_type": "wan-t2v-1.3b", "engine_id": "wan2gp"},
    )
    db.add(job)
    db.commit()

    worker = GenerationWorker(
        session_factory=sessionmaker(bind=db.get_bind()),
        engine_registry=registry,
        storage_root=tmp_path / "storage",
    )

    assert worker.run_once() is True
    updated_job = db.get(GenerationJob, "engine-job-1")
    assert updated_job.status == GenerationStatus.COMPLETED
    assert updated_job.progress == 100
    assert updated_job.output_path == f"videos/{user.id}/engine-job-1/output.mp4"
    assert (tmp_path / "storage" / updated_job.output_path).is_file()
