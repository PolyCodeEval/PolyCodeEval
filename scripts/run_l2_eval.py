#!/usr/bin/env python3
"""CLI entry point for L2 file-level evaluation."""

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

from l2_evaluator.scorer import aggregate  # noqa: E402
from l2_evaluator.solver import make_solver  # noqa: E402
from l2_evaluator.task import evaluate_task  # noqa: E402
from runner_lib import DATASETS_ROOT, discover_projects  # noqa: E402


def _is_l2_task(task_dir: Path) -> bool:
    task_json = task_dir / "task.json"
    if not task_json.is_file():
        return False
    with task_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("level") == "L2"


def discover_tasks(
    *,
    task: str | None = None,
    project: str | None = None,
    language: str | None = None,
    all_: bool = False,
) -> list[Path]:
    """Discover L2 task directories based on CLI filters."""
    if task:
        task_dir = Path(task)
        if not task_dir.is_absolute():
            task_dir = REPO_ROOT / task_dir
        if not _is_l2_task(task_dir):
            print(f"Error: not a valid L2 task directory: {task_dir}", file=sys.stderr)
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
            if d.is_dir() and _is_l2_task(d)
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
            if d.is_dir() and _is_l2_task(d):
                task_dirs.append(d)
    return task_dirs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run L2 file-level evaluation on PolyCodeEval tasks.",
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
    parser.add_argument("--workers", type=int, default=4, help="Concurrent Docker workers (default: 4)")
    parser.add_argument("--output", type=Path, default=None, help="Output directory for results")
    parser.add_argument(
        "--tests", choices=["both", "whitebox", "blackbox"], default="both",
        help="Test suites to run: both (default), whitebox only, or blackbox only",
    )
    parser.add_argument(
        "--docker-image",
        help="Override the runtime image for all selected tasks.",
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
        print("No L2 tasks found.")
        return 0

    output_dir = args.output
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        solver_tag = solver.name.replace("/", "_")
        output_dir = REPO_ROOT / "results" / f"l2_{solver_tag}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Solver:  {solver.name}")
    print(f"Tasks:   {len(task_dirs)}")
    print(f"Workers: {args.workers}")
    print(f"Tests:   {args.tests}")
    if getattr(args, "docker_image", None):
        print(f"Image:   {args.docker_image}")
    print(f"Output:  {output_dir}")
    print()

    # Group tasks by project — one container per project
    from collections import defaultdict
    from l2_evaluator.runner import ProjectContainer
    import json as _json

    def _load_json(p):
        with open(p) as f:
            return _json.load(f)

    projects: dict[Path, list[Path]] = defaultdict(list)
    for td in task_dirs:
        projects[td.parents[1]].append(td)

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

    def run_project(project_dir: Path, task_list: list[Path]) -> list[dict]:
        """Start one container for the project, run all its tasks, stop container."""
        language = project_dir.parent.name
        # Use first task's run_config (all tasks in same project share it)
        run_config = _load_json(task_list[0] / "run_config.json")
        src_dir = (task_list[0] / run_config["src_dir"]).resolve()
        tests_dir = project_dir / "tests"

        # install timeout: use project config.json or language default
        cfg_path = project_dir / "config.json"
        install_timeout = 900
        if cfg_path.exists():
            cfg = _load_json(cfg_path)
            install_timeout = cfg.get("timeout_seconds", install_timeout)

        container = ProjectContainer(
            project_dir, run_config, language,
            test_mode=args.tests,
            docker_image=getattr(args, "docker_image", "") or "",
        )
        results = []
        try:
            container.start(src_dir, tests_dir if tests_dir.is_dir() else None,
                            timeout=install_timeout)
            for td in task_list:
                result = evaluate_task(td, solver, output_dir, container,
                                       test_mode=args.tests)
                results.append(result)
                with lock:
                    nonlocal done_count, passed_count, failed_count
                    done_count += 1
                    if result.get("passed"):
                        passed_count += 1
                    else:
                        failed_count += 1
                        msg = result.get("error", "")
                        suffix = f"  error: {msg}" if msg else ""
                        sys.stderr.write(
                            f"\n  [FAIL] {result.get('task', td.name)}"
                            f"  ({result.get('duration_seconds', 0):.1f}s){suffix}\n"
                        )
                    sys.stderr.write(_progress_bar())
                    sys.stderr.flush()
        except Exception as e:
            # Container failed to start — mark all tasks as failed
            with lock:
                for td in task_list:
                    done_count += 1
                    failed_count += 1
                sys.stderr.write(f"\n  [CONTAINER FAIL] {project_dir.name}: {e}\n")
                sys.stderr.write(_progress_bar())
                sys.stderr.flush()
        finally:
            container.stop()
        return results

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_project, proj_dir, task_list): proj_dir
            for proj_dir, task_list in projects.items()
        }
        for future in as_completed(futures):
            proj_dir = futures[future]
            try:
                future.result()
            except Exception as e:
                sys.stderr.write(f"\n  ! Project {proj_dir.name} unhandled: {e}\n")
                sys.stderr.flush()

    sys.stderr.write("\n")

    print(f"\nDone: {passed_count} passed, {failed_count} failed out of {total_tasks}")

    summary = aggregate(output_dir)
    if summary:
        print(f"\nResults saved to: {output_dir}")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
