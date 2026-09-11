"""CLI script to download WanGP models and their required text encoders/dependencies."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.api import init
from shared.utils import files_locator as fl
from shared.utils.download import download_file


def download_model_files(model_type: str = "t2v_1.3B") -> bool:
    print(f"Initializing WanGP session to inspect '{model_type}' dependencies...", flush=True)
    session = init(root=ROOT, console_output=True, console_isatty=True)

    model_def = session.get_model_def(model_type)
    if model_def is None:
        print(f"Error: Model '{model_type}' not found in WanGP model definitions.", file=sys.stderr)
        return False

    availability = session.get_model_availability(model_type)
    print(f"Current availability for '{model_type}': {availability.get('status')} (code: {availability.get('status_code')})")

    if availability.get("available", False):
        print(f"Model '{model_type}' is already fully available!")
        return True

    # 1. Download core model checkpoint if missing
    core_urls = model_def.get("URLs", [])
    if isinstance(core_urls, str):
        core_urls = [core_urls]

    for url in core_urls:
        filename = Path(url.split("|")[0]).name
        local_path = fl.get_local_model_filename(filename)
        if local_path is None or not Path(local_path).is_file():
            download_target = fl.get_download_location(filename)
            print(f"Downloading core model file: {filename} -> {download_target}")
            Path(download_target).parent.mkdir(parents=True, exist_ok=True)
            download_file(url, download_target)
        else:
            print(f"Core model file present: {local_path}")

    # 2. Download text encoder checkpoint if missing
    text_encoder_urls = model_def.get("text_encoder_URLs", [])
    text_encoder_folder = model_def.get("text_encoder_folder", "umt5-xxl")

    # By default, int8 text encoder is used when text_encoder_quantization is int8
    # Search for quanto_int8 URL first, fallback to first URL
    int8_url = next((u for u in text_encoder_urls if "quanto_int8" in u.lower()), text_encoder_urls[0] if text_encoder_urls else None)
    
    if int8_url:
        encoder_filename = Path(int8_url.split("|")[0]).name
        local_encoder_path = fl.get_local_model_filename(encoder_filename, extra_paths=text_encoder_folder)
        
        if local_encoder_path is None or not Path(local_encoder_path).is_file():
            # Place in ckpts/<text_encoder_folder>/<encoder_filename>
            download_target = fl.get_download_location(f"{text_encoder_folder}/{encoder_filename}")
            print(f"Downloading text encoder file: {encoder_filename} -> {download_target}")
            Path(download_target).parent.mkdir(parents=True, exist_ok=True)
            download_file(int8_url, download_target)
        else:
            print(f"Text encoder file present: {local_encoder_path}")

    # 3. Re-check availability
    updated_availability = session.get_model_availability(model_type)
    print(f"Final availability status for '{model_type}': {updated_availability.get('status')} (available: {updated_availability.get('available')})")
    
    return bool(updated_availability.get("available", False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Download model files for WanGP video generation")
    parser.add_argument("model", nargs="?", default="t2v_1.3B", help="Model type to download (default: t2v_1.3B)")
    args = parser.parse_args()

    success = download_model_files(args.model)
    if not success:
        print(f"\nWarning: '{args.model}' is still not fully available after setup download.", file=sys.stderr)
        sys.exit(1)
    print(f"\nSuccessfully set up '{args.model}'!")


if __name__ == "__main__":
    main()
