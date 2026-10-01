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


def _stats(passed_list: list[bool]) -> dict:
    total = len(passed_list)
    passed = sum(passed_list)
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _score_stats(rows: list[dict]) -> dict:
    scored = [row for row in rows if row.get("overall_score") is not None]
    return {
        "scored_tasks": len(scored),
        "scoring_coverage": round(len(scored) / len(rows), 4) if rows else 0.0,
        "avg_overall_score": _avg([row["overall_score"] for row in scored]),
        "avg_correctness": _avg([row.get("radar_scores", {}).get("Correctness") for row in scored if row.get("radar_scores", {}).get("Correctness") is not None]),
        "avg_faithfulness": _avg([row.get("radar_scores", {}).get("Faithfulness") for row in scored if row.get("radar_scores", {}).get("Faithfulness") is not None]),
        "avg_architecture": _avg([row.get("radar_scores", {}).get("Architecture") for row in scored if row.get("radar_scores", {}).get("Architecture") is not None]),
        "avg_health": _avg([row.get("radar_scores", {}).get("Health") for row in scored if row.get("radar_scores", {}).get("Health") is not None]),
    }


def aggregate(results_dir: Path, *, detail: bool = False) -> dict:
    """Read all per-task result JSONs and produce a summary.

    If detail=True, also prints per-test-case breakdown.
    """
    results = [
        _load_json(p)
        for p in sorted(results_dir.glob("**/*.json"))
        if p.name != "summary.json"
    ]
    if not results:
        print("No results found.")
        return {}

    by_lang: dict[str, list[bool]] = defaultdict(list)
    by_proj: dict[str, list[bool]] = defaultdict(list)
    rows_by_lang: dict[str, list[dict]] = defaultdict(list)
    rows_by_proj: dict[str, list[dict]] = defaultdict(list)
    by_proj_tests: dict[str, dict] = {}

    for r in results:
        parts = r["task"].split("/")
        lang, proj = parts[0], parts[1]
        by_lang[lang].append(r["passed"])
        by_proj[f"{lang}/{proj}"].append(r["passed"])
        rows_by_lang[lang].append(r)
        rows_by_proj[f"{lang}/{proj}"].append(r)
        td = r.get("test_details")
        if td and td.get("total", 0) > 0:
            by_proj_tests[f"{lang}/{proj}"] = td

    all_passed = [r["passed"] for r in results]
    summary = {
        "solver": results[0].get("solver", "unknown"),
        **_stats(all_passed),
        **_score_stats(results),
        "by_language": {
            k: {**_stats(v), **_score_stats(rows_by_lang[k])}
            for k, v in sorted(by_lang.items())
        },
        "by_project": {
            k: {**_stats(v), **_score_stats(rows_by_proj[k])}
            for k, v in sorted(by_proj.items())
        },
    }

    if by_proj_tests:
        summary["test_case_stats"] = {
            k: {"passed": v["passed"], "failed": v["failed"], "total": v["total"]}
            for k, v in sorted(by_proj_tests.items())
        }

    _save_json(results_dir / "summary.json", summary)
    _print_table(summary)

    if detail and by_proj_tests:
        _print_detail(by_proj_tests)

    return summary


def _print_table(summary: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"Solver: {summary['solver']}")
    print(f"Overall: {summary['passed']}/{summary['total']} ({summary['pass_rate']:.1%})")
    print(
        f"Avg Score: {summary.get('avg_overall_score') if summary.get('avg_overall_score') is not None else 'n/a'} "
        f"| C {summary.get('avg_correctness') if summary.get('avg_correctness') is not None else 'n/a'} "
        f"| F {summary.get('avg_faithfulness') if summary.get('avg_faithfulness') is not None else 'n/a'} "
        f"| A {summary.get('avg_architecture') if summary.get('avg_architecture') is not None else 'n/a'} "
        f"| H {summary.get('avg_health') if summary.get('avg_health') is not None else 'n/a'}"
    )
    print(f"{'=' * 60}")

    print(f"\n{'Language':<20} {'Passed':>8} {'Total':>8} {'Rate':>8} {'Score':>8} {'C':>6} {'F':>6} {'A':>6} {'H':>6}")
    print("-" * 86)
    for lang, s in summary["by_language"].items():
        print(
            f"{lang:<20} {s['passed']:>8} {s['total']:>8} {s['pass_rate']:>7.1%} "
            f"{(s['avg_overall_score'] if s['avg_overall_score'] is not None else 'n/a'):>8} "
            f"{(s['avg_correctness'] if s['avg_correctness'] is not None else 'n/a'):>6} "
            f"{(s['avg_faithfulness'] if s['avg_faithfulness'] is not None else 'n/a'):>6} "
            f"{(s['avg_architecture'] if s['avg_architecture'] is not None else 'n/a'):>6} "
            f"{(s['avg_health'] if s['avg_health'] is not None else 'n/a'):>6}"
        )

    tcs = summary.get("test_case_stats")
    if tcs:
        total_passed = sum(v["passed"] for v in tcs.values())
        total_all = sum(v["total"] for v in tcs.values())
        print(f"\n{'Project':<35} {'Passed':>8} {'Total':>8} {'Rate':>8} {'Score':>8}")
        print("-" * 73)
        for proj, s in tcs.items():
            rate = s["passed"] / s["total"] if s["total"] else 0
            agg = summary["by_project"].get(proj, {})
            score = agg.get("avg_overall_score")
            print(f"{proj:<35} {s['passed']:>8} {s['total']:>8} {rate:>7.1%} {(score if score is not None else 'n/a'):>8}")
        print("-" * 73)
        total_rate = total_passed / total_all if total_all else 0
        print(f"{'TOTAL':<35} {total_passed:>8} {total_all:>8} {total_rate:>7.1%} {(summary.get('avg_overall_score') if summary.get('avg_overall_score') is not None else 'n/a'):>8}")
    else:
        print(f"\n{'Project':<35} {'Passed':>8} {'Total':>8} {'Rate':>8} {'Score':>8}")
        print("-" * 73)
        for proj, s in summary["by_project"].items():
            print(
                f"{proj:<35} {s['passed']:>8} {s['total']:>8} {s['pass_rate']:>7.1%} "
                f"{(s['avg_overall_score'] if s['avg_overall_score'] is not None else 'n/a'):>8}"
            )
    print()


def _print_detail(by_proj_tests: dict[str, dict]) -> None:
    """Print per-test-case detail for each project."""
    print(f"\n{'=' * 60}")
    print("TEST CASE DETAIL")
    print(f"{'=' * 60}")
    for proj, td in sorted(by_proj_tests.items()):
        failed_tests = [t for t in td["tests"] if not t["passed"]]
        status = "✓" if not failed_tests else "✗"
        print(f"\n{status} {proj}  ({td['passed']}/{td['total']})")
        if failed_tests:
            for t in failed_tests:
                print(f"    FAIL: {t['name']}")
