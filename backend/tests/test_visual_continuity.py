"""
Tests for Real Visual Continuity (Milestone: Level 2 - Previous-Frame Conditioning).
Verifies:
1. extract_last_frame on valid video returns a valid PNG image.
2. Missing video raises FileNotFoundError.
3. Empty / corrupted video raises ValueError or RuntimeError.
4. SceneDefinition continuation_context persistence.
5. Propagation of previous_frame_path from Scene 1 to Scene 2.
6. Wan2GP/scheduler payload receives image_start with valid file path.
7. Prompt-level continuity tokens remain intact in enriched_prompt.
8. Scene retry preserves previous frame reference.
9. Scene 1 has no previous_frame_path conditioning.
10. End-to-end multi-scene visual continuity chaining in LongVideoOrchestrator.
"""

from pathlib import Path
import pytest
from PIL import Image

from app.engines.mock_engine import MockVideoEngine, _generate_minimal_mp4
from app.orchestration.media_stitcher import MediaStitcher
from app.orchestration.models import (
    CharacterProfile,
    DialogueLine,
    SceneDefinition,
    SceneStatus,
    StoryPlan,
    WorldSetting,
)
from app.orchestration.orchestrator import LongVideoOrchestrator
from app.orchestration.generation_scheduler import GenerationScheduler
from app.orchestration.story_planner import StoryPlanner
from app.orchestration.continuity_manager import ContinuityManager
from app.orchestration.voice_scheduler import VoiceScheduler


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    video_path = tmp_path / "test_sample.mp4"
    _generate_minimal_mp4(video_path)
    assert video_path.exists()
    return video_path


def test_1_extract_last_frame_valid(sample_video: Path, temp_dir: Path):
    """Test 1: extract_last_frame extracts a valid PNG with dimensions > 0."""
    stitcher = MediaStitcher(output_dir=temp_dir)
    out_frame = temp_dir / "last_frame.png"
    result_path = stitcher.extract_last_frame(sample_video, out_frame)

    assert result_path.exists()
    assert result_path.stat().st_size > 0

    with Image.open(result_path) as img:
        img.verify()
        assert img.size[0] > 0
        assert img.size[1] > 0


def test_2_extract_last_frame_missing_file(temp_dir: Path):
    """Test 2: extract_last_frame on nonexistent file raises FileNotFoundError."""
    stitcher = MediaStitcher(output_dir=temp_dir)
    non_existent = temp_dir / "non_existent.mp4"

    with pytest.raises(FileNotFoundError):
        stitcher.extract_last_frame(non_existent)


def test_3_extract_last_frame_empty_file(temp_dir: Path):
    """Test 3: extract_last_frame on empty file raises ValueError."""
    stitcher = MediaStitcher(output_dir=temp_dir)
    empty_file = temp_dir / "empty.mp4"
    empty_file.write_bytes(b"")

    with pytest.raises(ValueError):
        stitcher.extract_last_frame(empty_file)


def test_4_continuation_context_persistence():
    """Test 4: SceneDefinition properly initializes and persists continuation_context."""
    scene = SceneDefinition(
        scene_index=2,
        title="Scene Two",
        visual_prompt="Approaching the glowing gate",
        continuation_context={"previous_clip_path": "scene1.mp4", "previous_frame_path": "frame1.png"},
    )
    assert scene.continuation_context["previous_clip_path"] == "scene1.mp4"
    assert scene.continuation_context["previous_frame_path"] == "frame1.png"


def test_5_previous_frame_path_propagation_to_next_scene():
    """Test 5: continuation_context holds previous_frame_path and previous_scene_index."""
    scene1 = SceneDefinition(
        scene_index=1,
        title="Scene One",
        visual_prompt="Walking along the neon corridor",
    )
    scene2 = SceneDefinition(
        scene_index=2,
        title="Scene Two",
        visual_prompt="Reaching the security console",
    )

    dummy_frame = "/tmp/scene1_last_frame.png"
    dummy_clip = "/tmp/scene1.mp4"

    # Simulate link
    scene2.continuation_context["previous_clip_path"] = dummy_clip
    scene2.continuation_context["previous_frame_path"] = dummy_frame
    scene2.continuation_context["previous_scene_index"] = scene1.scene_index

    assert scene2.continuation_context["previous_frame_path"] == dummy_frame
    assert scene2.continuation_context["previous_scene_index"] == 1


@pytest.mark.asyncio
async def test_6_scheduler_injects_image_start(temp_dir: Path, sample_video: Path):
    """Test 6: GenerationScheduler injects image_start and reference_image into settings."""
    # Extract actual frame from sample video
    stitcher = MediaStitcher(output_dir=temp_dir)
    frame_path = stitcher.extract_last_frame(sample_video, temp_dir / "scene1_frame.png")

    scene = SceneDefinition(
        scene_index=2,
        title="Scene Two",
        visual_prompt="Character steps through the doorway",
        continuation_context={
            "previous_clip_path": str(sample_video),
            "previous_frame_path": str(frame_path),
        },
    )

    mock_engine = MockVideoEngine()
    mock_engine.initialize()

    class RegistryMock:
        def get_engine(self, name="wan2gp"):
            return mock_engine

    scheduler = GenerationScheduler(engine_registry=RegistryMock(), media_stitcher=stitcher)

    res_scene = await scheduler.execute_scene_generation(
        scene=scene,
        project_id="test_proj_continuity",
        engine_name="mock-engine",
    )

    assert res_scene.status == SceneStatus.COMPLETED
    assert res_scene.video_clip_path is not None

    # Verify mock engine received image_start in settings
    job_data = list(mock_engine._active_jobs.values())[-1]
    submitted_settings = job_data["settings"]
    assert submitted_settings.get("image_start") == str(frame_path.resolve())
    assert submitted_settings.get("reference_image") == str(frame_path.resolve())


def test_7_prompt_level_continuity_tokens_intact():
    """Test 7: ContinuityManager enriches prompts with character clothing and world lighting."""
    continuity = ContinuityManager()
    char = CharacterProfile(
        id="char_1",
        name="Nova",
        visual_description="A cybernetic scout with silver cybernetic visor",
        clothing="tactical navy armor with gold insignias",
    )
    world = WorldSetting(
        setting_type="cyberpunk outpost",
        lighting="deep amber backlighting and volumetric fog",
        color_palette="dark teal and amber",
    )
    scenes = [
        SceneDefinition(
            scene_index=1,
            title="Entrance",
            visual_prompt="Nova scans the perimeter",
            characters_present=["char_1"],
        ),
        SceneDefinition(
            scene_index=2,
            title="Infiltration",
            visual_prompt="Nova bypasses the biometric lock",
            characters_present=["char_1"],
        ),
    ]

    enriched = continuity.enrich_scene_prompts(scenes, [char], world)
    for s in enriched:
        assert "Nova" in s.enriched_prompt
        assert "tactical navy armor" in s.enriched_prompt
        assert "deep amber backlighting" in s.enriched_prompt


@pytest.mark.asyncio
async def test_8_scene_retry_preserves_continuation_context(temp_dir: Path, sample_video: Path):
    """Test 8: Scene retry preserves previous frame reference and allows clean recovery."""
    stitcher = MediaStitcher(output_dir=temp_dir)
    frame_path = stitcher.extract_last_frame(sample_video, temp_dir / "scene1_frame.png")

    char = CharacterProfile(
        id="c1",
        name="Elena",
        visual_description="A scientist in a clean white coat",
    )
    scene1 = SceneDefinition(
        scene_index=1,
        title="Lab Entry",
        visual_prompt="Elena steps into the laboratory",
        status=SceneStatus.COMPLETED,
        video_clip_path=str(sample_video),
    )
    scene2 = SceneDefinition(
        scene_index=2,
        title="Experiment",
        visual_prompt="Elena checks the reaction vial",
        status=SceneStatus.FAILED,
        error_message="Simulated temporary failure",
        continuation_context={
            "previous_clip_path": str(sample_video),
            "previous_frame_path": str(frame_path),
        },
    )

    plan = StoryPlan(
        title="Lab Test",
        synopsis="Elena tests a compound",
        target_duration_seconds=10.0,
        characters=[char],
        scenes=[scene1, scene2],
        recommended_engine="mock-engine",
    )

    mock_engine = MockVideoEngine()
    mock_engine.initialize()

    class RegistryMock:
        def get_engine(self, name="mock-engine"):
            return mock_engine

    orchestrator = LongVideoOrchestrator(
        engine_registry=RegistryMock(),
        media_stitcher=stitcher,
    )
    orchestrator._plans_cache["proj_retry_test"] = plan

    # Retry scene 2
    res = await orchestrator.retry_scene("proj_retry_test", scene_index=2)

    assert res.status == "COMPLETED"
    assert scene2.status == SceneStatus.COMPLETED
    assert scene2.continuation_context["previous_frame_path"] == str(frame_path)
    assert Path(res.final_video_path).exists()


def test_9_scene_1_has_no_previous_frame_path(temp_dir: Path):
    """Test 9: Scene 1 has no previous_frame_path conditioning initially."""
    planner = StoryPlanner()
    plan = planner.plan_story(
        prompt_or_script="Scene 1: A space expedition lands on Mars. Scene 2: The team explores the crater.",
        target_duration=10.0,
    )
    assert len(plan.scenes) >= 2
    assert "previous_frame_path" not in plan.scenes[0].continuation_context


@pytest.mark.asyncio
async def test_10_end_to_end_multi_scene_visual_continuity(temp_dir: Path):
    """Test 10: Full multi-scene orchestrator run extracts frame from Scene 1 and chains into Scene 2."""
    char1 = CharacterProfile(
        id="char_elena",
        name="Elena",
        visual_description="A researcher in a silver jumpsuit",
        voice_profile_id="voice_amber",
    )
    scene1 = SceneDefinition(
        scene_index=1,
        title="Arrival",
        visual_prompt="Elena stands before the ancient portal",
        duration_seconds=2.0,
        dialogue=[DialogueLine(character_id="char_elena", character_name="Elena", text="We made it.")],
    )
    scene2 = SceneDefinition(
        scene_index=2,
        title="Activation",
        visual_prompt="Elena activates the glyph console",
        duration_seconds=2.0,
        dialogue=[DialogueLine(character_id="char_elena", character_name="Elena", text="The portal is opening.")],
    )

    plan = StoryPlan(
        title="Portal Journey",
        synopsis="Elena explores the ancient gate",
        target_duration_seconds=4.0,
        characters=[char1],
        scenes=[scene1, scene2],
        recommended_engine="mock-engine",
    )

    mock_engine = MockVideoEngine()
    mock_engine.initialize()

    class RegistryMock:
        def get_engine(self, name="mock-engine"):
            return mock_engine

    stitcher = MediaStitcher(output_dir=temp_dir / "output")
    voice_scheduler = VoiceScheduler(media_stitcher=stitcher, output_dir=str(temp_dir / "audio"))

    orchestrator = LongVideoOrchestrator(
        engine_registry=RegistryMock(),
        voice_scheduler=voice_scheduler,
        media_stitcher=stitcher,
    )

    result = await orchestrator.execute_project("proj_e2e_continuity", plan)

    assert result.status == "COMPLETED"
    assert result.final_video_path is not None
    assert Path(result.final_video_path).exists()

    # Verify that Scene 2 has previous_frame_path pointing to an existing image
    assert "previous_frame_path" in scene2.continuation_context
    prev_frame = Path(scene2.continuation_context["previous_frame_path"])
    assert prev_frame.exists()
    assert prev_frame.stat().st_size > 0

    # Verify extracted frame is a valid image
    with Image.open(prev_frame) as img:
        img.verify()
        assert img.size[0] > 0
        assert img.size[1] > 0
