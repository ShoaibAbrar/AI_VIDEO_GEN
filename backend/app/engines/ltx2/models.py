"""
Data models and configurations for LTX-2 Audio-Video engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class LTX2StatusCode(str, Enum):
    """Granular status codes for LTX-2 execution and environment."""
    READY = "READY"
    MOCK = "MOCK"
    GPU_UNVERIFIED = "GPU-UNVERIFIED"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    MODEL_MISSING = "MODEL_MISSING"
    INSUFFICIENT_VRAM = "INSUFFICIENT_VRAM"
    WORKER_OFFLINE = "WORKER_OFFLINE"
    ENGINE_ERROR = "ENGINE_ERROR"
    FAILED = "FAILED"


@dataclass(frozen=True)
class LTX2ModelConfig:
    """Configuration definition for an LTX-2 model variant."""
    model_type: str
    name: str
    description: str
    supports_audio: bool = True
    default_steps: int = 40
    default_guidance: float = 4.5
    default_fps: int = 25
    default_resolution: str = "1024*576"
    default_num_frames: int = 125
    audio_sample_rate: int = 44100
    repo_id: str = "DeepBeepMeep/LTX-2"
    min_vram_gb: float | None = None
    recommended_vram_gb: float | None = None


@dataclass
class LTX2GenerationRequest:
    """Normalized generation request passed to the LTX-2 pipeline."""
    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 576
    num_frames: int = 125
    fps: int = 25
    num_inference_steps: int = 40
    guidance_scale: float = 4.5
    seed: int = 42
    generate_audio: bool = True
    image_start: Optional[str] = None
    output_video_path: Optional[str] = None
    output_audio_path: Optional[str] = None
    model_type: str = "ltx-2-19b-av"
    job_id: Optional[str] = None
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LTX2GenerationResult:
    """Normalized result returned from LTX-2 execution."""
    job_id: str
    status: str
    success: bool
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    combined_media_path: Optional[str] = None
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: int = 0
    num_frames: int = 0
    has_audio: bool = False
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
