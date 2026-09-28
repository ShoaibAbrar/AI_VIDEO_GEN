"""
Comprehensive Test Suite for MiniMax H3 Director Multi-Character Narrative Engine.
Validates timeline cut compilation, character card reference binding, downstream dispatch,
Level 2 continuity handoff, worker execution, and output normalization without a GPU.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import uuid

import pytest

from app.engines.base import EngineCapabilities, EngineProgress, EngineResult
from app.engines.minimax_h3.models import MiniMaxH3GenerationResult
from app.engines.minimax_h3_adapter import MiniMaxH3DirectorAdapter, MiniMaxH3DirectorService
from app.engines.minimax_h3_director.diagnostics import (
    H3DirectorEnvironmentStatus,
    check_minimax_h3_director_environment,
)
from app.engines.minimax_h3_director.models import (
    DirectorCharacterCard,
    DirectorShotCut,
    DirectorTimelinePlan,
    H3DirectorGenerationRequest,
    H3DirectorGenerationResult,
    H3DirectorStatusCode,
)
from app.engines.minimax_h3_director.runner import MiniMaxH3DirectorRunner
from app.engines.registry import VideoEngineRegistry, get_engine_registry
from app.schemas.requirements import (
    CharacterMode,
    ContinuityLevel,
    DurationMode,
    QualityTier,
    UserRequirements,
    VoiceMode,
)
from app.services.capability_resolver import CapabilityResolver
from app.workers.base import (
    WorkerHealthStatus,
    WorkerProgress,
    WorkerResult,
    WorkerTaskStatus,
)
from app.workers.minimax_h3_director_worker import MiniMaxH3DirectorGPUWorker


# ---------------------------------------------------------------------------
# 1. Registration & Capability Discovery
# ---------------------------------------------------------------------------

def test_01_director_registration():
    """Verify that MiniMaxH3DirectorAdapter is registered in VideoEngineRegistry."""
    registry = get_engine_registry()
    engine = registry.get_engine("minimax-h3-director")
    assert engine is not None
    assert engine.engine_id == "minimax-h3-director"
    assert engine.display_name == "MiniMax H3 Director Engine"


def test_02_director_capabilities():
    """Verify declared capabilities for MiniMax H3 Director."""
    adapter = MiniMaxH3DirectorAdapter()
    caps = adapter.capabilities
    assert caps.multiple_characters is True
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.audio_generation is True
    assert caps.reference_image is True
    assert caps.reference_audio is True
    assert caps.cancellation is True
    assert caps.progress_reporting is True
    assert caps.native_long_video is True


# ---------------------------------------------------------------------------
# 2. Story & Timeline Planning
# ---------------------------------------------------------------------------

def test_03_timeline_plan_compilation():
    """Verify that story prompt is compiled into structured cuts with camera directives."""
    runner = MiniMaxH3DirectorRunner()
    chars = [
        DirectorCharacterCard(
            character_id="vance",
            name="Vance",
            description="A cybernetic detective in a trenchcoat",
            reference_image_path="/refs/vance.png",
        ),
        DirectorCharacterCard(
            character_id="elena",
            name="Elena",
            description="A rogue AI engineer",
            reference_image_path="/refs/elena.png",
        ),
    ]

    req = H3DirectorGenerationRequest(
        prompt="A tense negotiation in a neon-lit cyberpunk noodle shop",
        title="Night City Deal",
        total_duration_seconds=10.0,
        characters=chars,
    )

    plan = runner.plan_timeline(req)
    assert isinstance(plan, DirectorTimelinePlan)
    assert plan.title == "Night City Deal"
    assert len(plan.cuts) == 2
    assert plan.cuts[0].duration_seconds == 5.0
    assert plan.cuts[1].duration_seconds == 5.0
    assert "Vance" in plan.cuts[0].prompt or "Elena" in plan.cuts[0].prompt
    assert plan.cuts[0].camera_direction != ""


def test_04_custom_cuts_preservation():
    """Verify custom user-defined shot cuts are respected."""
    runner = MiniMaxH3DirectorRunner()
    custom_cuts = [
        DirectorShotCut(
            cut_index=1,
            start_second=0.0,
            end_second=4.0,
            duration_seconds=4.0,
            prompt="Close-up of cybernetic eye scanning the room",
        ),
        DirectorShotCut(
            cut_index=2,
            start_second=4.0,
            end_second=9.0,
            duration_seconds=5.0,
            prompt="Over the shoulder shot of Vance drawing a weapon",
        ),
    ]

    req = H3DirectorGenerationRequest(
        prompt="Cyberpunk action",
        custom_cuts=custom_cuts,
    )

    plan = runner.plan_timeline(req)
    assert len(plan.cuts) == 2
    assert plan.cuts[0].duration_seconds == 4.0
    assert plan.cuts[1].duration_seconds == 5.0
    assert plan.total_duration_seconds == 9.0


# ---------------------------------------------------------------------------
# 3. Diagnostic States & Downstream Verification
# ---------------------------------------------------------------------------

def test_05_diagnostics_cuda_unavailable_on_cpu():
    """Verify CUDA_UNAVAILABLE diagnostic reporting when no GPU is present."""
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = False

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "diffusers": MagicMock(),
            "transformers": MagicMock(),
            "soundfile": MagicMock(),
        },
    ), patch("shutil.which", return_value="ffmpeg"):
        diag = check_minimax_h3_director_environment(allow_mock=False)
        assert diag.is_available is False
        assert diag.status_code == H3DirectorStatusCode.CUDA_UNAVAILABLE
        assert "No NVIDIA CUDA GPU detected" in diag.diagnostic_message


def test_06_diagnostics_downstream_h3_unavailable():
    """Verify DOWNSTREAM_ENGINE_UNAVAILABLE when downstream MiniMax H3 weights are missing."""
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4090"
    mock_torch.cuda.get_device_properties.return_value = MagicMock(total_memory=24 * (1024**3))
    mock_torch.cuda.memory_allocated.return_value = 0

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "diffusers": MagicMock(),
            "transformers": MagicMock(),
            "soundfile": MagicMock(),
        },
    ), patch("shutil.which", return_value="ffmpeg"), \
       patch("app.engines.minimax_h3_director.diagnostics.check_minimax_h3_environment") as mock_h3_diag:
        mock_h3_diag.return_value = MagicMock(
            is_available=False,
            status_code=H3DirectorStatusCode.MODEL_MISSING,
            diagnostic_message="MiniMax H3 model weights not found",
        )

        diag = check_minimax_h3_director_environment(allow_mock=False)
        assert diag.is_available is False
        assert diag.status_code == H3DirectorStatusCode.DOWNSTREAM_ENGINE_UNAVAILABLE
        assert "Downstream MiniMax H3 engine is not available" in diag.diagnostic_message


def test_07_diagnostics_mock_mode():
    """Verify mock mode diagnostic reporting."""
    with patch.dict(os.environ, {"H3_DIRECTOR_MOCK_MODE": "true"}):
        diag = check_minimax_h3_director_environment(allow_mock=True)
        assert diag.is_available is True
        assert diag.is_mock is True
        assert diag.status_code == H3DirectorStatusCode.MOCK


# ---------------------------------------------------------------------------
# 4. Multi-Cut Generation & Level 2 Continuity
# ---------------------------------------------------------------------------

def test_08_director_multi_cut_generation_with_continuity(tmp_path: Path):
    """Verify sequential cut generation and Level 2 continuity frame extraction."""
    mock_h3_runner = MagicMock()
    mock_stitcher = MagicMock()

    # Mock cut generation results
    mock_h3_runner.execute_generation.side_effect = [
        MiniMaxH3GenerationResult(
            job_id="job_cut_1",
            status="COMPLETED",
            success=True,
            video_path=str(tmp_path / "cut_1.mp4"),
            combined_media_path=str(tmp_path / "cut_1.mp4"),
            duration=5.0,
            has_audio=True,
        ),
        MiniMaxH3GenerationResult(
            job_id="job_cut_2",
            status="COMPLETED",
            success=True,
            video_path=str(tmp_path / "cut_2.mp4"),
            combined_media_path=str(tmp_path / "cut_2.mp4"),
            duration=5.0,
            has_audio=True,
        ),
    ]

    # Create dummy video files
    (tmp_path / "cut_1.mp4").write_bytes(b"dummy_mp4_1")
    (tmp_path / "cut_2.mp4").write_bytes(b"dummy_mp4_2")

    # Create runner
    runner = MiniMaxH3DirectorRunner(
        h3_runner=mock_h3_runner,
        output_dir=tmp_path,
        media_stitcher=mock_stitcher,
    )

    req = H3DirectorGenerationRequest(
        prompt="Sci-fi cinematic narrative",
        total_duration_seconds=10.0,
        enable_visual_continuity=True,
        job_id="dir_test_job",
    )

    with patch("app.engines.minimax_h3_director.runner.check_minimax_h3_director_environment") as mock_diag:
        mock_diag.return_value = MagicMock(is_available=True)

        res = runner.execute_generation(req)
        assert res.success is True
        assert res.status == "COMPLETED"
        assert len(res.scenes) == 2
        assert mock_h3_runner.execute_generation.call_count == 2
        assert mock_stitcher.stitch_scenes.call_count == 1


# ---------------------------------------------------------------------------
# 5. GPU Worker Architecture & Telemetry
# ---------------------------------------------------------------------------

def test_09_director_worker_telemetry(tmp_path: Path):
    """Verify Director GPU worker telemetry and health check."""
    worker = MiniMaxH3DirectorGPUWorker(worker_id="test-dir-worker", output_dir=tmp_path)
    worker.initialize()

    health = worker.health_check()
    assert health == WorkerHealthStatus.HEALTHY

    telemetry = worker.get_telemetry()
    assert telemetry.worker_id == "test-dir-worker"
    assert telemetry.supported_engines == ["minimax-h3-director"]
    assert worker.send_heartbeat() is True


def test_10_director_worker_execution(tmp_path: Path):
    """Verify task submission through MiniMaxH3DirectorGPUWorker."""
    mock_runner = MagicMock()
    mock_runner.execute_generation.return_value = H3DirectorGenerationResult(
        job_id="task-dir-1",
        status="COMPLETED",
        success=True,
        video_path=str(tmp_path / "final.mp4"),
        combined_media_path=str(tmp_path / "final.mp4"),
        scenes=[{"cut_index": 1}],
        duration=10.0,
    )

    worker = MiniMaxH3DirectorGPUWorker(runner=mock_runner, output_dir=tmp_path)
    handle = worker.submit_task(
        task_id="task-dir-1",
        job_id="job-dir-1",
        engine_id="minimax-h3-director",
        model_type="minimax-h3-director-hd",
        settings={"prompt": "Epic space odyssey", "total_duration_seconds": 10.0},
    )

    res = worker.wait_for_result(handle)
    assert res.success is True
    assert worker.get_task_status("task-dir-1") == WorkerTaskStatus.COMPLETED


def test_11_director_worker_cancellation():
    """Verify task cancellation in Director GPU worker."""
    mock_runner = MagicMock()
    worker = MiniMaxH3DirectorGPUWorker(runner=mock_runner)

    handle = worker.submit_task(
        task_id="task-cancel",
        job_id="job-cancel",
        engine_id="minimax-h3-director",
        model_type="minimax-h3-director-hd",
        settings={"prompt": "Test prompt"},
    )

    cancelled = worker.cancel_task("task-cancel")
    assert cancelled is True
    assert worker.get_task_status("task-cancel") == WorkerTaskStatus.CANCELLED
    mock_runner.cancel.assert_called_with("task-cancel")


# ---------------------------------------------------------------------------
# 6. Engine Selection & Capability Resolver Integration
# ---------------------------------------------------------------------------

def test_12_capability_resolver_selects_director_for_multi_character():
    """Verify CapabilityResolver selects H3 Director for multi-character directed requirements."""
    registry = get_engine_registry()
    req = UserRequirements(
        prompt="A heated argument between detective Vance and hacker Elena",
        character_mode=CharacterMode.MULTIPLE,
        voice_mode=VoiceMode.HUMAN_LIKE,
        duration=DurationMode.LONG,
    )

    plan = CapabilityResolver.resolve_plan(
        requirements=req,
        registry=registry,
        preferred_engine_id="minimax-h3-director",
    )
    assert plan is not None
    eval_dir = next((e for e in plan.fallback_options if e.engine_id == "minimax-h3-director"), None)
    assert eval_dir is not None
    assert eval_dir.display_name == "MiniMax H3 Director Engine"
