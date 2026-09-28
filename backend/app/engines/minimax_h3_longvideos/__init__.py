"""
MiniMax H3 LongVideos Engine Package.

Provides sliding-window multi-chunk long video generation using MiniMax H3 Omni-AV
with beat parsing, latent-boundary handoff, and synchronized audio crossfade.

Upstream reference: Smite79/MiniMax-H3-Longvideos (ComfyUI custom-node on HuggingFace).
Architecture: Our implementation is a clean, standalone Python package that adapts the
sliding-window chunk orchestration pattern independently from the ComfyUI node wiring.
"""

from app.engines.minimax_h3_longvideos.models import (
    H3LongVideoGenerationRequest,
    H3LongVideoGenerationResult,
    H3LongVideoStatusCode,
    LongVideoCharacterCard,
    LongVideoBeat,
    LongVideoChunk,
    LongVideoTimelinePlan,
)
from app.engines.minimax_h3_longvideos.diagnostics import (
    H3LongVideoEnvironmentStatus,
    check_h3_longvideo_environment,
)
from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner

__all__ = [
    "H3LongVideoGenerationRequest",
    "H3LongVideoGenerationResult",
    "H3LongVideoStatusCode",
    "LongVideoCharacterCard",
    "LongVideoBeat",
    "LongVideoChunk",
    "LongVideoTimelinePlan",
    "H3LongVideoEnvironmentStatus",
    "check_h3_longvideo_environment",
    "H3LongVideoPlanner",
    "H3LongVideoContinuityCoordinator",
    "MiniMaxH3LongVideoRunner",
]
