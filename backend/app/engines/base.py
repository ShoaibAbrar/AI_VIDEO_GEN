"""
Abstract Base Video Engine and Capability Contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class EngineCapabilities:
    """Declared capabilities supported by a video generation engine."""

    text_to_video: bool = True
    image_to_video: bool = False
    video_continuation: bool = False
    native_long_video: bool = False
    audio_generation: bool = False
    voice_conditioning: bool = False
    reference_image: bool = False
    reference_video: bool = False
    reference_audio: bool = False
    voice_cloning: bool = False
    multiple_characters: bool = False
    custom_resolutions: bool = False
    configurable_fps: bool = True
    configurable_steps: bool = True
    configurable_seed: bool = True
    progress_reporting: bool = True
    cancellation: bool = True

    def to_dict(self) -> dict[str, bool]:
        """Return capabilities as a dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class EngineProgress:
    """Normalized progress update reported during video generation."""

    progress: int | None = None
    current_step: int | None = None
    total_steps: int | None = None
    phase: str | None = None
    status: str | None = None


@dataclass
class EngineJobHandle:
    """Opaque handle tracking an in-flight engine execution."""

    job_id: str
    engine_id: str
    raw_handle: Any = None
    progress: EngineProgress | None = None


@dataclass(frozen=True)
class EngineResult:
    """Normalized generation result returned by an engine execution."""

    success: bool
    output_files: list[str] = field(default_factory=list)
    error_message: str | None = None
    artifacts: tuple[Any, ...] = ()
    raw_result: Any = None


class BaseVideoEngine(ABC):
    """
    Abstract contract that all video generation engines must implement.
    Allows the platform to orchestrate Wan2GP, LTX-2, LTX-Video, MiniMax H3, etc.
    """

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique engine identifier (e.g. 'wan2gp', 'ltx-video', 'ltx-2', 'minimax-h3')."""
        raise NotImplementedError

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable engine name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Engine overview and specialization description."""
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> EngineCapabilities:
        """Set of capabilities supported by this engine."""
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        """Whether this engine is installed, configured, and ready for inference."""
        return True

    @abstractmethod
    def initialize(self) -> None:
        """Eagerly initialize engine sessions, weights, or worker connections."""
        raise NotImplementedError

    @abstractmethod
    def get_runtime_status(self) -> dict[str, Any]:
        """Report engine runtime telemetry, readiness, and model availability counts."""
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[dict[str, Any]]:
        """List metadata for all models supported by this engine."""
        raise NotImplementedError

    @abstractmethod
    def validate_generation(self, generation_settings: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize settings against engine capabilities and default parameters."""
        raise NotImplementedError

    @abstractmethod
    def submit_generation(
        self,
        generation_settings: dict[str, Any],
        on_progress: Callable[[EngineProgress], None],
    ) -> EngineJobHandle:
        """Submit a generation task for execution."""
        raise NotImplementedError

    @abstractmethod
    def wait_for_result(self, handle: EngineJobHandle) -> EngineResult:
        """Block or await until the generation completes and return the normalized result."""
        raise NotImplementedError

    @abstractmethod
    def cancel_generation(self, handle: EngineJobHandle) -> None:
        """Request cancellation of an active generation task."""
        raise NotImplementedError

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up GPU memory, unload models, or terminate worker connections."""
        raise NotImplementedError
