"""
Dedicated Standalone Voice Cloning GPU Server / Worker Endpoint.
Exposes REST API for zero-shot voice cloning, voice profile management, and speech synthesis on Port 8010.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import uuid

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
from app.services.voice.cloning.engine import VoiceCloningEngine
from app.services.voice.cloning.models import (
    AudioValidationErrorCode,
    VoiceCloningRequest,
    VoiceCloningResult,
    VoiceCloningStatusCode,
    VoiceProfile,
)
from app.services.voice.cloning.runner import ChatterboxVoiceCloningRunner
from app.services.voice.cloning.storage import VoiceProfileStore
from app.services.voice.cloning.validation import validate_reference_audio


app = FastAPI(
    title="GenVid.AI — Dedicated Voice Cloning GPU Server",
    version="1.0.0",
    description="REST API for Chatterbox zero-shot voice cloning and persistent VoiceProfile management.",
)

_engine: Optional[VoiceCloningEngine] = None
_job_history: Dict[str, VoiceCloningResult] = {}


def get_engine() -> VoiceCloningEngine:
    global _engine
    if _engine is None:
        _engine = VoiceCloningEngine()
    return _engine


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class CreateVoiceProfilePayload(BaseModel):
    name: str
    reference_audio_path: str
    owner_id: str = "default_user"
    reference_transcript: Optional[str] = None
    language: str = "en"
    gender: str = "neutral"
    consent_confirmed: bool = False


class GenerateSpeechPayload(BaseModel):
    text: str
    voice_profile_id: Optional[str] = None
    reference_audio_path: Optional[str] = None
    language: str = "en"
    speed: float = 1.0
    pitch: float = 0.0
    exaggeration: float = 0.0
    cfg_weight: float = 0.5
    consent_confirmed: bool = False
    plan_only: bool = False


class ValidateAudioPayload(BaseModel):
    audio_path: str
    consent_confirmed: bool = False


# ---------------------------------------------------------------------------
# Health & Diagnostics Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Health status and telemetry."""
    diag = check_voice_cloning_environment()
    return {
        "status": "HEALTHY" if diag.is_available else diag.status_code.value,
        "engine": "voice-cloning",
        "provider": "Chatterbox (Resemble AI)",
        "is_available": diag.is_available,
        "is_mock": diag.is_mock,
        "gpu_available": diag.gpu_available,
        "gpu_name": diag.gpu_name,
        "vram_total_gb": diag.vram_total_gb,
        "vram_available_gb": diag.vram_available_gb,
        "cuda_version": diag.cuda_version,
        "model_id": diag.model_id,
        "model_cached": diag.model_cached,
        "port": 8010,
        "message": diag.diagnostic_message,
    }


@app.get("/capabilities")
def get_capabilities():
    """Declares supported features, paralinguistic tags, and supported languages."""
    engine = get_engine()
    caps = engine.get_capabilities()
    return {
        "provider_name": caps.provider_name,
        "supports_voice_cloning": caps.supports_voice_cloning,
        "supports_neural_tts": caps.supports_neural_tts,
        "supports_paralinguistic_tags": True,
        "paralinguistic_tags": ["[laugh]", "[cough]", "[sigh]", "[gasp]", "[whisper]", "[chuckle]"],
        "supported_languages": ChatterboxVoiceCloningRunner.SUPPORTED_LANGUAGES,
        "total_voices_registered": len(caps.available_voices),
    }


@app.get("/diagnostics")
def get_diagnostics():
    """Detailed environment report."""
    diag = check_voice_cloning_environment()
    return diag.__dict__


# ---------------------------------------------------------------------------
# Voice Profile Management Endpoints
# ---------------------------------------------------------------------------

@app.post("/validate")
def validate_audio(payload: ValidateAudioPayload):
    """Validates reference audio duration, acoustics, format, and consent."""
    res = validate_reference_audio(
        audio_path=payload.audio_path,
        consent_confirmed=payload.consent_confirmed,
    )
    return {
        "is_valid": res.is_valid,
        "error_code": res.error_code.value,
        "error_message": res.error_message,
        "duration_seconds": res.duration_seconds,
        "sample_rate": res.sample_rate,
        "channels": res.channels,
        "has_clipping": res.has_clipping,
    }


@app.post("/voices")
def create_voice_profile(payload: CreateVoiceProfilePayload):
    """Creates and persists a new authorized VoiceProfile."""
    engine = get_engine()
    try:
        prof = engine.create_voice_profile(
            name=payload.name,
            reference_audio_path=payload.reference_audio_path,
            owner_id=payload.owner_id,
            reference_transcript=payload.reference_transcript,
            language=payload.language,
            gender=payload.gender,
            consent_confirmed=payload.consent_confirmed,
        )
        return prof.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create VoiceProfile: {exc}")


@app.get("/voices")
def list_voice_profiles(owner_id: Optional[str] = None):
    """Lists all stored VoiceProfiles."""
    engine = get_engine()
    profiles = engine.list_voice_profiles(owner_id=owner_id)
    return [p.to_dict() for p in profiles]


@app.get("/voices/{profile_id}")
def get_voice_profile(profile_id: str):
    """Retrieves a single VoiceProfile by ID."""
    engine = get_engine()
    prof = engine.get_voice_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail=f"VoiceProfile '{profile_id}' not found.")
    return prof.to_dict()


@app.delete("/voices/{profile_id}")
def delete_voice_profile(profile_id: str):
    """Securely deletes a VoiceProfile and all associated reference audio."""
    engine = get_engine()
    success = engine.delete_voice_profile(profile_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"VoiceProfile '{profile_id}' not found.")
    return {"success": True, "deleted_profile_id": profile_id}


# ---------------------------------------------------------------------------
# Speech Generation Endpoints
# ---------------------------------------------------------------------------

@app.post("/generate")
def generate_speech(payload: GenerateSpeechPayload):
    """Synthesizes speech cloning the target voice profile."""
    engine = get_engine()

    job_id = f"vc_{uuid.uuid4().hex[:8]}"
    req = VoiceCloningRequest(
        text=payload.text,
        voice_profile_id=payload.voice_profile_id,
        reference_audio_path=payload.reference_audio_path,
        language=payload.language,
        speed=payload.speed,
        pitch=payload.pitch,
        exaggeration=payload.exaggeration,
        cfg_weight=payload.cfg_weight,
        job_id=job_id,
        plan_only=payload.plan_only,
        extra_options={"consent_confirmed": payload.consent_confirmed},
    )

    result = engine.clone_voice(req)
    _job_history[job_id] = result

    if not result.success and result.status == VoiceCloningStatusCode.REFERENCE_INVALID.value:
        raise HTTPException(status_code=400, detail=result.error_message)

    return {
        "job_id": result.job_id,
        "status": result.status,
        "success": result.success,
        "audio_path": result.audio_path,
        "duration_seconds": result.duration_seconds,
        "sample_rate": result.sample_rate,
        "voice_profile_id": result.voice_profile_id,
        "voice_name": result.voice_name,
        "language": result.language,
        "error_message": result.error_message,
        "execution_time_seconds": result.execution_time_seconds,
        "telemetry": result.telemetry,
    }


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Retrieves status and result of a voice synthesis job."""
    res = _job_history.get(job_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return res.__dict__


@app.post("/cancel/{job_id}")
def cancel_job(job_id: str):
    """Cancels an active voice cloning job."""
    engine = get_engine()
    cancelled = engine.runner.cancel(job_id)
    return {"job_id": job_id, "cancelled": cancelled}


@app.get("/output/{job_id}")
def download_audio(job_id: str):
    """Downloads synthesized audio for a completed job."""
    res = _job_history.get(job_id)
    if not res or not res.audio_path:
        raise HTTPException(status_code=404, detail=f"Audio output for job '{job_id}' not found.")

    audio_path = Path(res.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing on disk.")

    return FileResponse(
        str(audio_path),
        media_type="audio/wav",
        filename=f"cloned_voice_{job_id}.wav",
    )


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Cloning Standalone Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8010, help="Bind port (default: 8010)")
    parser.add_argument("--reload", action="store_true", help="Hot reload")
    args = parser.parse_args()

    print(f"\n[VoiceCloningServer] Starting on http://{args.host}:{args.port}")
    print(f"[VoiceCloningServer] Health: http://{args.host}:{args.port}/health")
    print(f"[VoiceCloningServer] Docs:   http://{args.host}:{args.port}/docs\n")
    uvicorn.run("standalone_voice_cloning_server:app", host=args.host, port=args.port, reload=args.reload)
