#!/usr/bin/env python3
"""Build PolyCodeEval tasks with the formal construction pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from construction.prompt_descriptions import (  # noqa: E402
    PromptConstructionError,
    TaskInfo,
    build_l2_context,
    build_l2_description_request,
    build_l3_context,
    build_l3_description_request,
    discover_tasks,
    render_l2_prompt,
    render_l3_prompt,
    write_json,
)
from l0_evaluator.scoring.judge_clients import (  # noqa: E402
    JudgeError,
    resolve_judge_provider_model,
    run_judge,
)
from slicer.file_task_builder import build_l2_tasks  # noqa: E402
from slicer.l0_task_builder import build_l0_task  # noqa: E402
from slicer.project import discover_projects, load_project  # noqa: E402
from slicer.project_task_builder import build_l1_task  # noqa: E402
from slicer.task_builder import build_l3_tasks  # noqa: E402


FINAL_PROMPT_SCHEMA = "polycodeeval_final_prompt_v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def select_projects(args: argparse.Namespace) -> list[Path]:
    datasets_root = REPO_ROOT / "datasets"
    if args.project:
        return [Path(args.project).resolve()]
    if args.language:
        return discover_projects(datasets_root, args.language)
    return discover_projects(datasets_root)


def build_base_tasks(level: str, projects: list[Path]) -> int:
    total = 0
    for project_dir in projects:
        print(f"\n[{project_dir.parent.name}/{project_dir.name}]")
        try:
            ctx = load_project(project_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR loading project: {exc}")
            continue

        if level == "L0":
            created = build_l0_task(ctx)
            total += int(created)
            print("  Generated L0 task" if created else "  Skipped L0 task")
        elif level == "L1":
            created = build_l1_task(ctx)
            total += int(created)
            print("  Generated L1 task" if created else "  Skipped L1 task")
        elif level == "L2":
            count = build_l2_tasks(ctx)
            total += count
            print(f"  Generated {count} L2 tasks")
        elif level == "L3":
            _, count = build_l3_tasks(ctx)
            total += count
            print(f"  Generated {count} L3 tasks")
        else:
            raise ValueError(f"Unsupported level: {level}")
    return total


def task_meta_path(task: TaskInfo) -> Path:
    return task.task_dir / "prompt_meta.json"


def should_skip_prompt(task: TaskInfo, model: str, resume: bool) -> bool:
    if not resume:
        return False
    meta_path = task_meta_path(task)
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return meta.get("status") == "ok" and meta.get("model") == model and meta.get("schema") == FINAL_PROMPT_SCHEMA


def finalize_one_prompt(task: TaskInfo, provider: str, model: str, *, resume: bool) -> dict[str, Any]:
    if should_skip_prompt(task, model, resume):
        return {"task": task.task_id, "status": "skipped", "reason": "resume"}

    started_at = utc_now()
    try:
        if task.level == "L2":
            context = build_l2_context(task)
            system_prompt, user_prompt = build_l2_description_request(task, context)
            payload = run_judge(provider, model, system_prompt, user_prompt)
            prompt = render_l2_prompt(context, payload)
        elif task.level == "L3":
            context = build_l3_context(task)
            system_prompt, user_prompt = build_l3_description_request(task, context)
            payload = run_judge(provider, model, system_prompt, user_prompt)
            prompt = render_l3_prompt(task, context, payload)
        else:
            raise PromptConstructionError(f"Final prompt generation is only supported for L2/L3, got {task.level}")

        task.prompt_path.write_text(prompt, encoding="utf-8")
        meta = {
            "schema": FINAL_PROMPT_SCHEMA,
            "status": "ok",
            "level": task.level,
            "task": task.task_id,
            "provider": provider,
            "model": model,
            "started_at": started_at,
            "completed_at": utc_now(),
            "prompt_path": str(task.prompt_path),
            "description_keys": sorted(payload.keys()),
        }
        write_json(task_meta_path(task), meta)
        return meta
    except (JudgeError, PromptConstructionError, OSError, KeyError, ValueError) as exc:
        failure = {
            "schema": FINAL_PROMPT_SCHEMA,
            "status": "failed",
            "level": task.level,
            "task": task.task_id,
            "provider": provider,
            "model": model,
            "started_at": started_at,
            "completed_at": utc_now(),
            "error": str(exc),
        }
        write_json(task_meta_path(task), failure)
        return failure


def finalize_prompts(level: str, args: argparse.Namespace) -> tuple[int, int, int]:
    provider, model = resolve_judge_provider_model(args.provider, args.model)
    tasks = discover_tasks(
        REPO_ROOT / "datasets",
        level,
        language=args.language,
        project=args.project,
        task=args.task,
    )
    if args.limit:
        tasks = tasks[: args.limit]
    if not tasks:
        print(f"No {level} tasks found for prompt finalization.")
        return 0, 0, 0

    print(f"\nFinalizing {len(tasks)} {level} prompts with {provider}:{model} ...")
    ok = failed = skipped = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(finalize_one_prompt, task, provider, model, resume=args.resume): task
            for task in tasks
        }
        for idx, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            result = future.result()
            status = result.get("status")
            if status == "ok":
                ok += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
            print(f"  [{idx}/{len(tasks)}] {status}: {task.task_id}", flush=True)
    return ok, failed, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PolyCodeEval tasks with the formal construction pipeline.")
    parser.add_argument("--level", choices=["L0", "L1", "L2", "L3", "all"], required=True)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--project", help="Path to one project directory, or a language/project id for prompt-only mode.")
    scope.add_argument("--language", help="Process all projects in one language.")
    scope.add_argument("--all", action="store_true", help="Process all projects.")
    parser.add_argument("--task", help="Restrict L2/L3 prompt finalization to one task id or task directory name.")
    parser.add_argument("--prompt-only", action="store_true", help="Finalize prompts for existing L2/L3 tasks without rebuilding base tasks.")
    parser.add_argument("--with-llm-description", action="store_true", help="Generate final L2/L3 prompts during construction.")
    parser.add_argument("--provider", help="LLM provider for description generation.")
    parser.add_argument("--model", help="LLM model for description generation.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent LLM workers for prompt finalization.")
    parser.add_argument("--resume", action="store_true", help="Skip prompts with matching successful prompt_meta.json.")
    parser.add_argument("--limit", type=int, help="Limit prompt finalization to the first N discovered tasks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    levels = ["L0", "L1", "L2", "L3"] if args.level == "all" else [args.level]

    projects: list[Path] = []
    if not args.prompt_only:
        projects = select_projects(args)
        if not projects:
            print("No projects found.")
            return

    total_base = 0
    for level in levels:
        if not args.prompt_only:
            total_base += build_base_tasks(level, projects)
        if args.with_llm_description and level in {"L2", "L3"}:
            ok, failed, skipped = finalize_prompts(level, args)
            print(f"{level} prompt finalization: ok={ok}, failed={failed}, skipped={skipped}")

    if not args.prompt_only:
        print(f"\nDone. Base tasks generated: {total_base}")


if __name__ == "__main__":
    main()

