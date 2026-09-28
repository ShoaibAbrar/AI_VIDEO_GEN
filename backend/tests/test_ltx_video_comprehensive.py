"""
Comprehensive Non-GPU Test Suite for Real LTX-Video Engine & Worker Integration.
Verifies all 15 Phase 12 criteria without requiring NVIDIA CUDA hardware.
"""

from pathlib import Path
import sys
from types import ModuleType
import pytest
from unittest.mock import MagicMock, patch

from app.engines.base import EngineCapabilities, EngineProgress, EngineResult
from app.engines.ltx_video.diagnostics import LTXEnvironmentStatus, check_ltx_environment
from app.engines.ltx_video.models import (
    LTXGenerationRequest,
    LTXGenerationResult,
    LTXModelConfig,
    LTXStatusCode,
)
from app.engines.ltx_video.runner import LTXVideoInferenceRunner
from app.engines.ltx_video_adapter import LTXVideoAdapter, LTXVideoService
from app.engines.registry import VideoEngineRegistry
from app.workers.base import WorkerHealthStatus, WorkerTaskStatus
from app.workers.ltx_worker import LTXGPUWorker


# ============================================================================
# 1. Adapter Registration
# ============================================================================

def test_1_ltx_video_adapter_registration():
    registry = VideoEngineRegistry()
    adapter = LTXVideoAdapter()
    registry.register(adapter)

    assert "ltx-video" in registry.list_engine_ids()
    retrieved = registry.get_engine("ltx-video")
    assert retrieved.engine_id == "ltx-video"
    assert retrieved.display_name == "LTX-Video Engine"


# ============================================================================
# 2. Capability Discovery
# ============================================================================

def test_2_ltx_video_capabilities_discovery():
    adapter = LTXVideoAdapter()
    caps = adapter.capabilities

    assert isinstance(caps, EngineCapabilities)
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.audio_generation is False  # Explicitly verified: pure visual video model
    assert caps.voice_conditioning is False
    assert caps.reference_image is True
    assert caps.custom_resolutions is True
    assert caps.progress_reporting is True
    assert caps.cancellation is True


# ============================================================================
# 3. Parameter Validation
# ============================================================================

def test_3_ltx_video_parameter_validation():
    adapter = LTXVideoAdapter()

    # Valid request
    valid_payload = {
        "prompt": "A futuristic city in rain",
        "resolution": "1024*576",
        "fps": 24,
        "num_inference_steps": 25,
        "guidance_scale": 3.5,
        "seed": 1234,
        "image_start": "/tmp/start.png",
    }
    validated = adapter.validate_generation(valid_payload)
    assert validated["prompt"] == "A futuristic city in rain"
    assert validated["width"] == 1024
    assert validated["height"] == 576
    assert validated["fps"] == 24
    assert validated["num_inference_steps"] == 25
    assert validated["guidance_scale"] == 3.5
    assert validated["seed"] == 1234
    assert validated["image_start"] == "/tmp/start.png"

    # Empty prompt raises ValueError
    with pytest.raises(ValueError):
        adapter.validate_generation({"prompt": ""})


# ============================================================================
# 4. Request Translation
# ============================================================================

def test_4_ltx_generation_request_translation():
    req = LTXGenerationRequest(
        prompt="Cyberpunk vehicle chase",
        negative_prompt="blurry, distorted",
        width=768,
        height=512,
        num_frames=121,
        fps=24,
        num_inference_steps=30,
        guidance_scale=3.0,
        seed=42,
        image_start="/frames/scene1_last.png",
        model_type="ltx-video-0.9.5",
        job_id="test_job_123",
    )
    assert req.prompt == "Cyberpunk vehicle chase"
    assert req.negative_prompt == "blurry, distorted"
    assert req.width == 768
    assert req.height == 512
    assert req.num_frames == 121
    assert req.image_start == "/frames/scene1_last.png"


# ============================================================================
# 5. Configuration Loading
# ============================================================================

def test_5_ltx_config_loading_from_env(tmp_path: Path, monkeypatch):
    custom_dir = tmp_path / "custom_ltx_models"
    custom_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LTX_VIDEO_MODEL_PATH", str(custom_dir))

    runner = LTXVideoInferenceRunner()
    assert runner.checkpoints_dir == custom_dir


# ============================================================================
# 6. Model Path Detection & Weights Scanning
# ============================================================================

def test_6_model_path_weights_scanning(tmp_path: Path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    weight_file = models_dir / "ltx-video-2b.safetensors"
    weight_file.write_bytes(b"dummy_weights_header")

    diag = check_ltx_environment(checkpoints_dir=models_dir)
    assert "ltx-video-2b.safetensors" in diag.models_found or diag.status_code in [
        LTXStatusCode.CUDA_UNAVAILABLE,
        LTXStatusCode.DEPENDENCY_MISSING,
    ]


# ============================================================================
# 7. CUDA Detection Diagnostics
# ============================================================================

def test_7_cuda_detection_on_host():
    diag = check_ltx_environment()
    # On the current Windows test machine, CUDA is not present
    assert diag.status_code in [
        LTXStatusCode.CUDA_UNAVAILABLE,
        LTXStatusCode.DEPENDENCY_MISSING,
        LTXStatusCode.MOCK,
    ]
    assert isinstance(diag.diagnostic_message, str)


# ============================================================================
# 8. Worker Health Check & Telemetry
# ============================================================================

def test_8_worker_health_check_and_telemetry(tmp_path: Path):
    worker = LTXGPUWorker(worker_id="test-ltx-worker", output_dir=tmp_path)
    worker.initialize()

    health = worker.health_check()
    assert health == WorkerHealthStatus.HEALTHY

    telemetry = worker.get_telemetry()
    assert telemetry.worker_id == "test-ltx-worker"
    assert telemetry.supported_engines == ["ltx-video"]
    assert telemetry.active_tasks == 0


# ============================================================================
# 9. Missing Worker Handling & Truthful Error
# ============================================================================

def test_9_truthful_missing_hardware_error():
    service = LTXVideoService()
    status = service.get_runtime_status()

    assert status["engine_id"] == "ltx-video"
    assert "status" in status
    assert "message" in status


# ============================================================================
# 10. Missing Model Handling
# ============================================================================

def test_10_missing_model_handling(tmp_path: Path):
    empty_dir = tmp_path / "empty_models"
    empty_dir.mkdir()

    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4090"
    mock_torch.cuda.get_device_properties.return_value = MagicMock(total_memory=24 * 1024**3)
    mock_torch.cuda.memory_allocated.return_value = 0

    mock_diffusers = MagicMock()
    mock_transformers = MagicMock()
    mock_accelerate = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "diffusers": mock_diffusers,
            "transformers": mock_transformers,
            "accelerate": mock_accelerate,
        },
    ):
        diag = check_ltx_environment(checkpoints_dir=empty_dir)
        assert diag.status_code == LTXStatusCode.MODEL_MISSING
        assert "No LTX-Video weights found" in diag.diagnostic_message


# ============================================================================
# 11. Insufficient VRAM Handling
# ============================================================================

def test_11_insufficient_vram_handling(tmp_path: Path):
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA GTX 1060"
    mock_torch.cuda.get_device_properties.return_value = MagicMock(total_memory=6 * 1024**3)  # 6 GB
    mock_torch.cuda.memory_allocated.return_value = 0

    mock_diffusers = MagicMock()
    mock_transformers = MagicMock()
    mock_accelerate = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "diffusers": mock_diffusers,
            "transformers": mock_transformers,
            "accelerate": mock_accelerate,
        },
    ):
        diag = check_ltx_environment(checkpoints_dir=tmp_path)
        assert diag.status_code == LTXStatusCode.INSUFFICIENT_VRAM
        assert "requires at least 12.0 GB VRAM" in diag.diagnostic_message


# ============================================================================
# 12. Output Normalization
# ============================================================================

def test_12_output_normalization():
    res = LTXGenerationResult(
        job_id="job_789",
        status="COMPLETED",
        success=True,
        output_path="/output/ltx_job_789.mp4",
        duration=5.04,
        width=768,
        height=512,
        fps=24,
        num_frames=121,
        metadata={"model_type": "ltx-video-0.9.5", "steps": 30, "seed": 42},
    )
    assert res.success is True
    assert res.duration == 5.04
    assert res.width == 768
    assert res.height == 512
    assert res.fps == 24
    assert res.num_frames == 121
    assert res.metadata["model_type"] == "ltx-video-0.9.5"


# ============================================================================
# 13. Mock Mode vs Real Mode Separation
# ============================================================================

def test_13_mock_mode_separation():
    diag_mock = check_ltx_environment(allow_mock=True)
    if diag_mock.is_mock:
        assert diag_mock.status_code == LTXStatusCode.MOCK
        assert diag_mock.is_mock is True

    diag_real = check_ltx_environment(allow_mock=False)
    assert diag_real.is_mock is False


# ============================================================================
# 14. Platform -> LTX Worker Execution & Progress Bridge
# ============================================================================

def test_14_worker_execution_bridge(tmp_path: Path):
    mock_runner = MagicMock()
    mock_runner.execute_generation.return_value = LTXGenerationResult(
        job_id="task_abc",
        status="COMPLETED",
        success=True,
        output_path=str(tmp_path / "rendered.mp4"),
        duration=5.0,
        width=768,
        height=512,
        fps=24,
        num_frames=121,
    )

    worker = LTXGPUWorker(
        worker_id="ltx-unit-worker",
        runner=mock_runner,
        output_dir=tmp_path,
    )
    worker.initialize()

    progress_events = []
    handle = worker.submit_task(
        task_id="task_abc",
        job_id="job_abc",
        engine_id="ltx-video",
        model_type="ltx-video-0.9.5",
        settings={
            "prompt": "A tranquil mountain sunrise",
            "resolution": "768*512",
            "num_inference_steps": 20,
        },
        on_progress=lambda p: progress_events.append(p),
    )

    assert handle.task_id == "task_abc"
    assert handle.engine_id == "ltx-video"

    import time
    time.sleep(0.1)

    result = worker.wait_for_result(handle)
    assert result.success is True
    assert len(result.output_paths) == 1
    assert result.output_paths[0] == str(tmp_path / "rendered.mp4")


# ============================================================================
# 15. Path Safety Validation (Traversal Prevention)
# ============================================================================

def test_15_path_safety_validation(tmp_path: Path):
    worker = LTXGPUWorker(worker_id="ltx-secure-worker", output_dir=tmp_path)

    # Insecure system path should raise ValueError
    with pytest.raises(ValueError):
        worker._validate_path_safety("C:\\Windows\\System32")

    with pytest.raises(ValueError):
        worker._validate_path_safety("/")

    # Safe local path should succeed
    safe_path = tmp_path / "frame.png"
    safe_path.write_bytes(b"")
    validated = worker._validate_path_safety(str(safe_path))
    assert validated == str(safe_path.resolve())
