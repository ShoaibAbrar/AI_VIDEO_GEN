"""
Voice Provider Abstraction & Engine Interfaces.
Defines base interfaces, data models, capabilities, and contracts for real TTS engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class VoiceProfile:
    """
    Persistent voice definition bound to a character.
    Guarantees consistent voice identity across scenes and shots.
    """
    voice_profile_id: str
    character_id: str = ""
    provider: str = "edge-tts"
    voice_id: str = "en-US-JennyNeural"
    language: str = "en-US"
    gender: str = "female"
    style: Optional[str] = None
    pitch: str = "+0Hz"
    rate: str = "+0%"
    reference_audio_path: Optional[str] = None
    cloning_supported: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceCapabilities:
    """Declares features supported by a specific voice provider."""
    provider_name: str
    supports_neural_tts: bool = True
    supports_voice_cloning: bool = False
    supports_pitch_rate: bool = True
    supports_multi_character: bool = True
    is_offline: bool = False
    available_voices: List[Dict[str, Any]] = field(default_factory=list)


class BaseVoiceEngine(ABC):
    """
    Abstract Base Class for all voice synthesis engines.
    """

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique identifier for this voice provider (e.g. 'edge-tts', 'pyttsx3', 'mock')."""
        pass

    @abstractmethod
    def get_capabilities(self) -> VoiceCapabilities:
        """Returns provider capabilities and supported features."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Validates that the voice engine backend is reachable/operational."""
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
    ) -> Path:
        """
        Synthesizes text into audible speech and writes to output_path.
        Returns the confirmed output audio path.
        """
        pass

    @abstractmethod
    def list_voices(self) -> List[Dict[str, Any]]:
        """Lists all available voice models/identities in this engine."""
        pass
