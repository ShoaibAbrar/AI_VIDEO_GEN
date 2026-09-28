"""
Mock Video Generation Engine for local development and GPU-free environments.
Allows full end-to-end testing of the platform on Windows 10/11 without requiring an NVIDIA GPU.
"""

from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from app.config import settings
from app.core.logging_config import logger
from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)


def _generate_minimal_mp4(dest_path: Path) -> Path:
    """Generate a lightweight valid MP4 container file for testing and playback."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = None

    if ffmpeg:
        import subprocess
        res = subprocess.run([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24",
            "-t", "2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(dest_path.resolve())
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and dest_path.exists() and dest_path.stat().st_size > 0:
            return dest_path

    # Minimal ftyp + moov + mdat box MP4 structure fallback
    minimal_mp4_bytes = (
        b"\x00\x00\x00\x20\x66\x74\x79\x70\x69\x73\x6f\x6d\x00\x00\x02\x00"
        b"\x69\x73\x6f\x6d\x69\x73\x6f\x32\x61\x76\x63\x31\x6d\x70\x34\x31"
        b"\x00\x00\x00\x08\x66\x72\x65\x65\x00\x00\x02\xb6\x6d\x64\x61\x74"
        + b"\x00" * 512
        + b"\x00\x00\x00\x40\x6d\x6f\x6f\x76\x00\x00\x00\x38\x6d\x76\x68\x64"
        + b"\x00" * 48
    )
    dest_path.write_bytes(minimal_mp4_bytes)
    return dest_path


class MockVideoEngine(BaseVideoEngine):
    """
    Mock video engine simulating generative workflows for Windows developers
    without NVIDIA CUDA hardware.
    """

    def __init__(self, engine_id: str = "mock-engine", speed_multiplier: float = 1.0) -> None:
        self._engine_id = engine_id
        self._speed_multiplier = speed_multiplier
        self._capabilities = EngineCapabilities(
            text_to_video=True,
            image_to_video=True,
            video_continuation=True,
            native_long_video=True,
            audio_generation=True,
            voice_conditioning=True,
            reference_image=True,
            reference_video=True,
            reference_audio=True,
            multiple_characters=True,
            custom_resolutions=True,
            configurable_fps=True,
            configurable_steps=True,
            configurable_seed=True,
            progress_reporting=True,
            cancellation=True,
        )
        self._active_jobs: dict[str, dict[str, Any]] = {}
        self._initialized = False

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def display_name(self) -> str:
        return "Simulated Dev Engine (Mock GPU)"

    @property
    def description(self) -> str:
        return (
            "Mock video engine designed for local Windows development and testing "
            "without requiring an NVIDIA GPU or model weights."
        )

    @property
    def capabilities(self) -> EngineCapabilities:
        return self._capabilities

    @property
    def is_available(self) -> bool:
        return True

    def initialize(self) -> None:
        self._initialized = True
        logger.info("MockVideoEngine '%s' initialized (Dev Mode)", self._engine_id)

    def get_runtime_status(self) -> dict[str, Any]:
        return {
            "engine_id": self._engine_id,
            "display_name": self.display_name,
            "available": True,
            "initialized": True,
            "status": "ready (mock dev mode)",
            "models_available": 3,
            "models_total": 3,
            "gpu_mode": "mock_simulated",
        }

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "model_type": "mock-t2v-preview",
                "name": "Mock Fast Text-to-Video",
                "engine_id": self._engine_id,
                "aspect_ratios": ["16:9", "9:16", "1:1"],
                "default_resolution": "720p",
                "max_duration": 30.0,
                "availability": {"available": True},
            },
            {
                "model_type": "mock-i2v-preview",
                "name": "Mock Image-to-Video",
                "engine_id": self._engine_id,
                "aspect_ratios": ["16:9", "9:16", "1:1"],
                "default_resolution": "720p",
                "max_duration": 30.0,
                "availability": {"available": True},
            },
            {
                "model_type": "mock-long-video",
                "name": "Mock Multi-Scene Long Video",
                "engine_id": self._engine_id,
                "aspect_ratios": ["16:9"],
                "default_resolution": "720p",
                "max_duration": 300.0,
                "availability": {"available": True},
            },
        ]

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        settings_dict = dict(generation_settings)
        settings_dict.setdefault("prompt", "A cinematic scene in a cybernetic future")
        settings_dict.setdefault("aspect_ratio", "16:9")
        settings_dict.setdefault("resolution", "720p")
        settings_dict.setdefault("duration_seconds", 5.0)
        settings_dict["engine_id"] = self._engine_id
        return settings_dict

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> EngineJobHandle:
        job_id = str(generation_settings.get("id") or uuid.uuid4())
        logger.info("MockVideoEngine submitting simulated job %s", job_id)

        # Emulate progress steps
        steps = [
            (10, "prompt_encoding", "Encoding prompt conditioning..."),
            (30, "diffusion_latent", "Synthesizing latent video tokens (step 10/40)..."),
            (60, "diffusion_denoise", "Synthesizing latent video tokens (step 30/40)..."),
            (85, "audio_synthesis", "Generating voiceover and audio stems..."),
            (100, "video_encoding", "Packaging MP4 container..."),
        ]

        for pct, phase, status_msg in steps:
            on_progress(
                EngineProgress(
                    progress=pct,
                    phase=phase,
                    status=status_msg,
                )
            )

        # Generate sample video in storage path
        storage_dir = Path(settings.STORAGE_PATH) / "mock_generated" / job_id
        output_mp4 = storage_dir / "output.mp4"
        _generate_minimal_mp4(output_mp4)

        self._active_jobs[job_id] = {
            "output_path": output_mp4,
            "success": True,
            "settings": generation_settings,
        }

        return EngineJobHandle(
            job_id=job_id,
            engine_id=self._engine_id,
            raw_handle=job_id,
        )

    def wait_for_result(self, handle: EngineJobHandle) -> EngineResult:
        job_id = handle.job_id
        job_data = self._active_jobs.get(job_id)
        if not job_data or not job_data.get("success"):
            return EngineResult(
                success=False,
                error_message="Mock generation failed",
            )

        output_path = job_data["output_path"]
        return EngineResult(
            success=True,
            output_files=[str(output_path)],
        )

    def cancel_generation(self, handle: EngineJobHandle) -> None:
        if handle.job_id in self._active_jobs:
            self._active_jobs[handle.job_id]["success"] = False
            logger.info("MockVideoEngine cancelled job %s", handle.job_id)

    def shutdown(self) -> None:
        self._active_jobs.clear()
        self._initialized = False
        logger.info("MockVideoEngine '%s' shut down", self._engine_id)
