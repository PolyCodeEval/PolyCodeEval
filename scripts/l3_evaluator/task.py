"""Task — orchestrates a single L3 evaluation: workspace -> solver -> backfill -> docker run."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from l0_evaluator.test_parser import parse_test_results

from .runner import ProjectContainer, run
from .solver import Solver
from .workspace import (
    Workspace,
    _format_brace_language_backfill,
    _format_python_backfill,
    _stub_line_bounds,
    _resolve_file,
)


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def evaluate_task(
    task_dir: Path,
    solver: Solver,
    output_dir: Path,
    *,
    container: ProjectContainer | None = None,
    test_mode: str = "both",
) -> dict:
    """Evaluate a single L3 task and write the result to output_dir.

    If *container* is provided, uses the long-running project container
    (docker exec) instead of spinning up a new container per task.
    Supports resume: if the result file already exists, it is returned as-is.
    """
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    task_id = f"{language}/{project}/{task_dir.name}"
    result_path = output_dir / language / project / f"{task_dir.name}.json"

    if result_path.exists():
        return _load_json(result_path)

    timeout = 900 if language == "java" else 600

    if container is not None:
        result = _evaluate_with_container(task_dir, solver, container, timeout=timeout)
    else:
        result = _evaluate_standalone(task_dir, solver, timeout=timeout, test_mode=test_mode)

    result["task"] = task_id
    result["solver"] = solver.name
    result["test_mode"] = test_mode
    _attach_scoring(result, language)
    _save_json(result_path, result)
    return result


def _attach_scoring(result: dict, language: str) -> None:
    """Attach compile/test-based partial-credit scoring to an L3 result."""
    stdout = result.get("stdout", "") or ""
    stderr = result.get("stderr", "") or ""
    # Try stdout first; if no tests found, try stderr (Jest writes to stderr)
    test_details = parse_test_results(stdout, language)
    if not test_details.get("total"):
        test_details = parse_test_results(stderr, language)
    result["test_details"] = test_details

    compile_passed = bool(result.get("passed")) or test_details.get("total", 0) > 0
    result["compile_passed"] = compile_passed
    result["full_passed"] = bool(result.get("passed"))

    if not compile_passed:
        result["test_pass_ratio"] = 0.0
        result["compile_score"] = 0.0
        result["test_score"] = 0.0
        result["score"] = 0.0
        return

    total = test_details.get("total", 0)
    passed = test_details.get("passed", 0)
    test_ratio = (passed / total) if total else 0.0
    result["test_pass_ratio"] = round(test_ratio, 4)
    result["compile_score"] = 0.5
    result["test_score"] = round(0.5 * test_ratio, 4)
    result["score"] = round(result["compile_score"] + result["test_score"], 4)


def _evaluate_standalone(task_dir: Path, solver: Solver, *, timeout: int, test_mode: str = "both") -> dict:
    ws = Workspace(task_dir)
    try:
        ws.build()
        function_body = solver.solve(task_dir)
        ws.backfill(function_body)
        if task_dir.parents[2].name == "python":
            debug_root = Path("output/backfill_runtime_debug")
            debug_path = debug_root / task_dir.parents[2].name / task_dir.parents[1].name / f"{task_dir.name}.py"
            ws.export_last_backfilled(debug_path)
        return run(ws, task_dir, timeout=timeout, test_mode=test_mode)
    except Exception as e:
        return {
            "passed": False,
            "exit_code": -1,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": "",
            "error": str(e),
        }
    finally:
        ws.cleanup()


def _evaluate_with_container(
    task_dir: Path,
    solver: Solver,
    container: ProjectContainer,
    *,
    timeout: int,
) -> dict:
    try:
        task_json = _load_json(task_dir / "task.json")
        run_config = _load_json(task_dir / "run_config.json")
        stub_info = task_json["stub_info"]
        src_dir = (task_dir / run_config["src_dir"]).resolve()
        resolved = _resolve_file(src_dir, stub_info["file"])

        function_body = solver.solve(task_dir)

        hollowed = (task_dir / "hollowed_files" / stub_info["file"]).read_bytes()
        hollowed_text = hollowed.decode("utf-8")
        original = (src_dir / resolved).read_bytes()
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

        tmp_file = Path(tempfile.mktemp(prefix="pce_backfill_", suffix=Path(resolved).suffix))
        try:
            tmp_file.write_bytes(filled)
            return container.exec_task(
                tmp_file, resolved, original, timeout=timeout,
            )
        finally:
            tmp_file.unlink(missing_ok=True)
    except Exception as e:
        return {
            "passed": False,
            "exit_code": -1,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": "",
            "error": str(e),
        }
