#!/usr/bin/env python3
"""Run the upstream RepoCoder public pipeline on its released benchmark data."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
UPSTREAM_ROOT = REPO_ROOT.parent / "L3works" / "CodeT" / "RepoCoder"

REPOS = [
    "huggingface_diffusers",
    "nerfstudio-project_nerfstudio",
    "awslabs_fortuna",
    "huggingface_evaluate",
    "google_vizier",
    "alibaba_FederatedScope",
    "pytorch_rl",
    "opendilab_ACE",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run upstream RepoCoder on released public data")
    parser.add_argument(
        "--python",
        default="python3",
        help="Python interpreter used for upstream RepoCoder execution",
    )
    parser.add_argument(
        "--prediction-file",
        help="Optional prediction jsonl to use for the second-stage RepoCoder pipeline. "
             "If omitted, a mock prediction file will be generated from the dataset ground truth.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "output" / "repocoder_public"),
        help="Directory to store execution artifacts and reports",
    )
    return parser.parse_args()


def _ensure_public_layout() -> None:
    datasets = {
        "random-api-completion.test.jsonl": "api_level_completion_2k_context_codex.test.jsonl",
        "random-line-completion.test.jsonl": "line_level_completion_2k_context_codex.test.jsonl",
        "random-api-completion-short-version.test.jsonl": "api_level_completion_1k_context_codegen.test.jsonl",
        "random-line-completion-short-version.test.jsonl": "line_level_completion_1k_context_codegen.test.jsonl",
    }
    for link_name, target_name in datasets.items():
        link = UPSTREAM_ROOT / "datasets" / link_name
        target = Path(target_name)
        if link.exists() or link.is_symlink():
            continue
        link.symlink_to(target)


def _run_python(code: str, python_exe: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [python_exe, "-c", code],
        cwd=UPSTREAM_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _build_mock_predictions(output_dir: Path) -> Path:
    dataset_path = UPSTREAM_ROOT / "datasets" / "random-api-completion.test.jsonl"
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = predictions_dir / "rg-one-gram-ws-20-ss-2_samples.0.jsonl"

    lines = []
    with dataset_path.open(encoding="utf-8") as f:
        for raw_line in f:
            item = json.loads(raw_line)
            lines.append(
                {
                    "prompt": item["prompt"],
                    "choices": [{"text": item["metadata"]["ground_truth"]}],
                    "metadata": item["metadata"],
                }
            )
    with prediction_path.open("w", encoding="utf-8") as f:
        for item in lines:
            f.write(json.dumps(item) + "\n")
    return prediction_path


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    _ensure_public_layout()

    rg_code = (
        "from run_pipeline import run_RG1_and_oracle_method;"
        "from utils import CONSTANTS;"
        f"repos={REPOS!r};"
        "run_RG1_and_oracle_method(CONSTANTS.api_benchmark, repos, [20], [2])"
    )
    rg_result = _run_python(rg_code, args.python)
    (output_dir / "run_rg1.stdout.txt").write_text(rg_result.stdout, encoding="utf-8")
    (output_dir / "run_rg1.stderr.txt").write_text(rg_result.stderr, encoding="utf-8")
    if rg_result.returncode != 0:
        print(rg_result.stdout)
        print(rg_result.stderr, file=sys.stderr)
        return rg_result.returncode

    prediction_path = Path(args.prediction_file).resolve() if args.prediction_file else _build_mock_predictions(output_dir)

    repocoder_code = (
        "from run_pipeline import run_RepoCoder_method;"
        "from utils import CONSTANTS;"
        f"repos={REPOS!r};"
        f"prediction_path={str(prediction_path)!r};"
        "run_RepoCoder_method(CONSTANTS.api_benchmark, repos, [20], [2], prediction_path)"
    )
    repocoder_result = _run_python(repocoder_code, args.python)
    (output_dir / "run_repocoder.stdout.txt").write_text(repocoder_result.stdout, encoding="utf-8")
    (output_dir / "run_repocoder.stderr.txt").write_text(repocoder_result.stderr, encoding="utf-8")
    if repocoder_result.returncode != 0:
        print(repocoder_result.stdout)
        print(repocoder_result.stderr, file=sys.stderr)
        return repocoder_result.returncode

    score_code = (
        "from compute_score import compute_score_by_repo_with_metadata;"
        "from utils import Tools;"
        f"repos={REPOS!r};"
        f"lines=Tools.load_jsonl({str(prediction_path)!r});"
        "compute_score_by_repo_with_metadata(repos, lines, 'EM', passk=1);"
        "compute_score_by_repo_with_metadata(repos, lines, 'ES', passk=1)"
    )
    score_result = _run_python(score_code, args.python)
    (output_dir / "compute_score.stdout.txt").write_text(score_result.stdout, encoding="utf-8")
    (output_dir / "compute_score.stderr.txt").write_text(score_result.stderr, encoding="utf-8")
    if score_result.returncode != 0:
        print(score_result.stdout)
        print(score_result.stderr, file=sys.stderr)
        return score_result.returncode

    summary = {
        "upstream_root": str(UPSTREAM_ROOT),
        "python": args.python,
        "prediction_file": str(prediction_path),
        "output_dir": str(output_dir),
        "prompts": {
            "round1": str(UPSTREAM_ROOT / "prompts" / "rg-one-gram-ws-20-ss-2.jsonl"),
            "round2": str(UPSTREAM_ROOT / "prompts" / "repocoder-one-gram-ws-20-ss-2.jsonl"),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"RepoCoder public pipeline completed. Artifacts saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
