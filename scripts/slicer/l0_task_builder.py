"""L0 project-level task builder — generates one from-scratch evaluation task per project.

Unlike L1, L0 provides NO skeleton. The model receives only the PRD and must
generate all source files from scratch.
"""

from __future__ import annotations

import json
from pathlib import Path

from slicer.project import ProjectContext


def build_l0_task(ctx: ProjectContext) -> bool:
    tasks_dir = ctx.project_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    task_name = f"L0_{ctx.project_dir.name}"
    task_dir = tasks_dir / task_name

    prd_path = ctx.project_dir / "docs" / "prd.md"
    if not prd_path.exists():
        return False

    prd_text = prd_path.read_text(encoding="utf-8", errors="replace")
    if not prd_text.strip():
        return False

    task_dir.mkdir(parents=True, exist_ok=True)

    task_json = {
        "level": "L0",
        "target_dir": ".",
        "stub_info": {"lang": ctx.language},
    }
    _write_json(task_dir / "task.json", task_json)

    run_config = {
        "docker_image": ctx.config.get("docker_image", ""),
        "install_command": "",
        "test_command": "",
        "src_dir": "../../src",
    }
    _write_json(task_dir / "run_config.json", run_config)

    prompt = _build_l0_prompt(ctx.language, prd_text)
    (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")

    return True


def _build_l0_prompt(language: str, prd_text: str) -> str:
    return (
        f"# Task\n\n"
        f"You are given a product requirements document for a {language} project.\n"
        f"Generate the complete project source code from scratch, including build configuration files.\n"
        f"Return your answer as a sequence of file sections, each starting with:\n\n"
        f"===FILE: relative/path/to/file===\n\n"
        f"followed by the complete file content. Do not wrap files in markdown fences.\n"
        f"Do not generate test files.\n\n"
        f"# Project Requirements\n\n"
        f"{prd_text}\n"
    )


def _write_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
