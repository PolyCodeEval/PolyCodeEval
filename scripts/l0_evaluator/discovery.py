"""Shared L0 task discovery helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def is_l0_task(task_dir: Path) -> bool:
    task_json = task_dir / "task.json"
    if not task_json.is_file():
        return False
    with task_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("level") == "L0"


def discover_l0_tasks(
    *,
    task: str | None = None,
    project: str | None = None,
    language: str | None = None,
    all_: bool = False,
    repo_root: Path | None = None,
) -> list[Path]:
    """Discover L0 task directories based on CLI filters."""
    root = repo_root or REPO_ROOT

    if task:
        task_dir = Path(task)
        if not task_dir.is_absolute():
            task_dir = root / task_dir
        if not is_l0_task(task_dir):
            print(f"Error: not a valid L0 task directory: {task_dir}", file=sys.stderr)
            sys.exit(1)
        return [task_dir]

    if project:
        project_dir = Path(project)
        if not project_dir.is_absolute():
            project_dir = root / project_dir
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            print(f"Error: no tasks/ directory in {project_dir}", file=sys.stderr)
            sys.exit(1)
        return sorted(d for d in tasks_dir.iterdir() if d.is_dir() and is_l0_task(d))

    if not all_ and language is None:
        print("Error: specify --task, --project, --language, or --all", file=sys.stderr)
        sys.exit(1)

    project_dirs = _discover_project_dirs(language)
    task_dirs: list[Path] = []
    for proj_dir in project_dirs:
        tasks_dir = proj_dir / "tasks"
        if not tasks_dir.is_dir():
            continue
        for d in sorted(tasks_dir.iterdir()):
            if d.is_dir() and is_l0_task(d):
                task_dirs.append(d)
    return task_dirs


def _discover_project_dirs(language: str | None) -> list[Path]:
    from runner_lib import DATASETS_ROOT, discover_projects

    projects = discover_projects(language)
    if projects:
        return projects

    # Fallback for flat layouts (e.g. _test_data/python/project/)
    root = DATASETS_ROOT
    if not root.is_dir():
        return []

    if language:
        lang_dirs = [root / language]
    else:
        lang_dirs = [
            p for p in root.iterdir()
            if p.is_dir() and p.name in {"python", "cpp", "java", "javascript", "go"}
        ]

    found: list[Path] = []
    for lang_dir in lang_dirs:
        if not lang_dir.is_dir():
            continue
        for config_path in lang_dir.glob("*/config.json"):
            found.append(config_path.parent)
    return sorted(found)


def task_id(task_dir: Path) -> str:
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    return f"{language}/{project}/{task_dir.name}"


def precomputed_task_dir(output_dir: Path, task_dir: Path) -> Path:
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    return output_dir / language / project / task_dir.name
