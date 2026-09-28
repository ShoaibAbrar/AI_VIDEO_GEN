"""
MoneyPrinterTurbo Engine Adapter implementing BaseVideoEngine contract.
Enables transparent, model-agnostic execution of automated short/long production videos.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
import os
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional
import uuid

from app.core.logging_config import logger
from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)
from app.engines.money_printer_turbo.diagnostics import (
    MoneyPrinterTurboEnvironmentStatus,
    check_moneyprinterturbo_environment,
)
from app.engines.money_printer_turbo.models import (
    MaterialSourceType,
    MoneyPrinterTurboRequest,
    MoneyPrinterTurboResult,
    MoneyPrinterTurboStatusCode,
    SubtitleStyle,
)
from app.engines.money_printer_turbo.runner import MoneyPrinterTurboRunner


# ---------------------------------------------------------------------------
# Service Layer
# ---------------------------------------------------------------------------

class MoneyPrinterTurboService:
    """
    Service layer managing MoneyPrinterTurbo runner lifecycle,
    environment discovery, settings validation, and job dispatch.
    """

    def __init__(
        self,
        runner_factory: Callable[..., Any] | None = None,
        output_dir: Optional[str | Path] = None,
        materials_dir: Optional[str | Path] = None,
        music_dir: Optional[str | Path] = None,
    ) -> None:
        self._runner_factory = runner_factory
        self._runner: Optional[MoneyPrinterTurboRunner] = None
        self._lock = threading.Lock()
        self._initialized = False

        self._output_dir = Path(
            output_dir
            or os.environ.get("MONEYPRINTERTURBO_OUTPUT_DIR")
            or "./output/moneyprinterturbo"
        )
        self._materials_dir = Path(
            materials_dir
            or os.environ.get("LOCAL_MATERIAL_DIR")
            or "./materials"
        )
        self._music_dir = Path(
            music_dir
            or os.environ.get("MONEYPRINTERTURBO_MUSIC_DIR")
            or "./materials/music"
        )

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            try:
                if self._runner_factory:
                    self._runner = self._runner_factory()
                else:
                    self._runner = MoneyPrinterTurboRunner(
                        output_dir=self._output_dir,
                        materials_dir=self._materials_dir,
                        music_dir=self._music_dir,
                    )
                self._initialized = True
                logger.info("MoneyPrinterTurboService initialized.")
            except Exception as exc:
                logger.error(f"MoneyPrinterTurboService initialization failed: {exc}", exc_info=True)

    def get_runtime_status(self) -> Dict[str, Any]:
        diag = check_moneyprinterturbo_environment(
            local_material_dir=self._materials_dir,
            allow_mock=False,
        )
        return {
            "engine_id": "moneyprinterturbo",
            "available": diag.is_available,
            "status_code": diag.status_code.value,
            "is_mock": diag.is_mock,
            "ffmpeg_available": diag.ffmpeg_available,
            "ffmpeg_path": diag.ffmpeg_path,
            "edge_tts_available": diag.edge_tts_available,
            "pexels_configured": diag.pexels_configured,
            "pixabay_configured": diag.pixabay_configured,
            "local_materials_count": diag.local_materials_count,
            "missing_dependencies": diag.missing_dependencies,
            "missing_api_keys": diag.missing_api_keys,
            "message": diag.diagnostic_message,
        }

    def list_models(self) -> List[Dict[str, Any]]:
        diag = check_moneyprinterturbo_environment(allow_mock=False)
        return [
            {
                "model_id": "moneyprinterturbo-production-v1",
                "model_type": "production-pipeline",
                "name": "MoneyPrinterTurbo Automated Production",
                "description": (
                    "End-to-end video synthesis pipeline: script writing, stock footage sourcing "
                    "(Pexels/Pixabay/Local), Edge TTS narration, animated subtitles, BGM mixing, and FFmpeg composition."
                ),
                "supports_audio": True,
                "supports_subtitles": True,
                "supports_bgm": True,
                "native_long_video": True,
                "aspect_ratios": ["9:16", "16:9", "1:1"],
                "availability": {
                    "available": diag.is_available,
                    "reason": diag.diagnostic_message,
                },
            }
        ]

    def validate_generation(self, generation_settings: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        topic = generation_settings.get("topic") or generation_settings.get("prompt")
        script = generation_settings.get("script")

        if not topic and not script:
            errors.append("Either 'topic' (or 'prompt') or 'script' must be provided.")

        duration = float(generation_settings.get("duration", generation_settings.get("total_duration_seconds", 30.0)))
        if duration < 5.0:
            errors.append("Video duration must be at least 5.0 seconds.")
        elif duration > 600.0:
            warnings.append("Video duration exceeds 10 minutes; rendering may take longer.")

        aspect_ratio = generation_settings.get("aspect_ratio", "9:16")
        if aspect_ratio not in ("9:16", "16:9", "1:1", "portrait", "landscape", "square"):
            warnings.append(f"Uncommon aspect ratio '{aspect_ratio}', defaulting to 9:16.")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "engine_id": "moneyprinterturbo",
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }

    def submit_generation(
        self,
        generation_settings: Dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> Any:
        if not self._initialized:
            self.initialize()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        service_self = self

        class MoneyPrinterTurboJob:
            def __init__(self, job_id: str, settings_dict: Dict[str, Any], prog_cb: Any) -> None:
                self.job_id = job_id
                self.settings = settings_dict
                self.prog_cb = prog_cb
                self.cancelled = False
                self._future = executor.submit(self._run)

            def _run(self) -> EngineResult:
                if service_self._runner is None:
                    return EngineResult(
                        success=False,
                        error_message="MoneyPrinterTurbo runner is not initialized.",
                    )

                # Parse material provider
                mat_prov_raw = self.settings.get("material_provider", "composite")
                try:
                    mat_prov = MaterialSourceType(mat_prov_raw)
                except Exception:
                    mat_prov = MaterialSourceType.COMPOSITE

                # Parse subtitle style
                sub_style_raw = self.settings.get("subtitle_style", "bottom_center")
                try:
                    sub_style = SubtitleStyle(sub_style_raw)
                except Exception:
                    sub_style = SubtitleStyle.BOTTOM_CENTER

                req = MoneyPrinterTurboRequest(
                    topic=self.settings.get("topic") or self.settings.get("prompt"),
                    script=self.settings.get("script"),
                    language=str(self.settings.get("language", "en")),
                    voice_name=str(self.settings.get("voice_name", "en-US-ChristopherNeural")),
                    voice_rate=str(self.settings.get("voice_rate", "+0%")),
                    target_duration_seconds=float(self.settings.get("duration", self.settings.get("total_duration_seconds", 30.0))),
                    aspect_ratio=str(self.settings.get("aspect_ratio", "9:16")),
                    resolution=str(self.settings.get("resolution", "1080*1920")),
                    fps=int(self.settings.get("fps", 30)),
                    subtitle_enabled=bool(self.settings.get("subtitles_enabled", self.settings.get("subtitle_enabled", True))),
                    subtitle_style=sub_style,
                    music_enabled=bool(self.settings.get("music_enabled", True)),
                    music_name=self.settings.get("music_name"),
                    music_volume=float(self.settings.get("music_volume", 0.20)),
                    material_provider=mat_prov,
                    pexels_api_key=self.settings.get("pexels_api_key"),
                    pixabay_api_key=self.settings.get("pixabay_api_key"),
                    local_material_dir=self.settings.get("local_material_dir"),
                    job_id=self.job_id,
                    output_video_path=self.settings.get("output_video_path"),
                    plan_only=bool(self.settings.get("plan_only", False)),
                )

                def progress_adapter(pct: float, msg: str) -> None:
                    if not self.cancelled:
                        on_progress(EngineProgress(percentage=pct, status_text=msg))

                result = service_self._runner.execute_production_video(
                    request=req,
                    progress_callback=progress_adapter,
                )

                return EngineResult(
                    success=result.success,
                    output_files=list(result.output_files or ([result.output_path] if result.output_path else [])),
                    error_message=result.error_message,
                )

            def result(self) -> EngineResult:
                return self._future.result()

            def cancel(self) -> None:
                self.cancelled = True
                if service_self._runner and hasattr(service_self._runner, "cancel"):
                    service_self._runner.cancel(self.job_id)

        job_id = str(generation_settings.get("id") or uuid.uuid4())
        return MoneyPrinterTurboJob(job_id, generation_settings, on_progress)

    def shutdown(self) -> None:
        with self._lock:
            self._runner = None
            self._initialized = False
            logger.info("MoneyPrinterTurboService shut down.")


# ---------------------------------------------------------------------------
# Engine Adapter
# ---------------------------------------------------------------------------

class MoneyPrinterTurboAdapter(BaseVideoEngine):
    """
    Adapter integrating MoneyPrinterTurbo production pipeline into GenVid.AI.
    """

    def __init__(self, service: Optional[MoneyPrinterTurboService] = None) -> None:
        self._service = service or MoneyPrinterTurboService()
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
            multiple_characters=False,  # Narration focus
            custom_resolutions=True,
            configurable_fps=True,
            configurable_steps=False,  # Video composition based, not diffusion steps
            configurable_seed=False,
            progress_reporting=True,
            cancellation=True,
        )

    @property
    def engine_id(self) -> str:
        return "moneyprinterturbo"

    @property
    def display_name(self) -> str:
        return "MoneyPrinterTurbo Production Engine"

    @property
    def description(self) -> str:
        return (
            "Automated production video synthesis engine. Orchestrates script generation, "
            "stock footage sourcing (Pexels/Pixabay/Local), Edge TTS voiceover, stylized subtitles, "
            "background music mixing, and FFmpeg video assembly."
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

    def get_runtime_status(self) -> Dict[str, Any]:
        return self._service.get_runtime_status()

    def list_models(self) -> List[Dict[str, Any]]:
        return self._service.list_models()

    def validate_generation(self, generation_settings: Dict[str, Any]) -> Dict[str, Any]:
        return self._service.validate_generation(generation_settings)

    def submit_generation(
        self,
        generation_settings: Dict[str, Any],
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
            return EngineResult(success=False, error_message="Invalid MoneyPrinterTurbo job handle.")
        except Exception as exc:
            logger.error(f"MoneyPrinterTurbo wait_for_result failed: {exc}", exc_info=True)
            return EngineResult(success=False, error_message=str(exc))

    def cancel_generation(self, handle: EngineJobHandle) -> None:
        if handle and handle.raw_handle and hasattr(handle.raw_handle, "cancel"):
            handle.raw_handle.cancel()

    def shutdown(self) -> None:
        self._service.shutdown()
