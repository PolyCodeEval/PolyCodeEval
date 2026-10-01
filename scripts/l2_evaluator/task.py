"""Task — evaluates a single L2 task using a long-running ProjectContainer."""

from __future__ import annotations

import json
from pathlib import Path

from l0_evaluator.test_parser import parse_test_results

from .runner import ProjectContainer
from .solver import Solver
from .workspace import Workspace


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _get_timeout(task_dir: Path) -> int:
    lang = task_dir.parents[2].name
    project_dir = task_dir.parents[1]
    cfg_path = project_dir / "config.json"
    if cfg_path.exists():
        cfg = _load_json(cfg_path)
        t = cfg.get("timeout_seconds")
        if t:
            return int(t)
    if lang in ("java", "javascript"):
        return 900
    return 600


def evaluate_task(
    task_dir: Path,
    solver: Solver,
    output_dir: Path,
    container: ProjectContainer,
    *,
    test_mode: str = "both",
) -> dict:
    """Evaluate a single L2 task using the shared project container."""
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    task_id = f"{language}/{project}/{task_dir.name}"
    result_path = output_dir / language / project / f"{task_dir.name}.json"

    if result_path.exists():
        return _load_json(result_path)

    timeout = _get_timeout(task_dir)
    ws = Workspace(task_dir)

    try:
        # Get original file bytes for restoration after test
        container_rel, original_bytes = ws.get_target_info()

        # Solve (oracle reads from src; precomputed reads from generated_outputs)
        file_content = solver.solve(task_dir)

        # Write solver output to a temp file
        tmp_file, _ = ws.make_backfilled_file(file_content)

        try:
            result = container.exec_task(
                tmp_file, container_rel, original_bytes, timeout=timeout
            )
        finally:
            tmp_file.unlink(missing_ok=True)

    except Exception as e:
        result = {
            "passed": False,
            "exit_code": -1,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": "",
            "error": str(e),
        }
    finally:
        ws.cleanup()

    result["task"] = task_id
    result["solver"] = solver.name
    result["test_mode"] = test_mode
    _attach_scoring(result, language)
    _save_json(result_path, result)
    return result


def _attach_scoring(result: dict, language: str) -> None:
    stdout = result.get("stdout", "") or ""
    stderr = result.get("stderr", "") or ""
    # Try stdout first; if no tests found, fall back to stderr (Jest writes to stderr)
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
