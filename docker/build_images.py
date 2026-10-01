from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from runner_lib import DOCKER_ROOT

DOCKERFILE = DOCKER_ROOT / "images" / "unified.Dockerfile"
IMAGE_TAG = "polycodeeval/unified:all"


def build_image() -> int:
    command = [
        "docker", "build",
        "-f", str(DOCKERFILE),
        "-t", IMAGE_TAG,
        str(DOCKER_ROOT.parent),
    ]
    print("==>", IMAGE_TAG)
    print("    command:", " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    if not DOCKERFILE.is_file():
        print(f"Missing Dockerfile: {DOCKERFILE}")
        return 1
    return build_image()


if __name__ == "__main__":
    raise SystemExit(main())
