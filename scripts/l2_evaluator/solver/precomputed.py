"""PrecomputedSolver — reads pre-generated file contents from a directory."""

from __future__ import annotations

from pathlib import Path

from . import Solver


class PrecomputedSolver(Solver):
    """Read complete file contents from a directory of pre-generated outputs.

    Expected directory layout:
      <outputs_dir>/{language}/{project}/{task_name}.txt

    Each .txt file contains the complete file content (no markdown wrapping).
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

    def solve(self, task_dir: Path) -> str:
        language = task_dir.parents[2].name
        project = task_dir.parents[1].name
        task_name = task_dir.name
        output_file = self._outputs_dir / language / project / f"{task_name}.txt"
        if not output_file.exists():
            raise FileNotFoundError(
                f"No precomputed output for {language}/{project}/{task_name}\n"
                f"Expected: {output_file}"
            )
        return output_file.read_text(encoding="utf-8")
