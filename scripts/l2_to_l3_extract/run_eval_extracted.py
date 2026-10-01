#!/usr/bin/env python3
"""Run L3 evaluation on L2-extracted function bodies.

Task set is derived from the oracle dataset (all L3 tasks whose target file
also has an L2 task), making the denominator model-independent. Models that
failed to extract a function score 0 on that task.

Usage:
    conda run -n polycodeeval python scripts/l2_to_l3_extract/run_eval_extracted.py \
        --model l2_direct_full_sonnet \
        --output finalresults/L2toL3/l2toL3_eval_sonnet \
        --workers 16
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPTS_DIR.parent

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO_ROOT / "docker"))

from l3_evaluator.scorer import aggregate  # noqa: E402
from l3_evaluator.solver import make_solver  # noqa: E402
from run_l3_eval import _group_by_project, _run_project  # noqa: E402


def discover_oracle_tasks(datasets_dir: Path) -> list[Path]:
    """Return all L3 task dirs whose target file also has an L2 task.

    This set is fixed by the dataset structure — model-independent.
    Every model is evaluated against the same denominator.
    """
    # Step 1: collect (lang, project, target_file) covered by L2 tasks
    l2_target_files: set[tuple[str, str, str]] = set()
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
                with task_json.open(encoding="utf-8") as f:
                    data = json.load(f)
                target_file = data.get("stub_info", {}).get("file", "")
                if target_file:
                    l2_target_files.add((lang, project, target_file))

    # Step 2: collect L3 tasks whose file appears in the L2 coverage set
    task_dirs: list[Path] = []
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
                if not (task_dir.name.startswith("L3_") and (task_dir / "task.json").is_file()):
                    continue
                with (task_dir / "task.json").open(encoding="utf-8") as f:
                    data = json.load(f)
                target_file = data.get("stub_info", {}).get("file", "")
                if (lang, project, target_file) in l2_target_files:
                    task_dirs.append(task_dir)

    return task_dirs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run L3 evaluation on L2-extractable tasks (oracle-fixed task set)."
    )
    parser.add_argument(
        "--model", required=True,
        help="L2toL3 model directory name (e.g. l2_direct_full_sonnet)",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output directory for results")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent projects (default: 4)")
    parser.add_argument(
        "--tests", choices=["both", "whitebox", "blackbox"], default="both",
        help="Test suites to run (default: both)",
    )
    parser.add_argument(
        "--l2tol3-base", type=Path,
        default=REPO_ROOT / "All_answers" / "L2toL3",
        help="Base directory containing L2toL3 model outputs",
    )
    parser.add_argument(
        "--datasets", type=Path,
        default=REPO_ROOT / "datasets",
        help="Datasets directory",
    )
    parser.add_argument("--docker-image", default="", help="Override Docker image for all tasks")
    args = parser.parse_args(argv)

    generated_code_dir = args.l2tol3_base / args.model / "generated_code"
    solver = make_solver(f"precomputed:{generated_code_dir}")

    print("Building oracle task set from datasets...")
    task_dirs = discover_oracle_tasks(args.datasets)
    if not task_dirs:
        print("No oracle tasks found.")
        return 0

    args.output.mkdir(parents=True, exist_ok=True)
    project_groups = _group_by_project(task_dirs)
    total_tasks = sum(len(v) for v in project_groups.values())

    print(f"Model:    {args.model}")
    print(f"Solver:   {solver.name}")
    print(f"Tasks:    {total_tasks}  (oracle-fixed: same for all models)")
    print(f"Projects: {len(project_groups)}")
    print(f"Workers:  {args.workers}")
    print(f"Tests:    {args.tests}")
    print(f"Output:   {args.output}")
    print()

    passed_count = 0
    failed_count = 0
    done_count = 0
    start_time = time.time()
    lock = threading.Lock()

    def _progress_bar() -> str:
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
                _run_project, proj_dir, tasks, solver, args.output,
                test_mode=args.tests,
                docker_image=args.docker_image,
            ): proj_dir
            for proj_dir, tasks in project_groups.items()
        }
        for future in as_completed(futures):
            proj_dir = futures[future]
            try:
                results = future.result()
            except Exception as e:
                with lock:
                    task_count = len(project_groups[proj_dir])
                    failed_count += task_count
                    done_count += task_count
                    sys.stderr.write(f"\n  ! {proj_dir.name}  (unhandled: {e})\n")
                    sys.stderr.write(_progress_bar())
                    sys.stderr.flush()
                continue

            for result in results:
                with lock:
                    done_count += 1
                    if result.get("passed"):
                        passed_count += 1
                    else:
                        failed_count += 1
                        msg = result.get("error", "")
                        suffix = f"  error: {msg}" if msg else ""
                        sys.stderr.write(
                            f"\n  [FAIL] {result['task']}  "
                            f"({result.get('duration_seconds', 0):.1f}s){suffix}\n"
                        )
                    sys.stderr.write(_progress_bar())
                    sys.stderr.flush()

    sys.stderr.write("\n")
    print(f"\nDone: {passed_count} passed, {failed_count} failed out of {total_tasks}")
    aggregate(args.output)
    print(f"Results saved to: {args.output}")
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
