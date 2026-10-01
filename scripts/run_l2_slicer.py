#!/usr/bin/env python3
"""CLI entry point for the L2 file-level Task Slicer."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slicer.project import load_project, discover_projects
from slicer.file_task_builder import build_l2_tasks


def main():
    parser = argparse.ArgumentParser(description="Generate L2 file-level evaluation tasks")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Path to a single project directory")
    group.add_argument("--language", help="Process all projects for a language")
    group.add_argument("--all", action="store_true", help="Process all projects")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    datasets_root = repo_root / "datasets"

    if args.project:
        projects = [Path(args.project).resolve()]
    elif args.language:
        projects = discover_projects(datasets_root, args.language)
    else:
        projects = discover_projects(datasets_root)

    if not projects:
        print("No projects found.")
        return

    total_tasks = 0
    for project_dir in projects:
        print(f"\n[{project_dir.parent.name}/{project_dir.name}]")
        try:
            ctx = load_project(project_dir)
        except Exception as e:
            print(f"  ERROR loading project: {e}")
            continue

        print(f"  Language: {ctx.language}, Source files: {len(ctx.source_files)}")
        count = build_l2_tasks(ctx)
        print(f"  Generated {count} L2 tasks")
        total_tasks += count

    print(f"\nDone. Total L2 tasks generated: {total_tasks}")


if __name__ == "__main__":
    main()
