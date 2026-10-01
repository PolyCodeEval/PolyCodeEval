"""Task — orchestrates a single L0 evaluation: workspace -> solver -> backfill -> docker run -> scoring."""

from __future__ import annotations

import json
from pathlib import Path

from .commands import resolve_l0_commands
from .runner import run
from .scoring import RESULT_SCHEMA_VERSION, SCORE_FORMULA, SCORE_SCALE, is_current_result
from .scoring.orchestrator import apply_scoring
from .solver import Solver
from .test_parser import parse_test_results, infer_compile_status
from .workspace import Workspace


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _timeout_for(language: str) -> int:
    if language in ("java", "javascript"):
        return 900
    return 600


def evaluate_task(
    task_dir: Path,
    solver: Solver,
    output_dir: Path,
    *,
    judge_provider: str = "openai",
    judge_model: str = "gpt-4o-mini",
    correctness_only: bool = False,
) -> dict:
    """Evaluate a single L0 task (blackbox only) and write the result to output_dir.

    Supports resume: returns cached results matching the current scoring schema.
    If correctness_only=True, skip the LLM judge (F/A/H) and only report Correctness.
    """
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    task_id = f"{language}/{project}/{task_dir.name}"
    result_path = output_dir / language / project / f"{task_dir.name}.json"

    if result_path.exists():
        cached = _load_json(result_path)
        if is_current_result(cached):
            return cached

    ws = Workspace(task_dir)
    try:
        ws.build()
        file_map = solver.solve(task_dir)
        ws.backfill(file_map)
        ws.inject_blackbox_tests()
        ws.inject_test_fixtures()
        ws.inject_oracle_build_config()

        install_cmd, test_cmd, _combined = resolve_l0_commands(task_dir)
        run_config = _load_json(task_dir / "run_config.json")
        timeout = run_config.get("timeout_seconds") or _timeout_for(language)

        result = run(ws, task_dir, install_cmd, test_cmd, timeout=timeout)
        result["inferred_commands"] = {
            "install": install_cmd,
            "test": test_cmd,
            "combined": False,
        }
        result["attempts"] = [{"install": install_cmd, "test": test_cmd, "combined": False}]
        result["retries"] = 0
        result["test_details"] = parse_test_results(
            result.get("stdout", "") + "\n" + result.get("stderr", ""), language
        )
        # Override passed flag: if all test cases passed, treat the task as
        # passed regardless of the process exit code.  Some test runners
        # (e.g. Mocha, GTest) exit with a non-zero code for reasons unrelated
        # to test outcomes (e.g. unhandled promises, signal handlers).
        _td = result["test_details"]
        if _td.get("total", 0) > 0 and _td.get("passed", 0) == _td.get("total", 0):
            result["passed"] = True
        result["build_status"] = infer_compile_status(
            result.get("stdout", "") + "\n" + result.get("stderr", ""),
            result.get("exit_code", -1),
            result["test_details"]["total"],
        )
        result["test_mode"] = "blackbox"

        if correctness_only:
            td = result["test_details"]
            total = td.get("total", 0)
            passed = td.get("passed", 0)
            ratio = passed / total if total > 0 else 0.0
            correctness = ratio * 5.0
            result.update({
                "result_schema_version": RESULT_SCHEMA_VERSION,
                "score_scale": SCORE_SCALE,
                "score_formula": SCORE_FORMULA,
                "radar_scores": {
                    "Correctness": correctness,
                    "Faithfulness": None,
                    "Architecture": None,
                    "Health": None,
                },
                "overall_score": correctness,
                "dimension_details": {
                    "correctness": {
                        "status": "ok",
                        "tests_passed": passed,
                        "tests_failed": td.get("failed", 0),
                        "tests_total": total,
                        "test_pass_ratio": ratio,
                    },
                },
                "judge_reviews": {},
            })
        else:
            result = apply_scoring(
                result=result,
                task_dir=task_dir,
                repo_root=ws.tmp_dir / "src",
                language=language,
                docker_image=ws.run_config.get("docker_image", ""),
                judge_provider=judge_provider,
                judge_model=judge_model,
            )

    except Exception as e:
        result = {
            "passed": False,
            "exit_code": -1,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": "",
            "error": str(e),
            "retries": 0,
            "test_mode": "blackbox",
            "result_schema_version": RESULT_SCHEMA_VERSION,
            "score_scale": SCORE_SCALE,
            "score_formula": SCORE_FORMULA,
            "radar_scores": {
                "Correctness": 0.0,
                "Faithfulness": None,
                "Architecture": None,
                "Health": None,
            },
            "overall_score": None,
            "dimension_details": {
                "correctness": {
                    "status": "ok",
                    "tests_passed": 0,
                    "tests_failed": 0,
                    "tests_total": 0,
                    "test_pass_ratio": 0.0,
                    "derived_from": "task_exception",
                },
                "faithfulness": {"status": "error", "error": str(e)},
                "architecture": {"status": "error", "error": str(e)},
                "health": {"status": "error", "error": str(e)},
            },
            "judge_reviews": {
                "faithfulness_review": "",
                "architecture_review": "",
            },
        }
    finally:
        ws.cleanup()

    result["task"] = task_id
    result["solver"] = solver.name
    _save_json(result_path, result)
    return result
