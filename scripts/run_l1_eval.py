#!/usr/bin/env python3
"""CLI entry point for L1 project-level evaluation."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO_ROOT / "docker"))

from l1_evaluator.scorer import aggregate  # noqa: E402
from l1_evaluator.solver import make_solver  # noqa: E402
from l1_evaluator.task import evaluate_task  # noqa: E402
from l0_evaluator.scoring.judge_clients import resolve_judge_provider_model  # noqa: E402
from runner_lib import DATASETS_ROOT, discover_projects  # noqa: E402


def _is_l1_task(task_dir: Path) -> bool:
    task_json = task_dir / "task.json"
    if not task_json.is_file():
        return False
    with task_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("level") == "L1"


def discover_tasks(
    *,
    task: str | None = None,
    project: str | None = None,
    language: str | None = None,
    all_: bool = False,
) -> list[Path]:
    """Discover L1 task directories based on CLI filters."""
    if task:
        task_dir = Path(task)
        if not task_dir.is_absolute():
            task_dir = REPO_ROOT / task_dir
        if not _is_l1_task(task_dir):
            print(f"Error: not a valid L1 task directory: {task_dir}", file=sys.stderr)
            sys.exit(1)
        return [task_dir]

    if project:
        project_dir = Path(project)
        if not project_dir.is_absolute():
            project_dir = REPO_ROOT / project_dir
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            print(f"Error: no tasks/ directory in {project_dir}", file=sys.stderr)
            sys.exit(1)
        return sorted(
            d for d in tasks_dir.iterdir()
            if d.is_dir() and _is_l1_task(d)
        )

    if not all_ and language is None:
        print("Error: specify --task, --project, --language, or --all", file=sys.stderr)
        sys.exit(1)

    project_dirs = discover_projects(language)
    task_dirs: list[Path] = []
    for proj_dir in project_dirs:
        tasks_dir = proj_dir / "tasks"
        if not tasks_dir.is_dir():
            continue
        for d in sorted(tasks_dir.iterdir()):
            if d.is_dir() and _is_l1_task(d):
                task_dirs.append(d)
    return task_dirs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run L1 project-level evaluation on PolyCodeEval tasks (blackbox only).",
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--task", help="Path to a single task directory")
    scope.add_argument("--project", help="Path to a project directory")
    scope.add_argument("--language", choices=["python", "cpp", "java", "javascript", "go"])
    scope.add_argument("--all", action="store_true", dest="all_", help="Evaluate all tasks")

    parser.add_argument(
        "--solver", required=True,
        help=(
            "Solver spec: oracle | anthropic/<model> | openai/<model> "
            "| precomputed:<outputs_dir>"
        ),
    )
    parser.add_argument(
        "--judge-provider", choices=["openai", "anthropic"], default=None,
        help="Judge provider for Faithfulness/Architecture scoring (default: from .env)",
    )
    parser.add_argument(
        "--judge-model", default=None,
        help="Judge model for Faithfulness/Architecture scoring (default: from .env)",
    )
    parser.add_argument("--workers", type=int, default=4, help="Concurrent Docker workers (default: 4)")
    parser.add_argument("--output", type=Path, default=None, help="Output directory for results")
    parser.add_argument("--detail", action="store_true", help="Show per-test-case detail in output")
    parser.add_argument(
        "--correctness-only", action="store_true", dest="correctness_only",
        help="Skip LLM judge (F/A/H). Only run blackbox tests and report Correctness score.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    solver = make_solver(args.solver)
    task_dirs = discover_tasks(
        task=args.task,
        project=args.project,
        language=args.language,
        all_=args.all_,
    )

    if not task_dirs:
        print("No L1 tasks found.")
        return 0

    judge_provider, judge_model = resolve_judge_provider_model(
        args.judge_provider, args.judge_model,
    )

    output_dir = args.output
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        solver_tag = solver.name.replace("/", "_")
        output_dir = REPO_ROOT / "results" / f"l1_{solver_tag}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Solver:  {solver.name}")
    print(f"Tasks:   {len(task_dirs)}")
    print(f"Workers: {args.workers}")
    print("Tests:   blackbox")
    print(f"Judge:   {judge_provider}/{judge_model}")
    print(f"Output:  {output_dir}")
    print()

    passed_count = 0
    failed_count = 0
    done_count = 0
    total_tasks = len(task_dirs)
    start_time = time.time()
    lock = threading.Lock()

    def _progress_bar():
        elapsed = time.time() - start_time
        pct = done_count / total_tasks * 100 if total_tasks else 0
        bar_len = 30
        filled = int(bar_len * done_count / total_tasks) if total_tasks else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        rate = done_count / elapsed if elapsed > 0 else 0
        eta = (total_tasks - done_count) / rate if rate > 0 else 0
        eta_str = f"{int(eta // 60)}m{int(eta % 60):02d}s" if eta < 3600 else f"{eta / 3600:.1f}h"
        return (
            f"\r  [{bar}] {done_count}/{total_tasks} ({pct:.0f}%) "
            f"| pass:{passed_count} fail:{failed_count} "
            f"| {elapsed:.0f}s elapsed, ETA {eta_str}  "
        )

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
                pool.submit(
                    evaluate_task, td, solver, output_dir,
                    judge_provider=judge_provider,
                    judge_model=judge_model,
                    correctness_only=args.correctness_only,
                ): td
                for td in task_dirs
            }
        for future in as_completed(futures):
            td = futures[future]
            try:
                result = future.result()
            except Exception as e:
                with lock:
                    failed_count += 1
                    done_count += 1
                    sys.stderr.write(f"\n  ! {td.name}  (unhandled: {e})\n")
                    sys.stderr.write(_progress_bar())
                    sys.stderr.flush()
                continue

            with lock:
                done_count += 1
                if result["passed"]:
                    passed_count += 1
                else:
                    failed_count += 1
                    msg = result.get("error", "")
                    suffix = f"  error: {msg}" if msg else ""
                    sys.stderr.write(f"\n  [FAIL] {result['task']}  ({result['duration_seconds']:.1f}s){suffix}\n")
                sys.stderr.write(_progress_bar())
                sys.stderr.flush()

    sys.stderr.write("\n")

    print(f"\nDone: {passed_count} passed, {failed_count} failed out of {total_tasks}")

    summary = aggregate(output_dir, detail=args.detail)
    if summary:
        print(f"\nResults saved to: {output_dir}")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
