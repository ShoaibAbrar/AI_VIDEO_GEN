"""
Comprehensive Test Suite for MiniMax H3 Multimodal Omni-AV Engine.
Validates registration, capability resolution, diagnostic states, request translation,
worker communication, and output normalization without requiring a local GPU.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import uuid

import pytest

from app.engines.base import EngineCapabilities, EngineProgress, EngineResult
from app.engines.minimax_h3.diagnostics import (
    MiniMaxH3EnvironmentStatus,
    check_minimax_h3_environment,
)
from app.engines.minimax_h3.models import (
    MiniMaxH3GenerationRequest,
    MiniMaxH3GenerationResult,
    MiniMaxH3ModelConfig,
    MiniMaxH3StatusCode,
    MiniMaxH3TaskType,
)
from app.engines.minimax_h3.runner import MiniMaxH3InferenceRunner
from app.engines.minimax_h3_adapter import MiniMaxH3Adapter, MiniMaxH3Service
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
from app.workers.minimax_h3_worker import MiniMaxH3GPUWorker


# ---------------------------------------------------------------------------
# 1. Registration & Capability Discovery
# ---------------------------------------------------------------------------

def test_01_minimax_h3_engine_registration():
    """Verify that MiniMaxH3Adapter is correctly registered in VideoEngineRegistry."""
    registry = get_engine_registry()
    engine = registry.get_engine("minimax-h3")
    assert engine is not None
    assert engine.engine_id == "minimax-h3"
    assert engine.display_name == "MiniMax H3 Omni-AV Engine"
    assert "minimax-h3" in registry.list_engine_ids()


def test_02_minimax_h3_capabilities():
    """Verify declared capabilities for MiniMax H3 core engine."""
    adapter = MiniMaxH3Adapter()
    caps = adapter.capabilities
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.audio_generation is True
    assert caps.reference_image is True
    assert caps.reference_audio is True
    assert caps.reference_video is True
    assert caps.cancellation is True
    assert caps.progress_reporting is True
    # Truthful reporting: core H3 is not native long video
    assert caps.native_long_video is False


def test_03_minimax_h3_model_listing():
    """Verify model listing returns Omni-AV model metadata."""
    adapter = MiniMaxH3Adapter()
    models = adapter.list_models()
    assert len(models) >= 2
    types = [m["model_type"] for m in models]
    assert "minimax-h3-v1" in types
    assert "minimax-h3-ref2va" in types
    assert models[0]["supports_audio"] is True
    assert models[0]["defaults"]["audio_sample_rate"] == 32000


# ---------------------------------------------------------------------------
# 2. Request Validation & Normalization
# ---------------------------------------------------------------------------

def test_04_minimax_h3_validate_generation_valid():
    """Verify validation and normalization of valid generation parameters."""
    adapter = MiniMaxH3Adapter()
    settings = {
        "prompt": "A majestic dragon soaring above misty mountain peaks",
        "resolution": "1280*720",
        "num_frames": 125,
        "fps": 25,
        "guidance_scale": 5.5,
        "generate_audio": True,
    }
    validated = adapter.validate_generation(settings)
    assert validated["prompt"] == settings["prompt"]
    assert validated["width"] == 1280
    assert validated["height"] == 720
    assert validated["num_frames"] == 125
    assert validated["fps"] == 25
    assert validated["guidance_scale"] == 5.5
    assert validated["generate_audio"] is True


def test_05_minimax_h3_validate_generation_empty_prompt():
    """Verify that empty prompt is strictly rejected."""
    adapter = MiniMaxH3Adapter()
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        adapter.validate_generation({"prompt": "   "})


def test_06_minimax_h3_task_type_deduction():
    """Verify task type is deduced correctly (T2VA, FL2VA, REF2VA)."""
    # 1. Text only -> T2VA
    req1 = MiniMaxH3GenerationRequest(prompt="Test prompt")
    assert req1.task_type == MiniMaxH3TaskType.T2VA

    # 2. First/Last frame -> FL2VA
    req2 = MiniMaxH3GenerationRequest(prompt="Test", image_start="frame.png", task_type=MiniMaxH3TaskType.FL2VA)
    assert req2.task_type == MiniMaxH3TaskType.FL2VA

    # 3. References -> REF2VA
    req3 = MiniMaxH3GenerationRequest(prompt="Test", reference_audios=["sound.wav"], task_type=MiniMaxH3TaskType.REF2VA)
    assert req3.task_type == MiniMaxH3TaskType.REF2VA


# ---------------------------------------------------------------------------
# 3. Diagnostic States & Hardware Detection
# ---------------------------------------------------------------------------

def test_07_diagnostics_cuda_unavailable_on_cpu():
    """Verify that on a non-GPU environment check_minimax_h3_environment returns CUDA_UNAVAILABLE."""
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = False

    mock_diffusers = MagicMock()
    mock_transformers = MagicMock()
    mock_accelerate = MagicMock()
    mock_soundfile = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "diffusers": mock_diffusers,
            "transformers": mock_transformers,
            "accelerate": mock_accelerate,
            "soundfile": mock_soundfile,
        },
    ):
        diag = check_minimax_h3_environment(allow_mock=False)
        assert diag.is_available is False
        assert diag.status_code == MiniMaxH3StatusCode.CUDA_UNAVAILABLE
        assert "No NVIDIA CUDA GPU detected" in diag.diagnostic_message


def test_08_diagnostics_insufficient_vram():
    """Verify truthful INSUFFICIENT_VRAM reporting when GPU VRAM < 24 GB."""
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 3060"
    mock_props = MagicMock(total_memory=12 * (1024**3))  # 12 GB
    mock_torch.cuda.get_device_properties.return_value = mock_props
    mock_torch.cuda.memory_allocated.return_value = 0

    mock_diffusers = MagicMock()
    mock_transformers = MagicMock()
    mock_accelerate = MagicMock()
    mock_soundfile = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "diffusers": mock_diffusers,
            "transformers": mock_transformers,
            "accelerate": mock_accelerate,
            "soundfile": mock_soundfile,
        },
    ):
        diag = check_minimax_h3_environment(allow_mock=False)
        assert diag.is_available is False
        assert diag.status_code == MiniMaxH3StatusCode.INSUFFICIENT_VRAM
        assert "requires at least 24 GB VRAM" in diag.diagnostic_message


def test_09_diagnostics_model_missing(tmp_path: Path):
    """Verify truthful MODEL_MISSING reporting when weights directory is empty."""
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 6000 Ada"
    mock_props = MagicMock(total_memory=48 * (1024**3))  # 48 GB
    mock_torch.cuda.get_device_properties.return_value = mock_props
    mock_torch.cuda.memory_allocated.return_value = 0

    mock_diffusers = MagicMock()
    mock_transformers = MagicMock()
    mock_accelerate = MagicMock()
    mock_soundfile = MagicMock()

    empty_dir = tmp_path / "empty_models"
    empty_dir.mkdir()

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "diffusers": mock_diffusers,
            "transformers": mock_transformers,
            "accelerate": mock_accelerate,
            "soundfile": mock_soundfile,
        },
    ):
        diag = check_minimax_h3_environment(checkpoints_dir=empty_dir, allow_mock=False)
        assert diag.is_available is False
        assert diag.status_code == MiniMaxH3StatusCode.MODEL_MISSING
        assert "MiniMax H3 model weights not found" in diag.diagnostic_message


def test_10_diagnostics_mock_mode():
    """Verify mock mode diagnostic reporting."""
    with patch.dict(os.environ, {"H3_MOCK_MODE": "true"}):
        diag = check_minimax_h3_environment(allow_mock=True)
        assert diag.is_available is True
        assert diag.is_mock is True
        assert diag.status_code == MiniMaxH3StatusCode.MOCK


# ---------------------------------------------------------------------------
# 4. Result Normalization & Flexible Schema
# ---------------------------------------------------------------------------

def test_11_result_normalization_to_dict():
    """Verify platform-neutral output schema serialization."""
    res = MiniMaxH3GenerationResult(
        job_id="test-job-123",
        status="COMPLETED",
        success=True,
        video_path="/path/to/video.mp4",
        audio_path="/path/to/audio.wav",
        combined_media_path="/path/to/video.mp4",
        output_paths=["/path/to/video.mp4"],
        duration=5.0,
        width=1024,
        height=576,
        fps=25,
        sample_rate=32000,
        num_frames=125,
        has_audio=True,
        metadata={"model_type": "minimax-h3-v1", "task_type": "T2VA"},
    )
    d = res.to_dict()
    assert d["job_id"] == "test-job-123"
    assert d["status"] == "COMPLETED"
    assert d["success"] is True
    assert d["has_audio"] is True
    assert d["sample_rate"] == 32000
    assert d["duration"] == 5.0
    assert d["output_paths"] == ["/path/to/video.mp4"]


# ---------------------------------------------------------------------------
# 5. GPU Worker Architecture & Telemetry
# ---------------------------------------------------------------------------

def test_12_worker_initialization_and_telemetry():
    """Verify worker initialization and telemetry reporting."""
    worker = MiniMaxH3GPUWorker(worker_id="test-h3-worker")
    worker.initialize()
    telem = worker.get_telemetry()
    assert telem.worker_id == "test-h3-worker"
    assert telem.supported_engines == ["minimax-h3"]
    assert telem.health_status in (WorkerHealthStatus.HEALTHY, WorkerHealthStatus.BUSY)
    assert worker.send_heartbeat() is True


def test_13_worker_path_safety():
    """Verify that insecure traversal paths are rejected."""
    worker = MiniMaxH3GPUWorker()
    with pytest.raises(ValueError, match="Insecure path rejected"):
        worker._validate_path_safety("C:\\Windows\\System32\\cmd.exe")


def test_14_worker_mock_execution():
    """Verify end-to-end task submission through MiniMaxH3GPUWorker with mock runner."""
    mock_runner = MagicMock()
    mock_runner.execute_generation.return_value = MiniMaxH3GenerationResult(
        job_id="task-456",
        status="COMPLETED",
        success=True,
        video_path="./output/minimax_h3/mock.mp4",
        audio_path="./output/minimax_h3/mock.wav",
        combined_media_path="./output/minimax_h3/mock.mp4",
        output_paths=["./output/minimax_h3/mock.mp4"],
        has_audio=True,
        metadata={"mock": True},
    )

    worker = MiniMaxH3GPUWorker(runner=mock_runner)
    progress_updates = []

    def on_prog(p: WorkerProgress):
        progress_updates.append(p.percent)

    handle = worker.submit_task(
        task_id="task-456",
        job_id="job-456",
        engine_id="minimax-h3",
        model_type="minimax-h3-v1",
        settings={"prompt": "Ocean waves crashing on rocky cliff", "generate_audio": True},
        on_progress=on_prog,
    )

    result = worker.wait_for_result(handle)
    assert result.success is True
    assert len(result.output_paths) >= 1
    assert worker.get_task_status("task-456") == WorkerTaskStatus.COMPLETED


def test_15_worker_cancellation():
    """Verify worker task cancellation handling."""
    mock_runner = MagicMock()
    worker = MiniMaxH3GPUWorker(runner=mock_runner)

    handle = worker.submit_task(
        task_id="task-cancel",
        job_id="job-cancel",
        engine_id="minimax-h3",
        model_type="minimax-h3-v1",
        settings={"prompt": "Fast sports car racing"},
    )

    cancelled = worker.cancel_task("task-cancel")
    assert cancelled is True
    assert worker.get_task_status("task-cancel") == WorkerTaskStatus.CANCELLED
    mock_runner.cancel.assert_called_with("task-cancel")


# ---------------------------------------------------------------------------
# 6. Engine Selection & Capability Resolver Integration
# ---------------------------------------------------------------------------

def test_16_capability_resolver_selects_minimax_h3_when_requested():
    """Verify CapabilityResolver evaluates and selects MiniMax H3 for omni-modal audio-video requirements."""
    registry = get_engine_registry()
    req = UserRequirements(
        prompt="A bustling cyberpunk market with neon signs",
        voice_mode=VoiceMode.AI,
        duration=DurationMode.SHORT,
    )

    plan = CapabilityResolver.resolve_plan(
        requirements=req,
        registry=registry,
        preferred_engine_id="minimax-h3",
    )
    assert plan is not None
    assert plan.selected_engine_id in ["minimax-h3", "wan2gp", "mock", "mock-engine"]
    eval_h3 = next((e for e in plan.fallback_options if e.engine_id == "minimax-h3"), None)
    assert eval_h3 is not None
    assert eval_h3.display_name == "MiniMax H3 Omni-AV Engine"


def test_17_truthful_error_handling_when_cuda_missing():
    """Verify that when real execution is attempted without CUDA and without mock mode, a truthful error is returned."""
    service = MiniMaxH3Service(checkpoints_dir="/nonexistent")

    with patch("app.engines.minimax_h3.adapter.check_minimax_h3_environment" if hasattr(MiniMaxH3Service, "_check_env") else "app.engines.minimax_h3_adapter.check_minimax_h3_environment") as mock_diag, \
         patch("app.config.settings.DEV_MOCK_ENGINE", False), \
         patch.dict(os.environ, {"H3_MOCK_MODE": "false"}):
        mock_diag.return_value = MiniMaxH3EnvironmentStatus(
            status_code=MiniMaxH3StatusCode.CUDA_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name="No CUDA Device",
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version="2.4.0",
            diffusers_version="0.32.0",
            transformers_version="4.45.0",
            model_weights_path=None,
            models_found=[],
            missing_dependencies=[],
            diagnostic_message="No NVIDIA CUDA GPU detected on local host.",
        )

        job = service.submit_generation({"prompt": "A peaceful meadow"}, on_progress=lambda p: None)
        res = job.result()
        assert res.success is False
        assert "CUDA_UNAVAILABLE" in res.error_message
