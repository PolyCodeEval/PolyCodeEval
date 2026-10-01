"""Resolve L0 install/test commands from task run_config."""

from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_l0_commands(task_dir: Path) -> tuple[str, str, bool]:
    """Return (install_command, test_command, use_combined_script) for L0 blackbox-only eval."""
    run_config = _load_json(task_dir / "run_config.json")
    install_command = (run_config.get("install_command") or "").strip()
    test_command = (run_config.get("test_command") or "").strip()
    if not test_command:
        raise ValueError(f"L0 run_config missing test_command: {task_dir / 'run_config.json'}")
    return install_command, test_command, False
