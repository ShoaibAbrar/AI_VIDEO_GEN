"""
Unit and integration tests for the LTX-Video Engine Adapter.
Validates isolated programmatic integration, non-audio video-only capability declarations,
parameter validation, model discovery, error handling, cancellation, and registry routing.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
import pytest

from app.engines.base import EngineCapabilities, EngineJobHandle, EngineProgress, EngineResult
from app.engines.ltx_video_adapter import LTXVideoAdapter, LTXVideoService
from app.engines.registry import VideoEngineRegistry


class MockLTXVideoRunner:
    """Mock programmatic runner for LTX-Video inference execution."""

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
                    return EngineResult(success=False, error_message="CUDA out of memory during DiT spatial attention.")

                if self.cb:
                    self.cb(EngineProgress(progress=50, current_step=4, total_steps=8, phase="diffusion", status="Rendering frames"))
                    self.cb(EngineProgress(progress=100, current_step=8, total_steps=8, phase="completed", status="Done"))

                return EngineResult(
                    success=True,
                    output_files=["/output/ltx_video/ltx_video_sample.mp4"],
                )

            def cancel(self):
                self.cancelled = True

        return JobHandle(settings, on_progress)

    def shutdown(self):
        self.shutdown_called = True


# ============================================================================
# 1. Metadata, Contract & Capability Declarations
# ============================================================================

def test_ltx_video_adapter_metadata_and_capabilities():
    adapter = LTXVideoAdapter()

    assert adapter.engine_id == "ltx-video"
    assert adapter.display_name == "LTX-Video Engine"
    assert "LTX-Video" in adapter.description or "DiT" in adapter.description

    caps = adapter.capabilities
    assert isinstance(caps, EngineCapabilities)
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.video_continuation is False
    assert caps.native_long_video is False
    assert caps.audio_generation is False  # Explicitly verified: LTX-Video does NOT generate audio
    assert caps.voice_conditioning is False
    assert caps.reference_image is True
    assert caps.reference_video is False
    assert caps.reference_audio is False
    assert caps.multiple_characters is False
    assert caps.custom_resolutions is True
    assert caps.configurable_fps is True
    assert caps.configurable_steps is True
    assert caps.configurable_seed is True
    assert caps.progress_reporting is True
    assert caps.cancellation is True


# ============================================================================
# 2. Isolation from Wan2GP and LTX-2
# ============================================================================

def test_ltx_video_isolation_from_wan2gp_and_ltx2():
    from app.engines import ltx_video_adapter

    with open(ltx_video_adapter.__file__, "r", encoding="utf-8") as f:
        content = f.read()

    assert "shared.api" not in content
    assert "Wan2GPService" not in content
    assert "Wan2GPAdapter" not in content
    assert "LTX2Service" not in content
    assert "LTX2Adapter" not in content


# ============================================================================
# 3. Model Discovery & Runtime Status
# ============================================================================

def test_ltx_video_runtime_status_when_unconfigured():
    service = LTXVideoService(checkpoints_dir="/non_existent_checkpoints_dir_456")
    adapter = LTXVideoAdapter(service=service)

    status = adapter.get_runtime_status()
    assert status["engine_id"] == "ltx-video"
    assert status["available"] is False
    assert status["status"] == "unconfigured"
    assert status["supports_audio"] is False
    assert adapter.is_available is False

    models = adapter.list_models()
    assert len(models) == 3
    assert models[0]["model_type"] == "ltx-video-0.9.8-distilled"
    assert models[0]["supports_audio"] is False
    assert models[0]["availability"]["available"] is False


def test_ltx_video_runtime_status_when_configured_with_runner():
    mock_runner = MockLTXVideoRunner()
    service = LTXVideoService(runner_factory=lambda: mock_runner)
    adapter = LTXVideoAdapter(service=service)

    status = adapter.get_runtime_status()
    assert status["engine_id"] == "ltx-video"
    assert status["available"] is True
    assert status["status"] == "ready"
    assert status["supports_audio"] is False
    assert adapter.is_available is True

    models = adapter.list_models()
    assert len(models) == 3
    assert models[0]["availability"]["available"] is True


# ============================================================================
# 4. Settings Validation & Parameter Normalization
# ============================================================================

def test_ltx_video_validate_generation_defaults():
    mock_runner = MockLTXVideoRunner()
    service = LTXVideoService(runner_factory=lambda: mock_runner)
    adapter = LTXVideoAdapter(service=service)

    payload = {
        "prompt": "Cinematic shot of ocean waves crashing on dark rocks",
        "model_type": "ltx-video-0.9.8-distilled",
    }
    validated = adapter.validate_generation(payload)

    assert validated["engine_id"] == "ltx-video"
    assert validated["prompt"] == "Cinematic shot of ocean waves crashing on dark rocks"
    assert validated["num_inference_steps"] == 8
    assert validated["guidance_scale"] == 1.0
    assert validated["fps"] == 24
    assert validated["resolution"] == "768*512"
    assert validated["num_frames"] == 121


def test_ltx_video_validate_generation_rejects_empty_prompt():
    adapter = LTXVideoAdapter()
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        adapter.validate_generation({"prompt": "   ", "model_type": "ltx-video-0.9.8-distilled"})


def test_ltx_video_validate_generation_rejects_unknown_model():
    adapter = LTXVideoAdapter()
    with pytest.raises(ValueError, match="Unknown LTX-Video model type"):
        adapter.validate_generation({"prompt": "valid prompt", "model_type": "unknown-model"})


# ============================================================================
# 5. Programmatic Execution, Progress & Failure Handling
# ============================================================================

def test_ltx_video_submit_generation_and_result_delivery():
    mock_runner = MockLTXVideoRunner()
    service = LTXVideoService(runner_factory=lambda: mock_runner)
    adapter = LTXVideoAdapter(service=service)

    progress_events = []

    def on_prog(p: EngineProgress):
        progress_events.append(p)

    settings = {
        "id": "ltxv_job_001",
        "prompt": "A wolf running through snowy mountains",
        "model_type": "ltx-video-0.9.8-distilled",
    }
    validated = adapter.validate_generation(settings)
    handle = adapter.submit_generation(validated, on_prog)

    assert isinstance(handle, EngineJobHandle)
    assert handle.engine_id == "ltx-video"
    assert handle.job_id == "ltxv_job_001"

    result = adapter.wait_for_result(handle)
    assert isinstance(result, EngineResult)
    assert result.success is True
    assert len(result.output_files) == 1
    assert "ltx_video_sample.mp4" in result.output_files[0]
    assert len(progress_events) == 2
    assert progress_events[-1].progress == 100


def test_ltx_video_clean_error_reporting_on_execution_failure():
    mock_runner = MockLTXVideoRunner(should_fail=True)
    service = LTXVideoService(runner_factory=lambda: mock_runner)
    adapter = LTXVideoAdapter(service=service)

    settings = {
        "id": "ltxv_fail_001",
        "prompt": "heavy scene exceeding VRAM",
        "model_type": "ltx-video-0.9.5",
    }
    validated = adapter.validate_generation(settings)
    handle = adapter.submit_generation(validated, lambda p: None)

    result = adapter.wait_for_result(handle)
    assert result.success is False
    assert result.output_files == []
    assert "CUDA out of memory" in result.error_message


def test_ltx_video_cancellation_and_shutdown():
    mock_runner = MockLTXVideoRunner()
    service = LTXVideoService(runner_factory=lambda: mock_runner)
    adapter = LTXVideoAdapter(service=service)

    settings = {"id": "cancel_job", "prompt": "test prompt", "model_type": "ltx-video-0.9.8-distilled"}
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

def test_ltx_video_in_video_engine_registry():
    reg = VideoEngineRegistry()
    mock_runner = MockLTXVideoRunner()
    service = LTXVideoService(runner_factory=lambda: mock_runner)
    adapter = LTXVideoAdapter(service=service)

    reg.register(adapter)

    fetched = reg.get_engine("ltx-video")
    assert fetched is not None
    assert fetched.engine_id == "ltx-video"
    assert fetched.capabilities.audio_generation is False
    assert fetched.capabilities.text_to_video is True

    engines_list = reg.list_engines()
    ltx_info = next((e for e in engines_list if e["engine_id"] == "ltx-video"), None)
    assert ltx_info is not None
    assert ltx_info["capabilities"]["audio_generation"] is False
