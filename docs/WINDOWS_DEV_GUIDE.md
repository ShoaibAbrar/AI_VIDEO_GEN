# Windows 10/11 Developer Guide (PowerShell)

This guide walks you through setting up, configuring, running, and testing the **GenVid.AI / Wan2GP Video Generation Platform** on Windows 10 or Windows 11 using PowerShell.

---

## 1. System Requirements

- **Operating System**: Windows 10 (version 2004+) or Windows 11 (64-bit)
- **Shell**: PowerShell 5.1+ or PowerShell 7+ (pwsh)
- **Python**: Python 3.10, 3.11, 3.12, or 3.13 (64-bit)
- **Node.js**: Node.js 18.x or 20.x LTS + npm
- **GPU Requirement**: **Optional**. 
  - If you have an NVIDIA GPU (RTX 3060/4090, etc.), CUDA inference can be enabled.
  - If you do **NOT** have an NVIDIA GPU, set `DEV_MOCK_ENGINE=true` to run the full application in simulated developer mode with generated video playback.

---

## 2. Quick Setup (1-Command Script)

From the project root directory, run the automated setup script in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

This script will:
1. Verify Python and Node.js installations.
2. Create `.env` from `.env.example`.
3. Install backend Python dependencies (`pip install -r backend/requirements.txt`).
4. Install frontend npm dependencies (`npm install`).
5. Initialize the SQLite database schema and seed default development users.
6. Detect and report GPU hardware / CUDA status.

---

## 3. Manual Setup & Configuration

If you prefer to configure components step-by-step:

### A. Environment Configuration
Copy the provided `.env.example` templates:
```powershell
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env
```

Key environment variables in `.env`:
- `DEV_MOCK_ENGINE`: Set `true` to enable GPU-free simulated engine mode on standard Windows PCs.
- `DATABASE_URL`: `sqlite:///./wangp.db` (zero-setup local database) or PostgreSQL connection URL.
- `BACKEND_HOST`: `127.0.0.1` (or `0.0.0.0`)
- `BACKEND_PORT`: `8000`
- `FRONTEND_URL`: `http://localhost:5173`
- `STORAGE_PATH`: `./generated_videos` (relative, portable path)

### B. Backend Dependencies & Database Initialization
```powershell
cd backend
python -m pip install -r requirements.txt
python -m app.db.init_db
cd ..
```

Default credentials seeded by `init_db`:
- **Admin**: `admin@wan2gp.local` / `Admin12345!`
- **User**: `user@wan2gp.local` / `User12345!`

### C. Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

---

## 4. Running the Development Servers

### Option 1: Start Both Servers Together
```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-dev.ps1
```
This opens two separate PowerShell windows for the FastAPI backend and Vite frontend.

### Option 2: Start Individually
- **Backend (FastAPI)**:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\start-backend.ps1
  ```
  Backend will run at: `http://127.0.0.1:8000` (API Docs: `http://127.0.0.1:8000/docs`)

- **Frontend (React/Vite)**:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\start-frontend.ps1
  ```
  Frontend will run at: `http://localhost:5173`

---

## 5. Running Tests

Run the full automated test suite on Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-tests.ps1
```

Or invoke pytest directly from the backend directory:
```powershell
cd backend
python -m pytest tests -v
```

---

## 6. GPU Modes vs Mock Simulated Mode

| Mode | Configuration | Hardware Required | Description |
|---|---|---|---|
| **Mock Engine (Dev)** | `DEV_MOCK_ENGINE=true` | None (CPU only) | Generates valid simulated video artifacts, progress steps, and playback for complete UI/API end-to-end testing. |
| **Real GPU Inference** | `DEV_MOCK_ENGINE=false` | NVIDIA GPU with CUDA | Uses real in-process Wan2GP / LTX / MiniMax weights. If GPU or weights are missing, cleanly returns unavailable status rather than pretending to generate. |
| **Remote GPU Server** | `WorkerType.REMOTE_HTTP` | Private GPU Server | Dispatches generation over REST to an external Linux/Windows GPU instance. |
| **RunPod Cloud GPU** | `WorkerType.RUNPOD` | RunPod Serverless / Pod | Submits workload to cloud GPU serverless endpoints. |

---

## 7. Windows Troubleshooting

### 1. PowerShell Execution Policy Restriction
If PowerShell errors with `File cannot be loaded because running scripts is disabled on this system`:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 2. Port Collisions (Port 8000 or 5173 occupied)
Find process listening on port 8000:
```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object OwningProcess
```
Kill process:
```powershell
Stop-Process -Id <PID> -Force
```

### 3. Missing ffmpeg
If video stitching or audio encoding operations require ffmpeg on Windows, install via `winget`:
```powershell
winget install Gyan.FFmpeg
```
