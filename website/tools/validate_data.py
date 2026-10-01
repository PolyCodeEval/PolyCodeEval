#!/usr/bin/env python3
"""Validate committed PolyCodeEval website data snapshots."""

from __future__ import annotations

import json

from exporters.common import OUTPUT, validate_output
from exporters.leaderboard import LEVEL_COUNTS, RELEASE_VERSION


DATA = OUTPUT


def validate_community_data() -> list[str]:
    errors: list[str] = []
    release_path = DATA / "common" / "manifest.json"
    ranking_path = DATA / "leaderboard" / "rankings.json"
    schema_path = DATA / "submit" / "submission-schema.json"
    template_path = DATA / "submit" / "submission-template.json"
    kit_path = DATA / "submit" / "result-submission-kit.zip"
    community_paths = [
        DATA / "community" / "manifest.json",
        DATA / "community" / "leaderboard.json",
        DATA / "community" / "submissions.json",
        *(DATA / "community" / "tasks" / f"{name}.json" for name in (
            "l0", "l1", "l2", "l3-cpp", "l3-go", "l3-java", "l3-javascript", "l3-python"
        )),
    ]
    for path in (release_path, ranking_path, schema_path, template_path, kit_path, *community_paths):
        if not path.is_file():
            errors.append(f"Missing output: {path.relative_to(DATA)}")
    if errors:
        return errors
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if release.get("benchmarkVersion") != RELEASE_VERSION:
        errors.append("Release manifest benchmark version is invalid")
    if release.get("taskCounts") != LEVEL_COUNTS:
        errors.append("Release manifest task counts are invalid")
    for level, expected in LEVEL_COUNTS.items():
        task_ids = release.get("tasks", {}).get(level, [])
        if len(task_ids) != expected or len(set(task_ids)) != expected:
            errors.append(f"{level} release task IDs are incomplete or duplicated")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("properties", {}).get("schemaVersion", {}).get("const") != "2":
        errors.append("Submission schema version must be 2")
    rankings = json.loads(ranking_path.read_text(encoding="utf-8"))
    ranking_rows = rankings.get("records", [])
    if len(ranking_rows) != 132:
        errors.append(f"Leaderboard has {len(ranking_rows)} rows, expected 132")
    if len({row.get("id") for row in ranking_rows}) != len(ranking_rows):
        errors.append("Leaderboard row identifiers are not unique")
    if any("rank" in row for row in ranking_rows):
        errors.append("Leaderboard snapshot must not persist presentation ranks")
    overall = [row for row in ranking_rows if not row.get("language")]
    expected_configs = {"L0": 4, "L1": 2, "L2": 4, "L3": 12}
    for level, expected in expected_configs.items():
        count = sum(row.get("level") == level for row in overall)
        if count != expected:
            errors.append(f"{level} leaderboard has {count} overall rows, expected {expected}")
    community = json.loads((DATA / "community" / "leaderboard.json").read_text(encoding="utf-8"))
    community_ids = [row.get("id") for row in community.get("records", [])]
    if len(community_ids) != len(set(community_ids)):
        errors.append("Community leaderboard row identifiers are not unique")
    return errors


def main() -> int:
    errors = [*validate_output(), *validate_community_data()]
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Website data validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
