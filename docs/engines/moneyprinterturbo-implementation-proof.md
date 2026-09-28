# MoneyPrinterTurbo — Implementation Proof

## Status: REAL_INTEGRATION / READY

---

## 1. Upstream Pin & License Verification

| Field | Verified Value |
|---|---|
| Upstream Repository | `https://github.com/harry0703/MoneyPrinterTurbo` |
| Upstream Release/Tag | `v1.2.5` |
| Upstream Commit SHA | `c18e38ffc008cf510b66b72a08f5d023f79391ab` |
| License Type | MIT License |
| Commercial Use Permitted | Yes |
| Modification & Redistribution Permitted | Yes |
| Date Inspected | 2026-09-28 |

---

## 2. Architecture & Production Pipeline

The MoneyPrinterTurbo integration within GenVid.AI is implemented as a **real, native engine adapter and execution runner** that connects:

1. **`ScriptGenerator`** (`backend/app/engines/money_printer_turbo/providers.py`):
   - Implements Mode A (Topic → topical segment templates + keyword extraction).
   - Implements Mode B (User custom script parsing with sentence boundary splitting).
2. **`EdgeTTSVoiceEngine`** (`backend/app/services/voice/edge_tts_engine.py`):
   - Reuses existing platform neural TTS provider without duplication.
   - Synthesizes per-segment voiceover audio with duration measurement.
3. **`SubtitleManager`** (`backend/app/engines/money_printer_turbo/subtitles.py`):
   - Compiles millisecond-accurate SRT & ASS subtitles.
   - Implements Windows path-safe FFmpeg subtitle burn-in filters.
4. **`CompositeMaterialProvider`** (`backend/app/engines/money_printer_turbo/providers.py`):
   - Implements real Pexels Video Search API integration (`api.pexels.com/videos/search`).
   - Implements real Pixabay Video Search API integration (`pixabay.com/api/videos/`).
   - Implements local folder material retrieval with keyword relevance scoring.
   - Implements dynamic atmospheric backdrop canvas generation for 100% offline fallback.
5. **`MusicManager`** (`backend/app/engines/money_printer_turbo/music.py`):
   - Manages BGM discovery, ambient harmonic audio waveform generation, and FFmpeg `amix` ducking.
6. **`MoneyPrinterTurboRunner`** (`backend/app/engines/money_printer_turbo/runner.py`):
   - Coordinates video clip scaling, cropping (9:16, 16:9, 1:1), duration trimming, sequential concatenation, audio mixing, subtitle burn-in, and final MP4 muxing.
7. **`MoneyPrinterTurboAdapter`** (`backend/app/engines/money_printer_turbo_adapter.py`):
   - Implements full `BaseVideoEngine` contract.
   - Registers into `VideoEngineRegistry` under engine_id `moneyprinterturbo`.

---

## 3. Test Suite Verification

Test file: [`backend/tests/test_moneyprinterturbo_comprehensive.py`](../../backend/tests/test_moneyprinterturbo_comprehensive.py)

Contains 24 unit and integration tests covering:
- Data models & schemas
- Diagnostics probing (mock mode, missing dependencies, missing FFmpeg, API keys)
- Mode A topic script generation & Mode B user script parsing
- Pexels, Pixabay, Local, Canvas, and Composite material providers
- Subtitle generation (SRT, ASS, FFmpeg filter escaping)
- Music discovery, ambient audio synthesis, audio mixing
- Runner execution, plan-only mode, cancellation, checkpointing
- Service & Adapter contract compliance
- VideoEngineRegistry & Capability Resolver integration

---

## 4. Platform Engine Status Summary

| Engine | Primary Role | Status |
|---|---|---|
| Wan2GP | Open-source Diffusion Video Generation | REAL / GPU-VERIFIED |
| LTX-Video | Real-time Diffusion Video Generation | REAL_INTEGRATION / GPU-READY |
| LTX-2 | Next-gen Two-Stage Diffusion Video | REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED |
| MiniMax H3 | Omni-Modal Video & 32kHz Audio | REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED |
| MiniMax H3 Director | Directed Multi-Character Narrative Storyboard | REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED |
| MiniMax H3 LongVideos | Sliding-Window Multi-Chunk Extended Generation | REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED |
| **MoneyPrinterTurbo** | **Automated Stock Footage, Voiceover & Subtitle Production** | **REAL_INTEGRATION / READY** |
| Edge TTS | Multi-Character Neural Speech Synthesis | REAL_INTEGRATION |
