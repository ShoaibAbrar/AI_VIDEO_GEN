"""
MiniMax H3 LongVideos Continuity Coordinator.

Manages inter-chunk visual and audio continuity for sliding-window long video generation:

  Visual continuity:
    - After each chunk completes, extracts the final frame (PIL Image) using FFmpeg/PIL.
    - Passes that frame as the image_start / FL2VA conditioning input to the next chunk.
    - Stores extracted frame to disk for resume-on-failure.

  Audio continuity:
    - Tracks raw audio segment paths per chunk.
    - Applies linear cross-fade between consecutive audio segments using soundfile + numpy.
    - Concatenates all audio segments into a single output WAV.

Architecture note:
  The latent-handoff mechanism (injecting previous-chunk video latents directly into the
  next H3 diffusion pass) is the documented pattern from Smite79/MiniMax-H3-Longvideos.
  This implementation reproduces the pattern at the Python/PIL/FFmpeg level without
  copying or adapting the ComfyUI node code.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from app.core.logging_config import logger
from app.engines.minimax_h3_longvideos.models import LongVideoChunk


class H3LongVideoContinuityCoordinator:
    """
    Coordinates frame-level visual handoff and audio cross-fade stitching
    between consecutive LongVideoChunks.
    """

    def __init__(
        self,
        output_dir: str | Path,
        audio_crossfade_duration_seconds: float = 0.2,
        audio_sample_rate: int = 32000,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_crossfade_duration_seconds = audio_crossfade_duration_seconds
        self.audio_sample_rate = audio_sample_rate

    # ------------------------------------------------------------------
    # Visual continuity
    # ------------------------------------------------------------------

    def extract_final_frame(
        self,
        video_path: str | Path,
        chunk_index: int,
    ) -> Optional[str]:
        """
        Extracts the last frame from a completed chunk video.
        Returns path to saved PNG, or None on failure.

        Strategy:
          1. Try FFmpeg (subprocess) for precise frame extraction.
          2. Fallback: OpenCV if available.
          3. Final fallback: PIL-based seek (for static test images).
        """
        video_path = Path(video_path)
        if not video_path.exists():
            logger.warning(f"H3Continuity: video path not found: {video_path}")
            return None

        frame_path = self.output_dir / f"chunk_{chunk_index:04d}_final_frame.png"

        # 1. Try FFmpeg
        extracted = self._extract_frame_ffmpeg(video_path, frame_path)
        if extracted and frame_path.exists():
            logger.info(f"H3Continuity: extracted final frame via FFmpeg → {frame_path}")
            return str(frame_path)

        # 2. Try OpenCV
        extracted = self._extract_frame_opencv(video_path, frame_path)
        if extracted and frame_path.exists():
            logger.info(f"H3Continuity: extracted final frame via OpenCV → {frame_path}")
            return str(frame_path)

        logger.warning(
            f"H3Continuity: could not extract final frame from {video_path} "
            "(FFmpeg and OpenCV both unavailable or failed)."
        )
        return None

    def _extract_frame_ffmpeg(
        self, video_path: Path, output_path: Path
    ) -> bool:
        """Uses FFmpeg to extract the last frame from the video."""
        try:
            import subprocess
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-sseof", "-0.1",
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-q:v", "1",
                    str(output_path),
                ],
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0 and output_path.exists()
        except Exception as e:
            logger.debug(f"H3Continuity: FFmpeg frame extraction failed: {e}")
            return False

    def _extract_frame_opencv(
        self, video_path: Path, output_path: Path
    ) -> bool:
        """Uses OpenCV to extract the last frame from the video."""
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return False
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames > 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                cv2.imwrite(str(output_path), frame)
                return output_path.exists()
            return False
        except Exception as e:
            logger.debug(f"H3Continuity: OpenCV frame extraction failed: {e}")
            return False

    def apply_conditioning_to_chunk(
        self,
        chunk: LongVideoChunk,
        previous_frame_path: Optional[str],
    ) -> LongVideoChunk:
        """
        Injects the previous chunk's final frame as FL2VA conditioning into this chunk.
        Modifies and returns the chunk (does not copy).
        """
        if previous_frame_path and Path(previous_frame_path).exists():
            chunk.conditioning_image_path = previous_frame_path
            logger.debug(
                f"H3Continuity: chunk[{chunk.chunk_index}] "
                f"conditioned on frame → {previous_frame_path}"
            )
        return chunk

    # ------------------------------------------------------------------
    # Audio continuity
    # ------------------------------------------------------------------

    def crossfade_and_concat_audio(
        self,
        audio_paths: List[str],
        output_path: str | Path,
    ) -> Optional[str]:
        """
        Concatenates a list of audio file paths into a single WAV with linear
        cross-fades between consecutive segments.

        Returns the output path on success, or None on failure.
        """
        output_path = Path(output_path)
        valid_paths = [p for p in audio_paths if p and Path(p).exists()]

        if not valid_paths:
            logger.warning("H3Continuity: no valid audio segments to concatenate.")
            return None

        if len(valid_paths) == 1:
            shutil.copy2(valid_paths[0], output_path)
            return str(output_path)

        try:
            import numpy as np
            import soundfile as sf  # type: ignore

            segments: List[Any] = []
            sr: Optional[int] = None
            channels: int = 1

            for path in valid_paths:
                data, file_sr = sf.read(path, always_2d=True)
                if sr is None:
                    sr = file_sr
                    channels = data.shape[1]
                elif file_sr != sr:
                    # Skip mismatched sample rate
                    logger.warning(
                        f"H3Continuity: audio sample rate mismatch {file_sr} != {sr}, skipping {path}"
                    )
                    continue
                segments.append(data)

            if not segments or sr is None:
                return None

            crossfade_samples = int(self.audio_crossfade_duration_seconds * sr)
            combined = segments[0]

            for seg in segments[1:]:
                if crossfade_samples > 0 and len(combined) >= crossfade_samples and len(seg) >= crossfade_samples:
                    fade_out = np.linspace(1.0, 0.0, crossfade_samples).reshape(-1, 1)
                    fade_in = np.linspace(0.0, 1.0, crossfade_samples).reshape(-1, 1)
                    # Blend the last N samples of combined with first N samples of seg
                    combined[-crossfade_samples:] = (
                        combined[-crossfade_samples:] * fade_out
                        + seg[:crossfade_samples] * fade_in
                    )
                    combined = np.concatenate([combined, seg[crossfade_samples:]], axis=0)
                else:
                    combined = np.concatenate([combined, seg], axis=0)

            sf.write(str(output_path), combined, sr)
            logger.info(f"H3Continuity: audio concatenated ({len(valid_paths)} segments) → {output_path}")
            return str(output_path)

        except ImportError:
            logger.warning("H3Continuity: soundfile/numpy not available; falling back to raw concatenation.")
            return self._concat_audio_raw(valid_paths, output_path)
        except Exception as e:
            logger.error(f"H3Continuity: audio crossfade failed: {e}", exc_info=True)
            return self._concat_audio_raw(valid_paths, output_path)

    def _concat_audio_raw(
        self,
        audio_paths: List[str],
        output_path: Path,
    ) -> Optional[str]:
        """
        Fallback: byte-level concatenation for WAV files (skips headers beyond first).
        Only valid for WAV files with identical format.
        """
        try:
            with open(output_path, "wb") as out_f:
                for i, path in enumerate(audio_paths):
                    with open(path, "rb") as f:
                        data = f.read()
                    if i == 0:
                        out_f.write(data)
                    else:
                        # Skip 44-byte WAV header for subsequent files
                        out_f.write(data[44:])
            return str(output_path)
        except Exception as e:
            logger.error(f"H3Continuity: raw audio concatenation failed: {e}")
            return None

    # ------------------------------------------------------------------
    # State checkpointing
    # ------------------------------------------------------------------

    def save_chunk_state(
        self,
        chunk: LongVideoChunk,
        state: Dict[str, Any],
        job_dir: Path,
    ) -> None:
        """Persists per-chunk generation state for resume-on-failure."""
        try:
            import json
            state_file = job_dir / f"chunk_{chunk.chunk_index:04d}_state.json"
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"H3Continuity: failed to save chunk state: {e}")

    def load_chunk_state(
        self,
        chunk_index: int,
        job_dir: Path,
    ) -> Optional[Dict[str, Any]]:
        """Loads previously checkpointed chunk state if present."""
        try:
            import json
            state_file = job_dir / f"chunk_{chunk_index:04d}_state.json"
            if state_file.exists():
                with open(state_file) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"H3Continuity: failed to load chunk state: {e}")
        return None
