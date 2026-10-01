"""Validate community submissions and export public website snapshots."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import LANGUAGES, OUTPUT, ROOT, round_value, write_json

sys.path.insert(0, str(ROOT))
from scripts.submission.core import CanonicalRegistry, validate_package  # noqa: E402


COMMUNITY_ROOT = ROOT / "community-results" / "pce-1.0"
REPOSITORY_URL = "https://github.com/PolyCodeEval/PolyCodeEval"


def _git_provenance(path: Path) -> dict[str, str]:
    try:
        relative = path.relative_to(ROOT).as_posix()
        output = subprocess.check_output(
            ["git", "log", "-1", "--format=%H%x00%cI%x00%s", "--", relative],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        commit, reviewed_at, subject = (output.split("\x00", 2) + ["", "", ""])[:3]
    except (OSError, subprocess.CalledProcessError, ValueError):
        return {"mergeCommit": "", "reviewedAt": "", "pullRequestUrl": ""}
    match = re.search(r"\(#(\d+)\)|\bPR\s*#?(\d+)\b", subject, re.IGNORECASE)
    number = next((group for group in match.groups() if group), "") if match else ""
    return {
        "mergeCommit": commit,
        "reviewedAt": reviewed_at,
        "pullRequestUrl": f"{REPOSITORY_URL}/pull/{number}" if number else "",
    }


def _submission_directories() -> list[Path]:
    if not COMMUNITY_ROOT.is_dir():
        return []
    return sorted(
        path
        for path in COMMUNITY_ROOT.glob("L*/*/*")
        if path.is_dir() and (path / "submission.json").is_file()
    )


def _leaderboard_row(
    *,
    metadata: dict[str, Any],
    stats: dict[str, Any],
    submission_id: str,
    language: str,
    provenance: dict[str, str],
) -> dict[str, Any]:
    expected = int(stats["expected_tasks"])
    submitted = int(stats["submitted_tasks"])
    scope = language or "all"
    return {
        "id": f"community:{submission_id}:{scope}",
        "configuration": submission_id,
        "submissionId": submission_id,
        "level": metadata["level"],
        "language": language,
        "method": metadata["method"]["name"],
        "model": metadata["model"]["name"],
        "total": expected,
        "submittedTasks": submitted,
        "expectedTasks": expected,
        "coverageRate": stats["coverage_rate"],
        "buildSuccessRate": stats["build_pass_rate"],
        "fullPassRate": stats["full_pass_rate"],
        "conditionalTestPassRatio": stats["conditional_test_pass_ratio"],
        "executionScore": stats["avg_execution_score"],
        "correctness": stats["avg_correctness"],
        "faithfulness": stats["avg_faithfulness"],
        "architecture": stats["avg_architecture"],
        "health": stats["avg_health"],
        "overall": stats["avg_overall"],
        "sourceType": "Community Self-Evaluated",
        "submitter": metadata["submitter"]["github"],
        "scoringMode": metadata["evaluation"]["scoringMode"],
        "qualityEligible": stats["quality_eligible"],
        "benchmarkVersion": metadata["benchmarkVersion"],
        "evaluatedAt": metadata["evaluation"].get("finishedAt") or None,
        **provenance,
    }


def _task_rows(
    package: Path,
    metadata: dict[str, Any],
    aggregate: dict[str, Any],
    submission_id: str,
    provenance: dict[str, str],
) -> list[dict[str, Any]]:
    registry = CanonicalRegistry.discover(ROOT, metadata["level"])
    submitted = aggregate["by_task"]
    expected = aggregate["expected_tasks"]
    submitted_count = aggregate["submitted_tasks"]
    coverage = aggregate["coverage_rate"]
    rows: list[dict[str, Any]] = []
    for task_id in sorted(registry.task_ids):
        language, project, task = task_id.split("/", 2)
        result = submitted.get(task_id)
        missing = result is None
        result = result or {
            "buildSuccess": False,
            "fullPass": False,
            "testPassRatio": 0.0,
            "executionScore": 0.0,
            "correctness": 0.0 if metadata["level"] in {"L0", "L1"} else None,
            "faithfulness": 0.0 if metadata["evaluation"]["scoringMode"] == "full_quality" else None,
            "architecture": 0.0 if metadata["evaluation"]["scoringMode"] == "full_quality" else None,
            "health": 0.0 if metadata["evaluation"]["scoringMode"] == "full_quality" else None,
            "overall": 0.0 if metadata["evaluation"]["scoringMode"] == "full_quality" else None,
        }
        source = package / "evaluation" / language / project / f"{task}.json"
        rows.append(
            {
                "level": metadata["level"],
                "language": language,
                "project": project,
                "taskId": task_id,
                "configuration": submission_id,
                "submissionId": submission_id,
                "method": metadata["method"]["name"],
                "model": metadata["model"]["name"],
                "buildSuccess": bool(result["buildSuccess"]),
                "fullPass": bool(result["fullPass"]),
                "testPassRatio": round_value(result["testPassRatio"]),
                "executionScore": round_value(result["executionScore"]),
                "correctness": round_value(result.get("correctness")),
                "faithfulness": round_value(result.get("faithfulness")),
                "architecture": round_value(result.get("architecture")),
                "health": round_value(result.get("health")),
                "overall": round_value(result.get("overall")),
                "sourceType": "Community Self-Evaluated",
                "submitter": metadata["submitter"]["github"],
                "submittedTasks": submitted_count,
                "expectedTasks": expected,
                "coverageRate": coverage,
                "scoringMode": metadata["evaluation"]["scoringMode"],
                "qualityEligible": aggregate["quality_eligible"],
                "missing": missing,
                "sourceLink": (
                    source.relative_to(ROOT).as_posix()
                    if not missing
                    else (package / "submission.json").relative_to(ROOT).as_posix()
                ),
                **provenance,
            }
        )
    return rows


def build_community_snapshots() -> list[Path]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    leaderboard: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    task_rows: dict[str, list[dict[str, Any]]] = {level: [] for level in ("L0", "L1", "L2", "L3")}

    for package in _submission_directories():
        report = validate_package(package, ROOT)
        if not report.valid:
            details = "; ".join(issue.message for issue in report.errors[:5])
            raise ValueError(f"Invalid community submission {package.relative_to(ROOT)}: {details}")
        metadata = report.metadata
        aggregate = report.aggregate
        submission_id = package.name
        provenance = _git_provenance(package)
        overall = _leaderboard_row(
            metadata=metadata,
            stats=aggregate,
            submission_id=submission_id,
            language="",
            provenance=provenance,
        )
        leaderboard.append(overall)
        for language in LANGUAGES:
            leaderboard.append(
                _leaderboard_row(
                    metadata=metadata,
                    stats=aggregate["by_language"][language],
                    submission_id=submission_id,
                    language=language,
                    provenance=provenance,
                )
            )
        submissions.append(
            {
                **overall,
                "submissionName": metadata["submissionName"],
                "methodVersion": metadata["method"]["version"],
                "modelVersion": metadata["model"]["version"],
                "notes": metadata.get("notes", ""),
            }
        )
        task_rows[metadata["level"]].extend(
            _task_rows(package, metadata, aggregate, submission_id, provenance)
        )

    paths = [
        write_json(
            "community/manifest.json",
            {
                "benchmarkVersion": "pce-1.0",
                "generatedAt": generated_at,
                "submissionCount": len(submissions),
                "levels": {
                    level: sum(row["level"] == level for row in submissions)
                    for level in task_rows
                },
            },
        ),
        write_json(
            "community/leaderboard.json",
            {"benchmarkVersion": "pce-1.0", "generatedAt": generated_at, "records": leaderboard},
        ),
        write_json(
            "community/submissions.json",
            {"benchmarkVersion": "pce-1.0", "generatedAt": generated_at, "records": submissions},
        ),
        write_json("community/tasks/l0.json", {"level": "L0", "records": task_rows["L0"]}),
        write_json("community/tasks/l1.json", {"level": "L1", "records": task_rows["L1"]}),
        write_json("community/tasks/l2.json", {"level": "L2", "records": task_rows["L2"]}),
    ]
    for language in LANGUAGES:
        paths.append(
            write_json(
                f"community/tasks/l3-{language}.json",
                {
                    "level": "L3",
                    "language": language,
                    "records": [row for row in task_rows["L3"] if row["language"] == language],
                },
            )
        )
    return paths
