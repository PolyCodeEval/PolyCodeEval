#!/usr/bin/env python3
"""Validate accepted community submissions and refresh public snapshots."""

from __future__ import annotations

from exporters.community import build_community_snapshots


def main() -> int:
    paths = build_community_snapshots()
    total_bytes = sum(path.stat().st_size for path in paths)
    print(f"Generated {len(paths)} community artifacts ({total_bytes / 1_000_000:.2f} MB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
