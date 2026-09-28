#!/usr/bin/env python3
"""
Real GPU Test Script — MiniMax H3 LongVideos
=============================================
Executes a real end-to-end long video generation test on a machine with
an NVIDIA CUDA GPU and the required MiniMax H3 model weights.

This script MUST be run on hardware with:
  - NVIDIA GPU with >= 24 GB VRAM (48 GB recommended)
  - CUDA 12.x
  - MiniMax H3 checkpoints in MINIMAX_H3_CHECKPOINTS_DIR

DO NOT run this script on a machine without a GPU. It will report
GPU-UNVERIFIED status and exit without executing inference.

Usage:
    python scripts/test-real-minimax-h3-longvideo.py
    python scripts/test-real-minimax-h3-longvideo.py --plan-only
    python scripts/test-real-minimax-h3-longvideo.py --duration 30 --chunks 6
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engines.minimax_h3_longvideos.diagnostics import check_h3_longvideo_environment
from app.engines.minimax_h3_longvideos.models import (
    H3LongVideoGenerationRequest,
    LongVideoCharacterCard,
)
from app.engines.minimax_h3_longvideos.runner import MiniMaxH3LongVideoRunner


# ---------------------------------------------------------------------------
# Test prompt
# ---------------------------------------------------------------------------

TEST_SCENE = "A cinematic mountain landscape at golden hour, dramatic lighting, photorealistic."

TEST_BEATS = """\
A cinematic mountain landscape at golden hour, dramatic lighting, photorealistic.

A lone explorer stands at the edge of a cliff, gazing at the horizon.
"The journey has just begun," she whispers.

She turns and begins to walk along the ridge, the wind catching her coat.

The camera pulls back to reveal the vast, snow-capped mountain range stretching to the horizon.
"""

TEST_CHARACTERS = [
    LongVideoCharacterCard(
        character_id="explorer",
        name="Elena",
        description="A courageous explorer in a weathered brown coat. Mid-30s, determined expression.",
    )
]


def run_test(args: argparse.Namespace) -> None:
    print("\n" + "=" * 60)
    print("  MiniMax H3 LongVideos — Real GPU Validation Test")
    print("=" * 60)

    checkpoints_dir = os.environ.get("MINIMAX_H3_CHECKPOINTS_DIR", "./models/minimax_h3")
    output_dir = os.environ.get("MINIMAX_H3_LONGVIDEO_OUTPUT_DIR", "./output/minimax_h3_longvideos_test")

    # 1. Environment check
    print("\n[STEP 1] Environment Diagnostics")
    diag = check_h3_longvideo_environment(checkpoints_dir=checkpoints_dir)
    print(f"  Status Code        : {diag.status_code.value}")
    print(f"  Is Available       : {diag.is_available}")
    print(f"  GPU Name           : {diag.gpu_name or 'N/A'}")
    print(f"  VRAM Total         : {diag.vram_total_gb:.1f} GB")
    print(f"  VRAM Available     : {diag.vram_available_gb:.1f} GB")
    print(f"  CUDA Version       : {diag.cuda_version or 'N/A'}")
    print(f"  PyTorch            : {diag.pytorch_version or 'N/A'}")
    print(f"  Models Found       : {diag.models_found}")
    print(f"  Missing Deps       : {diag.missing_dependencies}")
    print(f"  Downstream H3      : {diag.downstream_h3_available}")
    print(f"  Max Feasible Chunks: {diag.max_feasible_chunks}")
    print(f"  Message            : {diag.diagnostic_message}")

    if not diag.is_available:
        print("\n[ABORT] H3 LongVideos is not available on this machine.")
        print("  This is expected on a machine without a CUDA GPU or model weights.")
        print("  Status: REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED")
        sys.exit(0)

    # 2. Build request
    print(f"\n[STEP 2] Building generation request")
    print(f"  Duration : {args.duration}s")
    print(f"  Chunks   : ~{int(args.duration / args.chunk_duration)}")
    print(f"  Plan only: {args.plan_only}")

    runner = MiniMaxH3LongVideoRunner(
        checkpoints_dir=checkpoints_dir,
        output_dir=output_dir,
    )

    request = H3LongVideoGenerationRequest(
        prompt=TEST_SCENE,
        scene_description=TEST_SCENE,
        beats_text=TEST_BEATS if not args.no_beats else None,
        characters=TEST_CHARACTERS,
        title="H3 LongVideos GPU Validation",
        total_duration_seconds=float(args.duration),
        chunk_duration_seconds=float(args.chunk_duration),
        fps=25,
        resolution=args.resolution,
        num_inference_steps=args.steps,
        guidance_scale=5.0,
        seed=42,
        generate_audio=not args.no_audio,
        enable_visual_continuity=True,
        enable_audio_crossfade=True,
        plan_only=args.plan_only,
    )

    # 3. Plan report
    print("\n[STEP 3] Planning chunks")
    from app.engines.minimax_h3_longvideos.planner import H3LongVideoPlanner
    planner = H3LongVideoPlanner(fps=request.fps)
    plan = planner.plan(request)
    print(planner.plan_report(plan))

    if args.plan_only:
        print("\n[RESULT] Plan-only mode. No inference executed.")
        print("Status: REAL_INTEGRATION / GPU-READY / GPU-UNVERIFIED (plan validated)")
        sys.exit(0)

    # 4. Execute
    print("\n[STEP 4] Executing long video generation...")
    start = time.time()

    def on_progress(pct: float, msg: str) -> None:
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  [{bar}] {pct:5.1f}%  {msg}")

    result = runner.execute_long_video(request, progress_callback=on_progress)

    elapsed = time.time() - start

    # 5. Report
    print("\n[STEP 5] Result")
    print(f"  Job ID      : {result.job_id}")
    print(f"  Status      : {result.status}")
    print(f"  Success     : {result.success}")
    print(f"  Video Path  : {result.video_path or 'N/A'}")
    print(f"  Audio Path  : {result.audio_path or 'N/A'}")
    print(f"  Chunks done : {len([c for c in result.chunks if c.get('success')])}/{len(result.chunks)}")
    print(f"  Elapsed     : {elapsed:.2f}s")

    if not result.success:
        print(f"\n[FAILURE] {result.error_message}")
        sys.exit(1)

    if result.video_path and Path(result.video_path).exists():
        size_mb = Path(result.video_path).stat().st_size / (1024 * 1024)
        print(f"  Output size : {size_mb:.2f} MB")

    print("\n[PASS] MiniMax H3 LongVideos GPU validation PASSED.")
    print("Status: REAL_INTEGRATION / GPU-VERIFIED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MiniMax H3 LongVideos Real GPU Test")
    parser.add_argument("--duration", type=float, default=15.0, help="Total video duration in seconds")
    parser.add_argument("--chunk-duration", type=float, default=5.0, help="Per-chunk duration in seconds")
    parser.add_argument("--resolution", default="1024*576", help="Resolution (WxH, e.g. 1024*576)")
    parser.add_argument("--steps", type=int, default=20, help="Inference steps (lower = faster test)")
    parser.add_argument("--no-audio", action="store_true", help="Skip audio generation")
    parser.add_argument("--no-beats", action="store_true", help="Use simple prompt (skip beats parsing)")
    parser.add_argument("--plan-only", action="store_true", help="Only generate plan, no inference")
    args = parser.parse_args()

    run_test(args)
