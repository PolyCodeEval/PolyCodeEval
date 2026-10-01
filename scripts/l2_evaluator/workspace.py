"""Workspace — resolves file paths and prepares hollowed files for L2 evaluation.

With the long-running container architecture, the workspace only needs to:
1. Provide the original src/ directory path for docker cp
2. Apply hollowed_files on top of a temp copy (for the backfill target)
3. Expose the original bytes of the target file (for restoration after each task)
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_file(src_dir: Path, rel_path: str) -> str:
    """Resolve a potentially incorrect relative path to the actual file in src_dir."""
    if (src_dir / rel_path).exists():
        return rel_path
    if rel_path.startswith("src/"):
        stripped = rel_path[len("src/"):]
        if (src_dir / stripped).exists():
            return stripped
    target = Path(rel_path)
    fname = target.name
    matches = list(src_dir.rglob(fname))
    if not matches:
        return rel_path
    if len(matches) == 1:
        return str(matches[0].relative_to(src_dir))
    for m in matches:
        m_rel = str(m.relative_to(src_dir))
        if m_rel.endswith(rel_path) or m_rel.endswith(str(target)):
            return m_rel
    return str(matches[0].relative_to(src_dir))


class Workspace:

    def __init__(self, task_dir: Path):
        self.task_dir = task_dir
        self.run_config = _load_json(task_dir / "run_config.json")
        self._task = _load_json(task_dir / "task.json")
        self._src_dir = (task_dir / self.run_config["src_dir"]).resolve()
        self._hollowed_tmp: Path | None = None

    @property
    def src_dir(self) -> Path:
        return self._src_dir

    @property
    def project_dir(self) -> Path:
        return self._src_dir.parent

    def get_target_info(self) -> tuple[str, bytes]:
        """Return (container_rel_path, original_bytes) for the hollowed target file."""
        stub_info = self._task["stub_info"]
        rel = _resolve_file(self._src_dir, stub_info["file"])
        original = (self._src_dir / rel).read_bytes()
        return rel, original

    def make_backfilled_file(self, file_content: str) -> tuple[Path, str]:
        """Write solver output to a temp file. Returns (tmp_path, container_rel_path)."""
        stub_info = self._task["stub_info"]
        rel = _resolve_file(self._src_dir, stub_info["file"])
        # Apply hollowed stub first, then overwrite with solver content
        hollowed_src = self.task_dir / "hollowed_files" / stub_info["file"]
        tmp = Path(tempfile.mktemp(prefix="pce_l2_bf_", suffix=Path(rel).suffix))
        if hollowed_src.exists():
            shutil.copy2(hollowed_src, tmp)
        tmp.write_text(file_content, encoding="utf-8")
        return tmp, rel

    def cleanup(self) -> None:
        if self._hollowed_tmp:
            shutil.rmtree(self._hollowed_tmp, ignore_errors=True)
            self._hollowed_tmp = None

