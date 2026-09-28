"""
Environment and Hardware Diagnostics for MiniMax H3.
Evaluates CUDA, VRAM, PyTorch, Diffusers, Transformers, Qwen3-VL text encoders, and Video/Audio VAEs.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_config import logger
from app.engines.minimax_h3.models import MiniMaxH3StatusCode


@dataclass
class MiniMaxH3EnvironmentStatus:
    """Detailed diagnostic breakdown of the host environment for MiniMax H3."""
    status_code: MiniMaxH3StatusCode
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


def check_minimax_h3_environment(
    checkpoints_dir: Optional[Path | str] = None,
    allow_mock: bool = False,
) -> MiniMaxH3EnvironmentStatus:
    """
    Evaluates system environment for MiniMax H3 without running model inference.
    """
    # 1. Check DEV_MOCK_ENGINE / H3_MOCK_MODE
    mock_mode = (
        getattr(settings, "DEV_MOCK_ENGINE", False)
        or os.environ.get("H3_MOCK_MODE", "").lower() in ("true", "1", "yes")
    )
    if mock_mode and allow_mock:
        return MiniMaxH3EnvironmentStatus(
            status_code=MiniMaxH3StatusCode.MOCK,
            is_available=True,
            is_mock=True,
            gpu_name="Simulated Mock Device (MiniMax H3 Omni-AV)",
            vram_total_gb=48.0,
            vram_available_gb=48.0,
            cuda_version="mock-cuda",
            pytorch_version="mock-torch",
            diffusers_version="mock-diffusers",
            transformers_version="mock-transformers",
            model_weights_path="./models/minimax_h3",
            models_found=["minimax_h3_transformer.safetensors", "qwen3_vl_text_encoder", "video_vae.safetensors", "audio_vae.safetensors"],
            missing_dependencies=[],
            diagnostic_message="MiniMax H3 running in Development Mock Mode (GPU simulation active).",
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

    try:
        import soundfile  # type: ignore
    except ImportError:
        missing_deps.append("soundfile")

    if missing_deps:
        return MiniMaxH3EnvironmentStatus(
            status_code=MiniMaxH3StatusCode.DEPENDENCY_MISSING,
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
            diagnostic_message=f"Missing required MiniMax H3 dependencies: {', '.join(missing_deps)}. Run: pip install torch diffusers transformers accelerate soundfile",
        )

    # 3. Check CUDA Availability
    import torch  # type: ignore
    if not torch.cuda.is_available():
        return MiniMaxH3EnvironmentStatus(
            status_code=MiniMaxH3StatusCode.CUDA_UNAVAILABLE,
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
            diagnostic_message="No NVIDIA CUDA GPU detected on local host. A dedicated GPU worker (local or remote) is required for real MiniMax H3 inference.",
        )

    gpu_name = torch.cuda.get_device_name(0)
    cuda_ver = getattr(torch.version, "cuda", "unknown")
    props = torch.cuda.get_device_properties(0)
    vram_total_gb = round(props.total_memory / (1024**3), 2)
    vram_avail_gb = round((props.total_memory - torch.cuda.memory_allocated(0)) / (1024**3), 2)

    # 4. Check VRAM threshold (minimum practical VRAM: 24.0 GB for quantized/FP8, 48.0 GB recommended)
    if vram_total_gb < 23.0:
        return MiniMaxH3EnvironmentStatus(
            status_code=MiniMaxH3StatusCode.INSUFFICIENT_VRAM,
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
            diagnostic_message=f"Detected GPU '{gpu_name}' has {vram_total_gb} GB VRAM, but MiniMax H3 requires at least 24 GB VRAM (48 GB+ recommended).",
        )

    # 5. Check model checkpoints
    search_dir = Path(
        checkpoints_dir
        or os.environ.get("MINIMAX_H3_MODEL_PATH")
        or os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR")
        or "./models/minimax_h3"
    )

    models_found: List[str] = []
    if search_dir.exists():
        for item in search_dir.glob("**/*"):
            if item.is_file() and item.suffix in [".safetensors", ".pt", ".bin", ".json"]:
                models_found.append(item.name)

    has_models = (len(models_found) > 0) or bool(os.environ.get("MINIMAX_H3_ALLOW_HF_DOWNLOAD"))

    if not has_models:
        return MiniMaxH3EnvironmentStatus(
            status_code=MiniMaxH3StatusCode.MODEL_MISSING,
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
            diagnostic_message=f"MiniMax H3 model weights not found in '{search_dir}'. Please place model checkpoints in models/minimax_h3 or set MINIMAX_H3_MODEL_PATH.",
        )

    return MiniMaxH3EnvironmentStatus(
        status_code=MiniMaxH3StatusCode.GPU_UNVERIFIED,
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
        models_found=models_found,
        missing_dependencies=[],
        diagnostic_message=f"CUDA and candidate model files detected on '{gpu_name}' ({vram_total_gb} GB VRAM). GPU inference readiness is GPU-UNVERIFIED until actual CUDA generation is executed.",
    )
