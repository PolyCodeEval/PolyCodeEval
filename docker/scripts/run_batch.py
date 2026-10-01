#!/usr/bin/env python3
"""Container-internal batch runner for PolyCodeEval.

Reads /manifest/projects.json, runs each project's test script,
and writes results to /results/results.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

JAVA_HOMES = {
    "8": "/usr/lib/jvm/java-8-openjdk",
    "11": "/usr/lib/jvm/java-11-openjdk",
    "17": "/usr/lib/jvm/java-17-openjdk",
}


def build_env(language: str, version: str) -> dict[str, str]:
    env = os.environ.copy()
    if language == "java":
        java_home = JAVA_HOMES.get(version, JAVA_HOMES["11"])
        env["JAVA_HOME"] = java_home
        env["PATH"] = f"{java_home}/bin:{env['PATH']}"
    elif language == "go":
        env.setdefault("GOPROXY", "https://goproxy.cn,direct")
        env["GOPATH"] = "/tmp/gopath"
        env["GOCACHE"] = "/tmp/go-build"
    elif language == "python":
        env.setdefault("PIP_INDEX_URL", "https://mirrors.aliyun.com/pypi/simple/")
        env.setdefault("PIP_TRUSTED_HOST", "mirrors.aliyun.com")
    elif language == "javascript":
        env.setdefault("npm_config_registry", "https://registry.npmmirror.com")
    return env


def run_project(project: dict) -> dict:
    name = project["name"]
    language = project["language"]
    version = project.get("version", "")
    workspace_path = project["workspace"]
    script = project["script"]
    timeout = project.get("timeout", 600)

    # Symlink /workspace → this project's workspace
    link = Path("/workspace")
    if link.is_symlink():
        link.unlink()
    elif link.is_dir():
        # First run: /workspace is the Dockerfile WORKDIR directory
        shutil.rmtree(link)
    link.symlink_to(workspace_path)

    env = build_env(language, version)

    # JavaScript: wrap script with `n exec <ver>` to switch Node version
    if language == "javascript" and version:
        actual_script = f"n exec {version} sh -c {json.dumps(script)}"
    else:
        actual_script = script

    start = time.monotonic()
    try:
        proc = subprocess.run(
            actual_script,
            shell=True,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        exit_code = proc.returncode
        stdout = proc.stdout[-8000:]
        stderr = proc.stderr[-4000:]
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = f"Timed out after {timeout}s"

    duration = round(time.monotonic() - start, 2)

    if link.is_symlink():
        link.unlink()

    return {
        "name": name,
        "task_id": project.get("task_id", name),
        "language": language,
        "passed": exit_code == 0,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "stdout": stdout,
        "stderr": stderr,
    }


def main() -> None:
    manifest_path = Path("/manifest/projects.json")
    if not manifest_path.exists():
        print("ERROR: /manifest/projects.json not found", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    projects = manifest["projects"]

    results = []
    total = len(projects)
    for i, project in enumerate(projects, 1):
        print(f"  [{i}/{total}] running {project['name']} ...", flush=True)
        result = run_project(project)
        status = "✓" if result["passed"] else "✗"
        print(f"  {status} {result['name']}  ({result['duration_seconds']:.1f}s)", flush=True)
        results.append(result)

    Path("/results").mkdir(parents=True, exist_ok=True)
    Path("/results/results.json").write_text(
        json.dumps({"results": results}, indent=2, ensure_ascii=False)
    )

    passed = sum(1 for r in results if r["passed"])
    print(f"\nDone: {passed}/{len(results)} passed")


if __name__ == "__main__":
    main()
