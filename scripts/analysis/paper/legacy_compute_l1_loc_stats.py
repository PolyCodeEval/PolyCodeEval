#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"


def count_lines(path: Path) -> int:
    data = path.read_bytes()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def main() -> None:
    rows: list[dict] = []
    per_lang = defaultdict(list)

    for task_json in sorted(DATASETS_ROOT.glob("*/*/tasks/L1_*/task.json")):
        task_dir = task_json.parent
        payload = json.loads(task_json.read_text(encoding="utf-8"))
        hollowed_files = payload.get("hollowed_files", [])
        line_total = 0
        file_count = 0

        for rel in hollowed_files:
            file_path = task_dir / "hollowed_files" / rel
            if not file_path.is_file():
                continue
            line_total += count_lines(file_path)
            file_count += 1

        language = task_dir.parents[2].name
        project = task_dir.parents[1].name
        row = {
            "language": language,
            "project": project,
            "task": task_dir.name,
            "files": file_count,
            "loc": line_total,
        }
        rows.append(row)
        per_lang[language].append(line_total)

    overall_avg = sum(r["loc"] for r in rows) / len(rows) if rows else 0.0
    print(f"L1 tasks: {len(rows)}")
    print(f"L1 average LOC: {overall_avg:.2f}")
    print()

    for language in sorted(per_lang):
        values = per_lang[language]
        avg = sum(values) / len(values)
        print(f"{language:12s} {len(values):2d} tasks, avg LOC = {avg:.2f}")

    print()
    print("Top 10 largest L1 tasks:")
    for row in sorted(rows, key=lambda x: x["loc"], reverse=True)[:10]:
        print(
            f"{row['language']:12s} {row['project']:24s} "
            f"LOC={row['loc']:6d} files={row['files']:4d}"
        )


if __name__ == "__main__":
    main()
