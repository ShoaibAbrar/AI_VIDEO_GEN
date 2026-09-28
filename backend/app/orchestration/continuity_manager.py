"""
Continuity Manager for Long-Video Orchestration.
Maintains visual, narrative, character, and environment consistency across scene boundaries.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.orchestration.models import (
    CharacterProfile,
    SceneDefinition,
    WorldSetting,
)


class ContinuityManager:
    """
    Ensures seamless narrative and visual continuity across video clips.
    Injects character identity anchors, world lighting/color constraints,
    and continuation references between sequential scenes.
    """

    def enrich_scene_prompts(
        self,
        scenes: List[SceneDefinition],
        characters: List[CharacterProfile],
        world: WorldSetting,
    ) -> List[SceneDefinition]:
        """
        Enriches each scene's prompt with character descriptions, environment aesthetics,
        and sequential continuation tags.
        """
        char_map: Dict[str, CharacterProfile] = {}
        for c in characters:
            char_map[c.id.lower()] = c
            char_map[c.name.lower()] = c
            char_map[c.id] = c
            char_map[c.name] = c

        previous_scene: Optional[SceneDefinition] = None

        for scene in scenes:
            enriched = self.build_enriched_prompt(
                scene=scene,
                char_map=char_map,
                world=world,
                previous_scene=previous_scene,
            )
            scene.enriched_prompt = enriched

            continuation_ctx = {
                "scene_index": scene.scene_index,
                "world_setting_type": world.setting_type,
                "lighting": world.lighting,
                "color_palette": world.color_palette,
                "characters": [
                    char_map[cid.lower()].name
                    for cid in scene.characters_present
                    if cid.lower() in char_map
                ],
            }

            if previous_scene:
                continuation_ctx["previous_scene_index"] = previous_scene.scene_index
                continuation_ctx["transition"] = previous_scene.transition_to_next
                if previous_scene.video_clip_path:
                    continuation_ctx["previous_clip_path"] = previous_scene.video_clip_path

            scene.continuation_context = continuation_ctx
            previous_scene = scene

        return scenes

    def build_enriched_prompt(
        self,
        scene: SceneDefinition,
        char_map: Dict[str, CharacterProfile],
        world: WorldSetting,
        previous_scene: Optional[SceneDefinition] = None,
    ) -> str:
        """
        Constructs a prompt string with continuity anchors.
        """
        prompt_parts: List[str] = []

        # 1. Base action / visual prompt
        prompt_parts.append(scene.visual_prompt.rstrip("."))

        # 2. Character visual anchors
        char_anchors = []
        for cid in scene.characters_present:
            char = char_map.get(cid.lower()) or char_map.get(cid)
            if char:
                desc = f"{char.name} ({char.visual_description}"
                if char.clothing:
                    desc += f", wearing {char.clothing}"
                desc += ")"
                char_anchors.append(desc)

        if char_anchors:
            prompt_parts.append("Characters: " + "; ".join(char_anchors))

        # 3. World and cinematic style
        style_tokens = []
        if world.lighting:
            style_tokens.append(f"lighting: {world.lighting}")
        if world.color_palette:
            style_tokens.append(f"palette: {world.color_palette}")
        if scene.camera_motion:
            style_tokens.append(f"camera: {scene.camera_motion}")
        elif world.camera_style:
            style_tokens.append(f"camera: {world.camera_style}")

        if style_tokens:
            prompt_parts.append("Visual style: " + ", ".join(style_tokens))

        # 4. Continuation anchor if following a previous scene
        if previous_scene:
            continuation_hint = (
                f"Continuous progression from Scene {previous_scene.scene_index}, "
                f"maintaining consistent visual features, environment lighting, and attire."
            )
            prompt_parts.append(continuation_hint)

        return ". ".join(prompt_parts) + "."
