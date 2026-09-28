"""
Environment and Hardware Diagnostics for MiniMax H3 LongVideos.
Evaluates CUDA, VRAM, PyTorch, Diffusers, downstream H3 runner availability,
and per-chunk VRAM budget feasibility for sliding-window long video generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_config import logger
from app.engines.minimax_h3_longvideos.models import H3LongVideoStatusCode


@dataclass
class H3LongVideoEnvironmentStatus:
    """Detailed diagnostic breakdown of the host environment for H3 LongVideos."""
    status_code: H3LongVideoStatusCode
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
    downstream_h3_available: bool
    chunk_vram_budget_gb: float
    max_feasible_chunks: int
    diagnostic_message: str
    extra: Dict[str, Any] = field(default_factory=dict)


def check_h3_longvideo_environment(
    checkpoints_dir: Optional[Path | str] = None,
    allow_mock: bool = False,
) -> H3LongVideoEnvironmentStatus:
    """
    Evaluates the host environment for MiniMax H3 LongVideos without running inference.
    Checks CUDA, VRAM, required dependencies, and downstream H3 runner readiness.
    """
    # 1. Mock mode
    mock_mode = (
        getattr(settings, "DEV_MOCK_ENGINE", False)
        or os.environ.get("H3_LONGVIDEO_MOCK_MODE", "").lower() in ("true", "1", "yes")
        or os.environ.get("H3_MOCK_MODE", "").lower() in ("true", "1", "yes")
    )
    if mock_mode and allow_mock:
        return H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.MOCK,
            is_available=True,
            is_mock=True,
            gpu_name="Simulated Mock Device (H3 LongVideos)",
            vram_total_gb=48.0,
            vram_available_gb=48.0,
            cuda_version="mock-cuda",
            pytorch_version="mock-torch",
            diffusers_version="mock-diffusers",
            transformers_version="mock-transformers",
            model_weights_path="./models/minimax_h3",
            models_found=[
                "minimax_h3_transformer.safetensors",
                "qwen3_vl_text_encoder",
                "video_vae.safetensors",
                "audio_vae.safetensors",
            ],
            missing_dependencies=[],
            downstream_h3_available=True,
            chunk_vram_budget_gb=24.0,
            max_feasible_chunks=99,
            diagnostic_message=(
                "MiniMax H3 LongVideos running in Development Mock Mode (GPU simulation active)."
            ),
        )

    # 2. Dependency checks
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
        from PIL import Image  # noqa: F401
    except ImportError:
        missing_deps.append("pillow")

    try:
        import soundfile  # noqa: F401
    except ImportError:
        missing_deps.append("soundfile")

    # 3. CUDA check
    cuda_available = False
    gpu_name: Optional[str] = None
    vram_total_gb = 0.0
    vram_available_gb = 0.0
    cuda_version: Optional[str] = None

    if "torch" not in missing_deps:
        import torch  # type: ignore
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            try:
                gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram_total_gb = props.total_memory / (1024 ** 3)
                vram_available_gb = (
                    props.total_memory - torch.cuda.memory_reserved(0)
                ) / (1024 ** 3)
                cuda_version = torch.version.cuda  # type: ignore
            except Exception as e:
                logger.warning(f"H3 LongVideos: CUDA property query failed: {e}")

    # 4. Model weights check
    weights_dir = Path(
        checkpoints_dir
        or os.environ.get("MINIMAX_H3_MODEL_PATH")
        or os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR")
        or "./models/minimax_h3"
    )
    model_weights_path = str(weights_dir.resolve())
    models_found: List[str] = []

    REQUIRED_WEIGHT_PATTERNS = [
        "minimax_h3_transformer.safetensors",
        "video_vae.safetensors",
        "audio_vae.safetensors",
    ]
    if weights_dir.exists():
        for pat in REQUIRED_WEIGHT_PATTERNS:
            if any(weights_dir.rglob(pat)):
                models_found.append(pat)

    # 5. Downstream H3 runner readiness
    downstream_h3_available = False
    try:
        from app.engines.minimax_h3.diagnostics import check_minimax_h3_environment
        h3_env = check_minimax_h3_environment(checkpoints_dir=weights_dir, allow_mock=False)
        downstream_h3_available = h3_env.is_available
    except Exception:
        downstream_h3_available = False

    # 6. VRAM budget estimation
    # Each H3 chunk (5s, 125 frames, 1024x576) requires ~22-24 GB peak VRAM
    PER_CHUNK_VRAM_GB = 24.0
    chunk_vram_budget_gb = vram_available_gb if cuda_available else 0.0
    max_feasible_chunks = (
        max(1, int(chunk_vram_budget_gb / PER_CHUNK_VRAM_GB))
        if cuda_available and chunk_vram_budget_gb > 0
        else 0
    )

    # 7. Build final status
    if missing_deps:
        return H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.DEPENDENCY_MISSING,
            is_available=False,
            is_mock=False,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_available_gb=vram_available_gb,
            cuda_version=cuda_version,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=model_weights_path,
            models_found=models_found,
            missing_dependencies=missing_deps,
            downstream_h3_available=downstream_h3_available,
            chunk_vram_budget_gb=chunk_vram_budget_gb,
            max_feasible_chunks=max_feasible_chunks,
            diagnostic_message=(
                f"H3 LongVideos: missing Python dependencies: {missing_deps}. "
                "Install with: pip install torch diffusers transformers pillow soundfile"
            ),
        )

    if not cuda_available:
        return H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.CUDA_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=model_weights_path,
            models_found=models_found,
            missing_dependencies=[],
            downstream_h3_available=downstream_h3_available,
            chunk_vram_budget_gb=0.0,
            max_feasible_chunks=0,
            diagnostic_message=(
                "H3 LongVideos requires an NVIDIA CUDA GPU. No CUDA device detected on this machine. "
                "This platform is GPU-READY and GPU-UNVERIFIED on the current development machine."
            ),
        )

    if len(models_found) < len(REQUIRED_WEIGHT_PATTERNS):
        missing_weights = [p for p in REQUIRED_WEIGHT_PATTERNS if p not in models_found]
        return H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.MODEL_MISSING,
            is_available=False,
            is_mock=False,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_available_gb=vram_available_gb,
            cuda_version=cuda_version,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=model_weights_path,
            models_found=models_found,
            missing_dependencies=[],
            downstream_h3_available=downstream_h3_available,
            chunk_vram_budget_gb=chunk_vram_budget_gb,
            max_feasible_chunks=max_feasible_chunks,
            diagnostic_message=(
                f"H3 LongVideos: model weight files not found in {model_weights_path}. "
                f"Missing: {missing_weights}. "
                "Download MiniMax H3 checkpoint from https://huggingface.co/MiniMaxAI/MiniMax-H3"
            ),
        )

    if vram_total_gb < 20.0:
        return H3LongVideoEnvironmentStatus(
            status_code=H3LongVideoStatusCode.INSUFFICIENT_VRAM,
            is_available=False,
            is_mock=False,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_available_gb=vram_available_gb,
            cuda_version=cuda_version,
            pytorch_version=torch_ver,
            diffusers_version=diffusers_ver,
            transformers_version=transformers_ver,
            model_weights_path=model_weights_path,
            models_found=models_found,
            missing_dependencies=[],
            downstream_h3_available=downstream_h3_available,
            chunk_vram_budget_gb=chunk_vram_budget_gb,
            max_feasible_chunks=max_feasible_chunks,
            diagnostic_message=(
                f"H3 LongVideos: insufficient VRAM ({vram_total_gb:.1f} GB). "
                "Minimum 24 GB VRAM required for a single chunk. Recommended: 48 GB."
            ),
        )

    return H3LongVideoEnvironmentStatus(
        status_code=H3LongVideoStatusCode.GPU_UNVERIFIED,
        is_available=True,
        is_mock=False,
        gpu_name=gpu_name,
        vram_total_gb=vram_total_gb,
        vram_available_gb=vram_available_gb,
        cuda_version=cuda_version,
        pytorch_version=torch_ver,
        diffusers_version=diffusers_ver,
        transformers_version=transformers_ver,
        model_weights_path=model_weights_path,
        models_found=models_found,
        missing_dependencies=[],
        downstream_h3_available=downstream_h3_available,
        chunk_vram_budget_gb=chunk_vram_budget_gb,
        max_feasible_chunks=max_feasible_chunks,
        diagnostic_message=(
            f"H3 LongVideos: REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED. "
            f"GPU detected: {gpu_name} ({vram_total_gb:.1f} GB VRAM). "
            f"Max feasible chunks per pass: {max_feasible_chunks}. "
            "GPU inference not yet physically executed on this machine."
        ),
    )
