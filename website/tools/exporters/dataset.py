"""Export the repository registry and benchmark task inventory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import (
    CJK_RE,
    DATASETS,
    EXPECTED_TASKS,
    FINAL,
    LANGUAGES,
    LANGUAGE_LABELS,
    load_json,
    round_value,
)


def clean_markdown(value: str) -> str:
    value = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", value)
    return re.sub(r"[*`]", "", value).strip()


def difficulty(raw: str, loc: float | None) -> str:
    value = clean_markdown(raw)
    if value in {"Small", "Medium", "Large", "Very Large"}:
        return value
    stars = value.count("⭐")
    if stars:
        return {1: "Small", 2: "Medium", 3: "Large"}.get(stars, "Very Large")
    if loc is None:
        return "Unknown"
    if loc < 500:
        return "Small"
    if loc < 2000:
        return "Medium"
    if loc < 6000:
        return "Large"
    return "Very Large"


def infer_framework(language: str, project: str) -> str:
    config = DATASETS / language / project / "config.json"
    text = config.read_text(encoding="utf-8").lower() if config.exists() else ""
    if language == "python":
        return "pytest" if "pytest" in text else "unittest"
    return {
        "cpp": "Project-specific",
        "go": "Go testing",
        "java": "JUnit",
        "javascript": "Jest/Mocha",
    }[language]


def normalize_source(value: str) -> str:
    value = clean_markdown(value)
    if not value or value in {"—", "-"}:
        return "Unknown"
    return "Custom" if CJK_RE.search(value) else value


def parse_registry_readme(language: str) -> list[dict[str, Any]]:
    path = DATASETS / language / "README.md"
    header: list[str] | None = None
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if any("\u9879\u76ee\u540d\u79f0" in cell for cell in cells):
            header = cells
            continue
        if header is None or len(cells) != len(header) or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if "**" not in cells[0] and "[" not in cells[0]:
            continue
        record = dict(zip(header, cells))
        project = re.sub(r"\*", "", cells[0])
        project = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", project).strip()
        loc_text = next((value for key, value in record.items() if "LOC" in key), "")
        match = re.search(r"[\d,]+(?:\.\d+)?", loc_text)
        loc = float(match.group(0).replace(",", "")) if match else None
        diff = next((value for key, value in record.items() if "\u96be\u5ea6" in key or "\u6863\u4f4d" in key), "")
        framework = next((value for key, value in record.items() if "\u6d4b\u8bd5\u6846\u67b6" in key), "")
        origin = next((value for key, value in record.items() if "\u6570\u636e\u6765\u6e90" in key), "")
        rows.append({
            "language": language,
            "languageLabel": LANGUAGE_LABELS[language],
            "project": project,
            "loc": round_value(loc, 2),
            "difficulty": difficulty(diff, loc),
            "testFramework": clean_markdown(framework) or infer_framework(language, project),
            "source": normalize_source(origin),
        })
    return rows


def task_paths(language: str, project: str, level: str) -> list[Path]:
    return sorted((DATASETS / language / project / "tasks").glob(f"{level}_*/task.json"))


def task_sets_from_dataset() -> dict[str, set[str]]:
    return {
        level: {
            "/".join((path.parts[-5], path.parts[-4], path.parent.name))
            for path in DATASETS.glob(f"*/*/tasks/{level}_*/task.json")
        }
        for level in EXPECTED_TASKS
    }


def build_dataset() -> dict[str, Any]:
    projects = [item for language in LANGUAGES for item in parse_registry_readme(language)]
    for item in projects:
        item["taskCounts"] = {
            level: len(task_paths(item["language"], item["project"], level))
            for level in EXPECTED_TASKS
        }
        item["oracleValidated"] = (FINAL / "oracle_l0_eval_final" / item["language"] / item["project"]).exists()
        coverage_path = FINAL / "coverage_report/L0" / item["language"] / f"{item['project']}.json"
        item["coverageAvailable"] = coverage_path.exists()
        item["coverage"] = round_value(float(load_json(coverage_path)["project_line_coverage_pct"]) / 100.0) if coverage_path.exists() else None
    counts_by_language = {
        language: {
            level: sum(item["taskCounts"][level] for item in projects if item["language"] == language)
            for level in EXPECTED_TASKS
        }
        for language in LANGUAGES
    }
    return {
        "projectCount": len(projects),
        "taskCounts": {level: sum(item["taskCounts"][level] for item in projects) for level in EXPECTED_TASKS},
        "countsByLanguage": counts_by_language,
        "difficultyBands": [
            {"id": "Small", "targetLoc": "Below 500"},
            {"id": "Medium", "targetLoc": "500 to below 2,000"},
            {"id": "Large", "targetLoc": "2,000 to below 6,000"},
            {"id": "Very Large", "targetLoc": "6,000 or more"},
        ],
        "projects": projects,
    }
