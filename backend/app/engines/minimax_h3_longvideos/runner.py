"""
Real MiniMax H3 LongVideos Inference Runner.

Executes sliding-window multi-chunk long video generation using MiniMax H3 Omni-AV
as the per-chunk backbone, with:
  - Beat-based chunk planning via H3LongVideoPlanner
  - FL2VA visual continuity frame handoff via H3LongVideoContinuityCoordinator
  - Per-chunk audio generation (native 32kHz stereo) with cross-fade concatenation
  - Per-shot checkpointing and resume-on-failure
  - FFmpeg-based final timeline stitching via MediaStitcher

Upstream architecture reference:
  Smite79/MiniMax-H3-Longvideos (HuggingFace, ComfyUI custom nodes)
  Canonical MiniMax H3 Omni-AV: https://github.com/MiniMax-AI/MiniMax-H3

Implementation note:
  This runner is a standalone Python implementation. It does not reproduce ComfyUI
  node wiring or the upstream custom node code. It implements the same documented
  sliding-window orchestration pattern using our own planner/continuity modules.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional
import uuid

from app.core.logging_config import logger
from app.engines.minimax_h3.models import (
    MiniMaxH3GenerationRequest,
    MiniMaxH3TaskType,
)
from app.engines.minimax_h3.runner import MiniMaxH3InferenceRunner
from app.engines.minimax_h3_longvideos.continuity import H3LongVideoContinuityCoordinator
from app.engines.minimax_h3_longvideos.diagnostics import check_h3_longvideo_environment
from app.engines.minimax_h3_longvideos.models import (
    H3LongVideoGenerationRequest,
    H3LongVideoGenerationResult,
    H3LongVideoStatusCode,
    LongVideoChunk,
)
from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
from app.orchestration.media_stitcher import MediaStitcher


class MiniMaxH3LongVideoRunner:
    """
    Canonical Inference Runner for MiniMax H3 LongVideos.

    Orchestrates multi-chunk sliding-window video generation:
      plan → [chunk_0 → extract_frame → chunk_1 → extract_frame → ... → chunk_N]
      → crossfade audio → FFmpeg stitch → final MP4
    """

    def __init__(
        self,
        h3_runner: Optional[MiniMaxH3InferenceRunner] = None,
        checkpoints_dir: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
        media_stitcher: Optional[MediaStitcher] = None,
        planner: Optional[H3LongVideoPlanner] = None,
    ) -> None:
        self.checkpoints_dir = Path(
            checkpoints_dir
            or os.environ.get("MINIMAX_H3_MODEL_PATH")
            or os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR")
            or "./models/minimax_h3"
        )
        self.output_dir = Path(
            output_dir
            or os.environ.get("MINIMAX_H3_LONGVIDEO_OUTPUT_DIR", "./output/minimax_h3_longvideos")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.media_stitcher = media_stitcher or MediaStitcher(output_dir=self.output_dir)
        self.h3_runner = h3_runner or MiniMaxH3InferenceRunner(
            checkpoints_dir=self.checkpoints_dir,
            output_dir=self.output_dir,
            media_stitcher=self.media_stitcher,
        )
        self.planner = planner or H3LongVideoPlanner()

        self._lock = threading.Lock()
        self._active_cancellations: Dict[str, threading.Event] = {}

    # ------------------------------------------------------------------
    # GPU readiness
    # ------------------------------------------------------------------

    def is_gpu_ready(self) -> tuple[bool, str]:
        """Verify if CUDA hardware, VRAM, and dependencies are ready."""
        diag = check_h3_longvideo_environment(checkpoints_dir=self.checkpoints_dir)
        return diag.is_available, diag.diagnostic_message

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute_long_video(
        self,
        request: H3LongVideoGenerationRequest,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> H3LongVideoGenerationResult:
        """
        Executes full sliding-window long video generation.
        Returns H3LongVideoGenerationResult on completion.
        """
        job_id = request.job_id or str(uuid.uuid4())
        cancel_event = threading.Event()
        self._active_cancellations[job_id] = cancel_event
        start_time = time.time()

        logger.info(
            f"[H3LongVideo] Starting job {job_id} | "
            f"'{request.title}' | prompt: '{request.prompt[:60]}...'"
        )

        try:
            # 1. Environment check
            diag = check_h3_longvideo_environment(checkpoints_dir=self.checkpoints_dir)
            if not diag.is_available:
                return H3LongVideoGenerationResult(
                    job_id=job_id,
                    status=diag.status_code.value,
                    success=False,
                    error_message=diag.diagnostic_message,
                )

            # 2. Plan
            if progress_callback:
                progress_callback(2.0, "Building sliding-window chunk plan...")

            plan = self.planner.plan(request)
            logger.info(self.planner.plan_report(plan))

            # Plan-only mode: return plan without executing
            if request.plan_only:
                return H3LongVideoGenerationResult(
                    job_id=job_id,
                    status="PLAN_COMPLETE",
                    success=True,
                    plan_only=True,
                    plan=self._plan_to_dict(plan),
                    chunks=[
                        {"chunk_index": c.chunk_index, "start": c.start_second,
                         "end": c.end_second, "duration": c.duration_seconds,
                         "prompt": c.prompt[:80]}
                        for c in plan.chunks
                    ],
                    execution_time_seconds=round(time.time() - start_time, 2),
                )

            if not plan.chunks:
                return H3LongVideoGenerationResult(
                    job_id=job_id,
                    status="FAILED",
                    success=False,
                    error_message="No chunks generated by planner. Check prompt or beats_text.",
                )

            # 3. Per-job output directory
            job_dir = self.output_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            # Save plan to disk
            plan_file = job_dir / "plan.json"
            with open(plan_file, "w") as f:
                json.dump(self._plan_to_dict(plan), f, indent=2, default=str)

            # 4. Continuity coordinator
            continuity = H3LongVideoContinuityCoordinator(
                output_dir=job_dir,
                audio_crossfade_duration_seconds=request.audio_crossfade_duration_seconds,
            )

            # 5. Execute chunks sequentially with frame handoff
            completed_chunks: List[Dict[str, Any]] = []
            chunk_video_paths: List[str] = []
            chunk_audio_paths: List[str] = []
            previous_frame_path: Optional[str] = None

            total_chunks = len(plan.chunks)

            for idx, chunk in enumerate(plan.chunks):
                if cancel_event.is_set():
                    logger.info(f"[H3LongVideo] Job {job_id} cancelled at chunk {idx}.")
                    return H3LongVideoGenerationResult(
                        job_id=job_id,
                        status="CANCELLED",
                        success=False,
                        error_message=f"Cancelled at chunk {idx}/{total_chunks}.",
                        chunks=completed_chunks,
                    )

                chunk_pct_start = 5.0 + (idx / total_chunks) * 80.0
                chunk_pct_end = 5.0 + ((idx + 1) / total_chunks) * 80.0

                if progress_callback:
                    progress_callback(
                        chunk_pct_start,
                        f"Generating chunk {idx + 1}/{total_chunks} "
                        f"({chunk.start_second:.1f}s–{chunk.end_second:.1f}s)...",
                    )

                # Check for resume: skip if chunk output already exists
                existing_state = continuity.load_chunk_state(idx, job_dir)
                if (
                    existing_state
                    and existing_state.get("success")
                    and existing_state.get("video_path")
                    and Path(existing_state["video_path"]).exists()
                ):
                    logger.info(
                        f"[H3LongVideo] Resuming job {job_id}: chunk {idx} already complete."
                    )
                    chunk.output_video_path = existing_state["video_path"]
                    chunk.output_audio_path = existing_state.get("audio_path")
                    previous_frame_path = existing_state.get("final_frame_path")
                    if chunk.output_video_path:
                        chunk_video_paths.append(chunk.output_video_path)
                    if chunk.output_audio_path:
                        chunk_audio_paths.append(chunk.output_audio_path)
                    completed_chunks.append(self._chunk_to_dict(chunk, success=True))
                    continue

                # Apply visual continuity conditioning
                if request.enable_visual_continuity and previous_frame_path:
                    chunk = continuity.apply_conditioning_to_chunk(chunk, previous_frame_path)

                # Execute this chunk
                chunk_result = self._execute_single_chunk(
                    chunk=chunk,
                    plan=plan,
                    request=request,
                    job_dir=job_dir,
                    job_id=job_id,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                    pct_start=chunk_pct_start,
                    pct_end=chunk_pct_end,
                )

                if not chunk_result.get("success"):
                    logger.error(
                        f"[H3LongVideo] Chunk {idx} failed: {chunk_result.get('error')}"
                    )
                    # Save failure state for potential retry
                    continuity.save_chunk_state(chunk, {"success": False, "error": chunk_result.get("error")}, job_dir)
                    # Continue to next chunk rather than aborting entire job
                    completed_chunks.append(chunk_result)
                    continue

                # Record outputs
                if chunk_result.get("video_path"):
                    chunk_video_paths.append(chunk_result["video_path"])
                    chunk.output_video_path = chunk_result["video_path"]
                if chunk_result.get("audio_path"):
                    chunk_audio_paths.append(chunk_result["audio_path"])
                    chunk.output_audio_path = chunk_result["audio_path"]

                # Extract final frame for next chunk conditioning
                if request.enable_visual_continuity and chunk.output_video_path:
                    previous_frame_path = continuity.extract_final_frame(
                        chunk.output_video_path, idx
                    )
                    chunk_result["final_frame_path"] = previous_frame_path

                # Checkpoint
                continuity.save_chunk_state(chunk, chunk_result, job_dir)
                completed_chunks.append(chunk_result)

            if progress_callback:
                progress_callback(87.0, "Stitching audio segments with crossfade...")

            # 6. Audio concatenation with crossfade
            combined_audio_path: Optional[str] = None
            if chunk_audio_paths and request.generate_audio:
                audio_out = job_dir / f"{job_id}_combined_audio.wav"
                combined_audio_path = continuity.crossfade_and_concat_audio(
                    chunk_audio_paths, audio_out
                )

            if progress_callback:
                progress_callback(92.0, "Stitching video chunks into final timeline...")

            # 7. Video stitching
            final_video_path = job_dir / f"{job_id}_final.mp4"
            valid_video_paths = [p for p in chunk_video_paths if p and Path(p).exists()]

            if not valid_video_paths:
                return H3LongVideoGenerationResult(
                    job_id=job_id,
                    status="FAILED",
                    success=False,
                    error_message="No completed chunk videos to stitch.",
                    chunks=completed_chunks,
                    plan=self._plan_to_dict(plan),
                    execution_time_seconds=round(time.time() - start_time, 2),
                )

            stitched_video = self._stitch_video_chunks(
                video_paths=valid_video_paths,
                output_path=final_video_path,
                audio_path=combined_audio_path,
            )

            if progress_callback:
                progress_callback(100.0, "Long video generation complete.")

            elapsed = round(time.time() - start_time, 2)
            logger.info(f"[H3LongVideo] Job {job_id} complete in {elapsed}s → {stitched_video}")

            return H3LongVideoGenerationResult(
                job_id=job_id,
                status="COMPLETED",
                success=True,
                video_path=stitched_video,
                audio_path=combined_audio_path,
                combined_media_path=stitched_video,
                output_paths=[stitched_video] if stitched_video else [],
                chunks=completed_chunks,
                plan=self._plan_to_dict(plan),
                execution_time_seconds=elapsed,
                telemetry={
                    "total_chunks": total_chunks,
                    "successful_chunks": sum(1 for c in completed_chunks if c.get("success")),
                    "audio_segments": len(chunk_audio_paths),
                    "visual_continuity_enabled": request.enable_visual_continuity,
                    "audio_crossfade_enabled": request.enable_audio_crossfade,
                },
            )

        except Exception as exc:
            logger.error(f"[H3LongVideo] Job {job_id} failed: {exc}", exc_info=True)
            return H3LongVideoGenerationResult(
                job_id=job_id,
                status="FAILED",
                success=False,
                error_message=str(exc),
                execution_time_seconds=round(time.time() - start_time, 2),
            )
        finally:
            self._active_cancellations.pop(job_id, None)

    # ------------------------------------------------------------------
    # Single-chunk execution
    # ------------------------------------------------------------------

    def _execute_single_chunk(
        self,
        chunk: LongVideoChunk,
        plan: Any,
        request: H3LongVideoGenerationRequest,
        job_dir: Path,
        job_id: str,
        cancel_event: threading.Event,
        progress_callback: Optional[Callable[[float, str], None]],
        pct_start: float,
        pct_end: float,
    ) -> Dict[str, Any]:
        """Executes a single chunk using the downstream MiniMaxH3InferenceRunner."""
        chunk_video_path = str(job_dir / f"chunk_{chunk.chunk_index:04d}.mp4")
        chunk_audio_path = str(job_dir / f"chunk_{chunk.chunk_index:04d}.wav")

        def chunk_progress(pct: float, msg: str) -> None:
            if progress_callback and not cancel_event.is_set():
                mapped = pct_start + (pct / 100.0) * (pct_end - pct_start)
                progress_callback(mapped, f"[chunk {chunk.chunk_index}] {msg}")

        h3_request = MiniMaxH3GenerationRequest(
            prompt=chunk.prompt,
            negative_prompt=chunk.negative_prompt,
            num_inference_steps=request.num_inference_steps,
            guidance_scale=request.guidance_scale,
            width=self._parse_resolution_w(plan.resolution),
            height=self._parse_resolution_h(plan.resolution),
            num_frames=chunk.num_frames,
            fps=plan.fps,
            seed=chunk.seed,
            generate_audio=request.generate_audio,
            image_start=chunk.conditioning_image_path,
            reference_images=[chunk.reference_image_path] if chunk.reference_image_path else [],
            reference_audios=[chunk.reference_audio_path] if chunk.reference_audio_path else [],
            output_video_path=chunk_video_path,
            output_audio_path=chunk_audio_path,
            job_id=f"{job_id}_chunk_{chunk.chunk_index:04d}",
            task_type=MiniMaxH3TaskType.FL2VA if chunk.conditioning_image_path else MiniMaxH3TaskType.T2VA,
            model_type="minimax-h3-v1",
        )

        result = self.h3_runner.execute_generation(h3_request, progress_callback=chunk_progress)

        return {
            "chunk_index": chunk.chunk_index,
            "start_second": chunk.start_second,
            "end_second": chunk.end_second,
            "success": result.success,
            "video_path": result.video_path,
            "audio_path": result.audio_path,
            "error": result.error_message if not result.success else None,
            "status": result.status,
        }

    # ------------------------------------------------------------------
    # Video stitching
    # ------------------------------------------------------------------

    def _stitch_video_chunks(
        self,
        video_paths: List[str],
        output_path: Path,
        audio_path: Optional[str],
    ) -> Optional[str]:
        """Concatenates chunk videos using FFmpeg concat demuxer via MediaStitcher."""
        try:
            return self.media_stitcher.stitch_video_segments(
                video_paths=video_paths,
                output_path=str(output_path),
                audio_path=audio_path,
            )
        except Exception as e:
            logger.warning(f"[H3LongVideo] MediaStitcher stitch failed: {e}. Trying FFmpeg direct...")
            return self._ffmpeg_concat(video_paths, output_path)

    def _ffmpeg_concat(
        self,
        video_paths: List[str],
        output_path: Path,
    ) -> Optional[str]:
        """Direct FFmpeg concat demuxer fallback."""
        try:
            import subprocess
            import tempfile

            concat_file = output_path.parent / "concat_list.txt"
            with open(concat_file, "w") as f:
                for p in video_paths:
                    f.write(f"file '{p}'\n")

            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c", "copy",
                    str(output_path),
                ],
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0 and output_path.exists():
                return str(output_path)
            logger.error(f"FFmpeg concat failed: {result.stderr.decode()[:500]}")
            return None
        except Exception as e:
            logger.error(f"[H3LongVideo] FFmpeg concat exception: {e}")
            return None

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self, job_id: str) -> bool:
        """Signals cancellation for a running long video job."""
        event = self._active_cancellations.get(job_id)
        if event:
            event.set()
            logger.info(f"[H3LongVideo] Cancelled job {job_id}.")
            return True
        return False

    def shutdown(self) -> None:
        """Graceful shutdown."""
        try:
            self.h3_runner.unload()
        except Exception:
            pass
        logger.info("[H3LongVideo] Runner shut down.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_resolution_w(resolution: str) -> int:
        try:
            return int(resolution.split("*")[0].strip())
        except Exception:
            return 1024

    @staticmethod
    def _parse_resolution_h(resolution: str) -> int:
        try:
            return int(resolution.split("*")[1].strip())
        except Exception:
            return 576

    @staticmethod
    def _plan_to_dict(plan: Any) -> Dict[str, Any]:
        return {
            "title": plan.title,
            "scene_description": plan.scene_description,
            "total_duration_seconds": plan.total_duration_seconds,
            "fps": plan.fps,
            "resolution": plan.resolution,
            "num_chunks": len(plan.chunks),
            "num_beats": len(plan.beats),
            "characters": list(plan.characters.keys()),
            "estimated_vram_gb": plan.estimated_vram_gb,
            "plan_only": plan.plan_only,
        }

    @staticmethod
    def _chunk_to_dict(chunk: LongVideoChunk, success: bool = True) -> Dict[str, Any]:
        return {
            "chunk_index": chunk.chunk_index,
            "start_second": chunk.start_second,
            "end_second": chunk.end_second,
            "duration_seconds": chunk.duration_seconds,
            "success": success,
            "video_path": chunk.output_video_path,
            "audio_path": chunk.output_audio_path,
            "active_characters": chunk.active_characters,
        }
