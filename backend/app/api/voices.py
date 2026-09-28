"""Voice management and voice profile API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.models.user import User
from app.services.voice.registry import get_voice_engine_registry
from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
from app.services.voice.cloning.models import AudioValidationErrorCode
from app.services.voice.cloning.storage import VoiceProfileStore
from app.services.voice.cloning.validation import validate_reference_audio

router = APIRouter(prefix="/voices", tags=["voices"])

profile_store = VoiceProfileStore()


class VoiceProfileCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    reference_audio_path: str = Field(...)
    reference_transcript: Optional[str] = None
    language: str = "en"
    gender: str = "neutral"
    consent_confirmed: bool = Field(True, description="Must be true to authorize voice cloning")


class VoiceProfileResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    reference_audio_path: Optional[str]
    language: str
    engine: str
    gender: str
    consent_confirmed: bool
    created_at: str


@router.get("", response_model=List[Dict[str, Any]])
async def list_voices(current_user: User = Depends(get_current_user)):
    """List all available voice engines and registered voice profiles."""
    registry = get_voice_engine_registry()
    cloned_profiles = profile_store.list_profiles()

    voices = []
    # Include cloned profiles
    for p in cloned_profiles:
        voices.append({
            "id": p.id,
            "name": p.name,
            "engine": p.engine,
            "language": p.language,
            "gender": p.gender,
            "is_custom_cloned": True,
            "consent_confirmed": p.consent_confirmed,
            "owner_id": p.owner_id,
        })

    # Include default voice engine options
    for item in registry.list_engines():
        voices.append({
            "id": f"engine:{item['engine_id']}",
            "name": f"Engine Voice: {item['engine_id']}",
            "engine": item['engine_id'],
            "language": "en",
            "gender": "neutral",
            "is_custom_cloned": False,
            "consent_confirmed": True,
            "owner_id": "system",
        })

    return voices


@router.post("/profiles", response_model=VoiceProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_profile(
    req: VoiceProfileCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a new custom cloned voice profile with reference audio validation and consent enforcement."""
    if not req.consent_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit user consent is required to create a cloned voice profile.",
        )

    val_res = validate_reference_audio(req.reference_audio_path, consent_confirmed=req.consent_confirmed)
    if not val_res.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audio validation failed [{val_res.error_code}]: {val_res.error_message}",
        )

    try:
        profile = profile_store.create_profile(
            name=req.name,
            reference_audio_path=req.reference_audio_path,
            owner_id=str(current_user.id),
            reference_transcript=req.reference_transcript,
            language=req.language,
            gender=req.gender,
            consent_confirmed=req.consent_confirmed,
        )
        return VoiceProfileResponse(
            id=profile.id,
            name=profile.name,
            owner_id=profile.owner_id,
            reference_audio_path=profile.reference_audio_path,
            language=profile.language,
            engine=profile.engine,
            gender=profile.gender,
            consent_confirmed=profile.consent_confirmed,
            created_at=profile.created_at.isoformat(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create voice profile: {exc}",
        ) from exc


@router.get("/profiles/{profile_id}", response_model=VoiceProfileResponse)
async def get_voice_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve details of a specific voice profile."""
    del current_user
    profile = profile_store.get_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice profile '{profile_id}' not found.",
        )
    return VoiceProfileResponse(
        id=profile.id,
        name=profile.name,
        owner_id=profile.owner_id,
        reference_audio_path=profile.reference_audio_path,
        language=profile.language,
        engine=profile.engine,
        gender=profile.gender,
        consent_confirmed=profile.consent_confirmed,
        created_at=profile.created_at.isoformat(),
    )


@router.delete("/profiles/{profile_id}")
async def delete_voice_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a custom voice profile."""
    del current_user
    success = profile_store.delete_profile(profile_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice profile '{profile_id}' not found or could not be deleted.",
        )
    return {"message": f"Voice profile '{profile_id}' deleted successfully."}


@router.get("/diagnostics")
async def voice_diagnostics(current_user: User = Depends(get_current_user)):
    """Return Chatterbox zero-shot voice cloning environment diagnostics."""
    del current_user
    status_obj = check_voice_cloning_environment()
    return {
        "status_code": status_obj.status_code,
        "is_available": status_obj.is_available,
        "is_mock": status_obj.is_mock,
        "gpu_available": status_obj.gpu_available,
        "gpu_name": status_obj.gpu_name,
        "vram_total_gb": status_obj.vram_total_gb,
        "vram_available_gb": status_obj.vram_available_gb,
        "model_id": status_obj.model_id,
        "model_cached": status_obj.model_cached,
        "missing_dependencies": status_obj.missing_dependencies,
        "diagnostic_message": status_obj.diagnostic_message,
    }
