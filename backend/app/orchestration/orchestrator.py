"""
Long Video Orchestrator.
Master coordinator managing story decomposition, continuity enforcement,
voice synthesis, scene-by-scene generation, failure recovery, and video stitching.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.core.exceptions import AppException
from app.core.logging_config import logger
from app.engines.registry import VideoEngineRegistry, get_engine_registry
from app.orchestration.continuity_manager import ContinuityManager
from app.orchestration.generation_scheduler import GenerationScheduler
from app.orchestration.media_stitcher import MediaStitcher
from app.orchestration.models import (
    CharacterProfile,
    LongVideoMode,
    OrchestrationProgress,
    OrchestrationResult,
    OrchestrationStage,
    SceneDefinition,
    SceneStatus,
    StoryPlan,
    WorldSetting,
)
from app.orchestration.story_planner import StoryPlanner
from app.orchestration.voice_scheduler import VoiceScheduler


class LongVideoOrchestrator:
    """
    Coordinates end-to-end generation of long cohesive multi-scene videos.
    """

    def __init__(
        self,
        story_planner: Optional[StoryPlanner] = None,
        continuity_manager: Optional[ContinuityManager] = None,
        voice_scheduler: Optional[VoiceScheduler] = None,
        generation_scheduler: Optional[GenerationScheduler] = None,
        media_stitcher: Optional[MediaStitcher] = None,
        engine_registry: Optional[VideoEngineRegistry] = None,
    ):
        self.story_planner = story_planner or StoryPlanner()
        self.continuity_manager = continuity_manager or ContinuityManager()
        self.media_stitcher = media_stitcher or MediaStitcher()
        self.engine_registry = engine_registry or get_engine_registry()
        self.generation_scheduler = generation_scheduler or GenerationScheduler(
            self.engine_registry, media_stitcher=self.media_stitcher
        )
        self.voice_scheduler = voice_scheduler or VoiceScheduler(media_stitcher=self.media_stitcher)

        # In-memory progress and project tracking cache
        self._progress_cache: Dict[str, OrchestrationProgress] = {}
        self._plans_cache: Dict[str, StoryPlan] = {}

    def get_progress(self, project_id: str) -> Optional[OrchestrationProgress]:
        """Returns the current two-tier progress of a long-video project."""
        return self._progress_cache.get(project_id)

    def plan_project(
        self,
        prompt_or_script: str,
        target_duration: Optional[float] = None,
        world_override: Optional[Dict] = None,
        characters_override: Optional[List[Dict]] = None,
        preferred_engine: str = "wan2gp",
    ) -> StoryPlan:
        """
        Decomposes user input into story plan with continuity-enriched scenes.
        """
        plan = self.story_planner.plan_story(
            prompt_or_script=prompt_or_script,
            target_duration=target_duration,
            world_override=world_override,
            characters_override=characters_override,
            preferred_engine=preferred_engine,
        )

        # Assign voice profiles
        plan.characters = self.voice_scheduler.assign_voice_profiles(plan.characters)

        # Enrich scenes with continuity anchors
        plan.scenes = self.continuity_manager.enrich_scene_prompts(
            scenes=plan.scenes,
            characters=plan.characters,
            world=plan.world_setting,
        )

        # Resolve mode
        plan.generation_mode = self.generation_scheduler.resolve_mode(
            engine_name=preferred_engine,
            requested_duration=plan.target_duration_seconds,
            scene_count=len(plan.scenes),
        )

        return plan

    async def execute_project(
        self,
        project_id: str,
        plan: StoryPlan,
        generation_settings: Optional[dict] = None,
        progress_callback: Optional[Callable[[OrchestrationProgress], None]] = None,
    ) -> OrchestrationResult:
        """
        Executes the entire long-video generation pipeline for a project.
        """
        self._plans_cache[project_id] = plan
        progress = OrchestrationProgress(
            overall_progress=0.0,
            current_scene_index=0,
            total_scenes=len(plan.scenes),
            current_stage=OrchestrationStage.PLANNING,
            stage_detail="Decomposing story and preparing continuity...",
            status_message="Generating your long video...",
            active_engine=plan.recommended_engine,
            completed_scene_count=0,
        )
        self._progress_cache[project_id] = progress
        self._notify_progress(project_id, progress, progress_callback)

        total_scenes = len(plan.scenes)

        try:
            # 1. Voice synthesis stage
            progress.current_stage = OrchestrationStage.VOICE_SYNTHESIS
            progress.overall_progress = 5.0
            progress.stage_detail = "Synthesizing character dialogue and voice tracks..."
            self._notify_progress(project_id, progress, progress_callback)

            for scene in plan.scenes:
                if scene.dialogue:
                    await self.voice_scheduler.synthesize_scene_dialogue(
                        scene=scene,
                        characters=plan.characters,
                        project_id=project_id,
                    )

            # 2. Scene generation stage
            progress.current_stage = OrchestrationStage.SCENE_GENERATION
            progress.overall_progress = 10.0
            self._notify_progress(project_id, progress, progress_callback)

            for i, scene in enumerate(plan.scenes):
                # Skip already completed scenes (for resumption / retry support)
                if scene.status == SceneStatus.COMPLETED and scene.video_clip_path:
                    logger.info(f"Skipping already completed Scene {scene.scene_index}")
                    continue

                progress.current_scene_index = scene.scene_index
                progress.stage_detail = f"Generating Scene {scene.scene_index}/{total_scenes}..."
                self._notify_progress(project_id, progress, progress_callback)

                def _scene_progress_cb(pct: float, detail: str):
                    # Map scene 0..100% to overall 10..85%
                    scene_share = 75.0 / max(1, total_scenes)
                    base = 10.0 + (i * scene_share)
                    progress.overall_progress = min(85.0, base + (pct * scene_share / 100.0))
                    progress.stage_detail = detail
                    self._notify_progress(project_id, progress, progress_callback)

                updated_scene = await self.generation_scheduler.execute_scene_generation(
                    scene=scene,
                    project_id=project_id,
                    engine_name=plan.recommended_engine,
                    generation_settings=generation_settings,
                    progress_callback=_scene_progress_cb,
                )

                if updated_scene.status == SceneStatus.FAILED:
                    progress.current_stage = OrchestrationStage.FAILED
                    progress.stage_detail = f"Failed at Scene {scene.scene_index}: {updated_scene.error_message}"
                    self._notify_progress(project_id, progress, progress_callback)
                    return OrchestrationResult(
                        project_id=project_id,
                        status=OrchestrationStage.FAILED,
                        scenes=plan.scenes,
                        error_message=f"Scene {scene.scene_index} generation failed: {updated_scene.error_message}",
                    )

                # Visual continuity: extract final frame from completed scene to condition next scene
                if updated_scene.video_clip_path and Path(updated_scene.video_clip_path).exists():
                    try:
                        final_frame = self.media_stitcher.extract_last_frame(updated_scene.video_clip_path)
                        if i + 1 < len(plan.scenes):
                            next_scene = plan.scenes[i + 1]
                            next_scene.continuation_context["previous_clip_path"] = str(updated_scene.video_clip_path)
                            next_scene.continuation_context["previous_frame_path"] = str(final_frame.resolve())
                            next_scene.continuation_context["previous_scene_index"] = scene.scene_index
                            logger.info(
                                f"Extracted visual continuity frame from Scene {scene.scene_index} "
                                f"for Scene {next_scene.scene_index}: {final_frame}"
                            )
                    except Exception as frame_err:
                        logger.warning(
                            f"Could not extract visual continuity frame for Scene {scene.scene_index}: {frame_err}"
                        )

                progress.completed_scene_count += 1

            # 3. Stitching stage
            progress.current_stage = OrchestrationStage.STITCHING
            progress.overall_progress = 90.0
            progress.stage_detail = "Assembling scenes into unified final video..."
            self._notify_progress(project_id, progress, progress_callback)

            final_video_path = self.media_stitcher.stitch_scenes(
                scenes=plan.scenes,
                project_id=project_id,
            )

            # 4. Completed
            progress.current_stage = OrchestrationStage.COMPLETED
            progress.overall_progress = 100.0
            progress.stage_detail = "Long video generation completed successfully."
            progress.status_message = "Your long video is ready!"
            self._notify_progress(project_id, progress, progress_callback)

            return OrchestrationResult(
                project_id=project_id,
                final_video_path=final_video_path,
                status=OrchestrationStage.COMPLETED,
                scenes=plan.scenes,
                duration_seconds=sum(s.duration_seconds for s in plan.scenes),
            )

        except Exception as e:
            logger.error(f"Long-video orchestration failed for project {project_id}: {e}", exc_info=True)
            progress.current_stage = OrchestrationStage.FAILED
            progress.stage_detail = f"Orchestration error: {str(e)}"
            self._notify_progress(project_id, progress, progress_callback)
            return OrchestrationResult(
                project_id=project_id,
                status=OrchestrationStage.FAILED,
                scenes=plan.scenes,
                error_message=str(e),
            )

    async def retry_scene(
        self,
        project_id: str,
        scene_index: int,
        generation_settings: Optional[dict] = None,
        progress_callback: Optional[Callable[[OrchestrationProgress], None]] = None,
    ) -> OrchestrationResult:
        """
        Retries generation for a single failed scene and re-stitches final video without losing completed scenes.
        """
        plan = self._plans_cache.get(project_id)
        if not plan:
            raise AppException(status_code=404, message=f"Project plan for '{project_id}' not found.")

        target_scene = next((s for s in plan.scenes if s.scene_index == scene_index), None)
        if not target_scene:
            raise AppException(status_code=404, message=f"Scene {scene_index} not found in project {project_id}.")

        logger.info(f"Retrying Scene {scene_index} for project {project_id} (retry #{target_scene.retry_count + 1})")
        target_scene.retry_count += 1
        target_scene.status = SceneStatus.PENDING
        target_scene.error_message = None

        return await self.execute_project(
            project_id=project_id,
            plan=plan,
            generation_settings=generation_settings,
            progress_callback=progress_callback,
        )

    async def resume_project(
        self,
        project_id: str,
        generation_settings: Optional[dict] = None,
        progress_callback: Optional[Callable[[OrchestrationProgress], None]] = None,
    ) -> OrchestrationResult:
        """
        Resumes a project from the first uncompleted or failed scene.
        """
        plan = self._plans_cache.get(project_id)
        if not plan:
            raise AppException(status_code=404, message=f"Project plan for '{project_id}' not found.")

        logger.info(f"Resuming project {project_id} execution.")
        return await self.execute_project(
            project_id=project_id,
            plan=plan,
            generation_settings=generation_settings,
            progress_callback=progress_callback,
        )

    def _notify_progress(
        self,
        project_id: str,
        progress: OrchestrationProgress,
        cb: Optional[Callable[[OrchestrationProgress], None]],
    ):
        self._progress_cache[project_id] = progress
        if cb:
            try:
                cb(progress)
            except Exception as e:
                logger.warning(f"Error in orchestration progress callback: {e}")


_global_orchestrator: Optional[LongVideoOrchestrator] = None


def get_long_video_orchestrator() -> LongVideoOrchestrator:
    """Singleton getter for LongVideoOrchestrator."""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = LongVideoOrchestrator()
    return _global_orchestrator
