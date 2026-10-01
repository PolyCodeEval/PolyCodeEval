"""Orchestrate per-project L3 coverage runs (Docker + parsers)."""

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

from l3_coverage.commands import augment_for_coverage  # noqa: E402
from l3_coverage.parsers import (  # noqa: E402
    byte_to_line,
    go_cover_line_hit,
    jacoco_line_hit,
    js_summary_file_hit,
    python_coverage_line_hit,
)


def _is_l3_task_dir(d: Path) -> bool:
    return d.is_dir() and d.name.startswith("L3_") and (d / "task.json").is_file()


def coverage_results_subdir(config_language: str) -> str:
    """Directory under output for JSON files (typescript shares javascript)."""
    lang = (config_language or "").lower()
    if lang in ("javascript", "typescript"):
        return "javascript"
    return lang


def discover_projects_with_l3(language: str | None = None) -> list[Path]:
    projects: list[Path] = []
    for project_dir in discover_projects(language):
        tasks_dir = project_dir / "tasks"
        if not tasks_dir.is_dir():
            continue
        if any(_is_l3_task_dir(x) for x in tasks_dir.iterdir()):
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


def load_l3_stub_rows(project_dir: Path) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    tasks_dir = project_dir / "tasks"
    if not tasks_dir.is_dir():
        return rows
    for d in sorted(tasks_dir.iterdir()):
        if not _is_l3_task_dir(d):
            continue
        task = load_json(d / "task.json")
        stub = task.get("stub_info") or {}
        rows.append((d.name, stub))
    return rows


def _build_shell(install: str, test: str) -> str:
    parts = ["mkdir -p /workspace/coverage_out"]
    if install.strip():
        parts.append(f"cd /workspace && {{ {install.strip()}; }}")
    if test.strip():
        parts.append(f"cd /workspace && {{ {test.strip()}; }}")
    return "set -eu; " + " && ".join(parts)


def _iter_jacoco_report_xmls(project_dir: Path) -> list[Path]:
    """Collect jacoco.xml / jacocoTestReport.xml under the project (Maven/Gradle outputs)."""
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
    if name == "jacoco.xml" and "/coverage_out/" in sp:
        tier = 0
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


def _docker_timeout_seconds(language: str, project_name: str) -> int:
    if language == "java":
        return 900
    if language in ("javascript", "typescript"):
        if project_name == "babel-parser":
            return 3600
        return 1800
    return 600


def run_coverage_for_project(
    project_dir: Path,
    output_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Run Docker coverage for one project and write results JSON. Returns output path."""
    config = load_json(project_dir / "config.json")
    language = str(config.get("language") or "").lower()
    project_name = project_dir.name
    out_subdir = coverage_results_subdir(language)
    out_path = output_dir / out_subdir / f"{project_name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        return out_path

    stub_rows = load_l3_stub_rows(project_dir)
    src_root = project_dir / "src"

    def base_payload(**extra) -> dict:
        tasks_out: dict[str, dict] = {}
        covered_n = uncovered_n = unknown_n = 0
        for task_name, stub in stub_rows:
            fn = stub.get("func_name") or stub.get("func") or ""
            file_ = stub.get("file") or ""
            tasks_out[task_name] = {
                "covered": None,
                "file": file_,
                "func": fn,
            }
            unknown_n += 1
        payload = {
            "project": project_name,
            "language": language,
            "total_tasks": len(stub_rows),
            "covered": covered_n,
            "uncovered": uncovered_n,
            "unknown": unknown_n,
            "tasks": tasks_out,
        }
        payload.update(extra)
        return payload

    if not stub_rows:
        payload = base_payload(note="no L3 tasks")
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out_path

    if language == "cpp":
        payload = base_payload(note="cpp coverage not implemented (always unknown)")
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out_path

    aug = augment_for_coverage(
        language=language,
        project_name=project_name,
        install_command=config.get("install_command", ""),
        test_command=config.get("test_command", ""),
        project_dir=project_dir,
    )

    if aug is None:
        reason = "skipped_instrumentation"
        if project_name in {"nanoid", "minimist", "mitt"} and language in ("javascript", "typescript"):
            reason = "no_standard_coverage_tool"
        elif language == "java":
            reason = "unsupported_java_build"
        payload = base_payload(skip_reason=reason)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out_path

    inst_aug, test_aug = aug
    script = _build_shell(inst_aug, test_aug)
    docker_lang = "javascript" if language == "typescript" else language
    cmd = docker_command(project_dir, script, language=docker_lang)

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

    java_jacoco_xml: Path | None = None
    if language == "java" and exit_ok:
        java_jacoco_xml = _find_jacoco_xml(project_dir)

    js_summary_path = cov_dir / "coverage-summary.json"
    jest_summary_ok = language in ("javascript", "typescript") and exit_ok and js_summary_path.is_file()

    tasks_out: dict[str, dict] = {}
    covered_n = uncovered_n = unknown_n = 0

    for task_name, stub in stub_rows:
        file_ = stub.get("file") or ""
        fn = stub.get("func_name") or ""
        body_start = stub.get("body_start_byte")
        if not file_ or body_start is None:
            tasks_out[task_name] = {"covered": None, "file": file_, "func": fn}
            unknown_n += 1
            continue

        if not exit_ok:
            tasks_out[task_name] = {"covered": None, "file": file_, "func": fn}
            unknown_n += 1
            continue

        resolved = _resolve_file(src_root, file_) if src_root.is_dir() else file_
        src_path = src_root / resolved
        if not src_path.is_file():
            tasks_out[task_name] = {"covered": None, "file": file_, "func": fn}
            unknown_n += 1
            continue

        src_bytes = src_path.read_bytes()
        target_line = byte_to_line(src_bytes, int(body_start))
        basename = Path(resolved).name

        covered_val: bool | None = None
        if language == "go":
            gout = cov_dir / "cover.out"
            if gout.is_file():
                covered_val = go_cover_line_hit(gout, basename, target_line)
        elif language == "python":
            pj = cov_dir / "coverage.json"
            if pj.is_file():
                covered_val = python_coverage_line_hit(pj, resolved, file_, target_line)
        elif language == "java":
            if java_jacoco_xml is not None:
                covered_val = jacoco_line_hit(java_jacoco_xml, file_, target_line)
        elif language in ("javascript", "typescript"):
            if jest_summary_ok:
                covered_val = js_summary_file_hit(js_summary_path, basename, file_)

        if covered_val is None:
            unknown_n += 1
        elif covered_val:
            covered_n += 1
        else:
            uncovered_n += 1

        tasks_out[task_name] = {"covered": covered_val, "file": file_, "func": fn}

    payload = {
        "project": project_name,
        "language": language,
        "total_tasks": len(stub_rows),
        "covered": covered_n,
        "uncovered": uncovered_n,
        "unknown": unknown_n,
        "tasks": tasks_out,
        "docker_exit_code": proc.returncode,
    }
    if language == "java":
        if java_jacoco_xml is not None:
            try:
                payload["jacoco_xml"] = java_jacoco_xml.relative_to(project_dir).as_posix()
            except ValueError:
                payload["jacoco_xml"] = str(java_jacoco_xml)
        else:
            payload["jacoco_xml"] = None
            probe = _iter_jacoco_report_xmls(project_dir)
            payload["jacoco_xml_probe"] = [
                p.relative_to(project_dir).as_posix() for p in probe[:30]
            ]
            out = proc.stdout or ""
            err = proc.stderr or ""
            if out.strip():
                payload["docker_stdout_tail"] = out[-12000:]
            if err.strip() and "docker_stderr_tail" not in payload:
                payload["docker_stderr_tail"] = err[-8000:]
    if language in ("javascript", "typescript"):
        payload["jest_coverage_summary_present"] = jest_summary_ok
    if not exit_ok and "docker_stderr_tail" not in payload:
        payload["docker_stderr_tail"] = (proc.stderr or "")[-4000:]

    shutil.rmtree(cov_dir, ignore_errors=True)

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def discover_project_list(
    *,
    project: str | None,
    language: str | None,
    all_: bool,
) -> list[Path]:
    if project:
        p = resolve_cli_project(project)
        if not (p / "config.json").is_file():
            raise FileNotFoundError(f"Missing config.json: {p}")
        return [p]
    if language == "javascript":
        seen: set[Path] = set()
        merged: list[Path] = []
        for p in discover_projects_with_l3("javascript") + discover_projects_with_l3("typescript"):
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                merged.append(p)
        return sorted(merged, key=str)
    if language:
        return discover_projects_with_l3(language)
    if all_:
        return discover_projects_with_l3(None)
    raise ValueError("Specify --project, --language, or --all")


def write_summary(output_dir: Path) -> Path:
    """Aggregate per-project JSON into summary.json."""
    summary: dict = {"projects": []}
    for path in sorted(output_dir.glob("*/*.json")):
        if path.name == "summary.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        summary["projects"].append(
            {
                "path": str(path.relative_to(output_dir)),
                "language": data.get("language"),
                "project": data.get("project"),
                "total_tasks": data.get("total_tasks"),
                "covered": data.get("covered"),
                "uncovered": data.get("uncovered"),
                "unknown": data.get("unknown"),
            }
        )
    out = output_dir / "summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
