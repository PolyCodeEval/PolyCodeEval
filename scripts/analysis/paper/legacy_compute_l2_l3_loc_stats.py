#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from slicer.project import load_project  # noqa: E402


def count_lines_from_bytes(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def count_lines_from_file(path: Path) -> int:
    return count_lines_from_bytes(path.read_bytes())


def count_nonempty_lines_from_bytes(data: bytes) -> int:
    if not data:
        return 0
    return sum(1 for line in data.decode("utf-8", errors="replace").splitlines() if line.strip())


def resolve_source_path(ctx, rel_path: str) -> Path:
    for root in ctx.source_roots:
        candidate = root / rel_path
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Cannot resolve source file: {rel_path} in {ctx.project_dir}")


def compute_l2() -> tuple[list[dict], dict[str, list[int]]]:
    rows: list[dict] = []
    per_lang = defaultdict(list)
    project_cache: dict[Path, object] = {}

    for task_json in sorted(DATASETS_ROOT.glob("*/*/tasks/L2_*/task.json")):
        task_dir = task_json.parent
        payload = json.loads(task_json.read_text(encoding="utf-8"))
        language = task_dir.parents[2].name
        project_dir = task_dir.parents[1]
        project = project_dir.name
        target_rel = payload["stub_info"]["file"]
        if project_dir not in project_cache:
            ctx = load_project(project_dir)
            project_cache[project_dir] = ctx
        ctx = project_cache[project_dir]
        target_path = resolve_source_path(ctx, target_rel)
        loc = count_lines_from_file(target_path)
        hollowed_path = task_dir / "hollowed_files" / target_rel
        hollowed_loc = count_lines_from_file(hollowed_path)
        row = {
            "language": language,
            "project": project,
            "task": task_dir.name,
            "loc": loc,
            "hollowed_loc": hollowed_loc,
            "functions": payload["stub_info"].get("function_count", 0),
        }
        rows.append(row)
        per_lang[language].append(hollowed_loc)

    return rows, per_lang


def compute_l3() -> tuple[list[dict], dict[str, list[int]]]:
    rows: list[dict] = []
    per_lang_body = defaultdict(list)

    project_cache: dict[Path, object] = {}

    for task_json in sorted(DATASETS_ROOT.glob("*/*/tasks/L3_*/task.json")):
        task_dir = task_json.parent
        payload = json.loads(task_json.read_text(encoding="utf-8"))
        language = task_dir.parents[2].name
        project_dir = task_dir.parents[1]
        project_name = project_dir.name
        stub = payload["stub_info"]
        target_rel = stub["file"]
        func_name = stub["func_name"]
        body_start = stub["body_start_byte"]
        body_end = stub["body_end_byte"]

        if project_dir not in project_cache:
            ctx = load_project(project_dir)
            project_cache[project_dir] = ctx
        ctx = project_cache[project_dir]
        source_path = resolve_source_path(ctx, target_rel)
        source_bytes = source_path.read_bytes()
        body_bytes = source_bytes[body_start:body_end]
        body_loc = count_lines_from_bytes(body_bytes)
        nonempty_body_loc = count_nonempty_lines_from_bytes(body_bytes)
        row = {
            "language": language,
            "project": project_name,
            "task": task_dir.name,
            "body_loc": body_loc,
            "nonempty_body_loc": nonempty_body_loc,
            "func": func_name,
        }
        rows.append(row)
        per_lang_body[language].append(body_loc)

    return rows, per_lang_body


def print_section(title: str) -> None:
    print(title)
    print("-" * len(title))


def main() -> None:
    l2_rows, l2_per_lang = compute_l2()
    l3_rows, l3_body_per_lang = compute_l3()

    print_section("L2 target-file LOC")
    l2_avg = sum(r["loc"] for r in l2_rows) / len(l2_rows)
    l2_hollowed_avg = sum(r["hollowed_loc"] for r in l2_rows) / len(l2_rows)
    print(f"L2 tasks: {len(l2_rows)}")
    print(f"L2 average original target-file LOC: {l2_avg:.2f}")
    print(f"L2 average hollowed target-file LOC: {l2_hollowed_avg:.2f}")
    print()
    for language in sorted(l2_per_lang):
        values = l2_per_lang[language]
        print(f"{language:12s} {len(values):3d} tasks, avg LOC = {sum(values) / len(values):.2f}")

    print()
    print("Top 10 largest L2 tasks:")
    for row in sorted(l2_rows, key=lambda x: x["loc"], reverse=True)[:10]:
        print(
            f"{row['language']:12s} {row['project']:24s} "
            f"{row['task']:30s} LOC={row['loc']:6d} funcs={row['functions']:3d}"
        )

    print()
    print_section("L3 function LOC")
    body_avg = sum(r["body_loc"] for r in l3_rows) / len(l3_rows)
    nonempty_body_avg = sum(r["nonempty_body_loc"] for r in l3_rows) / len(l3_rows)
    print(f"L3 tasks: {len(l3_rows)}")
    print(f"L3 average function-body LOC: {body_avg:.2f}")
    print(f"L3 average non-empty function-body LOC: {nonempty_body_avg:.2f}")
    print()
    for language in sorted(l3_body_per_lang):
        body_values = l3_body_per_lang[language]
        print(
            f"{language:12s} {len(body_values):4d} tasks, "
            f"avg body LOC = {sum(body_values) / len(body_values):.2f}"
        )

    print()
    print("Top 10 largest L3 function bodies:")
    for row in sorted(l3_rows, key=lambda x: x["body_loc"], reverse=True)[:10]:
        print(
            f"{row['language']:12s} {row['project']:24s} {row['func']:24s} "
            f"body={row['body_loc']:4d} nonempty={row['nonempty_body_loc']:4d}"
        )


if __name__ == "__main__":
    main()
