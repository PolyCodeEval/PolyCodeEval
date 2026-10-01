#!/usr/bin/env python3
"""CLI entry point for L3 function-level evaluation."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO_ROOT / "docker"))

from l3_evaluator.runner import ProjectContainer  # noqa: E402
from l3_evaluator.scorer import aggregate  # noqa: E402
from l3_evaluator.solver import make_solver  # noqa: E402
from l3_evaluator.task import evaluate_task  # noqa: E402
from runner_lib import DATASETS_ROOT, discover_projects  # noqa: E402


def _is_l3_task_dir(task_path: Path) -> bool:
    return task_path.is_dir() and task_path.name.startswith("L3_") and (task_path / "task.json").is_file()


def discover_tasks(
    *,
    task: str | None = None,
    project: str | None = None,
    language: str | None = None,
    all_: bool = False,
) -> list[Path]:
    """Discover L3 task directories based on CLI filters."""
    if task:
        task_dir = Path(task)
        if not task_dir.is_absolute():
            task_dir = REPO_ROOT / task_dir
        if not (task_dir / "task.json").is_file():
            print(f"Error: not a valid task directory: {task_dir}", file=sys.stderr)
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
        return sorted(d for d in tasks_dir.iterdir() if _is_l3_task_dir(d))

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
            if _is_l3_task_dir(d):
                task_dirs.append(d)
    return task_dirs


def _group_by_project(task_dirs: list[Path]) -> dict[Path, list[Path]]:
    """Group task dirs by their project directory (parent of tasks/)."""
    groups: dict[Path, list[Path]] = defaultdict(list)
    for td in task_dirs:
        project_dir = td.parents[1]
        groups[project_dir].append(td)
    return dict(groups)


def _run_project(
    project_dir: Path,
    task_dirs: list[Path],
    solver,
    output_dir: Path,
    *,
    test_mode: str = "both",
    docker_image: str = "",
) -> list[dict]:
    """Run all tasks for a single project using a shared long-running container."""
    first_task = task_dirs[0]
    with open(first_task / "run_config.json", encoding="utf-8") as f:
        run_config = json.load(f)
    language = project_dir.parent.name

    timeout = 900 if language == "java" else 600
    container = ProjectContainer(
        project_dir, run_config, language,
        test_mode=test_mode,
        docker_image=docker_image,
    )
    results = []
    try:
        container.start(timeout=timeout)
        for td in task_dirs:
            result = evaluate_task(td, solver, output_dir, container=container, test_mode=test_mode)
            results.append(result)
    except Exception as e:
        for td in task_dirs:
            task_id = f"{language}/{project_dir.name}/{td.name}"
            result_path = output_dir / language / project_dir.name / f"{td.name}.json"
            if result_path.exists():
                continue
            result = {
                "task": task_id,
                "solver": solver.name,
                "passed": False,
                "exit_code": -1,
                "duration_seconds": 0.0,
                "stdout": "",
                "stderr": "",
                "error": f"Container setup failed: {e}",
            }
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with result_path.open("w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
                f.write("\n")
            results.append(result)
    finally:
        container.stop()
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run L3 function-level evaluation on PolyCodeEval tasks.",
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
            "| precomputed:<outputs_dir> | repocoder-openai/<model> "
            "| aligncoder-openai/<model> | hcpcoder-openai/<model>"
        ),
    )
    parser.add_argument("--workers", type=int, default=4, help="Concurrent projects (default: 4)")
    parser.add_argument("--output", type=Path, default=None, help="Output directory for results")
    parser.add_argument(
        "--tests", choices=["both", "whitebox", "blackbox"], default="both",
        help="Test suites to run: both (default), whitebox only, or blackbox only",
    )
    parser.add_argument(
        "--docker-image",
        help=(
            "Override the runtime image for all selected tasks. "
            "install_command is skipped only when the image already contains "
            "a preloaded project workspace under /opt/pce-projects/<lang>/<project>."
        ),
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
        print("No tasks found.")
        return 0

    output_dir = args.output
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        solver_tag = solver.name.replace("/", "_")
        output_dir = REPO_ROOT / "results" / f"l3_{solver_tag}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    project_groups = _group_by_project(task_dirs)
    total_tasks = sum(len(v) for v in project_groups.values())

    print(f"Solver:   {solver.name}")
    print(f"Tasks:    {total_tasks}")
    print(f"Projects: {len(project_groups)}")
    print(f"Workers:  {args.workers}")
    print(f"Tests:    {args.tests}")
    if args.docker_image:
        print(f"Image:    {args.docker_image}")
    print(f"Output:   {output_dir}")
    print()

    passed_count = 0
    failed_count = 0
    done_count = 0
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
                _run_project, proj_dir, tasks, solver, output_dir,
                test_mode=args.tests,
                docker_image=args.docker_image or "",
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

    summary = aggregate(output_dir)
    if summary:
        print(f"\nResults saved to: {output_dir}")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
