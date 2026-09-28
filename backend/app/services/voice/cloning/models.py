"""
Data models and schemas for Voice Cloning & Custom Voice Subsystem.
Supports zero-shot reference audio cloning, persistent voice profiles, and paralinguistic controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


class VoiceCloningStatusCode(str, Enum):
    """Operational and diagnostic status codes for Voice Cloning engine."""
    READY = "READY"
    MOCK = "MOCK"
    MODEL_MISSING = "MODEL_MISSING"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"
    GPU_UNVERIFIED = "GPU-UNVERIFIED"
    INSUFFICIENT_VRAM = "INSUFFICIENT_VRAM"
    REFERENCE_INVALID = "REFERENCE_INVALID"
    VOICE_PROFILE_MISSING = "VOICE_PROFILE_MISSING"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    WORKER_OFFLINE = "WORKER_OFFLINE"
    ENGINE_ERROR = "ENGINE_ERROR"
    FAILED = "FAILED"


class AudioValidationErrorCode(str, Enum):
    """Specific error codes for reference audio validation failures."""
    VALID = "VALID"
    REFERENCE_AUDIO_TOO_SHORT = "REFERENCE_AUDIO_TOO_SHORT"
    REFERENCE_AUDIO_TOO_LONG = "REFERENCE_AUDIO_TOO_LONG"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
    CLIPPING_DETECTED = "CLIPPING_DETECTED"
    EXCESSIVE_NOISE = "EXCESSIVE_NOISE"
    MULTIPLE_SPEAKERS_DETECTED = "MULTIPLE_SPEAKERS_DETECTED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    TRANSCRIPT_REQUIRED = "TRANSCRIPT_REQUIRED"
    TRANSCRIPT_MISMATCH = "TRANSCRIPT_MISMATCH"


@dataclass
class AudioValidationResult:
    """Detailed diagnostic result of reference audio verification."""
    is_valid: bool
    error_code: AudioValidationErrorCode
    error_message: str
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 1
    rms_loudness_db: float = 0.0
    has_clipping: bool = False
    consent_confirmed: bool = False


@dataclass
class VoiceProfile:
    """
    Persistent voice profile representing an authorized, cloned, or preset speaker identity.
    Persists across projects, scenes, and video engine generations.
    """
    id: str = field(default_factory=lambda: f"vp_{uuid.uuid4().hex[:12]}")
    name: str = "Custom Cloned Voice"
    owner_id: str = "default_user"
    reference_audio_path: Optional[str] = None
    reference_transcript: Optional[str] = None
    language: str = "en"
    engine: str = "chatterbox"
    model_id: str = "resemble-ai/chatterbox-multilingual"
    speaker_embedding_path: Optional[str] = None
    gender: str = "neutral"
    consent_confirmed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "reference_audio_path": self.reference_audio_path,
            "reference_transcript": self.reference_transcript,
            "language": self.language,
            "engine": self.engine,
            "model_id": self.model_id,
            "speaker_embedding_path": self.speaker_embedding_path,
            "gender": self.gender,
            "consent_confirmed": self.consent_confirmed,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VoiceProfile:
        created_raw = data.get("created_at")
        updated_raw = data.get("updated_at")
        created_dt = datetime.fromisoformat(created_raw) if created_raw else datetime.now(timezone.utc)
        updated_dt = datetime.fromisoformat(updated_raw) if updated_raw else datetime.now(timezone.utc)

        return cls(
            id=data.get("id", f"vp_{uuid.uuid4().hex[:12]}"),
            name=data.get("name", "Custom Cloned Voice"),
            owner_id=data.get("owner_id", "default_user"),
            reference_audio_path=data.get("reference_audio_path"),
            reference_transcript=data.get("reference_transcript"),
            language=data.get("language", "en"),
            engine=data.get("engine", "chatterbox"),
            model_id=data.get("model_id", "resemble-ai/chatterbox-multilingual"),
            speaker_embedding_path=data.get("speaker_embedding_path"),
            gender=data.get("gender", "neutral"),
            consent_confirmed=bool(data.get("consent_confirmed", False)),
            created_at=created_dt,
            updated_at=updated_dt,
            metadata=data.get("metadata", {}),
        )


@dataclass
class VoiceCloningRequest:
    """Request payload for synthesizing speech with a cloned voice profile."""
    text: str
    voice_profile_id: Optional[str] = None
    voice_profile: Optional[VoiceProfile] = None
    reference_audio_path: Optional[str] = None
    reference_transcript: Optional[str] = None
    language: str = "en"
    emotion: Optional[str] = None  # e.g. "happy", "serious", "dramatic"
    speed: float = 1.0
    pitch: float = 0.0
    exaggeration: float = 0.0  # Chatterbox creative emotion/prosody exaggeration
    cfg_weight: float = 0.5    # Classifier-Free Guidance weight
    paralinguistic_tags: bool = True  # Supports [laugh], [sigh], [gasp], [whisper]
    output_audio_path: Optional[str] = None
    job_id: Optional[str] = None
    plan_only: bool = False
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceCloningResult:
    """Standardized response from Voice Cloning Engine."""
    job_id: str
    status: str
    success: bool
    audio_path: Optional[str] = None
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    channels: int = 1
    voice_profile_id: Optional[str] = None
    voice_name: Optional[str] = None
    language: str = "en"
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    execution_time_seconds: float = 0.0
    telemetry: Dict[str, Any] = field(default_factory=dict)
