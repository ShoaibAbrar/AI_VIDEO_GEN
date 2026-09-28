"""
Real Neural TTS Engine using edge-tts.
Provides high-fidelity, audible character voices with persistent identities without GPU requirements.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logging_config import logger
from app.services.voice.base import BaseVoiceEngine, VoiceCapabilities, VoiceProfile


class EdgeTTSVoiceEngine(BaseVoiceEngine):
    """
    Real Microsoft Neural TTS provider.
    Synthesizes natural, emotive multi-character speech asynchronously.
    """

    VOICE_PRESETS = {
        "voice_amber": {
            "voice_id": "en-US-JennyNeural",
            "name": "Amber (Warm Expressive Female)",
            "gender": "female",
            "language": "en-US",
            "style": "warm",
        },
        "voice_marcus": {
            "voice_id": "en-US-GuyNeural",
            "name": "Marcus (Deep Resonant Male)",
            "gender": "male",
            "language": "en-US",
            "style": "resonant",
        },
        "voice_narrator": {
            "voice_id": "en-US-ChristopherNeural",
            "name": "Narrator (Authoritative Documentary Male)",
            "gender": "male",
            "language": "en-US",
            "style": "cinematic_narrator",
        },
        "voice_aria": {
            "voice_id": "en-US-AriaNeural",
            "name": "Aria (Ethereal Clear Female)",
            "gender": "female",
            "language": "en-US",
            "style": "ethereal",
        },
        "voice_kaelen": {
            "voice_id": "en-US-EricNeural",
            "name": "Kaelen (Gravelly Detective Male)",
            "gender": "male",
            "language": "en-US",
            "style": "intense",
        },
        "voice_sonia": {
            "voice_id": "en-GB-SoniaNeural",
            "name": "Sonia (British Refined Female)",
            "gender": "female",
            "language": "en-GB",
            "style": "refined",
        },
        "voice_ryan": {
            "voice_id": "en-GB-RyanNeural",
            "name": "Ryan (British Dramatic Male)",
            "gender": "male",
            "language": "en-GB",
            "style": "dramatic",
        },
        "voice_elena": {
            "voice_id": "en-US-MichelleNeural",
            "name": "Elena (Crisp Professional Female)",
            "gender": "female",
            "language": "en-US",
            "style": "professional",
        },
        "voice_leo": {
            "voice_id": "en-US-AndrewNeural",
            "name": "Leo (Energetic Young Male)",
            "gender": "male",
            "language": "en-US",
            "style": "energetic",
        },
    }

    @property
    def engine_id(self) -> str:
        return "edge-tts"

    def get_capabilities(self) -> VoiceCapabilities:
        return VoiceCapabilities(
            provider_name="edge-tts (Microsoft Neural TTS)",
            supports_neural_tts=True,
            supports_voice_cloning=False,  # EdgeTTS is neural preset based, not few-shot cloning
            supports_pitch_rate=True,
            supports_multi_character=True,
            is_offline=False,
            available_voices=self.list_voices(),
        )

    def health_check(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def list_voices(self) -> List[Dict[str, Any]]:
        return [
            {
                "profile_id": pid,
                "voice_id": pdata["voice_id"],
                "name": pdata["name"],
                "gender": pdata["gender"],
                "language": pdata["language"],
                "style": pdata["style"],
            }
            for pid, pdata in self.VOICE_PRESETS.items()
        ]

    def resolve_voice_id(self, profile: VoiceProfile) -> str:
        """Resolves profile ID or voice name to a concrete neural voice model."""
        if profile.voice_id and profile.voice_id.endswith("Neural"):
            return profile.voice_id

        pid = profile.voice_profile_id.lower()
        if pid in self.VOICE_PRESETS:
            return self.VOICE_PRESETS[pid]["voice_id"]

        # Keyword matching heuristics
        if "narrat" in pid:
            return "en-US-ChristopherNeural"
        if "detective" in pid or "kaelen" in pid or "male" in pid:
            return "en-US-EricNeural"
        if "female" in pid or "aria" in pid or "amber" in pid:
            return "en-US-JennyNeural"

        return "en-US-JennyNeural"

    async def synthesize(
        self,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
    ) -> Path:
        """
        Executes real neural speech synthesis via edge_tts.
        """
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Cannot synthesize empty dialogue text.")

        import edge_tts

        voice_id = self.resolve_voice_id(voice_profile)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Synthesizing speech via edge-tts (voice={voice_id}, pitch={voice_profile.pitch}, rate={voice_profile.rate}): {clean_text[:60]}..."
        )

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=voice_id,
            rate=voice_profile.rate or "+0%",
            pitch=voice_profile.pitch or "+0Hz",
        )

        await communicate.save(str(output_path.resolve()))

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"EdgeTTS failed to write synthesized audio to {output_path}")

        return output_path
