"""
Validation and integration tests for the Wan2GP Engine Adapter.
Verifies programmatic invocation, verified capabilities, model validation,
runtime status reporting, progress forwarding, error reporting, and shutdown.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
import pytest

from app.engines.base import EngineCapabilities, EngineJobHandle, EngineProgress, EngineResult
from app.engines.wan2gp_adapter import Wan2GPAdapter
from app.services.wan2gp_service import Wan2GPProgress, Wan2GPService


class MockWanGPSession:
    """Mock in-process WanGPSession for testing adapter behavior."""

    def __init__(self, available: bool = True, model_fails: bool = False, execute_fails: bool = False):
        self.available = available
        self.model_fails = model_fails
        self.execute_fails = execute_fails
        self.closed = False
        self.cancelled_jobs = []

    def list_model_metadata(self, include_availability: bool = True, main_output: str = "video") -> list[dict[str, Any]]:
        if not self.available:
            raise RuntimeError("Underlying CUDA runtime unavailable.")
        return [
            {
                "model_type": "wan2.1_t2v_1.3B",
                "name": "Wan2.1 T2V 1.3B",
                "availability": {"available": True},
            },
            {
                "model_type": "wan2.1_t2v_14B",
                "name": "Wan2.1 T2V 14B",
                "availability": {"available": False, "reason": "Weights not downloaded"},
            },
        ]

    def get_model_def(self, model_type: str) -> dict[str, Any] | None:
        if model_type == "wan2.1_t2v_1.3B":
            return {"name": "Wan2.1 T2V 1.3B", "image_prompt_types_allowed": "SV"}
        return None

    def get_model_availability(self, model_type: str) -> dict[str, Any]:
        if model_type == "wan2.1_t2v_1.3B":
            return {"available": not self.model_fails}
        return {"available": False, "reason": "Model not found"}

    def get_default_settings(self, model_type: str) -> dict[str, Any]:
        return {
            "num_inference_steps": 30,
            "guidance_scale": 6.0,
            "fps": 16,
            "resolution": "832*480",
        }

    def submit_task(self, settings: dict[str, Any], callbacks: Any) -> Any:
        class TaskHandle:
            def __init__(self, session, settings, callbacks):
                self._session = session
                self._settings = settings
                self._callbacks = callbacks

            def result(self):
                if self._session.execute_fails:
                    raise RuntimeError("CUDA Out of Memory during inference.")
                # Simulate progress update
                if self._callbacks:
                    self._callbacks.on_progress(
                        SimpleNamespace(
                            progress=100,
                            current_step=30,
                            total_steps=30,
                            phase="completed",
                            status="Done",
                        )
                    )
                return SimpleNamespace(
                    success=True,
                    generated_files=["/storage/wan2gp-runtime/output_001.mp4"],
                    artifacts=(),
                    errors=(),
                )

            def cancel(self):
                self._session.cancelled_jobs.append(self._settings)

        return TaskHandle(self, settings, callbacks)

    def close(self):
        self.closed = True


# ============================================================================
# 1. Adapter Contract & Capability Declarations
# ============================================================================

def test_wan2gp_adapter_metadata_and_capabilities():
    mock_session = MockWanGPSession()
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    assert adapter.engine_id == "wan2gp"
    assert adapter.display_name == "Wan2GP Engine"
    assert "Wan2GP" in adapter.description

    caps = adapter.capabilities
    assert isinstance(caps, EngineCapabilities)
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.video_continuation is True
    assert caps.native_long_video is False
    assert caps.configurable_fps is True
    assert caps.configurable_steps is True
    assert caps.configurable_seed is True
    assert caps.progress_reporting is True
    assert caps.cancellation is True


# ============================================================================
# 2. Runtime Status & Model Discovery
# ============================================================================

def test_wan2gp_adapter_runtime_status_ready():
    mock_session = MockWanGPSession(available=True)
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    status = adapter.get_runtime_status()
    assert status["available"] is True
    assert status["status"] == "ready"
    assert status["engine_id"] == "wan2gp"
    assert status["models_available"] == 1
    assert status["models_total"] == 2
    assert adapter.is_available is True

    models = adapter.list_models()
    assert len(models) == 2
    assert models[0]["engine_id"] == "wan2gp"
    assert models[0]["model_type"] == "wan2.1_t2v_1.3B"


def test_wan2gp_adapter_runtime_status_unavailable_error():
    mock_session = MockWanGPSession(available=False)
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    status = adapter.get_runtime_status()
    assert status["available"] is False
    assert status["status"] == "unavailable"
    assert "Underlying CUDA runtime unavailable" in status["error"]
    assert adapter.is_available is False


# ============================================================================
# 3. Settings Validation & Default Merging
# ============================================================================

def test_wan2gp_adapter_validates_settings_and_merges_defaults():
    mock_session = MockWanGPSession()
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    payload = {"model_type": "wan2.1_t2v_1.3B", "prompt": "a serene landscape"}
    validated = adapter.validate_generation(payload)

    assert validated["engine_id"] == "wan2gp"
    assert validated["prompt"] == "a serene landscape"
    assert validated["num_inference_steps"] == 30
    assert validated["guidance_scale"] == 6.0
    assert validated["fps"] == 16


def test_wan2gp_adapter_validation_rejects_unknown_model():
    mock_session = MockWanGPSession()
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    with pytest.raises(ValueError, match="Unknown Wan2GP model"):
        adapter.validate_generation({"model_type": "non_existent_model"})


def test_wan2gp_adapter_validation_rejects_unavailable_model():
    mock_session = MockWanGPSession(model_fails=True)
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    with pytest.raises(ValueError, match="The selected Wan2GP model is not available"):
        adapter.validate_generation({"model_type": "wan2.1_t2v_1.3B"})


# ============================================================================
# 4. Programmatic Submission, Progress Tracking & Results
# ============================================================================

def test_wan2gp_adapter_submit_and_progress_reporting():
    mock_session = MockWanGPSession()
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    progress_events = []

    def on_progress(p: EngineProgress):
        progress_events.append(p)

    settings = {"id": "test_job_1", "model_type": "wan2.1_t2v_1.3B", "prompt": "cyberpunk city"}
    handle = adapter.submit_generation(settings, on_progress)

    assert isinstance(handle, EngineJobHandle)
    assert handle.job_id == "test_job_1"
    assert handle.engine_id == "wan2gp"

    result = adapter.wait_for_result(handle)
    assert isinstance(result, EngineResult)
    assert result.success is True
    assert len(result.output_files) == 1
    assert result.output_files[0] == "/storage/wan2gp-runtime/output_001.mp4"
    assert result.error_message is None
    assert len(progress_events) == 1
    assert progress_events[0].progress == 100


def test_wan2gp_adapter_clean_error_reporting_on_runtime_failure():
    mock_session = MockWanGPSession(execute_fails=True)
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    def on_progress(p: EngineProgress):
        pass

    settings = {"id": "fail_job", "model_type": "wan2.1_t2v_1.3B", "prompt": "ocean wave"}
    handle = adapter.submit_generation(settings, on_progress)

    result = adapter.wait_for_result(handle)
    assert result.success is False
    assert result.output_files == []
    assert "CUDA Out of Memory" in result.error_message


# ============================================================================
# 5. Cancellation & Shutdown Lifecycle
# ============================================================================

def test_wan2gp_adapter_cancellation():
    mock_session = MockWanGPSession()
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    settings = {"id": "cancel_job", "model_type": "wan2.1_t2v_1.3B"}
    handle = adapter.submit_generation(settings, lambda p: None)

    adapter.cancel_generation(handle)
    assert len(mock_session.cancelled_jobs) == 1
    assert mock_session.cancelled_jobs[0]["id"] == "cancel_job"


def test_wan2gp_adapter_shutdown():
    mock_session = MockWanGPSession()
    service = Wan2GPService(session_factory=lambda **kwargs: mock_session)
    adapter = Wan2GPAdapter(service=service)

    adapter.initialize()
    assert service._initialized is True
    assert mock_session.closed is False

    adapter.shutdown()
    assert service._initialized is False
    assert mock_session.closed is True
