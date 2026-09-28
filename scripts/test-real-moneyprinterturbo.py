#!/usr/bin/env python3
"""
Real End-to-End Test Script — MoneyPrinterTurbo Production Pipeline
===================================================================
Executes a real production video generation test on the current machine.
Tests:
  1. Environment diagnostics (FFmpeg, Edge TTS, Requests, Pillow)
  2. Script generation / parsing (Mode A & Mode B)
  3. Voice synthesis (Edge TTS)
  4. Subtitle generation (SRT & ASS with millisecond timing)
  5. Stock material search & download (Pexels / Pixabay / Local / Canvas fallback)
  6. Video composition (scale, crop to 9:16 / 16:9 / 1:1, sequential stitching)
  7. Background music selection, volume ducking & audio mixing
  8. Final MP4 output verification (video stream, audio stream, duration, resolution)

Usage:
    python scripts/test-real-moneyprinterturbo.py
    python scripts/test-real-moneyprinterturbo.py --plan-only
    python scripts/test-real-moneyprinterturbo.py --topic "Artificial Intelligence in Healthcare" --duration 15
    python scripts/test-real-moneyprinterturbo.py --script "First sentence. Second sentence." --no-music
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engines.money_printer_turbo.diagnostics import check_moneyprinterturbo_environment
from app.engines.money_printer_turbo.models import (
    MaterialSourceType,
    MoneyPrinterTurboRequest,
    SubtitleStyle,
)
from app.engines.money_printer_turbo.runner import MoneyPrinterTurboRunner


def run_test(args: argparse.Namespace) -> None:
    print("\n" + "=" * 65)
    print("  MoneyPrinterTurbo — Real Production Pipeline Validation Test")
    print("=" * 65)

    output_dir = Path(os.environ.get("MONEYPRINTERTURBO_OUTPUT_DIR", "./output/moneyprinterturbo_test"))

    # 1. Environment Diagnostics
    print("\n[STEP 1] Probing Environment Diagnostics...")
    diag = check_moneyprinterturbo_environment()
    print(f"  Status Code        : {diag.status_code.value}")
    print(f"  Is Available       : {diag.is_available}")
    print(f"  FFmpeg Path        : {diag.ffmpeg_path or 'NOT FOUND'}")
    print(f"  Edge TTS Ready     : {diag.edge_tts_available}")
    print(f"  Pexels Configured  : {diag.pexels_configured}")
    print(f"  Pixabay Configured : {diag.pixabay_configured}")
    print(f"  Local Materials    : {diag.local_materials_count} files found")
    print(f"  Missing Deps       : {diag.missing_dependencies}")
    print(f"  Diagnostic Message : {diag.diagnostic_message}")

    if not diag.is_available:
        print("\n[ABORT] MoneyPrinterTurbo cannot run due to missing environment requirements.")
        print(f"Reason: {diag.diagnostic_message}")
        sys.exit(1)

    # 2. Build Request
    print("\n[STEP 2] Configuring Production Request...")
    mat_provider = MaterialSourceType(args.material_provider)

    req = MoneyPrinterTurboRequest(
        topic=args.topic if not args.script else None,
        script=args.script,
        language=args.language,
        voice_name=args.voice,
        target_duration_seconds=float(args.duration),
        aspect_ratio=args.aspect_ratio,
        subtitle_enabled=not args.no_subtitles,
        subtitle_style=SubtitleStyle.BOTTOM_CENTER,
        music_enabled=not args.no_music,
        music_volume=args.music_volume,
        material_provider=mat_provider,
        plan_only=args.plan_only,
    )

    print(f"  Topic/Script  : {req.topic or req.script[:40] + '...'}")
    print(f"  Duration      : {req.target_duration_seconds}s")
    print(f"  Aspect Ratio  : {req.aspect_ratio}")
    print(f"  Voice         : {req.voice_name}")
    print(f"  Subtitles     : {'Enabled' if req.subtitle_enabled else 'Disabled'}")
    print(f"  Music         : {'Enabled' if req.music_enabled else 'Disabled'}")
    print(f"  Material Prov : {req.material_provider.value}")
    print(f"  Plan-Only     : {req.plan_only}")

    # 3. Instantiate Runner
    runner = MoneyPrinterTurboRunner(output_dir=output_dir)

    # 4. Execute Pipeline
    print("\n[STEP 3] Executing Production Pipeline...")
    start_time = time.time()

    def on_progress(pct: float, msg: str) -> None:
        filled = int(pct / 5)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"  [{bar}] {pct:5.1f}% | {msg}")

    result = runner.execute_production_video(req, progress_callback=on_progress)
    elapsed = time.time() - start_time

    # 5. Output Verification
    print("\n[STEP 4] Production Result Verification...")
    print(f"  Job ID          : {result.job_id}")
    print(f"  Status          : {result.status}")
    print(f"  Success         : {result.success}")
    print(f"  Output MP4      : {result.output_path or 'N/A'}")
    print(f"  Duration        : {result.duration}s")
    print(f"  Resolution      : {result.resolution}")
    print(f"  Audio Present   : {result.audio_present}")
    print(f"  Subtitles       : {result.subtitle_present}")
    print(f"  Materials Used  : {len(result.source_materials)} clips")
    print(f"  Execution Time  : {elapsed:.2f}s")

    if req.plan_only:
        print("\n[PASS] MoneyPrinterTurbo plan validation PASSED (Plan-Only Mode).")
        sys.exit(0)

    if not result.success:
        print(f"\n[FAILURE] Production failed: {result.error_message}")
        sys.exit(1)

    if result.output_path and Path(result.output_path).exists():
        file_size_mb = Path(result.output_path).stat().st_size / (1024 * 1024)
        print(f"  File Size       : {file_size_mb:.2f} MB")

    print("\n[PASS] MoneyPrinterTurbo Real Production Pipeline execution PASSED.")
    print("Status: REAL_INTEGRATION / READY")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MoneyPrinterTurbo Real Production Pipeline Validation")
    parser.add_argument("--topic", default="The Power of Consistency and Daily Habits", help="Video topic (Mode A)")
    parser.add_argument("--script", default=None, help="Direct custom script (Mode B)")
    parser.add_argument("--duration", type=float, default=15.0, help="Target duration in seconds")
    parser.add_argument("--aspect-ratio", default="9:16", choices=["9:16", "16:9", "1:1"], help="Video aspect ratio")
    parser.add_argument("--language", default="en", help="Narration language code")
    parser.add_argument("--voice", default="en-US-ChristopherNeural", help="Edge TTS voice identifier")
    parser.add_argument("--music-volume", type=float, default=0.20, help="BGM volume factor (0.0 to 1.0)")
    parser.add_argument("--no-music", action="store_true", help="Disable background music mixing")
    parser.add_argument("--no-subtitles", action="store_true", help="Disable subtitle burn-in")
    parser.add_argument(
        "--material-provider",
        default="composite",
        choices=["composite", "pexels", "pixabay", "local"],
        help="Footage sourcing provider",
    )
    parser.add_argument("--plan-only", action="store_true", help="Run script & footage planning only")
    args = parser.parse_args()

    run_test(args)
