#!/usr/bin/env python3
"""Repair Python generated_code outputs without overwriting the originals."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from adapter import _normalize_python_body


@dataclass(slots=True)
class RepairStats:
    total_files: int = 0
    python_files: int = 0
    modified_python_files: int = 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair Python generated_code indentation")
    parser.add_argument("--input-generated-code-root", type=Path, required=True)
    parser.add_argument("--datasets-python-root", type=Path, required=True)
    parser.add_argument("--output-generated-code-root", type=Path, required=True)
    return parser.parse_args()


def _repair_python_body(body: str) -> tuple[str, bool]:
    body = body.strip("\n")
    if not body:
        return "", False

    repaired = _normalize_python_body(body)
    lines = repaired.splitlines()
    if not lines:
        return repaired + "\n", repaired != body

    def _leading_spaces(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return repaired + "\n", repaired != body

    min_indent = min(_leading_spaces(line) for line in non_empty)
    target_indent = 4
    shift = target_indent - min_indent

    modified = repaired != body or shift != 0
    adjusted: list[str] = []
    for line in lines:
        if not line.strip():
            adjusted.append("")
            continue
        leading = _leading_spaces(line)
        content = line.lstrip(" ")
        new_indent = max(0, leading + shift)
        adjusted.append((" " * new_indent) + content)
    return "\n".join(adjusted).rstrip() + "\n", modified


def _task_dir_for(rel_path: Path, datasets_python_root: Path) -> Path:
    project = rel_path.parts[1]
    task_name = rel_path.stem
    return datasets_python_root / project / "tasks" / task_name


def main() -> int:
    args = _parse_args()
    src_root = args.input_generated_code_root.resolve()
    datasets_root = args.datasets_python_root.resolve()
    out_root = args.output_generated_code_root.resolve()

    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    stats = RepairStats()
    report: dict[str, dict[str, object]] = {}

    for path in sorted(src_root.rglob("*.txt")):
        stats.total_files += 1
        rel = path.relative_to(src_root)
        dest = out_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        text = path.read_text(encoding="utf-8")
        if rel.parts[0] != "python":
            dest.write_text(text, encoding="utf-8")
            continue

        stats.python_files += 1
        task_dir = _task_dir_for(rel, datasets_root)
        repaired, modified = _repair_python_body(text)
        dest.write_text(repaired, encoding="utf-8")

        if modified:
            stats.modified_python_files += 1

        report[str(rel)] = {
            "modified": modified,
            "task_dir": str(task_dir),
        }

    summary = {
        "input_generated_code_root": str(src_root),
        "datasets_python_root": str(datasets_root),
        "output_generated_code_root": str(out_root),
        "total_files": stats.total_files,
        "python_files": stats.python_files,
        "modified_python_files": stats.modified_python_files,
        "report": report,
    }
    (out_root.parent / f"{out_root.name}_repair_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "total_files": stats.total_files,
            "python_files": stats.python_files,
            "modified_python_files": stats.modified_python_files,
            "output_generated_code_root": str(out_root),
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
