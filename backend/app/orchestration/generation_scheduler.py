"""
Generation Scheduler for Long-Video Orchestration.
Selects generation strategy (Mode A: Native Long Video vs Mode B: Segmented Continuation),
schedules engine jobs scene-by-scene with continuity chaining, and composites dialogue audio.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Optional

from app.core.logging_config import logger
from app.engines.base import EngineProgress
from app.engines.registry import VideoEngineRegistry, get_engine_registry
from app.orchestration.media_stitcher import MediaStitcher
from app.orchestration.models import (
    LongVideoMode,
    SceneDefinition,
    SceneStatus,
    StoryPlan,
)


class GenerationScheduler:
    """
    Schedules and executes video generation according to engine capabilities
    and performs automated audio-visual compositing for generated scenes.
    """

    def __init__(
        self,
        engine_registry: Optional[VideoEngineRegistry] = None,
        media_stitcher: Optional[MediaStitcher] = None,
    ):
        self.registry = engine_registry or get_engine_registry()
        self.media_stitcher = media_stitcher or MediaStitcher()

    def resolve_mode(self, engine_name: str, requested_duration: float, scene_count: int) -> LongVideoMode:
        """
        Determines whether to use Mode A (Native) or Mode B (Segmented Continuation).
        """
        try:
            engine = self.registry.get_engine(engine_name)
        except Exception:
            try:
                engine = self.registry.get_engine()
            except Exception:
                return LongVideoMode.SEGMENTED_CONTINUATION

        if not engine:
            return LongVideoMode.SEGMENTED_CONTINUATION

        caps = engine.capabilities
        if caps.native_long_video and scene_count <= 1:
            return LongVideoMode.NATIVE_LONG_VIDEO

        return LongVideoMode.SEGMENTED_CONTINUATION

    async def execute_scene_generation(
        self,
        scene: SceneDefinition,
        project_id: str,
        engine_name: str = "wan2gp",
        generation_settings: Optional[dict] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> SceneDefinition:
        """
        Executes generation for an individual scene using the registered BaseVideoEngine
        and combines video with synthesized dialogue audio.
        """
        scene.status = SceneStatus.GENERATING
        scene.error_message = None

        engine = self.registry.get_engine(engine_name)
        if not engine:
            scene.status = SceneStatus.FAILED
            scene.error_message = f"Engine '{engine_name}' not found in registry."
            return scene

        settings = generation_settings.copy() if generation_settings else {}
        settings["duration"] = scene.duration_seconds
        settings["scene_index"] = scene.scene_index
        settings["project_id"] = project_id
        if scene.continuation_context:
            settings["continuation"] = scene.continuation_context
            prev_frame_path = scene.continuation_context.get("previous_frame_path")
            if prev_frame_path:
                prev_frame = Path(prev_frame_path)
                if prev_frame.exists():
                    settings["image_start"] = str(prev_frame.resolve())
                    settings["reference_image"] = str(prev_frame.resolve())

        prompt_to_use = scene.enriched_prompt or scene.visual_prompt

        payload = {
            "prompt": prompt_to_use,
            "model_type": settings.get("model_type", "wan2.1_t2v_1.3B"),
            **settings,
        }

        logger.info(
            f"Starting generation for Project {project_id} Scene {scene.scene_index} "
            f"via engine '{engine_name}'."
        )

        try:
            if progress_callback:
                progress_callback(10.0, f"Preparing Scene {scene.scene_index}...")

            validated_settings = engine.validate_generation(payload)

            def _on_engine_prog(ep: EngineProgress):
                if progress_callback:
                    pct = 10.0 + (float(ep.progress or 0) * 0.8)
                    progress_callback(pct, f"Rendering Scene {scene.scene_index} ({ep.status or 'running'})")

            job_handle = engine.submit_generation(validated_settings, _on_engine_prog)

            # Wait for execution in thread to keep async loop responsive
            res = await asyncio.to_thread(engine.wait_for_result, job_handle)

            if res and res.success and res.output_files:
                raw_video_path = res.output_files[0]
                final_scene_clip = raw_video_path

                # Composite with dialogue audio if available
                if scene.audio_clip_path and Path(scene.audio_clip_path).exists():
                    try:
                        final_scene_clip = self.media_stitcher.composite_scene_video_audio(
                            video_path=raw_video_path,
                            audio_path=scene.audio_clip_path,
                        )
                    except Exception as comp_err:
                        logger.warning(f"Scene {scene.scene_index} audio composite warning: {comp_err}")
                        final_scene_clip = raw_video_path

                scene.video_clip_path = str(final_scene_clip)
                scene.status = SceneStatus.COMPLETED
                logger.info(f"Scene {scene.scene_index} successfully generated & composed: {scene.video_clip_path}")
                if progress_callback:
                    progress_callback(100.0, f"Scene {scene.scene_index} completed.")
                return scene
            else:
                scene.status = SceneStatus.FAILED
                scene.error_message = res.error_message if res else "Engine generation failed."
                logger.warning(f"Scene {scene.scene_index} generation failed: {scene.error_message}")
                return scene

        except Exception as e:
            logger.error(f"Error generating Scene {scene.scene_index}: {e}", exc_info=True)
            scene.status = SceneStatus.FAILED
            scene.error_message = str(e)
            return scene
