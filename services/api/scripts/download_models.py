"""Explicitly download speech model weights. Never run automatically.

Usage (from services/api):
  uv run python scripts/download_models.py asr --size small     # faster-whisper (MIT), ~480 MB
  uv run python scripts/download_models.py asr --size tiny      # ~75 MB, for testing only
  uv run python scripts/download_models.py tts                  # Indic Parler-TTS (Apache-2.0)

The TTS model is gated: accept its licence on Hugging Face and run `hf auth login` first.

Models are written to <repo>/models/ (git-ignored) with a manifest recording the exact
revision and file checksums. Print the env var to set afterwards.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = REPO_ROOT / "models"

ASR_REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
}
TTS_REPO = "ai4bharat/indic-parler-tts"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    repo: str, target: Path, revision: str | None, allow_patterns: list[str] | None = None
) -> Path:
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError:
        sys.exit("huggingface_hub is not installed (it comes with the `speech` dependency group).")
    info = HfApi().model_info(repo, revision=revision)
    path = Path(
        snapshot_download(repo, revision=info.sha, local_dir=target, allow_patterns=allow_patterns)
    )
    manifest = {
        "repo": repo,
        "revision": info.sha,
        "files": {
            str(p.relative_to(path)): _sha256(p)
            for p in sorted(path.rglob("*"))
            if p.is_file() and ".cache" not in p.parts
        },
    }
    (path / "sneha-manifest.json").write_text(json.dumps(manifest, indent=2))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="kind", required=True)
    asr = sub.add_parser("asr")
    asr.add_argument("--size", choices=sorted(ASR_REPOS), default="small")
    asr.add_argument("--revision", default=None, help="pin a specific commit")
    tts = sub.add_parser("tts")
    tts.add_argument("--revision", default=None)
    args = parser.parse_args()

    if args.kind == "asr":
        repo = ASR_REPOS[args.size]
        path = download(repo, MODELS_DIR / "asr" / f"faster-whisper-{args.size}", args.revision)
        print(f"Downloaded {repo} to {path}\nSet: SNEHA_ASR_MODEL_PATH={path}")
    else:
        path = download(TTS_REPO, MODELS_DIR / "tts" / "indic-parler-tts", args.revision)
        # The voice-description tokenizer lives in another repo. Keep a local copy (tokenizer
        # files only) so the server never fetches it at runtime.
        config = json.loads((path / "config.json").read_text())
        desc_repo = config["text_encoder"]["_name_or_path"]
        download(
            desc_repo,
            path / "description_tokenizer",
            None,
            allow_patterns=["*.json", "*.model", "*.txt"],
        )
        print(f"Downloaded {TTS_REPO} to {path}\nSet: SNEHA_TTS_MODEL_PATH={path}")


if __name__ == "__main__":
    main()
