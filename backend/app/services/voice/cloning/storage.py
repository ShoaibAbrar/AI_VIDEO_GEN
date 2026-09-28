"""
Voice Profile Store and Persistent Speaker Asset Management.
Provides secure local disk storage, CRUD operations, and speaker embedding persistence for VoiceProfiles.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import threading
from typing import Any, Dict, List, Optional
import uuid

from app.core.logging_config import logger
from app.services.voice.cloning.models import VoiceProfile


class VoiceProfileStore:
    """
    Manages persistent VoiceProfiles and their associated reference audio & speaker embeddings on disk.
    Directory structure:
      storage/voice_profiles/
        ├── vp_abc123/
        │     ├── profile.json
        │     ├── reference.wav
        │     └── speaker_embedding.pt
    """

    def __init__(self, storage_dir: Optional[str | Path] = None):
        self.storage_dir = Path(
            storage_dir
            or os.environ.get("VOICE_PROFILES_STORAGE_DIR")
            or "./storage/voice_profiles"
        ).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create_profile(
        self,
        name: str,
        reference_audio_path: str | Path,
        owner_id: str = "default_user",
        reference_transcript: Optional[str] = None,
        language: str = "en",
        gender: str = "neutral",
        consent_confirmed: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceProfile:
        """
        Creates and stores a new VoiceProfile with copied reference audio.
        """
        ref_path = Path(reference_audio_path).resolve()
        if not ref_path.exists():
            raise FileNotFoundError(f"Reference audio file not found: {ref_path}")

        profile_id = f"vp_{uuid.uuid4().hex[:12]}"
        profile_dir = self.storage_dir / profile_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Securely copy reference audio into profile directory
        stored_audio_filename = f"reference{ref_path.suffix.lower()}"
        stored_audio_path = profile_dir / stored_audio_filename
        shutil.copy2(ref_path, stored_audio_path)

        profile = VoiceProfile(
            id=profile_id,
            name=name,
            owner_id=owner_id,
            reference_audio_path=str(stored_audio_path.resolve()),
            reference_transcript=reference_transcript,
            language=language,
            gender=gender,
            consent_confirmed=consent_confirmed,
            metadata=metadata or {},
        )

        self._save_profile_json(profile)
        logger.info(f"Created persistent VoiceProfile '{profile.name}' ({profile.id}) in {profile_dir}")
        return profile

    def get_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        """Retrieves a VoiceProfile by ID."""
        with self._lock:
            profile_dir = self.storage_dir / profile_id
            json_file = profile_dir / "profile.json"
            if not json_file.exists():
                return None
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                return VoiceProfile.from_dict(data)
            except Exception as exc:
                logger.error(f"Failed to load VoiceProfile {profile_id}: {exc}", exc_info=True)
                return None

    def list_profiles(self, owner_id: Optional[str] = None) -> List[VoiceProfile]:
        """Lists all stored VoiceProfiles, optionally filtered by owner_id."""
        with self._lock:
            profiles: List[VoiceProfile] = []
            if not self.storage_dir.exists():
                return []

            for p_dir in self.storage_dir.iterdir():
                if p_dir.is_dir():
                    json_file = p_dir / "profile.json"
                    if json_file.exists():
                        try:
                            data = json.loads(json_file.read_text(encoding="utf-8"))
                            prof = VoiceProfile.from_dict(data)
                            if owner_id is None or prof.owner_id == owner_id:
                                profiles.append(prof)
                        except Exception as exc:
                            logger.warning(f"Could not read profile in {p_dir}: {exc}")

            return sorted(profiles, key=lambda p: p.created_at, reverse=True)

    def update_profile(self, profile: VoiceProfile) -> VoiceProfile:
        """Updates and persists changes to an existing VoiceProfile."""
        with self._lock:
            self._save_profile_json(profile)
            return profile

    def delete_profile(self, profile_id: str) -> bool:
        """Securely deletes a VoiceProfile directory and all associated audio/embeddings."""
        with self._lock:
            profile_dir = self.storage_dir / profile_id
            if profile_dir.exists() and profile_dir.is_dir():
                try:
                    shutil.rmtree(profile_dir)
                    logger.info(f"Deleted VoiceProfile {profile_id} and all associated audio assets.")
                    return True
                except Exception as exc:
                    logger.error(f"Error deleting VoiceProfile {profile_id}: {exc}", exc_info=True)
                    return False
            return False

    def save_speaker_embedding(self, profile_id: str, embedding_bytes: bytes) -> str:
        """Caches precomputed speaker embedding tensor / binary blob for fast zero-shot inference."""
        with self._lock:
            profile_dir = self.storage_dir / profile_id
            profile_dir.mkdir(parents=True, exist_ok=True)
            emb_path = profile_dir / "speaker_embedding.bin"
            emb_path.write_bytes(embedding_bytes)

            prof = self.get_profile(profile_id)
            if prof:
                prof.speaker_embedding_path = str(emb_path.resolve())
                self.update_profile(prof)

            return str(emb_path.resolve())

    def _save_profile_json(self, profile: VoiceProfile) -> None:
        profile_dir = self.storage_dir / profile.id
        profile_dir.mkdir(parents=True, exist_ok=True)
        json_file = profile_dir / "profile.json"
        json_file.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
