"""
Data models and configurations for MiniMax H3 LongVideos Engine.
Supports sliding-window multi-chunk generation, beat parsing, and long-context continuity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class H3LongVideoStatusCode(str, Enum):
    """Diagnostic status codes for H3 LongVideos engine."""
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
    INVALID_BEAT_PLAN = "INVALID_BEAT_PLAN"


@dataclass
class LongVideoCharacterCard:
    """Character identity and visual/voice reference card."""
    character_id: str
    name: str
    description: str
    reference_image_path: Optional[str] = None
    reference_audio_path: Optional[str] = None
    voice_name: Optional[str] = None


@dataclass
class LongVideoBeat:
    """A discrete narrative beat extracted from prompt or beats script."""
    beat_index: int
    raw_text: str
    action: str
    dialogue: Optional[str] = None
    speaker: Optional[str] = None
    active_characters: List[str] = field(default_factory=list)
    duration_seconds: float = 5.0
    transition_style: str = "cut"


@dataclass
class LongVideoChunk:
    """A single sliding-window video/audio chunk in the long video timeline."""
    chunk_index: int
    start_second: float
    end_second: float
    duration_seconds: float
    num_frames: int
    prompt: str
    negative_prompt: str = ""
    active_characters: List[str] = field(default_factory=list)
    dialogue: Optional[str] = None
    speaker: Optional[str] = None
    conditioning_image_path: Optional[str] = None
    conditioning_latent_path: Optional[str] = None
    reference_image_path: Optional[str] = None
    reference_audio_path: Optional[str] = None
    seed: int = 42
    output_video_path: Optional[str] = None
    output_audio_path: Optional[str] = None
    output_combined_path: Optional[str] = None


@dataclass
class LongVideoTimelinePlan:
    """Compiled long video plan containing beat breakdown and chunk schedule."""
    title: str
    scene_description: str
    total_duration_seconds: float
    fps: int = 25
    resolution: str = "1024*576"
    chunks: List[LongVideoChunk] = field(default_factory=list)
    beats: List[LongVideoBeat] = field(default_factory=list)
    characters: Dict[str, LongVideoCharacterCard] = field(default_factory=dict)
    estimated_vram_gb: float = 24.0
    plan_only: bool = False


@dataclass
class H3LongVideoGenerationRequest:
    """Generation request for MiniMax H3 LongVideos engine."""
    prompt: str
    scene_description: str = ""
    beats_text: Optional[str] = None
    characters: List[LongVideoCharacterCard] = field(default_factory=list)
    title: str = "MiniMax H3 Long Video"
    total_duration_seconds: float = 15.0
    chunk_duration_seconds: float = 5.0
    overlap_frames: int = 0
    fps: int = 25
    resolution: str = "1024*576"
    num_inference_steps: int = 35
    guidance_scale: float = 5.0
    seed: int = 42
    generate_audio: bool = True
    enable_visual_continuity: bool = True
    enable_audio_crossfade: bool = True
    audio_crossfade_duration_seconds: float = 0.2
    plan_only: bool = False
    custom_chunks: Optional[List[LongVideoChunk]] = None
    job_id: Optional[str] = None
    output_video_path: Optional[str] = None
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class H3LongVideoGenerationResult:
    """Result returned from MiniMax H3 LongVideos execution."""
    job_id: str
    status: str
    success: bool
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    combined_media_path: Optional[str] = None
    output_paths: List[str] = field(default_factory=list)
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    plan_only: bool = False
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    telemetry: Dict[str, Any] = field(default_factory=dict)
