#!/usr/bin/env python3
"""Batch-generate L3 function bodies by sending task prompts directly to an LLM API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"

SYSTEM_PROMPT = (
    "You are an expert programmer. Complete the body of the function described in the prompt. "
    "Return ONLY the function body code. "
    "Do NOT include the function signature. "
    "Do NOT wrap the code in markdown formatting."
)


@dataclass(slots=True)
class ModelResult:
    completion: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-generate PolyCodeEval L3 outputs via plain LLM API")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--task", help="Single L3 task directory")
    scope.add_argument("--project", help="Project directory")
    scope.add_argument("--language", choices=["python", "cpp", "java", "javascript", "go"])
    scope.add_argument("--all", action="store_true", dest="all_", help="All L3 tasks")

    parser.add_argument("--provider", choices=["openai", "anthropic"], default="openai")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--output-dir", required=True, help="Run output directory")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent generation workers")
    parser.add_argument("--limit", type=int, help="Limit discovered tasks")
    parser.add_argument("--resume", action="store_true", help="Skip tasks with existing output files")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=300.0, help="API timeout in seconds")
    parser.add_argument("--max-retries", type=int, default=4, help="Retry count for transient failures")
    parser.add_argument("--retry-base-delay", type=float, default=2.0, help="Base retry delay in seconds")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL; defaults to OPENAI_BASE_URL")
    return parser.parse_args()


def _is_l3_task_dir(task_path: Path) -> bool:
    return task_path.is_dir() and task_path.name.startswith("L3_") and (task_path / "task.json").is_file()


def _discover_projects(language: str | None) -> list[Path]:
    roots = [DATASETS_ROOT / language] if language else [p for p in DATASETS_ROOT.iterdir() if p.is_dir()]
    projects: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for project_dir in sorted(root.iterdir()):
            if (project_dir / "tasks").is_dir():
                projects.append(project_dir)
    return projects


def discover_tasks(
    *,
    task: str | None = None,
    project: str | None = None,
    language: str | None = None,
    all_: bool = False,
) -> list[Path]:
    if task:
        task_dir = Path(task)
        if not task_dir.is_absolute():
            task_dir = REPO_ROOT / task_dir
        if not (task_dir / "task.json").is_file():
            raise FileNotFoundError(f"not a valid task directory: {task_dir}")
        return [task_dir]

    if project:
        project_dir = Path(project)
        if not project_dir.is_absolute():
            project_dir = REPO_ROOT / project_dir
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            raise FileNotFoundError(f"no tasks/ directory in {project_dir}")
        return sorted(d for d in tasks_dir.iterdir() if _is_l3_task_dir(d))

    if not all_ and language is None:
        raise ValueError("specify --task, --project, --language, or --all")

    task_dirs: list[Path] = []
    for project_dir in _discover_projects(language):
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            continue
        for task_dir in sorted(tasks_dir.iterdir()):
            if _is_l3_task_dir(task_dir):
                task_dirs.append(task_dir)
    return task_dirs


def _task_id(task_dir: Path) -> str:
    return f"{task_dir.parents[2].name}/{task_dir.parents[1].name}/{task_dir.name}"


def _output_file(outputs_dir: Path, task_dir: Path) -> Path:
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    task_name = task_dir.name
    return outputs_dir / "generated_code" / language / project / f"{task_name}.txt"


def _failure_file(outputs_dir: Path) -> Path:
    return outputs_dir / "failures.json"


def _summary_file(outputs_dir: Path) -> Path:
    return outputs_dir / "summary.json"


def _load_json_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_previous_task_usages(path: Path) -> dict[str, dict[str, object]]:
    data = _load_json_dict(path)
    per_task = data.get("per_task_token_usage")
    if not isinstance(per_task, dict):
        return {}
    return {k: v for k, v in per_task.items() if isinstance(k, str) and isinstance(v, dict)}


def _load_failures(path: Path) -> dict[str, dict]:
    return _load_json_dict(path)


def _indent_width(line: str, tabstop: int = 4) -> int:
    width = 0
    for ch in line:
        if ch == " ":
            width += 1
        elif ch == "\t":
            width += tabstop
        else:
            break
    return width


def _rebase_body_to_storage_indent(body: str, *, storage_base_width: int = 4) -> str:
    lines = body.strip("\n").splitlines()
    if not lines:
        return ""

    first_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_idx is None:
        return ""

    first_width = _indent_width(lines[first_idx])
    normalized: list[str] = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        width = _indent_width(line)
        relative_width = width - first_width
        stored_width = storage_base_width + relative_width
        if stored_width < 0:
            raise RuntimeError(
                "Indentation rebase produced a negative stored width; "
                "model output relative indentation is invalid."
            )
        normalized.append((" " * stored_width) + line.lstrip(" \t"))
    return "\n".join(normalized).rstrip()


def _normalize_python_body(body: str) -> str:
    return _rebase_body_to_storage_indent(textwrap.dedent(body).strip("\n"))


def _normalize_non_python_body(body: str) -> str:
    return _rebase_body_to_storage_indent(body)


def _fallback_clean_completion(raw_completion: str, lang: str) -> str:
    cleaned = raw_completion.strip()
    if not cleaned:
        return ""

    fenced = re.match(r"^```[\w+-]*\n([\s\S]*?)\n```$", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()

    if lang == "python":
        match = re.search(r"^\s*(?:async\s+def|def)\s+\w+\s*\(.*?\)\s*:\s*\n([\s\S]*)$", cleaned, re.MULTILINE)
        if match:
            return textwrap.dedent(match.group(1)).strip()
        return cleaned

    stripped = cleaned.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped[1:-1].strip()
    return stripped


def _normalize_function_body(task_dir: Path, body: str) -> str:
    if not body:
        return ""

    language = task_dir.parents[2].name
    if language == "python":
        return _normalize_python_body(body)
    return _normalize_non_python_body(body)


def _should_retry(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    text = str(exc).lower()
    retry_markers = (
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "bad gateway",
        "rate limit",
        "server error",
    )
    return any(marker in text for marker in retry_markers)


def _call_openai(prompt: str, *, model: str, timeout: float, temperature: float, max_tokens: int, base_url: str | None) -> ModelResult:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        **({"base_url": base_url} if base_url else {}),
        timeout=timeout,
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    usage = resp.usage
    return ModelResult(
        completion=resp.choices[0].message.content or "",
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
    )


def _call_anthropic(prompt: str, *, model: str, timeout: float, temperature: float, max_tokens: int) -> ModelResult:
    import anthropic

    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        timeout=timeout,
    )
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    usage = getattr(resp, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    return ModelResult(
        completion=resp.content[0].text if resp.content else "",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def _generate_one(
    task_dir: Path,
    *,
    provider: str,
    model: str,
    output_file: Path,
    timeout: float,
    temperature: float,
    max_tokens: int,
    max_retries: int,
    retry_base_delay: float,
    base_url: str | None,
) -> ModelResult:
    prompt = (task_dir / "prompt.md").read_text(encoding="utf-8")
    language = task_dir.parents[2].name

    for attempt in range(max_retries + 1):
        try:
            if provider == "anthropic":
                result = _call_anthropic(
                    prompt,
                    model=model,
                    timeout=timeout,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                result = _call_openai(
                    prompt,
                    model=model,
                    timeout=timeout,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    base_url=base_url,
                )
            cleaned = _normalize_function_body(
                task_dir,
                _fallback_clean_completion(result.completion, language),
            )
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(cleaned, encoding="utf-8")
            result.completion = cleaned
            return result
        except Exception as exc:
            if attempt < max_retries and _should_retry(exc):
                time.sleep(retry_base_delay * (2 ** attempt))
                continue
            raise RuntimeError(str(exc)) from exc


def main() -> int:
    args = _parse_args()
    outputs_dir = Path(args.output_dir).resolve()
    outputs_dir.mkdir(parents=True, exist_ok=True)

    task_dirs = discover_tasks(
        task=args.task,
        project=args.project,
        language=args.language,
        all_=args.all_,
    )
    if args.limit:
        task_dirs = task_dirs[: args.limit]

    solver_spec = f"{args.provider}/{args.model}"
    failures_path = _failure_file(outputs_dir)
    summary_path = _summary_file(outputs_dir)
    failures = _load_failures(failures_path)
    previous_task_usages = _load_previous_task_usages(summary_path) if args.resume else {}
    failures_lock = threading.Lock()
    progress_lock = threading.Lock()

    total = len(task_dirs)
    generated = 0
    skipped = 0
    failed = 0
    start_time = time.time()
    usage_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    task_usages: dict[str, dict[str, object]] = {}

    print("=" * 60)
    print("Direct API Batch Generation")
    print("=" * 60)
    print(f"Solver:  {solver_spec}")
    print(f"Tasks:   {total}")
    print(f"Workers: {args.workers}")
    print(f"Resume:  {args.resume}")
    print(f"Output:  {outputs_dir}")
    print()

    def _progress(done: int) -> str:
        elapsed = time.time() - start_time
        pct = done / total * 100 if total else 0
        bar_len = 30
        filled = int(bar_len * done / total) if total else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        eta_str = f"{int(eta // 60)}m{int(eta % 60):02d}s" if eta < 3600 else f"{eta / 3600:.1f}h"
        return (
            f"\r  [{bar}] {done}/{total} ({pct:.0f}%) "
            f"| ok:{generated} skip:{skipped} fail:{failed} "
            f"| {elapsed:.0f}s elapsed, ETA {eta_str}  "
        )

    def _record_usage(task_id: str, usage: dict[str, object]) -> None:
        task_usages[task_id] = usage
        usage_totals["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        usage_totals["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        usage_totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)

    def _run_one(task_dir: Path) -> tuple[str, str, dict[str, object] | None, str | None]:
        task_id = _task_id(task_dir)
        output_file = _output_file(outputs_dir, task_dir)
        if args.resume and output_file.exists():
            return task_id, "skipped", previous_task_usages.get(task_id), None

        result = _generate_one(
            task_dir,
            provider=args.provider,
            model=args.model,
            output_file=output_file,
            timeout=args.timeout,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            max_retries=args.max_retries,
            retry_base_delay=args.retry_base_delay,
            base_url=args.base_url or os.environ.get("OPENAI_BASE_URL"),
        )
        usage = {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
        }
        return task_id, "generated", usage, None

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_run_one, task_dir): task_dir for task_dir in task_dirs}
        for future in as_completed(futures):
            task_dir = futures[future]
            task_id = _task_id(task_dir)
            status = "failed"
            usage: dict[str, object] | None = None
            error: str | None = "Unknown error"
            try:
                task_id, status, usage, error = future.result()
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"

            with progress_lock:
                done += 1
                if status == "generated":
                    generated += 1
                    _record_usage(task_id, usage or {})
                    with failures_lock:
                        failures.pop(task_id, None)
                elif status == "skipped":
                    skipped += 1
                    if usage:
                        _record_usage(task_id, usage)
                else:
                    failed += 1
                    with failures_lock:
                        failures[task_id] = {
                            "task": task_id,
                            "error": error,
                            "timestamp": datetime.now().isoformat(),
                        }
                _save_json(failures_path, failures)
                sys.stderr.write(_progress(done))
                sys.stderr.flush()

    sys.stderr.write("\n")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "solver": solver_spec,
        "provider": args.provider,
        "model": args.model,
        "workers": args.workers,
        "resume": args.resume,
        "total_tasks": total,
        "generated": generated,
        "skipped": skipped,
        "failed": failed,
        "generated_code_dir": str((outputs_dir / "generated_code").resolve()),
        "failures_file": str(failures_path.resolve()),
        "token_usage_accounted_tasks": len(task_usages),
        "token_usage": usage_totals,
        "per_task_token_usage": task_usages,
    }
    _save_json(summary_path, summary)

    print(f"Generated: {generated}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")
    print(f"Outputs:   {outputs_dir / 'generated_code'}")
    print(f"Summary:   {summary_path}")
    print(f"Failures:  {failures_path}")
    print()
    print("Evaluate with:")
    print(
        f"python3 {REPO_ROOT / 'scripts' / 'run_l3_eval.py'} "
        f"--all --solver precomputed:{outputs_dir / 'generated_code'} --workers 16 --tests both"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
