"""Parse coverage artifacts and map stub byte offsets to line coverage."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def byte_to_line(src_bytes: bytes, byte_offset: int) -> int:
    if byte_offset <= 0:
        return 1
    if byte_offset > len(src_bytes):
        byte_offset = len(src_bytes)
    return src_bytes[:byte_offset].count(b"\n") + 1


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def go_cover_line_hit(cover_out: str | Path, source_basename: str, target_line: int) -> bool | None:
    """Return True if target_line lies in a region with execution count > 0."""
    text = Path(cover_out).read_text(encoding="utf-8", errors="replace")
    pat = re.compile(
        r"^(.+):(\d+)\.(\d+),(\d+)\.(\d+) (\d+) (\d+)\s*$",
    )
    blocks: list[tuple[int, int, int]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("mode:"):
            continue
        m = pat.match(line)
        if not m:
            continue
        file_part, sline, _scol, eline, _ecol, _stmts, count_s = m.groups()
        name = Path(file_part.replace("\\", "/")).name
        if name != source_basename:
            continue
        blocks.append((int(sline), int(eline), int(count_s)))
    if not blocks:
        return None
    for sline_i, eline_i, count in blocks:
        if sline_i <= target_line <= eline_i and count > 0:
            return True
    return False


def go_cover_file_hit(cover_out: str | Path, source_basename: str) -> bool | None:
    """Return True if any block for source_basename has execution count > 0."""
    text = Path(cover_out).read_text(encoding="utf-8", errors="replace")
    pat = re.compile(
        r"^(.+):(\d+)\.(\d+),(\d+)\.(\d+) (\d+) (\d+)\s*$",
    )
    found = False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("mode:"):
            continue
        m = pat.match(line)
        if not m:
            continue
        file_part, _sline, _scol, _eline, _ecol, _stmts, count_s = m.groups()
        name = Path(file_part.replace("\\", "/")).name
        if name != source_basename:
            continue
        found = True
        if int(count_s) > 0:
            return True
    if found:
        return False
    return None


def python_coverage_line_hit(
    coverage_json: Path,
    resolved_rel: str,
    stub_file: str,
    target_line: int,
) -> bool | None:
    data = json.loads(Path(coverage_json).read_text(encoding="utf-8"))
    files = data.get("files") or {}
    basename = Path(resolved_rel).name
    candidates: list[tuple[str, set[int]]] = []
    for path_key, meta in files.items():
        norm = path_key.replace("\\", "/")
        pk = Path(norm).name
        if pk != basename and not norm.endswith(resolved_rel.replace("\\", "/")):
            continue
        executed = meta.get("executed_lines") or []
        candidates.append((path_key, set(int(x) for x in executed)))
    if not candidates:
        return None
    for _pk, lines in candidates:
        if target_line in lines:
            return True
    return False


def python_coverage_file_hit(
    coverage_json: Path,
    resolved_rel: str,
    stub_file: str,
) -> bool | None:
    data = json.loads(Path(coverage_json).read_text(encoding="utf-8"))
    files = data.get("files") or {}
    basename = Path(resolved_rel).name
    found = False
    for path_key, meta in files.items():
        norm = path_key.replace("\\", "/")
        pk = Path(norm).name
        if pk != basename and not norm.endswith(resolved_rel.replace("\\", "/")):
            continue
        found = True
        executed = meta.get("executed_lines") or []
        if executed:
            return True
    if found:
        return False
    return None


def _norm_java_stub_path(stub_rel: str) -> str:
    return stub_rel.replace("\\", "/").lstrip("./")


def jacoco_line_hit(xml_path: Path, stub_rel: str, target_line: int) -> bool | None:
    """Match JaCoCo XML package/sourcefile paths to stub path (e.g. io/foo/Bar.java)."""
    stub_norm = _norm_java_stub_path(stub_rel)
    basename = Path(stub_norm).name
    tree = ET.parse(xml_path)
    root = tree.getroot()

    candidates: list[tuple[int, ET.Element]] = []
    for pkg in root.iter():
        if _local_tag(pkg.tag) != "package":
            continue
        pkg_raw = pkg.get("name") or ""
        if "/" in pkg_raw:
            pkg_name = pkg_raw.replace("\\", "/")
        else:
            pkg_name = pkg_raw.replace(".", "/")
        for sf in pkg:
            if _local_tag(sf.tag) != "sourcefile":
                continue
            sf_name = sf.get("name") or ""
            if pkg_name:
                full = f"{pkg_name.rstrip('/')}/{sf_name}".replace("//", "/")
            else:
                full = sf_name
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
    sf_elem = candidates[0][1]

    line_by_nr: dict[int, int] = {}
    for child in sf_elem:
        if _local_tag(child.tag) != "line":
            continue
        nr_s = child.get("nr")
        if not nr_s:
            continue
        nr = int(nr_s)
        ci = int(child.get("ci") or "0")
        line_by_nr[nr] = ci

    if target_line in line_by_nr:
        return line_by_nr[target_line] > 0
    for delta in (1, -1, 2, -2, 3, -3):
        adj = target_line + delta
        if adj in line_by_nr and line_by_nr[adj] > 0:
            return True
    if line_by_nr:
        return False
    return None


def jacoco_file_hit(xml_path: Path, stub_rel: str) -> bool | None:
    """Return True if any line in the file was covered, False if file is present but
    nothing was covered, None if the file is not found in the JaCoCo report."""
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
    sf_elem = candidates[0][1]

    for child in sf_elem:
        if _local_tag(child.tag) != "line":
            continue
        if int(child.get("ci") or "0") > 0:
            return True
    # File found in report but no lines covered
    return False


def _strip_workspace_prefix(p: str) -> str:
    n = p.replace("\\", "/")
    for prefix in ("/workspace/", "/workspace", "./"):
        if n.startswith(prefix):
            n = n[len(prefix) :].lstrip("/")
            break
    return n


def js_summary_file_hit(summary_json: Path, source_basename: str, stub_rel: str) -> bool | None:
    """Match Jest json-summary keys (/workspace/src/...) to stub paths relative to src/."""
    data = json.loads(Path(summary_json).read_text(encoding="utf-8"))
    stub_norm = stub_rel.replace("\\", "/").lstrip("/")
    best_score = 0
    best_meta: dict | None = None

    for path_key, meta in data.items():
        if path_key == "total":
            continue
        if not isinstance(meta, dict):
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
        basename_hits: list[dict] = []
        for path_key, meta in data.items():
            if path_key == "total" or not isinstance(meta, dict):
                continue
            norm = _strip_workspace_prefix(path_key.replace("\\", "/"))
            if Path(norm).name == source_basename:
                basename_hits.append(meta)
        if len(basename_hits) == 1:
            best_meta = basename_hits[0]

    if best_meta is None:
        return None
    lines = best_meta.get("lines") or {}
    covered = int(lines.get("covered") or 0)
    return covered > 0


def _lcov_load(lcov_info: Path) -> dict[str, dict[int, int]]:
    """Parse lcov.info into {source_file: {line_nr: hit_count}}."""
    result: dict[str, dict[int, int]] = {}
    current: str | None = None
    try:
        text = lcov_info.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("SF:"):
            current = line[3:]
            if current not in result:
                result[current] = {}
        elif line.startswith("DA:") and current is not None:
            parts = line[3:].split(",")
            if len(parts) >= 2:
                try:
                    nr = int(parts[0])
                    count = int(parts[1])
                    result[current][nr] = result[current].get(nr, 0) + count
                except ValueError:
                    pass
        elif line == "end_of_record":
            current = None
    return result


def _lcov_find(
    file_map: dict[str, dict[int, int]], source_basename: str, stub_rel: str
) -> dict[int, int] | None:
    """Find the best matching file entry in the lcov file map."""
    stub_norm = stub_rel.replace("\\", "/").lstrip("./")

    def _path_endswith(long: str, short: str) -> bool:
        if not long.endswith(short):
            return False
        idx = len(long) - len(short)
        return idx == 0 or long[idx - 1] == "/"

    # Collect all candidates; when stub_norm is a plain filename, merge all basename
    # matches so that duplicate copies (e.g. tests/foo.h vs src/foo.h) are combined.
    is_plain_name = "/" not in stub_norm

    exact_matches: list[dict[int, int]] = []   # stub_norm suffix match
    name_matches: list[dict[int, int]] = []    # basename-only match

    for sf, lines in file_map.items():
        sf_norm = sf.replace("\\", "/")
        sf_name = Path(sf_norm).name
        if _path_endswith(sf_norm, stub_norm) or _path_endswith(stub_norm, sf_norm):
            exact_matches.append(lines)
        elif sf_name == source_basename:
            name_matches.append(lines)

    chosen = exact_matches or name_matches
    if not chosen:
        return None

    if len(chosen) == 1:
        return chosen[0]

    # Multiple matches — merge by OR-ing coverage counts
    merged: dict[int, int] = {}
    for lns in chosen:
        for nr, count in lns.items():
            merged[nr] = merged.get(nr, 0) + count
    return merged


def lcov_line_hit(lcov_info: Path, stub_rel: str, target_line: int) -> bool | None:
    """Return True if target_line has hit count > 0 in lcov.info."""
    file_map = _lcov_load(lcov_info)
    if not file_map:
        return None
    source_basename = Path(stub_rel.replace("\\", "/")).name
    lines = _lcov_find(file_map, source_basename, stub_rel)
    if lines is None:
        return None
    if target_line in lines:
        return lines[target_line] > 0
    # Try adjacent lines (C++ has different line numbering for braces/templates,
    # and #ifdef blocks may shift the active implementation by many lines)
    for delta in range(1, 31):
        for sign in (1, -1):
            adj = target_line + sign * delta
            if adj in lines and lines[adj] > 0:
                return True
    if lines:
        return False
    return None


def lcov_file_hit(lcov_info: Path, stub_rel: str) -> bool | None:
    """Return True if any line in the file has hit count > 0."""
    file_map = _lcov_load(lcov_info)
    if not file_map:
        return None
    source_basename = Path(stub_rel.replace("\\", "/")).name
    lines = _lcov_find(file_map, source_basename, stub_rel)
    if lines is None:
        return None
    return any(count > 0 for count in lines.values()) if lines else False
