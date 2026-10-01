from __future__ import annotations

from pathlib import Path

from common import PAPER_ROOT

IMG_ROOT = PAPER_ROOT / "imgs"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def default_output(filename: str) -> Path:
    return IMG_ROOT / filename
