"""
Generate LLM-based function descriptions for L3 tasks.
Reads the Target File section from prompt.md and calls a cheap model
(e.g. gpt-5.4-nano) to produce a short, test-oriented behavior summary
of what the function should do. Saves the result to desc.txt in each
task directory.
"""
from __future__ import annotations

import re
import sys
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_SYSTEM_PROMPT = (
    "Based on the code context, summarize the target function in concise English bullets. "
    "Focus on test-critical behavior, not implementation strategy.\n"
    "Include:\n"
    "- inputs and optional arguments\n"
    "- default values or argument count rules if visible\n"
    "- return value and side effects\n"
    "- invalid input behavior / error behavior if visible\n"
    "- important boundary conditions explicitly visible in the code or documentation\n"
    "Do not invent behavior that is not supported by the context.\n"
    "Do not say the function takes no inputs if the signature has parameters.\n"
    "Prefer 3-6 bullet points. Reply in English."
)

_TARGET_FILE_RE = re.compile(
    r"# Target File\n.*?```\n(.*?)```",
    re.DOTALL,
)


def _extract_target_file_snippet(prompt_md: str, max_chars: int = 3000) -> str:
    m = _TARGET_FILE_RE.search(prompt_md)
    if m:
        return m.group(1)[:max_chars]
    return prompt_md[:max_chars]


def _extract_func_name(task_dir: Path) -> str:
    name = task_dir.name
    if name.startswith("L3_"):
        parts = name.split("__", 1)
        if len(parts) == 2:
            return parts[1]
    return name


def _extract_signature(prompt_md: str) -> str:
    lines = prompt_md.splitlines()
    in_target = False
    in_code = False
    code_lines: list[str] = []
    for line in lines:
        if line.startswith("# Target File"):
            in_target = True
            continue
        if not in_target:
            continue
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                continue
            break
        if in_code:
            code_lines.append(line)

    name_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)$")
    for i, line in enumerate(code_lines):
        if "panic(\"not implemented\")" in line or line.strip() == "pass":
            for j in range(i - 1, -1, -1):
                s = code_lines[j].rstrip()
                if not s.strip():
                    continue
                return s
    for line in code_lines:
        s = line.strip()
        if s.startswith(("def ", "func ", "function ")):
            return s
        if name_re.match(s):
            return s
    return ""


def _extract_doc_context(prompt_md: str) -> str:
    parts = []
    m = re.search(r"## Documentation\n(.*?)(?:\n## |\Z)", prompt_md, re.DOTALL)
    if m:
        doc = m.group(1).strip()
        if doc:
            parts.append(f"Documentation:\n{doc}")
    return "\n\n".join(parts)


def _format_desc(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        if not text.startswith("-"):
            text = f"- {text.lstrip('*').strip()}"
        lines.append(text)
    return "\n".join(lines).strip()


def _desc_conflicts_with_signature(desc: str, signature: str) -> bool:
    sig = signature.strip()
    desc_lower = desc.lower()
    if not sig:
        return False
    has_args = ("(" in sig and ")" in sig and "()" not in sig)
    returns_error = " error" in sig or ") error" in sig or ", error" in sig
    variadic = "..." in sig

    if has_args and "takes no input" in desc_lower:
        return True
    if returns_error and ("panics internally" in desc_lower or "guarantee an id is produced" in desc_lower):
        return True
    if variadic and "takes no input" in desc_lower:
        return True
    return False


def _should_retry(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    text = str(exc).lower()
    return any(m in text for m in ("timeout", "timed out", "connection",
                                   "temporarily unavailable", "bad gateway",
                                   "rate limit", "server error"))


def _generate_one(
    client,
    task_dir: Path,
    model: str,
    max_retries: int,
    retry_base_delay: float,
) -> bool:
    desc_file = task_dir / "desc.txt"
    if desc_file.exists():
        return True

    prompt_file = task_dir / "prompt.md"
    if not prompt_file.exists():
        return False

    func_name = _extract_func_name(task_dir)
    prompt_md = prompt_file.read_text(encoding="utf-8")
    snippet = _extract_target_file_snippet(prompt_md)
    signature = _extract_signature(prompt_md)
    doc_context = _extract_doc_context(prompt_md)

    user_msg = (
        f"Function name: `{func_name}`\n\n"
        f"Signature:\n```\n{signature}\n```\n\n"
        f"{doc_context}\n\n"
        f"Code context:\n```\n{snippet}\n```"
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                max_tokens=220,
            )
            desc = _format_desc(response.choices[0].message.content.strip())
            if _desc_conflicts_with_signature(desc, signature):
                raise ValueError(f"Generated description conflicts with signature for {task_dir.name}")
            desc_file.write_text(desc, encoding="utf-8")
            return True
        except Exception as e:
            if attempt < max_retries and _should_retry(e):
                delay = retry_base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            print(f"\n  Error {task_dir.name}: {e}", file=sys.stderr)
            return False


def generate_descriptions(
    task_dirs: list[Path],
    model: str,
    base_url: str,
    api_key: str,
    workers: int = 8,
    max_retries: int = 3,
    retry_base_delay: float = 2.0,
    timeout: float = 60.0,
) -> tuple[int, int]:
    """Generate desc.txt for each task_dir. Returns (success, failed) counts."""
    try:
        from openai import OpenAI
    except ImportError:
        print("需要安装 openai 包：pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    total = len(task_dirs)
    success = 0
    failed = 0
    done = 0
    start_time = time.time()

    def _progress() -> str:
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
            f"| ok:{success} err:{failed} "
            f"| {elapsed:.0f}s elapsed, ETA {eta_str}  "
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_generate_one, client, td, model, max_retries, retry_base_delay): td
            for td in task_dirs
        }
        for future in as_completed(futures):
            done += 1
            if future.result():
                success += 1
            else:
                failed += 1
            sys.stderr.write(_progress())
            sys.stderr.flush()

    sys.stderr.write("\n")
    return success, failed
