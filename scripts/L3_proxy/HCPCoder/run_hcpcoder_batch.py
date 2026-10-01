#!/usr/bin/env python3
"""Batch-generate L3 function bodies with HCP-Coder."""

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
DEBUG_ROOT = REPO_ROOT / "results" / "l3_hcpcoder_debug"

sys.path.insert(0, str(SCRIPT_DIR))

from adapter import generate_function_body, HCPCoderError  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HCP-Coder on PolyCodeEval L3 tasks")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--task")
    scope.add_argument("--project")
    scope.add_argument("--language")
    scope.add_argument("--all", action="store_true", dest="all_")
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def _solver_spec(provider: str, model: str) -> str:
    return f"hcpcoder-{provider}/{model}"


def _output_file(outputs_dir: Path, task_dir: Path) -> Path:
    return outputs_dir / "generated_code" / task_dir.parents[2].name / task_dir.parents[1].name / f"{task_dir.name}.txt"


def _raw_output_file(outputs_dir: Path, task_dir: Path) -> Path:
    return outputs_dir / "raw_completion" / task_dir.parents[2].name / task_dir.parents[1].name / f"{task_dir.name}.txt"


def _task_id(task_dir: Path) -> str:
    return f"{task_dir.parents[2].name}/{task_dir.parents[1].name}/{task_dir.name}"


def _task_debug_dir(task_dir: Path) -> Path:
    return DEBUG_ROOT / task_dir.parents[2].name / task_dir.parents[1].name / task_dir.name


def _load_task_usage(task_dir: Path) -> dict:
    debug_dir = _task_debug_dir(task_dir)
    totals = {"input_tokens": 0, "output_tokens": 0, "embedding_tokens": 0, "total_tokens": 0}
    rounds = []
    for usage_file in sorted(debug_dir.glob("usage_round*.json")):
        try:
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        rounds.append({"round": usage_file.stem.removeprefix("usage_"), **usage})
        for k in totals:
            totals[k] += int(usage.get(k, 0) or 0)
    return {"rounds": rounds, **totals}


def _has_task_usage(usage: dict) -> bool:
    return bool(usage.get("rounds")) or any(
        int(usage.get(k, 0) or 0) > 0 for k in ("input_tokens", "output_tokens", "total_tokens")
    )


def _accumulate(task_usages, usage_totals, task_id, usage):
    if not _has_task_usage(usage):
        return
    task_usages[task_id] = usage
    for k in usage_totals:
        usage_totals[k] += int(usage.get(k, 0) or 0)


def _load_failures(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_failures(path: Path, failures: dict) -> None:
    path.write_text(json.dumps(failures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _is_l3_task_dir(p: Path) -> bool:
    return p.is_dir() and p.name.startswith("L3_") and (p / "task.json").is_file()


def _discover_projects(language):
    roots = [DATASETS_ROOT / language] if language else [p for p in DATASETS_ROOT.iterdir() if p.is_dir()]
    projects = []
    for root in roots:
        if not root.is_dir():
            continue
        for project_dir in sorted(root.iterdir()):
            if (project_dir / "tasks").is_dir():
                projects.append(project_dir)
    return projects


def discover_tasks(*, task=None, project=None, language=None, all_=False):
    if task:
        d = Path(task) if Path(task).is_absolute() else REPO_ROOT / task
        if not (d / "task.json").is_file():
            raise FileNotFoundError(f"not a valid task directory: {d}")
        return [d]
    if project:
        d = Path(project) if Path(project).is_absolute() else REPO_ROOT / project
        tasks_dir = d / "tasks"
        if not tasks_dir.is_dir():
            raise FileNotFoundError(f"no tasks/ directory in {d}")
        return sorted(t for t in tasks_dir.iterdir() if _is_l3_task_dir(t))
    if not all_ and language is None:
        raise ValueError("specify --task, --project, --language, or --all")
    result = []
    for proj in _discover_projects(language):
        tasks_dir = proj / "tasks"
        if tasks_dir.is_dir():
            result.extend(t for t in sorted(tasks_dir.iterdir()) if _is_l3_task_dir(t))
    return result


def main() -> int:
    args = _parse_args()
    outputs_dir = Path(args.output_dir).resolve()
    outputs_dir.mkdir(parents=True, exist_ok=True)

    task_dirs = discover_tasks(task=args.task, project=args.project, language=args.language, all_=args.all_)
    if args.limit:
        task_dirs = task_dirs[:args.limit]

    solver_spec = _solver_spec(args.provider, args.model)
    failures_path = outputs_dir / "failures.json"
    failures = _load_failures(failures_path)

    total = len(task_dirs)
    generated = skipped = failed = 0
    start_time = time.time()
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "embedding_tokens": 0, "total_tokens": 0}
    task_usages: dict = {}

    print("=" * 60)
    print("HCP-Coder Batch Generation")
    print("=" * 60)
    print(f"Solver:    {solver_spec}")
    print(f"Tasks:     {total}")
    print(f"Resume:    {args.resume}")
    print(f"Output:    {outputs_dir}\n")

    for i, task_dir in enumerate(task_dirs, 1):
        task_id = _task_id(task_dir)
        output_file = _output_file(outputs_dir, task_dir)

        if args.resume and output_file.exists():
            skipped += 1
            _accumulate(task_usages, usage_totals, task_id, _load_task_usage(task_dir))
            _print_progress(i, total, generated, skipped, failed, start_time)
            continue

        try:
            body = generate_function_body(task_dir, solver_spec)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(body, encoding="utf-8")
            raw_src = _task_debug_dir(task_dir) / "raw_completion.txt"
            if raw_src.exists():
                raw_file = _raw_output_file(outputs_dir, task_dir)
                raw_file.parent.mkdir(parents=True, exist_ok=True)
                raw_file.write_text(raw_src.read_text(encoding="utf-8"), encoding="utf-8")
            generated += 1
            failures.pop(task_id, None)
            _accumulate(task_usages, usage_totals, task_id, _load_task_usage(task_dir))
        except Exception as exc:
            failed += 1
            failures[task_id] = {"task": task_id, "error": f"{type(exc).__name__}: {exc}", "timestamp": datetime.now().isoformat()}
            print(f"\n  FAILED {task_id}: {type(exc).__name__}: {exc}", file=sys.stderr)

        _save_failures(failures_path, failures)
        _print_progress(i, total, generated, skipped, failed, start_time)

    print()

    summary = {
        "timestamp": datetime.now().isoformat(),
        "solver": solver_spec, "model": args.model, "provider": args.provider,
        "resume": args.resume, "total_tasks": total,
        "generated": generated, "skipped": skipped, "failed": failed,
        "generated_code_dir": str((outputs_dir / "generated_code").resolve()),
        "failures_file": str(failures_path.resolve()),
        "token_usage_accounted_tasks": len(task_usages),
        "token_usage": usage_totals,
        "per_task_token_usage": task_usages,
    }
    summary_path = outputs_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Generated: {generated}\nSkipped:   {skipped}\nFailed:    {failed}")
    print(f"Token usage: in={usage_totals['input_tokens']} out={usage_totals['output_tokens']} total={usage_totals['total_tokens']}")
    print(f"Outputs:   {outputs_dir / 'generated_code'}\nSummary:   {summary_path}")
    if failures:
        print(f"Failures:  {failures_path}")
    return 0 if failed == 0 else 1


def _print_progress(done, total, ok, skip, fail, start):
    elapsed = time.time() - start
    pct = done / total * 100 if total else 0
    filled = int(30 * done / total) if total else 0
    bar = "█" * filled + "░" * (30 - filled)
    rate = done / elapsed if elapsed > 0 else 0
    eta = (total - done) / rate if rate > 0 else 0
    eta_str = f"{int(eta // 60)}m{int(eta % 60):02d}s" if eta < 3600 else f"{eta / 3600:.1f}h"
    sys.stderr.write(f"\r  [{bar}] {done}/{total} ({pct:.0f}%) | ok:{ok} skip:{skip} fail:{fail} | {elapsed:.0f}s elapsed, ETA {eta_str}  ")
    sys.stderr.flush()


if __name__ == "__main__":
    raise SystemExit(main())
