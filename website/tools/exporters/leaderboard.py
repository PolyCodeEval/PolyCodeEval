"""Build the static benchmark release manifest and maintainer leaderboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import EXPECTED_TASKS


LEVEL_COUNTS = EXPECTED_TASKS
RELEASE_VERSION = "pce-1.0"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


def _task_ids(data_dir: Path, level: str) -> list[str]:
    if level != "L3":
        payloads = [_read(data_dir / "results" / "tasks" / f"{level.lower()}.json")]
    else:
        payloads = [_read(path) for path in sorted((data_dir / "results" / "tasks").glob("l3-*.json"))]
    return sorted({row["taskId"] for payload in payloads for row in payload["records"]})


def build_release_manifest(data_dir: Path) -> tuple[dict[str, Any], Path]:
    source = _read(data_dir / "overview" / "summary.json")
    tasks = {level: _task_ids(data_dir, level) for level in LEVEL_COUNTS}
    for level, expected in LEVEL_COUNTS.items():
        if len(tasks[level]) != expected:
            raise ValueError(f"{level}: found {len(tasks[level])} task IDs, expected {expected}")
    payload = {
        "schemaVersion": "1.0.0",
        "benchmarkVersion": RELEASE_VERSION,
        "generatedAt": source.get("generatedAt", ""),
        "repository": source.get("repository", ""),
        "languages": source.get("languages", []),
        "taskCounts": LEVEL_COUNTS,
        "tasks": tasks,
        "submission": {
            "schemaVersion": "2",
            "partialResults": "Accepted; missing tasks receive zero under the fixed level denominator.",
        },
    }
    return payload, _write(data_dir / "common" / "manifest.json", payload)


def build_rankings(data_dir: Path, release: dict[str, Any]) -> Path:
    source = _read(data_dir / "results" / "aggregates.json")
    rows: list[dict[str, Any]] = []
    for item in source["records"]:
        if item.get("scopeType") not in {"all", "language"}:
            continue
        scope_type = str(item["scopeType"])
        scope = str(item.get("scope", ""))
        language = "" if scope_type == "all" else scope
        total = int(item["total"])
        rows.append({
            "id": f'{item["configuration"]}:{scope_type}:{scope.lower()}',
            "configuration": item["configuration"],
            "level": item["level"],
            "scopeType": scope_type,
            "scope": scope,
            "language": language,
            "method": item["method"],
            "model": item["model"],
            "total": total,
            "buildSuccessCount": round(float(item.get("buildSuccessRate") or 0) * total),
            "fullPassCount": round(float(item.get("fullPassRate") or 0) * total),
            "buildSuccessRate": item.get("buildSuccessRate"),
            "fullPassRate": item.get("fullPassRate"),
            "conditionalTestPassRatio": item.get("conditionalTestPassRatio"),
            "executionScore": item.get("meanExecutionScore"),
            "correctness": item.get("meanCorrectness"),
            "faithfulness": item.get("meanFaithfulness"),
            "architecture": item.get("meanArchitecture"),
            "health": item.get("meanHealth"),
            "overall": item.get("meanOverall"),
            "sourceType": "Maintainer Evaluated",
            "submitter": "PolyCodeEval Maintainers",
            "submissionId": "",
            "submittedTasks": total,
            "expectedTasks": total,
            "coverageRate": 1.0,
            "pullRequestUrl": "",
            "mergeCommit": "",
            "scoringMode": "full_quality" if item["level"] in {"L0", "L1"} else "execution",
            "qualityEligible": item["level"] in {"L0", "L1"},
            "benchmarkVersion": RELEASE_VERSION,
            "evaluatedAt": None,
        })

    payload = {
        "benchmarkVersion": RELEASE_VERSION,
        "generatedAt": release.get("generatedAt", ""),
        "rankingOrder": ["fullPassRate", "executionScore", "buildSuccessRate", "configuration"],
        "records": sorted(rows, key=lambda row: (row["level"], row["language"], row["configuration"])),
    }
    return _write(data_dir / "leaderboard" / "rankings.json", payload)
