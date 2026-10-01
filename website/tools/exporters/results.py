"""Export canonical task-level results and aggregate metrics."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import EXPECTED_TASKS, LANGUAGES, RUNS, Run, load_json, round_value, source_link


def project_result_paths(run: Run) -> list[Path]:
    return sorted(run.path.glob("*/*/*.json"))


def l0_l1_record(run: Run, path: Path) -> dict[str, Any]:
    row = load_json(path)
    task_id = str(row.get("task") or "/".join((path.parts[-3], path.parts[-2], path.stem)))
    language, project, _ = task_id.split("/", 2)
    radar = row.get("radar_scores") or {}
    detail = (row.get("dimension_details") or {}).get("correctness") or {}
    test_details = row.get("test_details") or {}
    ratio = detail.get("test_pass_ratio")
    if ratio is None and test_details.get("total"):
        ratio = float(test_details.get("passed", 0)) / float(test_details["total"])
    correctness = float(radar.get("Correctness", 0.0))
    return {
        "level": run.level,
        "language": language,
        "project": project,
        "taskId": task_id,
        "configuration": run.id,
        "method": run.method,
        "model": run.model,
        "buildSuccess": row.get("build_status") == "ok",
        "fullPass": bool(row.get("all_tests_passed", row.get("passed", False))),
        "testPassRatio": round_value(ratio if ratio is not None else 0.0),
        "executionScore": round_value(correctness / 5.0),
        "correctness": round_value(correctness),
        "faithfulness": round_value(radar.get("Faithfulness", row.get("faithfulness_score"))),
        "architecture": round_value(radar.get("Architecture", row.get("architecture_score"))),
        "health": round_value(radar.get("Health", row.get("health_score"))),
        "overall": round_value(row.get("overall_score")),
        "testsPassed": test_details.get("passed"),
        "testsTotal": test_details.get("total"),
        "sourceLink": source_link(path),
    }


def execution_record(run: Run, task_id: str, row: dict[str, Any]) -> dict[str, Any]:
    language, project, task = task_id.split("/", 2)
    result_path = run.path.parent / language / project / f"{task}.json"
    if not result_path.is_file():
        raise ValueError(f"{run.id}: missing task result {source_link(result_path)}")
    build_success = float(row.get("compile_score", 0.0) or 0.0) > 0
    test_ratio = float(row.get("test_pass_ratio", 0.0) or 0.0)
    return {
        "level": run.level,
        "language": language,
        "project": project,
        "taskId": task_id,
        "configuration": run.id,
        "method": run.method,
        "model": run.model,
        "buildSuccess": build_success,
        "fullPass": build_success and test_ratio >= 1.0,
        "testPassRatio": round_value(test_ratio),
        "executionScore": round_value(row.get("score", 0.0)),
        "correctness": None,
        "faithfulness": None,
        "architecture": None,
        "health": None,
        "overall": None,
        "sourceLink": source_link(result_path),
    }


def build_result_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, set[str]]]:
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    task_sets: dict[str, list[set[str]]] = defaultdict(list)
    for run in RUNS:
        if run.level in {"L0", "L1"}:
            current = [l0_l1_record(run, path) for path in project_result_paths(run)]
        else:
            summary = load_json(run.path)
            current = [execution_record(run, task_id, row) for task_id, row in sorted(summary["by_task"].items())]
            if len(current) != int(summary["total"]):
                raise ValueError(f"{run.id}: summary total does not match by_task")
            if sum(record["buildSuccess"] for record in current) != int(summary["compile_passed"]):
                raise ValueError(f"{run.id}: derived build count differs from summary")
        current_set = {record["taskId"] for record in current}
        if len(current_set) != len(current):
            raise ValueError(f"{run.id}: duplicate task records")
        task_sets[run.level].append(current_set)
        records[run.level].extend(current)
    canonical_sets: dict[str, set[str]] = {}
    for level, sets in task_sets.items():
        if not sets or any(item != sets[0] for item in sets[1:]):
            raise ValueError(f"{level}: canonical configurations have different task sets")
        canonical_sets[level] = sets[0]
    return dict(records), canonical_sets


def summarize(records: list[dict[str, Any]], scope_type: str, scope: str) -> dict[str, Any]:
    build_rows = [row for row in records if row["buildSuccess"]]
    conditional_test_ratio = statistics.mean(row["testPassRatio"] for row in build_rows) if build_rows else None
    if conditional_test_ratio is not None and records[0]["level"] in {"L2", "L3"}:
        conditional_test_ratio = math.floor(conditional_test_ratio * 1000 + 1e-9) / 1000
    result = {
        "level": records[0]["level"],
        "configuration": records[0]["configuration"],
        "method": records[0]["method"],
        "model": records[0]["model"],
        "scopeType": scope_type,
        "scope": scope,
        "total": len(records),
        "buildSuccessRate": round_value(sum(row["buildSuccess"] for row in records) / len(records)),
        "fullPassRate": round_value(sum(row["fullPass"] for row in records) / len(records)),
        "conditionalTestPassRatio": round_value(conditional_test_ratio),
        "meanExecutionScore": round_value(statistics.mean(row["executionScore"] for row in records)),
    }
    for field in ("correctness", "faithfulness", "architecture", "health", "overall"):
        values = [float(row[field]) for row in records if row.get(field) is not None]
        result[f"mean{field.title()}"] = round_value(statistics.mean(values)) if values else None
    return result


def build_aggregates(all_records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    output: list[dict[str, Any]] = []
    for level in EXPECTED_TASKS:
        for config in sorted({row["configuration"] for row in all_records[level]}):
            rows = [row for row in all_records[level] if row["configuration"] == config]
            output.append(summarize(rows, "all", "All"))
            for language in LANGUAGES:
                selected = [row for row in rows if row["language"] == language]
                if selected:
                    output.append(summarize(selected, "language", language))
            for project in sorted({row["project"] for row in rows}):
                selected = [row for row in rows if row["project"] == project]
                output.append(summarize(selected, "project", f"{selected[0]['language']}/{project}"))
    return {
        "metricScale": "Rates and execution scores are in [0, 1]; L0/L1 quality scores are in [0, 5].",
        "records": output,
    }
