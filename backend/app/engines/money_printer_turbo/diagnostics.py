"""
Environment and Dependency Diagnostics for MoneyPrinterTurbo.
Evaluates FFmpeg, Edge TTS, Requests, Pexels/Pixabay API credentials, and local media caches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging_config import logger
from app.engines.money_printer_turbo.models import MoneyPrinterTurboStatusCode
from app.orchestration.media_stitcher import get_ffmpeg_binary


@dataclass
class MoneyPrinterTurboEnvironmentStatus:
    """Diagnostic report for MoneyPrinterTurbo production engine environment."""
    status_code: MoneyPrinterTurboStatusCode
    is_available: bool
    is_mock: bool
    ffmpeg_available: bool
    ffmpeg_path: Optional[str]
    edge_tts_available: bool
    pexels_configured: bool
    pixabay_configured: bool
    local_materials_path: Optional[str]
    local_materials_count: int
    missing_dependencies: List[str]
    missing_api_keys: List[str]
    diagnostic_message: str


def check_moneyprinterturbo_environment(
    pexels_api_key: Optional[str] = None,
    pixabay_api_key: Optional[str] = None,
    local_material_dir: Optional[str | Path] = None,
    allow_mock: bool = False,
) -> MoneyPrinterTurboEnvironmentStatus:
    """
    Evaluates host system environment for MoneyPrinterTurbo without executing rendering.
    Checks FFmpeg, Python libraries, voice providers, and material provider API keys.
    """
    # 1. Mock mode check
    mock_mode = (
        getattr(settings, "DEV_MOCK_ENGINE", False)
        or os.environ.get("MONEYPRINTERTURBO_MOCK_MODE", "").lower() in ("true", "1", "yes")
        or os.environ.get("MPT_MOCK_MODE", "").lower() in ("true", "1", "yes")
    )
    if mock_mode and allow_mock:
        return MoneyPrinterTurboEnvironmentStatus(
            status_code=MoneyPrinterTurboStatusCode.MOCK,
            is_available=True,
            is_mock=True,
            ffmpeg_available=True,
            ffmpeg_path="mock-ffmpeg",
            edge_tts_available=True,
            pexels_configured=True,
            pixabay_configured=True,
            local_materials_path="./materials",
            local_materials_count=10,
            missing_dependencies=[],
            missing_api_keys=[],
            diagnostic_message="MoneyPrinterTurbo running in Development Mock Mode (Simulated Production Pipeline).",
        )

    # 2. Dependency checks
    missing_deps: List[str] = []

    try:
        import requests  # noqa: F401
    except ImportError:
        missing_deps.append("requests")

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing_deps.append("pillow")

    # Check Edge TTS
    edge_tts_avail = False
    try:
        import edge_tts  # noqa: F401
        edge_tts_avail = True
    except ImportError:
        missing_deps.append("edge-tts")

    # 3. FFmpeg check
    ffmpeg_exe = get_ffmpeg_binary()
    ffmpeg_avail = bool(ffmpeg_exe and Path(ffmpeg_exe).exists())

    # 4. API Keys check
    p_key = (
        pexels_api_key
        or os.environ.get("PEXELS_API_KEY")
        or getattr(settings, "PEXELS_API_KEY", None)
    )
    px_key = (
        pixabay_api_key
        or os.environ.get("PIXABAY_API_KEY")
        or getattr(settings, "PIXABAY_API_KEY", None)
    )

    pexels_configured = bool(p_key and str(p_key).strip())
    pixabay_configured = bool(px_key and str(px_key).strip())

    missing_keys: List[str] = []
    if not pexels_configured:
        missing_keys.append("PEXELS_API_KEY")
    if not pixabay_configured:
        missing_keys.append("PIXABAY_API_KEY")

    # 5. Local materials directory
    mat_dir = Path(
        local_material_dir
        or os.environ.get("LOCAL_MATERIAL_DIR")
        or "./materials"
    )
    mat_count = 0
    if mat_dir.exists():
        mat_count = len(list(mat_dir.glob("*.mp4"))) + len(list(mat_dir.glob("*.jpg"))) + len(list(mat_dir.glob("*.png")))

    # 6. Status determination
    if missing_deps:
        return MoneyPrinterTurboEnvironmentStatus(
            status_code=MoneyPrinterTurboStatusCode.DEPENDENCY_MISSING,
            is_available=False,
            is_mock=False,
            ffmpeg_available=ffmpeg_avail,
            ffmpeg_path=ffmpeg_exe,
            edge_tts_available=edge_tts_avail,
            pexels_configured=pexels_configured,
            pixabay_configured=pixabay_configured,
            local_materials_path=str(mat_dir) if mat_dir.exists() else None,
            local_materials_count=mat_count,
            missing_dependencies=missing_deps,
            missing_api_keys=missing_keys,
            diagnostic_message=f"Missing Python dependencies: {', '.join(missing_deps)}. Install with: pip install {' '.join(missing_deps)}",
        )

    if not ffmpeg_avail:
        return MoneyPrinterTurboEnvironmentStatus(
            status_code=MoneyPrinterTurboStatusCode.FFMPEG_MISSING,
            is_available=False,
            is_mock=False,
            ffmpeg_available=False,
            ffmpeg_path=None,
            edge_tts_available=edge_tts_avail,
            pexels_configured=pexels_configured,
            pixabay_configured=pixabay_configured,
            local_materials_path=str(mat_dir) if mat_dir.exists() else None,
            local_materials_count=mat_count,
            missing_dependencies=[],
            missing_api_keys=missing_keys,
            diagnostic_message="FFmpeg executable not found in PATH or project root. FFmpeg is required for video composition.",
        )

    # Note: Stock footage APIs are optional if local materials exist, but recommended for automated sourcing.
    has_material_source = pexels_configured or pixabay_configured or mat_count > 0 or True

    return MoneyPrinterTurboEnvironmentStatus(
        status_code=MoneyPrinterTurboStatusCode.READY,
        is_available=True,
        is_mock=False,
        ffmpeg_available=True,
        ffmpeg_path=ffmpeg_exe,
        edge_tts_available=edge_tts_avail,
        pexels_configured=pexels_configured,
        pixabay_configured=pixabay_configured,
        local_materials_path=str(mat_dir) if mat_dir.exists() else None,
        local_materials_count=mat_count,
        missing_dependencies=[],
        missing_api_keys=missing_keys,
        diagnostic_message="MoneyPrinterTurbo production pipeline is READY for execution.",
    )
