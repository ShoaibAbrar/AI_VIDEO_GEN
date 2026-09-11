"""API schemas for generation jobs."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerationStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GenerationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, max_length=4000)
    model_type: str = Field(..., min_length=1, max_length=255)
    video_length: int = Field(..., ge=1, le=9999)
    num_inference_steps: int = Field(..., ge=1, le=100)
    seed: int = Field(-1, ge=-1, le=2**63 - 1)

    @field_validator("prompt", "model_type")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class GenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: GenerationStatus
    prompt: str
    model_type: str
    generation_settings: dict[str, Any]
    progress: int | None = None
    current_step: int | None = None
    total_steps: int | None = None
    phase: str | None = None
    status_text: str | None = None
    output_available: bool = False
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ModelMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_type: str
    name: str
    description: str | None = None
    availability: dict[str, Any] | None = None


class GenerationCancelResponse(BaseModel):
    id: str
    status: GenerationStatus
