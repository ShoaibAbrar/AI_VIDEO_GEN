"""Voice synthesis and character dialogue services."""

from app.services.voice.base import BaseVoiceEngine, VoiceCapabilities, VoiceProfile
from app.services.voice.edge_tts_engine import EdgeTTSVoiceEngine
from app.services.voice.mock_voice_engine import MockVoiceEngine
from app.services.voice.registry import VoiceEngineRegistry, get_voice_engine_registry

__all__ = [
    "BaseVoiceEngine",
    "VoiceCapabilities",
    "VoiceProfile",
    "EdgeTTSVoiceEngine",
    "MockVoiceEngine",
    "VoiceEngineRegistry",
    "get_voice_engine_registry",
]
