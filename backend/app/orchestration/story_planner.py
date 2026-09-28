"""
Story and Scene Planning module for Long-Video Orchestration.
Decomposes long narrative prompts/scripts into structured scenes, characters, and world settings.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.orchestration.models import (
    CharacterProfile,
    DialogueLine,
    LongVideoMode,
    SceneDefinition,
    SceneStatus,
    StoryPlan,
    WorldSetting,
)


class StoryPlanner:
    """
    Parses natural language scripts or long prompts into a structured StoryPlan.
    Identifies characters, environment rules, scene boundaries, and dialogue.
    """

    def __init__(self, default_scene_duration: float = 5.0):
        self.default_scene_duration = default_scene_duration

    def plan_story(
        self,
        prompt_or_script: str,
        target_duration: Optional[float] = None,
        world_override: Optional[Dict[str, Any]] = None,
        characters_override: Optional[List[Dict[str, Any]]] = None,
        preferred_engine: str = "wan2gp",
    ) -> StoryPlan:
        """
        Main entry point for story planning.
        """
        clean_text = prompt_or_script.strip()
        if not clean_text:
            raise ValueError("Prompt or script cannot be empty.")

        # 1. Extract world setting
        world = self._extract_world_setting(clean_text, world_override)

        # 2. Extract characters
        characters = self._extract_characters(clean_text, characters_override)

        # 3. Break into scenes
        scenes = self._extract_scenes(clean_text, characters)

        # 4. Compute target duration
        if target_duration and target_duration > 0:
            total_duration = target_duration
            per_scene_dur = max(3.0, round(total_duration / max(1, len(scenes)), 2))
            for sc in scenes:
                sc.duration_seconds = per_scene_dur
        else:
            total_duration = sum(sc.duration_seconds for sc in scenes)

        title = self._extract_title(clean_text)
        synopsis = self._extract_synopsis(clean_text)

        return StoryPlan(
            title=title,
            synopsis=synopsis,
            target_duration_seconds=total_duration,
            characters=characters,
            world_setting=world,
            scenes=scenes,
            generation_mode=LongVideoMode.SEGMENTED_CONTINUATION,
            recommended_engine=preferred_engine,
        )

    def _extract_title(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "Untitled Project"

        title_match = re.search(r"^(?:Title|TITLE)\s*:\s*(.+)$", lines[0], re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()

        first_line = lines[0]
        if len(first_line) > 60:
            return first_line[:57] + "..."
        return first_line

    def _extract_synopsis(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""
        joined = " ".join(lines)
        return joined[:200] + ("..." if len(joined) > 200 else "")

    def _extract_world_setting(self, text: str, override: Optional[Dict[str, Any]] = None) -> WorldSetting:
        world = WorldSetting()
        if override:
            world.setting_type = override.get("setting_type", world.setting_type)
            world.environment_rules = override.get("environment_rules", world.environment_rules)
            world.lighting = override.get("lighting", world.lighting)
            world.color_palette = override.get("color_palette", world.color_palette)
            world.camera_style = override.get("camera_style", world.camera_style)
            world.era_or_genre = override.get("era_or_genre", world.era_or_genre)
            return world

        lower_text = text.lower()
        if any(w in lower_text for w in ["cyberpunk", "neon", "futuristic", "sci-fi"]):
            world.setting_type = "cyberpunk sci-fi"
            world.lighting = "moody neon backlighting, high contrast reflections"
            world.color_palette = "cyan, magenta, deep obsidian blacks"
            world.camera_style = "dynamic steady tracking shots"
            world.era_or_genre = "futuristic"
        elif any(w in lower_text for w in ["medieval", "fantasy", "castle", "knight", "dragon", "enchanted", "shrine"]):
            world.setting_type = "epic fantasy"
            world.lighting = "warm golden hour, torchlight shadows"
            world.color_palette = "earthy tones, deep amber, emerald greens"
            world.camera_style = "sweeping cinematic wide shots"
            world.era_or_genre = "fantasy"
        elif any(w in lower_text for w in ["noir", "detective", "mystery", "shadows"]):
            world.setting_type = "film noir"
            world.lighting = "dramatic chiaroscuro lighting, venetian blind shadows"
            world.color_palette = "monochromatic with high contrast silvers and blacks"
            world.camera_style = "low angle Dutch tilts, slow pans"
            world.era_or_genre = "noir"
        elif any(w in lower_text for w in ["nature", "forest", "wildlife", "ocean", "mountain"]):
            world.setting_type = "nature documentary"
            world.lighting = "pristine natural sunlight, volumetric atmospheric haze"
            world.color_palette = "vivid natural greens, sky blues, warm sunbeams"
            world.camera_style = "smooth gimbal aerials and macro zooms"
            world.era_or_genre = "documentary"
        else:
            world.setting_type = "cinematic contemporary"
            world.lighting = "natural cinematic lighting with soft key illumination"
            world.color_palette = "balanced rich colors, natural skin tones"
            world.camera_style = "smooth cinematic camera movements"
            world.era_or_genre = "contemporary"

        return world

    def _extract_characters(self, text: str, override: Optional[List[Dict[str, Any]]] = None) -> List[CharacterProfile]:
        if override:
            return [
                CharacterProfile(
                    id=c.get("id", f"char_{i+1}"),
                    name=c.get("name", f"Character {i+1}"),
                    visual_description=c.get("visual_description", ""),
                    clothing=c.get("clothing", ""),
                    voice_profile_id=c.get("voice_profile_id"),
                    voice_style=c.get("voice_style"),
                    reference_image_path=c.get("reference_image_path"),
                    personality_notes=c.get("personality_notes", ""),
                )
                for i, c in enumerate(override)
            ]

        characters: List[CharacterProfile] = []
        found_names = set()

        for raw_line in text.splitlines():
            line = raw_line.strip()
            speaker_match = re.match(r"^([A-Za-z][a-zA-Z0-9_\s]{0,20}):\s*(.+)$", line)
            if speaker_match:
                name_clean = speaker_match.group(1).strip()
                if name_clean.lower().startswith("scene") or name_clean.lower().startswith("shot") or name_clean.lower() in {"int", "ext", "title"}:
                    continue
                if name_clean not in found_names:
                    found_names.add(name_clean)
                    char_id = re.sub(r"\W+", "_", name_clean.lower()).strip("_")
                    characters.append(
                        CharacterProfile(
                            id=char_id,
                            name=name_clean,
                            visual_description=f"Distinctive appearance of {name_clean}, highly consistent facial features and build.",
                            clothing="Signature tailored outfit matching the environment",
                        )
                    )

        if not characters:
            lower = text.lower()
            if "woman" in lower or "girl" in lower or "heroine" in lower:
                characters.append(
                    CharacterProfile(
                        id="protagonist_female",
                        name="Female Protagonist",
                        visual_description="Young woman with expressive eyes, detailed facial features.",
                        clothing="Signature tailored outfit matching the environment",
                    )
                )
            elif "man" in lower or "boy" in lower or "warrior" in lower or "detective" in lower or "traveler" in lower:
                characters.append(
                    CharacterProfile(
                        id="protagonist_male",
                        name="Male Protagonist",
                        visual_description="Adult man with defined features and sharp gaze.",
                        clothing="Signature tailored outfit matching the environment",
                    )
                )
            else:
                characters.append(
                    CharacterProfile(
                        id="lead_subject",
                        name="Main Subject",
                        visual_description="Central subject with distinct, recognizable visual characteristics.",
                        clothing="Cohesive visual styling",
                    )
                )

        return characters

    def _extract_scenes(self, text: str, characters: List[CharacterProfile]) -> List[SceneDefinition]:
        scenes: List[SceneDefinition] = []

        scene_pattern = re.compile(
            r"(?:^|\n|\b)(?:\[?\s*(?:SCENE|Scene|SHOT|Shot)\s*(\d+)[\s:\-\]]+|(?:\d+)\.\s+Scene[\s:\-]+)(.*?)(?=(?:(?:\n|\s+)\[?\s*(?:SCENE|Scene|SHOT|Shot)\s*\d+|(?:\n|\s+)\d+\.\s+Scene|$))",
            re.DOTALL | re.IGNORECASE,
        )
        matches = list(scene_pattern.finditer(text))

        if matches:
            for match in matches:
                scene_num = int(match.group(1)) if match.group(1) else (len(scenes) + 1)
                scene_body = match.group(2).strip()
                scene = self._parse_single_scene_block(scene_num, scene_body, characters)
                scenes.append(scene)
        else:
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]

            if len(paragraphs) == 1:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraphs[0]) if s.strip()]
                if len(sentences) >= 2:
                    paragraphs = sentences

            for idx, p in enumerate(paragraphs, start=1):
                scene = self._parse_single_scene_block(idx, p, characters)
                scenes.append(scene)

        if not scenes:
            scenes.append(
                SceneDefinition(
                    scene_index=1,
                    title="Scene 1 - Opening",
                    visual_prompt=text,
                    action_description=text,
                    characters_present=[c.id for c in characters],
                    camera_motion="smooth cinematic pan",
                    transition_to_next="cut",
                    duration_seconds=self.default_scene_duration,
                )
            )

        return scenes

    def _parse_single_scene_block(
        self, index: int, block_text: str, characters: List[CharacterProfile]
    ) -> SceneDefinition:
        lines = [line.strip() for line in block_text.splitlines() if line.strip()]
        if not lines:
            lines = [block_text.strip()]

        title = f"Scene {index}"
        action_parts = []
        dialogue: List[DialogueLine] = []
        present_characters = set()

        for line in lines:
            diag_match = re.match(r"^([A-Za-z0-9_\s]{1,20}):\s*[\"']?(.+?)[\"']?$", line)
            if diag_match and not diag_match.group(1).lower().startswith("scene") and not diag_match.group(1).lower().startswith("shot"):
                speaker_name = diag_match.group(1).strip()
                speech_text = diag_match.group(2).strip()
                char_id = next(
                    (c.id for c in characters if c.name.lower() == speaker_name.lower() or c.id.lower() == speaker_name.lower()),
                    re.sub(r"\W+", "_", speaker_name.lower()).strip("_"),
                )
                present_characters.add(char_id)
                dialogue.append(
                    DialogueLine(
                        character_id=char_id,
                        character_name=speaker_name,
                        text=speech_text,
                    )
                )
            else:
                action_parts.append(line)
                for c in characters:
                    if re.search(rf"\b{re.escape(c.name)}\b", line, re.IGNORECASE) or re.search(rf"\b{re.escape(c.id)}\b", line, re.IGNORECASE):
                        present_characters.add(c.id)

        action_desc = " ".join(action_parts) if action_parts else block_text
        visual_prompt = action_desc

        lower_action = action_desc.lower()
        if "zoom" in lower_action:
            camera_motion = "slow camera zoom in"
        elif "pan" in lower_action:
            camera_motion = "smooth camera pan"
        elif "aerial" in lower_action or "drone" in lower_action:
            camera_motion = "sweeping aerial drone shot"
        elif "close" in lower_action or "face" in lower_action:
            camera_motion = "cinematic close-up"
        else:
            camera_motion = "subtle cinematic tracking shot"

        if not present_characters and characters:
            present_characters.add(characters[0].id)

        return SceneDefinition(
            scene_index=index,
            title=title,
            visual_prompt=visual_prompt,
            action_description=action_desc,
            characters_present=list(present_characters),
            dialogue=dialogue,
            camera_motion=camera_motion,
            transition_to_next="smooth cut",
            duration_seconds=self.default_scene_duration,
            status=SceneStatus.PENDING,
        )


class ScenePlanner(StoryPlanner):
    """Alias for ScenePlanner providing explicit scene-level decomposition methods."""
    pass
