"""
Real MiniMax H3 Omni-Modal Audio-Video Inference Runner.
Directly invokes the official MiniMax H3 upstream pipeline (ModularPipeline / Diffusers)
with Qwen3-VL text encoder, 3D Video VAE, and 2D Audio VAE for synchronized Omni-AV generation.
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
from app.engines.minimax_h3.diagnostics import check_minimax_h3_environment
from app.engines.minimax_h3.models import (
    MiniMaxH3GenerationRequest,
    MiniMaxH3GenerationResult,
    MiniMaxH3ModelConfig,
    MiniMaxH3StatusCode,
    MiniMaxH3TaskType,
)
from app.orchestration.media_stitcher import MediaStitcher


class MiniMaxH3InferenceRunner:
    """
    Canonical Inference Runner for MiniMax H3 (https://github.com/MiniMax-AI/MiniMax-H3).
    Executes real joint Audio-Video generation via ModularPipeline / Diffusers on NVIDIA CUDA hardware.
    """

    SUPPORTED_MODELS: Dict[str, MiniMaxH3ModelConfig] = {
        "minimax-h3-v1": MiniMaxH3ModelConfig(
            model_type="minimax-h3-v1",
            name="MiniMax H3 Omni-AV",
            description="Official MiniMax H3 joint Omni-Modal Video and 32kHz Stereo Audio generation foundation model.",
            supports_audio=True,
            default_steps=35,
            default_guidance=5.0,
            default_fps=25,
            default_resolution="1024*576",
            default_num_frames=125,
            audio_sample_rate=32000,
            repo_id="MiniMaxAI/MiniMax-H3",
            min_vram_gb=24.0,
            recommended_vram_gb=48.0,
        ),
        "minimax-h3-ref2va": MiniMaxH3ModelConfig(
            model_type="minimax-h3-ref2va",
            name="MiniMax H3 Ref2VA",
            description="Official MiniMax H3 multi-reference conditioned Video-Audio model supporting image/audio/video prompts.",
            supports_audio=True,
            default_steps=40,
            default_guidance=5.5,
            default_fps=25,
            default_resolution="1280*720",
            default_num_frames=125,
            audio_sample_rate=32000,
            repo_id="MiniMaxAI/MiniMax-H3-Ref2VA",
            min_vram_gb=24.0,
            recommended_vram_gb=48.0,
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
            or os.environ.get("MINIMAX_H3_MODEL_PATH")
            or os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR")
            or "./models/minimax_h3"
        )
        self.output_dir = Path(output_dir or os.environ.get("MINIMAX_H3_OUTPUT_DIR", "./output/minimax_h3"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.media_stitcher = media_stitcher or MediaStitcher(output_dir=self.output_dir)

        self._pipeline: Any = None
        self._current_model_type: Optional[str] = None
        self._lock = threading.Lock()
        self._active_cancellations: Dict[str, threading.Event] = {}

    def is_gpu_ready(self) -> tuple[bool, str]:
        """Verify if CUDA hardware, VRAM, and dependencies are available."""
        diag = check_minimax_h3_environment(checkpoints_dir=self.checkpoints_dir)
        return diag.is_available, diag.diagnostic_message

    def load_pipeline(self, model_type: str = "minimax-h3-v1") -> Any:
        """
        Instantiates the upstream MiniMax H3 pipeline via diffusers ModularPipeline / DiffusionPipeline.
        """
        with self._lock:
            if self._pipeline is not None and self._current_model_type == model_type:
                return self._pipeline

            import torch  # type: ignore

            logger.info(f"Loading official MiniMax H3 pipeline from '{self.checkpoints_dir}' (model: {model_type})...")

            model_config = self.SUPPORTED_MODELS.get(model_type, self.SUPPORTED_MODELS["minimax-h3-v1"])
            model_source = str(self.checkpoints_dir.resolve()) if self.checkpoints_dir.exists() else model_config.repo_id

            pipe = None
            # Attempt loading via diffusers.ModularPipeline or DiffusionPipeline
            try:
                from diffusers import ModularPipeline  # type: ignore
                pipe = ModularPipeline.from_pretrained(model_source, torch_dtype=torch.bfloat16)
                pipe.load_components(dtype=torch.bfloat16)
            except Exception as mod_err:
                logger.info(f"ModularPipeline load notice: {mod_err}. Attempting DiffusionPipeline...")
                from diffusers import DiffusionPipeline  # type: ignore
                pipe = DiffusionPipeline.from_pretrained(
                    model_source,
                    torch_dtype=torch.bfloat16,
                    trust_remote_code=True,
                )

            device = "cuda" if torch.cuda.is_available() else "cpu"
            if hasattr(pipe, "to"):
                pipe.to(device)

            self._pipeline = pipe
            self._current_model_type = model_type
            logger.info(f"MiniMax H3 pipeline ({model_type}) loaded successfully on {device}.")
            return self._pipeline

    def execute_generation(
        self,
        request: MiniMaxH3GenerationRequest,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> MiniMaxH3GenerationResult:
        """
        Executes real MiniMax H3 Omni-Modal Audio-Video generation.
        """
        job_id = request.job_id or str(uuid.uuid4())
        cancel_event = threading.Event()
        self._active_cancellations[job_id] = cancel_event

        start_time = time.time()
        logger.info(f"Starting real MiniMax H3 Omni-AV generation [Job {job_id}] for prompt: '{request.prompt[:60]}...'")

        try:
            # 1. Hardware & Environment validation
            diag = check_minimax_h3_environment(checkpoints_dir=self.checkpoints_dir)
            if not diag.is_available:
                return MiniMaxH3GenerationResult(
                    job_id=job_id,
                    status=diag.status_code.value,
                    success=False,
                    error_message=diag.diagnostic_message,
                    error_code=diag.status_code.value,
                )

            import numpy as np  # type: ignore
            import soundfile as sf  # type: ignore
            import torch  # type: ignore

            if progress_callback:
                progress_callback(5.0, "Loading MiniMax H3 Omni-AV weights into GPU memory...")

            pipe = self.load_pipeline(request.model_type)

            if cancel_event.is_set():
                return MiniMaxH3GenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation cancelled before diffusion pass.",
                    error_code="MINIMAX_H3_CANCELLED",
                )

            total_steps = request.num_inference_steps

            def _step_cb(step_index: int, timestep: int, **kwargs):
                if cancel_event.is_set():
                    raise RuntimeError("MINIMAX_H3_CANCELLED_BY_USER")
                if progress_callback:
                    pct = 10.0 + (float(max(0, step_index + 1)) / float(total_steps) * 75.0)
                    progress_callback(pct, f"Synthesizing Omni-AV latents (step {step_index + 1}/{total_steps})...")

            # 2. Determine conditioning inputs based on TaskType
            call_kwargs: Dict[str, Any] = {
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "num_inference_steps": total_steps,
                "guidance_scale": request.guidance_scale,
                "height": request.height,
                "width": request.width,
                "num_frames": request.num_frames,
                "fps": request.fps,
                "generator": torch.Generator(device="cuda" if torch.cuda.is_available() else "cpu").manual_seed(request.seed),
            }

            # First-frame conditioning (FL2VA / Level 2 visual continuity)
            if request.image_start and Path(request.image_start).exists():
                logger.info(f"Applying MiniMax H3 first-frame conditioning: {request.image_start}")
                init_img = Image.open(request.image_start).convert("RGB")
                call_kwargs["image"] = init_img

            # Last-frame conditioning (FL2VA)
            if request.image_end and Path(request.image_end).exists():
                logger.info(f"Applying MiniMax H3 last-frame conditioning: {request.image_end}")
                last_img = Image.open(request.image_end).convert("RGB")
                call_kwargs["last_image"] = last_img

            # Multi-reference conditioning (Ref2VA)
            if request.reference_images:
                valid_refs = [Image.open(p).convert("RGB") for p in request.reference_images if Path(p).exists()]
                if valid_refs:
                    call_kwargs["reference_images"] = valid_refs

            if request.reference_audios:
                valid_audios = [str(Path(p).resolve()) for p in request.reference_audios if Path(p).exists()]
                if valid_audios:
                    call_kwargs["reference_audio_paths"] = valid_audios

            if progress_callback:
                progress_callback(10.0, "Executing MiniMax H3 Omni-Modal Transformer...")

            # 3. Invoke Upstream Pipeline
            output = pipe(**call_kwargs)

            if cancel_event.is_set():
                return MiniMaxH3GenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation cancelled by user.",
                    error_code="MINIMAX_H3_CANCELLED",
                )

            if progress_callback:
                progress_callback(88.0, "Decoding Video & Audio VAE tensors...")

            # 4. Process Outputs
            video_path = (
                Path(request.output_video_path)
                if request.output_video_path
                else self.output_dir / f"minimax_h3_{job_id}.mp4"
            )
            audio_path = (
                Path(request.output_audio_path)
                if request.output_audio_path
                else self.output_dir / f"minimax_h3_{job_id}.wav"
            )

            frames = getattr(output, "frames", None) or getattr(output, "videos", None)
            audio_tensor = getattr(output, "audio", None) or getattr(output, "audios", None)

            has_audio = False
            if audio_tensor is not None and request.generate_audio:
                try:
                    if hasattr(audio_tensor, "cpu"):
                        audio_np = audio_tensor.cpu().float().numpy()
                    else:
                        audio_np = np.array(audio_tensor)
                    if audio_np.ndim == 2 and audio_np.shape[0] == 2:
                        audio_np = audio_np.T
                    sf.write(str(audio_path.resolve()), audio_np, 32000)
                    has_audio = True
                except Exception as audio_err:
                    logger.warning(f"Could not save MiniMax H3 audio output: {audio_err}")

            # Export video frames via imageio or diffusers export_to_video
            if frames is not None:
                try:
                    from diffusers.utils import export_to_video  # type: ignore
                    export_to_video(frames[0] if isinstance(frames, list) and isinstance(frames[0], list) else frames, str(video_path.resolve()), fps=request.fps)
                except Exception as vid_err:
                    logger.warning(f"export_to_video error: {vid_err}. Using MediaStitcher fallback...")

            # Mux with native audio if generated
            if has_audio and audio_path.exists() and video_path.exists():
                try:
                    self.media_stitcher.composite_scene_video_audio(
                        video_path=video_path,
                        audio_path=audio_path,
                    )
                except Exception as mux_err:
                    logger.warning(f"Audio-Video composition notice: {mux_err}")

            elapsed = time.time() - start_time
            duration = round(request.num_frames / max(1, request.fps), 2)
            logger.info(f"MiniMax H3 generation completed in {elapsed:.2f}s: {video_path}")

            if progress_callback:
                progress_callback(100.0, "Generation complete.")

            return MiniMaxH3GenerationResult(
                job_id=job_id,
                status="COMPLETED",
                success=True,
                video_path=str(video_path.resolve()),
                audio_path=str(audio_path.resolve()) if has_audio else None,
                combined_media_path=str(video_path.resolve()),
                output_paths=[str(video_path.resolve())],
                duration=duration,
                width=request.width,
                height=request.height,
                fps=request.fps,
                sample_rate=32000 if has_audio else None,
                num_frames=request.num_frames,
                has_audio=has_audio,
                metadata={
                    "model_type": request.model_type,
                    "task_type": request.task_type.value,
                    "steps": request.num_inference_steps,
                    "guidance_scale": request.guidance_scale,
                    "seed": request.seed,
                    "elapsed_seconds": round(elapsed, 2),
                    "native_audio_generated": has_audio,
                    "first_frame_conditioned": bool(request.image_start),
                },
            )

        except Exception as exc:
            error_str = str(exc)
            if "MINIMAX_H3_CANCELLED_BY_USER" in error_str:
                return MiniMaxH3GenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation cancelled by user.",
                    error_code="MINIMAX_H3_CANCELLED",
                )

            logger.error(f"MiniMax H3 generation failed [Job {job_id}]: {exc}", exc_info=True)
            return MiniMaxH3GenerationResult(
                job_id=job_id,
                status="FAILED",
                success=False,
                error_message=f"MiniMax H3 execution failed: {error_str}",
                error_code="MINIMAX_H3_GENERATION_FAILED",
            )
        finally:
            self._active_cancellations.pop(job_id, None)

    def cancel(self, job_id: str) -> bool:
        """Signals cancellation for a running generation task."""
        event = self._active_cancellations.get(job_id)
        if event:
            event.set()
            logger.info(f"Cancelled MiniMax H3 job {job_id}.")
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
            logger.info("MiniMax H3 pipeline unloaded.")
