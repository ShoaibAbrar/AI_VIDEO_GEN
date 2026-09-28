"""
MoneyPrinterTurbo Production Engine Package.
Provides automated short video generation from topics or user scripts with stock footage,
Edge TTS narration, stylized subtitles, background music, and FFmpeg video editing.
"""

from app.engines.money_printer_turbo.models import (
    MaterialInfo,
    MaterialSourceType,
    MoneyPrinterTurboRequest,
    MoneyPrinterTurboResult,
    MoneyPrinterTurboStatusCode,
    ProductionPhase,
    ProductionVideoPlan,
    ScriptSegment,
    SubtitleStyle,
)
from app.engines.money_printer_turbo.diagnostics import (
    MoneyPrinterTurboEnvironmentStatus,
    check_moneyprinterturbo_environment,
)
from app.engines.money_printer_turbo.providers import (
    BaseMaterialProvider,
    CompositeMaterialProvider,
    LocalMaterialProvider,
    PexelsMaterialProvider,
    PixabayMaterialProvider,
    ScriptGenerator,
)
from app.engines.money_printer_turbo.subtitles import SubtitleManager
from app.engines.money_printer_turbo.music import MusicManager
from app.engines.money_printer_turbo.runner import MoneyPrinterTurboRunner

__all__ = [
    "MaterialInfo",
    "MaterialSourceType",
    "MoneyPrinterTurboRequest",
    "MoneyPrinterTurboResult",
    "MoneyPrinterTurboStatusCode",
    "ProductionPhase",
    "ProductionVideoPlan",
    "ScriptSegment",
    "SubtitleStyle",
    "MoneyPrinterTurboEnvironmentStatus",
    "check_moneyprinterturbo_environment",
    "BaseMaterialProvider",
    "CompositeMaterialProvider",
    "LocalMaterialProvider",
    "PexelsMaterialProvider",
    "PixabayMaterialProvider",
    "ScriptGenerator",
    "SubtitleManager",
    "MusicManager",
    "MoneyPrinterTurboRunner",
]
