"""Export coverage and prompt-quality records."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

from .common import EXPECTED_TASKS, FINAL, load_json, round_value, source_link


PROMPT_QUALITY = {
    "L0": ("l0_prompt_score", ("sonnet4.6_judge", "dpskv4pro_judge", "gpt5.4_judge")),
    "L2": ("l2_prompt_score", ("sonnet4.6_judge", "dpskv4_judge", "gpt5.4_judge")),
    "L3": ("l3_prompt_score", ("sonnet4.6_judge", "dpskv4pro_judge", "gpt5.4_judge")),
}
JUDGE_LABELS = {
    "sonnet4.6_judge": "Claude Sonnet 4.6",
    "dpskv4_judge": "DeepSeek-V4-Pro",
    "dpskv4pro_judge": "DeepSeek-V4-Pro",
    "gpt5.4_judge": "GPT-5.4",
}


def build_coverage() -> dict[str, Any]:
    summary = load_json(FINAL / "coverage_report/summary.json")
    projects = [{
        "language": item["language"],
        "project": item["project"],
        "projectLineCoverage": round_value(float(item["project_line_coverage_pct"]) / 100.0),
        "levels": {
            level: {
                "taskCount": value["count"],
                "mean": round_value(float(value["avg_pct"]) / 100.0),
                "minimum": round_value(float(value["min_pct"]) / 100.0),
                "maximum": round_value(float(value["max_pct"]) / 100.0),
            }
            for level, value in item.get("summary_by_level", {}).items()
        },
    } for item in summary["projects"]]
    tasks = []
    for level in EXPECTED_TASKS:
        for path in sorted((FINAL / "coverage_report" / level).glob("*/*.json")):
            row = load_json(path)
            for task, detail in sorted((row.get("tasks") or {}).items()):
                tasks.append({
                    "level": level,
                    "language": row["language"],
                    "project": row["project"],
                    "taskId": f"{row['language']}/{row['project']}/{task}",
                    "coverage": round_value(float(detail["coverage_pct"]) / 100.0),
                    "linesCovered": detail.get("lines_covered"),
                    "linesTotal": detail.get("lines_total"),
                    "sourceLink": source_link(path),
                })
    available = {level: sum(row["level"] == level for row in tasks) for level in EXPECTED_TASKS}
    return {
        "projectCount": len(projects),
        "expectedTaskCounts": EXPECTED_TASKS,
        "availableTaskCounts": available,
        "coverageDefinition": "L0/L1 use project-level line coverage. L2/L3 use target-level coverage recorded by the language-specific coverage pipeline.",
        "projects": projects,
        "tasks": tasks,
    }


def prompt_quality_score(row: dict[str, Any]) -> float | None:
    if isinstance(row.get("scores"), dict):
        values = [float(value["score"]) for value in row["scores"].values() if isinstance(value, dict) and "score" in value]
        return statistics.mean(values) if values else None
    return float(row["score"]) if row.get("score") is not None else None


def parse_embedded_json(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def build_prompt_quality(level: str) -> dict[str, Any]:
    dirname, judges = PROMPT_QUALITY[level]
    by_task: dict[str, dict[str, Any]] = {}
    for judge in judges:
        base = FINAL / dirname / judge
        judge_rows: dict[str, tuple[dict[str, Any], Path]] = {}
        for path in sorted(base.glob("*/*/*.raw.md")):
            row = parse_embedded_json(path)
            if row:
                task_id = f"{path.parts[-3]}/{path.parts[-2]}/{path.name.removesuffix('.raw.md')}"
                judge_rows[task_id] = (row, path)
        for path in sorted(base.glob("*/*/*.json")):
            row = load_json(path)
            task_id = row.get("task")
            if task_id:
                judge_rows.setdefault(task_id, (row, path))
        for task_id, (row, path) in sorted(judge_rows.items()):
            language, project, _ = task_id.split("/", 2)
            record = by_task.setdefault(task_id, {
                "level": level,
                "language": language,
                "project": project,
                "taskId": task_id,
                "judges": {},
            })
            record["judges"][JUDGE_LABELS[judge]] = {
                "score": round_value(prompt_quality_score(row)),
                "completeEnough": row.get("complete_enough"),
                "descriptionPresent": row.get("description_present", row.get("descriptions_present")),
                "sourceLink": source_link(path),
            }
    records = [by_task[key] for key in sorted(by_task)]
    return {
        "level": level,
        "taskCount": len(records),
        "judges": [JUDGE_LABELS[judge] for judge in judges],
        "records": records,
    }
