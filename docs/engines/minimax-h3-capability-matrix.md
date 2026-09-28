# MiniMax H3 Capability Matrix

## 1. Engine Capability Classification

The matrix below documents what the core **MiniMax H3** (Omni-AV) foundation model actually provides versus platform services.

| Capability | Supported | Task / Mechanism | Notes |
| :--- | :---: | :--- | :--- |
| **Text → Video** | **YES** | `T2VA` | Generates 1024x576 / 1280x720 video from text prompts. |
| **Image → Video** | **YES** | `FL2VA` | Uses first-frame (`image_start`) as initial state anchor. |
| **Audio → Video** | **YES** | `REF2VA` | Synthesizes video conditioned on input audio rhythm/timbre. |
| **Video → Video** | **YES** | `REF2VA` | Video reference conditioning for motion and style transfer. |
| **First-Frame Conditioning** | **YES** | `FL2VA` (`image_start`) | Anchors initial frame for Level 2 visual continuity. |
| **Last-Frame Conditioning** | **YES** | `FL2VA` (`image_end`) | Anchors final frame for guided transition synthesis. |
| **Keyframes** | **PARTIAL** | Start + End frames | Supports opening and closing endpoints, not arbitrary intermediate keyframe meshes. |
| **Video Continuation** | **PARTIAL** | `FL2VA` chained | Can start from previous scene's final frame; true latent continuation requires LongVideos. |
| **Native Audio** | **YES** | Joint Omni-AV DiT | Generates synchronized 32kHz stereo ambient audio, foley, and soundtrack. |
| **Character Dialogue TTS** | **NO** | Edge TTS / Platform | Handled by platform dialogue service; H3 is not an arbitrary text-to-speech engine. |
| **Voice Cloning** | **PARTIAL** | `REF2VA` reference audio | Guides timbre and environmental acoustics; not a zero-shot phonetic voice cloner. |
| **Spatial / Temporal Upscaling** | **NO** | Native DiT Generation | Generates target resolutions directly without a cascaded upscaler. |
| **Long-Video (30+ min)** | **NO** | Core H3 is clip-based | Supports clips up to 15 seconds; multi-scene orchestration is handled by GenVid.AI. (MiniMax-H3-LongVideos is a separate future integration). |
| **Text Generation / Scriptwriting** | **NO** | N/A | MiniMax H3 is a generative diffusion transformer, not an autoregressive text LLM. |
| **Reasoning Tokens** | **NO** | N/A | Does not produce text reasoning chains. |

---

## 2. Multi-Engine Capability Comparison

| Dimension | Wan2GP | LTX-Video | LTX-2 | MiniMax H3 |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Focus** | Efficient 14B Video | Fast DiT Video | 19B Dual-Stream AV | 33B/20B Omni-Modal AV |
| **Native Audio** | NO | NO | YES (44.1kHz) | YES (32kHz Stereo) |
| **First-Frame Conditioning** | YES (`image_start`) | YES (`image_cond`) | YES (`images` tuple) | YES (`FL2VA`) |
| **Last-Frame Conditioning** | NO | NO | NO | YES (`image_end`) |
| **Multi-Reference Conditioning** | NO | NO | NO | YES (Up to 9 images / audios) |
| **Minimum VRAM** | 8.0 GB - 12.0 GB | 12.0 GB | 24.0 GB | 24.0 GB (Quantized) |
| **Recommended VRAM** | 16.0 GB | 16.0 GB - 24.0 GB | 32.0 GB - 48.0 GB | 48.0 GB+ |
| **Maximum Native Clip Length** | 5.0s (81 frames) | 5.0s (121 frames) | 5.0s (125 frames) | 15.0s (375 frames) |
