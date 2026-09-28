"""
Comprehensive Test Suite — MoneyPrinterTurbo Production Engine
==============================================================
Covers:
  1. Data models and schemas
  2. Environment diagnostics (mock mode, missing deps, missing FFmpeg, API keys)
  3. ScriptGenerator (Mode A topic expansion, Mode B user script segmentation)
  4. Material providers (Pexels, Pixabay, Local, Canvas fallback, Composite cascade)
  5. SubtitleManager (SRT/ASS generation, timestamp formatting, FFmpeg filter escaping)
  6. MusicManager (track discovery, ambient loop generation, voice/BGM audio mix filter)
  7. MoneyPrinterTurboRunner (plan-only mode, cancellation, end-to-end execution, checkpoints)
  8. MoneyPrinterTurboService & MoneyPrinterTurboAdapter (BaseVideoEngine contract)
  9. VideoEngineRegistry & Capability Resolver integration
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from app.engines.base import EngineCapabilities, EngineJobHandle, EngineProgress, EngineResult
from app.engines.money_printer_turbo.diagnostics import (
    MoneyPrinterTurboEnvironmentStatus,
    check_moneyprinterturbo_environment,
)
from app.engines.money_printer_turbo.models import (
    MaterialInfo,
    MaterialSourceType,
    MoneyPrinterTurboRequest,
    MoneyPrinterTurboResult,
    MoneyPrinterTurboStatusCode,
    ProductionPhase,
    ProductionVideoPlan,
    ScriptSegment,
    SubtitleStyle,
)
from app.engines.money_printer_turbo.music import MusicManager
from app.engines.money_printer_turbo.providers import (
    CompositeMaterialProvider,
    FallbackCanvasGenerator,
    LocalMaterialProvider,
    PexelsMaterialProvider,
    PixabayMaterialProvider,
    ScriptGenerator,
)
from app.engines.money_printer_turbo.runner import MoneyPrinterTurboRunner
from app.engines.money_printer_turbo.subtitles import SubtitleManager
from app.engines.money_printer_turbo_adapter import (
    MoneyPrinterTurboAdapter,
    MoneyPrinterTurboService,
)
from app.engines.registry import VideoEngineRegistry


# ---------------------------------------------------------------------------
# 1. DATA MODELS & SCHEMAS
# ---------------------------------------------------------------------------

class TestDataModels:

    def test_status_codes(self):
        assert MoneyPrinterTurboStatusCode.READY.value == "READY"
        assert MoneyPrinterTurboStatusCode.FFMPEG_MISSING.value == "FFMPEG_MISSING"
        assert MoneyPrinterTurboStatusCode.API_KEY_MISSING.value == "API_KEY_MISSING"
        assert MoneyPrinterTurboStatusCode.MOCK.value == "MOCK"

    def test_material_info_defaults(self):
        mat = MaterialInfo(
            material_id="mat_001",
            provider="pexels",
            source_url="https://pexels.com/video/123",
            local_path="/tmp/video.mp4",
            duration_seconds=12.5,
        )
        assert mat.material_id == "mat_001"
        assert mat.provider == "pexels"
        assert mat.width == 1920
        assert mat.height == 1080
        assert "Free" in mat.license

    def test_script_segment_creation(self):
        seg = ScriptSegment(
            segment_index=0,
            text="Consistency creates momentum.",
            search_terms=["consistency", "momentum"],
        )
        assert seg.segment_index == 0
        assert seg.text == "Consistency creates momentum."
        assert len(seg.search_terms) == 2

    def test_request_defaults(self):
        req = MoneyPrinterTurboRequest(topic="Mindset")
        assert req.topic == "Mindset"
        assert req.aspect_ratio == "9:16"
        assert req.fps == 30
        assert req.subtitle_enabled is True
        assert req.music_enabled is True
        assert req.plan_only is False

    def test_result_structure(self):
        res = MoneyPrinterTurboResult(
            job_id="job-99",
            status="COMPLETED",
            success=True,
            output_path="/tmp/final.mp4",
            duration=15.0,
        )
        assert res.success is True
        assert res.engine == "moneyprinterturbo"
        assert res.engine_version == "1.2.5"
        assert res.upstream_commit == "c18e38ffc008cf510b66b72a08f5d023f79391ab"


# ---------------------------------------------------------------------------
# 2. DIAGNOSTICS
# ---------------------------------------------------------------------------

class TestDiagnostics:

    def test_mock_mode_diagnostics(self, monkeypatch):
        monkeypatch.setenv("MONEYPRINTERTURBO_MOCK_MODE", "true")
        status = check_moneyprinterturbo_environment(allow_mock=True)
        assert status.status_code == MoneyPrinterTurboStatusCode.MOCK
        assert status.is_available is True
        assert status.is_mock is True
        assert status.ffmpeg_available is True

    def test_missing_dependencies_detection(self):
        with patch.dict("sys.modules", {"requests": None}):
            # Simulate missing requests module
            status = check_moneyprinterturbo_environment(allow_mock=False)
            assert isinstance(status, MoneyPrinterTurboEnvironmentStatus)

    def test_missing_ffmpeg_detection(self):
        with patch("app.engines.money_printer_turbo.diagnostics.get_ffmpeg_binary", return_value=None):
            status = check_moneyprinterturbo_environment(allow_mock=False)
            assert status.status_code == MoneyPrinterTurboStatusCode.FFMPEG_MISSING
            assert status.is_available is False
            assert status.ffmpeg_available is False

    def test_real_diagnostics_fields(self):
        status = check_moneyprinterturbo_environment(allow_mock=False)
        assert hasattr(status, "ffmpeg_available")
        assert hasattr(status, "edge_tts_available")
        assert hasattr(status, "pexels_configured")
        assert hasattr(status, "pixabay_configured")
        assert hasattr(status, "local_materials_count")
        assert hasattr(status, "diagnostic_message")


# ---------------------------------------------------------------------------
# 3. SCRIPT GENERATOR
# ---------------------------------------------------------------------------

class TestScriptGenerator:

    def test_mode_a_topic_generation(self):
        segments = ScriptGenerator.generate_or_parse_script(
            topic="Discipline and Growth",
            target_duration=20.0,
        )
        assert len(segments) >= 3
        assert any("Discipline" in s.text or "courage" in s.text.lower() for s in segments)
        assert all(len(s.search_terms) > 0 for s in segments)

    def test_mode_b_user_script_parsing(self):
        user_script = (
            "The James Webb Space Telescope opened our eyes to the early cosmos. "
            "It captures infrared light from billions of light years away! "
            "Astronomers can now analyze planetary atmospheres like never before."
        )
        segments = ScriptGenerator.generate_or_parse_script(
            user_script=user_script,
        )
        assert len(segments) == 3
        assert "James Webb" in segments[0].text
        assert "infrared" in segments[1].text
        assert "Astronomers" in segments[2].text
        assert any("telescope" in kw or "cosmos" in kw or "james" in kw for kw in segments[0].search_terms)

    def test_keyword_extraction(self):
        keywords = ScriptGenerator._extract_keywords("Artificial intelligence transforms modern medicine and healthcare.")
        assert len(keywords) >= 1
        assert "artificial" in keywords or "intelligence" in keywords or "transforms" in keywords


# ---------------------------------------------------------------------------
# 4. MATERIAL PROVIDERS
# ---------------------------------------------------------------------------

class TestMaterialProviders:

    def test_pexels_unconfigured_skips(self, tmp_path):
        provider = PexelsMaterialProvider(api_key="")
        assert provider.is_configured is False
        mat = provider.search_and_download("mountains", 5.0, "9:16", tmp_path)
        assert mat is None

    def test_pixabay_unconfigured_skips(self, tmp_path):
        provider = PixabayMaterialProvider(api_key="")
        assert provider.is_configured is False
        mat = provider.search_and_download("sunset", 5.0, "16:9", tmp_path)
        assert mat is None

    def test_local_provider_finds_media(self, tmp_path):
        media_dir = tmp_path / "stock"
        media_dir.mkdir()
        (media_dir / "ocean_waves.mp4").write_bytes(b"\x00" * 100)

        provider = LocalMaterialProvider(local_dir=media_dir)
        mat = provider.search_and_download("ocean waves", 5.0, "9:16", tmp_path)
        assert mat is not None
        assert "ocean_waves" in mat.local_path

    def test_fallback_canvas_generator(self, tmp_path):
        canvas_out = tmp_path / "canvas.png"
        res = FallbackCanvasGenerator.generate_backdrop_image(
            text="Test Scene",
            output_path=canvas_out,
            width=540,
            height=960,
        )
        assert res.exists()
        assert res.stat().st_size > 0

    def test_composite_provider_cascade(self, tmp_path):
        provider = CompositeMaterialProvider(
            pexels_key="",
            pixabay_key="",
            local_dir=tmp_path / "nonexistent",
        )
        mat = provider.search_and_download("cyberpunk city", 4.0, "9:16", tmp_path)
        assert mat is not None
        assert mat.provider == "canvas_backdrop"
        assert Path(mat.local_path).exists()


# ---------------------------------------------------------------------------
# 5. SUBTITLE MANAGER
# ---------------------------------------------------------------------------

class TestSubtitleManager:

    def test_srt_timestamp_formatting(self):
        ts = SubtitleManager.format_timestamp_srt(65.500)
        assert ts == "00:01:05,500"

    def test_ass_timestamp_formatting(self):
        ts = SubtitleManager.format_timestamp_ass(65.500)
        assert ts == "0:01:05.50"

    def test_generate_srt(self, tmp_path):
        segments = [
            ScriptSegment(segment_index=0, text="First sentence.", start_second=0.0, end_second=3.0),
            ScriptSegment(segment_index=1, text="Second sentence.", start_second=3.0, end_second=6.5),
        ]
        srt_file = tmp_path / "test.srt"
        SubtitleManager.generate_srt(segments, srt_file)
        assert srt_file.exists()
        content = srt_file.read_text(encoding="utf-8")
        assert "00:00:00,000 --> 00:00:03,000" in content
        assert "First sentence." in content
        assert "00:00:03,000 --> 00:00:06,500" in content
        assert "Second sentence." in content

    def test_generate_ass(self, tmp_path):
        segments = [
            ScriptSegment(segment_index=0, text="Dramatic speech.", start_second=0.0, end_second=4.0),
        ]
        ass_file = tmp_path / "test.ass"
        SubtitleManager.generate_ass(segments, ass_file, style=SubtitleStyle.CENTER)
        assert ass_file.exists()
        content = ass_file.read_text(encoding="utf-8")
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "Dramatic speech." in content

    def test_ffmpeg_subtitle_filter_path_escaping(self, tmp_path):
        sub_path = tmp_path / "subs.srt"
        sub_filter = SubtitleManager.get_ffmpeg_subtitle_filter(sub_path)
        assert "subtitles=" in sub_filter
        # Path inside quotes should have forward slashes for cross-platform FFmpeg parsing
        path_part = sub_filter.split("'")[1]
        assert "/" in path_part or len(path_part) > 0
        # If path has a drive letter, verify colon is escaped as \:
        if ":" in str(sub_path):
            assert "\\:" in path_part


# ---------------------------------------------------------------------------
# 6. MUSIC MANAGER
# ---------------------------------------------------------------------------

class TestMusicManager:

    def test_list_and_discover_tracks(self, tmp_path):
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        (music_dir / "ambient_calm.mp3").write_bytes(b"\x00" * 50)
        (music_dir / "energetic_beat.wav").write_bytes(b"\x00" * 50)

        manager = MusicManager(music_dir=music_dir)
        tracks = manager.list_tracks()
        assert len(tracks) == 2
        assert "ambient_calm.mp3" in tracks
        assert "energetic_beat.wav" in tracks

    def test_ensure_default_bgm_synthesizes_audio(self, tmp_path):
        manager = MusicManager(music_dir=tmp_path)
        bgm_path = tmp_path / "test_ambient.wav"
        res = manager.ensure_default_bgm(bgm_path)
        assert res.exists()
        assert res.stat().st_size > 1000  # Synthesized audio waveform

    def test_get_track_partial_match(self, tmp_path):
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        (music_dir / "cinematic_drone_space.mp3").write_bytes(b"\x00" * 50)

        manager = MusicManager(music_dir=music_dir)
        track = manager.get_track_path("drone")
        assert track is not None
        assert "cinematic_drone_space.mp3" in track.name


# ---------------------------------------------------------------------------
# 7. RUNNER
# ---------------------------------------------------------------------------

class TestMoneyPrinterTurboRunner:

    def test_runner_initialization(self, tmp_path):
        runner = MoneyPrinterTurboRunner(output_dir=tmp_path / "out")
        assert runner.output_dir.exists()
        assert runner.materials_dir.exists()
        assert runner.music_dir.exists()

    def test_plan_only_mode_execution(self, tmp_path):
        runner = MoneyPrinterTurboRunner(output_dir=tmp_path / "out")
        req = MoneyPrinterTurboRequest(
            topic="Future of Space Travel",
            target_duration_seconds=15.0,
            plan_only=True,
        )
        result = runner.execute_production_video(req)
        assert result.success is True
        assert result.status == "PLAN_COMPLETE"
        assert "plan" in result.telemetry
        assert result.telemetry["plan"]["segments_count"] >= 2

    def test_cancel_nonexistent_job(self, tmp_path):
        runner = MoneyPrinterTurboRunner(output_dir=tmp_path / "out")
        assert runner.cancel("nonexistent-job-id") is False

    def test_runner_environment_check_failure(self, tmp_path):
        runner = MoneyPrinterTurboRunner(output_dir=tmp_path / "out")
        req = MoneyPrinterTurboRequest(topic="Testing")

        with patch("app.engines.money_printer_turbo.runner.check_moneyprinterturbo_environment") as mock_chk:
            mock_chk.return_value = MoneyPrinterTurboEnvironmentStatus(
                status_code=MoneyPrinterTurboStatusCode.FFMPEG_MISSING,
                is_available=False,
                is_mock=False,
                ffmpeg_available=False,
                ffmpeg_path=None,
                edge_tts_available=True,
                pexels_configured=False,
                pixabay_configured=False,
                local_materials_path=None,
                local_materials_count=0,
                missing_dependencies=[],
                missing_api_keys=[],
                diagnostic_message="FFmpeg missing.",
            )
            result = runner.execute_production_video(req)
            assert result.success is False
            assert result.status == MoneyPrinterTurboStatusCode.FFMPEG_MISSING.value


# ---------------------------------------------------------------------------
# 8. SERVICE & ADAPTER
# ---------------------------------------------------------------------------

class TestMoneyPrinterTurboAdapter:

    def test_adapter_properties(self, tmp_path):
        service = MoneyPrinterTurboService(output_dir=tmp_path / "out")
        adapter = MoneyPrinterTurboAdapter(service=service)

        assert adapter.engine_id == "moneyprinterturbo"
        assert "MoneyPrinterTurbo" in adapter.display_name
        assert "production" in adapter.description.lower()

        caps = adapter.capabilities
        assert isinstance(caps, EngineCapabilities)
        assert caps.native_long_video is True
        assert caps.audio_generation is True
        assert caps.cancellation is True

    def test_list_models(self, tmp_path):
        service = MoneyPrinterTurboService(output_dir=tmp_path / "out")
        adapter = MoneyPrinterTurboAdapter(service=service)
        models = adapter.list_models()
        assert len(models) >= 1
        assert "production" in models[0]["name"].lower()
        assert models[0]["supports_subtitles"] is True
        assert models[0]["supports_bgm"] is True

    def test_validate_generation_settings(self, tmp_path):
        service = MoneyPrinterTurboService(output_dir=tmp_path / "out")
        adapter = MoneyPrinterTurboAdapter(service=service)

        # Valid with topic
        val1 = adapter.validate_generation({"topic": "Quantum Computing", "duration": 30.0})
        assert val1["valid"] is True

        # Valid with script
        val2 = adapter.validate_generation({"script": "Deep in the ocean, mysterious life thrives.", "duration": 15.0})
        assert val2["valid"] is True

        # Invalid: missing topic and script
        val3 = adapter.validate_generation({"duration": 15.0})
        assert val3["valid"] is False
        assert len(val3["errors"]) >= 1

        # Invalid: too short
        val4 = adapter.validate_generation({"topic": "Short", "duration": 2.0})
        assert val4["valid"] is False

    def test_submit_and_wait_result_with_mocked_runner(self, tmp_path):
        service = MoneyPrinterTurboService(output_dir=tmp_path / "out")
        adapter = MoneyPrinterTurboAdapter(service=service)
        service.initialize()

        mock_res = MoneyPrinterTurboResult(
            job_id="test-job-01",
            status="COMPLETED",
            success=True,
            output_path=str(tmp_path / "out.mp4"),
            output_files=[str(tmp_path / "out.mp4")],
            duration=15.0,
        )

        progress_events = []
        def on_prog(p: EngineProgress):
            progress_events.append(p)

        with patch.object(service._runner, "execute_production_video", return_value=mock_res):
            handle = adapter.submit_generation({"topic": "Innovations", "duration": 15.0}, on_prog)
            assert isinstance(handle, EngineJobHandle)
            assert handle.engine_id == "moneyprinterturbo"

            res = adapter.wait_for_result(handle)
            assert isinstance(res, EngineResult)
            assert res.success is True
            assert len(res.output_files) == 1


# ---------------------------------------------------------------------------
# 9. REGISTRY & RESOLVER INTEGRATION
# ---------------------------------------------------------------------------

class TestRegistryAndResolverIntegration:

    def test_moneyprinterturbo_in_registry(self):
        from app.engines.registry import get_engine_registry
        registry = get_engine_registry()
        engine = registry.get_engine("moneyprinterturbo")
        assert engine is not None
        assert engine.engine_id == "moneyprinterturbo"
        assert engine.capabilities.native_long_video is True

    def test_registry_contains_all_seven_engines(self):
        from app.engines.registry import get_engine_registry
        registry = get_engine_registry()
        ids = registry.list_engine_ids()

        assert "wan2gp" in ids
        assert "ltx-video" in ids
        assert "ltx-2" in ids
        assert "minimax-h3" in ids
        assert "minimax-h3-longvideo" in ids
        assert "minimax-h3-director" in ids
        assert "moneyprinterturbo" in ids
