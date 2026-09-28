"""
VoiceCloningEngine implementing BaseVoiceEngine.
Provides seamless integration of zero-shot voice cloning into GenVid.AI's voice subsystem.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.core.logging_config import logger
from app.services.voice.base import BaseVoiceEngine, VoiceCapabilities, VoiceProfile as BaseVoiceProfile
from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
from app.services.voice.cloning.models import (
    AudioValidationResult,
    VoiceCloningRequest,
    VoiceCloningResult,
    VoiceProfile,
)
from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
from app.services.voice.cloning.storage import VoiceProfileStore
from app.services.voice.cloning.validation import validate_reference_audio


class VoiceCloningEngine(BaseVoiceEngine):
    """
    Real Zero-Shot Voice Cloning Engine using Chatterbox architecture.
    Provides authorized custom voice creation and high-fidelity speech synthesis.
    """

    def __init__(
        self,
        runner: Optional[ChatterboxVoiceCloningRunner] = None,
        profile_store: Optional[VoiceProfileStore] = None,
    ):
        self.profile_store = profile_store or VoiceProfileStore()
        self.runner = runner or ChatterboxVoiceCloningRunner(profile_store=self.profile_store)

    @property
    def engine_id(self) -> str:
        return "voice-cloning"

    def get_capabilities(self) -> VoiceCapabilities:
        diag = check_voice_cloning_environment()
        return VoiceCapabilities(
            provider_name="Chatterbox Zero-Shot Voice Cloning (Resemble AI)",
            supports_neural_tts=True,
            supports_voice_cloning=True,
            supports_pitch_rate=True,
            supports_multi_character=True,
            is_offline=True,
            available_voices=self.list_voices(),
        )

    def health_check(self) -> bool:
        return self.runner.is_ready()

    async def synthesize(
        self,
        text: str,
        voice_profile: BaseVoiceProfile,
        output_path: Path,
    ) -> Path:
        """
        Synthesizes speech using the provided VoiceProfile.
        Adheres to BaseVoiceEngine contract for drop-in platform compatibility.
        """
        # Map BaseVoiceProfile to VoiceCloningRequest
        req = VoiceCloningRequest(
            text=text,
            voice_profile_id=voice_profile.voice_profile_id,
            reference_audio_path=voice_profile.reference_audio_path,
            language=voice_profile.language or "en",
            speed=1.0,
            output_audio_path=str(output_path.resolve()),
            extra_options={"consent_confirmed": True},
        )

        # Run synthesis in background executor thread
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, self.runner.execute_cloning, req)

        if not res.success:
            raise RuntimeError(f"Voice cloning synthesis failed: {res.error_message}")

        return Path(res.audio_path) if res.audio_path else output_path

    def clone_voice(self, request: VoiceCloningRequest) -> VoiceCloningResult:
        """Synchronous cloning entry point for direct API / worker execution."""
        return self.runner.execute_cloning(request)

    def create_voice_profile(
        self,
        name: str,
        reference_audio_path: str | Path,
        owner_id: str = "default_user",
        reference_transcript: Optional[str] = None,
        language: str = "en",
        gender: str = "neutral",
        consent_confirmed: bool = False,
    ) -> VoiceProfile:
        """
        Validates reference audio & consent, then creates a persistent VoiceProfile.
        """
        val = validate_reference_audio(reference_audio_path, consent_confirmed=consent_confirmed)
        if not val.is_valid:
            raise ValueError(f"Reference audio validation failed: {val.error_message}")

        return self.profile_store.create_profile(
            name=name,
            reference_audio_path=reference_audio_path,
            owner_id=owner_id,
            reference_transcript=reference_transcript,
            language=language,
            gender=gender,
            consent_confirmed=consent_confirmed,
        )

    def get_voice_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        return self.profile_store.get_profile(profile_id)

    def list_voice_profiles(self, owner_id: Optional[str] = None) -> List[VoiceProfile]:
        return self.profile_store.list_profiles(owner_id=owner_id)

    def delete_voice_profile(self, profile_id: str) -> bool:
        return self.profile_store.delete_profile(profile_id)

    def validate_reference(
        self,
        audio_path: str | Path,
        consent_confirmed: bool = False,
    ) -> AudioValidationResult:
        return validate_reference_audio(audio_path, consent_confirmed=consent_confirmed)

    def list_voices(self) -> List[Dict[str, Any]]:
        """Returns all persistent cloned voice profiles registered in this engine."""
        profiles = self.profile_store.list_profiles()
        return [
            {
                "voice_id": p.id,
                "name": p.name,
                "language": p.language,
                "gender": p.gender,
                "is_custom_cloned": True,
                "reference_audio_present": bool(p.reference_audio_path),
                "created_at": p.created_at.isoformat(),
            }
            for p in profiles
        ]
