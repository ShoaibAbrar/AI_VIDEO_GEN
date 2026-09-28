# LTX-2 Capability Matrix

## Audit Scope

The matrix below describes what the **current platform runner wiring** passes to its bundled `TI2VidOneStagePipeline` adaptation. It does not assert upstream v0.9.1 behavior: the requested official SHA and `v0.9.1` tag are not resolvable, and the bundled `models/ltx2` implementation is not a checkout at that revision. `YES` means the current runner has an explicit interface/path for the capability, not that GPU output has been verified.

No production pipeline is approved. The runner currently names `TI2VidOneStagePipeline`; that is not accepted as the production default by this audit. Current official Lightricks guidance found during review identifies one-stage as educational/prototyping and recommends DFR for production quality, but that later guidance cannot be projected onto the missing requested revision. Production selection is therefore **BLOCKED**, not DFR by assumption.

## Current Runner Matrix

| Capability | Pipeline wired by platform | Supported | Notes |
|---|---|---:|---|
| Text → Video | Local `TI2VidOneStagePipeline` adaptation | YES | Prompt is passed to the pipeline call. Upstream revision and actual CUDA inference are unverified. |
| Image → Video | Local `TI2VidOneStagePipeline` adaptation | PARTIAL | One image path is converted to a frame-zero image condition; checkpoint/conditioning compatibility is unverified. |
| Audio → Video | None | NO | No audio reference path is accepted by `LTX2GenerationRequest` or passed to the runner call. |
| Video → Video | None | NO | No source video conditioning is passed. |
| First-frame conditioning | Local `TI2VidOneStagePipeline` adaptation | PARTIAL | `image_start` is passed as one image at index 0; this alone does not establish temporal continuation. |
| Keyframes | None | NO | The platform request supports only one `image_start`, not positioned keyframes. |
| Video continuation | None | NO | No source-video latent/conditioning interface is passed. |
| Native audio | Local one-stage call output | PARTIAL | The runner consumes a returned audio object and attempts muxing; it does not prove the selected official pipeline/checkpoint provides native audio. |
| Character TTS | Separate platform service | PARTIAL | Edge TTS is a separate dialogue system; not an LTX-2 capability. |
| Voice cloning | None in the LTX-2 runner | NO | No verified LTX-2 reference-voice workflow is wired here. Keep any future voice-cloning system separate from native audio and TTS. |
| Upscaling | None | NO | Current runner invokes a one-stage pipeline and passes no spatial upscaler. |
| Long-video continuation | None verified | NO | No supported continuation conditioning is connected end-to-end. Do not infer this from generic scene stitching. |

## Candidate Pipeline Audit

This candidate list is for the requested audit. Since the target revision is unavailable, the rows do not claim a pipeline's v0.9.1 constructor, weight contract, audio behavior, memory profile, or conditioning support.

| Candidate | Intended role from official pipeline names/docs reviewed | Platform-wired at present | v0.9.1 verified |
|---|---|---:|---:|
| `TI2VidOneStagePipeline` | Single-stage text/image generation; prototyping | YES | NO |
| `TI2VidTwoStagesPipeline` | Guided two-stage text/image generation and upsampling | NO | NO |
| `TI2VidTwoStagesHQPipeline` | Guided two-stage HQ sampler | NO | NO |
| `DFRPipeline` | Later official docs describe production-quality text/image generation | NO | NO |
| `DistilledPipeline` | Fast distilled two-stage generation | NO | NO |
| `ICLoraPipeline` | IC-LoRA image/video transformation | NO | NO |
| `A2VidPipelineTwoStage` | Audio-conditioned video generation | NO | NO |
| `KeyframeInterpolationPipeline` | Keyframe image interpolation | NO | NO |
| `RetakePipeline` | Regeneration/editing of a region in existing video | NO | NO |

Do not treat later-release pipeline summaries as the missing v0.9.1 API contract. Exact modules, classes, constructor parameters, checkpoint loaders, generation methods, decoders, and model filenames remain unverified for this target. The user-facing engine identifier remains `LTX-2` / `ltx-2`; no user-facing pipeline selector should be added.

## Audio Systems

- **LTX-2 native audio:** The current runner attempts to use the pipeline's returned audio and mux it with video. Availability for the requested official version and model checkpoint is unverified.
- **Character dialogue:** Edge TTS remains a separate platform component; it is not native LTX-2 generation.
- **Voice cloning:** Not implemented by the current LTX-2 runner and not verified for the requested revision. It must remain an independent system if added later.

## Continuity and Status

The current `image_start` path is only a first-frame image condition. It does not establish source-video continuation, temporal latent continuation, or long-video continuity. The engine may not advertise those capabilities until a selected upstream pipeline exposes the conditioning interface and an integration test verifies its use.

Final classification: structural `REAL_INTEGRATION`; `GPU-READY` not established; `GPU-UNVERIFIED`. No CUDA inference was run as part of this documentation audit. Never report `REAL_VERIFIED` based on mocked generation or unit tests.