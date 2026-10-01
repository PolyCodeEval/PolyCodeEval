#!/usr/bin/env python3
"""Run L3 function-description-only scoring against full function implementations."""

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

from l0_evaluator.scoring.judge_clients import JudgeError, extract_json, resolve_judge_provider_model, run_judge
from l3_evaluator.workspace import _resolve_file

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS_ROOT = REPO_ROOT / "datasets"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "finalresults" / "l3_prompt_score" / "gpt5.4_judge"
REVIEW_TYPE = "l3_prompt_score"
REVIEW_SCHEMA_VERSION = "l3_prompt_score_v3"
DEFAULT_JUDGE_MODEL_LABEL = "gpt-5.4"
MISSING_DESCRIPTION_SCORE = 1.0
_JSONL_LOCK = Lock()


class ReviewValidationError(Exception):
    """Raised when a review payload is invalid."""


class FunctionExtractionError(Exception):
    """Raised when full function extraction fails."""


@dataclass(frozen=True)
class TaskInfo:
    language: str
    project: str
    task_name: str
    task_dir: Path
    task_json_path: Path
    prompt_path: Path
    desc_path: Path
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
    for task_json_path in sorted(DATASETS_ROOT.glob("*/*/tasks/L3_*/task.json")):
        task_dir = task_json_path.parent
        project_root = task_dir.parents[1]
        current = TaskInfo(
            language=project_root.parent.name,
            project=project_root.name,
            task_name=task_dir.name,
            task_dir=task_dir,
            task_json_path=task_json_path,
            prompt_path=task_dir / "prompt.md",
            desc_path=task_dir / "desc.txt",
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


def _extract_json_blob(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        stripped = next((part for part in parts if "{" in part and "}" in part), stripped)
        stripped = stripped.replace("json", "", 1).strip()
    return extract_json(stripped)


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


def _extract_named_section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^# {re.escape(heading)}\s*$|^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^# |^## ", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    return markdown[start:end].strip()


def _find_symbol_start(prefix: str, symbol: str) -> int | None:
    blocked_prefix_tokens = ("return ", "if ", "for ", "while ", "switch ", "case ", "catch ", "throw ", "new ")
    patterns = [
        rf"(?:^|\n)\s*{re.escape(symbol)}\s*<",
        rf"(?:^|\n)\s*{re.escape(symbol)}\s*\(",
        rf"(?:^|\n)\s*(?:public|private|protected|static|async|virtual|inline|constexpr|export\s+|default\s+)*\s*{re.escape(symbol)}\s*\(",
        rf"(?:^|\n)\s*(?:[\w.:<>,~*&?\[\]\s]+)\b{re.escape(symbol)}\s*\(",
        rf"(?:^|\n)\s*(?:def|async def|function)\s+{re.escape(symbol)}\b",
        rf"(?:^|\n)\s*(?:class)\s+{re.escape(symbol)}\b",
    ]
    best: int | None = None
    for pattern in patterns:
        for match in re.finditer(pattern, prefix, re.MULTILINE):
            candidate = match.start()
            line_start = prefix.rfind("\n", 0, candidate)
            line_start = 0 if line_start < 0 else line_start + 1
            line_end = prefix.find("\n", candidate)
            line_end = len(prefix) if line_end < 0 else line_end
            line = prefix[line_start:line_end].strip()
            if any(line.startswith(token) for token in blocked_prefix_tokens):
                continue
            if best is None or candidate > best:
                best = candidate
    if best is None:
        return None
    return best + (1 if prefix[best:best + 1] == "\n" else 0)


def _find_nearest_brace(source: str, body_start: int, body_end: int) -> int:
    if source[body_start:body_start + 1] == "{":
        return body_start
    window_start = max(0, body_start - 256)
    window_end = min(len(source), body_end + 256)
    for idx in range(body_start, window_end):
        if source[idx] == "{":
            return idx
    for idx in range(body_start - 1, window_start - 1, -1):
        if source[idx] == "{":
            return idx
    raise FunctionExtractionError("could not locate function body opening brace near stub range")


def _byte_to_char_index(source_bytes: bytes, byte_offset: int) -> int:
    if byte_offset <= 0:
        return 0
    if byte_offset >= len(source_bytes):
        return len(source_bytes.decode("utf-8", errors="replace"))
    return len(source_bytes[:byte_offset].decode("utf-8", errors="replace"))


def _find_body_bounds(source: str, body_start: int, body_end: int, lang: str, symbol: str) -> tuple[int, int]:
    if lang == "python":
        line_start = source.rfind("\n", 0, body_start)
        line_start = 0 if line_start < 0 else line_start + 1
        base_indent = len(source[line_start:body_start]) - len(source[line_start:body_start].lstrip(" \t"))
        scan = line_start
        start = 0
        while scan > 0:
            prev_line_end = scan - 1
            prev_line_start = source.rfind("\n", 0, prev_line_end)
            prev_line_start = 0 if prev_line_start < 0 else prev_line_start + 1
            line = source[prev_line_start:prev_line_end + 1]
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" \t"))
            if stripped.startswith(("def ", "async def ", "class ")) and indent <= base_indent:
                start = prev_line_start
                break
            scan = prev_line_start
        else:
            raise FunctionExtractionError("could not find python declaration line")
        end = len(source)
        for match in re.finditer(r"\n", source[body_end:]):
            line_start_2 = body_end + match.start() + 1
            line_end_2 = source.find("\n", line_start_2)
            line_end_2 = len(source) if line_end_2 == -1 else line_end_2
            line = source[line_start_2:line_end_2]
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip(" \t"))
            if indent <= base_indent and not stripped.startswith(("@", ")")):
                end = line_start_2
                break
        return start, end

    brace_start = _find_nearest_brace(source, body_start, body_end)
    body_close = max(brace_start + 1, min(len(source), body_end))
    search_start = max(0, brace_start - 6000)
    prefix = source[search_start:brace_start]
    symbol_start = _find_symbol_start(prefix, symbol)
    if symbol_start is not None:
        start = search_start + symbol_start
        while start > 0:
            prev_end = start - 1
            prev_start = source.rfind("\n", 0, prev_end)
            prev_start = 0 if prev_start < 0 else prev_start + 1
            line = source[prev_start:prev_end + 1]
            if line.lstrip().startswith(("@", "[[")) or line.strip().startswith(("template<", "/**", "/*", "*", "//")):
                start = prev_start
                continue
            break
        return start, body_close

    start = source.rfind("\n", 0, brace_start)
    start = 0 if start < 0 else start + 1
    return start, body_close


def extract_full_function_for_symbol(source: str, *, body_start: int, body_end: int, lang: str, symbol: str) -> tuple[str, int, int]:
    start, end = _find_body_bounds(source, body_start, body_end, lang, symbol)
    snippet = source[start:end].strip("\n")
    if not snippet:
        raise FunctionExtractionError("extracted function is empty")
    return snippet, start, end


def build_task_context(task: TaskInfo) -> dict[str, Any]:
    task_json = _load_json(task.task_json_path)
    run_config = _load_json(task.run_config_path)
    stub_info = task_json.get("stub_info") or {}
    src_dir = (task.task_dir / run_config["src_dir"]).resolve()
    resolved_rel = _resolve_file(src_dir, stub_info["file"])
    source_path = (src_dir / resolved_rel).resolve()
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8", errors="replace")
    body_start = _byte_to_char_index(source_bytes, int(stub_info["body_start_byte"]))
    body_end = _byte_to_char_index(source_bytes, int(stub_info["body_end_byte"]))
    function_source, full_start, full_end = extract_full_function_for_symbol(
        source_text,
        body_start=body_start,
        body_end=body_end,
        lang=stub_info.get("lang", ""),
        symbol=stub_info.get("func_name", ""),
    )
    prompt_markdown = task.prompt_path.read_text(encoding="utf-8")
    function_description = _extract_named_section(prompt_markdown, "Function Description")
    pre_start = max(0, full_start - 600)
    post_end = min(len(source_text), full_end + 600)
    return {
        "task_json": task_json,
        "run_config": run_config,
        "stub_info": stub_info,
        "source_file_path": str(source_path),
        "source_file_rel": resolved_rel,
        "function_source": function_source,
        "function_extraction_status": "ok",
        "function_description": function_description,
        "description_present": bool(function_description.strip()),
        "surrounding_source": source_text[pre_start:post_end],
    }


def build_judge_prompt(task: TaskInfo, context: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are a senior code review judge. "
        "Your task is to evaluate the quality of an L3 function description against the real full function implementation. "
        "Use the full function implementation as the primary source of truth. "
        "Focus on only two things: whether the abstract functional description matches the implementation, "
        "and whether the description is complete enough to support implementing the function. "
        "Be slightly lenient. Return valid JSON only."
    )
    user = f"""Evaluate this L3 function description.

Task ID: {task.task_id}
Language: {task.language}
Project: {task.project}
Target: {context["task_json"].get("target")}
Source file: {context["source_file_rel"]}

Important rule:
- The FULL FUNCTION IMPLEMENTATION below is the main source of truth.
- If the description captures the core task and only misses secondary details, you may still give a relatively high score.
- If the description claims behavior that is not implemented, lower the score.

Function Description:
```markdown
{context["function_description"]}
```

FULL FUNCTION IMPLEMENTATION:
```{context["stub_info"].get("lang", "text")}
{context["function_source"]}
```

Nearby source context:
```{context["stub_info"].get("lang", "text")}
{context["surrounding_source"]}
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
- `score` must be from 1.0 to 5.0, with at most one decimal place.
- Higher score means the function description both matches the implementation and describes the function sufficiently completely.
- `complete_enough` should be true only if the function description is sufficient for a model to implement the function without missing important behavior.
"""
    return system, user


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
        "target_symbol": context["task_json"].get("target"),
        "function_extraction_status": context["function_extraction_status"],
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": judge_model,
        "description_present": context["description_present"],
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
        "target_symbol": context["task_json"].get("target"),
        "function_extraction_status": context["function_extraction_status"],
        "review_type": REVIEW_TYPE,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "judge_model": judge_model,
        "description_present": False,
        "score": MISSING_DESCRIPTION_SCORE,
        "reason": "The prompt is missing a Function Description section, so there is no function-level abstract description to evaluate against the implementation.",
        "missing_functionality": ["Function Description section is missing."],
        "incorrect_or_misleading_points": [],
        "complete_enough": False,
        "raw_response_file": None,
    }


def _score_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [row["score"] for row in rows]
    complete = [row for row in rows if row.get("complete_enough")]
    missing_desc = [row for row in rows if not row.get("description_present", True)]
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
        (output_root / language_name / project_name / f"L3_{project_name}.json").unlink(missing_ok=True)


def aggregate(output_root: Path, *, language: str | None = None, project: str | None = None, task: str | None = None, judge_model: str = DEFAULT_JUDGE_MODEL_LABEL) -> dict[str, Any]:
    tasks, results, failed_tasks, by_project_rows, by_language_rows = collect_results(
        output_root,
        language=language,
        project=project,
        task=task,
    )
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
                    "description_present": row.get("description_present", True),
                }
                for row in sorted(rows, key=lambda entry: entry["task"])
            ],
            "failed_tasks": [],
        }
        _write_json(output_root / language_name / project_name / f"L3_{project_name}.json", project_summary)
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
        if not context["description_present"]:
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
    except (FunctionExtractionError, JudgeError, ReviewValidationError, KeyError, FileNotFoundError, OSError, ValueError) as exc:
        _record_run(output_root=output_root, task=task, status="failed", started_at=started_at, completed_at=_utc_now(), raw_response_path=str(raw_path) if raw_path.exists() else None, json_result_path=None, parse_ok=False, error=str(exc), judge_model=model)
        raise


def _cmd_discover(args: argparse.Namespace) -> int:
    tasks = discover_tasks(language=args.language, project=args.project, task=args.task)
    rows = []
    for task in tasks[: args.limit or None]:
        context = build_task_context(task)
        rows.append({
            "task": task.task_id,
            "description_present": context["description_present"],
            "function_description_preview": context["function_description"][:400],
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
            executor.submit(
                _run_single_task,
                task,
                output_root=output_root,
                provider=provider,
                model=model,
                resume=args.resume,
            ): task
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
    parser = argparse.ArgumentParser(description="Run L3 function-description-only scoring.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_filters(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("--language", default=None)
        cmd.add_argument("--project", default=None)
        cmd.add_argument("--task", default=None)
        cmd.add_argument("--limit", type=int, default=None)

    discover_parser = subparsers.add_parser("discover", help="Discover L3 tasks and preview Function Description extraction.")
    add_filters(discover_parser)
    discover_parser.set_defaults(func=_cmd_discover)

    run_parser = subparsers.add_parser("run", help="Run L3 function-description scoring.")
    add_filters(run_parser)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--judge-provider", choices=["openai", "anthropic"], default=None)
    run_parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL_LABEL)
    run_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run_parser.add_argument("--max-workers", type=int, default=4)
    run_parser.set_defaults(func=_cmd_run)

    aggregate_parser = subparsers.add_parser("aggregate", help="Aggregate existing L3 description score results.")
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
