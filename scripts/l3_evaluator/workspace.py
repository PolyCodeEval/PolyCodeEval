"""Workspace — manages the temporary directory lifecycle for a single L3 task evaluation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import textwrap
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_copytree(src: Path, dst: Path) -> None:
    """Copy a tree while skipping broken symlinks."""

    def _ignore(path: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        path_obj = Path(path)
        for name in names:
            candidate = path_obj / name
            if not candidate.is_symlink():
                continue
            target = os.readlink(candidate)
            resolved = (candidate.parent / target).resolve() if not os.path.isabs(target) else Path(target)
            if not resolved.exists():
                ignored.add(name)
        return ignored

    shutil.copytree(src, dst, ignore=_ignore)


def _resolve_file(src_dir: Path, rel_path: str) -> str:
    """Resolve a potentially incorrect relative path to the actual file in src_dir.

    Dataset paths in stub_info.file / hollowed_files may not match the real
    filesystem layout.  Common mismatches:
      - Python: 'src/foo.py' when actual is 'foo.py', or 'foo.py' when actual
        is 'pkg/foo.py'
      - Java: 'com/pkg/Foo.java' when actual is 'src/main/java/com/pkg/Foo.java'
      - C++: 'foo.cpp' when actual is 'subdir/foo.cpp'

    Strategy:
      1. If the path exists as-is, return it unchanged.
      2. Try stripping a leading 'src/' prefix (Python pattern A).
      3. Search for the filename in src_dir; if exactly one match, use it.
         If multiple matches, prefer the one whose path ends with the given
         rel_path suffix.
    """
    if (src_dir / rel_path).exists():
        return rel_path

    # Pattern A: strip leading 'src/' prefix
    if rel_path.startswith("src/"):
        stripped = rel_path[len("src/"):]
        if (src_dir / stripped).exists():
            return stripped

    # Search by filename (or by trailing path segments for multi-component paths)
    target = Path(rel_path)
    fname = target.name
    matches = list(src_dir.rglob(fname))

    if not matches:
        # Last resort: return original and let downstream fail with a clear error
        return rel_path

    if len(matches) == 1:
        return str(matches[0].relative_to(src_dir))

    # Multiple matches — prefer the one ending with the given rel_path
    for m in matches:
        m_rel = str(m.relative_to(src_dir))
        if m_rel.endswith(rel_path) or m_rel.endswith(str(target)):
            return m_rel

    # Fall back to first match
    return str(matches[0].relative_to(src_dir))


class Workspace:

    def __init__(self, task_dir: Path):
        self.task_dir = task_dir
        self.run_config = _load_json(task_dir / "run_config.json")
        self._task = _load_json(task_dir / "task.json")
        self.tmp_dir: Path | None = None

    def build(self) -> None:
        """Copy src/ and tests/ to a temp dir."""
        src_dir = (self.task_dir / self.run_config["src_dir"]).resolve()
        self._src_dir = src_dir
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="pce_l3_"))
        shutil.copytree(src_dir, self.tmp_dir / "src")
        project_dir = src_dir.parent
        tests_dir = project_dir / "tests"
        if tests_dir.is_dir():
            _safe_copytree(tests_dir, self.tmp_dir / "tests")
        blackbox_dir = project_dir / "blackbox_tests"
        if blackbox_dir.is_dir():
            _safe_copytree(blackbox_dir, self.tmp_dir / "blackbox_tests")

    def backfill(self, function_body: str) -> None:
        """Splice function_body into the workspace using byte offsets from stub_info."""
        stub_info = self._task["stub_info"]
        resolved = _resolve_file(self._src_dir, stub_info["file"])

        hollowed = (self.task_dir / "hollowed_files" / stub_info["file"]).read_bytes()
        hollowed_text = hollowed.decode("utf-8")
        original = (self.tmp_dir / "src" / resolved).read_bytes()

        body_start = stub_info["body_start_byte"]
        lang = stub_info.get("lang", "")
        if lang == "python":
            replace_start, replace_end = _stub_line_bounds(
                hollowed,
                body_start,
                stub_info.get("stub", ""),
            )
            body_bytes = _format_python_backfill(
                function_body,
                hollowed_text,
                stub_info.get("stub", ""),
                stub_info.get("func_name", ""),
            )
        elif hollowed[body_start:body_start+1] == b"{":
            replace_start, replace_end = _stub_line_bounds(
                hollowed,
                body_start,
                stub_info.get("stub", ""),
            )
            body_bytes = _format_brace_language_backfill(
                function_body,
                hollowed_text,
                stub_info.get("stub", ""),
            )
        else:
            replace_start, replace_end = _stub_line_bounds(
                hollowed,
                body_start,
                stub_info.get("stub", ""),
            )
            body_bytes = function_body.encode("utf-8")

        filled = hollowed[:replace_start] + body_bytes + hollowed[replace_end:]
        (self.tmp_dir / "src" / resolved).write_bytes(filled)
        self._last_backfilled_relpath = resolved
        self._last_backfilled_bytes = filled

    def cleanup(self) -> None:
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
            self.tmp_dir = None

    def export_last_backfilled(self, output_path: Path) -> None:
        if not hasattr(self, "_last_backfilled_bytes") or self._last_backfilled_bytes is None:
            raise RuntimeError("No backfilled content available to export")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self._last_backfilled_bytes)


def _format_brace_language_backfill(
    function_body: str,
    hollowed_text: str,
    stub: str,
) -> bytes:
    body = _normalize_generated_brace_body(function_body).strip("\n")
    if not body:
        return b""

    lines = body.splitlines()
    if not lines:
        return b""

    stub_indent = _find_stub_indent(hollowed_text, stub)

    normalized = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        normalized.append(f"{stub_indent}{line.rstrip()}")
    return ("\n".join(normalized).rstrip() + "\n").encode("utf-8")


def _format_python_backfill(
    function_body: str,
    hollowed_text: str,
    stub: str,
    func_name: str,
) -> bytes:
    body = function_body.strip("\n")
    if not body:
        return b""

    lines = body.splitlines()
    if not any(line.strip() for line in lines):
        return b""

    def_indent = _find_python_def_indent(hollowed_text, func_name)
    def_width = _indent_width(def_indent)
    normalized: list[str] = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        normalized.append((" " * def_width) + line)
    return ("\n".join(normalized).rstrip() + "\n").encode("utf-8")


def _find_stub_indent(hollowed_text: str, stub: str) -> str:
    for line in hollowed_text.splitlines():
        if line.strip() == stub:
            return line[: len(line) - len(line.lstrip(" \t"))]
    return ""


def _find_python_def_indent(hollowed_text: str, func_name: str) -> str:
    for line in hollowed_text.splitlines():
        stripped = line.lstrip(" \t")
        if stripped.startswith(f"def {func_name}(") or stripped.startswith(f"async def {func_name}("):
            return line[: len(line) - len(stripped)]
    return ""


def _stub_line_bounds(
    hollowed_bytes: bytes,
    body_start_byte: int,
    stub: str,
) -> tuple[int, int]:
    data = hollowed_bytes
    pos = body_start_byte
    while pos < len(data):
        line_start = data.rfind(b"\n", 0, pos)
        line_start = 0 if line_start == -1 else line_start + 1
        line_end = data.find(b"\n", pos)
        line_end = len(data) if line_end == -1 else line_end
        line = data[line_start:line_end].decode("utf-8", errors="replace")
        if line.strip() == stub:
            replace_end = line_end if line_end == len(data) else line_end + 1
            return line_start, replace_end
        pos = line_end + 1
    raise ValueError(f"Failed to locate stub line {stub!r} after body_start")


def _normalize_generated_brace_body(function_body: str) -> str:
    body = textwrap.dedent(function_body).strip("\n")
    if not body:
        return ""

    stripped = body.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        inner = stripped[1:-1].strip("\n")
        body = inner

    lines = body.splitlines()
    if not lines:
        return ""

    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""

    min_width = min(_indent_width(line) for line in non_empty)
    normalized: list[str] = []
    for line in lines:
        if not line.strip():
            normalized.append("")
            continue
        normalized.append(_strip_indent_width(line, min_width))
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
