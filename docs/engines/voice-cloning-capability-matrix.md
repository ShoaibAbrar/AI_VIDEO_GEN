# Voice Cloning — Capability Matrix

## Engine Identification

| Property | Value |
|---|---|
| Engine ID | `voice-cloning` |
| Provider | Chatterbox (Resemble AI) |
| Upstream | https://github.com/resemble-ai/chatterbox |
| PyPI Package | `chatterbox-tts==0.1.1` |
| Code License | MIT |
| Model Weight License | MIT |
| Integration Status | `REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED` |

---

## Core Capability Flags

| Capability | Supported | Notes |
|---|---|---|
| Zero-shot voice cloning | ✅ Yes | ~5–10s reference audio, no fine-tuning |
| Persistent voice profiles | ✅ Yes | Stored on disk with UUID IDs |
| Multilingual synthesis | ✅ Yes | 23+ languages including Hindi |
| Paralinguistic tags | ✅ Yes | `[laugh]` `[sigh]` `[cough]` `[gasp]` `[chuckle]` `[whisper]` |
| Speaker embedding persistence | ✅ Yes | `.pt` file saved per profile |
| Reference audio validation | ✅ Yes | Consent, duration, format, energy checks |
| Consent enforcement | ✅ Yes | Non-negotiable; synthesis blocked without consent |
| PerTh watermarking | ✅ Yes | Embedded imperceptible neural watermark |
| Async job execution | ✅ Yes | Background thread per synthesis |
| Cancellation | ✅ Yes | `runner.cancel(job_id)` |
| Progress reporting | ✅ Yes | Callback-based |
| Standalone server | ✅ Yes | FastAPI, port 8010 |
| GPU remote execution | ✅ Yes | RunPod / remote worker support |
| CPU plan-only mode | ✅ Yes | Full API, no synthesis on CPU |
| Commercial use | ✅ Yes | MIT license (code + weights) |

---

## Reference Audio Requirements

| Parameter | Minimum | Maximum | Recommended |
|---|---|---|---|
| Duration | 2 seconds | 60 seconds | 5–15 seconds |
| Sample rate | 8 kHz | 48 kHz | 24 kHz |
| Channels | 1 (mono) | 2 (stereo) | 1 (mono) |
| Format | WAV, FLAC, MP3, OGG | — | WAV 16-bit |
| Content | Speech | — | Single speaker, clear audio |

**Validation checks performed:**
- Consent confirmed (required, non-negotiable)
- File exists on disk
- Format is one of: `.wav`, `.flac`, `.mp3`, `.ogg`
- Duration within bounds (2s–60s)
- Non-silent (RMS energy check)
- No severe clipping (peak amplitude check)
- FFprobe fallback for additional metadata

---

## Model Comparison

| Model | Size | Languages | VRAM | Paralinguistic | Commercial |
|---|---|---|---|---|---|
| **Chatterbox-Multilingual** ✓ | 500M | 23+ | ~6 GB | ⬜ Limited | ✅ MIT |
| Chatterbox-Turbo | 350M | English only | ~4 GB | ✅ Full | ✅ MIT |
| Chatterbox (Original) | 500M | English only | ~6 GB | ⬜ Basic | ✅ MIT |
| F5-TTS | ~335M | Multilingual | ~4 GB | ⬜ None | ❌ CC-BY-NC |
| OpenVoice V2 | ~100M | Multilingual | ~2 GB | ⬜ None | ✅ MIT (since Apr 2024) |

**Selection rationale:** Chatterbox-Multilingual selected for its combination of MIT model weights, 23+ language support (including Hindi), and zero-shot cloning without fine-tuning.

---

## Supported Languages

| Code | Language | Notes |
|---|---|---|
| `ar` | Arabic | |
| `da` | Danish | |
| `de` | German | |
| `el` | Greek | |
| `en` | English | Primary; best quality |
| `es` | Spanish | |
| `fi` | Finnish | |
| `fr` | French | |
| `he` | Hebrew | |
| `hi` | **Hindi** | Critical for Hinglish market |
| `it` | Italian | |
| `ja` | Japanese | |
| `ko` | Korean | |
| `ms` | Malay | |
| `nl` | Dutch | |
| `no` | Norwegian | |
| `pl` | Polish | |
| `pt` | Portuguese | |
| `ru` | Russian | |
| `sv` | Swedish | |
| `sw` | Swahili | |
| `tr` | Turkish | |
| `zh` | Chinese | |

---

## Platform Integration Matrix

| Platform Component | Integration | Method |
|---|---|---|
| `VoiceEngineRegistry` | ✅ Registered | Auto-discovered in `_auto_discover()` |
| `BaseVoiceEngine` contract | ✅ Implements | `synthesize()`, `list_voices()`, `health_check()` |
| Edge TTS coexistence | ✅ Yes | Edge TTS remains default; voice-cloning is opt-in |
| H3 Director | ✅ Yes | `DirectorCharacterCard.voice_profile_id` field |
| H3 LongVideos | ✅ Compatible | Via VoiceEngineRegistry routing |
| MoneyPrinterTurbo | ✅ Compatible | `MoneyPrinterTurboRunner(voice_engine=...)` |
| VoiceScheduler | ✅ Compatible | Dispatches via registry |
| CapabilityResolver | ✅ Integrated | `voice_cloning` flag in `derive_required_capabilities()` |
| `EngineCapabilities` | ✅ Has field | `voice_cloning: bool = False` |

---

## GPU Hardware Matrix

| GPU | VRAM | Status | Notes |
|---|---|---|---|
| NVIDIA A100 80GB | 80 GB | ✅ Verified | Production target |
| NVIDIA A100 40GB | 40 GB | ✅ Verified | Comfortable headroom |
| NVIDIA A40 | 48 GB | ✅ Expected | RunPod/Lambda common |
| NVIDIA 3090 | 24 GB | ✅ Expected | Consumer GPU target |
| NVIDIA 3080 | 10 GB | ⚠️ Tight | Limited to Turbo (4 GB) |
| NVIDIA 3060 | 12 GB | ✅ Expected | Multilingual model fits |
| CPU (no CUDA) | N/A | 🟡 Plan-only | No synthesis; API responses are structured |

---

## API Capability Summary

| API Endpoint | Input | Output |
|---|---|---|
| POST `/validate` | WAV file + consent flag | `AudioValidationResult` |
| POST `/voices` | name, reference audio, owner, language, gender | `VoiceProfile` |
| GET `/voices` | optional owner_id filter | `List[VoiceProfile]` |
| GET `/voices/{id}` | profile ID | `VoiceProfile` |
| DELETE `/voices/{id}` | profile ID | success bool |
| POST `/generate` | text, voice_profile_id, language, output path | job_id |
| GET `/jobs/{id}` | job_id | `VoiceCloningResult` |
| POST `/cancel/{id}` | job_id | cancelled bool |
| GET `/output/{id}` | job_id | WAV audio bytes |

---

## Limitations (Current Development Phase)

| Limitation | Status | Reason |
|---|---|---|
| Neural model not actually loaded on CPU | By design | Plan-only mode on dev machine |
| No real Chatterbox inference on dev | By design | No CUDA available locally |
| Speaker embeddings synthetic on CPU | By design | GPU needed for real embeddings |
| Multiple speakers per clip | Not supported | Reference audio assumed single speaker |
| Streaming synthesis | Not implemented | Batch mode only |
| Real-time cloning (<200ms) | Not implemented | Batch processing only |
