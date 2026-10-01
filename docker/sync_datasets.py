#!/usr/bin/env python3
"""Sync PolyCodeEval datasets via DockerHub images.

Usage (from repo root):
    python docker/sync_datasets.py pull --all
    python docker/sync_datasets.py pull --language go
    python docker/sync_datasets.py push --all
    python docker/sync_datasets.py push --language javascript
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

LANGUAGES = ["python", "go", "java", "cpp", "javascript"]
IMAGE_PREFIX = "err404notfound/polycodeeval-datasets"
REPO_ROOT = Path(__file__).resolve().parent.parent

# Default proxy for buildkit (buildx --push doesn't inherit Docker Desktop proxy).
# Override with --proxy or set HTTPS_PROXY env var before running.
DEFAULT_PROXY = "http://127.0.0.1:7897"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def _ensure_proxy(proxy: str | None) -> None:
    """Set HTTP(S)_PROXY env vars for buildkit if not already set."""
    proxy = proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not proxy:
        proxy = DEFAULT_PROXY
        print(f"[proxy] No proxy env var found, using default: {proxy}")
    os.environ.setdefault("HTTP_PROXY", proxy)
    os.environ.setdefault("HTTPS_PROXY", proxy)
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
    print(f"[proxy] HTTP_PROXY={os.environ['HTTP_PROXY']}")


def pull(language: str) -> None:
    image = f"{IMAGE_PREFIX}-{language}:latest"
    print(f"\n[pull] {image}")

    _run(["docker", "pull", image])

    cid = subprocess.check_output(
        ["docker", "create", image], text=True
    ).strip()

    try:
        dest = REPO_ROOT / "datasets"
        dest.mkdir(exist_ok=True)

        # Remove existing target dirs to avoid stale files or nested folders
        lang_dir = dest / language
        if lang_dir.exists():
            shutil.rmtree(lang_dir)
            print(f"  [clean] removed {lang_dir}")

        docs_dir = REPO_ROOT / "docs"
        if docs_dir.exists():
            shutil.rmtree(docs_dir)
            print(f"  [clean] removed {docs_dir}")

        # docker cp uses forward slashes for container paths on all platforms.
        # Copy to parent dir so that /data/{language} becomes datasets/{language}.
        _run(["docker", "cp", f"{cid}:/data/{language}", str(dest)])
        _run(["docker", "cp", f"{cid}:/data/docs", str(REPO_ROOT)])
    finally:
        subprocess.run(["docker", "rm", cid], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[pull] {language} done -> datasets/{language}/")


def _backup_from_hub(language: str) -> None:
    """Pull current image from DockerHub and extract to datasets_bak/ as backup."""
    image = f"{IMAGE_PREFIX}-{language}:latest"
    backup_dir = REPO_ROOT / "datasets_bak"
    backup_dir.mkdir(exist_ok=True)

    print(f"\n[backup] pulling {image} for backup ...")
    try:
        _run(["docker", "pull", image])
    except subprocess.CalledProcessError:
        print(f"[backup] {language}: no existing image on DockerHub, skip backup")
        return

    cid = subprocess.check_output(
        ["docker", "create", image], text=True
    ).strip()

    try:
        lang_bak = backup_dir / language
        if lang_bak.exists():
            shutil.rmtree(lang_bak)
        _run(["docker", "cp", f"{cid}:/data/{language}", str(backup_dir)])
    finally:
        subprocess.run(["docker", "rm", cid], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[backup] {language} done -> datasets_bak/{language}/")


def push(language: str) -> None:
    image = f"{IMAGE_PREFIX}-{language}:latest"
    dockerfile = REPO_ROOT / "docker" / "datasets" / f"Dockerfile.{language}"

    if not dockerfile.exists():
        print(f"[push] Dockerfile not found: {dockerfile}", file=sys.stderr)
        sys.exit(1)

    src_dir = REPO_ROOT / "datasets" / language
    if not src_dir.exists():
        print(f"[push] Dataset not found: {src_dir}", file=sys.stderr)
        sys.exit(1)

    _backup_from_hub(language)

    print(f"\n[push] {image}")

    # Build multi-arch image and push in one step.
    # Requires HTTPS_PROXY env var for buildkit to reach DockerHub.
    _run([
        "docker", "buildx", "build",
        "--platform", "linux/amd64,linux/arm64",
        "-f", str(dockerfile),
        "-t", image,
        "--push",
        str(REPO_ROOT),
    ])

    print(f"[push] {language} done → {image}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync datasets via DockerHub")
    parser.add_argument("action", choices=["pull", "push"])
    parser.add_argument("--language", choices=LANGUAGES)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--proxy", help="HTTP proxy address (e.g. http://127.0.0.1:7897)")
    parser.add_argument("--no-proxy", action="store_true",
                        help="Disable automatic proxy setup")
    args = parser.parse_args()

    if not args.language and not args.all:
        parser.error("specify --language or --all")

    # Set up proxy for push (buildx needs it)
    if args.action == "push" and not args.no_proxy:
        _ensure_proxy(args.proxy)

    languages = LANGUAGES if args.all else [args.language]
    fn = pull if args.action == "pull" else push

    for lang in languages:
        fn(lang)

    print("\nAll done.")


if __name__ == "__main__":
    main()
