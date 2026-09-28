"""
Declarative stub adapters for upcoming video generation engines.
Declare capabilities and availability status without implementing fake execution.
"""

from __future__ import annotations

from typing import Any, Callable

from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)
from app.engines.ltx2_adapter import LTX2Adapter


class _StubEngine(BaseVideoEngine):
    """Base helper for engines planned or not yet configured."""

    _engine_id: str
    _display_name: str
    _description: str
    _capabilities: EngineCapabilities

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def capabilities(self) -> EngineCapabilities:
        return self._capabilities

    @property
    def is_available(self) -> bool:
        return False

    def initialize(self) -> None:
        pass

    def get_runtime_status(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "display_name": self.display_name,
            "available": False,
            "initialized": False,
            "status": "unconfigured",
            "models_available": 0,
            "models_total": 0,
        }

    def list_models(self) -> list[dict[str, Any]]:
        return []

    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.display_name} is not yet installed or configured on this node.")

    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> EngineJobHandle:
        raise NotImplementedError(f"{self.display_name} is not yet installed or configured on this node.")

    def wait_for_result(self, handle: EngineJobHandle) -> EngineResult:
        raise NotImplementedError(f"{self.display_name} is not yet installed or configured on this node.")

    def cancel_generation(self, handle: EngineJobHandle) -> None:
        pass

    def shutdown(self) -> None:
        pass


from app.engines.ltx_video_adapter import LTXVideoAdapter
from app.engines.minimax_h3_adapter import (
    MiniMaxH3DirectorAdapter,
    MiniMaxH3LongVideoAdapter,
)
