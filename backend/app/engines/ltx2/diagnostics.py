"""
Environment and Hardware Diagnostics for LTX-2.
Evaluates CUDA, VRAM, PyTorch, Gemma text encoders, Video VAE, Audio VAE, and Vocoders.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_config import logger
from app.engines.ltx2.models import LTX2StatusCode


@dataclass
class LTX2EnvironmentStatus:
    """Detailed diagnostic breakdown of the host environment for LTX-2."""
    status_code: LTX2StatusCode
    is_available: bool
    is_mock: bool
    gpu_name: Optional[str]
    vram_total_gb: float
    vram_available_gb: float
    cuda_version: Optional[str]
    pytorch_version: Optional[str]
    model_weights_path: Optional[str]
    video_models_found: List[str]
    audio_models_found: List[str]
    text_encoders_found: List[str]
    missing_dependencies: List[str]
    diagnostic_message: str


def check_ltx2_environment(
    checkpoints_dir: Optional[Path | str] = None,
    allow_mock: bool = False,
) -> LTX2EnvironmentStatus:
    """
    Evaluates current system environment for LTX-2 without executing inference.
    """
    # 1. Check DEV_MOCK_ENGINE mode
    if getattr(settings, "DEV_MOCK_ENGINE", False) and allow_mock:
        return LTX2EnvironmentStatus(
            status_code=LTX2StatusCode.MOCK,
            is_available=True,
            is_mock=True,
            gpu_name="Simulated Mock Device (LTX-2 AV)",
            vram_total_gb=24.0,
            vram_available_gb=24.0,
            cuda_version="mock-cuda",
            pytorch_version="mock-torch",
            model_weights_path="./models/ltx2",
            video_models_found=["ltx2_19b_config.json", "ltx-2-19b_vae.safetensors"],
            audio_models_found=["ltx-2-19b_audio_vae.safetensors", "ltx-2-19b_vocoder.safetensors"],
            text_encoders_found=["gemma-3-12b-it-qat-q4_0-unquantized.safetensors"],
            missing_dependencies=[],
            diagnostic_message="LTX-2 running in Development Mock Mode (GPU simulation active).",
        )

    # 2. Check dependencies
    missing_deps: List[str] = []
    torch_ver: Optional[str] = None

    try:
        import torch  # type: ignore
        torch_ver = getattr(torch, "__version__", "unknown")
    except ImportError:
        missing_deps.append("torch")

    try:
        import transformers  # type: ignore
    except ImportError:
        missing_deps.append("transformers")

    try:
        import accelerate  # type: ignore
    except ImportError:
        missing_deps.append("accelerate")

    try:
        import soundfile  # type: ignore
    except ImportError:
        missing_deps.append("soundfile")

    if missing_deps:
        return LTX2EnvironmentStatus(
            status_code=LTX2StatusCode.DEPENDENCY_MISSING,
            is_available=False,
            is_mock=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=torch_ver,
            model_weights_path=None,
            video_models_found=[],
            audio_models_found=[],
            text_encoders_found=[],
            missing_dependencies=missing_deps,
            diagnostic_message=f"Missing required LTX-2 dependencies: {', '.join(missing_deps)}. Run: pip install torch transformers accelerate soundfile",
        )

    # 3. Check CUDA Availability
    import torch  # type: ignore
    cuda_avail = torch.cuda.is_available()
    if not cuda_avail:
        return LTX2EnvironmentStatus(
            status_code=LTX2StatusCode.CUDA_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name="No CUDA Device",
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=torch_ver,
            model_weights_path=None,
            video_models_found=[],
            audio_models_found=[],
            text_encoders_found=[],
            missing_dependencies=[],
            diagnostic_message="No NVIDIA CUDA GPU detected on local host. A dedicated GPU worker (local or remote) is required for real LTX-2 inference.",
        )

    gpu_name = torch.cuda.get_device_name(0)
    cuda_ver = getattr(torch.version, "cuda", "unknown")
    props = torch.cuda.get_device_properties(0)
    vram_total_gb = round(props.total_memory / (1024**3), 2)
    vram_avail_gb = round((props.total_memory - torch.cuda.memory_allocated(0)) / (1024**3), 2)

    # Check candidate model files without asserting that memory or weights are sufficient.
    search_dir = Path(
        checkpoints_dir
        or os.environ.get("LTX2_MODEL_PATH")
        or os.environ.get("LTX2_CHECKPOINTS_DIR")
        or "./models/ltx2"
    )

    video_models: List[str] = []
    audio_models: List[str] = []
    text_encoders: List[str] = []

    if search_dir.exists():
        for item in search_dir.glob("**/*"):
            if item.is_file() and item.suffix in [".safetensors", ".pt", ".bin", ".json"]:
                name_lower = item.name.lower()
                if "audio" in name_lower or "vocoder" in name_lower:
                    audio_models.append(item.name)
                elif "gemma" in name_lower or "t5" in name_lower or "tokenizer" in name_lower:
                    text_encoders.append(item.name)
                elif "ltx" in name_lower or "vae" in name_lower or "config" in name_lower:
                    video_models.append(item.name)

    has_models = (len(video_models) > 0 and len(audio_models) > 0) or bool(os.environ.get("LTX2_ALLOW_HF_DOWNLOAD"))

    if not has_models:
        return LTX2EnvironmentStatus(
            status_code=LTX2StatusCode.MODEL_MISSING,
            is_available=False,
            is_mock=False,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_available_gb=vram_avail_gb,
            cuda_version=cuda_ver,
            pytorch_version=torch_ver,
            model_weights_path=str(search_dir),
            video_models_found=video_models,
            audio_models_found=audio_models,
            text_encoders_found=text_encoders,
            missing_dependencies=[],
            diagnostic_message=f"Required LTX-2 audio/video weights not found in '{search_dir}'. Please download LTX-2 checkpoints or set LTX2_MODEL_PATH.",
        )

    return LTX2EnvironmentStatus(
        status_code=LTX2StatusCode.GPU_UNVERIFIED,
        is_available=False,
        is_mock=False,
        gpu_name=gpu_name,
        vram_total_gb=vram_total_gb,
        vram_available_gb=vram_avail_gb,
        cuda_version=cuda_ver,
        pytorch_version=torch_ver,
        model_weights_path=str(search_dir),
        video_models_found=video_models,
        audio_models_found=audio_models,
        text_encoders_found=text_encoders,
        missing_dependencies=[],
        diagnostic_message=(
            f"CUDA and candidate model files were detected on '{gpu_name}' ({vram_total_gb} GB VRAM), "
            "but the pinned upstream pipeline and checkpoint are not verified. GPU inference readiness is unverified."
        ),
    )
