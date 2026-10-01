"""Export paired experiments and statistical evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import EXPECTED_PAIRED, FINAL, REPORTS, load_json, round_value, source_link


def status_payload(row: dict[str, Any]) -> dict[str, Any]:
    build_success = bool(row.get("compile_passed"))
    test_pass_ratio = float(row.get("test_pass_ratio", 0.0) or 0.0)
    return {
        "buildSuccess": build_success,
        "fullPass": build_success and test_pass_ratio >= 1.0,
        "testPassRatio": round_value(test_pass_ratio),
        "executionScore": round_value(row.get("score", 0.0)),
    }


def load_task_details(summary_path: Path) -> dict[str, dict[str, Any]]:
    details = {}
    for path in sorted(summary_path.parent.glob("*/*/*.json")):
        row = load_json(path)
        if row.get("task"):
            details[row["task"]] = row
    return details


def build_l2_to_l3() -> dict[str, Any]:
    report = load_json(REPORTS / "l2tol3_vs_l3_direct.json")
    specs = {
        "GPT-5.4": (
            FINAL / "L2toL3/l2toL3_eval_gpt54/summary.json",
            FINAL / "L3/direct/direct_eval_gpt54/summary.json",
            "gpt54",
        ),
        "Claude Sonnet 4.6": (
            FINAL / "L2toL3/l2toL3_eval_sonnet/summary.json",
            FINAL / "L3/direct/direct_eval_sonnet/summary.json",
            "sonnet",
        ),
    }
    records = []
    for model, (context_path, direct_path, report_key) in specs.items():
        context_summary = load_json(context_path)
        direct_summary = load_json(direct_path)
        context_details = load_task_details(context_path)
        direct_details = load_task_details(direct_path)
        paired = sorted(set(context_summary["by_task"]) & set(direct_summary["by_task"]))
        if len(paired) != EXPECTED_PAIRED:
            raise ValueError(f"{model}: expected {EXPECTED_PAIRED} paired tasks, found {len(paired)}")
        for task_id in paired:
            language, project, task = task_id.split("/", 2)
            records.append({
                "model": model,
                "language": language,
                "project": project,
                "taskId": task_id,
                "withRelatedImplementations": status_payload(context_details[task_id]),
                "signatureContextOnly": status_payload(direct_details[task_id]),
                "sourceLinks": {
                    "withRelatedImplementations": source_link(context_path.parent / language / project / f"{task}.json"),
                    "signatureContextOnly": source_link(direct_path.parent / language / project / f"{task}.json"),
                },
            })
        if report[report_key]["counts"]["intersection_tasks"] != len(paired):
            raise ValueError(f"{model}: report pairing count is inconsistent")
    return {
        "pairedTaskCount": EXPECTED_PAIRED,
        "definition": "The paired experiment compares L3 generation with related function implementations against L3 Direct generation with semantic descriptions and interface signatures.",
        "summary": report,
        "records": records,
    }


def build_significance() -> dict[str, Any]:
    selected = load_json(REPORTS / "significance_tests_selected.json")
    paired = load_json(REPORTS / "l2tol3_vs_l3_direct_significance.json")
    keep = (
        "name", "level", "hypothesis", "model", "scope", "n_pairs", "n_nonzero",
        "median_a", "median_b", "median_direct", "median_l2tol3", "median_delta",
        "mean_a", "mean_b", "mean_direct", "mean_l2tol3", "mean_delta",
        "positive_deltas", "negative_deltas", "wilcoxon_statistic", "p_value",
        "p_value_holm", "significant_0_05", "both_yes", "l2tol3_only", "direct_only", "both_no",
    )

    def compact(row: dict[str, Any]) -> dict[str, Any]:
        return {key: row[key] for key in keep if key in row}

    selected_comparisons = []
    for row in selected:
        payload = compact(row)
        payload["raw_p_value"] = row["p_value"]
        payload["p_value"] = row["p_value_holm"]
        payload["adjustment"] = "Holm (9 selected tests)"
        selected_comparisons.append(payload)

    def unadjusted(row: dict[str, Any]) -> dict[str, Any]:
        payload = compact(row)
        payload["adjustment"] = "None"
        return payload

    return {
        "alpha": 0.05,
        "test": "Wilcoxon signed-rank test for paired scores; exact paired test for binary full-pass outcomes.",
        "selectedComparisons": selected_comparisons,
        "l2ToL3ScoreTests": [unadjusted(row) for row in paired["score_wilcoxon"]],
        "l2ToL3FullPassTests": [unadjusted(row) for row in paired["full_pass_exact"]],
        "sourceLinks": [
            source_link(REPORTS / "significance_tests_selected.json"),
            source_link(REPORTS / "l2tol3_vs_l3_direct_significance.json"),
        ],
    }
