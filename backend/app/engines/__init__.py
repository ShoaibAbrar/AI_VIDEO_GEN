"""
Video Engines Abstraction Package.
"""

from app.engines.base import (
    BaseVideoEngine,
    EngineCapabilities,
    EngineJobHandle,
    EngineProgress,
    EngineResult,
)
from app.engines.ltx2_adapter import LTX2Adapter
from app.engines.ltx_video_adapter import LTXVideoAdapter
from app.engines.minimax_h3_adapter import (
    MiniMaxH3DirectorAdapter,
    MiniMaxH3DirectorService,
    MiniMaxH3LongVideoAdapter,
    PromptZone,
    SlidingWindowChunk,
)
from app.engines.registry import VideoEngineRegistry, get_engine_registry
from app.engines.wan2gp_adapter import Wan2GPAdapter

__all__ = [
    "BaseVideoEngine",
    "EngineCapabilities",
    "EngineProgress",
    "EngineJobHandle",
    "EngineResult",
    "VideoEngineRegistry",
    "get_engine_registry",
    "Wan2GPAdapter",
    "LTXVideoAdapter",
    "LTX2Adapter",
    "MiniMaxH3LongVideoAdapter",
    "MiniMaxH3DirectorAdapter",
]
