#!/usr/bin/env python3
"""Score L2 prompts for file-level multi-function completion sufficiency."""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Any

from l0_evaluator.scoring.judge_clients import JudgeError, resolve_judge_provider_model, run_judge
from l3_evaluator.workspace import _resolve_file

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS_ROOT = REPO_ROOT / "datasets"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "finalresults" / "l2_prompt_score" / "gpt5.4_judge"
REVIEW_TYPE = "l2_prompt_score"
REVIEW_SCHEMA_VERSION = "l2_prompt_score_v1"
DEFAULT_JUDGE_MODEL_LABEL = "gpt-5.4"
MISSING_DESCRIPTION_SCORE = 1.0
_JSONL_LOCK = Lock()


class ReviewValidationError(Exception):
    pass


@dataclass(frozen=True)
class TaskInfo:
    language: str
    project: str
    task_name: str
    task_dir: Path
    task_json_path: Path
    prompt_path: Path
    run_config_path: Path

    @property
    def task_id(self) -> str:
        return f"{self.language}/{self.project}/{self.task_name}"

    @property
    def project_id(self) -> str:
        return f"{self.language}/{self.project}"

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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _JSONL_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def discover_tasks(*, language: str | None = None, project: str | None = None, task: str | None = None) -> list[TaskInfo]:
    tasks: list[TaskInfo] = []
    for task_json_path in sorted(DATASETS_ROOT.glob("*/*/tasks/L2_*/task.json")):
        task_dir = task_json_path.parent
        project_root = task_dir.parents[1]
        current = TaskInfo(
            language=project_root.parent.name,
            project=project_root.name,
            task_name=task_dir.name,
            task_dir=task_dir,
            task_json_path=task_json_path,
            prompt_path=task_dir / "prompt.md",
            run_config_path=task_dir / "run_config.json",
        )
        if language and current.language != language:
            continue
        if project and f"{current.language}/{current.project}" != project and current.project != project:
            continue
        if task and current.task_id != task and current.task_name != task:
            continue
        tasks.append(current)
    return tasks


def _extract_section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^# {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^# ", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    return markdown[start:end].strip()


def build_task_context(task: TaskInfo) -> dict[str, Any]:
    task_json = _load_json(task.task_json_path)
    run_config = _load_json(task.run_config_path)
    src_dir = (task.task_dir / run_config["src_dir"]).resolve()
    target_rel = task_json["target"]
    resolved_rel = _resolve_file(src_dir, target_rel)
    source_path = (src_dir / resolved_rel).resolve()
    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    skeleton_path = task.task_dir / "hollowed_files" / target_rel
    if not skeleton_path.exists():
        skeleton_path = task.task_dir / "hollowed_files" / resolved_rel
    skeleton_text = skeleton_path.read_text(encoding="utf-8", errors="replace")
    prompt_markdown = task.prompt_path.read_text(encoding="utf-8", errors="replace")
    file_description = _extract_section(prompt_markdown, "File Description")
    function_responsibilities = _extract_section(prompt_markdown, "Function Responsibilities")
    return {
        "task_json": task_json,
        "run_config": run_config,
        "source_file_path": str(source_path),
        "source_file_rel": resolved_rel,
        "source_text": source_text,
        "skeleton_text": skeleton_text,
        "file_description": file_description,
        "function_responsibilities": function_responsibilities,
        "descriptions_present": bool(file_description.strip() and function_responsibilities.strip()),
    }


def build_judge_prompt(task: TaskInfo, context: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are a senior code review judge. "
        "Your task is to evaluate an L2 file-level prompt description against the real full target file implementation. "
        "This is a multi-function completion task where the model must reconstruct an entire file with multiple hollowed function bodies. "
        "Focus on two things only: whether the file-level and function-level descriptions match the implementation, "
        "and whether they are complete enough to support reconstructing the file. "
        "Return valid JSON only."
    )
    user = f"""Evaluate this L2 file-level prompt description.

Task ID: {task.task_id}
Language: {task.language}
Project: {task.project}
Target file: {context['task_json'].get('target')}
Hollowed function count: {context['task_json']['stub_info'].get('function_count')}

File Description:
```markdown
{context['file_description']}
```

Function Responsibilities:
```markdown
{context['function_responsibilities']}
```

Target file skeleton:
```{context['task_json']['stub_info']['lang']}
{context['skeleton_text']}
```

Full current implementation of the target file:
```{context['task_json']['stub_info']['lang']}
{context['source_text']}
```

Return JSON with this exact shape:
{{
  "score": 4.3,
  "reason": "short markdown paragraph",
  "missing_functionality": ["item 1"],
  "incorrect_or_misleading_points": ["item 1"],
  "complete_enough": true
}}

Scoring rules:
- `score` must be on a 1.0 to 5.0 scale only.
- Do not use a 10-point scale or any other scale.
- Use at most one decimal place.
- Higher score means the file-level descriptions both match the implementation and are sufficiently complete to support reconstructing the file.
- `complete_enough` should be true only if the prompt description is sufficient for a model to reconstruct the file without missing important behavior.
"""
    return system, user


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


def _normalize_review(task: TaskInfo, context: dict[str, Any], raw_payload: dict[str, Any], *, judge_model: str) -> dict[str, Any]:
    score = _parse_score(raw_payload.get("score"), name="score")
    reason = raw_payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ReviewValidationError("missing reason")
    missing_functionality = raw_payload.get("missing_functionality") or []
    incorrect_points = raw_payload.get("incorrect_or_misleading_points") or []
    if not isinstance(missing_functionality, list) or not isinstance(incorrect_points, list):
        raise ReviewValidationError("missing_functionality / incorrect_or_misleading_points must be arrays")
    complete_enough = raw_payload.get("complete_enough")
    if not isinstance(complete_enough, bool):
        raise ReviewValidationError("complete_enough must be bool")
    return {
        "task": task.task_id,
        "project": task.project_id,
        "language": task.language,
        "prompt_path": str(task.prompt_path),
        "task_json_path": str(task.task_json_path),
        "source_file_path": context["source_file_path"],
        "target_file": context["task_json"].get("target"),
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": judge_model,
        "descriptions_present": context["descriptions_present"],
        "score": score,
        "reason": reason.strip(),
        "missing_functionality": [str(item).strip() for item in missing_functionality],
        "incorrect_or_misleading_points": [str(item).strip() for item in incorrect_points],
        "complete_enough": complete_enough,
        "raw_response_file": task.raw_file_name,
    }


def _make_missing_description_result(task: TaskInfo, context: dict[str, Any], *, judge_model: str) -> dict[str, Any]:
    return {
        "task": task.task_id,
        "project": task.project_id,
        "language": task.language,
        "prompt_path": str(task.prompt_path),
        "task_json_path": str(task.task_json_path),
        "source_file_path": context["source_file_path"],
        "target_file": context["task_json"].get("target"),
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": judge_model,
        "descriptions_present": False,
        "score": MISSING_DESCRIPTION_SCORE,
        "reason": "The prompt is missing either File Description or Function Responsibilities, so the file-level multi-function completion description cannot be evaluated properly.",
        "missing_functionality": ["File Description or Function Responsibilities section is missing."],
        "incorrect_or_misleading_points": [],
        "complete_enough": False,
        "raw_response_file": None,
    }


def _score_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [row["score"] for row in rows]
    complete = [row for row in rows if row.get("complete_enough")]
    missing_desc = [row for row in rows if not row.get("descriptions_present", True)]
    return {
        "total": len(rows),
        "avg_score": round(sum(scores) / len(scores), 4) if scores else None,
        "complete_enough_count": len(complete),
        "missing_description_count": len(missing_desc),
    }


def collect_results(output_root: Path, *, language: str | None = None, project: str | None = None, task: str | None = None) -> tuple[list[TaskInfo], list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    tasks = discover_tasks(language=language, project=project, task=task)
    by_project_rows: dict[str, list[dict[str, Any]]] = {}
    by_language_rows: dict[str, list[dict[str, Any]]] = {}
    results: list[dict[str, Any]] = []
    failed_tasks: list[dict[str, Any]] = []
    for item in tasks:
        result_path = output_root / item.language / item.project / item.json_file_name
        raw_path = output_root / item.language / item.project / item.raw_file_name
        if result_path.is_file():
            row = _load_json(result_path)
            results.append(row)
            by_project_rows.setdefault(item.project_id, []).append(row)
            by_language_rows.setdefault(item.language, []).append(row)
        else:
            failed_tasks.append(
                {
                    "task": item.task_id,
                    "language": item.language,
                    "project": item.project_id,
                    "missing_json": True,
                    "missing_raw": not raw_path.is_file(),
                }
            )
    return tasks, results, failed_tasks, by_project_rows, by_language_rows


def write_incomplete_run_report(output_root: Path, *, tasks: list[TaskInfo], results: list[dict[str, Any]], failed_tasks: list[dict[str, Any]], judge_model: str, language: str | None = None, project: str | None = None, task: str | None = None) -> Path:
    report = {
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": judge_model,
        "generated_at": _utc_now(),
        "scope": {"language": language, "project": project, "task": task},
        "total_expected": len(tasks),
        "completed": len(results),
        "missing": len(failed_tasks),
        "failed_tasks": failed_tasks,
        "resume_hint": "Rerun the same command with --resume after resolving the interruption.",
    }
    report_path = output_root / "incomplete_run.json"
    _write_json(report_path, report)
    return report_path


def remove_existing_aggregate_outputs(output_root: Path, *, language: str | None = None, project: str | None = None, task: str | None = None) -> None:
    (output_root / "summary.json").unlink(missing_ok=True)
    tasks = discover_tasks(language=language, project=project, task=task)
    touched_projects = sorted({(item.language, item.project) for item in tasks})
    for language_name, project_name in touched_projects:
        (output_root / language_name / project_name / f"L2_{project_name}.json").unlink(missing_ok=True)


def aggregate(output_root: Path, *, language: str | None = None, project: str | None = None, task: str | None = None, judge_model: str = DEFAULT_JUDGE_MODEL_LABEL) -> dict[str, Any]:
    tasks, results, failed_tasks, by_project_rows, by_language_rows = collect_results(output_root, language=language, project=project, task=task)
    if failed_tasks:
        raise ReviewValidationError(f"cannot aggregate incomplete run: {len(results)}/{len(tasks)} tasks completed, {len(failed_tasks)} missing")
    for project_id, rows in sorted(by_project_rows.items()):
        language_name, project_name = project_id.split("/", 1)
        project_summary = {
            "project": project_id,
            "language": language_name,
            **_score_rows(rows),
            "completed": len(rows),
            "failed": 0,
            "tasks": [
                {
                    "task": row["task"],
                    "score": row["score"],
                    "complete_enough": row["complete_enough"],
                    "descriptions_present": row.get("descriptions_present", True),
                }
                for row in sorted(rows, key=lambda entry: entry["task"])
            ],
            "failed_tasks": [],
        }
        _write_json(output_root / language_name / project_name / f"L2_{project_name}.json", project_summary)
    summary = {
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": judge_model,
        "generated_at": _utc_now(),
        "total": len(tasks),
        "completed": len(results),
        "failed": 0,
        **_score_rows(results),
        "by_language": {name: _score_rows(rows) for name, rows in sorted(by_language_rows.items())},
        "by_project": {name: _score_rows(rows) for name, rows in sorted(by_project_rows.items())},
        "failed_tasks": [],
    }
    _write_json(output_root / "summary.json", summary)
    return summary


def _record_run(*, output_root: Path, task: TaskInfo, status: str, started_at: str, completed_at: str, raw_response_path: str | None, json_result_path: str | None, parse_ok: bool, error: str | None, judge_model: str) -> None:
    _append_jsonl(
        output_root / "agent_runs.jsonl",
        {
            "task": task.task_id,
            "language": task.language,
            "project": task.project_id,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "raw_response_path": raw_response_path,
            "json_result_path": json_result_path,
            "parse_ok": parse_ok,
            "error": error,
            "model": judge_model,
        },
    )


def _run_single_task(task: TaskInfo, *, output_root: Path, provider: str, model: str, resume: bool) -> dict[str, Any]:
    result_path = output_root / task.language / task.project / task.json_file_name
    raw_path = output_root / task.language / task.project / task.raw_file_name
    if resume and result_path.is_file():
        return _load_json(result_path)
    started_at = _utc_now()
    try:
        context = build_task_context(task)
        if not context["descriptions_present"]:
            result = _make_missing_description_result(task, context, judge_model=model)
            _write_json(result_path, result)
            _record_run(output_root=output_root, task=task, status="ok", started_at=started_at, completed_at=_utc_now(), raw_response_path=None, json_result_path=str(result_path), parse_ok=True, error=None, judge_model=model)
            return result
        system_prompt, user_prompt = build_judge_prompt(task, context)
        payload = run_judge(provider, model, system_prompt, user_prompt)
        _write_text(raw_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        result = _normalize_review(task, context, payload, judge_model=model)
        _write_json(result_path, result)
        _record_run(output_root=output_root, task=task, status="ok", started_at=started_at, completed_at=_utc_now(), raw_response_path=str(raw_path), json_result_path=str(result_path), parse_ok=True, error=None, judge_model=model)
        return result
    except (JudgeError, ReviewValidationError, FileNotFoundError, OSError, ValueError, KeyError) as exc:
        _record_run(output_root=output_root, task=task, status="failed", started_at=started_at, completed_at=_utc_now(), raw_response_path=str(raw_path) if raw_path.exists() else None, json_result_path=None, parse_ok=False, error=str(exc), judge_model=model)
        raise


def _cmd_discover(args: argparse.Namespace) -> int:
    tasks = discover_tasks(language=args.language, project=args.project, task=args.task)
    rows = []
    for task in tasks[: args.limit or None]:
        context = build_task_context(task)
        rows.append({
            "task": task.task_id,
            "descriptions_present": context["descriptions_present"],
            "file_description_preview": context["file_description"][:300],
            "function_responsibilities_preview": context["function_responsibilities"][:300],
        })
    print(json.dumps({"total": len(tasks), "tasks": rows}, indent=2, ensure_ascii=False))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    provider, model = resolve_judge_provider_model(args.judge_provider, args.judge_model)
    output_root = args.output_root.resolve()
    tasks = discover_tasks(language=args.language, project=args.project, task=args.task)
    if args.limit:
        tasks = tasks[: args.limit]
    failures = 0
    max_workers = max(1, args.max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_single_task, task, output_root=output_root, provider=provider, model=model, resume=args.resume): task
            for task in tasks
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                failures += 1
    tasks_all, completed, missing, _, _ = collect_results(output_root, language=args.language, project=args.project, task=args.task)
    if failures or missing:
        remove_existing_aggregate_outputs(output_root, language=args.language, project=args.project, task=args.task)
        write_incomplete_run_report(output_root, tasks=tasks_all, results=completed, failed_tasks=missing, judge_model=model, language=args.language, project=args.project, task=args.task)
        return 1
    aggregate(output_root, language=args.language, project=args.project, task=args.task, judge_model=model)
    incomplete_report = output_root / "incomplete_run.json"
    if incomplete_report.exists():
        incomplete_report.unlink()
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    output_root = args.output_root.resolve()
    tasks, completed, missing, _, _ = collect_results(output_root, language=args.language, project=args.project, task=args.task)
    if missing:
        remove_existing_aggregate_outputs(output_root, language=args.language, project=args.project, task=args.task)
        report_path = write_incomplete_run_report(output_root, tasks=tasks, results=completed, failed_tasks=missing, judge_model=args.judge_model or DEFAULT_JUDGE_MODEL_LABEL, language=args.language, project=args.project, task=args.task)
        print(json.dumps({"status": "incomplete", "message": "Aggregation aborted because the target scope is incomplete.", "incomplete_run_report": str(report_path), "completed": len(completed), "total_expected": len(tasks)}, indent=2, ensure_ascii=False))
        return 1
    summary = aggregate(output_root, language=args.language, project=args.project, task=args.task, judge_model=args.judge_model or DEFAULT_JUDGE_MODEL_LABEL)
    incomplete_report = output_root / "incomplete_run.json"
    if incomplete_report.exists():
        incomplete_report.unlink()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run L2 prompt scoring for file-level multi-function completion.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_filters(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("--language", default=None)
        cmd.add_argument("--project", default=None)
        cmd.add_argument("--task", default=None)
        cmd.add_argument("--limit", type=int, default=None)

    discover_parser = subparsers.add_parser("discover", help="Discover L2 tasks and preview prompt sections.")
    add_filters(discover_parser)
    discover_parser.set_defaults(func=_cmd_discover)

    run_parser = subparsers.add_parser("run", help="Run L2 prompt scoring.")
    add_filters(run_parser)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--judge-provider", choices=["openai", "anthropic"], default=None)
    run_parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL_LABEL)
    run_parser.add_argument("--max-workers", type=int, default=4)
    run_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run_parser.set_defaults(func=_cmd_run)

    aggregate_parser = subparsers.add_parser("aggregate", help="Aggregate existing L2 prompt score results.")
    add_filters(aggregate_parser)
    aggregate_parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL_LABEL)
    aggregate_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    aggregate_parser.set_defaults(func=_cmd_aggregate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
