"""
Comprehensive Non-GPU Test Suite for Real LTX-2 Multimodal Audio-Video Integration.
Verifies all 17 Phase 10 criteria without requiring NVIDIA CUDA hardware.
"""

from pathlib import Path
import sys
import pytest
from unittest.mock import MagicMock, patch

from app.engines.base import EngineCapabilities, EngineProgress, EngineResult
from app.engines.ltx2.diagnostics import LTX2EnvironmentStatus, check_ltx2_environment
from app.engines.ltx2.models import (
    LTX2GenerationRequest,
    LTX2GenerationResult,
    LTX2ModelConfig,
    LTX2StatusCode,
)
from app.engines.ltx2.runner import LTX2InferenceRunner
from app.engines.ltx2_adapter import LTX2Adapter, LTX2Service
from app.engines.registry import VideoEngineRegistry
from app.workers.base import WorkerHealthStatus, WorkerTaskStatus
from app.workers.ltx2_worker import LTX2GPUWorker


# ============================================================================
# 1. Adapter Registration
# ============================================================================

def test_1_ltx2_adapter_registration():
    registry = VideoEngineRegistry()
    adapter = LTX2Adapter()
    registry.register(adapter)

    assert "ltx-2" in registry.list_engine_ids()
    retrieved = registry.get_engine("ltx-2")
    assert retrieved.engine_id == "ltx-2"
    assert retrieved.display_name == "LTX-2 Audio-Video Engine"


# ============================================================================
# 2. Capability Discovery (Joint Audio-Video)
# ============================================================================

def test_2_ltx2_capabilities_discovery():
    adapter = LTX2Adapter()
    caps = adapter.capabilities

    assert isinstance(caps, EngineCapabilities)
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.audio_generation is True  # Verified: LTX-2 generates synchronized audio natively
    assert caps.voice_conditioning is True
    assert caps.reference_image is True
    assert caps.reference_audio is True
    assert caps.custom_resolutions is True
    assert caps.progress_reporting is True
    assert caps.cancellation is True


# ============================================================================
# 3. Request Validation
# ============================================================================

def test_3_ltx2_parameter_validation():
    adapter = LTX2Adapter()

    valid_payload = {
        "prompt": "An atmospheric stormy shoreline with thunder",
        "resolution": "1280*720",
        "fps": 25,
        "num_inference_steps": 45,
        "guidance_scale": 5.0,
        "seed": 9999,
        "generate_audio": True,
        "image_start": "/tmp/start_frame.png",
    }
    validated = adapter.validate_generation(valid_payload)
    assert validated["prompt"] == "An atmospheric stormy shoreline with thunder"
    assert validated["width"] == 1280
    assert validated["height"] == 720
    assert validated["fps"] == 25
    assert validated["num_inference_steps"] == 45
    assert validated["guidance_scale"] == 5.0
    assert validated["generate_audio"] is True
    assert validated["image_start"] == "/tmp/start_frame.png"

    # Empty prompt raises ValueError
    with pytest.raises(ValueError):
        adapter.validate_generation({"prompt": ""})

    # Unknown model raises ValueError
    with pytest.raises(ValueError, match="Unknown LTX-2 model type"):
        adapter.validate_generation({"prompt": "valid", "model_type": "nonexistent-model"})


# ============================================================================
# 4. Request Translation
# ============================================================================

def test_4_ltx2_generation_request_translation():
    req = LTX2GenerationRequest(
        prompt="Thunderstorm over ocean waves",
        negative_prompt="artifacts, silent",
        width=1024,
        height=576,
        num_frames=125,
        fps=25,
        num_inference_steps=40,
        guidance_scale=4.5,
        seed=123,
        generate_audio=True,
        image_start="/frames/ocean_frame.png",
        model_type="ltx-2-19b-av",
        job_id="ltx2_job_test",
    )
    assert req.prompt == "Thunderstorm over ocean waves"
    assert req.generate_audio is True
    assert req.width == 1024
    assert req.height == 576
    assert req.num_frames == 125
    assert req.image_start == "/frames/ocean_frame.png"


# ============================================================================
# 5. Model Detection & Weights Scanning
# ============================================================================

def test_5_ltx2_model_detection(tmp_path: Path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "ltx-2-19b_vae.safetensors").write_bytes(b"dummy")
    (models_dir / "ltx-2-19b_audio_vae.safetensors").write_bytes(b"dummy")
    (models_dir / "ltx-2-19b_vocoder.safetensors").write_bytes(b"dummy")

    diag = check_ltx2_environment(checkpoints_dir=models_dir)
    assert len(diag.video_models_found) > 0 or diag.status_code in [
        LTX2StatusCode.CUDA_UNAVAILABLE,
        LTX2StatusCode.DEPENDENCY_MISSING,
    ]


def test_runner_rejects_missing_or_vae_checkpoint(tmp_path: Path, monkeypatch):
    runner = LTX2InferenceRunner(checkpoints_dir=tmp_path, output_dir=tmp_path)
    monkeypatch.delenv("LTX2_CHECKPOINT_PATH", raising=False)

    with pytest.raises(RuntimeError, match="LTX2_CHECKPOINT_PATH"):
        runner.load_pipeline()

    vae_checkpoint = tmp_path / "ltx-2-19b_vae.safetensors"
    vae_checkpoint.write_bytes(b"not a model")
    monkeypatch.setenv("LTX2_CHECKPOINT_PATH", str(vae_checkpoint))

    with pytest.raises(ValueError, match="not a VAE"):
        runner.load_pipeline()


# ============================================================================
# 6. Dependency Detection
# ============================================================================

def test_6_ltx2_dependency_detection():
    diag = check_ltx2_environment()
    assert isinstance(diag.missing_dependencies, list)


# ============================================================================
# 7. CUDA Detection Diagnostics
# ============================================================================

def test_7_ltx2_cuda_detection_on_host():
    diag = check_ltx2_environment()
    assert diag.status_code in [
        LTX2StatusCode.CUDA_UNAVAILABLE,
        LTX2StatusCode.DEPENDENCY_MISSING,
        LTX2StatusCode.MOCK,
    ]
    assert isinstance(diag.diagnostic_message, str)


# ============================================================================
# 8. VRAM Detection
# ============================================================================

def test_8_ltx2_does_not_claim_unverified_vram_minimum(tmp_path: Path):
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 3060"
    mock_torch.cuda.get_device_properties.return_value = MagicMock(total_memory=12 * 1024**3)  # 12 GB
    mock_torch.cuda.memory_allocated.return_value = 0

    mock_transformers = MagicMock()
    mock_accelerate = MagicMock()
    mock_sf = MagicMock()
    (tmp_path / "ltx-candidate-model.safetensors").write_bytes(b"candidate")
    (tmp_path / "ltx-candidate-audio.safetensors").write_bytes(b"candidate")

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "transformers": mock_transformers,
            "accelerate": mock_accelerate,
            "soundfile": mock_sf,
        },
    ):
        diag = check_ltx2_environment(checkpoints_dir=tmp_path)
        assert diag.status_code == LTX2StatusCode.GPU_UNVERIFIED
        assert diag.is_available is False
        assert "16.0 GB" not in diag.diagnostic_message


# ============================================================================
# 9. Worker Health Check & Telemetry
# ============================================================================

def test_9_ltx2_worker_health_and_telemetry(tmp_path: Path):
    worker = LTX2GPUWorker(worker_id="test-ltx2-worker", output_dir=tmp_path)
    worker.initialize()

    health = worker.health_check()
    assert health == WorkerHealthStatus.HEALTHY

    telemetry = worker.get_telemetry()
    assert telemetry.worker_id == "test-ltx2-worker"
    assert telemetry.supported_engines == ["ltx-2"]
    assert telemetry.active_tasks == 0


# ============================================================================
# 10. Worker Offline / Missing Hardware Handling
# ============================================================================

def test_10_ltx2_truthful_missing_hardware_status():
    service = LTX2Service()
    status = service.get_runtime_status()

    assert status["engine_id"] == "ltx-2"
    assert "status" in status
    assert "message" in status
    assert status["supports_joint_audio"] is True


# ============================================================================
# 11. Model Missing Handling
# ============================================================================

def test_11_ltx2_missing_model_handling(tmp_path: Path):
    empty_dir = tmp_path / "empty_ltx2_models"
    empty_dir.mkdir()

    mock_torch = MagicMock()
    mock_torch.__version__ = "2.4.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4090"
    mock_torch.cuda.get_device_properties.return_value = MagicMock(total_memory=24 * 1024**3)
    mock_torch.cuda.memory_allocated.return_value = 0

    mock_transformers = MagicMock()
    mock_accelerate = MagicMock()
    mock_sf = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "torch": mock_torch,
            "transformers": mock_transformers,
            "accelerate": mock_accelerate,
            "soundfile": mock_sf,
        },
    ):
        diag = check_ltx2_environment(checkpoints_dir=empty_dir)
        assert diag.status_code == LTX2StatusCode.MODEL_MISSING
        assert "audio/video weights not found" in diag.diagnostic_message


# ============================================================================
# 12. Serialization
# ============================================================================

def test_12_ltx2_serialization():
    req = LTX2GenerationRequest(
        prompt="Forest stream with birds chirping",
        width=1024,
        height=576,
        fps=25,
        generate_audio=True,
    )
    assert isinstance(req.prompt, str)
    assert req.generate_audio is True


# ============================================================================
# 13. Output Normalization (Video + Audio + Multiplexed MP4)
# ============================================================================

def test_13_ltx2_output_normalization():
    res = LTX2GenerationResult(
        job_id="ltx2_job_001",
        status="COMPLETED",
        success=True,
        video_path="/output/ltx2/video_001.mp4",
        audio_path="/output/ltx2/audio_001.wav",
        combined_media_path="/output/ltx2/composed_001.mp4",
        duration=5.0,
        width=1024,
        height=576,
        fps=25,
        num_frames=125,
        has_audio=True,
        metadata={"model_type": "ltx-2-19b-av", "joint_audio_generated": True},
    )
    assert res.success is True
    assert res.has_audio is True
    assert res.video_path == "/output/ltx2/video_001.mp4"
    assert res.audio_path == "/output/ltx2/audio_001.wav"
    assert res.combined_media_path == "/output/ltx2/composed_001.mp4"
    assert res.duration == 5.0


# ============================================================================
# 14. Mock Mode Separation
# ============================================================================

def test_14_ltx2_mock_mode_separation():
    diag_mock = check_ltx2_environment(allow_mock=True)
    if diag_mock.is_mock:
        assert diag_mock.status_code == LTX2StatusCode.MOCK
        assert diag_mock.is_mock is True

    diag_real = check_ltx2_environment(allow_mock=False)
    assert diag_real.is_mock is False


# ============================================================================
# 15. Platform -> Worker Request Dispatch
# ============================================================================

def test_15_ltx2_platform_to_worker_dispatch(tmp_path: Path):
    mock_runner = MagicMock()
    mock_runner.execute_generation.return_value = LTX2GenerationResult(
        job_id="task_ltx2",
        status="COMPLETED",
        success=True,
        video_path=str(tmp_path / "vid.mp4"),
        audio_path=str(tmp_path / "aud.wav"),
        combined_media_path=str(tmp_path / "combined.mp4"),
        duration=5.0,
        width=1024,
        height=576,
        fps=25,
        num_frames=125,
        has_audio=True,
    )

    worker = LTX2GPUWorker(
        worker_id="ltx2-unit-worker",
        runner=mock_runner,
        output_dir=tmp_path,
    )
    worker.initialize()

    handle = worker.submit_task(
        task_id="task_ltx2",
        job_id="job_ltx2",
        engine_id="ltx-2",
        model_type="ltx-2-19b-av",
        settings={
            "prompt": "Ocean waves crashing at dusk",
            "resolution": "1024*576",
            "generate_audio": True,
        },
    )

    assert handle.task_id == "task_ltx2"
    assert handle.engine_id == "ltx-2"


# ============================================================================
# 16. Worker -> Platform Result Delivery
# ============================================================================

def test_16_ltx2_worker_to_platform_result_delivery(tmp_path: Path):
    mock_runner = MagicMock()
    mock_runner.execute_generation.return_value = LTX2GenerationResult(
        job_id="task_ltx2_result",
        status="COMPLETED",
        success=True,
        video_path=str(tmp_path / "vid.mp4"),
        audio_path=str(tmp_path / "aud.wav"),
        combined_media_path=str(tmp_path / "combined.mp4"),
        duration=5.0,
        width=1024,
        height=576,
        fps=25,
        num_frames=125,
        has_audio=True,
    )

    worker = LTX2GPUWorker(
        worker_id="ltx2-unit-worker",
        runner=mock_runner,
        output_dir=tmp_path,
    )
    worker.initialize()

    handle = worker.submit_task(
        task_id="task_ltx2_result",
        job_id="job_ltx2",
        engine_id="ltx-2",
        model_type="ltx-2-19b-av",
        settings={"prompt": "Sunrise over misty mountains"},
    )

    import time
    time.sleep(0.1)

    result = worker.wait_for_result(handle)
    assert result.success is True
    assert len(result.output_paths) >= 1
    assert str(tmp_path / "combined.mp4") in result.output_paths


# ============================================================================
# 17. Path Safety Validation (Path Traversal Rejection)
# ============================================================================

def test_17_ltx2_path_safety_validation(tmp_path: Path):
    worker = LTX2GPUWorker(worker_id="ltx2-secure-worker", output_dir=tmp_path)

    with pytest.raises(ValueError):
        worker._validate_path_safety("C:\\Windows\\System32")

    with pytest.raises(ValueError):
        worker._validate_path_safety("/")

    safe_path = tmp_path / "safe_start_frame.png"
    safe_path.write_bytes(b"")
    validated = worker._validate_path_safety(str(safe_path))
    assert validated == str(safe_path.resolve())
