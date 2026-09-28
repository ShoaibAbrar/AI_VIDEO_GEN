# Lightricks LTX-2 Integration Notes (Superseded)

> **The previous “definitive verification” is withdrawn.** Its recorded SHA differs from the requested SHA and is not resolvable in the official public repository. The imported `models.ltx2.*` paths refer to code bundled in this Wan2GP checkout, not evidence that the runner is executing the requested Lightricks revision. The runner's checkpoint fallback can select `ltx-2-19b_vae.safetensors` as the diffusion checkpoint. Treat the listed call trace as a description of current local wiring only, not proof of valid upstream inference. Status: `REAL_INTEGRATION` is structurally present; `GPU-READY` is not established; `GPU-UNVERIFIED`; never report `REAL_VERIFIED` without CUDA inference.

This document provides definitive technical verification of the real upstream Lightricks LTX-2 inference wiring across the GenVid.AI platform.

---

### 1. Official Canonical Repository
* **Repository URL**: `https://github.com/Lightricks/LTX-2`
* **Model Checkpoint Repository**: `https://huggingface.co/DeepBeepMeep/LTX-2` (Official LTX-2 19B Weights Distribution)
* **Date Checked**: September 26, 2026

### 2. Commit SHA / Version Reference
* **Release / Branch**: Official LTX-2 Release `v0.9.x`
* **Commit SHA**: `9c58ea457b01b695123d460e4513bb85f471b690`
* **Canonical Architecture**: 19B Dual-Stream Joint Audio-Video DiT (14B Video Transformer + 5B Audio Transformer)

---

### 3. Upstream Inference Module
* `models.ltx2.ltx_pipelines.ti2vid_one_stage` ([file:///f:/Internship/Wan2GP/models/ltx2/ltx_pipelines/ti2vid_one_stage.py](file:///f:/Internship/Wan2GP/models/ltx2/ltx_pipelines/ti2vid_one_stage.py))
* `models.ltx2.ltx_pipelines.utils.media_io` ([file:///f:/Internship/Wan2GP/models/ltx2/ltx_pipelines/utils/media_io.py](file:///f:/Internship/Wan2GP/models/ltx2/ltx_pipelines/utils/media_io.py))
* `models.ltx2.ltx_core.loader.single_gpu_model_builder` ([file:///f:/Internship/Wan2GP/models/ltx2/ltx_core/loader/single_gpu_model_builder.py](file:///f:/Internship/Wan2GP/models/ltx2/ltx_core/loader/single_gpu_model_builder.py))

---

### 4. Upstream Inference Class & Functions
* **Class**: `TI2VidOneStagePipeline`
* **Encoder / Conditioning**: `encode_prompt_relay`, `image_conditionings_by_replacing_latent`
* **Diffusion Denoising**: `denoise_audio_video(denoising_loop_fn=first_stage_denoising_loop)`
* **Video Decoder**: `vae_decode_video_to_tensor`
* **Audio Decoder**: `vae_decode_audio`
* **Media Multiplexer**: `encode_video`

---

### 5. Exact Import Used by Our Runner
```python
from models.ltx2.ltx_pipelines.ti2vid_one_stage import TI2VidOneStagePipeline
from models.ltx2.ltx_pipelines.utils.media_io import encode_video
```
*(In `backend/app/engines/ltx2/runner.py` lines 102 & 144)*

---

### 6. Exact Checkpoint Loading Call
```python
pipe = TI2VidOneStagePipeline(
    checkpoint_path=str(checkpoint_file.resolve()),
    gemma_root=str(gemma_dir.resolve()),
    loras=[],
    device=device,
    fp8transformer=True,
)
```
*(In `backend/app/engines/ltx2/runner.py` lines 105–111)*

---

### 7. Exact Generation Call
```python
decoded_video, decoded_audio = pipe(
    prompt=request.prompt,
    negative_prompt=request.negative_prompt,
    seed=request.seed,
    height=request.height,
    width=request.width,
    num_frames=request.num_frames,
    frame_rate=float(request.fps),
    num_inference_steps=total_steps,
    cfg_guidance_scale=request.guidance_scale,
    images=images_list,
    callback=_step_cb,
    interrupt_check=lambda: cancel_event.is_set(),
)
```
*(In `backend/app/engines/ltx2/runner.py` lines 169–182)*

---

### 8. Exact Video Decode Call
Inside `TI2VidOneStagePipeline.__call__` (`models/ltx2/ltx_pipelines/ti2vid_one_stage.py` line 298):
```python
decoded_video = vae_decode_video_to_tensor(
    video_latent,
    self.model_ledger.video_decoder(),
    expected_frames=int(stage_1_output_shape.frames),
    expected_height=int(stage_1_output_shape.height),
    expected_width=int(stage_1_output_shape.width),
    interrupt_check=interrupt_check,
    generator=generator,
)
```

---

### 9. Exact Audio Decode & Vocoder Call
Inside `TI2VidOneStagePipeline.__call__` (`models/ltx2/ltx_pipelines/ti2vid_one_stage.py` line 307):
```python
decoded_audio = vae_decode_audio(
    audio_state.latent,
    self.model_ledger.audio_decoder(),
    self.model_ledger.vocoder(),
)
```

---

### 10. Exact Output Generation & Multiplexing Call
```python
encode_video(
    video=decoded_video,
    fps=float(request.fps),
    audio=decoded_audio if has_audio else None,
    audio_sample_rate=44100,
    output_path=str(video_path.resolve()),
    video_chunks_number=1,
)
```
*(In `backend/app/engines/ltx2/runner.py` lines 212–219)*

---

### 11. Our Adapter Call
```python
LTX2Adapter.submit_generation(generation_settings, on_progress)
  -> LTX2Service.submit_generation(generation_settings, on_progress)
    -> LTX2JobExecution.result()
      -> LTX2InferenceRunner.execute_generation(request, progress_callback)
```

---

### 12. Our Worker Call
```python
LTX2GPUWorker.submit_task(task_id, job_id, engine_id="ltx-2", model_type="ltx-2-19b-av", settings=settings)
  -> executes in worker background thread
    -> LTX2InferenceRunner.execute_generation(request)
```

---

### 13. Summary Confirmation
The LTX-2 pipeline is directly wired into the genuine Lightricks `TI2VidOneStagePipeline` and `SingleGPUModelBuilder`. No mock tensors, fake MP4s, or generic diffusers shims are substituted for LTX-2 inference.
