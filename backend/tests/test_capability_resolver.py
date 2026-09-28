"""Comprehensive tests for User Requirements & Capability Resolver."""

import pytest
from app.engines.base import EngineCapabilities
from app.engines.registry import VideoEngineRegistry
from app.engines.ltx2_adapter import LTX2Adapter
from app.engines.stubs import (
    LTXVideoAdapter,
    MiniMaxH3DirectorAdapter,
    MiniMaxH3LongVideoAdapter,
)
from app.engines.wan2gp_adapter import Wan2GPAdapter
from app.schemas.requirements import (
    CharacterMode,
    ContinuityLevel,
    DurationMode,
    GenerationPlanRead,
    GenerationStyle,
    QualityTier,
    UserRequirements,
    VoiceMode,
)
from app.services.capability_resolver import CapabilityResolver
from tests.test_engine_abstraction import MockWan2GPService


@pytest.fixture
def populated_registry(tmp_path):
    """Registry with Wan2GP active and stub engines registered."""
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"test video")
    mock_wan = MockWan2GPService(output_path=video_file, available=True)
    wan_adapter = Wan2GPAdapter(mock_wan)

    registry = VideoEngineRegistry()
    registry.register(wan_adapter, default=True)
    registry.register(LTXVideoAdapter())
    registry.register(LTX2Adapter())
    registry.register(MiniMaxH3LongVideoAdapter())
    registry.register(MiniMaxH3DirectorAdapter())
    return registry


def test_combination_1_short_no_voice(populated_registry):
    """1. Short + no voice -> standard video engine."""
    req = UserRequirements(
        prompt="A cute cat drinking water from a bowl",
        duration=DurationMode.SHORT,
        voice_mode=VoiceMode.NONE,
        character_mode=CharacterMode.SINGLE,
    )
    plan = CapabilityResolver.resolve_plan(req, populated_registry)
    assert plan.satisfies_all is True
    assert plan.selected_engine_id == "wan2gp"
    assert plan.requested_capabilities["text_to_video"] is True
    assert plan.requested_capabilities["audio_generation"] is False
    assert plan.requested_capabilities["multiple_characters"] is False
    assert "Wan2GP" in plan.reason
    assert len(plan.unsupported_requirements) == 0


def test_combination_2_short_ai_voice(populated_registry):
    """2. Short + AI voice -> audio generation capable engine."""
    req = UserRequirements(
        prompt="A reporter speaking in front of a stadium",
        duration=DurationMode.SHORT,
        voice_mode=VoiceMode.AI,
        audio_prompt="Welcome to tonight's championship match!",
    )
    plan = CapabilityResolver.resolve_plan(req, populated_registry)
    assert plan.satisfies_all is True
    assert plan.selected_engine_id == "wan2gp"
    assert plan.requested_capabilities["audio_generation"] is True
    assert plan.normalized_settings["voice_mode"] == "ai"
    assert plan.normalized_settings["audio_prompt"] == "Welcome to tonight's championship match!"


def test_combination_3_long_no_voice(populated_registry):
    """3. Long + no voice -> continuation / long video capability."""
    req = UserRequirements(
        prompt="A train moving through a snowy mountain pass",
        duration=DurationMode.LONG,
        voice_mode=VoiceMode.NONE,
    )
    plan = CapabilityResolver.resolve_plan(req, populated_registry)
    assert plan.satisfies_all is True
    assert plan.selected_engine_id == "wan2gp"
    assert plan.requested_capabilities["video_continuation"] is True
    assert plan.normalized_settings["video_length"] > 30


def test_combination_4_long_ai_voice(populated_registry):
    """4. Long + AI voice -> continuation + audio generation."""
    req = UserRequirements(
        prompt="A documentary on marine life deep in the ocean",
        duration=DurationMode.LONG,
        voice_mode=VoiceMode.AI,
        audio_prompt="The ocean abyss remains one of the final frontiers.",
        generation_style=GenerationStyle.DOCUMENTARY,
    )
    plan = CapabilityResolver.resolve_plan(req, populated_registry)
    assert plan.satisfies_all is True
    assert plan.selected_engine_id == "wan2gp"
    assert plan.requested_capabilities["video_continuation"] is True
    assert plan.requested_capabilities["audio_generation"] is True


def test_combination_5_long_human_like_voices(populated_registry):
    """5. Long + human-like voices -> voice conditioning."""
    req = UserRequirements(
        prompt="A teacher lecturing in a grand library",
        duration=DurationMode.LONG,
        voice_mode=VoiceMode.HUMAN_LIKE,
        audio_prompt="Knowledge is the foundation of progress.",
    )
    plan = CapabilityResolver.resolve_plan(req, populated_registry)
    assert plan.satisfies_all is True
    assert plan.selected_engine_id == "wan2gp"
    assert plan.requested_capabilities["voice_conditioning"] is True


def test_combination_6_long_custom_voice(populated_registry):
    """6. Long + custom voice -> reference audio / voice clone conditioning."""
    req = UserRequirements(
        prompt="A podcast host introducing the weekly episode",
        duration=DurationMode.LONG,
        voice_mode=VoiceMode.CUSTOM_USER_VOICE,
        reference_audio_url="/storage/audio/sample_voice.wav",
    )
    plan = CapabilityResolver.resolve_plan(req, populated_registry)
    assert plan.satisfies_all is True
    assert plan.selected_engine_id == "wan2gp"
    assert plan.requested_capabilities["reference_audio"] is True


def test_combination_7_multiple_characters_different_voices(populated_registry):
    """7. Multiple characters + different voices -> requires multi-character engine."""
    req = UserRequirements(
        prompt="A detective interrogating a suspect across a dimly lit table",
        duration=DurationMode.LONG,
        voice_mode=VoiceMode.HUMAN_LIKE,
        character_mode=CharacterMode.MULTIPLE,
        continuity=ContinuityLevel.MAXIMUM,
    )
    plan = CapabilityResolver.resolve_plan(req, populated_registry)
    # MiniMax H3 Director has multiple_characters=True, but is not installed/configured (available=False).
    # Wan2GP is available but lacks native multiple_characters.
    # Therefore, the resolver should select Wan2GP as fallback and clearly declare unsupported requirement!
    assert plan.selected_engine_id == "wan2gp"
    assert plan.satisfies_all is False
    assert any("multiple_characters" in u for u in plan.unsupported_requirements)
    assert len(plan.fallback_options) > 0


def test_combination_8_unsupported_when_no_engine_available():
    """8. Unsupported combination when registry has only unconfigured engines."""
    empty_registry = VideoEngineRegistry()
    empty_registry.register(LTXVideoAdapter(), default=True)
    empty_registry.register(MiniMaxH3DirectorAdapter())

    req = UserRequirements(
        prompt="Spaceship landing on alien planet",
        duration=DurationMode.SHORT,
    )
    plan = CapabilityResolver.resolve_plan(req, empty_registry)
    assert plan.satisfies_all is False
    assert len(plan.unsupported_requirements) > 0


def test_deterministic_and_explainable_plan(populated_registry):
    """Ensure resolver output is deterministic and fully populated."""
    req = UserRequirements(
        prompt="A cinematic drone shot over a misty pine forest",
        duration=DurationMode.SHORT,
        quality=QualityTier.CINEMATIC,
        generation_style=GenerationStyle.CINEMATIC,
        seed=42,
    )
    plan1 = CapabilityResolver.resolve_plan(req, populated_registry)
    plan2 = CapabilityResolver.resolve_plan(req, populated_registry)

    assert plan1.selected_engine_id == plan2.selected_engine_id
    assert plan1.normalized_settings["seed"] == 42
    assert plan1.normalized_settings["num_inference_steps"] == 35  # Cinematic quality tier
    assert "cinematic lighting" in plan1.normalized_settings["prompt"]
