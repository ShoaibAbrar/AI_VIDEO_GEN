# Minimal GPU Video Generation Prototype

This prototype is intentionally separate from the production platform code. It provides one browser page, one in-memory job, one generation at a time, and uses the real in-process Wan2GP programmatic API.

```text
Browser
  -> gpu_prototype/main.py
    -> shared.api.init()
      -> WanGPSession.submit_task()
        -> actual Wan2GP generation
          -> GPU (Tesla T4)
            -> outputs/<job_id>/generated.mp4
```

> [!NOTE]
> **REAL GPU GENERATION NOT VERIFIED** locally until executed on an actual Lightning AI GPU Studio.

---

## Lightning AI Tesla T4 Environment

The target environment on Lightning AI Studio is:
* **OS**: Linux
* **GPU**: Tesla T4 (15,360 MB VRAM)
* **Python**: 3.12.11 (Lightning default environment)
* **PyTorch**: 2.8.0+cu128

Do **NOT** attempt to create a custom Conda environment inside Lightning Studio. Use the default pre-configured PyTorch CUDA environment.

---

## Step-by-Step Lightning Setup & Execution

### Step 1: Clone Repository & Verify Environment
Start in your workspace folder (`~/AI_VIDEO_GEN` or `Wan2GP`):

```bash
cd ~/AI_VIDEO_GEN
nvidia-smi
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0)); print('PyTorch:', torch.__version__); print('CUDA runtime:', torch.version.cuda)"
```

### Step 2: Install Repository Dependencies
Install repository requirements and prototype-specific requirements:

```bash
pip install -r requirements.txt
pip install -r gpu_prototype/requirements.txt
```

### Step 3: Run Model Setup
Wan2GP requires both the main model weights (`t2v_1.3B`) and the UMT5-XXL text encoder checkpoint (`models_t5_umt5-xxl-enc-quanto_int8.safetensors`).

Run the automated setup script:

```bash
python scripts/download_model.py t2v_1.3B
```

This will download:
* `ckpts/wan2.1_text2video_1.3B_mbf16.safetensors`
* `ckpts/umt5-xxl/models_t5_umt5-xxl-enc-quanto_int8.safetensors`

### Step 4: Run Prototype Server
Start FastAPI server with uvicorn on port `8000`:

```bash
python -m uvicorn gpu_prototype.main:app --host 0.0.0.0 --port 8000
```

### Step 5: Open Browser & Expose Port 8000
Expose/forward port `8000` in your Lightning AI Studio UI and open the URL in your browser.

---

## First Generation Settings

Use the following low-memory settings tailored for Tesla T4:

* **Prompt**: `A small golden bird flying over a quiet lake at sunrise`
* **Model**: `t2v_1.3B`
* **Frames**: `33` (~2 seconds of video at 16 fps)
* **Steps**: `20`
* **Seed**: `42`

Click **Generate Video**. Watch the real status and progress updates as WanGP runs.

Upon completion:
* Output video will be saved at `outputs/<job_id>/generated.mp4`.
* The browser video player will automatically display the generated video.
* Click **Download video** to save the file.

---

## Prototype API Endpoints

* `GET /api/health`: Returns PyTorch, CUDA, and GPU status diagnostics.
* `GET /api/models`: Returns list of available models and diagnostic info for unavailable models.
* `POST /api/generate`: Submits a real Wan2GP generation task.
* `GET /api/generate/{job_id}`: Polls task status and progress (0-100%).
* `GET /api/video/{job_id}`: Streams the generated MP4 file.

---

## Troubleshooting

* **CUDA/GPU unavailable**: Confirm `nvidia-smi` works and `torch.cuda.is_available()` returns `True`.
* **Model unavailable in UI**: Run `python scripts/download_model.py t2v_1.3B` to download missing main checkpoint or UMT5 text encoder files.
* **FP16 Warning**: On Tesla T4 (compute capability 7.5 < 8.0), WanGP automatically logs:
  `Switching to FP16 models when possible as GPU architecture doesn't support optimed BF16 Kernels`
  This is normal and expected behavior.
