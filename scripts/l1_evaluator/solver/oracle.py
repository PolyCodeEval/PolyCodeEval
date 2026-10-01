"""OracleSolver — reads the full original repository tree for infrastructure validation."""

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

    def solve(self, task_dir: Path) -> dict[str, str]:
        run_config = _load_json(task_dir / "run_config.json")
        src_dir = (task_dir / run_config["src_dir"]).resolve()
        result: dict[str, str] = {}
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(src_dir))
                result[rel] = path.read_text(encoding="utf-8")
        return result
