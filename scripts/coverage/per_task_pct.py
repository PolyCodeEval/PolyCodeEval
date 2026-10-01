"""Compute per-file and per-function line coverage percentages from artifacts."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from coverage.parsers import _lcov_load, _lcov_find, _local_tag, _norm_java_stub_path, _strip_workspace_prefix


CovResult = tuple[int | None, int | None, float | None]  # (covered, total, pct)


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------

_GO_BLOCK_PAT = re.compile(r"^(.+):(\d+)\.(\d+),(\d+)\.(\d+) (\d+) (\d+)\s*$")


def _go_parse_blocks_raw(cover_out: Path) -> list[tuple[str, int, int, int, int]]:
    """Parse cover.out into [(file_path, start_line, end_line, stmts, count), ...]
    Deduplicates by taking max count per block key. file_path is the full path from cover.out."""
    if not cover_out.is_file():
        return []
    text = cover_out.read_text(encoding="utf-8", errors="replace")
    blocks: dict[str, tuple[str, int, int, int, int]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("mode:"):
            continue
        m = _GO_BLOCK_PAT.match(line)
        if not m:
            continue
        file_part, sline, _scol, eline, _ecol, stmts_s, count_s = m.groups()
        file_path = file_part.replace("\\", "/")
        key = m.group(0)[:m.start(6)]
        stmts = int(stmts_s)
        count = int(count_s)
        if key in blocks:
            old = blocks[key]
            blocks[key] = (file_path, int(sline), int(eline), stmts, max(old[4], count))
        else:
            blocks[key] = (file_path, int(sline), int(eline), stmts, count)
    return list(blocks.values())


def _go_match_file(block_path: str, file_basename: str, stub_rel: str) -> bool:
    """Match a cover.out file path against target file.
    stub_rel is the relative path from the dataset (e.g. '_examples/rest/main.go')."""
    block_name = Path(block_path).name
    if block_name != file_basename:
        return False
    if file_basename != "main.go" and "/" not in stub_rel:
        return True
    stub_norm = stub_rel.replace("\\", "/").lstrip("./")
    stub_parts = stub_norm.split("/")
    block_parts = block_path.split("/")
    if len(stub_parts) <= 1:
        return True
    last_stub_part = stub_parts[-2]
    for bp in block_parts[:-1]:
        if last_stub_part in bp:
            return True
    return len(block_parts) == 1


def go_file_line_pct(cover_out: Path, file_basename: str, stub_rel: str = "") -> CovResult:
    blocks = _go_parse_blocks_raw(cover_out)
    total_stmts = 0
    covered_stmts = 0
    found = False
    for fpath, _sl, _el, stmts, count in blocks:
        if not _go_match_file(fpath, file_basename, stub_rel):
            continue
        found = True
        total_stmts += stmts
        if count > 0:
            covered_stmts += stmts
    if not found or total_stmts == 0:
        return None, None, None
    pct = round(covered_stmts / total_stmts * 100, 1)
    return covered_stmts, total_stmts, pct


def go_func_line_pct(cover_out: Path, file_basename: str, start_line: int, end_line: int, stub_rel: str = "") -> CovResult:
    blocks = _go_parse_blocks_raw(cover_out)
    total_stmts = 0
    covered_stmts = 0
    found = False
    for fpath, sl, el, stmts, count in blocks:
        if not _go_match_file(fpath, file_basename, stub_rel):
            continue
        if el < start_line or sl > end_line:
            continue
        found = True
        total_stmts += stmts
        if count > 0:
            covered_stmts += stmts
    if not found or total_stmts == 0:
        return None, None, None
    pct = round(covered_stmts / total_stmts * 100, 1)
    return covered_stmts, total_stmts, pct


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

def python_file_line_pct(coverage_json: Path, resolved_rel: str, stub_file: str) -> CovResult:
    if not coverage_json.is_file():
        return None, None, None
    data = json.loads(coverage_json.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    basename = Path(resolved_rel).name

    for path_key, meta in files.items():
        norm = path_key.replace("\\", "/")
        pk = Path(norm).name
        if pk != basename and not norm.endswith(resolved_rel.replace("\\", "/")):
            continue
        summary = meta.get("summary") or {}
        covered = summary.get("covered_lines")
        total = summary.get("num_statements")
        pct = summary.get("percent_covered")
        if covered is not None and total is not None and int(total) > 0:
            return int(covered), int(total), round(float(pct), 1) if pct is not None else round(int(covered) / int(total) * 100, 1)
    return None, None, None


def python_func_line_pct(
    coverage_json: Path, resolved_rel: str, stub_file: str, start_line: int, end_line: int
) -> CovResult:
    if not coverage_json.is_file():
        return None, None, None
    data = json.loads(coverage_json.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    basename = Path(resolved_rel).name

    for path_key, meta in files.items():
        norm = path_key.replace("\\", "/")
        pk = Path(norm).name
        if pk != basename and not norm.endswith(resolved_rel.replace("\\", "/")):
            continue
        executed = set(int(x) for x in (meta.get("executed_lines") or []))
        missing = set(int(x) for x in (meta.get("missing_lines") or []))
        all_lines = executed | missing
        func_lines = {ln for ln in all_lines if start_line <= ln <= end_line}
        if not func_lines:
            return None, None, None
        covered = len(func_lines & executed)
        total = len(func_lines)
        pct = round(covered / total * 100, 1)
        return covered, total, pct
    return None, None, None


# ---------------------------------------------------------------------------
# Java (JaCoCo XML)
# ---------------------------------------------------------------------------

def _jacoco_find_sourcefile(xml_path: Path, stub_rel: str) -> ET.Element | None:
    stub_norm = _norm_java_stub_path(stub_rel)
    basename = Path(stub_norm).name
    tree = ET.parse(xml_path)
    root = tree.getroot()

    candidates: list[tuple[int, ET.Element]] = []
    for pkg in root.iter():
        if _local_tag(pkg.tag) != "package":
            continue
        pkg_raw = pkg.get("name") or ""
        pkg_name = pkg_raw.replace("\\", "/") if "/" in pkg_raw else pkg_raw.replace(".", "/")
        for sf in pkg:
            if _local_tag(sf.tag) != "sourcefile":
                continue
            sf_name = sf.get("name") or ""
            full = f"{pkg_name.rstrip('/')}/{sf_name}".replace("//", "/") if pkg_name else sf_name
            full = full.replace("\\", "/")
            score = 0
            if full == stub_norm or stub_norm.endswith(full) or full.endswith(stub_norm):
                score = len(full)
            elif sf_name == basename:
                score = 1
            else:
                continue
            candidates.append((score, sf))

    if not candidates:
        for elem in root.iter():
            if _local_tag(elem.tag) != "sourcefile":
                continue
            sf_name = elem.get("name") or ""
            if sf_name == basename or stub_norm.endswith(sf_name):
                candidates.append((1 if sf_name == basename else 5, elem))

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def java_file_line_pct(jacoco_xml: Path, stub_rel: str) -> CovResult:
    if not jacoco_xml.is_file():
        return None, None, None
    try:
        sf_elem = _jacoco_find_sourcefile(jacoco_xml, stub_rel)
    except ET.ParseError:
        return None, None, None
    if sf_elem is None:
        return None, None, None
    covered = 0
    missed = 0
    for child in sf_elem:
        if _local_tag(child.tag) != "line":
            continue
        ci = int(child.get("ci") or "0")
        mi = int(child.get("mi") or "0")
        if ci > 0:
            covered += 1
        elif mi > 0:
            missed += 1
    total = covered + missed
    if total == 0:
        return None, None, None
    pct = round(covered / total * 100, 1)
    return covered, total, pct


def java_func_line_pct(jacoco_xml: Path, stub_rel: str, start_line: int, end_line: int) -> CovResult:
    if not jacoco_xml.is_file():
        return None, None, None
    try:
        sf_elem = _jacoco_find_sourcefile(jacoco_xml, stub_rel)
    except ET.ParseError:
        return None, None, None
    if sf_elem is None:
        return None, None, None
    covered = 0
    missed = 0
    for child in sf_elem:
        if _local_tag(child.tag) != "line":
            continue
        nr = int(child.get("nr") or "0")
        if nr < start_line or nr > end_line:
            continue
        ci = int(child.get("ci") or "0")
        mi = int(child.get("mi") or "0")
        if ci > 0:
            covered += 1
        elif mi > 0:
            missed += 1
    total = covered + missed
    if total == 0:
        return None, None, None
    pct = round(covered / total * 100, 1)
    return covered, total, pct


# ---------------------------------------------------------------------------
# C++ (lcov)
# ---------------------------------------------------------------------------

def cpp_file_line_pct(lcov_info: Path, stub_rel: str) -> CovResult:
    if not lcov_info.is_file():
        return None, None, None
    file_map = _lcov_load(lcov_info)
    if not file_map:
        return None, None, None
    source_basename = Path(stub_rel.replace("\\", "/")).name
    lines = _lcov_find(file_map, source_basename, stub_rel)
    if lines is None or not lines:
        return None, None, None
    total = len(lines)
    covered = sum(1 for c in lines.values() if c > 0)
    pct = round(covered / total * 100, 1)
    return covered, total, pct


def cpp_func_line_pct(lcov_info: Path, stub_rel: str, start_line: int, end_line: int) -> CovResult:
    if not lcov_info.is_file():
        return None, None, None
    file_map = _lcov_load(lcov_info)
    if not file_map:
        return None, None, None
    source_basename = Path(stub_rel.replace("\\", "/")).name
    lines = _lcov_find(file_map, source_basename, stub_rel)
    if lines is None:
        return None, None, None
    func_lines = {nr: count for nr, count in lines.items() if start_line <= nr <= end_line}
    if not func_lines:
        return None, None, None
    total = len(func_lines)
    covered = sum(1 for c in func_lines.values() if c > 0)
    pct = round(covered / total * 100, 1)
    return covered, total, pct


# ---------------------------------------------------------------------------
# JavaScript (coverage-summary.json)
# ---------------------------------------------------------------------------

def js_file_line_pct(summary_json: Path, source_basename: str, stub_rel: str) -> CovResult:
    if not summary_json.is_file():
        return None, None, None
    try:
        data = json.loads(summary_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None, None

    stub_norm = stub_rel.replace("\\", "/").lstrip("/")
    best_score = 0
    best_meta: dict | None = None

    for path_key, meta in data.items():
        if path_key == "total" or not isinstance(meta, dict):
            continue
        norm = _strip_workspace_prefix(path_key.replace("\\", "/"))
        name_ok = Path(norm).name == source_basename
        suffix_ok = norm.endswith(stub_norm) or stub_norm.endswith(norm)
        src_suffix = norm.split("src/", 1)[-1] if "src/" in norm else norm
        stub_suffix = stub_norm.split("src/", 1)[-1] if "src/" in stub_norm else stub_norm
        loose_ok = src_suffix == stub_suffix or src_suffix.endswith(stub_suffix)
        if not (name_ok or suffix_ok or loose_ok):
            continue
        score = 0
        if norm.endswith(stub_norm):
            score += 100 + len(norm)
        elif loose_ok:
            score += 50
        elif name_ok:
            score += 1
        if score > best_score:
            best_score = score
            best_meta = meta

    if best_meta is None:
        return None, None, None
    lines = best_meta.get("lines") or {}
    covered = lines.get("covered")
    total = lines.get("total")
    pct = lines.get("pct")
    if covered is not None and total is not None and int(total) > 0:
        return int(covered), int(total), round(float(pct), 1) if pct is not None else round(int(covered) / int(total) * 100, 1)
    return None, None, None
