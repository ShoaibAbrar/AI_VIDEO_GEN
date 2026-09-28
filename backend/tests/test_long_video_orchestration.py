"""
Unit and integration tests for Long-Video Orchestration Architecture.
Tests story planning, continuity management, voice scheduling, generation scheduling,
media stitching, two-tier progress tracking, failure recovery, and API endpoints.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
from typing import Any, Callable
import pytest

from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)
from app.engines.registry import VideoEngineRegistry
from app.models.long_video import LongVideoProject, LongVideoScene
from app.orchestration import (
    CharacterProfile,
    ContinuityManager,
    GenerationScheduler,
    LongVideoMode,
    LongVideoOrchestrator,
    MediaStitcher,
    OrchestrationProgress,
    OrchestrationResult,
    OrchestrationStage,
    SceneDefinition,
    SceneStatus,
    StoryPlan,
    StoryPlanner,
    VoiceScheduler,
)


class MockVideoEngine(BaseVideoEngine):
    """Mock engine implementing BaseVideoEngine for testing."""

    def __init__(self, name: str = "mock_engine", can_native_long: bool = False, fail_scene_index: int = -1):
        self._name = name
        self._can_native_long = can_native_long
        self._fail_scene_index = fail_scene_index
        self.jobs: dict[str, dict] = {}
        self.temp_dir = tempfile.mkdtemp()

    @property
    def engine_id(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return f"Mock {self._name}"

    @property
    def description(self) -> str:
        return "Mock engine for testing"

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            text_to_video=True,
            native_long_video=self._can_native_long,
            video_continuation=True,
            reference_image=True,
            configurable_steps=True,
        )

    def initialize(self) -> None:
        pass

    def get_runtime_status(self) -> dict[str, Any]:
        return {"available": True, "engine_id": self.engine_id}

    def list_models(self) -> list[dict[str, Any]]:
        return [{"model_type": "wan2.1_t2v_1.3B", "name": "Mock Model"}]

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        return generation_settings

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> EngineJobHandle:
        job_id = f"mock_job_{len(self.jobs) + 1}"
        scene_idx = generation_settings.get("scene_index", 1)
        self.jobs[job_id] = {
            "prompt": generation_settings.get("prompt", ""),
            "scene_index": scene_idx,
            "status": "COMPLETED",
        }
        on_progress(EngineProgress(progress=50, current_step=10, total_steps=20, status="Generating"))
        return EngineJobHandle(job_id=job_id, engine_id=self.engine_id)

    def wait_for_result(self, handle: EngineJobHandle) -> EngineResult:
        job = self.jobs.get(handle.job_id)
        if not job:
            return EngineResult(success=False, error_message="Job not found")

        if job["scene_index"] == self._fail_scene_index:
            return EngineResult(
                success=False,
                error_message=f"Simulated failure on scene {self._fail_scene_index}",
            )

        clip_path = Path(self.temp_dir) / f"clip_{handle.job_id}.mp4"
        with open(clip_path, "wb") as f:
            f.write(b"MOCK_MP4_VIDEO_HEADER_DATA_1234567890")

        return EngineResult(success=True, output_files=[str(clip_path)])

    def cancel_generation(self, handle: EngineJobHandle) -> None:
        pass

    def shutdown(self) -> None:
        pass


# ============================================================================
# 1. Story & Scene Planner Tests
# ============================================================================

def test_story_planner_parses_formatted_script():
    planner = StoryPlanner(default_scene_duration=5.0)
    script = """Title: Neon Odyssey
Scene 1:
Detective Vance: "The city never sleeps, but secrets do."
Vance steps under the flickering neon sign in the rain.

Scene 2:
Vance walks into the alleyway.
Vance: "Who is there?"
Camera zooms in on a shadowy figure.
"""
    plan = planner.plan_story(script, target_duration=10.0)

    assert plan.title == "Neon Odyssey"
    assert len(plan.scenes) == 2
    assert plan.scenes[0].scene_index == 1
    assert len(plan.scenes[0].dialogue) == 1
    assert plan.scenes[0].dialogue[0].character_name == "Detective Vance"
    assert plan.scenes[0].dialogue[0].text == "The city never sleeps, but secrets do."
    assert plan.scenes[1].scene_index == 2
    assert "zoom" in plan.scenes[1].camera_motion.lower()
    assert plan.world_setting.setting_type == "cyberpunk sci-fi"


def test_story_planner_parses_unformatted_narrative():
    planner = StoryPlanner()
    narrative = (
        "An astronaut explores a desolate Martian valley at sunrise. "
        "She discovers a strange crystalline monument humming with energy. "
        "The monument begins to glow brighter, illuminating the ancient dust."
    )
    plan = planner.plan_story(narrative, target_duration=15.0)

    assert len(plan.scenes) >= 2
    assert plan.target_duration_seconds == 15.0
    for s in plan.scenes:
        assert s.duration_seconds > 0


# ============================================================================
# 2. Continuity Manager Tests
# ============================================================================

def test_continuity_manager_enriches_prompts():
    planner = StoryPlanner()
    continuity = ContinuityManager()

    script = """Scene 1:
Sarah: "Let's explore the hidden grove."
Sarah walks through the ancient gate.

Scene 2:
Sarah approaches the glowing spring.
"""
    plan = planner.plan_story(script)
    plan.characters[0].visual_description = "Auburn braid, amber eyes"
    plan.characters[0].clothing = "leather explorer jacket"

    enriched_scenes = continuity.enrich_scene_prompts(
        scenes=plan.scenes,
        characters=plan.characters,
        world=plan.world_setting,
    )

    scene1_prompt = enriched_scenes[0].enriched_prompt
    assert "Auburn braid" in scene1_prompt
    assert "leather explorer jacket" in scene1_prompt
    assert "Visual style:" in scene1_prompt

    scene2_prompt = enriched_scenes[1].enriched_prompt
    assert "Continuous progression from Scene 1" in scene2_prompt
    assert enriched_scenes[1].continuation_context["previous_scene_index"] == 1


# ============================================================================
# 3. Voice Scheduler Tests
# ============================================================================

@pytest.mark.asyncio
async def test_voice_scheduler():
    with tempfile.TemporaryDirectory() as temp_dir:
        scheduler = VoiceScheduler(output_dir=temp_dir)
        chars = [
            CharacterProfile(id="vance", name="Vance", visual_description="Detective"),
            CharacterProfile(id="elena", name="Elena", visual_description="Scientist"),
        ]
        assigned_chars = scheduler.assign_voice_profiles(chars)
        assert assigned_chars[0].voice_profile_id is not None
        assert assigned_chars[1].voice_profile_id is not None

        from app.orchestration.models import DialogueLine

        scene = SceneDefinition(
            scene_index=1,
            title="Scene 1",
            visual_prompt="Alleyway",
            characters_present=["vance"],
            dialogue=[DialogueLine(character_id="vance", character_name="Vance", text="Hello world.")],
        )

        audio_path = await scheduler.synthesize_scene_dialogue(scene, assigned_chars, project_id="proj_test_1")
        assert audio_path is not None
        assert Path(audio_path).exists()
        assert Path(audio_path).stat().st_size > 0


# ============================================================================
# 4. Generation Scheduler & Mode Resolution Tests
# ============================================================================

def test_generation_scheduler_mode_resolution():
    reg = VideoEngineRegistry()
    native_engine = MockVideoEngine("native_eng", can_native_long=True)
    segmented_engine = MockVideoEngine("seg_eng", can_native_long=False)
    reg.register(native_engine)
    reg.register(segmented_engine)

    scheduler = GenerationScheduler(engine_registry=reg)

    mode_native = scheduler.resolve_mode("native_eng", requested_duration=30.0, scene_count=1)
    assert mode_native == LongVideoMode.NATIVE_LONG_VIDEO

    mode_seg = scheduler.resolve_mode("seg_eng", requested_duration=30.0, scene_count=3)
    assert mode_seg == LongVideoMode.SEGMENTED_CONTINUATION


# ============================================================================
# 5. Media Stitcher Tests
# ============================================================================

def test_media_stitcher_combines_clips():
    with tempfile.TemporaryDirectory() as temp_dir:
        stitcher = MediaStitcher(output_dir=temp_dir)

        clip1 = Path(temp_dir) / "clip1.mp4"
        clip2 = Path(temp_dir) / "clip2.mp4"
        clip1.write_bytes(b"SCENE_ONE_BYTES_")
        clip2.write_bytes(b"SCENE_TWO_BYTES_")

        scenes = [
            SceneDefinition(scene_index=1, title="S1", visual_prompt="P1", video_clip_path=str(clip1)),
            SceneDefinition(scene_index=2, title="S2", visual_prompt="P2", video_clip_path=str(clip2)),
        ]

        final_path = stitcher.stitch_scenes(scenes, project_id="test_stitch_123")
        assert Path(final_path).exists()
        assert Path(final_path).stat().st_size > 0
        content = Path(final_path).read_bytes()
        assert b"SCENE_ONE_BYTES_" in content
        assert b"SCENE_TWO_BYTES_" in content


# ============================================================================
# 6. End-to-End LongVideoOrchestrator & Fault Recovery Tests
# ============================================================================

@pytest.mark.asyncio
async def test_orchestrator_full_execution_and_two_tier_progress():
    reg = VideoEngineRegistry()
    mock_eng = MockVideoEngine("wan2gp")
    reg.register(mock_eng)

    with tempfile.TemporaryDirectory() as temp_dir:
        stitcher = MediaStitcher(output_dir=temp_dir)
        voice_sched = VoiceScheduler(output_dir=temp_dir)
        gen_sched = GenerationScheduler(engine_registry=reg)

        orchestrator = LongVideoOrchestrator(
            voice_scheduler=voice_sched,
            generation_scheduler=gen_sched,
            media_stitcher=stitcher,
            engine_registry=reg,
        )

        prompt = """Scene 1:
A warrior stands at the edge of the cliff.

Scene 2:
The warrior draws a radiant glowing sword.
"""
        plan = orchestrator.plan_project(prompt, preferred_engine="wan2gp")
        assert len(plan.scenes) == 2

        progress_history = []

        def track_progress(p: OrchestrationProgress):
            progress_history.append((p.overall_progress, p.current_stage, p.stage_detail))

        result = await orchestrator.execute_project(
            project_id="test_proj_full",
            plan=plan,
            progress_callback=track_progress,
        )

        assert result.status == OrchestrationStage.COMPLETED
        assert result.final_video_path is not None
        assert Path(result.final_video_path).exists()
        assert len(progress_history) > 0
        assert progress_history[-1][0] == 100.0
        assert progress_history[-1][1] == OrchestrationStage.COMPLETED


@pytest.mark.asyncio
async def test_orchestrator_resilient_failure_recovery_and_scene_retry():
    reg = VideoEngineRegistry()
    mock_eng = MockVideoEngine("wan2gp", fail_scene_index=2)
    reg.register(mock_eng)

    with tempfile.TemporaryDirectory() as temp_dir:
        stitcher = MediaStitcher(output_dir=temp_dir)
        voice_sched = VoiceScheduler(output_dir=temp_dir)
        gen_sched = GenerationScheduler(engine_registry=reg)

        orchestrator = LongVideoOrchestrator(
            voice_scheduler=voice_sched,
            generation_scheduler=gen_sched,
            media_stitcher=stitcher,
            engine_registry=reg,
        )

        prompt = """Scene 1:
Opening shot of tranquil river.

Scene 2:
Boat capsizes in the rapid currents.

Scene 3:
Survivor reaches the rocky river bank.
"""
        plan = orchestrator.plan_project(prompt, preferred_engine="wan2gp")

        # 1. First execution fails at Scene 2
        result1 = await orchestrator.execute_project("proj_fail_recovery", plan)
        assert result1.status == OrchestrationStage.FAILED
        assert "Scene 2 generation failed" in result1.error_message

        # Verify Scene 1 was completed and its clip preserved
        assert plan.scenes[0].status == SceneStatus.COMPLETED
        assert plan.scenes[0].video_clip_path is not None
        assert Path(plan.scenes[0].video_clip_path).exists()
        # Scene 2 failed
        assert plan.scenes[1].status == SceneStatus.FAILED

        # 2. Fix the engine failure and retry Scene 2
        mock_eng._fail_scene_index = -1

        result_retry = await orchestrator.retry_scene("proj_fail_recovery", scene_index=2)
        assert result_retry.status == OrchestrationStage.COMPLETED
        assert result_retry.final_video_path is not None
        assert Path(result_retry.final_video_path).exists()
        assert plan.scenes[0].status == SceneStatus.COMPLETED
        assert plan.scenes[1].status == SceneStatus.COMPLETED
        assert plan.scenes[2].status == SceneStatus.COMPLETED


# ============================================================================
# 7. Long-Video API Route Integration Tests
# ============================================================================

def auth_token(client, username, email):
    client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": "strongpass123"})
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "strongpass123"})
    return response.json()["access_token"]


def test_long_video_api_plan_and_project_lifecycle(client):
    token = auth_token(client, "longvid_user", "longvid@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test POST /long-video/plan
    plan_payload = {
        "prompt": "Scene 1: A traveler enters the enchanted forest.\nScene 2: The traveler discovers a hidden shrine.",
        "target_duration": 12.0,
        "preferred_engine": "wan2gp",
    }
    plan_res = client.post("/api/v1/long-video/plan", headers=headers, json=plan_payload)
    assert plan_res.status_code == 200, plan_res.text
    plan_data = plan_res.json()
    assert len(plan_data["scenes"]) == 2
    assert plan_data["recommended_engine"] == "wan2gp"
    assert plan_data["generation_mode"] == "SEGMENTED_CONTINUATION"

    # 2. Test POST /long-video/projects
    create_payload = {
        "prompt": "Scene 1: A traveler enters the enchanted forest.\nScene 2: The traveler discovers a hidden shrine.",
        "title": "Enchanted Forest Journey",
        "target_duration": 10.0,
        "preferred_engine": "wan2gp",
    }
    create_res = client.post("/api/v1/long-video/projects", headers=headers, json=create_payload)
    assert create_res.status_code == 201, create_res.text
    project = create_res.json()
    project_id = project["id"]
    assert project["title"] == "Enchanted Forest Journey"
    assert project["total_scenes"] == 2
    assert len(project["scenes"]) == 2

    # 3. Test GET /long-video/projects
    list_res = client.get("/api/v1/long-video/projects", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Test GET /long-video/projects/{id}
    detail_res = client.get(f"/api/v1/long-video/projects/{project_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == project_id

    # 5. Test GET /long-video/projects/{id}/progress
    prog_res = client.get(f"/api/v1/long-video/projects/{project_id}/progress", headers=headers)
    assert prog_res.status_code == 200
    prog_data = prog_res.json()
    assert "overall_progress" in prog_data
    assert "status_message" in prog_data
    assert "current_stage" in prog_data

    # 6. Test POST /long-video/projects/{id}/retry-scene/1
    retry_res = client.post(f"/api/v1/long-video/projects/{project_id}/retry-scene/1", headers=headers)
    assert retry_res.status_code == 200

    # 7. Test POST /long-video/projects/{id}/resume
    resume_res = client.post(f"/api/v1/long-video/projects/{project_id}/resume", headers=headers)
    assert resume_res.status_code == 200
