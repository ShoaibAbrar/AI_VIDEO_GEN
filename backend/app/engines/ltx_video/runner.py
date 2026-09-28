"""
Real LTX-Video Inference Runner.
Executes actual diffusion-transformer video inference via PyTorch and Diffusers/LTX pipelines.
Supports Text-to-Video and Image-to-Video (Level 2 visual continuity).
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
from app.engines.ltx_video.diagnostics import check_ltx_environment
from app.engines.ltx_video.models import (
    LTXGenerationRequest,
    LTXGenerationResult,
    LTXModelConfig,
    LTXStatusCode,
)


class LTXVideoInferenceRunner:
    """
    Executes real LTX-Video generation workloads on NVIDIA CUDA GPUs.
    Handles pipeline instantiation, memory offloading, image conditioning,
    step-wise progress callbacks, cancellation, and MP4 packaging.
    """

    SUPPORTED_MODELS: Dict[str, LTXModelConfig] = {
        "ltx-video-0.9.8-distilled": LTXModelConfig(
            model_type="ltx-video-0.9.8-distilled",
            name="LTX-Video 0.9.8 Distilled",
            description="Ultra-fast distilled DiT model (8 steps) for high-throughput generation.",
            default_steps=8,
            default_guidance=1.0,
            default_fps=24,
            default_resolution="768*512",
            default_num_frames=121,
            hf_repo_id="Lightricks/LTX-Video",
            min_vram_gb=12.0,
        ),
        "ltx-video-0.9.5": LTXModelConfig(
            model_type="ltx-video-0.9.5",
            name="LTX-Video 0.9.5 Base",
            description="High-quality DiT foundation model for text-to-video and image-to-video generation.",
            default_steps=30,
            default_guidance=3.0,
            default_fps=24,
            default_resolution="768*512",
            default_num_frames=121,
            hf_repo_id="Lightricks/LTX-Video",
            min_vram_gb=12.0,
        ),
        "ltx-video-2b": LTXModelConfig(
            model_type="ltx-video-2b",
            name="LTX-Video 2B Lightweight",
            description="Lightweight 2B DiT variant optimized for low VRAM GPUs.",
            default_steps=25,
            default_guidance=3.0,
            default_fps=24,
            default_resolution="512*384",
            default_num_frames=97,
            hf_repo_id="Lightricks/LTX-Video",
            min_vram_gb=12.0,
        ),
    }

    def __init__(
        self,
        checkpoints_dir: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
        enable_cpu_offload: bool = True,
    ) -> None:
        self.checkpoints_dir = Path(
            checkpoints_dir
            or os.environ.get("LTX_VIDEO_MODEL_PATH")
            or os.environ.get("LTX_VIDEO_CHECKPOINTS_DIR")
            or "./models/ltx_video"
        )
        self.output_dir = Path(output_dir or os.environ.get("LTX_VIDEO_OUTPUT_DIR", "./output/ltx_video"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enable_cpu_offload = enable_cpu_offload

        self._pipeline: Any = None
        self._current_model_type: Optional[str] = None
        self._lock = threading.Lock()
        self._active_cancellations: Dict[str, threading.Event] = {}

    def is_gpu_ready(self) -> tuple[bool, str]:
        """Verify if CUDA hardware and dependencies are available."""
        diag = check_ltx_environment(checkpoints_dir=self.checkpoints_dir)
        return diag.is_available, diag.diagnostic_message

    def load_pipeline(self, model_type: str = "ltx-video-0.9.5") -> Any:
        """
        Loads and caches the diffusers LTX-Video pipeline in memory.
        Applies bfloat16 precision and CPU offloading for VRAM optimization.
        """
        with self._lock:
            if self._pipeline is not None and self._current_model_type == model_type:
                return self._pipeline

            import torch  # type: ignore
            from diffusers import LTXPipeline, LTXImageToVideoPipeline  # type: ignore

            model_cfg = self.SUPPORTED_MODELS.get(model_type, self.SUPPORTED_MODELS["ltx-video-0.9.5"])
            repo_id = os.environ.get("LTX_VIDEO_HF_MODEL_ID", model_cfg.hf_repo_id)

            logger.info(f"Loading real LTX-Video pipeline for '{model_type}' from '{repo_id}'...")

            # 1. Attempt local checkpoint path if safetensors exists
            local_checkpoint = self.checkpoints_dir / (model_cfg.weights_filename or "")
            if local_checkpoint.exists():
                logger.info(f"Loading LTX-Video from single local file: {local_checkpoint}")
                pipe = LTXPipeline.from_single_file(
                    str(local_checkpoint.resolve()),
                    torch_dtype=torch.bfloat16,
                )
            else:
                # 2. Load from HuggingFace pretrained model repository
                logger.info(f"Loading LTX-Video from model hub: {repo_id}")
                pipe = LTXPipeline.from_pretrained(
                    repo_id,
                    torch_dtype=torch.bfloat16,
                )

            if self.enable_cpu_offload and hasattr(pipe, "enable_model_cpu_offload"):
                logger.info("Enabling diffusers CPU offload for LTX-Video to minimize VRAM footprint.")
                pipe.enable_model_cpu_offload()
            else:
                pipe = pipe.to("cuda")

            self._pipeline = pipe
            self._current_model_type = model_type
            logger.info("LTX-Video pipeline successfully loaded into memory.")
            return self._pipeline

    def execute_generation(
        self,
        request: LTXGenerationRequest,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> LTXGenerationResult:
        """
        Executes real LTX-Video diffusion generation.
        """
        job_id = request.job_id or str(uuid.uuid4())
        cancel_event = threading.Event()
        self._active_cancellations[job_id] = cancel_event

        start_time = time.time()
        logger.info(f"Starting real LTX-Video generation [Job {job_id}] for prompt: '{request.prompt[:60]}...'")

        try:
            # 1. Environment & Hardware validation
            diag = check_ltx_environment(checkpoints_dir=self.checkpoints_dir)
            if not diag.is_available:
                return LTXGenerationResult(
                    job_id=job_id,
                    status=diag.status_code.value,
                    success=False,
                    error_message=diag.diagnostic_message,
                    error_code=diag.status_code.value,
                )

            import torch  # type: ignore
            from diffusers.utils import export_to_video  # type: ignore

            if progress_callback:
                progress_callback(5.0, "Loading LTX-Video model weights into GPU...")

            pipe = self.load_pipeline(request.model_type)

            if cancel_event.is_set():
                return LTXGenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation cancelled before diffusion pass.",
                    error_code="LTX_VIDEO_CANCELLED",
                )

            # 2. Prepare conditioning & inputs
            generator = torch.Generator(device="cuda").manual_seed(request.seed)
            total_steps = request.num_inference_steps

            def _step_cb(pipe_obj: Any, step_index: int, timestep: int, callback_kwargs: dict):
                if cancel_event.is_set():
                    raise RuntimeError("LTX_VIDEO_CANCELLED_BY_USER")
                if progress_callback:
                    pct = 10.0 + (float(step_index + 1) / float(total_steps) * 80.0)
                    progress_callback(pct, f"Denoising frame latents (step {step_index + 1}/{total_steps})...")
                return callback_kwargs

            # 3. Check for image-to-video / Level 2 visual continuity
            input_image = None
            if request.image_start and Path(request.image_start).exists():
                img_path = Path(request.image_start).resolve()
                logger.info(f"Applying Level 2 visual continuity start frame: {img_path}")
                raw_img = Image.open(img_path).convert("RGB")
                input_image = raw_img.resize((request.width, request.height), Image.Resampling.LANCZOS)

            # 4. Invoke Diffusers LTX-Video pipeline
            if progress_callback:
                progress_callback(10.0, "Synthesizing video latents with LTX-Video...")

            pipeline_kwargs: Dict[str, Any] = {
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt or None,
                "width": request.width,
                "height": request.height,
                "num_frames": request.num_frames,
                "frame_rate": request.fps,
                "num_inference_steps": total_steps,
                "guidance_scale": request.guidance_scale,
                "generator": generator,
                "callback_on_step_end": _step_cb,
            }

            if input_image is not None:
                pipeline_kwargs["image"] = input_image

            output = pipe(**pipeline_kwargs)
            video_frames = output.frames[0]

            if progress_callback:
                progress_callback(92.0, "Encoding video frames to MP4 container...")

            # 5. Export frames to MP4
            target_out = (
                Path(request.output_path)
                if request.output_path
                else self.output_dir / f"ltx_{job_id}.mp4"
            )
            target_out.parent.mkdir(parents=True, exist_ok=True)

            export_to_video(video_frames, str(target_out.resolve()), fps=request.fps)
            elapsed = time.time() - start_time

            duration = round(len(video_frames) / max(1, request.fps), 2)
            logger.info(f"LTX-Video generation finished in {elapsed:.2f}s: {target_out}")

            if progress_callback:
                progress_callback(100.0, "Generation complete.")

            return LTXGenerationResult(
                job_id=job_id,
                status="COMPLETED",
                success=True,
                output_path=str(target_out.resolve()),
                duration=duration,
                width=request.width,
                height=request.height,
                fps=request.fps,
                num_frames=len(video_frames),
                metadata={
                    "model_type": request.model_type,
                    "steps": request.num_inference_steps,
                    "guidance_scale": request.guidance_scale,
                    "seed": request.seed,
                    "elapsed_seconds": round(elapsed, 2),
                    "image_start_conditioned": input_image is not None,
                },
            )

        except Exception as exc:
            error_str = str(exc)
            if "LTX_VIDEO_CANCELLED_BY_USER" in error_str:
                return LTXGenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation cancelled by user.",
                    error_code="LTX_VIDEO_CANCELLED",
                )

            logger.error(f"LTX-Video generation failed [Job {job_id}]: {exc}", exc_info=True)
            return LTXGenerationResult(
                job_id=job_id,
                status="FAILED",
                success=False,
                error_message=f"LTX-Video execution failed: {error_str}",
                error_code="LTX_VIDEO_GENERATION_FAILED",
            )
        finally:
            self._active_cancellations.pop(job_id, None)

    def cancel(self, job_id: str) -> bool:
        """Signals cancellation for a running generation task."""
        event = self._active_cancellations.get(job_id)
        if event:
            event.set()
            logger.info(f"Cancelled LTX-Video job {job_id}.")
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
            logger.info("LTX-Video pipeline unloaded.")
