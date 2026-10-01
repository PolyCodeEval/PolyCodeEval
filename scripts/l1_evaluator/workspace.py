"""Workspace — manages the temporary directory lifecycle for a single L1 task evaluation.

L1 now mirrors L0 semantics:
- start from an empty workspace
- backfill the model-generated full repository tree into `src/`
- inject blackbox-only evaluation resources afterward
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class Workspace:

    def __init__(self, task_dir: Path):
        self.task_dir = task_dir
        self.run_config = _load_json(task_dir / "run_config.json")
        self._task = _load_json(task_dir / "task.json")
        self.tmp_dir: Path | None = None

    def build(self) -> None:
        """Create an empty temp directory — no oracle src is copied."""
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="pce_l1_"))
        (self.tmp_dir / "src").mkdir()

    def backfill(self, file_map: dict[str, str]) -> None:
        """Write solver-generated files into src/."""
        for rel_path, content in file_map.items():
            target = self.tmp_dir / "src" / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def inject_blackbox_tests(self) -> None:
        """Inject blackbox_tests/ from the project directory into the workspace."""
        project_dir = self.task_dir.parents[1]
        blackbox_dir = project_dir / "blackbox_tests"
        if not blackbox_dir.is_dir():
            return
        dest = self.tmp_dir / "blackbox_tests"
        shutil.copytree(blackbox_dir, dest)

    def inject_test_fixtures(self) -> None:
        """Inject non-code fixture directories from oracle tests/ into workspace tests/."""
        project_dir = self.task_dir.parents[1]
        oracle_tests = project_dir / "tests"
        if not oracle_tests.is_dir():
            return
        fixture_dirs = [
            item for item in oracle_tests.iterdir()
            if item.is_dir() and item.name not in ("src", "test", "acceptanceTest")
        ]
        if not fixture_dirs:
            return
        dest_tests = self.tmp_dir / "tests"
        dest_tests.mkdir(exist_ok=True)
        for item in fixture_dirs:
            shutil.copytree(item, dest_tests / item.name)

    def inject_oracle_build_config(self) -> None:
        """Inject oracle build configuration files into the workspace src/.

        This mirrors the L0 blackbox evaluation behavior: generated repository
        contents are treated as the primary source of truth, while a small set
        of build/config files may be injected from the oracle project when the
        blackbox runner depends on them to execute.
        """
        project_dir = self.task_dir.parents[1]
        language = self.task_dir.parents[2].name
        if language != "java":
            return

        oracle_src = project_dir / "src"
        if not oracle_src.is_dir():
            return

        gradle_items = [
            "build.gradle", "build.gradle.kts",
            "settings.gradle", "settings.gradle.kts",
            "gradlew", "gradlew.bat", "gradle",
        ]

        dest_src = self.tmp_dir / "src"
        for name in gradle_items:
            src_path = oracle_src / name
            if not src_path.exists():
                continue
            dest_path = dest_src / name
            if src_path.is_dir():
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(src_path, dest_path)
            else:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)

    def cleanup(self) -> None:
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
            self.tmp_dir = None
