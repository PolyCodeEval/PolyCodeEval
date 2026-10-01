#!/usr/bin/env python3
"""CLI entry point for the L1 project-level Task Slicer."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slicer.project import load_project, discover_projects
from slicer.project_task_builder import build_l1_task


def main():
    parser = argparse.ArgumentParser(description="Generate L1 project-level evaluation tasks")
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
        created = build_l1_task(ctx)
        if created:
            print(f"  Generated L1 task: L1_{ctx.project_dir.name}")
            total_tasks += 1
        else:
            print("  Skipped: no functions found in source files")

    print(f"\nDone. Total L1 tasks generated: {total_tasks}")


if __name__ == "__main__":
    main()
