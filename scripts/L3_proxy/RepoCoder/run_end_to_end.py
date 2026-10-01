#!/usr/bin/env python3
"""Generate L3 outputs with RepoCoder, save precomputed files, then evaluate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RepoCoder end-to-end pipeline for PolyCodeEval L3")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--task", help="Single L3 task directory")
    scope.add_argument("--project", help="Project directory")
    scope.add_argument("--language", choices=["python", "cpp", "java", "javascript", "go"])
    scope.add_argument("--all", action="store_true", dest="all_", help="All L3 tasks")

    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--provider", choices=["openai", "anthropic"], default="openai")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent generation workers")
    parser.add_argument("--eval-workers", type=int, default=16, help="Concurrent evaluation workers")
    parser.add_argument("--limit", type=int, help="Limit discovered tasks")
    parser.add_argument("--resume", action="store_true", help="Skip generated outputs that already exist")
    parser.add_argument("--tests", choices=["both", "whitebox", "blackbox"], default="both")
    parser.add_argument("--output-dir", help="Custom output directory")
    return parser.parse_args()


def _generated_task_dirs(generated_code_dir: Path) -> list[Path]:
    task_dirs: list[Path] = []
    for txt_file in sorted(generated_code_dir.rglob("*.txt")):
        try:
            language = txt_file.parents[1].name
            project = txt_file.parent.name
            task_name = txt_file.stem
            task_dir = DATASETS_ROOT / language / project / "tasks" / task_name
            if task_dir.is_dir() and (task_dir / "task.json").is_file():
                task_dirs.append(task_dir)
        except Exception:
            continue
    return task_dirs


def _write_eval_manifest(task_dirs: list[Path], output_dir: Path) -> Path:
    manifest_dir = output_dir / "eval_manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "tasks.txt"
    manifest_path.write_text("".join(f"{task_dir}\n" for task_dir in task_dirs), encoding="utf-8")
    return manifest_path


def main() -> int:
    args = _parse_args()
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        scope_tag = "all"
        if args.task:
            scope_tag = Path(args.task).name
        elif args.project:
            scope_tag = Path(args.project).name
        elif args.language:
            scope_tag = args.language
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_tag = args.model.replace("/", "_").replace(":", "_")
        output_dir = REPO_ROOT / "output" / "repocoder_e2e" / f"{args.provider}_{model_tag}_{scope_tag}_{timestamp}"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("RepoCoder End-to-End Pipeline")
    print("=" * 60)
    print(f"Model:   {args.model}")
    print(f"Provider:{args.provider}")
    print(f"GenWorkers:  {args.workers}")
    print(f"EvalWorkers: {args.eval_workers}")
    print(f"Tests:   {args.tests}")
    print(f"Resume:  {args.resume}")
    print(f"Output:  {output_dir}")
    print()

    generate_cmd = [
        sys.executable,
        str(SCRIPT_DIR / "run_repocoder_batch.py"),
        "--model", args.model,
        "--solver-prefix", f"repocoder-{args.provider}",
        "--workers", str(args.workers),
        "--output-dir", str(output_dir),
    ]
    if args.resume:
        generate_cmd.append("--resume")
    if args.limit:
        generate_cmd.extend(["--limit", str(args.limit)])
    if args.task:
        generate_cmd.extend(["--task", args.task])
    elif args.project:
        generate_cmd.extend(["--project", args.project])
    elif args.language:
        generate_cmd.extend(["--language", args.language])
    else:
        generate_cmd.append("--all")

    gen_result = subprocess.run(generate_cmd, capture_output=False, text=True)
    if gen_result.returncode != 0:
        return gen_result.returncode

    generated_code_dir = output_dir / "generated_code"
    if not generated_code_dir.is_dir():
        print("No generated task outputs found; skipping evaluation.", file=sys.stderr)
        return 1

    generated_task_dirs = _generated_task_dirs(generated_code_dir)
    if not generated_task_dirs:
        print("No generated task outputs found; skipping evaluation.", file=sys.stderr)
        return 1

    manifest_path = _write_eval_manifest(generated_task_dirs, output_dir)

    eval_output_dir = output_dir / "eval_results"
    eval_script = f"""
import sys
from pathlib import Path
REPO_ROOT = Path({str(REPO_ROOT)!r})
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO_ROOT / "docker"))
from run_l3_eval import main as run_main

manifest = Path({str(manifest_path)!r}).read_text(encoding="utf-8").splitlines()
exit_code = 0
for task in manifest:
    rc = run_main([
        "--task", task,
        "--solver", {f"precomputed:{generated_code_dir}"!r},
        "--workers", {str(args.eval_workers)!r},
        "--tests", {args.tests!r},
        "--output", {str(eval_output_dir)!r},
    ])
    if rc != 0:
        exit_code = rc
raise SystemExit(exit_code)
"""
    eval_result = subprocess.run([sys.executable, "-c", eval_script], capture_output=False, text=True)
    summary_file = eval_output_dir / "summary.json"
    if not summary_file.exists():
        return eval_result.returncode

    summary = {
        "timestamp": datetime.now().isoformat(),
        "model": args.model,
        "provider": args.provider,
        "output_dir": str(output_dir),
        "generated_code_dir": str(generated_code_dir),
        "eval_output_dir": str(eval_output_dir),
        "evaluated_tasks": [str(task_dir) for task_dir in generated_task_dirs],
        "tests": args.tests,
        "gen_workers": args.workers,
        "eval_workers": args.eval_workers,
        "resume": args.resume,
    }
    (output_dir / "end_to_end_report.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"RepoCoder L3 results saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
