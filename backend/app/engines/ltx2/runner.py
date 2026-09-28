"""
Real LTX-2 Multimodal Audio-Video Inference Runner.
Directly invokes the official Lightricks LTX-2 pipeline:
TI2VidOneStagePipeline (models.ltx2.ltx_pipelines.ti2vid_one_stage)
with Gemma text encoding, Video VAE, Audio VAE, Vocoder, and media_io multiplexing.
"""

from __future__ import annotations

import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from PIL import Image

from app.core.logging_config import logger
from app.engines.ltx2.diagnostics import check_ltx2_environment
from app.engines.ltx2.models import (
    LTX2GenerationRequest,
    LTX2GenerationResult,
    LTX2ModelConfig,
    LTX2StatusCode,
)
from app.orchestration.media_stitcher import MediaStitcher


class LTX2InferenceRunner:
    """
    Canonical Inference Runner for Lightricks LTX-2 (https://github.com/Lightricks/LTX-2).
    Executes real joint Audio-Video generation via TI2VidOneStagePipeline on NVIDIA CUDA hardware.
    """

    SUPPORTED_MODELS: Dict[str, LTX2ModelConfig] = {
        "ltx-2-19b-av": LTX2ModelConfig(
            model_type="ltx-2-19b-av",
            name="LTX-2 19B Audio-Video",
            description="Official Lightricks LTX-2 19B dual-stream joint Audio-Video foundation model.",
            supports_audio=True,
            default_steps=40,
            default_guidance=4.5,
            default_fps=25,
            default_resolution="1024*576",
            default_num_frames=125,
            min_vram_gb=16.0,
            recommended_vram_gb=24.0,
        ),
        "ltx-2-distilled": LTX2ModelConfig(
            model_type="ltx-2-distilled",
            name="LTX-2 Distilled Fast",
            description="Official Lightricks LTX-2 distilled checkpoint for low-latency AV generation.",
            supports_audio=True,
            default_steps=8,
            default_guidance=1.0,
            default_fps=25,
            default_resolution="768*512",
            default_num_frames=100,
            min_vram_gb=16.0,
            recommended_vram_gb=24.0,
        ),
    }

    def __init__(
        self,
        checkpoints_dir: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
        media_stitcher: Optional[MediaStitcher] = None,
    ) -> None:
        self.checkpoints_dir = Path(
            checkpoints_dir
            or os.environ.get("LTX2_MODEL_PATH")
            or os.environ.get("LTX2_CHECKPOINTS_DIR")
            or "./models/ltx2"
        )
        self.output_dir = Path(output_dir or os.environ.get("LTX2_OUTPUT_DIR", "./output/ltx2"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.media_stitcher = media_stitcher or MediaStitcher(output_dir=self.output_dir)

        self._pipeline: Any = None
        self._current_model_type: Optional[str] = None
        self._lock = threading.Lock()
        self._active_cancellations: Dict[str, threading.Event] = {}

    def is_gpu_ready(self) -> tuple[bool, str]:
        """Verify if CUDA hardware, VRAM, and dependencies are available."""
        diag = check_ltx2_environment(checkpoints_dir=self.checkpoints_dir)
        return diag.is_available, diag.diagnostic_message

    def load_pipeline(self, model_type: str = "ltx-2-19b-av") -> Any:
        """
        Instantiates the canonical upstream TI2VidOneStagePipeline from models.ltx2.
        """
        with self._lock:
            if self._pipeline is not None and self._current_model_type == model_type:
                return self._pipeline

            configured_checkpoint = os.environ.get("LTX2_CHECKPOINT_PATH")
            if not configured_checkpoint:
                raise RuntimeError(
                    "LTX-2 inference is blocked until an approved transformer checkpoint is configured "
                    "with LTX2_CHECKPOINT_PATH."
                )
            checkpoint_file = Path(configured_checkpoint).expanduser().resolve()
            if not checkpoint_file.is_file():
                raise FileNotFoundError(f"LTX-2 checkpoint file does not exist: {checkpoint_file}")
            if "vae" in checkpoint_file.name.lower():
                raise ValueError("LTX2_CHECKPOINT_PATH must point to the model checkpoint, not a VAE file.")

            import torch  # type: ignore

            logger.info(f"Loading canonical Lightricks LTX-2 pipeline from '{self.checkpoints_dir}'...")

            # Locate Gemma folder and checkpoint file
            gemma_dir = self.checkpoints_dir / "gemma-3-12b-it-qat-q4_0-unquantized"
            if not gemma_dir.exists():
                gemma_dir = self.checkpoints_dir

            # Upstream canonical import
            from models.ltx2.ltx_pipelines.ti2vid_one_stage import TI2VidOneStagePipeline  # type: ignore

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            pipe = TI2VidOneStagePipeline(
                checkpoint_path=str(checkpoint_file.resolve()),
                gemma_root=str(gemma_dir.resolve()),
                loras=[],
                device=device,
                fp8transformer=True,
            )

            self._pipeline = pipe
            self._current_model_type = model_type
            logger.info("Canonical LTX-2 TI2VidOneStagePipeline loaded successfully.")
            return self._pipeline

    def execute_generation(
        self,
        request: LTX2GenerationRequest,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> LTX2GenerationResult:
        """
        Executes real Lightricks LTX-2 joint Audio-Video generation via TI2VidOneStagePipeline.
        """
        job_id = request.job_id or str(uuid.uuid4())
        cancel_event = threading.Event()
        self._active_cancellations[job_id] = cancel_event

        start_time = time.time()
        logger.info(f"Starting real LTX-2 AV generation [Job {job_id}] for prompt: '{request.prompt[:60]}...'")

        try:
            # 1. Environment & Hardware validation
            diag = check_ltx2_environment(checkpoints_dir=self.checkpoints_dir)
            if not diag.is_available:
                return LTX2GenerationResult(
                    job_id=job_id,
                    status=diag.status_code.value,
                    success=False,
                    error_message=diag.diagnostic_message,
                    error_code=diag.status_code.value,
                )

            import numpy as np  # type: ignore
            import soundfile as sf  # type: ignore
            import torch  # type: ignore
            from models.ltx2.ltx_pipelines.utils.media_io import encode_video  # type: ignore

            if progress_callback:
                progress_callback(5.0, "Loading canonical LTX-2 weights into GPU...")

            pipe = self.load_pipeline(request.model_type)

            if cancel_event.is_set():
                return LTX2GenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation cancelled before diffusion pass.",
                    error_code="LTX2_CANCELLED",
                )

            total_steps = request.num_inference_steps

            def _step_cb(step_index: int, timestep: int, is_start: bool = False, **kwargs):
                if cancel_event.is_set():
                    raise RuntimeError("LTX2_CANCELLED_BY_USER")
                if progress_callback:
                    pct = 10.0 + (float(max(0, step_index + 1)) / float(total_steps) * 75.0)
                    progress_callback(pct, f"Denoising joint AV latents (step {step_index + 1}/{total_steps})...")

            # 2. First-frame conditioning for Level 2 visual continuity
            images_list: List[tuple[str, int, float]] = []
            if request.image_start and Path(request.image_start).exists():
                img_path = str(Path(request.image_start).resolve())
                logger.info(f"Applying Level 2 visual continuity conditioning frame: {img_path}")
                images_list.append((img_path, 0, 1.0))

            # 3. Invoke Canonical TI2VidOneStagePipeline
            if progress_callback:
                progress_callback(10.0, "Synthesizing joint audio-video latents with LTX-2...")

            decoded_video, decoded_audio = pipe(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                seed=request.seed,
                height=request.height,
                width=request.width,
                num_frames=request.num_frames,
                frame_rate=float(request.fps),
                num_inference_steps=total_steps,
                cfg_guidance_scale=request.guidance_scale,
                images=images_list,
                callback=_step_cb,
                interrupt_check=lambda: cancel_event.is_set(),
            )

            if cancel_event.is_set() or decoded_video is None:
                return LTX2GenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation was cancelled by user.",
                    error_code="LTX2_CANCELLED",
                )

            if progress_callback:
                progress_callback(88.0, "Encoding Video VAE & Audio Vocoder outputs...")

            # 4. Export Video & Audio to disk
            video_path = (
                Path(request.output_video_path)
                if request.output_video_path
                else self.output_dir / f"ltx2_video_{job_id}.mp4"
            )
            audio_path = (
                Path(request.output_audio_path)
                if request.output_audio_path
                else self.output_dir / f"ltx2_audio_{job_id}.wav"
            )

            has_audio = False
            if decoded_audio is not None and request.generate_audio:
                try:
                    audio_tensor = decoded_audio.cpu().float()
                    audio_np = audio_tensor.numpy()
                    if audio_np.ndim == 2 and audio_np.shape[0] == 2:
                        audio_np = audio_np.T
                    sf.write(str(audio_path.resolve()), audio_np, 44100)
                    has_audio = True
                except Exception as audio_err:
                    logger.warning(f"Could not write audio WAV: {audio_err}")

            # Encode unified video + audio using upstream media_io
            try:
                encode_video(
                    video=decoded_video,
                    fps=float(request.fps),
                    audio=decoded_audio if has_audio else None,
                    audio_sample_rate=44100,
                    output_path=str(video_path.resolve()),
                    video_chunks_number=1,
                )
            except Exception as enc_err:
                logger.warning(f"media_io.encode_video notice: {enc_err}. Fallback to MediaStitcher...")
                # Fallback to MediaStitcher if PyAV is not installed
                if has_audio and audio_path.exists():
                    self.media_stitcher.composite_scene_video_audio(
                        video_path=video_path,
                        audio_path=audio_path,
                    )

            combined_path = str(video_path.resolve())
            elapsed = time.time() - start_time
            duration = round(request.num_frames / max(1, request.fps), 2)
            logger.info(f"LTX-2 generation finished in {elapsed:.2f}s: {combined_path}")

            if progress_callback:
                progress_callback(100.0, "Generation complete.")

            return LTX2GenerationResult(
                job_id=job_id,
                status="COMPLETED",
                success=True,
                video_path=str(video_path.resolve()),
                audio_path=str(audio_path.resolve()) if has_audio else None,
                combined_media_path=combined_path,
                duration=duration,
                width=request.width,
                height=request.height,
                fps=request.fps,
                num_frames=request.num_frames,
                has_audio=has_audio,
                metadata={
                    "model_type": request.model_type,
                    "steps": request.num_inference_steps,
                    "guidance_scale": request.guidance_scale,
                    "seed": request.seed,
                    "elapsed_seconds": round(elapsed, 2),
                    "joint_audio_generated": has_audio,
                    "image_start_conditioned": len(images_list) > 0,
                    "upstream_pipeline": "TI2VidOneStagePipeline",
                },
            )

        except Exception as exc:
            error_str = str(exc)
            if "LTX2_CANCELLED_BY_USER" in error_str:
                return LTX2GenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation cancelled by user.",
                    error_code="LTX2_CANCELLED",
                )

            logger.error(f"LTX-2 generation failed [Job {job_id}]: {exc}", exc_info=True)
            return LTX2GenerationResult(
                job_id=job_id,
                status="FAILED",
                success=False,
                error_message=f"LTX-2 execution failed: {error_str}",
                error_code="LTX2_GENERATION_FAILED",
            )
        finally:
            self._active_cancellations.pop(job_id, None)

    def cancel(self, job_id: str) -> bool:
        """Signals cancellation for a running generation task."""
        event = self._active_cancellations.get(job_id)
        if event:
            event.set()
            logger.info(f"Cancelled LTX-2 job {job_id}.")
            return True
        return False

    def unload(self) -> None:
        """Unloads pipeline and clears CUDA cache."""
        with self._lock:
            self._pipeline = None
            self._current_model_type = None
            try:
                import torch  # type: ignore
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("LTX-2 pipeline unloaded.")
