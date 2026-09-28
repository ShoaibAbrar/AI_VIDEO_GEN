"""
Environment Diagnostics for Voice Cloning Subsystem.
Probes CUDA, VRAM, PyTorch, audio libraries, and Chatterbox model checkpoint availability.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_config import logger
from app.services.voice.cloning.models import VoiceCloningStatusCode


@dataclass
class VoiceCloningEnvironmentStatus:
    """Detailed diagnostic report for Voice Cloning runtime."""
    status_code: VoiceCloningStatusCode
    is_available: bool
    is_mock: bool
    gpu_available: bool
    gpu_name: Optional[str]
    vram_total_gb: float
    vram_available_gb: float
    cuda_version: Optional[str]
    pytorch_version: Optional[str]
    model_id: str
    model_weights_path: Optional[str]
    model_cached: bool
    missing_dependencies: List[str]
    diagnostic_message: str


def check_voice_cloning_environment(
    model_id: str = "resemble-ai/chatterbox-multilingual",
    checkpoints_dir: Optional[str | Path] = None,
    allow_mock: bool = False,
) -> VoiceCloningEnvironmentStatus:
    """
    Evaluates host system environment for Voice Cloning without executing inference.
    """
    # 1. Check Mock Mode
    mock_mode = (
        getattr(settings, "DEV_MOCK_ENGINE", False)
        or os.environ.get("DEV_MOCK_VOICE", "").lower() in ("true", "1", "yes")
        or os.environ.get("VOICE_CLONING_MOCK_MODE", "").lower() in ("true", "1", "yes")
    )
    if mock_mode and allow_mock:
        return VoiceCloningEnvironmentStatus(
            status_code=VoiceCloningStatusCode.MOCK,
            is_available=True,
            is_mock=True,
            gpu_available=True,
            gpu_name="Simulated Voice GPU",
            vram_total_gb=8.0,
            vram_available_gb=6.0,
            cuda_version="12.4",
            pytorch_version="2.3.0",
            model_id=model_id,
            model_weights_path="./models/chatterbox",
            model_cached=True,
            missing_dependencies=[],
            diagnostic_message="Voice Cloning running in Development Mock Mode.",
        )

    # 2. Dependency Checks
    missing_deps: List[str] = []

    try:
        import torch
        torch_ver = torch.__version__
        cuda_avail = torch.cuda.is_available()
    except ImportError:
        torch_ver = None
        cuda_avail = False
        missing_deps.append("torch")

    try:
        import torchaudio  # noqa: F401
    except ImportError:
        missing_deps.append("torchaudio")

    try:
        import transformers  # noqa: F401
    except ImportError:
        missing_deps.append("transformers")

    try:
        import soundfile  # noqa: F401
    except ImportError:
        missing_deps.append("soundfile")

    if missing_deps:
        return VoiceCloningEnvironmentStatus(
            status_code=VoiceCloningStatusCode.DEPENDENCY_MISSING,
            is_available=False,
            is_mock=False,
            gpu_available=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=torch_ver,
            model_id=model_id,
            model_weights_path=None,
            model_cached=False,
            missing_dependencies=missing_deps,
            diagnostic_message=f"Missing Python dependencies: {', '.join(missing_deps)}. Install with: pip install {' '.join(missing_deps)}",
        )

    # 3. Hardware / CUDA Probing
    gpu_name = None
    vram_total = 0.0
    vram_avail = 0.0
    cuda_version = None

    if cuda_avail:
        try:
            import torch
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram_total = props.total_memory / (1024 ** 3)
            vram_avail = (props.total_memory - torch.cuda.memory_allocated(0)) / (1024 ** 3)
            cuda_version = torch.version.cuda
        except Exception:
            pass

    # 4. Model Checkpoint Location
    models_root = Path(
        checkpoints_dir
        or os.environ.get("VOICE_CLONING_MODEL_PATH")
        or os.environ.get("CHATTERBOX_MODEL_DIR")
        or "./models/chatterbox"
    ).resolve()

    model_cached = models_root.exists() and len(list(models_root.glob("*"))) > 0

    # Determine Status
    if not cuda_avail:
        # Voice cloning can still run on CPU in fallback mode, but with higher latency
        msg = "CUDA GPU not detected. Voice cloning is running in CPU mode (or GPU-UNVERIFIED on development host)."
        return VoiceCloningEnvironmentStatus(
            status_code=VoiceCloningStatusCode.GPU_UNVERIFIED,
            is_available=True,  # CPU / Unverified mode available
            is_mock=False,
            gpu_available=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=torch_ver,
            model_id=model_id,
            model_weights_path=str(models_root) if model_cached else None,
            model_cached=model_cached,
            missing_dependencies=[],
            diagnostic_message=msg,
        )

    return VoiceCloningEnvironmentStatus(
        status_code=VoiceCloningStatusCode.READY,
        is_available=True,
        is_mock=False,
        gpu_available=True,
        gpu_name=gpu_name,
        vram_total_gb=round(vram_total, 2),
        vram_available_gb=round(vram_avail, 2),
        cuda_version=cuda_version,
        pytorch_version=torch_ver,
        model_id=model_id,
        model_weights_path=str(models_root) if model_cached else None,
        model_cached=model_cached,
        missing_dependencies=[],
        diagnostic_message=f"Voice Cloning ready on {gpu_name} ({vram_total:.1f} GB VRAM).",
    )
