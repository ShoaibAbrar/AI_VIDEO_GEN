# Voice Cloning & Custom Voice — Engine Documentation

## Overview

**Engine ID:** `voice-cloning`  
**Status:** `REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED`  
**Upstream:** [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox)  
**Package:** `chatterbox-tts==0.1.1`  
**License:** MIT (code AND model weights)

The Voice Cloning engine provides zero-shot custom voice generation within the GenVid.AI platform. A user supplies a short reference audio clip (~5–10 seconds) and the engine generates new speech in that voice — no fine-tuning required.

---

## Architecture

```
User Reference Audio (WAV, 2–60s)
         │
         ▼
 validate_reference_audio()
 ─────────────────────────
 • Consent enforcement
 • Format check (WAV/FLAC/MP3/OGG)
 • Duration bounds: 2s–60s
 • Energy / silence check
 • Clipping detection
         │
         ▼
 VoiceProfileStore.create_profile()
 ──────────────────────────────────
 • Unique UUID profile ID
 • Persists to ./storage/voice_profiles/<id>/
 • Saves reference audio copy
 • Optional speaker embedding (GPU)
         │
         ▼
 ChatterboxVoiceCloningRunner.execute_cloning()
 ──────────────────────────────────────────────
 • Extracts speaker embedding
 • Applies paralinguistic tags ([laugh], [sigh], ...)
 • Generates cloned speech waveform
 • Writes output WAV at 24 kHz, 16-bit, mono
         │
         ▼
 VoiceCloningResult
 • success: bool
 • audio_path: str
 • duration_seconds: float
```

---

## Models

| Model Variant | Size | Languages | Features | VRAM |
|---|---|---|---|---|
| Chatterbox-Multilingual *(selected)* | 500M | 23+ incl. Hindi | Zero-shot cloning, multi-lingual | ~6 GB |
| Chatterbox-Turbo | 350M | English | Paralinguistic tags, low latency | ~4 GB |
| Chatterbox (Original) | 500M | English | CFG + exaggeration control | ~6 GB |

**Selected model for GenVid.AI:** Chatterbox-Multilingual (`resemble-ai/chatterbox-multilingual`)  
**Rationale:** Only fully MIT-licensed multilingual voice cloning model with Hindi/Hinglish support.

---

## Supported Languages

Arabic (ar) • Danish (da) • German (de) • Greek (el) • **English (en)** • Spanish (es) • Finnish (fi) • French (fr) • Hebrew (he) • **Hindi (hi)** • Italian (it) • Japanese (ja) • Korean (ko) • Malay (ms) • Dutch (nl) • Norwegian (no) • Polish (pl) • Portuguese (pt) • Russian (ru) • Swedish (sv) • Swahili (sw) • Turkish (tr) • Chinese (zh)

---

## Paralinguistic Tags

The Chatterbox-Turbo variant natively supports these expressive tags in the text:

| Tag | Description |
|---|---|
| `[laugh]` | Natural laughter |
| `[chuckle]` | Quiet laughter |
| `[sigh]` | Audible sigh |
| `[cough]` | Cough sound |
| `[gasp]` | Surprised gasp |
| `[whisper]` | Whispered delivery |

---

## File Structure

```
backend/app/services/voice/cloning/
├── __init__.py          — Package exports
├── models.py            — VoiceProfile, VoiceCloningRequest, VoiceCloningResult, status codes
├── validation.py        — validate_reference_audio() with consent enforcement
├── storage.py           — VoiceProfileStore (CRUD, speaker embedding persistence)
├── diagnostics.py       — check_voice_cloning_environment() → VoiceCloningEnvironmentStatus
├── runner.py            — ChatterboxVoiceCloningRunner (model inference stub + GPU path)
└── engine.py            — VoiceCloningEngine(BaseVoiceEngine) — platform integration

backend/app/workers/
├── voice_cloning_worker.py            — VoiceCloningGPUWorker(BaseGPUWorker)
└── standalone_voice_cloning_server.py — FastAPI server on port 8010

scripts/
├── start-voice-cloning-worker.ps1  — Windows GPU worker launcher
├── start-voice-cloning-worker.sh   — Linux/RunPod GPU worker launcher
├── test-real-voice-cloning.py      — End-to-end CLI validation
└── create_test_voice.py            — Generates test reference audio

materials/
└── test_reference_voice.wav        — Pre-generated 5s, 24kHz test reference
```

---

## API Endpoints (Standalone Server — Port 8010)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/capabilities` | Model capabilities JSON |
| GET | `/diagnostics` | Environment status (CUDA, VRAM, model) |
| POST | `/validate` | Validate reference audio before cloning |
| POST | `/voices` | Create a new voice profile |
| GET | `/voices` | List all voice profiles |
| GET | `/voices/{id}` | Get specific voice profile |
| DELETE | `/voices/{id}` | Delete voice profile |
| POST | `/generate` | Generate cloned speech (async job) |
| GET | `/jobs/{id}` | Poll job status |
| POST | `/cancel/{id}` | Cancel in-flight job |
| GET | `/output/{id}` | Download generated audio |

---

## GPU Requirements

| Component | Minimum | Recommended |
|---|---|---|
| VRAM | 6 GB | 12+ GB |
| CUDA | 11.8+ | 12.x |
| RAM | 16 GB | 32 GB |
| Storage | 10 GB (model weights) | 20 GB |

> [!NOTE]
> On CPU-only machines the engine operates in **plan-only mode**: all API calls return structured responses describing what would happen on GPU. No synthesis is performed. This matches the pattern used by LTX-2 and MiniMax H3.

---

## Installation (GPU Machine)

```bash
# Python 3.11 recommended
pip install chatterbox-tts==0.1.1

# Or from source (master branch)
git clone https://github.com/resemble-ai/chatterbox.git
cd chatterbox
pip install -e .
```

---

## Voice Profile Persistence

Voice profiles are stored in `./storage/voice_profiles/<profile_id>/`:

```
storage/voice_profiles/
└── <uuid>/
    ├── profile.json          — VoiceProfile metadata
    ├── reference_audio.wav   — Validated reference copy
    └── speaker_embedding.npy — (GPU only) Extracted embedding
```

Profiles persist across restarts. They can be shared across H3 Director character cards, H3 LongVideos chunks, and MoneyPrinterTurbo pipeline runs via `voice_profile_id`.

---

## Integration with Other Engines

### H3 Director
`DirectorCharacterCard.voice_profile_id: Optional[str]` — assign a voice profile to a director character for persistent cloning across all shots.

### H3 LongVideos
The `LongVideoCharacterCard` supports the same `voice_profile_id` mechanism through the `VoiceEngineRegistry`.

### MoneyPrinterTurbo
`MoneyPrinterTurboRunner(voice_engine=...)` accepts any `BaseVoiceEngine` subclass. The registry can dispatch to `VoiceCloningEngine` when a voice profile is present.

---

## Watermarking

Every audio output includes **PerTh (Perceptual Threshold) Watermarking** by Resemble AI:
- Imperceptible neural watermark embedded in each generated clip
- Survives MP3 compression, audio editing, and common manipulations
- ~100% detection accuracy
- Detectable via `perth.PerthImplicitWatermarker`

> [!IMPORTANT]
> Do NOT remove or attempt to suppress the PerTh watermark. It is a responsible AI safeguard and required by the MIT license's responsible use expectations.
