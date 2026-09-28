"""
Unit and integration tests for the LTX-2 Engine Adapter.
Validates isolated programmatic integration, capability declarations,
parameter validation, model discovery, error handling, cancellation, and registry routing.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
import pytest

from app.engines.base import EngineCapabilities, EngineJobHandle, EngineProgress, EngineResult
from app.engines.ltx2_adapter import LTX2Adapter, LTX2Service
from app.engines.registry import VideoEngineRegistry


class MockLTX2Runner:
    """Mock programmatic runner for LTX-2 inference execution."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.submitted_jobs = []
        self.shutdown_called = False

    def submit(self, settings: dict[str, Any], on_progress: Any):
        self.submitted_jobs.append(settings)
        runner_self = self

        class JobHandle:
            def __init__(self, s, cb):
                self.s = s
                self.cb = cb
                self.cancelled = False

            def result(self):
                if self.cancelled:
                    return EngineResult(success=False, error_message="Cancelled by user.")
                if runner_self.should_fail:
                    return EngineResult(success=False, error_message="CUDA out of memory in 14B video stream.")

                if self.cb:
                    self.cb(EngineProgress(progress=50, current_step=20, total_steps=40, phase="denoising", status="Generating AV"))
                    self.cb(EngineProgress(progress=100, current_step=40, total_steps=40, phase="completed", status="Done"))

                return EngineResult(
                    success=True,
                    output_files=["/output/ltx2/ltx2_sample_av.mp4"],
                )

            def cancel(self):
                self.cancelled = True

        return JobHandle(settings, on_progress)

    def shutdown(self):
        self.shutdown_called = True


# ============================================================================
# 1. Metadata, Contract & Capability Declarations
# ============================================================================

def test_ltx2_adapter_metadata_and_capabilities():
    adapter = LTX2Adapter()

    assert adapter.engine_id == "ltx-2"
    assert adapter.display_name == "LTX-2 Audio-Video Engine"
    assert "LTX-2" in adapter.description
    assert "audio" in adapter.description.lower()

    caps = adapter.capabilities
    assert isinstance(caps, EngineCapabilities)
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.video_continuation is True
    assert caps.native_long_video is False
    assert caps.audio_generation is True  # Verified joint AV generation
    assert caps.voice_conditioning is True
    assert caps.reference_image is True
    assert caps.reference_video is False
    assert caps.reference_audio is True
    assert caps.multiple_characters is False
    assert caps.custom_resolutions is True
    assert caps.configurable_fps is True
    assert caps.configurable_steps is True
    assert caps.configurable_seed is True
    assert caps.progress_reporting is True
    assert caps.cancellation is True


# ============================================================================
# 2. Isolation from Wan2GP
# ============================================================================

def test_ltx2_isolation_from_wan2gp():
    import sys
    from app.engines import ltx2_adapter

    # Check that ltx2_adapter module does not import Wan2GPService or shared.api
    with open(ltx2_adapter.__file__, "r", encoding="utf-8") as f:
        content = f.read()

    assert "shared.api" not in content
    assert "Wan2GP" not in content or "Wan2GP or UI" in content  # only docstring mention of isolation
    assert "Wan2GPService" not in content
    assert "Wan2GPAdapter" not in content


# ============================================================================
# 3. Model Discovery & Runtime Status
# ============================================================================

def test_ltx2_runtime_status_when_unconfigured():
    service = LTX2Service(checkpoints_dir="/non_existent_checkpoints_dir_123")
    adapter = LTX2Adapter(service=service)

    status = adapter.get_runtime_status()
    assert status["engine_id"] == "ltx-2"
    assert status["available"] is False
    assert status["status"] == "unconfigured"
    assert adapter.is_available is False

    models = adapter.list_models()
    assert len(models) == 3
    assert models[0]["model_type"] == "ltx-2-19b-av"
    assert models[0]["supports_audio"] is True
    assert models[0]["availability"]["available"] is False


def test_ltx2_runtime_status_when_configured_with_runner():
    mock_runner = MockLTX2Runner()
    service = LTX2Service(runner_factory=lambda: mock_runner)
    adapter = LTX2Adapter(service=service)

    status = adapter.get_runtime_status()
    assert status["engine_id"] == "ltx-2"
    assert status["available"] is True
    assert status["status"] == "GPU-UNVERIFIED"
    assert status["status_code"] == "GPU-UNVERIFIED"
    assert status["supports_joint_audio"] is True
    assert adapter.is_available is True

    models = adapter.list_models()
    assert len(models) == 3
    assert models[0]["availability"]["available"] is True


# ============================================================================
# 4. Settings Validation & Parameter Normalization
# ============================================================================

def test_ltx2_validate_generation_defaults():
    mock_runner = MockLTX2Runner()
    service = LTX2Service(runner_factory=lambda: mock_runner)
    adapter = LTX2Adapter(service=service)

    payload = {
        "prompt": "A futuristic city with flying cars and ambient sirens",
        "model_type": "ltx-2-19b-av",
    }
    validated = adapter.validate_generation(payload)

    assert validated["engine_id"] == "ltx-2"
    assert validated["prompt"] == "A futuristic city with flying cars and ambient sirens"
    assert validated["num_inference_steps"] == 40
    assert validated["guidance_scale"] == 4.5
    assert validated["fps"] == 25
    assert validated["resolution"] == "1024*576"
    assert validated["generate_audio"] is True


def test_ltx2_validate_generation_rejects_empty_prompt():
    adapter = LTX2Adapter()
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        adapter.validate_generation({"prompt": "   ", "model_type": "ltx-2-19b-av"})


def test_ltx2_validate_generation_rejects_unknown_model():
    adapter = LTX2Adapter()
    with pytest.raises(ValueError, match="Unknown LTX-2 model type"):
        adapter.validate_generation({"prompt": "valid prompt", "model_type": "unknown-model"})


# ============================================================================
# 5. Programmatic Execution, Progress & Failure Handling
# ============================================================================

def test_ltx2_submit_generation_and_result_delivery():
    mock_runner = MockLTX2Runner()
    service = LTX2Service(runner_factory=lambda: mock_runner)
    adapter = LTX2Adapter(service=service)

    progress_events = []

    def on_prog(p: EngineProgress):
        progress_events.append(p)

    settings = {
        "id": "ltx2_job_001",
        "prompt": "A musician playing violin under rainfall",
        "model_type": "ltx-2-19b-av",
    }
    validated = adapter.validate_generation(settings)
    handle = adapter.submit_generation(validated, on_prog)

    assert isinstance(handle, EngineJobHandle)
    assert handle.engine_id == "ltx-2"
    assert handle.job_id == "ltx2_job_001"

    result = adapter.wait_for_result(handle)
    assert isinstance(result, EngineResult)
    assert result.success is True
    assert len(result.output_files) == 1
    assert "ltx2_sample_av.mp4" in result.output_files[0]
    assert len(progress_events) == 2
    assert progress_events[-1].progress == 100


def test_ltx2_clean_error_reporting_on_execution_failure():
    mock_runner = MockLTX2Runner(should_fail=True)
    service = LTX2Service(runner_factory=lambda: mock_runner)
    adapter = LTX2Adapter(service=service)

    settings = {
        "id": "ltx2_fail_001",
        "prompt": "heavy scene exceeding VRAM",
        "model_type": "ltx-2-19b-av",
    }
    validated = adapter.validate_generation(settings)
    handle = adapter.submit_generation(validated, lambda p: None)

    result = adapter.wait_for_result(handle)
    assert result.success is False
    assert result.output_files == []
    assert "CUDA out of memory" in result.error_message


def test_ltx2_cancellation_and_shutdown():
    mock_runner = MockLTX2Runner()
    service = LTX2Service(runner_factory=lambda: mock_runner)
    adapter = LTX2Adapter(service=service)

    settings = {"id": "cancel_job", "prompt": "test prompt", "model_type": "ltx-2-19b-av"}
    validated = adapter.validate_generation(settings)
    handle = adapter.submit_generation(validated, lambda p: None)

    adapter.cancel_generation(handle)
    result = adapter.wait_for_result(handle)
    assert result.success is False
    assert "Cancelled" in result.error_message

    adapter.shutdown()
    assert mock_runner.shutdown_called is True


# ============================================================================
# 6. VideoEngineRegistry Integration
# ============================================================================

def test_ltx2_in_video_engine_registry():
    reg = VideoEngineRegistry()
    mock_runner = MockLTX2Runner()
    service = LTX2Service(runner_factory=lambda: mock_runner)
    adapter = LTX2Adapter(service=service)

    reg.register(adapter)

    fetched = reg.get_engine("ltx-2")
    assert fetched is not None
    assert fetched.engine_id == "ltx-2"
    assert fetched.capabilities.audio_generation is True

    engines_list = reg.list_engines()
    ltx_info = next((e for e in engines_list if e["engine_id"] == "ltx-2"), None)
    assert ltx_info is not None
    assert ltx_info["capabilities"]["audio_generation"] is True
