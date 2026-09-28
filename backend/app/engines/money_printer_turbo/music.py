"""
Background Music (BGM) Manager for MoneyPrinterTurbo.
Handles music discovery, volume mixing, looping, and audio ducking.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import struct
import subprocess
from typing import List, Optional
import wave

from app.core.logging_config import logger
from app.orchestration.media_stitcher import get_ffmpeg_binary


class MusicManager:
    """
    Manages background music selection, volume normalization, and audio mixing.
    """

    def __init__(self, music_dir: Optional[str | Path] = None):
        self.music_dir = Path(
            music_dir
            or os.environ.get("MONEYPRINTERTURBO_MUSIC_DIR")
            or "./materials/music"
        )
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def list_tracks(self) -> List[str]:
        """Lists available background audio tracks in the music directory."""
        if not self.music_dir.exists():
            return []
        tracks = []
        for ext in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg"):
            tracks.extend(p.name for p in self.music_dir.glob(ext))
        return sorted(tracks)

    def get_track_path(self, music_name: Optional[str] = None) -> Optional[Path]:
        """Finds named track or defaults to first available track in music library."""
        if not self.music_dir.exists():
            return None

        if music_name:
            exact = self.music_dir / music_name
            if exact.exists():
                return exact
            # Case-insensitive / partial match
            for p in self.music_dir.iterdir():
                if music_name.lower() in p.name.lower() and p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac"):
                    return p

        # Fallback to first track
        available = self.list_tracks()
        if available:
            return self.music_dir / available[0]

        return None

    def ensure_default_bgm(self, output_path: Path) -> Path:
        """
        Creates an ambient low-frequency harmonic background audio track
        if no custom music files exist in library.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path

        sample_rate = 44100
        duration_s = 60.0  # 60 second loop
        num_samples = int(sample_rate * duration_s)

        with wave.open(str(output_path), "w") as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)

            # Generate warm ambient pad chords (A minor: A2 110Hz, C3 130.8Hz, E3 164.8Hz)
            frames = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                # Slow volume swell
                envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 0.05 * t)
                # Harmonic superposition
                v1 = math.sin(2 * math.pi * 110.0 * t)
                v2 = 0.7 * math.sin(2 * math.pi * 130.81 * t)
                v3 = 0.5 * math.sin(2 * math.pi * 164.81 * t)
                v4 = 0.3 * math.sin(2 * math.pi * 220.0 * t)
                sample_val = int(3000 * envelope * (v1 + v2 + v3 + v4))
                sample_val = max(-32768, min(32767, sample_val))
                data = struct.pack("<hh", sample_val, sample_val)
                frames.extend(data)

            wav_file.writeframes(frames)

        logger.info(f"Generated default ambient BGM track → {output_path}")
        return output_path

    def mix_voice_and_bgm(
        self,
        voice_path: Path,
        bgm_path: Optional[Path],
        output_path: Path,
        total_duration: float,
        bgm_volume: float = 0.18,
    ) -> Path:
        """
        Mixes voiceover narration with background music ducked underneath using FFmpeg.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not voice_path.exists():
            raise FileNotFoundError(f"Voice track not found: {voice_path}")

        # If no BGM, copy/transcode voice track directly
        if not bgm_path or not bgm_path.exists():
            return self._normalize_voice_only(voice_path, output_path)

        ffmpeg = get_ffmpeg_binary()
        if not ffmpeg:
            return self._normalize_voice_only(voice_path, output_path)

        # FFmpeg filter:
        # Loop BGM to cover total duration, adjust volume, add 2s fade-out at end, and mix with voice
        fade_out_start = max(0.5, total_duration - 2.0)
        filter_complex = (
            f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.2f},"
            f"afade=t=out:st={fade_out_start:.2f}:d=2.0[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[outa]"
        )

        cmd = [
            ffmpeg, "-y",
            "-i", str(voice_path.resolve()),
            "-i", str(bgm_path.resolve()),
            "-filter_complex", filter_complex,
            "-map", "[outa]",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path.resolve()),
        ]

        try:
            logger.info(f"Mixing voice + BGM (vol={bgm_volume:.2f}) → {output_path.name}")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return output_path
            else:
                logger.warning(f"FFmpeg audio mix non-zero code {res.returncode}: {res.stderr[:200]}")
        except Exception as exc:
            logger.error(f"Error during audio mix: {exc}", exc_info=True)

        return self._normalize_voice_only(voice_path, output_path)

    @staticmethod
    def _normalize_voice_only(voice_path: Path, output_path: Path) -> Path:
        """Copies voice audio to destination if mixing is skipped or fails."""
        import shutil
        shutil.copy2(voice_path, output_path)
        return output_path
