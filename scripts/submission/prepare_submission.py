#!/usr/bin/env python3
"""Wrap an untouched native evaluation output into a PR-ready submission."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .core import (
        EXPECTED_TOTALS,
        SubmissionError,
        repository_root,
        tree_hashes,
        validate_package,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import EXPECTED_TOTALS, SubmissionError, repository_root, tree_hashes, validate_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path, help="Native evaluator output directory")
    parser.add_argument("--output", required=True, type=Path, help="PR-ready output directory")
    parser.add_argument("--level", required=True, choices=sorted(EXPECTED_TOTALS))
    parser.add_argument("--submission-name", required=True)
    parser.add_argument("--github-user", required=True)
    parser.add_argument("--affiliation", default="")
    parser.add_argument("--method", required=True)
    parser.add_argument("--method-version", required=True)
    parser.add_argument("--method-paper-url", default="")
    parser.add_argument("--method-code-url", default="")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--model-provider", default="")
    parser.add_argument("--scoring-mode", choices=["execution", "correctness_only", "full_quality"])
    parser.add_argument("--evaluation-command", default="")
    parser.add_argument("--started-at", default="")
    parser.add_argument("--finished-at", default="")
    parser.add_argument("--logs", type=Path, help="Optional log directory")
    parser.add_argument("--notes", default="")
    parser.add_argument("--repo-root", type=Path, default=repository_root())
    return parser.parse_args()


def prepare_submission(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Any]]:
    results = args.results.resolve()
    output = args.output.resolve()
    repo_root = args.repo_root.resolve()
    if not results.is_dir() or not (results / "summary.json").is_file():
        raise SubmissionError("--results must be a native evaluator output containing summary.json.")
    zip_path = Path(f"{output}.zip")
    if output.exists() or zip_path.exists():
        raise SubmissionError("Output directory or ZIP already exists; choose a new --output path.")
    if args.logs and not args.logs.resolve().is_dir():
        raise SubmissionError("--logs must be a directory.")

    test_mode, inferred_scoring = _infer_modes(results, args.level)
    scoring_mode = args.scoring_mode or inferred_scoring
    if args.level in {"L2", "L3"} and scoring_mode != "execution":
        raise SubmissionError("L2/L3 require scoring mode 'execution'.")
    if args.level in {"L0", "L1"} and scoring_mode not in {"correctness_only", "full_quality"}:
        raise SubmissionError("L0/L1 require correctness_only or full_quality.")

    metadata = _metadata(args, test_mode, scoring_mode, repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        before = tree_hashes(results)
        shutil.copytree(results, staging / "evaluation")
        after = tree_hashes(staging / "evaluation")
        if before != after:
            raise SubmissionError("Evaluation files changed while being copied.")
        if args.logs:
            shutil.copytree(args.logs.resolve(), staging / "logs")
        (staging / "submission.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        report = validate_package(staging, repo_root)
        if not report.valid:
            details = "; ".join(issue.message for issue in report.errors[:8])
            raise SubmissionError(f"Prepared package failed validation: {details}")

        os.replace(staging, output)
        _write_zip(output, zip_path)
        return output, zip_path, report.to_dict()
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _metadata(
    args: argparse.Namespace,
    test_mode: str,
    scoring_mode: str,
    repo_root: Path,
) -> dict[str, Any]:
    commit = _run(["git", "rev-parse", "HEAD"], repo_root) or "unknown"
    dirty = bool(_run(["git", "status", "--porcelain"], repo_root))
    docker = _run(["docker", "--version"], repo_root)
    evaluation: dict[str, Any] = {
        "polycodeevalCommit": commit,
        "testMode": test_mode,
        "scoringMode": scoring_mode,
        "packagedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workingTreeDirty": dirty,
        "environment": {
            "os": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "docker": docker,
        },
    }
    for key, value in (
        ("command", args.evaluation_command),
        ("startedAt", args.started_at),
        ("finishedAt", args.finished_at),
    ):
        if value:
            evaluation[key] = value
    return {
        "schemaVersion": "2",
        "benchmarkVersion": "pce-1.0",
        "level": args.level,
        "submissionName": args.submission_name,
        "submitter": {"github": args.github_user, "affiliation": args.affiliation},
        "method": {
            "name": args.method,
            "version": args.method_version,
            "paperUrl": args.method_paper_url,
            "codeUrl": args.method_code_url,
        },
        "model": {
            "name": args.model,
            "version": args.model_version,
            "provider": args.model_provider,
        },
        "evaluation": evaluation,
        "notes": args.notes,
    }


def _infer_modes(results: Path, level: str) -> tuple[str, str]:
    rows = []
    for path in sorted(results.glob("*/*/*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    if not rows:
        raise SubmissionError("No native per-task result JSON files were found.")
    modes = {row.get("test_mode") for row in rows if isinstance(row.get("test_mode"), str)}
    test_mode = next(iter(modes)) if len(modes) == 1 else "mixed"
    if level in {"L2", "L3"}:
        return test_mode, "execution"
    complete_quality = all(
        isinstance(row.get("overall_score"), (int, float))
        and isinstance(row.get("radar_scores"), dict)
        and all(isinstance(row["radar_scores"].get(key), (int, float)) for key in ("Correctness", "Faithfulness", "Architecture", "Health"))
        for row in rows
    )
    return test_mode, "full_quality" if complete_quality else "correctness_only"


def _run(command: list[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _write_zip(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())


def main() -> int:
    args = parse_args()
    try:
        directory, archive, report = prepare_submission(args)
    except SubmissionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Submission directory: {directory}")
    print(f"Submission ZIP:       {archive}")
    print(f"Tasks:                {report['submittedTasks']}/{report['expectedTasks']}")
    print(f"Missing tasks:        {report['missingTasks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
