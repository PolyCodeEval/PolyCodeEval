from __future__ import annotations

import re
from pathlib import Path

from slicer.parser import FunctionInfo, SymbolExtractor

PROMPT_CHAR_BUDGET = 32_000
TARGET_FILE_BUDGET_RATIO = 0.7
CONTEXT_LINES_AROUND_TARGET = 30
MAX_TEST_SNIPPETS = 3

_LICENSE_RE = re.compile(
    r"^\s*(/\*[\s\S]*?\*/|<!--[\s\S]*?-->|#[^\n]*license[^\n]*\n(?:#[^\n]*\n)*)",
    re.IGNORECASE,
)

_COMMENT_BLOCK_RE = re.compile(
    r"/\*[\s\S]*?\*/",
)


def build_prompt(
    func: FunctionInfo,
    hollowed_source: bytes,
    project_dir: Path,
    source_files: list[Path],
    source_roots: list[Path],
    extractor: SymbolExtractor,
    task_dir: Path | None = None,
) -> str:
    original_source = func.file.read_bytes()
    callees = extractor.find_callees(func, original_source)

    other_files = [f for f in source_files if f != func.file]

    callee_snippets = _collect_callee_signatures(
        callees, other_files, extractor
    )
    caller_snippets = _collect_caller_call_sites(
        func.name, func.file, other_files, extractor, original_source,
    )
    req_context = _build_requirement_context(func, task_dir)
    hollowed_text = hollowed_source.decode("utf-8", errors="replace")
    hollowed_rel = _rel_path(func.file, source_roots)
    test_snippets = _collect_test_snippets(func.name, project_dir)

    target_text = _build_skeleton(hollowed_text, func, hollowed_source)

    sections = []
    sections.append(
        f"# Task\n"
        f"Complete the body of the `{func.name}` function.\n"
        f"Return only the function body. Do not change the signature.\n"
    )

    if req_context:
        sections.append(f"# Function Contract\n{req_context}\n")

    sections.append(f"# Target File\n## {hollowed_rel}\n```\n{target_text}\n```\n")

    if callee_snippets:
        parts = []
        for path, name, sig in callee_snippets:
            rel = _rel_path(path, source_roots)
            parts.append(f"### {rel} — {name}\n```\n{sig}\n```")
        sections.append("# Related Definitions\n" + "\n\n".join(parts) + "\n")

    if caller_snippets:
        parts = []
        for path, name, snippet in caller_snippets:
            rel = _rel_path(path, source_roots)
            parts.append(f"### {rel} — {name}\n```\n{snippet}\n```")
        sections.append("# Call Sites\n" + "\n\n".join(parts) + "\n")

    if test_snippets:
        parts = []
        for rel, snippet in test_snippets:
            parts.append(f"### {rel}\n```\n{snippet}\n```")
        sections.append("# Relevant Tests\n" + "\n\n".join(parts) + "\n")

    prompt = "\n".join(sections)
    return _enforce_budget(prompt, PROMPT_CHAR_BUDGET)


def _build_skeleton(
    hollowed_text: str, func: FunctionInfo, hollowed_source: bytes,
) -> str:
    lines = hollowed_text.split("\n")
    total = len(lines)
    if total <= 200:
        return _strip_license(hollowed_text)

    source_before_func = hollowed_source[:func.start_byte]
    func_start_line = source_before_func.count(b"\n")

    source_before_body_end = hollowed_source[:func.body_end_byte]
    func_end_line = source_before_body_end.count(b"\n")

    keep_start = max(0, func_start_line - CONTEXT_LINES_AROUND_TARGET)
    keep_end = min(total, func_end_line + CONTEXT_LINES_AROUND_TARGET + 1)

    header_lines = _extract_header_lines(lines)
    skeleton_parts = []

    if header_lines:
        skeleton_parts.append("\n".join(header_lines))

    if keep_start > len(header_lines):
        above = _collapse_functions(lines, len(header_lines), keep_start)
        if above:
            skeleton_parts.append(above)

    skeleton_parts.append("\n".join(lines[keep_start:keep_end]))

    if keep_end < total:
        below = _collapse_functions(lines, keep_end, total)
        if below:
            skeleton_parts.append(below)

    result = "\n".join(skeleton_parts)
    return _strip_license(result)


def _extract_header_lines(lines: list[str]) -> list[str]:
    header = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            header.append(line)
            continue
        if stripped.startswith(("import ", "from ", "require(", "const ", "let ",
                                "var ", "export ", "package ", "#include",
                                "using ", "//", "/*", " *", "*/", "#pragma",
                                "#ifndef", "#define", "#endif", "module ")):
            header.append(line)
            continue
        if stripped.startswith("*"):
            header.append(line)
            continue
        break
    return header


def _collapse_functions(lines: list[str], start: int, end: int) -> str:
    collapsed = []
    i = start
    while i < end:
        line = lines[i]
        stripped = line.strip()
        if _is_function_start(stripped):
            collapsed.append(line)
            indent = len(line) - len(line.lstrip())
            brace_depth = stripped.count("{") - stripped.count("}")
            i += 1
            while i < end:
                inner = lines[i]
                inner_stripped = inner.strip()
                if brace_depth <= 0 and inner_stripped == "":
                    break
                brace_depth += inner_stripped.count("{") - inner_stripped.count("}")
                if brace_depth <= 0:
                    collapsed.append(" " * indent + "    // ...")
                    collapsed.append(inner)
                    i += 1
                    break
                i += 1
            else:
                collapsed.append(" " * indent + "    // ...")
        elif _is_class_or_type_line(stripped):
            collapsed.append(line)
            i += 1
        elif stripped.startswith(("//", "/*", "*", "*/", "#")):
            i += 1
        elif not stripped:
            i += 1
        else:
            collapsed.append(line)
            i += 1
        continue
    return "\n".join(collapsed)


def _is_function_start(stripped: str) -> bool:
    keywords = ("function ", "def ", "func ", "fn ", "pub fn ", "async ",
                "static ", "public ", "private ", "protected ", "override ")
    if any(stripped.startswith(kw) for kw in keywords):
        return True
    if re.match(r"^\w+\s*\(", stripped) and "{" in stripped:
        return True
    return False


def _is_class_or_type_line(stripped: str) -> bool:
    return stripped.startswith(("class ", "struct ", "enum ", "interface ",
                                "type ", "typedef ", "const ", "let ", "var ",
                                "export "))


def _strip_license(text: str) -> str:
    return _LICENSE_RE.sub("", text, count=1).lstrip("\n")


# ---------------------------------------------------------------------------
# Callee: signature only
# ---------------------------------------------------------------------------

def _collect_callee_signatures(
    callees: list[str],
    other_files: list[Path],
    extractor: SymbolExtractor,
) -> list[tuple[Path, str, str]]:
    snippets = []
    seen = set()
    for symbol in callees:
        if symbol in seen:
            continue
        result = extractor.find_symbol_definition(symbol, other_files)
        if result is None:
            continue
        fpath, start, end = result
        source = fpath.read_bytes()
        full_code = source[start:end].decode("utf-8", errors="replace")
        sig = _extract_signature(full_code)
        snippets.append((fpath, symbol, sig))
        seen.add(symbol)
    return snippets


def _extract_signature(full_code: str) -> str:
    lines = full_code.split("\n")
    sig_lines = []
    doc_lines = []

    in_doc = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("/**", "///", '"""', "'''", "/*")):
            in_doc = True
            doc_lines.append(line)
            if stripped.endswith(("*/", '"""', "'''")):
                in_doc = False
            continue
        if in_doc:
            doc_lines.append(line)
            if stripped.endswith(("*/", '"""', "'''")):
                in_doc = False
            continue
        if stripped.startswith(("//", "#")) and not sig_lines:
            doc_lines.append(line)
            continue
        break

    first_doc = ""
    if doc_lines:
        for dl in doc_lines:
            text = dl.strip().lstrip("/*#/ ").rstrip("*/# ")
            if text and text not in ("**", ""):
                first_doc = text
                break

    for line in lines[len(doc_lines):]:
        sig_lines.append(line)
        stripped = line.strip()
        if "{" in stripped or ":" in stripped or stripped.endswith(")"):
            break
        if stripped.startswith(("def ", "func ", "function ")):
            break

    sig = "\n".join(sig_lines).rstrip("{").rstrip().rstrip(":")
    if doc_lines:
        doc_block = "\n".join(doc_lines)
        sig = f"{doc_block}\n{sig}"
    elif first_doc:
        sig = f"// {first_doc}\n{sig}"

    return sig


# ---------------------------------------------------------------------------
# Caller: signature + call-site lines only
# ---------------------------------------------------------------------------

MAX_FILES_FOR_CALLER_SEARCH = 50
MAX_CALLERS = 3


def _collect_caller_call_sites(
    func_name: str,
    func_file: Path,
    other_files: list[Path],
    extractor: SymbolExtractor,
    original_source: bytes,
) -> list[tuple[Path, str, str]]:
    if len(other_files) > MAX_FILES_FOR_CALLER_SEARCH:
        return []
    callers = extractor.find_callers(func_name, other_files)
    snippets = []
    seen_names = set()
    for caller in callers[:MAX_CALLERS * 2]:
        if caller.name in seen_names:
            continue
        seen_names.add(caller.name)
        source = caller.file.read_bytes()
        full_code = source[caller.start_byte:caller.end_byte].decode("utf-8", errors="replace")
        snippet = _extract_call_site(full_code, func_name)
        snippets.append((caller.file, caller.name, snippet))
        if len(snippets) >= MAX_CALLERS:
            break
    return snippets


def _extract_call_site(full_code: str, func_name: str) -> str:
    lines = full_code.split("\n")

    sig_line = lines[0] if lines else ""

    call_lines = []
    for i, line in enumerate(lines):
        if func_name in line:
            start = max(0, i - 1)
            end = min(len(lines), i + 2)
            call_lines.extend(lines[start:end])
            call_lines.append("...")
            break

    if call_lines:
        return sig_line + "\n    ...\n" + "\n".join(call_lines)
    return sig_line


# ---------------------------------------------------------------------------
# Requirement Context: doc comment + LLM-generated description
# ---------------------------------------------------------------------------

def _build_requirement_context(func: FunctionInfo, task_dir: Path | None) -> str:
    parts = []

    # 1. 函数签名（从 tree-sitter 提取，可靠）
    if func.signature:
        parts.append(f"## Signature\n```\n{func.signature}\n```")

    # 2. Doc comment（从源码提取）
    if func.doc_comment:
        parts.append(f"## Documentation\n{func.doc_comment}")

    # 3. LLM 生成的描述（如果已预生成）
    if task_dir is not None:
        desc_file = task_dir / "desc.txt"
        if desc_file.exists():
            desc = desc_file.read_text(encoding="utf-8").strip()
            if desc:
                parts.append(f"## Function Description\n{desc}")

    return "\n\n".join(parts)


def _collect_test_snippets(func_name: str, project_dir: Path) -> list[tuple[str, str]]:
    search_roots = []
    for name in ("tests", "blackbox_tests"):
        d = project_dir / name
        if d.is_dir():
            search_roots.append(d)

    snippets: list[tuple[str, str]] = []
    needle_variants = {
        func_name,
        f"{func_name}(",
        f".{func_name}(",
        f"::{func_name}",
    }

    for root in search_roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".go", ".js", ".ts", ".java", ".cpp", ".cc", ".cxx", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            lines = text.splitlines()
            hit = None
            for i, line in enumerate(lines):
                if any(v in line for v in needle_variants):
                    hit = i
                    break
            if hit is None:
                continue
            start = max(0, hit - 3)
            end = min(len(lines), hit + 6)
            snippet = "\n".join(lines[start:end]).strip()
            rel = str(path.relative_to(project_dir))
            snippets.append((rel, snippet))
            if len(snippets) >= MAX_TEST_SNIPPETS:
                return snippets
    return snippets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rel_path(file_path: Path, source_roots: list[Path]) -> str:
    for root in source_roots:
        try:
            return str(file_path.relative_to(root))
        except ValueError:
            continue
    return file_path.name


def _enforce_budget(prompt: str, budget: int) -> str:
    if len(prompt) <= budget:
        return prompt

    sections = prompt.split("\n# ")
    if len(sections) <= 1:
        return prompt[:budget]

    header = sections[0]
    named = {}
    order = []
    for s in sections[1:]:
        title = s.split("\n", 1)[0]
        named[title] = "\n# " + s
        order.append(title)

    cut_priority = ["Relevant Tests", "Call Sites", "Related Definitions", "Function Contract"]
    for title_prefix in cut_priority:
        for key in list(named.keys()):
            if key.startswith(title_prefix):
                del named[key]
                order.remove(key)
        current = header + "".join(named[k] for k in order)
        if len(current) <= budget:
            return current

    target_key = next((k for k in order if k.startswith("Target File")), None)
    if target_key and target_key in named:
        excess = len(header + "".join(named[k] for k in order)) - budget
        content = named[target_key]
        if len(content) > excess + 200:
            named[target_key] = content[:len(content) - excess - 100] + "\n// ... (truncated)\n```\n"

    return (header + "".join(named[k] for k in order))[:budget]
