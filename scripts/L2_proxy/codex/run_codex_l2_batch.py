#!/usr/bin/env python3
"""Batch-generate L2 files with Codex CLI."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from adapter import CodexL2Error, _DEFAULT_MODEL, generate_file  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex CLI on L2 tasks")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--task", nargs="+", help="One or more task directories")
    scope.add_argument("--project", help="Project name (all L2 tasks in it)")
    scope.add_argument("--language", help="Language (all L2 tasks)")
    scope.add_argument("--all", action="store_true", dest="all_")
    parser.add_argument("--model", default=_DEFAULT_MODEL, help="Only gpt-5.4 is supported")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, help="Max tasks to process")
    return parser.parse_args()


def _is_l2_task_dir(p: Path) -> bool:
    return (
        p.is_dir()
        and p.name.startswith("L2_")
        and (p / "task.json").exists()
        and (p / "prompt.md").exists()
    )


def _discover_tasks(args: argparse.Namespace) -> list[Path]:
    if args.task:
        result = []
        for t in args.task:
            task_dir = Path(t).resolve()
            if not _is_l2_task_dir(task_dir):
                sys.exit(f"Not a valid L2 task dir: {task_dir}")
            result.append(task_dir)
        return result

    tasks: list[Path] = []
    for lang_dir in sorted(DATASETS_ROOT.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue
        if args.language and lang_dir.name != args.language:
            continue
        for proj_dir in sorted(lang_dir.iterdir()):
            if not proj_dir.is_dir() or proj_dir.name == "README.md":
                continue
            if args.project and proj_dir.name != args.project:
                continue
            tasks_dir = proj_dir / "tasks"
            if not tasks_dir.is_dir():
                continue
            for task_dir in sorted(tasks_dir.iterdir()):
                if _is_l2_task_dir(task_dir):
                    tasks.append(task_dir)
    return tasks


def _task_id(task_dir: Path) -> str:
    return f"{task_dir.parents[2].name}/{task_dir.parents[1].name}/{task_dir.name}"


def _debug_dir(output_dir: Path, task_dir: Path) -> Path:
    return (
        output_dir / "debug" / task_dir.parents[2].name /
        task_dir.parents[1].name / task_dir.name
    )


def _output_file(output_dir: Path, task_dir: Path) -> Path:
    return (
        output_dir / "generated_outputs" / task_dir.parents[2].name /
        task_dir.parents[1].name / f"{task_dir.name}.txt"
    )


def _is_done(output_dir: Path, task_dir: Path) -> bool:
    return (_debug_dir(output_dir, task_dir) / "_done").exists()


def main() -> None:
    args = _parse_args()
    if args.model != _DEFAULT_MODEL:
        sys.exit(f"Unsupported model: {args.model}. Only {_DEFAULT_MODEL} is supported.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    tasks = _discover_tasks(args)
    if args.resume:
        tasks = [t for t in tasks if not _is_done(args.output_dir, t)]
    if args.limit:
        tasks = tasks[:args.limit]

    print("=" * 60)
    print("Codex L2 Batch Generation")
    print("=" * 60)
    print(f"Model:     {args.model}")
    print(f"Tasks:     {len(tasks)}")
    print(f"Resume:    {args.resume}")
    print(f"Output:    {args.output_dir}")
    print()

    usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0}
    task_usages: dict[str, dict] = {}
    failures: dict[str, str] = {}
    generated = 0
    start_time = time.time()

    for i, task_dir in enumerate(tasks, 1):
        tid = _task_id(task_dir)
        print(f"[{i}/{len(tasks)}] {tid} ...", end=" ", flush=True)

        try:
            content, usage = generate_file(task_dir, args.model, args.output_dir)

            out_file = _output_file(args.output_dir, task_dir)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(content, encoding="utf-8")

            (_debug_dir(args.output_dir, task_dir) / "_done").touch()

            task_usages[tid] = usage
            for k in ("input_tokens", "output_tokens", "total_tokens"):
                usage_totals[k] += int(usage.get(k, 0) or 0)
            if usage.get("cost_usd"):
                usage_totals["cost_usd"] += float(usage["cost_usd"])

            generated += 1
            print(
                f"ok ({usage.get('duration_s', 0):.0f}s, "
                f"in={usage.get('input_tokens', 0)}, out={usage.get('output_tokens', 0)})"
            )
        except (CodexL2Error, Exception) as e:
            failures[tid] = str(e)
            print(f"FAIL: {str(e)[:80]}")

    total_elapsed = time.time() - start_time

    print()
    print("=" * 60)
    print(f"Generated: {generated}")
    print(f"Failed:    {len(failures)}")
    print(f"Time:      {total_elapsed:.0f}s")
    print(
        f"Tokens:    in={usage_totals['input_tokens']} "
        f"out={usage_totals['output_tokens']} total={usage_totals['total_tokens']}"
    )

    summary = {
        "solver": f"codex/{args.model}",
        "model": args.model,
        "level": "L2",
        "generated": generated,
        "failed": len(failures),
        "skipped": 0,
        "total_elapsed_s": round(total_elapsed, 1),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "token_usage": usage_totals,
        "per_task": task_usages,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if failures:
        (args.output_dir / "failures.json").write_text(
            json.dumps(failures, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(f"Summary:   {args.output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
