"""L1 project-level task builder — generates one evaluation task per project.

For each project, ALL functions across ALL source files are hollowed.
The prompt provides the full PRD + entire project skeleton.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from slicer.parser import SymbolExtractor, FunctionInfo
from slicer.hollower import hollow_all_functions
from slicer.project import ProjectContext


def build_l1_task(ctx: ProjectContext) -> bool:
    extractor = SymbolExtractor(ctx.lang_config)
    tasks_dir = ctx.project_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    task_name = f"L1_{ctx.project_dir.name}"
    task_dir = tasks_dir / task_name

    hollowed_file_map: dict[str, bytes] = {}
    total_func_count = 0

    for src_file in ctx.source_files:
        functions = extractor.extract_functions(src_file)
        rel = _resolve_rel_path(src_file, ctx.source_roots)
        if rel is None:
            continue
        if not functions:
            hollowed_file_map[rel] = src_file.read_bytes()
            continue
        source = src_file.read_bytes()
        hollowed = hollow_all_functions(
            source, functions, ctx.lang_config.stub, ctx.language,
        )
        hollowed_file_map[rel] = hollowed
        total_func_count += len(functions)

    if total_func_count == 0:
        return False

    hollowed_rels = sorted(hollowed_file_map.keys())

    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    hollowed_files_dir = task_dir / "hollowed_files"
    for rel, content in hollowed_file_map.items():
        dest = hollowed_files_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

    task_json = {
        "level": "L1",
        "target_dir": ".",
        "hollowed_files": hollowed_rels,
        "context_from_src": [],
        "stub_info": {
            "lang": ctx.language,
            "file_count": len(hollowed_rels),
            "total_function_count": total_func_count,
        },
    }
    _write_json(task_dir / "task.json", task_json)

    run_config = {
        "docker_image": ctx.config.get("docker_image", ""),
        "install_command": ctx.config.get("install_command", ""),
        "test_command": ctx.config.get("test_command", ""),
        "src_dir": "../../src",
        "hollowed_files": hollowed_rels,
    }
    _write_json(task_dir / "run_config.json", run_config)

    prompt = _build_l1_prompt(ctx, hollowed_file_map, total_func_count)
    (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")

    return True


def _resolve_rel_path(src_file: Path, source_roots: list[Path]) -> str | None:
    for root in source_roots:
        try:
            return str(src_file.relative_to(root))
        except ValueError:
            continue
    return None


def _build_l1_prompt(
    ctx: ProjectContext,
    hollowed_file_map: dict[str, bytes],
    total_func_count: int,
) -> str:
    lang = ctx.language
    stub = ctx.lang_config.stub
    sections: list[str] = []

    sections.append(
        f"# Task\n\n"
        f"You are given the skeleton of a {lang} project with "
        f"{total_func_count} function bodies replaced by `{stub}`.\n"
        f"Implement every stubbed function. Return your answer as a sequence of "
        f"file sections, each starting with a delimiter line:\n\n"
        f"```\n===FILE: relative/path/to/file===\n```\n\n"
        f"followed by the complete file content. "
        f"Do not wrap individual files in markdown fences.\n"
    )

    prd_text = _read_prd(ctx.project_dir)
    if prd_text:
        sections.append(f"# Project Requirements\n\n{prd_text}\n")

    skeleton_parts: list[str] = []
    for rel in sorted(hollowed_file_map.keys()):
        content = hollowed_file_map[rel].decode("utf-8", errors="replace")
        skeleton_parts.append(f"## {rel}\n\n```\n{content}\n```")
    sections.append("# Project Skeleton\n\n" + "\n\n".join(skeleton_parts) + "\n")

    return "\n".join(sections)


def _read_prd(project_dir: Path) -> str:
    prd_path = project_dir / "docs" / "prd.md"
    if not prd_path.exists():
        return ""
    return prd_path.read_text(encoding="utf-8", errors="replace")


def _write_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
