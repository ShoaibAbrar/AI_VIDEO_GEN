"""
Pydantic schemas for Long-Video Orchestration API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.orchestration.models import LongVideoMode, OrchestrationStage, SceneStatus


class WorldSettingSchema(BaseModel):
    setting_type: str = "cinematic contemporary"
    environment_rules: str = ""
    lighting: str = "natural cinematic lighting"
    color_palette: str = "balanced rich colors"
    camera_style: str = "smooth cinematic camera movements"
    era_or_genre: str = "contemporary"


class CharacterProfileSchema(BaseModel):
    id: str
    name: str
    visual_description: str
    clothing: str = ""
    voice_profile_id: Optional[str] = None
    voice_style: Optional[str] = None
    reference_image_path: Optional[str] = None
    personality_notes: str = ""


class DialogueLineSchema(BaseModel):
    character_id: str
    character_name: str
    text: str
    emotion: str = "neutral"
    audio_clip_path: Optional[str] = None


class SceneDefinitionSchema(BaseModel):
    scene_index: int
    title: str
    visual_prompt: str
    action_description: Optional[str] = ""
    characters_present: List[str] = Field(default_factory=list)
    dialogue: List[DialogueLineSchema] = Field(default_factory=list)
    camera_motion: str = "static"
    transition_to_next: str = "cut"
    duration_seconds: float = 5.0
    enriched_prompt: Optional[str] = None
    status: SceneStatus = SceneStatus.PENDING
    video_clip_path: Optional[str] = None
    audio_clip_path: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class StoryPlanResponse(BaseModel):
    title: str
    synopsis: str
    target_duration_seconds: float
    characters: List[CharacterProfileSchema]
    world_setting: WorldSettingSchema
    scenes: List[SceneDefinitionSchema]
    generation_mode: LongVideoMode
    recommended_engine: str


class LongVideoPlanRequest(BaseModel):
    prompt: str = Field(..., min_length=5, description="Full script or narrative long prompt.")
    target_duration: Optional[float] = Field(None, ge=3.0, description="Desired total duration in seconds.")
    world_override: Optional[Dict[str, Any]] = None
    characters_override: Optional[List[Dict[str, Any]]] = None
    preferred_engine: Optional[str] = "wan2gp"


class LongVideoCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=5, description="Full script or narrative long prompt.")
    title: Optional[str] = None
    target_duration: Optional[float] = Field(None, ge=3.0)
    world_override: Optional[Dict[str, Any]] = None
    characters_override: Optional[List[Dict[str, Any]]] = None
    preferred_engine: Optional[str] = "wan2gp"
    generation_settings: Optional[Dict[str, Any]] = None


class LongVideoProjectResponse(BaseModel):
    id: str
    user_id: int
    title: str
    prompt: str
    synopsis: Optional[str] = None
    status: OrchestrationStage
    generation_mode: LongVideoMode
    engine_name: str
    world_setting: Dict[str, Any]
    characters: List[Dict[str, Any]]
    total_scenes: int
    current_scene: int
    progress_percent: float
    status_text: Optional[str] = None
    output_video_path: Optional[str] = None
    error_message: Optional[str] = None
    scenes: List[SceneDefinitionSchema] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LongVideoProgressResponse(BaseModel):
    overall_progress: float
    current_scene_index: int
    total_scenes: int
    current_stage: OrchestrationStage
    stage_detail: str
    status_message: str
    active_engine: str
    completed_scene_count: int
