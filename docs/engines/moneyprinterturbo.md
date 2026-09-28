# MoneyPrinterTurbo — Engine Integration Guide

## Status: REAL_INTEGRATION / READY

---

## 1. Upstream Reference

| Field | Value |
|---|---|
| Repository | [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) |
| Release / Tag | `v1.2.5` |
| Commit SHA | `c18e38ffc008cf510b66b72a08f5d023f79391ab` |
| License | MIT License (Permissive, Commercial use permitted) |
| Date Inspected | 2026-09-28 |

---

## 2. What This Engine Does

MoneyPrinterTurbo is a **production video synthesis engine** designed for automated content creation (explainer videos, social media reels, educational shorts, and faceless channels).

Unlike diffusion video generators (such as Wan2GP, LTX-Video, LTX-2, or MiniMax H3) which synthesize visual frames from latent noise, MoneyPrinterTurbo automates the complete multi-stage production editing pipeline:

```
User Input (Topic or Custom Script)
      ↓
[ScriptGenerator]
  ├── Mode A: Topic → Segmented narration + Visual search terms
  └── Mode B: User Script → Sentence boundaries + Keyword extraction
      ↓
[EdgeTTSVoiceEngine]
  └── High-fidelity neural voiceover narration per segment
      ↓
[SubtitleManager]
  └── Millisecond-timed SRT & ASS subtitle formatting + visual styling
      ↓
[CompositeMaterialProvider]
  ├── Pexels Videos API (Stock footage search & download)
  ├── Pixabay Videos API (Stock footage search & download)
  ├── Local Media Library (Local clips/images)
  └── Dynamic Atmospheric Canvas (Offline fallback)
      ↓
[Video Sizing & Cropping]
  └── Aspect ratio normalization (9:16 vertical, 16:9 landscape, 1:1 square)
      ↓
[MusicManager]
  └── Background music discovery, duration looping, volume ducking & mixing
      ↓
[FFmpeg Final Muxing]
  └── Video stitch + mixed audio + subtitle burn-in → Final High-Definition MP4
```

---

## 3. Package Structure

```
backend/app/engines/money_printer_turbo/
├── __init__.py           # Package exports
├── models.py             # Schemas for topics, scripts, materials, subtitles, audio mix, results
├── diagnostics.py        # FFmpeg, Edge TTS, Requests, API credentials probing
├── providers.py          # ScriptGenerator (Mode A/B) + Material providers (Pexels, Pixabay, Local)
├── subtitles.py          # SRT & ASS subtitle generation, timing, and FFmpeg filter formatting
├── music.py              # Background music discovery, ambient audio synthesis, audio mix filter
└── runner.py             # MoneyPrinterTurboRunner production pipeline coordinator

backend/app/engines/money_printer_turbo_adapter.py
  ├── MoneyPrinterTurboService  # Service lifecycle & background job management
  └── MoneyPrinterTurboAdapter  # BaseVideoEngine contract implementation

scripts/
└── test-real-moneyprinterturbo.py  # Standalone CLI validation test script

backend/tests/
└── test_moneyprinterturbo_comprehensive.py  # 24 unit & integration tests
```

---

## 4. Hardware & Environment Requirements

| Requirement | Specification |
|---|---|
| OS | Windows 10/11, Linux (Ubuntu 20.04+), macOS |
| Python | 3.10+ (Tested on Python 3.13) |
| GPU | **Not required** (CPU / Network / FFmpeg based pipeline) |
| FFmpeg | Required in system PATH or project root (`ffmpeg.exe` / `ffmpeg`) |
| Edge TTS | Required (`edge-tts` python package) |
| Stock APIs | Optional (Pexels / Pixabay API keys improve automated stock coverage) |

---

## 5. API Keys Configuration

To enable automated stock footage sourcing from Pexels or Pixabay, set the following environment variables in `.env`:

```env
# Pexels Video Search API (Free API key from https://www.pexels.com/api/)
PEXELS_API_KEY=your_pexels_api_key_here

# Pixabay Video Search API (Free API key from https://pixabay.com/api/docs/)
PIXABAY_API_KEY=your_pixabay_api_key_here

# Local footage directory (optional)
LOCAL_MATERIAL_DIR=./materials

# Local music library (optional)
MONEYPRINTERTURBO_MUSIC_DIR=./materials/music
```

*Note: If no API keys are provided, the pipeline gracefully falls back to local clips or generated atmospheric backdrops.*

---

## 6. Execution Modes

### Mode A — Topic to Video
```python
request = MoneyPrinterTurboRequest(
    topic="The Science of Deep Focus and Productivity",
    target_duration_seconds=30.0,
    aspect_ratio="9:16",
    voice_name="en-US-ChristopherNeural",
    music_enabled=True,
    subtitle_enabled=True,
)
result = runner.execute_production_video(request)
```

### Mode B — User Script to Video
```python
request = MoneyPrinterTurboRequest(
    script=(
        "The James Webb Space Telescope opened our eyes to the early cosmos. "
        "It captures infrared light from billions of light years away. "
        "Astronomers can now analyze planetary atmospheres like never before."
    ),
    aspect_ratio="16:9",
    voice_name="en-US-JennyNeural",
    music_enabled=True,
    subtitle_enabled=True,
)
result = runner.execute_production_video(request)
```

---

## 7. Real Test CLI Execution

```bash
# Full real production test with automated topic
python scripts/test-real-moneyprinterturbo.py --topic "Artificial Intelligence in Healthcare" --duration 15

# Custom script with 16:9 landscape aspect ratio
python scripts/test-real-moneyprinterturbo.py --script "First line. Second line." --aspect-ratio 16:9

# Plan-only mode
python scripts/test-real-moneyprinterturbo.py --plan-only
```
