"""
Core MiniMax H3 Multimodal Engine Data Models and Status Codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MiniMaxH3StatusCode(str, Enum):
    """Granular diagnostic status codes for MiniMax H3 engine."""
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


class MiniMaxH3TaskType(str, Enum):
    """Core operating tasks for MiniMax H3."""
    T2VA = "T2VA"      # Text-to-Video-Audio
    FL2VA = "FL2VA"    # First/Last-frame to Video-Audio
    REF2VA = "REF2VA"  # Reference-conditioned Video-Audio


@dataclass(frozen=True)
class MiniMaxH3ModelConfig:
    """Configuration definition for MiniMax H3 models."""
    model_type: str
    name: str
    description: str
    supports_audio: bool = True
    default_steps: int = 35
    default_guidance: float = 5.0
    default_fps: int = 25
    default_resolution: str = "1024*576"
    default_num_frames: int = 125
    audio_sample_rate: int = 32000
    repo_id: str = "MiniMaxAI/MiniMax-H3"
    min_vram_gb: float = 24.0
    recommended_vram_gb: float = 48.0


@dataclass
class MiniMaxH3GenerationRequest:
    """Normalized generation request passed to the MiniMax H3 inference runner."""
    prompt: str
    negative_prompt: str = ""
    task_type: MiniMaxH3TaskType = MiniMaxH3TaskType.T2VA
    width: int = 1024
    height: int = 576
    num_frames: int = 125
    fps: int = 25
    num_inference_steps: int = 35
    guidance_scale: float = 5.0
    seed: int = 42
    generate_audio: bool = True
    image_start: Optional[str] = None
    image_end: Optional[str] = None
    reference_images: List[str] = field(default_factory=list)
    reference_audios: List[str] = field(default_factory=list)
    reference_videos: List[str] = field(default_factory=list)
    output_video_path: Optional[str] = None
    output_audio_path: Optional[str] = None
    model_type: str = "minimax-h3-v1"
    job_id: Optional[str] = None
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MiniMaxH3GenerationResult:
    """Platform-neutral result returned from MiniMax H3 execution."""
    job_id: str
    status: str
    success: bool
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    combined_media_path: Optional[str] = None
    output_paths: List[str] = field(default_factory=list)
    text: Optional[str] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    sample_rate: Optional[int] = None
    num_frames: Optional[int] = None
    has_audio: bool = False
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "success": self.success,
            "video_path": self.video_path,
            "audio_path": self.audio_path,
            "combined_media_path": self.combined_media_path,
            "output_paths": self.output_paths or ([self.video_path] if self.video_path else []),
            "text": self.text,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "sample_rate": self.sample_rate,
            "num_frames": self.num_frames,
            "has_audio": self.has_audio,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "metadata": self.metadata,
        }
