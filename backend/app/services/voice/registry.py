"""
Voice Engine Registry.
Manages discovery, instantiation, and routing for available Voice Engines.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from app.core.logging_config import logger
from app.services.voice.base import BaseVoiceEngine, VoiceProfile
from app.services.voice.edge_tts_engine import EdgeTTSVoiceEngine
from app.services.voice.mock_voice_engine import MockVoiceEngine


class VoiceEngineRegistry:
    """
    Central registry for Voice Engines.
    Provides auto-discovery, default engine selection, and fallback resolution.
    """

    def __init__(self):
        self._engines: Dict[str, BaseVoiceEngine] = {}
        self._default_engine_id: Optional[str] = None
        self._auto_discover()

    def _auto_discover(self) -> None:
        """Discovers and registers available voice engines."""
        dev_mock = os.environ.get("DEV_MOCK_ENGINE", "false").lower() == "true"
        force_mock_voice = os.environ.get("DEV_MOCK_VOICE", "false").lower() == "true"

        # 1. Edge-TTS Engine
        edge_engine = EdgeTTSVoiceEngine()
        if edge_engine.health_check():
            self.register(edge_engine, default=not (dev_mock and force_mock_voice))
            logger.info("Registered VoiceEngine: edge-tts (Microsoft Neural TTS)")

        # 2. Mock Engine (always available as fallback)
        mock_engine = MockVoiceEngine()
        self.register(mock_engine, default=self._default_engine_id is None or (dev_mock and force_mock_voice))
        logger.info("Registered VoiceEngine: mock (Dev Mock Voice)")

        # 3. Voice Cloning Engine (Chatterbox zero-shot; registered but NOT set as default)
        try:
            from app.services.voice.cloning.engine import VoiceCloningEngine  # noqa: PLC0415
            clone_engine = VoiceCloningEngine()
            self.register(clone_engine, default=False)
            logger.info("Registered VoiceEngine: voice-cloning (Chatterbox Zero-Shot)")
        except Exception as exc:  # pragma: no cover
            logger.warning("VoiceCloningEngine not registered: %s", exc)

    def register(self, engine: BaseVoiceEngine, default: bool = False) -> None:
        self._engines[engine.engine_id] = engine
        if default or self._default_engine_id is None:
            self._default_engine_id = engine.engine_id

    def get_engine(self, engine_id: Optional[str] = None) -> BaseVoiceEngine:
        if engine_id and engine_id in self._engines:
            return self._engines[engine_id]
        if self._default_engine_id and self._default_engine_id in self._engines:
            return self._engines[self._default_engine_id]
        if self._engines:
            return next(iter(self._engines.values()))
        raise RuntimeError("No Voice Engine registered in VoiceEngineRegistry.")

    def list_engines(self) -> List[Dict]:
        return [
            {
                "engine_id": eid,
                "default": eid == self._default_engine_id,
                "capabilities": eng.get_capabilities().__dict__,
            }
            for eid, eng in self._engines.items()
        ]


_global_voice_registry: Optional[VoiceEngineRegistry] = None


def get_voice_engine_registry() -> VoiceEngineRegistry:
    global _global_voice_registry
    if _global_voice_registry is None:
        _global_voice_registry = VoiceEngineRegistry()
    return _global_voice_registry
