"""Bridge PolyCodeEval L3 tasks to the upstream RepoCoder pipeline."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

_THIS_FILE = Path(__file__).resolve()
_SCRIPTS_DIR = _THIS_FILE.parents[2]
_REPO_ROOT = _THIS_FILE.parents[3]
_REPOCODER_ROOT = _REPO_ROOT.parent / "L3works" / "CodeT" / "RepoCoder"
_DEBUG_ROOT = _REPO_ROOT / "results" / "l3_repocoder_debug"
_WORKSPACE_ROOT = _REPO_ROOT / "output" / "repocoder_workspaces"
_API_TIMEOUT_SECONDS = 300


class RepoCoderError(RuntimeError):
    """Raised when the upstream RepoCoder pipeline cannot produce a function body."""


@dataclass(slots=True)
class _TaskContext:
    task_dir: Path
    task_json: dict
    prompt: str
    language: str
    project: str
    task_name: str
    stub_info: dict
    hollowed_text: str
    file_relpath: str
    left_context: str
    right_context: str
    debug_dir: Path
    src_dir: Path


@dataclass(slots=True)
class _ModelCallResult:
    completion: str
    usage: dict[str, int]


def generate_function_body(task_dir: Path, model_spec: str) -> str:
    provider, model_name = _parse_model_spec(model_spec)
    ctx = _load_task_context(task_dir)
    modules = _load_repocoder_modules()
    workspace_dir = _build_temp_workspace(ctx)
    try:
        round1 = _run_round(
            ctx,
            modules,
            provider=provider,
            model_name=model_name,
            round_idx=1,
            draft_prefix="",
            workspace_dir=workspace_dir,
        )
        round1_completion = round1["cleaned_completion"]

        round2 = None
        if round1_completion:
            round2 = _run_round(
                ctx,
                modules,
                provider=provider,
                model_name=model_name,
                round_idx=2,
                draft_prefix=round1_completion,
                workspace_dir=workspace_dir,
            )

        final_completion = ""
        if round2 and round2["cleaned_completion"]:
            final_completion = round2["cleaned_completion"]
        else:
            final_completion = round1_completion

        if not final_completion:
            raise RepoCoderError("RepoCoder failed to produce a valid function body.")
        return final_completion
    finally:
        shutil.rmtree(workspace_dir, ignore_errors=True)


def _parse_model_spec(model_spec: str) -> tuple[str, str]:
    if model_spec.startswith("repocoder-openai/"):
        return "openai", model_spec.removeprefix("repocoder-openai/")
    if model_spec.startswith("repocoder-anthropic/"):
        return "anthropic", model_spec.removeprefix("repocoder-anthropic/")
    raise RepoCoderError(
        f"Unsupported RepoCoder solver spec: {model_spec!r}. "
        "Use repocoder-openai/<model> or repocoder-anthropic/<model>."
    )


def _load_task_context(task_dir: Path) -> _TaskContext:
    prompt = (task_dir / "prompt.md").read_text(encoding="utf-8")
    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    run_config = json.loads((task_dir / "run_config.json").read_text(encoding="utf-8"))
    stub_info = task_json["stub_info"]
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    task_name = task_dir.name
    file_relpath = stub_info["file"]
    hollowed_text = (task_dir / "hollowed_files" / file_relpath).read_text(encoding="utf-8")

    body_start = stub_info["body_start_byte"]
    body_end = stub_info["body_end_byte"]
    left_context = hollowed_text.encode("utf-8")[:body_start].decode("utf-8", errors="replace")
    right_context = hollowed_text.encode("utf-8")[body_end:].decode("utf-8", errors="replace")

    debug_dir = _DEBUG_ROOT / language / project / task_name
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "task_prompt.md").write_text(prompt, encoding="utf-8")
    (debug_dir / "request_meta.json").write_text(
        json.dumps(
            {
                "task_dir": str(task_dir),
                "target": task_json.get("target", ""),
                "context_from_src_count": len(task_json.get("context_from_src", [])),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return _TaskContext(
        task_dir=task_dir,
        task_json=task_json,
        prompt=prompt,
        language=language,
        project=project,
        task_name=task_name,
        stub_info=stub_info,
        hollowed_text=hollowed_text,
        file_relpath=file_relpath,
        left_context=left_context,
        right_context=right_context,
        debug_dir=debug_dir,
        src_dir=(task_dir / run_config["src_dir"]).resolve(),
    )


def _load_repocoder_modules() -> dict[str, object]:
    if not _REPOCODER_ROOT.is_dir():
        raise RepoCoderError(f"RepoCoder source repo not found: {_REPOCODER_ROOT}")

    repocoder_root_str = str(_REPOCODER_ROOT)
    added = False
    if repocoder_root_str not in sys.path:
        sys.path.insert(0, repocoder_root_str)
        added = True

    try:
        import utils as utils_module  # type: ignore
    except Exception as exc:  # pragma: no cover - import error path
        raise RepoCoderError(f"Failed to import RepoCoder source modules: {exc}") from exc
    finally:
        if added:
            try:
                sys.path.remove(repocoder_root_str)
            except ValueError:
                pass

    return {"utils": utils_module}


def _run_round(
    ctx: _TaskContext,
    modules: dict[str, object],
    *,
    provider: str,
    model_name: str,
    round_idx: int,
    draft_prefix: str,
    workspace_dir: Path,
) -> dict[str, Any]:
    query_text = ctx.left_context if not draft_prefix else f"{ctx.left_context}{draft_prefix}"
    repo_windows = _build_repo_windows(ctx, workspace_dir)
    query_window = _build_query_window(ctx, query_text, workspace_dir)
    top_context = _search_top_context(repo_windows, query_window, top_k=10)
    retrieved_context = _format_retrieved_context(ctx.language, top_context)
    final_prompt = _build_final_prompt(ctx.prompt, query_text, ctx.right_context, retrieved_context)

    model_result = _call_model(provider, model_name, final_prompt)
    raw_completion = model_result.completion
    cleaned_completion = _normalize_function_body(
        ctx.task_dir,
        _fallback_clean_completion(raw_completion, ctx.stub_info.get("lang", "")),
        ctx.stub_info,
    )

    suffix = f"round{round_idx}"
    (ctx.debug_dir / f"query_context_{suffix}.txt").write_text(query_text, encoding="utf-8")
    (ctx.debug_dir / f"retrieved_context_{suffix}.txt").write_text(retrieved_context, encoding="utf-8")
    (ctx.debug_dir / f"final_prompt_{suffix}.txt").write_text(final_prompt, encoding="utf-8")
    (ctx.debug_dir / f"raw_completion_{suffix}.txt").write_text(raw_completion, encoding="utf-8")
    (ctx.debug_dir / f"cleaned_completion_{suffix}.txt").write_text(cleaned_completion, encoding="utf-8")
    (ctx.debug_dir / f"usage_{suffix}.json").write_text(
        json.dumps(model_result.usage, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "raw_completion": raw_completion,
        "cleaned_completion": cleaned_completion,
        "usage": model_result.usage,
    }


def _build_temp_workspace(ctx: _TaskContext) -> Path:
    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    workspace_dir = Path(tempfile.mkdtemp(prefix="pce_repocoder_", dir=_WORKSPACE_ROOT))
    workspace_src_dir = workspace_dir / "src"
    shutil.copytree(ctx.src_dir, workspace_src_dir)
    resolved_target = _resolve_repo_file(workspace_src_dir, ctx.file_relpath)
    if resolved_target is None:
        raise RepoCoderError(f"Failed to resolve target file in temporary workspace: {ctx.file_relpath}")
    hollowed_source = (ctx.task_dir / "hollowed_files" / ctx.file_relpath).read_text(encoding="utf-8")
    resolved_target.write_text(hollowed_source, encoding="utf-8")
    (ctx.debug_dir / "workspace_path.txt").write_text(str(workspace_dir) + "\n", encoding="utf-8")
    return workspace_dir


def _build_repo_windows(ctx: _TaskContext, workspace_dir: Path) -> list[dict]:
    src_dir = workspace_dir / "src"
    target_path = _resolve_repo_file(src_dir, ctx.file_relpath) or (src_dir / ctx.file_relpath)
    suffixes = _language_suffixes(ctx.language)
    candidate_files = list(_iter_candidate_files(src_dir, ctx.task_json.get("context_from_src", []), suffixes))

    repo_windows: list[dict] = []
    for candidate in candidate_files:
        if candidate.resolve() == target_path.resolve():
            continue
        rel_path = candidate.relative_to(src_dir)
        text = candidate.read_text(encoding="utf-8", errors="replace")
        repo_windows.extend(_slice_file_windows(text, rel_path.parts, ctx.project))

    summary = {
        "repo_windows": len(repo_windows),
        "candidate_files": len(candidate_files),
        "language": ctx.language,
    }
    (ctx.debug_dir / "repo_windows_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return repo_windows


def _iter_candidate_files(src_dir: Path, context_from_src: list[str], suffixes: tuple[str, ...]) -> Iterable[Path]:
    if context_from_src:
        for rel in context_from_src:
            path = _resolve_repo_file(src_dir, rel)
            if path is not None and path.is_file() and path.suffix.lower() in suffixes:
                yield path
        return

    for suffix in suffixes:
        yield from src_dir.rglob(f"*{suffix}")


def _language_suffixes(language: str) -> tuple[str, ...]:
    if language == "python":
        return (".py",)
    if language == "java":
        return (".java",)
    if language == "javascript":
        return (".js",)
    if language == "go":
        return (".go",)
    if language == "cpp":
        return (".cpp", ".cc", ".cxx", ".hpp", ".h")
    return (".txt",)


def _resolve_repo_file(src_dir: Path, rel_path: str) -> Path | None:
    direct = src_dir / rel_path
    if direct.exists():
        return direct

    if rel_path.startswith("src/"):
        stripped = src_dir / rel_path[len("src/"):]
        if stripped.exists():
            return stripped

    target = Path(rel_path)
    matches = list(src_dir.rglob(target.name))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    for match in matches:
        rel = match.relative_to(src_dir)
        if str(rel).endswith(rel_path):
            return match
    return matches[0]


def _slice_file_windows(code: str, fpath_parts: tuple[str, ...], repo: str, *, window_size: int = 20, slice_size: int = 2) -> list[dict]:
    code_lines = code.splitlines()
    delta_size = window_size // 2
    slice_step = 1 if window_size // slice_size == 0 else window_size // slice_size
    windows = []
    for line_no in range(0, len(code_lines), slice_step):
        start_line_no = max(0, line_no - delta_size)
        end_line_no = min(len(code_lines), line_no + window_size - delta_size)
        window_lines = code_lines[start_line_no:end_line_no]
        if not window_lines:
            continue
        windows.append(
            {
                "context": "\n".join(window_lines),
                "metadata": [
                    {
                        "fpath_tuple": (repo, *fpath_parts),
                        "line_no": line_no,
                        "start_line_no": start_line_no,
                        "end_line_no": end_line_no,
                        "window_size": window_size,
                        "repo": repo,
                        "slice_size": slice_size,
                    }
                ],
            }
        )
    return windows


def _build_query_window(ctx: _TaskContext, query_text: str, workspace_dir: Path) -> dict:
    src_dir = workspace_dir / "src"
    resolved_target = _resolve_repo_file(src_dir, ctx.file_relpath)
    if resolved_target is None:
        raise RepoCoderError(f"Failed to resolve target file for query window: {ctx.file_relpath}")
    line_no = len(query_text.splitlines())
    context_start_lineno = max(0, line_no - 20)
    query_lines = query_text.splitlines()
    window_lines = query_lines[context_start_lineno:line_no]
    return {
        "context": "\n".join(window_lines),
        "metadata": {
            "fpath_tuple": (ctx.project, *resolved_target.relative_to(src_dir).parts),
            "line_no": line_no,
            "task_id": f"{ctx.project}/{ctx.task_name}",
            "start_line_no": context_start_lineno,
            "end_line_no": line_no,
            "window_size": 20,
            "context_start_lineno": context_start_lineno,
            "repo": ctx.project,
        },
    }


def _search_top_context(repo_windows: list[dict], query_window: dict, *, top_k: int) -> list[tuple[dict, float]]:
    query_embedding = set(_tokenize(query_window["context"]))
    top_context: list[tuple[dict, float]] = []
    for repo_window in repo_windows:
        if _is_context_after_hole(repo_window, query_window):
            continue
        repo_embedding = set(_tokenize(repo_window["context"]))
        union = query_embedding | repo_embedding
        if not union:
            score = 0.0
        else:
            score = len(query_embedding & repo_embedding) / len(union)
        top_context.append((repo_window, score))
    top_context.sort(key=lambda item: item[1], reverse=True)
    return top_context[:top_k]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\S", text)


def _is_context_after_hole(repo_window: dict, query_window: dict) -> bool:
    hole_fpath_tuple = tuple(query_window["metadata"]["fpath_tuple"])
    for metadata in repo_window["metadata"]:
        if tuple(metadata["fpath_tuple"]) != hole_fpath_tuple:
            return False
        if metadata["end_line_no"] <= query_window["metadata"]["context_start_lineno"]:
            return False
    return True


def _format_retrieved_context(language: str, top_context: list[tuple[dict, float]]) -> str:
    comment_prefix = "#" if language == "python" else "//"
    separator = f"{comment_prefix} " + "-" * 50
    blocks = [f"{comment_prefix} Here are some relevant code fragments from other files of the repo:", separator]
    for content, _score in top_context:
        metadata = content["metadata"][0]
        file_path = "/".join(metadata["fpath_tuple"][1:])
        blocks.append(f"{comment_prefix} the below code fragment can be found in:")
        blocks.append(f"{comment_prefix} {file_path}")
        blocks.append(separator)
        for line in content["context"].splitlines():
            blocks.append(f"{comment_prefix} {line}")
        blocks.append(separator)
    return "\n".join(blocks).rstrip()


def _build_final_prompt(task_prompt: str, left_context: str, right_context: str, retrieved_context: str) -> str:
    parts = [task_prompt.strip()]
    if retrieved_context:
        parts.append(retrieved_context)
    parts.append(
        "\n".join(
            [
                "# Current File Context",
                "```text",
                left_context.rstrip(),
                "<FILL_FUNCTION_BODY_HERE>",
                right_context.lstrip(),
                "```",
            ]
        )
    )
    return "\n\n".join(part for part in parts if part.strip())


def _call_model(provider: str, model_name: str, prompt: str) -> _ModelCallResult:
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(timeout=_API_TIMEOUT_SECONDS)
        msg = client.messages.create(
            model=model_name,
            max_tokens=4096,
            system=_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return _ModelCallResult(
            completion=msg.content[0].text or "",
            usage=_extract_usage_dict(getattr(msg, "usage", None)),
        )

    from openai import OpenAI

    base_url = os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(
        **({"base_url": base_url} if base_url else {}),
        **({"api_key": api_key} if api_key else {}),
        timeout=_API_TIMEOUT_SECONDS,
    )
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.2,
    )
    return _ModelCallResult(
        completion=resp.choices[0].message.content or "",
        usage=_extract_usage_dict(getattr(resp, "usage", None)),
    )


def _extract_usage_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def _to_int(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    if hasattr(usage, "model_dump"):
        raw = usage.model_dump()
    elif hasattr(usage, "dict"):
        raw = usage.dict()
    elif isinstance(usage, dict):
        raw = usage
    else:
        raw = {}

    input_tokens = _to_int(raw.get("input_tokens", raw.get("prompt_tokens")))
    output_tokens = _to_int(raw.get("output_tokens", raw.get("completion_tokens")))
    total_tokens = _to_int(raw.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    extracted = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }
    for key in (
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "reasoning_tokens",
        "prompt_tokens",
        "completion_tokens",
    ):
        value = _to_int(raw.get(key))
        if value:
            extracted[key] = value
    return extracted


def _system_prompt() -> str:
    return (
        "You are an expert programmer. Complete the body of the target function described in the prompt. "
        "Return ONLY the function body code. "
        "Do NOT include the function signature. "
        "Do NOT wrap the code in markdown formatting. "
        "Use the repository context when it is relevant."
    )


def _fallback_clean_completion(raw_completion: str, lang: str) -> str:
    cleaned = raw_completion.strip()
    if not cleaned:
        return ""

    fenced = re.match(r"^```[\w+-]*\n([\s\S]*?)\n```$", cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()

    if lang == "python":
        match = re.search(r"^\s*def\s+\w+\s*\(.*?\)\s*:\s*\n([\s\S]*)$", cleaned, re.MULTILINE)
        if match:
            return textwrap.dedent(match.group(1)).strip()
        return cleaned

    stripped = cleaned.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped[1:-1].strip()
    return stripped


def _normalize_function_body(task_dir: Path, body: str, stub_info: dict) -> str:
    if not body:
        return body

    lang = stub_info.get("lang", "")
    if lang == "python":
        normalized = _normalize_python_body(body)
        if not normalized:
            return ""
        return normalized
    dedented = _normalize_brace_indentation(body).rstrip()
    hollowed_text = (task_dir / "hollowed_files" / stub_info["file"]).read_text(encoding="utf-8")
    stub_indent = _find_stub_indent(hollowed_text.splitlines(), stub_info.get("stub", ""))
    normalized_lines = []
    for line in dedented.splitlines():
        if not line.strip():
            normalized_lines.append("")
            continue
        normalized_lines.append(f"{stub_indent}{line}")
    return "\n".join(normalized_lines).rstrip()


def _find_stub_indent(lines: list[str], stub: str) -> str:
    for line in lines:
        if line.strip() == stub:
            return line[: len(line) - len(line.lstrip(" \t"))]
    return ""


def _normalize_brace_indentation(body: str, *, tabstop: int = 4) -> str:
    lines = body.strip("\n").splitlines()
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""

    min_width = min(_indent_width(line, tabstop) for line in non_empty)
    normalized: list[str] = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        normalized.append(_strip_indent_width(line, min_width, tabstop))
    return "\n".join(normalized).rstrip()


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


def _strip_indent_width(line: str, width: int, tabstop: int = 4) -> str:
    remaining = width
    idx = 0
    while idx < len(line) and remaining > 0:
        ch = line[idx]
        if ch == " ":
            remaining -= 1
            idx += 1
            continue
        if ch == "\t":
            remaining -= tabstop
            idx += 1
            continue
        break
    return line[idx:]


def _normalize_python_body(body: str) -> str:
    dedented = textwrap.dedent(body).strip("\n")
    lines = dedented.splitlines()
    if not lines:
        return ""

    first_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_idx is None:
        return ""

    first_width = _indent_width(lines[first_idx])
    storage_base_width = 4
    normalized: list[str] = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        width = _indent_width(line)
        relative_width = width - first_width
        stored_width = storage_base_width + relative_width
        if stored_width < 0:
            raise RepoCoderError(
                "Python indentation rebase produced a negative stored width; "
                "the model output has an invalid relative indentation structure."
            )
        normalized.append((" " * stored_width) + line.lstrip(" \t"))
    return "\n".join(normalized).rstrip()
