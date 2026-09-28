# MiniMax H3 LongVideos — Capability Matrix

## Engine ID: `minimax-h3-longvideo`
## Status: REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED

---

## Core Capabilities

| Capability | Supported | Notes |
|---|---|---|
| Text-to-Video | ✅ | Via H3 T2VA pipeline per chunk |
| Image-to-Video | ✅ | Via FL2VA first-frame conditioning |
| Video Continuation | ✅ | FL2VA inter-chunk visual handoff |
| Native Long Video | ✅ | Sliding-window unlimited duration |
| Audio Generation | ✅ | Native 32kHz stereo per chunk |
| Audio Crossfade | ✅ | Linear crossfade between segments |
| Voice Conditioning | ✅ | Reference audio per character card |
| Reference Image | ✅ | Per-chunk image_start conditioning |
| Reference Video | ✅ | Via H3 REF2VA task type |
| Reference Audio | ✅ | Per-character audio reference |
| Multiple Characters | ✅ | Character card binding per beat |
| Custom Resolutions | ✅ | WxH via `resolution` field |
| Configurable FPS | ✅ | Default: 25fps |
| Configurable Steps | ✅ | Default: 35 |
| Configurable Seed | ✅ | Per-chunk seed offset |
| Progress Reporting | ✅ | Per-chunk + overall percentage |
| Cancellation | ✅ | Inter-chunk cancellation check |
| Plan-Only Mode | ✅ | Dry-run chunk schedule without inference |
| Resume on Failure | ✅ | Per-chunk state.json checkpoint |
| Beat Parsing | ✅ | Dialogue-aware duration estimation |
| Audio Concat | ✅ | soundfile/numpy or raw WAV fallback |

---

## Limitations

| Limitation | Details |
|---|---|
| Per-chunk max duration | ~14s (H3 native ceiling, ~350 frames at 25fps) |
| VRAM per chunk | 24 GB minimum (48 GB recommended) |
| Sequential only | Chunks are generated sequentially, not parallel |
| Latent-level stitching | Frame-boundary handoff only; no diffusion-space latent blending |
| Audio crossfade | Requires soundfile+numpy; falls back to raw WAV concat |

---

## Performance Estimates (approximate)

| Duration | Chunks | GPU | Est. Time |
|---|---|---|---|
| 15s (3×5s) | 3 | A100 80 GB | ~6–10 min |
| 30s (6×5s) | 6 | A100 80 GB | ~12–20 min |
| 60s (12×5s) | 12 | A100 80 GB | ~24–40 min |
| 120s (24×5s) | 24 | H100 SXM | ~40–70 min |

> Estimates assume 35 diffusion steps at 1024×576. Actual times vary with step count, resolution, and GPU model.

---

## VRAM Profiles

| Resolution | Frames | VRAM (peak) |
|---|---|---|
| 1024×576 | 125 (5s) | ~24 GB |
| 1280×720 | 125 (5s) | ~32 GB |
| 1920×1080 | 125 (5s) | ~48 GB |

---

## Supported Task Types (per chunk)

| Task Type | Trigger Condition |
|---|---|
| T2VA | First chunk with no conditioning image |
| FL2VA | Chunks 2+ with previous frame path |
| REF2VA | When reference_image_path is provided |

---

## Audio Spec

| Property | Value |
|---|---|
| Sample Rate | 32,000 Hz (native MiniMax H3) |
| Channels | Stereo (2-channel) |
| Format | WAV (per-chunk) → crossfaded WAV → muxed MP4 |
| Crossfade Duration | Configurable (default: 0.2s) |

---

## Port Assignment

| Engine | Port |
|---|---|
| LTX-Video | 8005 |
| LTX-2 | 8006 |
| MiniMax H3 | 8007 |
| MiniMax H3 Director | 8008 |
| **MiniMax H3 LongVideos** | **8009** |
