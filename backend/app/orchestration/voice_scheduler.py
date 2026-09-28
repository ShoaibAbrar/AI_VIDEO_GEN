"""
Voice and Dialogue Scheduling module for Long-Video Orchestration.
Coordinates voice profile assignment and real TTS dialogue audio synthesis for characters.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List, Optional

from app.core.logging_config import logger
from app.orchestration.media_stitcher import MediaStitcher
from app.orchestration.models import CharacterProfile, SceneDefinition
from app.services.voice.base import BaseVoiceEngine, VoiceProfile
from app.services.voice.registry import VoiceEngineRegistry, get_voice_engine_registry


class VoiceScheduler:
    """
    Schedules and generates character dialogue audio tracks for long video scenes
    using real TTS backends with persistent character voice identities.
    """

    VOICE_LIBRARY = [
        {"id": "voice_amber", "style": "warm expressive female", "voice_id": "en-US-JennyNeural"},
        {"id": "voice_marcus", "style": "deep resonant male", "voice_id": "en-US-GuyNeural"},
        {"id": "voice_narrator", "style": "authoritative documentary male", "voice_id": "en-US-ChristopherNeural"},
        {"id": "voice_aria", "style": "ethereal clear female", "voice_id": "en-US-AriaNeural"},
        {"id": "voice_kaelen", "style": "gravelly detective male", "voice_id": "en-US-EricNeural"},
        {"id": "voice_sonia", "style": "british refined female", "voice_id": "en-GB-SoniaNeural"},
        {"id": "voice_ryan", "style": "british dramatic male", "voice_id": "en-GB-RyanNeural"},
    ]

    def __init__(
        self,
        output_dir: Optional[str] = None,
        voice_registry: Optional[VoiceEngineRegistry] = None,
        media_stitcher: Optional[MediaStitcher] = None,
    ):
        self.output_dir = Path(output_dir or "./output/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.voice_registry = voice_registry or get_voice_engine_registry()
        self.media_stitcher = media_stitcher or MediaStitcher()

    def assign_voice_profiles(
        self, characters: List[CharacterProfile], default_voice_mode: str = "ai"
    ) -> List[CharacterProfile]:
        """
        Assigns persistent voice profiles and timbre to characters if not already specified.
        Guarantees that a character retains the same voice across all scenes.
        """
        used_profiles = {c.voice_profile_id for c in characters if c.voice_profile_id}

        for i, char in enumerate(characters):
            if not char.voice_profile_id:
                # Assign distinct voice from preset library
                name_lower = char.name.lower()
                if "narrat" in name_lower:
                    assigned = next((v for v in self.VOICE_LIBRARY if v["id"] == "voice_narrator"), self.VOICE_LIBRARY[2])
                elif "maya" in name_lower or "aria" in name_lower or "female" in name_lower or "woman" in name_lower:
                    assigned = next((v for v in self.VOICE_LIBRARY if v["id"] == "voice_aria"), self.VOICE_LIBRARY[0])
                elif "alex" in name_lower or "marcus" in name_lower or "kaelen" in name_lower or "male" in name_lower:
                    assigned = next((v for v in self.VOICE_LIBRARY if v["id"] == "voice_marcus"), self.VOICE_LIBRARY[1])
                else:
                    assigned = self.VOICE_LIBRARY[i % len(self.VOICE_LIBRARY)]

                char.voice_profile_id = assigned["id"]
                if not char.voice_style:
                    char.voice_style = assigned["style"]

        return characters

    async def synthesize_scene_dialogue(
        self,
        scene: SceneDefinition,
        characters: List[CharacterProfile],
        project_id: str,
        engine_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Synthesizes audible speech for all dialogue lines in a scene using the real VoiceEngine.
        Combines lines into a sequential scene dialogue audio file.
        """
        if not scene.dialogue:
            return None

        char_map: Dict[str, CharacterProfile] = {
            c.id: c for c in characters
        }
        for c in characters:
            char_map[c.name.lower()] = c
            char_map[c.id.lower()] = c

        scene_audio_dir = self.output_dir / project_id / f"scene_{scene.scene_index}"
        scene_audio_dir.mkdir(parents=True, exist_ok=True)

        voice_engine = self.voice_registry.get_engine(engine_id)

        logger.info(
            f"Synthesizing {len(scene.dialogue)} dialogue lines for Project {project_id} "
            f"Scene {scene.scene_index} via {voice_engine.engine_id}"
        )

        generated_line_paths: List[Path] = []

        for line_idx, line in enumerate(scene.dialogue, start=1):
            char = char_map.get(line.character_id) or char_map.get(line.character_id.lower()) or char_map.get(line.character_name.lower())
            voice_pid = char.voice_profile_id if char and char.voice_profile_id else "voice_amber"
            voice_style = char.voice_style if char else "natural"

            # Build formal voice profile
            profile = VoiceProfile(
                voice_profile_id=voice_pid,
                character_id=line.character_id,
                style=voice_style,
                reference_audio_path=char.reference_image_path if char else None,
            )

            # File extension depends on provider
            ext = "wav" if voice_engine.engine_id == "mock" else "mp3"
            line_audio_path = scene_audio_dir / f"line_{line_idx}_{line.character_id}.{ext}"

            # Synthesize real speech
            await voice_engine.synthesize(
                text=line.text,
                voice_profile=profile,
                output_path=line_audio_path,
            )

            line.audio_clip_path = str(line_audio_path.resolve())
            generated_line_paths.append(line_audio_path)

        # Merge dialogue lines into a combined scene audio track
        combined_ext = "wav" if voice_engine.engine_id == "mock" else "mp3"
        combined_audio_path = scene_audio_dir / f"scene_{scene.scene_index}_dialogue.{combined_ext}"

        if len(generated_line_paths) == 1:
            scene.audio_clip_path = str(generated_line_paths[0].resolve())
        else:
            self.media_stitcher.concat_audio_files(generated_line_paths, combined_audio_path)
            scene.audio_clip_path = str(combined_audio_path.resolve())

        return scene.audio_clip_path
