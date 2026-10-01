"""Orchestrate per-project coverage runs (Docker + parsers) for L0–L3."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
_REPO = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_REPO / "docker") not in sys.path:
    sys.path.insert(0, str(_REPO / "docker"))

from l3_evaluator.workspace import _resolve_file  # noqa: E402
from runner_lib import (  # noqa: E402
    discover_projects,
    docker_command,
    load_json,
    resolve_project_path,
)

from coverage.commands import augment_for_coverage  # noqa: E402
from coverage.parsers import (  # noqa: E402
    byte_to_line,
    go_cover_file_hit,
    go_cover_line_hit,
    jacoco_file_hit,
    jacoco_line_hit,
    js_summary_file_hit,
    lcov_file_hit,
    lcov_line_hit,
    python_coverage_file_hit,
    python_coverage_line_hit,
)
from coverage.percentage import extract_line_coverage_pct  # noqa: E402


# ---------------------------------------------------------------------------
# Task discovery helpers
# ---------------------------------------------------------------------------

def _is_task_dir(d: Path, level: str | None = None) -> bool:
    """Return True if d is a valid task directory, optionally filtered by level prefix."""
    if not d.is_dir() or not (d / "task.json").is_file():
        return False
    if level is None:
        return d.name.startswith(("L0_", "L1_", "L2_", "L3_"))
    return d.name.startswith(f"{level}_")


def coverage_results_subdir(config_language: str) -> str:
    lang = (config_language or "").lower()
    if lang in ("javascript", "typescript"):
        return "javascript"
    return lang


def discover_projects_with_tasks(language: str | None = None, level: str | None = None) -> list[Path]:
    projects: list[Path] = []
    for project_dir in discover_projects(language):
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            continue
        if any(_is_task_dir(x, level) for x in tasks_dir.iterdir()):
            projects.append(project_dir)
    return projects


def resolve_cli_project(project: str) -> Path:
    raw = Path(project)
    if raw.is_absolute():
        return raw.resolve()
    cand = (_REPO / raw).resolve()
    if cand.is_dir() and (cand / "config.json").is_file():
        return cand
    return resolve_project_path(project).resolve()


def load_stub_rows(project_dir: Path, level: str | None = None) -> list[tuple[str, str, dict]]:
    """Return [(task_name, task_level, stub_info), ...] for all matching tasks."""
    rows: list[tuple[str, str, dict]] = []
    tasks_dir = project_dir / "tasks"
    if not tasks_dir.is_dir():
        return rows
    for d in sorted(tasks_dir.iterdir()):
        if not _is_task_dir(d, level):
            continue
        task_level = d.name.split("_")[0]  # L0, L1, L2, or L3
        task = load_json(d / "task.json")
        stub = task.get("stub_info") or {}
        rows.append((d.name, task_level, stub))
    return rows


# ---------------------------------------------------------------------------
# Shell script builder
# ---------------------------------------------------------------------------

def _build_shell(
    install: str,
    test: str,
    *,
    language: str | None = None,
    blackbox_dir: Path | None = None,
) -> str:
    parts = ["mkdir -p /workspace/coverage_out"]
    if install.strip():
        parts.append(f"cd /workspace && {{ {install.strip()}; }}")
    if test.strip():
        parts.append(f"cd /workspace && {{ {test.strip()}; }}")
    # For Java: save JaCoCo XML to coverage_out before blackbox tests can overwrite it
    if language == "java":
        parts.append(
            "find /workspace/src -name 'jacocoTestReport.xml' -o -name 'jacoco.xml' 2>/dev/null | "
            "grep -v '/coverage_out/' | head -1 | xargs -I{} cp {} /workspace/coverage_out/ 2>/dev/null || true"
        )
    if blackbox_dir is not None:
        blackbox_cmd = "sh /workspace/blackbox_tests/run_tests.sh"
        if language == "python":
            blackbox_cmd = (
                "PYTHONPATH=/workspace/src "
                "PYTEST_ADDOPTS='--cov=src --cov-append "
                "--cov-report=json:/workspace/coverage_out/coverage.json' "
                "sh /workspace/blackbox_tests/run_tests.sh"
            )
        parts.append(f"if [ -f /workspace/blackbox_tests/run_tests.sh ]; then {blackbox_cmd}; fi")
    return "set -eu; " + " && ".join(parts)


def _build_go_shell(install: str, test: str, *, has_blackbox: bool = False) -> str:
    parts = ["mkdir -p /workspace/coverage_out"]
    if install.strip():
        parts.append(f"cd /workspace && {{ {install.strip()}; }}")

    copy_parts = [
        "cd /workspace",
        'find /workspace/tests -type f -name "*_test.go" | while read -r f; do '
        'rel=${f#/workspace/tests/}; '
        'dest=/workspace/src/${rel}; '
        'mkdir -p "$(dirname "$dest")"; '
        'cp "$f" "$dest"; '
        "done",
    ]
    if has_blackbox:
        copy_parts.append(
            'find /workspace/blackbox_tests -type f -name "*_test.go" | while read -r f; do '
            'rel=${f#/workspace/blackbox_tests/}; '
            'dest=/workspace/src/${rel}; '
            'mkdir -p "$(dirname "$dest")"; '
            'cp "$f" "$dest"; '
            "done"
        )
    parts.append(" && ".join(copy_parts))

    # Run the root module coverage command plus any nested Go modules under src/.
    parts.append(
        "cd /workspace/src && { "
        "go test -coverprofile=/workspace/coverage_out/cover_root.out -coverpkg=./... ./...; "
        "}"
    )
    parts.append(
        'find /workspace/src -mindepth 2 -name go.mod | while read -r mod; do '
        'moddir=$(dirname "$mod"); '
        'rel=${moddir#/workspace/src/}; '
        'safe=$(printf "%s" "$rel" | tr "/" "_"); '
        '(cd "$moddir" && go mod download && '
        'go test -coverprofile="/workspace/coverage_out/cover_${safe}.out" -coverpkg=./... ./...); '
        "done"
    )
    parts.append(
        'cd /workspace/coverage_out && { '
        'echo "mode: set" > cover.out; '
        'for f in cover_*.out; do [ -f "$f" ] && tail -n +2 "$f" >> cover.out; done; '
        "}"
    )
    return "set -eu; " + " && ".join(parts)


# ---------------------------------------------------------------------------
# JaCoCo XML discovery
# ---------------------------------------------------------------------------

def _iter_jacoco_report_xmls(project_dir: Path) -> list[Path]:
    found: list[Path] = []
    for p in project_dir.rglob("*.xml"):
        ln = p.name.lower()
        if ln not in ("jacoco.xml", "jacocotestreport.xml"):
            continue
        sp = p.as_posix().lower()
        if ".m2/" in sp or "node_modules" in sp:
            continue
        if "/target/classes/" in sp or "/target/generated-sources/" in sp:
            continue
        try:
            if not p.is_file() or p.stat().st_size < 16:
                continue
        except OSError:
            continue
        found.append(p)
    return found


def _jacoco_candidate_rank(path: Path) -> tuple[int, int]:
    sp = path.as_posix().lower()
    name = path.name.lower()
    if "/coverage_out/" in sp:
        tier = 0  # anything in coverage_out/ is highest priority
    elif name == "jacoco.xml" and "/target/site/jacoco/" in sp:
        tier = 0
    elif name == "jacocotestreport.xml" and "/build/reports/jacoco/" in sp:
        tier = 1
    elif name == "jacoco.xml" and "/build/reports/jacoco/" in sp:
        tier = 2
    elif name == "jacocotestreport.xml" and "/target/" in sp:
        tier = 3
    elif "/target/" in sp or "/build/" in sp:
        tier = 5
    else:
        tier = 9
    try:
        sz = path.stat().st_size
    except OSError:
        sz = 0
    return (tier, -sz)


def _find_jacoco_xml(project_dir: Path) -> Path | None:
    cands = _iter_jacoco_report_xmls(project_dir)
    if not cands:
        return None
    cands.sort(key=_jacoco_candidate_rank)
    return cands[0]


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

def _docker_timeout_seconds(language: str, project_name: str) -> int:
    if language == "java":
        return 900
    if language in ("javascript", "typescript"):
        if project_name == "babel-parser":
            return 3600
        return 1800
    return 600


# ---------------------------------------------------------------------------
# Per-task coverage check
# ---------------------------------------------------------------------------

def _check_task_coverage(
    task_name: str,
    task_level: str,
    stub: dict,
    language: str,
    src_root: Path,
    cov_dir: Path,
    exit_ok: bool,
    java_jacoco_xml: Path | None,
) -> bool | None:
    """Return True/False/None for whether the task's target is covered."""
    file_ = stub.get("file") or ""
    body_start = stub.get("body_start_byte")
    body_end = stub.get("body_end_byte")

    # For Go and Python, coverage artifacts may exist even if tests fail (partial runs).
    # For Java, we need a successful run to get JaCoCo XML.
    # For JS, same as Java.
    has_artifacts = _has_coverage_artifacts(language, cov_dir, java_jacoco_xml)
    can_check = exit_ok or (has_artifacts and language in ("go", "python", "java", "cpp"))

    # L1 tasks: check if any hollowed file is covered (file-level)
    if task_level == "L1":
        hollowed_files = (
            stub.get("hollowed_files")
            or task_name.startswith("L1_") and []
            or []
        )
        if not hollowed_files:
            # Older task schemas keep hollowed_files at the task root, not in stub_info.
            # Preserve compatibility by looking at the original task payload when present.
            task_path = src_root.parent / "tasks" / task_name / "task.json"
            if task_path.is_file():
                try:
                    task_payload = load_json(task_path)
                    hollowed_files = task_payload.get("hollowed_files") or []
                except Exception:
                    hollowed_files = []
        hollowed_files = hollowed_files or (stub.get("file") and [stub["file"]]) or []
        if not hollowed_files or not can_check:
            return None
        # For L1, return True if at least one hollowed file has any coverage
        saw_false = False
        for hf in hollowed_files:
            resolved = _resolve_file(src_root, hf) if src_root.is_dir() else hf
            src_path = src_root / resolved
            if not src_path.is_file():
                continue
            if language == "python":
                pj = cov_dir / "coverage.json"
                covered_val = (
                    python_coverage_file_hit(pj, resolved, hf) if pj.is_file() else None
                )
            elif language == "go":
                gout = cov_dir / "cover.out"
                covered_val = (
                    go_cover_file_hit(gout, Path(resolved).name) if gout.is_file() else None
                )
            elif language == "java" and java_jacoco_xml is not None:
                covered_val = jacoco_file_hit(java_jacoco_xml, hf)
            elif language == "cpp":
                lcov_info = cov_dir / "lcov.info"
                covered_val = lcov_file_hit(lcov_info, hf) if lcov_info.is_file() else None
            else:
                # Use line 1 as a coarse proxy for non-Python languages until a file-level
                # parser is available.
                covered_val = _check_line_coverage(
                    language, resolved, hf, 1, cov_dir, java_jacoco_xml
                )
            if covered_val is True:
                return True
            if covered_val is False:
                saw_false = True
        return False if saw_false else None

    # L2 tasks: check if the target file is covered (file-level, line 1 proxy)
    if task_level == "L2":
        if not file_ or not can_check:
            return None
        resolved = _resolve_file(src_root, file_) if src_root.is_dir() else file_
        src_path = src_root / resolved
        if not src_path.is_file():
            return None
        if language == "python":
            pj = cov_dir / "coverage.json"
            if pj.is_file():
                return python_coverage_file_hit(pj, resolved, file_)
            return None
        if language == "go":
            gout = cov_dir / "cover.out"
            if gout.is_file():
                return go_cover_file_hit(gout, Path(resolved).name)
            return None
        # Java: use file-level hit (any covered line) instead of line-1 proxy
        if language == "java" and java_jacoco_xml is not None:
            return jacoco_file_hit(java_jacoco_xml, file_)
        if language == "cpp":
            lcov_info = cov_dir / "lcov.info"
            if lcov_info.is_file():
                return lcov_file_hit(lcov_info, file_)
            return None
        return _check_line_coverage(language, resolved, file_, 1, cov_dir, java_jacoco_xml)

    # L3 tasks: check specific function body start line
    if task_level == "L3":
        if not file_ or body_start is None or not can_check:
            return None
        resolved = _resolve_file(src_root, file_) if src_root.is_dir() else file_
        src_path = src_root / resolved
        if not src_path.is_file():
            return None
        src_bytes = src_path.read_bytes()
        start_line = byte_to_line(src_bytes, int(body_start))
        end_byte = int(body_end) - 1 if body_end is not None else int(body_start)
        end_byte = max(int(body_start), end_byte)
        end_line = byte_to_line(src_bytes, end_byte)

        saw_false = False
        for target_line in range(start_line, end_line + 1):
            covered_val = _check_line_coverage(
                language,
                resolved,
                file_,
                target_line,
                cov_dir,
                java_jacoco_xml,
            )
            if covered_val is True:
                return True
            if covered_val is False:
                saw_false = True
        return False if saw_false else None

    # L0: whole-project generation — just check if Docker ran successfully
    if task_level == "L0":
        if exit_ok:
            return True
        if has_artifacts and language in ("go", "python", "java", "cpp"):
            return True
        return None

    return None


def _has_coverage_artifacts(language: str, cov_dir: Path, java_jacoco_xml: Path | None) -> bool:
    """Return True if coverage artifacts exist for this language."""
    if language == "go":
        return (cov_dir / "cover.out").is_file()
    if language == "python":
        return (cov_dir / "coverage.json").is_file()
    if language == "java":
        return java_jacoco_xml is not None
    if language in ("javascript", "typescript"):
        return (cov_dir / "coverage-summary.json").is_file()
    if language == "cpp":
        return (cov_dir / "lcov.info").is_file()
    return False


def _check_line_coverage(
    language: str,
    resolved: str,
    file_: str,
    target_line: int,
    cov_dir: Path,
    java_jacoco_xml: Path | None,
) -> bool | None:
    """Check if target_line in resolved file is covered."""
    from pathlib import Path as _Path
    basename = _Path(resolved).name

    if language == "go":
        gout = cov_dir / "cover.out"
        if gout.is_file():
            return go_cover_line_hit(gout, basename, target_line)
        return None

    if language == "python":
        pj = cov_dir / "coverage.json"
        if pj.is_file():
            return python_coverage_line_hit(pj, resolved, file_, target_line)
        return None

    if language == "java":
        if java_jacoco_xml is not None:
            return jacoco_line_hit(java_jacoco_xml, file_, target_line)
        return None

    if language in ("javascript", "typescript"):
        js_summary = cov_dir / "coverage-summary.json"
        if js_summary.is_file():
            return js_summary_file_hit(js_summary, basename, file_)
        return None

    if language == "cpp":
        lcov_info = cov_dir / "lcov.info"
        if lcov_info.is_file():
            return lcov_line_hit(lcov_info, file_, target_line)
        return None

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_coverage_for_project(
    project_dir: Path,
    output_dir: Path,
    artifacts_dir: Path,
    *,
    level: str | None = None,
    force: bool = False,
) -> Path:
    """Run Docker coverage for one project and write results JSON. Returns output path."""
    project_dir = project_dir.resolve()
    config = load_json(project_dir / "config.json")
    language = str(config.get("language") or "").lower()
    project_name = project_dir.name
    out_subdir = coverage_results_subdir(language)
    out_path = output_dir / out_subdir / f"{project_name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        return out_path

    stub_rows = load_stub_rows(project_dir, level)
    src_root = project_dir / "src"

    # Artifacts destination
    art_dest = artifacts_dir / out_subdir / project_name
    art_dest.mkdir(parents=True, exist_ok=True)

    def _write(payload: dict) -> Path:
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out_path

    if not stub_rows:
        return _write({
            "project": project_name,
            "language": language,
            "line_coverage_pct": None,
            "lines_covered": None,
            "lines_total": None,
            "total_tasks": 0,
            "tasks": {},
            "note": "no tasks found",
        })

    aug = augment_for_coverage(
        language=language,
        project_name=project_name,
        install_command=config.get("install_command", ""),
        test_command=config.get("test_command", ""),
        project_dir=project_dir,
    )

    if aug is None:
        tasks_out = {
            name: {"covered": None, "level": lvl, "file": stub.get("file", ""), "func": stub.get("func_name", "")}
            for name, lvl, stub in stub_rows
        }
        return _write({
            "project": project_name,
            "language": language,
            "line_coverage_pct": None,
            "lines_covered": None,
            "lines_total": None,
            "total_tasks": len(stub_rows),
            "tasks": tasks_out,
            "skip_reason": "instrumentation_not_supported",
        })

    inst_aug, test_aug = aug
    # For Go: copy blackbox *_test.go files into src/ before running instrumented go test
    # so all tests run in a single go test invocation with coverage.
    # For other languages: run blackbox tests after whitebox (they use separate test runners).
    blackbox_dir = project_dir / "blackbox_tests"
    has_blackbox = blackbox_dir.is_dir() and (blackbox_dir / "run_tests.sh").is_file()

    if language == "go":
        script = _build_go_shell(inst_aug, test_aug, has_blackbox=has_blackbox)
    else:
        script = _build_shell(
            inst_aug,
            test_aug,
            language=language,
            blackbox_dir=project_dir if has_blackbox else None,
        )

    docker_lang = "javascript" if language == "typescript" else language
    docker_image = config.get("docker_image", "")
    cmd = docker_command(project_dir, script, language=docker_lang, docker_image=docker_image)

    timeout = _docker_timeout_seconds(
        language if language != "typescript" else "javascript",
        project_name,
    )
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    cov_dir = project_dir / "coverage_out"
    exit_ok = proc.returncode == 0

    # Copy artifacts to persistent location before cleanup
    if cov_dir.is_dir():
        for f in cov_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, art_dest / f.name)

    # For Java, also copy JaCoCo XML from build output
    java_jacoco_xml: Path | None = None
    if language == "java":
        java_jacoco_xml = _find_jacoco_xml(project_dir)
        if java_jacoco_xml is not None:
            shutil.copy2(java_jacoco_xml, art_dest / java_jacoco_xml.name)
            # Point to the saved copy for consistent access
            java_jacoco_xml = art_dest / java_jacoco_xml.name

    # Extract overall line coverage percentage from saved artifacts
    line_pct, lines_covered, lines_total = extract_line_coverage_pct(language, art_dest)

    # Per-task coverage — use art_dest (persistent) instead of cov_dir (will be cleaned)
    tasks_out: dict[str, dict] = {}
    covered_by_level: dict[str, dict] = {}

    for task_name, task_level, stub in stub_rows:
        file_ = stub.get("file") or ""
        fn = stub.get("func_name") or stub.get("func") or ""

        covered_val = _check_task_coverage(
            task_name, task_level, stub, language, src_root,
            art_dest, exit_ok, java_jacoco_xml,
        )

        tasks_out[task_name] = {
            "covered": covered_val,
            "level": task_level,
            "file": file_,
            "func": fn,
        }

        if task_level not in covered_by_level:
            covered_by_level[task_level] = {"covered": 0, "uncovered": 0, "unknown": 0}
        if covered_val is None:
            covered_by_level[task_level]["unknown"] += 1
        elif covered_val:
            covered_by_level[task_level]["covered"] += 1
        else:
            covered_by_level[task_level]["uncovered"] += 1

    # Build payload
    total_covered = sum(v["covered"] for v in covered_by_level.values())
    total_uncovered = sum(v["uncovered"] for v in covered_by_level.values())
    total_unknown = sum(v["unknown"] for v in covered_by_level.values())

    payload: dict = {
        "project": project_name,
        "language": language,
        "line_coverage_pct": line_pct,
        "lines_covered": lines_covered,
        "lines_total": lines_total,
        "total_tasks": len(stub_rows),
        "covered": total_covered,
        "uncovered": total_uncovered,
        "unknown": total_unknown,
        "tasks": tasks_out,
        "docker_exit_code": proc.returncode,
        "artifacts_dir": str(art_dest),
    }

    # Add per-level breakdowns
    for lvl, counts in sorted(covered_by_level.items()):
        payload[f"{lvl.lower()}_tasks"] = counts

    # Language-specific debug info
    if language == "java":
        if java_jacoco_xml is not None:
            try:
                payload["jacoco_xml"] = java_jacoco_xml.relative_to(project_dir).as_posix()
            except ValueError:
                payload["jacoco_xml"] = str(java_jacoco_xml)
        else:
            payload["jacoco_xml"] = None
            if not exit_ok:
                payload["docker_stderr_tail"] = (proc.stderr or "")[-4000:]
    elif language in ("javascript", "typescript"):
        payload["jest_coverage_summary_present"] = (cov_dir / "coverage-summary.json").is_file()

    if not exit_ok and "docker_stderr_tail" not in payload:
        payload["docker_stderr_tail"] = (proc.stderr or "")[-4000:]

    # Cleanup coverage_out from project dir (artifacts already saved)
    shutil.rmtree(cov_dir, ignore_errors=True)

    return _write(payload)


# ---------------------------------------------------------------------------
# Project list discovery
# ---------------------------------------------------------------------------

def discover_project_list(
    *,
    project: str | None,
    language: str | None,
    all_: bool,
    level: str | None = None,
) -> list[Path]:
    if project:
        p = resolve_cli_project(project)
        if not (p / "config.json").is_file():
            raise FileNotFoundError(f"Missing config.json: {p}")
        return [p]
    if language == "javascript":
        seen: set[Path] = set()
        merged: list[Path] = []
        for p in (
            discover_projects_with_tasks("javascript", level)
            + discover_projects_with_tasks("typescript", level)
        ):
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                merged.append(p)
        return sorted(merged, key=str)
    if language:
        return discover_projects_with_tasks(language, level)
    if all_:
        return discover_projects_with_tasks(None, level)
    raise ValueError("Specify --project, --language, or --all")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def write_summary(output_dir: Path) -> Path:
    """Aggregate per-project JSON into summary.json."""
    summary: dict = {"projects": []}
    for path in sorted(output_dir.glob("*/*.json")):
        if path.name == "summary.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        summary["projects"].append({
            "path": str(path.relative_to(output_dir)),
            "language": data.get("language"),
            "project": data.get("project"),
            "line_coverage_pct": data.get("line_coverage_pct"),
            "lines_covered": data.get("lines_covered"),
            "lines_total": data.get("lines_total"),
            "total_tasks": data.get("total_tasks"),
            "covered": data.get("covered"),
            "uncovered": data.get("uncovered"),
            "unknown": data.get("unknown"),
        })
    out = output_dir / "summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
