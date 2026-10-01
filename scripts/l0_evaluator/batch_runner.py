"""Batch runner — evaluates all tasks in a single Docker container invocation."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_DOCKER_DIR = str(Path(__file__).resolve().parents[2] / "docker")
if _DOCKER_DIR not in sys.path:
    sys.path.insert(0, _DOCKER_DIR)

from runner_lib import VERSION_MAP, build_script, run_batch  # noqa: E402

from .commands import resolve_l0_commands
from .scoring import is_current_result
from .scoring.orchestrator import apply_scoring
from .solver import Solver
from .test_parser import parse_test_results
from .workspace import Workspace


def _resolve_version(docker_image: str) -> tuple[str, str]:
    return VERSION_MAP.get(docker_image, ("", ""))


def _build_project_entry(task_dir: Path, ws: Workspace) -> dict:
    """Build a manifest project entry for one task."""
    language = task_dir.parents[2].name
    project = task_dir.parents[1].name
    task_name = task_dir.name
    ws_name = f"{language}__{project}__{task_name}"

    run_config = ws.run_config
    _, version = _resolve_version(run_config.get("docker_image", ""))

    install_cmd, test_cmd, _combined = resolve_l0_commands(task_dir)
    script = build_script(install_cmd, test_cmd)
    timeout = 900 if language == "java" else 600

    return {
        "name": ws_name,
        "language": language,
        "version": version,
        "workspace": str(ws.tmp_dir),
        "script": script,
        "timeout": timeout,
        "task_id": f"{language}/{project}/{task_name}",
    }


def evaluate_batch(
    task_dirs: list[Path],
    solver: Solver,
    output_dir: Path,
    *,
    judge_provider: str = "openai",
    judge_model: str = "gpt-4o-mini",
) -> list[dict]:
    """Evaluate all tasks in a single Docker container. Returns list of result dicts."""
    workspace_list: list[Workspace] = []
    project_entries: list[dict] = []
    task_index: dict[str, tuple[Path, Workspace]] = {}

    for task_dir in task_dirs:
        language = task_dir.parents[2].name
        project = task_dir.parents[1].name
        task_name = task_dir.name
        result_path = output_dir / language / project / f"{task_name}.json"

        if result_path.exists():
            cached = json.loads(result_path.read_text())
            if is_current_result(cached):
                print(f"  [skip] {language}/{project}/{task_name} (cached)", flush=True)
                continue

        print(f"  [prep] {language}/{project}/{task_name} ...", end=" ", flush=True)
        ws = Workspace(task_dir)
        ws.build()
        print("build", end=" ", flush=True)
        file_map = solver.solve(task_dir)
        ws.backfill(file_map)
        print("backfill", end=" ", flush=True)
        ws.inject_blackbox_tests()
        workspace_list.append(ws)
        entry = _build_project_entry(task_dir, ws)
        project_entries.append(entry)
        task_index[entry["task_id"]] = (task_dir, ws)
        print("ready", flush=True)

    results: list[dict] = []

    if project_entries:
        print(f"\n  [batch] launching Docker container with {len(project_entries)} tasks ...", flush=True)
        total_timeout = sum(e["timeout"] for e in project_entries) + 300
        batch_results = run_batch(project_entries, timeout=total_timeout)
        print(f"  [batch] container finished, processing {len(batch_results)} results ...", flush=True)

        for raw in batch_results:
            task_id = raw["task_id"]
            parts = task_id.split("/", 2)
            language, project, task_name = parts[0], parts[1], parts[2]

            result = {
                "task": task_id,
                "solver": solver.name,
                "passed": raw["passed"],
                "exit_code": raw["exit_code"],
                "duration_seconds": raw["duration_seconds"],
                "stdout": raw.get("stdout", ""),
                "stderr": raw.get("stderr", ""),
                "test_details": parse_test_results(raw.get("stdout", ""), language),
                "inferred_commands": {"install": "", "test": "", "combined": False},
                "attempts": [{"install": "", "test": ""}],
                "retries": 0,
                "test_mode": "blackbox",
            }
            matching_task, matching_ws = task_index[task_id]
            result = apply_scoring(
                result=result,
                task_dir=matching_task,
                repo_root=matching_ws.tmp_dir / "src",
                language=language,
                docker_image=matching_ws.run_config.get("docker_image", ""),
                judge_provider=judge_provider,
                judge_model=judge_model,
            )

            result_path = output_dir / language / project / f"{task_name}.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n"
            )
            results.append(result)

    for task_dir in task_dirs:
        language = task_dir.parents[2].name
        project = task_dir.parents[1].name
        task_name = task_dir.name
        result_path = output_dir / language / project / f"{task_name}.json"
        if result_path.exists():
            cached = json.loads(result_path.read_text())
            tid = f"{language}/{project}/{task_name}"
            if not any(r["task"] == tid for r in results) and is_current_result(cached):
                results.append(cached)

    for ws in workspace_list:
        ws.cleanup()

    return results
