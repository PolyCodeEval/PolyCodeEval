#!/usr/bin/env python3
"""Runbook helpers for L0 prompt review result ingestion and aggregation."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS_ROOT = REPO_ROOT / "datasets"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "finalresults" / "l0_prompt_score" / "gpt5.4_judge"
REVIEW_TYPE = "l0_prompt_review"
REVIEW_SCHEMA_VERSION = "l0_prompt_review_v1"
JUDGE_MODEL = "gpt-5.4"
DIMENSIONS = ("completeness", "unambiguity", "testability", "consistency")
EXPECTED_LANGUAGE_COUNTS = {
    "python": 13,
    "go": 12,
    "cpp": 11,
    "java": 11,
    "javascript": 11,
}


class ReviewValidationError(Exception):
    """Raised when a review payload is invalid."""


@dataclass(frozen=True)
class TaskInfo:
    language: str
    project: str
    task_name: str
    prompt_path: Path
    project_root: Path

    @property
    def task_id(self) -> str:
        return f"{self.language}/{self.project}/{self.task_name}"

    @property
    def project_id(self) -> str:
        return f"{self.language}/{self.project}"

    @property
    def output_dir(self) -> Path:
        return DEFAULT_OUTPUT_ROOT / self.language / self.project

    @property
    def raw_file_name(self) -> str:
        return f"{self.task_name}.raw.md"

    @property
    def json_file_name(self) -> str:
        return f"{self.task_name}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def discover_tasks() -> list[TaskInfo]:
    tasks: list[TaskInfo] = []
    for prompt_path in sorted(DATASETS_ROOT.glob("*/*/tasks/L0_*/prompt.md")):
        task_dir = prompt_path.parent
        project_root = task_dir.parents[1]
        tasks.append(
            TaskInfo(
                language=project_root.parent.name,
                project=project_root.name,
                task_name=task_dir.name,
                prompt_path=prompt_path,
                project_root=project_root,
            )
        )
    return tasks


def validate_discovery(tasks: list[TaskInfo]) -> dict[str, int]:
    if len(tasks) != 58:
        raise ReviewValidationError(f"expected 58 L0 prompt tasks, found {len(tasks)}")
    by_language: dict[str, int] = {}
    for task in tasks:
        by_language[task.language] = by_language.get(task.language, 0) + 1
    if by_language != EXPECTED_LANGUAGE_COUNTS:
        raise ReviewValidationError(
            f"language counts mismatch: expected {EXPECTED_LANGUAGE_COUNTS}, got {by_language}"
        )
    return by_language


def _extract_json_blob(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(raw_text):
        if char != "{":
            continue
        try:
            payload, end = decoder.raw_decode(raw_text[index:])
        except json.JSONDecodeError:
            continue
        trailing = raw_text[index + end :].strip()
        if trailing:
            continue
        if isinstance(payload, dict):
            return payload
    raise ReviewValidationError("could not extract a single JSON object from raw response")


def _parse_score(value: Any, *, name: str) -> float:
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ReviewValidationError(f"{name} score is not numeric: {value!r}") from exc
    if dec < Decimal("1.0") or dec > Decimal("5.0"):
        raise ReviewValidationError(f"{name} score out of range [1.0, 5.0]: {value!r}")
    if dec.as_tuple().exponent < -1:
        raise ReviewValidationError(f"{name} score has more than 1 decimal place: {value!r}")
    return float(dec)


def _normalize_review(task: TaskInfo, raw_payload: dict[str, Any]) -> dict[str, Any]:
    if "scores" not in raw_payload or not isinstance(raw_payload["scores"], dict):
        raise ReviewValidationError("missing scores object")

    normalized_scores: dict[str, dict[str, Any]] = {}
    score_values: list[float] = []
    for dimension in DIMENSIONS:
        value = raw_payload["scores"].get(dimension)
        if not isinstance(value, dict):
            raise ReviewValidationError(f"missing scores.{dimension} object")
        score = _parse_score(value.get("score"), name=dimension)
        reason = value.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ReviewValidationError(f"missing scores.{dimension}.reason")
        normalized_scores[dimension] = {
            "score": score,
            "reason": reason.strip(),
        }
        score_values.append(score)

    overall_score = round(sum(score_values) / len(score_values), 2)
    return {
        "task": task.task_id,
        "project": task.project_id,
        "language": task.language,
        "prompt_path": str(task.prompt_path),
        "project_root": str(task.project_root),
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": JUDGE_MODEL,
        "scores": normalized_scores,
        "overall_score": overall_score,
        "raw_response_file": task.raw_file_name,
    }


def _find_task(tasks: list[TaskInfo], task_id: str) -> TaskInfo:
    for task in tasks:
        if task.task_id == task_id:
            return task
    raise ReviewValidationError(f"unknown task id: {task_id}")


def ingest_result(
    *,
    output_root: Path,
    task: TaskInfo,
    raw_response_path: Path,
    agent_id: str,
    agent_type: str,
    status: str,
    started_at: str,
    completed_at: str,
    retry_count: int,
    error: str | None,
) -> tuple[bool, str | None, Path | None]:
    raw_text = raw_response_path.read_text(encoding="utf-8")
    parse_ok = False
    json_result_path: Path | None = None
    parse_error: str | None = None
    try:
        payload = _extract_json_blob(raw_text)
        normalized = _normalize_review(task, payload)
        json_result_path = output_root / task.language / task.project / task.json_file_name
        _write_json(json_result_path, normalized)
        parse_ok = True
    except ReviewValidationError as exc:
        parse_error = str(exc)

    run_row = {
        "task": task.task_id,
        "language": task.language,
        "project": task.project_id,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "model": JUDGE_MODEL,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "raw_response_path": str(raw_response_path),
        "json_result_path": str(json_result_path) if json_result_path else None,
        "parse_ok": parse_ok,
        "retry_count": retry_count,
        "error": error or parse_error,
    }
    _append_jsonl(output_root / "agent_runs.jsonl", run_row)
    return parse_ok, parse_error, json_result_path


def aggregate(output_root: Path) -> dict[str, Any]:
    tasks = discover_tasks()
    validate_discovery(tasks)

    results: list[dict[str, Any]] = []
    failed_tasks: list[dict[str, Any]] = []
    for task in tasks:
        result_path = output_root / task.language / task.project / task.json_file_name
        raw_path = output_root / task.language / task.project / task.raw_file_name
        if result_path.is_file():
            results.append(_load_json(result_path))
        else:
            failed_tasks.append(
                {
                    "task": task.task_id,
                    "language": task.language,
                    "project": task.project_id,
                    "missing_json": not result_path.is_file(),
                    "missing_raw": not raw_path.is_file(),
                }
            )

    def _avg(values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    by_language: dict[str, list[dict[str, Any]]] = {}
    by_project: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        by_language.setdefault(row["language"], []).append(row)
        by_project.setdefault(row["project"], []).append(row)

    def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        completeness = [row["scores"]["completeness"]["score"] for row in rows]
        unambiguity = [row["scores"]["unambiguity"]["score"] for row in rows]
        testability = [row["scores"]["testability"]["score"] for row in rows]
        consistency = [row["scores"]["consistency"]["score"] for row in rows]
        overall = [row["overall_score"] for row in rows]
        return {
            "total": len(rows),
            "avg_overall_score": _avg(overall),
            "avg_completeness": _avg(completeness),
            "avg_unambiguity": _avg(unambiguity),
            "avg_testability": _avg(testability),
            "avg_consistency": _avg(consistency),
        }

    summary = {
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": JUDGE_MODEL,
        "generated_at": _utc_now(),
        "total": len(tasks),
        "completed": len(results),
        "failed": len(tasks) - len(results),
        "avg_overall_score": _summary(results)["avg_overall_score"] if results else None,
        "avg_completeness": _summary(results)["avg_completeness"] if results else None,
        "avg_unambiguity": _summary(results)["avg_unambiguity"] if results else None,
        "avg_testability": _summary(results)["avg_testability"] if results else None,
        "avg_consistency": _summary(results)["avg_consistency"] if results else None,
        "by_language": {name: _summary(rows) for name, rows in sorted(by_language.items())},
        "by_project": {name: _summary(rows) for name, rows in sorted(by_project.items())},
        "failed_tasks": failed_tasks,
    }
    _write_json(output_root / "summary.json", summary)
    return summary


def _cmd_discover(args: argparse.Namespace) -> int:
    tasks = discover_tasks()
    counts = validate_discovery(tasks)
    payload = {
        "total": len(tasks),
        "by_language": counts,
        "tasks": [
            {
                "task": task.task_id,
                "project": task.project_id,
                "language": task.language,
                "prompt_path": str(task.prompt_path),
                "project_root": str(task.project_root),
            }
            for task in tasks
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    tasks = discover_tasks()
    validate_discovery(tasks)
    task = _find_task(tasks, args.task)

    raw_path = output_root / task.language / task.project / task.raw_file_name
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_text = Path(args.raw_input).read_text(encoding="utf-8")
    raw_path.write_text(raw_text, encoding="utf-8")

    parse_ok, parse_error, json_result_path = ingest_result(
        output_root=output_root,
        task=task,
        raw_response_path=raw_path,
        agent_id=args.agent_id,
        agent_type=args.agent_type,
        status=args.status,
        started_at=args.started_at,
        completed_at=args.completed_at,
        retry_count=args.retry_count,
        error=args.error,
    )
    payload = {
        "task": task.task_id,
        "parse_ok": parse_ok,
        "json_result_path": str(json_result_path) if json_result_path else None,
        "error": parse_error,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if parse_ok else 1


def _cmd_materialize(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    tasks = discover_tasks()
    validate_discovery(tasks)
    task = _find_task(tasks, args.task)

    raw_path = output_root / task.language / task.project / task.raw_file_name
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(args.raw_text, encoding="utf-8")

    parse_ok, parse_error, json_result_path = ingest_result(
        output_root=output_root,
        task=task,
        raw_response_path=raw_path,
        agent_id=args.agent_id,
        agent_type=args.agent_type,
        status=args.status,
        started_at=args.started_at,
        completed_at=args.completed_at,
        retry_count=args.retry_count,
        error=args.error,
    )
    payload = {
        "task": task.task_id,
        "parse_ok": parse_ok,
        "raw_path": str(raw_path),
        "json_result_path": str(json_result_path) if json_result_path else None,
        "error": parse_error,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if parse_ok else 1


def _cmd_record_run(args: argparse.Namespace) -> int:
    row = {
        "task": args.task,
        "language": args.language,
        "project": args.project,
        "agent_id": args.agent_id,
        "agent_type": args.agent_type,
        "model": JUDGE_MODEL,
        "status": args.status,
        "started_at": args.started_at,
        "completed_at": args.completed_at,
        "raw_response_path": args.raw_response_path,
        "json_result_path": args.json_result_path,
        "parse_ok": args.parse_ok,
        "retry_count": args.retry_count,
        "error": args.error,
    }
    _append_jsonl(args.output_root.resolve() / "agent_runs.jsonl", row)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


def _cmd_normalize(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    tasks = discover_tasks()
    validate_discovery(tasks)
    task = _find_task(tasks, args.task)

    raw_path = Path(args.raw_input).resolve()
    raw_text = raw_path.read_text(encoding="utf-8")
    payload = _extract_json_blob(raw_text)
    normalized = _normalize_review(task, payload)
    json_result_path = output_root / task.language / task.project / task.json_file_name
    _write_json(json_result_path, normalized)
    result = {
        "task": task.task_id,
        "raw_path": str(raw_path),
        "json_result_path": str(json_result_path),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    summary = aggregate(output_root)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helpers for L0 prompt review execution.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Discover all L0 prompt tasks.")
    discover_parser.set_defaults(func=_cmd_discover)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a single raw agent response.")
    ingest_parser.add_argument("--task", required=True, help="Task id, e.g. javascript/mitt/L0_mitt")
    ingest_parser.add_argument("--raw-input", required=True, help="Path to raw response text file")
    ingest_parser.add_argument("--agent-id", required=True)
    ingest_parser.add_argument("--agent-type", default="default")
    ingest_parser.add_argument("--status", required=True)
    ingest_parser.add_argument("--started-at", required=True)
    ingest_parser.add_argument("--completed-at", required=True)
    ingest_parser.add_argument("--retry-count", type=int, default=0)
    ingest_parser.add_argument("--error", default=None)
    ingest_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    ingest_parser.set_defaults(func=_cmd_ingest)

    materialize_parser = subparsers.add_parser(
        "materialize",
        help="Write raw response text directly and ingest it in one step.",
    )
    materialize_parser.add_argument("--task", required=True, help="Task id, e.g. javascript/mitt/L0_mitt")
    materialize_parser.add_argument("--raw-text", required=True, help="Raw response text")
    materialize_parser.add_argument("--agent-id", required=True)
    materialize_parser.add_argument("--agent-type", default="default")
    materialize_parser.add_argument("--status", required=True)
    materialize_parser.add_argument("--started-at", required=True)
    materialize_parser.add_argument("--completed-at", required=True)
    materialize_parser.add_argument("--retry-count", type=int, default=0)
    materialize_parser.add_argument("--error", default=None)
    materialize_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    materialize_parser.set_defaults(func=_cmd_materialize)

    record_run_parser = subparsers.add_parser(
        "record-run",
        help="Append one agent run row to agent_runs.jsonl without parsing content.",
    )
    record_run_parser.add_argument("--task", required=True)
    record_run_parser.add_argument("--language", required=True)
    record_run_parser.add_argument("--project", required=True)
    record_run_parser.add_argument("--agent-id", required=True)
    record_run_parser.add_argument("--agent-type", default="default")
    record_run_parser.add_argument("--status", required=True)
    record_run_parser.add_argument("--started-at", required=True)
    record_run_parser.add_argument("--completed-at", required=True)
    record_run_parser.add_argument("--raw-response-path", required=True)
    record_run_parser.add_argument("--json-result-path", required=True)
    record_run_parser.add_argument("--parse-ok", action="store_true")
    record_run_parser.add_argument("--retry-count", type=int, default=0)
    record_run_parser.add_argument("--error", default=None)
    record_run_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    record_run_parser.set_defaults(func=_cmd_record_run)

    normalize_parser = subparsers.add_parser(
        "normalize",
        help="Normalize a raw response file into the standard per-task JSON schema.",
    )
    normalize_parser.add_argument("--task", required=True, help="Task id, e.g. javascript/mitt/L0_mitt")
    normalize_parser.add_argument("--raw-input", required=True, help="Path to raw response text file")
    normalize_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    normalize_parser.set_defaults(func=_cmd_normalize)

    aggregate_parser = subparsers.add_parser("aggregate", help="Aggregate all ingested results.")
    aggregate_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    aggregate_parser.set_defaults(func=_cmd_aggregate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
