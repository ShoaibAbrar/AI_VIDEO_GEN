# MiniMax H3 Director Capability Matrix

## 1. Engine Capability Breakdown

| Capability | Supported | Task / Mechanism | Notes |
| :--- | :---: | :--- | :--- |
| **Story & Script Planning** | **YES** | `plan_timeline()` | Decomposes high-level story into structured camera shots, prompt zones, and timing windows. |
| **Scene & Shot Planning** | **YES** | `DirectorShotCut` | Organizes narrative into sequential cuts with explicit camera motion styles. |
| **Character Definition & Cards** | **YES** | `DirectorCharacterCard` | Binds name, description, reference image, and reference audio to characters. |
| **Character Consistency** | **PARTIAL** | Reference card injection | Injects reference image & text into downstream `REF2VA`; maintains visual style and key subject markers. |
| **Environment Consistency** | **YES** | Level 2 Continuity | Hands off previous cut's final frame to anchor scene background and lighting. |
| **Camera Planning** | **YES** | Prompt zoning directives | Directs establishing, tracking, close-up, and panning camera movements per shot. |
| **First-Frame Continuity** | **YES** | `image_start` (`FL2VA`) | Carries over exact final frame of Cut $N$ to Cut $N+1$. |
| **Multi-Cut Video Generation** | **YES** | Downstream MiniMax H3 | Generates full video for each cut via downstream H3 diffusion passes. |
| **Native 32kHz Audio** | **YES** | Downstream MiniMax H3 | Generates synchronized ambient soundscapes and foley per cut. |
| **Multi-Character Dialogue TTS** | **YES** | Edge TTS Integration | Character cards map to persistent voices for dialogue tracks. |
| **Voice Cloning** | **PARTIAL** | `REF2VA` reference audio | Acoustic timbre guidance; zero-shot phonetic voice cloning remains an external module. |
| **Timeline Assembly & Stitching** | **YES** | `MediaStitcher` / FFmpeg | Concatenates cuts with audio ducking and video transition smoothing. |
| **Long-Video Generation** | **YES** | Multi-cut orchestration | Produces continuous long videos by assembling chained directed cuts. |
| **Automatic Cut Retries** | **YES** | Worker state machine | Retries failed cuts before stitching. |
