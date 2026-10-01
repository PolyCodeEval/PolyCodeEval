"""Final L2/L3 prompt construction helpers.

This module contains the formal prompt-description generation path used by
`build_tasks.py`. It folds the useful behavior from earlier prompt iteration
scripts into one construction-stage implementation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from l3_evaluator.workspace import _resolve_file


STUB_BY_LANG = {
    "python": "pass",
    "go": 'panic("not implemented")',
    "java": "throw new UnsupportedOperationException();",
    "javascript": "throw new Error('not implemented')",
    "typescript": "throw new Error('not implemented')",
    "cpp": "/* not implemented */",
}

CALL_KEYWORD_BLOCKLIST = {
    "if", "for", "while", "switch", "return", "sizeof", "catch", "throw",
    "new", "delete", "await", "yield", "typeof", "elif", "assert",
}

LOCAL_SYMBOL_BLOCKLIST = {
    "handler", "handlers", "callback", "cb", "fn", "func", "item", "value",
    "key", "result", "node", "elem", "element", "event", "evt", "self", "cls",
}

LANGUAGE_BUILTIN_BLOCKLIST: dict[str, set[str]] = {
    "go": {"len", "make", "append", "copy", "new", "delete", "panic", "recover", "close", "cap", "complex", "real", "imag", "print", "println"},
    "python": {"len", "list", "dict", "set", "tuple", "print", "range", "enumerate", "zip", "map", "filter", "sum", "min", "max", "any", "all", "isinstance", "getattr", "setattr", "hasattr"},
    "javascript": {"map", "filter", "reduce", "slice", "push", "pop", "shift", "unshift", "forEach", "includes", "setTimeout", "setInterval", "Promise"},
    "typescript": {"map", "filter", "reduce", "slice", "push", "pop", "shift", "unshift", "forEach", "includes", "setTimeout", "setInterval", "Promise"},
    "java": {"length", "size", "add", "put", "get", "equals", "hashCode", "toString", "valueOf", "format"},
    "cpp": {"copy", "copy_n", "move", "begin", "end", "next", "prev", "back_inserter", "make", "size"},
}


class PromptConstructionError(RuntimeError):
    """Raised when final prompt construction fails."""


@dataclass(frozen=True)
class TaskInfo:
    level: str
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


def discover_tasks(
    datasets_root: Path,
    level: str,
    *,
    language: str | None = None,
    project: str | None = None,
    task: str | None = None,
) -> list[TaskInfo]:
    tasks: list[TaskInfo] = []
    for task_json_path in sorted(datasets_root.glob(f"*/*/tasks/{level}_*/task.json")):
        task_dir = task_json_path.parent
        project_root = task_dir.parents[1]
        current = TaskInfo(
            level=level,
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_l2_context(task: TaskInfo) -> dict[str, Any]:
    task_json = load_json(task.task_json_path)
    run_config = load_json(task.run_config_path)
    prompt_markdown = task.prompt_path.read_text(encoding="utf-8")
    src_dir = (task.task_dir / run_config["src_dir"]).resolve()
    target_rel = task_json["target"]
    resolved_rel = _resolve_file(src_dir, target_rel)
    source_path = (src_dir / resolved_rel).resolve()
    skeleton_path = task.task_dir / "hollowed_files" / target_rel
    if not skeleton_path.exists():
        skeleton_path = task.task_dir / "hollowed_files" / resolved_rel
    skeleton_text = skeleton_path.read_text(encoding="utf-8", errors="replace")
    language = task_json["stub_info"]["lang"]
    stubbed_signatures = extract_stubbed_signatures(skeleton_text, language)
    return {
        "task_json": task_json,
        "run_config": run_config,
        "prompt_markdown": prompt_markdown,
        "requirement_context": extract_section(prompt_markdown, "Requirement Context"),
        "source_file_rel": resolved_rel,
        "source_text": source_path.read_text(encoding="utf-8", errors="replace"),
        "skeleton_text": skeleton_text,
        "stubbed_signatures": stubbed_signatures,
        "function_count": int(task_json["stub_info"].get("function_count", len(stubbed_signatures))),
    }


def build_l2_description_request(task: TaskInfo, context: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are a senior software engineer writing a file-level multi-function "
        "completion prompt for an L2 task. The solver must reconstruct an entire "
        "file whose multiple function bodies have been replaced by stubs. Describe "
        "the file-level responsibilities and each hollowed function clearly enough "
        "to reproduce the current implemented behavior. Return valid JSON only."
    )
    lang = context["task_json"]["stub_info"]["lang"]
    user = f"""Write the descriptive sections for this L2 file-completion task.

Task ID: {task.task_id}
Language: {task.language}
Target file: {context['source_file_rel']}
Hollowed function count: {context['function_count']}

Requirement context:
```markdown
{context['requirement_context']}
```

Target file skeleton:
```{lang}
{context['skeleton_text']}
```

Full current implementation of the target file:
```{lang}
{context['source_text']}
```

Functions to describe:
```json
{json.dumps(context['stubbed_signatures'], ensure_ascii=False, indent=2)}
```

Requirements:
- Summarize the file as a whole in `file_description`.
- Cover every hollowed function in `function_responsibilities`.
- Use behavior-focused descriptions.
- Do not write line-by-line source explanations.
- Return JSON with this exact shape:
{{
  "file_description": ["bullet 1", "bullet 2"],
  "function_responsibilities": [
    {{"signature": "function signature", "responsibility": ["bullet 1", "bullet 2"]}}
  ]
}}
"""
    return system, user


def render_l2_prompt(context: dict[str, Any], description_payload: dict[str, Any]) -> str:
    file_description = description_payload.get("file_description")
    function_responsibilities = description_payload.get("function_responsibilities")
    if not isinstance(file_description, list) or not file_description:
        raise PromptConstructionError("file_description must be a non-empty list")
    if not isinstance(function_responsibilities, list) or not function_responsibilities:
        raise PromptConstructionError("function_responsibilities must be a non-empty list")

    lang = context["task_json"]["stub_info"]["lang"]
    parts = [
        "# Task",
        "",
        f"Generate the complete contents of `{context['source_file_rel']}`.",
        "The file skeleton below shows the structure with function bodies replaced by stubs. Fill in all function bodies and return the entire file.",
        "",
        "# File Description",
    ]
    parts.extend(f"- {str(item).strip()}" for item in file_description if str(item).strip())
    parts.extend(["", "# Function Responsibilities"])
    for entry in function_responsibilities:
        if not isinstance(entry, dict):
            continue
        signature = str(entry.get("signature", "")).strip()
        responsibility = entry.get("responsibility")
        if not signature or not isinstance(responsibility, list):
            continue
        parts.append(f"## {signature}")
        parts.extend(f"- {str(item).strip()}" for item in responsibility if str(item).strip())
        parts.append("")
    if parts[-1] == "":
        parts.pop()
    parts.extend(
        [
            "",
            "# Related Context",
            "",
            "## Target File (Skeleton)",
            "",
            f"### {context['source_file_rel']}",
            "",
            f"```{lang}",
            context["skeleton_text"].rstrip(),
            "```",
            "",
            "## Hollowed Function Signatures",
        ]
    )
    if context["stubbed_signatures"]:
        parts.extend(f"- `{signature}`" for signature in context["stubbed_signatures"])
    else:
        parts.append("- None")
    return "\n".join(parts).rstrip() + "\n"


def build_l3_context(task: TaskInfo) -> dict[str, Any]:
    task_json = load_json(task.task_json_path)
    run_config = load_json(task.run_config_path)
    prompt_markdown = task.prompt_path.read_text(encoding="utf-8")
    stub_info = task_json.get("stub_info") or {}
    src_dir = (task.task_dir / run_config["src_dir"]).resolve()
    resolved_rel = _resolve_file(src_dir, stub_info["file"])
    source_path = (src_dir / resolved_rel).resolve()
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8", errors="replace")
    body_start = int(stub_info["body_start_byte"])
    body_end = int(stub_info["body_end_byte"])
    signature = extract_l3_signature(prompt_markdown)
    if not signature:
        signature = derive_signature_from_source(source_bytes, body_start, stub_info.get("func_name", ""), stub_info.get("lang", task.language))
    signature = normalize_signature(signature, task.language)
    function_body = source_bytes[body_start:body_end].decode("utf-8", errors="replace")
    called_signatures = collect_called_function_signatures(task, task_json, run_config, function_body)
    return {
        "task_json": task_json,
        "run_config": run_config,
        "prompt_markdown": prompt_markdown,
        "signature": signature,
        "function_body": function_body,
        "called_signatures": called_signatures,
        "signature_summary": build_signature_summary(signature, task.language),
    }


def build_l3_description_request(task: TaskInfo, context: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are a senior software engineer writing the function description for "
        "an L3 function-completion prompt. Read the function signature and complete "
        "implementation body, then produce an abstract but complete behavior "
        "description. Return valid JSON only."
    )
    lang = context["task_json"]["stub_info"].get("lang", "text")
    user = f"""Write the descriptive section for this L3 function-completion task.

Task ID: {task.task_id}
Language: {task.language}
Function name: {context["task_json"]["stub_info"]["func_name"]}

Function signature:
```text
{context["signature"]}
```

Complete implementation body:
```{lang}
{context["function_body"]}
```

Requirements:
- Summarize what the function does at an abstract behavior level.
- Cover important branches, boundary cases, return values, side effects, and error behavior present in the implementation.
- Do not narrate the source line by line.
- Do not add sections beyond the requested JSON.
- Return JSON with this exact shape:
{{
  "function_description": ["bullet 1", "bullet 2"]
}}
"""
    return system, user


def render_l3_prompt(task: TaskInfo, context: dict[str, Any], description_payload: dict[str, Any]) -> str:
    function_description = description_payload.get("function_description")
    if not isinstance(function_description, list) or not function_description:
        raise PromptConstructionError("function_description must be a non-empty list")

    func_name = context["task_json"]["stub_info"]["func_name"]
    src_dir = (task.task_dir / context["run_config"]["src_dir"]).resolve()
    target_rel = str(Path(_resolve_file(src_dir, context["task_json"]["stub_info"]["file"])))
    parts = [
        "# Task",
        f"Complete the body of the `{func_name}` function.",
        "Return only the function body. Do not change the signature.",
        "",
        "# Function Description",
    ]
    parts.extend(f"- {str(item).strip()}" for item in function_description if str(item).strip())
    parts.extend(
        [
            "",
            "# Related Context",
            "## Signature",
            "```text",
            context["signature"].strip(),
            "```",
            "",
            "## Inputs / Outputs",
        ]
    )
    parts.extend(f"- {str(item).strip()}" for item in context["signature_summary"] if str(item).strip())
    parts.extend(["", "## Called Function Signatures"])
    if context["called_signatures"]:
        for item in context["called_signatures"]:
            heading = f"{item['path']} - {item['symbol']}"
            if item["path"] == target_rel:
                heading = item["symbol"]
            parts.extend([f"### {heading}", "```text", item["signature"].strip(), "```", ""])
        if parts[-1] == "":
            parts.pop()
    else:
        parts.append("- None")
    return "\n".join(parts).rstrip() + "\n"


def extract_section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^# {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^# ", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    return markdown[start:end].strip()


def extract_stubbed_signatures(skeleton_text: str, language: str) -> list[str]:
    stub = STUB_BY_LANG[language]
    lines = skeleton_text.splitlines()
    signatures: list[str] = []
    for idx, line in enumerate(lines):
        if stub not in line:
            continue
        start = idx - 1
        while start >= 0:
            current = lines[start].strip()
            if language == "python" and current.startswith(("def ", "async def ")):
                signatures.append(current)
                break
            if language == "go" and current.startswith("func "):
                signatures.append(current)
                break
            if language in {"java", "cpp", "javascript", "typescript"} and "(" in current:
                collected = [current]
                cursor = start + 1
                while cursor < idx and lines[cursor].strip() and stub not in lines[cursor]:
                    if lines[cursor].strip() == "{":
                        break
                    collected.append(lines[cursor].strip())
                    if "{" in lines[cursor]:
                        break
                    cursor += 1
                signatures.append(" ".join(collected).replace(" {", "").strip())
                break
            start -= 1
    return signatures


def extract_l3_signature(prompt_markdown: str) -> str:
    match = re.search(r"^## Signature\s*$\n```(?:\w+)?\n(.*?)\n```", prompt_markdown, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def derive_signature_from_source(source_bytes: bytes, body_start: int, symbol: str, language: str) -> str:
    prefix = source_bytes[:body_start].decode("utf-8", errors="replace")
    lines = prefix.splitlines()
    for line in reversed(lines[-30:]):
        stripped = line.strip()
        if not stripped:
            continue
        if language == "python" and stripped.startswith(("def ", "async def ")):
            return stripped
        if language == "go" and stripped.startswith("func "):
            return stripped
        if symbol and symbol in stripped and "(" in stripped:
            return stripped.rstrip("{").rstrip(":").strip()
    return lines[-1].strip() if lines else ""


def normalize_signature(signature: str, language: str) -> str:
    lines = [line.rstrip() for line in signature.splitlines() if line.strip()]
    if not lines:
        return signature.strip()
    if language == "python":
        acc: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                break
            acc.append(line)
            if stripped.endswith(":"):
                break
        return "\n".join(acc).strip()
    if language == "go":
        acc: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                break
            acc.append(line)
            joined = " ".join(part.strip() for part in acc)
            if joined.startswith("func "):
                return joined.strip()
        return " ".join(lines).strip()
    return "\n".join(lines).strip()


def extract_candidate_callees(function_source: str, self_name: str, language: str) -> list[tuple[str, str | None]]:
    found: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    builtin_blocklist = LANGUAGE_BUILTIN_BLOCKLIST.get(language, set())
    pattern = re.compile(r"\b(?:(?P<qualifier>[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
    for match in pattern.finditer(function_source):
        qualifier = match.group("qualifier")
        name = match.group("name")
        prefix = function_source[max(0, match.start() - 8):match.start()]
        if language in {"javascript", "typescript"} and re.search(r"\bnew\s+$", prefix):
            continue
        if name == self_name or name in CALL_KEYWORD_BLOCKLIST or name in LOCAL_SYMBOL_BLOCKLIST or name in builtin_blocklist:
            continue
        candidate = (name, qualifier)
        if candidate not in seen:
            seen.add(candidate)
            found.append(candidate)
    return found


def extract_signature_from_text(text: str, symbol: str, language: str) -> str | None:
    lines = text.splitlines()
    patterns = [
        re.compile(rf"^\s*(?:def|async def|function)\s+{re.escape(symbol)}\b"),
        re.compile(rf"^\s*(?:public|private|protected|static|inline|virtual|constexpr|export\s+|async\s+|[\w:<>,~*&\[\]\s]+)\b{re.escape(symbol)}\s*\("),
        re.compile(rf"^\s*{re.escape(symbol)}\s*\("),
    ]
    for idx, line in enumerate(lines):
        if not line.strip() or not any(pattern.search(line) for pattern in patterns):
            continue
        start = idx
        while start > 0:
            previous = lines[start - 1].strip()
            if not previous or previous.startswith(("//", "/*", "*", "#", "@")):
                start -= 1
                continue
            break
        signature_lines = [lines[start]]
        balance = lines[start].count("(") - lines[start].count(")")
        cursor = start + 1
        while cursor < len(lines) and (balance > 0 or not lines[cursor - 1].strip().endswith(("{", ":", ")"))):
            signature_lines.append(lines[cursor])
            balance += lines[cursor].count("(") - lines[cursor].count(")")
            cursor += 1
            if cursor - start > 12:
                break
        signature = "\n".join(signature_lines).strip()
        signature = re.sub(r"\s*\{\s*$", "", signature).rstrip()
        if language == "go" and "if " in signature:
            return None
        if language in {"go", "java", "javascript", "typescript"} and (" return" in signature or "=" in signature):
            return None
        return normalize_signature(signature, language)
    return None


def collect_called_function_signatures(
    task: TaskInfo,
    task_json: dict[str, Any],
    run_config: dict[str, Any],
    function_source: str,
) -> list[dict[str, str]]:
    stub_info = task_json.get("stub_info") or {}
    src_dir = (task.task_dir / run_config["src_dir"]).resolve()
    search_files: list[Path] = []
    resolved_target = _resolve_file(src_dir, stub_info["file"])
    target_path = (src_dir / resolved_target).resolve()
    if target_path.is_file():
        search_files.append(target_path)
    for rel in task_json.get("context_from_src") or []:
        resolved = _resolve_file(src_dir, rel)
        candidate = (src_dir / resolved).resolve()
        if candidate.is_file() and candidate not in search_files:
            search_files.append(candidate)

    candidates = extract_candidate_callees(function_source, stub_info.get("func_name", ""), task.language)
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for symbol, qualifier in candidates:
        if qualifier is not None:
            continue
        for path in search_files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            signature = extract_signature_from_text(text, symbol, task.language)
            if not signature:
                continue
            rel = str(path.relative_to(src_dir))
            key = (rel, symbol)
            if key in seen:
                break
            seen.add(key)
            results.append({"path": rel, "symbol": symbol, "signature": signature})
            break
    return results


def split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth_angle = depth_round = depth_square = depth_curly = 0
    for char in text:
        if char == "<":
            depth_angle += 1
        elif char == ">":
            depth_angle = max(0, depth_angle - 1)
        elif char == "(":
            depth_round += 1
        elif char == ")":
            depth_round = max(0, depth_round - 1)
        elif char == "[":
            depth_square += 1
        elif char == "]":
            depth_square = max(0, depth_square - 1)
        elif char == "{":
            depth_curly += 1
        elif char == "}":
            depth_curly = max(0, depth_curly - 1)
        if char == "," and depth_angle == depth_round == depth_square == depth_curly == 0:
            piece = "".join(current).strip()
            if piece:
                parts.append(piece)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def extract_signature_components(signature: str, language: str) -> tuple[list[str], str]:
    signature_line = " ".join(signature.split())
    params: list[str] = []
    paren_start = signature_line.find("(")
    paren_end = -1
    if paren_start >= 0:
        depth = 0
        for idx in range(paren_start, len(signature_line)):
            char = signature_line[idx]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    paren_end = idx
                    break
    params_raw = signature_line[paren_start + 1:paren_end].strip() if paren_start >= 0 and paren_end > paren_start else ""
    if params_raw:
        params = split_top_level_commas(params_raw)

    return_type = "unknown"
    if language == "python":
        match = re.match(r"^def\s+[^(]+\((.*)\)\s*(?:->\s*(.*?))?:?$", signature_line)
        if match:
            params = split_top_level_commas(match.group(1).strip()) if match.group(1).strip() else []
            return_type = (match.group(2) or "None").strip()
        return params, return_type
    if language == "go":
        if signature_line.startswith("func ") and paren_start >= 0 and paren_end > paren_start:
            params = split_top_level_commas(signature_line[paren_start + 1:paren_end].strip()) if signature_line[paren_start + 1:paren_end].strip() else []
            return_type = signature_line[paren_end + 1:].strip() or "void"
        return params, return_type
    if language in {"javascript", "typescript"}:
        match = re.match(r"^(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*([^(]+)\((.*)\)\s*(?::\s*(.*))?$", signature_line)
        if match:
            params = split_top_level_commas(match.group(2).strip()) if match.group(2).strip() else []
            return_type = (match.group(3) or "void").strip()
        return params, return_type
    if language == "java":
        before_paren = signature_line.split("(", 1)[0].strip()
        tokens = [tok for tok in before_paren.split() if tok not in {"public", "private", "protected", "static", "final", "abstract", "synchronized", "native", "default"}]
        if len(tokens) >= 2:
            return_type = tokens[-2]
        elif tokens:
            return_type = tokens[0]
        return params, return_type
    if language == "cpp":
        before_paren = signature_line.split("(", 1)[0].strip()
        func_name = before_paren.split()[-1] if before_paren.split() else ""
        prefix = before_paren[: before_paren.rfind(func_name)].strip() if func_name and func_name in before_paren else before_paren
        return_type = prefix or "unknown"
        return params, return_type
    return params, return_type


def build_signature_summary(signature: str, language: str) -> list[str]:
    params, return_type = extract_signature_components(signature, language)
    lines: list[str] = []
    if params:
        lines.extend(f"Input parameter: `{param}`" for param in params)
    else:
        lines.append("Input parameters: none")
    if return_type.lower() in {"void", "none"}:
        lines.append("Output format: no return value.")
    else:
        lines.append(f"Output format: returns `{return_type}`.")
    return lines

