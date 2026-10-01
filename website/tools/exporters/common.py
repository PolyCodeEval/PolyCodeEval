"""Shared configuration, serialization, and validation for website exports."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
DATASETS = ROOT / "datasets"
FINAL = ROOT / "finalresults"
ANSWERS = ROOT / "All_answers"
REPORTS = ROOT / "docs/reports"
PROMPT_DOCS = ROOT / "docs/prompts"
OUTPUT = ROOT / "website/public/data"

LANGUAGES = ("cpp", "go", "java", "javascript", "python")
LANGUAGE_LABELS = {
    "cpp": "C++",
    "go": "Go",
    "java": "Java",
    "javascript": "JavaScript",
    "python": "Python",
}
EXPECTED_TASKS = {"L0": 58, "L1": 58, "L2": 150, "L3": 2324}
EXPECTED_PAIRED = 1891
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


@dataclass(frozen=True)
class Run:
    id: str
    level: str
    method: str
    model: str
    result_path: str

    @property
    def path(self) -> Path:
        return ROOT / self.result_path


RUNS = (
    Run("l0-claude-code-sonnet", "L0", "Claude Code", "Claude Sonnet 4.6", "finalresults/L0/cc_l0_full_sonnet_eval_new"),
    Run("l0-codex-gpt", "L0", "Codex", "GPT-5.4", "finalresults/L0/codex_l0_full_gpt54_eval"),
    Run("l0-chatdev-sonnet", "L0", "ChatDev", "Claude Sonnet 4.6", "finalresults/L0/chatdev_l0_full_sonnet46_eval"),
    Run("l0-chatdev-gpt", "L0", "ChatDev", "GPT-5.4", "finalresults/L0/chatdev_l0_full_gpt54_eval"),
    Run("l1-claude-code-sonnet", "L1", "Claude Code", "Claude Sonnet 4.6", "finalresults/L1/cc_l1_full_sonnet_eval"),
    Run("l1-codex-gpt", "L1", "Codex", "GPT-5.4", "finalresults/L1/codex_l1_full_gpt54_eval"),
    Run("l2-direct-gpt", "L2", "Direct", "GPT-5.4", "finalresults/L2/direct_gpt_l2_eval/summary.json"),
    Run("l2-direct-sonnet", "L2", "Direct", "Claude Sonnet 4.6", "finalresults/L2/direct_sonnet_l2_eval/summary.json"),
    Run("l2-codex-gpt", "L2", "Codex", "GPT-5.4", "finalresults/L2/codex_l2_eval/summary.json"),
    Run("l2-claude-code-sonnet", "L2", "Claude Code", "Claude Sonnet 4.6", "finalresults/L2/cc_l2_eval/summary.json"),
    Run("l3-direct-gpt", "L3", "Direct", "GPT-5.4", "finalresults/L3/direct/direct_eval_gpt54/summary.json"),
    Run("l3-direct-sonnet", "L3", "Direct", "Claude Sonnet 4.6", "finalresults/L3/direct/direct_eval_sonnet/summary.json"),
    Run("l3-direct-deepseek", "L3", "Direct", "DeepSeek-V4-Pro", "finalresults/L3/direct/direct_eval_dpsk/summary.json"),
    Run("l3-repocoder-gpt", "L3", "RepoCoder", "GPT-5.4", "finalresults/L3/repocoder/repoder_eval_gpt5.4/summary.json"),
    Run("l3-repocoder-sonnet", "L3", "RepoCoder", "Claude Sonnet 4.6", "finalresults/L3/repocoder/repoder_eval_sonnet/summary.json"),
    Run("l3-repocoder-deepseek", "L3", "RepoCoder", "DeepSeek-V4-Pro", "finalresults/L3/repocoder/repoder_eval_dpsk/summary.json"),
    Run("l3-hcp-gpt", "L3", "HCP", "GPT-5.4", "finalresults/L3/HCP/hcpcoder_eval_gpt54/summary.json"),
    Run("l3-hcp-sonnet", "L3", "HCP", "Claude Sonnet 4.6", "finalresults/L3/HCP/hcpcoder_eval_sonnet/summary.json"),
    Run("l3-hcp-deepseek", "L3", "HCP", "DeepSeek-V4-Pro", "finalresults/L3/HCP/hcpcoder_eval_dpsk/summary.json"),
    Run("l3-aligncoder-gpt", "L3", "AlignCoder", "GPT-5.4", "finalresults/L3/aligncoder/aligncoder_eval_gpt54/summary.json"),
    Run("l3-aligncoder-sonnet", "L3", "AlignCoder", "Claude Sonnet 4.6", "finalresults/L3/aligncoder/aligncoder_eval_sonnet/summary.json"),
    Run("l3-aligncoder-deepseek", "L3", "AlignCoder", "DeepSeek-V4-Pro", "finalresults/L3/aligncoder/aligncoder_eval_dpsk/summary.json"),
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def source_link(path: Path | str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        candidate = candidate.relative_to(ROOT)
    return candidate.as_posix()


def round_value(value: float | int | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def write_json(relative: str, payload: Any) -> Path:
    path = OUTPUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def validate_output(output: Path = OUTPUT) -> list[str]:
    required = {
        "overview/summary.json", "dataset/projects.json", "results/aggregates.json", "quality/coverage.json",
        "quality/prompt-quality/index.json", "quality/prompt-quality/l0.json", "quality/prompt-quality/l2.json", "quality/prompt-quality/l3.json",
        "results/tasks/l0.json", "results/tasks/l1.json", "results/tasks/l2.json",
        *(f"results/tasks/l3-{language}.json" for language in LANGUAGES),
        "statistics/l2-to-l3.json", "statistics/significance.json", "tokens/accounting.json", "prompts/catalog.json",
    }
    errors: list[str] = []
    actual = {path.relative_to(output).as_posix() for path in output.rglob("*.json")}
    errors.extend(f"Missing output: {name}" for name in sorted(required - actual))
    payloads: dict[str, Any] = {}
    for relative in sorted(required & actual):
        try:
            payloads[relative] = load_json(output / relative)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid JSON {relative}: {exc}")
            continue
        if any(CJK_RE.search(text) for text in iter_strings(payloads[relative])):
            errors.append(f"Non-English text in {relative}")

    manifest = payloads.get("overview/summary.json", {})
    if manifest.get("taskCounts") != EXPECTED_TASKS:
        errors.append(f"Manifest task counts are {manifest.get('taskCounts')}, expected {EXPECTED_TASKS}")
    if manifest.get("pairedTaskCount") != EXPECTED_PAIRED:
        errors.append("Manifest paired task count is invalid")
    if {row.get("id") for row in manifest.get("configurations", [])} != {run.id for run in RUNS}:
        errors.append("Manifest configuration allowlist is invalid")

    dataset = payloads.get("dataset/projects.json", {})
    if dataset.get("projectCount") != 58:
        errors.append(f"Dataset registry has {dataset.get('projectCount')} projects, expected 58")
    if dataset.get("taskCounts") != EXPECTED_TASKS:
        errors.append("Dataset registry task counts are invalid")

    available = payloads.get("quality/coverage.json", {}).get("availableTaskCounts", {})
    for level, expected in EXPECTED_TASKS.items():
        if not 0 <= available.get(level, 0) <= expected:
            errors.append(f"{level} coverage count {available.get(level, 0)} is outside the valid range")
    for level in ("L0", "L1"):
        if available.get(level) != EXPECTED_TASKS[level]:
            errors.append(f"{level} project-level coverage is incomplete")

    for level, expected in {"L0": 58, "L2": 150, "L3": 2324}.items():
        count = payloads.get(f"quality/prompt-quality/{level.lower()}.json", {}).get("taskCount")
        if count != expected:
            errors.append(f"{level} prompt quality covers {count} tasks, expected {expected}")

    config_counts = defaultdict(int)
    for run in RUNS:
        config_counts[run.level] += 1
    task_payloads = {
        "L0": payloads.get("results/tasks/l0.json", {}).get("records", []),
        "L1": payloads.get("results/tasks/l1.json", {}).get("records", []),
        "L2": payloads.get("results/tasks/l2.json", {}).get("records", []),
        "L3": sum((payloads.get(f"results/tasks/l3-{language}.json", {}).get("records", []) for language in LANGUAGES), []),
    }
    required_fields = {"level", "language", "project", "taskId", "method", "model", "buildSuccess", "fullPass", "testPassRatio", "executionScore", "sourceLink"}
    for level, rows in task_payloads.items():
        expected_rows = EXPECTED_TASKS[level] * config_counts[level]
        if len(rows) != expected_rows:
            errors.append(f"{level}: found {len(rows)} evaluation records, expected {expected_rows}")
        if len({row.get("taskId") for row in rows}) != EXPECTED_TASKS[level]:
            errors.append(f"{level}: unique task count is invalid")
        for row in rows:
            missing = required_fields - row.keys()
            if missing:
                errors.append(f"{level}: record {row.get('taskId')} lacks {sorted(missing)}")
                break
            if level in {"L2", "L3"}:
                expected_full = bool(row["buildSuccess"]) and float(row["testPassRatio"]) >= 1.0
                if bool(row["fullPass"]) != expected_full:
                    errors.append(f"{level}: record {row.get('taskId')} violates the paper full-pass definition")
                    break
            if not str(row["sourceLink"]).startswith("finalresults/"):
                errors.append(f"{level}: invalid sourceLink for {row['taskId']}")
                break

    paired = payloads.get("statistics/l2-to-l3.json", {})
    if paired.get("pairedTaskCount") != EXPECTED_PAIRED:
        errors.append("L2-to-L3 paired count is invalid")
    if len(paired.get("records", [])) != EXPECTED_PAIRED * 2:
        errors.append("L2-to-L3 model-task record count is invalid")

    all_scope = {(row.get("configuration"), row.get("total")) for row in payloads.get("results/aggregates.json", {}).get("records", []) if row.get("scopeType") == "all"}
    for run in RUNS:
        if (run.id, EXPECTED_TASKS[run.level]) not in all_scope:
            errors.append(f"Missing or invalid aggregate for {run.id}")
    return errors
