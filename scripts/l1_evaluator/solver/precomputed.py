"""PrecomputedSolver — reads pre-generated full-project outputs from a directory."""

from __future__ import annotations

import json
from pathlib import Path

from . import Solver


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class PrecomputedSolver(Solver):
    """Read complete file contents from a directory of pre-generated outputs.

    Expected directory layout:
      <outputs_dir>/{language}/{project}/{task_name}/{rel_path}

    Every file under that task subtree is treated as part of the generated
    project workspace and written back into `/workspace/src/<rel_path>`.
    """

    def __init__(self, outputs_dir: Path):
        self._outputs_dir = outputs_dir.resolve()
        if not self._outputs_dir.is_dir():
            raise FileNotFoundError(
                f"Precomputed outputs dir not found: {self._outputs_dir}"
            )

    @property
    def name(self) -> str:
        return self._outputs_dir.name

    def solve(self, task_dir: Path) -> dict[str, str]:
        language = task_dir.parents[2].name
        project = task_dir.parents[1].name
        task_name = task_dir.name
        base = self._outputs_dir / language / project / task_name
        if not base.is_dir():
            return {}
        result: dict[str, str] = {}
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(base))
                result[rel] = path.read_text(encoding="utf-8")
        return result
