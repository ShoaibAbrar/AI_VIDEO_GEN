"""
Central Video Engine Registry & Capability Discovery.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from app.core.logging_config import logger
from app.engines.base import BaseVideoEngine
from app.engines.ltx2_adapter import LTX2Adapter
from app.engines.ltx_video_adapter import LTXVideoAdapter
from app.engines.minimax_h3_adapter import (
    MiniMaxH3Adapter,
    MiniMaxH3DirectorAdapter,
    MiniMaxH3LongVideoAdapter,
)
from app.engines.money_printer_turbo_adapter import MoneyPrinterTurboAdapter
from app.engines.wan2gp_adapter import Wan2GPAdapter


class VideoEngineRegistry:
    """
    Registry for managing available video generation engines,
    providing capability discovery, engine routing, and lifecycle control.
    """

    def __init__(self) -> None:
        self._engines: dict[str, BaseVideoEngine] = {}
        self._default_engine_id: str | None = None
        self._lock = Lock()

    def register(self, engine: BaseVideoEngine, default: bool = False) -> None:
        """Register a video generation engine."""
        with self._lock:
            engine_id = engine.engine_id.lower().strip()
            self._engines[engine_id] = engine
            if default or self._default_engine_id is None:
                self._default_engine_id = engine_id
            logger.info("Registered video engine: %s (%s)", engine.display_name, engine_id)

    def unregister(self, engine_id: str) -> None:
        """Unregister a video engine by ID."""
        with self._lock:
            engine_id = engine_id.lower().strip()
            if engine_id in self._engines:
                del self._engines[engine_id]
                if self._default_engine_id == engine_id:
                    self._default_engine_id = next(iter(self._engines.keys()), None)

    def get_engine(self, engine_id: str | None = None) -> BaseVideoEngine:
        """
        Get an engine by ID or return the default registered engine.
        Raises ValueError if the requested engine is unknown.
        """
        with self._lock:
            if engine_id is None or not engine_id.strip():
                if self._default_engine_id is None or self._default_engine_id not in self._engines:
                    raise RuntimeError("No default video engine is registered.")
                return self._engines[self._default_engine_id]

            key = engine_id.lower().strip()
            engine = self._engines.get(key)
            if engine is None:
                available_ids = list(self._engines.keys())
                raise ValueError(
                    f"Unknown video engine: '{engine_id}'. Available engines: {available_ids}"
                )
            return engine

    def resolve_engine_for_model(self, model_type: str) -> BaseVideoEngine:
        """
        Find the engine that owns the given model_type, or fallback to default engine.
        """
        with self._lock:
            for engine in self._engines.values():
                try:
                    for model in engine.list_models():
                        if model.get("model_type") == model_type:
                            return engine
                except Exception:
                    continue
            # Fallback to default engine
            return self.get_engine()

    def list_engine_ids(self) -> list[str]:
        """List all registered engine IDs."""
        with self._lock:
            return list(self._engines.keys())

    def list_engines(self, only_available: bool = False) -> list[dict[str, Any]]:
        """List all registered engines with metadata and capabilities."""
        with self._lock:
            records = []
            for engine_id, engine in self._engines.items():
                is_avail = engine.is_available
                if only_available and not is_avail:
                    continue
                records.append({
                    "engine_id": engine.engine_id,
                    "display_name": engine.display_name,
                    "description": engine.description,
                    "available": is_avail,
                    "is_default": engine_id == self._default_engine_id,
                    "capabilities": engine.capabilities.to_dict(),
                })
            return records

    def list_all_models(self, only_available: bool = False) -> list[dict[str, Any]]:
        """List models across all registered and active engines."""
        with self._lock:
            all_models: list[dict[str, Any]] = []
            for engine in self._engines.values():
                try:
                    models = engine.list_models()
                    for model in models:
                        is_avail = model.get("availability", {}).get("available", False)
                        if only_available and not is_avail:
                            continue
                        all_models.append(model)
                except Exception as exc:
                    logger.warning(
                        "Could not list models for engine %s: %s", engine.engine_id, exc
                    )
            return all_models

    def get_runtime_status(self) -> dict[str, Any]:
        """Aggregate health and runtime status across all engines."""
        with self._lock:
            statuses: dict[str, Any] = {}
            total_available_models = 0
            for engine_id, engine in self._engines.items():
                try:
                    st = engine.get_runtime_status()
                    statuses[engine_id] = st
                    total_available_models += st.get("models_available", 0)
                except Exception as exc:
                    statuses[engine_id] = {
                        "available": False,
                        "status": "error",
                        "error": str(exc),
                    }

            default_eng = self._engines.get(self._default_engine_id or "")
            is_overall_available = default_eng.is_available if default_eng else False

            return {
                "available": is_overall_available,
                "default_engine": self._default_engine_id,
                "models_available": total_available_models,
                "engines": statuses,
            }

    def shutdown_all(self) -> None:
        """Shutdown and release resources across all registered engines."""
        with self._lock:
            for engine in self._engines.values():
                try:
                    engine.shutdown()
                except Exception as exc:
                    logger.warning("Error shutting down engine %s: %s", engine.engine_id, exc)


from app.config import settings
from app.engines.mock_engine import MockVideoEngine

_GLOBAL_REGISTRY: VideoEngineRegistry | None = None
_REGISTRY_LOCK = Lock()


def get_engine_registry() -> VideoEngineRegistry:
    """Return the global VideoEngineRegistry singleton, initializing default engines."""
    global _GLOBAL_REGISTRY
    with _REGISTRY_LOCK:
        if _GLOBAL_REGISTRY is None:
            registry = VideoEngineRegistry()
            if settings.DEV_MOCK_ENGINE:
                logger.info("DEV_MOCK_ENGINE is enabled: Registering MockVideoEngine as default")
                registry.register(MockVideoEngine(), default=True)
                registry.register(Wan2GPAdapter())
            else:
                # Register Wan2GP as primary default engine
                registry.register(Wan2GPAdapter(), default=True)
                registry.register(MockVideoEngine())
            # Register declarative engine stubs for capability discovery
            registry.register(LTXVideoAdapter())
            registry.register(LTX2Adapter())
            registry.register(MiniMaxH3Adapter())
            registry.register(MiniMaxH3LongVideoAdapter())
            registry.register(MiniMaxH3DirectorAdapter())
            registry.register(MoneyPrinterTurboAdapter())
            _GLOBAL_REGISTRY = registry
        return _GLOBAL_REGISTRY
