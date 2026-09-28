"""
Environment and Hardware Diagnostics for LTX-Video.
Distinguishes READY, MOCK, CUDA_UNAVAILABLE, DEPENDENCY_MISSING, MODEL_MISSING, INSUFFICIENT_VRAM.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_config import logger
from app.engines.ltx_video.models import LTXStatusCode


@dataclass
class LTXEnvironmentStatus:
    """Detailed diagnostic breakdown of the host environment for LTX-Video."""
    status_code: LTXStatusCode
    is_available: bool
    is_mock: bool
    gpu_name: Optional[str]
    vram_total_gb: float
    vram_available_gb: float
    cuda_version: Optional[str]
    pytorch_version: Optional[str]
    diffusers_version: Optional[str]
    transformers_version: Optional[str]
    model_weights_path: Optional[str]
    models_found: List[str]
    missing_dependencies: List[str]
    diagnostic_message: str


def check_ltx_environment(
    checkpoints_dir: Optional[Path | str] = None,
    allow_mock: bool = False,
) -> LTXEnvironmentStatus:
    """
    Evaluates current system environment without executing inference.
    Returns structured diagnostic information.
    """
    # 1. Check DEV_MOCK_ENGINE mode
    if getattr(settings, "DEV_MOCK_ENGINE", False) and allow_mock:
        return LTXEnvironmentStatus(
            status_code=LTXStatusCode.MOCK,
            is_available=True,
            is_mock=True,
            gpu_name="Simulated Mock Device",
            vram_total_gb=24.0,
            vram_available_gb=24.0,
            cuda_version="mock-cuda",
            pytorch_version="mock-torch",
            diffusers_version="mock-diffusers",
            transformers_version="mock-transformers",
            model_weights_path="./models/ltx_video",
            models_found=["ltx-video-0.9.8-distilled", "ltx-video-0.9.5", "ltx-video-2b"],
            missing_dependencies=[],
            diagnostic_message="LTX-Video running in Development Mock Mode (GPU simulation active).",
        )

    # 2. Check dependencies
    missing_deps: List[str] = []
    torch_ver: Optional[str] = None
    diffusers_ver: Optional[str] = None
    transformers_ver: Optional[str] = None

    try:
        import torch  # type: ignore
        torch_ver = getattr(torch, "__version__", "unknown")
    except ImportError:
        missing_deps.append("torch")

    try:
        import diffusers  # type: ignore
        diffusers_ver = getattr(diffusers, "__version__", "unknown")
    except ImportError:
        missing_deps.append("diffusers")

    try:
        import transformers  # type: ignore
        transformers_ver = getattr(transformers, "__version__", "unknown")
    except ImportError:
        missing_deps.append("transformers")

    try:
        import accelerate  # type: ignore
    except ImportError:
        missing_deps.append("accelerate")

    if missing_deps:
        return LTXEnvironmentStatus(
            status_code=LTXStatusCode.DEPENDENCY_MISSING,
            is_available=False,
            is_mock=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=None,
            models_found=[],
            missing_dependencies=missing_deps,
            diagnostic_message=f"Missing required LTX-Video dependencies: {', '.join(missing_deps)}. Run: pip install torch diffusers transformers accelerate",
        )

    # 3. Check CUDA Availability
    import torch  # type: ignore
    cuda_avail = torch.cuda.is_available()
    if not cuda_avail:
        return LTXEnvironmentStatus(
            status_code=LTXStatusCode.CUDA_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name="No CUDA Device",
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=None,
            models_found=[],
            missing_dependencies=[],
            diagnostic_message="No NVIDIA CUDA GPU detected on local host. A dedicated GPU worker (local or remote) is required for real LTX-Video inference.",
        )

    gpu_name = torch.cuda.get_device_name(0)
    cuda_ver = getattr(torch.version, "cuda", "unknown")
    props = torch.cuda.get_device_properties(0)
    vram_total_gb = round(props.total_memory / (1024**3), 2)
    vram_avail_gb = round((props.total_memory - torch.cuda.memory_allocated(0)) / (1024**3), 2)

    # 4. Check VRAM sufficiency (minimum 12GB for distilled/quantized offload)
    if vram_total_gb < 11.5:
        return LTXEnvironmentStatus(
            status_code=LTXStatusCode.INSUFFICIENT_VRAM,
            is_available=False,
            is_mock=False,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_available_gb=vram_avail_gb,
            cuda_version=cuda_ver,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=None,
            models_found=[],
            missing_dependencies=[],
            diagnostic_message=f"Detected GPU '{gpu_name}' has {vram_total_gb} GB VRAM. LTX-Video requires at least 12.0 GB VRAM.",
        )

    # 5. Check model weights
    search_dir = Path(
        checkpoints_dir
        or os.environ.get("LTX_VIDEO_MODEL_PATH")
        or os.environ.get("LTX_VIDEO_CHECKPOINTS_DIR")
        or "./models/ltx_video"
    )

    models_found: List[str] = []
    if search_dir.exists():
        for item in search_dir.glob("**/*"):
            if item.is_file() and item.suffix in [".safetensors", ".pt", ".bin"]:
                models_found.append(item.name)

    # Also check HuggingFace hub cached model if configured
    hf_model_id = os.environ.get("LTX_VIDEO_HF_MODEL_ID", "Lightricks/LTX-Video")

    has_models = len(models_found) > 0 or bool(os.environ.get("LTX_VIDEO_ALLOW_HF_DOWNLOAD"))

    if not has_models:
        return LTXEnvironmentStatus(
            status_code=LTXStatusCode.MODEL_MISSING,
            is_available=False,
            is_mock=False,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_available_gb=vram_avail_gb,
            cuda_version=cuda_ver,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=str(search_dir),
            models_found=[],
            missing_dependencies=[],
            diagnostic_message=f"No LTX-Video weights found in '{search_dir}'. Download checkpoints from Hugging Face ({hf_model_id}) or set LTX_VIDEO_MODEL_PATH.",
        )

    return LTXEnvironmentStatus(
        status_code=LTXStatusCode.READY,
        is_available=True,
        is_mock=False,
        gpu_name=gpu_name,
        vram_total_gb=vram_total_gb,
        vram_available_gb=vram_avail_gb,
        cuda_version=cuda_ver,
        pytorch_version=torch_ver,
        diffusers_version=diffusers_ver,
        transformers_version=transformers_ver,
        model_weights_path=str(search_dir),
        models_found=models_found,
        missing_dependencies=[],
        diagnostic_message=f"LTX-Video engine is READY on '{gpu_name}' ({vram_total_gb} GB VRAM).",
    )
