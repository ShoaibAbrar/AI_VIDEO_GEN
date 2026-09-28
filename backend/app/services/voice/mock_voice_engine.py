"""
Mock Voice Engine for headless test environments.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from app.services.voice.base import BaseVoiceEngine, VoiceCapabilities, VoiceProfile


class MockVoiceEngine(BaseVoiceEngine):
    """
    Simulated Voice Engine for offline / CI tests.
    Writes a standard 44-byte WAV header without making network or GPU calls.
    """

    @property
    def engine_id(self) -> str:
        return "mock"

    def get_capabilities(self) -> VoiceCapabilities:
        return VoiceCapabilities(
            provider_name="Mock Dev Engine",
            supports_neural_tts=False,
            supports_voice_cloning=False,
            supports_pitch_rate=False,
            supports_multi_character=True,
            is_offline=True,
            available_voices=[{"profile_id": "mock_voice", "name": "Mock Test Voice"}],
        )

    def health_check(self) -> bool:
        return True

    def list_voices(self) -> List[Dict[str, Any]]:
        return [{"profile_id": "mock_voice", "name": "Mock Voice"}]

    async def synthesize(
        self,
        text: str,
        voice_profile: VoiceProfile,
        output_path: Path,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # 44-byte standard silent WAV header
        wav_header = bytes([
            0x52, 0x49, 0x46, 0x46,  # "RIFF"
            0x24, 0x00, 0x00, 0x00,  # File size - 8
            0x57, 0x41, 0x56, 0x45,  # "WAVE"
            0x66, 0x6D, 0x74, 0x20,  # "fmt "
            0x10, 0x00, 0x00, 0x00,  # Subchunk1Size (16 for PCM)
            0x01, 0x00,              # AudioFormat (1 for PCM)
            0x01, 0x00,              # NumChannels (1 mono)
            0x44, 0xAC, 0x00, 0x00,  # SampleRate (44100 Hz)
            0x88, 0x58, 0x01, 0x00,  # ByteRate (44100 * 2)
            0x02, 0x00,              # BlockAlign (2)
            0x10, 0x00,              # BitsPerSample (16)
            0x64, 0x61, 0x74, 0x61,  # "data"
            0x00, 0x00, 0x00, 0x00   # Subchunk2Size (0 bytes of data)
        ])
        output_path.write_bytes(wav_header)
        return output_path
