"""
Concrete LTX-2 Engine Adapter implementing BaseVideoEngine.
Provides programmatic integration for Lightricks LTX-2 joint multimodal Audio-Video foundation models.
Connects to real LTX2InferenceRunner on CUDA hardware or returns truthful diagnostics.
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
from app.engines.ltx2.diagnostics import LTX2EnvironmentStatus, check_ltx2_environment
from app.engines.ltx2.models import (
    LTX2GenerationRequest,
    LTX2GenerationResult,
    LTX2ModelConfig,
    LTX2StatusCode,
)
from app.engines.ltx2.runner import LTX2InferenceRunner


class LTX2Service:
    """
    Service layer managing LTX-2 model lifecycle, environment verification,
    and delegating inference execution to LTX2InferenceRunner.
    """

    SUPPORTED_MODELS = [
        LTX2ModelConfig(
            model_type="ltx-2-19b-av",
            name="LTX-2 19B Audio-Video",
            description="14B Video + 5B Audio dual-stream transformer for joint AV generation.",
            supports_audio=True,
            default_steps=40,
            default_guidance=4.5,
            default_fps=25,
            default_resolution="1024*576",
            default_num_frames=125,
        ),
        LTX2ModelConfig(
            model_type="ltx-2-distilled",
            name="LTX-2 Distilled Fast",
            description="Few-step distilled LTX-2 checkpoint for low-latency AV generation.",
            supports_audio=True,
            default_steps=8,
            default_guidance=1.0,
            default_fps=25,
            default_resolution="768*512",
            default_num_frames=100,
        ),
        LTX2ModelConfig(
            model_type="ltx-2.3-av",
            name="LTX-2.3 AV High Fidelity",
            description="Upgraded LTX-2.3 high-fidelity audio-video checkpoint.",
            supports_audio=True,
            default_steps=50,
            default_guidance=5.0,
            default_fps=25,
            default_resolution="1280*720",
            default_num_frames=125,
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
            or os.environ.get("LTX2_MODEL_PATH")
            or os.environ.get("LTX2_CHECKPOINTS_DIR")
            or "./models/ltx2"
        )
        self._output_dir = Path(output_dir or os.environ.get("LTX2_OUTPUT_DIR", "./output/ltx2"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            try:
                if self._runner_factory:
                    self._runner = self._runner_factory()
                else:
                    self._runner = LTX2InferenceRunner(
                        checkpoints_dir=self._checkpoints_dir,
                        output_dir=self._output_dir,
                    )
                self._initialized = True
            except Exception as exc:
                logger.warning(f"LTX-2 service initialization notice: {exc}")
                self._runner = None
                self._initialized = True

    def get_environment_status(self) -> LTX2EnvironmentStatus:
        """Returns detailed environment diagnostics."""
        allow_mock = getattr(settings, "DEV_MOCK_ENGINE", False)
        return check_ltx2_environment(
            checkpoints_dir=self._checkpoints_dir,
            allow_mock=allow_mock,
        )

    def get_runtime_status(self) -> dict[str, Any]:
        self.initialize()
        diag = self.get_environment_status()
        has_custom_runner = self._runner_factory is not None and self._runner is not None
        available = bool(diag.is_available or has_custom_runner)
        status_str = "GPU-UNVERIFIED" if has_custom_runner else ("ready" if available else "unconfigured")

        return {
            "engine_id": "ltx-2",
            "display_name": "LTX-2 Audio-Video Engine",
            "available": available,
            "initialized": self._initialized,
            "status_code": diag.status_code.value if not has_custom_runner else LTX2StatusCode.GPU_UNVERIFIED.value,
            "status": status_str,
            "is_mock": diag.is_mock,
            "gpu_name": diag.gpu_name,
            "vram_total_gb": diag.vram_total_gb,
            "vram_available_gb": diag.vram_available_gb,
            "cuda_version": diag.cuda_version,
            "models_available": len(self.SUPPORTED_MODELS) if available else 0,
            "models_total": len(self.SUPPORTED_MODELS),
            "checkpoints_path": str(self._checkpoints_dir),
            "supports_joint_audio": True,
            "message": diag.diagnostic_message,
        }

    def list_models(self) -> list[dict[str, Any]]:
        status = self.get_runtime_status()
        is_avail = status["available"]
        return [
            {
                "engine_id": "ltx-2",
                "model_type": m.model_type,
                "name": m.name,
                "description": m.description,
                "supports_audio": m.supports_audio,
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
        model_type = str(generation_settings.get("model_type", "ltx-2-19b-av")).strip()
        model_config = next((m for m in self.SUPPORTED_MODELS if m.model_type == model_type), None)
        if not model_config:
            raise ValueError(f"Unknown LTX-2 model type '{model_type}'.")

        prompt = str(generation_settings.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("Prompt cannot be empty for LTX-2 generation.")

        # Parse resolution
        res_str = str(generation_settings.get("resolution", model_config.default_resolution))
        if "*" in res_str:
            parts = res_str.split("*")
            width, height = int(parts[0]), int(parts[1])
        elif "x" in res_str:
            parts = res_str.split("x")
            width, height = int(parts[0]), int(parts[1])
        else:
            width, height = 1024, 576

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
            "generate_audio": bool(generation_settings.get("generate_audio", True)),
            "engine_id": "ltx-2",
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

        req = LTX2GenerationRequest(
            prompt=generation_settings["prompt"],
            negative_prompt=generation_settings.get("negative_prompt", ""),
            width=generation_settings.get("width", 1024),
            height=generation_settings.get("height", 576),
            num_frames=generation_settings.get("num_frames", 125),
            fps=generation_settings.get("fps", 25),
            num_inference_steps=generation_settings.get("num_inference_steps", 40),
            guidance_scale=generation_settings.get("guidance_scale", 4.5),
            seed=generation_settings.get("seed", 42),
            generate_audio=generation_settings.get("generate_audio", True),
            image_start=generation_settings.get("image_start"),
            model_type=generation_settings.get("model_type", "ltx-2-19b-av"),
            job_id=job_id,
        )

        class LTX2JobExecution:
            def __init__(self, svc: LTX2Service, job_req: LTX2GenerationRequest, cb: Callable):
                self.svc = svc
                self.req = job_req
                self.cb = cb
                self.cancelled = False

            def result(self) -> EngineResult:
                if self.cancelled:
                    return EngineResult(success=False, error_message="LTX-2 generation was cancelled.")

                if self.svc._runner is not None and hasattr(self.svc._runner, "execute"):
                    return self.svc._runner.execute(self.req, self.cb)

                diag = self.svc.get_environment_status()

                # Handle mock mode when DEV_MOCK_ENGINE=True
                if diag.is_mock:
                    if self.cb:
                        self.cb(EngineProgress(progress=50, phase="mock_diffusion", status="Mock rendering AV latents"))
                        self.cb(EngineProgress(progress=100, phase="completed", status="Mock completed"))
                    out_path = self.svc._output_dir / f"ltx2_mock_{self.req.job_id}.mp4"
                    return EngineResult(
                        success=True,
                        output_files=[str(out_path.resolve())],
                    )

                if not diag.is_available:
                    return EngineResult(
                        success=False,
                        error_message=f"[{diag.status_code.value}] {diag.diagnostic_message}",
                    )

                # Real GPU execution
                def _prog_bridge(pct: float, msg: str):
                    if self.cb:
                        self.cb(EngineProgress(progress=pct, status=msg, phase="diffusion"))

                res: LTX2GenerationResult = self.svc._runner.execute_generation(
                    request=self.req,
                    progress_callback=_prog_bridge,
                )

                if res.success:
                    files = []
                    if res.combined_media_path:
                        files.append(res.combined_media_path)
                    elif res.video_path:
                        files.append(res.video_path)
                    if res.audio_path and res.audio_path not in files:
                        files.append(res.audio_path)

                    return EngineResult(
                        success=True,
                        output_files=files,
                    )
                else:
                    return EngineResult(
                        success=False,
                        error_message=res.error_message or "LTX-2 generation failed.",
                    )

            def cancel(self):
                self.cancelled = True
                if self.svc._runner and hasattr(self.svc._runner, "cancel"):
                    self.svc._runner.cancel(self.req.job_id)

        return LTX2JobExecution(self, req, on_progress)

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
            logger.info("LTX-2 service shutdown complete.")


class LTX2Adapter(BaseVideoEngine):
    """
    Adapter integrating the Lightricks LTX-2 joint Audio-Video foundation model
    into the GenVid.AI engine registry.
    """

    def __init__(self, service: LTX2Service | None = None) -> None:
        self._service = service or LTX2Service()
        self._capabilities = EngineCapabilities(
            text_to_video=True,
            image_to_video=True,
            video_continuation=True,
            native_long_video=False,
            audio_generation=True,  # LTX-2 natively generates synchronized audio
            voice_conditioning=True,
            reference_image=True,
            reference_video=False,
            reference_audio=True,
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
        return "ltx-2"

    @property
    def display_name(self) -> str:
        return "LTX-2 Audio-Video Engine"

    @property
    def description(self) -> str:
        return (
            "Lightricks LTX-2 multimodal joint Audio-Video diffusion engine "
            "producing synchronized cinematic video and audio."
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
            return EngineResult(success=False, error_message="Invalid LTX-2 job handle.")
        except Exception as exc:
            logger.error("LTX-2 generation failed during wait_for_result: %s", exc, exc_info=True)
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
