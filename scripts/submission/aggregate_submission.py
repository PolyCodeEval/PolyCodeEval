#!/usr/bin/env python3
"""Recompute fixed-denominator metrics for a result submission."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .core import SubmissionError, aggregate_package, repository_root
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import SubmissionError, aggregate_package, repository_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="PR-ready submission directory or ZIP")
    parser.add_argument("--repo-root", type=Path, default=repository_root())
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        aggregate = aggregate_package(args.package, args.repo_root)
    except SubmissionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Aggregate written to {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
