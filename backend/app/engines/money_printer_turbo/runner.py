"""
Core Production Pipeline Runner for MoneyPrinterTurbo.
Orchestrates end-to-end video synthesis:
  Topic/Script → TTS Voiceover → Subtitles → Stock Footage Acquisition → Video Composition → BGM Audio Mix → Final MP4.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from app.core.logging_config import logger
from app.engines.money_printer_turbo.diagnostics import check_moneyprinterturbo_environment
from app.engines.money_printer_turbo.models import (
    MaterialInfo,
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
    ScriptGenerator,
)
from app.engines.money_printer_turbo.subtitles import SubtitleManager
from app.orchestration.media_stitcher import MediaStitcher, get_ffmpeg_binary
from app.services.voice.edge_tts_engine import EdgeTTSVoiceEngine


class MoneyPrinterTurboRunner:
    """
    Canonical production video synthesis engine for MoneyPrinterTurbo.
    Transforms scripts or topics into fully edited, subtitled short videos with BGM.
    """

    def __init__(
        self,
        output_dir: Optional[str | Path] = None,
        materials_dir: Optional[str | Path] = None,
        music_dir: Optional[str | Path] = None,
        voice_engine: Optional[EdgeTTSVoiceEngine] = None,
    ):
        self.output_dir = Path(
            output_dir
            or os.environ.get("MONEYPRINTERTURBO_OUTPUT_DIR")
            or "./output/moneyprinterturbo"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.materials_dir = Path(
            materials_dir
            or os.environ.get("LOCAL_MATERIAL_DIR")
            or "./materials"
        )
        self.materials_dir.mkdir(parents=True, exist_ok=True)

        self.music_dir = Path(
            music_dir
            or os.environ.get("MONEYPRINTERTURBO_MUSIC_DIR")
            or "./materials/music"
        )
        self.music_dir.mkdir(parents=True, exist_ok=True)

        self.voice_engine = voice_engine or EdgeTTSVoiceEngine()
        self.music_manager = MusicManager(music_dir=self.music_dir)
        self.media_stitcher = MediaStitcher(output_dir=str(self.output_dir))

        self._active_cancellations: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Main Execution Entry Point
    # ------------------------------------------------------------------

    def execute_production_video(
        self,
        request: MoneyPrinterTurboRequest,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> MoneyPrinterTurboResult:
        """
        Executes end-to-end video synthesis pipeline according to request parameters.
        """
        job_id = request.job_id or str(uuid.uuid4())
        cancel_event = threading.Event()
        with self._lock:
            self._active_cancellations[job_id] = cancel_event

        start_time = time.time()
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        warnings: List[str] = []

        logger.info(
            f"[MoneyPrinterTurbo] Starting production job {job_id} | "
            f"Topic: '{request.topic}' | Aspect: {request.aspect_ratio}"
        )

        def _report(pct: float, phase: str, msg: str):
            if progress_callback and not cancel_event.is_set():
                progress_callback(pct, f"[{phase}] {msg}")

        try:
            # 1. Environment & Diagnostics Check
            _report(2.0, ProductionPhase.INITIALIZING, "Checking rendering environment...")
            diag = check_moneyprinterturbo_environment(
                pexels_api_key=request.pexels_api_key,
                pixabay_api_key=request.pixabay_api_key,
                local_material_dir=request.local_material_dir or self.materials_dir,
            )

            if not diag.is_available:
                logger.error(f"[MoneyPrinterTurbo] Environment check failed: {diag.diagnostic_message}")
                return MoneyPrinterTurboResult(
                    job_id=job_id,
                    status=diag.status_code.value,
                    success=False,
                    error_message=diag.diagnostic_message,
                    error_code=diag.status_code.value,
                )

            # 2. Script Generation / Parsing
            _report(8.0, ProductionPhase.SCRIPT_GENERATION, "Parsing/generating narration script...")
            segments = ScriptGenerator.generate_or_parse_script(
                topic=request.topic,
                user_script=request.script,
                language=request.language,
                target_duration=request.target_duration_seconds,
            )

            if not segments:
                return MoneyPrinterTurboResult(
                    job_id=job_id,
                    status="FAILED",
                    success=False,
                    error_message="Script generation produced no segments.",
                    error_code="SCRIPT_EMPTY",
                )

            full_script_text = " ".join(s.text for s in segments)
            logger.info(f"[MoneyPrinterTurbo] Script prepared: {len(segments)} segments.")

            # Plan-only mode
            if request.plan_only:
                plan_dict = {
                    "topic": request.topic,
                    "segments_count": len(segments),
                    "segments": [s.text for s in segments],
                    "aspect_ratio": request.aspect_ratio,
                    "voice": request.voice_name,
                }
                return MoneyPrinterTurboResult(
                    job_id=job_id,
                    status="PLAN_COMPLETE",
                    success=True,
                    source_materials=[],
                    voice=request.voice_name,
                    music=request.music_name,
                    execution_time_seconds=round(time.time() - start_time, 2),
                    telemetry={"plan": plan_dict},
                )

            if cancel_event.is_set():
                return self._cancelled_result(job_id)

            # 3. Voiceover Synthesis (Edge TTS)
            _report(18.0, ProductionPhase.VOICE_GENERATION, "Synthesizing narration voiceover...")
            voice_dir = job_dir / "voice"
            voice_dir.mkdir(parents=True, exist_ok=True)

            timeline_cursor = 0.0
            for idx, seg in enumerate(segments):
                if cancel_event.is_set():
                    return self._cancelled_result(job_id)

                audio_path = voice_dir / f"segment_{idx:03d}.mp3"
                seg_dur = self._synthesize_segment_voice(
                    text=seg.text,
                    voice_name=request.voice_name,
                    voice_rate=request.voice_rate,
                    output_path=audio_path,
                )
                seg.audio_path = str(audio_path.resolve())
                seg.duration_seconds = seg_dur
                seg.start_second = timeline_cursor
                seg.end_second = timeline_cursor + seg_dur
                timeline_cursor += seg_dur

            total_duration = timeline_cursor
            logger.info(f"[MoneyPrinterTurbo] Voiceover completed. Total duration: {total_duration:.2f}s")

            # Concatenate voice segments into master narration track
            master_voice_path = job_dir / "master_voice.mp3"
            self._concat_audio_segments([Path(s.audio_path) for s in segments if s.audio_path], master_voice_path)

            if cancel_event.is_set():
                return self._cancelled_result(job_id)

            # 4. Subtitle Generation
            _report(32.0, ProductionPhase.SUBTITLE_GENERATION, "Compiling subtitles and timing...")
            sub_dir = job_dir / "subtitles"
            sub_dir.mkdir(parents=True, exist_ok=True)

            srt_path = sub_dir / "subtitles.srt"
            ass_path = sub_dir / "subtitles.ass"

            SubtitleManager.generate_srt(segments, srt_path)
            w, h = self._parse_resolution(request.aspect_ratio, request.resolution)
            SubtitleManager.generate_ass(
                segments=segments,
                output_path=ass_path,
                style=request.subtitle_style,
                video_width=w,
                video_height=h,
            )

            # 5. Stock Material Search & Acquisition
            _report(45.0, ProductionPhase.MATERIAL_SEARCH, "Acquiring matching stock video footage...")
            mat_provider = CompositeMaterialProvider(
                pexels_key=request.pexels_api_key,
                pixabay_key=request.pixabay_api_key,
                local_dir=request.local_material_dir or self.materials_dir,
            )
            clips_dir = job_dir / "clips"
            clips_dir.mkdir(parents=True, exist_ok=True)

            source_materials_meta: List[Dict[str, Any]] = []

            for idx, seg in enumerate(segments):
                if cancel_event.is_set():
                    return self._cancelled_result(job_id)

                search_query = " ".join(seg.search_terms) if seg.search_terms else seg.text[:25]
                _report(
                    45.0 + (idx / len(segments)) * 20.0,
                    ProductionPhase.MATERIAL_DOWNLOAD,
                    f"Sourcing footage for clip {idx + 1}/{len(segments)} ('{search_query}')...",
                )

                mat_info = mat_provider.search_and_download(
                    query=search_query,
                    target_duration=seg.duration_seconds,
                    aspect_ratio=request.aspect_ratio,
                    output_dir=clips_dir,
                )
                seg.material = mat_info
                if mat_info:
                    source_materials_meta.append({
                        "segment_index": idx,
                        "provider": mat_info.provider,
                        "source_url": mat_info.source_url,
                        "author": mat_info.author,
                        "license": mat_info.license,
                        "local_path": mat_info.local_path,
                    })

            # Checkpoint metadata
            with open(job_dir / "script.json", "w") as f:
                json.dump([{"idx": s.segment_index, "text": s.text, "dur": s.duration_seconds} for s in segments], f, indent=2)
            with open(job_dir / "materials.json", "w") as f:
                json.dump(source_materials_meta, f, indent=2)

            if cancel_event.is_set():
                return self._cancelled_result(job_id)

            # 6. Video Clip Composition (Scale, Crop, Duration Match)
            _report(68.0, ProductionPhase.VIDEO_COMPOSITION, "Processing & sizing visual clips...")
            rendered_clip_paths: List[Path] = []

            for idx, seg in enumerate(segments):
                if cancel_event.is_set():
                    return self._cancelled_result(job_id)

                clip_out = clips_dir / f"rendered_clip_{idx:03d}.mp4"
                mat_local = seg.material.local_path if seg.material else None

                self._render_single_clip(
                    source_media_path=Path(mat_local) if mat_local else None,
                    duration=seg.duration_seconds,
                    width=w,
                    height=h,
                    fps=request.fps,
                    output_path=clip_out,
                )
                seg.rendered_clip_path = str(clip_out.resolve())
                rendered_clip_paths.append(clip_out)

            # Stitch video clips into master video stream
            stitched_video_raw = job_dir / "stitched_raw_video.mp4"
            self._stitch_video_clips(rendered_clip_paths, stitched_video_raw)

            if cancel_event.is_set():
                return self._cancelled_result(job_id)

            # 7. Background Music & Audio Mix
            _report(82.0, ProductionPhase.AUDIO_MIX, "Balancing dialogue and background music...")
            master_audio_path = job_dir / "master_mixed_audio.mp3"

            bgm_track_path: Optional[Path] = None
            if request.music_enabled:
                bgm_track_path = self.music_manager.get_track_path(request.music_name)
                if not bgm_track_path:
                    # Generate harmonious ambient pad
                    default_bgm = self.music_dir / "ambient_loop.wav"
                    bgm_track_path = self.music_manager.ensure_default_bgm(default_bgm)

            self.music_manager.mix_voice_and_bgm(
                voice_path=master_voice_path,
                bgm_path=bgm_track_path if request.music_enabled else None,
                output_path=master_audio_path,
                total_duration=total_duration,
                bgm_volume=request.music_volume,
            )

            # 8. Final Encoding, Subtitle Burn-In & Muxing
            _report(92.0, ProductionPhase.FINAL_ENCODING, "Finalizing high-definition MP4 stream...")
            final_mp4_path = (
                Path(request.output_video_path)
                if request.output_video_path
                else job_dir / f"production_{job_id}.mp4"
            )

            self._mux_final_video(
                video_raw_path=stitched_video_raw,
                audio_path=master_audio_path,
                subtitle_path=ass_path if request.subtitle_enabled else None,
                subtitle_style=request.subtitle_style,
                output_path=final_mp4_path,
            )

            _report(100.0, ProductionPhase.COMPLETED, "Production video ready.")
            elapsed = round(time.time() - start_time, 2)
            logger.info(f"[MoneyPrinterTurbo] Job {job_id} successfully generated in {elapsed}s: {final_mp4_path}")

            return MoneyPrinterTurboResult(
                job_id=job_id,
                status="COMPLETED",
                success=True,
                output_path=str(final_mp4_path.resolve()),
                output_files=[str(final_mp4_path.resolve()), str(srt_path.resolve())],
                duration=round(total_duration, 2),
                resolution=f"{w}*{h}",
                fps=request.fps,
                audio_present=True,
                subtitle_present=request.subtitle_enabled,
                source_materials=source_materials_meta,
                voice=request.voice_name,
                music=bgm_track_path.name if bgm_track_path else "None",
                warnings=warnings,
                execution_time_seconds=elapsed,
                telemetry={
                    "total_segments": len(segments),
                    "material_provider": request.material_provider.value,
                    "resolution": f"{w}x{h}",
                    "script_character_count": len(full_script_text),
                },
            )

        except Exception as exc:
            logger.error(f"[MoneyPrinterTurbo] Job {job_id} encountered error: {exc}", exc_info=True)
            return MoneyPrinterTurboResult(
                job_id=job_id,
                status="FAILED",
                success=False,
                error_message=str(exc),
                error_code="PRODUCTION_PIPELINE_ERROR",
                execution_time_seconds=round(time.time() - start_time, 2),
            )
        finally:
            with self._lock:
                self._active_cancellations.pop(job_id, None)

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _synthesize_segment_voice(
        self,
        text: str,
        voice_name: str,
        voice_rate: str,
        output_path: Path,
    ) -> float:
        """Synthesizes voice audio for text and returns duration in seconds."""
        # Run async EdgeTTS in synchronous thread runner
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.voice_engine.synthesize_speech(
                    text=text,
                    voice_id=voice_name,
                    output_path=output_path,
                    rate=voice_rate,
                )
            )
            loop.close()
        except Exception as e:
            logger.warning(f"EdgeTTS synthesis failed ({e}), creating silent tone fallback.")
            self._generate_silent_audio(output_path, max(2.0, len(text.split()) * 0.4))

        # Probe duration
        return self._probe_audio_duration(output_path)

    @staticmethod
    def _probe_audio_duration(audio_path: Path) -> float:
        """Probes accurate duration of audio file via FFprobe/FFmpeg."""
        ffmpeg = get_ffmpeg_binary()
        if not ffmpeg:
            return 3.0

        ffprobe = str(ffmpeg).replace("ffmpeg", "ffprobe")
        if shutil.which("ffprobe") or Path(ffprobe).exists():
            cmd = [
                ffprobe if shutil.which("ffprobe") else ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    return max(0.5, float(res.stdout.strip()))
            except Exception:
                pass
        return 3.0

    @staticmethod
    def _generate_silent_audio(output_path: Path, duration_s: float):
        """Generates silent audio file as fallback."""
        import math, struct, wave
        sample_rate = 24000
        with wave.open(str(output_path), "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            f.writeframes(bytearray(int(sample_rate * duration_s * 2)))

    def _concat_audio_segments(self, audio_paths: List[Path], output_path: Path):
        """Concatenates multiple audio segment files into a single master audio track."""
        ffmpeg = get_ffmpeg_binary()
        if not ffmpeg or not audio_paths:
            return

        concat_txt = output_path.parent / "audio_concat.txt"
        with open(concat_txt, "w") as f:
            for p in audio_paths:
                f.write(f"file '{str(p.resolve()).replace(os.sep, '/')}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)

    def _render_single_clip(
        self,
        source_media_path: Optional[Path],
        duration: float,
        width: int,
        height: int,
        fps: int,
        output_path: Path,
    ):
        """
        Scales, crops (centered), duration-loops, and normalizes a single video/image clip.
        """
        ffmpeg = get_ffmpeg_binary()
        if not ffmpeg:
            return

        # Target filter: scale to fill viewport then crop center
        # e.g. "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}"

        is_image = source_media_path and source_media_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")

        if is_image:
            cmd = [
                ffmpeg, "-y",
                "-loop", "1",
                "-i", str(source_media_path.resolve()),
                "-vf", vf,
                "-t", f"{duration:.3f}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(output_path.resolve()),
            ]
        elif source_media_path and source_media_path.exists():
            # Video: loop if video is shorter than duration
            cmd = [
                ffmpeg, "-y",
                "-stream_loop", "-1",
                "-i", str(source_media_path.resolve()),
                "-vf", vf,
                "-t", f"{duration:.3f}",
                "-an",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(output_path.resolve()),
            ]
        else:
            # Generate solid dark slate canvas
            cmd = [
                ffmpeg, "-y",
                "-f", "lavfi",
                "-i", f"color=c=0x111827:s={width}x{height}:r={fps}",
                "-t", f"{duration:.3f}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(output_path.resolve()),
            ]

        subprocess.run(cmd, capture_output=True, timeout=90)

    def _stitch_video_clips(self, clip_paths: List[Path], output_path: Path):
        """Concatenates sequential video clips via FFmpeg concat demuxer."""
        ffmpeg = get_ffmpeg_binary()
        if not ffmpeg:
            return

        concat_txt = output_path.parent / "video_concat.txt"
        with open(concat_txt, "w") as f:
            for p in clip_paths:
                f.write(f"file '{str(p.resolve()).replace(os.sep, '/')}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_path.resolve()),
        ]
        subprocess.run(cmd, capture_output=True, timeout=180)

    def _mux_final_video(
        self,
        video_raw_path: Path,
        audio_path: Path,
        subtitle_path: Optional[Path],
        subtitle_style: SubtitleStyle,
        output_path: Path,
    ):
        """Combines raw video + mixed audio + burns in ASS/SRT subtitles into final MP4."""
        ffmpeg = get_ffmpeg_binary()
        if not ffmpeg:
            return

        if subtitle_path and subtitle_path.exists():
            sub_filter = SubtitleManager.get_ffmpeg_subtitle_filter(subtitle_path, subtitle_style)
            cmd = [
                ffmpeg, "-y",
                "-i", str(video_raw_path.resolve()),
                "-i", str(audio_path.resolve()),
                "-vf", sub_filter,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path.resolve()),
            ]
        else:
            cmd = [
                ffmpeg, "-y",
                "-i", str(video_raw_path.resolve()),
                "-i", str(audio_path.resolve()),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path.resolve()),
            ]

        res = subprocess.run(cmd, capture_output=True, timeout=180)
        if res.returncode != 0 and subtitle_path:
            # Fallback if subtitles filter fails (e.g. fontconfig missing on Windows)
            logger.warning("Subtitles burn-in filter returned non-zero code. Falling back to direct audio-video mux.")
            cmd_fallback = [
                ffmpeg, "-y",
                "-i", str(video_raw_path.resolve()),
                "-i", str(audio_path.resolve()),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path.resolve()),
            ]
            subprocess.run(cmd_fallback, capture_output=True, timeout=120)

    @staticmethod
    def _parse_resolution(aspect_ratio: str, resolution_str: str) -> tuple[int, int]:
        """Resolves target width and height in pixels."""
        if aspect_ratio == "9:16":
            return 1080, 1920
        elif aspect_ratio == "1:1":
            return 1080, 1080
        elif aspect_ratio == "16:9":
            return 1920, 1080
        try:
            parts = resolution_str.split("*") if "*" in resolution_str else resolution_str.split("x")
            return int(parts[0]), int(parts[1])
        except Exception:
            return 1080, 1920

    def cancel(self, job_id: str) -> bool:
        """Signals cancellation for an active job."""
        with self._lock:
            evt = self._active_cancellations.get(job_id)
            if evt:
                evt.set()
                logger.info(f"[MoneyPrinterTurbo] Cancelled job {job_id}")
                return True
        return False

    def _cancelled_result(self, job_id: str) -> MoneyPrinterTurboResult:
        return MoneyPrinterTurboResult(
            job_id=job_id,
            status="CANCELLED",
            success=False,
            error_message="Production pipeline execution cancelled by user.",
            error_code="USER_CANCELLED",
        )
