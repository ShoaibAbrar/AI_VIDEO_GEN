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
        self._available = False
        self._init_error: str | None = None

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            try:
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
                self._available = True
                self._init_error = None
                logger.info("Wan2GP session initialized successfully")
            except Exception as e:
                self._session = None
                self._available = False
                self._init_error = str(e)
                logger.warning("Wan2GP runtime initialization skipped/failed: %s", e)
            finally:
                self._initialized = True

    def is_available(self) -> bool:
        self.initialize()
        return self._available

    def get_runtime_status(self) -> dict[str, Any]:
        self.initialize()
        if not self._available:
            return {
                "available": False,
                "reason": self._init_error or "Wan2GP runtime unavailable on this environment",
                "models_total": 0,
                "models_available": 0,
            }
        try:
            records = self._session.list_model_metadata(include_availability=True, main_output="video")
            total = len(records)
            avail = sum(1 for r in records if r.get("availability", {}).get("available", False))
            return {
                "available": True,
                "reason": None,
                "models_total": total,
                "models_available": avail,
            }
        except Exception as e:
            return {
                "available": False,
                "reason": str(e),
                "models_total": 0,
                "models_available": 0,
            }

    def _require_session(self) -> Any:
        self.initialize()
        if self._session is None:
            raise RuntimeError(f"Wan2GP session is not available: {self._init_error}")
        return self._session

    def list_models(self, only_available: bool = False) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        session = self._require_session()
        records = session.list_model_metadata(include_availability=True, main_output="video")
        if only_available:
            return [record for record in records if record.get("availability", {}).get("available", False)]
        return records

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        if not self.is_available():
            raise ValueError("GPU generation is unavailable on this environment (Wan2GP runtime not initialized).")
        session = self._require_session()
        model_type = str(generation_settings.get("model_type", "")).strip()
        model_def = session.get_model_def(model_type)
        if model_def is None:
            raise ValueError(f"Unknown Wan2GP model: '{model_type}'")

        availability = session.get_model_availability(model_type)
        if not availability.get("available", False):
            reason = availability.get("reason", "Model checkpoint files missing")
            raise ValueError(f"The selected model '{model_type}' is not available on this GPU machine: {reason}")

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
                self._available = False
                return
            try:
                self._session.close()
            finally:
                self._session = None
                self._initialized = False
                self._available = False
                logger.info("Wan2GP session shut down")
