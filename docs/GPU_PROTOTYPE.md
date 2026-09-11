# Minimal GPU Prototype

This prototype is intentionally separate from the production platform code. It provides one browser page, one in-memory job, one generation at a time, and the existing Wan2GP programmatic API.

```text
Browser
  -> gpu_prototype/main.py
    -> shared.api.init()
      -> WanGPSession.submit_task()
        -> actual Wan2GP generation
          -> GPU
            -> outputs/<job_id>/generated.mp4
```

## Supported environment

Use the combinations documented by the existing WanGP repository:

- RTX 20xx through RTX 50xx: Python 3.11.14, PyTorch 2.10.0, CUDA 13.0/13.1.
- GTX 10xx: Python 3.10.9, PyTorch 2.7.1, CUDA 12.8.

The prototype does not invent a VRAM minimum. Start with the actual selected model's profile and resolution. The repository advertises some configurations from 6 GB VRAM, but requirements vary by model and profile.

## Lightning AI setup

The following uses the RTX 20xx-50xx environment. For GTX 10xx, use the Python 3.10/PyTorch 2.7.1/CUDA 12.8 commands in [INSTALLATION.md](INSTALLATION.md).

```bash
conda create -n wangp-prototype python=3.11.14
conda activate wangp-prototype
nvidia-smi
python --version
pip install torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu130
git clone <YOUR_REPOSITORY_URL>
cd Wan2GP
pip install -r requirements.txt
pip install -r gpu_prototype/requirements.txt
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'); print('count:', torch.cuda.device_count()); print('PyTorch:', torch.__version__); print('CUDA runtime:', torch.version.cuda)"
```

The selected WanGP model definition downloads its configured checkpoint on first use when the machine has network access. The initial UI selects the first available video model reported by WanGP. For a predictable first test, select `t2v_1.3B` when it is available; its repository definition is [defaults/t2v_1.3B.json](../defaults/t2v_1.3B.json).

## Run

From the repository root:

```bash
python -m uvicorn gpu_prototype.main:app --host 0.0.0.0 --port 8000
```

Open the Lightning AI forwarded port for `8000` in a browser. The backend serves the minimal UI and API from the same process. No separate worker command is needed.

The prototype endpoints are:

- `GET /api/health`
- `GET /api/models`
- `POST /api/generate`
- `GET /api/generate/{job_id}`
- `GET /api/video/{job_id}`

Generated files are copied to:

```text
outputs/<job_id>/generated.mp4
```

## First test

Use:

```text
A small golden bird flying over a quiet lake at sunrise
```

Use a short frame count such as `33`, the model's default-compatible step count shown by the UI, and seed `42`.

Success means the job reaches `COMPLETED`, `outputs/<job_id>/generated.mp4` exists, and the browser video player can play the returned file. The backend logs the actual WanGP/model errors if loading or generation fails.

## Troubleshooting

- `CUDA/GPU unavailable`: check `nvidia-smi`, `torch.cuda.is_available()`, and that the PyTorch wheel matches the CUDA setup.
- `Model loading failed`: confirm the model is available, the checkpoint download completed, and the WanGP root dependencies were installed.
- Out-of-memory errors: use a smaller supported model/profile, shorter video, or lower resolution through WanGP's model configuration. Do not increase jobs; this prototype already allows only one generation.
- Missing output: inspect the backend log and `outputs/`; the prototype fails visibly rather than creating a placeholder file.
- Port access: expose/forward port `8000` in the Lightning workspace and use the forwarded URL, not `localhost` from your own computer.

## Verification boundary

Local checks can verify imports, API validation, and frontend delivery. They cannot prove generation. A real GPU video-generation pass is successful only when WanGP produces the MP4 and the browser plays it.
