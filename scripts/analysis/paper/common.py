from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS_ROOT = REPO_ROOT / "datasets"
FINALRESULTS_ROOT = REPO_ROOT / "finalresults"
ALL_ANSWERS_ROOT = REPO_ROOT / "All_answers"
RESULTS_ROOT = REPO_ROOT / "results"
PAPER_ROOT = REPO_ROOT / "docs" / "paper" / "IEEE_Conference_Template" / "polycodeeval_ieee_en"

LANG_ORDER = ["cpp", "go", "java", "javascript", "python"]
LANG_LABEL = {
    "cpp": "Cpp",
    "go": "Go",
    "java": "Java",
    "javascript": "JS",
    "python": "Py",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def round4(value: float) -> float:
    return round(float(value), 4)


def round1(value: float) -> float:
    return round(float(value), 1)


def floor1(value: float) -> float:
    value = float(value)
    return math.floor(value * 10.0 + 1e-9) / 10.0


def pct(value: float) -> float:
    return round1(100.0 * float(value))


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def iter_result_jsons(results_dir: Path) -> list[Path]:
    return sorted(p for p in results_dir.glob("**/*.json") if p.name != "summary.json")


def build_ok(row: dict[str, Any]) -> bool:
    if "build_status" in row:
        return row.get("build_status") == "ok"
    if "compile_passed" in row:
        return bool(row.get("compile_passed"))
    return bool(row.get("passed"))


def full_ok(row: dict[str, Any]) -> bool:
    if "all_tests_passed" in row:
        return bool(row.get("all_tests_passed"))
    return bool(row.get("passed"))


def aggregate_project_level_dir(results_dir: Path) -> dict[str, Any]:
    rows = [load_json(path) for path in iter_result_jsons(results_dir)]
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        task = row.get("task", "")
        parts = task.split("/") if task else []
        if "language" not in row and parts:
            row["language"] = parts[0]
        if "project_name" not in row and len(parts) >= 2:
            row["project_name"] = parts[1]
        by_lang[row["language"]].append(row)

    def _stats(lang_rows: list[dict[str, Any]]) -> dict[str, float]:
        def _corr(row: dict[str, Any]) -> float:
            if "correctness" in row:
                return float(row["correctness"])
            detail = ((row.get("dimension_details") or {}).get("correctness") or {})
            if "test_pass_ratio" in detail:
                return 100.0 * float(detail["test_pass_ratio"])
            radar = row.get("radar_scores") or {}
            return 20.0 * float(radar.get("Correctness", 0.0))

        def _faith(row: dict[str, Any]) -> float:
            if "faithfulness_score" in row:
                return float(row["faithfulness_score"])
            return float((row.get("radar_scores") or {}).get("Faithfulness", 0.0))

        def _arch(row: dict[str, Any]) -> float:
            if "architecture_score" in row:
                return float(row["architecture_score"])
            return float((row.get("radar_scores") or {}).get("Architecture", 0.0))

        def _health(row: dict[str, Any]) -> float:
            if "health_score" in row:
                return float(row["health_score"])
            return float((row.get("radar_scores") or {}).get("Health", 0.0))

        correctness = average([_corr(r) for r in lang_rows]) or 0.0
        faithfulness = average([_faith(r) for r in lang_rows]) or 0.0
        architecture = average([_arch(r) for r in lang_rows]) or 0.0
        health = average([_health(r) for r in lang_rows]) or 0.0
        build_rate = 100.0 * sum(1 for r in lang_rows if build_ok(r)) / len(lang_rows)
        full_rate = 100.0 * sum(1 for r in lang_rows if full_ok(r)) / len(lang_rows)
        return {
            "C": round1(correctness),
            "F": round(float(faithfulness), 2),
            "A": round(float(architecture), 2),
            "H": round(float(health), 2),
            "Build": round1(build_rate),
            "Full": round1(full_rate),
            "N": len(lang_rows),
        }

    overall = _stats(rows)
    per_language = {lang: _stats(by_lang[lang]) for lang in LANG_ORDER if lang in by_lang}
    return {
        "rows": rows,
        "by_language": per_language,
        "overall": overall,
    }


def conditional_test_pass_pct(summary: dict[str, Any], *, by_language: str | None = None) -> float:
    by_task = summary.get("by_task") or {}
    ratios: list[float] = []
    for task_id, task_row in by_task.items():
        if by_language and not str(task_id).startswith(f"{by_language}/"):
            continue
        if float(task_row.get("compile_score", 0.0) or 0.0) <= 0:
            continue
        ratios.append(float(task_row.get("test_pass_ratio", 0.0) or 0.0))

    if not ratios:
        bucket = summary["by_language"][by_language] if by_language else summary
        compile_score = float(bucket.get("compile_score", 0.0))
        test_score = float(bucket.get("test_score", 0.0))
        if compile_score <= 0:
            return 0.0
        return floor1(100.0 * test_score / compile_score)

    return floor1(100.0 * sum(ratios) / len(ratios))


def combine_js_ts_language_means(items: list[dict[str, Any]], value_key: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        lang = item["language"]
        if lang in {"javascript", "typescript"}:
            lang = "javascript"
        value = item.get(value_key)
        if value is None:
            continue
        grouped[lang].append(float(value))
        counts[lang] += 1
    return {lang: round1(sum(vals) / len(vals)) for lang, vals in grouped.items() if vals}


def parse_readme_loc_tables() -> list[dict[str, Any]]:
    readmes = [
        DATASETS_ROOT / "python" / "README.md",
        DATASETS_ROOT / "java" / "README.md",
        DATASETS_ROOT / "go" / "README.md",
        DATASETS_ROOT / "cpp" / "README.md",
        DATASETS_ROOT / "javascript" / "README.md",
    ]
    rows: list[dict[str, Any]] = []
    for readme in readmes:
        language = readme.parent.name
        text = readme.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.startswith("| **"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            name = re.sub(r"^\*\*|\*\*$", "", cells[0])
            name = re.sub(r"^\[(.*?)\]\(.*\)$", r"\1", name)
            loc_raw = cells[1]
            number = float(re.sub(r"[^0-9.]", "", loc_raw).replace(",", ""))
            rows.append({"language": language, "project": name, "loc": number})
    return rows


def parse_repocoder_consumption_markdown(path: Path) -> dict[str, dict[str, float]]:
    text = path.read_text(encoding="utf-8")
    rows: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            continue
        model = cells[0]
        if model in {"模型", "合计"}:
            continue
        rows[model] = {
            "records": float(cells[1].replace(",", "")),
            "input_tokens": float(cells[2].replace(",", "")),
            "output_tokens": float(cells[3].replace(",", "")),
            "total_tokens": float(cells[4].replace(",", "")),
            "cost_usd": float(cells[5].replace(",", "")),
        }
    return rows
