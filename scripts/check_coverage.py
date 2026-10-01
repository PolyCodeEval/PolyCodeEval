#!/usr/bin/env python3
"""Unified coverage analysis tool for PolyCodeEval (L0–L3).

Runs the project's test suite with coverage instrumentation inside Docker,
then produces:
  - Per-project JSON with overall line coverage % and per-task covered/uncovered
  - Native coverage artifacts saved to --artifacts directory
  - Aggregated summary.json

Usage examples:
  python scripts/check_coverage.py --language go --workers 2
  python scripts/check_coverage.py --project datasets/go/chi
  python scripts/check_coverage.py --all --workers 4
  python scripts/check_coverage.py --language python --level L3
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_REPO / "docker") not in sys.path:
    sys.path.insert(0, str(_REPO / "docker"))

from coverage.runner import (  # noqa: E402
    discover_project_list,
    run_coverage_for_project,
    write_summary,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run coverage analysis for PolyCodeEval projects (L0–L3).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--project", help="Path to a single project directory")
    scope.add_argument(
        "--language",
        choices=["python", "cpp", "java", "javascript", "go", "typescript"],
        help="Analyze all projects for this language",
    )
    scope.add_argument("--all", action="store_true", dest="all_", help="Analyze all projects")

    parser.add_argument(
        "--level",
        choices=["L0", "L1", "L2", "L3", "all"],
        default="all",
        help="Task level(s) to analyze (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory for JSON reports (default: results/coverage/)",
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=None,
        help="Directory to save native coverage artifacts (default: results/coverage_artifacts/)",
    )
    parser.add_argument("--workers", type=int, default=2, help="Concurrent Docker workers (default: 2)")
    parser.add_argument("--force", action="store_true", help="Re-run even if output already exists")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.project and not args.language and not args.all_:
        print("Error: specify --project, --language, or --all", file=sys.stderr)
        return 1

    output_dir = args.output
    if output_dir is None:
        output_dir = _REPO / "results" / "coverage"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts_dir = args.artifacts
    if artifacts_dir is None:
        artifacts_dir = _REPO / "results" / "coverage_artifacts"
    artifacts_dir = artifacts_dir.resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    level_filter = None if args.level == "all" else args.level

    try:
        projects = discover_project_list(
            project=args.project,
            language=args.language,
            all_=args.all_,
            level=level_filter,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not projects:
        print("No projects found.")
        return 0

    print(f"Projects: {len(projects)}")
    print(f"Level:    {args.level}")
    print(f"Workers:  {args.workers}")
    print(f"Output:   {output_dir}")
    print(f"Artifacts:{artifacts_dir}")
    print()

    results: list[tuple[str, str, dict | None, str | None]] = []  # (status, display, data, err)

    def _run_one(project_dir: Path) -> tuple[str, str, dict | None, str | None]:
        lang = project_dir.parent.name
        display = f"{lang}/{project_dir.name}"
        try:
            out_path = run_coverage_for_project(
                project_dir,
                output_dir,
                artifacts_dir,
                level=level_filter,
                force=args.force,
            )
            import json
            data = json.loads(out_path.read_text(encoding="utf-8"))
            exit_code = data.get("docker_exit_code")
            pct = data.get("line_coverage_pct")
            if exit_code is not None and exit_code != 0:
                status = "WARN"
            elif data.get("skip_reason") or data.get("note"):
                status = "SKIP"
            else:
                status = "OK"
            return status, display, data, None
        except Exception as e:
            return "ERR", display, None, str(e)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_run_one, p): p for p in projects}
        for future in as_completed(futures):
            status, display, data, err = future.result()
            if err:
                print(f"  [ERR]  {display}  error: {err}")
                results.append(("ERR", display, None, err))
                continue

            pct = data.get("line_coverage_pct")
            covered = data.get("covered", 0) or 0
            uncovered = data.get("uncovered", 0) or 0
            unknown = data.get("unknown", 0) or 0
            total = data.get("total_tasks", 0) or 0

            pct_str = f"  line_cov={pct:.1f}%" if pct is not None else ""
            note = data.get("note") or data.get("skip_reason") or ""
            note_str = f"  [{note}]" if note else ""

            print(
                f"  [{status}]  {display}"
                f"  tasks={total} covered={covered} uncovered={uncovered} unknown={unknown}"
                f"{pct_str}{note_str}"
            )
            results.append((status, display, data, None))

    # Write summary
    summary_path = write_summary(output_dir)

    # Print aggregate stats
    total_projects = len(results)
    ok_count = sum(1 for s, _, _, _ in results if s == "OK")
    warn_count = sum(1 for s, _, _, _ in results if s == "WARN")
    err_count = sum(1 for s, _, _, _ in results if s == "ERR")
    skip_count = sum(1 for s, _, _, _ in results if s == "SKIP")

    all_pcts = [d["line_coverage_pct"] for _, _, d, _ in results if d and d.get("line_coverage_pct") is not None]
    avg_pct = sum(all_pcts) / len(all_pcts) if all_pcts else None

    total_covered = sum((d.get("covered") or 0) for _, _, d, _ in results if d)
    total_uncovered = sum((d.get("uncovered") or 0) for _, _, d, _ in results if d)
    total_unknown = sum((d.get("unknown") or 0) for _, _, d, _ in results if d)
    total_tasks = total_covered + total_uncovered + total_unknown

    print()
    print("=" * 60)
    print(f"Projects: {total_projects}  OK={ok_count}  WARN={warn_count}  SKIP={skip_count}  ERR={err_count}")
    if avg_pct is not None:
        print(f"Avg line coverage: {avg_pct:.1f}%  (across {len(all_pcts)} projects with data)")
    print(f"Tasks: {total_tasks}  covered={total_covered}  uncovered={total_uncovered}  unknown={total_unknown}")
    print(f"Summary: {summary_path}")
    print("=" * 60)

    return 0 if err_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
