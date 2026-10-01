#!/usr/bin/env python3
"""CLI entry point for the L3 Task Slicer."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slicer.project import load_project, discover_projects
from slicer.task_builder import build_l3_tasks
from slicer.prompt_builder import build_prompt


def _rebuild_prompts_with_desc(task_dirs: list[Path], ctx_map: dict) -> None:
    """Re-write prompt.md for each task now that desc.txt exists."""
    for task_dir in task_dirs:
        prompt_file = task_dir / "prompt.md"
        desc_file = task_dir / "desc.txt"
        if not desc_file.exists() or not prompt_file.exists():
            continue
        ctx = ctx_map.get(task_dir)
        if ctx is None:
            continue
        func, hollowed_source, project_ctx, extractor = ctx
        prompt = build_prompt(
            func=func,
            hollowed_source=hollowed_source,
            project_dir=project_ctx.project_dir,
            source_files=project_ctx.source_files,
            source_roots=project_ctx.source_roots,
            extractor=extractor,
            task_dir=task_dir,
        )
        prompt_file.write_text(prompt, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate L3 evaluation tasks")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Path to a single project directory")
    group.add_argument("--language", help="Process all projects for a language")
    group.add_argument("--all", action="store_true", help="Process all projects")

    parser.add_argument("--model", default="gpt-5.4-nano",
                        help="Model for generating function descriptions (default: gpt-5.4-nano)")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                        help="API base URL (default: $OPENAI_BASE_URL)")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"),
                        help="API key (default: $OPENAI_API_KEY)")
    parser.add_argument("--desc-workers", type=int, default=8,
                        help="Concurrent workers for description generation (default: 8)")
    parser.add_argument("--skip-desc", action="store_true",
                        help="Skip LLM description generation (pure local mode)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    datasets_root = repo_root / "datasets"

    if args.project:
        projects = [Path(args.project).resolve()]
    elif args.language:
        projects = discover_projects(datasets_root, args.language)
    else:
        projects = discover_projects(datasets_root)

    if not projects:
        print("No projects found.")
        return

    total_tasks = 0
    all_task_dirs: list[Path] = []

    for project_dir in projects:
        print(f"\n[{project_dir.parent.name}/{project_dir.name}]")
        try:
            ctx = load_project(project_dir)
        except Exception as e:
            print(f"  ERROR loading project: {e}")
            continue

        print(f"  Language: {ctx.language}, Source files: {len(ctx.source_files)}")
        task_dirs, count = build_l3_tasks(ctx)
        print(f"  Generated {count} L3 tasks")
        total_tasks += count
        all_task_dirs.extend(task_dirs)

    print(f"\nDone. Total L3 tasks generated: {total_tasks}")

    if args.skip_desc or not all_task_dirs:
        return

    if not args.api_key:
        print("\n跳过描述生成：未提供 --api-key 或 $OPENAI_API_KEY")
        return
    if not args.base_url:
        print("\n跳过描述生成：未提供 --base-url 或 $OPENAI_BASE_URL")
        return

    print(f"\n生成函数描述（模型: {args.model}, workers: {args.desc_workers}）...")
    from slicer.desc_generator import generate_descriptions
    success, failed = generate_descriptions(
        task_dirs=all_task_dirs,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        workers=args.desc_workers,
    )
    print(f"描述生成完成：{success} 成功，{failed} 失败")

    if success > 0:
        print("重建 prompt.md（合并函数描述）...")
        # Re-load projects to rebuild prompts with desc.txt
        for project_dir in projects:
            try:
                ctx = load_project(project_dir)
            except Exception:
                continue
            from slicer.task_builder import _rebuild_prompts
            _rebuild_prompts(ctx, project_dir / "tasks")
        print("prompt.md 重建完成")


if __name__ == "__main__":
    main()
