"""
Voice Cloning & Custom Voice Subsystem Package.
Provides zero-shot reference voice cloning, speaker embedding extraction,
persistent voice profile storage, and multi-character dialogue synthesis.
"""

from app.services.voice.cloning.models import (
    AudioValidationErrorCode,
    AudioValidationResult,
    VoiceCloningRequest,
    VoiceCloningResult,
    VoiceCloningStatusCode,
    VoiceProfile,
)
from app.services.voice.cloning.diagnostics import (
    VoiceCloningEnvironmentStatus,
    check_voice_cloning_environment,
)
from app.services.voice.cloning.validation import validate_reference_audio
from app.services.voice.cloning.storage import VoiceProfileStore
from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
from app.services.voice.cloning.engine import VoiceCloningEngine

__all__ = [
    "AudioValidationErrorCode",
    "AudioValidationResult",
    "VoiceCloningRequest",
    "VoiceCloningResult",
    "VoiceCloningStatusCode",
    "VoiceProfile",
    "VoiceCloningEnvironmentStatus",
    "check_voice_cloning_environment",
    "validate_reference_audio",
    "VoiceProfileStore",
    "ChatterboxVoiceCloningRunner",
    "VoiceCloningEngine",
]
