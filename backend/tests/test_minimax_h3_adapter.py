"""
Unit and integration tests for MiniMax H3 Long-Video and Director Engine Adapters.
Validates sliding-window chunk calculation, prompt zone timeline parsing,
omni-modal audio-video capability declarations, parameter normalization, and registry integration.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
import pytest

from app.engines.base import EngineCapabilities, EngineJobHandle, EngineProgress, EngineResult
from app.engines.minimax_h3_adapter import (
    MiniMaxH3DirectorAdapter,
    MiniMaxH3DirectorService,
    MiniMaxH3LongVideoAdapter,
    PromptZone,
    SlidingWindowChunk,
)
from app.engines.registry import VideoEngineRegistry


class MockMiniMaxH3Runner:
    """Mock programmatic runner for MiniMax H3 inference execution."""

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
                    return EngineResult(success=False, error_message="CUDA out of memory during sliding-window attention.")

                if self.cb:
                    self.cb(EngineProgress(progress=30, current_step=1, total_steps=3, phase="window_1", status="Rendering chunk 1"))
                    self.cb(EngineProgress(progress=60, current_step=2, total_steps=3, phase="window_2", status="Rendering chunk 2"))
                    self.cb(EngineProgress(progress=100, current_step=3, total_steps=3, phase="completed", status="Done"))

                return EngineResult(
                    success=True,
                    output_files=["/output/minimax_h3/h3_continuous_long_video.mp4"],
                )

            def cancel(self):
                self.cancelled = True

        return JobHandle(settings, on_progress)

    def shutdown(self):
        self.shutdown_called = True


# ============================================================================
# 1. Capabilities & Contract Declarations
# ============================================================================

def test_minimax_h3_longvideo_capabilities():
    adapter = MiniMaxH3LongVideoAdapter()

    assert adapter.engine_id == "minimax-h3-longvideo"
    assert adapter.display_name == "MiniMax H3 Long Video Engine"
    assert "sliding-window" in adapter.description.lower()

    caps = adapter.capabilities
    assert isinstance(caps, EngineCapabilities)
    assert caps.native_long_video is True
    assert caps.video_continuation is True
    assert caps.audio_generation is True  # 32kHz stereo audio
    assert caps.voice_conditioning is True
    assert caps.reference_audio is True
    assert caps.reference_image is True
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.cancellation is True


def test_minimax_h3_director_capabilities():
    adapter = MiniMaxH3DirectorAdapter()

    assert adapter.engine_id == "minimax-h3-director"
    assert adapter.display_name == "MiniMax H3 Director Engine"
    assert "narrative" in adapter.description.lower()

    caps = adapter.capabilities
    assert isinstance(caps, EngineCapabilities)
    assert caps.multiple_characters is True  # Directed multi-character storyboard
    assert caps.native_long_video is True
    assert caps.audio_generation is True
    assert caps.reference_audio is True
    assert caps.reference_image is True


# ============================================================================
# 2. Sliding-Window Chunk Calculation & Timeline Prompt Zones
# ============================================================================

def test_sliding_window_chunk_calculation():
    service = MiniMaxH3DirectorService()

    # Plan a 12-second video at 25 fps = 300 frames total
    # Window: 125 frames (5s), Overlap: 25 frames (1s), Step: 100 frames (4s)
    chunks = service.build_sliding_window_plan(
        total_duration_seconds=12.0,
        fps=25,
        window_frames=125,
        overlap_frames=25,
        prompt="A continuous journey through a misty forest",
        seed=100,
    )

    assert len(chunks) == 3
    # Chunk 1: [0, 125], overlap = 0
    assert chunks[0].chunk_index == 1
    assert chunks[0].start_frame == 0
    assert chunks[0].end_frame == 125
    assert chunks[0].overlap_frames == 0
    assert chunks[0].seed == 101

    # Chunk 2: [100, 225], overlap = 25
    assert chunks[1].chunk_index == 2
    assert chunks[1].start_frame == 100
    assert chunks[1].end_frame == 225
    assert chunks[1].overlap_frames == 25
    assert chunks[1].seed == 102

    # Chunk 3: [200, 300], overlap = 25
    assert chunks[2].chunk_index == 3
    assert chunks[2].start_frame == 200
    assert chunks[2].end_frame == 300
    assert chunks[2].overlap_frames == 25
    assert chunks[2].seed == 103


def test_sliding_window_with_prompt_zones():
    service = MiniMaxH3DirectorService()

    zones = [
        PromptZone(
            start_second=0.0,
            end_second=5.0,
            prompt="Close up of Vance walking into neon cafe",
            sound_directive="Rain patter on window, jazz piano",
        ),
        PromptZone(
            start_second=5.0,
            end_second=10.0,
            prompt="Elena looks up from table and speaks",
            reference_audio_path="/audio/elena_voice.wav",
            sound_directive="Cafe chatter, clear female voice",
        ),
    ]

    chunks = service.build_sliding_window_plan(
        total_duration_seconds=10.0,
        fps=25,
        window_frames=125,
        overlap_frames=25,
        prompt="Fallback prompt",
        prompt_zones=zones,
    )

    assert len(chunks) >= 2
    assert "Vance" in chunks[0].prompt
    assert "Rain patter" in chunks[0].prompt
    assert "Elena" in chunks[1].prompt
    assert chunks[1].reference_audio_path == "/audio/elena_voice.wav"


# ============================================================================
# 3. Model Discovery & Runtime Status
# ============================================================================

def test_minimax_h3_runtime_status_unconfigured():
    service = MiniMaxH3DirectorService(checkpoints_dir="/non_existent_h3_checkpoints")
    adapter = MiniMaxH3LongVideoAdapter(service=service)

    status = adapter.get_runtime_status()
    assert status["engine_id"] == "minimax-h3-longvideo"
    assert status["available"] is False
    assert status["status"] == "unconfigured"
    assert status["supports_sliding_window"] is True
    assert status["supports_32khz_stereo_audio"] is True
    assert adapter.is_available is False

    models = adapter.list_models()
    assert len(models) == 2
    assert models[0]["supports_audio"] is True
    assert models[0]["availability"]["available"] is False


def test_minimax_h3_runtime_status_with_runner():
    mock_runner = MockMiniMaxH3Runner()
    service = MiniMaxH3DirectorService(runner_factory=lambda: mock_runner)
    adapter = MiniMaxH3DirectorAdapter(service=service)

    status = adapter.get_runtime_status()
    assert status["available"] is True
    assert status["status"] == "ready"
    assert adapter.is_available is True

    models = adapter.list_models()
    assert len(models) == 2
    assert models[0]["availability"]["available"] is True


# ============================================================================
# 4. Settings Validation
# ============================================================================

def test_minimax_h3_validate_settings():
    """validate_generation returns {valid, errors, warnings} — matches real MiniMaxH3LongVideoService."""
    adapter = MiniMaxH3LongVideoAdapter()

    payload = {
        "prompt": "An astronaut discovering an ancient crystal on Mars",
        "total_duration_seconds": 15.0,
        "fps": 25,
    }
    validated = adapter.validate_generation(payload)

    assert "valid" in validated
    assert validated["valid"] is True
    assert validated["errors"] == []


def test_minimax_h3_validation_rejects_empty_prompt():
    """validate_generation returns valid=False for empty prompt (no exception raised)."""
    adapter = MiniMaxH3LongVideoAdapter()
    result = adapter.validate_generation({"prompt": ""})
    assert result["valid"] is False
    assert any("prompt" in e.lower() for e in result["errors"])


# ============================================================================
# 5. Programmatic Execution, Progress & Failure Handling
# ============================================================================

def test_minimax_h3_submit_generation_and_result():
    """submit_generation/wait_for_result work end-to-end with a mocked runner."""
    from app.engines.minimax_h3_adapter import MiniMaxH3LongVideoService
    from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationResult
    from unittest.mock import patch

    service = MiniMaxH3LongVideoService(
        checkpoints_dir="/nonexistent", output_dir="/tmp/lv_submit_test"
    )
    adapter = MiniMaxH3LongVideoAdapter(service=service)
    service.initialize()

    mock_result = H3LongVideoGenerationResult(
        job_id="h3_job_001",
        status="COMPLETED",
        success=True,
        video_path="/output/minimax_h3_longvideos/h3_continuous_long_video.mp4",
        output_paths=["/output/minimax_h3_longvideos/h3_continuous_long_video.mp4"],
    )

    progress_events = []

    def on_prog(p: EngineProgress):
        progress_events.append(p)

    settings = {
        "id": "h3_job_001",
        "prompt": "Drone shot traveling down a vast canyon",
        "total_duration_seconds": 10.0,
    }

    with patch.object(service._runner, "execute_long_video", return_value=mock_result):
        handle = adapter.submit_generation(settings, on_prog)
        assert isinstance(handle, EngineJobHandle)
        assert handle.engine_id == "minimax-h3-longvideo"
        result = adapter.wait_for_result(handle)

    assert isinstance(result, EngineResult)
    assert result.success is True
    assert len(result.output_files) >= 1
    assert "h3_continuous_long_video.mp4" in result.output_files[0]


def test_minimax_h3_clean_error_on_failure():
    mock_runner = MockMiniMaxH3Runner(should_fail=True)
    service = MiniMaxH3DirectorService(runner_factory=lambda: mock_runner)
    adapter = MiniMaxH3DirectorAdapter(service=service)

    settings = {
        "id": "h3_fail_001",
        "prompt": "complex scene",
    }
    validated = adapter.validate_generation(settings)
    handle = adapter.submit_generation(validated, lambda p: None)

    result = adapter.wait_for_result(handle)
    assert result.success is False
    assert result.output_files == []
    assert "CUDA out of memory" in result.error_message


def test_minimax_h3_cancellation_and_shutdown():
    """cancel_generation and shutdown work correctly with real LongVideoService."""
    from app.engines.minimax_h3_adapter import MiniMaxH3LongVideoService
    from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationResult
    from unittest.mock import patch

    service = MiniMaxH3LongVideoService(
        checkpoints_dir="/nonexistent", output_dir="/tmp/lv_cancel_test"
    )
    adapter = MiniMaxH3LongVideoAdapter(service=service)
    service.initialize()

    cancelled_result = H3LongVideoGenerationResult(
        job_id="cancel_job",
        status="CANCELLED",
        success=False,
        error_message="Cancelled by user.",
    )

    settings = {"id": "cancel_job", "prompt": "test prompt"}
    with patch.object(service._runner, "execute_long_video", return_value=cancelled_result):
        handle = adapter.submit_generation(settings, lambda p: None)
        adapter.cancel_generation(handle)
        result = adapter.wait_for_result(handle)

    assert result.success is False
    adapter.shutdown()


# ============================================================================
# 6. VideoEngineRegistry Integration
# ============================================================================

def test_minimax_h3_in_video_engine_registry():
    reg = VideoEngineRegistry()
    mock_runner = MockMiniMaxH3Runner()
    service = MiniMaxH3DirectorService(runner_factory=lambda: mock_runner)
    long_adapter = MiniMaxH3LongVideoAdapter(service=service)
    director_adapter = MiniMaxH3DirectorAdapter(service=service)

    reg.register(long_adapter)
    reg.register(director_adapter)

    fetched_long = reg.get_engine("minimax-h3-longvideo")
    assert fetched_long is not None
    assert fetched_long.capabilities.native_long_video is True
    assert fetched_long.capabilities.audio_generation is True

    fetched_dir = reg.get_engine("minimax-h3-director")
    assert fetched_dir is not None
    assert fetched_dir.capabilities.multiple_characters is True
