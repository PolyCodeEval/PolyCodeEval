"""Resolve L1 install/test commands using the paired L0 blackbox config."""

from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_l0_commands(task_dir: Path) -> tuple[str, str, bool]:
    """Return the paired L0 blackbox install/test commands for an L1 task."""
    tasks_dir = task_dir.parent
    project_name = task_dir.name.removeprefix("L1_")
    l0_run_config = tasks_dir / f"L0_{project_name}" / "run_config.json"
    if not l0_run_config.is_file():
        raise ValueError(f"Paired L0 run_config not found for L1 task: {l0_run_config}")
    run_config = _load_json(l0_run_config)
    install_command = (run_config.get("install_command") or "").strip()
    test_command = (run_config.get("test_command") or "").strip()
    if not test_command:
        raise ValueError(f"L0 run_config missing test_command: {l0_run_config}")
    return install_command, test_command, False
