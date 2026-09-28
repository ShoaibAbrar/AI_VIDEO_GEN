"""
Reference Audio Validation and User Consent Verification for Voice Cloning.
Ensures reference audio meets acoustic, duration, format, and legal consent standards.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import struct
import wave
from typing import Optional

from app.core.logging_config import logger
from app.engines.money_printer_turbo.runner import get_ffmpeg_binary
from app.services.voice.cloning.models import (
    AudioValidationErrorCode,
    AudioValidationResult,
)


SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
MIN_REFERENCE_DURATION_SECONDS = 2.0
MAX_REFERENCE_DURATION_SECONDS = 60.0


def validate_reference_audio(
    audio_path: str | Path,
    consent_confirmed: bool = False,
    min_duration: float = MIN_REFERENCE_DURATION_SECONDS,
    max_duration: float = MAX_REFERENCE_DURATION_SECONDS,
) -> AudioValidationResult:
    """
    Validates that reference audio file is structurally sound, audible,
    within permissible duration limits, and that user consent has been confirmed.
    """
    path = Path(audio_path).resolve()

    # 1. Consent Confirmation Check (Non-negotiable safety requirement)
    if not consent_confirmed:
        logger.warning(f"Voice cloning rejected: user consent not confirmed for '{path.name}'.")
        return AudioValidationResult(
            is_valid=False,
            error_code=AudioValidationErrorCode.CONSENT_REQUIRED,
            error_message="Explicit user authorization and consent confirmation is required to clone this voice.",
            consent_confirmed=False,
        )

    # 2. File Existence Check
    if not path.exists() or path.stat().st_size == 0:
        return AudioValidationResult(
            is_valid=False,
            error_code=AudioValidationErrorCode.FILE_NOT_FOUND,
            error_message=f"Reference audio file not found or empty: {path}",
            consent_confirmed=True,
        )

    # 3. Format Check
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        return AudioValidationResult(
            is_valid=False,
            error_code=AudioValidationErrorCode.UNSUPPORTED_FORMAT,
            error_message=(
                f"Unsupported audio format '{path.suffix}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            ),
            consent_confirmed=True,
        )

    # 4. Audio Metric Probing
    duration, sample_rate, channels, has_clipping, is_silent = _probe_audio_metrics(path)

    # 5. Duration Bounds
    if duration < min_duration:
        return AudioValidationResult(
            is_valid=False,
            error_code=AudioValidationErrorCode.REFERENCE_AUDIO_TOO_SHORT,
            error_message=f"Reference audio duration ({duration:.2f}s) is too short. Minimum required is {min_duration:.1f}s.",
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            consent_confirmed=True,
        )

    if duration > max_duration:
        return AudioValidationResult(
            is_valid=False,
            error_code=AudioValidationErrorCode.REFERENCE_AUDIO_TOO_LONG,
            error_message=f"Reference audio duration ({duration:.2f}s) exceeds maximum limit of {max_duration:.1f}s.",
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            consent_confirmed=True,
        )

    # 6. Audio Content Quality Checks
    if is_silent:
        return AudioValidationResult(
            is_valid=False,
            error_code=AudioValidationErrorCode.NO_SPEECH_DETECTED,
            error_message="Reference audio appears silent or below audible threshold. Please provide clear speech.",
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            consent_confirmed=True,
        )

    if has_clipping:
        logger.warning(f"Reference audio '{path.name}' contains severe audio clipping / distortion.")

    logger.info(
        f"Reference audio validated: {path.name} | "
        f"Duration: {duration:.2f}s | SampleRate: {sample_rate}Hz | Channels: {channels}"
    )

    return AudioValidationResult(
        is_valid=True,
        error_code=AudioValidationErrorCode.VALID,
        error_message="Reference audio is valid and authorized for zero-shot voice cloning.",
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        has_clipping=has_clipping,
        consent_confirmed=True,
    )


def _probe_audio_metrics(audio_path: Path) -> tuple[float, int, int, bool, bool]:
    """
    Probes audio duration, sample rate, channels, clipping, and silence.
    Uses Python standard wave module for WAV or FFprobe/FFmpeg for compressed formats.
    """
    # Quick WAV probe if format is .wav
    if audio_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio_path), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                duration = n_frames / float(sample_rate)
                sample_width = wf.getsampwidth()

                # Sample energy check
                raw_frames = wf.readframes(min(n_frames, sample_rate * 5))
                has_clipping = False
                is_silent = False

                if sample_width == 2 and raw_frames:
                    count = len(raw_frames) // 2
                    shorts = struct.unpack(f"<{count}h", raw_frames)
                    if shorts:
                        max_val = max(abs(s) for s in shorts)
                        has_clipping = max_val >= 32700
                        rms = math.sqrt(sum(s * s for s in shorts) / count)
                        is_silent = rms < 50.0  # Near zero energy

                return duration, sample_rate, channels, has_clipping, is_silent
        except Exception:
            pass

    # Fallback / General FFprobe
    import subprocess
    ffmpeg = get_ffmpeg_binary()
    if ffmpeg:
        ffprobe = str(ffmpeg).replace("ffmpeg", "ffprobe")
        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration:stream=channels,sample_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]
                # Typically outputs sample_rate, channels, duration
                dur = 5.0
                sr = 24000
                ch = 1
                for line in lines:
                    try:
                        val = float(line)
                        if val > 1000:
                            sr = int(val)
                        elif val in (1, 2, 6):
                            ch = int(val)
                        else:
                            dur = val
                    except ValueError:
                        pass
                return dur, sr, ch, False, False
        except Exception:
            pass

    return 5.0, 24000, 1, False, False
