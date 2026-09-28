"""Deterministic, explainable capability resolver for user video requirements."""

from __future__ import annotations

from typing import Any

from app.core.logging_config import logger
from app.engines.base import BaseVideoEngine, EngineCapabilities
from app.engines.registry import VideoEngineRegistry
from app.schemas.requirements import (
    CharacterMode,
    ContinuityLevel,
    DurationMode,
    EngineEvaluation,
    GenerationPlanRead,
    GenerationStyle,
    QualityTier,
    UserRequirements,
    VoiceMode,
)


class CapabilityResolver:
    """
    Evaluates normalized UserRequirements against registered VideoEngine capabilities
    to produce a deterministic, explainable GenerationPlan.
    """

    @staticmethod
    def derive_required_capabilities(req: UserRequirements) -> dict[str, bool]:
        """Map user-level requirements into technical capability requirements."""
        is_long = req.duration == DurationMode.LONG or (
            req.duration == DurationMode.CUSTOM and (req.custom_seconds or 0) > 5.0
        )
        is_audio = req.voice_mode in (
            VoiceMode.AI,
            VoiceMode.HUMAN_LIKE,
            VoiceMode.CUSTOM_USER_VOICE,
        )
        is_voice_cond = req.voice_mode in (
            VoiceMode.HUMAN_LIKE,
            VoiceMode.CUSTOM_USER_VOICE,
        )
        is_custom_voice = req.voice_mode == VoiceMode.CUSTOM_USER_VOICE or bool(req.reference_audio_url)
        is_multi_char = req.character_mode == CharacterMode.MULTIPLE
        needs_high_continuity = req.continuity in (
            ContinuityLevel.HIGH,
            ContinuityLevel.MAXIMUM,
        )

        caps: dict[str, bool] = {
            "text_to_video": True if not req.reference_image_url else False,
            "image_to_video": True if req.reference_image_url else False,
            "video_continuation": bool(is_long or needs_high_continuity),
            "native_long_video": bool(is_long and req.duration == DurationMode.LONG),
            "audio_generation": is_audio,
            "voice_conditioning": is_voice_cond,
            "reference_image": bool(req.reference_image_url),
            "reference_audio": is_custom_voice,
            "multiple_characters": is_multi_char,
        }
        return caps

    @classmethod
    def resolve_plan(
        cls,
        requirements: UserRequirements,
        registry: VideoEngineRegistry,
        preferred_engine_id: str | None = None,
    ) -> GenerationPlanRead:
        """
        Produce a deterministic, explainable GenerationPlan for the given user requirements.
        """
        required_caps = cls.derive_required_capabilities(requirements)
        active_required = {k for k, v in required_caps.items() if v}

        # Evaluate all registered engines
        evaluations: list[EngineEvaluation] = []
        compatible_available: list[tuple[BaseVideoEngine, EngineEvaluation]] = []
        partial_available: list[tuple[BaseVideoEngine, EngineEvaluation]] = []

        for item in registry.list_engines():
            engine_id = item["engine_id"]
            engine = registry.get_engine(engine_id)
            engine_caps_dict = engine.capabilities.to_dict()
            is_avail = engine.is_available

            matched = []
            missing = []

            for cap in active_required:
                # Handle alternative long-video capability: either native_long_video or video_continuation
                if cap == "native_long_video" and not engine_caps_dict.get("native_long_video"):
                    if engine_caps_dict.get("video_continuation"):
                        matched.append("video_continuation (satisfies long video via continuation)")
                        continue
                if engine_caps_dict.get(cap, False):
                    matched.append(cap)
                else:
                    missing.append(cap)

            is_compatible = len(missing) == 0
            # Score based on matches + availability bonus + specialization
            score = len(matched) * 10 - len(missing) * 15
            if is_avail:
                score += 50
            if engine_id == preferred_engine_id:
                score += 15

            notes_parts = []
            if not is_avail:
                notes_parts.append("Engine runtime/checkpoints currently unavailable or not configured on this host.")
            if is_compatible:
                notes_parts.append("Fully satisfies all requested capabilities.")
            else:
                notes_parts.append(f"Missing required capabilities: {', '.join(missing)}.")

            eval_obj = EngineEvaluation(
                engine_id=engine_id,
                display_name=engine.display_name,
                available=is_avail,
                is_compatible=is_compatible,
                matched_capabilities=matched,
                missing_capabilities=missing,
                score=score,
                notes=" ".join(notes_parts),
            )
            evaluations.append(eval_obj)

            if is_avail and is_compatible:
                compatible_available.append((engine, eval_obj))
            elif is_avail:
                partial_available.append((engine, eval_obj))

        # Sort evaluations by score descending
        evaluations.sort(key=lambda e: e.score, reverse=True)

        selected_engine: BaseVideoEngine | None = None
        selected_model_type: str | None = None
        satisfies_all = False
        reason = ""
        unsupported_requirements: list[str] = []

        if compatible_available:
            # Pick highest scoring compatible available engine
            compatible_available.sort(key=lambda x: x[1].score, reverse=True)
            selected_engine, eval_info = compatible_available[0]
            satisfies_all = True
            reason = (
                f"Selected '{selected_engine.display_name}' because it is available and satisfies 100% "
                f"of the requested capabilities ({', '.join(eval_info.matched_capabilities)})."
            )
        elif partial_available:
            # Graceful fallback to best available engine with clear compromise notes
            partial_available.sort(key=lambda x: x[1].score, reverse=True)
            selected_engine, eval_info = partial_available[0]
            satisfies_all = False
            for miss in eval_info.missing_capabilities:
                unsupported_requirements.append(
                    f"Capability '{miss}' is not supported by available engine '{selected_engine.display_name}'."
                )
            reason = (
                f"Selected '{selected_engine.display_name}' as best available fallback. "
                f"Note that the following requested features could not be fully satisfied: {', '.join(eval_info.missing_capabilities)}."
            )
        else:
            # Fallback to default engine in registry even if offline/stubs
            try:
                selected_engine = registry.get_engine(preferred_engine_id)
            except Exception:
                selected_engine = registry.get_engine()
            satisfies_all = False
            unsupported_requirements.append("No configured video engine is currently active or installed.")
            reason = (
                f"Defaulted to '{selected_engine.display_name}' but the engine runtime is not currently ready."
            )

        # Select model type from selected engine
        if selected_engine:
            models = selected_engine.list_models()
            available_models = [m for m in models if m.get("availability", {}).get("available", False)]
            if available_models:
                selected_model_type = available_models[0].get("model_type")
            elif models:
                selected_model_type = models[0].get("model_type")
            else:
                selected_model_type = f"{selected_engine.engine_id}-default"

        # Calculate normalized settings for execution
        normalized_settings = cls._calculate_normalized_settings(requirements, selected_engine, selected_model_type)

        return GenerationPlanRead(
            requirements=requirements,
            requested_capabilities=required_caps,
            selected_engine_id=selected_engine.engine_id if selected_engine else None,
            selected_engine_name=selected_engine.display_name if selected_engine else None,
            selected_model_type=selected_model_type,
            satisfies_all=satisfies_all,
            reason=reason,
            unsupported_requirements=unsupported_requirements,
            fallback_options=evaluations,
            normalized_settings=normalized_settings,
        )

    @classmethod
    def _calculate_normalized_settings(
        cls,
        req: UserRequirements,
        engine: BaseVideoEngine | None,
        model_type: str | None,
    ) -> dict[str, Any]:
        """Convert requirements to execution parameters (steps, frames, fps, prompt style)."""
        # Duration frames mapping
        if req.duration == DurationMode.SHORT:
            frames = 17  # ~2.5 seconds at 8fps
        elif req.duration == DurationMode.LONG:
            frames = 81  # ~10+ seconds
        elif req.custom_seconds:
            frames = max(17, int(req.custom_seconds * 8))
        else:
            frames = 17

        # Quality steps mapping
        if req.quality == QualityTier.STANDARD:
            steps = 15
        elif req.quality == QualityTier.HIGH:
            steps = 25
        elif req.quality == QualityTier.CINEMATIC:
            steps = 35
        else:
            steps = 25

        # Style prompt enrichment
        prompt = req.prompt.strip()
        style_modifiers = {
            GenerationStyle.CINEMATIC: "cinematic lighting, film grain, photorealistic, 8k resolution, award-winning cinematography",
            GenerationStyle.REALISTIC: "photorealistic, natural lighting, sharp focus, 4k ultra hd",
            GenerationStyle.ANIME: "anime aesthetic, vibrant colors, makoto shinkai style, detailed illustration",
            GenerationStyle.ANIMATION_3D: "3d animated film style, pixar render style, smooth shading, ambient occlusion",
            GenerationStyle.FANTASY: "epic fantasy, ethereal glow, magical atmosphere, intricate detailing",
            GenerationStyle.CYBERPUNK: "cyberpunk city, neon lights, volumetric smoke, futuristic tech, rainy night reflections",
            GenerationStyle.DOCUMENTARY: "raw documentary footage, natural colors, authentic handheld camera style",
            GenerationStyle.CUSTOM: "",
        }
        modifier = style_modifiers.get(req.generation_style, "")
        enhanced_prompt = f"{prompt}, {modifier}" if modifier and req.generation_style != GenerationStyle.CUSTOM else prompt

        engine_id = engine.engine_id if engine else "wan2gp"

        return {
            "prompt": enhanced_prompt,
            "original_prompt": prompt,
            "model_type": model_type or "wan-t2v-1.3b",
            "video_length": frames,
            "num_inference_steps": steps,
            "seed": req.seed,
            "engine_id": engine_id,
            "aspect_ratio": req.aspect_ratio,
            "voice_mode": req.voice_mode.value,
            "audio_prompt": req.audio_prompt,
            "character_mode": req.character_mode.value,
            "continuity": req.continuity.value,
            "quality": req.quality.value,
            "generation_style": req.generation_style.value,
        }
