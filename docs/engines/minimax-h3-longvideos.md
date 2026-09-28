# MiniMax H3 LongVideos — Engine Integration Guide

## Status: REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED

---

## 1. Upstream Reference

| Field | Value |
|---|---|
| Canonical backbone | [MiniMax-AI/MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3) |
| Community long-video reference | [Smite79/MiniMax-H3-Longvideos](https://huggingface.co/Smite79/MiniMax-H3-Longvideos) (HuggingFace) |
| Implementation type | Clean standalone Python; does NOT copy ComfyUI node source |
| Architecture pattern | Sliding-window beat-to-chunk orchestration as documented by upstream |

> **Note:** Smite79/MiniMax-H3-Longvideos is a ComfyUI custom node pack hosted on HuggingFace. Our implementation adapts the sliding-window orchestration pattern (beat parsing, FL2VA frame handoff, audio crossfade) as a standalone Python backend, cleanly independent of the ComfyUI node wiring and subject to the upstream's specific licensing terms (as of September 2026).

---

## 2. What This Engine Does

MiniMax H3 natively generates up to ~15 seconds per pass (25fps × 375 frames). H3 LongVideos extends this by:

1. **Beat Parsing** — a multiline "scene + beats" prompt is split into discrete narrative beats (paragraphs). The first paragraph is the scene context; subsequent paragraphs are individual beats.
2. **Chunk Planning** — each beat is converted to a `LongVideoChunk` with estimated duration (dialogue-word-count / 2.5 WPS).
3. **Sliding-Window Generation** — each chunk is generated sequentially using the core H3 Omni-AV runner.
4. **FL2VA Visual Continuity** — the final frame of each completed chunk is extracted (FFmpeg/OpenCV) and passed as `image_start` conditioning to the next chunk.
5. **Audio Crossfade** — chunk audio segments are concatenated with configurable linear cross-fades using soundfile/numpy.
6. **Checkpoint Resumption** — per-chunk `state.json` allows resuming interrupted jobs.
7. **FFmpeg Stitching** — completed chunk videos are concatenated into a final MP4.

---

## 3. Architecture

```
H3LongVideoGenerationRequest
          │
          ▼
  H3LongVideoPlanner
    ├── parse_beats() → [LongVideoBeat, ...]
    └── beats_to_chunks() → [LongVideoChunk, ...]
          │
          ▼
MiniMaxH3LongVideoRunner.execute_long_video()
    For each chunk:
      ├── apply_conditioning (FL2VA, previous frame)
      ├── MiniMaxH3InferenceRunner.execute_generation()
      ├── extract_final_frame (FFmpeg → PIL)
      ├── save_chunk_state (checkpoint JSON)
    ├── crossfade_and_concat_audio (soundfile/numpy)
    └── stitch_video_chunks (FFmpeg concat demuxer)
          │
          ▼
  H3LongVideoGenerationResult
    ├── video_path (final stitched MP4)
    ├── audio_path (combined WAV)
    ├── chunks[] (per-chunk results)
    └── plan{} (JSON plan)
```

---

## 4. Package Structure

```
backend/app/engines/minimax_h3_longvideos/
├── __init__.py           # Package exports
├── models.py             # Data models (request/result/chunk/beat/character)
├── diagnostics.py        # CUDA/VRAM/dependency checks
├── planner.py            # Beat parser + chunk scheduler
├── continuity.py         # Frame extraction + audio crossfade
└── runner.py             # Main orchestration runner

backend/app/engines/minimax_h3_adapter.py
  └── MiniMaxH3LongVideoService   # Service layer
  └── MiniMaxH3LongVideoAdapter   # BaseVideoEngine adapter

backend/app/workers/
├── minimax_h3_longvideo_worker.py              # GPU worker (port 8009)
└── standalone_minimax_h3_longvideo_server.py   # FastAPI server

scripts/
├── start-minimax-h3-longvideo-worker.ps1   # Windows launcher
├── start-minimax-h3-longvideo-worker.sh    # Linux/WSL2/RunPod launcher
└── test-real-minimax-h3-longvideo.py       # Real GPU validation script

backend/tests/
└── test_minimax_h3_longvideos_comprehensive.py  # 56 tests
```

---

## 5. Environment Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| GPU | NVIDIA RTX 3090 (24 GB) | A100 80 GB / H100 |
| VRAM | 24 GB per chunk | 48 GB |
| CUDA | 12.x | 12.4+ |
| Python | 3.10+ | 3.12+ |
| PyTorch | 2.1+ | 2.3+ |
| Diffusers | 0.28+ | 0.30+ |

**Python dependencies:**
```bash
pip install torch diffusers transformers accelerate pillow soundfile numpy
```

---

## 6. Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `MINIMAX_H3_CHECKPOINTS_DIR` | `./models/minimax_h3` | Path to H3 model weights |
| `MINIMAX_H3_LONGVIDEO_OUTPUT_DIR` | `./output/minimax_h3_longvideos` | Output directory |
| `H3_LONGVIDEO_MOCK_MODE` | `false` | Enable dev mock mode |
| `H3_LONGVIDEO_HOST` | `0.0.0.0` | Worker bind host |
| `H3_LONGVIDEO_PORT` | `8009` | Worker port |

---

## 7. Beat Prompt Format

```
Scene: A neon-lit cyberpunk city at night, rain falling on steel streets.

A detective steps out of a taxi, scanning the alley with a flashlight.
"Someone was here," she mutters.

She crouches to examine a data chip on the ground.

The camera pulls back to reveal the towering corporate spire in the distance.
```

- **First paragraph** = scene/location context (applied to all chunks)
- **Subsequent paragraphs** = individual beats (one per chunk)
- **Quoted lines** = dialogue (triggers speech duration estimation)

---

## 8. Plan-Only Mode

To preview the chunk schedule without running inference:

```python
request = H3LongVideoGenerationRequest(
    prompt="...",
    beats_text="...",
    plan_only=True,
)
result = runner.execute_long_video(request)
# result.plan_only == True
# result.plan == {...chunk schedule...}
```

Or via HTTP:
```
GET /plan?prompt=...&total_duration_seconds=30
```

---

## 9. Standalone Worker

Start the worker on a GPU machine:

```bash
# Linux / WSL2 / RunPod
bash scripts/start-minimax-h3-longvideo-worker.sh

# Windows
.\scripts\start-minimax-h3-longvideo-worker.ps1
```

Endpoints:
- `GET  /health`      — Diagnostics + GPU status
- `GET  /diagnostics` — Full environment report
- `GET  /models`      — List supported models
- `GET  /plan`        — Dry-run chunk planning
- `POST /generate`    — Submit generation job
- `GET  /jobs/{id}`   — Query job result

---

## 10. GPU Validation

On a machine with a supported GPU:

```bash
# Quick plan validation (no GPU required)
python scripts/test-real-minimax-h3-longvideo.py --plan-only

# Full GPU inference (requires CUDA + model weights)
python scripts/test-real-minimax-h3-longvideo.py --duration 15 --steps 20
```

---

## 11. Current Status

| Dimension | Status |
|---|---|
| Engine implementation | REAL_INTEGRATION |
| GPU readiness | GPU-READY |
| Physical GPU inference | GPU-UNVERIFIED (no local CUDA device) |
| Test suite | 56 tests / 100% pass |
| DEV_MOCK_ENGINE | OFF (truthful diagnostics only) |
