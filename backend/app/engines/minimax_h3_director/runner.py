"""
Real MiniMax H3 Director Multi-Character Narrative Runner.
Implements automated timeline cut compilation, character reference card binding,
downstream MiniMax H3 Omni-AV multi-cut generation, Level 2 visual continuity frame handoff,
and FFmpeg timeline assembly.
"""

from __future__ import annotations

import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from PIL import Image

from app.core.logging_config import logger
from app.engines.minimax_h3.models import (
    MiniMaxH3GenerationRequest,
    MiniMaxH3GenerationResult,
    MiniMaxH3TaskType,
)
from app.engines.minimax_h3.runner import MiniMaxH3InferenceRunner
from app.engines.minimax_h3_director.diagnostics import check_minimax_h3_director_environment
from app.engines.minimax_h3_director.models import (
    DirectorCharacterCard,
    DirectorShotCut,
    DirectorTimelinePlan,
    H3DirectorGenerationRequest,
    H3DirectorGenerationResult,
    H3DirectorStatusCode,
)
from app.orchestration.media_stitcher import MediaStitcher


class MiniMaxH3DirectorRunner:
    """
    Canonical Inference Runner for MiniMax H3 Director (https://github.com/muse-collective-26/MiniMaxH3-Director).
    Coordinates multi-shot narrative timelines, character reference cards, and downstream H3 diffusion generation.
    """

    def __init__(
        self,
        h3_runner: Optional[MiniMaxH3InferenceRunner] = None,
        checkpoints_dir: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
        media_stitcher: Optional[MediaStitcher] = None,
    ) -> None:
        self.checkpoints_dir = Path(
            checkpoints_dir
            or os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR")
            or "./models/minimax_h3"
        )
        self.output_dir = Path(output_dir or os.environ.get("MINIMAX_H3_DIRECTOR_OUTPUT_DIR", "./output/minimax_h3_director"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.media_stitcher = media_stitcher or MediaStitcher(output_dir=self.output_dir)
        self.h3_runner = h3_runner or MiniMaxH3InferenceRunner(
            checkpoints_dir=self.checkpoints_dir,
            output_dir=self.output_dir,
            media_stitcher=self.media_stitcher,
        )
        self._lock = threading.Lock()
        self._active_cancellations: Dict[str, threading.Event] = {}

    def plan_timeline(self, request: H3DirectorGenerationRequest) -> DirectorTimelinePlan:
        """
        Compiles the high-level prompt and character cards into a structured multi-cut timeline plan.
        """
        if request.custom_cuts:
            cuts = request.custom_cuts
            total_dur = sum(c.duration_seconds for c in cuts)
        else:
            total_dur = max(5.0, float(request.total_duration_seconds))
            cut_duration = 5.0
            num_cuts = max(1, int(total_dur / cut_duration))
            cuts = []

            char_map = {c.character_id: c for c in request.characters}
            char_ids = list(char_map.keys())

            camera_styles = [
                "wide establishing tracking shot",
                "medium character focus with subtle handheld motion",
                "cinematic close-up with shallow depth of field",
                "dynamic panning shot across the scene",
            ]

            for idx in range(num_cuts):
                start_sec = idx * cut_duration
                end_sec = min(total_dur, (idx + 1) * cut_duration)
                cam_style = camera_styles[idx % len(camera_styles)]

                # Assign active character if character cards exist
                active_chars = []
                ref_img = None
                ref_aud = None
                if char_ids:
                    char_id = char_ids[idx % len(char_ids)]
                    active_chars.append(char_id)
                    card = char_map[char_id]
                    ref_img = card.reference_image_path
                    ref_aud = card.reference_audio_path

                cut_prompt = f"{request.prompt}. Shot {idx + 1}: {cam_style}."
                if active_chars:
                    card = char_map[active_chars[0]]
                    cut_prompt += f" Featuring {card.name}: {card.description}."

                cuts.append(
                    DirectorShotCut(
                        cut_index=idx + 1,
                        start_second=start_sec,
                        end_second=end_sec,
                        duration_seconds=round(end_sec - start_sec, 2),
                        prompt=cut_prompt,
                        negative_prompt="",
                        camera_direction=cam_style,
                        active_characters=active_chars,
                        reference_image_path=ref_img,
                        reference_audio_path=ref_aud,
                        seed=request.seed + idx,
                    )
                )

        return DirectorTimelinePlan(
            title=request.title,
            total_duration_seconds=total_dur,
            fps=request.fps,
            resolution=request.resolution,
            cuts=cuts,
            characters={c.character_id: c for c in request.characters},
        )

    def execute_generation(
        self,
        request: H3DirectorGenerationRequest,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> H3DirectorGenerationResult:
        """
        Executes real MiniMax H3 Director multi-cut generation workflow.
        """
        job_id = request.job_id or str(uuid.uuid4())
        cancel_event = threading.Event()
        self._active_cancellations[job_id] = cancel_event

        start_time = time.time()
        logger.info(f"Starting MiniMax H3 Director execution [Job {job_id}] for story: '{request.prompt[:60]}...'")

        try:
            # 1. Diagnostic Verification
            diag = check_minimax_h3_director_environment(checkpoints_dir=self.checkpoints_dir)
            if not diag.is_available:
                return H3DirectorGenerationResult(
                    job_id=job_id,
                    status=diag.status_code.value,
                    success=False,
                    error_message=diag.diagnostic_message,
                    error_code=diag.status_code.value,
                )

            # 2. Compile Timeline Plan
            if progress_callback:
                progress_callback(5.0, "Compiling multi-cut timeline plan and character cards...")

            plan = self.plan_timeline(request)
            num_cuts = len(plan.cuts)
            logger.info(f"H3 Director compiled {num_cuts} cuts for total duration {plan.total_duration_seconds}s")

            res_str = request.resolution
            width, height = 1024, 576
            if "*" in res_str:
                parts = res_str.split("*")
                width, height = int(parts[0]), int(parts[1])
            elif "x" in res_str:
                parts = res_str.split("x")
                width, height = int(parts[0]), int(parts[1])

            cut_results: List[Dict[str, Any]] = []
            cut_video_paths: List[Path] = []
            previous_last_frame: Optional[str] = None

            # 3. Generate Each Shot / Cut
            for idx, cut in enumerate(plan.cuts):
                if cancel_event.is_set():
                    raise RuntimeError("H3_DIRECTOR_CANCELLED_BY_USER")

                cut_pct_base = 10.0 + (float(idx) / float(num_cuts) * 75.0)
                if progress_callback:
                    progress_callback(cut_pct_base, f"Generating Cut {cut.cut_index}/{num_cuts}: {cut.prompt[:40]}...")

                cut_frames = int(cut.duration_seconds * request.fps)

                # Reference assets
                ref_images = []
                if cut.reference_image_path and Path(cut.reference_image_path).exists():
                    ref_images.append(cut.reference_image_path)

                ref_audios = []
                if cut.reference_audio_path and Path(cut.reference_audio_path).exists():
                    ref_audios.append(cut.reference_audio_path)

                # Determine conditioning task type
                task_type = MiniMaxH3TaskType.T2VA
                image_start = None
                if request.enable_visual_continuity and previous_last_frame and Path(previous_last_frame).exists():
                    image_start = previous_last_frame
                    task_type = MiniMaxH3TaskType.FL2VA
                    logger.info(f"Cut {cut.cut_index} applying Level 2 continuity frame: {previous_last_frame}")
                elif ref_images or ref_audios:
                    task_type = MiniMaxH3TaskType.REF2VA

                cut_req = MiniMaxH3GenerationRequest(
                    prompt=cut.prompt,
                    negative_prompt=cut.negative_prompt,
                    task_type=task_type,
                    width=width,
                    height=height,
                    num_frames=cut_frames,
                    fps=request.fps,
                    num_inference_steps=request.num_inference_steps,
                    guidance_scale=request.guidance_scale,
                    seed=cut.seed,
                    generate_audio=request.generate_audio,
                    image_start=image_start,
                    reference_images=ref_images,
                    reference_audios=ref_audios,
                    job_id=f"{job_id}_cut_{cut.cut_index}",
                )

                def _cut_prog_bridge(pct: float, detail: str):
                    if progress_callback:
                        overall = cut_pct_base + (pct / 100.0) * (75.0 / float(num_cuts))
                        progress_callback(overall, f"Cut {cut.cut_index}/{num_cuts}: {detail}")

                h3_res: MiniMaxH3GenerationResult = self.h3_runner.execute_generation(
                    request=cut_req,
                    progress_callback=_cut_prog_bridge,
                )

                if not h3_res.success:
                    return H3DirectorGenerationResult(
                        job_id=job_id,
                        status="FAILED",
                        success=False,
                        error_message=f"Generation failed at Cut {cut.cut_index}: {h3_res.error_message}",
                        error_code=h3_res.error_code or "H3_DIRECTOR_CUT_FAILED",
                    )

                cut_vid = Path(h3_res.combined_media_path or h3_res.video_path)
                cut_video_paths.append(cut_vid)
                cut_results.append({
                    "cut_index": cut.cut_index,
                    "prompt": cut.prompt,
                    "duration": h3_res.duration,
                    "video_path": str(cut_vid.resolve()),
                    "audio_path": h3_res.audio_path,
                    "has_audio": h3_res.has_audio,
                })

                # Extract last frame for Level 2 visual continuity
                if request.enable_visual_continuity and cut_vid.exists():
                    try:
                        frame_out = self.output_dir / f"{job_id}_cut_{cut.cut_index}_last_frame.png"
                        self.media_stitcher.extract_last_frame(
                            video_path=cut_vid,
                            output_image_path=frame_out,
                        )
                        if frame_out.exists():
                            previous_last_frame = str(frame_out.resolve())
                    except Exception as frame_err:
                        logger.warning(f"Could not extract last frame for continuity: {frame_err}")
                        previous_last_frame = None

            if cancel_event.is_set():
                raise RuntimeError("H3_DIRECTOR_CANCELLED_BY_USER")

            # 4. Stitch All Cuts into Final Video
            if progress_callback:
                progress_callback(88.0, "Stitching directed cuts into final cinematic sequence...")

            final_video_path = (
                Path(request.output_video_path)
                if request.output_video_path
                else self.output_dir / f"h3_director_{job_id}_final.mp4"
            )

            if len(cut_video_paths) == 1:
                # Single cut, copy directly
                import shutil
                shutil.copy2(cut_video_paths[0], final_video_path)
            else:
                self.media_stitcher.stitch_scenes(
                    scene_paths=cut_video_paths,
                    output_path=final_video_path,
                )

            elapsed = time.time() - start_time
            logger.info(f"H3 Director finished in {elapsed:.2f}s: {final_video_path}")

            if progress_callback:
                progress_callback(100.0, "Directed video generation complete.")

            return H3DirectorGenerationResult(
                job_id=job_id,
                status="COMPLETED",
                success=True,
                video_path=str(final_video_path.resolve()),
                combined_media_path=str(final_video_path.resolve()),
                output_paths=[str(final_video_path.resolve())],
                scenes=cut_results,
                duration=round(plan.total_duration_seconds, 2),
                width=width,
                height=height,
                fps=request.fps,
                metadata={
                    "total_cuts": num_cuts,
                    "title": plan.title,
                    "elapsed_seconds": round(elapsed, 2),
                    "visual_continuity_enabled": request.enable_visual_continuity,
                    "downstream_engine": "minimax-h3",
                },
            )

        except Exception as exc:
            error_str = str(exc)
            if "H3_DIRECTOR_CANCELLED_BY_USER" in error_str:
                return H3DirectorGenerationResult(
                    job_id=job_id,
                    status="CANCELLED",
                    success=False,
                    error_message="Generation was cancelled by user.",
                    error_code="H3_DIRECTOR_CANCELLED",
                )

            logger.error(f"H3 Director generation failed [Job {job_id}]: {exc}", exc_info=True)
            return H3DirectorGenerationResult(
                job_id=job_id,
                status="FAILED",
                success=False,
                error_message=f"H3 Director execution failed: {error_str}",
                error_code="H3_DIRECTOR_FAILED",
            )
        finally:
            self._active_cancellations.pop(job_id, None)

    def cancel(self, job_id: str) -> bool:
        """Cancels running generation job."""
        event = self._active_cancellations.get(job_id)
        if event:
            event.set()
            self.h3_runner.cancel(job_id)
            logger.info(f"Cancelled H3 Director job {job_id}.")
            return True
        return False

    def unload(self) -> None:
        """Unloads runner and downstream models."""
        with self._lock:
            self.h3_runner.unload()
            logger.info("H3 Director runner unloaded.")
