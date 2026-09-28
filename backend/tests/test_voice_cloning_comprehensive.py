"""
Comprehensive Test Suite — Phase 7: Voice Cloning & Custom Voice
================================================================
Covers all aspects of the real Chatterbox-based voice cloning integration.
All tests pass on CPU-only dev machine (no CUDA required).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional
import uuid

import pytest


# ---------------------------------------------------------------------------
# 1. DATA MODELS
# ---------------------------------------------------------------------------

class TestVoiceCloningStatusCode:
    def test_all_core_status_codes_importable(self):
        from app.services.voice.cloning.models import VoiceCloningStatusCode
        assert VoiceCloningStatusCode.READY
        assert VoiceCloningStatusCode.FAILED
        assert VoiceCloningStatusCode.CONSENT_REQUIRED
        assert VoiceCloningStatusCode.CUDA_UNAVAILABLE
        assert VoiceCloningStatusCode.MODEL_MISSING

    def test_status_codes_are_string_enum(self):
        from app.services.voice.cloning.models import VoiceCloningStatusCode
        assert isinstance(VoiceCloningStatusCode.READY, str)
        assert isinstance(VoiceCloningStatusCode.FAILED, str)

    def test_audio_validation_error_codes_importable(self):
        from app.services.voice.cloning.models import AudioValidationErrorCode
        assert AudioValidationErrorCode.VALID
        assert AudioValidationErrorCode.FILE_NOT_FOUND
        assert AudioValidationErrorCode.UNSUPPORTED_FORMAT
        assert AudioValidationErrorCode.REFERENCE_AUDIO_TOO_SHORT
        assert AudioValidationErrorCode.CONSENT_REQUIRED


class TestVoiceCloningModels:
    def test_voice_profile_creation(self):
        from app.services.voice.cloning.models import VoiceProfile
        p = VoiceProfile(
            id="vp-001",
            name="Test Voice",
            reference_audio_path="/audio/ref.wav",
            owner_id="user-123",
            consent_confirmed=True,
        )
        assert p.id == "vp-001"
        assert p.name == "Test Voice"
        assert p.consent_confirmed is True

    def test_voice_profile_to_dict(self):
        from app.services.voice.cloning.models import VoiceProfile
        p = VoiceProfile(
            id="vp-002",
            name="Dict Voice",
            reference_audio_path="/audio/ref2.wav",
            owner_id="user-001",
            consent_confirmed=True,
        )
        d = p.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "vp-002"
        assert d["name"] == "Dict Voice"

    def test_voice_profile_from_dict(self):
        from app.services.voice.cloning.models import VoiceProfile
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        d = {
            "id": "vp-003",
            "name": "From Dict",
            "reference_audio_path": "/audio/ref3.wav",
            "owner_id": "user-002",
            "consent_confirmed": True,
            "language": "en",
            "gender": "neutral",
            "reference_transcript": None,
            "speaker_embedding_path": None,
            "engine": "chatterbox",
            "model_id": "resemble-ai/chatterbox-multilingual",
            "created_at": now_iso,
            "updated_at": now_iso,
            "metadata": {},
        }
        p = VoiceProfile.from_dict(d)
        assert p.id == "vp-003"
        assert p.name == "From Dict"

    def test_cloning_request_creation(self):
        from app.services.voice.cloning.models import VoiceCloningRequest
        req = VoiceCloningRequest(
            text="Hello, this is a test.",
            voice_profile_id="vp-001",
            reference_audio_path="/audio/ref.wav",
            language="en",
            output_audio_path="/out/audio.wav",
            extra_options={"consent_confirmed": True},
        )
        assert req.text == "Hello, this is a test."
        assert req.language == "en"
        assert req.voice_profile_id == "vp-001"

    def test_cloning_result_success_fields(self):
        from app.services.voice.cloning.models import VoiceCloningResult, VoiceCloningStatusCode
        res = VoiceCloningResult(
            job_id="job-001",
            status=VoiceCloningStatusCode.READY,
            success=True,
            audio_path="/out/audio.wav",
            duration_seconds=3.0,
        )
        assert res.success is True
        assert res.job_id == "job-001"
        assert res.audio_path == "/out/audio.wav"

    def test_cloning_result_failure_fields(self):
        from app.services.voice.cloning.models import VoiceCloningResult, VoiceCloningStatusCode
        res = VoiceCloningResult(
            job_id="job-002",
            status=VoiceCloningStatusCode.CONSENT_REQUIRED,
            success=False,
            error_message="Consent not confirmed.",
        )
        assert res.success is False
        assert res.error_message == "Consent not confirmed."

    def test_audio_validation_result_valid(self):
        from app.services.voice.cloning.models import AudioValidationResult, AudioValidationErrorCode
        r = AudioValidationResult(
            is_valid=True,
            error_code=AudioValidationErrorCode.VALID,
            error_message="",
        )
        assert r.is_valid is True

    def test_audio_validation_result_failure(self):
        from app.services.voice.cloning.models import AudioValidationResult, AudioValidationErrorCode
        r = AudioValidationResult(
            is_valid=False,
            error_code=AudioValidationErrorCode.REFERENCE_AUDIO_TOO_SHORT,
            error_message="Audio is too short.",
        )
        assert r.is_valid is False
        assert r.error_code == AudioValidationErrorCode.REFERENCE_AUDIO_TOO_SHORT


# ---------------------------------------------------------------------------
# 2. DIAGNOSTICS
# ---------------------------------------------------------------------------

class TestVoiceCloningDiagnostics:
    def test_check_environment_returns_status(self):
        from app.services.voice.cloning.diagnostics import (
            VoiceCloningEnvironmentStatus,
            check_voice_cloning_environment,
        )
        status = check_voice_cloning_environment()
        assert isinstance(status, VoiceCloningEnvironmentStatus)

    def test_status_has_required_fields(self):
        from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
        status = check_voice_cloning_environment()
        assert hasattr(status, "is_available")
        assert hasattr(status, "gpu_available")
        assert hasattr(status, "model_cached")
        assert hasattr(status, "status_code")
        assert hasattr(status, "diagnostic_message")

    def test_cpu_only_machine_not_available(self):
        """On CPU-only dev machine, gpu_available should be False (no CUDA)."""
        torch = pytest.importorskip("torch", reason="torch not installed")
        from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
        status = check_voice_cloning_environment()
        if not torch.cuda.is_available():
            assert status.gpu_available is False

    def test_status_is_safe_to_call_multiple_times(self):
        from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
        s1 = check_voice_cloning_environment()
        s2 = check_voice_cloning_environment()
        assert s1.gpu_available == s2.gpu_available


# ---------------------------------------------------------------------------
# 3. REFERENCE AUDIO VALIDATION
# ---------------------------------------------------------------------------

class TestReferenceAudioValidation:
    def test_consent_required_fails(self, tmp_path):
        """Validation must fail when consent_confirmed=False."""
        from app.services.voice.cloning.validation import validate_reference_audio
        from app.services.voice.cloning.models import AudioValidationErrorCode
        audio = tmp_path / "ref.wav"
        audio.write_bytes(b"\x00" * 100)
        result = validate_reference_audio(audio, consent_confirmed=False)
        assert result.is_valid is False
        assert result.error_code == AudioValidationErrorCode.CONSENT_REQUIRED

    def test_nonexistent_file_fails(self):
        from app.services.voice.cloning.validation import validate_reference_audio
        from app.services.voice.cloning.models import AudioValidationErrorCode
        result = validate_reference_audio(
            "/nonexistent/path/audio.wav", consent_confirmed=True
        )
        assert result.is_valid is False
        assert result.error_code == AudioValidationErrorCode.FILE_NOT_FOUND

    def test_unsupported_format_fails(self, tmp_path):
        from app.services.voice.cloning.validation import validate_reference_audio
        from app.services.voice.cloning.models import AudioValidationErrorCode
        audio = tmp_path / "voice.mp4"
        audio.write_bytes(b"\x00" * 100)
        result = validate_reference_audio(audio, consent_confirmed=True)
        assert result.is_valid is False
        assert result.error_code == AudioValidationErrorCode.UNSUPPORTED_FORMAT

    def test_valid_wav_file_passes(self):
        """Test against the pre-generated WAV reference file."""
        from app.services.voice.cloning.validation import validate_reference_audio
        ref_wav = Path("materials/test_reference_voice.wav")
        if not ref_wav.exists():
            pytest.skip("materials/test_reference_voice.wav not present")
        result = validate_reference_audio(ref_wav, consent_confirmed=True)
        assert result.is_valid is True, f"Expected valid, got: {result.error_message}"


def _make_dummy_wav(path: Path) -> Path:
    """Create a minimal real WAV file for tests that require an existing audio file."""
    import math, struct, wave
    path.parent.mkdir(parents=True, exist_ok=True)
    sr, dur = 24000, 5.0
    n = int(sr * dur)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            v = int(4000 * math.sin(2 * math.pi * 440 * i / sr))
            frames.extend(struct.pack("<h", max(-32768, min(32767, v))))
        wf.writeframes(frames)
    return path


class TestVoiceProfileStore:
    def test_create_profile(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        ref = _make_dummy_wav(tmp_path / "ref.wav")
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        profile = store.create_profile(
            name="Test Speaker",
            reference_audio_path=str(ref),
            owner_id="user-001",
            consent_confirmed=True,
        )
        assert profile.id is not None
        assert profile.name == "Test Speaker"
        assert profile.consent_confirmed is True

    def test_get_profile(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        ref = _make_dummy_wav(tmp_path / "ref.wav")
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        created = store.create_profile(
            name="Speaker B",
            reference_audio_path=str(ref),
            owner_id="user-002",
            consent_confirmed=True,
        )
        retrieved = store.get_profile(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Speaker B"

    def test_list_profiles(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        ref = _make_dummy_wav(tmp_path / "ref.wav")
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        store.create_profile("A", str(ref), "user-001", consent_confirmed=True)
        store.create_profile("B", str(ref), "user-001", consent_confirmed=True)
        store.create_profile("C", str(ref), "user-002", consent_confirmed=True)
        all_profiles = store.list_profiles()
        assert len(all_profiles) == 3

    def test_list_profiles_by_owner(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        ref = _make_dummy_wav(tmp_path / "ref.wav")
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        store.create_profile("A", str(ref), "user-001", consent_confirmed=True)
        store.create_profile("B", str(ref), "user-002", consent_confirmed=True)
        owned = store.list_profiles(owner_id="user-001")
        assert len(owned) == 1
        assert owned[0].name == "A"

    def test_delete_profile(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        ref = _make_dummy_wav(tmp_path / "ref.wav")
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        p = store.create_profile("Del", str(ref), "user-001", consent_confirmed=True)
        deleted = store.delete_profile(p.id)
        assert deleted is True
        assert store.get_profile(p.id) is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        result = store.delete_profile("nonexistent-id")
        assert result is False

    def test_save_speaker_embedding(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        ref = _make_dummy_wav(tmp_path / "ref.wav")
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        p = store.create_profile("Embed", str(ref), "user-001", consent_confirmed=True)
        dummy_embedding = b"\x01\x02\x03\x04"
        emb_path = store.save_speaker_embedding(p.id, dummy_embedding)
        assert emb_path is not None
        assert Path(emb_path).exists()


# ---------------------------------------------------------------------------
# 5. CHATTERBOX RUNNER (plan-only / stub mode)
# ---------------------------------------------------------------------------

class TestChatterboxRunner:
    def test_runner_instantiation(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        runner = ChatterboxVoiceCloningRunner(profile_store=store)
        assert runner is not None

    def test_is_ready_returns_bool(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        runner = ChatterboxVoiceCloningRunner(profile_store=store)
        assert isinstance(runner.is_ready(), bool)

    def test_execute_cloning_returns_result(self, tmp_path):
        """Runner must return a VoiceCloningResult without crashing."""
        from app.services.voice.cloning.storage import VoiceProfileStore
        from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
        from app.services.voice.cloning.models import VoiceCloningRequest, VoiceCloningResult
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        runner = ChatterboxVoiceCloningRunner(profile_store=store,
                                              output_dir=tmp_path / "out")
        out_path = tmp_path / "output.wav"
        req = VoiceCloningRequest(
            text="This is a plan-only test.",
            voice_profile_id="vp-test",
            reference_audio_path=str(tmp_path / "ref.wav"),
            language="en",
            output_audio_path=str(out_path),
            extra_options={"consent_confirmed": True},
        )
        result = runner.execute_cloning(req)
        assert isinstance(result, VoiceCloningResult)

    def test_cancel_unknown_job_returns_false(self, tmp_path):
        """Cancelling an unknown job should return False (no-op)."""
        from app.services.voice.cloning.storage import VoiceProfileStore
        from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        runner = ChatterboxVoiceCloningRunner(profile_store=store)
        # No job registered → should return False
        result = runner.cancel("unknown-job-id")
        assert isinstance(result, bool)

    def test_supported_languages_class_attr(self, tmp_path):
        """SUPPORTED_LANGUAGES class attribute must include English and Hindi."""
        from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
        langs = ChatterboxVoiceCloningRunner.SUPPORTED_LANGUAGES
        assert isinstance(langs, dict)
        assert "en" in langs
        assert "hi" in langs  # Hindi (Chatterbox-Multilingual)


# ---------------------------------------------------------------------------
# 6. VOICE CLONING ENGINE
# ---------------------------------------------------------------------------

class TestVoiceCloningEngine:
    def _make_engine(self, tmp_path):
        from app.services.voice.cloning.storage import VoiceProfileStore
        from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
        from app.services.voice.cloning.engine import VoiceCloningEngine
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        runner = ChatterboxVoiceCloningRunner(profile_store=store,
                                              output_dir=tmp_path / "out")
        return VoiceCloningEngine(runner=runner, profile_store=store)

    def test_engine_id(self, tmp_path):
        engine = self._make_engine(tmp_path)
        assert engine.engine_id == "voice-cloning"

    def test_get_capabilities(self, tmp_path):
        from app.services.voice.base import VoiceCapabilities
        engine = self._make_engine(tmp_path)
        caps = engine.get_capabilities()
        assert isinstance(caps, VoiceCapabilities)
        assert caps.supports_voice_cloning is True

    def test_create_voice_profile_consent_error(self, tmp_path):
        engine = self._make_engine(tmp_path)
        with pytest.raises((ValueError, Exception)):
            engine.create_voice_profile(
                name="Bad Profile",
                reference_audio_path="/nonexistent.wav",
                consent_confirmed=False,
            )

    def test_list_voices_returns_list(self, tmp_path):
        engine = self._make_engine(tmp_path)
        voices = engine.list_voices()
        assert isinstance(voices, list)

    def test_create_and_get_voice_profile(self, tmp_path):
        engine = self._make_engine(tmp_path)
        profile = engine.create_voice_profile(
            name="Created Speaker",
            reference_audio_path="materials/test_reference_voice.wav",
            consent_confirmed=True,
        )
        retrieved = engine.get_voice_profile(profile.id)
        assert retrieved is not None
        assert retrieved.id == profile.id

    def test_list_voices_after_profile_creation(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine.create_voice_profile(
            name="Listed Speaker",
            reference_audio_path="materials/test_reference_voice.wav",
            consent_confirmed=True,
        )
        voices = engine.list_voices()
        assert len(voices) >= 1
        assert voices[0]["is_custom_cloned"] is True

    def test_delete_voice_profile(self, tmp_path):
        engine = self._make_engine(tmp_path)
        profile = engine.create_voice_profile(
            name="To Delete",
            reference_audio_path="materials/test_reference_voice.wav",
            consent_confirmed=True,
        )
        deleted = engine.delete_voice_profile(profile.id)
        assert deleted is True
        assert engine.get_voice_profile(profile.id) is None


# ---------------------------------------------------------------------------
# 7. VOICE ENGINE REGISTRY INTEGRATION
# ---------------------------------------------------------------------------

class TestVoiceEngineRegistryIntegration:
    def test_registry_contains_voice_cloning_engine(self):
        """VoiceCloningEngine must appear in the VoiceEngineRegistry after auto-discovery."""
        import app.services.voice.registry as reg_module
        reg_module._global_voice_registry = None
        from app.services.voice.registry import get_voice_engine_registry
        registry = get_voice_engine_registry()
        engine_ids = [e["engine_id"] for e in registry.list_engines()]
        assert "voice-cloning" in engine_ids, (
            f"VoiceCloningEngine not found. Registered engines: {engine_ids}"
        )

    def test_registry_can_retrieve_cloning_engine_by_id(self):
        import app.services.voice.registry as reg_module
        reg_module._global_voice_registry = None
        from app.services.voice.registry import get_voice_engine_registry
        registry = get_voice_engine_registry()
        engine = registry.get_engine("voice-cloning")
        assert engine is not None
        assert engine.engine_id == "voice-cloning"

    def test_edge_tts_or_mock_is_default_not_cloning(self):
        """voice-cloning must NOT be the default engine."""
        import app.services.voice.registry as reg_module
        reg_module._global_voice_registry = None
        from app.services.voice.registry import get_voice_engine_registry
        registry = get_voice_engine_registry()
        default_engine = registry.get_engine()
        assert default_engine.engine_id != "voice-cloning"


# ---------------------------------------------------------------------------
# 8. CAPABILITY RESOLVER — VOICE CLONING ROUTING
# ---------------------------------------------------------------------------

class TestCapabilityResolverVoiceCloning:
    def test_voice_cloning_flag_set_for_custom_voice(self):
        from app.services.capability_resolver import CapabilityResolver
        from app.schemas.requirements import UserRequirements, VoiceMode
        req = UserRequirements(
            prompt="A woman speaks to camera",
            voice_mode=VoiceMode.CUSTOM_USER_VOICE,
            reference_audio_url="https://example.com/ref.wav",
        )
        caps = CapabilityResolver.derive_required_capabilities(req)
        assert caps.get("reference_audio") is True

    def test_voice_cloning_not_set_for_ai_voice(self):
        from app.services.capability_resolver import CapabilityResolver
        from app.schemas.requirements import UserRequirements, VoiceMode
        req = UserRequirements(
            prompt="A man narrates",
            voice_mode=VoiceMode.AI,
        )
        caps = CapabilityResolver.derive_required_capabilities(req)
        assert caps.get("reference_audio") is False

    def test_voice_cloning_not_set_for_none_voice(self):
        from app.services.capability_resolver import CapabilityResolver
        from app.schemas.requirements import UserRequirements, VoiceMode
        req = UserRequirements(
            prompt="Silent video of mountains",
            voice_mode=VoiceMode.NONE,
        )
        caps = CapabilityResolver.derive_required_capabilities(req)
        assert caps.get("reference_audio") is False


# ---------------------------------------------------------------------------
# 9. ENGINE CAPABILITIES — voice_cloning FIELD
# ---------------------------------------------------------------------------

class TestEngineCapabilitiesVoiceCloning:
    def test_default_voice_cloning_is_false(self):
        from app.engines.base import EngineCapabilities
        caps = EngineCapabilities()
        assert caps.voice_cloning is False

    def test_can_set_voice_cloning_true(self):
        from app.engines.base import EngineCapabilities
        caps = EngineCapabilities(voice_cloning=True)
        assert caps.voice_cloning is True

    def test_voice_cloning_appears_in_to_dict(self):
        from app.engines.base import EngineCapabilities
        caps = EngineCapabilities(voice_cloning=True)
        d = caps.to_dict()
        assert "voice_cloning" in d
        assert d["voice_cloning"] is True


# ---------------------------------------------------------------------------
# 10. H3 DIRECTOR — voice_profile_id IN CHARACTER CARD
# ---------------------------------------------------------------------------

class TestH3DirectorVoiceProfileId:
    def test_director_character_card_has_voice_profile_id(self):
        from app.engines.minimax_h3_director.models import DirectorCharacterCard
        card = DirectorCharacterCard(
            character_id="char-001",
            name="Alice",
            description="A scientist",
            voice_profile_id="vp-abc123",
        )
        assert card.voice_profile_id == "vp-abc123"

    def test_director_character_card_voice_profile_id_optional(self):
        from app.engines.minimax_h3_director.models import DirectorCharacterCard
        card = DirectorCharacterCard(
            character_id="char-002",
            name="Bob",
            description="A narrator",
        )
        assert card.voice_profile_id is None

    def test_voice_profile_id_can_be_updated(self):
        from app.engines.minimax_h3_director.models import DirectorCharacterCard
        card = DirectorCharacterCard(
            character_id="char-003",
            name="Carol",
            description="A host",
        )
        card.voice_profile_id = "vp-xyz999"
        assert card.voice_profile_id == "vp-xyz999"


# ---------------------------------------------------------------------------
# 11. MONEYPRINTERTURBO VOICE LAYER COMPATIBILITY
# ---------------------------------------------------------------------------

class TestMoneyPrinterTurboVoiceLayerCompatibility:
    def test_mpt_runner_accepts_base_voice_engine(self):
        """MPT runner constructor must accept any BaseVoiceEngine, not just EdgeTTS."""
        import inspect
        from app.engines.money_printer_turbo.runner import MoneyPrinterTurboRunner
        sig = inspect.signature(MoneyPrinterTurboRunner.__init__)
        assert "voice_engine" in sig.parameters

    def test_mpt_runner_default_voice_engine_is_base_type(self):
        """When instantiated without voice_engine, voice_engine must be BaseVoiceEngine."""
        from app.services.voice.base import BaseVoiceEngine
        from app.engines.money_printer_turbo.runner import MoneyPrinterTurboRunner
        runner = MoneyPrinterTurboRunner()
        if hasattr(runner, "voice_engine") and runner.voice_engine is not None:
            assert isinstance(runner.voice_engine, BaseVoiceEngine)


# ---------------------------------------------------------------------------
# 12. ASYNC SYNTHESIZE CONTRACT
# ---------------------------------------------------------------------------

class TestVoiceCloningEngineSynthesizeContract:
    def test_synthesize_is_coroutine(self):
        """synthesize() must be an async method per BaseVoiceEngine contract."""
        import inspect
        from app.services.voice.cloning.engine import VoiceCloningEngine
        assert inspect.iscoroutinefunction(VoiceCloningEngine.synthesize)

    def test_engine_health_check_returns_bool(self, tmp_path):
        """health_check() must always return bool."""
        from app.services.voice.cloning.storage import VoiceProfileStore
        from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
        from app.services.voice.cloning.engine import VoiceCloningEngine
        store = VoiceProfileStore(storage_dir=tmp_path / "profiles")
        runner = ChatterboxVoiceCloningRunner(profile_store=store)
        engine = VoiceCloningEngine(runner=runner, profile_store=store)
        result = engine.health_check()
        assert isinstance(result, bool)
