"""
MiniMax H3 LongVideos Beat-to-Chunk Planner.

Parses a multiline "beats" script (scene description + per-paragraph action beats) into
a structured LongVideoTimelinePlan of discrete sliding-window generation chunks, each
mapped to the downstream MiniMax H3 Omni-AV runner.

Beat format (from Smite79/MiniMax-H3-Longvideos architecture):
  - First paragraph: scene/location description (applied to all chunks)
  - Subsequent paragraphs: individual beats; lines in double-quotes = dialogue
  - Character sheets referenced by character_id tags

Architecture note:
  This planner is a clean standalone Python implementation of the sliding-window beat
  planner pattern observed in the Smite79/MiniMax-H3-Longvideos ComfyUI custom node.
  It does NOT copy or reproduce the ComfyUI node source code. The planning logic
  (beat parsing, duration estimation, chunk overlap scheduling) is implemented
  independently using the real upstream's documented interface contract.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
import uuid

from app.core.logging_config import logger
from app.engines.minimax_h3_longvideos.models import (
    H3LongVideoGenerationRequest,
    LongVideoBeat,
    LongVideoCharacterCard,
    LongVideoChunk,
    LongVideoTimelinePlan,
)


# ---------------------------------------------------------------------------
# Duration estimation constants (tuned to H3 25fps, 5s default chunk)
# ---------------------------------------------------------------------------

# Seconds of video per spoken word (approximation for dialogue beats)
_WORDS_PER_SECOND = 2.5
# Default duration when no dialogue is detected
_DEFAULT_ACTION_DURATION_S = 5.0
# Minimum chunk duration (must produce at least 1 frame)
_MIN_CHUNK_DURATION_S = 2.0
# Maximum single-chunk duration (H3 native ceiling ~15s at 25fps = 375 frames)
_MAX_CHUNK_DURATION_S = 14.0


class H3LongVideoPlanner:
    """
    Compiles a H3LongVideoGenerationRequest into a LongVideoTimelinePlan
    containing discrete LongVideoChunk entries ready for sliding-window generation.
    """

    def __init__(self, fps: int = 25) -> None:
        self.fps = fps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, request: H3LongVideoGenerationRequest) -> LongVideoTimelinePlan:
        """
        Main entry point. Returns a fully populated LongVideoTimelinePlan.
        If request.custom_chunks is provided, uses those directly.
        Otherwise, parses beats_text and builds chunks automatically.
        """
        characters: Dict[str, LongVideoCharacterCard] = {
            c.character_id: c for c in (request.characters or [])
        }

        if request.custom_chunks:
            chunks = request.custom_chunks
            total_dur = sum(c.duration_seconds for c in chunks)
            return LongVideoTimelinePlan(
                title=request.title,
                scene_description=request.scene_description or request.prompt,
                total_duration_seconds=total_dur,
                fps=request.fps,
                resolution=request.resolution,
                chunks=chunks,
                beats=[],
                characters=characters,
                estimated_vram_gb=24.0,
                plan_only=request.plan_only,
            )

        beats = self._parse_beats(
            beats_text=request.beats_text,
            fallback_prompt=request.prompt,
            characters=characters,
            default_chunk_duration=request.chunk_duration_seconds,
        )

        # Override total duration if explicitly requested
        total_dur = max(
            request.total_duration_seconds,
            sum(b.duration_seconds for b in beats) if beats else request.chunk_duration_seconds,
        )

        chunks = self._beats_to_chunks(
            beats=beats,
            scene_description=request.scene_description or request.prompt,
            characters=characters,
            fps=request.fps,
            overlap_frames=request.overlap_frames,
            seed=request.seed,
        )

        estimated_vram = 24.0  # per-chunk minimum on H3

        return LongVideoTimelinePlan(
            title=request.title,
            scene_description=request.scene_description or request.prompt,
            total_duration_seconds=total_dur,
            fps=request.fps,
            resolution=request.resolution,
            chunks=chunks,
            beats=beats,
            characters=characters,
            estimated_vram_gb=estimated_vram,
            plan_only=request.plan_only,
        )

    # ------------------------------------------------------------------
    # Beat parsing
    # ------------------------------------------------------------------

    def _parse_beats(
        self,
        beats_text: Optional[str],
        fallback_prompt: str,
        characters: Dict[str, LongVideoCharacterCard],
        default_chunk_duration: float,
    ) -> List[LongVideoBeat]:
        """
        Parses a multiline beats script into a list of LongVideoBeat entries.

        Beat detection rules (matching Smite79/H3-Longvideos documented interface):
          - First paragraph (before a blank line) = scene description → skip (used as context)
          - Each subsequent paragraph = one beat
          - Lines enclosed in double-quotes → dialogue extraction
          - Character IDs mentioned in text → character assignment
        """
        if not beats_text or not beats_text.strip():
            # No beats provided — create a single beat from the main prompt
            return [
                LongVideoBeat(
                    beat_index=0,
                    raw_text=fallback_prompt,
                    action=fallback_prompt,
                    duration_seconds=max(default_chunk_duration, _DEFAULT_ACTION_DURATION_S),
                )
            ]

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", beats_text.strip()) if p.strip()]
        if not paragraphs:
            return [
                LongVideoBeat(
                    beat_index=0,
                    raw_text=fallback_prompt,
                    action=fallback_prompt,
                    duration_seconds=default_chunk_duration,
                )
            ]

        # First paragraph = scene description — skip for beat list
        beat_paragraphs = paragraphs[1:] if len(paragraphs) > 1 else paragraphs

        beats: List[LongVideoBeat] = []
        for idx, para in enumerate(beat_paragraphs):
            beat = self._parse_single_beat(
                idx, para, characters, default_chunk_duration
            )
            beats.append(beat)
            logger.debug(
                f"H3LongVideoPlanner: beat[{idx}] dur={beat.duration_seconds:.1f}s "
                f"chars={beat.active_characters} dialogue={bool(beat.dialogue)}"
            )

        return beats

    def _parse_single_beat(
        self,
        idx: int,
        text: str,
        characters: Dict[str, LongVideoCharacterCard],
        default_duration: float,
    ) -> LongVideoBeat:
        """Extracts action, dialogue, speaker, active characters, and duration from one beat paragraph."""
        lines = text.strip().splitlines()

        # Extract dialogue (lines enclosed in double-quotes)
        dialogue_lines: List[str] = []
        action_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            match = re.match(r'^"(.+)"$', stripped)
            if match:
                dialogue_lines.append(match.group(1))
            else:
                action_lines.append(stripped)

        action = " ".join(action_lines).strip() or text.strip()
        dialogue = " ".join(dialogue_lines).strip() or None

        # Detect active characters by name/id mention
        active_chars: List[str] = []
        speaker: Optional[str] = None
        for char_id, card in characters.items():
            if char_id.lower() in text.lower() or card.name.lower() in text.lower():
                active_chars.append(char_id)
                if dialogue and speaker is None:
                    speaker = char_id

        # Duration estimation
        duration = self._estimate_duration(action, dialogue, default_duration)

        return LongVideoBeat(
            beat_index=idx,
            raw_text=text,
            action=action,
            dialogue=dialogue,
            speaker=speaker,
            active_characters=active_chars,
            duration_seconds=duration,
        )

    def _estimate_duration(
        self,
        action: str,
        dialogue: Optional[str],
        default: float,
    ) -> float:
        """
        Estimates beat duration based on dialogue length (words / WPS) or default.
        Clamps to [MIN, MAX] chunk duration bounds.
        """
        if dialogue:
            word_count = len(dialogue.split())
            speech_dur = word_count / _WORDS_PER_SECOND
            # Add 1-second buffer for visual action
            dur = max(speech_dur + 1.0, _DEFAULT_ACTION_DURATION_S)
        else:
            dur = default or _DEFAULT_ACTION_DURATION_S

        return max(_MIN_CHUNK_DURATION_S, min(_MAX_CHUNK_DURATION_S, dur))

    # ------------------------------------------------------------------
    # Chunk building
    # ------------------------------------------------------------------

    def _beats_to_chunks(
        self,
        beats: List[LongVideoBeat],
        scene_description: str,
        characters: Dict[str, LongVideoCharacterCard],
        fps: int,
        overlap_frames: int,
        seed: int,
    ) -> List[LongVideoChunk]:
        """
        Converts beats to LongVideoChunk list, scheduling start/end times
        and injecting per-character reference assets.
        """
        chunks: List[LongVideoChunk] = []
        cursor = 0.0

        for beat in beats:
            dur = beat.duration_seconds
            num_frames = max(1, int(round(dur * fps)))

            # Build per-chunk prompt (scene context + beat action)
            prompt_parts = [scene_description] if scene_description else []
            if beat.action:
                prompt_parts.append(beat.action)
            if beat.dialogue:
                prompt_parts.append(f'Character says: "{beat.dialogue}"')
            chunk_prompt = ". ".join(filter(None, prompt_parts))

            # Reference assets from first active character
            ref_image: Optional[str] = None
            ref_audio: Optional[str] = None
            if beat.active_characters:
                first_char = characters.get(beat.active_characters[0])
                if first_char:
                    ref_image = first_char.reference_image_path
                    ref_audio = first_char.reference_audio_path

            chunk = LongVideoChunk(
                chunk_index=len(chunks),
                start_second=cursor,
                end_second=cursor + dur,
                duration_seconds=dur,
                num_frames=num_frames,
                prompt=chunk_prompt,
                negative_prompt="blurry, low quality, static, watermark",
                active_characters=beat.active_characters,
                dialogue=beat.dialogue,
                speaker=beat.speaker,
                reference_image_path=ref_image,
                reference_audio_path=ref_audio,
                seed=seed + len(chunks),
            )
            chunks.append(chunk)
            cursor += dur

        return chunks

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def plan_report(self, plan: LongVideoTimelinePlan) -> str:
        """Returns a human-readable plan summary string."""
        lines = [
            f"=== H3 LongVideos Plan: {plan.title} ===",
            f"Total duration : {plan.total_duration_seconds:.1f}s",
            f"FPS            : {plan.fps}",
            f"Resolution     : {plan.resolution}",
            f"Chunks         : {len(plan.chunks)}",
            f"Beats          : {len(plan.beats)}",
            f"Characters     : {list(plan.characters.keys())}",
            f"Est. VRAM/chunk: {plan.estimated_vram_gb:.1f} GB",
            f"Plan-only mode : {plan.plan_only}",
            "",
        ]
        for chunk in plan.chunks:
            lines.append(
                f"  [{chunk.chunk_index:02d}] "
                f"{chunk.start_second:.1f}s → {chunk.end_second:.1f}s "
                f"({chunk.duration_seconds:.1f}s, {chunk.num_frames} frames) "
                f"chars={chunk.active_characters}"
            )
        return "\n".join(lines)
