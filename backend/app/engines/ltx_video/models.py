"""
Data models and configurations for LTX-Video.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class LTXStatusCode(str, Enum):
    """Granular status codes for LTX-Video execution and environment."""
    READY = "READY"
    MOCK = "MOCK"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    MODEL_MISSING = "MODEL_MISSING"
    INSUFFICIENT_VRAM = "INSUFFICIENT_VRAM"
    WORKER_OFFLINE = "WORKER_OFFLINE"
    ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class LTXModelConfig:
    """Configuration definition for an LTX-Video model variant."""
    model_type: str
    name: str
    description: str
    default_steps: int = 30
    default_guidance: float = 3.0
    default_fps: int = 24
    default_resolution: str = "768*512"
    default_num_frames: int = 121
    hf_repo_id: str = "Lightricks/LTX-Video"
    weights_filename: Optional[str] = "ltx-video-2b-v0.9.safetensors"
    min_vram_gb: float = 12.0
    recommended_vram_gb: float = 24.0


@dataclass
class LTXGenerationRequest:
    """Normalized generation request passed to the LTX-Video pipeline."""
    prompt: str
    negative_prompt: str = ""
    width: int = 768
    height: int = 512
    num_frames: int = 121
    fps: int = 24
    num_inference_steps: int = 30
    guidance_scale: float = 3.0
    seed: int = 42
    image_start: Optional[str] = None
    output_path: Optional[str] = None
    model_type: str = "ltx-video-0.9.5"
    job_id: Optional[str] = None
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LTXGenerationResult:
    """Normalized result returned from LTX-Video execution."""
    job_id: str
    status: str
    success: bool
    output_path: Optional[str] = None
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: int = 0
    num_frames: int = 0
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
