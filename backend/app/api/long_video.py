"""
API Endpoints for Long-Video Orchestration.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.db.database import SessionLocal, get_db
from app.models.long_video import LongVideoProject, LongVideoScene
from app.models.user import User
from app.orchestration import (
    LongVideoMode,
    LongVideoOrchestrator,
    OrchestrationProgress,
    OrchestrationResult,
    OrchestrationStage,
    SceneDefinition,
    SceneStatus,
    StoryPlan,
    get_long_video_orchestrator,
)
from app.schemas.long_video import (
    CharacterProfileSchema,
    DialogueLineSchema,
    LongVideoCreateRequest,
    LongVideoPlanRequest,
    LongVideoProgressResponse,
    LongVideoProjectResponse,
    SceneDefinitionSchema,
    StoryPlanResponse,
    WorldSettingSchema,
)

router = APIRouter(prefix="/long-video", tags=["long-video"])


def _to_project_response(project: LongVideoProject) -> LongVideoProjectResponse:
    scenes_schema = []
    for s in (project.scenes or []):
        dialogue_items = []
        for d in (s.dialogue or []):
            dialogue_items.append(
                DialogueLineSchema(
                    character_id=d.get("character_id", ""),
                    character_name=d.get("character_name", ""),
                    text=d.get("text", ""),
                    emotion=d.get("emotion", "neutral"),
                    audio_clip_path=d.get("audio_clip_path"),
                )
            )
        scenes_schema.append(
            SceneDefinitionSchema(
                scene_index=s.scene_index,
                title=s.title,
                visual_prompt=s.visual_prompt,
                action_description=s.action_description,
                characters_present=s.characters_present or [],
                dialogue=dialogue_items,
                camera_motion=s.camera_motion,
                transition_to_next=s.transition_to_next,
                duration_seconds=s.duration_seconds,
                enriched_prompt=s.enriched_prompt,
                status=s.status,
                video_clip_path=s.video_clip_path,
                audio_clip_path=s.audio_clip_path,
                error_message=s.error_message,
                retry_count=s.retry_count,
            )
        )

    return LongVideoProjectResponse(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        prompt=project.prompt,
        synopsis=project.synopsis,
        status=project.status,
        generation_mode=project.generation_mode,
        engine_name=project.engine_name,
        world_setting=project.world_setting or {},
        characters=project.characters or [],
        total_scenes=project.total_scenes,
        current_scene=project.current_scene,
        progress_percent=project.progress_percent,
        status_text=project.status_text,
        output_video_path=project.output_video_path,
        error_message=project.error_message,
        scenes=scenes_schema,
        created_at=project.created_at,
        updated_at=project.updated_at,
        completed_at=project.completed_at,
    )


async def _run_orchestration_background(
    project_id: str,
    plan: StoryPlan,
    generation_settings: Optional[dict] = None,
):
    """Background task running orchestrator and syncing DB state."""
    orchestrator = get_long_video_orchestrator()

    def sync_progress_to_db(prog: OrchestrationProgress):
        db = SessionLocal()
        try:
            proj = db.query(LongVideoProject).filter(LongVideoProject.id == project_id).first()
            if proj:
                proj.status = prog.current_stage
                proj.progress_percent = prog.overall_progress
                proj.current_scene = prog.current_scene_index
                proj.status_text = prog.stage_detail
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    result = await orchestrator.execute_project(
        project_id=project_id,
        plan=plan,
        generation_settings=generation_settings,
        progress_callback=sync_progress_to_db,
    )

    db = SessionLocal()
    try:
        proj = db.query(LongVideoProject).filter(LongVideoProject.id == project_id).first()
        if proj:
            proj.status = result.status
            proj.output_video_path = result.final_video_path
            proj.error_message = result.error_message
            proj.progress_percent = 100.0 if result.status == OrchestrationStage.COMPLETED else proj.progress_percent
            proj.status_text = "Your long video is ready!" if result.status == OrchestrationStage.COMPLETED else f"Failed: {result.error_message}"

            # Sync scene results to db
            for sc in result.scenes:
                scene_record = (
                    db.query(LongVideoScene)
                    .filter(LongVideoScene.project_id == project_id, LongVideoScene.scene_index == sc.scene_index)
                    .first()
                )
                if scene_record:
                    scene_record.status = sc.status
                    scene_record.video_clip_path = sc.video_clip_path
                    scene_record.audio_clip_path = sc.audio_clip_path
                    scene_record.error_message = sc.error_message
                    scene_record.retry_count = sc.retry_count

            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.post("/plan", response_model=StoryPlanResponse)
async def plan_long_video(
    req: LongVideoPlanRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: LongVideoOrchestrator = Depends(get_long_video_orchestrator),
):
    """
    Decomposes a script or long prompt into scenes, characters, and world settings
    without executing generation.
    """
    del current_user
    plan = orchestrator.plan_project(
        prompt_or_script=req.prompt,
        target_duration=req.target_duration,
        world_override=req.world_override,
        characters_override=req.characters_override,
        preferred_engine=req.preferred_engine or "wan2gp",
    )

    return StoryPlanResponse(
        title=plan.title,
        synopsis=plan.synopsis,
        target_duration_seconds=plan.target_duration_seconds,
        characters=[
            CharacterProfileSchema(
                id=c.id,
                name=c.name,
                visual_description=c.visual_description,
                clothing=c.clothing,
                voice_profile_id=c.voice_profile_id,
                voice_style=c.voice_style,
                reference_image_path=c.reference_image_path,
                personality_notes=c.personality_notes,
            )
            for c in plan.characters
        ],
        world_setting=WorldSettingSchema(
            setting_type=plan.world_setting.setting_type,
            environment_rules=plan.world_setting.environment_rules,
            lighting=plan.world_setting.lighting,
            color_palette=plan.world_setting.color_palette,
            camera_style=plan.world_setting.camera_style,
            era_or_genre=plan.world_setting.era_or_genre,
        ),
        scenes=[
            SceneDefinitionSchema(
                scene_index=s.scene_index,
                title=s.title,
                visual_prompt=s.visual_prompt,
                action_description=s.action_description,
                characters_present=s.characters_present,
                dialogue=[
                    DialogueLineSchema(
                        character_id=d.character_id,
                        character_name=d.character_name,
                        text=d.text,
                        emotion=d.emotion,
                        audio_clip_path=d.audio_clip_path,
                    )
                    for d in s.dialogue
                ],
                camera_motion=s.camera_motion,
                transition_to_next=s.transition_to_next,
                duration_seconds=s.duration_seconds,
                enriched_prompt=s.enriched_prompt,
                status=s.status,
                video_clip_path=s.video_clip_path,
                audio_clip_path=s.audio_clip_path,
                error_message=s.error_message,
                retry_count=s.retry_count,
            )
            for s in plan.scenes
        ],
        generation_mode=plan.generation_mode,
        recommended_engine=plan.recommended_engine,
    )


@router.post("/projects", response_model=LongVideoProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_long_video_project(
    req: LongVideoCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    orchestrator: LongVideoOrchestrator = Depends(get_long_video_orchestrator),
):
    """
    Submits a full long-video generation project. Automatically plans, prepares continuity,
    and runs the generation lifecycle in the background.
    """
    plan = orchestrator.plan_project(
        prompt_or_script=req.prompt,
        target_duration=req.target_duration,
        world_override=req.world_override,
        characters_override=req.characters_override,
        preferred_engine=req.preferred_engine or "wan2gp",
    )

    project_id = str(uuid.uuid4())
    title_to_use = req.title or plan.title

    # Create DB project record
    project = LongVideoProject(
        id=project_id,
        user_id=current_user.id,
        title=title_to_use,
        prompt=req.prompt,
        synopsis=plan.synopsis,
        status=OrchestrationStage.PLANNING,
        generation_mode=plan.generation_mode,
        engine_name=plan.recommended_engine,
        world_setting=asdict(plan.world_setting),
        characters=[asdict(c) for c in plan.characters],
        total_scenes=len(plan.scenes),
        current_scene=0,
        progress_percent=0.0,
        status_text="Initializing long video generation pipeline...",
    )
    db.add(project)

    # Create scene records
    for sc in plan.scenes:
        scene_record = LongVideoScene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_index=sc.scene_index,
            title=sc.title,
            visual_prompt=sc.visual_prompt,
            enriched_prompt=sc.enriched_prompt,
            action_description=sc.action_description,
            characters_present=sc.characters_present,
            dialogue=[asdict(d) for d in sc.dialogue],
            camera_motion=sc.camera_motion,
            transition_to_next=sc.transition_to_next,
            duration_seconds=sc.duration_seconds,
            status=SceneStatus.PENDING,
        )
        db.add(scene_record)

    db.commit()
    db.refresh(project)

    # Start generation pipeline in background
    background_tasks.add_task(
        _run_orchestration_background,
        project_id=project_id,
        plan=plan,
        generation_settings=req.generation_settings,
    )

    return _to_project_response(project)


@router.get("/projects", response_model=List[LongVideoProjectResponse])
async def list_long_video_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists long-video projects belonging to the user."""
    query = select(LongVideoProject)
    if not current_user.has_role("admin"):
        query = query.where(LongVideoProject.user_id == current_user.id)
    query = query.order_by(LongVideoProject.created_at.desc())
    projects = db.execute(query).scalars().all()
    return [_to_project_response(p) for p in projects]


@router.get("/projects/{project_id}", response_model=LongVideoProjectResponse)
async def get_long_video_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves full details for a long-video project."""
    query = select(LongVideoProject).where(LongVideoProject.id == project_id)
    if not current_user.has_role("admin"):
        query = query.where(LongVideoProject.user_id == current_user.id)
    project = db.execute(query).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return _to_project_response(project)


@router.get("/projects/{project_id}/progress", response_model=LongVideoProgressResponse)
async def get_project_progress(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    orchestrator: LongVideoOrchestrator = Depends(get_long_video_orchestrator),
):
    """Retrieves real-time two-tier progress for a project."""
    query = select(LongVideoProject).where(LongVideoProject.id == project_id)
    if not current_user.has_role("admin"):
        query = query.where(LongVideoProject.user_id == current_user.id)
    project = db.execute(query).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    live_prog = orchestrator.get_progress(project_id)
    if live_prog:
        return LongVideoProgressResponse(
            overall_progress=live_prog.overall_progress,
            current_scene_index=live_prog.current_scene_index,
            total_scenes=live_prog.total_scenes,
            current_stage=live_prog.current_stage,
            stage_detail=live_prog.stage_detail,
            status_message=live_prog.status_message,
            active_engine=live_prog.active_engine,
            completed_scene_count=live_prog.completed_scene_count,
        )

    return LongVideoProgressResponse(
        overall_progress=project.progress_percent,
        current_scene_index=project.current_scene,
        total_scenes=project.total_scenes,
        current_stage=project.status,
        stage_detail=project.status_text or "",
        status_message="Generating your long video...",
        active_engine=project.engine_name,
        completed_scene_count=sum(1 for s in project.scenes if s.status == SceneStatus.COMPLETED),
    )


@router.post("/projects/{project_id}/retry-scene/{scene_index}")
async def retry_project_scene(
    project_id: str,
    scene_index: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    orchestrator: LongVideoOrchestrator = Depends(get_long_video_orchestrator),
):
    """
    Retries an individual failed scene and re-stitches without losing existing clips.
    """
    query = select(LongVideoProject).where(LongVideoProject.id == project_id)
    if not current_user.has_role("admin"):
        query = query.where(LongVideoProject.user_id == current_user.id)
    project = db.execute(query).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    scene = next((s for s in project.scenes if s.scene_index == scene_index), None)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scene {scene_index} not found.")

    scene.status = SceneStatus.PENDING
    scene.retry_count += 1
    project.status = OrchestrationStage.SCENE_GENERATION
    project.status_text = f"Retrying Scene {scene_index}..."
    db.commit()

    async def _run_retry():
        await orchestrator.retry_scene(project_id=project_id, scene_index=scene_index)

    background_tasks.add_task(_run_retry)
    return {"message": f"Scene {scene_index} retry scheduled for project {project_id}."}


@router.post("/projects/{project_id}/resume")
async def resume_long_video_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    orchestrator: LongVideoOrchestrator = Depends(get_long_video_orchestrator),
):
    """
    Resumes long video generation from the first incomplete scene.
    """
    query = select(LongVideoProject).where(LongVideoProject.id == project_id)
    if not current_user.has_role("admin"):
        query = query.where(LongVideoProject.user_id == current_user.id)
    project = db.execute(query).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    project.status = OrchestrationStage.SCENE_GENERATION
    project.status_text = "Resuming long video generation..."
    db.commit()

    async def _run_resume():
        await orchestrator.resume_project(project_id=project_id)

    background_tasks.add_task(_run_resume)
    return {"message": f"Project {project_id} resumed."}


@router.get("/projects/{project_id}/video")
async def stream_project_video(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Streams the final unified long video."""
    query = select(LongVideoProject).where(LongVideoProject.id == project_id)
    if not current_user.has_role("admin"):
        query = query.where(LongVideoProject.user_id == current_user.id)
    project = db.execute(query).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if not project.output_video_path or not Path(project.output_video_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Final stitched video is not ready or does not exist.",
        )

    return FileResponse(
        path=project.output_video_path,
        media_type="video/mp4",
        filename=f"long_video_{project_id}.mp4",
    )
