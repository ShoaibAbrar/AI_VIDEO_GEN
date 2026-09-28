# GenVid.AI — Multi-Engine AI Video Creation & Orchestration Platform

GenVid.AI is an enterprise-grade, model-agnostic AI video generation and narrative orchestration platform. It unifies state-of-the-art diffusion video engines, omni-modal audio-video foundation models, production pipelines, and zero-shot voice cloning into a single, intuitive interface and API gateway.

---

## 1. Project Architecture

```text
User / Browser (React 18 + Vite + Tailwind CSS)
                       │
                       ▼
         FastAPI REST API Gateway (Port 8000)
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
Capability       VoiceEngine        GenerationWorker
 Resolver         Registry             Pool
       │               │               │
       ▼               ▼               ▼
 Video Engine      Edge TTS /      Local Worker /
   Adapters        Chatterbox       Remote RunPod
       │               │               │
       └───────────────┼───────────────┘
                       ▼
          Output Media (.mp4 / .wav)
```

### Core Architecture Principles:
* **Model-Agnostic Interface:** End users specify creative requirements (prompt, duration, voice, characters, quality, style). The backend **Capability Resolver** dynamically resolves and selects the optimal AI engine.
* **Decoupled Engine Adapters:** All engines (Wan2GP, LTX, MiniMax H3, MoneyPrinterTurbo) implement standard contracts (`BaseVideoEngine` and `BaseVoiceEngine`).
* **Heterogeneous Worker Execution:** Supports local CPU/GPU worker execution as well as remote worker pools (e.g. RunPod, custom GPU endpoints).

---

## 2. Supported Engines & Verification Status

| Engine / Component | Capability Type | Upstream Reference | Approved Status |
|---|---|---|---|
| **Wan2GP** | Diffusion Video Generation | Local / Wan2GP | `REAL integration / GPU verified` |
| **LTX-Video** | Fast Diffusion Video | [Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video) | `REAL_INTEGRATION / GPU-READY` |
| **LTX-2** | Omni-Modal Audio-Video | [Lightricks/LTX-2](https://github.com/Lightricks/LTX-2) | `REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED` |
| **MiniMax H3** | Omni-Modal Audio-Video | [MiniMax-AI/H3](https://github.com/MiniMax-AI/H3) | `REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED` |
| **H3 Director** | Multi-Character Narrative | [MiniMax-AI/H3](https://github.com/MiniMax-AI/H3) | `REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED` |
| **H3 LongVideos** | Native Long Video Orchestration | [Smite79/MiniMax-H3-LongVideos](https://github.com/Smite79/MiniMax-H3-LongVideos) | `REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED` |
| **MoneyPrinterTurbo** | Topic-to-Video Production Pipeline | [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | `REAL_INTEGRATION / PRODUCTION PIPELINE` |
| **Edge TTS** | Standard AI Voice Generation | [rany2/edge-tts](https://github.com/rany2/edge-tts) | `REAL integration` |
| **Voice Cloning (Chatterbox)** | Zero-Shot Custom Voice | [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) | `REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED` |

> [!IMPORTANT]
> **Status Definitions:**
> * `GPU VERIFIED`: Physically tested and validated on NVIDIA GPU hardware with real tensor inference output.
> * `GPU-READY / GPU-UNVERIFIED`: Real integration code written and validated against official upstream code/repos, operating in plan-only/stub mode on CPU dev machines, awaiting physical GPU execution.

---

## 3. Capability vs Interface Matrix

| Capability / Feature | UI Accessible | API / CLI Accessible | GPU Required | Remote GPU Support | Verification Status |
|---|---|---|---|---|---|
| **Text-to-Video Generation** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL / GPU VERIFIED` (Wan2GP) |
| **Image-to-Video Generation** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL / GPU VERIFIED` (Wan2GP) |
| **Fast Video Diffusion (LTX-Video)** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL_INTEGRATION / GPU-READY` |
| **Omni-Modal Audio-Video (LTX-2)** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL_INTEGRATION / GPU-UNVERIFIED` |
| **Omni-Modal Audio-Video (H3)** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL_INTEGRATION / GPU-UNVERIFIED` |
| **Multi-Character Narrative (H3 Director)** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL_INTEGRATION / GPU-UNVERIFIED` |
| **Native Long Video (H3 LongVideos)** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL_INTEGRATION / GPU-UNVERIFIED` |
| **Scripted Video Production (MoneyPrinterTurbo)** | ✅ Yes | ✅ Yes | ❌ No (CPU) | ✅ Yes | `REAL_INTEGRATION / PRODUCTION PIPELINE` |
| **Standard Voiceover (Edge TTS)** | ✅ Yes | ✅ Yes | ❌ No (CPU) | ✅ Yes | `REAL integration` |
| **Zero-Shot Voice Cloning (Chatterbox)** | ✅ Yes | ✅ Yes | ✅ Yes (CUDA) | ✅ Yes | `REAL_INTEGRATION / GPU-UNVERIFIED` |
| **Multi-Scene Story Planning** | ❌ API/CLI | ✅ Yes | ❌ No (CPU) | ✅ Yes | `REAL integration` |
| **User & Role Administration** | ✅ Yes | ✅ Yes | ❌ No | N/A | `REAL integration` |
| **System Diagnostics & Health Status** | ✅ Yes | ✅ Yes | ❌ No | N/A | `REAL integration` |

---

## 4. System Requirements & Setup

### Prerequisites
* **Operating System:** Windows 10/11, Ubuntu 22.04+, or WSL2.
* **Python:** Python 3.10 – 3.13.
* **Node.js:** Node.js 18.0+.
* **FFmpeg:** System FFmpeg installed and accessible in PATH.
* **GPU (Optional for Dev, Required for Real Inference):** NVIDIA GPU with 12GB+ VRAM (24GB+ recommended for H3/LTX-2).

---

### Step 1 — Environment Configuration

Clone the repository and create your `.env` file:

```bash
cp .env.example .env
```

Default `.env` settings for local CPU development:

```env
DEBUG=true
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
DEV_MOCK_ENGINE=true
DATABASE_URL=sqlite:///./wangp.db
STORAGE_PATH=./generated_videos
FRONTEND_URL=http://localhost:5173
```

---

### Step 2 — Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 3 — Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node modules
npm install

# Build check
npm run build
```

---

### Step 4 — Starting the Application

#### Option A — Backend API Gateway & Worker

```bash
# From backend directory with venv activated:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Option B — Frontend Development Server

```bash
# From frontend directory:
npm run dev
```

Open browser at `http://localhost:5173`. Default admin user initialized automatically:
* **Username:** `admin` or create account on `/register` page.

---

## 5. Complete Testing Guide & CLI Matrix

### Test Categories

Tests are classified into 5 operational levels:

1. **UNIT/INTEGRATION:** Pure logic, schema, and API routing tests (0.5s execution time).
2. **REAL CPU:** Executes real CPU tasks (e.g. Edge TTS synthesis, FFmpeg stitching, MoneyPrinterTurbo script parsing).
3. **REAL GPU:** Requires local NVIDIA CUDA hardware for neural inference.
4. **REMOTE GPU:** Dispatches inference tasks to remote worker pools or RunPod endpoints.
5. **END-TO-END:** Complete path from request submission to final output file generation.

---

### Full Test Suite Command

Run the complete backend test suite:

```bash
cd backend
python -m pytest backend/tests -v --tb=short
```

**Expected Result:** 312 passed, 1 skipped (CUDA hardware skip), 0 failed.

---

### Engine-by-Engine Test Commands

| Engine | Test Target | Command | Test Type |
|---|---|---|---|
| **Platform E2E Audit** | 20-Point Audit | `python -m pytest backend/tests/test_platform_e2e_audit.py -v` | INTEGRATION / REAL CPU |
| **Capability Resolver** | Capability Mapping | `python -m pytest backend/tests/test_capability_resolver.py -v` | UNIT/INTEGRATION |
| **Wan2GP** | Engine Adapter | `python -m pytest backend/tests/test_wan2gp_adapter.py -v` | INTEGRATION / REAL GPU |
| **LTX-Video** | Engine Adapter | `python -m pytest backend/tests/test_ltx_video_adapter.py -v` | INTEGRATION / REAL CPU |
| **LTX-2** | Audio-Video Engine | `python -m pytest backend/tests/test_ltx2_adapter.py -v` | INTEGRATION / REAL CPU |
| **MiniMax H3** | Omni-AV Engine | `python -m pytest backend/tests/test_minimax_h3_adapter.py -v` | INTEGRATION / REAL CPU |
| **H3 Director** | Multi-Character Card | `python -m pytest backend/tests/test_minimax_h3_director_comprehensive.py -v` | INTEGRATION / REAL CPU |
| **H3 LongVideos** | Long Video Chunking | `python -m pytest backend/tests/test_minimax_h3_longvideos_comprehensive.py -v` | INTEGRATION / REAL CPU |
| **MoneyPrinterTurbo** | Production Pipeline | `python -m pytest backend/tests/test_money_printer_turbo_comprehensive.py -v` | INTEGRATION / REAL CPU |
| **Voice Cloning** | Chatterbox Zero-Shot | `python -m pytest backend/tests/test_voice_cloning_comprehensive.py -v` | INTEGRATION / REAL CPU |

---

### Dedicated Feature CLI Test Scripts

#### 1. Voice Cloning CLI Test (Chatterbox Zero-Shot)

```bash
python scripts/test-real-voice-cloning.py
```

* **Validates:** Reference audio validation, consent enforcement, profile creation, speaker embedding extraction, output WAV generation.

#### 2. MoneyPrinterTurbo Scripted Production Pipeline

```bash
python -m pytest backend/tests/test_money_printer_turbo_comprehensive.py -v
```

#### 3. Long Video Orchestrator CLI Test

```bash
python -m pytest backend/tests/test_minimax_h3_longvideos_comprehensive.py -v
```

---

## 6. Remote GPU & RunPod Setup

To run neural inference on remote cloud GPUs (e.g., RunPod, Lambda Labs, or custom GPU servers):

1. Set `.env` values:
   ```env
   DEV_MOCK_ENGINE=false
   RUNPOD_API_KEY=your-runpod-api-key
   RUNPOD_ENDPOINT_ID=your-endpoint-id
   ```
2. Start the remote worker:
   ```bash
   # Windows:
   .\scripts\start-voice-cloning-worker.ps1
   # Linux / RunPod:
   bash ./scripts/start-voice-cloning-worker.sh
   ```

---

## 7. Media Output Directory Locations

All media artifacts and database assets are saved locally:

* **Rendered AI Videos:** `./generated_videos/`
* **Custom Voice Profiles & Embeddings:** `./storage/voice_profiles/`
* **MoneyPrinterTurbo Video Outputs:** `./output/moneyprinterturbo/`
* **Cloned Voice WAV Outputs:** `./output/voice_cloning/`
* **Database File:** `./wangp.db`

---

## 8. Known Limitations & Truthful Status

1. **GPU Verification Status:**
   * `Wan2GP` is physically GPU verified.
   * `LTX-2`, `MiniMax H3`, `H3 Director`, `H3 LongVideos`, and `Chatterbox Voice Cloning` are **GPU-READY / GPU-UNVERIFIED**. Code integrations, schemas, workers, and diagnostics are complete, running in CPU plan-only / stub mode on non-CUDA development hardware. Physical CUDA hardware is required for real tensor weights inference.
2. **PyPI / Upstream Dependencies:**
   * Real Chatterbox voice synthesis requires `pip install chatterbox-tts==0.1.1` on CUDA host.
3. **Database:**
   * SQLite is configured by default for zero-setup local operation. Production environments should set `DATABASE_URL` to PostgreSQL.

---

## 9. License

This repository contains integration code for multiple open-source software packages:
* **GenVid.AI Platform:** MIT License
* **Chatterbox TTS:** MIT License (Code & Weights)
* **MoneyPrinterTurbo:** MIT License
* **Edge TTS:** MIT License
* **LTX-2 / LTX-Video:** Apache 2.0 / Custom Community License
