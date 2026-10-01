"""Scorer — aggregates per-task results into a summary report."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _task_test_pass_ratio(row: dict) -> float:
    if "test_pass_ratio" in row and row["test_pass_ratio"] is not None:
        return float(row["test_pass_ratio"])
    td = row.get("test_details") or {}
    total = td.get("total", 0) or 0
    passed = td.get("passed", 0) or 0
    return (passed / total) if total else 0.0


def _task_compile_score(row: dict) -> float:
    if "compile_score" in row and row["compile_score"] is not None:
        return float(row["compile_score"])
    return 0.5 if row.get("compile_passed") else 0.0


def _task_test_score(row: dict) -> float:
    if "test_score" in row and row["test_score"] is not None:
        return float(row["test_score"])
    score = float(row.get("score", 0.0))
    return max(0.0, score - _task_compile_score(row))


def _stats(rows: list[dict]) -> dict:
    total = len(rows)
    full_passed = sum(1 for r in rows if r["passed"])
    compile_passed = sum(1 for r in rows if r.get("compile_passed"))
    total_score = sum(float(r.get("score", 0.0)) for r in rows)
    compile_score = sum(float(r.get("compile_score", 0.0)) for r in rows)
    test_score = sum(float(r.get("test_score", 0.0)) for r in rows)
    avg_score = total_score / total if total else 0.0
    return {
        "total": total,
        "full_passed": full_passed,
        "compile_passed": compile_passed,
        "full_pass_rate": round(full_passed / total, 4) if total else 0.0,
        "compile_pass_rate": round(compile_passed / total, 4) if total else 0.0,
        "compile_score": round(compile_score, 4),
        "test_score": round(test_score, 4),
        "avg_score": round(avg_score, 4),
        "total_score": round(total_score, 4),
    }


def aggregate(results_dir: Path) -> dict:
    """Read all per-task result JSONs and produce a summary."""
    results: list[dict] = []
    for p in sorted(results_dir.glob("**/*.json")):
        if p.name == "summary.json":
            continue
        row = _load_json(p)
        task_id = row.get("task", "")
        if "/L3_" not in task_id:
            continue
        results.append(row)
    if not results:
        print("No results found.")
        return {}

    by_lang: dict[str, list[dict]] = defaultdict(list)
    by_proj: dict[str, list[dict]] = defaultdict(list)
    by_task: dict[str, dict] = {}
    for r in results:
        parts = r["task"].split("/")
        lang, proj = parts[0], parts[1]
        by_lang[lang].append(r)
        by_proj[f"{lang}/{proj}"].append(r)
        by_task[r["task"]] = {
            "score": round(float(r.get("score", 0.0)), 4),
            "compile_score": round(_task_compile_score(r), 4),
            "test_score": round(_task_test_score(r), 4),
            "test_pass_ratio": round(_task_test_pass_ratio(r), 4),
        }

    summary = {
        "solver": results[0].get("solver", "unknown"),
        **_stats(results),
        "by_language": {k: _stats(v) for k, v in sorted(by_lang.items())},
        "by_project": {k: _stats(v) for k, v in sorted(by_proj.items())},
        "by_task": dict(sorted(by_task.items())),
    }

    _save_json(results_dir / "summary.json", summary)
    _print_table(summary)
    return summary


def _print_table(summary: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"Solver: {summary['solver']}")
    print(f"Avg score:   {summary['avg_score']:.3f}")
    print(f"Compile-pass: {summary['compile_passed']}/{summary['total']} ({summary['compile_pass_rate']:.1%})")
    print(f"Full-pass:    {summary['full_passed']}/{summary['total']} ({summary['full_pass_rate']:.1%})")
    print(f"{'=' * 60}")

    print(f"\n{'Language':<20} {'Avg':>8} {'Compile':>8} {'Full':>8} {'Total':>8}")
    print("-" * 60)
    for lang, s in summary["by_language"].items():
        print(
            f"{lang:<20} {s['avg_score']:>8.3f} "
            f"{s['compile_passed']:>8} {s['full_passed']:>8} {s['total']:>8}"
        )

    print(f"\n{'Project':<35} {'Avg':>8} {'Compile':>8} {'Full':>8} {'Total':>8}")
    print("-" * 75)
    for proj, s in summary["by_project"].items():
        print(
            f"{proj:<35} {s['avg_score']:>8.3f} "
            f"{s['compile_passed']:>8} {s['full_passed']:>8} {s['total']:>8}"
        )

    print(f"\n{'Task':<55} {'Score':>8} {'Compiles':>8} {'TestRate':>10} {'TestScore':>10}")
    print("-" * 100)
    for task, s in summary["by_task"].items():
        print(
            f"{task:<55} {s['score']:>8.3f} "
            f"{s['compile_score']:>8.3f} {s['test_pass_ratio']:>8.3f} {s['test_score']:>8.3f}"
        )
    print()
