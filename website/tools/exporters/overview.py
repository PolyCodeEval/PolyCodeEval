"""Export website-level release metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .common import EXPECTED_PAIRED, EXPECTED_TASKS, LANGUAGES, LANGUAGE_LABELS, RUNS


def build_manifest(task_sets: dict[str, set[str]]) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "datasetVersion": "PolyCodeEval website snapshot",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repository": "https://github.com/PolyCodeEval/PolyCodeEval",
        "languages": [{"id": language, "label": LANGUAGE_LABELS[language]} for language in LANGUAGES],
        "taskCounts": {level: len(task_sets[level]) for level in EXPECTED_TASKS},
        "pairedTaskCount": EXPECTED_PAIRED,
        "configurations": [
            {"id": run.id, "level": run.level, "method": run.method, "model": run.model}
            for run in RUNS
        ],
        "fieldDefinitions": {
            "executionScore": "L0/L1 correctness normalized to [0, 1], or the evaluator score for L2/L3.",
            "testPassRatio": "The fraction of tests passed by one task; conditional aggregates include build-successful tasks only.",
            "fullPass": "A successful build with a task-level test-pass ratio of 1.0.",
            "qualityScores": "Correctness, faithfulness, architecture, health, and overall use a 0 to 5 scale.",
            "sourceLink": "A path relative to the GitHub repository root.",
        },
    }
