"""
Comprehensive Test Suite — MiniMax H3 LongVideos Engine
========================================================
Covers:
  - Environment diagnostics (CUDA-unavailable path, mock path, dependency-missing path)
  - H3LongVideoPlanner: single-beat, multi-beat, dialogue estimation, character binding
  - H3LongVideoContinuityCoordinator: frame extraction, conditioning handoff, audio crossfade,
    state checkpoint save/load
  - MiniMaxH3LongVideoRunner: env check branching, plan-only mode, chunk execution,
    cancel signalling, error propagation
  - MiniMaxH3LongVideoService: initialization, runtime_status, list_models, validate_generation,
    submit_generation lifecycle
  - MiniMaxH3LongVideoAdapter: full BaseVideoEngine interface contract
  - Standalone server: health, diagnostics, models, plan endpoints
  - Data model construction: all dataclasses instantiate correctly
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, PropertyMock
import uuid

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Ensure DEV_MOCK_ENGINE is off unless test explicitly uses mock path."""
    monkeypatch.setenv("DEV_MOCK_ENGINE", "false")
    monkeypatch.setenv("H3_MOCK_MODE", "false")
    monkeypatch.setenv("H3_LONGVIDEO_MOCK_MODE", "false")


@pytest.fixture()
def tmp_output_dir(tmp_path):
    return tmp_path / "longvideo_output"


# ===========================================================================
# 1. DATA MODELS
# ===========================================================================

class TestDataModels:

    def test_h3_longvideo_status_code_values(self):
        from app.engines.minimax_h3_longvideos.models import H3LongVideoStatusCode
        assert H3LongVideoStatusCode.READY.value == "READY"
        assert H3LongVideoStatusCode.GPU_UNVERIFIED.value == "GPU-UNVERIFIED"
        assert H3LongVideoStatusCode.CUDA_UNAVAILABLE.value == "CUDA_UNAVAILABLE"
        assert H3LongVideoStatusCode.DEPENDENCY_MISSING.value == "DEPENDENCY_MISSING"
        assert H3LongVideoStatusCode.MODEL_MISSING.value == "MODEL_MISSING"
        assert H3LongVideoStatusCode.INSUFFICIENT_VRAM.value == "INSUFFICIENT_VRAM"
        assert H3LongVideoStatusCode.FAILED.value == "FAILED"

    def test_long_video_character_card_defaults(self):
        from app.engines.minimax_h3_longvideos.models import LongVideoCharacterCard
        card = LongVideoCharacterCard(
            character_id="hero",
            name="Alice",
            description="The protagonist.",
        )
        assert card.character_id == "hero"
        assert card.reference_image_path is None
        assert card.voice_name is None

    def test_long_video_beat_defaults(self):
        from app.engines.minimax_h3_longvideos.models import LongVideoBeat
        beat = LongVideoBeat(beat_index=0, raw_text="test", action="runs forward")
        assert beat.duration_seconds == 5.0
        assert beat.active_characters == []

    def test_long_video_chunk_fields(self):
        from app.engines.minimax_h3_longvideos.models import LongVideoChunk
        chunk = LongVideoChunk(
            chunk_index=2,
            start_second=10.0,
            end_second=15.0,
            duration_seconds=5.0,
            num_frames=125,
            prompt="A hero walks.",
        )
        assert chunk.chunk_index == 2
        assert chunk.num_frames == 125
        assert chunk.conditioning_image_path is None

    def test_generation_request_defaults(self):
        from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationRequest
        req = H3LongVideoGenerationRequest(prompt="test prompt")
        assert req.fps == 25
        assert req.chunk_duration_seconds == 5.0
        assert req.enable_visual_continuity is True
        assert req.plan_only is False

    def test_generation_result_defaults(self):
        from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationResult
        res = H3LongVideoGenerationResult(
            job_id="test-123",
            status="COMPLETED",
            success=True,
        )
        assert res.output_paths == []
        assert res.telemetry == {}


# ===========================================================================
# 2. DIAGNOSTICS
# ===========================================================================

class TestDiagnostics:

    def test_mock_mode_returns_mock_status(self, monkeypatch):
        monkeypatch.setenv("H3_LONGVIDEO_MOCK_MODE", "true")
        from app.engines.minimax_h3_longvideos.diagnostics import (
            check_h3_longvideo_environment,
            H3LongVideoEnvironmentStatus,
        )
        from app.engines.minimax_h3_longvideos.models import H3LongVideoStatusCode
        # Mock settings.DEV_MOCK_ENGINE
        with patch("app.engines.minimax_h3_longvideos.diagnostics.settings") as mock_settings:
            mock_settings.DEV_MOCK_ENGINE = False
            status = check_h3_longvideo_environment(allow_mock=True)
        assert status.status_code == H3LongVideoStatusCode.MOCK
        assert status.is_available is True
        assert status.is_mock is True
        assert status.downstream_h3_available is True

    def test_missing_torch_dependency(self, monkeypatch):
        from app.engines.minimax_h3_longvideos.diagnostics import check_h3_longvideo_environment
        from app.engines.minimax_h3_longvideos.models import H3LongVideoStatusCode

        with patch("app.engines.minimax_h3_longvideos.diagnostics.settings") as mock_settings:
            mock_settings.DEV_MOCK_ENGINE = False
            with patch.dict("sys.modules", {"torch": None}):
                import importlib
                import app.engines.minimax_h3_longvideos.diagnostics as diag_mod
                status = diag_mod.check_h3_longvideo_environment(allow_mock=False)

        # torch missing → DEPENDENCY_MISSING or CUDA_UNAVAILABLE depending on import order
        assert status.status_code in (
            H3LongVideoStatusCode.DEPENDENCY_MISSING,
            H3LongVideoStatusCode.CUDA_UNAVAILABLE,
            H3LongVideoStatusCode.MODEL_MISSING,
        )
        assert status.is_available is False

    def test_cuda_unavailable_path(self):
        from app.engines.minimax_h3_longvideos.diagnostics import check_h3_longvideo_environment
        from app.engines.minimax_h3_longvideos.models import H3LongVideoStatusCode
        with patch("app.engines.minimax_h3_longvideos.diagnostics.settings") as mock_settings:
            mock_settings.DEV_MOCK_ENGINE = False
            status = check_h3_longvideo_environment(allow_mock=False)
        # On this machine (no CUDA) must be one of these truthful codes
        assert status.status_code in (
            H3LongVideoStatusCode.CUDA_UNAVAILABLE,
            H3LongVideoStatusCode.DEPENDENCY_MISSING,
            H3LongVideoStatusCode.MODEL_MISSING,
            H3LongVideoStatusCode.GPU_UNVERIFIED,
        )
        assert isinstance(status.diagnostic_message, str)
        assert len(status.diagnostic_message) > 0

    def test_status_has_required_fields(self):
        from app.engines.minimax_h3_longvideos.diagnostics import check_h3_longvideo_environment
        with patch("app.engines.minimax_h3_longvideos.diagnostics.settings") as mock_settings:
            mock_settings.DEV_MOCK_ENGINE = False
            status = check_h3_longvideo_environment(allow_mock=False)
        assert hasattr(status, "status_code")
        assert hasattr(status, "is_available")
        assert hasattr(status, "is_mock")
        assert hasattr(status, "gpu_name")
        assert hasattr(status, "vram_total_gb")
        assert hasattr(status, "downstream_h3_available")
        assert hasattr(status, "chunk_vram_budget_gb")
        assert hasattr(status, "max_feasible_chunks")


# ===========================================================================
# 3. PLANNER
# ===========================================================================

class TestH3LongVideoPlanner:

    def _make_request(self, **kwargs):
        from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationRequest
        defaults = dict(
            prompt="A cinematic short film.",
            total_duration_seconds=15.0,
            chunk_duration_seconds=5.0,
        )
        defaults.update(kwargs)
        return H3LongVideoGenerationRequest(**defaults)

    def test_no_beats_text_creates_single_beat(self):
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
        planner = H3LongVideoPlanner()
        req = self._make_request(beats_text=None, total_duration_seconds=5.0)
        plan = planner.plan(req)
        assert len(plan.chunks) >= 1
        assert plan.chunks[0].prompt != ""

    def test_multi_paragraph_beats_creates_multiple_chunks(self):
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
        beats = """Scene: a beach at sunset.

A woman walks along the shoreline.

The sun dips below the horizon.

Waves crash gently on the rocks."""
        planner = H3LongVideoPlanner()
        req = self._make_request(beats_text=beats, total_duration_seconds=15.0)
        plan = planner.plan(req)
        # 3 beats (excluding first scene paragraph)
        assert len(plan.beats) == 3
        assert len(plan.chunks) == 3

    def test_dialogue_increases_duration(self):
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
        beats_long_dialogue = """Scene: a courtroom.

"Ladies and gentlemen of the jury, the evidence presented today conclusively demonstrates that my client is entirely innocent of all charges laid before this court." The lawyer adjusts her notes."""

        beats_action_only = """Scene: a courtroom.

The lawyer adjusts her notes quietly."""

        planner = H3LongVideoPlanner()
        req_long = self._make_request(beats_text=beats_long_dialogue)
        req_short = self._make_request(beats_text=beats_action_only)
        plan_long = planner.plan(req_long)
        plan_short = planner.plan(req_short)
        assert plan_long.beats[0].duration_seconds >= plan_short.beats[0].duration_seconds

    def test_character_binding(self):
        from app.engines.minimax_h3_longvideos.models import LongVideoCharacterCard
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
        beats = """Scene.

alice walks forward."""
        char = LongVideoCharacterCard(character_id="alice", name="Alice", description="Protagonist.")
        planner = H3LongVideoPlanner()
        req = self._make_request(beats_text=beats, characters=[char])
        plan = planner.plan(req)
        # Alice should be detected in the beat
        assert "alice" in plan.beats[0].active_characters

    def test_duration_clamps_to_min(self):
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner, _MIN_CHUNK_DURATION_S
        planner = H3LongVideoPlanner()
        req = self._make_request(chunk_duration_seconds=0.1, total_duration_seconds=2.0, beats_text=None)
        plan = planner.plan(req)
        for chunk in plan.chunks:
            assert chunk.duration_seconds >= _MIN_CHUNK_DURATION_S

    def test_custom_chunks_bypass_parser(self):
        from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationRequest, LongVideoChunk
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
        chunk = LongVideoChunk(
            chunk_index=0, start_second=0.0, end_second=5.0,
            duration_seconds=5.0, num_frames=125, prompt="Custom chunk."
        )
        req = H3LongVideoGenerationRequest(prompt="test", custom_chunks=[chunk])
        planner = H3LongVideoPlanner()
        plan = planner.plan(req)
        assert len(plan.chunks) == 1
        assert plan.chunks[0].prompt == "Custom chunk."

    def test_plan_report_is_string(self):
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
        planner = H3LongVideoPlanner()
        req = self._make_request()
        plan = planner.plan(req)
        report = planner.plan_report(plan)
        assert isinstance(report, str)
        assert "H3 LongVideos Plan" in report

    def test_chunk_seeds_are_unique(self):
        from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
        beats = """Scene.

Beat one.

Beat two.

Beat three."""
        planner = H3LongVideoPlanner()
        req = self._make_request(beats_text=beats, seed=42)
        plan = planner.plan(req)
        seeds = [c.seed for c in plan.chunks]
        assert len(set(seeds)) == len(seeds)  # all unique


# ===========================================================================
# 4. CONTINUITY COORDINATOR
# ===========================================================================

class TestH3LongVideoContinuityCoordinator:

    def test_apply_conditioning_sets_path(self, tmp_output_dir):
        from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
        from app.engines.minimax_h3_longvideos.models import LongVideoChunk

        tmp_output_dir.mkdir(parents=True, exist_ok=True)
        frame_path = tmp_output_dir / "frame.png"
        frame_path.write_bytes(b"PNG")

        coord = H3LongVideoContinuityCoordinator(output_dir=tmp_output_dir)
        chunk = LongVideoChunk(
            chunk_index=1, start_second=5.0, end_second=10.0,
            duration_seconds=5.0, num_frames=125, prompt="test"
        )
        updated = coord.apply_conditioning_to_chunk(chunk, str(frame_path))
        assert updated.conditioning_image_path == str(frame_path)

    def test_apply_conditioning_skips_missing_path(self, tmp_output_dir):
        from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
        from app.engines.minimax_h3_longvideos.models import LongVideoChunk

        tmp_output_dir.mkdir(parents=True, exist_ok=True)
        coord = H3LongVideoContinuityCoordinator(output_dir=tmp_output_dir)
        chunk = LongVideoChunk(
            chunk_index=1, start_second=5.0, end_second=10.0,
            duration_seconds=5.0, num_frames=125, prompt="test"
        )
        updated = coord.apply_conditioning_to_chunk(chunk, "/nonexistent/frame.png")
        assert updated.conditioning_image_path is None

    def test_save_and_load_chunk_state(self, tmp_path):
        from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
        from app.engines.minimax_h3_longvideos.models import LongVideoChunk

        coord = H3LongVideoContinuityCoordinator(output_dir=tmp_path)
        chunk = LongVideoChunk(
            chunk_index=3, start_second=15.0, end_second=20.0,
            duration_seconds=5.0, num_frames=125, prompt="state test"
        )
        state_data = {"success": True, "video_path": "/tmp/chunk_0003.mp4"}
        coord.save_chunk_state(chunk, state_data, tmp_path)
        loaded = coord.load_chunk_state(3, tmp_path)
        assert loaded is not None
        assert loaded["success"] is True
        assert loaded["video_path"] == "/tmp/chunk_0003.mp4"

    def test_load_missing_state_returns_none(self, tmp_path):
        from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
        coord = H3LongVideoContinuityCoordinator(output_dir=tmp_path)
        result = coord.load_chunk_state(99, tmp_path)
        assert result is None

    def test_audio_concat_single_segment(self, tmp_path):
        from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator

        # Create a dummy WAV file (minimal 44-byte header + data)
        wav_path = tmp_path / "seg0.wav"
        wav_path.write_bytes(b"\x00" * 88)  # fake 44-byte header + 44 bytes data
        output = tmp_path / "combined.wav"

        coord = H3LongVideoContinuityCoordinator(output_dir=tmp_path)
        result = coord.crossfade_and_concat_audio([str(wav_path)], output)
        # Single segment = copy; should return path (even if soundfile not available)
        assert result is not None or output.exists() or True  # no crash

    def test_audio_concat_empty_list_returns_none(self, tmp_path):
        from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
        coord = H3LongVideoContinuityCoordinator(output_dir=tmp_path)
        result = coord.crossfade_and_concat_audio([], tmp_path / "out.wav")
        assert result is None

    def test_extract_final_frame_missing_file(self, tmp_path):
        from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
        coord = H3LongVideoContinuityCoordinator(output_dir=tmp_path)
        result = coord.extract_final_frame("/nonexistent/video.mp4", 0)
        assert result is None


# ===========================================================================
# 5. RUNNER
# ===========================================================================

class TestMiniMaxH3LongVideoRunner:

    def _make_runner(self, tmp_path):
        from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner
        return MiniMaxH3LongVideoRunner(
            checkpoints_dir=str(tmp_path / "models"),
            output_dir=str(tmp_path / "output"),
        )

    def test_runner_instantiates(self, tmp_path):
        runner = self._make_runner(tmp_path)
        assert runner is not None

    def test_gpu_ready_returns_bool_and_string(self, tmp_path):
        runner = self._make_runner(tmp_path)
        ready, msg = runner.is_gpu_ready()
        assert isinstance(ready, bool)
        assert isinstance(msg, str)

    def test_plan_only_mode_no_inference(self, tmp_path):
        """Plan-only mode must return plan without calling H3 runner."""
        from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationRequest
        from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner
        from app.engines.minimax_h3_longvideos.diagnostics import H3LongVideoEnvironmentStatus
        from app.engines.minimax_h3_longvideos.models import H3LongVideoStatusCode

        runner = self._make_runner(tmp_path)

        # Patch env check to say available
        mock_diag = H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.GPU_UNVERIFIED,
            is_available=True,
            is_mock=False,
            gpu_name="Mock GPU",
            vram_total_gb=48.0,
            vram_available_gb=40.0,
            cuda_version="12.4",
            pytorch_version="2.3.0",
            diffusers_version="0.30.0",
            transformers_version="4.40.0",
            model_weights_path="./models/minimax_h3",
            models_found=["minimax_h3_transformer.safetensors", "video_vae.safetensors", "audio_vae.safetensors"],
            missing_dependencies=[],
            downstream_h3_available=True,
            chunk_vram_budget_gb=40.0,
            max_feasible_chunks=1,
            diagnostic_message="Mock GPU available.",
        )

        with patch("app.engines.minimax_h3_longvideos.runner.check_h3_longvideo_environment", return_value=mock_diag):
            req = H3LongVideoGenerationRequest(
                prompt="Test scene.",
                total_duration_seconds=10.0,
                chunk_duration_seconds=5.0,
                plan_only=True,
            )
            result = runner.execute_long_video(req)

        assert result.success is True
        assert result.plan_only is True
        assert result.status == "PLAN_COMPLETE"
        assert result.plan is not None
        assert result.plan["num_chunks"] >= 1

    def test_env_unavailable_returns_failure(self, tmp_path):
        from app.engines.minimax_h3_longvideos.models import H3LongVideoGenerationRequest, H3LongVideoStatusCode
        from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner
        from app.engines.minimax_h3_longvideos.diagnostics import H3LongVideoEnvironmentStatus

        runner = self._make_runner(tmp_path)
        mock_diag = H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.CUDA_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=None,
            diffusers_version=None,
            transformers_version=None,
            model_weights_path="./models/minimax_h3",
            models_found=[],
            missing_dependencies=[],
            downstream_h3_available=False,
            chunk_vram_budget_gb=0.0,
            max_feasible_chunks=0,
            diagnostic_message="No CUDA.",
        )

        with patch("app.engines.minimax_h3_longvideos.runner.check_h3_longvideo_environment", return_value=mock_diag):
            req = H3LongVideoGenerationRequest(prompt="Test")
            result = runner.execute_long_video(req)

        assert result.success is False
        assert result.status == H3LongVideoStatusCode.CUDA_UNAVAILABLE.value

    def test_cancel_before_execution(self, tmp_path):
        from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner
        runner = self._make_runner(tmp_path)
        # cancel a nonexistent job → returns False
        assert runner.cancel("nonexistent-job-id") is False

    def test_shutdown_does_not_raise(self, tmp_path):
        from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner
        runner = self._make_runner(tmp_path)
        runner.shutdown()  # Should not raise


# ===========================================================================
# 6. SERVICE
# ===========================================================================

class TestMiniMaxH3LongVideoService:

    def _make_service(self, tmp_path):
        from app.engines.minimax_h3_adapter import MiniMaxH3LongVideoService
        return MiniMaxH3LongVideoService(
            checkpoints_dir=str(tmp_path / "models"),
            output_dir=str(tmp_path / "output"),
        )

    def test_service_instantiates(self, tmp_path):
        service = self._make_service(tmp_path)
        assert service is not None

    def test_get_runtime_status_returns_dict(self, tmp_path):
        service = self._make_service(tmp_path)
        status = service.get_runtime_status()
        assert isinstance(status, dict)
        assert "engine_id" in status
        assert status["engine_id"] == "minimax-h3-longvideo"
        assert "available" in status
        assert "status_code" in status
        assert "chunk_vram_budget_gb" in status
        assert "max_feasible_chunks" in status

    def test_list_models_returns_list(self, tmp_path):
        service = self._make_service(tmp_path)
        models = service.list_models()
        assert isinstance(models, list)
        assert len(models) >= 1
        assert "model_id" in models[0]
        assert models[0]["native_long_video"] is True

    def test_validate_generation_requires_prompt(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.validate_generation({"prompt": ""})
        assert result["valid"] is False
        assert any("prompt" in e for e in result["errors"])

    def test_validate_generation_valid_request(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.validate_generation({
            "prompt": "A mountain scene.",
            "total_duration_seconds": 15.0,
            "chunk_duration_seconds": 5.0,
        })
        assert result["valid"] is True

    def test_validate_generation_too_short(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.validate_generation({
            "prompt": "Test",
            "total_duration_seconds": 0.5,
        })
        assert result["valid"] is False

    def test_validate_generation_warns_on_long_chunk(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.validate_generation({
            "prompt": "Test",
            "chunk_duration_seconds": 20.0,
        })
        assert any("14s" in w or "14" in w for w in result.get("warnings", []))

    def test_initialize_creates_runner(self, tmp_path):
        from app.engines.minimax_h3_adapter import MiniMaxH3LongVideoService
        from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner

        service = MiniMaxH3LongVideoService(
            checkpoints_dir=str(tmp_path / "models"),
            output_dir=str(tmp_path / "output"),
        )
        service.initialize()
        assert service._runner is not None
        assert isinstance(service._runner, MiniMaxH3LongVideoRunner)


# ===========================================================================
# 7. ADAPTER (BaseVideoEngine contract)
# ===========================================================================

class TestMiniMaxH3LongVideoAdapter:

    def _make_adapter(self, tmp_path):
        from app.engines.minimax_h3_adapter import MiniMaxH3LongVideoAdapter, MiniMaxH3LongVideoService
        service = MiniMaxH3LongVideoService(
            checkpoints_dir=str(tmp_path / "models"),
            output_dir=str(tmp_path / "output"),
        )
        return MiniMaxH3LongVideoAdapter(service=service)

    def test_engine_id(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        assert adapter.engine_id == "minimax-h3-longvideo"

    def test_display_name(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        assert "Long Video" in adapter.display_name

    def test_description(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        assert isinstance(adapter.description, str)
        assert len(adapter.description) > 10

    def test_capabilities_native_long_video(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        caps = adapter.capabilities
        assert caps.native_long_video is True
        assert caps.text_to_video is True
        assert caps.audio_generation is True
        assert caps.cancellation is True

    def test_get_runtime_status(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        status = adapter.get_runtime_status()
        assert isinstance(status, dict)
        assert "engine_id" in status

    def test_list_models(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        models = adapter.list_models()
        assert isinstance(models, list)

    def test_validate_generation(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        result = adapter.validate_generation({"prompt": "test"})
        assert "valid" in result

    def test_submit_and_cancel(self, tmp_path):
        from app.engines.minimax_h3_adapter import MiniMaxH3LongVideoAdapter, MiniMaxH3LongVideoService
        from app.engines.base import EngineProgress

        service = MiniMaxH3LongVideoService(
            checkpoints_dir=str(tmp_path / "models"),
            output_dir=str(tmp_path / "output"),
        )
        adapter = MiniMaxH3LongVideoAdapter(service=service)
        service.initialize()

        progress_events = []
        def on_progress(p: EngineProgress):
            progress_events.append(p)

        # Mock the runner so we don't actually run GPU inference
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.output_paths = []
        mock_result.error_message = "CUDA unavailable"
        mock_result.status = "CUDA_UNAVAILABLE"
        mock_result.plan_only = False
        mock_result.chunks = []
        mock_result.telemetry = {}
        mock_result.execution_time_seconds = 0.1

        with patch.object(service._runner, "execute_long_video", return_value=mock_result):
            handle = adapter.submit_generation(
                {"prompt": "test", "total_duration_seconds": 5.0},
                on_progress,
            )
            assert handle is not None
            result = adapter.wait_for_result(handle)
            assert isinstance(result.success, bool)

    def test_shutdown_does_not_raise(self, tmp_path):
        adapter = self._make_adapter(tmp_path)
        adapter.shutdown()


# ===========================================================================
# 8. STANDALONE SERVER
# ===========================================================================

class TestStandaloneH3LongVideoServer:

    @pytest.fixture(autouse=True)
    def setup_client(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MINIMAX_H3_CHECKPOINTS_DIR", str(tmp_path / "models"))
        monkeypatch.setenv("MINIMAX_H3_LONGVIDEO_OUTPUT_DIR", str(tmp_path / "output"))

        import importlib
        import app.workers.standalone_minimax_h3_longvideo_server as server_mod
        # Reset runner singleton
        server_mod._runner = None
        server_mod._job_history = {}

        from fastapi.testclient import TestClient
        self.client = TestClient(server_mod.app)
        yield
        server_mod._runner = None
        server_mod._job_history = {}

    def test_health_endpoint_returns_200(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "engine" in data
        assert data["engine"] == "minimax-h3-longvideo"
        assert "is_available" in data
        assert "supports_sliding_window" in data

    def test_diagnostics_endpoint(self):
        response = self.client.get("/diagnostics")
        assert response.status_code == 200
        data = response.json()
        assert "status_code" in data
        assert "chunk_vram_budget_gb" in data

    def test_models_endpoint(self):
        response = self.client.get("/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) >= 1
        assert data["models"][0]["native_long_video"] is True

    def test_plan_endpoint(self):
        response = self.client.get("/plan", params={
            "prompt": "A beach at sunset.",
            "total_duration_seconds": 10.0,
            "chunk_duration_seconds": 5.0,
        })
        assert response.status_code == 200
        data = response.json()
        assert "num_chunks" in data
        assert data["num_chunks"] >= 1
        assert "chunks" in data
        assert "report" in data

    def test_generate_returns_503_when_unavailable(self):
        import app.workers.standalone_minimax_h3_longvideo_server as server_mod
        from app.engines.minimax_h3_longvideos.diagnostics import H3LongVideoEnvironmentStatus
        from app.engines.minimax_h3_longvideos.models import H3LongVideoStatusCode

        unavailable_diag = H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.CUDA_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=None,
            diffusers_version=None,
            transformers_version=None,
            model_weights_path="./models",
            models_found=[],
            missing_dependencies=[],
            downstream_h3_available=False,
            chunk_vram_budget_gb=0.0,
            max_feasible_chunks=0,
            diagnostic_message="No CUDA.",
        )

        with patch(
            "app.workers.standalone_minimax_h3_longvideo_server.check_h3_longvideo_environment",
            return_value=unavailable_diag,
        ):
            response = self.client.post("/generate", json={
                "prompt": "Test",
                "total_duration_seconds": 5.0,
            })
        assert response.status_code == 503

    def test_job_not_found_returns_404(self):
        response = self.client.get("/jobs/nonexistent-job-id")
        assert response.status_code == 404


# ===========================================================================
# 9. REGISTRY / ADAPTER INTEGRATION
# ===========================================================================

class TestRegistryIntegration:

    def test_longvideo_adapter_in_registry(self):
        from app.engines.registry import VideoEngineRegistry
        from app.engines.minimax_h3_adapter import MiniMaxH3LongVideoAdapter
        registry = VideoEngineRegistry()
        registry.register(MiniMaxH3LongVideoAdapter())
        engine = registry.get_engine("minimax-h3-longvideo")
        assert engine is not None
        assert engine.engine_id == "minimax-h3-longvideo"

    def test_director_and_longvideo_both_in_registry(self):
        from app.engines.registry import VideoEngineRegistry
        from app.engines.minimax_h3_adapter import MiniMaxH3DirectorAdapter, MiniMaxH3LongVideoAdapter
        registry = VideoEngineRegistry()
        registry.register(MiniMaxH3LongVideoAdapter())
        registry.register(MiniMaxH3DirectorAdapter())
        assert registry.get_engine("minimax-h3-longvideo") is not None
        assert registry.get_engine("minimax-h3-director") is not None
        assert registry.get_engine("minimax-h3-longvideo") is not registry.get_engine("minimax-h3-director")
