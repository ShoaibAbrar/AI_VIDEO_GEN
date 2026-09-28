"""
Data models and configurations for MoneyPrinterTurbo Production Engine.
Defines schemas for topics, scripts, segments, stock materials, subtitles, audio mix, and production results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MoneyPrinterTurboStatusCode(str, Enum):
    """Diagnostic and operational status codes for MoneyPrinterTurbo."""
    READY = "READY"
    MOCK = "MOCK"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    FFMPEG_MISSING = "FFMPEG_MISSING"
    API_KEY_MISSING = "API_KEY_MISSING"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MATERIAL_PROVIDER_UNAVAILABLE = "MATERIAL_PROVIDER_UNAVAILABLE"
    VOICE_PROVIDER_UNAVAILABLE = "VOICE_PROVIDER_UNAVAILABLE"
    SCRIPT_FAILED = "SCRIPT_FAILED"
    COMPOSITION_FAILED = "COMPOSITION_FAILED"
    ENGINE_ERROR = "ENGINE_ERROR"
    FAILED = "FAILED"


class ProductionPhase(str, Enum):
    """Granular execution phases for progress telemetry."""
    INITIALIZING = "INITIALIZING"
    SCRIPT_GENERATION = "SCRIPT_GENERATION"
    VOICE_GENERATION = "VOICE_GENERATION"
    SUBTITLE_GENERATION = "SUBTITLE_GENERATION"
    MATERIAL_SEARCH = "MATERIAL_SEARCH"
    MATERIAL_DOWNLOAD = "MATERIAL_DOWNLOAD"
    VIDEO_COMPOSITION = "VIDEO_COMPOSITION"
    AUDIO_MIX = "AUDIO_MIX"
    FINAL_ENCODING = "FINAL_ENCODING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MaterialSourceType(str, Enum):
    """Material sourcing provider types."""
    PEXELS = "pexels"
    PIXABAY = "pixabay"
    LOCAL = "local"
    COMPOSITE = "composite"


class SubtitleStyle(str, Enum):
    """Subtitle visual styling modes."""
    BOTTOM_CENTER = "bottom_center"
    CENTER = "center"
    TOP_CENTER = "top_center"
    CUSTOM = "custom"


@dataclass
class MaterialInfo:
    """Metadata describing a sourced stock or local video/image asset."""
    material_id: str
    provider: str
    source_url: Optional[str] = None
    local_path: Optional[str] = None
    duration_seconds: float = 0.0
    width: int = 1920
    height: int = 1080
    author: Optional[str] = None
    license: str = "Standard Stock / Free to use"
    search_query: str = ""


@dataclass
class ScriptSegment:
    """A discrete sentence or narration beat with matched footage and voice audio."""
    segment_index: int
    text: str
    search_terms: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    start_second: float = 0.0
    end_second: float = 0.0
    audio_path: Optional[str] = None
    srt_path: Optional[str] = None
    material: Optional[MaterialInfo] = None
    rendered_clip_path: Optional[str] = None


@dataclass
class ProductionVideoPlan:
    """Compiled narrative timeline and media production blueprint."""
    title: str
    topic: str
    full_script: str
    language: str = "en"
    aspect_ratio: str = "9:16"  # 9:16 (vertical/Shorts/TikTok), 16:9 (horizontal), 1:1
    resolution: str = "1080*1920"
    fps: int = 30
    voice_name: str = "en-US-ChristopherNeural"
    voice_rate: str = "+0%"
    subtitle_enabled: bool = True
    subtitle_style: SubtitleStyle = SubtitleStyle.BOTTOM_CENTER
    music_enabled: bool = True
    music_name: Optional[str] = None
    music_volume: float = 0.20
    material_provider: MaterialSourceType = MaterialSourceType.COMPOSITE
    segments: List[ScriptSegment] = field(default_factory=list)
    total_duration_seconds: float = 0.0


@dataclass
class MoneyPrinterTurboRequest:
    """Platform-neutral production video request sent to MoneyPrinterTurbo."""
    topic: Optional[str] = None
    script: Optional[str] = None  # If provided, bypasses LLM script generation (Mode B)
    language: str = "en"
    voice_name: str = "en-US-ChristopherNeural"
    voice_rate: str = "+0%"
    target_duration_seconds: float = 30.0
    aspect_ratio: str = "9:16"  # "9:16", "16:9", "1:1"
    resolution: str = "1080*1920"
    fps: int = 30
    subtitle_enabled: bool = True
    subtitle_style: SubtitleStyle = SubtitleStyle.BOTTOM_CENTER
    music_enabled: bool = True
    music_name: Optional[str] = None
    music_volume: float = 0.20
    material_provider: MaterialSourceType = MaterialSourceType.COMPOSITE
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None
    local_material_dir: Optional[str] = None
    job_id: Optional[str] = None
    output_video_path: Optional[str] = None
    plan_only: bool = False
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MoneyPrinterTurboResult:
    """Standardized output returned from MoneyPrinterTurbo production pipeline."""
    job_id: str
    status: str
    success: bool
    output_path: Optional[str] = None
    output_files: List[str] = field(default_factory=list)
    duration: float = 0.0
    resolution: str = "1080*1920"
    fps: int = 30
    audio_present: bool = True
    subtitle_present: bool = True
    source_materials: List[Dict[str, Any]] = field(default_factory=list)
    voice: Optional[str] = None
    music: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    execution_time_seconds: float = 0.0
    engine: str = "moneyprinterturbo"
    engine_version: str = "1.2.5"
    upstream_commit: str = "c18e38ffc008cf510b66b72a08f5d023f79391ab"
    telemetry: Dict[str, Any] = field(default_factory=dict)
