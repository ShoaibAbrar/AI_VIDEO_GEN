"""
Concrete LTX-Video Engine Adapter implementing BaseVideoEngine.
Provides programmatic integration for Lightricks LTX-Video high-speed DiT video generation.
Connects to real LTXVideoInferenceRunner on CUDA hardware or returns truthful diagnostics.
"""

from __future__ import annotations

import os
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional
import uuid

from app.config import settings
from app.core.logging_config import logger
from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)
from app.engines.ltx_video.diagnostics import LTXEnvironmentStatus, check_ltx_environment
from app.engines.ltx_video.models import (
    LTXGenerationRequest,
    LTXGenerationResult,
    LTXModelConfig,
    LTXStatusCode,
)
from app.engines.ltx_video.runner import LTXVideoInferenceRunner


class LTXVideoService:
    """
    Service layer managing LTX-Video model lifecycle, environment verification,
    and delegating inference execution to LTXVideoInferenceRunner.
    """

    SUPPORTED_MODELS = [
        LTXModelConfig(
            model_type="ltx-video-0.9.8-distilled",
            name="LTX-Video 0.9.8 Distilled",
            description="Ultra-fast few-step distilled DiT model for high-throughput video generation.",
            default_steps=8,
            default_guidance=1.0,
            default_fps=24,
            default_resolution="768*512",
            default_num_frames=121,
            hf_repo_id="Lightricks/LTX-Video",
            min_vram_gb=12.0,
        ),
        LTXModelConfig(
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
        LTXModelConfig(
            model_type="ltx-video-2b",
            name="LTX-Video 2B Lightweight",
            description="Lightweight 2B parameter DiT variant optimized for low VRAM consumer GPUs.",
            default_steps=25,
            default_guidance=3.0,
            default_fps=24,
            default_resolution="512*384",
            default_num_frames=97,
            hf_repo_id="Lightricks/LTX-Video",
            min_vram_gb=12.0,
        ),
    ]

    def __init__(
        self,
        runner_factory: Callable[..., Any] | None = None,
        checkpoints_dir: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        self._runner_factory = runner_factory
        self._runner: Any | None = None
        self._lock = threading.Lock()
        self._initialized = False
        self._checkpoints_dir = Path(
            checkpoints_dir
            or os.environ.get("LTX_VIDEO_MODEL_PATH")
            or os.environ.get("LTX_VIDEO_CHECKPOINTS_DIR")
            or "./models/ltx_video"
        )
        self._output_dir = Path(output_dir or os.environ.get("LTX_VIDEO_OUTPUT_DIR", "./output/ltx_video"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            try:
                if self._runner_factory:
                    self._runner = self._runner_factory()
                else:
                    self._runner = LTXVideoInferenceRunner(
                        checkpoints_dir=self._checkpoints_dir,
                        output_dir=self._output_dir,
                    )
                self._initialized = True
            except Exception as exc:
                logger.warning(f"LTX-Video service initialization notice: {exc}")
                self._runner = None
                self._initialized = True

    def get_environment_status(self) -> LTXEnvironmentStatus:
        """Returns detailed environment diagnostics."""
        allow_mock = getattr(settings, "DEV_MOCK_ENGINE", False)
        return check_ltx_environment(
            checkpoints_dir=self._checkpoints_dir,
            allow_mock=allow_mock,
        )

    def get_runtime_status(self) -> dict[str, Any]:
        self.initialize()
        diag = self.get_environment_status()
        has_custom_runner = self._runner_factory is not None and self._runner is not None
        available = bool(diag.is_available or has_custom_runner)

        status_str = "ready" if available else "unconfigured"

        return {
            "engine_id": "ltx-video",
            "display_name": "LTX-Video Engine",
            "available": available,
            "initialized": self._initialized,
            "status_code": diag.status_code.value if not has_custom_runner else "READY",
            "status": status_str,
            "is_mock": diag.is_mock,
            "gpu_name": diag.gpu_name,
            "vram_total_gb": diag.vram_total_gb,
            "vram_available_gb": diag.vram_available_gb,
            "cuda_version": diag.cuda_version,
            "models_available": len(self.SUPPORTED_MODELS) if available else 0,
            "models_total": len(self.SUPPORTED_MODELS),
            "checkpoints_path": str(self._checkpoints_dir),
            "supports_audio": False,  # Pure visual video model
            "message": diag.diagnostic_message,
        }

    def list_models(self) -> list[dict[str, Any]]:
        status = self.get_runtime_status()
        is_avail = status["available"]
        return [
            {
                "engine_id": "ltx-video",
                "model_type": m.model_type,
                "name": m.name,
                "description": m.description,
                "supports_audio": False,
                "defaults": {
                    "num_inference_steps": m.default_steps,
                    "guidance_scale": m.default_guidance,
                    "fps": m.default_fps,
                    "resolution": m.default_resolution,
                    "num_frames": m.default_num_frames,
                },
                "availability": {
                    "available": is_avail,
                    "reason": None if is_avail else status.get("message"),
                },
            }
            for m in self.SUPPORTED_MODELS
        ]

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        self.initialize()
        model_type = str(generation_settings.get("model_type", "ltx-video-0.9.5")).strip()
        model_config = next((m for m in self.SUPPORTED_MODELS if m.model_type == model_type), None)
        if not model_config:
            raise ValueError(f"Unknown LTX-Video model type '{model_type}'.")

        prompt = str(generation_settings.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("Prompt cannot be empty for LTX-Video generation.")

        # Parse resolution
        res_str = str(generation_settings.get("resolution", model_config.default_resolution))
        if "*" in res_str:
            parts = res_str.split("*")
            width, height = int(parts[0]), int(parts[1])
        elif "x" in res_str:
            parts = res_str.split("x")
            width, height = int(parts[0]), int(parts[1])
        else:
            width, height = 768, 512

        validated = {
            "model_type": model_config.model_type,
            "prompt": prompt,
            "negative_prompt": str(generation_settings.get("negative_prompt", "") or ""),
            "width": int(generation_settings.get("width", width)),
            "height": int(generation_settings.get("height", height)),
            "num_inference_steps": int(generation_settings.get("num_inference_steps", model_config.default_steps)),
            "guidance_scale": float(generation_settings.get("guidance_scale", model_config.default_guidance)),
            "fps": int(generation_settings.get("fps", model_config.default_fps)),
            "resolution": f"{width}*{height}",
            "num_frames": int(generation_settings.get("num_frames", model_config.default_num_frames)),
            "seed": int(generation_settings.get("seed", 42)),
            "engine_id": "ltx-video",
        }

        if generation_settings.get("image_start"):
            validated["image_start"] = str(generation_settings["image_start"])
        if generation_settings.get("reference_image"):
            validated["image_start"] = str(generation_settings["reference_image"])
        if generation_settings.get("id"):
            validated["id"] = str(generation_settings["id"])

        return validated

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> Any:
        self.initialize()
        job_id = str(generation_settings.get("id") or uuid.uuid4())

        # If mock runner provided via factory
        if self._runner is not None and hasattr(self._runner, "submit"):
            return self._runner.submit(generation_settings, on_progress)

        # Build request object
        req = LTXGenerationRequest(
            prompt=generation_settings["prompt"],
            negative_prompt=generation_settings.get("negative_prompt", ""),
            width=generation_settings.get("width", 768),
            height=generation_settings.get("height", 512),
            num_frames=generation_settings.get("num_frames", 121),
            fps=generation_settings.get("fps", 24),
            num_inference_steps=generation_settings.get("num_inference_steps", 30),
            guidance_scale=generation_settings.get("guidance_scale", 3.0),
            seed=generation_settings.get("seed", 42),
            image_start=generation_settings.get("image_start"),
            model_type=generation_settings.get("model_type", "ltx-video-0.9.5"),
            job_id=job_id,
        )

        class LTXVideoJobExecution:
            def __init__(self, svc: LTXVideoService, job_req: LTXGenerationRequest, cb: Callable):
                self.svc = svc
                self.req = job_req
                self.cb = cb
                self.cancelled = False

            def result(self) -> EngineResult:
                if self.cancelled:
                    return EngineResult(success=False, error_message="LTX-Video generation was cancelled.")

                # If custom execute method
                if self.svc._runner is not None and hasattr(self.svc._runner, "execute"):
                    return self.svc._runner.execute(self.req, self.cb)

                diag = self.svc.get_environment_status()

                # Handle mock mode when DEV_MOCK_ENGINE=True
                if diag.is_mock:
                    if self.cb:
                        self.cb(EngineProgress(progress=50, phase="mock_diffusion", status="Mock rendering frames"))
                        self.cb(EngineProgress(progress=100, phase="completed", status="Mock completed"))
                    out_path = self.svc._output_dir / f"ltx_mock_{self.req.job_id}.mp4"
                    return EngineResult(
                        success=True,
                        output_files=[str(out_path.resolve())],
                    )

                # If real hardware is not available, report truthful error
                if not diag.is_available:
                    return EngineResult(
                        success=False,
                        error_message=f"[{diag.status_code.value}] {diag.diagnostic_message}",
                    )

                # Real GPU execution
                def _prog_bridge(pct: float, msg: str):
                    if self.cb:
                        self.cb(EngineProgress(progress=pct, status=msg, phase="diffusion"))

                res: LTXGenerationResult = self.svc._runner.execute_generation(
                    request=self.req,
                    progress_callback=_prog_bridge,
                )

                if res.success and res.output_path:
                    return EngineResult(
                        success=True,
                        output_files=[res.output_path],
                    )
                else:
                    return EngineResult(
                        success=False,
                        error_message=res.error_message or "LTX-Video generation failed.",
                    )

            def cancel(self):
                self.cancelled = True
                if self.svc._runner and hasattr(self.svc._runner, "cancel"):
                    self.svc._runner.cancel(self.req.job_id)

        return LTXVideoJobExecution(self, req, on_progress)

    def shutdown(self) -> None:
        with self._lock:
            if self._runner is not None:
                if hasattr(self._runner, "shutdown"):
                    try:
                        self._runner.shutdown()
                    except Exception:
                        pass
                if hasattr(self._runner, "unload"):
                    try:
                        self._runner.unload()
                    except Exception:
                        pass
            self._runner = None
            self._initialized = False
            logger.info("LTX-Video service shutdown complete.")


class LTXVideoAdapter(BaseVideoEngine):
    """
    Adapter integrating the Lightricks LTX-Video high-throughput DiT engine
    into the GenVid.AI engine registry.
    """

    def __init__(self, service: LTXVideoService | None = None) -> None:
        self._service = service or LTXVideoService()
        self._capabilities = EngineCapabilities(
            text_to_video=True,
            image_to_video=True,
            video_continuation=False,
            native_long_video=False,
            audio_generation=False,  # LTX-Video is pure visual video generation
            voice_conditioning=False,
            reference_image=True,
            reference_video=False,
            reference_audio=False,
            multiple_characters=False,
            custom_resolutions=True,
            configurable_fps=True,
            configurable_steps=True,
            configurable_seed=True,
            progress_reporting=True,
            cancellation=True,
        )

    @property
    def engine_id(self) -> str:
        return "ltx-video"

    @property
    def display_name(self) -> str:
        return "LTX-Video Engine"

    @property
    def description(self) -> str:
        return (
            "Lightricks LTX-Video high-throughput DiT video generation engine "
            "supporting fast text-to-video and image-to-video inference."
        )

    @property
    def capabilities(self) -> EngineCapabilities:
        return self._capabilities

    @property
    def is_available(self) -> bool:
        status = self.get_runtime_status()
        return bool(status.get("available", False))

    def initialize(self) -> None:
        self._service.initialize()

    def get_runtime_status(self) -> dict[str, Any]:
        return self._service.get_runtime_status()

    def list_models(self) -> list[dict[str, Any]]:
        return self._service.list_models()

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        return self._service.validate_generation(generation_settings)

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> EngineJobHandle:
        raw_handle = self._service.submit_generation(generation_settings, on_progress)
        return EngineJobHandle(
            job_id=str(generation_settings.get("id") or uuid.uuid4()),
            engine_id=self.engine_id,
            raw_handle=raw_handle,
        )

    def wait_for_result(self, handle: EngineJobHandle) -> EngineResult:
        try:
            if hasattr(handle.raw_handle, "result"):
                res = handle.raw_handle.result()
                if isinstance(res, EngineResult):
                    return res
                return EngineResult(
                    success=bool(getattr(res, "success", False)),
                    output_files=list(getattr(res, "output_files", []) or []),
                    error_message=getattr(res, "error_message", None),
                )
            return EngineResult(success=False, error_message="Invalid LTX-Video job handle.")
        except Exception as exc:
            logger.error("LTX-Video generation failed during wait_for_result: %s", exc, exc_info=True)
            return EngineResult(
                success=False,
                output_files=[],
                error_message=str(exc),
            )

    def cancel_generation(self, handle: EngineJobHandle) -> None:
        if handle and handle.raw_handle and hasattr(handle.raw_handle, "cancel"):
            handle.raw_handle.cancel()

    def shutdown(self) -> None:
        self._service.shutdown()
