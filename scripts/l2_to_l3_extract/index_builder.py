"""Build lookup indexes from datasets task.json files for L2→L3 mapping."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass


@dataclass
class L2TaskInfo:
    target_file: str
    parser_lang: str


def build_l2_index(datasets_dir: Path) -> dict[tuple[str, str, str], L2TaskInfo]:
    """Build mapping: (lang, project, L2_task_name) → L2TaskInfo."""
    index: dict[tuple[str, str, str], L2TaskInfo] = {}
    for lang_dir in sorted(datasets_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        for proj_dir in sorted(lang_dir.iterdir()):
            if not proj_dir.is_dir():
                continue
            project = proj_dir.name
            tasks_dir = proj_dir / "tasks"
            if not tasks_dir.is_dir():
                continue
            for task_dir in sorted(tasks_dir.iterdir()):
                if not task_dir.name.startswith("L2_"):
                    continue
                task_json = task_dir / "task.json"
                if not task_json.exists():
                    continue
                with task_json.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                stub_info = data.get("stub_info", {})
                index[(lang, project, task_dir.name)] = L2TaskInfo(
                    target_file=stub_info.get("file", ""),
                    parser_lang=stub_info.get("lang", lang),
                )
    return index


def build_l3_index(datasets_dir: Path) -> dict[tuple[str, str, str, str], str]:
    """Build mapping: (lang, project, target_file, func_name) → L3_task_name."""
    index: dict[tuple[str, str, str, str], str] = {}
    for lang_dir in sorted(datasets_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        lang = lang_dir.name
        for proj_dir in sorted(lang_dir.iterdir()):
            if not proj_dir.is_dir():
                continue
            project = proj_dir.name
            tasks_dir = proj_dir / "tasks"
            if not tasks_dir.is_dir():
                continue
            for task_dir in sorted(tasks_dir.iterdir()):
                if not task_dir.name.startswith("L3_"):
                    continue
                task_json = task_dir / "task.json"
                if not task_json.exists():
                    continue
                with task_json.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                stub_info = data.get("stub_info", {})
                target_file = stub_info.get("file", "")
                func_name = stub_info.get("func_name", "")
                if target_file and func_name:
                    key = (lang, project, target_file, func_name)
                    if key not in index:
                        index[key] = task_dir.name
    return index
