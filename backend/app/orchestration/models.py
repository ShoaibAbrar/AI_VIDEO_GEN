"""
Data models and representations for Long-Video Orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LongVideoMode(str, Enum):
    """
    Mode A: Native long-video generation (engine natively renders long continuous timeline).
    Mode B: Segmented generation with automatic continuation (engine renders scene clips with continuity chaining).
    """
    NATIVE_LONG_VIDEO = "NATIVE_LONG_VIDEO"
    SEGMENTED_CONTINUATION = "SEGMENTED_CONTINUATION"


class OrchestrationStage(str, Enum):
    """Lifecycle stages of a long video project."""
    PLANNING = "PLANNING"
    VOICE_SYNTHESIS = "VOICE_SYNTHESIS"
    SCENE_GENERATION = "SCENE_GENERATION"
    STITCHING = "STITCHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SceneStatus(str, Enum):
    """Status for an individual scene."""
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class CharacterProfile:
    """Character definition maintaining visual and voice identity across scenes."""
    id: str
    name: str
    visual_description: str
    clothing: str = ""
    voice_profile_id: Optional[str] = None
    voice_style: Optional[str] = None
    reference_image_path: Optional[str] = None
    personality_notes: str = ""


@dataclass
class WorldSetting:
    """World and environment rules ensuring consistent background, lighting, and palette."""
    setting_type: str = "cinematic"
    environment_rules: str = ""
    lighting: str = "natural cinematic lighting"
    color_palette: str = "natural vibrant"
    camera_style: str = "smooth cinematic camera movements"
    era_or_genre: str = "contemporary"


@dataclass
class DialogueLine:
    """A line of character dialogue within a scene."""
    character_id: str
    character_name: str
    text: str
    emotion: str = "neutral"
    audio_clip_path: Optional[str] = None


@dataclass
class SceneDefinition:
    """Complete specification of a single scene/shot."""
    scene_index: int
    title: str
    visual_prompt: str
    action_description: str = ""
    characters_present: List[str] = field(default_factory=list)
    dialogue: List[DialogueLine] = field(default_factory=list)
    camera_motion: str = "static"
    transition_to_next: str = "cut"
    duration_seconds: float = 5.0
    enriched_prompt: Optional[str] = None
    continuation_context: Dict[str, Any] = field(default_factory=dict)
    status: SceneStatus = SceneStatus.PENDING
    video_clip_path: Optional[str] = None
    audio_clip_path: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class StoryPlan:
    """Structured breakdown of a user prompt into world rules, character roster, and sequential scenes."""
    title: str
    synopsis: str
    target_duration_seconds: float
    characters: List[CharacterProfile] = field(default_factory=list)
    world_setting: WorldSetting = field(default_factory=WorldSetting)
    scenes: List[SceneDefinition] = field(default_factory=list)
    generation_mode: LongVideoMode = LongVideoMode.SEGMENTED_CONTINUATION
    recommended_engine: str = "wan2gp"


@dataclass
class OrchestrationProgress:
    """Two-tier progress reporting containing high-level user messages and low-level scene progress."""
    overall_progress: float = 0.0
    current_scene_index: int = 0
    total_scenes: int = 0
    current_stage: OrchestrationStage = OrchestrationStage.PLANNING
    stage_detail: str = ""
    status_message: str = "Generating your long video..."
    active_engine: str = "wan2gp"
    completed_scene_count: int = 0


@dataclass
class OrchestrationResult:
    """Result of an orchestration execution."""
    project_id: str
    final_video_path: Optional[str] = None
    status: OrchestrationStage = OrchestrationStage.COMPLETED
    scenes: List[SceneDefinition] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
