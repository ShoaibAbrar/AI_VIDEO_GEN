# Wan2GP Integration

## Integration method

The platform uses Wan2GP's existing in-process API. The backend generation worker owns one reusable `WanGPSession` created through `shared.api.init()`.

The platform does not call `wgp.generate_media()` from HTTP handlers, does not use the MCP server internally, and does not start a subprocess for each generation.

## Lifecycle

```text
FastAPI lifespan
  -> one GenerationWorker
    -> one Wan2GPService
      -> shared.api.init()
        -> one reusable WanGPSession
```

The MVP is intentionally limited to one backend process and one generation worker for one GPU. Do not run multiple backend worker processes against the same GPU runtime.

The session is initialized lazily by `Wan2GPService` when the worker first needs it. The same session remains available for later jobs so Wan2GP can reuse its loaded model state. On application shutdown, the worker stops and closes the session.

## Generation flow

1. An authenticated client submits a validated generation request.
2. The API stores a `GenerationJob` with status `QUEUED`.
3. The worker claims the oldest queued job using a transactional `FOR UPDATE SKIP LOCKED` query.
4. The job changes to `PROCESSING`.
5. `Wan2GPService` calls `WanGPSession.submit_task()`.
6. Wan2GP validates settings and invokes its existing generation path.
7. Progress callbacks update the job with real Wan2GP progress where available.
8. `SessionJob.result()` returns a `GenerationResult`.
9. The worker verifies the generated artifact and copies it into controlled storage.
10. The job becomes `COMPLETED`, or `FAILED` if generation or artifact handling fails.

## Supported request parameters

The initial platform API exposes only:

- `prompt`
- `model_type`
- `video_length`
- `num_inference_steps`
- `seed`

The service obtains model metadata, availability, and defaults from the actual Wan2GP API. Unknown model types, unavailable models, blank prompts, extra request fields, and invalid numeric ranges are rejected before queue insertion.

## Queue and worker

The queue is database-backed and uses the `generation_job` table. The worker is a daemon thread started by the FastAPI lifespan. It processes one job at a time and uses the existing Wan2GP generation lock internally through `shared.api`.

Redis, Celery, Kubernetes, S3, and additional GPU workers are not used.

The design intentionally does not claim horizontal scaling. A production deployment must keep one backend process and one generation worker for this MVP.

## Progress

Progress comes from Wan2GP's `ProgressUpdate` callbacks. The platform stores percentage, current step, total steps, phase, and status text when reported. The worker throttles database progress writes to avoid writing every event.

The platform does not invent progress values when Wan2GP does not provide meaningful progress.

## Storage

Generated media is copied into:

```text
<STORAGE_PATH>/videos/<user_id>/<job_id>/output.<extension>
```

The database stores only the controlled relative path. Users never submit an output path, and the video endpoint resolves paths relative to the configured storage root and rejects traversal.

## Cancellation

Queued jobs can be cancelled safely by changing `QUEUED` to `CANCELLED`.

Processing cancellation is not exposed by the platform API. Although the underlying `SessionJob` supports cancellation, the MVP does not claim that arbitrary model-specific GPU interruption is safe for every Wan2GP model.

## Errors

Wan2GP failures, missing artifacts, CUDA failures, and worker exceptions mark the job `FAILED`. Users receive a safe error message. Technical details are logged server-side. The worker catches failures per job and continues with later queued jobs.

## GPU requirements

For a Lightning AI Linux GPU instance, follow the repository's tested WanGP combinations:

- RTX 20xx through RTX 50xx: Python 3.11.14, PyTorch 2.10.0, and the CUDA 13.0/13.1 stack.
- GTX 10xx: Python 3.10.9, PyTorch 2.7.1, and CUDA 12.8.

The initial platform test target is the actual repository definition `t2v_1.3B`, whose default configuration is [defaults/t2v_1.3B.json](../defaults/t2v_1.3B.json). That definition points to the Wan2.1 Text2Video 1.3B checkpoint. WanGP advertises selected low-VRAM configurations from 6 GB, but the repository does not declare a single model-independent VRAM minimum for every profile; confirm the selected model's availability and use a GPU with enough VRAM for the selected profile and resolution.

The model definition may download the checkpoint from its configured Hugging Face URL on first use. Ensure the instance has network access or pre-populate the configured WanGP model/checkpoint directories. FFmpeg and the dependencies in the root `requirements.txt` are also required.

The automated tests use a fake service and do not prove GPU generation.

A real GPU generation was not executed as part of the current verification because the required model/GPU runtime was not available in the test environment.

## One real-generation procedure

On the GPU instance, from the repository root:

```bash
conda create -n wangp-platform python=3.11.14
conda activate wangp-platform
pip install torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
pip install -r backend/requirements.txt
cd backend
cp .env.example .env
```

Set these values in `backend/.env`:

```dotenv
DATABASE_URL=postgresql://<user>:<password>@<postgres-host>:5432/<database>
JWT_SECRET_KEY=<long-random-secret>
WAN2GP_ROOT=..
STORAGE_PATH=../storage
```

Then initialize the schema and start one backend process:

```bash
alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Start the frontend in a second shell:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Log in, open `/dashboard/videos`, select the available `t2v_1.3B` model, submit one short prompt, and wait for the job to transition from `QUEUED` to `PROCESSING` to `COMPLETED`. The worker starts with FastAPI; no separate worker command is required. The resulting file should appear under `STORAGE_PATH/videos/<user_id>/<job_id>/` and be playable from the generation history.

## API endpoints

- `GET /api/v1/generations/models`
- `POST /api/v1/generations`
- `GET /api/v1/generations`
- `GET /api/v1/generations/{job_id}`
- `GET /api/v1/generations/{job_id}/video`
- `POST /api/v1/generations/{job_id}/cancel` for queued jobs

All endpoints require authentication. Non-admin users can access only their own jobs and videos. Admins can view jobs globally.
