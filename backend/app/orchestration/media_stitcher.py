"""
Media Stitcher module for Long-Video Orchestration.
Concatenates segmented video clips and multiplexes dialogue audio tracks into unified, playable MP4 outputs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from app.core.exceptions import AppException
from app.core.logging_config import logger
from app.orchestration.models import SceneDefinition


def get_ffmpeg_binary() -> Optional[str]:
    """Resolves system ffmpeg or imageio-ffmpeg portable binary."""
    # 1. System PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    # 2. imageio-ffmpeg package
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    # 3. Wan2GP downloaded ffmpeg in repo root
    repo_ffmpeg = Path("ffmpeg.exe")
    if repo_ffmpeg.exists():
        return str(repo_ffmpeg.resolve())

    return None


class MediaStitcher:
    """
    Concatenates individual scene clips and multiplexes audio dialogue tracks.
    Uses FFmpeg with stream copy and transcoding fallbacks.
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or "./output/long_videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_binary = get_ffmpeg_binary()

    def composite_scene_video_audio(
        self,
        video_path: Path | str,
        audio_path: Path | str,
        output_path: Optional[Path | str] = None,
    ) -> str:
        """
        Combines a generated visual video clip with dialogue audio into a unified MP4.
        """
        v_path = Path(video_path).resolve()
        a_path = Path(audio_path).resolve()

        if not v_path.exists():
            raise FileNotFoundError(f"Video file not found for compositing: {v_path}")
        if not a_path.exists() or a_path.stat().st_size == 0:
            # If audio doesn't exist, return video path directly
            return str(v_path)

        target_path = Path(output_path) if output_path else v_path.parent / f"composed_{v_path.name}"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg = self.ffmpeg_binary or get_ffmpeg_binary()
        if ffmpeg:
            try:
                # Multiplex video stream and audio stream into MP4 container
                cmd = [
                    ffmpeg,
                    "-y",
                    "-i", str(v_path),
                    "-i", str(a_path),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-movflags", "+faststart",
                    "-shortest",
                    str(target_path.resolve()),
                ]
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120,
                )
                if res.returncode == 0 and target_path.exists() and target_path.stat().st_size > 0:
                    logger.info(f"Composited video + dialogue audio: {target_path}")
                    return str(target_path.resolve())
                else:
                    logger.warning(f"FFmpeg copy composite notice: {res.stderr}. Retrying with re-encode...")
                    # Re-encode fallback if stream copy failed due to container flags
                    cmd_reencode = [
                        ffmpeg,
                        "-y",
                        "-i", str(v_path),
                        "-i", str(a_path),
                        "-c:v", "libx264",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        str(target_path.resolve()),
                    ]
                    res2 = subprocess.run(
                        cmd_reencode,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=180,
                    )
                    if res2.returncode == 0 and target_path.exists() and target_path.stat().st_size > 0:
                        return str(target_path.resolve())
            except Exception as exc:
                logger.warning(f"Error during video/audio compositing: {exc}")

        # Fallback: return original video
        return str(v_path)

    def extract_last_frame(
        self,
        video_path: Path | str,
        output_path: Optional[Path | str] = None,
    ) -> Path:
        """
        Extracts the exact final decoded frame of a video clip to PNG for visual continuity conditioning.
        """
        v_path = Path(video_path).resolve()
        if not v_path.exists():
            raise FileNotFoundError(f"Video file not found for frame extraction: {v_path}")
        if v_path.stat().st_size == 0:
            raise ValueError(f"Video file is empty (0 bytes): {v_path}")

        target_frame = Path(output_path) if output_path else v_path.parent / f"{v_path.stem}_last_frame.png"
        target_frame.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg = self.ffmpeg_binary or get_ffmpeg_binary()
        if not ffmpeg:
            raise RuntimeError("FFmpeg binary is required for final frame extraction.")

        cmd = [
            ffmpeg,
            "-y",
            "-sseof", "-0.1",
            "-i", str(v_path),
            "-frames:v", "1",
            "-update", "1",
            str(target_frame.resolve()),
        ]

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

        if res.returncode != 0 or not target_frame.exists() or target_frame.stat().st_size == 0:
            # Fallback attempt using reverse filter
            cmd_fallback = [
                ffmpeg,
                "-y",
                "-i", str(v_path),
                "-vf", "reverse",
                "-frames:v", "1",
                "-update", "1",
                str(target_frame.resolve()),
            ]
            res_fb = subprocess.run(
                cmd_fallback,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=45,
            )
            if res_fb.returncode != 0 or not target_frame.exists() or target_frame.stat().st_size == 0:
                raise RuntimeError(
                    f"Failed to extract final frame from {v_path}. FFmpeg error: {res.stderr or res_fb.stderr}"
                )

        # Validate that the extracted image is openable and valid
        try:
            from PIL import Image
            with Image.open(target_frame) as img:
                img.verify()
        except Exception as img_err:
            raise ValueError(f"Extracted frame from {v_path} is not a valid image: {img_err}")

        logger.info(f"Extracted final frame from {v_path.name} -> {target_frame.name}")
        return target_frame.resolve()

    def concat_audio_files(
        self,
        audio_files: List[Path],
        output_path: Path,
    ) -> Path:
        """
        Concatenates dialogue audio tracks in sequence.
        """
        valid_files = [f for f in audio_files if f.exists() and f.stat().st_size > 0]
        if not valid_files:
            raise ValueError("No valid audio files to concatenate.")

        if len(valid_files) == 1:
            shutil.copyfile(valid_files[0], output_path)
            return output_path

        ffmpeg = self.ffmpeg_binary or get_ffmpeg_binary()
        if ffmpeg:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                list_file = f.name
                for af in valid_files:
                    p = af.resolve().as_posix()
                    f.write(f"file '{p}'\n")

            try:
                cmd = [
                    ffmpeg,
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file,
                    "-c:a", "copy",
                    str(output_path.resolve()),
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
            except Exception as e:
                logger.warning(f"FFmpeg audio concat notice: {e}")
            finally:
                if os.path.exists(list_file):
                    try:
                        os.remove(list_file)
                    except OSError:
                        pass

        # Direct byte copy or primary line fallback
        shutil.copyfile(valid_files[0], output_path)
        return output_path

    def stitch_scenes(
        self,
        scenes: List[SceneDefinition],
        project_id: str,
        output_filename: Optional[str] = None,
    ) -> str:
        """
        Stitches all completed scenes into a single final video file.
        Returns the absolute path to the resulting video.
        """
        valid_scenes = [s for s in scenes if s.video_clip_path and Path(s.video_clip_path).exists()]
        if not valid_scenes:
            raise AppException(
                status_code=400,
                message=f"No valid generated scene clips found to stitch for project {project_id}.",
            )

        target_name = output_filename or f"long_video_{project_id}.mp4"
        final_output_path = self.output_dir / target_name

        logger.info(
            f"Stitching {len(valid_scenes)} scenes for project {project_id} -> {final_output_path}"
        )

        ffmpeg = self.ffmpeg_binary or get_ffmpeg_binary()
        if ffmpeg and len(valid_scenes) > 1:
            try:
                self._stitch_with_ffmpeg(valid_scenes, final_output_path, ffmpeg)
                if final_output_path.exists() and final_output_path.stat().st_size > 0:
                    return str(final_output_path.resolve())
            except Exception as e:
                logger.warning(f"ffmpeg stitching failed: {e}. Falling back to direct concatenation.")

        if len(valid_scenes) == 1:
            shutil.copyfile(valid_scenes[0].video_clip_path, final_output_path)
            return str(final_output_path.resolve())

        # Fallback stitching
        self._stitch_fallback(valid_scenes, final_output_path)
        return str(final_output_path.resolve())

    def _stitch_with_ffmpeg(self, scenes: List[SceneDefinition], output_path: Path, ffmpeg_bin: str):
        """
        Uses ffmpeg concat demuxer for stream copy.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            list_file_path = f.name
            for s in scenes:
                p = Path(s.video_clip_path).resolve().as_posix()
                f.write(f"file '{p}'\n")

        try:
            cmd = [
                ffmpeg_bin,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file_path,
                "-c", "copy",
                str(output_path.resolve()),
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                # If stream copy failed due to varying codecs, re-encode concat
                cmd_reencode = [
                    ffmpeg_bin,
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file_path,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    str(output_path.resolve()),
                ]
                res_reencode = subprocess.run(cmd_reencode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=240)
                if res_reencode.returncode != 0:
                    raise RuntimeError(f"ffmpeg concat returned non-zero ({result.returncode}): {result.stderr}")
        finally:
            if os.path.exists(list_file_path):
                try:
                    os.remove(list_file_path)
                except OSError:
                    pass

    def _stitch_fallback(self, scenes: List[SceneDefinition], output_path: Path):
        """
        Safe fallback: writes combined video chunks into the output file.
        """
        with open(output_path, "wb") as out_f:
            for s in scenes:
                with open(s.video_clip_path, "rb") as in_f:
                    shutil.copyfileobj(in_f, out_f)
