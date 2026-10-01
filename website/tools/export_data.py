#!/usr/bin/env python3
"""Generate canonical static JSON snapshots for the PolyCodeEval website."""

from __future__ import annotations

import argparse
from pathlib import Path

from exporters.common import EXPECTED_TASKS, LANGUAGES, OUTPUT, validate_output, write_json
from exporters.community import build_community_snapshots
from exporters.dataset import build_dataset, task_sets_from_dataset
from exporters.leaderboard import build_rankings, build_release_manifest
from exporters.overview import build_manifest
from exporters.prompts import build_prompt_catalog
from exporters.quality import PROMPT_QUALITY, build_coverage, build_prompt_quality
from exporters.results import build_aggregates, build_result_records
from exporters.statistics import build_l2_to_l3, build_significance
from exporters.submission_templates import build_submission_assets
from exporters.tokens import build_tokens


def export_benchmark_data() -> list[Path]:
    dataset = build_dataset()
    records, result_task_sets = build_result_records()
    dataset_task_sets = task_sets_from_dataset()
    for level, expected in EXPECTED_TASKS.items():
        if len(dataset_task_sets[level]) != expected:
            raise ValueError(f"{level}: dataset has {len(dataset_task_sets[level])} tasks, expected {expected}")
        if result_task_sets[level] != dataset_task_sets[level]:
            missing = sorted(dataset_task_sets[level] - result_task_sets[level])[:3]
            extra = sorted(result_task_sets[level] - dataset_task_sets[level])[:3]
            raise ValueError(f"{level}: result task set differs from dataset; missing={missing}, extra={extra}")

    paths = [
        write_json("dataset/projects.json", dataset),
        write_json("results/aggregates.json", build_aggregates(records)),
        write_json("quality/coverage.json", build_coverage()),
        write_json("results/tasks/l0.json", {"level": "L0", "records": records["L0"]}),
        write_json("results/tasks/l1.json", {"level": "L1", "records": records["L1"]}),
        write_json("results/tasks/l2.json", {"level": "L2", "records": records["L2"]}),
    ]
    for language in LANGUAGES:
        selected = [row for row in records["L3"] if row["language"] == language]
        paths.append(write_json(f"results/tasks/l3-{language}.json", {"level": "L3", "language": language, "records": selected}))

    quality_index = []
    for level in PROMPT_QUALITY:
        payload = build_prompt_quality(level)
        filename = f"quality/prompt-quality/{level.lower()}.json"
        paths.append(write_json(filename, payload))
        quality_index.append({"level": level, "taskCount": payload["taskCount"], "path": f"data/{filename}"})
    paths.extend([
        write_json("quality/prompt-quality/index.json", {"levels": quality_index}),
        write_json("statistics/l2-to-l3.json", build_l2_to_l3()),
        write_json("statistics/significance.json", build_significance()),
        write_json("tokens/accounting.json", build_tokens()),
        write_json("prompts/catalog.json", build_prompt_catalog()),
        write_json("overview/summary.json", build_manifest(result_task_sets)),
    ])
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-validation", action="store_true", help="Generate snapshots without the final validation pass.")
    args = parser.parse_args()

    paths = export_benchmark_data()
    data_dir = OUTPUT
    release, release_path = build_release_manifest(data_dir)
    paths.append(release_path)
    paths.append(build_rankings(data_dir, release))
    paths.extend(build_submission_assets(data_dir, release))
    paths.extend(build_community_snapshots())
    if not args.skip_validation:
        errors = validate_output()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
    total_bytes = sum(path.stat().st_size for path in paths)
    print(f"Generated {len(paths)} website artifacts ({total_bytes / 1_000_000:.2f} MB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
