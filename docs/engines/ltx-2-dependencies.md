# LTX-2 Dependency Audit

## Status: Blocked on Upstream Provenance

The requested upstream identity cannot be reproduced from the public official repository:

- Repository: `https://github.com/Lightricks/LTX-2`
- Requested version: `v0.9.1`
- Requested commit: `9c58ea4f8b2d1891a329d2b700efc164a66391d7`
- GitHub commit API result: `422`, “No commit found for SHA”
- GitHub tag and release lookup for `v0.9.1`: `404`, not found
- Public tag listing includes `v1.2.0` and `v1.3.0`; these are not substitutes for the requested version.

Consequently, there is no verified v0.9.1 `pyproject.toml`, lock file, package metadata, or installation guide to derive exact package versions from. This document intentionally does not repeat the previous generic minimum versions or invent a replacement lock. Do not use generic LTX-Video dependencies for LTX-2.

## Reproducible Environment

**Not available for the supplied pin.** A reproducible environment requires a resolvable upstream commit and its repository-owned lock/configuration files. Approval is blocked until the repository owner supplies a valid official commit or tag and the exact files at that revision can be inspected.

The current public repository's installation guide says to use `uv sync --frozen`, but that guidance belongs to a later release and does not establish dependencies for the requested revision. It is recorded here only to distinguish the later instructions from the missing v0.9.1 manifest; it is not an installation instruction for this platform integration.

Do not install an inferred set such as `torch`, `torchvision`, `torchaudio`, `transformers`, `accelerate`, or `diffusers` with guessed version bounds and call it v0.9.1 reproducible. The platform's `backend/requirements.txt` is not a substitute for the model repository's environment lock.

## Runtime Platform Notes

- **Linux:** No exact Python, CUDA, driver, compiler, or package versions have been verified against the requested source. Production worker support is unapproved.
- **Windows:** No exact native Windows support is established. WSL2 is not verified either. Do not advertise Windows local inference as supported based on this audit.
- **Remote worker:** A Linux CUDA worker is the intended deployment boundary, but it remains `GPU-UNVERIFIED` until an approved upstream revision, dependencies, exact weights, and real CUDA generation have all been tested.
- **Platform host:** The backend can remain separate from the model environment; no model dependency lock for it is established here.

## Approval Gate

Before integration approval, record the resolvable upstream URL and immutable SHA, archive the upstream manifest and lock at that SHA, install from that lock in a clean environment, and capture the resulting Python/PyTorch/CUDA/driver versions. Do not claim `REAL_VERIFIED` on the basis of unit tests or mocked neural generation.