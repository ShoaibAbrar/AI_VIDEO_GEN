"""
Concrete Wan2GP Adapter implementing BaseVideoEngine.
Directly wraps the in-process Wan2GP runtime (shared.api).
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)
from app.services.wan2gp_service import Wan2GPProgress, Wan2GPService


class Wan2GPAdapter(BaseVideoEngine):
    """
    Adapter integrating the repository's in-process Wan2GP engine
    behind the generic BaseVideoEngine interface.
    """

    def __init__(self, service: Wan2GPService | None = None) -> None:
        self._service = service or Wan2GPService()
        self._capabilities = EngineCapabilities(
            text_to_video=True,
            image_to_video=True,
            video_continuation=True,
            native_long_video=False,
            audio_generation=True,
            voice_conditioning=True,
            reference_image=True,
            reference_video=True,
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
        return "wan2gp"

    @property
    def display_name(self) -> str:
        return "Wan2GP Engine"

    @property
    def description(self) -> str:
        return (
            "In-process Wan2GP multi-modal generation engine supporting Wan2.1, LTXV, "
            "and derived generative video models with local GPU inference."
        )

    @property
    def capabilities(self) -> EngineCapabilities:
        return self._capabilities

    @property
    def is_available(self) -> bool:
        status = self.get_runtime_status()
        return bool(status.get("available", False))

    @property
    def raw_service(self) -> Wan2GPService:
        """Access the underlying Wan2GP service instance."""
        return self._service

    def initialize(self) -> None:
        self._service.initialize()

    def get_runtime_status(self) -> dict[str, Any]:
        status = self._service.get_runtime_status()
        status["engine_id"] = self.engine_id
        status["display_name"] = self.display_name
        return status

    def list_models(self) -> list[dict[str, Any]]:
        models = self._service.list_models()
        # Ensure engine_id is tagged on all model metadata
        for model in models:
            model.setdefault("engine_id", self.engine_id)
        return models

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        validated = self._service.validate_generation(generation_settings)
        validated["engine_id"] = self.engine_id
        return validated

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> EngineJobHandle:
        def _progress_bridge(p: Wan2GPProgress) -> None:
            on_progress(
                EngineProgress(
                    progress=p.progress,
                    current_step=p.current_step,
                    total_steps=p.total_steps,
                    phase=p.phase,
                    status=p.status,
                )
            )

        raw_handle = self._service.submit_generation(generation_settings, _progress_bridge)
        return EngineJobHandle(
            job_id=str(generation_settings.get("id") or uuid.uuid4()),
            engine_id=self.engine_id,
            raw_handle=raw_handle,
        )

    def wait_for_result(self, handle: EngineJobHandle) -> EngineResult:
        try:
            raw_result = self._service.wait_for_result(handle.raw_handle)
            success = bool(getattr(raw_result, "success", False))
            generated_files = list(getattr(raw_result, "generated_files", []) or [])
            artifacts = tuple(getattr(raw_result, "artifacts", ()) or ())
            errors = list(getattr(raw_result, "errors", ()) or ())
            error_message = str(errors[0]) if errors else None

            return EngineResult(
                success=success,
                output_files=generated_files,
                error_message=error_message,
                artifacts=artifacts,
                raw_result=raw_result,
            )
        except Exception as exc:
            return EngineResult(
                success=False,
                output_files=[],
                error_message=str(exc),
            )

    def cancel_generation(self, handle: EngineJobHandle) -> None:
        self._service.cancel_generation(handle.raw_handle)

    def shutdown(self) -> None:
        self._service.shutdown()
