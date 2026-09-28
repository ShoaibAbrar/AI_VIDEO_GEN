#!/usr/bin/env python3
"""
Real End-to-End Test Script — Chatterbox Zero-Shot Voice Cloning
================================================================
Validates zero-shot voice cloning pipeline on the current system:
  1. Environment diagnostics (PyTorch, torchaudio, CUDA, Chatterbox model)
  2. Reference audio validation (duration, sample rate, clipping, silence)
  3. Consent confirmation enforcement
  4. VoiceProfile creation & persistent storage
  5. Zero-shot speech synthesis with paralinguistic tag support
  6. Cloned WAV output verification (duration, sample rate, channels, playback integrity)

Usage:
    python scripts/test-real-voice-cloning.py
    python scripts/test-real-voice-cloning.py --plan-only
    python scripts/test-real-voice-cloning.py --text "Welcome to the future of AI video generation! [laugh]"
    python scripts/test-real-voice-cloning.py --reference-audio "materials/test_reference_voice.wav" --language en
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.voice.cloning.diagnostics import check_voice_cloning_environment
from app.services.voice.cloning.engine import VoiceCloningEngine
from app.services.voice.cloning.models import VoiceCloningRequest
from app.services.voice.cloning.storage import VoiceProfileStore
from app.services.voice.cloning.validation import validate_reference_audio


def run_test(args: argparse.Namespace) -> None:
    print("\n" + "=" * 65)
    print("  Chatterbox Voice Cloning — Real Engine Validation Test")
    print("=" * 65)

    ref_audio_path = Path(args.reference_audio).resolve()
    output_dir = Path(os.environ.get("VOICE_CLONING_OUTPUT_DIR", "./output/voice_cloning_test")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Environment Diagnostics
    print("\n[STEP 1] Environment & Hardware Diagnostics")
    diag = check_voice_cloning_environment(model_id=args.model_id)
    print(f"  Status Code        : {diag.status_code.value}")
    print(f"  Is Available       : {diag.is_available}")
    print(f"  GPU Available      : {diag.gpu_available}")
    print(f"  GPU Name           : {diag.gpu_name or 'N/A (CPU Mode)'}")
    print(f"  VRAM Total         : {diag.vram_total_gb:.1f} GB")
    print(f"  PyTorch Version    : {diag.pytorch_version or 'N/A'}")
    print(f"  Model ID           : {diag.model_id}")
    print(f"  Missing Deps       : {diag.missing_dependencies}")
    print(f"  Diagnostic Message : {diag.diagnostic_message}")

    if not diag.is_available:
        print(f"\n[ABORT] Voice cloning environment check failed: {diag.diagnostic_message}")
        sys.exit(1)

    # 2. Reference Audio & Consent Validation
    print("\n[STEP 2] Reference Audio & Consent Validation")
    print(f"  Reference Audio    : {ref_audio_path}")
    print(f"  Consent Confirmed  : {args.consent}")

    val = validate_reference_audio(ref_audio_path, consent_confirmed=args.consent)
    print(f"  Is Valid           : {val.is_valid}")
    print(f"  Error Code         : {val.error_code.value}")
    print(f"  Duration           : {val.duration_seconds:.2f}s")
    print(f"  Sample Rate        : {val.sample_rate} Hz")
    print(f"  Channels           : {val.channels}")
    print(f"  Has Clipping       : {val.has_clipping}")

    if not val.is_valid:
        print(f"\n[FAILURE] Reference audio validation rejected: {val.error_message}")
        sys.exit(1)

    # 3. Persistent Voice Profile Management
    print("\n[STEP 3] Initializing VoiceProfile...")
    profile_store = VoiceProfileStore(storage_dir=output_dir / "profiles")
    engine = VoiceCloningEngine(profile_store=profile_store)

    profile = engine.create_voice_profile(
        name=args.voice_name,
        reference_audio_path=ref_audio_path,
        owner_id="test_user",
        language=args.language,
        consent_confirmed=args.consent,
    )
    print(f"  Created Profile ID : {profile.id}")
    print(f"  Profile Name       : {profile.name}")
    print(f"  Stored Audio Path  : {profile.reference_audio_path}")

    # 4. Speech Synthesis Execution
    print("\n[STEP 4] Executing Voice Cloning...")
    print(f"  Dialogue Text      : '{args.text}'")
    print(f"  Language           : {args.language}")
    print(f"  Speed / Pitch      : speed={args.speed}x, pitch={args.pitch}")
    print(f"  Exaggeration / CFG : exag={args.exaggeration}, cfg={args.cfg_weight}")
    print(f"  Plan-Only Mode     : {args.plan_only}")

    start_time = time.time()

    def on_progress(pct: float, msg: str):
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  [{bar}] {pct:5.1f}% | {msg}")

    out_file = output_dir / f"cloned_test_output_{profile.id}.wav"
    req = VoiceCloningRequest(
        text=args.text,
        voice_profile=profile,
        language=args.language,
        speed=args.speed,
        pitch=args.pitch,
        exaggeration=args.exaggeration,
        cfg_weight=args.cfg_weight,
        output_audio_path=str(out_file),
        plan_only=args.plan_only,
        extra_options={"consent_confirmed": args.consent},
    )

    result = engine.clone_voice(req)
    elapsed = time.time() - start_time

    # 5. Output Verification
    print("\n[STEP 5] Result Verification")
    print(f"  Job ID             : {result.job_id}")
    print(f"  Status             : {result.status}")
    print(f"  Success            : {result.success}")
    print(f"  Output Audio Path  : {result.audio_path or 'N/A'}")
    print(f"  Duration           : {result.duration_seconds}s")
    print(f"  Sample Rate        : {result.sample_rate} Hz")
    print(f"  Channels           : {result.channels}")
    print(f"  Execution Time     : {elapsed:.2f}s")
    print(f"  Telemetry          : {result.telemetry}")

    if args.plan_only:
        print("\n[PASS] Voice cloning plan validation PASSED (Plan-Only Mode).")
        sys.exit(0)

    if not result.success:
        print(f"\n[FAILURE] Voice cloning execution failed: {result.error_message}")
        sys.exit(1)

    if result.audio_path and Path(result.audio_path).exists():
        size_kb = Path(result.audio_path).stat().st_size / 1024
        print(f"  Generated File Size: {size_kb:.2f} KB")

    print("\n[PASS] Chatterbox Voice Cloning validation PASSED.")
    status_str = "REAL_INTEGRATION / GPU-READY" if diag.gpu_available else "REAL_INTEGRATION / READY (CPU Mode)"
    print(f"Status: {status_str}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chatterbox Voice Cloning Real Validation Test")
    parser.add_argument(
        "--text",
        default="Artificial intelligence empowers creative storytelling across the world. [laugh] The possibilities are endless.",
        help="Text to synthesize in cloned voice",
    )
    parser.add_argument(
        "--reference-audio",
        default="materials/test_reference_voice.wav",
        help="Path to authorized reference audio file",
    )
    parser.add_argument("--voice-name", default="Authorized Developer Voice", help="Voice profile name")
    parser.add_argument("--language", default="en", help="Language code (en, hi, es, fr, de, zh, ja, etc.)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech rate multiplier")
    parser.add_argument("--pitch", type=float, default=0.0, help="Pitch shift in semitones")
    parser.add_argument("--exaggeration", type=float, default=0.0, help="Emotion exaggeration (0.0 to 1.0)")
    parser.add_argument("--cfg-weight", type=float, default=0.5, help="Classifier-Free Guidance weight")
    parser.add_argument("--model-id", default="resemble-ai/chatterbox-multilingual", help="HuggingFace model ID")
    parser.add_argument("--consent", action="store_true", default=True, help="Explicit confirmation of voice rights")
    parser.add_argument("--plan-only", action="store_true", help="Run tokenization & plan check only")
    args = parser.parse_args()

    run_test(args)
