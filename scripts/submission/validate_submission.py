#!/usr/bin/env python3
"""Validate a PR-ready PolyCodeEval result submission."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .core import repository_root, validate_package
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import repository_root, validate_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="PR-ready submission directory or ZIP")
    parser.add_argument("--repo-root", type=Path, default=repository_root())
    parser.add_argument("--json", action="store_true", help="Print the complete JSON report")
    parser.add_argument("--report", type=Path, help="Write the complete JSON report to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_package(args.package, args.repo_root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        status = "VALID" if report.valid else "INVALID"
        print(f"Submission: {status}")
        print(f"Tasks: {report.submitted_tasks}/{report.expected_tasks} submitted; {report.missing_tasks} missing")
        if report.aggregate:
            print(f"Build success: {report.aggregate['build_pass_rate']:.2%}")
            print(f"Full pass: {report.aggregate['full_pass_rate']:.2%}")
            print(f"Execution score: {report.aggregate['avg_execution_score']:.4f}")
        for issue in report.errors:
            location = issue.task or issue.path
            suffix = f" [{location}]" if location else ""
            print(f"ERROR {issue.code}: {issue.message}{suffix}")
        for issue in report.warnings:
            location = issue.task or issue.path
            suffix = f" [{location}]" if location else ""
            print(f"WARNING {issue.code}: {issue.message}{suffix}")
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
