"""OracleSolver — reads the original file content from src/ for infrastructure validation."""

from __future__ import annotations

import json
from pathlib import Path

from . import Solver


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class OracleSolver(Solver):

    @property
    def name(self) -> str:
        return "oracle"

    def solve(self, task_dir: Path) -> str:
        task = _load_json(task_dir / "task.json")
        run_config = _load_json(task_dir / "run_config.json")
        stub_info = task["stub_info"]
        src_dir = (task_dir / run_config["src_dir"]).resolve()

        # Import _resolve_file from workspace
        from ..workspace import _resolve_file
        resolved = _resolve_file(src_dir, stub_info["file"])
        src_file = src_dir / resolved

        return src_file.read_text(encoding="utf-8")
