"""Normalized user requirement schemas and capability mapping contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DurationMode(str, Enum):
    SHORT = "short"
    LONG = "long"
    CUSTOM = "custom"


class VoiceMode(str, Enum):
    NONE = "none"
    AI = "ai"
    HUMAN_LIKE = "human_like"
    CUSTOM_USER_VOICE = "custom_user_voice"


class CharacterMode(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"


class ContinuityLevel(str, Enum):
    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"


class QualityTier(str, Enum):
    STANDARD = "standard"
    HIGH = "high"
    CINEMATIC = "cinematic"


class GenerationStyle(str, Enum):
    CINEMATIC = "cinematic"
    REALISTIC = "realistic"
    ANIME = "anime"
    ANIMATION_3D = "3d_animation"
    FANTASY = "fantasy"
    CYBERPUNK = "cyberpunk"
    DOCUMENTARY = "documentary"
    CUSTOM = "custom"


class UserRequirements(BaseModel):
    """Normalized user-facing requirements for AI video generation."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000, description="Text description of the desired video")
    duration: DurationMode = Field(default=DurationMode.SHORT, description="Video duration tier")
    custom_seconds: float | None = Field(default=None, ge=1.0, le=120.0, description="Custom duration in seconds")
    voice_mode: VoiceMode = Field(default=VoiceMode.NONE, description="Audio and voice synthesis mode")
    audio_prompt: str | None = Field(default=None, max_length=1000, description="Optional dialogue or voice description")
    character_mode: CharacterMode = Field(default=CharacterMode.SINGLE, description="Single character vs multi-character narrative")
    continuity: ContinuityLevel = Field(default=ContinuityLevel.STANDARD, description="Scene and character continuity priority")
    quality: QualityTier = Field(default=QualityTier.HIGH, description="Visual resolution and sampling quality")
    generation_style: GenerationStyle = Field(default=GenerationStyle.CINEMATIC, description="Aesthetic style direction")
    aspect_ratio: str = Field(default="16:9", description="Target video aspect ratio")
    seed: int = Field(default=-1, ge=-1, le=2**63 - 1, description="Random seed")
    reference_image_url: str | None = Field(default=None, description="Optional URL or path to reference image")
    reference_audio_url: str | None = Field(default=None, description="Optional URL or path to reference voice audio")
    preferred_engine_id: str | None = Field(default=None, description="Optional preferred engine ID override")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Prompt cannot be blank")
        return s


class EngineEvaluation(BaseModel):
    """Evaluation of a single engine against requested requirements."""

    model_config = ConfigDict(extra="allow")

    engine_id: str
    display_name: str
    available: bool
    is_compatible: bool
    matched_capabilities: list[str]
    missing_capabilities: list[str]
    score: int
    notes: str


class GenerationPlanRead(BaseModel):
    """Deterministic and explainable plan resolving user requirements to engine execution."""

    model_config = ConfigDict(extra="allow")

    requirements: UserRequirements
    requested_capabilities: dict[str, bool]
    selected_engine_id: str | None
    selected_engine_name: str | None
    selected_model_type: str | None
    satisfies_all: bool
    reason: str
    unsupported_requirements: list[str] = Field(default_factory=list)
    fallback_options: list[EngineEvaluation] = Field(default_factory=list)
    normalized_settings: dict[str, Any]
