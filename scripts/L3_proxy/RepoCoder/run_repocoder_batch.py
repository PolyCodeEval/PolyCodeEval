#!/usr/bin/env python3
"""Batch-generate L3 function bodies with RepoCoder and save precomputed outputs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"
DEBUG_ROOT = REPO_ROOT / "results" / "l3_repocoder_debug"

sys.path.insert(0, str(SCRIPT_DIR))

from adapter import generate_function_body  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RepoCoder on PolyCodeEval L3 tasks")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--task", help="Single L3 task directory")
    scope.add_argument("--project", help="Project directory")
    scope.add_argument("--language", choices=["python", "cpp", "java", "javascript", "go"])
    scope.add_argument("--all", action="store_true", dest="all_", help="All L3 tasks")

    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument(
        "--solver-prefix",
        default="repocoder-openai",
        choices=["repocoder-openai", "repocoder-anthropic"],
        help="Solver prefix used to build the internal solver spec",
    )
    parser.add_argument("--workers", type=int, default=4, help="Concurrent generation workers")
    parser.add_argument("--limit", type=int, help="Limit number of discovered tasks")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--resume", action="store_true", help="Skip tasks with existing output files")
    parser.add_argument("--_single-task-output-file", help=argparse.SUPPRESS)
    parser.add_argument("--_single-task-quiet", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def _output_file(outputs_dir: Path, task_dir: Path) -> Path:
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    task_name = task_dir.name
    return outputs_dir / "generated_code" / language / project / f"{task_name}.txt"


def _failure_file(outputs_dir: Path) -> Path:
    return outputs_dir / "failures.json"


def _load_failures(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid failures json file: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"invalid failures json file: {path}: expected top-level object")
    return data


def _save_failures(path: Path, failures: dict[str, dict]) -> None:
    path.write_text(json.dumps(failures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _task_id(task_dir: Path) -> str:
    return f"{task_dir.parents[2].name}/{task_dir.parents[1].name}/{task_dir.name}"


def _task_debug_dir(task_dir: Path) -> Path:
    return DEBUG_ROOT / task_dir.parents[2].name / task_dir.parents[1].name / task_dir.name


def _load_task_usage(task_dir: Path) -> dict[str, object]:
    debug_dir = _task_debug_dir(task_dir)
    rounds = []
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    for usage_file in sorted(debug_dir.glob("usage_round*.json")):
        usage = json.loads(usage_file.read_text(encoding="utf-8"))
        round_name = usage_file.stem.removeprefix("usage_")
        rounds.append({"round": round_name, **usage})
        totals["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        totals["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    return {
        "rounds": rounds,
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "total_tokens": totals["total_tokens"],
    }


def _summary_file(outputs_dir: Path) -> Path:
    return outputs_dir / "summary.json"


def _load_previous_task_usages(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    per_task = data.get("per_task_token_usage")
    if not isinstance(per_task, dict):
        return {}
    normalized: dict[str, dict[str, object]] = {}
    for task_id, usage in per_task.items():
        if isinstance(task_id, str) and isinstance(usage, dict):
            normalized[task_id] = usage
    return normalized


def _has_task_usage(usage: dict[str, object]) -> bool:
    return bool(usage.get("rounds")) or any(
        int(usage.get(key, 0) or 0) > 0 for key in ("input_tokens", "output_tokens", "total_tokens")
    )


def _accumulate_task_usage(
    task_usages: dict[str, dict[str, object]],
    usage_totals: dict[str, int],
    task_id: str,
    usage: dict[str, object],
) -> None:
    if not _has_task_usage(usage):
        return
    task_usages[task_id] = usage
    usage_totals["input_tokens"] += int(usage["input_tokens"])
    usage_totals["output_tokens"] += int(usage["output_tokens"])
    usage_totals["total_tokens"] += int(usage["total_tokens"])


def _resolve_task_usage(
    task_dir: Path,
    task_id: str,
    previous_task_usages: dict[str, dict[str, object]],
) -> dict[str, object]:
    usage = _load_task_usage(task_dir)
    if _has_task_usage(usage):
        return usage
    previous_usage = previous_task_usages.get(task_id)
    if isinstance(previous_usage, dict):
        return previous_usage
    return usage


def _is_l3_task_dir(task_path: Path) -> bool:
    return task_path.is_dir() and task_path.name.startswith("L3_") and (task_path / "task.json").is_file()


def _discover_projects(language: str | None) -> list[Path]:
    if language:
        roots = [DATASETS_ROOT / language]
    else:
        roots = [p for p in DATASETS_ROOT.iterdir() if p.is_dir()]

    projects: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for project_dir in sorted(root.iterdir()):
            if (project_dir / "tasks").is_dir():
                projects.append(project_dir)
    return projects


def discover_tasks(
    *,
    task: str | None = None,
    project: str | None = None,
    language: str | None = None,
    all_: bool = False,
) -> list[Path]:
    if task:
        task_dir = Path(task)
        if not task_dir.is_absolute():
            task_dir = REPO_ROOT / task_dir
        if not (task_dir / "task.json").is_file():
            raise FileNotFoundError(f"not a valid task directory: {task_dir}")
        return [task_dir]

    if project:
        project_dir = Path(project)
        if not project_dir.is_absolute():
            project_dir = REPO_ROOT / project_dir
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            raise FileNotFoundError(f"no tasks/ directory in {project_dir}")
        return sorted(d for d in tasks_dir.iterdir() if _is_l3_task_dir(d))

    if not all_ and language is None:
        raise ValueError("specify --task, --project, --language, or --all")

    task_dirs: list[Path] = []
    for project_dir in _discover_projects(language):
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            continue
        for task_dir in sorted(tasks_dir.iterdir()):
            if _is_l3_task_dir(task_dir):
                task_dirs.append(task_dir)
    return task_dirs


def main() -> int:
    args = _parse_args()
    outputs_dir = Path(args.output_dir).resolve()
    outputs_dir.mkdir(parents=True, exist_ok=True)

    if args._single_task_output_file:
        return _run_single_task_child(args)

    task_dirs = discover_tasks(
        task=args.task,
        project=args.project,
        language=args.language,
        all_=args.all_,
    )
    if args.limit:
        task_dirs = task_dirs[: args.limit]

    solver_spec = f"{args.solver_prefix}/{args.model}"
    failures_path = _failure_file(outputs_dir)
    summary_path = _summary_file(outputs_dir)
    failures = _load_failures(failures_path)
    previous_task_usages = _load_previous_task_usages(summary_path) if args.resume else {}
    failures_lock = threading.Lock()
    progress_lock = threading.Lock()

    total = len(task_dirs)
    generated = 0
    skipped = 0
    failed = 0
    start_time = time.time()
    usage_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    task_usages: dict[str, dict[str, object]] = {}

    print("=" * 60)
    print("RepoCoder Batch Generation")
    print("=" * 60)
    print(f"Solver:  {solver_spec}")
    print(f"Tasks:   {total}")
    print(f"Workers: {args.workers}")
    print(f"Resume:  {args.resume}")
    print(f"Output:  {outputs_dir}")
    print()

    def _progress(done: int) -> str:
        elapsed = time.time() - start_time
        pct = done / total * 100 if total else 0
        bar_len = 30
        filled = int(bar_len * done / total) if total else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        eta_str = f"{int(eta // 60)}m{int(eta % 60):02d}s" if eta < 3600 else f"{eta / 3600:.1f}h"
        return (
            f"\r  [{bar}] {done}/{total} ({pct:.0f}%) "
            f"| ok:{generated} skip:{skipped} fail:{failed} "
            f"| {elapsed:.0f}s elapsed, ETA {eta_str}  "
        )

    def _run_one(task_dir: Path) -> tuple[str, str, str | None]:
        task_id = _task_id(task_dir)
        output_file = _output_file(outputs_dir, task_dir)
        if args.resume and output_file.exists():
            return task_id, "skipped", None

        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--task", str(task_dir),
            "--model", args.model,
            "--solver-prefix", args.solver_prefix,
            "--workers", "1",
            "--output-dir", str(outputs_dir),
            "--_single-task-output-file", str(output_file),
            "--_single-task-quiet",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=os.environ.copy(),
        )
        if proc.returncode == 0 and output_file.exists():
            return task_id, "generated", None

        error_text = "\n".join(
            part.strip() for part in (proc.stderr, proc.stdout) if part and part.strip()
        ).strip()
        if not error_text:
            error_text = f"child process exited with code {proc.returncode}"
        else:
            error_text = f"[exit_code={proc.returncode}]\n{error_text}"
        return task_id, "failed", error_text[-12000:]

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_run_one, task_dir): task_dir for task_dir in task_dirs}
        for future in as_completed(futures):
            task_dir = futures[future]
            task_id = _task_id(task_dir)
            status = "failed"
            error: str | None = "Unknown error"
            try:
                task_id, status, error = future.result()
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"

            with progress_lock:
                done += 1
                if status == "generated":
                    generated += 1
                    usage = _resolve_task_usage(task_dir, task_id, previous_task_usages)
                    _accumulate_task_usage(task_usages, usage_totals, task_id, usage)
                    with failures_lock:
                        if task_id in failures:
                            failures.pop(task_id, None)
                elif status == "skipped":
                    skipped += 1
                    usage = _resolve_task_usage(task_dir, task_id, previous_task_usages)
                    _accumulate_task_usage(task_usages, usage_totals, task_id, usage)
                else:
                    failed += 1
                    with failures_lock:
                        failures[task_id] = {
                            "task": task_id,
                            "error": error,
                            "timestamp": datetime.now().isoformat(),
                        }
                _save_failures(failures_path, failures)
                sys.stderr.write(_progress(done))
                sys.stderr.flush()

    sys.stderr.write("\n")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "solver": solver_spec,
        "model": args.model,
        "workers": args.workers,
        "resume": args.resume,
        "total_tasks": total,
        "generated": generated,
        "skipped": skipped,
        "failed": failed,
        "generated_code_dir": str((outputs_dir / "generated_code").resolve()),
        "failures_file": str(failures_path.resolve()),
        "token_usage_accounted_tasks": len(task_usages),
        "token_usage": {
            "input_tokens": usage_totals["input_tokens"],
            "output_tokens": usage_totals["output_tokens"],
            "total_tokens": usage_totals["total_tokens"],
        },
        "per_task_token_usage": task_usages,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Generated: {generated}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")
    print(f"Outputs:   {outputs_dir / 'generated_code'}")
    print(f"Summary:   {summary_path}")
    print(f"Failures:  {failures_path}")
    return 0


def _run_single_task_child(args: argparse.Namespace) -> int:
    task_dirs = discover_tasks(task=args.task)
    task_dir = task_dirs[0]
    solver_spec = f"{args.solver_prefix}/{args.model}"
    output_file = Path(args._single_task_output_file).resolve()
    try:
        body = generate_function_body(task_dir, solver_spec)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(body, encoding="utf-8")
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
