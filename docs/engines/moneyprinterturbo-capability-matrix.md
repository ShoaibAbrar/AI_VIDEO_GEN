# MoneyPrinterTurbo — Capability Matrix

## Engine ID: `moneyprinterturbo`
## Status: REAL_INTEGRATION / READY

---

## Core Capabilities

| Capability | Supported | Description / Implementation |
|---|---|---|
| Topic → Script (Mode A) | ✅ | `ScriptGenerator._generate_from_topic` with targeted visual search term extraction |
| User Script → Video (Mode B) | ✅ | `ScriptGenerator._parse_user_script` with punctuation boundary segmentation |
| Stock Footage Sourcing | ✅ | Automated retrieval via Pexels Videos API & Pixabay Videos API |
| Local Media Sourcing | ✅ | Scans local folders for matching MP4/JPG clips with keyword scoring |
| Offline Canvas Fallback | ✅ | Dynamic atmospheric gradient backdrops ensure 100% render reliability |
| Neural Voiceover (TTS) | ✅ | Microsoft Edge TTS neural voices with customizable speed/pitch |
| Subtitle Generation | ✅ | Millisecond-accurate `.srt` and `.ass` subtitle compilation |
| Subtitle Burn-In | ✅ | Hardcoded subtitle rendering via FFmpeg `subtitles` / `ass` filters |
| Background Music (BGM) | ✅ | Local music library discovery + ambient harmonic wave synthesis |
| Audio Mixing & Ducking | ✅ | FFmpeg `amix` filter ducking BGM under narration with smooth fade-out |
| Aspect Ratio Conversion | ✅ | Centered scale & crop for `9:16` (Shorts/TikTok), `16:9` (YouTube), `1:1` |
| Progress Reporting | ✅ | 10 discrete lifecycle phases reported across execution |
| Job Cancellation | ✅ | Non-blocking inter-stage cancellation signal checks |
| Checkpointing & Resumption | ✅ | Per-job `script.json`, `materials.json`, `state.json` persistence |
| GPU Required | ❌ | **CPU & Network only**; no NVIDIA CUDA hardware required |
| Windows 10/11 Support | ✅ | Fully native Windows execution path with path escaping |
| Linux / macOS Support | ✅ | Cross-platform compatible |

---

## Intent & Workload Routing Comparison

| Use Case | Recommended Engine | Reason |
|---|---|---|
| Explainer video / Educational shorts | **MoneyPrinterTurbo** | Stock footage + narration + burned-in captions + BGM |
| Social media quote / Motivational reel | **MoneyPrinterTurbo** | Automated topic-to-video workflow with rapid turnaround |
| High-concept cinematic shot (Spaceship, alien planet) | **Wan2GP / LTX-Video / LTX-2** | Generative neural diffusion video synthesis |
| Consistent character multi-shot narrative | **MiniMax H3 Director** | Multi-character reference cards and storyboard cuts |
| Extended unbroken generative scene | **MiniMax H3 LongVideos** | Sliding-window FL2VA visual continuity handoff |

---

## Output Specifications

| Metric | Value |
|---|---|
| Video Codec | H.264 (`libx264`, `yuv420p` pixel format) |
| Audio Codec | AAC (`libmp3lame` / `aac`, 192 kbps stereo) |
| Container | MP4 (`-movflags +faststart` for web streaming) |
| Aspect Ratios | `9:16` (1080x1920), `16:9` (1920x1080), `1:1` (1080x1080) |
| Target FPS | 30 fps (configurable) |
| Subtitle Formats | Embedded burn-in + standalone `.srt` file |
