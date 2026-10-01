"""Extract overall line coverage percentage from native coverage artifacts."""

from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def go_coverage_pct(cover_out: Path) -> float | None:
    """Parse go cover.out and return overall statement coverage percentage.

    Runs `go tool cover -func=cover.out` inside the container is not feasible
    here (we're on the host), so we compute it directly from the cover.out format:
      file:sline.col,eline.col stmts count
    Coverage = (blocks with count>0 weighted by stmts) / total stmts * 100

    When -coverpkg=./... is used, the same block may appear multiple times
    (once per test binary). We take the max count per block to avoid
    undercounting coverage.
    """
    if not cover_out.is_file():
        return None
    text = cover_out.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"^(.+:\d+\.\d+,\d+\.\d+) (\d+) (\d+)\s*$")
    # key -> (stmts, max_count)
    blocks: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("mode:"):
            continue
        m = pat.match(line)
        if not m:
            continue
        key = m.group(1)
        stmts = int(m.group(2))
        count = int(m.group(3))
        if key in blocks:
            blocks[key] = (stmts, max(blocks[key][1], count))
        else:
            blocks[key] = (stmts, count)
    total_stmts = sum(s for s, _ in blocks.values())
    covered_stmts = sum(s for s, c in blocks.values() if c > 0)
    if total_stmts == 0:
        return None
    return round(covered_stmts / total_stmts * 100, 1)


def python_coverage_pct(coverage_json: Path) -> float | None:
    """Extract percent_covered from pytest-cov JSON output."""
    if not coverage_json.is_file():
        return None
    try:
        data = json.loads(coverage_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    totals = data.get("totals") or {}
    pct = totals.get("percent_covered")
    if pct is not None:
        return round(float(pct), 1)
    # Fallback: compute from covered_lines / num_statements
    covered = totals.get("covered_lines")
    total = totals.get("num_statements")
    if covered is not None and total and int(total) > 0:
        return round(int(covered) / int(total) * 100, 1)
    return None


def java_coverage_pct(jacoco_xml: Path) -> float | None:
    """Parse JaCoCo XML and return overall line coverage percentage."""
    if not jacoco_xml.is_file():
        return None
    try:
        tree = ET.parse(jacoco_xml)
        root = tree.getroot()
    except ET.ParseError:
        return None

    def local_tag(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    missed = 0
    covered = 0
    # Look for top-level <counter type="LINE"> in the report element
    for elem in root:
        if local_tag(elem.tag) == "counter" and elem.get("type") == "LINE":
            missed += int(elem.get("missed") or 0)
            covered += int(elem.get("covered") or 0)
    total = missed + covered
    if total == 0:
        # Try summing across all packages
        for elem in root.iter():
            if local_tag(elem.tag) == "counter" and elem.get("type") == "LINE":
                missed += int(elem.get("missed") or 0)
                covered += int(elem.get("covered") or 0)
        total = missed + covered
    if total == 0:
        return None
    return round(covered / total * 100, 1)


def js_coverage_pct(summary_json: Path) -> float | None:
    """Extract total line coverage percentage from Jest coverage-summary.json."""
    if not summary_json.is_file():
        return None
    try:
        data = json.loads(summary_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    total = data.get("total") or {}
    lines = total.get("lines") or {}
    pct = lines.get("pct")
    if pct is not None:
        try:
            return round(float(pct), 1)
        except (TypeError, ValueError):
            pass
    return None


def cpp_coverage_pct(lcov_info: Path) -> float | None:
    """Parse lcov.info and return overall line coverage percentage.

    lcov.info format uses DA:<line>,<count> entries.
    LF:/LH: summary lines may not be present in all lcov versions;
    fall back to counting DA: entries directly.
    """
    if not lcov_info.is_file():
        return None
    try:
        text = lcov_info.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # Try LF:/LH: summary lines first
    total_lf = 0
    total_lh = 0
    has_summary = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("LF:"):
            try:
                total_lf += int(line[3:])
                has_summary = True
            except ValueError:
                pass
        elif line.startswith("LH:"):
            try:
                total_lh += int(line[3:])
            except ValueError:
                pass
    if has_summary and total_lf > 0:
        return round(total_lh / total_lf * 100, 1)
    # Fallback: count DA: entries
    lines_found = 0
    lines_hit = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("DA:"):
            parts = line[3:].split(",")
            if len(parts) >= 2:
                try:
                    count = int(parts[1])
                    lines_found += 1
                    if count > 0:
                        lines_hit += 1
                except ValueError:
                    pass
    if lines_found == 0:
        return None
    return round(lines_hit / lines_found * 100, 1)


def extract_line_coverage_pct(language: str, cov_dir: Path) -> tuple[float | None, int | None, int | None]:
    """Return (pct, lines_covered, lines_total) from coverage artifacts in cov_dir.

    Returns (None, None, None) if artifacts are missing or language unsupported.
    """
    lang = language.lower()
    if lang == "go":
        cover_out = cov_dir / "cover.out"
        pct = go_coverage_pct(cover_out)
        if pct is None:
            return None, None, None
        # Recompute covered/total from cover.out (deduplicating blocks)
        text = cover_out.read_text(encoding="utf-8", errors="replace") if cover_out.is_file() else ""
        pat = re.compile(r"^(.+:\d+\.\d+,\d+\.\d+) (\d+) (\d+)\s*$")
        blocks: dict[str, tuple[int, int]] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("mode:"):
                continue
            m = pat.match(line)
            if m:
                key = m.group(1)
                stmts = int(m.group(2))
                count = int(m.group(3))
                if key in blocks:
                    blocks[key] = (stmts, max(blocks[key][1], count))
                else:
                    blocks[key] = (stmts, count)
        total_s = sum(s for s, _ in blocks.values())
        covered_s = sum(s for s, c in blocks.values() if c > 0)
        return pct, covered_s, total_s

    if lang == "python":
        coverage_json = cov_dir / "coverage.json"
        pct = python_coverage_pct(coverage_json)
        if pct is None:
            return None, None, None
        try:
            data = json.loads(coverage_json.read_text(encoding="utf-8"))
            totals = data.get("totals") or {}
            covered = totals.get("covered_lines")
            total = totals.get("num_statements")
            if covered is not None and total is not None:
                return pct, int(covered), int(total)
        except (json.JSONDecodeError, OSError):
            pass
        return pct, None, None

    if lang == "java":
        # Find jacoco xml in cov_dir or project dir
        for name in ("jacoco.xml", "jacocoTestReport.xml"):
            xml_path = cov_dir / name
            if xml_path.is_file():
                pct = java_coverage_pct(xml_path)
                if pct is not None:
                    # Compute covered/total
                    try:
                        tree = ET.parse(xml_path)
                        root = tree.getroot()
                        def local_tag(tag: str) -> str:
                            return tag.rsplit("}", 1)[-1] if "}" in tag else tag
                        missed = covered_n = 0
                        for elem in root:
                            if local_tag(elem.tag) == "counter" and elem.get("type") == "LINE":
                                missed += int(elem.get("missed") or 0)
                                covered_n += int(elem.get("covered") or 0)
                        total = missed + covered_n
                        if total > 0:
                            return pct, covered_n, total
                    except ET.ParseError:
                        pass
                    return pct, None, None
        return None, None, None

    if lang in ("javascript", "typescript"):
        summary_json = cov_dir / "coverage-summary.json"
        pct = js_coverage_pct(summary_json)
        if pct is None:
            return None, None, None
        try:
            data = json.loads(summary_json.read_text(encoding="utf-8"))
            total_data = data.get("total") or {}
            lines = total_data.get("lines") or {}
            covered = lines.get("covered")
            total = lines.get("total")
            if covered is not None and total is not None:
                return pct, int(covered), int(total)
        except (json.JSONDecodeError, OSError):
            pass
        return pct, None, None

    if lang == "cpp":
        lcov_info = cov_dir / "lcov.info"
        pct = cpp_coverage_pct(lcov_info)
        if pct is None:
            return None, None, None
        try:
            text = lcov_info.read_text(encoding="utf-8", errors="replace")
            # Try LF:/LH: first
            total_lf = total_lh = 0
            has_summary = False
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("LF:"):
                    total_lf += int(line[3:])
                    has_summary = True
                elif line.startswith("LH:"):
                    total_lh += int(line[3:])
            if has_summary and total_lf > 0:
                return pct, total_lh, total_lf
            # Fallback: count DA: entries
            lines_found = lines_hit = 0
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("DA:"):
                    parts = line[3:].split(",")
                    if len(parts) >= 2:
                        try:
                            lines_found += 1
                            if int(parts[1]) > 0:
                                lines_hit += 1
                        except ValueError:
                            pass
            if lines_found > 0:
                return pct, lines_hit, lines_found
        except (OSError, ValueError):
            pass
        return pct, None, None

    return None, None, None
