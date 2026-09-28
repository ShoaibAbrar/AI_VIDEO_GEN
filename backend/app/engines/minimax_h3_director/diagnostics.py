"""
Environment and Hardware Diagnostics for MiniMax H3 Director.
Evaluates CUDA, VRAM, FFmpeg, and Downstream MiniMax H3 engine availability.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_config import logger
from app.engines.minimax_h3.diagnostics import check_minimax_h3_environment
from app.engines.minimax_h3_director.models import H3DirectorStatusCode


@dataclass
class H3DirectorEnvironmentStatus:
    """Detailed diagnostic status for MiniMax H3 Director."""
    status_code: H3DirectorStatusCode
    is_available: bool
    is_mock: bool
    gpu_name: Optional[str]
    vram_total_gb: float
    vram_available_gb: float
    cuda_version: Optional[str]
    downstream_h3_available: bool
    ffmpeg_available: bool
    missing_dependencies: List[str]
    diagnostic_message: str


def check_minimax_h3_director_environment(
    checkpoints_dir: Optional[Path | str] = None,
    allow_mock: bool = False,
) -> H3DirectorEnvironmentStatus:
    """
    Evaluates system environment for MiniMax H3 Director.
    """
    # 1. Check Mock Mode
    mock_mode = (
        getattr(settings, "DEV_MOCK_ENGINE", False)
        or os.environ.get("H3_DIRECTOR_MOCK_MODE", "").lower() in ("true", "1", "yes")
        or os.environ.get("H3_MOCK_MODE", "").lower() in ("true", "1", "yes")
    )
    if mock_mode and allow_mock:
        return H3DirectorEnvironmentStatus(
            status_code=H3DirectorStatusCode.MOCK,
            is_available=True,
            is_mock=True,
            gpu_name="Simulated Mock Device (H3 Director)",
            vram_total_gb=48.0,
            vram_available_gb=48.0,
            cuda_version="mock-cuda",
            downstream_h3_available=True,
            ffmpeg_available=True,
            missing_dependencies=[],
            diagnostic_message="MiniMax H3 Director running in Development Mock Mode.",
        )

    # 2. Check FFmpeg binary
    ffmpeg_path = shutil.which("ffmpeg") or os.environ.get("FFMPEG_BINARY")
    ffmpeg_avail = bool(ffmpeg_path)

    # 3. Check Python dependencies
    missing_deps: List[str] = []
    try:
        import torch  # type: ignore
    except ImportError:
        missing_deps.append("torch")

    try:
        import diffusers  # type: ignore
    except ImportError:
        missing_deps.append("diffusers")

    try:
        import transformers  # type: ignore
    except ImportError:
        missing_deps.append("transformers")

    try:
        import soundfile  # type: ignore
    except ImportError:
        missing_deps.append("soundfile")

    if not ffmpeg_avail:
        missing_deps.append("ffmpeg")

    if missing_deps:
        return H3DirectorEnvironmentStatus(
            status_code=H3DirectorStatusCode.DEPENDENCY_MISSING,
            is_available=False,
            is_mock=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            downstream_h3_available=False,
            ffmpeg_available=ffmpeg_avail,
            missing_dependencies=missing_deps,
            diagnostic_message=f"Missing required H3 Director dependencies: {', '.join(missing_deps)}.",
        )

    # 4. Check CUDA
    import torch  # type: ignore
    if not torch.cuda.is_available():
        return H3DirectorEnvironmentStatus(
            status_code=H3DirectorStatusCode.CUDA_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name="No CUDA Device",
            vram_total_gb=0.0,
            vram_available_gb=0.0,
            cuda_version=None,
            downstream_h3_available=False,
            ffmpeg_available=ffmpeg_avail,
            missing_dependencies=[],
            diagnostic_message="No NVIDIA CUDA GPU detected on local host. A dedicated GPU worker is required for real H3 Director execution.",
        )

    gpu_name = torch.cuda.get_device_name(0)
    cuda_ver = getattr(torch.version, "cuda", "unknown")
    props = torch.cuda.get_device_properties(0)
    vram_total_gb = round(props.total_memory / (1024**3), 2)
    vram_avail_gb = round((props.total_memory - torch.cuda.memory_allocated(0)) / (1024**3), 2)

    # 5. Check downstream MiniMax H3 engine
    h3_diag = check_minimax_h3_environment(checkpoints_dir=checkpoints_dir, allow_mock=False)
    if not h3_diag.is_available and h3_diag.status_code != H3DirectorStatusCode.GPU_UNVERIFIED:
        return H3DirectorEnvironmentStatus(
            status_code=H3DirectorStatusCode.DOWNSTREAM_ENGINE_UNAVAILABLE,
            is_available=False,
            is_mock=False,
            gpu_name=gpu_name,
            vram_total_gb=vram_total_gb,
            vram_available_gb=vram_avail_gb,
            cuda_version=cuda_ver,
            downstream_h3_available=False,
            ffmpeg_available=ffmpeg_avail,
            missing_dependencies=[],
            diagnostic_message=f"Downstream MiniMax H3 engine is not available: {h3_diag.diagnostic_message}",
        )

    return H3DirectorEnvironmentStatus(
        status_code=H3DirectorStatusCode.GPU_UNVERIFIED,
        is_available=False,
        is_mock=False,
        gpu_name=gpu_name,
        vram_total_gb=vram_total_gb,
        vram_available_gb=vram_avail_gb,
        cuda_version=cuda_ver,
        downstream_h3_available=True,
        ffmpeg_available=ffmpeg_avail,
        missing_dependencies=[],
        diagnostic_message=f"CUDA and downstream H3 components detected on '{gpu_name}' ({vram_total_gb} GB VRAM). Status is GPU-UNVERIFIED until actual multi-cut CUDA generation executes.",
    )
