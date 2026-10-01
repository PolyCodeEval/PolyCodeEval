from __future__ import annotations

import json
import shutil
from pathlib import Path

from slicer.parser import SymbolExtractor, FunctionInfo
from slicer.hollower import hollow_function
from slicer.prompt_builder import build_prompt
from slicer.project import ProjectContext


def build_l3_tasks(ctx: ProjectContext) -> tuple[list[Path], int]:
    extractor = SymbolExtractor(ctx.lang_config)
    tasks_dir = ctx.project_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    task_dirs = []
    count = 0
    for src_file in ctx.source_files:
        functions = extractor.extract_functions(src_file)
        for func in functions:
            if func.is_trivial:
                continue
            task_dir = _build_one_task(func, src_file, ctx, extractor, tasks_dir)
            task_dirs.append(task_dir)
            count += 1

    return task_dirs, count


def _rebuild_prompts(ctx: ProjectContext, tasks_dir: Path) -> None:
    """Re-write prompt.md for all tasks that have a desc.txt."""
    extractor = SymbolExtractor(ctx.lang_config)
    for src_file in ctx.source_files:
        functions = extractor.extract_functions(src_file)
        for func in functions:
            if func.is_trivial:
                continue
            file_stem = src_file.stem
            task_name = f"L3_{file_stem}__{func.name}"
            task_dir = tasks_dir / task_name
            if not task_dir.exists() or not (task_dir / "desc.txt").exists():
                continue
            hollowed_files_dir = task_dir / "hollowed_files"
            # Find the hollowed file
            hollowed_files = list(hollowed_files_dir.rglob("*")) if hollowed_files_dir.exists() else []
            hollowed_source = None
            for hf in hollowed_files:
                if hf.is_file() and hf.stem == src_file.stem:
                    hollowed_source = hf.read_bytes()
                    break
            if hollowed_source is None:
                continue
            prompt = build_prompt(
                func=func,
                hollowed_source=hollowed_source,
                project_dir=ctx.project_dir,
                source_files=ctx.source_files,
                source_roots=ctx.source_roots,
                extractor=extractor,
                task_dir=task_dir,
            )
            (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")


def _build_one_task(
    func: FunctionInfo,
    src_file: Path,
    ctx: ProjectContext,
    extractor: SymbolExtractor,
    tasks_dir: Path,
) -> Path:
    file_stem = src_file.stem
    task_name = f"L3_{file_stem}__{func.name}"
    task_dir = tasks_dir / task_name

    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    # --- hollow the target file ---
    source = src_file.read_bytes()
    hollowed_source = hollow_function(
        source, func, ctx.lang_config.stub, ctx.language
    )

    # --- find relative path and collect context files ---
    hollowed_file_rel = None
    context_files = []

    for root in ctx.source_roots:
        for f in ctx.source_files:
            try:
                rel = f.relative_to(root)
            except ValueError:
                continue
            rel_str = str(rel)
            if f == src_file:
                hollowed_file_rel = rel_str
            else:
                context_files.append(rel_str)

    # --- write hollowed_files/ (only the one modified file) ---
    if hollowed_file_rel:
        hollowed_files_dir = task_dir / "hollowed_files"
        dest = hollowed_files_dir / hollowed_file_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(hollowed_source)

    # --- write task.json ---
    task_json = {
        "level": "L3",
        "target": f"{hollowed_file_rel}::{func.name}",
        "hollowed_files": [hollowed_file_rel] if hollowed_file_rel else [],
        "context_from_src": sorted(set(context_files)),
        "stub_info": {
            "file": hollowed_file_rel,
            "func_name": func.name,
            "body_start_byte": func.body_start_byte,
            "body_end_byte": func.body_end_byte,
            "stub": ctx.lang_config.stub,
            "lang": ctx.language,
        },
    }
    (task_dir / "task.json").write_text(
        json.dumps(task_json, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- write run_config.json ---
    run_config = {
        "docker_image": ctx.config.get("docker_image", ""),
        "install_command": ctx.config.get("install_command", ""),
        "test_command": ctx.config.get("test_command", ""),
        "src_dir": "../../src",
        "hollowed_files": [hollowed_file_rel] if hollowed_file_rel else [],
    }
    (task_dir / "run_config.json").write_text(
        json.dumps(run_config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- write prompt.md ---
    prompt = build_prompt(
        func=func,
        hollowed_source=hollowed_source,
        project_dir=ctx.project_dir,
        source_files=ctx.source_files,
        source_roots=ctx.source_roots,
        extractor=extractor,
        task_dir=task_dir,
    )
    (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    return task_dir
