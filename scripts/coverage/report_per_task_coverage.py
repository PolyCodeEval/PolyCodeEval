#!/usr/bin/env python3
"""Generate per-task coverage percentage report from existing artifacts.

For L2 tasks: computes per-file line coverage rate.
For L3 tasks: computes per-function line coverage rate.
For L0/L1 tasks: uses whole-project line coverage.

Usage:
  python scripts/report_per_task_coverage.py --all
  python scripts/report_per_task_coverage.py --language python
  python scripts/report_per_task_coverage.py --language go --project chi
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from l3_evaluator.workspace import _resolve_file  # noqa: E402
from coverage.parsers import byte_to_line
from coverage.per_task_pct import (
    CovResult,
    cpp_file_line_pct,
    cpp_func_line_pct,
    go_file_line_pct,
    go_func_line_pct,
    java_file_line_pct,
    java_func_line_pct,
    js_file_line_pct,
    python_file_line_pct,
    python_func_line_pct,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate per-task coverage % report.")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--project", help="Single project name (requires --language)")
    scope.add_argument("--all", action="store_true", dest="all_")

    parser.add_argument(
        "--language",
        choices=["python", "cpp", "java", "javascript", "go"],
        help="Language filter",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory with existing coverage JSON results (default: finalresults/coverage/)",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Directory with coverage artifacts (default: results/coverage_artifacts/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for the report (default: finalresults/coverage_report/)",
    )
    return parser.parse_args(argv)


def _find_jacoco_xml(artifacts_dir: Path) -> Path | None:
    for name in ("jacoco.xml", "jacocoTestReport.xml"):
        p = artifacts_dir / name
        if p.is_file():
            return p
    return None


def compute_task_coverage(
    task_name: str,
    task_info: dict,
    language: str,
    project_dir: Path,
    artifacts_dir: Path,
    project_pct: float | None,
    project_lines_covered: int | None,
    project_lines_total: int | None,
) -> dict | None:
    """Compute coverage percentage for a single task.

    Returns None if the task cannot be measured (file not instrumented,
    task dir doesn't exist, etc.) — these are excluded from stats.
    """
    level = task_info.get("level", "")
    file_ = task_info.get("file", "")
    func_ = task_info.get("func", "")

    if level in ("L0", "L1"):
        if project_pct is None:
            return None
        return {
            "level": level,
            "file": file_,
            "func": func_,
            "coverage_pct": project_pct,
            "lines_covered": project_lines_covered or 0,
            "lines_total": project_lines_total or 0,
        }

    src_root = project_dir / "src"
    task_json_path = project_dir / "tasks" / task_name / "task.json"

    # Skip tasks whose task directory doesn't exist in the dataset
    if not task_json_path.is_file() and level in ("L2", "L3"):
        if not (project_dir / "tasks" / task_name).is_dir():
            return None

    if level == "L2":
        if not file_:
            return None
        resolved = _resolve_file(src_root, file_) if src_root.is_dir() else file_
        covered, total, pct = _compute_file_pct(language, artifacts_dir, resolved, file_)
        if pct is None or total is None or total == 0:
            return None
        return {
            "level": level,
            "file": file_,
            "func": func_,
            "coverage_pct": pct,
            "lines_covered": covered or 0,
            "lines_total": total,
        }

    if level == "L3":
        if not file_:
            return None
        stub_info = _load_stub_info(task_json_path)
        body_start = stub_info.get("body_start_byte")
        body_end = stub_info.get("body_end_byte")
        if body_start is None:
            return None

        resolved = _resolve_file(src_root, file_) if src_root.is_dir() else file_
        src_path = src_root / resolved
        if not src_path.is_file():
            return None

        src_bytes = src_path.read_bytes()
        start_line = byte_to_line(src_bytes, int(body_start))
        end_byte = int(body_end) - 1 if body_end is not None else int(body_start)
        end_byte = max(int(body_start), end_byte)
        end_line = byte_to_line(src_bytes, end_byte)

        covered, total, pct = _compute_func_pct(
            language, artifacts_dir, resolved, file_, start_line, end_line
        )
        if pct is None or total is None or total == 0:
            return None
        return {
            "level": level,
            "file": file_,
            "func": func_,
            "coverage_pct": pct,
            "lines_covered": covered or 0,
            "lines_total": total,
        }

    return None


def _load_stub_info(task_json_path: Path) -> dict:
    if not task_json_path.is_file():
        return {}
    try:
        data = json.loads(task_json_path.read_text(encoding="utf-8"))
        return data.get("stub_info") or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _compute_file_pct(language: str, artifacts_dir: Path, resolved: str, stub_file: str) -> CovResult:
    basename = Path(resolved).name

    if language == "python":
        return python_file_line_pct(artifacts_dir / "coverage.json", resolved, stub_file)
    if language == "go":
        cover_out = artifacts_dir / "cover.out"
        return go_file_line_pct(cover_out, basename, stub_file)
    if language == "java":
        xml = _find_jacoco_xml(artifacts_dir)
        if xml:
            return java_file_line_pct(xml, stub_file)
        return None, None, None
    if language == "cpp":
        return cpp_file_line_pct(artifacts_dir / "lcov.info", stub_file)
    if language in ("javascript", "typescript"):
        return js_file_line_pct(artifacts_dir / "coverage-summary.json", basename, stub_file)
    return None, None, None


def _compute_func_pct(
    language: str, artifacts_dir: Path, resolved: str, stub_file: str, start_line: int, end_line: int
) -> CovResult:
    basename = Path(resolved).name

    if language == "python":
        return python_func_line_pct(
            artifacts_dir / "coverage.json", resolved, stub_file, start_line, end_line
        )
    if language == "go":
        return go_func_line_pct(artifacts_dir / "cover.out", basename, start_line, end_line, stub_file)
    if language == "java":
        xml = _find_jacoco_xml(artifacts_dir)
        if xml:
            return java_func_line_pct(xml, stub_file, start_line, end_line)
        return None, None, None
    if language == "cpp":
        return cpp_func_line_pct(artifacts_dir / "lcov.info", stub_file, start_line, end_line)
    if language in ("javascript", "typescript"):
        return js_file_line_pct(artifacts_dir / "coverage-summary.json", basename, stub_file)
    return None, None, None


def process_project(
    project_json_path: Path,
    datasets_dir: Path,
    artifacts_base_dir: Path,
    output_dir: Path,
) -> dict | None:
    """Process one project JSON and write per-level report files.

    Output structure:
      output_dir/L0/<lang>/<project>.json
      output_dir/L1/<lang>/<project>.json
      output_dir/L2/<lang>/<project>.json
      output_dir/L3/<lang>/<project>.json
    """
    try:
        data = json.loads(project_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    project_name = data.get("project", "")
    language = data.get("language", "")
    tasks = data.get("tasks") or {}
    if not tasks:
        return None

    project_pct = data.get("line_coverage_pct")
    project_lines_covered = data.get("lines_covered")
    project_lines_total = data.get("lines_total")

    lang_dir = "javascript" if language == "typescript" else language
    project_dir = datasets_dir / lang_dir / project_name
    artifacts_dir = artifacts_base_dir / lang_dir / project_name

    if not artifacts_dir.is_dir():
        return None

    # Compute coverage for all tasks and group by level
    tasks_by_level: dict[str, dict[str, dict]] = {}
    for task_name, task_info in tasks.items():
        result = compute_task_coverage(
            task_name, task_info, language, project_dir, artifacts_dir,
            project_pct, project_lines_covered, project_lines_total,
        )
        if result is None:
            continue
        lvl = result["level"]
        if lvl not in tasks_by_level:
            tasks_by_level[lvl] = {}
        tasks_by_level[lvl][task_name] = result

    # Write one JSON per level
    summary_by_level: dict = {}
    for lvl, lvl_tasks in sorted(tasks_by_level.items()):
        pcts = [t["coverage_pct"] for t in lvl_tasks.values()]
        count = len(pcts)
        avg_pct = round(sum(pcts) / count, 1) if count > 0 else 0.0
        min_pct = min(pcts) if pcts else 0.0
        max_pct = max(pcts) if pcts else 0.0

        payload = {
            "project": project_name,
            "language": language,
            "project_line_coverage_pct": project_pct if project_pct is not None else 0.0,
            "project_lines_covered": project_lines_covered if project_lines_covered is not None else 0,
            "project_lines_total": project_lines_total if project_lines_total is not None else 0,
            "level": lvl,
            "task_count": count,
            "avg_coverage_pct": avg_pct,
            "min_coverage_pct": min_pct,
            "max_coverage_pct": max_pct,
            "tasks": lvl_tasks,
        }

        out_path = output_dir / lvl / lang_dir / f"{project_name}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        summary_by_level[lvl] = {
            "count": count,
            "avg_pct": avg_pct,
            "min_pct": min_pct,
            "max_pct": max_pct,
        }

    return {
        "project": project_name,
        "language": language,
        "project_line_coverage_pct": project_pct,
        "summary_by_level": summary_by_level,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    input_dir = args.input_dir or (_REPO / "results" / "coverage")
    artifacts_dir = args.artifacts_dir or (_REPO / "results" / "coverage_artifacts")
    output_dir = args.output_dir or (_REPO / "finalresults" / "coverage_report")
    datasets_dir = _REPO / "datasets"

    if not input_dir.is_dir():
        print(f"Error: input dir not found: {input_dir}", file=sys.stderr)
        return 1

    # Collect project JSONs to process
    project_jsons: list[Path] = []
    if args.project and args.language:
        lang_sub = "javascript" if args.language == "typescript" else args.language
        p = input_dir / lang_sub / f"{args.project}.json"
        if p.is_file():
            project_jsons.append(p)
        else:
            print(f"Error: not found: {p}", file=sys.stderr)
            return 1
    elif args.language:
        lang_sub = "javascript" if args.language == "typescript" else args.language
        lang_dir = input_dir / lang_sub
        if lang_dir.is_dir():
            project_jsons = sorted(lang_dir.glob("*.json"))
    elif args.all_:
        for lang_dir in sorted(input_dir.iterdir()):
            if lang_dir.is_dir():
                project_jsons.extend(sorted(lang_dir.glob("*.json")))
    else:
        print("Error: specify --project (with --language), --language, or --all", file=sys.stderr)
        return 1

    project_jsons = [p for p in project_jsons if p.name != "summary.json"]

    if not project_jsons:
        print("No project files found.")
        return 0

    print(f"Processing {len(project_jsons)} project(s)...")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []
    for pj in project_jsons:
        result = process_project(pj, datasets_dir, artifacts_dir, output_dir)
        if result:
            all_results.append(result)
            lang = result["language"]
            proj = result["project"]
            levels = result.get("summary_by_level", {})
            parts = []
            for lvl, info in sorted(levels.items()):
                parts.append(f"{lvl}={info['avg_pct']:.1f}%({info['count']})")
            print(f"  {lang}/{proj}: {' '.join(parts)}")

    # Write per-level summary.json
    for lvl in ("L0", "L1", "L2", "L3"):
        lvl_dir = output_dir / lvl
        if not lvl_dir.is_dir():
            continue
        lvl_summary: list[dict] = []
        for r in all_results:
            if lvl in r.get("summary_by_level", {}):
                info = r["summary_by_level"][lvl]
                lvl_summary.append({
                    "project": r["project"],
                    "language": r["language"],
                    "project_line_coverage_pct": r["project_line_coverage_pct"],
                    "task_count": info["count"],
                    "avg_coverage_pct": info["avg_pct"],
                    "min_coverage_pct": info["min_pct"],
                    "max_coverage_pct": info["max_pct"],
                })
        if lvl_summary:
            sp = lvl_dir / "summary.json"
            sp.write_text(json.dumps({"level": lvl, "projects": lvl_summary}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Write global summary
    summary = {
        "total_projects": len(all_results),
        "projects": [
            {
                "project": r["project"],
                "language": r["language"],
                "project_line_coverage_pct": r["project_line_coverage_pct"],
                "summary_by_level": r["summary_by_level"],
            }
            for r in all_results
        ],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nSummary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
