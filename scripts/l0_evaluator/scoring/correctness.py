"""Correctness scoring for L0 tasks."""

from __future__ import annotations


def score_correctness(result: dict) -> tuple[float, dict]:
    """Score correctness using parsed test results."""
    td = result.get("test_details") or {}
    passed = int(td.get("passed", 0))
    failed = int(td.get("failed", 0))
    total = int(td.get("total", 0))

    if total > 0:
        ratio = passed / total
        score = round(5 * ratio, 2)
    else:
        ratio = 1.0 if result.get("passed") else 0.0
        score = 5.0 if result.get("passed") else 0.0

    detail = {
        "status": "ok",
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_total": total,
        "test_pass_ratio": round(ratio, 4),
        "derived_from": "test_details",
    }
    return score, detail
