"""Platform-facing adapter for the repository's in-process WanGP API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from app.config import settings as app_settings
from app.core.logging_config import logger


@dataclass(frozen=True)
class Wan2GPProgress:
    progress: int | None = None
    current_step: int | None = None
    total_steps: int | None = None
    phase: str | None = None
    status: str | None = None


class _ProgressCallbacks:
    def __init__(self, on_progress: Callable[[Wan2GPProgress], None]) -> None:
        self._on_progress = on_progress

    def on_progress(self, update: Any) -> None:
        self._on_progress(
            Wan2GPProgress(
                progress=getattr(update, "progress", None),
                current_step=getattr(update, "current_step", None),
                total_steps=getattr(update, "total_steps", None),
                phase=getattr(update, "phase", None),
                status=getattr(update, "status", None),
            )
        )

    def on_status(self, status: str) -> None:
        self._on_progress(Wan2GPProgress(status=str(status)))


@dataclass
class Wan2GPJobHandle:
    """Internal handle kept by the single worker for one WanGP submission."""

    job: Any
    progress: Wan2GPProgress | None = None


class Wan2GPService:
    """Own one reusable WanGPSession and serialize access to it."""

    def __init__(self, session_factory: Callable[..., Any] | None = None) -> None:
        self._session_factory = session_factory
        self._session: Any | None = None
        self._lock = Lock()
        self._initialized = False

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            session_factory = self._session_factory
            if session_factory is None:
                from shared.api import init as session_factory

            config_path = app_settings.WAN2GP_CONFIG_PATH or None
            self._session = session_factory(
                root=Path(app_settings.WAN2GP_ROOT),
                config_path=config_path,
                output_dir=Path(app_settings.STORAGE_PATH) / "wan2gp-runtime",
                console_output=False,
                console_isatty=False,
            )
            self._initialized = True
            logger.info("Wan2GP session initialized")

    def _require_session(self) -> Any:
        self.initialize()
        if self._session is None:
            raise RuntimeError("Wan2GP session is not initialized")
        return self._session

    def list_models(self) -> list[dict[str, Any]]:
        session = self._require_session()
        records = session.list_model_metadata(include_availability=True, main_output="video")
        return records

    def get_runtime_status(self) -> dict[str, Any]:
        with self._lock:
            initialized = self._initialized and self._session is not None
        try:
            session = self._require_session()
            records = session.list_model_metadata(include_availability=True, main_output="video")
            available_count = sum(1 for r in records if r.get("availability", {}).get("available", False))
            return {
                "available": True,
                "initialized": True,
                "status": "ready",
                "models_available": available_count,
                "models_total": len(records),
            }
        except Exception as exc:
            return {
                "available": False,
                "initialized": initialized,
                "status": "unavailable",
                "error": str(exc),
                "models_available": 0,
                "models_total": 0,
            }

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session()
        model_type = str(generation_settings.get("model_type", "")).strip()
        model_def = session.get_model_def(model_type)
        if model_def is None:
            raise ValueError("Unknown Wan2GP model")

        availability = session.get_model_availability(model_type)
        if not availability.get("available", False):
            raise ValueError("The selected Wan2GP model is not available")

        defaults = session.get_default_settings(model_type)
        merged = dict(defaults)
        merged.update(generation_settings)
        merged["model_type"] = model_type
        return merged

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[Wan2GPProgress], None],
    ) -> Wan2GPJobHandle:
        session = self._require_session()
        callbacks = _ProgressCallbacks(on_progress)
        job = session.submit_task(generation_settings, callbacks=callbacks)
        return Wan2GPJobHandle(job=job)

    def wait_for_result(self, handle: Wan2GPJobHandle) -> Any:
        return handle.job.result()

    def cancel_generation(self, handle: Wan2GPJobHandle) -> None:
        handle.job.cancel()

    def shutdown(self) -> None:
        with self._lock:
            if self._session is None:
                self._initialized = False
                return
            try:
                self._session.close()
            finally:
                self._session = None
                self._initialized = False
                logger.info("Wan2GP session shut down")
