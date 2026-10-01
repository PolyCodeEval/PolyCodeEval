"""OracleSolver — reads all source files from src/ for infrastructure validation."""

from __future__ import annotations

import json
from pathlib import Path

from . import Solver

EXCLUDED_DIRS = {"node_modules", ".git", "__pycache__", ".idea", "tests", "test", "vendor"}

EXCLUDED_FILE_SUFFIXES = {"_test.go", "_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"}
EXCLUDED_FILE_PREFIXES = {"test_"}
EXCLUDED_FILE_EXACT = {"Test.java"}


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
        if not src_dir.is_dir():
            return {}
        result: dict[str, str] = {}
        for path in sorted(src_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(src_dir).parts
            if any(part in EXCLUDED_DIRS for part in rel_parts):
                continue
            filename = path.name
            if any(filename.endswith(s) for s in EXCLUDED_FILE_SUFFIXES):
                continue
            if filename in EXCLUDED_FILE_EXACT:
                continue
            rel = str(path.relative_to(src_dir))
            try:
                result[rel] = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
        return result
