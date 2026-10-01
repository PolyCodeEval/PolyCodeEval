#!/usr/bin/env python3
"""Batch-generate L2 full-file outputs by calling an LLM directly."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


class DirectL2Error(RuntimeError):
    pass


def _load_repo_env() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


_load_repo_env()


def _parse_model_spec(spec: str) -> tuple[str, str]:
    if "/" not in spec:
        raise ValueError(
            "Model spec must look like anthropic/<model> or openai/<model>"
        )
    provider, model_id = spec.split("/", 1)
    if provider not in {"anthropic", "openai"}:
        raise ValueError(f"Unsupported provider: {provider}")
    if not model_id.strip():
        raise ValueError("Model id must not be empty")
    return provider, model_id


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run direct LLM generation on L2 tasks")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--task", nargs="+", help="One or more task directories")
    scope.add_argument("--project", help="Project name (all L2 tasks in it)")
    scope.add_argument("--language", help="Language (all L2 tasks)")
    scope.add_argument("--all", action="store_true", dest="all_")
    parser.add_argument(
        "--model",
        required=True,
        help="LLM spec: anthropic/<model_id> or openai/<model_id>",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, help="Max tasks to process")
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout", type=float, default=300.0, help="Per-request timeout in seconds")
    return parser.parse_args()


def _is_l2_task_dir(p: Path) -> bool:
    return (
        p.is_dir()
        and p.name.startswith("L2_")
        and (p / "task.json").exists()
        and (p / "prompt.md").exists()
    )


def _discover_tasks(args) -> list[Path]:
    if args.task:
        result = []
        for t in args.task:
            task_dir = Path(t).resolve()
            if not _is_l2_task_dir(task_dir):
                sys.exit(f"Not a valid L2 task dir: {task_dir}")
            result.append(task_dir)
        return result

    tasks: list[Path] = []
    for lang_dir in sorted(DATASETS_ROOT.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue
        if args.language and lang_dir.name != args.language:
            continue
        for proj_dir in sorted(lang_dir.iterdir()):
            if not proj_dir.is_dir() or proj_dir.name == "README.md":
                continue
            if args.project and proj_dir.name != args.project:
                continue
            tasks_dir = proj_dir / "tasks"
            if not tasks_dir.is_dir():
                continue
            for task_dir in sorted(tasks_dir.iterdir()):
                if _is_l2_task_dir(task_dir):
                    tasks.append(task_dir)
    return tasks


def _task_id(task_dir: Path) -> str:
    return f"{task_dir.parents[2].name}/{task_dir.parents[1].name}/{task_dir.name}"


def _debug_dir(output_dir: Path, task_dir: Path) -> Path:
    return (
        output_dir / "debug" / task_dir.parents[2].name / task_dir.parents[1].name / task_dir.name
    )


def _output_file(output_dir: Path, task_dir: Path) -> Path:
    return (
        output_dir
        / "generated_outputs"
        / task_dir.parents[2].name
        / task_dir.parents[1].name
        / f"{task_dir.name}.txt"
    )


def _is_done(output_dir: Path, task_dir: Path) -> bool:
    return (_debug_dir(output_dir, task_dir) / "_done").exists()


def _resolve_file(src_dir: Path, rel_path: str) -> str:
    if (src_dir / rel_path).exists():
        return rel_path
    if rel_path.startswith("src/"):
        stripped = rel_path[len("src/"):]
        if (src_dir / stripped).exists():
            return stripped
    target = Path(rel_path)
    matches = list(src_dir.rglob(target.name))
    if not matches:
        return rel_path
    if len(matches) == 1:
        return str(matches[0].relative_to(src_dir))
    for m in matches:
        rel = str(m.relative_to(src_dir))
        if rel.endswith(rel_path) or rel.endswith(str(target)):
            return rel
    return str(matches[0].relative_to(src_dir))


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_skeleton(task_dir: Path, task_json: dict) -> tuple[str, str]:
    run_config = _load_json(task_dir / "run_config.json")
    src_dir = (task_dir / run_config["src_dir"]).resolve()
    target_rel = task_json["stub_info"]["file"]
    resolved_rel = _resolve_file(src_dir, target_rel)
    skeleton_candidates = [
        task_dir / "hollowed_files" / target_rel,
        task_dir / "hollowed_files" / resolved_rel,
    ]
    for candidate in skeleton_candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8"), resolved_rel
    raise FileNotFoundError(
        f"Missing skeleton for {task_dir.name}: expected one of "
        f"{skeleton_candidates[0]} or {skeleton_candidates[1]}"
    )


def _build_prompt(task_dir: Path) -> tuple[str, dict]:
    prompt_md = _load_text(task_dir / "prompt.md")
    task_json = _load_json(task_dir / "task.json")
    skeleton_text, resolved_rel = _load_skeleton(task_dir, task_json)
    lang = task_json["stub_info"].get("lang", "")

    prompt = "\n\n".join(
        [
            prompt_md.rstrip(),
            "# Target File Skeleton",
            f"```{lang}\n{skeleton_text.rstrip()}\n```",
            "# Output Contract",
            "Return only the complete file contents. Do not wrap the result in markdown fences.",
            f"Target file: {resolved_rel}",
        ]
    ).rstrip() + "\n"
    return prompt, task_json


def _extract_text_from_response(resp) -> str:
    text = getattr(resp, "output_text", None)
    if text:
        return text
    if hasattr(resp, "choices") and resp.choices:
        choice = resp.choices[0]
        message = getattr(choice, "message", None)
        if message is not None:
            content = getattr(message, "content", "")
            if isinstance(content, str):
                return content
    if hasattr(resp, "content"):
        chunks = []
        for item in resp.content:
            maybe_text = getattr(item, "text", None)
            if maybe_text:
                chunks.append(maybe_text)
        if chunks:
            return "\n".join(chunks)
    return str(resp)


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _extract_cost(resp: object, usage: object | None) -> float:
    for candidate in (getattr(resp, "cost_usd", None), getattr(resp, "total_cost_usd", None)):
        if candidate is not None:
            try:
                return float(candidate)
            except (TypeError, ValueError):
                continue
    if isinstance(usage, dict):
        for key in ("cost_usd", "total_cost_usd"):
            if key in usage:
                try:
                    return float(usage[key] or 0)
                except (TypeError, ValueError):
                    pass
    return 0.0


def _clean_file_content(text: str) -> str:
    stripped = text.strip()
    fence_pattern = re.compile(r"```(?:[\w+-]+)?\s*\n(.*?)\n```", re.DOTALL)
    matches = fence_pattern.findall(stripped)
    if matches:
        stripped = max(matches, key=len).strip()
    elif stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped.strip("`").strip()
    return stripped.rstrip() + "\n"


def _extract_usage(resp: object, provider: str, model: str) -> dict:
    usage = getattr(resp, "usage", None)
    model_usage = getattr(resp, "modelUsage", None)

    input_tokens = output_tokens = cache_read = cache_creation = 0

    if isinstance(model_usage, dict) and model_usage:
        model_data = model_usage.get(model) or next(iter(model_usage.values()))
        input_tokens = _as_int(model_data.get("inputTokens"))
        output_tokens = _as_int(model_data.get("outputTokens"))
        cache_read = _as_int(model_data.get("cacheReadInputTokens"))
        cache_creation = _as_int(model_data.get("cacheCreationInputTokens"))
    elif isinstance(usage, dict) and usage:
        input_tokens = _as_int(
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or usage.get("inputTokens")
        )
        output_tokens = _as_int(
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or usage.get("outputTokens")
        )
        cache_read = _as_int(
            usage.get("cache_read_input_tokens")
            or usage.get("cacheReadInputTokens")
        )
        cache_creation = _as_int(
            usage.get("cache_creation_input_tokens")
            or usage.get("cacheCreationInputTokens")
        )
        if not input_tokens and not output_tokens:
            input_tokens = _as_int(usage.get("total_tokens"))
    elif usage is not None:
        input_tokens = _as_int(
            getattr(usage, "input_tokens", None)
            or getattr(usage, "prompt_tokens", None)
            or getattr(usage, "inputTokens", None)
        )
        output_tokens = _as_int(
            getattr(usage, "output_tokens", None)
            or getattr(usage, "completion_tokens", None)
            or getattr(usage, "outputTokens", None)
        )
        cache_read = _as_int(
            getattr(usage, "cache_read_input_tokens", None)
            or getattr(usage, "cacheReadInputTokens", None)
        )
        cache_creation = _as_int(
            getattr(usage, "cache_creation_input_tokens", None)
            or getattr(usage, "cacheCreationInputTokens", None)
        )

    total_tokens = input_tokens + output_tokens
    return {
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "total_tokens": total_tokens,
        "cost_usd": _extract_cost(resp, usage),
    }


def _build_client(provider: str, timeout: float):
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - env dependent
            raise DirectL2Error(
                "Failed to import anthropic for anthropic/<model>: "
                f"{exc.__class__.__name__}: {exc}"
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        kwargs = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        kwargs["timeout"] = timeout
        return anthropic.Anthropic(**kwargs)

    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - env dependent
            raise DirectL2Error(
                "Failed to import openai for openai/<model>: "
                f"{exc.__class__.__name__}: {exc}"
            ) from exc

        kwargs = {}
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        kwargs["timeout"] = timeout
        return OpenAI(**kwargs)

    raise ValueError(f"Unsupported provider: {provider}")


def _call_model(
    provider: str,
    model: str,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    timeout: float,
):
    client = _build_client(provider, timeout)
    if provider == "anthropic":
        return client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=(
                "You are a senior software engineer. "
                "Generate the complete contents of the target file described by the prompt. "
                "Return only the file contents, with no explanation and no markdown fences."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
    try:
        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer. "
                        "Generate the complete contents of the target file described by the prompt. "
                        "Return only the file contents, with no explanation and no markdown fences."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except TypeError:
        return client.chat.completions.create(
            model=model,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer. "
                        "Generate the complete contents of the target file described by the prompt. "
                        "Return only the file contents, with no explanation and no markdown fences."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    args = _parse_args()
    provider, model = _parse_model_spec(args.model)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    tasks = _discover_tasks(args)
    if args.resume:
        tasks = [t for t in tasks if not _is_done(args.output_dir, t)]
    if args.limit:
        tasks = tasks[: args.limit]

    print("=" * 60)
    print("Direct LLM L2 Batch Generation")
    print("=" * 60)
    print(f"Provider:  {provider}")
    print(f"Model:     {model}")
    print(f"Tasks:     {len(tasks)}")
    print(f"Resume:    {args.resume}")
    print(f"Output:    {args.output_dir}")
    print()

    usage_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0,
    }
    task_usages: dict[str, dict] = {}
    failures: dict[str, str] = {}
    generated = 0
    start_time = time.time()

    for i, task_dir in enumerate(tasks, 1):
        tid = _task_id(task_dir)
        print(f"[{i}/{len(tasks)}] {tid} ...", end=" ", flush=True)

        try:
            prompt, task_json = _build_prompt(task_dir)
            start = time.time()
            resp = _call_model(
                provider,
                model,
                prompt,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                timeout=args.timeout,
            )
            duration = time.time() - start
            raw_text = _extract_text_from_response(resp)
            file_content = _clean_file_content(raw_text)
            usage = _extract_usage(resp, provider, model)
            usage["duration_s"] = round(duration, 1)
            usage["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            out_file = _output_file(args.output_dir, task_dir)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(file_content, encoding="utf-8")

            debug_dir = _debug_dir(args.output_dir, task_dir)
            debug_dir.mkdir(parents=True, exist_ok=True)
            _save_json(debug_dir / "usage.json", usage)
            (debug_dir / "raw_response.txt").write_text(raw_text, encoding="utf-8")
            (debug_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
            _save_json(debug_dir / "task.json", task_json)
            (debug_dir / "_done").touch()

            task_usages[tid] = usage
            for key in usage_totals:
                usage_totals[key] += usage.get(key, 0)

            generated += 1
            print(
                f"ok ({usage.get('duration_s', 0):.0f}s, "
                f"in={usage.get('input_tokens', 0)}, out={usage.get('output_tokens', 0)})"
            )
        except Exception as exc:  # noqa: BLE001
            failures[tid] = str(exc)
            print(f"FAIL: {str(exc)[:120]}")

    total_elapsed = time.time() - start_time

    print()
    print("=" * 60)
    print(f"Generated: {generated}")
    print(f"Failed:    {len(failures)}")
    print(f"Time:      {total_elapsed:.0f}s")
    print(
        f"Tokens:    in={usage_totals['input_tokens']} "
        f"out={usage_totals['output_tokens']} total={usage_totals['total_tokens']}"
    )
    if usage_totals["cost_usd"]:
        print(f"Cost:      ${usage_totals['cost_usd']:.4f}")

    summary = {
        "solver": f"direct/{provider}/{model}",
        "provider": provider,
        "model": model,
        "level": "L2",
        "generated": generated,
        "failed": len(failures),
        "skipped": 0,
        "total_elapsed_s": round(total_elapsed, 1),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "token_usage": usage_totals,
        "per_task": task_usages,
    }
    _save_json(args.output_dir / "summary.json", summary)
    if failures:
        _save_json(args.output_dir / "failures.json", failures)

    print(f"Summary:   {args.output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
