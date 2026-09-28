"""
Data models and configurations for MiniMax H3 Director Multi-Character Narrative Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class H3DirectorStatusCode(str, Enum):
    """Diagnostic status codes for H3 Director engine."""
    READY = "READY"
    MOCK = "MOCK"
    GPU_UNVERIFIED = "GPU-UNVERIFIED"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    MODEL_MISSING = "MODEL_MISSING"
    INSUFFICIENT_VRAM = "INSUFFICIENT_VRAM"
    DOWNSTREAM_ENGINE_UNAVAILABLE = "DOWNSTREAM_ENGINE_UNAVAILABLE"
    WORKER_OFFLINE = "WORKER_OFFLINE"
    ENGINE_ERROR = "ENGINE_ERROR"
    FAILED = "FAILED"


@dataclass
class DirectorCharacterCard:
    """Character identity and reference asset binding."""
    character_id: str
    name: str
    description: str
    reference_image_path: Optional[str] = None
    reference_audio_path: Optional[str] = None
    voice_name: Optional[str] = None
    voice_profile_id: Optional[str] = None  # VoiceCloningEngine profile ID for zero-shot cloning


@dataclass
class DirectorShotCut:
    """A discrete directed narrative shot / cut within the timeline."""
    cut_index: int
    start_second: float
    end_second: float
    duration_seconds: float
    prompt: str
    negative_prompt: str = ""
    camera_direction: str = "cinematic tracking shot"
    active_characters: List[str] = field(default_factory=list)
    dialogue: Optional[str] = None
    speaker: Optional[str] = None
    reference_image_path: Optional[str] = None
    reference_audio_path: Optional[str] = None
    seed: int = 42
    output_video_path: Optional[str] = None
    output_audio_path: Optional[str] = None


@dataclass
class DirectorTimelinePlan:
    """Compiled multi-shot directed narrative timeline."""
    title: str
    total_duration_seconds: float
    fps: int = 25
    resolution: str = "1024*576"
    cuts: List[DirectorShotCut] = field(default_factory=list)
    characters: Dict[str, DirectorCharacterCard] = field(default_factory=dict)


@dataclass
class H3DirectorGenerationRequest:
    """Generation request sent to MiniMax H3 Director."""
    prompt: str
    title: str = "Directed Cinematic Sequence"
    total_duration_seconds: float = 15.0
    fps: int = 25
    resolution: str = "1024*576"
    num_inference_steps: int = 35
    guidance_scale: float = 5.0
    seed: int = 42
    generate_audio: bool = True
    enable_visual_continuity: bool = True
    characters: List[DirectorCharacterCard] = field(default_factory=list)
    custom_cuts: Optional[List[DirectorShotCut]] = None
    job_id: Optional[str] = None
    output_video_path: Optional[str] = None
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class H3DirectorGenerationResult:
    """Platform-neutral result returned from H3 Director execution."""
    job_id: str
    status: str
    success: bool
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    combined_media_path: Optional[str] = None
    output_paths: List[str] = field(default_factory=list)
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
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
            "scenes": self.scenes,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "metadata": self.metadata,
        }
